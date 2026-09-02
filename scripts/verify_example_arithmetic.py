#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_example_arithmetic.py — 示例/工程 JSON 数值自洽校验器（正式入库版）

来源：2026-09-01 对抗式审查 Round7 收尾。审查发现示例宣称"全部数字手工推演自洽"
不成立（P1-1: chain 末节点 ROUND(unit×area) 与权威总价断链；P2-1: 物质折旧
571671 无合法口径）。本脚本把审查时的独立重算逻辑固化为正式校验器，任何
schema/example-*.json 入库前都必须跑通。

Round 8 泛化改造（B1，仅泛化不新增断言）：
原版只在两个 schema 示例上跑得通，遇到真实工程 JSON（标量形态 adjustments、
optional 字段缺失、骨架期工程）直接 KeyError 崩溃——泛化能力实测为 0。本版
改为按 schema v1.5 的**可选性契约**容错：
- adjustments 支持两种形态（schema 第 260-306 行：标量倍率 / *Details 子项明细），
  子项优先，回退标量，两者皆无按 1.0 处理并 INFO；
- optional 字段（crossMethodDifference 等）缺失时 SKIP 而非崩溃；
- 价值时点/竣工年/经济寿命**可导**（读 valuation.valueDate），不再硬编码 2026 / 11 / 58.5；
- 骨架期工程（result.finalTotalValue 为 0/缺失）识别并整段 SKIP，不误报；
- 方法间差异率从 crossMethodDifference.analysis 文本提取后比对，不再写死 9.3%/-14.8%。

口径（与项目硬纪律一致，总价三级验算）：
- 总价是权威值（先取整），单价是派生展示值 = ROUND(总价/面积)
- comps: unit = ROUND(Σw·adj, -1) 权威，total = unit×area 必须闭合（±0）
- income/cost/result: total 权威，unit = ROUND(total/area)；取整后 unit×area
  与 total 允许 ±1 元差（四舍五入固有），不做回乘一致性断言
- 偏差合并修正系数 = 100/(100+Σ(f−100)) = 100/(Σf−(n−1)·100)

用法: python scripts/verify_example_arithmetic.py [example.json]
      [--value-date YYYY-MM-DD] [--land-detail 起算:年限]
退出码: 0 全部通过（含 SKIP）；1 存在 FAIL（CI/提交前门禁）
"""
import json
import re
import sys
import datetime
from pathlib import Path

ROUND_OK = 0
FAILED = []
SKIPPED = []


def check(ok: bool, label: str, detail: str = ""):
    global FAILED
    mark = "PASS" if ok else "FAIL"
    if not ok:
        FAILED.append(label)
    print(f"[{mark}] {label}" + (f"  ({detail})" if detail else ""))


def skip(label: str, detail: str = ""):
    SKIPPED.append(label)
    print(f"[SKIP] {label}" + (f"  ({detail})" if detail else ""))


def info(msg: str):
    print(f"[INFO] {msg}")


def merge_coef(factors, n):
    """偏差合并修正系数 = 100/(Σf − (n−1)·100)；n 为因子项数"""
    s = sum(f["factor"] for f in factors)
    return 100.0 / (s - (n - 1) * 100.0)


def factor_of(adj: dict, key: str) -> tuple[float, str]:
    """
    取某一维度（location/physical/interest）的合并系数。

    schema v1.5 允许两种并存形态：
      1. 标量形态：adj[key] 为已合并的小数倍率（如 0.98）
      2. 子项形态：adj[key+"Details"] 为 100 基准因子明细数组
    子项优先（粒度更细、可复算），回退标量；两者皆无按中性 1.0 处理。
    返回 (系数, 来源说明)。
    """
    details = adj.get(key + "Details")
    if isinstance(details, list) and details:
        return merge_coef(details, len(details)), f"{key}Details({len(details)}项)"
    scalar = adj.get(key)
    if isinstance(scalar, (int, float)):
        return float(scalar), f"{key}标量"
    return 1.0, f"{key}缺失→1.0"


def parse_value_date(d: dict, override: str | None) -> tuple[datetime.date, str]:
    """价值时点可导：优先 CLI 覆盖，其次 valuation.valueDate，最后回退常量。"""
    if override:
        return datetime.date.fromisoformat(override), "CLI --value-date"
    vd = (d.get("valuation") or {}).get("valueDate")
    if vd:
        return datetime.date.fromisoformat(vd[:10]), "valuation.valueDate"
    return datetime.date(2026, 8, 1), "回退常量 2026-08-01"


# 末节点（target 在 result.* 上）的回乘闭合阈值。
# 背景：rebuild_excel_formula.NODE_TOLERANCE 曾给 result.totalValue 开 ±65 特例
# （"面积×单价 vs 加权总价 双口径舍入传播"，出自 659e9e3 创建日，无缺陷编号背书）。
# 实测该容差足以放过 P1-1 形态的末节点断裂（武汉洪山住宅 result.totalValue 差 18 元
# 却 PASS）。该豁免已于 Round 10（H10）删除：R7/R9 整改为"单价派生自权威总价"后
# 双口径不复存在。末节点是报告最终结论值，不存在"双口径"借口——
# ROUND 语义确定，闭合差应由取整传播上界界定，不靠拍脑袋常量。
CHAIN_TAIL_TOLERANCE = 1


def check_chain_nodes(doc: dict, label_prefix: str = "chain"):
    """
    calculationChain 公式 ↔ target 一致性（P1-1 类缺陷的机器防线）。

    复用 scripts/rebuild_excel_formula.py 的 rebuild_values（ast 白名单求值 +
    ROUND/SUM + {{ref}} 解析），不重复实现求值器。

    SKIP 语义收紧（本轮关键改动）：原实现把"求值失败"一律降级为 SKIP，
    于是**公式写错（引用了 refs 里不存在的键）也会被优雅放过**。
    本函数区分两种 SKIP：
      - target 字段在数据中不存在 → 该节点不适用，真 SKIP；
      - target 存在却求值失败 → 公式不可复现，判 FAIL。
    """
    chain = doc.get("calculationChain")
    nodes = (chain or {}).get("nodes") or []
    if not nodes:
        skip(f"{label_prefix} 一致性", "无 calculationChain 节点")
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from rebuild_excel_formula import rebuild_values, get_jsonpath
    except ImportError as e:  # pragma: no cover
        skip(f"{label_prefix} 一致性", f"无法导入求值器: {e}")
        return

    for r in rebuild_values(chain, doc):
        nid = r["id"]
        if r["status"] == "PASS":
            diff = r.get("diff") or 0.0
            if nid.startswith("result.") and diff > CHAIN_TAIL_TOLERANCE:
                check(False, f"{label_prefix} 末节点回乘闭合 {nid}",
                      f"公式算 {r.get('computed')} vs target {r.get('actual')} "
                      f"(差 {diff}，末节点阈值 {CHAIN_TAIL_TOLERANCE})——"
                      f"P1-1 形态：末节点公式推不出结论值")
            else:
                check(True, f"{label_prefix} 节点 {nid}",
                      f"{r.get('computed')} vs {r.get('actual')}")
        elif r["status"] == "FAIL":
            check(False, f"{label_prefix} 节点 {nid}",
                  f"公式算 {r.get('computed')} vs target {r.get('actual')} "
                  f"(差 {r.get('diff')}, 容差 {r.get('tolerance')})")
        else:  # SKIP
            ok, actual = get_jsonpath(doc, r["target"])
            if ok and actual is not None:
                check(False, f"{label_prefix} 节点 {nid} 公式不可求值",
                      f"target ({r['target']}) 有值却求不出——"
                      f"{r.get('reason')}（引用了 refs 中不存在的键 = 公式写错）")
            else:
                skip(f"{label_prefix} 节点 {nid}",
                     f"target 字段缺失，该节点不适用（{r.get('reason')}）")


def is_skeleton(res: dict, methods: dict) -> bool:
    """
    骨架期工程判定：结果值未填（0/缺失）即视为尚未进入测算阶段。
    此类工程不应跑数值断言——否则把"还没算"误报成"算错了"。
    """
    total = res.get("finalTotalValue")
    if not total:
        return True
    return not any(
        isinstance(m, dict) and m.get("finalValue", {}).get("total")
        for m in methods.values()
    )


def check_pct_claims(analysis: str, claims: dict[str, float], label_prefix: str):
    """
    泛化的百分比声明核对：从 analysis 文本中提取 N 个百分比，与各方法实算差异比对。
    原版写死 9.3% / -14.8%，换个示例即失效。改为匹配已知声明值集合。

    注意：业务文本习惯写"偏低 14.8%"（不带负号），而实算差异为 −14.8%，
    故按**绝对值**比对符号无关（Round 8 B1 实测踩中）。
    """
    found = re.findall(r"(-?\d+(?:\.\d+)?)%", analysis or "")
    vals = [abs(float(x)) for x in found]
    for name, expect in claims.items():
        # 容差 0.05pct：文本声明只保留一位小数
        hit = any(abs(v - abs(expect)) <= 0.05 for v in vals)
        check(hit, f"{label_prefix} {name}",
              f"实算 {expect}%，analysis 文本含 {vals}")


def main(path: str, value_date: str | None = None, land_detail: str | None = None) -> int:
    d = json.load(open(path, encoding="utf-8"))
    P = d["property"]
    area = P["area"]
    methods = d["methods"]
    comps = methods["comps"]
    income = methods.get("income")
    cost = methods.get("cost")
    res = d["result"]
    vd, vd_src = parse_value_date(d, value_date)
    print(f"== 校验 {path} (area={area}, 价值时点={vd} 来源={vd_src}) ==")

    # ---------- 骨架期工程：整段跳过数值断言 ----------
    if is_skeleton(res, methods):
        skip("骨架期工程（result.finalTotalValue 未填）",
             "仅做结构可达性检查，数值断言不适用")
        # 结构可达性：仍确认关键路径可解析，避免"跳过"掩盖结构腐烂
        insts = comps.get("comparableInstances", [])
        check(len(insts) >= 3, "骨架期可比实例数≥3", f"{len(insts)} 个")
        for i, inst in enumerate(insts):
            adj = inst.get("adjustments") or {}
            if not isinstance(adj, dict):
                check(False, f"骨架期实例{i+1} adjustments 结构", f"{type(adj).__name__}")
                continue
            for k in ("location", "physical", "interest"):
                _, src = factor_of(adj, k)
                if src.endswith("缺失→1.0"):
                    info(f"骨架期实例{i+1} {k} 两种形态均缺失，按 1.0 处理")
        print(f"\n结果: {len(FAILED)} 项 FAIL: {FAILED}" if FAILED else "\n结果: 全部通过 ✓")
        return 1 if FAILED else 0

    # ---------- 比较法 ----------
    insts = comps["comparableInstances"]
    # 权威权重来源：calculationChain 中 comps.finalUnitPrice 节点的 formula 系数
    weights = None
    for node in d.get("calculationChain", {}).get("nodes", []):
        if node.get("id") == "comps.finalUnitPrice":
            m = re.findall(r"\*(\d+(?:\.\d+)?)", node.get("formula", ""))
            if m and len(m) == len(insts):
                weights = [float(x) for x in m]
                break
    if weights is None:
        weights = [round(1.0 / len(insts), 4)] * len(insts)  # 按实例数均权回退
        info(f"comps 权重未在 chain 中找到，按 {len(insts)} 实例均权回退 {weights[0]}")
    for i, inst in enumerate(insts):
        adj = inst.get("adjustments") or {}
        loc, _ = factor_of(adj, "location")
        inte, _ = factor_of(adj, "interest")
        phy, _ = factor_of(adj, "physical")
        calc = round(inst["unitPrice"] * adj.get("transactionSituation", 1.0)
                     * adj.get("marketCondition", 1.0) * loc * inte * phy)
        check(calc == inst["adjustedUnitPrice"],
              f"comps 实例{i+1} 比准单价复现",
              f"独立算 {calc} vs 声明 {inst['adjustedUnitPrice']}")
    w_unit = round(sum(insts[k]["adjustedUnitPrice"] * weights[k]
                       for k in range(len(insts))), -1)
    fv = comps["finalValue"]
    check(w_unit == fv["unit"], "comps 加权单价", f"算 {w_unit} vs 声明 {fv['unit']}")
    check(fv["unit"] * area == fv["total"], "comps 总价闭合(unit×area)",
          f"{fv['unit']}×{area}={fv['unit']*area} vs 声明 {fv['total']}")

    # ---------- 收益法（方法缺失/不可用时跳过） ----------
    if income is None or not income.get("applicable", True):
        skip("收益法（未采用）")
    else:
        noi = income["netOperatingIncome"]
        calc_noi = noi["effectiveGrossIncome"] - noi["operatingExpenses"]
        check(calc_noi == noi["annualAmount"], "收益法 NOI",
              f"{noi['effectiveGrossIncome']}-{noi['operatingExpenses']}={calc_noi}")
        inc_total = round(calc_noi / income["rate"]["value"])
        inc_fv = income["finalValue"]
        check(inc_total == inc_fv["total"], "收益法总价(权威)",
              f"ROUND({calc_noi}/{income['rate']['value']})={inc_total} vs {inc_fv['total']}")
        inc_unit = round(inc_fv["total"] / area)
        check(inc_unit == inc_fv["unit"], "收益法单价=ROUND(总价/面积)",
              f"{inc_fv['total']}/{area}={inc_unit} vs {inc_fv['unit']}")
        back = inc_fv["unit"] * area
        # 回乘差上界 = 总价取整(≤0.5) + 单价取整(≤0.5/㎡×area)
        tol = 0.5 * area + 0.5
        check(abs(back - inc_fv["total"]) <= tol, "收益法回乘容差(取整传播上界)",
              f"{inc_fv['unit']}×{area}={back} vs {inc_fv['total']} (差 {inc_fv['total']-back}, 上界 {tol})")

    # ---------- 成本法（方法缺失/不可用时跳过） ----------
    if cost is None or not cost.get("applicable", True):
        skip("成本法（未采用）")
    else:
        cc = cost["costComponents"]
        repro = sum(v for v in cc.values())
        check(repro == cost["reproductionCost"], "成本法重置成本",
              f"七项和 {repro} vs {cost['reproductionCost']}")
        dep = cost["depreciation"]
        # 年龄-寿命法：物质折旧 = 重置成本 × 有效年龄/(有效年龄+剩余经济寿命)
        # 有效年龄由价值时点年份推导，不再硬编码
        cy = P.get("completionYear")
        if not cy:
            skip("有效年龄自洽", "property.completionYear 缺失")
            phys_expected = None
        else:
            eff_age = vd.year - cy
            remain = P.get("remainingUsefulLife")
            if not remain:
                skip("成本法物质折旧复现", "property.remainingUsefulLife 缺失")
                phys_expected = None
            else:
                phys_expected = round(repro * eff_age / (eff_age + remain))
                check(phys_expected == dep["physical"], "成本法物质折旧复现",
                      f"ROUND({repro}×{eff_age}/{eff_age+remain})={phys_expected} vs {dep['physical']}")
        dep_total = dep["physical"] + dep["functional"] + dep["external"]
        check(dep_total == dep["total"], "成本法折旧合计", f"{dep_total} vs {dep['total']}")
        cost_total = repro - dep_total
        cost_fv = cost["finalValue"]
        check(cost_total == cost_fv["total"], "成本法总价(权威)",
              f"{repro}-{dep_total}={cost_total} vs {cost_fv['total']}")
        cost_unit = round(cost_fv["total"] / area)
        check(cost_unit == cost_fv["unit"], "成本法单价=ROUND(总价/面积)",
              f"{cost_fv['total']}/{area}={cost_unit} vs {cost_fv['unit']}")

    # ---------- 最终结果（按 weightAllocation 动态加权） ----------
    w = res["weightAllocation"]
    parts = []
    for k, wt in w.items():
        if wt and wt > 0 and methods.get(k):
            fv = methods[k].get("finalValue")
            if fv:
                parts.append((k, fv["total"], wt))
    check(len(parts) >= 1, "参与加权方法数", f"{len(parts)} 个 ({', '.join(k for k,_,_ in parts)})")
    calc_final = round(sum(t * wt for _, t, wt in parts), -1)
    check(calc_final == res["finalTotalValue"], "最终总价(权威加权)",
          f"算 {calc_final} vs {res['finalTotalValue']}")
    calc_unit = round(res["finalTotalValue"] / area)
    check(calc_unit == res["finalUnitValue"], "最终单价=ROUND(总价/面积)",
          f"{res['finalTotalValue']}/{area}={calc_unit} vs {res['finalUnitValue']}")
    back = res["finalUnitValue"] * area
    # 最终总价取整到十位(≤5) + 单价取整(≤0.5/㎡×area)
    tol = 0.5 * area + 5.0
    check(abs(back - res["finalTotalValue"]) <= tol, "最终回乘容差(取整传播上界)",
          f"{res['finalUnitValue']}×{area}={back} vs {res['finalTotalValue']} (差 {res['finalTotalValue']-back}, 上界 {tol})")

    # ---------- 交叉验证（参与方法动态取 max/min；字段 optional 时跳过） ----------
    xm = res.get("crossMethodDifference")
    totals = [t for _, t, _ in parts]
    if not xm:
        skip("交叉验证", "result.crossMethodDifference 缺失（schema 中该字段 optional）")
    else:
        mx, mn = max(totals), min(totals)
        check(xm["maxValue"] == mx and xm["minValue"] == mn, "交叉验证 max/min 一致",
              f"{xm['maxValue']}/{xm['minValue']} vs 实算 {mx}/{mn}")
        calc_ratio = round(mx / mn, 3)
        check(calc_ratio == xm["ratio"], "交叉验证比值 max/min",
              f"{mx}/{mn}={calc_ratio} vs {xm['ratio']}")

    # ---------- 方法间差异声明核对（从 analysis 文本提取，不再硬编码） ----------
    claims = {}
    if len(parts) == 3:
        base_total = comps["finalValue"]["total"]
        inc_vs = round((income["finalValue"]["total"] / base_total - 1) * 100, 1)
        cost_vs = round((cost["finalValue"]["total"] / base_total - 1) * 100, 1)
        claims = {"收益/比较差异": inc_vs, "成本/比较差异": cost_vs}
    if claims:
        analysis = (xm or {}).get("analysis", "") if xm else ""
        if analysis:
            check_pct_claims(analysis, claims, "方法差异声明")
        else:
            skip("方法差异声明核对", "analysis 文本缺失")

    # ---------- calculationChain 公式 ↔ target 一致性（P1-1 类缺陷防线） ----------
    check_chain_nodes(d)

    # ---------- 土地剩余年限可导性（需 --land-detail 起算:年限 参数，否则降级 INFO） ----------
    if land_detail:
        start_str, total_years = land_detail.split(":")
        sy, sm = map(int, start_str.split("-"))
        start = datetime.date(sy, sm, 1)
        remain_years = int(total_years) - (vd - start).days / 365.25
        check(round(remain_years, 1) == P["landUseRightYears"], "土地剩余年限可导",
              f"{total_years}−{(vd-start).days/365.25:.2f}={remain_years:.1f} vs {P['landUseRightYears']}")
    else:
        info("土地剩余年限可导性跳过（未传 --land-detail 起算:年限）")

    print(f"\n结果: {len(FAILED)} 项 FAIL: {FAILED}" if FAILED else "\n结果: 全部通过 ✓")
    return 1 if FAILED else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    LAND_DETAIL = None
    VALUE_DATE = None
    JSON_OUT = None
    if "--land-detail" in args:
        i = args.index("--land-detail")
        LAND_DETAIL = args[i + 1]
        del args[i:i + 2]
    if "--value-date" in args:
        i = args.index("--value-date")
        VALUE_DATE = args[i + 1]
        del args[i:i + 2]
    if "--json-out" in args:
        # 机器可读结果：供 tests/test_example_arithmetic.py 精确断言 FAIL 集合，
        # 避免回归测试去解析人类可读的 stdout（脆弱且易随文案漂移）。
        i = args.index("--json-out")
        JSON_OUT = args[i + 1]
        del args[i:i + 2]
    target = args[0] if args else "schema/example-多方法商业.json"
    rc = main(target, VALUE_DATE, LAND_DETAIL)
    if JSON_OUT:
        Path(JSON_OUT).write_text(
            json.dumps({"target": target, "failed": FAILED,
                        "skipped": SKIPPED, "exit_code": rc},
                       ensure_ascii=False, indent=1),
            encoding="utf-8")
    sys.exit(rc)
