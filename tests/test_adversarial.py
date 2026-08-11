"""
对抗测试 — 把审查报告 8 个攻击固化成"恶意输入必须被拦截"的 pytest 用例。

参考：outputs/对抗式审查报告_2026-08-11.md §3 发现5

每个用例构造一种恶意变异，断言验证器必须返回至少一条错误。
这是"负向测试"的固定部分——确保 schema 不只是"对良好样本绿"，
而是"对恶意输入红"。
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCHEMA_PATH = ROOT / "schema" / "appraisal-result.schema.json"
EXAMPLE_PATH = ROOT / "schema" / "example-武汉洪山住宅.json"

sys.path.insert(0, str(ROOT / "scripts"))
from validate_appraisal_json import validate_full


@pytest.fixture(scope="session")
def example():
    with open(EXAMPLE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _copy(data):
    """深拷贝，供负面用例修改。"""
    return json.loads(json.dumps(data))


# ════════════════════════════════════════════════════════
# 攻击 1: methods 空对象 — "一份没有任何测算方法的估价结果"
# 根因: methods 没有 additionalProperties:false + minProperties
# ════════════════════════════════════════════════════════
def test_attack_1_empty_methods(example):
    data = _copy(example)
    data["methods"] = {}
    errors = validate_full(data)
    assert errors, "攻击1失败: 空 methods 对象应被拦截"


# ════════════════════════════════════════════════════════
# 攻击 2: weightSum = 999 — "权重总和不是1.0"
# 根因: schema 只要求 weightSum "存在"，没有 const: 1.0
# ════════════════════════════════════════════════════════
def test_attack_2_weightsum_nonone(example):
    data = _copy(example)
    data["result"]["weightSum"] = 999
    errors = validate_full(data)
    assert errors, "攻击2失败: weightSum≠1.0 应被拦截"


# ════════════════════════════════════════════════════════
# 攻击 3: valueDate = "下周三" — "中文口语日期"
# 根因: format: "date" 需 FormatChecker 才能生效
# ════════════════════════════════════════════════════════
def test_attack_3_invalid_date(example):
    data = _copy(example)
    data["valuation"]["valueDate"] = "下周三"
    errors = validate_full(data)
    assert errors, "攻击3失败: 非 YYYY-MM-DD 格式日期应被拦截"


# ════════════════════════════════════════════════════════
# 攻击 4: redLineChecks 空数组 — "一条红线都没检查"
# 根因: 数组没有 minItems
# ════════════════════════════════════════════════════════
def test_attack_4_empty_redline_checks(example):
    data = _copy(example)
    data["methods"]["comps"]["redLineChecks"] = []
    errors = validate_full(data)
    assert errors, "攻击4失败: 空 redLineChecks 应被拦截"


# ════════════════════════════════════════════════════════
# 攻击 5: 拼错字段名 project.cllient — "额外的未知字段"
# 根因: project/property/valuation/result 没有 additionalProperties:false
# ════════════════════════════════════════════════════════
def test_attack_5_typo_field_name(example):
    data = _copy(example)
    data["project"]["cllient"] = "测试拼错字段"
    errors = validate_full(data)
    assert errors, "攻击5失败: 拼错的字段名 project.cllient 应被拦截"


# ════════════════════════════════════════════════════════
# 攻击 6: applicable=false 且缺 finalValue — "标记为不适用但没填理由"
# （这个攻击原本就被拦截，作为回归基线）
# ════════════════════════════════════════════════════════
def test_attack_6_not_applicable_no_final_value(example):
    data = _copy(example)
    data["methods"]["comps"]["applicable"] = False
    del data["methods"]["comps"]["finalValue"]
    errors = validate_full(data)
    assert errors, "攻击6失败: applicable=false 且缺 finalValue 应被拦截"


# ════════════════════════════════════════════════════════
# 攻击 7: methods.fakeMethod — "未定义的方法名"
# 根因: methods 没有 additionalProperties:false
# ════════════════════════════════════════════════════════
def test_attack_7_fake_method(example):
    data = _copy(example)
    data["methods"]["fakeMethod"] = {"applicable": True, "finalValue": {}, "weight": 1.0, "redLineChecks": []}
    errors = validate_full(data)
    assert errors, "攻击7失败: 未定义的 fakeMethod 应被拦截"


# ════════════════════════════════════════════════════════
# 攻击 8: 可比实例仅1个 — "红线要求≥3"
# 根因: comparableInstances 没有 minItems
# ════════════════════════════════════════════════════════
def test_attack_8_single_comparable_instance(example):
    data = _copy(example)
    data["methods"]["comps"]["comparableInstances"] = [
        data["methods"]["comps"]["comparableInstances"][0]
    ]
    errors = validate_full(data)
    assert errors, "攻击8失败: 仅1个可比实例 (≤2) 应被拦截"


# ════════════════════════════════════════════════════════
# 额外对抗: 扩展字段在嵌套对象中
# ════════════════════════════════════════════════════════
def test_attack_extra_field_in_property(example):
    data = _copy(example)
    data["property"]["secretField"] = "oops"
    errors = validate_full(data)
    assert errors, "嵌套 property 不应接受额外字段"


def test_attack_extra_field_in_valuation(example):
    data = _copy(example)
    data["valuation"]["bogusField"] = "oops"
    errors = validate_full(data)
    assert errors, "嵌套 valuation 不应接受额外字段"
