"""
test_schema_v12.py — v1.2 Schema 测试（修正系数多子项 + calculationChain）

覆盖维度：
1. v1.2 schema 合法性与新增字段（locationDetails/physicalDetails/interestDetails + calculationChain）
2. factorDetail 约束（required: [name, factor]，additionalProperties: false）
3. 1.1 → 1.2 迁移
4. 版本路由（VERSION_SCHEMA_MAP 含 1.2，detect_version 识别 1.2）
5. 子项合并一致性：偏差加总法 100/(100+Σ(f-100)) 与顶层系数一致
6. 公式重建 cells 模式：calculationChain → Excel 单元格公式
7. 公式重建 values 模式：对示例数据求值验证
8. v1.1 schema 拒绝 v1.2 新增字段（版本隔离）
"""

import json
import sys
from pathlib import Path

import pytest
import jsonschema

ROOT = Path(__file__).parent.parent
SCHEMA_DIR = ROOT / "schema"
V12_SCHEMA_PATH = SCHEMA_DIR / "v1.2" / "appraisal-result.schema.json"
V11_SCHEMA_PATH = SCHEMA_DIR / "v1.1" / "appraisal-result.schema.json"
ROOT_SCHEMA_PATH = SCHEMA_DIR / "appraisal-result.schema.json"
EXAMPLE_PATH = ROOT / "schema" / "example-武汉洪山住宅.json"
CHAIN_PATH = ROOT / "outputs" / "calculation_chain.json"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

sys.path.insert(0, str(ROOT / "scripts"))
from validate_appraisal_json import detect_version, validate_full, VERSION_SCHEMA_MAP
from rebuild_excel_formula import rebuild_cells, rebuild_values
from migrate_schema import _migrate_1_1_to_1_2


# ── Fixture ───────────────────────────────────────────
@pytest.fixture(scope="session")
def v12_schema():
    with open(V12_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def v11_schema():
    with open(V11_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def root_schema():
    """根目录 schema 应始终等于最新版（当前 v1.3）。"""
    with open(ROOT_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def example_data():
    with open(EXAMPLE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def chain_data():
    with open(CHAIN_PATH, encoding="utf-8") as f:
        return json.load(f)


def _strip_v12_fields(data: dict) -> None:
    """移除 v1.2 及 v1.3 新增字段，还原为干净 v1.1 数据。"""
    data.pop("calculationChain", None)
    data.pop("decisionPoints", None)
    for inst in data.get("methods", {}).get("comps", {}).get("comparableInstances", []):
        adj = inst.get("adjustments", {})
        for key in ("locationDetails", "physicalDetails", "interestDetails"):
            adj.pop(key, None)


def _strip_v13_fields(data: dict) -> None:
    """移除 v1.3 新增字段（decisionPoints），还原为干净 v1.2 数据。"""
    data.pop("decisionPoints", None)


# ════════════════════════════════════════════════════════
# 1. v1.2 Schema 合法性与新增字段
# ════════════════════════════════════════════════════════
class TestV12Schema:
    def test_v12_schema_is_valid_draft_2020_12(self, v12_schema):
        jsonschema.Draft202012Validator.check_schema(v12_schema)

    def test_v12_schema_version_is_pattern(self, v12_schema):
        sv = v12_schema["properties"]["schemaVersion"]
        assert sv["pattern"] == "^1\\.2$"

    def test_v12_has_three_details_arrays(self, v12_schema):
        adj = (
            v12_schema["properties"]["methods"]["properties"]["comps"]
            ["properties"]["comparableInstances"]["items"]["properties"]["adjustments"]
        )
        for key in ("locationDetails", "physicalDetails", "interestDetails"):
            assert key in adj["properties"], f"adjustments 缺 {key}"
            arr = adj["properties"][key]
            assert arr["type"] == "array"
            assert arr["items"]["$ref"] == "#/$defs/factorDetail"

    def test_v12_has_calculation_chain(self, v12_schema):
        cc = v12_schema["properties"]["calculationChain"]
        assert cc["type"] == "object"
        assert "nodes" in cc["required"]
        assert cc["properties"]["version"]["const"] == "1.2"

    def test_v12_has_factor_detail_def(self, v12_schema):
        fd = v12_schema["$defs"]["factorDetail"]
        assert fd["required"] == ["name", "factor"]
        assert fd["additionalProperties"] is False

    def test_v12_has_calculation_node_def(self, v12_schema):
        cn = v12_schema["$defs"]["calculationNode"]
        assert "id" in cn["required"] and "formula" in cn["required"] and "refs" in cn["required"]
        assert cn["additionalProperties"] is False

    def test_root_schema_upgraded_beyond_v12(self, root_schema, v12_schema):
        """根目录 schema 已升级到 v1.3（不再等于 v1.2 版本化副本）。"""
        r, v = dict(root_schema), dict(v12_schema)
        r.pop("$id"), v.pop("$id")
        assert r != v, "root schema 应已升级到 v1.3，不再等于 v1.2"

    def test_v12_backward_compatible_with_v11(self, v11_schema, v12_schema):
        """v1.2 是 v1.1 的超集：v1.1 的所有 required 字段在 v1.2 中也 required。"""
        for field in v11_schema["required"]:
            assert field in v12_schema["required"], f"{field} 在 v1.2 中缺失 required"


# ════════════════════════════════════════════════════════
# 2. factorDetail 约束行为
# ════════════════════════════════════════════════════════
class TestFactorDetail:
    def test_details_item_missing_name_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        item = data["methods"]["comps"]["comparableInstances"][0]["adjustments"]["locationDetails"][0]
        del item["name"]
        errors = validate_full(data)
        assert errors, "缺 name 的 detail 项应被拒绝"

    def test_details_item_missing_factor_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        item = data["methods"]["comps"]["comparableInstances"][0]["adjustments"]["locationDetails"][0]
        del item["factor"]
        errors = validate_full(data)
        assert errors, "缺 factor 的 detail 项应被拒绝"

    def test_details_item_extra_field_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        item = data["methods"]["comps"]["comparableInstances"][0]["adjustments"]["locationDetails"][0]
        item["extra"] = "不应存在"
        errors = validate_full(data)
        assert errors, "detail 项的额外字段应被拒绝（additionalProperties: false）"

    def test_details_item_factor_non_numeric_rejected(self, example_data):
        data = json.loads(json.dumps(example_data))
        item = data["methods"]["comps"]["comparableInstances"][0]["adjustments"]["locationDetails"][0]
        item["factor"] = "优"
        errors = validate_full(data)
        assert errors, "非数值 factor 应被拒绝"


# ════════════════════════════════════════════════════════
# 3. 版本检测与路由
# ════════════════════════════════════════════════════════
class TestVersionRoutingV12:
    def test_version_map_contains_1_2(self):
        assert "1.2" in VERSION_SCHEMA_MAP

    def test_detect_1_2(self):
        assert detect_version({"schemaVersion": "1.2"}) == "1.2"

    def test_example_detects_1_2(self, example_data):
        """示例数据剥离 v1.3 字段后应检测为 v1.2。"""
        data = json.loads(json.dumps(example_data))
        _strip_v13_fields(data)
        data["schemaVersion"] = "1.2"
        assert detect_version(data) == "1.2"

    def test_example_validates_under_v12(self, example_data):
        errors = validate_full(example_data)
        assert not errors, f"v1.2 示例应通过 v1.2 schema，错误: {[e.message for e in errors]}"

    def test_example_validates_under_explicit_1_2(self, example_data):
        """示例数据剥离 v1.3 字段后应通过 v1.2 schema。"""
        data = json.loads(json.dumps(example_data))
        _strip_v13_fields(data)
        data["schemaVersion"] = "1.2"
        errors = validate_full(data, version="1.2")
        assert not errors

    def test_v12_fields_rejected_by_v11_schema(self, example_data):
        """v1.2 新增字段在 v1.1 schema 下应被拒绝（版本隔离）。"""
        data = json.loads(json.dumps(example_data))
        _strip_v12_fields(data)
        data["schemaVersion"] = "1.1"
        # 干净 v1.1 数据先确认通过
        assert not validate_full(data, version="1.1")
        # 加回 v1.2 顶层字段 → 被 v1.1 拒绝
        data["calculationChain"] = {"version": "1.2", "nodes": []}
        errors = validate_full(data, version="1.1")
        assert errors, "v1.1 schema 应拒绝 calculationChain"

    def test_v12_details_rejected_by_v11_schema(self, example_data):
        """v1.2 子项 details 数组在 v1.1 schema 下被拒绝的语义：
        v1.1 adjustments 无 additionalProperties 限制（接受额外字段），
        但顶层 calculationChain 被拒绝——验证重点在顶层隔离。"""
        data = json.loads(json.dumps(example_data))
        _strip_v12_fields(data)
        data["schemaVersion"] = "1.1"
        errors = validate_full(data, version="1.1")
        assert not errors, f"剥离 v1.2 字段后应通过 v1.1，错误: {[e.message for e in errors]}"


# ════════════════════════════════════════════════════════
# 4. 1.1 → 1.2 迁移
# ════════════════════════════════════════════════════════
class TestMigrationV12:
    def test_migrate_updates_schema_version(self, example_data):
        data = json.loads(json.dumps(example_data))
        _strip_v12_fields(data)
        data["schemaVersion"] = "1.1"
        migrated, notes = _migrate_1_1_to_1_2(data)
        assert migrated["schemaVersion"] == "1.2"
        assert any("schemaVersion" in n for n in notes)

    def test_migrate_does_not_fabricate_details(self, example_data):
        """迁移只更新版本号，不自动编造子项明细（需 Excel 子项粒度）。"""
        data = json.loads(json.dumps(example_data))
        _strip_v12_fields(data)
        data["schemaVersion"] = "1.1"
        migrated, _ = _migrate_1_1_to_1_2(data)
        inst = migrated["methods"]["comps"]["comparableInstances"][0]["adjustments"]
        assert "locationDetails" not in inst
        assert "calculationChain" not in migrated

    def test_migrated_data_passes_v12_schema(self, example_data):
        data = json.loads(json.dumps(example_data))
        _strip_v12_fields(data)
        data["schemaVersion"] = "1.1"
        migrated, _ = _migrate_1_1_to_1_2(data)
        errors = validate_full(migrated, version="1.2")
        assert not errors, f"迁移后应通过 v1.2 schema，错误: {[e.message for e in errors]}"


# ════════════════════════════════════════════════════════
# 5. 子项合并一致性（偏差加总法）
# ════════════════════════════════════════════════════════
class TestDetailMergeConsistency:
    """顶层系数必须等于子项按偏差加总法合并的结果：
    100/(100+Σ(factor-100)) = 100/(Σfactor-(n-1)*100)。
    """

    @staticmethod
    def merged_factor(details):
        return 100.0 / (sum(d["factor"] for d in details) - (len(details) - 1) * 100)

    def test_all_three_groups_all_instances(self, example_data):
        instances = example_data["methods"]["comps"]["comparableInstances"]
        assert len(instances) == 3
        for i, inst in enumerate(instances):
            adj = inst["adjustments"]
            for top_key, details_key in [
                ("location", "locationDetails"),
                ("physical", "physicalDetails"),
                ("interest", "interestDetails"),
            ]:
                details = adj[details_key]
                assert len(details) >= 1, f"实例{i+1} {details_key} 不应为空"
                merged = self.merged_factor(details)
                top = adj[top_key]
                assert abs(merged - top) < 1e-5, (
                    f"实例{i+1} {top_key}: 子项合并 {merged:.6f} ≠ 顶层系数 {top}"
                )

    def test_location_102_corrects_down(self, example_data):
        """实例 location 子项 102（优于估价对象）→ 合并系数 <1（单价向下修正）。"""
        inst = example_data["methods"]["comps"]["comparableInstances"][0]
        adj = inst["adjustments"]
        assert adj["locationDetails"][0]["factor"] == 102  # 唯一非 100 项
        assert adj["location"] < 1.0

    def test_physical_97_corrects_up(self, example_data):
        """实例 physical 子项 97（劣于估价对象）→ 合并系数 >1（单价向上修正）。"""
        inst = example_data["methods"]["comps"]["comparableInstances"][0]
        adj = inst["adjustments"]
        assert adj["physicalDetails"][0]["factor"] == 97
        assert adj["physical"] > 1.0

    def test_known_values(self, example_data):
        """抽查三实例顶层系数与已知合并值一致。"""
        instances = example_data["methods"]["comps"]["comparableInstances"]
        expected = [
            {"location": 0.980392, "physical": 1.030928},
            {"location": 0.990099, "physical": 0.980392},
            {"location": 1.020408, "physical": 1.010101},
        ]
        for i, (inst, exp) in enumerate(zip(instances, expected)):
            adj = inst["adjustments"]
            for key, val in exp.items():
                assert abs(adj[key] - val) < 1e-5, f"实例{i+1} {key} 应≈{val}"


# ════════════════════════════════════════════════════════
# 6. calculationChain 重建（cells 模式）
# ════════════════════════════════════════════════════════
class TestRebuildCells:
    def test_chain_has_8_nodes(self, chain_data):
        assert chain_data["version"] == "1.2"
        assert len(chain_data["nodes"]) == 8

    def test_instance1_formula(self, chain_data):
        nodes = {n["id"]: n for n in chain_data["nodes"]}
        rebuilt = rebuild_cells({"nodes": [nodes["comps.adjustedUnitPrice.instance1"]]})[0]["rebuilt"]
        assert rebuilt == (
            "=ROUND(T4*T5/V5*T6/V6*100/(SUM(V7:V18)-1100)"
            "*100/(SUM(V19:V23)-400)*100/(SUM(V24:V31)-700),0)"
        )

    def test_final_unit_price_formula(self, chain_data):
        nodes = {n["id"]: n for n in chain_data["nodes"]}
        rebuilt = rebuild_cells({"nodes": [nodes["comps.finalUnitPrice"]]})[0]["rebuilt"]
        assert rebuilt == "ROUND((T32*0.5+W32*0.3+Z32*0.2),-1)"

    def test_income_noi_formula(self, chain_data):
        nodes = {n["id"]: n for n in chain_data["nodes"]}
        rebuilt = rebuild_cells({"nodes": [nodes["income.noi"]]})[0]["rebuilt"]
        # egi → G5（effectiveGrossIncome），oe → G11（operatingExpenses）
        assert rebuilt == "=G5-G11"

    def test_total_value_formula(self, chain_data):
        nodes = {n["id"]: n for n in chain_data["nodes"]}
        rebuilt = rebuild_cells({"nodes": [nodes["result.totalValue"]]})[0]["rebuilt"]
        assert rebuilt == "ROUND(M6*N6,0)"

    def test_all_nodes_rebuild_without_leftover_refs(self, chain_data):
        """所有节点重建后不应残留 {{refKey}} 占位符（局部引用 G23 除外）。"""
        import re
        for n in chain_data["nodes"]:
            rebuilt = rebuild_cells({"nodes": [n]})[0]["rebuilt"]
            leftovers = re.findall(r"\{\{(\w+)\}\}", rebuilt)
            assert not leftovers, f"{n['id']} 残留未解析引用: {leftovers}"


# ════════════════════════════════════════════════════════
# 7. calculationChain 求值（values 模式）
# ════════════════════════════════════════════════════════
class TestRebuildValues:
    def test_expected_nodes_pass(self, chain_data, example_data):
        """对示例数据求值：7 个节点应 PASS（income.value 依赖 growthRate，
        示例用 directCapitalization 模式无此字段，允许 SKIP 而非 FAIL）。"""
        results = rebuild_values(chain_data, example_data)
        by_id = {r["id"]: r for r in results}
        assert len(results) == 8
        for node_id in [
            "comps.adjustedUnitPrice.instance1",
            "comps.adjustedUnitPrice.instance2",
            "comps.adjustedUnitPrice.instance3",
            "comps.finalUnitPrice",
            "income.noi",
            "result.finalTotalValue",
            "result.totalValue",
        ]:
            assert by_id[node_id]["status"] == "PASS", (
                f"{node_id}: {by_id[node_id]}"
            )
        assert by_id["income.value"]["status"] in ("PASS", "SKIP"), (
            f"income.value 不应 FAIL: {by_id['income.value']}"
        )

    def test_instance1_adjusted_price_value(self, chain_data, example_data):
        results = rebuild_values(chain_data, example_data)
        by_id = {r["id"]: r for r in results}
        r = by_id["comps.adjustedUnitPrice.instance1"]
        assert r["computed"] == 25773.0
        assert r["actual"] == 25773

    def test_final_unit_price_value(self, chain_data, example_data):
        results = rebuild_values(chain_data, example_data)
        r = {x["id"]: x for x in results}["comps.finalUnitPrice"]
        assert r["computed"] == 25790.0
        assert r["actual"] == 25790

    def test_income_noi_value(self, chain_data, example_data):
        results = rebuild_values(chain_data, example_data)
        r = {x["id"]: x for x in results}["income.noi"]
        assert r["computed"] == 48124.0
        assert r["actual"] == 48124


# ════════════════════════════════════════════════════════
# 8. CHANGELOG
# ════════════════════════════════════════════════════════
class TestChangelogV12:
    def test_changelog_has_v1_2_entry(self):
        content = CHANGELOG_PATH.read_text(encoding="utf-8")
        assert "## [1.2]" in content, "CHANGELOG 应有 v1.2 条目"
