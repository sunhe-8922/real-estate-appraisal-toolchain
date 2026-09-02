"""
test_generator_fixture_parity.py — 生成器 ↔ 冻结载体一致性门禁（Round 11 H11 固化）

背景：R7→R10 的整改连续三次漏同步「载体」（R9 示例 JSON、R10 冻结 fixture、
R11 生成器）。Round 10 删除 ±65 豁免后，门禁已能拦截旧形态末节点，但
`extract_calculation_chain.py` 仍产出 ROUND(面积×单价) + 重复 target 的旧形态
——生成器是最后一个缺陷源。Round 11 把生成器同步为整改形态，并用生成器输出
重写冻结载体（字节级一致），本门禁把「不再漂移」固化为常驻断言：

  ① 奇偶：生成器输出 == outputs/calculation_chain.json（字段级全等）
     ——生成器或载体任何一方单独漂移即红灯。
  ② 末节点形态：末节点必须是单价派生自权威总价（target 唯一），
     全链不得出现重复 target（P1-2B 形态的机器定义）。
  ③ 负向验证：把旧形态节点注入求值器必须 FAIL——证明旧形态回来不会静默通过
     （依赖 Round 10 删除的 NODE_TOLERANCE=65 豁免；尾节点阈值 1 < 18 元差）。

运行：python -m pytest tests/test_generator_fixture_parity.py -q
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
TEMPLATE = ROOT / "outputs" / "房地产评估明细表-计算模板.xlsx"
FIXTURE = ROOT / "outputs" / "calculation_chain.json"
RESIDENTIAL_EXAMPLE = ROOT / "schema" / "example-武汉洪山住宅.json"

sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="module")
def generated():
    if not TEMPLATE.exists():
        pytest.skip(f"模板不存在: {TEMPLATE}")
    from extract_calculation_chain import extract_chain
    return extract_chain(str(TEMPLATE))


@pytest.fixture(scope="module")
def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ── ① 奇偶：生成器输出 == 冻结载体 ────────────────────────────────
def test_generator_output_equals_frozen_fixture(generated, fixture):
    """任何一方单独漂移（改生成器不改载体，或手改载体）即红灯。"""
    assert generated == fixture, (
        "生成器输出与冻结载体漂移——两者必须同步变更。\n"
        f"生成器节点序: {[n['id'] for n in generated['nodes']]}\n"
        f"载体节点序  : {[n['id'] for n in fixture['nodes']]}"
    )


def test_generator_does_not_emit_legacy_tail_node(generated):
    """旧形态节点 id（result.totalValue）不得再出现（P1-2B 载体分裂源头）。"""
    ids = [n["id"] for n in generated["nodes"]]
    assert "result.totalValue" not in ids, (
        "生成器回退到旧形态末节点（result.totalValue）——Round 11 H11 已整改，"
        "恢复旧形态必须同时给出新的缺陷编号背书"
    )


# ── ② 末节点形态 + target 唯一 ────────────────────────────────────
def test_tail_node_is_derived_unit_form(fixture):
    """末节点 = 单价派生自权威总价（R7 P1-1 整改形态的机器定义）。"""
    last = fixture["nodes"][-1]
    assert last["id"] == "result.finalUnitValue"
    assert last["formula"] == "=ROUND({{finalTotal}}/{{area}},0)"
    assert last["target"] == "result.finalUnitValue"
    assert last["refs"] == {
        "finalTotal": "result.finalTotalValue",
        "area": "property.area",
    }


def test_no_duplicate_targets_across_chain(fixture):
    """全链 target 唯一——P1-2B 的重复 target（两节点写同一 result.finalTotalValue）不得复发。"""
    targets = [n["target"] for n in fixture["nodes"]]
    dupes = sorted({t for t in targets if targets.count(t) > 1})
    assert not dupes, f"重复 target: {dupes}（P1-2B 形态：两节点写同一 target）"


# ── ③ 负向验证：旧形态回来必须被拦 ────────────────────────────────
def test_legacy_tail_node_is_rejected_by_evaluator():
    """把 Round 10 前的旧形态节点注入求值器：必须 FAIL，不得静默 PASS。

    旧形态 ROUND(面积×单价) 对住宅示例 = ROUND(128.5×25461) = 3271738，
    与权威总价 3271720 差 18 元 > 默认容差 1。该 18 元在 Round 10 前被
    NODE_TOLERANCE=65 豁免成静默 PASS——本测试证明豁免删除后旧形态必红。
    """
    from rebuild_excel_formula import rebuild_values

    data = json.loads(RESIDENTIAL_EXAMPLE.read_text(encoding="utf-8"))
    legacy_node = {
        "id": "result.totalValue",
        "target": "result.finalTotalValue",
        "formula": "ROUND({{area}}*{{unitValue}},0)",
        "refs": {
            "area": "property.area",
            "unitValue": "result.finalUnitValue",
        },
    }
    results = rebuild_values({"nodes": [legacy_node]}, data)
    r = results[0]
    assert r["status"] == "FAIL", f"旧形态被放过了（豁免复活？）: {r}"
    assert r["diff"] == 18.0, f"闭合差应为 18 元（面积×单价回乘）: {r}"
