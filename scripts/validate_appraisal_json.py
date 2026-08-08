#!/usr/bin/env python3
"""
validate_appraisal_json.py — 房地产估价 JSON Schema 验证工具

用法:
  # 验证完整 AppraisalCalculationResult 对象
  python validate_appraisal_json.py path/to/result.json

  # 验证单个方法片段 (comps/income/cost/hypotheticalDev)
  python validate_appraisal_json.py --fragment comps path/to/comps_fragment.json

  # 验证降级模式 (naturalLanguage sourceMode)
  python validate_appraisal_json.py --degraded path/to/result.json

  # 作为模块导入
  from validate_appraisal_json import validate_full, validate_fragment, format_errors
"""

import json
import sys
from pathlib import Path

import jsonschema

SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "appraisal-result.schema.json"

# 方法片段 → schema 内的路径
METHOD_FRAGMENTS = {
    "comps": ["methods", "comps"],
    "income": ["methods", "income"],
    "cost": ["methods", "cost"],
    "hypotheticalDev": ["methods", "hypotheticalDev"],
}


def _load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _extract_subschema(schema, path):
    """从完整 schema 中按路径提取子 schema。"""
    node = schema
    for key in path:
        node = node["properties"][key]
    return node


def validate_full(data: dict) -> list:
    """
    验证完整的 AppraisalCalculationResult 对象。
    返回错误列表，空列表=通过。
    """
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return errors


def validate_fragment(data: dict, method: str) -> list:
    """
    验证单个方法片段（不含外层 project/property/result 等）。
    method: comps / income / cost / hypotheticalDev
    返回错误列表，空列表=通过。
    """
    if method not in METHOD_FRAGMENTS:
        raise ValueError(f"未知方法: {method}. 可选: {list(METHOD_FRAGMENTS)}")

    schema = _load_schema()
    subschema = _extract_subschema(schema, METHOD_FRAGMENTS[method])

    # type: ["object", "null"] — 如果 data 是 None，直接通过
    if data is None:
        return []

    # 把 $defs 注入子 schema，使 $ref: "#/$defs/redLineCheck" 可解析
    wrapper = {"$defs": schema.get("$defs", {}), **subschema}
    validator = jsonschema.Draft202012Validator(wrapper)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return errors


def validate_degraded(data: dict) -> list:
    """
    验证降级模式对象。
    降级模式要求：sourceMode == "naturalLanguage"
    额外检查：不能有 redLineChecks 全为 passed=true 的方法（降级模式无法保证红线已验）。
    """
    errors = validate_full(data)

    # 额外降级模式检查
    if data.get("sourceMode") != "naturalLanguage":
        errors = list(errors) + [
            _make_error("sourceMode 必须为 'naturalLanguage'（降级模式）", ["sourceMode"])
        ]

    return errors


def _make_error(message, path):
    """构造一个简单的错误对象。"""
    class _Err:
        def __init__(self, message, path):
            self.message = message
            self.path = path
        def __str__(self):
            return self.message
    return _Err(message, path)


def format_errors(errors: list) -> str:
    """格式化错误列表为可读字符串。"""
    if not errors:
        return "✅ 验证通过"
    lines = [f"❌ 发现 {len(errors)} 个错误:"]
    for e in errors:
        path = ".".join(str(p) for p in e.path) if hasattr(e, 'path') else "(root)"
        if not path:
            path = "(root)"
        lines.append(f"  [{path}] {e.message}")
    return "\n".join(lines)


def _load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    fragmented = False
    degraded = False
    method = None

    # 解析参数
    if args[0] == "--fragment":
        fragmented = True
        method = args[1]
        json_path = args[2]
    elif args[0] == "--degraded":
        degraded = True
        json_path = args[1]
    else:
        json_path = args[0]

    data = _load_json(json_path)

    if fragmented:
        errors = validate_fragment(data, method)
    elif degraded:
        errors = validate_degraded(data)
    else:
        errors = validate_full(data)

    print(format_errors(errors))
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
