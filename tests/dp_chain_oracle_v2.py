# -*- coding: utf-8 -*-
r"""决策点决策链独立参考实现（oracle v2）。

由独立会话按《决策点规格定义》第四章（4.2 规则 1-5，参考 1.3）+ 函数契约实现，
未参考任何现有实现（未读取 app/、tests/、rounds/、scripts/ 下任何文件）。

用途：交叉验证另一实现者的 dp-core 版本。

实现的设计选择（规格未定义处，交叉验证时对齐裁决）：
  A1. attempt 数值化：若为浮点且为整数值（如 2.0），按 JS Number 语义视作整数 2，
      用于 attempt+1 运算与 id 拼接（successor id 永不含 ".0"）。
  A2. 布尔不算实数：True/False 不满足"attempt 为实数且 ≥1"，视作缺失（base=1）。
  A3. base id 剥离：用正则 -\d+$ 剥离尾部"-数字"后缀（仅一段数字后缀），
      "DP1"（无连字符前缀）不剥离，"DP2-10" → "DP2"。
  A4. resolve_chain 的"未访问"判定：沿后继行走时，以 id 是否已在**当前链序列**中判定；
      匹配后继时跳过已在序列中的匹配项、继续找下一个未访问匹配（而非立即终止）。
  A5. resolve_chain 中链节点候选要求：必须是 dict 且 id 为字符串（与 byId 口径一致），
      无 id / id 非字符串的元素不参与链行走。
  A6. 重复 id 覆盖后，byId 插入顺序按**首次出现**位置（Python dict / JS object 语义）。
  A7. build_successor_shell 分叉判定（C4）排除"自身"：初版按对象同一性（is not dp），
      交叉验证后改为**按 id**（详见代码内裁决注释）——重复 id 时规格无定义，
      生产契约（JS）以 id 为准，故对齐。
  A8. C5 环回溯时记录已访问 id 集合，防环回溯本身死循环。
  A9. resolve_chain 输入非 list 时按空数组处理（返回空结构，不抛异常）。
  A10. evidence/risks：键缺失 **或值为 None** 时置为 []；存在且非 None 则深拷贝（不校验类型）。
"""

import copy
import re

_TRAILING_ATTEMPT_RE = re.compile(r"-\d+$")


def _is_real_number(v):
    """实数 = int/float 且非 bool。"""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _as_js_number_str(v):
    """按 JS Number→string 语义转字符串：整数值浮点去掉 .0。"""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def _has_supersedes(dp):
    """supersedes 缺失 / None / 空串都算"没有"。"""
    if not isinstance(dp, dict):
        return False
    s = dp.get("supersedes")
    return isinstance(s, str) and s != ""


def resolve_chain(decision_points):
    """解析决策点数组 → {"byId", "roots", "chains"}。

    byId:   id → dp 的索引（仅 id 为字符串的元素参与；重复 id 后者覆盖前者）。
    roots:  无 supersedes 的 DP 的 id，按 by_id 构建时插入顺序。
    chains: 从每个 root 沿后继方向行走得到的节点 id 序列，仅保留长度 ≥2 的链。
    """
    by_id = {}
    if not isinstance(decision_points, list):
        decision_points = []
    # 第一遍：建 by_id 索引（重复 id 后者覆盖前者；仅 id 为字符串者参与）
    for dp in decision_points:
        if isinstance(dp, dict):
            dp_id = dp.get("id")
            if isinstance(dp_id, str):
                by_id[dp_id] = dp  # dict 覆盖赋值保留首次插入位置（A6）

    roots = [dp_id for dp_id, dp in by_id.items() if not _has_supersedes(dp)]

    chains = []
    for root_id in roots:
        seq_ids = [root_id]
        current_id = root_id
        while True:
            nxt = None
            for elem in decision_points:
                if not isinstance(elem, dict):
                    continue
                elem_id = elem.get("id")
                if not isinstance(elem_id, str):
                    continue  # 链节点候选须有字符串 id（A5）
                if elem.get("supersedes") != current_id:
                    continue
                if elem_id in seq_ids:
                    continue  # 已在当前序列中，跳过（防环；A4）
                nxt = elem_id
                break
            if nxt is None:
                break
            seq_ids.append(nxt)
            current_id = nxt
        if len(seq_ids) >= 2:
            chains.append(seq_ids)

    return {"byId": list(by_id.keys()), "roots": roots, "chains": chains}


def build_successor_shell(chain, dp):
    """为被驳回的决策点 dp 构造后继 shell。

    返回 {"ok": bool, "code": str|None, "successor": dict|None}。
    守卫顺序：E_CHAIN_NOT_ARRAY → E_DP_NO_ID → C3 → C4 → C5。
    """
    # 守卫 1：chain 必须是 list
    if not isinstance(chain, list):
        return {"ok": False, "code": "E_CHAIN_NOT_ARRAY", "successor": None}
    # 守卫 2：dp 必须是 dict 且 id 为字符串
    if not isinstance(dp, dict) or not isinstance(dp.get("id"), str):
        return {"ok": False, "code": "E_DP_NO_ID", "successor": None}
    # 守卫 3：只有 rejected 可被取代（规格 4.2 规则 2）
    if dp.get("status") != "rejected":
        return {"ok": False, "code": "C3", "successor": None}
    dp_id = dp["id"]
    # 守卫 4：1:1 后继——除 dp 自身外不得有其他元素 supersedes 指向 dp.id（规则 3）
    for elem in chain:
        # 交叉验证裁决（2026-08-31）：原按对象同一性（is）排除自身，与 JS 实现在
        # 重复 id 场景分歧（37/1000）。规格 4.2 规则 3 说"同一 DP 只能被一个后继取代"，
        # 重复 id 时"同一 DP"本就无定义；生产契约以 id 为准（JS `d.id !== dp.id`），
        # 故改为按 id 排除——同名元素一律视为"自身"，不参与分叉判定。
        if isinstance(elem, dict) and elem.get("id") == dp_id:
            continue
        if isinstance(elem, dict) and elem.get("supersedes") == dp_id:
            return {"ok": False, "code": "C4", "successor": None}
    # 守卫 5：沿 supersedes 回溯不得回到 dp 自身 id（规则 3，防环；A8）
    visited = {dp_id}
    current = dp
    while True:
        s = current.get("supersedes")
        if not isinstance(s, str) or s == "":
            break
        if s == dp_id:
            return {"ok": False, "code": "C5", "successor": None}
        if s in visited:
            break  # 环不经过 dp 自身，不归本函数管（业务校验 C2/C5 范畴）
        visited.add(s)
        nxt = None
        for elem in chain:
            if isinstance(elem, dict) and elem.get("id") == s:
                nxt = elem
                break
        if nxt is None:
            break
        current = nxt

    # ---- 全部通过，构造 successor ----
    base_id = _TRAILING_ATTEMPT_RE.sub("", dp_id)
    raw_attempt = dp.get("attempt")
    if _is_real_number(raw_attempt) and raw_attempt >= 1:
        attempt = raw_attempt + 1
    else:
        attempt = 2  # 缺失/非法视作 1，再 +1（规则 4）
    # attempt 数值规范化：整数值浮点转 int（A1），保证 id 拼接无 ".0"
    if isinstance(attempt, float) and attempt.is_integer():
        attempt = int(attempt)

    successor = {"id": base_id + "-" + _as_js_number_str(attempt), "attempt": attempt}
    successor["status"] = "pending"
    successor["supersedes"] = dp_id
    for field in ("name", "phase", "trigger", "riskLevel"):
        if field in dp and dp[field] is not None:
            successor[field] = copy.deepcopy(dp[field])
    if "method" in dp and dp["method"] is not None:
        successor["method"] = copy.deepcopy(dp["method"])
    successor["conclusion"] = ""  # 规则 5：由 AI 重写，回应否决原因
    successor["reasoning"] = ""
    for field in ("evidence", "risks"):
        val = dp.get(field)
        successor[field] = copy.deepcopy(val) if val is not None else []
    if isinstance(dp.get("comparison"), list):
        successor["comparison"] = copy.deepcopy(dp["comparison"])

    # 值为 None 的字段不出现（JSON undefined 语义）
    successor = {k: v for k, v in successor.items() if v is not None}
    return {"ok": True, "code": None, "successor": successor}


def run_case(case):
    """执行单个测试用例：{"kind", "dps", "dpIndex", "outsideDp"?}。

    dp 取值：有 outsideDp 键用它；否则 dps[dpIndex]，JS 数组下标语义
    （负数 / 越界 / 非整数下标 → None，不做 Python 末位回溯）。
    """
    dps = case.get("dps")
    if "outsideDp" in case:
        dp = case["outsideDp"]
    else:
        idx = case.get("dpIndex")
        if isinstance(dps, list) and isinstance(idx, int) and not isinstance(idx, bool) \
                and 0 <= idx < len(dps):
            dp = dps[idx]
        else:
            dp = None
    return {
        "kind": case.get("kind"),
        "resolve": resolve_chain(dps),
        "successor": build_successor_shell(dps, dp),
    }


# ---------------------------------------------------------------------------
# 自测：手动推演预期并断言
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    def dp(id_, attempt=None, status=None, supersedes=None, **kw):
        d = {"id": id_}
        if attempt is not None:
            d["attempt"] = attempt
        if status is not None:
            d["status"] = status
        if supersedes is not None:
            d["supersedes"] = supersedes
        d.update(kw)
        return d

    # 用例 1：合法链 DP-comp → DP-comp-2 → DP-comp-3
    c1 = [dp("DP-comp", 1, "rejected"),
          dp("DP-comp-2", 2, "rejected", supersedes="DP-comp"),
          dp("DP-comp-3", 3, "approved", supersedes="DP-comp-2")]
    r1 = resolve_chain(c1)
    assert r1 == {"byId": ["DP-comp", "DP-comp-2", "DP-comp-3"],
                  "roots": ["DP-comp"],
                  "chains": [["DP-comp", "DP-comp-2", "DP-comp-3"]]}, r1
    # 对 approved 的 DP-comp-3 生成后继 → C3
    s1 = build_successor_shell(c1, c1[2])
    assert s1 == {"ok": False, "code": "C3", "successor": None}, s1
    # 对已有后继的 DP-comp-2 生成后继 → C4（其已有后继 DP-comp-3 supersedes 它）
    s1b = build_successor_shell(c1, c1[1])
    assert s1b == {"ok": False, "code": "C4", "successor": None}, s1b
    # ok 路径：对尚无后继的 DP-comp，在不含其后继的链中生成 → attempt=2
    s1c = build_successor_shell([c1[0]], c1[0])
    assert s1c["ok"] is True and s1c["code"] is None
    assert s1c["successor"]["id"] == "DP-comp-2"
    assert s1c["successor"]["attempt"] == 2
    assert s1c["successor"]["supersedes"] == "DP-comp"
    assert s1c["successor"]["status"] == "pending"
    assert s1c["successor"]["conclusion"] == "" and s1c["successor"]["reasoning"] == ""
    assert "comparison" not in s1c["successor"]  # 非 list 不复制

    # 用例 2：自引用（C5）：dp.supersedes 指向自身 id
    c2 = [dp("DP1", 1, "rejected", supersedes="DP1")]
    r2 = resolve_chain(c2)
    assert r2["roots"] == [] and r2["chains"] == []  # 有 supersedes，非 root
    s2 = build_successor_shell(c2, c2[0])
    assert s2 == {"ok": False, "code": "C5", "successor": None}, s2

    # 用例 3：双后继分叉（C4）：B、C 都 supersedes A
    c3 = [dp("A", 1, "rejected"),
          dp("A-2", 2, "pending", supersedes="A"),
          dp("A-3", 2, "pending", supersedes="A")]
    r3 = resolve_chain(c3)
    # 行走取数组中第一个未访问匹配 → 只走 A→A-2，A-3 不进入任何链
    assert r3["roots"] == ["A"] and r3["chains"] == [["A", "A-2"]], r3
    s3 = build_successor_shell(c3, c3[0])
    assert s3 == {"ok": False, "code": "C4", "successor": None}, s3

    # 用例 4：A↔B 环（resolve 层面：无 root，无链）
    c4 = [dp("A", 1, "rejected", supersedes="B"),
          dp("B", 1, "rejected", supersedes="A")]
    r4 = resolve_chain(c4)
    assert r4["roots"] == [] and r4["chains"] == [] and set(r4["byId"]) == {"A", "B"}, r4
    # shell 层面：对 A 而言 B supersedes=A → 先命中 C4（守卫顺序 C4 先于 C5）
    s4 = build_successor_shell(c4, c4[0])
    assert s4["code"] == "C4", s4

    # 用例 5：缺 attempt（视作 1）+ 缺 name 等字段
    c5 = [dp("DP2", status="rejected", evidence=[{"item": "x"}], risks=None)]
    s5 = build_successor_shell(c5, c5[0])
    assert s5["ok"] is True
    assert s5["successor"]["id"] == "DP2-2" and s5["successor"]["attempt"] == 2
    assert s5["successor"]["evidence"] == [{"item": "x"}]
    assert s5["successor"]["risks"] == []  # None 视作缺失 → []
    assert "name" not in s5["successor"] and "method" not in s5["successor"]

    # 用例 6：含 null 元素 + supersedes=None/"" 视作无
    c6 = [dp("R", 1, "rejected"), None,
          dp("R-2", 2, "approved", supersedes="R"),
          dp("X", supersedes=None), dp("Y", supersedes="")]
    r6 = resolve_chain(c6)
    assert r6["roots"] == ["R", "X", "Y"], r6
    assert r6["chains"] == [["R", "R-2"]], r6

    # 用例 7：空数组
    r7 = resolve_chain([])
    assert r7 == {"byId": [], "roots": [], "chains": []}, r7
    s7 = build_successor_shell([], dp("DP1", 1, "rejected"))
    assert s7["ok"] is True and s7["successor"]["id"] == "DP1-2"
    assert build_successor_shell("not-a-list", dp("DP1"))["code"] == "E_CHAIN_NOT_ARRAY"

    # 用例 8：id 缺失 / 非字符串
    c8 = [{"status": "rejected"}, {"id": 42, "status": "rejected"}, dp("OK", 1)]
    r8 = resolve_chain(c8)
    assert r8["byId"] == ["OK"] and r8["roots"] == ["OK"] and r8["chains"] == []
    s8 = build_successor_shell(c8, c8[0])
    assert s8 == {"ok": False, "code": "E_DP_NO_ID", "successor": None}, s8

    # 补充：重复 id 后者覆盖；attempt=2.0 浮点 → id 无 ".0"
    c9 = [dp("D", 1, "pending"), dp("D", 1, "rejected"),
          dp("D-2", 2, "approved", supersedes="D")]
    r9 = resolve_chain(c9)
    assert r9["byId"] == ["D", "D-2"] and r9["roots"] == ["D"]  # 首次插入位置（A6）
    s9 = build_successor_shell([], dp("D", 2.0, "rejected"))
    assert s9["successor"]["id"] == "D-3" and s9["successor"]["attempt"] == 3, s9

    # 补充：run_case 的 JS 下标语义 + outsideDp
    rc1 = run_case({"kind": "neg-index", "dps": c1, "dpIndex": -1})
    assert rc1["successor"]["code"] == "E_DP_NO_ID"  # JS arr[-1] = undefined
    rc2 = run_case({"kind": "oob", "dps": c1, "dpIndex": 3})
    assert rc2["successor"]["code"] == "E_DP_NO_ID"
    rc3 = run_case({"kind": "outside", "dps": c1, "dpIndex": 0,
                    "outsideDp": dp("DP1", 1, "rejected", name="n", comparison=[1])})
    assert rc3["successor"]["ok"] is True and rc3["successor"]["successor"]["id"] == "DP1-2"
    assert rc3["successor"]["successor"]["comparison"] == [1]
    assert rc3["resolve"]["chains"] == [["DP-comp", "DP-comp-2", "DP-comp-3"]]

    # 补充：守卫顺序——非 rejected 优先于分叉/环
    s10 = build_successor_shell(c3, dp("A", 1, "approved"))
    assert s10["code"] == "C3"
    # 补充：A1 base id 剥离："DP1" 不剥离（无 -数字 后缀）
    s11 = build_successor_shell([], dp("DP1", 1, "rejected"))
    assert s11["successor"]["id"] == "DP1-2"

    print("ALL SELF-TESTS PASSED (9 groups + extras)")


# SPEC-AMBIGUITIES：实现时记录的 8 条规格模糊点已于 2026-09-01 回写
# 《决策点规格定义》§4.5（含逐条裁决与 D-015 改判规则），此处不再重复；
# 实现内 A1-A10 注释仅保留实现视角的最小说明。改判须先改
# tests/test_dp_chain_oracle_cross.py 固化锚点。
