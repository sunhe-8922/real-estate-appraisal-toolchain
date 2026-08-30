#!/usr/bin/env python3
"""
diff_check_chain.py — 双端决策链校验差分测试 CLI 入口（Round 1 建档）

2026-08-30 起生成器/分类器的唯一事实源为 tests/diff_chain_generator.py，
Node 执行器为 tests/chain_runner.js（审查 P2-2 解耦：正式回归测试不再
反向依赖 rounds/ 实验文件）。本文件保留 CLI 薄壳，历史验证命令继续可用：

    cd rounds/1 && python diff_check_chain.py --count 1000 --seed 20260828

结果存档规则见 rounds/README.md：diff_result_roundN.json 按轮独立命名，
禁止原地覆盖。
"""
import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))
from diff_chain_generator import (  # noqa: E402
    DIFF_KINDS, find_node, gen_case, classify_codes_py, classify_py,
)
from validate_appraisal_json import _check_decision_chain  # noqa: E402

# NODE 解析：WORKBUDDY_NODE 环境变量 > PATH 探测 > 本机受管路径兜底（换机不失效）
FALLBACK_NODE = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2\node.exe"
NODE = find_node() or FALLBACK_NODE
RUNNER = ROOT / "tests" / "chain_runner.js"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260828)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "diff_result.json"))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    inputs = []
    case_kinds = []
    for _ in range(args.count):
        k = rng.choice(DIFF_KINDS)
        case_kinds.append(k)
        inputs.append({"decisionPoints": gen_case(rng, k)})

    # Python 端
    py_errs = [_check_decision_chain(inp) for inp in inputs]
    py_results = [classify_py(e) for e in py_errs]
    py_codes = [classify_codes_py(e) for e in py_errs]
    py_counts = [len(e) for e in py_errs]

    # Node 端（一次子进程调用）
    proc = subprocess.run(
        [NODE, str(RUNNER)], input=json.dumps(inputs),
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        sys.exit("node runner failed: " + proc.stderr)
    js_rows = json.loads(proc.stdout)
    js_results = [set(r["violations"]) for r in js_rows]
    js_codes = [set(r["codes"]) for r in js_rows]
    js_counts = [r["errorCount"] for r in js_rows]

    # 对比：① 类别 ② 违规码（含 key，更严）③ 条数
    mismatches = []
    code_mismatches = []
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
        if py_codes[i] != js_codes[i]:
            code_mismatches.append({
                "index": i, "kind": case_kinds[i],
                "py_codes": sorted(py_codes[i]), "js_codes": sorted(js_codes[i]),
                "input": inputs[i]["decisionPoints"],
            })

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
        "code_mismatch_count": len(code_mismatches),
        "count_diff_only": count_diff_only,
        "by_kind_agree": by_kind_agree,
        "mismatches": mismatches,  # 全量存档（可复现、可审计）
        "code_mismatches": code_mismatches,
        "py_counts_total": sum(py_counts), "js_counts_total": sum(js_counts),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("差分测试结果 (seed=%d, N=%d)" % (args.seed, args.count))
    print("类别判定一致率: %d/%d = %.4f" % (agree, args.count, rate))
    print("判定不一致: %d | 违规码不一致: %d | 仅错误条数不一致: %d" % (
        len(mismatches), len(code_mismatches), count_diff_only))
    print("Python 总错误条数: %d | JS 总错误条数: %d" % (sum(py_counts), sum(js_counts)))
    if mismatches:
        print("\n不一致样例（前 %d 个）:" % len(mismatches))
        for m in mismatches[:10]:
            print("  #%d [%s] py=%s js=%s (count %d vs %d)" % (
                m["index"], m["kind"],
                m["py_violations"], m["js_violations"],
                m["py_count"], m["js_count"]))
    if code_mismatches:
        print("\n违规码不一致样例（前 5，归因漂移）:")
        for m in code_mismatches[:5]:
            print("  #%d [%s] py=%s js=%s" % (
                m["index"], m["kind"], m["py_codes"], m["js_codes"]))
    print("结果存档: %s" % args.out)


if __name__ == "__main__":
    main()
