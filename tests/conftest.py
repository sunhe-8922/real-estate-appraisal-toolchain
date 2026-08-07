"""Shared fixtures — ensures .xlsx templates are generated before testing."""
import subprocess
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TEMPLATES_DIR = PROJECT_ROOT / "outputs" / "templates"
PYTHON = sys.executable

TEMPLATE_MAP = {
    "comps": (SCRIPTS_DIR / "gen_comps_template.py", TEMPLATES_DIR / "比较法测算_模板.xlsx"),
    "income": (SCRIPTS_DIR / "gen_income_template.py", TEMPLATES_DIR / "收益法测算_模板.xlsx"),
    "cost": (SCRIPTS_DIR / "gen_cost_template.py", TEMPLATES_DIR / "成本法测算_模板.xlsx"),
    "hypo_dev": (SCRIPTS_DIR / "gen_hypo_dev_template.py", TEMPLATES_DIR / "假设开发法测算_模板.xlsx"),
}


def _run_gen_script(script_path: Path):
    result = subprocess.run(
        [PYTHON, str(script_path)],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=30,
    )
    if result.returncode != 0:
        pytest.fail(f"{script_path.name} failed: {result.stderr}")


@pytest.fixture(scope="session")
def _all_templates_generated():
    for script, _ in TEMPLATE_MAP.values():
        _run_gen_script(script)


def _load_wb(template_name, _all_templates_generated):
    _, xlsx_path = TEMPLATE_MAP[template_name]
    return load_workbook(str(xlsx_path), data_only=False)


@pytest.fixture
def comps_wb(_all_templates_generated):
    wb = _load_wb("comps", True)
    yield wb
    wb.close()


@pytest.fixture
def income_wb(_all_templates_generated):
    wb = _load_wb("income", True)
    yield wb
    wb.close()


@pytest.fixture
def cost_wb(_all_templates_generated):
    wb = _load_wb("cost", True)
    yield wb
    wb.close()


@pytest.fixture
def hypo_dev_wb(_all_templates_generated):
    wb = _load_wb("hypo_dev", True)
    yield wb
    wb.close()


ALL_WBS = {
    "comps": "comps_wb",
    "income": "income_wb",
    "cost": "cost_wb",
    "hypo_dev": "hypo_dev_wb",
}

SHEET_NAMES = {
    "comps": ["可比实例数据", "比较价值汇总"],
    "income": ["净收益测算", "收益价值"],
    "cost": ["重置成本", "折旧测算", "成本价值"],
    "hypo_dev": ["假设开发法", "现金流时间线"],
}
