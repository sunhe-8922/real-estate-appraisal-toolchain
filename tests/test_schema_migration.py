"""
test_schema_migration.py — Schema 版本化与迁移测试

覆盖维度：
1. v1.0 schema 不可变（历史快照）
2. v1.1 schema 新增字段可接受
3. 迁移脚本正确补全字段
4. validate_full 自动检测版本并路由到正确 schema
5. 1.0 数据用 1.0 schema 验证通过，用 1.1 schema 验证也通过（向后兼容）
6. CHANGELOG.md 存在且格式正确
"""

import json
import sys
from pathlib import Path

import pytest
import jsonschema

ROOT = Path(__file__).parent.parent
SCHEMA_DIR = ROOT / "schema"
V10_SCHEMA_PATH = SCHEMA_DIR / "v1.0" / "appraisal-result.schema.json"
V11_SCHEMA_PATH = SCHEMA_DIR / "v1.1" / "appraisal-result.schema.json"
EXAMPLE_PATH = ROOT / "schema" / "example-武汉洪山住宅.json"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
MIGRATE_SCRIPT = ROOT / "scripts" / "migrate_schema.py"

sys.path.insert(0, str(ROOT / "scripts"))
from validate_appraisal_json import detect_version, validate_full


# ── Fixture ───────────────────────────────────────────
@pytest.fixture(scope="session")
def v10_schema():
    with open(V10_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def v11_schema():
    with open(V11_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _strip_v12_fields(data: dict) -> None:
    """从数据中移除 v1.2 及 v1.3 新增字段，还原为干净 v1.1 数据。"""
    # 顶层 calculationChain（v1.2 新增）
    data.pop("calculationChain", None)
    # 顶层 decisionPoints（v1.3 新增）
    data.pop("decisionPoints", None)
    # adjustments 子项 details 数组（v1.2 新增）
    for inst in data.get("methods", {}).get("comps", {}).get("comparableInstances", []):
        adj = inst.get("adjustments", {})
        for key in ("locationDetails", "physicalDetails", "interestDetails"):
            adj.pop(key, None)


@pytest.fixture(scope="session")
def example_v11_data():
    """加载 example 并标记为 1.1（深拷贝后移除 v1.2 新增字段）。"""
    with open(EXAMPLE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    _strip_v12_fields(data)
    data["schemaVersion"] = "1.1"
    return data


@pytest.fixture
def example_v10_copy(example_v11_data):
    """深拷贝并将 schemaVersion 改回 1.0，模拟真实 v1.0 数据。"""
    data = json.loads(json.dumps(example_v11_data))
    data["schemaVersion"] = "1.0"
    # 移除 v1.1 新增字段（模拟干净 v1.0 数据）
    if "calculationMode" in data.get("result", {}):
        del data["result"]["calculationMode"]
    if "crossMethodNotes" in data:
        del data["crossMethodNotes"]
    if "estimatedDate" in data.get("valuation", {}):
        del data["valuation"]["estimatedDate"]
    return data


# ════════════════════════════════════════════════════════
# 1. v1.0 Schema 不可变性
# ════════════════════════════════════════════════════════
class TestV10SchemaImmutable:
    def test_v10_schema_is_valid_draft_2020_12(self, v10_schema):
        jsonschema.Draft202012Validator.check_schema(v10_schema)

    def test_v10_schema_version_is_const_1_0(self, v10_schema):
        sv = v10_schema["properties"]["schemaVersion"]
        assert sv.get("const") == "1.0", "v1.0 schema 的 schemaVersion 必须是 const: 1.0"

    def test_v10_schema_no_new_fields(self, v10_schema):
        """v1.0 schema 不应有 v1.1 新增字段。"""
        valuation_keys = set(v10_schema["properties"]["valuation"]["properties"].keys())
        result_keys = set(v10_schema["properties"]["result"]["properties"].keys())
        assert "estimatedDate" not in valuation_keys
        assert "calculationMode" not in result_keys
        assert "crossMethodNotes" not in v10_schema["properties"]

    def test_v10_schema_id_points_to_v10(self, v10_schema):
        assert "v1.0" in v10_schema["$id"]


# ════════════════════════════════════════════════════════
# 2. v1.1 Schema 新增字段
# ════════════════════════════════════════════════════════
class TestV11Schema:
    def test_v11_schema_is_valid_draft_2020_12(self, v11_schema):
        jsonschema.Draft202012Validator.check_schema(v11_schema)

    def test_v11_schema_version_is_pattern(self, v11_schema):
        sv = v11_schema["properties"]["schemaVersion"]
        assert "pattern" in sv, "v1.1 schemaVersion 应为 pattern（非 const）"
        assert sv["pattern"] == "^1\\.1$"

    def test_v11_has_estimated_date(self, v11_schema):
        assert "estimatedDate" in v11_schema["properties"]["valuation"]["properties"]
        prop = v11_schema["properties"]["valuation"]["properties"]["estimatedDate"]
        assert prop["type"] == "string"
        assert prop.get("format") == "date"

    def test_v11_has_calculation_mode(self, v11_schema):
        assert "calculationMode" in v11_schema["properties"]["result"]["properties"]
        prop = v11_schema["properties"]["result"]["properties"]["calculationMode"]
        assert prop["enum"] == [
            "weightedAverage", "arithmeticMean",
            "primaryMethodDominant", "expertJudgment"
        ]

    def test_v11_has_cross_method_notes(self, v11_schema):
        assert "crossMethodNotes" in v11_schema["properties"]
        prop = v11_schema["properties"]["crossMethodNotes"]
        assert prop["type"] == "string"

    def test_v11_schema_is_backward_compatible(self, v10_schema, v11_schema):
        """v1.1 是 v1.0 的超集：v1.0 的所有 required 字段在 v1.1 中也 required。"""
        for field in v10_schema["required"]:
            assert field in v11_schema["required"], f"{field} 在 v1.1 中缺失 required"


# ════════════════════════════════════════════════════════
# 3. 版本检测
# ════════════════════════════════════════════════════════
class TestDetectVersion:
    def test_detect_1_0(self):
        assert detect_version({"schemaVersion": "1.0"}) == "1.0"

    def test_detect_1_1(self):
        assert detect_version({"schemaVersion": "1.1"}) == "1.1"

    def test_detect_unknown(self):
        assert detect_version({"schemaVersion": "9.9"}) == "unknown"

    def test_detect_missing(self):
        assert detect_version({}) == "unknown"


# ════════════════════════════════════════════════════════
# 4. 迁移脚本功能
# ════════════════════════════════════════════════════════
class TestMigration:
    def test_migrate_adds_calculation_mode_weighted(self, example_v10_copy):
        """determinationMethod 含'加权平均' → calculationMode=weightedAverage"""
        from migrate_schema import migrate
        data, notes = migrate(example_v10_copy, "1.0", "1.1")
        assert data["result"]["calculationMode"] == "weightedAverage"
        assert any("calculationMode" in n for n in notes)

    def test_migrate_updates_schema_version(self, example_v10_copy):
        from migrate_schema import migrate
        data, _ = migrate(example_v10_copy, "1.0", "1.1")
        assert data["schemaVersion"] == "1.1"

    def test_migrate_skips_if_already_v1_1(self, example_v11_data):
        """v1.1 数据迁移到 v1.1 应返回原数据，无变更。"""
        from migrate_schema import migrate
        data, notes = migrate(example_v11_data, "1.1", "1.1")
        assert data is example_v11_data  # 同一对象引用
        assert notes == []

    def test_migrate_unsupported_version_raises(self, example_v10_copy):
        from migrate_schema import migrate
        with pytest.raises(ValueError, match="不支持的迁移路径"):
            migrate(example_v10_copy, "0.9", "1.0")


# ════════════════════════════════════════════════════════
# 5. validate_full 版本路由
# ════════════════════════════════════════════════════════
class TestVersionRouting:
    def test_validate_full_auto_detects_1_0(self, example_v10_copy):
        """v1.0 数据自动路由到 v1.0 schema，验证通过。"""
        errors = validate_full(example_v10_copy)
        assert not errors, f"v1.0 数据应通过 v1.0 schema 验证，错误: {[e.message for e in errors]}"

    def test_validate_full_auto_detects_1_1(self, example_v11_data):
        """v1.1 数据自动路由到 v1.1 schema，验证通过。"""
        errors = validate_full(example_v11_data)
        assert not errors, f"v1.1 数据应通过 v1.1 schema 验证，错误: {[e.message for e in errors]}"

    def test_validate_full_v1_0_data_passes_v1_0_schema(self, example_v10_copy):
        """v1.0 数据用 v1.0 schema 验证通过（核心正确性）。"""
        errors = validate_full(example_v10_copy, version="1.0")
        assert not errors, f"v1.0 数据应通过 v1.0 schema 验证，错误: {[e.message for e in errors]}"

    def test_migrated_v1_0_data_passes_v1_1_schema(self, example_v10_copy):
        """迁移后 v1.0 数据用 v1.1 schema 验证通过。"""
        from migrate_schema import migrate
        migrated, _ = migrate(example_v10_copy, "1.0", "1.1")
        errors = validate_full(migrated, version="1.1")
        assert not errors, f"迁移后数据应通过 v1.1 schema，错误: {[e.message for e in errors]}"

    def test_validate_full_explicit_version(self, example_v10_copy):
        """显式指定 version="1.0" 路由到 v1.0 schema。"""
        errors = validate_full(example_v10_copy, version="1.0")
        assert not errors

    def test_v1_1_new_field_accepted(self, example_v11_data):
        """v1.1 新增字段在 v1.1 schema 下应被接受。"""
        data = json.loads(json.dumps(example_v11_data))
        data["crossMethodNotes"] = "测试跨方法讨论笔记"
        data["result"]["calculationMode"] = "weightedAverage"
        data["valuation"]["estimatedDate"] = "2026-09-01"
        errors = validate_full(data, version="1.1")
        assert not errors, f"v1.1 新字段应通过验证，错误: {[e.message for e in errors]}"

    def test_v1_1_new_field_rejected_by_v1_0_schema(self, example_v10_copy):
        """v1.1 新增字段在 v1.0 schema 下应被拒绝。"""
        example_v10_copy["crossMethodNotes"] = "不应在 v1.0 出现"
        errors = validate_full(example_v10_copy, version="1.0")
        assert errors, "v1.0 schema 应拒绝 v1.1 新增字段"


# ════════════════════════════════════════════════════════
# 6. CHANGELOG 存在与基本格式
# ════════════════════════════════════════════════════════
class TestChangelog:
    def test_changelog_exists(self):
        assert CHANGELOG_PATH.exists(), "CHANGELOG.md 应存在"

    def test_changelog_has_v1_1_entry(self):
        content = CHANGELOG_PATH.read_text(encoding="utf-8")
        assert "## [1.1]" in content or "## 1.1" in content, "CHANGELOG 应有 v1.1 条目"

    def test_changelog_has_v1_0_entry(self):
        content = CHANGELOG_PATH.read_text(encoding="utf-8")
        assert "## [1.0]" in content or "## 1.0" in content, "CHANGELOG 应有 v1.0 条目"

    def test_changelog_mentions_migration(self, example_v10_copy):
        """CHANGELOG 应说明迁移方式。"""
        content = CHANGELOG_PATH.read_text(encoding="utf-8")
        assert "migrate" in content.lower() or "迁移" in content, "CHANGELOG 应包含迁移说明"
