"""
test_fixtures.py — 编排层 fixture 一致性锁定（第 8 项：条件 DP 独立示例）

覆盖：
1. 4 个 orchestrator pending fixture 均通过 validate_full（schema v1.5 + C1-C6）
2. 每个 fixture 恰有一个 pending 条件 DP，trigger/method/phase 组合合法
3. pending 条件 DP 无 humanDecision（待人类决策）
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
FIXTURES_DIR = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(ROOT / "scripts"))
from validate_appraisal_json import validate_full

PENDING_FIXTURES = [
    ("orchestrator_pending_comps.json", "DP-comp", "method:comps", "comps"),
    ("orchestrator_pending_income.json", "DP-income", "method:income", "income"),
    ("orchestrator_pending_cost.json", "DP-cost", "method:cost", "cost"),
    ("orchestrator_pending_hypoth.json", "DP-hypoth", "method:hypotheticalDev", "hypotheticalDev"),
]


def _load(name):
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class TestPendingFixtures:
    @pytest.mark.parametrize("name,dp_id,trigger,method", PENDING_FIXTURES)
    def test_fixture_passes_validation(self, name, dp_id, trigger, method):
        data = _load(name)
        assert data["schemaVersion"] == "1.5"
        errors = validate_full(data)
        assert not errors, f"{name} 应通过校验: {[e.message for e in errors]}"

    @pytest.mark.parametrize("name,dp_id,trigger,method", PENDING_FIXTURES)
    def test_pending_dp_trigger_combination(self, name, dp_id, trigger, method):
        """pending 条件 DP 的 trigger/method/phase 组合合法且待决策。"""
        data = _load(name)
        dps = {dp["id"]: dp for dp in data["decisionPoints"]}
        assert dp_id in dps, f"{name} 应含 {dp_id}"
        dp = dps[dp_id]
        assert dp["status"] == "pending"
        assert dp["trigger"] == trigger
        assert dp["method"] == method
        assert dp["phase"] == "inMethod"
        assert "humanDecision" not in dp, f"{dp_id} pending 状态不应有 humanDecision"

    @pytest.mark.parametrize("name,dp_id,trigger,method", PENDING_FIXTURES)
    def test_pending_dp_five_part_package(self, name, dp_id, trigger, method):
        """pending 决策包五段式：conclusion/evidence/reasoning/risks 完整。"""
        data = _load(name)
        dp = next(d for d in data["decisionPoints"] if d["id"] == dp_id)
        assert dp["conclusion"], "结论不能为空（结论先行）"
        assert dp["evidence"], "证据不能为空"
        assert dp["reasoning"], "理由不能为空"
        assert dp["risks"], "风险不能为空"
        for risk in dp["risks"]:
            assert risk["level"] in ("P0", "P1", "P2")
            assert risk["mitigation"], "风险应有缓解措施"
