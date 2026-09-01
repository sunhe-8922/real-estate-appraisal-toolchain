"""
test_dp_action_oracle_cross.py — 决策动作「三方交叉验证」常驻测试（Round 7 / 假设池复用）

背景：动作侧 oracle v1（`tests/dp_action_oracle.py`）由单一实现者按规格写成，
存在"同一作者按同一份规格共同误解"的残留风险（同 Round 6 审查 P2-3）。
故由**独立会话**的第二实现者只依据《决策点规格定义》§1.3/§4.3 + 函数契约重写
（`tests/dp_action_oracle_v2.py`，隔离纪律：未读任何实现代码，2026-09-01）。

三方：
  v1  = tests/dp_action_oracle.py      （Round 7 参考实现）
  v2  = tests/dp_action_oracle_v2.py   （独立实现，2026-09-01）
  JS  = app/js/dp-core.js（经 tests/dp_action_runner.js）

断言：
  ① v1 ≡ v2（纯 Python，无 node 也跑——交叉验证核心）
  ② v2 ≡ JS（v1 ≡ JS 由 test_dp_action_vs_oracle.py + dp_action_diff.py 覆盖）
  ③ 裁决锚点 ×2（冻结 2026-09-01 D-015 裁决，改判须先改本锚点）：
     a) list 形态 dp → E_NOT_PENDING（JS typeof 数组=object，放行进状态检查）
     b) modifications=null → 通过且为 "null"（生产实现无 null 排除守卫，与 comment 不对称）
  ④ 每个 kind 至少触发一次

运行：python -m pytest tests/test_dp_action_vs_oracle.py tests/test_dp_action_oracle_cross.py -q
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from dp_action_shapes import ACTION_KINDS, gen_action_case  # noqa: E402
from diff_chain_generator import find_node  # noqa: E402
import dp_action_oracle as v1  # noqa: E402
import dp_action_oracle_v2 as v2  # noqa: E402

SEED = 20260901
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
    """② v2 ≡ JS：独立实现也必须与生产实现一致。"""
    js = _js_rows()
    bad = [i for i in range(COUNT) if R2[i] != js[i]]
    assert not bad, (
        f"v2 与 JS 分歧 {len(bad)} 例（N={COUNT}）："
        f"首例 #{bad[0]} kind={CASES[bad[0]]['kind']}\n"
        f"  v2={json.dumps(R2[bad[0]], ensure_ascii=False)}\n"
        f"  js={json.dumps(js[bad[0]], ensure_ascii=False)}"
    )


def test_adjudicated_list_dp_anchor():
    """③a 裁决锚点：list 形态 dp 落 E_NOT_PENDING 而非 E_DP_NOT_OBJECT。

    分歧史：v2 初版仅 dict 算对象 → list 落 E_DP_NOT_OBJECT；
    JS `!dp || typeof dp !== "object"` 中数组也是 object → 放行进状态检查，
    无 status → E_NOT_PENDING。规格未定义"对象"边界，裁决对齐生产契约（69/1000 分歧之一）。
    """
    case = {"kind": "dp_list_anchor", "dp": [{"id": "DP-comp"}], "action": "approved",
            "status": "pending"}
    r1, r2 = v1.run_case(case), v2.run_case(case)
    for name, r in (("v1", r1), ("v2", r2)):
        assert r["apply"]["code"] == "E_NOT_PENDING", (
            f"{name} 偏离裁决锚点（list dp 应为 E_NOT_PENDING）：{r['apply']}"
        )
    if NODE_BIN:
        proc = subprocess.run([NODE_BIN, str(RUNNER)], input=json.dumps([case]),
                              capture_output=True, text=True, timeout=60)
        js = json.loads(proc.stdout)[0]
        assert js["apply"]["code"] == "E_NOT_PENDING", f"JS 端偏离裁决锚点：{js['apply']}"
        assert r2 == js


def test_adjudicated_null_mods_anchor():
    """③b 裁决锚点：modifications=null 渲染为 "null" 非空 → 通过。

    分歧史：v2 初版把 None 视作缺失 → 拒绝；生产实现对 modifications 无 null
    排除守卫（与 comment 的 `!== null` 守卫不对称），String(null)="null" →
    通过且 modifications="null"。裁决对齐生产契约（69/1000 分歧之一）。
    """
    case = {"kind": "mods_null_anchor",
            "dp": {"id": "DP-comp", "status": "pending"},
            "action": "modified", "status": "pending",
            "opts": {"modifications": None, "comment": "调整"}}
    r1, r2 = v1.run_case(case), v2.run_case(case)
    for name, r in (("v1", r1), ("v2", r2)):
        assert r["apply"]["ok"] is True, f"{name} 偏离裁决锚点（mods=null 应通过）：{r['apply']}"
        assert r["apply"]["dp"]["humanDecision"]["modifications"] == "null"
    if NODE_BIN:
        proc = subprocess.run([NODE_BIN, str(RUNNER)], input=json.dumps([case]),
                              capture_output=True, text=True, timeout=60)
        js = json.loads(proc.stdout)[0]
        assert js["apply"]["ok"] is True, f"JS 端偏离裁决锚点：{js['apply']}"
        assert r2 == js


def test_every_action_kind_triggered():
    """④ 语料自检：每个动作 kind 至少触发一次。"""
    seen = {c["kind"] for c in CASES}
    missing = [k for k in ACTION_KINDS if k not in seen]
    assert not missing, f"生成器缺口：以下 kind 零触发 {missing}"
