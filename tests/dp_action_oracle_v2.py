# -*- coding: utf-8 -*-
"""dp_action_oracle_v2.py — 决策点动作函数的独立第二参考实现（交叉验证用）。

角色与依据
----------
本文件由"独立第二实现者"编写，用于交叉验证流程的第二实现席位：

* 依据来源：仅《outputs/决策点规格定义.md》（重点 §1.3 人类决策动作语义、
  §4.3 状态机）+ 任务下达方给出的函数契约（is_terminal / apply_decision / run_case）。
* 隔离声明：实现过程中**未读取** app/、tests/（本文件除外）、rounds/、scripts/、
  schema/ 下任何文件，不参考任何生产实现或其他 oracle 实现。
* 目的：与第一实现者版本、生产实现三方比对，暴露规格误解。

已知不可复现行为
----------------
* timestamp：生产实现在 opts 未提供 timestamp 时自动生成当前时间（不可复现）。
  比对约定：opts 无 timestamp 键 → 输出 humanDecision 不含 timestamp 字段；
  显式给出 → 原样保留（包括 None）。

SPEC-AMBIGUITIES（规格未定义点，自行决策）
------------------------------------------
A1. "dp 必须是对象"的对象边界：
    初版决策：仅 Python dict（含子类）算对象，list/str/数字/None 均为
    E_DP_NOT_OBJECT。**交叉验证裁决（2026-09-01，D-015 对齐生产契约）**：
    JS 守卫是 `!dp || typeof dp !== "object"`——数组也算 object，会放行进
    状态检查（落 E_NOT_PENDING）。改为 dict/list 视为对象，其余拒绝。

A2. opts 为 None / 缺失 / 非 dict 的行为：
    决策：None 与缺失等价于 {}；其他非 dict 值（list/str/数字等）宽松处理为
    {}（所有字段视作缺失），不报错。理由：契约明确 opts=None 合法；正常语料
    只有 dict 与缺失两种，宽松回退不会引入正常语料分歧。

A3. comment 的"转字符串"渲染语义：
    决策：None 视作"无 comment"（转空串，字段不写入）——与生产契约一致
    （JS 守卫显式排除 null，String(null) 语义在 comment 上不可达）；其余非
    字符串按 JS String() 渲染：bool→"true"/"false"，整数→十进制，浮点整数值
    去掉".0"，list 按 JS Array.prototype.toString 递归以","连接（None 元素
    渲染为空段），dict→"[object Object]"。

A4. modifications 的"缺失/空值"判定：
    初版决策：键缺失、None、转字符串去空白后为空串三种都判
    E_MODIFIED_REQUIRES_MODIFICATIONS。**交叉验证裁决（2026-09-01，D-015）**：
    生产实现对 modifications 无 null 排除守卫（与 comment 不对称）——
    键缺失 → ""（拒绝）；键存在且为 null → String(null)="null" 非空 →
    **通过**且 modifications="null"。改为区分"键缺失"与"显式 null"。

A5. decidedBy 的"空值"判定：
    初版决策：缺失/None/非字符串/空白字符串 → 默认"估价师"。
    **交叉验证裁决（2026-09-01，D-015）**：生产实现是 `opts.decidedBy || 默认`
    （falsy 语义）——仅缺失/None/""/0/false 等假值回退；空白串 " " 为真值
    **原样保留**，非字符串真值（如 42）也原样保留。改为 falsy 回退语义。

A6. timestamp 的显式 None：
    决策：opts 中存在 timestamp 键即原样写入（哪怕值为 None）；只有键不存在
    才省略字段。理由：比对约定只区分"给没给"，给了就"原样保留"。

A7. 终结状态判定的类型严格性：
    决策：仅字符串精确相等（大小写敏感）"approved"/"modified" 为终结；
    None、非字符串、大小写不符一律非终结。理由：契约明文，无歧义，列出仅为
    完整性。

A8. 守卫后两类内容校验的相对顺序：
    决策：action=modified 时先查 modifications（E_MODIFIED_REQUIRES_
    MODIFICATIONS），action=rejected 时查 comment（E_REJECTED_REQUIRES_
    COMMENT）。二者互斥（action 不同时为两者），顺序实际无冲突，列出仅为
    明确实现路径。
"""

from copy import deepcopy

ACTIONS = ("approved", "modified", "rejected")
TERMINAL_STATUSES = ("approved", "modified")

DEFAULT_DECIDED_BY = "估价师"


def is_terminal(status):
    """判断状态是否终结。approved/modified 为终结，其余（含 None/非字符串）非终结。"""
    return isinstance(status, str) and status in TERMINAL_STATUSES


def _js_string(value, null_text=""):
    """按 JS String() 语义渲染；value 为 None 时按 null_text 渲染
    （comment 场景传 ""——null 被守卫排除；modifications 场景传 "null"——
    生产实现无 null 排除守卫，String(null)="null"，见 A4 裁决）。"""
    if value is None:
        return null_text
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:
            return "NaN"
        if value == float("inf"):
            return "Infinity"
        if value == float("-inf"):
            return "-Infinity"
        if value.is_integer():
            return str(int(value))
        return repr(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ",".join("" if v is None else _js_string(v) for v in value)
    if isinstance(value, dict):
        return "[object Object]"
    return str(value)


def apply_decision(dp, action, opts=None):
    """把人类决策应用到决策点上，返回 {"ok", "code", "dp"} 规范结果。"""
    # 守卫 1：dp 必须是对象（A1 裁决：JS typeof 数组也算 object → 放行进状态检查）
    if not isinstance(dp, (dict, list)):
        return {"ok": False, "code": "E_DP_NOT_OBJECT", "dp": None}

    # 守卫 2：action 必须是三种合法动作之一（大小写敏感，A7 同口径）
    if not (isinstance(action, str) and action in ACTIONS):
        return {"ok": False, "code": "E_BAD_ACTION", "dp": None}

    # 守卫 3：dp.status 必须是 pending（已决策的 dp 不可重复决策）；
    # list 形态的 dp 无 status → 非 pending → E_NOT_PENDING（A1 裁决）
    dp_status = dp.get("status") if isinstance(dp, dict) else None
    if dp_status != "pending":
        return {"ok": False, "code": "E_NOT_PENDING", "dp": None}

    # opts 规范化（A2）
    if not isinstance(opts, dict):
        opts = {}

    human_decision = {"action": action}

    # decidedBy（A5 裁决：JS `||` falsy 语义——仅假值回退，空白串/真值原样保留）
    decided_by = opts.get("decidedBy")
    human_decision["decidedBy"] = decided_by if decided_by else DEFAULT_DECIDED_BY

    # timestamp（比对约定 + A6）：键存在才写入，原样保留
    if "timestamp" in opts:
        human_decision["timestamp"] = opts["timestamp"]

    # comment（A3）：转字符串去前后空白，非空才写入
    comment = _js_string(opts.get("comment")).strip()
    if action == "rejected" and comment == "":
        return {"ok": False, "code": "E_REJECTED_REQUIRES_COMMENT", "dp": None}
    if comment != "":
        human_decision["comment"] = comment

    # modifications（A4 裁决）：仅 action=modified。键缺失 → ""（拒绝）；
    # 键存在且为 null → "null" 非空 → 通过（生产实现无 null 排除守卫，与 comment 不对称）
    if action == "modified":
        if "modifications" in opts:
            modifications = _js_string(opts["modifications"], null_text="null").strip()
        else:
            modifications = ""
        if modifications == "":
            return {"ok": False, "code": "E_MODIFIED_REQUIRES_MODIFICATIONS", "dp": None}
        human_decision["modifications"] = modifications

    # 成功：深拷贝出参，不改入参
    result = deepcopy(dp)
    result["status"] = action
    result["humanDecision"] = human_decision
    return {"ok": True, "code": None, "dp": result}


def run_case(case):
    """批量差分执行入口。"""
    return {
        "kind": case["kind"],
        "terminal": is_terminal(case.get("status")),
        "apply": apply_decision(
            case.get("dp"),
            case.get("action"),
            case["opts"] if "opts" in case else None,
        ),
    }


if __name__ == "__main__":
    failures = []

    def check(name, cond):
        if cond:
            print("PASS  " + name)
        else:
            failures.append(name)
            print("FAIL  " + name)

    def make_dp(status="pending", extra=None):
        dp = {"id": "DP1", "name": "估价事项确认", "status": status}
        if extra:
            dp.update(extra)
        return dp

    # 1. 正常 approved：状态转换 + decidedBy 默认 + 无 timestamp/comment
    r = apply_decision(make_dp(), "approved")
    check("approved ok", r["ok"] is True and r["code"] is None)
    check("approved status", r["dp"]["status"] == "approved")
    check("approved humanDecision", r["dp"]["humanDecision"] ==
          {"action": "approved", "decidedBy": "估价师"})
    check("approved no timestamp/comment",
          "timestamp" not in r["dp"]["humanDecision"] and
          "comment" not in r["dp"]["humanDecision"])

    # 2. 正常 modified：modifications 写入
    r = apply_decision(make_dp(), "modified",
                       {"modifications": "面积改为套内 100 m²", "comment": "口径修正"})
    check("modified ok", r["ok"] and r["dp"]["status"] == "modified")
    check("modified fields", r["dp"]["humanDecision"]["modifications"] ==
          "面积改为套内 100 m²" and r["dp"]["humanDecision"]["comment"] == "口径修正")

    # 3. modified 缺 modifications → E_MODIFIED_REQUIRES_MODIFICATIONS
    r = apply_decision(make_dp(), "modified", {})
    check("modified missing mods",
          not r["ok"] and r["code"] == "E_MODIFIED_REQUIRES_MODIFICATIONS" and r["dp"] is None)

    # 4. modified 空白 modifications → 同错误；None 按裁决通过且为 "null"（A4）
    r = apply_decision(make_dp(), "modified", {"modifications": "   "})
    check("modified blank mods",
          not r["ok"] and r["code"] == "E_MODIFIED_REQUIRES_MODIFICATIONS")
    r = apply_decision(make_dp(), "modified", {"modifications": None})
    check("modified None mods -> 'null' passes (A4 裁决)",
          r["ok"] and r["dp"]["humanDecision"]["modifications"] == "null")

    # 5. rejected 带 comment → ok
    r = apply_decision(make_dp(), "rejected", {"comment": "实例C信源T2不可靠"})
    check("rejected ok", r["ok"] and r["dp"]["status"] == "rejected")
    check("rejected no mods field", "modifications" not in r["dp"]["humanDecision"])

    # 6. rejected 缺 comment → E_REJECTED_REQUIRES_COMMENT
    r = apply_decision(make_dp(), "rejected", {})
    check("rejected no comment",
          not r["ok"] and r["code"] == "E_REJECTED_REQUIRES_COMMENT")

    # 7. rejected 纯空白 comment → 同错误
    r = apply_decision(make_dp(), "rejected", {"comment": " \t\n "})
    check("rejected blank comment",
          not r["ok"] and r["code"] == "E_REJECTED_REQUIRES_COMMENT")

    # 8. 重复决策（status=approved）→ E_NOT_PENDING
    r = apply_decision(make_dp(status="approved"), "approved")
    check("repeat approved", not r["ok"] and r["code"] == "E_NOT_PENDING")
    r = apply_decision(make_dp(status="modified"), "approved")
    check("repeat modified", not r["ok"] and r["code"] == "E_NOT_PENDING")
    r = apply_decision(make_dp(status="rejected"), "approved", {"comment": "x"})
    check("repeat rejected", not r["ok"] and r["code"] == "E_NOT_PENDING")
    r = apply_decision(make_dp(status="PENDING"), "approved")
    check("status case-sensitive pending", not r["ok"] and r["code"] == "E_NOT_PENDING")
    r = apply_decision({"id": "DP1"}, "approved")
    check("status missing", not r["ok"] and r["code"] == "E_NOT_PENDING")

    # 9. 非法 action：未知值 / 大小写不符 / 非字符串
    for bad in ("approve", "APPROVED", "", None, 1, ["approved"]):
        r = apply_decision(make_dp(), bad)
        check("bad action %r" % (bad,),
              not r["ok"] and r["code"] == "E_BAD_ACTION")

    # 10. dp 非对象：None / 字符串 / 数字（A1 裁决：list 也算对象 → E_NOT_PENDING）
    for bad in (None, "dp", 42):
        r = apply_decision(bad, "approved")
        check("dp not object %r" % (bad,),
              not r["ok"] and r["code"] == "E_DP_NOT_OBJECT")
    r = apply_decision([], "approved")
    check("dp list -> E_NOT_PENDING (A1 裁决)",
          not r["ok"] and r["code"] == "E_NOT_PENDING")

    # 11. comment 前后空白 trim
    r = apply_decision(make_dp(), "rejected", {"comment": "  面积口径错误  "})
    check("comment trimmed", r["ok"] and
          r["dp"]["humanDecision"]["comment"] == "面积口径错误")

    # 12. decidedBy：默认值 / 显式 / falsy 回退（A5 裁决：空白串为真值，原样保留）
    r = apply_decision(make_dp(), "approved")
    check("decidedBy default", r["dp"]["humanDecision"]["decidedBy"] == "估价师")
    r = apply_decision(make_dp(), "approved", {"decidedBy": "张估价师"})
    check("decidedBy explicit", r["dp"]["humanDecision"]["decidedBy"] == "张估价师")
    r = apply_decision(make_dp(), "approved", {"decidedBy": "   "})
    check("decidedBy blank kept (A5 裁决)",
          r["dp"]["humanDecision"]["decidedBy"] == "   ")

    # 13. timestamp：缺省省略 / 显式保留（含 None，A6）
    r = apply_decision(make_dp(), "approved")
    check("timestamp omitted", "timestamp" not in r["dp"]["humanDecision"])
    r = apply_decision(make_dp(), "approved", {"timestamp": "2026-09-01T10:00:00+08:00"})
    check("timestamp kept", r["dp"]["humanDecision"]["timestamp"] ==
          "2026-09-01T10:00:00+08:00")
    r = apply_decision(make_dp(), "approved", {"timestamp": None})
    check("timestamp explicit None kept",
          "timestamp" in r["dp"]["humanDecision"] and
          r["dp"]["humanDecision"]["timestamp"] is None)

    # 14. is_terminal 边界
    check("terminal approved/modified",
          is_terminal("approved") and is_terminal("modified"))
    for s in ("rejected", "pending", "PENDING", "APPROVED", "", None, 123, ["approved"], {}):
        check("terminal not %r" % (s,), is_terminal(s) is False)

    # 15. 非字符串 comment 按 A3 语义
    r = apply_decision(make_dp(), "rejected", {"comment": None})
    check("comment None absent",
          not r["ok"] and r["code"] == "E_REJECTED_REQUIRES_COMMENT")
    r = apply_decision(make_dp(), "rejected", {"comment": 42})
    check("comment int -> '42'", r["ok"] and
          r["dp"]["humanDecision"]["comment"] == "42")
    r = apply_decision(make_dp(), "rejected", {"comment": True})
    check("comment bool -> 'true'", r["ok"] and
          r["dp"]["humanDecision"]["comment"] == "true")
    r = apply_decision(make_dp(), "rejected", {"comment": [1, None, "a"]})
    check("comment list -> '1,,a'", r["ok"] and
          r["dp"]["humanDecision"]["comment"] == "1,,a")
    r = apply_decision(make_dp(), "rejected", {"comment": {"k": 1}})
    check("comment dict -> '[object Object]'", r["ok"] and
          r["dp"]["humanDecision"]["comment"] == "[object Object]")
    r = apply_decision(make_dp(), "rejected", {"comment": 3.0})
    check("comment float integral -> '3'", r["ok"] and
          r["dp"]["humanDecision"]["comment"] == "3")

    # 16. 非字符串 modifications 按 A3 语义
    r = apply_decision(make_dp(), "modified", {"modifications": 100})
    check("mods int -> '100'", r["ok"] and
          r["dp"]["humanDecision"]["modifications"] == "100")
    r = apply_decision(make_dp(), "modified", {"modifications": 0})
    check("mods falsy int -> '0' ok", r["ok"] and
          r["dp"]["humanDecision"]["modifications"] == "0")

    # 17. 入参不被修改 + 出参为深拷贝
    dp = make_dp(extra={"evidence": [{"item": "证", "src": ["a", "b"]}]})
    snapshot = deepcopy(dp)
    r = apply_decision(dp, "rejected", {"comment": "x"})
    check("input untouched", dp == snapshot)
    check("output is copy", r["dp"] is not dp and
          r["dp"]["evidence"] is not dp["evidence"])
    r["dp"]["evidence"][0]["src"].append("c")
    check("deep copy independent", dp["evidence"][0]["src"] == ["a", "b"])

    # 18. opts 非法形态宽松回退（A2）
    r = apply_decision(make_dp(), "approved", None)
    check("opts None ok", r["ok"])
    r = apply_decision(make_dp(), "approved", "not-a-dict")
    check("opts non-dict lenient", r["ok"] and
          r["dp"]["humanDecision"]["decidedBy"] == "估价师")

    # 19. run_case 结构
    case = {"kind": "normal_approved", "dp": make_dp(), "action": "approved",
            "status": "approved"}
    rc = run_case(case)
    check("run_case keys", set(rc.keys()) == {"kind", "terminal", "apply"} and
          rc["kind"] == "normal_approved" and rc["terminal"] is True and
          rc["apply"]["ok"] is True)
    case2 = {"kind": "no_opts_key", "dp": make_dp(), "action": "rejected"}
    rc2 = run_case(case2)
    check("run_case opts missing == None",
          rc2["apply"]["code"] == "E_REJECTED_REQUIRES_COMMENT")
    case3 = {"kind": "terminal_rejected", "dp": None, "action": None,
             "status": "rejected"}
    rc3 = run_case(case3)
    check("run_case rejected non-terminal", rc3["terminal"] is False)

    if failures:
        print("\nSELF-TEST FAILED: %d failure(s): %s" % (len(failures), failures))
        raise SystemExit(1)
    print("\nSELF-TEST OK: all assertions passed")
