"""
test_dp_action_vs_oracle.py — applyDecision / isTerminal 的差分固化测试（Round 7）

背景：决策点的核心逻辑里，`validateChain` 与两个建链函数已有机械验证，
**决策动作（applyDecision）与状态机（isTerminal）此前零机械验证**——只有
`tests/test_dp_core.js` 的手写断言。本测试按 Round 1 协议补齐：
分层生成器 + 执行器 + 规格参考实现（`tests/dp_action_oracle.py`）+ 固化锚点。

差分的对面同样是**规格参考实现**（Python 端没有这两个函数的生产实现，D-012 路线）。

断言：
  ① applyDecision 结果（ok / 机器码 / 输出 DP 全字段）双端一致
  ② isTerminal 状态机判定双端一致
  ③ 每个 kind 至少触发一次
  ④ 规格 1.3 / 4.3 直译锚点（不依赖 oracle 的手工期望，含状态机不变量）

运行：python -m pytest tests/test_dp_action_vs_oracle.py -q
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from diff_chain_generator import find_node  # noqa: E402
from dp_action_oracle import run_case  # noqa: E402
from dp_action_shapes import ACTION_KINDS, gen_action_case  # noqa: E402

SEED = 20260831
COUNT = 300
RUNNER = Path(__file__).resolve().parent / "dp_action_runner.js"
NODE_BIN = find_node()


def _cases():
    rng = random.Random(SEED)
    cases = []
    for _ in range(COUNT):
        kind = rng.choice(ACTION_KINDS)
        case = gen_action_case(rng, kind)
        case["kind"] = kind
        cases.append(case)
    return cases


@pytest.fixture(scope="module")
def diff_dataset():
    if not NODE_BIN:
        pytest.skip("未找到 node 可执行文件（设 WORKBUDDY_NODE 或加入 PATH）")
    cases = _cases()
    proc = subprocess.run(
        [NODE_BIN, str(RUNNER)], input=json.dumps(cases),
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        pytest.fail("node runner 失败: " + proc.stderr)
    return {"cases": cases, "py": [run_case(c) for c in cases], "js": json.loads(proc.stdout)}


def test_apply_decision_matches_oracle(diff_dataset):
    """① applyDecision（ok / 机器码 / 输出 DP 全字段）双端一致。"""
    bad = [(i, diff_dataset["py"][i]["apply"], diff_dataset["js"][i]["apply"])
           for i in range(COUNT)
           if diff_dataset["py"][i]["apply"] != diff_dataset["js"][i]["apply"]]
    assert not bad, (
        f"applyDecision 不一致 {len(bad)} 例（N={COUNT}）：首例 #{bad[0][0]} "
        f"kind={diff_dataset['cases'][bad[0][0]]['kind']}\n"
        f"  py={json.dumps(bad[0][1], ensure_ascii=False)}\n"
        f"  js={json.dumps(bad[0][2], ensure_ascii=False)}"
    )


def test_is_terminal_matches_oracle(diff_dataset):
    """② isTerminal 状态机判定双端一致。"""
    bad = [(i, diff_dataset["py"][i]["terminal"], diff_dataset["js"][i]["terminal"])
           for i in range(COUNT)
           if diff_dataset["py"][i]["terminal"] != diff_dataset["js"][i]["terminal"]]
    assert not bad, (
        f"isTerminal 不一致 {len(bad)} 例：首例 #{bad[0][0]} "
        f"status={diff_dataset['cases'][bad[0][0]].get('status')!r} "
        f"py={bad[0][1]} js={bad[0][2]}"
    )


def test_every_action_kind_triggered(diff_dataset):
    """③ 语料自检：每个 kind 至少触发一次。"""
    seen = {c["kind"] for c in diff_dataset["cases"]}
    missing = [k for k in ACTION_KINDS if k not in seen]
    assert not missing, f"生成器缺口：以下决策形状零触发 {missing}"


# ── ④ 规格直译锚点（期望值来自《决策点规格定义》1.3 / 4.3，不是从 JS 输出抄的） ──

def _dp(status="pending"):
    return {"id": "DP-comp", "name": "可比实例选取", "phase": "inMethod",
            "trigger": "method:comps", "riskLevel": "P1", "status": status,
            "conclusion": "建议选取 3 个可比实例",
            "evidence": [{"item": "同小区成交", "source": "中原地产"}],
            "reasoning": "同小区、近半年",
            "risks": [{"description": "楼层差异", "level": "P1", "mitigation": "楼层修正"}]}


ANCHORS = [
    # (说明, case, 期望 ok, 期望 code, 期望 status, 期望 isTerminal)
    ("批准：status=approved 且为终结状态（锚点 status 传决策后状态，专测状态机）",
     {"dp": _dp(), "action": "approved", "status": "approved", "opts": {"comment": "同意"}},
     True, None, "approved", True),
    ("调整：带 modifications → status=modified（终结）",
     {"dp": _dp(), "action": "modified", "status": "modified",
      "opts": {"comment": "微调", "modifications": "换 2 号实例"}},
     True, None, "modified", True),
    ("调整缺 modifications → 拒绝（规格 1.3 必填）",
     {"dp": _dp(), "action": "modified", "status": "pending", "opts": {"modifications": "  "}},
     False, "E_MODIFIED_REQUIRES_MODIFICATIONS", None, False),
    ("驳回：带 comment → status=rejected（非终结，触发建链）",
     {"dp": _dp(), "action": "rejected", "status": "rejected",
      "opts": {"comment": "实例 C 信源等级低"}},
     True, None, "rejected", False),
    ("驳回缺 comment → 拒绝（编排协议强化：否决原因是建链回应与学习信号）",
     {"dp": _dp(), "action": "rejected", "status": "pending", "opts": {}},
     False, "E_REJECTED_REQUIRES_COMMENT", None, False),
    ("非 pending（已 approved）→ 不可重复决策",
     {"dp": _dp("approved"), "action": "approved", "status": "approved"},
     False, "E_NOT_PENDING", None, True),
    ("非法动作 → 拒绝",
     {"dp": _dp(), "action": "cancel", "status": "pending"},
     False, "E_BAD_ACTION", None, False),
    ("dp 不是对象 → 拒绝",
     {"dp": "DP-comp", "action": "approved", "status": "pending"},
     False, "E_DP_NOT_OBJECT", None, False),
    ("comment 前后空白 → trim（规格：humanDecision.comment 为决策备注）",
     {"dp": _dp(), "action": "approved", "status": "approved",
      "opts": {"comment": "  同意  "}},
     True, None, "approved", True),
]


def test_spec_anchors():
    """④ 规格直译锚点：期望值手工写死，防 oracle 与 JS 一起错；并断言状态机不变量。"""
    if not NODE_BIN:
        pytest.skip("未找到 node 可执行文件（设 WORKBUDDY_NODE 或加入 PATH）")
    cases = []
    for i, (_desc, case, _ok, _code, _status, _term) in enumerate(ANCHORS):
        c = dict(case)
        c["kind"] = "anchor-%d" % i
        cases.append(c)

    proc = subprocess.run([NODE_BIN, str(RUNNER)], input=json.dumps(cases),
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        pytest.fail("node runner 失败: " + proc.stderr)
    js_rows = json.loads(proc.stdout)
    py_rows = [run_case(c) for c in cases]

    for (desc, _case, exp_ok, exp_code, exp_status, exp_term), py, js in zip(ANCHORS, py_rows, js_rows):
        for end, row in (("py", py), ("js", js)):
            a = row["apply"]
            assert a["ok"] is exp_ok, f"[{end}] {desc}：ok={a['ok']}，期望 {exp_ok}"
            assert a["code"] == exp_code, f"[{end}] {desc}：code={a['code']}，期望 {exp_code}"
            if exp_ok:
                assert a["dp"]["status"] == exp_status, f"[{end}] {desc}：status 不符"
                # 状态机不变量：输出状态与动作一致（schema P0-6a/b/c）
                assert a["dp"]["status"] == _case["action"]
            assert row["terminal"] is exp_term, f"[{end}] {desc}：isTerminal 不符"
        assert py == js, f"{desc}：双端不一致\n py={py}\n js={js}"

    # 额外不变量：驳回后应为非终结（触发新 DP），批准/调整为终结（规格 4.3）
    for (_desc, _case, exp_ok, _code, _status, exp_term), py in zip(ANCHORS, py_rows):
        if exp_ok:
            assert py["apply"]["dp"]["status"] != "pending", "决策后不应停留在 pending"
