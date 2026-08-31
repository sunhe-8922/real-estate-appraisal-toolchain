"""
test_schema_malformed_inputs.py — 畸形输入的 schema 层断言（Round 7 / 假设池 #10）

**双层防线**的第二层（第一层见 `tests/test_diff_chain_consistency.py` 的固化锚点
NUM_SUP / NO_ID_C6 / COLON_fork，覆盖绕过 schema 的 validateChain 直调路径）：

  第一层 业务校验层：validateChain 直调（dp-console.html 无 schema 层）→ 固化锚点断言
  第二层 schema 层（本文件）：正常工程 JSON 在入口即被拦下 → 逐条断言拦截点

本文件断言的是**拦截点本身**（required / type / minimum），不只"是否合法"——
否则把 schema 改坏（比如放宽松）可能仍然报错、测试却绿。

⚠️ 已固化的重要行为：`attempt=2.0` **合法**（JSON Schema `type: integer` 接受整数值
浮点，jsonschema 4.26 实测）。这是 P0-1 双端漂移的暴露面——2.0 能穿过 schema 直达
业务校验 C6。若将来收紧该行为，必须同步确认 C6 的浮点语义（scripts/validate_appraisal_json.py）
与固化锚点 S3_a2.0_b3 不受影响。

运行：python -m pytest tests/test_schema_malformed_inputs.py -q
"""
import json
from pathlib import Path

import jsonschema
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys_path = str(PROJECT_ROOT / "tests")
import sys  # noqa: E402

if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from helpers import make_minimal_decision_point  # noqa: E402

SCHEMA_PATH = PROJECT_ROOT / "schema" / "appraisal-result.schema.json"


@pytest.fixture(scope="module")
def dp_validator():
    """decisionPoint 子 schema 校验器（保留 $defs 以解析内嵌 $ref）。"""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    sub = {"$defs": schema["$defs"], "$ref": "#/$defs/decisionPoint"}
    return jsonschema.Draft202012Validator(sub)


def _errors(validator, mutate=None, delete=None):
    dp = make_minimal_decision_point()
    if mutate:
        dp.update(mutate)
    for k in delete or []:
        dp.pop(k, None)
    return sorted(validator.iter_errors(dp), key=str)


def _assert_rejected_at(validator, mutate=None, delete=None, path=(), keyword=None, label=""):
    errs = _errors(validator, mutate, delete)
    assert errs, f"{label}：schema 应拦截，实际通过"
    hits = [e for e in errs
            if tuple(e.absolute_path) == tuple(path) and (keyword is None or e.validator == keyword)]
    assert hits, (
        f"{label}：应在 {list(path)!r}/{keyword} 处拦截，实际错误为 "
        f"{[(list(e.absolute_path), e.validator) for e in errs]}"
    )


def test_baseline_is_valid(dp_validator):
    """基线：helpers 构造的最小合法 DP 必须通过（否则后续断言无从谈起）。"""
    assert not _errors(dp_validator)


def test_missing_id_rejected(dp_validator):
    """缺 id → required 拦截（对应 validateChain 侧 NO_ID_C6 锚点的畸形形状）。"""
    _assert_rejected_at(dp_validator, delete=["id"], path=(), keyword="required", label="缺 id")


def test_non_string_id_rejected(dp_validator):
    """id=42 → type 拦截（JS/Python 端 string-only 语义的上游防线）。"""
    _assert_rejected_at(dp_validator, mutate={"id": 42}, path=("id",), keyword="type", label="id=42")


def test_numeric_supersedes_rejected(dp_validator):
    """supersedes=42 / 2.0 → type 拦截（对应 NUM_SUP 锚点的畸形形状）。"""
    _assert_rejected_at(dp_validator, mutate={"supersedes": 42}, path=("supersedes",),
                        keyword="type", label="supersedes=42")
    _assert_rejected_at(dp_validator, mutate={"supersedes": 2.0}, path=("supersedes",),
                        keyword="type", label="supersedes=2.0")


def test_non_integer_attempt_rejected(dp_validator):
    """attempt=2.5 / "2" / true → type 拦截（float 非整数、字符串、布尔都不算 integer）。"""
    for label, val in (("attempt=2.5", 2.5), ("attempt='2'", "2"), ("attempt=true", True)):
        _assert_rejected_at(dp_validator, mutate={"attempt": val}, path=("attempt",),
                            keyword="type", label=label)


def test_attempt_below_minimum_rejected(dp_validator):
    """attempt=0 / -1 → minimum 拦截（规格 4.2 规则 1：≥1）。"""
    for val in (0, -1):
        _assert_rejected_at(dp_validator, mutate={"attempt": val}, path=("attempt",),
                            keyword="minimum", label=f"attempt={val}")


def test_integer_valued_float_attempt_is_accepted_by_schema(dp_validator):
    """⚠️ 已固化的 schema 层缺口：`attempt=2.0` 合法（type: integer 接受整数值浮点）。

    这是 P0-1 双端漂移的暴露面：2.0 能穿过 schema 到达业务校验 C6。
    本断言不是"期望行为"，而是"记录事实"——若 schema 未来收紧，此处会变红，
    提醒同步复核 C6 浮点语义与固化锚点 S3_a2.0_b3 / S2_b2.5。
    """
    assert not _errors(dp_validator, mutate={"attempt": 2.0}), (
        "attempt=2.0 现在被 schema 放行了？若是刻意收紧，请同步复核 C6 浮点语义与固化锚点"
    )


def test_rejected_dp_with_supersedes_still_valid(dp_validator):
    """驳回后继 DP（status=rejected + supersedes + attempt 递增）在 schema 层合法——
    它是 validateChain 的业务校验对象，不应在 schema 层被误杀。"""
    dp = make_minimal_decision_point("DP-comp-2", status="rejected",
                                     supersedes="DP-comp", attempt=2)
    assert not sorted(dp_validator.iter_errors(dp), key=str)
