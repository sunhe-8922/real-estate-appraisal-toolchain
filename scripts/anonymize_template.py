#!/usr/bin/env python3
"""
房地产评估明细表 → 计算模板模糊化脚本

策略：
1. 保留所有公式、结构、表头、修正系数逻辑
2. 模糊化：委托人/权属人/评估机构/评估人员/地址/楼盘名/学校/价格/URL
3. 输出到 outputs/ 目录

用法：
  python scripts/anonymize_template.py <源文件路径>

注意：TEXT_REPLACEMENTS 中的 key 需根据实际源文件替换。
      本脚本提供框架，具体模糊化规则请按案例填充。
"""

import re
import sys
import openpyxl
from copy import copy
from pathlib import Path

# 默认输出路径
DST = Path(__file__).parent.parent / "outputs" / "房地产评估明细表-计算模板.xlsx"


# ── 模糊化规则 ──────────────────────────────────────────────
# 使用时请将 【真实XXX】 替换为源文件中的实际文本

TEXT_REPLACEMENTS = {
    # 委托人/权属人
    "【真实公司名】投资有限公司": "XX投资有限公司",
    # 评估机构
    "【真实评估机构名】": "XX土地房地产与资产评估有限公司",
    # 评估人员
    "【评估师A姓名】": "评估师A",
    "【评估师B姓名】": "评估师B",
    # 估价对象地址
    "【真实地址】": "XX市XX区XX路XX号XX小区XX栋XX房",
    "【真实楼盘名】": "XX山庄",
    # 可比实例名称
    "【可比实例A名】": "XX苑",
    "【可比实例A名】住宅": "XX苑住宅",
    "【可比实例B名】": "XX湾山庄",
    "【可比实例B名】住宅": "XX湾山庄住宅",
    "【可比实例C完整地址】": "XX市XX路XX山庄XX栋别墅",
    "【可比实例C名】": "XX山庄",
    "【可比实例D名】": "XX居",
    # 学校/公共设施
    "【真实学校名A】": "XX中学",
    "【真实学校名A(校区)】": "XX中学",
    "【真实小学名】": "XX小学",
    "【真实幼儿园A名】": "XX幼儿园",
    "【真实幼儿园B名】": "XX幼儿园",
    "【真实幼儿园C名】": "XX小学及幼儿园",
    "【真实公园名】": "XX森林公园",
    "【真实幼儿园D名】": "XX幼儿园",
    "【真实中学B名】": "XX中学",
    "【真实医院名】": "XX医院",
    "【真实超市A名】": "XX超市",
    "【真实超市B名】": "XX超市",
    "【真实赛车场名】": "XX赛车场",
    "【真实俱乐部名】": "XX俱乐部",
    # 公交站/道路
    "【真实公交站A名】": "XX站",
    "【真实公交站B名】": "XX站",
    "【真实公交站C名】": "XX站",
    "【真实道路名】": "XX大道",
    # 权属证号
    "《【真实城市名】市商品房买卖合同》": "《商品房买卖合同》",
}

# 正则替换（模糊匹配）
REGEX_REPLACEMENTS = [
    # URL 链接 → 删除
    (re.compile(r"https?://[^\s\"]+"), ""),
    # 手机号
    (re.compile(r"1[3-9]\d{9}"), "XXXXXXXXXXX"),
    # 身份证号
    (re.compile(r"\d{17}[\dXx]"), "XXXXXXXXXXXXXXXXXX"),
]

# 数值替换（同量级占位）
# key = (sheet_name, cell_coord) → 替换值
# 使用时根据实际源文件调整
NUMERIC_REPLACEMENTS = {
    # 评估明细表 - 评估单价
    ("评估明细表", "N6"): 38000,
    ("评估明细表", "N7"): 38000,
    # 评估明细表 - 套内面积
    ("评估明细表", "L6"): 540.00,
    ("评估明细表", "M6"): 580.00,
    ("评估明细表", "L7"): 38.00,
    ("评估明细表", "M7"): 40.00,
    # 评估明细表 - 原购买价
    ("评估明细表", "W6"): 38000,
    # 市场价比较法 - 可比实例成交价
    ("市场价比较法", "E4"): 31000,
    ("市场价比较法", "F4"): 30000,
    ("市场价比较法", "G4"): 28000,
    # 市场价比较法 - 可比实例面积
    ("市场价比较法", "E24"): 450.00,
    ("市场价比较法", "F24"): 200.00,
    ("市场价比较法", "G24"): 270.00,
    # 可比案例
    ("可比案例", "G53"): 1100000,
    ("可比案例", "G54"): 1100000,
    ("可比案例", "G55"): 1600000,
    ("可比案例", "G56"): 1600000,
    ("可比案例", "G58"): 2300000,
    ("可比案例", "G59"): 2300000,
}


def anonymize_value(value):
    """对单元格值进行模糊化处理。"""
    if value is None:
        return None

    if isinstance(value, str):
        result = value
        # 跳过公式
        if result.startswith("="):
            return result
        # 精确替换
        for old, new in TEXT_REPLACEMENTS.items():
            result = result.replace(old, new)
        # 正则替换
        for pattern, replacement in REGEX_REPLACEMENTS:
            result = pattern.sub(replacement, result)
        return result if result.strip() else None

    return value


def copy_cell_style(src_cell, dst_cell):
    """复制单元格样式。"""
    if src_cell.has_style:
        dst_cell.font = copy(src_cell.font)
        dst_cell.border = copy(src_cell.border)
        dst_cell.fill = copy(src_cell.fill)
        dst_cell.number_format = src_cell.number_format
        dst_cell.protection = copy(src_cell.protection)
        dst_cell.alignment = copy(src_cell.alignment)


def process_workbook(src_path):
    """处理整个工作簿。"""
    wb = openpyxl.load_workbook(src_path)

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue

                coord = (sheet_name, cell.coordinate)

                # 1. 数值替换（精确单元格定位）
                if coord in NUMERIC_REPLACEMENTS:
                    cell.value = NUMERIC_REPLACEMENTS[coord]
                    continue

                # 2. 文本/正则模糊化
                cell.value = anonymize_value(cell.value)

    # 保存
    DST.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(DST))
    wb.close()
    print(f"✅ 模糊化完成: {DST}")


def verify_anonymization():
    """验证模糊化结果，扫描是否遗漏敏感信息。

    注意：sensitive_patterns 中的关键词需根据实际案例替换。
    """
    wb = openpyxl.load_workbook(str(DST))
    # 通用敏感关键词扫描（按实际案例补充）
    sensitive_patterns = [
        ("投资", "可能的公司名"),
        ("评估有限公司", "可能的机构名"),
        ("https://", "URL链接"),
    ]

    issues = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str):
                    for pattern, desc in sensitive_patterns:
                        if pattern in cell.value:
                            issues.append(
                                f"  ⚠️ {sheet_name}!{cell.coordinate}: 发现{desc} '{pattern}'"
                            )

    wb.close()

    if issues:
        print("⚠️ 以下内容需人工确认：")
        for issue in issues:
            print(issue)
        return False
    else:
        print("✅ 验证通过：未发现明显敏感信息")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/anonymize_template.py <源文件路径>")
        sys.exit(1)
    process_workbook(sys.argv[1])
    print()
    verify_anonymization()
