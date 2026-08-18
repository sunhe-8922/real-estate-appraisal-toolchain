"""
test_schema_v14.py — v1.4 Schema 测试（驳回后决策链 supersedes/attempt）

覆盖维度：
1. v1.4 schema 合法性与新增字段（supersedes / attempt）
2. root schema == v1.4 版本化副本
3. 向后兼容 v1.3（v1.4 是 v1.3 超集）
4. 决策链业务校验（C1-C6：存在性/自引用/被拒状态/1:1 后继/成环/attempt 一致性）
5. 版本路由（VERSION_SCHEMA_MAP 含 1.4，detect_version 识别 1.4）
6. 1.3 → 1.4 迁移
7. v1.3 schema 拒绝 v1.4 新增字段（版本隔离）
"""

import json
import sys
from pathlib import Path

import pytest
import jsonschema

ROOT = Path(__file__).parent.parent
SCHEMA_DIR = ROOT / "schema"
V14_SCHEMA_PATH = SCHEMA_DIR / "v1.4" / "appraisal-result.schema.json"
V13_SCHEMA_PATH = SCHEMA_DIR / "v1.3" / "appraisal-result.schema.json"
ROOT_SCHEMA_PATH = SCHEMA_DIR / "appraisal-result.schema.json"
EXAMPLE_PATH = ROOT / "schema" / "example-武汉洪山住宅.json"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

sys.path.insert(0, str(ROOT / "scripts"))
from validate_appraisal_json import detect_version, validate_full, VERSION_SCHEMA_MAP
from migrate_schema import _migrate_1_3_to_1_4


# ── Fixtures ───────────────────────────────────────────
@pytest.fixture(scope="session")
def v14_schema():
    with open(V14_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def v13_schema():
    with open(V13_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def root_schema():
    with open(ROOT_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def example_data():
    with open(EXAMPLE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _make_minimal_decision_point(dp_id="DP1", status="approved", supersedes=None, attempt=None):
    """构造一个最小合法的 decisionPoint 对象（可带 supersedes/attempt）。"""
    dp = {
        "id": dp_id,
        "name": "估价事项确认",
        "phase": "preCalculation",
        "trigger": "always",
        "riskLevel": "P0",
        "status": status,
        "conclusion": "建议确认估价目的为抵押估价",
        "evidence": [
            {"item": "委托合同明确估价目的", "source": "委托合同"}
        ],
        "reasoning": "抵押估价要求市场价值",
        "risks": [
            {"description": "附属面积需确认", "level": "P0", "mitigation": "按产权证"}
        ],
    }
    if status != "pending":
        dp["humanDecision"] = {
            "action": status,
            "decidedBy": "sun",
            "timestamp": "2026-08-18T10:30:00+08:00",
        }
        if status == "modified":
            dp["humanDecision"]["modifications"] = "将估价目的改为转让估价"
    if supersedes is not None:
        dp["supersedes"] = supersedes
    if attempt is not None:
        dp["attempt"] = attempt
    return dp


def _build_with_dps(dps):
    """基于示例数据构造带指定决策点的完整对象（schemaVersion 强制 v1.4）。"""
    with open(EXAMPLE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    data["schemaVersion"] = "1.4"
    data["decisionPoints"] = dps
    return data


# ════════════════════════════════════════════════════════
# 1. v1.4 Schema 合法性与新增字段
# ════════════════════════════════════════════════════════
class TestV14Schema:
    def test_v14_schema_is_valid_draft_2020_12(self, v14_schema):
        jsonschema.Draft202012Validator.check_schema(v14_schema)

    def test_v14_schema_version_is_pattern(self, v14_schema):
        sv = v14_schema["properties"]["schemaVersion"]
        assert sv["pattern"] == "^1\\.4$"

    def test_v14_has_supersedes_field(self, v14_schema):
        props = v14_schema["$defs"]["decisionPoint"]["properties"]
        assert "supersedes" in props
        assert props["supersedes"]["type"] == "string"

    def test_v14_has_attempt_field(self, v14_schema):
        props = v14_schema["$defs"]["decisionPoint"]["properties"]
        assert "attempt" in props
        assert props["attempt"]["type"] == "integer"
        assert props["attempt"]["minimum"] == 1

    def test_root_schema_matches_v14(self, root_schema, v14_schema):
        r, v = dict(root_schema), dict(v14_schema)
        r.pop("$id"), v.pop("$id")
        assert r == v, "根目录 schema 应等于 v1.4 版本化副本"

    def test_v14_backward_compatible_with_v13(self, v13_schema, v14_schema):
        for field in v13_schema["required"]:
            assert field in v14_schema["required"], f"{field} 在 v1.4 中缺失 required"
        # decisionPoint 的 required 与 v1.3 一致（supersedes/attempt 为可选）
        v13_required = set(v13_schema["$defs"]["decisionPoint"]["required"])
        v14_required = set(v14_schema["$defs"]["decisionPoint"]["required"])
        assert v13_required == v14_required, "supersedes/attempt 必须保持可选，不进入 required"

    def test_v14_fields_rejected_by_v13_schema(self, example_data):
        """v1.4 新增字段（supersedes/attempt）在 v1.3 schema 下应被拒绝（版本隔离）。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = _make_minimal_decision_point(supersedes="DP-old", attempt=2)
        data["decisionPoints"] = [dp]
        errors = validate_full(data, version="1.3")
        assert errors, "v1.3 schema 应拒绝 supersedes/attempt"

    def test_supersedes_attempt_accepted_by_v14(self, example_data):
        """合法 supersedes/attempt 应通过 v1.4 验证（结构层）。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.4"
        data["decisionPoints"] = [
            _make_minimal_decision_point(dp_id="DP-old", status="rejected", attempt=1),
            _make_minimal_decision_point(dp_id="DP-new", status="approved",
                                         supersedes="DP-old", attempt=2),
        ]
        errors = validate_full(data)
        assert not errors, f"合法决策链应通过: {[e.message for e in errors]}"


# ════════════════════════════════════════════════════════
# 2. 决策链业务校验（C1-C6）
# ════════════════════════════════════════════════════════
class TestDecisionChainValidation:
    """_check_decision_chain 的 6 条规则。"""

    def test_c1_supersedes_must_exist(self):
        data = _build_with_dps([
            _make_minimal_decision_point(dp_id="DP-a", status="rejected"),
            _make_minimal_decision_point(dp_id="DP-b", status="approved", supersedes="DP-ghost"),
        ])
        errors = validate_full(data)
        assert any("不存在的决策点" in e.message for e in errors), \
            f"C1 应拦截不存在的 supersedes: {[e.message for e in errors]}"

    def test_c2_no_self_reference(self):
        data = _build_with_dps([
            _make_minimal_decision_point(dp_id="DP-a", status="approved", supersedes="DP-a"),
        ])
        errors = validate_full(data)
        assert any("自引用" in e.message for e in errors), \
            f"C2 应拦截自引用: {[e.message for e in errors]}"

    def test_c3_superseded_must_be_rejected(self):
        data = _build_with_dps([
            _make_minimal_decision_point(dp_id="DP-a", status="approved"),
            _make_minimal_decision_point(dp_id="DP-b", status="approved", supersedes="DP-a"),
        ])
        errors = validate_full(data)
        assert any("只有 status=rejected" in e.message for e in errors), \
            f"C3 应拦截非 rejected 被取代: {[e.message for e in errors]}"

    def test_c4_one_to_one_successor(self):
        data = _build_with_dps([
            _make_minimal_decision_point(dp_id="DP-a", status="rejected"),
            _make_minimal_decision_point(dp_id="DP-b", status="approved", supersedes="DP-a"),
            _make_minimal_decision_point(dp_id="DP-c", status="approved", supersedes="DP-a"),
        ])
        errors = validate_full(data)
        assert any("只能被一个后继取代" in e.message for e in errors), \
            f"C4 应拦截分叉: {[e.message for e in errors]}"

    def test_c5_no_cycle(self):
        data = _build_with_dps([
            _make_minimal_decision_point(dp_id="DP-a", status="rejected", supersedes="DP-b"),
            _make_minimal_decision_point(dp_id="DP-b", status="rejected", supersedes="DP-a"),
        ])
        errors = validate_full(data)
        assert any("存在环" in e.message for e in errors), \
            f"C5 应拦截成环: {[e.message for e in errors]}"

    def test_c5_long_chain_cycle(self):
        """A→B→C→A 三节点环也应拦截。"""
        data = _build_with_dps([
            _make_minimal_decision_point(dp_id="DP-a", status="rejected", supersedes="DP-c"),
            _make_minimal_decision_point(dp_id="DP-b", status="rejected", supersedes="DP-a"),
            _make_minimal_decision_point(dp_id="DP-c", status="rejected", supersedes="DP-b"),
        ])
        errors = validate_full(data)
        assert any("存在环" in e.message for e in errors), \
            f"C5 应拦截三节点环: {[e.message for e in errors]}"

    def test_c6_attempt_consistency(self):
        data = _build_with_dps([
            _make_minimal_decision_point(dp_id="DP-a", status="rejected", attempt=1),
            _make_minimal_decision_point(dp_id="DP-b", status="approved", supersedes="DP-a", attempt=3),
        ])
        errors = validate_full(data)
        assert any("attempt=3" in e.message and "应为 2" in e.message for e in errors), \
            f"C6 应拦截 attempt 不一致: {[e.message for e in errors]}"

    # ── 正例 ──
    def test_valid_chain_passes(self):
        data = _build_with_dps([
            _make_minimal_decision_point(dp_id="DP-a", status="rejected", attempt=1),
            _make_minimal_decision_point(dp_id="DP-b", status="approved", supersedes="DP-a", attempt=2),
        ])
        errors = validate_full(data)
        assert not errors, f"合法决策链应通过: {[e.message for e in errors]}"

    def test_chain_without_attempt_passes(self):
        """省略 attempt 的合法链（attempt 可选）应通过。"""
        data = _build_with_dps([
            _make_minimal_decision_point(dp_id="DP-a", status="rejected"),
            _make_minimal_decision_point(dp_id="DP-b", status="approved", supersedes="DP-a"),
        ])
        errors = validate_full(data)
        assert not errors, f"省略 attempt 应通过: {[e.message for e in errors]}"

    def test_multiple_independent_dps_passes(self):
        """多个互不关联的 DP（无 supersedes）应通过。"""
        data = _build_with_dps([
            _make_minimal_decision_point(dp_id="DP1"),
            _make_minimal_decision_point(dp_id="DP2"),
            _make_minimal_decision_point(dp_id="DP3"),
        ])
        errors = validate_full(data)
        assert not errors, f"独立多 DP 应通过: {[e.message for e in errors]}"

    def test_rejected_alone_passes(self):
        """单个 rejected DP（无后继）应通过——审计记录允许存在未重试的否决。"""
        data = _build_with_dps([
            _make_minimal_decision_point(dp_id="DP-a", status="rejected"),
        ])
        errors = validate_full(data)
        assert not errors, f"孤立 rejected 应通过: {[e.message for e in errors]}"


# ════════════════════════════════════════════════════════
# 3. 版本路由
# ════════════════════════════════════════════════════════
class TestVersionRoutingV14:
    def test_version_map_contains_1_4(self):
        assert "1.4" in VERSION_SCHEMA_MAP

    def test_detect_1_4(self):
        assert detect_version({"schemaVersion": "1.4"}) == "1.4"

    def test_v14_data_passes_under_v14(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.4"
        errors = validate_full(data)
        assert not errors, f"v1.4 示例数据应通过: {[e.message for e in errors]}"


# ════════════════════════════════════════════════════════
# 4. 1.3 → 1.4 迁移
# ════════════════════════════════════════════════════════
class TestMigrationV14:
    def test_migrate_updates_schema_version(self, example_data):
        """示例数据（v1.4）剥离 v1.4 字段后还原为 v1.3，迁移到 v1.4 应更新版本号。"""
        data = json.loads(json.dumps(example_data))
        data.pop("decisionPoints", None)
        data["schemaVersion"] = "1.3"
        migrated, notes = _migrate_1_3_to_1_4(data)
        assert migrated["schemaVersion"] == "1.4"
        assert any("schemaVersion" in n for n in notes)

    def test_migrate_does_not_add_chain_fields(self, example_data):
        """迁移不自动添加 supersedes/attempt（运行时字段）。"""
        data = json.loads(json.dumps(example_data))
        data.pop("decisionPoints", None)
        data["schemaVersion"] = "1.3"
        migrated, _ = _migrate_1_3_to_1_4(data)
        assert "decisionPoints" not in migrated

    def test_migrated_data_passes_v14_schema(self, example_data):
        """v1.3 数据（剥离 v1.4 字段）迁移到 v1.4 后应通过 v1.4 schema 验证。"""
        data = json.loads(json.dumps(example_data))
        data.pop("decisionPoints", None)
        data["schemaVersion"] = "1.3"
        migrated, _ = _migrate_1_3_to_1_4(data)
        assert migrated["schemaVersion"] == "1.4"
        errors = validate_full(migrated, version="1.4")
        assert not errors, f"迁移后应通过 v1.4 schema: {[e.message for e in errors]}"

    def test_migrate_1_3_noop_on_1_4_data(self, example_data):
        """对已是 v1.4 的数据迁移应为 no-op（版本不变）。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.4"
        migrated, notes = _migrate_1_3_to_1_4(data)
        assert migrated["schemaVersion"] == "1.4"
        assert not notes, f"v1.4 数据迁移应为 no-op: {notes}"


# ════════════════════════════════════════════════════════
# 5. CHANGELOG
# ════════════════════════════════════════════════════════
class TestChangelogV14:
    def test_changelog_has_v14_entry(self):
        with open(CHANGELOG_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "[1.4]" in content, "CHANGELOG 应包含 [1.4] 条目"
        assert "supersedes" in content.lower() or "决策链" in content, \
            "CHANGELOG [1.4] 条目应说明决策链建模"
