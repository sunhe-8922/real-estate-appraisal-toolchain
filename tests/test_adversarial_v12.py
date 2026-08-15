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
# safe_eval：扩展函数白名单（IF/MAX/MIN/ABS/AVERAGE/POWER/INT/SQRT/AND/OR）
# ════════════════════════════════════════════════════════
class TestSafeEvalExtendedFuncs:
    def test_max_min(self):
        assert safe_eval("MAX(1, 5, 3)") == 5
        assert safe_eval("MIN(1, 5, 3)") == 1

    def test_abs(self):
        assert safe_eval("ABS(-42)") == 42
        assert safe_eval("ABS(42)") == 42

    def test_average(self):
        assert safe_eval("AVERAGE(10, 20, 30)") == pytest.approx(20.0)

    def test_power(self):
        assert safe_eval("POWER(2, 10)") == 1024

    def test_int(self):
        assert safe_eval("INT(3.7)") == 3
        assert safe_eval("INT(-3.7)") == -3

    def test_sqrt(self):
        assert safe_eval("SQRT(144)") == pytest.approx(12.0)

    def test_and_or(self):
        assert safe_eval("AND(1, 1, 1)") is True
        assert safe_eval("AND(1, 0)") is False
        assert safe_eval("OR(0, 0, 1)") is True
        assert safe_eval("OR(0, 0)") is False

    def test_round_still_works(self):
        assert safe_eval("ROUND(3.14159, 2)") == 3.14
        assert safe_eval("round(3.14159, 2)") == 3.14


# ════════════════════════════════════════════════════════
# safe_eval：IF 惰性求值
# ════════════════════════════════════════════════════════
class TestSafeEvalIf:
    def test_if_true_branch(self):
        assert safe_eval("IF(1 > 0, 100, 200)") == 100

    def test_if_false_branch(self):
        assert safe_eval("IF(1 < 0, 100, 200)") == 200

    def test_if_no_third_arg(self):
        assert safe_eval("IF(0, 100)") is False

    def test_if_nested(self):
        assert safe_eval("IF(1, IF(0, 10, 20), 30)") == 20

    def test_if_lazy_no_side_effect(self):
        """未取分支不得被求值（惰性语义）。"""
        # 未取分支含除零——若被求值会抛 ZeroDivisionError
        result = safe_eval("IF(1, 42, 1 / 0)")
        assert result == 42

    def test_if_with_comparison_ops(self):
        assert safe_eval("IF(5 >= 5, 1, 0)") == 1
        assert safe_eval("IF(5 != 5, 1, 0)") == 0
        assert safe_eval("IF(5 <= 4, 1, 0)") == 0


# ════════════════════════════════════════════════════════
# safe_eval：比较运算符
# ════════════════════════════════════════════════════════
class TestSafeEvalComparisons:
    def test_eq(self):
        assert safe_eval("1 == 1") is True
        assert safe_eval("1 == 2") is False

    def test_ne(self):
        assert safe_eval("1 != 2") is True

    def test_lt_le(self):
        assert safe_eval("3 < 5") is True
        assert safe_eval("5 <= 5") is True

    def test_gt_ge(self):
        assert safe_eval("5 > 3") is True
        assert safe_eval("5 >= 5") is True

    def test_chained_comparison_rejected(self):
        with pytest.raises(ValueError, match="链式比较"):
            safe_eval("1 < 2 < 3")


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
