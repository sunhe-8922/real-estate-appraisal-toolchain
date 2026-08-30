"""
test_dp_chain_vs_oracle.py — resolveChain / buildSuccessorShell 的差分固化测试

背景：这两个决策链函数此前只有 JS 单端实现 + 手写断言（tests/test_dp_core.js），
零机械验证，是"双端一致"声明的最大盲区（假设池 #10 / 审查未检查边界）。

**差分的第二端不是生产代码，而是规格参考实现** `tests/dp_chain_oracle.py`
（按《决策点规格定义》4.2 独立实现）。声明边界必须写清楚：
本测试证明的是「JS 实现 ≡ 规格参考实现」，**不是**「JS ≡ Python 生产实现」——
Python 端目前没有这两个函数的生产实现。

对比协议（种子固定 20260830，N=300）：
  ① resolveChain 输出（byId/roots/chains）双端一致
  ② buildSuccessorShell 输出（ok/机器码/successor 全字段）双端一致
  ③ 每个 kind 至少触发一次（防语料静默退化）
  ④ 规格直译的确定性锚点（不依赖随机语料，防 oracle 与 JS 同时错）

运行：python -m pytest tests/test_dp_chain_vs_oracle.py -q
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from chain_shapes import SHAPE_KINDS, gen_shape  # noqa: E402
from diff_chain_generator import find_node  # noqa: E402
from dp_chain_oracle import run_case  # noqa: E402

SEED = 20260830
COUNT = 300
RUNNER = Path(__file__).resolve().parent / "dp_chain_runner.js"
NODE_BIN = find_node()


def _build_cases():
    rng = random.Random(SEED)
    cases = []
    for _ in range(COUNT):
        kind = rng.choice(SHAPE_KINDS)
        case = gen_shape(rng, kind)
        case["kind"] = kind
        cases.append(case)
    return cases


@pytest.fixture(scope="module")
def diff_dataset():
    """生成并双端跑完的差分数据集（模块级缓存，跑一次）。"""
    if not NODE_BIN:
        pytest.skip("未找到 node 可执行文件（设 WORKBUDDY_NODE 或加入 PATH）")
    cases = _build_cases()
    proc = subprocess.run(
        [NODE_BIN, str(RUNNER)], input=json.dumps(cases),
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        pytest.fail("node runner 失败: " + proc.stderr)
    js_rows = json.loads(proc.stdout)
    py_rows = [run_case(c) for c in cases]
    return {"cases": cases, "py": py_rows, "js": js_rows}


def _first_mismatch(dataset, field):
    for i, (p, j) in enumerate(zip(dataset["py"], dataset["js"])):
        if p[field] != j[field]:
            return i, p[field], j[field]
    return None


def test_resolve_chain_matches_oracle(diff_dataset):
    """① resolveChain（byId / roots / chains）双端一致。"""
    bad = _first_mismatch(diff_dataset, "resolve")
    assert bad is None, (
        f"resolveChain 不一致：首例 #{bad[0]} kind={diff_dataset['cases'][bad[0]]['kind']} "
        f"py={bad[1]} js={bad[2]}"
    )


def test_build_successor_shell_matches_oracle(diff_dataset):
    """② buildSuccessorShell（ok / 机器码 / successor 全字段）双端一致。"""
    bad = _first_mismatch(diff_dataset, "successor")
    assert bad is None, (
        f"buildSuccessorShell 不一致：首例 #{bad[0]} "
        f"kind={diff_dataset['cases'][bad[0]]['kind']} py={bad[1]} js={bad[2]}"
    )


def test_every_shape_kind_triggered(diff_dataset):
    """③ 语料自检：每个 kind 至少触发一次（防静默退化）。"""
    seen = {c["kind"] for c in diff_dataset["cases"]}
    missing = [k for k in SHAPE_KINDS if k not in seen]
    assert not missing, f"生成器缺口：以下形状零触发 {missing}"


# ── ④ 规格直译锚点（期望值来自《决策点规格定义》4.2，不是从 JS 输出抄的） ──

def _dp(rid, status, attempt=None, supersedes=None, **extra):
    d = {"id": rid, "name": "DP " + rid, "phase": "inMethod", "trigger": "method:comps",
         "riskLevel": "P1", "status": status, "conclusion": "x", "evidence": [],
         "reasoning": "y", "risks": []}
    if attempt is not None:
        d["attempt"] = attempt
    if supersedes is not None:
        d["supersedes"] = supersedes
    d.update(extra)
    return d


ANCHORS = [
    # (说明, case, 期望 successor（ok/code/id/attempt）, 期望 chains)
    ("初版 rejected（attempt=1）→ DP1-2 / attempt=2",
     {"dps": [_dp("DP1", "rejected", 1)], "dpIndex": 0},
     (True, None, "DP1-2", 2), None),
    ("attempt 缺失视作 1 → DP2-2",
     {"dps": [_dp("DP2", "rejected")], "dpIndex": 0},
     (True, None, "DP2-2", 2), None),
    ("二次驳回 DP-comp-2 → DP-comp-3（baseIdOf 去尾号）",
     {"dps": [_dp("DP-comp", "rejected", 1),
              _dp("DP-comp-2", "rejected", 2, "DP-comp")], "dpIndex": 1},
     (True, None, "DP-comp-3", 3), None),
    ("approved 为终结状态 → C3 拒绝",
     {"dps": [_dp("DP-a", "approved", 1)], "dpIndex": 0},
     (False, "C3", None, None), None),
    ("已有后继 → C4 防分叉",
     {"dps": [_dp("DP-a", "rejected", 1), _dp("DP-b", "pending", 2, "DP-a")], "dpIndex": 0},
     (False, "C4", None, None), None),
    ("自引用 → C5（validateChain 定性为 C2，此处语义不同，属已知差异）",
     {"dps": [_dp("DP-a", "rejected", 1, supersedes="DP-a")], "dpIndex": 0},
     (False, "C5", None, None), None),
    ("三节点链 → 单链且顺序为旧→新",
     {"dps": [_dp("DP-0", "rejected", 1), _dp("DP-1", "rejected", 2, "DP-0"),
              _dp("DP-2", "pending", 3, "DP-1")], "dpIndex": 0},
     (False, "C4", None, None), [["DP-0", "DP-1", "DP-2"]]),
    # 注意：多节点环里 dp 必然已有后继，C4（防分叉）检查先于 C5（环检测）→ 实际落到 C4。
    # 即 buildSuccessorShell 的 C5 分支仅自引用场景可达（防御性代码），见 rounds/4/RESULTS.md。
    ("环 A→B→A：roots 为空、chains 为空；对 dp 建链由 C4 拦截（C5 不可达）",
     {"dps": [_dp("DP-a", "rejected", 1, supersedes="DP-b"),
              _dp("DP-b", "rejected", 2, supersedes="DP-a")], "dpIndex": 0},
     (False, "C4", None, None), []),
]


def test_spec_anchors():
    """④ 规格直译锚点：期望值手工写死，防 oracle 与 JS 一起错。"""
    if not NODE_BIN:
        pytest.skip("未找到 node 可执行文件（设 WORKBUDDY_NODE 或加入 PATH）")
    cases = [{"kind": "anchor-%d" % i, "dps": a[1]["dps"], "dpIndex": a[1]["dpIndex"]}
             for i, a in enumerate(ANCHORS)]
    proc = subprocess.run(
        [NODE_BIN, str(RUNNER)], input=json.dumps(cases),
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        pytest.fail("node runner 失败: " + proc.stderr)
    js_rows = json.loads(proc.stdout)
    py_rows = [run_case(c) for c in cases]

    for (desc, _case, (ok, code, sid, attempt), exp_chains), py, js in zip(ANCHORS, py_rows, js_rows):
        for end, row in (("py", py), ("js", js)):
            s = row["successor"]
            assert s["ok"] is ok, f"[{end}] {desc}：ok={s['ok']}，期望 {ok}"
            assert s["code"] == code, f"[{end}] {desc}：code={s['code']}，期望 {code}"
            if ok:
                assert s["successor"]["id"] == sid, f"[{end}] {desc}：id={s['successor']['id']}"
                assert s["successor"]["attempt"] == attempt, f"[{end}] {desc}：attempt 不符"
            if exp_chains is not None:
                assert row["resolve"]["chains"] == exp_chains, (
                    f"[{end}] {desc}：chains={row['resolve']['chains']}，期望 {exp_chains}")
        assert py == js, f"{desc}：双端不一致 py={py} js={js}"
