#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mutation_harness.py — 示例算术校验器的变异测试器（Round 8 度量工具）

作用：量化「校验器到底能抓到多少缺陷」。给示例 JSON 注入一组**已知缺陷**
（变异体 mutant），跑校验器，统计被抓到的比例 = **变异检出率 mutation score**。

设计要点：
- 本文件是**度量工具**，不是被测对象；被测对象是 scripts/verify_example_arithmetic.py。
- 判定：退出码 1 = 检出（killed）；0 = 存活（survived，漏检）；非 0/1 = 崩溃（crash）。
  crash 单独计数，因为它与 killed 的语义不同——崩溃不是"发现缺陷"，是校验器自身不健壮。
- 变异集按「校验器的每一类断言」一一对应设计，故存活的变异体可直接读出**盲区位置**。

用法:
    python tests/mutation_harness.py                     # 全部示例
    python tests/mutation_harness.py --json out.json     # 机器可读输出
    python tests/mutation_harness.py --verbose           # 打印每个变异体判定

退出码: 0 表示本命令执行成功（与检出率无关）；检出率从 stdout / --json 读取。
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERIFIER = ROOT / "scripts" / "verify_example_arithmetic.py"
TMP_DIR = ROOT / "tests" / "_tmp_mutants"

KILLED, SURVIVED, CRASH = "killed", "survived", "crash"


# --------------------------------------------------------------------------
# 变异算子：mutate(doc) -> None，原地修改。每个算子对应一类断言。
# 命名约定：mut_<目标>_<手法>
# --------------------------------------------------------------------------
def mut_final_unit_up(doc):
    """P1-1 原始形态的近亲：单价被改大 → 单价×面积 回乘断裂。"""
    doc["result"]["finalUnitValue"] += 100


def mut_final_total_up(doc):
    doc["result"]["finalTotalValue"] += 5000


def mut_inst1_adjusted_up(doc):
    doc["methods"]["comps"]["comparableInstances"][0]["adjustedUnitPrice"] += 200


def mut_comps_total_up(doc):
    doc["methods"]["comps"]["finalValue"]["total"] += 1000


def mut_comps_unit_up(doc):
    doc["methods"]["comps"]["finalValue"]["unit"] += 10


def mut_noi_amount_up(doc):
    doc["methods"]["income"]["netOperatingIncome"]["annualAmount"] += 500


def mut_income_total_up(doc):
    doc["methods"]["income"]["finalValue"]["total"] += 5000


def mut_income_unit_up(doc):
    doc["methods"]["income"]["finalValue"]["unit"] += 20


def mut_repro_up(doc):
    doc["methods"]["cost"]["reproductionCost"] += 10000


def mut_dep_physical_up(doc):
    doc["methods"]["cost"]["depreciation"]["physical"] += 100


def mut_dep_total_up(doc):
    doc["methods"]["cost"]["depreciation"]["total"] += 100


def mut_cross_max_up(doc):
    doc["result"]["crossMethodDifference"]["maxValue"] += 10000


def mut_weight_shift(doc):
    """权重漂移 → 加权总价不再等于声明值。"""
    w = doc["result"]["weightAllocation"]
    keys = [k for k, v in w.items() if v]
    if len(keys) >= 2:
        a, b = keys[0], keys[1]
        w[a] = round(w[a] - 0.1, 4)
        w[b] = round(w[b] + 0.1, 4)


def mut_area_up(doc):
    doc["property"]["area"] = round(doc["property"]["area"] + 3.0, 2)


def mut_chain_result_formula(doc):
    """
    P1-1 的真实形态：只改 calculationChain 末节点公式，不动任何数值。
    校验器若不校验 chain 公式与 target 的一致性 → 该变异体存活。
    """
    nodes = doc.get("calculationChain", {}).get("nodes", [])
    for n in nodes:
        if n.get("target") in ("result.finalTotalValue", "result.finalUnitValue"):
            n["formula"] = "ROUND({{area}}*{{unitValue}}*1.5,0)"
            return
    raise SkipMutant("无 result.* target 的 chain 节点")


class SkipMutant(Exception):
    """变异体不适用（目标结构缺失），不计入分母。"""


# (名称, 算子, 期望抓到的断言类别)
MUTANTS = [
    ("result.unit+100", mut_final_unit_up, "最终单价=ROUND(总价/面积) / 回乘容差"),
    ("result.total+5000", mut_final_total_up, "最终总价(权威加权)"),
    ("comps.inst1.adjusted+200", mut_inst1_adjusted_up, "比准单价复现"),
    ("comps.finalValue.total+1000", mut_comps_total_up, "comps 总价闭合"),
    ("comps.finalValue.unit+10", mut_comps_unit_up, "comps 加权单价"),
    ("income.NOI+500", mut_noi_amount_up, "收益法 NOI"),
    ("income.finalValue.total+5000", mut_income_total_up, "收益法总价(权威)"),
    ("income.finalValue.unit+20", mut_income_unit_up, "收益法单价=ROUND(总价/面积)"),
    ("cost.reproductionCost+10000", mut_repro_up, "成本法重置成本"),
    ("cost.depreciation.physical+100", mut_dep_physical_up, "成本法物质折旧复现"),
    ("cost.depreciation.total+100", mut_dep_total_up, "成本法折旧合计"),
    ("result.crossMethodDifference.max+10000", mut_cross_max_up, "交叉验证 max/min"),
    ("result.weightAllocation 漂移", mut_weight_shift, "最终总价(权威加权)"),
    ("property.area+3", mut_area_up, "面积相关的全部闭合断言"),
    ("calculationChain 末节点公式改写", mut_chain_result_formula, "chain 公式↔target 一致性"),
]


def run_verifier(path: Path, python: str = sys.executable) -> tuple[int, str]:
    """跑校验器，返回 (退出码, 输出)。"""
    p = subprocess.run(
        [python, str(VERIFIER), str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def evaluate(example_path: Path, verbose: bool = False) -> list[dict]:
    base = json.loads(example_path.read_text(encoding="utf-8"))
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # 前置自检：未变异的示例必须是干净的，否则任何"检出"都可能是既有 FAIL 造成的
    # 假阳性（Round 8 B2 实测踩中：示例自带缺陷时 mutation score 虚高到 100%）。
    clean = TMP_DIR / f"{example_path.stem}.clean.json"
    clean.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    base_code, base_out = run_verifier(clean)
    if base_code != 0:
        detail = next((l.strip() for l in base_out.splitlines()
                       if l.startswith("[FAIL]")), "校验器非 0 退出")
        print(f"  [CONTAMINATED] 基线本身不干净（退出码 {base_code}）→ 本示例变异判定不可信，"
              f"已排除。首个 FAIL：{detail}")
        if clean.exists():
            try:
                clean.unlink()
            except OSError:
                pass
        return [{"mutant": "<baseline>", "verdict": "contaminated",
                 "expected": "基线必须干净", "detail": detail}]

    results = []
    for name, fn, expected in MUTANTS:
        doc = copy.deepcopy(base)
        try:
            fn(doc)
        except SkipMutant as e:
            results.append({"mutant": name, "verdict": "skip",
                            "expected": expected, "detail": str(e)})
            if verbose:
                print(f"  [SKIP] {name} ({e})")
            continue
        except (KeyError, IndexError, TypeError) as e:
            results.append({"mutant": name, "verdict": "skip",
                            "expected": expected, "detail": f"结构缺失: {type(e).__name__}"})
            if verbose:
                print(f"  [SKIP] {name} (结构缺失 {type(e).__name__})")
            continue
        tmp = TMP_DIR / f"{example_path.stem}.mut.json"
        tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        code, out = run_verifier(tmp)
        if code == 1:
            verdict = KILLED
        elif code == 0:
            verdict = SURVIVED
        else:
            verdict = CRASH
        detail = ""
        for line in out.splitlines():
            if line.startswith("[FAIL]"):
                detail = line.strip()
                break
        if not detail and verdict == CRASH:
            detail = out.strip().splitlines()[-1] if out.strip() else "崩溃无输出"
        results.append({"mutant": name, "verdict": verdict,
                        "expected": expected, "detail": detail})
        if verbose:
            mark = {KILLED: "KILLED  ", SURVIVED: "SURVIVED", CRASH: "CRASH   "}[verdict]
            print(f"  [{mark}] {name} — {detail}")
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="机器可读结果输出路径")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--examples", nargs="*", help="显式指定示例 JSON（默认自动发现）")
    args = ap.parse_args()

    if args.examples:
        examples = [(ROOT / Path(p)).resolve() for p in args.examples]
    else:
        examples = sorted(ROOT.glob("schema/example-*.json"))

    report = {"examples": [], "totals": {}}
    agg = {KILLED: 0, SURVIVED: 0, CRASH: 0, "skip": 0}
    for ex in examples:
        print(f"== 变异测试 {ex.relative_to(ROOT)} ==")
        rs = evaluate(ex, verbose=args.verbose)
        c = {KILLED: 0, SURVIVED: 0, CRASH: 0, "skip": 0, "contaminated": 0}
        for r in rs:
            c[r["verdict"]] = c.get(r["verdict"], 0) + 1
            agg[r["verdict"]] = agg.get(r["verdict"], 0) + 1
        if c.get("contaminated"):
            report["examples"].append({
                "example": str(ex.relative_to(ROOT)), "counts": c,
                "score": None, "results": rs})
            continue
        scored = c[KILLED] + c[SURVIVED] + c[CRASH]
        score = (c[KILLED] / scored * 100) if scored else 0.0
        print(f"   检出 {c[KILLED]}/{scored} = {score:.1f}%"
              f"（存活 {c[SURVIVED]} / 崩溃 {c[CRASH]} / 跳过 {c['skip']}）")
        survivors = [r["mutant"] for r in rs if r["verdict"] == SURVIVED]
        if survivors:
            print(f"   存活（盲区）: {', '.join(survivors)}")
        report["examples"].append({"example": str(ex.relative_to(ROOT)),
                                   "counts": c, "score": round(score, 1),
                                   "results": rs})
    scored = agg[KILLED] + agg[SURVIVED] + agg[CRASH]
    total_score = (agg[KILLED] / scored * 100) if scored else 0.0
    report["totals"] = {"killed": agg[KILLED], "survived": agg[SURVIVED],
                        "crash": agg[CRASH], "skip": agg["skip"],
                        "scored": scored, "score": round(total_score, 1)}
    print(f"\n总计: mutation score = {agg[KILLED]}/{scored} = {total_score:.1f}%")

    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print(f"机器可读结果: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
