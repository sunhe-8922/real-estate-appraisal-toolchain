"""
test_schema_v13.py — v1.3 Schema 测试（人工决策点 decisionPoints）

覆盖维度：
1. v1.3 schema 合法性与新增字段（decisionPoints + $defs.decisionPoint 等）
2. decisionPoint 约束（required 字段、additionalProperties: false、enum 值）
3. evidenceItem / riskItem / comparisonItem 约束
4. 1.2 → 1.3 迁移
5. 版本路由（VERSION_SCHEMA_MAP 含 1.3，detect_version 识别 1.3）
6. v1.2 schema 拒绝 v1.3 新增字段（版本隔离）
7. decisionPoints 完整决策包示例验证
8. 边界用例：空 decisionPoints、pending 状态、modified 动作
"""

import json
import sys
from pathlib import Path

import pytest
import jsonschema

ROOT = Path(__file__).parent.parent
SCHEMA_DIR = ROOT / "schema"
V13_SCHEMA_PATH = SCHEMA_DIR / "v1.3" / "appraisal-result.schema.json"
V12_SCHEMA_PATH = SCHEMA_DIR / "v1.2" / "appraisal-result.schema.json"
ROOT_SCHEMA_PATH = SCHEMA_DIR / "appraisal-result.schema.json"
EXAMPLE_PATH = ROOT / "schema" / "example-武汉洪山住宅.json"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

sys.path.insert(0, str(ROOT / "scripts"))
from validate_appraisal_json import detect_version, validate_full, VERSION_SCHEMA_MAP
from migrate_schema import _migrate_1_2_to_1_3
from helpers import make_minimal_decision_point, make_comp_decision_point


# ── Fixtures ───────────────────────────────────────────
@pytest.fixture(scope="session")
def v13_schema():
    with open(V13_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def v12_schema():
    with open(V12_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def root_schema():
    with open(ROOT_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def example_data():
    with open(EXAMPLE_PATH, encoding="utf-8") as f:
        return json.load(f)


# ════════════════════════════════════════════════════════
# 1. v1.3 Schema 合法性与新增字段
# ════════════════════════════════════════════════════════
class TestV13Schema:
    def test_v13_schema_is_valid_draft_2020_12(self, v13_schema):
        jsonschema.Draft202012Validator.check_schema(v13_schema)

    def test_v13_schema_version_is_pattern(self, v13_schema):
        sv = v13_schema["properties"]["schemaVersion"]
        assert sv["pattern"] == "^1\\.3$"

    def test_v13_has_decision_points_property(self, v13_schema):
        dp = v13_schema["properties"]["decisionPoints"]
        assert dp["type"] == "array"
        assert dp["items"]["$ref"] == "#/$defs/decisionPoint"

    def test_v13_has_decision_point_def(self, v13_schema):
        dp = v13_schema["$defs"]["decisionPoint"]
        for field in ["id", "name", "phase", "trigger", "riskLevel",
                       "status", "conclusion", "evidence", "reasoning", "risks"]:
            assert field in dp["required"], f"decisionPoint 缺 required: {field}"
        assert dp["additionalProperties"] is False

    def test_v13_has_evidence_item_def(self, v13_schema):
        ei = v13_schema["$defs"]["evidenceItem"]
        assert ei["required"] == ["item", "source"]
        assert ei["additionalProperties"] is False

    def test_v13_has_risk_item_def(self, v13_schema):
        ri = v13_schema["$defs"]["riskItem"]
        assert ri["required"] == ["description", "level"]
        assert ri["additionalProperties"] is False

    def test_v13_has_comparison_item_def(self, v13_schema):
        ci = v13_schema["$defs"]["comparisonItem"]
        assert ci["required"] == ["instance", "differences"]
        assert ci["additionalProperties"] is False

    def test_v13_phase_enum(self, v13_schema):
        phase = v13_schema["$defs"]["decisionPoint"]["properties"]["phase"]
        assert set(phase["enum"]) == {"preCalculation", "inMethod", "postMethod", "postReport"}

    def test_v13_status_enum(self, v13_schema):
        status = v13_schema["$defs"]["decisionPoint"]["properties"]["status"]
        assert set(status["enum"]) == {"pending", "approved", "modified", "rejected"}

    def test_v13_risk_level_enum(self, v13_schema):
        rl = v13_schema["$defs"]["decisionPoint"]["properties"]["riskLevel"]
        assert set(rl["enum"]) == {"P0", "P1", "P2"}

    def test_v13_human_decision_action_enum(self, v13_schema):
        hd = v13_schema["$defs"]["decisionPoint"]["properties"]["humanDecision"]
        assert set(hd["properties"]["action"]["enum"]) == {"approved", "modified", "rejected"}

    def test_root_schema_upgraded_beyond_v13(self, root_schema, v13_schema):
        """根目录 schema 已升级到 v1.4（不再等于 v1.3 版本化副本）。"""
        r, v = dict(root_schema), dict(v13_schema)
        r.pop("$id"), v.pop("$id")
        assert r != v, "root schema 应已升级到 v1.4，不再等于 v1.3"

    def test_v13_backward_compatible_with_v12(self, v12_schema, v13_schema):
        for field in v12_schema["required"]:
            assert field in v13_schema["required"], f"{field} 在 v1.3 中缺失 required"


# ════════════════════════════════════════════════════════
# 2. decisionPoint 约束行为
# ════════════════════════════════════════════════════════
class TestDecisionPointConstraints:
    def test_minimal_dp_accepted(self, example_data):
        """最小合法 decisionPoint 应通过验证。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        data["decisionPoints"] = [make_minimal_decision_point()]
        errors = validate_full(data)
        assert not errors, f"最小 DP 应通过: {[e.message for e in errors]}"

    def test_dp_missing_id_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        del dp["id"]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "缺 id 应被拒绝"

    def test_dp_missing_conclusion_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        del dp["conclusion"]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "缺 conclusion 应被拒绝"

    def test_dp_missing_evidence_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        del dp["evidence"]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "缺 evidence 应被拒绝"

    def test_dp_missing_risks_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        del dp["risks"]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "缺 risks 应被拒绝"

    def test_dp_extra_field_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        dp["extraField"] = "不应存在"
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "额外字段应被拒绝（additionalProperties: false）"

    def test_dp_invalid_phase_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        dp["phase"] = "invalidPhase"
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "无效 phase 应被拒绝"

    def test_dp_invalid_status_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        dp["status"] = "draft"
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "无效 status 应被拒绝"

    def test_dp_empty_evidence_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        dp["evidence"] = []
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "空 evidence 数组应被拒绝（minItems: 1）"

    def test_dp_empty_risks_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        dp["risks"] = []
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "空 risks 数组应被拒绝（minItems: 1）"


# ════════════════════════════════════════════════════════
# 3. evidenceItem / riskItem / comparisonItem 约束
# ════════════════════════════════════════════════════════
class TestSubItemConstraints:
    def test_evidence_missing_item_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        del dp["evidence"][0]["item"]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "evidence 缺 item 应被拒绝"

    def test_evidence_missing_source_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        del dp["evidence"][0]["source"]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "evidence 缺 source 应被拒绝"

    def test_evidence_extra_field_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        dp["evidence"][0]["extra"] = "no"
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "evidence 额外字段应被拒绝"

    def test_risk_invalid_level_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        dp["risks"][0]["level"] = "P3"
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "无效 risk level 应被拒绝"

    def test_risk_missing_level_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point()
        del dp["risks"][0]["level"]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "risk 缺 level 应被拒绝"

    def test_comparison_missing_instance_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_comp_decision_point()
        del dp["comparison"][0]["instance"]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "comparison 缺 instance 应被拒绝"

    def test_comparison_missing_differences_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_comp_decision_point()
        del dp["comparison"][0]["differences"]
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert errors, "comparison 缺 differences 应被拒绝"


# ════════════════════════════════════════════════════════
# 4. 版本检测与路由
# ════════════════════════════════════════════════════════
class TestVersionRoutingV13:
    def test_version_map_contains_1_3(self):
        assert "1.3" in VERSION_SCHEMA_MAP

    def test_detect_1_3(self):
        assert detect_version({"schemaVersion": "1.3"}) == "1.3"

    def test_v13_data_without_decision_points_passes(self, example_data):
        """v1.3 数据不含 decisionPoints（可选字段）应通过。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        data.pop("decisionPoints", None)  # 示例数据已含 v1.4 决策链字段，剥离后测试 v1.3 可选性
        errors = validate_full(data)
        assert not errors, f"无 decisionPoints 的 v1.3 数据应通过: {[e.message for e in errors]}"

    def test_v13_data_with_empty_decision_points_passes(self, example_data):
        """空 decisionPoints 数组应通过。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        data["decisionPoints"] = []
        errors = validate_full(data)
        assert not errors, f"空 decisionPoints 应通过: {[e.message for e in errors]}"

    def test_v13_fields_rejected_by_v12_schema(self, example_data):
        """v1.3 新增字段在 v1.2 schema 下应被拒绝（版本隔离）。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.2"
        data["decisionPoints"] = [make_minimal_decision_point()]
        errors = validate_full(data, version="1.2")
        assert errors, "v1.2 schema 应拒绝 decisionPoints"


# ════════════════════════════════════════════════════════
# 5. 1.2 → 1.3 迁移
# ════════════════════════════════════════════════════════
class TestMigrationV13:
    def test_migrate_updates_schema_version(self, example_data):
        """示例数据（v1.3）剥离 v1.3 字段后还原为 v1.2，迁移到 v1.3 应更新版本号。"""
        data = json.loads(json.dumps(example_data))
        data.pop("decisionPoints", None)
        data["schemaVersion"] = "1.2"
        assert data["schemaVersion"] == "1.2"
        migrated, notes = _migrate_1_2_to_1_3(data)
        assert migrated["schemaVersion"] == "1.3"
        assert any("schemaVersion" in n for n in notes)

    def test_migrate_does_not_add_decision_points(self, example_data):
        """迁移不自动添加 decisionPoints（运行时字段）。"""
        data = json.loads(json.dumps(example_data))
        data.pop("decisionPoints", None)
        data["schemaVersion"] = "1.2"
        migrated, _ = _migrate_1_2_to_1_3(data)
        assert "decisionPoints" not in migrated

    def test_migrated_data_passes_v13_schema(self, example_data):
        """v1.2 数据（剥离 v1.3 字段）迁移到 v1.3 后应通过 v1.3 schema 验证。

        注意：示例数据已是 v1.3，直接迁移是 no-op（假阳性）。
        必须先剥离 decisionPoints 并还原版本号为 1.2，再走迁移路径。
        """
        data = json.loads(json.dumps(example_data))
        data.pop("decisionPoints", None)
        data["schemaVersion"] = "1.2"
        migrated, _ = _migrate_1_2_to_1_3(data)
        assert migrated["schemaVersion"] == "1.3"
        errors = validate_full(migrated, version="1.3")
        assert not errors, f"迁移后应通过 v1.3 schema: {[e.message for e in errors]}"


# ════════════════════════════════════════════════════════
# 6. 完整决策包示例验证
# ════════════════════════════════════════════════════════
class TestFullDecisionPackage:
    def test_fixed_dp_with_human_decision(self, example_data):
        """固定决策点 + 人类决策记录应通过。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        data["decisionPoints"] = [make_minimal_decision_point(status="approved")]
        errors = validate_full(data)
        assert not errors, f"固定 DP 应通过: {[e.message for e in errors]}"

    def test_method_specific_dp_with_comparison(self, example_data):
        """方法特定决策点 + comparison 字段应通过。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        data["decisionPoints"] = [make_comp_decision_point()]
        errors = validate_full(data)
        assert not errors, f"方法特定 DP 应通过: {[e.message for e in errors]}"

    def test_pending_dp_without_human_decision(self, example_data):
        """status=pending 时 humanDecision 可不存在。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point(status="pending")
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert not errors, f"pending DP 应通过: {[e.message for e in errors]}"

    def test_modified_dp_with_modifications(self, example_data):
        """status=modified 时 humanDecision.modifications 应存在。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point(status="modified")
        data["decisionPoints"] = [dp]
        errors = validate_full(data)
        assert not errors, f"modified DP 应通过: {[e.message for e in errors]}"

    def test_multiple_dps(self, example_data):
        """多个决策点（固定 + 条件）同时存在应通过。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        data["decisionPoints"] = [
            make_minimal_decision_point("DP1", "approved"),
            make_minimal_decision_point("DP2", "approved"),
            make_comp_decision_point(),
        ]
        errors = validate_full(data)
        assert not errors, f"多 DP 应通过: {[e.message for e in errors]}"


# ════════════════════════════════════════════════════════
# 6b. 条件约束（P0-1 ~ P0-8，v1.3.1 新增 if/then/else）
# ════════════════════════════════════════════════════════
class TestConditionalConstraints:
    """跨字段一致性约束：由 decisionPoint 的 allOf if/then/else 强制。"""

    @staticmethod
    def _validate(example_data, dp):
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        data["decisionPoints"] = [dp]
        return validate_full(data)

    def test_status_approved_requires_human_decision(self, example_data):
        """P0-1: status=approved 必须有人类决策记录。"""
        dp = make_minimal_decision_point(status="pending")
        dp["status"] = "approved"
        errors = self._validate(example_data, dp)
        assert errors, "approved 无 humanDecision 应被拒绝"

    def test_status_modified_requires_human_decision(self, example_data):
        """status=modified 必须有人类决策记录。"""
        dp = make_minimal_decision_point(status="pending")
        dp["status"] = "modified"
        errors = self._validate(example_data, dp)
        assert errors, "modified 无 humanDecision 应被拒绝"

    def test_status_rejected_requires_human_decision(self, example_data):
        """status=rejected 必须有人类决策记录。"""
        dp = make_minimal_decision_point(status="pending")
        dp["status"] = "rejected"
        errors = self._validate(example_data, dp)
        assert errors, "rejected 无 humanDecision 应被拒绝"

    def test_action_modified_requires_modifications(self, example_data):
        """P0-2: action=modified 必须填写 modifications。"""
        dp = make_minimal_decision_point(status="modified")
        del dp["humanDecision"]["modifications"]
        errors = self._validate(example_data, dp)
        assert errors, "modified 无 modifications 应被拒绝"

    def test_action_modified_empty_modifications_rejected(self, example_data):
        """action=modified 但 modifications 为空字符串应被拒绝。"""
        dp = make_minimal_decision_point(status="modified")
        dp["humanDecision"]["modifications"] = ""
        errors = self._validate(example_data, dp)
        assert errors, "空 modifications 应被拒绝（minLength: 1）"

    def test_method_trigger_requires_method(self, example_data):
        """P0-3: trigger=method:xxx 必须填写 method。"""
        dp = make_comp_decision_point()
        del dp["method"]
        errors = self._validate(example_data, dp)
        assert errors, "method: 触发无 method 应被拒绝"

    def test_pending_rejects_human_decision(self, example_data):
        """P0-4: status=pending 不允许有人类决策记录。"""
        dp = make_minimal_decision_point(status="approved")
        dp["status"] = "pending"
        errors = self._validate(example_data, dp)
        assert errors, "pending 有 humanDecision 应被拒绝"

    def test_trigger_pattern_restricted(self, example_data):
        """P0-5: trigger 只能是 always 或 method:comps|income|cost|hypotheticalDev。"""
        for bad in ["whatever", "method:foo", "Method:comps", "always "]:
            dp = make_minimal_decision_point()
            dp["trigger"] = bad
            errors = self._validate(example_data, dp)
            assert errors, f"非法 trigger '{bad}' 应被拒绝"

    def test_status_rejected_rejects_approved_action(self, example_data):
        """P0-6: status=rejected 时 action 必须也是 rejected（矛盾拒绝）。"""
        dp = make_minimal_decision_point(status="approved")
        dp["status"] = "rejected"
        dp["humanDecision"]["action"] = "approved"
        errors = self._validate(example_data, dp)
        assert errors, "rejected+approved 矛盾应被拒绝"

    def test_status_approved_rejects_modified_action(self, example_data):
        """status=approved 时 action 必须也是 approved。"""
        dp = make_minimal_decision_point(status="approved")
        dp["humanDecision"]["action"] = "modified"
        errors = self._validate(example_data, dp)
        assert errors, "approved+modified 矛盾应被拒绝"

    def test_risk_level_matches_max_risk(self, example_data):
        """P0-7: riskLevel 必须等于 risks 的最高等级。"""
        # riskLevel=P0 但 risks 全 P2 → 拒绝
        dp = make_minimal_decision_point(status="approved")
        dp["riskLevel"] = "P0"
        dp["risks"] = [{"description": "low risk", "level": "P2"}]
        errors = self._validate(example_data, dp)
        assert errors, "riskLevel=P0 但 risks 全 P2 应被拒绝"
        # riskLevel=P1 但 risks 含 P0 → 拒绝（P0 必须提升 riskLevel）
        dp2 = make_minimal_decision_point(status="approved")
        dp2["riskLevel"] = "P1"
        dp2["risks"] = [{"description": "high risk", "level": "P0"}]
        errors2 = self._validate(example_data, dp2)
        assert errors2, "riskLevel=P1 但 risks 含 P0 应被拒绝"
        # riskLevel=P2 但 risks 含 P1 → 拒绝
        dp3 = make_minimal_decision_point(status="approved")
        dp3["riskLevel"] = "P2"
        dp3["risks"] = [{"description": "mid risk", "level": "P1"}]
        errors3 = self._validate(example_data, dp3)
        assert errors3, "riskLevel=P2 但 risks 含 P1 应被拒绝"

    def test_phase_trigger_combo_restricted(self, example_data):
        """P0-8: always → 非 inMethod；method:xxx → inMethod。"""
        dp = make_comp_decision_point()
        dp["phase"] = "postReport"
        errors = self._validate(example_data, dp)
        assert errors, "postReport+method:comps 应被拒绝"

        dp2 = make_minimal_decision_point(status="approved")
        dp2["phase"] = "inMethod"  # always 触发不应出现在 inMethod
        errors2 = self._validate(example_data, dp2)
        assert errors2, "always+inMethod 应被拒绝"

    def test_rejected_dp_with_rejected_action_accepted(self, example_data):
        """rejected 状态 + rejected 动作应通过（正例）。"""
        dp = make_minimal_decision_point(status="approved")
        dp["status"] = "rejected"
        dp["humanDecision"]["action"] = "rejected"
        dp["humanDecision"]["comment"] = "理由不足，需补充证据"
        errors = self._validate(example_data, dp)
        assert not errors, f"合法 rejected DP 应通过: {[e.message for e in errors]}"


# ════════════════════════════════════════════════════════
# 6c. 业务校验（P0-9，validate 脚本补充）
# ════════════════════════════════════════════════════════
class TestBusinessValidation:
    def test_duplicate_dp_ids_rejected(self, example_data):
        """P0-9: decisionPoints 的 id 必须唯一（业务校验）。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        data["decisionPoints"] = [
            make_minimal_decision_point("DP1", "approved"),
            make_minimal_decision_point("DP1", "approved"),
        ]
        errors = validate_full(data)
        assert errors, "重复 DP id 应被业务校验拒绝"
        messages = [e.message for e in errors]
        assert any("重复" in m for m in messages), "错误信息应指出 id 重复"

    def test_unique_dp_ids_accepted(self, example_data):
        """id 唯一时业务校验应放行。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        data["decisionPoints"] = [
            make_minimal_decision_point("DP1", "approved"),
            make_minimal_decision_point("DP2", "approved"),
        ]
        errors = validate_full(data)
        assert not errors, f"唯一 DP id 应通过: {[e.message for e in errors]}"

    def test_duplicate_ids_detected_even_with_schema_errors(self, example_data):
        """业务校验独立于 schema 校验：即使存在其它 schema 错误也应报告重复。"""
        data = json.loads(json.dumps(example_data))
        data["schemaVersion"] = "1.3"
        dp = make_minimal_decision_point("DPX", "approved")
        data["decisionPoints"] = [dp, dict(dp, name="另一个")]
        errors = validate_full(data)
        assert any("重复" in e.message for e in errors), "应同时报告重复 id"


# ════════════════════════════════════════════════════════
# 7. CHANGELOG
# ════════════════════════════════════════════════════════
class TestChangelogV13:
    def test_changelog_has_v1_3_entry(self):
        content = CHANGELOG_PATH.read_text(encoding="utf-8")
        assert "## [1.3]" in content, "CHANGELOG 应有 v1.3 条目"
