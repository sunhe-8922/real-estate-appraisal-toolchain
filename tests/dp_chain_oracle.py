"""
dp_chain_oracle.py — resolveChain / buildSuccessorShell 的 Python 参考实现（测试专用 oracle）

**为什么有这个文件**：这两个函数此前只有 JS 单端实现 + 手写断言，是"双端一致"
声明的最大盲区（假设池 #10）。Python 端没有等价实现，因此按《决策点规格定义》
第四章 4.2（规则 1-4）+ 两函数的契约注释独立写一份参考实现，作为差分的第二端。

**纪律（重要）**：本文件必须**按规格实现，不得照抄 app/js/dp-core.js 的代码**。
若两边出现分歧，先判断是 oracle 理解错规格、还是 JS 实现有缺陷，并把结论写进
rounds/N/RESULTS.md——照抄 JS 会让差分退化成恒真断言，失去全部价值。

**已知的非规格行为（JS 实测，oracle 刻意对齐，仅作记录）**：
1. 浮点 attempt（schema 规定 integer ≥1，浮点属越界输入）：JS 字符串拼接时
   2.0 会渲染成 "2"，故 `id` 为 "DP-a-2"；oracle 用 _js_num() 复现该渲染。
2. resolveChain 遇分叉（一个 DP 有两个后继）时只取数组中第一个后继，第二个后继
   既不进 chains 也不会成为 root——在可视化里被静默丢弃（validateChain 的 C4 会报）。

用法：仅被 tests/test_dp_chain_vs_oracle.py 引用，不参与生产代码路径。
"""
import copy
import re


# ── resolveChain 参考实现 ────────────────────────────────

def resolve_chain(decision_points):
    """按 supersedes 分组为链：roots（无 supersedes 的起点）+ chains（长度 ≥2 的链）。"""
    out = {"byId": [], "roots": [], "chains": []}
    if not isinstance(decision_points, list):
        return out
    by_id = {}
    for d in decision_points:
        if isinstance(d, dict) and isinstance(d.get("id"), str):
            by_id[d["id"]] = d
    out["byId"] = sorted(by_id)
    out["roots"] = [dp_id for dp_id, d in by_id.items() if not d.get("supersedes")]
    for root_id in out["roots"]:
        current = by_id[root_id]
        chain = [current]
        seen = {root_id}
        while True:
            nxt = None
            for d in decision_points:
                if not isinstance(d, dict):
                    continue
                if d.get("supersedes") == current["id"] and d.get("id") not in seen:
                    nxt = d
                    break
            if nxt is None:
                break
            chain.append(nxt)
            seen.add(nxt["id"])
            current = nxt
        if len(chain) >= 2:
            out["chains"].append([d["id"] for d in chain])
    return out


# ── buildSuccessorShell 参考实现 ────────────────────────

def _js_num(x):
    """复现 JS 的数字→字符串渲染（2.0 → "2"），仅越界浮点输入会用到。"""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def base_id_of(dp_id):
    """决策链基础 id：去掉尾部 -N 序号（DP-comp-2 → DP-comp）。"""
    return re.sub(r"-\d+$", "", str(dp_id))


def _attempt_of(dp):
    """前驱 attempt：缺失或非法（非 number / <1）视作 1（规格 4.2 规则 1）。"""
    a = dp.get("attempt")
    if isinstance(a, (int, float)) and not isinstance(a, bool) and a >= 1:
        return a
    return 1


def build_successor_shell(chain, dp):
    """驳回后自动建链：生成新 DP 骨架（规格 4.2）。旧 DP 保留为不可变审计记录。"""
    if not isinstance(chain, list):
        return {"ok": False, "code": "E_CHAIN_NOT_ARRAY", "successor": None}
    if not isinstance(dp, dict) or not isinstance(dp.get("id"), str):
        return {"ok": False, "code": "E_DP_NO_ID", "successor": None}
    if dp.get("status") != "rejected":  # 规则 2：只有 rejected 才会被取代
        return {"ok": False, "code": "C3", "successor": None}

    others = [d for d in chain if d and d.get("id") != dp["id"]]
    forks = [d for d in others if d.get("supersedes") == dp["id"]]
    if forks:  # 规则 3：1:1 后继（防分叉）
        return {"ok": False, "code": "C4", "successor": None}

    cursor = dp  # 规则 3：沿链不得成环
    while cursor is not None and cursor.get("supersedes"):
        if cursor.get("supersedes") == dp["id"]:
            return {"ok": False, "code": "C5", "successor": None}
        target = cursor["supersedes"]
        cursor = next((d for d in chain if isinstance(d, dict) and d.get("id") == target), None)

    attempt = _attempt_of(dp) + 1  # 规则 4：新 DP attempt = 前驱 + 1
    successor = {
        "id": base_id_of(dp["id"]) + "-" + _js_num(attempt),
        "name": dp.get("name"),
        "phase": dp.get("phase"),
        "trigger": dp.get("trigger"),
        "riskLevel": dp.get("riskLevel"),
        "status": "pending",
        "supersedes": dp["id"],
        "attempt": attempt,
        # 规则 5：结论/理由清空，由编排层 AI 重写以回应否决原因
        "conclusion": "",
        "evidence": copy.deepcopy(dp["evidence"]) if dp.get("evidence") else [],
        "reasoning": "",
        "risks": copy.deepcopy(dp["risks"]) if dp.get("risks") else [],
    }
    # JSON 语义：undefined 字段不出现（JS 侧同），故清掉 None 值
    successor = {k: v for k, v in successor.items() if v is not None}
    if dp.get("method"):
        successor["method"] = dp["method"]
    if isinstance(dp.get("comparison"), list):
        successor["comparison"] = copy.deepcopy(dp["comparison"])
    return {"ok": True, "code": None, "successor": successor}


def run_case(case):
    """对单个 case 输出与 Node 执行器同构的规范结果。"""
    dps = case["dps"]
    if "outsideDp" in case:
        dp = case["outsideDp"]
    else:
        # JS 数组下标语义（负数为 undefined，非 Python 的末位回溯）——这是语言差异
        # 而非领域语义，必须同构才能逐字段比对
        idx = case["dpIndex"]
        dp = dps[idx] if isinstance(idx, int) and 0 <= idx < len(dps) else None
    return {
        "kind": case["kind"],
        "resolve": resolve_chain(dps),
        "successor": build_successor_shell(dps, dp),
    }
