"""
对抗测试（第二轮，v1.2）— 固化 2026-08-15 对抗式审查发现的安全攻击。

参考：outputs/对抗式审查报告_2026-08-15.md

核心：rebuild_excel_formula.py 曾用裸 eval + 空 __builtins__ 求值 calculationChain，
实测可经 object 子类遍历逃逸并执行任意系统命令（P0）。
修复为 AST 白名单求值器 safe_eval。本文件确保逃逸不可复活。
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from rebuild_excel_formula import safe_eval, rebuild_values
from migrate_schema import migrate


# ════════════════════════════════════════════════════════
# safe_eval：恶意结构必须抛 ValueError（绝不执行）
# ════════════════════════════════════════════════════════
@pytest.mark.parametrize("evil", [
    # 子类遍历逃逸（第二轮审查实测成功的 payload）
    "[c for c in ().__class__.__bases__[0].__subclasses__() if c.__name__ == '_wrap_close']",
    # 内置函数恢复
    "__import__('os').system('id')",
    # 文件读写
    "open('secret.txt').read()",
    # 布尔运算（数据值注入载体的最小形态）
    "1 or __import__('os')",
    # 属性访问
    "(1).__class__",
    # 下标访问
    "[1][0]",
    # 字符串常量
    "'not a number'",
    # lambda
    "(lambda: 1)()",
])
def test_safe_eval_rejects_malicious(evil):
    with pytest.raises((ValueError, SyntaxError)):
        safe_eval(evil)


def test_safe_eval_accepts_legit_formulas():
    """合法公式必须正常求值（防止修复过度拦截）。"""
    assert safe_eval("25000*0.980392") == pytest.approx(24509.8)
    assert safe_eval("round(25773.456, 0)") == 25773
    assert safe_eval("round(25000, -1)") == 25000
    assert safe_eval("sum([102, 100, 100])") == 302
    assert safe_eval("SUM([97, 100])") == 197
    assert safe_eval("2**3") == 8
    assert safe_eval("-5 + 3") == -2


# ════════════════════════════════════════════════════════
# 端到端：恶意 calculationChain 不能产生副作用
# ════════════════════════════════════════════════════════
def test_malicious_chain_no_side_effect(tmp_path):
    marker = tmp_path / "pwned.txt"
    chain = {
        "version": "1.2",
        "nodes": [{
            "id": "pwn",
            "formula": (
                "[c for c in ().__class__.__bases__[0].__subclasses__() "
                "if c.__name__ == '_wrap_close'][0].__init__.__globals__"
                f"['system']('echo x > {marker.as_posix()}')"
            ),
            "refs": {},
            "target": "schemaVersion",
            "description": "逃逸测试",
        }],
    }
    results = rebuild_values(chain, {"schemaVersion": "1.2"})
    assert results[0]["status"] == "SKIP"  # 求值被拒，不执行
    assert not marker.exists(), "沙箱逃逸：命令被执行了"


def test_data_value_injection_rejected(tmp_path):
    """refs 指向被注入代码的字符串字段时，注入值不得被执行。"""
    marker = tmp_path / "pwned3.txt"
    data = {"project": {"name": f"__import__('os').system('echo x > {marker.as_posix()}') or 1"}}
    chain = {
        "version": "1.2",
        "nodes": [{
            "id": "pwn.data",
            "formula": "{{evil}}",
            "refs": {"evil": "project.name"},
            "target": "schemaVersion",
            "description": "数据值注入",
        }],
    }
    results = rebuild_values(chain, data)
    assert results[0]["status"] == "SKIP"
    assert not marker.exists(), "数据值注入成功：命令被执行了"


# ════════════════════════════════════════════════════════
# migrate：result=None 时推断值必须写回（第二轮审查发现）
# ════════════════════════════════════════════════════════
def test_migrate_result_none_writes_back():
    data = {"schemaVersion": "1.0", "result": None}
    migrated, notes = migrate(data, "1.0", "1.1")
    assert migrated["result"] is not None, "result=None 时 calculationMode 推断值丢失"
    assert migrated["result"].get("calculationMode") == "expertJudgment"


def test_migrate_result_missing_writes_back():
    migrated, _ = migrate({"schemaVersion": "1.0"}, "1.0", "1.1")
    assert migrated.get("result", {}).get("calculationMode") == "expertJudgment"
