#!/usr/bin/env python3
"""
dp_action_diff.py — applyDecision / isTerminal 的差分 CLI（Round 7 / 假设池 #3 整改）

与 dp_chain_diff.py 对称：生成语料 → Python oracle 与 Node 生产实现双端比对 →
落盘结果存档（含 sha256 指纹，登记进当轮 RESULTS.md）。

  python tests/dp_action_diff.py --count 1000 --seed 20260901 --out <file>.json

存档命名须遵守 rounds/README.md 规则：`diff_result_roundN[_suffix].json`，
禁止原地覆盖既有存档。
"""
import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path


def _sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dp_action_shapes import ACTION_KINDS, gen_action_case  # noqa: E402
from diff_chain_generator import find_node  # noqa: E402
from dp_action_oracle import run_case  # noqa: E402

FALLBACK_NODE = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2\node.exe"
RUNNER = HERE / "dp_action_runner.js"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    node = find_node() or FALLBACK_NODE
    rng = random.Random(args.seed)
    cases = []
    for _ in range(args.count):
        kind = rng.choice(ACTION_KINDS)
        case = gen_action_case(rng, kind)
        case["kind"] = kind
        cases.append(case)

    py_rows = [run_case(c) for c in cases]
    proc = subprocess.run([node, str(RUNNER)], input=json.dumps(cases),
                          capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        sys.exit("node runner failed: " + proc.stderr)
    js_rows = json.loads(proc.stdout)

    mismatches, outcome = [], {}
    for i, (p, j) in enumerate(zip(py_rows, js_rows)):
        kind = cases[i]["kind"]
        code = p["apply"]["code"] or ("OK" if p["apply"]["ok"] else "?")
        key = "%s/%s/terminal=%s" % (kind, code, p["terminal"])
        outcome[key] = outcome.get(key, 0) + 1
        if p != j:
            mismatches.append({"index": i, "kind": kind, "py": p, "js": j,
                               "input": cases[i]})

    agree = args.count - len(mismatches)
    rate = agree / args.count
    summary = {
        "seed": args.seed, "count": args.count, "agree": agree,
        "rate": round(rate, 4), "mismatch_count": len(mismatches),
        "kinds": sorted(ACTION_KINDS), "outcome_distribution": dict(sorted(outcome.items())),
        "mismatches": mismatches,
    }
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("决策动作差分 (seed=%d, N=%d, kinds=%d)" % (args.seed, args.count, len(ACTION_KINDS)))
    print("双端一致率: %d/%d = %.4f | 不一致: %d" % (agree, args.count, rate, len(mismatches)))
    print("\nkind/断言结果分布（前 20）:")
    for k, v in sorted(outcome.items(), key=lambda kv: -kv[1])[:20]:
        print("  %-52s %d" % (k, v))
    if mismatches:
        print("\n不一致样例（前 3）:")
        for m in mismatches[:3]:
            print("  #%d [%s] py=%s js=%s" % (m["index"], m["kind"], m["py"], m["js"]))
    if args.out:
        # 存档指纹（Round 6 / P1-2）：登记进当轮 RESULTS.md，指纹不符即发现内容被覆盖
        print("\n结果存档: %s\n存档 sha256: %s" % (args.out, _sha256_of(args.out)))


if __name__ == "__main__":
    main()
