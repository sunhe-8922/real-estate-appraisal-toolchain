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
  from validate_appraisal_json import validate_full, validate_fragment, format_errors, detect_version
"""

import json
import sys
from pathlib import Path

import jsonschema

SCHEMA_DIR = Path(__file__).parent.parent / "schema"
SCHEMA_PATH = SCHEMA_DIR / "appraisal-result.schema.json"

# 版本 → schema 路径映射
VERSION_SCHEMA_MAP = {
    "1.0": SCHEMA_DIR / "v1.0" / "appraisal-result.schema.json",
    "1.1": SCHEMA_DIR / "v1.1" / "appraisal-result.schema.json",
    "1.2": SCHEMA_DIR / "v1.2" / "appraisal-result.schema.json",
    "1.3": SCHEMA_DIR / "v1.3" / "appraisal-result.schema.json",
    "1.4": SCHEMA_DIR / "v1.4" / "appraisal-result.schema.json",
    "1.5": SCHEMA_DIR / "v1.5" / "appraisal-result.schema.json",
}

# 方法片段 → schema 内的路径
METHOD_FRAGMENTS = {
    "comps": ["methods", "comps"],
    "income": ["methods", "income"],
    "cost": ["methods", "cost"],
    "hypotheticalDev": ["methods", "hypotheticalDev"],
}


def _load_schema(version: str = None) -> dict:
    """
    加载指定版本的 schema。
    version=None → 使用默认（最新）schema。
    version="1.0" → 使用 v1.0 历史 schema（不可变）。
    version="1.1" → 使用 v1.1 schema。
    """
    if version is None:
        path = SCHEMA_PATH
    else:
        path = VERSION_SCHEMA_MAP.get(version, SCHEMA_PATH)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def detect_version(data: dict) -> str:
    """
    从数据中检测 schema 版本号。
    返回 "1.0" / "1.1" / "1.2" / "1.3" / "1.4" / "1.5" / "unknown"。
    """
    v = data.get("schemaVersion", "unknown")
    return v if v in VERSION_SCHEMA_MAP else "unknown"


def _extract_subschema(schema, path):
    """从完整 schema 中按路径提取子 schema。"""
    node = schema
    for key in path:
        node = node["properties"][key]
    return node


def _check_decision_point_uniqueness(data: dict) -> list:
    """
    业务校验：decisionPoints 的 id 必须唯一（v1.3.1 新增）。
    JSON Schema 无法表达数组元素唯一性，由本函数补充。
    """
    dps = data.get("decisionPoints")
    if not isinstance(dps, list):
        return []
    seen = {}
    errors = []
    for i, dp in enumerate(dps):
        if not isinstance(dp, dict):
            continue  # 非对象元素由 schema 层拒绝
        dp_id = dp.get("id")
        if dp_id in seen:
            errors.append(_make_error(
                f"decisionPoints[{i}] 的 id '{dp_id}' 重复（与 decisionPoints[{seen[dp_id]}] 冲突），id 必须唯一",
                ["decisionPoints", i, "id"],
            ))
        else:
            seen[dp_id] = i
    return errors


def _check_decision_chain(data: dict) -> list:
    """
    业务校验：驳回后决策链约束（v1.4 新增，P2-2 决策链模型）。

    规则（对应《决策点规格定义》第四章）：
    C1. supersedes 引用的 id 必须存在于 decisionPoints 中
    C2. 不得自引用
    C3. 被取代的 DP 必须 status=rejected（只有被否决的决策点才会被取代）
    C4. 1:1 后继：同一 DP id 最多被一个其它 DP 取代（防分叉）
    C5. 不得成环（沿 supersedes 链不得回到自己）
    C6. attempt 一致性：若提供 attempt，须 = 被取代 DP 的 attempt + 1
    """
    dps = data.get("decisionPoints")
    if not isinstance(dps, list):
        return []

    def _code_key(x):
        """码层 key 归一（Round 6 / P1-1）：非字符串 id 统一渲染为哨兵 <no-id>，
        与 JS 端 validateChainCodes 同构，消除 None vs undefined 的渲染漂移。"""
        return x if isinstance(x, str) else "<no-id>"

    by_id = {}
    errors = []
    reported_c4 = set()  # 去重：同一被取代 key 只报一次（对齐 JS 条数口径，Round 3）
    for i, dp in enumerate(dps):
        # 对齐 JS string-only 语义（P1-1）：非字符串 id 不进 by_id
        if isinstance(dp, dict) and isinstance(dp.get("id"), str):
            by_id[dp["id"]] = (i, dp)

    for i, dp in enumerate(dps):
        if not isinstance(dp, dict):
            continue
        dp_id = dp.get("id")
        supersedes = dp.get("supersedes")
        # 对齐 JS string-only 语义（P1-1）：非字符串 supersedes 不参与任何 C 类检查
        if not isinstance(supersedes, str):
            continue
        base = ["decisionPoints", i]

        # C2: 自引用
        if supersedes == dp_id:
            errors.append(_make_error(
                f"decisionPoints[{i}] 的 supersedes 引用了自身 '{dp_id}'，不得自引用",
                base + ["supersedes"],
                code=f"C2:key={_code_key(dp_id)}",
            ))
            continue

        # C1: 存在性
        if supersedes not in by_id:
            errors.append(_make_error(
                f"decisionPoints[{i}] 的 supersedes 引用了不存在的决策点 '{supersedes}'",
                base + ["supersedes"],
                code=f"C1:key={supersedes}",
            ))
            continue

        prev_idx, prev = by_id[supersedes]

        # C3: 被取代者必须被驳回
        if prev.get("status") != "rejected":
            errors.append(_make_error(
                f"decisionPoints[{i}] 的 supersedes 指向 '{supersedes}'（status={prev.get('status')}），"
                f"只有 status=rejected 的决策点才能被取代",
                base + ["supersedes"],
                code=f"C3:key={supersedes}",
            ))

        # C4: 1:1 后继（防分叉）
        for j, other in enumerate(dps):
            if j != i and isinstance(other, dict) and other.get("supersedes") == supersedes:
                if supersedes not in reported_c4:
                    errors.append(_make_error(
                        f"decisionPoints[{j}] 与 decisionPoints[{i}] 都声明 supersedes='{supersedes}'，"
                        f"同一决策点只能被一个后继取代",
                        base + ["supersedes"],
                        code=f"C4:key={supersedes}",
                    ))
                    reported_c4.add(supersedes)
                break

        # C5: 不得成环（沿链走，若回到自己则成环）
        # 对齐 JS（P1-1）：非字符串 id 的 dp 跳过 C5——否则 cursor 终值 None == dp_id(None)
        # 会产生假阳性"环"（审查实测：缺 id 的 dp 被误报 C5:key=None）。
        # 注意只跳过 C5：JS 端 C6 对缺 id 的 dp 照常检查，此处 continue 会破坏 C6 对齐。
        if isinstance(dp_id, str):
            visited = set()
            cursor = supersedes
            while cursor in by_id and cursor not in visited:
                if cursor == dp_id:
                    break  # 回到起点，成环
                visited.add(cursor)
                cursor = by_id[cursor][1].get("supersedes")
            if cursor == dp_id:
                errors.append(_make_error(
                    f"decisionPoints[{i}] 的决策链存在环（{dp_id} → … → {dp_id}）",
                    base + ["supersedes"],
                    code=f"C5:key={dp_id}",
                ))

        # C6: attempt 一致性
        attempt = dp.get("attempt")
        # P0-1 修复（与 JS typeof number 语义对齐）：任何实数（int/float，bool 除外）
        # 都进入检查——整数值浮点（2.0）与整数同权，非整数浮点（2.5）按数值比较报 C6。
        if isinstance(attempt, (int, float)) and not isinstance(attempt, bool):
            prev_attempt = prev.get("attempt")
            # 与 JS nextAttempt() 语义对齐：缺失或非法（非 number / <1）视作 1
            if (not isinstance(prev_attempt, (int, float))
                    or isinstance(prev_attempt, bool) or prev_attempt < 1):
                prev_attempt = 1
            if attempt != prev_attempt + 1:
                errors.append(_make_error(
                    f"decisionPoints[{i}] 的 attempt={attempt} 与 supersedes '{supersedes}'（attempt={prev_attempt}）"
                    f"不一致，应为 {prev_attempt + 1}",
                    base + ["attempt"],
                    code=f"C6:key={_code_key(dp_id)}",
                ))

    return errors


def validate_full(data: dict, version: str = None) -> list:
    """
    验证完整的 AppraisalCalculationResult 对象。
    返回错误列表，空列表=通过。
    启用 FormatChecker 以支持 format: "date" 等格式校验。

    version: 指定 schema 版本（None = 自动检测，unknown = 使用默认最新 schema）。
    """
    if version is None:
        version = detect_version(data)
    schema = _load_schema(version)
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    # 追加业务校验（schema 表达不了的跨字段/集合约束）
    errors = list(errors) + _check_decision_point_uniqueness(data) + _check_decision_chain(data)
    return errors


def validate_fragment(data: dict, method: str, version: str = None) -> list:
    """
    验证单个方法片段（不含外层 project/property/result 等）。
    method: comps / income / cost / hypotheticalDev
    version: 指定 schema 版本（None = 自动检测）。
    返回错误列表，空列表=通过。
    """
    if method not in METHOD_FRAGMENTS:
        raise ValueError(f"未知方法: {method}. 可选: {list(METHOD_FRAGMENTS)}")

    if version is None:
        version = detect_version(data) if isinstance(data, dict) else None
    schema = _load_schema(version)
    subschema = _extract_subschema(schema, METHOD_FRAGMENTS[method])

    # type: ["object", "null"] — 如果 data 是 None，直接通过
    if data is None:
        return []

    # 把 $defs 注入子 schema，使 $ref: "#/$defs/redLineCheck" 可解析
    wrapper = {"$defs": schema.get("$defs", {}), **subschema}
    validator = jsonschema.Draft202012Validator(
        wrapper,
        format_checker=jsonschema.FormatChecker(),
    )
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return errors


def validate_degraded(data: dict) -> list:
    """
    验证降级模式对象。
    降级模式要求：
    1. sourceMode == "naturalLanguage"
    2. 至少有一个方法通过全部红线检查（降级模式仍须验红线）
    """
    errors = validate_full(data)

    # 额外降级模式检查
    if data.get("sourceMode") != "naturalLanguage":
        errors = list(errors) + [
            _make_error("sourceMode 必须为 'naturalLanguage'（降级模式）", ["sourceMode"])
        ]

    # 业务规则：降级模式至少一个方法红线条目非空（确保已做红线检查）
    methods = data.get("methods", {}) or {}
    has_redline_check = False
    for method_name, method_data in methods.items():
        if isinstance(method_data, dict) and method_data.get("applicable"):
            redlines = method_data.get("redLineChecks") or []
            if len(redlines) > 0:
                has_redline_check = True
                break
    if not has_redline_check:
        errors = list(errors) + [
            _make_error(
                "降级模式下至少一个适用方法必须有 redLineChecks（不能全为空）",
                ["methods"],
            )
        ]

    return errors


def _make_error(message, path, code=None):
    """构造一个简单的错误对象。

    code（可选）：机器可比对的错误编码，形如 `C4:key=DP-comp`（决策链 C1-C6 专用）。
    人类可读文案保持自然语言不变——报告/命令行输出不受影响，code 只供程序比对，
    消除双端"人工读差"（假设池 #6；此前靠关键词匹配分类，脆弱且易漏）。
    """
    class _Err:
        def __init__(self, message, path, code=None):
            self.message = message
            self.path = path
            self.code = code
        def __str__(self):
            return self.message
    return _Err(message, path, code)


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
