#!/usr/bin/env python3
"""
extract_calculation_chain.py — 从 Excel 模板提取公式逻辑，生成 JSON calculationChain（v1.2）

提取的核心公式链（住宅模板）：
  1. 市场价比较法!T32/W32/Z32  比准单价（3 实例，子项偏差加总合并）
  2. 市场价比较法!T34          比准单价加权平均（权重 0.5/0.3/0.2 常量）
  3. 住宅-收益法测算!G4         年净收益 = 有效毛收入 - 运营费用
  4. 住宅-收益法测算!G27       收益价值（报酬资本化分段折现）
  5. 住宅-收益法测算!J29       最终加权结果
  6. 评估明细表!O6             总价 = 面积 × 单价

输出：JSON calculationChain 对象（schema calculationChain 字段格式）
  {
    "version": "1.2",
    "nodes": [
      {"id", "target", "formula", "refs", "excelSource", "description"}
    ]
  }

公式模板语法：
  {{refKey}}             → refs[refKey] 的 JSONPath 指向数据
  SUM({{refKey}})        → refs 指向数组，重建时展开/求和
  数值常量（0.5 等）      → 直接嵌入公式，不入 refs
  Excel 局部中间量        → 保留原单元格引用（不入 refs，cells 重建还原）

用法：
  python scripts/extract_calculation_chain.py [--excel PATH] [--output PATH]
"""

import json
import re
import sys
import argparse
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("ERROR: openpyxl not installed. Run: pip install openpyxl")
    sys.exit(1)

DEFAULT_EXCEL = "outputs/房地产评估明细表-计算模板.xlsx"
DEFAULT_OUTPUT = "outputs/calculation_chain.json"


# ── 比值对折叠规则（评估对象指数/实例指数 → 合并系数）───────────────
# Excel 公式 T5/V5 = 评估对象交易指数/实例交易指数；JSON 只存合并系数
# transactionSituation（= 评估对象/实例）。因此 T5/V5 → {{txAdj}}。
PAIR_RULES = [
    (r"T5/V5", "txAdj", "methods.comps.comparableInstances[0].adjustments.transactionSituation"),
    (r"T6/V6", "mktAdj", "methods.comps.comparableInstances[0].adjustments.marketCondition"),
    (r"W5/Y5", "txAdj", "methods.comps.comparableInstances[1].adjustments.transactionSituation"),
    (r"W6/Y6", "mktAdj", "methods.comps.comparableInstances[1].adjustments.marketCondition"),
    (r"Z5/AB5", "txAdj", "methods.comps.comparableInstances[2].adjustments.transactionSituation"),
    (r"Z6/AB6", "mktAdj", "methods.comps.comparableInstances[2].adjustments.marketCondition"),
]

# ── 单格引用 → 语义名 + JSONPath ───────────────────────────────────
CELL_REFS = {
    # 评估明细表（面积/单价/总价）
    "评估明细表!M6": {"area": "property.area"},
    "评估明细表!N6": {"unitValue": "result.finalUnitValue"},
    "评估明细表!O6": {"totalValue": "result.finalTotalValue"},
    # 市场价比较法 成交单价（T4/W4/Z4 → 各实例）
    "市场价比较法!T4": {"unitPrice": "methods.comps.comparableInstances[0].unitPrice"},
    "市场价比较法!W4": {"unitPrice": "methods.comps.comparableInstances[1].unitPrice"},
    "市场价比较法!Z4": {"unitPrice": "methods.comps.comparableInstances[2].unitPrice"},
    # 市场价比较法 比准单价（前序节点结果）
    "市场价比较法!T32": {"adjPrice": "methods.comps.comparableInstances[0].adjustedUnitPrice"},
    "市场价比较法!W32": {"adjPrice": "methods.comps.comparableInstances[1].adjustedUnitPrice"},
    "市场价比较法!Z32": {"adjPrice": "methods.comps.comparableInstances[2].adjustedUnitPrice"},
    # 收益法
    "住宅-收益法测算!G4": {"noi": "methods.income.netOperatingIncome.annualAmount"},
    "住宅-收益法测算!G5": {"egi": "methods.income.netOperatingIncome.effectiveGrossIncome"},
    "住宅-收益法测算!G11": {"oe": "methods.income.netOperatingIncome.operatingExpenses"},
    "住宅-收益法测算!G24": {"rate": "methods.income.rate.value"},
    "住宅-收益法测算!G25": {"growth": "methods.income.netOperatingIncome.growthRate"},
    "住宅-收益法测算!G26": {"forwardPeriod": "methods.income.holdingPeriod"},
    "住宅-收益法测算!G27": {"incomeValue": "methods.income.finalValue.total"},
    "住宅-收益法测算!J27": {"incomeValue": "methods.income.finalValue.total"},
    "住宅-收益法测算!I27": {"incomeWeight": "result.weightAllocation.income"},
    "住宅-收益法测算!I28": {"compsWeight": "result.weightAllocation.comps"},
    "住宅-收益法测算!J28": {"compsValue": "methods.comps.finalValue.total"},
    "住宅-收益法测算!J29": {"finalTotal": "result.finalTotalValue"},
}

# ── 子项展开式 → SUM(区域) 折叠 ────────────────────────────────────
# 实例1: 评估对象列 T，实例指数列 V（区位 V7:V18 12项 / 权益 V19:V23 5项 / 实物 V24:V31 8项）
# 实例2: 实例指数列 Y
# 实例3: 实例指数列 AB
# 布局常量: -1100 = -(12-1)*100, -400 = -(5-1)*100, -700 = -(8-1)*100（全 100 时比值 = 1）
FACTOR_LAYOUT = {
    "市场价比较法": {
        0: {"col": "V", "ranges": [("loc", 7, 18), ("int", 19, 23), ("phy", 24, 31)],
            "path": "methods.comps.comparableInstances[0].adjustments."},
        1: {"col": "Y", "ranges": [("loc", 7, 18), ("int", 19, 23), ("phy", 24, 31)],
            "path": "methods.comps.comparableInstances[1].adjustments."},
        2: {"col": "AB", "ranges": [("loc", 7, 18), ("int", 19, 23), ("phy", 24, 31)],
            "path": "methods.comps.comparableInstances[2].adjustments."},
    }
}

DETAIL_JSONPATH = {
    "loc": "locationDetails",
    "int": "interestDetails",
    "phy": "physicalDetails",
}


def _build_expanded_sum_rules() -> list[tuple[str, str, str]]:
    """生成 (展开式正则, 语义名, JSONPath) 列表，如 V7+V8+...+V18 → SUM({{locFactors0}})。"""
    rules = []
    for sheet, instances in FACTOR_LAYOUT.items():
        for idx, cfg in instances.items():
            col = cfg["col"]
            for kind, start, end in cfg["ranges"]:
                cells = "+".join(f"{col}{r}" for r in range(start, end + 1))
                ref_key = f"{kind}Factors{idx}"
                path = cfg["path"] + DETAIL_JSONPATH[kind]
                rules.append((cells, ref_key, path))
    return rules


EXPANDED_SUM_RULES = _build_expanded_sum_rules()


def cell_to_paths(cell_ref: str) -> dict:
    """Excel 单元格引用 → {语义名: JSONPath} 映射。找不到返回空 dict。"""
    return CELL_REFS.get(cell_ref, {})


def translate_formula(formula: str, excel_ref: str) -> tuple[str, dict, list]:
    """
    将 Excel 公式翻译为 calculationChain 公式模板。
    返回 (公式模板, refs映射, 未识别引用列表)。
    替换顺序：比值对 → 子项展开式 → 单格引用。
    """
    if not formula or not formula.startswith("="):
        return formula, {}, []
    body = formula[1:].strip()
    refs = {}
    unknowns = []

    sheet_name = excel_ref.split("!")[0] if "!" in excel_ref else "市场价比较法"

    # 1) 子项展开式折叠（需在单格替换之前，避免 V7 被先行替换）
    for cells, ref_key, path in EXPANDED_SUM_RULES:
        if cells in body:
            body = body.replace(cells, f"SUM({{{{{ref_key}}}}})")
            refs[ref_key] = path

    # 2) 比值对折叠（如 T5/V5 → {{txAdj}}）
    for pattern, ref_key, path in PAIR_RULES:
        if re.search(pattern, body):
            body = re.sub(pattern, f"{{{{{ref_key}}}}}", body)
            refs[ref_key] = path

    # 3) 单格引用（sheet!cell 与同 sheet 内引用）
    pattern = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9]+)!(\$?[A-Z]{1,2}\$?\d+)")
    local_pattern = re.compile(r"(?<![A-Z])(\$?[A-Z]{1,2}\$?\d+)(?![A-Z0-9])")

    def replace_cell(m):
        sheet, cell = m.group(1), m.group(2)
        key = f"{sheet}!{cell.replace('$', '')}"
        mapping = cell_to_paths(key)
        if not mapping:
            unknowns.append(key)
            return m.group(0)
        name, path = next(iter(mapping.items()))
        refs[name] = path
        return f"{{{{{name}}}}}"

    body = pattern.sub(replace_cell, body)

    def replace_local(m):
        cell = m.group(1).replace("$", "")
        key = f"{sheet_name}!{cell}"
        mapping = cell_to_paths(key)
        if not mapping:
            unknowns.append(key)
            return m.group(0)
        name, path = next(iter(mapping.items()))
        refs[name] = path
        return f"{{{{{name}}}}}"

    body = local_pattern.sub(replace_local, body)
    return body, refs, unknowns


# ── 核心节点定义 ──────────────────────────────────────────────────
# (id, excel_ref, target_path, description, 自定义公式覆盖 or None)
# refs 中同 JSONPath 的多语义名（如 adjPrice 三实例）会在 translate 时被后写覆盖，
# 因此这里对多实例节点用 override 显式声明公式，保证模板确定性。
CORE_NODES = [
    (
        "comps.adjustedUnitPrice.instance1",
        "市场价比较法!T32",
        "methods.comps.comparableInstances[0].adjustedUnitPrice",
        "比准单价（实例1）= 成交单价 × 交易情况 × 市场状况 × 区位偏差合并 × 权益偏差合并 × 实物偏差合并。子项合并为偏差加总法：系数=100/(100+Σ(f-100))，Excel 展开式 100/(Σf-(n-1)*100)。",
        None,
    ),
    (
        "comps.adjustedUnitPrice.instance2",
        "市场价比较法!W32",
        "methods.comps.comparableInstances[1].adjustedUnitPrice",
        "比准单价（实例2），同上结构",
        None,
    ),
    (
        "comps.adjustedUnitPrice.instance3",
        "市场价比较法!Z32",
        "methods.comps.comparableInstances[2].adjustedUnitPrice",
        "比准单价（实例3），同上结构",
        None,
    ),
    (
        "comps.finalUnitPrice",
        "市场价比较法!T34",
        "methods.comps.finalValue.unit",
        "比准单价加权平均 = 实例1×0.5 + 实例2×0.3 + 实例3×0.2，四舍五入到十位。权重为模板常量 0.5/0.3/0.2（Excel T33/W33/Z33 数值单元格）。",
        "ROUND(({{adjPrice0}}*0.5+{{adjPrice1}}*0.3+{{adjPrice2}}*0.2),-1)",
    ),
    (
        "income.noi",
        "住宅-收益法测算!G4",
        "methods.income.netOperatingIncome.annualAmount",
        "年净收益 = 有效毛收入 − 运营费用",
        None,
    ),
    (
        "income.value",
        "住宅-收益法测算!G27",
        "methods.income.finalValue.total",
        "收益价值（报酬资本化分段折现：前 forwardPeriod 年递增折现 + 剩余年限折现）。G23（剩余年限 = 收益期−前段）为 Excel 局部中间量，schema 无对应字段，cells 重建时还原为 G23 引用。",
        None,
    ),
    (
        "result.finalTotalValue",
        "住宅-收益法测算!J29",
        "result.finalTotalValue",
        "最终结果 = 收益价值 × 收益权重 + 比较法价值 × 比较权重（四舍五入到十位）",
        None,
    ),
    (
        "result.totalValue",
        "评估明细表!O6",
        "result.finalTotalValue",
        "评估总价 = 面积 × 单价（四舍五入到元）",
        "ROUND({{area}}*{{unitValue}},0)",
    ),
]


def extract_chain(excel_path: str) -> dict:
    """从 Excel 读取核心单元格公式，构建 calculationChain。"""
    wb = openpyxl.load_workbook(excel_path, data_only=False)
    nodes = []

    for node_id, excel_ref, target, desc, override in CORE_NODES:
        sheet, cell = excel_ref.split("!")
        ws = wb[sheet]
        raw_formula = ws[cell].value
        if raw_formula is None:
            print(f"  [跳过] {excel_ref} 无公式")
            continue

        formula, refs, unknowns = translate_formula(str(raw_formula), excel_ref)
        if override:
            formula = override
            # override 公式的 refs 需显式声明（语义名 → JSONPath）
            refs = _resolve_override_refs(node_id)

        node = {
            "id": node_id,
            "target": target,
            "formula": formula,
            "refs": refs,
            "excelSource": excel_ref,
            "description": desc,
        }
        nodes.append(node)
        status = f"OK ({len(refs)} refs)"
        if unknowns:
            status += f", 局部引用 {len(unknowns)}: {sorted(set(unknowns))[:6]}"
        print(f"  [{status}] {node_id}: {formula[:90]}")

    wb.close()
    return {"version": "1.2", "nodes": nodes}


_OVERRIDE_REFS = {
    "comps.finalUnitPrice": {
        "adjPrice0": "methods.comps.comparableInstances[0].adjustedUnitPrice",
        "adjPrice1": "methods.comps.comparableInstances[1].adjustedUnitPrice",
        "adjPrice2": "methods.comps.comparableInstances[2].adjustedUnitPrice",
    },
    "result.totalValue": {
        "area": "property.area",
        "unitValue": "result.finalUnitValue",
    },
}


def _resolve_override_refs(node_id: str) -> dict:
    return dict(_OVERRIDE_REFS.get(node_id, {}))


def main():
    parser = argparse.ArgumentParser(description="Excel 模板 → JSON calculationChain 提取")
    parser.add_argument("--excel", default=DEFAULT_EXCEL, help="Excel 模板路径")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="输出 JSON 路径")
    args = parser.parse_args()

    excel_path = Path(args.excel)
    if not excel_path.exists():
        print(f"ERROR: Excel 文件不存在: {excel_path}")
        sys.exit(1)

    print(f"提取计算链: {excel_path}")
    chain = extract_chain(str(excel_path))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chain, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 计算链已保存: {output_path}（{len(chain['nodes'])} 个节点）")


if __name__ == "__main__":
    main()
