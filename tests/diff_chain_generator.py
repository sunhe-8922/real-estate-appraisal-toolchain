"""
diff_chain_generator.py — 双端决策链校验差分测试的生成器与分类器（唯一事实源）

2026-08-30 自 rounds/1/diff_check_chain.py 迁入（审查 P2-2 解耦：正式回归测试
不再反向依赖 rounds/ 实验文件）。rounds/1/diff_check_chain.py 保留为 CLI 薄壳，
历史验证命令 `cd rounds/1 && python diff_check_chain.py --count 1000 --seed 20260828`
继续可用；差分结果存档规则见 rounds/README.md（diff_result_roundN.json，禁止原地覆盖）。

分层生成协议（种子固定 20260828 可复现）：
  - 输入：decisionPoints 数组（合法 30% / 单违规注入 50% / 混合+边界 20%，18 kind）
  - 双端各输出：违规类别集合 + 错误条数（执行器见 chain_runner.js）
"""
import random


# ── 生成器 ──────────────────────────────────────────────

def gen_valid_dp(rid, status="pending", attempt=None, supersedes=None):
    dp = {
        "id": rid,
        "name": "DP " + rid,
        "phase": "inMethod",
        "trigger": "method:comps",
        "riskLevel": "P1",
        "status": status,
        "conclusion": "x",
        "evidence": [],
        "reasoning": "y",
        "risks": [],
    }
    if attempt is not None:
        dp["attempt"] = attempt
    if supersedes is not None:
        dp["supersedes"] = supersedes
    return dp


def gen_valid_chain(rng):
    """合法链：n 个 DP，rejected→…→pending，attempt 递增，无分叉。"""
    n = rng.randint(1, 4)
    dps = []
    for i in range(n):
        status = "rejected" if i < n - 1 else "pending"
        dps.append(gen_valid_dp(
            "DP-%d" % i, status, attempt=i + 1,
            supersedes="DP-%d" % (i - 1) if i > 0 else None,
        ))
    return dps


def gen_valid_multi(rng):
    """1-2 条独立合法链。"""
    dps = []
    for c in range(rng.randint(1, 2)):
        base = c * 10
        chain = gen_valid_chain(rng)
        for dp in chain:
            dp["id"] = "DP-%d-%d" % (base, int(dp["id"].split("-")[1]))
            if dp.get("supersedes"):
                dp["supersedes"] = "DP-%d-%d" % (base, int(dp["supersedes"].split("-")[1]))
        dps.extend(chain)
    return dps


def gen_case(rng, kind):
    """按 kind 生成一个输入（decisionPoints 数组）。"""
    if kind == "valid":
        return gen_valid_multi(rng)
    if kind == "c1":  # supersedes 指向不存在的 id
        dps = gen_valid_chain(rng)
        dps[-1]["supersedes"] = "NONEXISTENT"
        return dps
    if kind == "c2":  # 自引用
        dps = gen_valid_chain(rng)
        dps[-1]["supersedes"] = dps[-1]["id"]
        return dps
    if kind == "c3":  # 被取代者 status != rejected
        dps = gen_valid_chain(rng)
        if len(dps) >= 2:
            dps[-1]["supersedes"] = dps[-2]["id"]
            dps[-2]["status"] = "pending"
        return dps
    if kind == "c4":  # 双后继（分叉）：A 被 B、C 同时取代
        a = gen_valid_dp("DP-a", "rejected", 1)
        b = gen_valid_dp("DP-b", "pending", 2, supersedes="DP-a")
        c = gen_valid_dp("DP-c", "pending", 2, supersedes="DP-a")
        return [a, b, c]
    if kind == "c5":  # 成环：A→B, B→A
        a = gen_valid_dp("DP-a", "rejected", 1)
        b = gen_valid_dp("DP-b", "pending", 2, supersedes="DP-a")
        a["supersedes"] = "DP-b"
        return [a, b]
    if kind == "c6":  # attempt 与推导值不一致
        dps = gen_valid_chain(rng)
        dps[-1]["attempt"] = 99
        return dps
    if kind == "attempt0":  # 边界：被取代者 attempt=0
        dps = gen_valid_chain(rng)
        if len(dps) >= 2:
            dps[-2]["attempt"] = 0
        return dps
    if kind == "attemptneg":  # 边界：被取代者 attempt=-1
        dps = gen_valid_chain(rng)
        if len(dps) >= 2:
            dps[-2]["attempt"] = -1
        return dps
    if kind == "attempt_missing":  # 前驱无 attempt（默认 1）
        dps = gen_valid_chain(rng)
        if len(dps) >= 2:
            dps[-2].pop("attempt", None)
        return dps
    if kind == "dup_id":  # id 重复（唯一性不属 C1-C6，预期双端均不报 C 类）
        dps = gen_valid_chain(rng)
        if len(dps) >= 2:
            dps.append(gen_valid_dp(dps[0]["id"], "pending", attempt=len(dps) + 1,
                                    supersedes=dps[-1]["id"]))
        return dps
    if kind == "no_status":  # 被取代者缺 status
        dps = gen_valid_chain(rng)
        if len(dps) >= 2:
            dps[-2].pop("status", None)
        return dps
    if kind == "attempt_str":  # 非法类型：后继 attempt 为字符串（C6 仅对 number/int 检查）
        dps = gen_valid_chain(rng)
        if len(dps) >= 2:
            dps[-1]["attempt"] = "2"
        return dps
    if kind == "attempt_float":  # P0-1 回归形状：浮点 attempt（Round 4 补）
        dps = gen_valid_chain(rng)
        if len(dps) >= 2:
            if rng.random() < 0.5:
                # 前驱整数值浮点（2.0），后继 = 前驱+1 → 双端应通过（修复前 PY 报 C6）
                dps[-2]["attempt"] = float(dps[-2]["attempt"])
                dps[-1]["attempt"] = dps[-2]["attempt"] + 1
            else:
                # 后继非整数浮点（x.5）→ 双端应报 C6（修复前 PY 静默）
                dps[-1]["attempt"] = dps[-1]["attempt"] + 0.5
        return dps
    if kind == "ghost_fork":  # 双 DP 指向同一不存在 id → 双端均仅报 C1×2（Round 4 补）
        return [gen_valid_dp("DP-b", "pending", 2, supersedes="GHOST"),
                gen_valid_dp("DP-c", "pending", 2, supersedes="GHOST")]
    if kind == "mixed":  # 多违规混合（C1 + C6）
        dps = gen_valid_chain(rng)
        dps[-1]["supersedes"] = "NONEXISTENT"
        dps[-1]["attempt"] = 0
        return dps
    if kind == "empty":
        return []
    if kind == "null_elem":  # 数组含 null 元素
        dps = gen_valid_chain(rng)
        dps.append(None)
        return dps
    raise ValueError("unknown kind: " + kind)


# 分层清单（与 rounds/1..4 差分脚本一致）：合法 30% / 单违规 50% / 混合+边界 20%
DIFF_KINDS = (["valid"] * 3 + ["c1", "c2", "c3", "c4", "c5", "c6",
              "attempt0", "attemptneg", "attempt_missing", "attempt_str",
              "attempt_float", "ghost_fork",
              "dup_id", "no_status", "mixed", "empty", "null_elem"])


# ── 分类（按类别集合，不按消息文本） ──────────────────────

def classify_py(errors):
    cats = set()
    for e in errors:
        m = str(e.message)
        if "引用了不存在的决策点" in m:
            cats.add("C1")
        elif "不得自引用" in m or "引用了自身" in m:
            cats.add("C2")
        elif "只有 status=rejected" in m or "才能被取代" in m:
            cats.add("C3")
        elif "只能被一个后继取代" in m:
            cats.add("C4")
        elif "存在环" in m:
            cats.add("C5")
        elif "attempt=" in m:
            cats.add("C6")
    return cats
