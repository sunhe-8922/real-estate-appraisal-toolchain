"""
test_example_arithmetic.py — 示例/工程 JSON 数值自洽常驻回归（Round 8）

背景（为什么需要这个文件）：
  Round 7 收尾审查查出 P1-1——`calculationChain` 末节点公式 `ROUND(area×unit)`
  算出的值与权威总价不符（差 25 元）。该缺陷**穿过当时全部 348 个测试**：
  既有测试只证明"双端实现一致"和"schema 合法"，从不验证"数值自洽"。
  审查用的临时脚本当时被转正为 `scripts/verify_example_arithmetic.py`，
  但它**没有接入回归套件**——改示例数字仍然不会让任何测试变红。

  本文件把数值自洽从"人工审查发现"变成"CI 门禁拦截"。

设计要点：
  1. 自动发现示例：schema/example-*.json + outputs/ 下的工程 JSON，
     新增示例无需改本文件即被纳入门禁（防"新示例绕过校验"）。
  2. 已知缺陷登记制：已登记缺陷不阻塞 CI，但
     - 出现**未登记**的新缺陷 → 立即失败；
     - 已登记缺陷**被修复** → 立即失败，提醒从 KNOWN_DEFECTS 移除（防登记腐烂）。
     这比 xfail 严格：xfail 会掩盖"修好一半"和"登记过期"两种腐烂。
  3. 判定依赖校验器的 `--json-out`（机器可读），不解析人类可读 stdout。

运行：python -m pytest tests/test_example_arithmetic.py -q
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VERIFIER = ROOT / "scripts" / "verify_example_arithmetic.py"
TMP = ROOT / "tests" / "_tmp_verify_out.json"

# 已登记的既有缺陷（Round 8 B2 实测发现，待修复后从本表移除）
# 格式：{相对路径: [(FAIL 标签, 说明), ...]}
KNOWN_DEFECTS = {
    "schema/example-武汉洪山住宅.json": [
        ("chain 节点 income.value 公式不可求值",
         "P1-2A: chain 公式用报酬资本化法（含 growth/holdingPeriod/G23），"
         "数据实为直接资本化法 total=ROUND(48124/0.015)=3208267；公式与数据口径不符"),
        ("chain 末节点回乘闭合 result.totalValue",
         "P1-2B: 末节点 ROUND(area×unit)=3271738 ≠ 权威总价 3271720（R7 P1-1 同形态，"
         "该示例未随整改同步）；且 result.totalValue 与 result.finalTotalValue 重复 target"),
    ],
}


def _discover_examples() -> list[Path]:
    found = sorted(ROOT.glob("schema/example-*.json"))
    # outputs/ 下的工程 JSON：与 schema 示例同形态（含 property/methods/result）
    for p in sorted((ROOT / "outputs").glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(d, dict) and {"property", "methods", "result"} <= set(d):
            found.append(p)
    return found


EXAMPLES = _discover_examples()


def _run(path: Path) -> tuple[int, list[str], list[str]]:
    TMP.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, str(VERIFIER), str(path), "--json-out", str(TMP)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if TMP.is_file():
        data = json.loads(TMP.read_text(encoding="utf-8"))
        TMP.unlink(missing_ok=True)
        return proc.returncode, data.get("failed", []), data.get("skipped", [])
    # 校验器自身崩溃：stdout/stderr 作为诊断信息回传
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, [f"<校验器崩溃> {out.strip().splitlines()[-1]}"], []


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_example_arithmetic_is_self_consistent(path: Path):
    """示例/工程 JSON 的数值必须自洽（总价三级验算 + chain 公式↔target 一致）。"""
    code, failed, _skipped = _run(path)
    rel = path.relative_to(ROOT).as_posix()
    known = [label for label, _note in KNOWN_DEFECTS.get(rel, [])]

    unexpected = [f for f in failed if f not in known]
    assert not unexpected, (
        f"{rel} 数值自洽校验出现**未登记**的缺陷：{unexpected}\n"
        f"  已登记缺陷：{known or '（无）'}\n"
        f"  若为真实新缺陷——修它；若确认为既有缺陷且暂不修——"
        f"在 KNOWN_DEFECTS 中登记并写明编号与原因（不许默默放行）"
    )

    fixed = [k for k in known if k not in failed]
    assert not fixed, (
        f"{rel} 以下已登记缺陷**已不复现**（很可能已被修复）：{fixed}\n"
        f"  请从 tests/test_example_arithmetic.py 的 KNOWN_DEFECTS 中移除，"
        f"否则登记会腐烂成永久免检牌"
    )


def test_examples_discovered():
    """门禁覆盖面自检：至少覆盖 3 个工程 JSON，且发现逻辑没退化成空集。"""
    rels = [p.relative_to(ROOT).as_posix() for p in EXAMPLES]
    assert len(EXAMPLES) >= 3, (
        f"发现的示例/工程 JSON 仅 {len(EXAMPLES)} 个（{rels}）——"
        f"发现逻辑退化会让新示例绕过数值门禁"
    )
    assert any(r.startswith("schema/example-") for r in rels), (
        f"未发现任何 schema 示例：{rels}"
    )


def test_known_defects_entries_are_used():
    """KNOWN_DEFECTS 的键必须是真实存在的文件（防登记了错别字路径，等于没登记）。"""
    missing = [k for k in KNOWN_DEFECTS if not (ROOT / k).is_file()]
    assert not missing, f"KNOWN_DEFECTS 登记了不存在的路径：{missing}"
