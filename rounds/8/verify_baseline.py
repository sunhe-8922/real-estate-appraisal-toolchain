#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_example_arithmetic.py — 示例 JSON 数值自洽校验器（正式入库版）

来源：2026-09-01 对抗式审查 Round7 收尾。审查发现示例宣称"全部数字手工推演自洽"
不成立（P1-1: chain 末节点 ROUND(unit×area) 与权威总价断链；P2-1: 物质折旧
571671 无合法口径）。本脚本把审查时的独立重算逻辑固化为正式校验器，任何
schema/example-*.json 入库前都必须跑通。

口径（与项目硬纪律一致，总价三级验算）：
- 总价是权威值（先取整），单价是派生展示值 = ROUND(总价/面积)
- comps: unit = ROUND(Σw·adj, -1) 权威，total = unit×area 必须闭合（±0）
- income/cost/result: total 权威，unit = ROUND(total/area)；取整后 unit×area
  与 total 允许 ±1 元差（四舍五入固有），不做回乘一致性断言
- 偏差合并修正系数 = 100/(100+Σ(f−100)) = 100/(Σf−(n−1)·100)

用法: python scripts/verify_example_arithmetic.py [example.json]
退出码: 0 全部通过；1 存在 FAIL（CI/提交前门禁）
"""
import json
import re
import sys
import datetime

ROUND_OK = 0
FAILED = []


def check(ok: bool, label: str, detail: str = ""):
    global FAILED
    mark = "PASS" if ok else "FAIL"
    if not ok:
        FAILED.append(label)
    print(f"[{mark}] {label}" + (f"  ({detail})" if detail else ""))


def merge_coef(factors, n):
    """偏差合并修正系数 = 100/(Σf − (n−1)·100)；n 为因子项数"""
    s = sum(f["factor"] for f in factors)
    return 100.0 / (s - (n - 1) * 100.0)


def main(path: str) -> int:
    d = json.load(open(path, encoding="utf-8"))
    P = d["property"]
    area = P["area"]
    methods = d["methods"]
    comps = methods["comps"]
    income = methods.get("income")
    cost = methods.get("cost")
    res = d["result"]
    print(f"== 校验 {path} (area={area}) ==")

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
        weights = [0.4, 0.3, 0.3]  # 模板默认回退
        print("[INFO] comps 权重未在 chain 中找到，使用模板默认 0.4/0.3/0.3")
    for i, inst in enumerate(insts):
        adj = inst["adjustments"]
        loc = merge_coef(adj["locationDetails"], len(adj["locationDetails"]))
        inte = merge_coef(adj["interestDetails"], len(adj["interestDetails"]))
        phy = merge_coef(adj["physicalDetails"], len(adj["physicalDetails"]))
        calc = round(inst["unitPrice"] * adj["transactionSituation"]
                     * adj["marketCondition"] * loc * inte * phy)
        check(calc == inst["adjustedUnitPrice"],
              f"comps 实例{i+1} 比准单价复现",
              f"独立算 {calc} vs 声明 {inst['adjustedUnitPrice']}")
    w_unit = round(sum(insts[k]["adjustedUnitPrice"] * weights[k] for k in range(3)), -1)
    fv = comps["finalValue"]
    check(w_unit == fv["unit"], "comps 加权单价", f"算 {w_unit} vs 声明 {fv['unit']}")
    check(fv["unit"] * area == fv["total"], "comps 总价闭合(unit×area)",
          f"{fv['unit']}×{area}={fv['unit']*area} vs 声明 {fv['total']}")

    # ---------- 收益法（方法缺失/不可用时跳过） ----------
    if income is None or not income.get("applicable", True):
        print("[SKIP] 收益法（未采用）")
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
        print("[SKIP] 成本法（未采用）")
    else:
        cc = cost["costComponents"]
        repro = sum(v for v in cc.values())
        check(repro == cost["reproductionCost"], "成本法重置成本",
              f"七项和 {repro} vs {cost['reproductionCost']}")
        dep = cost["depreciation"]
        # 年龄-寿命法：物质折旧 = 重置成本 × 有效年龄/(有效年龄+剩余经济寿命)
        eff_age = 2026 - P["completionYear"]
        check(eff_age == 11, "有效年龄自洽(2026-竣工年)",
              f"2026-{P['completionYear']}={eff_age}")
        check(eff_age + P["remainingUsefulLife"] == 58.5, "经济寿命分母自洽(11+47.5)",
              f"{eff_age}+{P['remainingUsefulLife']}={eff_age+P['remainingUsefulLife']}")
        phys = round(repro * eff_age / (eff_age + P["remainingUsefulLife"]))
        check(phys == dep["physical"], "成本法物质折旧复现",
              f"ROUND({repro}×{eff_age}/{eff_age+P['remainingUsefulLife']})={phys} vs {dep['physical']}")
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

    # ---------- 交叉验证（参与方法动态取 max/min） ----------
    xm = res["crossMethodDifference"]
    totals = [t for _, t, _ in parts]
    mx, mn = max(totals), min(totals)
    check(xm["maxValue"] == mx and xm["minValue"] == mn, "交叉验证 max/min 一致",
          f"{xm['maxValue']}/{xm['minValue']} vs 实算 {mx}/{mn}")
    calc_ratio = round(mx / mn, 3)
    check(calc_ratio == xm["ratio"], "交叉验证比值 max/min",
          f"{mx}/{mn}={calc_ratio} vs {xm['ratio']}")
    if len(parts) == 3:
        inc_vs_comp = round((income["finalValue"]["total"] / comps["finalValue"]["total"] - 1) * 100, 1)
        check(inc_vs_comp == 9.3, "收益/比较差异 9.3%", f"实算 {inc_vs_comp}%")
        cost_vs_comp = round((cost["finalValue"]["total"] / comps["finalValue"]["total"] - 1) * 100, 1)
        check(cost_vs_comp == -14.8, "成本/比较差异 −14.8%", f"实算 {cost_vs_comp}%")

    # ---------- 土地剩余年限可导性（需 --land-detail 起算:年限 参数，否则降级 INFO） ----------
    if LAND_DETAIL:
        start_str, total_years = LAND_DETAIL.split(":")
        sy, sm = map(int, start_str.split("-"))
        start = datetime.date(sy, sm, 1)
        vd = datetime.date(2026, 8, 1)
        remain = int(total_years) - (vd - start).days / 365.25
        check(round(remain, 1) == P["landUseRightYears"], "土地剩余年限可导",
              f"{total_years}−{(vd-start).days/365.25:.2f}={remain:.1f} vs {P['landUseRightYears']}")
    else:
        print("[INFO] 土地剩余年限可导性跳过（未传 --land-detail 起算:年限）")

    print(f"\n结果: {len(FAILED)} 项 FAIL: {FAILED}" if FAILED else "\n结果: 全部通过 ✓")
    return 1 if FAILED else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    LAND_DETAIL = None
    if "--land-detail" in args:
        i = args.index("--land-detail")
        LAND_DETAIL = args[i + 1]
        del args[i:i + 2]
    target = args[0] if args else "schema/example-多方法商业.json"
    sys.exit(main(target))
