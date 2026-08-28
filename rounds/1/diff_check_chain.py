#!/usr/bin/env python3
"""
diff_check_chain.py — 双端决策链校验差分测试（Round 1）

对比协议：
  - 输入：decisionPoints 数组（分层生成，种子固定 20260828）
  - 双端各输出：违规类别集合 violations ⊆ {C1..C6} + 错误条数 errorCount
  - 核心指标：类别判定一致率 = 类别集合完全一致的输入数 / 总输入数
  - 错误条数差异记为信息级差异（单独统计，不阻塞判定）

用法：python diff_check_chain.py [--count 1000] [--seed 20260828]
"""
import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from validate_appraisal_json import _check_decision_chain  # noqa: E402

NODE = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2\node.exe"
RUNNER = Path(__file__).resolve().parent / "chain_runner.js"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260828)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "diff_result.json"))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    # 分层：合法 30% / 单违规 50% / 混合+边界 20%
    kinds = (["valid"] * 3 + ["c1", "c2", "c3", "c4", "c5", "c6",
             "attempt0", "attemptneg", "attempt_missing", "attempt_str",
             "dup_id", "no_status", "mixed", "empty", "null_elem"])
    inputs = []
    case_kinds = []
    for _ in range(args.count):
        k = rng.choice(kinds)
        case_kinds.append(k)
        inputs.append({"decisionPoints": gen_case(rng, k)})

    # Python 端
    py_results = [classify_py(_check_decision_chain(inp)) for inp in inputs]
    py_counts = [len(_check_decision_chain(inp)) for inp in inputs]

    # Node 端（一次子进程调用）
    proc = subprocess.run(
        [NODE, str(RUNNER)], input=json.dumps(inputs),
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        sys.exit("node runner failed: " + proc.stderr)
    js_results = [set(r["violations"]) for r in json.loads(proc.stdout)]
    js_counts = [r["errorCount"] for r in json.loads(proc.stdout)]

    # 对比
    mismatches = []
    count_diff_only = 0
    for i in range(args.count):
        p, j = py_results[i], js_results[i]
        if p != j:
            mismatches.append({
                "index": i, "kind": case_kinds[i],
                "py_violations": sorted(p), "js_violations": sorted(j),
                "py_count": py_counts[i], "js_count": js_counts[i],
                "input": inputs[i]["decisionPoints"],
            })
        elif py_counts[i] != js_counts[i]:
            count_diff_only += 1

    agree = args.count - len(mismatches)
    rate = agree / args.count
    # 统计每类违规的触发分布（仅在双端一致时的计数）
    by_kind_agree = {}
    for i in range(args.count):
        if py_results[i] == js_results[i]:
            by_kind_agree[case_kinds[i]] = by_kind_agree.get(case_kinds[i], 0) + 1

    result = {
        "seed": args.seed, "count": args.count,
        "agree": agree, "rate": round(rate, 4),
        "mismatch_count": len(mismatches),
        "count_diff_only": count_diff_only,
        "by_kind_agree": by_kind_agree,
        "mismatches": mismatches,  # 全量存档（可复现、可审计）
        "py_counts_total": sum(py_counts), "js_counts_total": sum(js_counts),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("差分测试结果 (seed=%d, N=%d)" % (args.seed, args.count))
    print("类别判定一致率: %d/%d = %.4f" % (agree, args.count, rate))
    print("判定不一致: %d | 仅错误条数不一致: %d" % (len(mismatches), count_diff_only))
    print("Python 总错误条数: %d | JS 总错误条数: %d" % (sum(py_counts), sum(js_counts)))
    if mismatches:
        print("\n不一致样例（前 %d 个）:" % len(mismatches))
        for m in mismatches[:10]:
            print("  #%d [%s] py=%s js=%s (count %d vs %d)" % (
                m["index"], m["kind"],
                m["py_violations"], m["js_violations"],
                m["py_count"], m["js_count"]))
    print("结果存档: %s" % args.out)


if __name__ == "__main__":
    main()
