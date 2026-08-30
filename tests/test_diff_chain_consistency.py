"""
test_diff_chain_consistency.py — 双端决策链校验一致性回归测试（Round 3 固化）

背景：决策链校验 C1-C6 存在 JS（app/js/dp-core.js）与 Python
（scripts/validate_appraisal_json.py）两套独立实现。Round 1 差分发现
判定一致率仅 90.70%，Round 2 修复后 100%。本测试将差分协议常驻，
防止双端语义再次漂移。

对比协议（与 tests/diff_chain_generator.py 一致，种子固定可复现）：
  - 输入：decisionPoints 数组（分层生成：合法/单违规注入 C1-C6/混合边界）
  - 双端各输出：违规类别集合 + 错误条数
  - 断言：① 类别判定一致率 = 1.0 ② 错误条数 100% 一致 ③ 每个 kind 至少触发一次
          ④ 固化对抗形状（浮点 attempt / ghost 分叉）双端语义锚定

运行：python -m pytest tests/test_diff_chain_consistency.py -q
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from diff_chain_generator import (  # noqa: E402
    DIFF_KINDS, find_node, gen_case, gen_valid_dp, classify_codes_py, classify_py,
)
from validate_appraisal_json import _check_decision_chain  # noqa: E402

SEED = 20260828
COUNT = 300
RUNNER = Path(__file__).resolve().parent / "chain_runner.js"

# KINDS 从生成器单一事实源派生（去重保序）：序列与 Round 4 固化语料完全一致，
# 生成器新增 kind 后此处自动跟进，杜绝"清单漏项"型失明（P1-3 教训）。
KINDS = list(dict.fromkeys(DIFF_KINDS))

NODE_BIN = find_node()


@pytest.fixture(scope="module")
def diff_dataset():
    """生成并双端跑完的差分数据集（模块级缓存，跑一次）。"""
    if not NODE_BIN:
        pytest.skip("未找到 node 可执行文件（设 WORKBUDDY_NODE 或加入 PATH）")
    rng = random.Random(SEED)
    inputs, case_kinds = [], []
    for _ in range(COUNT):
        k = rng.choice(KINDS)
        case_kinds.append(k)
        inputs.append({"decisionPoints": gen_case(rng, k)})

    py_errs = [_check_decision_chain(inp) for inp in inputs]
    py_cats = [classify_py(e) for e in py_errs]
    py_codes = [classify_codes_py(e) for e in py_errs]
    py_counts = [len(e) for e in py_errs]

    proc = subprocess.run(
        [NODE_BIN, str(RUNNER)], input=json.dumps(inputs),
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        pytest.fail("node runner 失败: " + proc.stderr)
    js_rows = json.loads(proc.stdout)
    js_cats = [set(r["violations"]) for r in js_rows]
    js_codes = [set(r["codes"]) for r in js_rows]
    js_counts = [r["errorCount"] for r in js_rows]

    return {
        "inputs": inputs, "kinds": case_kinds,
        "py_cats": py_cats, "py_counts": py_counts, "py_codes": py_codes,
        "js_cats": js_cats, "js_counts": js_counts, "js_codes": js_codes,
    }


def test_judgment_consistency_rate_is_100(diff_dataset):
    """① 类别判定一致率必须 = 100%（核心指标，防漂移复发）。"""
    mismatches = [
        i for i in range(COUNT)
        if diff_dataset["py_cats"][i] != diff_dataset["js_cats"][i]
    ]
    assert not mismatches, (
        f"判定不一致 {len(mismatches)} 例（N={COUNT}）："
        f"首例 #{mismatches[0]} kind={diff_dataset['kinds'][mismatches[0]]} "
        f"py={sorted(diff_dataset['py_cats'][mismatches[0]])} "
        f"js={sorted(diff_dataset['js_cats'][mismatches[0]])}"
    )


def test_error_code_consistency(diff_dataset):
    """①b 违规码（含 key）必须逐一一致——比类别级更严，能抓"归因给错对象"的漂移。

    码格式 `C4:key=DP-comp`：Python 端来自 error.code 字段，JS 端来自消息前缀。
    """
    mismatches = [
        i for i in range(COUNT)
        if diff_dataset["py_codes"][i] != diff_dataset["js_codes"][i]
    ]
    assert not mismatches, (
        f"违规码不一致 {len(mismatches)} 例（N={COUNT}）："
        f"首例 #{mismatches[0]} kind={diff_dataset['kinds'][mismatches[0]]} "
        f"py={sorted(diff_dataset['py_codes'][mismatches[0]])} "
        f"js={sorted(diff_dataset['js_codes'][mismatches[0]])}"
    )


def test_every_error_carries_a_code(diff_dataset):
    """①c 每条违规都必须带机器码（防新增分支漏挂 code 而退回人工读差）。"""
    bare = [
        (i, c) for i in range(COUNT)
        for c in diff_dataset["py_codes"][i] | diff_dataset["js_codes"][i]
        if ":" not in c or "key=" not in c
    ]
    assert not bare, (
        f"以下违规缺 key 机器码（前 5）：{bare[:5]}——码格式应为 C<n>:key=<id>"
    )


def test_error_count_consistency(diff_dataset):
    """② 错误条数必须 100% 一致（Round 3 H3：c4 去重后对齐）。"""
    diffs = [
        i for i in range(COUNT)
        if diff_dataset["py_counts"][i] != diff_dataset["js_counts"][i]
    ]
    assert not diffs, (
        f"条数不一致 {len(diffs)} 例（N={COUNT}）："
        f"首例 #{diffs[0]} kind={diff_dataset['kinds'][diffs[0]]} "
        f"py={diff_dataset['py_counts'][diffs[0]]} js={diff_dataset['js_counts'][diffs[0]]}"
    )


def test_every_kind_triggered_at_least_once(diff_dataset):
    """③ 生成器自检：每个 kind 至少触发一次（防测试静默退化）。"""
    seen = set(diff_dataset["kinds"])
    missing = [k for k in KINDS if k not in seen]
    assert not missing, f"生成器缺口：以下场景零触发 {missing}"


# ── ④ 固化对抗形状（Round 4/6，P0-1 / P1-3 / P1-1 教训：随机语料之外的确定性锚点） ──

def _frozen_shapes():
    """对抗探测形状 → 双端预期（类别集合, 违规码集合, 错误条数）。码含 key，逐一断言。"""
    a = lambda rid, status, attempt, sup=None: gen_valid_dp(rid, status, attempt, sup)
    num_sup = a("DP-b", "pending", 2)
    num_sup["supersedes"] = 42
    no_id = a("DP-b", "pending", 9, "DP-a")
    del no_id["id"]
    return [
        # S2: 非整数浮点后继 → 双端报 C6（修复前 PY 静默/JS 报，漂移）
        ("S2_b2.5", [a("DP-a", "rejected", 1), a("DP-b", "pending", 2.5, "DP-a")],
         {"C6"}, {"C6:key=DP-b"}, 1),
        # S3: 整数值浮点前驱 + 一致整数后继 → 双端通过（修复前 PY 报/JS 不报，漂移）
        ("S3_a2.0_b3", [a("DP-a", "rejected", 2.0), a("DP-b", "pending", 3, "DP-a")],
         set(), set(), 0),
        # S4: 整数值浮点前驱 + 错误后继 → 双端报 C6（修复前 PY 静默/JS 报，漂移）
        ("S4_a2.0_b2", [a("DP-a", "rejected", 2.0), a("DP-b", "pending", 2, "DP-a")],
         {"C6"}, {"C6:key=DP-b"}, 1),
        # GHOST: 双 DP 指向同一不存在 id → 双端均仅 C1×2（修复前 JS 多报 C4，漂移）
        ("GHOST_fork", [a("DP-b", "pending", 2, "GHOST"), a("DP-c", "pending", 2, "GHOST")],
         {"C1"}, {"C1:key=GHOST"}, 2),
        # Round 6（审查 P1-1 整改固化）：
        # NUM_SUP: 数值型 supersedes → 双端 string-only 语义静默一致（修复前 PY 报 C1:key=42）
        ("NUM_SUP", [a("DP-a", "rejected", 1), num_sup], set(), set(), 0),
        # NO_ID_C6: 缺 id + attempt 跳号 → 双端 C6:key=<no-id>（修复前 PY 多报假阳性 C5:key=None，
        #   且 key 渲染 None vs undefined 漂移）
        ("NO_ID_C6", [a("DP-a", "rejected", 1), no_id],
         {"C6"}, {"C6:key=<no-id>"}, 1),
        # COLON: id 含冒号的分叉 → 码结构化导出后 key 原样保留（修复前 JS 解析截断为 C4:key=DP）
        ("COLON_fork", [a("DP:a", "rejected", 1), a("DP-b", "pending", 2, "DP:a"),
                        a("DP-c", "pending", 2, "DP:a")],
         {"C4"}, {"C4:key=DP:a"}, 1),
    ]


def test_frozen_adversarial_shapes():
    """④ 固化对抗形状：浮点/ghost/畸形输入双端语义锚定（码级逐一断言）。"""
    if not NODE_BIN:
        pytest.skip("未找到 node 可执行文件（设 WORKBUDDY_NODE 或加入 PATH）")
    shapes = _frozen_shapes()
    inputs = [{"decisionPoints": dps} for _, dps, _, _, _ in shapes]

    for (name, _, exp_cats, exp_codes, exp_count), inp in zip(shapes, inputs):
        py_errs = _check_decision_chain(inp)
        py_cats = classify_py(py_errs)
        py_codes = classify_codes_py(py_errs)
        assert py_cats == exp_cats and len(py_errs) == exp_count, (
            f"Python 端偏离固化预期 [{name}]: "
            f"{sorted(py_cats)}x{len(py_errs)}，预期 {sorted(exp_cats)}x{exp_count}"
        )
        assert py_codes == exp_codes, (
            f"Python 端违规码偏离 [{name}]: {sorted(py_codes)}，预期 {sorted(exp_codes)}"
        )

    proc = subprocess.run(
        [NODE_BIN, str(RUNNER)], input=json.dumps(inputs),
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        pytest.fail("node runner 失败: " + proc.stderr)
    js_rows = json.loads(proc.stdout)
    for (name, _, exp_cats, exp_codes, exp_count), row in zip(shapes, js_rows):
        js_cats = set(row["violations"])
        js_codes = set(row["codes"])
        assert js_cats == exp_cats and row["errorCount"] == exp_count, (
            f"JS 端偏离固化预期 [{name}]: "
            f"{sorted(js_cats)}x{row['errorCount']}，预期 {sorted(exp_cats)}x{exp_count}"
        )
        assert js_codes == exp_codes, (
            f"JS 端违规码偏离 [{name}]: {sorted(js_codes)}，预期 {sorted(exp_codes)}"
        )
