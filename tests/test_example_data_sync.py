"""
test_example_data_sync.py — 前端内嵌示例数据与 schema/示例数据同步锁定

背景（第四轮审查 P1-1 教训）：升级 schema/示例数据时若不同步 app/js/example-data.js
（前端手工提取副本），会导致前端演示数据与项目契约脱节。
本测试将"升级 schema 时须同步 example-data.js"从文档约定变成可执行校验：
任何一侧（schema / 示例数据 / example-data.js）单独变更而不同步，测试立即失败。
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
EXAMPLE_DATA_JS = ROOT / "app" / "js" / "example-data.js"
EXAMPLE_PATH = ROOT / "schema" / "example-武汉洪山住宅.json"
ROOT_SCHEMA_PATH = ROOT / "schema" / "appraisal-result.schema.json"


def _parse_example_data_js():
    """从 example-data.js 提取内嵌 JSON 对象。"""
    src = EXAMPLE_DATA_JS.read_text(encoding="utf-8")
    m = re.search(r"window\.EXAMPLE_DATA = (\{.*\});?\s*$", src, re.S)
    assert m, "example-data.js 应含 window.EXAMPLE_DATA = {...}"
    return json.loads(m.group(1))


class TestExampleDataSync:
    def test_example_data_schema_version_matches_root(self):
        """example-data.js 的 schemaVersion 必须与根 schema pattern 一致。"""
        data = _parse_example_data_js()
        schema = json.loads(ROOT_SCHEMA_PATH.read_text(encoding="utf-8"))
        pattern = schema["properties"]["schemaVersion"]["pattern"]  # ^1\.5$
        assert re.fullmatch(pattern, data["schemaVersion"]), (
            f"example-data.js schemaVersion={data['schemaVersion']} 与根 schema pattern {pattern} 不一致——"
            "升级 schema 版本时必须同步 example-data.js"
        )

    def test_example_data_decision_points_in_sync_with_example(self):
        """example-data.js 的 decisionPoints 必须与示例数据完全一致（含 sourceGrade）。"""
        data = _parse_example_data_js()
        example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
        assert data["decisionPoints"] == example["decisionPoints"], (
            "example-data.js 的 decisionPoints 与 schema/example-武汉洪山住宅.json 不一致——"
            "修改示例数据决策链时必须同步 example-data.js（前端内嵌副本）"
        )

    def test_example_data_evidence_has_source_grade(self):
        """示例数据 22 条 evidence 应全部含结构化 sourceGrade（v1.5 信源等级）。"""
        data = _parse_example_data_js()
        evs = [e for dp in data["decisionPoints"] for e in dp.get("evidence", [])]
        assert evs, "示例数据应含 evidence"
        missing = [e for e in evs if "sourceGrade" not in e]
        assert not missing, f"{len(missing)} 条 evidence 缺 sourceGrade（v1.5 信源等级结构化）"
