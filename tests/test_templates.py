"""Tests for all 4 Excel template generators — verifies ROUND coverage and formula correctness.

Run: python -m pytest tests/ -v
"""
import re

import pytest

from conftest import ALL_WBS, SHEET_NAMES


# ── Helpers ──────────────────────────────────────────────────────────────────

CALC_RE = re.compile(r"(SUM\(|AVERAGE\(|IF\(|\*|/|MAX\(|MIN\()", re.IGNORECASE)
REF_RE = re.compile(r"^=[A-Z]+\d+$")
# Discount factor: =1/(1+rate)^n  or  =IF(...,1/(1+rate)^n,0)
DISCOUNT_FACTOR_RE = re.compile(r"1/\(1\+", re.IGNORECASE)


def _is_formula(val) -> bool:
    return isinstance(val, str) and val.startswith("=")


def _is_text_output(val) -> bool:
    """Formula returns text (contains quoted string in output)."""
    return '"' in val


def _is_discount_factor(val) -> bool:
    """Discount factor = 1/(1+r)^n — intermediate, needs precision, no ROUND."""
    return bool(DISCOUNT_FACTOR_RE.search(val))


def _is_calc(val) -> bool:
    """Final-value calculation formula (not reference, not text output,
    not discount factor, not display-only max/min)."""
    if not _is_formula(val) or bool(REF_RE.match(val)):
        return False
    if _is_text_output(val) or _is_discount_factor(val):
        return False
    # Pure MAX/MIN display (no SUM, *, /, IF, AVERAGE) — diagnostic, not calc
    has_real_calc = bool(re.search(r"(SUM\(|AVERAGE\(|IF\(|\*|/)", val, re.IGNORECASE))
    if not has_real_calc:
        return False
    return bool(CALC_RE.search(val))


def _has_round(val) -> bool:
    return "ROUND(" in val.upper()


def _is_percent(cell) -> bool:
    return "%" in (cell.number_format or "")


def _scan(wb, sheets):
    out = []
    for name in sheets:
        if name not in wb.sheetnames:
            continue
        for row in wb[name].iter_rows():
            for cell in row:
                if _is_formula(cell.value):
                    out.append((name, cell.coordinate, cell.value, _is_percent(cell)))
    return out


def _get_wb(request, template_name):
    return request.getfixturevalue(ALL_WBS[template_name])


# ── Sheet Structure Tests ───────────────────────────────────────────────────

@pytest.mark.parametrize("template_name", ["comps", "income", "cost", "hypo_dev"])
def test_expected_sheets_exist(request, template_name):
    wb = _get_wb(request, template_name)
    for sheet in SHEET_NAMES[template_name]:
        assert sheet in wb.sheetnames, f"Missing sheet '{sheet}' in {template_name}"


# ── ROUND Coverage (broad scan) ─────────────────────────────────────────────

@pytest.mark.parametrize("template_name", ["comps", "income", "cost", "hypo_dev"])
def test_all_calc_formulas_have_round(request, template_name):
    """Every calculation formula must be wrapped in ROUND, unless percentage format."""
    wb = _get_wb(request, template_name)
    sheets = SHEET_NAMES[template_name]
    formulas = _scan(wb, sheets)

    violations = [
        f"  {s}!{c}: {v}" for s, c, v, pct in formulas
        if not pct and _is_calc(v) and not _has_round(v)
    ]
    assert not violations, (
        f"{template_name}: {len(violations)} formula(s) missing ROUND:\n" + "\n".join(violations)
    )


# ── Comps Specific Tests ────────────────────────────────────────────────────

def test_comps_comparison_value_has_round(comps_wb):
    """比较法: 比较价格公式含 ROUND + 乘法."""
    ws = comps_wb["可比实例数据"]
    found = any(
        _has_round(c.value) and "*" in c.value
        for row in ws.iter_rows() for c in row if _is_formula(c.value)
    )
    assert found, "No ROUND(multiplication) comparison value in 可比实例数据"


def test_comps_summary_has_rounded_average(comps_wb):
    """比较价值汇总: AVERAGE/MEDIAN 含 ROUND."""
    ws = comps_wb["比较价值汇总"]
    found = any(
        _has_round(c.value) and ("AVERAGE" in c.value.upper() or "MEDIAN" in c.value.upper())
        for row in ws.iter_rows() for c in row if _is_formula(c.value)
    )
    assert found, "No ROUND(AVERAGE/MEDIAN) in 比较价值汇总"


# ── Income Specific Tests ────────────────────────────────────────────────────

def test_income_noi_has_round(income_wb):
    """净收益测算: 年净收益含 ROUND + SUM 或算术."""
    ws = income_wb["净收益测算"]
    found = any(
        _has_round(c.value) and ("SUM" in c.value.upper() or "+" in c.value or "-" in c.value)
        for row in ws.iter_rows() for c in row if _is_formula(c.value)
    )
    assert found, "No ROUND(SUM/arithmetic) NOI in 净收益测算"


def test_income_pv_discount_has_round(income_wb):
    """收益价值: 折现公式含 ROUND."""
    ws = income_wb["收益价值"]
    found = any(
        _has_round(c.value) and ("^" in c.value or "C3" in c.value)
        for row in ws.iter_rows() for c in row if _is_formula(c.value)
    )
    assert found, "No ROUND(discount) in 收益价值"


def test_income_total_value_has_round(income_wb):
    """收益价值: 收益总价值含 ROUND + 加法."""
    ws = income_wb["收益价值"]
    found = any(
        _has_round(c.value) and "+" in c.value
        for row in ws.iter_rows() for c in row if _is_formula(c.value)
    )
    assert found, "No ROUND(addition total) in 收益价值"


# ── Cost Specific Tests ─────────────────────────────────────────────────────

def test_cost_replacement_sum_has_round(cost_wb):
    """重置成本: SUM 含 ROUND."""
    ws = cost_wb["重置成本"]
    found = any(
        _has_round(c.value) and "SUM" in c.value.upper()
        for row in ws.iter_rows() for c in row if _is_formula(c.value)
    )
    assert found, "No ROUND(SUM) in 重置成本"


def test_cost_straight_line_depreciation_has_round(cost_wb):
    """折旧测算: 直线法折旧含 ROUND + MAX + MIN."""
    ws = cost_wb["折旧测算"]
    found = any(
        _has_round(c.value) and "MAX" in c.value.upper() and "MIN" in c.value.upper()
        for row in ws.iter_rows() for c in row if _is_formula(c.value)
    )
    assert found, "No ROUND(straight-line) in 折旧测算"


def test_cost_value_has_round(cost_wb):
    """成本价值: 成本价值含 ROUND."""
    ws = cost_wb["成本价值"]
    found = any(
        _has_round(c.value)
        for row in ws.iter_rows() for c in row if _is_formula(c.value)
    )
    assert found, "No ROUND formula in 成本价值"


# ── Hypo Dev Specific Tests ─────────────────────────────────────────────────

def test_hypo_dev_completed_value_has_round(hypo_dev_wb):
    """假设开发法: 开发完成后价值含 ROUND."""
    ws = hypo_dev_wb["假设开发法"]
    found = any(
        _has_round(c.value) and "B7" in c.value
        for row in ws.iter_rows() for c in row if _is_formula(c.value)
    )
    assert found, "No ROUND(completed value * B7) in 假设开发法"


def test_hypo_dev_discounts_have_round(hypo_dev_wb):
    """假设开发法: 至少3个折现公式含 ROUND."""
    ws = hypo_dev_wb["假设开发法"]
    count = sum(
        1 for row in ws.iter_rows() for c in row
        if _is_formula(c.value) and _has_round(c.value) and "/(1+" in c.value.replace(" ", "")
    )
    assert count >= 3, f"Expected >=3 discount ROUND formulas, found {count}"


def test_hypo_dev_dev_value_has_round(hypo_dev_wb):
    """假设开发法: 开发价值(总-支出)含 ROUND."""
    ws = hypo_dev_wb["假设开发法"]
    found = any(
        _has_round(c.value) and "-" in c.value
        for row in ws.iter_rows() for c in row if _is_formula(c.value)
    )
    assert found, "No ROUND(subtraction) development value in 假设开发法"


def test_hypo_dev_npv_has_round(hypo_dev_wb):
    """现金流时间线: NPV SUMPRODUCT 含 ROUND."""
    ws = hypo_dev_wb["现金流时间线"]
    found = any(
        _has_round(c.value) and "SUMPRODUCT" in c.value.upper()
        for row in ws.iter_rows() for c in row if _is_formula(c.value)
    )
    assert found, "No ROUND(SUMPRODUCT) NPV in 现金流时间线"


# ── File Integrity Tests ────────────────────────────────────────────────────

@pytest.mark.parametrize("template_name", ["comps", "income", "cost", "hypo_dev"])
def test_has_data_validations(request, template_name):
    """Each template should have >=1 data validation."""
    wb = _get_wb(request, template_name)
    total = sum(
        len(wb[s].data_validations.dataValidation)
        for s in SHEET_NAMES[template_name] if s in wb.sheetnames
    )
    assert total >= 1, f"{template_name}: no data validations"


@pytest.mark.parametrize("template_name", ["comps", "income", "cost", "hypo_dev"])
def test_has_comments(request, template_name):
    """Each template should have >=1 cell comment (GB/T references)."""
    wb = _get_wb(request, template_name)
    total = sum(
        1 for s in SHEET_NAMES[template_name] if s in wb.sheetnames
        for row in wb[s].iter_rows() for c in row if c.comment
    )
    assert total >= 1, f"{template_name}: no cell comments"
