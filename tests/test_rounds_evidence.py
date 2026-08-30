"""
test_rounds_evidence.py — 迭代存档（rounds/）证据机制常态化自查

来源：Round 4 审查 P1-1——`rounds/1/diff_result.json` 被下一轮重跑**原地覆盖**，
93 例基线证据永久丢失（git 历史两次提交都是 rate=1.0，原始档案从未留痕）。
当时订的规则写在 `rounds/README.md`，但规则只在"有人记得看"时才生效。
本测试把规则变成常驻断言，P1-1 复发即红灯。

检查项：
  ① 规则文档存在且仍含命名规则（防规则被无声删改）
  ② 差分存档文件名符合 `diff_result_roundN[_suffix].json`（历史遗留白名单除外）
  ③ 存档所在轮目录号 == 文件名里的轮次号（防跨轮乱放）
  ④ 存档可解析且含关键字段（防截断/半成品）
  ⑤ 每个轮目录都有 RESULTS.md（存档完整性）
  ⑥ 无 tmp_* 残留（中间探测脚本用后即删）

运行：python -m pytest tests/test_rounds_evidence.py -q
"""
import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROUNDS = PROJECT_ROOT / "rounds"

# 历史遗留：P1-1 事故本体——被原地覆盖过的 Round 1 档案，保留作为事故证据，不再改动
LEGACY_ALLOWLIST = {"rounds/1/diff_result.json"}
NAME_RE = re.compile(r"^diff_result_round(\d+)(_[a-z0-9]+)?\.json$")
REQUIRED_FIELDS = ("seed", "count", "rate", "mismatch_count")
RULE_MARKERS = ("diff_result_roundN.json", "禁止原地覆盖")


def _rel(p: Path) -> str:
    return p.relative_to(PROJECT_ROOT).as_posix()


def _archives():
    if not ROUNDS.is_dir():
        return []
    return sorted(ROUNDS.glob("**/*.json"))


def test_archive_naming_rule_documented():
    """① 命名规则文档在位（规则本身也要被度量）。"""
    readme = ROUNDS / "README.md"
    assert readme.is_file(), "缺 rounds/README.md（存档命名规则无处可查）"
    text = readme.read_text(encoding="utf-8")
    missing = [m for m in RULE_MARKERS if m not in text]
    assert not missing, f"rounds/README.md 缺规则标记 {missing}——规则被删改或改写走了样"


def test_archive_filenames_follow_rule():
    """② 存档文件名符合按轮独立命名（白名单为 P1-1 事故遗留）。"""
    bad = []
    for p in _archives():
        rel = _rel(p)
        if rel in LEGACY_ALLOWLIST:
            continue
        if not NAME_RE.match(p.name):
            bad.append(rel)
    assert not bad, (
        f"存档命名违规（应为 diff_result_roundN[_suffix].json）：{bad}\n"
        f"——原地覆盖是 P1-1 的根因，见 rounds/README.md"
    )


def test_archive_round_number_matches_directory():
    """③ 存档轮次号 == 所在目录轮次号（防跨轮乱放）。"""
    bad = []
    for p in _archives():
        if _rel(p) in LEGACY_ALLOWLIST:
            continue
        m = NAME_RE.match(p.name)
        if not m or not re.fullmatch(r"\d+", p.parent.name):
            continue
        if int(m.group(1)) != int(p.parent.name):
            bad.append(_rel(p))
    assert not bad, f"存档轮次号与目录不一致：{bad}"


def test_archives_are_complete_and_parseable():
    """④ 存档可解析且含关键字段（防截断/半成品混入）。"""
    bad = []
    for p in _archives():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            bad.append("%s（解析失败: %s）" % (_rel(p), e))
            continue
        missing = [f for f in REQUIRED_FIELDS if f not in data]
        if missing:
            bad.append("%s（缺字段 %s）" % (_rel(p), missing))
    assert not bad, f"存档不完整：{bad}"


def test_every_round_has_results():
    """⑤ 每个轮目录都有 RESULTS.md（存档完整性：有结果才有结论）。"""
    if not ROUNDS.is_dir():
        pytest.skip("无 rounds/ 目录")
    rounds = [d for d in ROUNDS.iterdir() if d.is_dir() and re.fullmatch(r"\d+", d.name)]
    missing = [d.name for d in rounds if not (d / "RESULTS.md").is_file()]
    assert not missing, f"以下轮次缺 RESULTS.md：{sorted(missing)}"


def test_no_tmp_leftovers():
    """⑥ 无 tmp_* 残留（中间探测脚本用后即删，不入库）。"""
    if not ROUNDS.is_dir():
        pytest.skip("无 rounds/ 目录")
    leftovers = [_rel(p) for p in ROUNDS.rglob("tmp_*")]
    assert not leftovers, f"rounds/ 下有 tmp_* 残留：{leftovers}（验证后应删除）"
