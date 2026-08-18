"""对抗式审查：验证 Schema v1.3 边界缺陷"""
import json, sys, copy
sys.path.insert(0, "scripts")
from validate_appraisal_json import validate_full

with open("schema/example-武汉洪山住宅.json", encoding="utf-8") as f:
    BASE = json.load(f)

def make_dp(**overrides):
    dp = {
        "id": "DP-TEST",
        "name": "Test",
        "phase": "preCalculation",
        "trigger": "always",
        "riskLevel": "P0",
        "status": "approved",
        "conclusion": "test conclusion",
        "evidence": [{"item": "test evidence", "source": "test source"}],
        "reasoning": "test reasoning",
        "risks": [{"description": "test risk", "level": "P0"}],
        "humanDecision": {"action": "approved", "decidedBy": "tester"},
    }
    dp.update(overrides)
    return dp

def test_case(name, dp_modifier, expect_pass=True):
    data = copy.deepcopy(BASE)
    dp = make_dp()
    dp = dp_modifier(dp) if dp_modifier else dp
    data["decisionPoints"] = [dp]
    errors = validate_full(data)
    passed = not errors
    status = "ACCEPTED" if passed else "REJECTED"
    bug = ""
    if passed and not expect_pass:
        bug = " <<< BUG: should be rejected!"
    if not passed and expect_pass:
        bug = " <<< BUG: should be accepted!"
    print(f"  {name}: {status}{bug}")
    if errors and not expect_pass:
        for e in errors[:2]:
            print(f"    -> {e.message}")

print("=" * 60)
print("对抗式审查：Schema v1.3 条件约束缺陷验证")
print("=" * 60)

# 1. status=approved but no humanDecision
test_case("1. status=approved, no humanDecision",
          lambda dp: (dp.pop("humanDecision"), dp)[1],
          expect_pass=False)

# 2. status=modified, action=modified, but no modifications
test_case("2. action=modified, no modifications field",
          lambda dp: dp.update(status="modified", humanDecision={"action": "modified", "decidedBy": "x"}) or dp,
          expect_pass=False)

# 3. trigger=method:comps but no method field
test_case("3. trigger=method:comps, no method field",
          lambda dp: dp.update(trigger="method:comps") or dp,
          expect_pass=False)

# 4. status=pending but HAS humanDecision (semantic inconsistency)
test_case("4. status=pending but has humanDecision",
          lambda dp: dp.update(status="pending") or dp,
          expect_pass=False)

# 5. trigger=arbitrary garbage string
test_case("5. trigger='whatever' (no pattern)",
          lambda dp: dp.update(trigger="whatever") or dp,
          expect_pass=False)

# 6. status=rejected but humanDecision.action=approved (contradiction)
test_case("6. status=rejected but action=approved",
          lambda dp: dp.update(status="rejected", humanDecision={"action": "approved", "decidedBy": "x"}) or dp,
          expect_pass=False)

# 7. riskLevel=P0 but riskItem.level=P2 (mismatch)
test_case("7. riskLevel=P0 but all risks are P2",
          lambda dp: dp.update(risks=[{"description": "low risk", "level": "P2"}]) or dp,
          expect_pass=False)

# 8. phase=postReport but trigger=method:comps (nonsensical combo)
test_case("8. phase=postReport + trigger=method:comps",
          lambda dp: dp.update(phase="postReport", trigger="method:comps") or dp,
          expect_pass=False)

print("\n" + "=" * 60)
print("对抗式审查：ID 唯一性 + 迁移测试假阳性")
print("=" * 60)

# 9. Duplicate DP IDs
data = copy.deepcopy(BASE)
data["decisionPoints"] = [make_dp(id="DP1"), make_dp(id="DP1")]
errors = validate_full(data)
print(f"  9. Duplicate DP IDs: {'ACCEPTED <<< BUG: no uniqueness!' if not errors else 'REJECTED'}")

# 10. Migration test false positive — 验证修复后的迁移路径
from migrate_schema import _migrate_1_2_to_1_3
data_v12 = copy.deepcopy(BASE)
data_v12.pop("decisionPoints", None)
data_v12["schemaVersion"] = "1.2"
migrated, notes = _migrate_1_2_to_1_3(data_v12)
migrate_ok = migrated["schemaVersion"] == "1.3" and any("schemaVersion" in n for n in notes)
print(f"  10. Migration of v1.2 data → v1.3: version={migrated['schemaVersion']} notes={notes}")
print(f"      -> migration path works: {'YES (FIXED)' if migrate_ok else 'NO <<< BUG'}")

# 11. comparison on fixed DP (should it be allowed?)
test_case("11. Fixed DP (trigger=always) with comparison field",
          lambda dp: dp.update(comparison=[{"instance": "X", "differences": "should not be here"}]) or dp,
          expect_pass=True)  # schema allows it but semantically wrong

print("\n" + "=" * 60)
print("对抗式审查：示例数据一致性检查")
print("=" * 60)

# 12. DP-comp comparison vs actual instances
dps = {dp["id"]: dp for dp in BASE["decisionPoints"]}
comp_dp = dps.get("DP-comp")
instances = BASE["methods"]["comps"]["comparableInstances"]
if comp_dp and "comparison" in comp_dp:
    comp_instances = {c["instance"] for c in comp_dp["comparison"]}
    actual_names = set()
    for inst in instances:
        # Extract A/B/C from name
        name = inst["name"]
        if "A" in name or "1号" in name:
            actual_names.add("A")
        elif "B" in name or "2号" in name:
            actual_names.add("B")
        elif "C" in name or "3号" in name:
            actual_names.add("C")
    print(f"  12. DP-comp comparison instances: {comp_instances}")
    print(f"      Actual instance names: {[i['name'] for i in instances]}")

    # Check area differences
    subject_area = BASE["property"]["area"]
    for comp in comp_dp["comparison"]:
        inst_idx = ord(comp["instance"]) - ord("A")
        inst = instances[inst_idx]
        actual_diff = abs(inst["area"] - subject_area)
        print(f"      {comp['instance']}: comparison says '{comp['differences'][:50]}...'")
        print(f"        actual area diff = {actual_diff:.1f} m2")

# 13. DP-income conclusion vs actual rate
income_dp = dps.get("DP-income")
actual_rate = BASE["methods"]["income"]["rate"]["value"]
print(f"\n  13. DP-income conclusion mentions: '{income_dp['conclusion'][:60]}...'")
print(f"      Actual rate in data: {actual_rate} ({actual_rate*100}%)")

# 14. design doc no longer contains "comparison: null"
import os
doc_path = "outputs/人工决策点架构设计.md"
doc = open(doc_path, encoding="utf-8").read() if os.path.exists(doc_path) else ""
if "comparison\": null" in doc or '"comparison": null' in doc:
    print(f"  14. Design doc still contains 'comparison: null': BUG <<<")
else:
    print(f"  14. Design doc 'comparison: null' removed: OK (FIXED)")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
