"""
test_dp_chain_oracle_cross.py — 决策链函数「三方交叉验证」常驻测试（Round 7 / 假设池 #9）

背景：Round 5 的 oracle（`tests/dp_chain_oracle.py`）由我按规格实现，存在"同一作者
按同一份规格写成、可能共同误解规格"的残留风险（Round 6 审查 P2-3）。故由**独立会话**
的第二实现者只依据《决策点规格定义》第四章 + 函数契约重写一版
（`tests/dp_chain_oracle_v2.py`，隔离纪律：未读任何实现代码）。

三方：
  v1  = tests/dp_chain_oracle.py      （Round 5 参考实现）
  v2  = tests/dp_chain_oracle_v2.py   （独立实现，2026-08-31）
  JS  = app/js/dp-core.js（经 tests/dp_chain_runner.js）

断言：
  ① v1 ≡ v2（纯 Python，无 node 也跑——交叉验证的核心，成本极低）
  ② v2 ≡ JS（两版参考实现都与生产实现一致）
  ③ 裁决锚点：重复 id 场景（`dup_id`）三方一致且为 OK 路径（冻结 2026-08-31 裁决）
  ④ 每个形状 kind 至少触发一次

运行：python -m pytest tests/test_dp_chain_vs_oracle.py tests/test_dp_chain_oracle_cross.py -q
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
import dp_chain_oracle as v1  # noqa: E402
import dp_chain_oracle_v2 as v2  # noqa: E402

SEED = 20260830
COUNT = 300
RUNNER = Path(__file__).resolve().parent / "dp_chain_runner.js"
NODE_BIN = find_node()


def _cases():
    rng = random.Random(SEED)
    cases = []
    for _ in range(COUNT):
        kind = rng.choice(SHAPE_KINDS)
        case = gen_shape(rng, kind)
        case["kind"] = kind
        cases.append(case)
    return cases


CASES = _cases()
R1 = [v1.run_case(c) for c in CASES]
R2 = [v2.run_case(c) for c in CASES]


def _js_rows():
    if not NODE_BIN:
        pytest.skip("未找到 node 可执行文件（设 WORKBUDDY_NODE 或加入 PATH）")
    proc = subprocess.run(
        [NODE_BIN, str(RUNNER)], input=json.dumps(CASES),
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        pytest.fail("node runner 失败: " + proc.stderr)
    return json.loads(proc.stdout)


def test_two_independent_oracles_agree():
    """① v1 ≡ v2：两份独立实现必须逐字段一致（交叉验证核心，无需 node）。"""
    bad = [i for i in range(COUNT) if R1[i] != R2[i]]
    assert not bad, (
        f"两份独立 oracle 分歧 {len(bad)} 例（N={COUNT}）："
        f"首例 #{bad[0]} kind={CASES[bad[0]]['kind']}\n"
        f"  v1={json.dumps(R1[bad[0]], ensure_ascii=False)}\n"
        f"  v2={json.dumps(R2[bad[0]], ensure_ascii=False)}"
    )


def test_second_oracle_agrees_with_js():
    """② v2 ≡ JS：独立实现也必须与生产实现一致（v1 ≡ JS 由 test_dp_chain_vs_oracle 覆盖）。"""
    js = _js_rows()
    bad = [i for i in range(COUNT) if R2[i] != js[i]]
    assert not bad, (
        f"v2 与 JS 分歧 {len(bad)} 例（N={COUNT}）："
        f"首例 #{bad[0]} kind={CASES[bad[0]]['kind']}\n"
        f"  v2={json.dumps(R2[bad[0]], ensure_ascii=False)}\n"
        f"  js={json.dumps(js[bad[0]], ensure_ascii=False)}"
    )


def test_adjudicated_dup_id_anchor():
    """③ 裁决锚点：重复 id 场景三方一致，且为 OK 路径（冻结 2026-08-31 裁决）。

    分歧史：v2 初版按"对象同一性"排除自身，v1/JS 按 **id** 排除 → 37/1000 分歧。
    规格 4.2 规则 3（"同一 DP 只能被一个后继取代"）在重复 id 时无定义，
    裁决对齐生产契约（id 语义）。若将来改判，本锚点必须先改。
    """
    dps = [{"id": "DP-a", "status": "rejected", "attempt": 1, "name": "DP DP-a",
            "phase": "inMethod", "trigger": "t", "riskLevel": "P1",
            "conclusion": "x", "evidence": [], "reasoning": "y", "risks": []},
           {"id": "DP-a", "status": "pending", "attempt": 2, "supersedes": "DP-a",
            "name": "DP DP-a", "phase": "inMethod", "trigger": "t", "riskLevel": "P1",
            "conclusion": "x", "evidence": [], "reasoning": "y", "risks": []}]
    case = {"kind": "dup_id", "dps": dps, "dpIndex": 0}

    r1, r2 = v1.run_case(case), v2.run_case(case)
    assert r1["successor"]["ok"] is True and r2["successor"]["ok"] is True, (
        f"重复 id 场景应为 OK 路径（按 id 排除自身）：v1={r1['successor']} v2={r2['successor']}"
    )
    assert r1["successor"]["successor"]["id"] == "DP-a-2"
    assert r1 == r2

    if NODE_BIN:
        proc = subprocess.run([NODE_BIN, str(RUNNER)], input=json.dumps([case]),
                              capture_output=True, text=True, timeout=60)
        js = json.loads(proc.stdout)[0]
        assert js["successor"]["ok"] is True, f"JS 端偏离裁决锚点：{js['successor']}"
        assert r2 == js


def test_every_shape_kind_triggered():
    """④ 语料自检：每个形状 kind 至少触发一次。"""
    seen = {c["kind"] for c in CASES}
    missing = [k for k in SHAPE_KINDS if k not in seen]
    assert not missing, f"生成器缺口：以下形状零触发 {missing}"
