"""
dp_action_oracle.py — applyDecision / isTerminal 的规格参考实现（Round 7，测试专用）

背景：这两块（决策动作 + 状态机）此前零机械验证（`tests/test_dp_core.js` 只有手写断言）。
与 `dp_chain_oracle.py` 同一纪律：**按规格实现，不得照抄 app/js/dp-core.js**，
分歧即发现。Python 端没有这两个函数的生产实现，故本文件是差分的第二端（D-012 路线）。

依据：
- 《决策点规格定义》1.3 人类决策动作语义（批准/调整/驳回；modified 必填 modifications）
- 4.3 状态机：pending ─┬─ approved（终结）
                       ├─ modified（终结）
                       └─ rejected（非终结 → 生成新 DP）
- JS 契约注释（applyDecision 的守卫顺序与 humanDecision 字段）

**已知非规格行为（JS 实测，oracle 对齐，仅记录）**：
1. 缺 timestamp 时 JS 用 `new Date().toISOString()`（不可复现）→ 比对时两端都不带该字段；
2. comment/modifications 先过 JS `String()` 再 trim：null → "null"、true → "true"、
   2.0 → "2"，故用 `_js_str()` 复现；
3. 驳回必填 comment 是"编排协议强化"（规格 4.2 要求新 DP 回应否决原因），非规格原文。
"""
import copy

ACTIONS = ("approved", "modified", "rejected")
TERMINAL_STATUSES = ("approved", "modified")


def _js_str(x):
    """复现 JS String() 渲染（null → "null"、true → "true"、2.0 → "2"）。"""
    if x is None:
        return "null"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def is_terminal(status):
    """终结状态：approved / modified（规格 4.3）。rejected 为非终结。"""
    return status in TERMINAL_STATUSES


def apply_decision(dp, action, opts=None):
    """应用人类决策到决策点（规格 1.3 + 4.3）。返回规范结果 {"ok","code","dp"}。"""
    # 交叉验证裁决（2026-08-31）：JS 守卫是 `!dp || typeof dp !== "object"`——
    # 数组也算 object，会放行进状态检查（落 E_NOT_PENDING 而非 E_DP_NOT_OBJECT）。
    # 规格未定义"对象"边界，裁决对齐生产契约：dict / list 视为对象，其余拒绝。
    if not isinstance(dp, (dict, list)):
        return {"ok": False, "code": "E_DP_NOT_OBJECT", "dp": None}
    dp_status = dp.get("status") if isinstance(dp, dict) else None
    if action not in ACTIONS:
        return {"ok": False, "code": "E_BAD_ACTION", "dp": None}
    if dp_status != "pending":
        return {"ok": False, "code": "E_NOT_PENDING", "dp": None}

    opts = opts if isinstance(opts, dict) else {}
    human_decision = {
        "action": action,
        "decidedBy": opts.get("decidedBy") or "估价师",
    }
    if "timestamp" in opts:  # 缺 timestamp 时 JS 取当前时间（不可复现）→ 比对时两端都不带
        human_decision["timestamp"] = opts["timestamp"]

    comment = opts.get("comment")
    cm = "" if comment is None else _js_str(comment).strip()
    if cm != "":
        human_decision["comment"] = cm

    if action == "modified":  # 规格 1.3：调整必填 modifications
        mods = "" if "modifications" not in opts else _js_str(opts["modifications"]).strip()
        if mods == "":
            return {"ok": False, "code": "E_MODIFIED_REQUIRES_MODIFICATIONS", "dp": None}
        human_decision["modifications"] = mods
    if action == "rejected":  # 编排协议强化：驳回必填 comment（否决原因）
        if cm == "":
            return {"ok": False, "code": "E_REJECTED_REQUIRES_COMMENT", "dp": None}

    out = copy.deepcopy(dp)
    out["status"] = action  # status 与 action 一致
    out["humanDecision"] = human_decision
    return {"ok": True, "code": None, "dp": out}


def run_case(case):
    """对单个 case 输出与 Node 执行器同构的规范结果。"""
    opts = case["opts"] if "opts" in case else None
    return {
        "kind": case["kind"],
        "terminal": is_terminal(case.get("status")),
        "apply": apply_decision(case.get("dp"), case.get("action"), opts),
    }
