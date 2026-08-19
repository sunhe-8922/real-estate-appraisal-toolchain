"""
test_schema_v15.py — v1.5 Schema 测试（evidenceItem.sourceGrade 信源等级结构化）

覆盖维度：
1. v1.5 schema 合法性与新增字段（evidenceItem.sourceGrade enum）
2. root schema == v1.5 版本化副本
3. 向后兼容 v1.4（sourceGrade 可选，旧数据无该字段仍通过）
4. sourceGrade 值约束（T0/T1/T2 接受，其他拒绝）
5. 版本路由（VERSION_SCHEMA_MAP 含 1.5，detect_version 识别 1.5）
6. 1.4 → 1.5 迁移（仅更新 schemaVersion，不推断 sourceGrade）
7. v1.4 schema 拒绝 v1.5 新增字段（版本隔离）
"""

import json
import sys
from pathlib import Path

import pytest
import jsonschema

ROOT = Path(__file__).parent.parent
SCHEMA_DIR = ROOT / "schema"
V15_SCHEMA_PATH = SCHEMA_DIR / "v1.5" / "appraisal-result.schema.json"
V14_SCHEMA_PATH = SCHEMA_DIR / "v1.4" / "appraisal-result.schema.json"
ROOT_SCHEMA_PATH = SCHEMA_DIR / "appraisal-result.schema.json"
EXAMPLE_PATH = ROOT / "schema" / "example-武汉洪山住宅.json"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

sys.path.insert(0, str(ROOT / "scripts"))
from validate_appraisal_json import detect_version, validate_full, VERSION_SCHEMA_MAP
from migrate_schema import _migrate_1_4_to_1_5
from helpers import make_minimal_decision_point


# ── Fixtures ───────────────────────────────────────────
@pytest.fixture(scope="session")
def v15_schema():
    with open(V15_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def v14_schema():
    with open(V14_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def root_schema():
    with open(ROOT_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def example_data():
    with open(EXAMPLE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _build_with_dps(dps):
    """基于示例数据构造带指定决策点的完整对象（schemaVersion 强制 v1.5）。"""
    with open(EXAMPLE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    data["schemaVersion"] = "1.5"
    data["decisionPoints"] = dps
    return data


def _evidence_item_schema(v15_schema):
    return v15_schema["$defs"]["evidenceItem"]["properties"]


# ════════════════════════════════════════════════════════
# 1. v1.5 Schema 合法性与新增字段
# ════════════════════════════════════════════════════════
class TestV15Schema:
    def test_v15_schema_is_valid_draft_2020_12(self, v15_schema):
        jsonschema.Draft202012Validator.check_schema(v15_schema)

    def test_v15_schema_version_is_pattern(self, v15_schema):
        sv = v15_schema["properties"]["schemaVersion"]
        assert sv["pattern"] == "^1\\.5$"

    def test_v15_has_source_grade_on_evidence_item(self, v15_schema):
        sg = _evidence_item_schema(v15_schema)["sourceGrade"]
        assert sg["type"] == "string"
        assert sg["enum"] == ["T0", "T1", "T2"]

    def test_source_grade_not_in_required(self, v15_schema):
        """sourceGrade 必须保持可选（向后兼容 v1.4 数据）。"""
        ev = v15_schema["$defs"]["evidenceItem"]
        assert "sourceGrade" not in ev["required"]

    def test_source_grade_optional_backward_compatible(self, example_data):
        """v1.4 数据（无 sourceGrade）应通过 v1.5 验证。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.5"
        errors = validate_full(data)
        assert not errors, f"无 sourceGrade 的旧数据应通过: {[e.message for e in errors]}"

    def test_root_schema_equals_v15_copy(self, root_schema, v15_schema):
        """根目录 schema 应等于 v1.5 版本化副本（排除 $id）。"""
        r, v = dict(root_schema), dict(v15_schema)
        r.pop("$id"), v.pop("$id")
        assert r == v, "root schema 应等于 v1.5 版本化副本"

    def test_v15_backward_compatible_with_v14(self, v14_schema, v15_schema):
        """v1.5 是 v1.4 的超集：v1.4 的所有 required 字段在 v1.5 中也 required。"""
        for field in v14_schema["required"]:
            assert field in v15_schema["required"], f"{field} 在 v1.5 中缺失 required"


# ════════════════════════════════════════════════════════
# 2. sourceGrade 值约束
# ════════════════════════════════════════════════════════
class TestSourceGrade:
    def test_source_grade_t0_accepted(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.5"
        dp = make_minimal_decision_point()
        dp["evidence"] = [
            {"item": "委托合同", "source": "委托合同", "sourceGrade": "T0"}
        ]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert not errors, f"T0 应接受: {[e.message for e in errors]}"

    def test_source_grade_t1_t2_accepted(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.5"
        dp = make_minimal_decision_point()
        dp["evidence"] = [
            {"item": "平台数据", "source": "链家", "sourceGrade": "T1"},
            {"item": "论坛信息", "source": "论坛", "sourceGrade": "T2"},
        ]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert not errors, f"T1/T2 应接受: {[e.message for e in errors]}"

    def test_source_grade_invalid_value_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.5"
        dp = make_minimal_decision_point()
        dp["evidence"] = [
            {"item": "委托合同", "source": "委托合同", "sourceGrade": "T3"}
        ]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "非法 sourceGrade（T3）应被拒绝"

    def test_source_grade_non_string_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.5"
        dp = make_minimal_decision_point()
        dp["evidence"] = [
            {"item": "委托合同", "source": "委托合同", "sourceGrade": 1}
        ]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "非字符串 sourceGrade 应被拒绝"

    def test_v15_fields_rejected_by_v14_schema(self, example_data):
        """v1.5 新增字段（sourceGrade）在 v1.4 schema 下应被拒绝（版本隔离）。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.4"
        dp = make_minimal_decision_point()
        dp["evidence"] = [
            {"item": "委托合同", "source": "委托合同", "sourceGrade": "T0"}
        ]
        data["decisionPoints"] = [dp]
        errors = validate_full(data, version="1.4")
        assert errors, "v1.4 schema 应拒绝 sourceGrade（additionalProperties: false）"


# ════════════════════════════════════════════════════════
# 3. 版本路由
# ════════════════════════════════════════════════════════
class TestVersionRoutingV15:
    def test_version_map_contains_1_5(self):
        assert "1.5" in VERSION_SCHEMA_MAP

    def test_detect_1_5(self):
        assert detect_version({"schemaVersion": "1.5"}) == "1.5"

    def test_detect_unknown_version(self):
        assert detect_version({"schemaVersion": "2.0"}) == "unknown"


# ════════════════════════════════════════════════════════
# 4. 1.4 → 1.5 迁移
# ════════════════════════════════════════════════════════
class TestMigrationV15:
    def test_migrate_updates_schema_version(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.4"
        migrated, notes = _migrate_1_4_to_1_5(data)
        assert migrated["schemaVersion"] == "1.5"
        assert any("1.4 → 1.5" in n for n in notes)

    def test_migrate_does_not_infer_source_grade(self, example_data):
        """sourceGrade 不自动推断：旧数据以 source 文本内 (T0) 形式保留。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.4"
        # 构造纯 v1.4 数据（无 sourceGrade）
        for dp in data.get("decisionPoints", []):
            for ev in dp.get("evidence", []):
                ev.pop("sourceGrade", None)
        migrated, _ = _migrate_1_4_to_1_5(data)
        for dp in migrated.get("decisionPoints", []):
            for ev in dp.get("evidence", []):
                assert "sourceGrade" not in ev, "迁移不应自动推断 sourceGrade"

    def test_migrated_data_passes_v15_schema(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.4"
        migrated, _ = _migrate_1_4_to_1_5(data)
        errors = validate_full(migrated)
        assert not errors, f"迁移后数据应通过 v1.5: {[e.message for e in errors]}"


# ════════════════════════════════════════════════════════
# 5. CHANGELOG
# ════════════════════════════════════════════════════════
class TestChangelogV15:
    def test_changelog_has_v1_5_entry(self):
        content = CHANGELOG_PATH.read_text(encoding="utf-8")
        assert "v1.5" in content or "1.5" in content, "CHANGELOG 应记录 v1.5"
