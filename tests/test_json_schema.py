"""
test_json_schema.py — JSON Schema 端到端验证测试

覆盖维度：
1. Schema 本身合法性 (Draft 2020-12)
2. 完整对象验证 (example + degradation fixture)
3. 单方法片段验证 (4个方法各自)
4. 负面用例 (缺字段/多字段/超范围/错误枚举)
5. 业务规则校验 (权重和/红线/一致性/可比实例数/历史年数/动态法利息利润)
"""

import copy
import json
from pathlib import Path

import jsonschema
import pytest

# ── 路径 ──────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
SCHEMA_PATH = ROOT / "schema" / "appraisal-result.schema.json"
EXAMPLE_PATH = ROOT / "schema" / "example-武汉洪山住宅.json"
FIXTURES_DIR = ROOT / "tests" / "fixtures"

VALIDATOR_SCRIPT = ROOT / "scripts" / "validate_appraisal_json.py"


# ── 公共 fixture ──────────────────────────────────────
@pytest.fixture(scope="session")
def schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def validator(schema):
    return jsonschema.Draft202012Validator(schema)


@pytest.fixture(scope="session")
def example_data():
    with open(EXAMPLE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def example_copy(example_data):
    """深拷贝，供负面用例修改。"""
    return copy.deepcopy(example_data)


def _load_fixture(name):
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def comps_fragment():
    return _load_fixture("comps_fragment.json")


@pytest.fixture(scope="session")
def income_fragment():
    return _load_fixture("income_fragment.json")


@pytest.fixture(scope="session")
def cost_fragment():
    return _load_fixture("cost_fragment.json")


@pytest.fixture(scope="session")
def hypo_dev_fragment():
    return _load_fixture("hypo_dev_fragment.json")


@pytest.fixture(scope="session")
def degradation_data():
    return _load_fixture("degradation_natural_language.json")


# ── 辅助函数 ──────────────────────────────────────────
def _extract_subschema(schema, path):
    node = schema
    for key in path:
        node = node["properties"][key]
    return node


def _validate_fragment(schema, data, method):
    path = {"comps": ["methods", "comps"],
            "income": ["methods", "income"],
            "cost": ["methods", "cost"],
            "hypotheticalDev": ["methods", "hypotheticalDev"]}[method]
    subschema = _extract_subschema(schema, path)
    if data is None:
        return []
    # 把 $defs 注入子 schema，使 $ref: "#/$defs/redLineCheck" 可解析
    wrapper = {"$defs": schema.get("$defs", {}), **subschema}
    v = jsonschema.Draft202012Validator(wrapper)
    return sorted(v.iter_errors(data), key=lambda e: list(e.path))


def _assert_no_errors(errors):
    if errors:
        msgs = [f"  [{'.'.join(str(p) for p in e.path) or 'root'}] {e.message}" for e in errors]
        pytest.fail("Expected no errors, got:\n" + "\n".join(msgs))


# ════════════════════════════════════════════════════════
# 1. Schema 本身合法性
# ════════════════════════════════════════════════════════
class TestSchemaValidity:
    def test_schema_is_valid_draft_2020_12(self, schema):
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_schema_has_required_fields(self, schema):
        required = schema["required"]
        for field in ["schemaVersion", "project", "property", "valuation",
                       "methods", "result", "crossMethodConsistency"]:
            assert field in required, f"{field} 应在 required 中"

    def test_schema_has_source_mode(self, schema):
        """降级策略引用的 sourceMode 字段必须在 schema 中定义。"""
        assert "sourceMode" in schema["properties"]
        enums = schema["properties"]["sourceMode"]["enum"]
        assert "json" in enums
        assert "naturalLanguage" in enums

    def test_schema_has_additional_properties_false(self, schema):
        """根对象和方法对象必须有 additionalProperties: false。"""
        assert schema.get("additionalProperties") is False
        for method in ["comps", "income", "cost", "hypotheticalDev"]:
            assert schema["properties"]["methods"]["properties"][method].get(
                "additionalProperties") is False, f"{method} 缺少 additionalProperties: false"

    def test_result_requires_weight_sum(self, schema):
        """weightSum 必须在 result.required 中。"""
        assert "weightSum" in schema["properties"]["result"]["required"]


# ════════════════════════════════════════════════════════
# 2. 完整对象验证
# ════════════════════════════════════════════════════════
class TestFullObjectValidation:
    def test_example_validates(self, validator, example_data):
        _assert_no_errors(sorted(validator.iter_errors(example_data), key=lambda e: list(e.path)))

    def test_example_has_source_mode_json(self, example_data):
        assert example_data.get("sourceMode") == "json"

    def test_degradation_validates(self, validator, degradation_data):
        _assert_no_errors(sorted(validator.iter_errors(degradation_data), key=lambda e: list(e.path)))

    def test_degradation_has_source_mode_natural_language(self, degradation_data):
        assert degradation_data.get("sourceMode") == "naturalLanguage"

    def test_degradation_has_redline_passed(self, degradation_data):
        """降级模式仍必须通过所有红线检查（虽然数据来源是自然语言）。"""
        for method_name in ["comps", "income"]:
            method = degradation_data["methods"][method_name]
            if method and method.get("applicable"):
                for check in method["redLineChecks"]:
                    assert check["passed"], f"{method_name} 红线未通过: {check['rule']}"


# ════════════════════════════════════════════════════════
# 3. 单方法片段验证
# ════════════════════════════════════════════════════════
class TestFragmentValidation:
    def test_comps_fragment_valid(self, schema, comps_fragment):
        errors = _validate_fragment(schema, comps_fragment, "comps")
        _assert_no_errors(errors)

    def test_income_fragment_valid(self, schema, income_fragment):
        errors = _validate_fragment(schema, income_fragment, "income")
        _assert_no_errors(errors)

    def test_cost_fragment_valid(self, schema, cost_fragment):
        errors = _validate_fragment(schema, cost_fragment, "cost")
        _assert_no_errors(errors)

    def test_hypo_dev_fragment_valid(self, schema, hypo_dev_fragment):
        errors = _validate_fragment(schema, hypo_dev_fragment, "hypotheticalDev")
        _assert_no_errors(errors)

    def test_null_method_valid(self, schema):
        """方法设为 null 时应通过验证。"""
        errors = _validate_fragment(schema, None, "cost")
        _assert_no_errors(errors)


# ════════════════════════════════════════════════════════
# 4. 负面用例 — 这些对象应该 FAIL
# ════════════════════════════════════════════════════════
class TestNegativeCases:
    def _assert_has_error(self, validator, data, expected_substring):
        errors = list(validator.iter_errors(data))
        msgs = [e.message for e in errors]
        assert any(expected_substring in m for m in msgs), \
            f"期望错误包含 '{expected_substring}'，实际: {msgs}"

    def test_missing_schema_version(self, validator, example_copy):
        del example_copy["schemaVersion"]
        self._assert_has_error(validator, example_copy, "schemaVersion")

    def test_missing_cross_method_consistency(self, validator, example_copy):
        del example_copy["crossMethodConsistency"]
        self._assert_has_error(validator, example_copy, "crossMethodConsistency")

    def test_missing_weight_sum(self, validator, example_copy):
        del example_copy["result"]["weightSum"]
        self._assert_has_error(validator, example_copy, "weightSum")

    def test_extra_field_at_root(self, validator, example_copy):
        """additionalProperties: false 应拒绝额外字段。"""
        example_copy["unexpectedField"] = "oops"
        self._assert_has_error(validator, example_copy, "Additional properties")

    def test_extra_field_in_method(self, validator, example_copy):
        example_copy["methods"]["comps"]["unexpectedField"] = "oops"
        self._assert_has_error(validator, example_copy, "Additional properties")

    def test_weight_out_of_range(self, validator, example_copy):
        example_copy["methods"]["comps"]["weight"] = 1.5
        self._assert_has_error(validator, example_copy, "1.5")

    def test_wrong_enum_calculation_mode(self, validator, example_copy):
        example_copy["methods"]["income"]["calculationMode"] = "invalidMode"
        self._assert_has_error(validator, example_copy, "invalidMode")

    def test_wrong_enum_premise(self, validator, example_copy):
        example_copy["methods"]["hypotheticalDev"] = {
            "applicable": True,
            "analysisMethod": "dynamic",
            "premise": "invalidPremise",
            "finalValue": {"total": 100, "unit": 10},
            "weight": 0.5,
            "redLineChecks": []
        }
        self._assert_has_error(validator, example_copy, "invalidPremise")

    def test_wrong_currency(self, validator, example_copy):
        example_copy["valuation"]["currency"] = "USD"
        self._assert_has_error(validator, example_copy, "CNY")

    def test_missing_final_value_in_method(self, validator, example_copy):
        del example_copy["methods"]["comps"]["finalValue"]
        self._assert_has_error(validator, example_copy, "finalValue")


# ════════════════════════════════════════════════════════
# 5. 业务规则校验 (超越 schema 的逻辑检查)
# ════════════════════════════════════════════════════════
class TestBusinessRules:
    """这些规则在 schema 中无法表达，需要单独验证。"""

    def test_weight_sum_equals_one(self, example_data):
        assert abs(example_data["result"]["weightSum"] - 1.0) < 0.001

    def test_weight_sum_degradation(self, degradation_data):
        assert abs(degradation_data["result"]["weightSum"] - 1.0) < 0.001

    def test_cross_method_consistency_all_passed(self, example_data):
        for item in example_data["crossMethodConsistency"]:
            assert item["passed"], f"跨方法一致性检查未通过: {item['checkItem']}"

    def test_cross_method_consistency_degradation(self, degradation_data):
        for item in degradation_data["crossMethodConsistency"]:
            assert item["passed"], f"降级模式跨方法一致性检查未通过: {item['checkItem']}"

    def test_all_redlines_passed(self, example_data):
        for method_name in ["comps", "income", "cost", "hypotheticalDev"]:
            method = example_data["methods"][method_name]
            if method and method.get("applicable"):
                for check in method["redLineChecks"]:
                    assert check["passed"], f"{method_name} 红线未通过: {check['rule']}"

    def test_comparable_instances_count(self, example_data):
        comps = example_data["methods"]["comps"]
        if comps and comps["applicable"]:
            assert len(comps["comparableInstances"]) >= 3, "可比实例必须≥3个"

    def test_comparable_instances_fixture(self, comps_fragment):
        if comps_fragment["applicable"]:
            assert len(comps_fragment["comparableInstances"]) >= 3

    def test_historical_data_years(self, example_data):
        income = example_data["methods"]["income"]
        if income and income["applicable"]:
            assert income["netOperatingIncome"]["historicalDataYears"] >= 3

    def test_historical_data_years_fixture(self, income_fragment):
        if income_fragment["applicable"]:
            assert income_fragment["netOperatingIncome"]["historicalDataYears"] >= 3

    def test_dynamic_method_no_interest_profit(self, hypo_dev_fragment):
        """动态分析法：investmentInterest=0 且 developerProfit=0 (4.5.6条)。"""
        if hypo_dev_fragment["applicable"] and hypo_dev_fragment["analysisMethod"] == "dynamic":
            costs = hypo_dev_fragment["subsequentCosts"]
            assert costs["investmentInterest"] == 0, "动态法投资利息必须为0"
            assert costs["developerProfit"] == 0, "动态法开发利润必须为0"

    def test_dynamic_method_example(self, example_data):
        hypo = example_data["methods"]["hypotheticalDev"]
        if hypo and hypo.get("applicable") and hypo.get("analysisMethod") == "dynamic":
            costs = hypo["subsequentCosts"]
            assert costs["investmentInterest"] == 0
            assert costs["developerProfit"] == 0

    def test_total_unit_consistency(self, example_data):
        """总价÷面积应约等于单价（允许1%误差）。"""
        r = example_data["result"]
        area = example_data["property"]["area"]
        expected_unit = r["finalTotalValue"] / area
        actual_unit = r["finalUnitValue"]
        assert abs(expected_unit - actual_unit) / actual_unit < 0.01, \
            f"总价÷面积={expected_unit:.0f} vs 单价={actual_unit}，差异>1%"

    def test_total_unit_consistency_degradation(self, degradation_data):
        r = degradation_data["result"]
        area = degradation_data["property"]["area"]
        expected_unit = r["finalTotalValue"] / area
        actual_unit = r["finalUnitValue"]
        assert abs(expected_unit - actual_unit) / actual_unit < 0.01

    def test_source_grade_is_valid_enum(self, comps_fragment):
        for inst in comps_fragment["comparableInstances"]:
            assert inst["sourceGrade"] in ["T0", "T1", "T2"], \
                f"sourceGrade 非法: {inst['sourceGrade']}"

    def test_redline_checks_cover_5_rules(self, comps_fragment):
        """比较法红线检查必须覆盖全部5条。"""
        if comps_fragment["applicable"]:
            rules = {c["rule"] for c in comps_fragment["redLineChecks"]}
            expected = {"可比实例数量", "成交距价值时点", "单项修正幅度",
                        "综合修正幅度", "最高价/最低价比"}
            assert rules == expected, f"红线检查不完整: 缺少 {expected - rules}"


# ════════════════════════════════════════════════════════
# 6. 验证脚本集成测试
# ════════════════════════════════════════════════════════
class TestValidationScript:
    """测试 scripts/validate_appraisal_json.py 的函数接口。"""

    def test_validate_full_passes_on_example(self):
        import sys
        sys.path.insert(0, str(VALIDATOR_SCRIPT.parent))
        from validate_appraisal_json import validate_full
        with open(EXAMPLE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        errors = validate_full(data)
        assert not errors, "example 应通过验证"

    def test_validate_full_fails_on_missing_field(self):
        import sys
        sys.path.insert(0, str(VALIDATOR_SCRIPT.parent))
        from validate_appraisal_json import validate_full
        with open(EXAMPLE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        del data["result"]["weightSum"]
        errors = validate_full(data)
        assert errors, "缺少 weightSum 应报错"

    def test_validate_fragment_comps(self):
        import sys
        sys.path.insert(0, str(VALIDATOR_SCRIPT.parent))
        from validate_appraisal_json import validate_fragment
        data = _load_fixture("comps_fragment.json")
        errors = validate_fragment(data, "comps")
        assert not errors

    def test_validate_fragment_income(self):
        import sys
        sys.path.insert(0, str(VALIDATOR_SCRIPT.parent))
        from validate_appraisal_json import validate_fragment
        data = _load_fixture("income_fragment.json")
        errors = validate_fragment(data, "income")
        assert not errors

    def test_validate_fragment_cost(self):
        import sys
        sys.path.insert(0, str(VALIDATOR_SCRIPT.parent))
        from validate_appraisal_json import validate_fragment
        data = _load_fixture("cost_fragment.json")
        errors = validate_fragment(data, "cost")
        assert not errors

    def test_validate_fragment_hypo_dev(self):
        import sys
        sys.path.insert(0, str(VALIDATOR_SCRIPT.parent))
        from validate_appraisal_json import validate_fragment
        data = _load_fixture("hypo_dev_fragment.json")
        errors = validate_fragment(data, "hypotheticalDev")
        assert not errors

    def test_validate_fragment_null_passes(self):
        import sys
        sys.path.insert(0, str(VALIDATOR_SCRIPT.parent))
        from validate_appraisal_json import validate_fragment
        errors = validate_fragment(None, "cost")
        assert not errors

    def test_validate_fragment_unknown_method_raises(self):
        import sys
        sys.path.insert(0, str(VALIDATOR_SCRIPT.parent))
        from validate_appraisal_json import validate_fragment
        with pytest.raises(ValueError, match="未知方法"):
            validate_fragment({}, "unknown")

    def test_format_errors_empty(self):
        import sys
        sys.path.insert(0, str(VALIDATOR_SCRIPT.parent))
        from validate_appraisal_json import format_errors
        result = format_errors([])
        assert "通过" in result

    def test_format_errors_nonempty(self):
        import sys
        sys.path.insert(0, str(VALIDATOR_SCRIPT.parent))
        from validate_appraisal_json import format_errors
        # 构造一个假错误
        class FakeErr:
            message = "test error"
            path = ["a", "b"]
        result = format_errors([FakeErr()])
        assert "1" in result
        assert "test error" in result
