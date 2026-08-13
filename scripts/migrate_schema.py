#!/usr/bin/env python3
"""
migrate_schema.py — 估价 JSON Schema 版本迁移工具

支持 v1.0 → v1.1 的自动迁移，补充 v1.1 新增的可选字段默认值。

用法:
  # 迁移数据文件
  python migrate_schema.py --input input.json --output output.json

  # 仅预览变更（不写文件）
  python migrate_schema.py --input input.json --preview

  # 查看支持的迁移路径
  python migrate_schema.py --list
"""

import json
import sys
from pathlib import Path

SCHEMA_DIR = Path(__file__).parent.parent / "schema"
MIGRATIONS = {
    "1.0": "1.1",
}


def load_schema(version: str) -> dict:
    path = SCHEMA_DIR / version / "appraisal-result.schema.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def migrate(data: dict, from_version: str, to_version: str) -> tuple[dict, list[str]]:
    """
    将数据从 from_version 迁移到 to_version。
    返回 (migrated_data, notes) ，notes 记录补全了哪些字段。
    同版本迁移直接返回原数据（无变更）。
    """
    if from_version == to_version:
        return data, []
    if from_version == "1.0" and to_version == "1.1":
        return _migrate_1_0_to_1_1(data)
    raise ValueError(f"不支持的迁移路径: {from_version} → {to_version}")


def _migrate_1_0_to_1_1(data: dict) -> tuple[dict, list[str]]:
    notes = []

    # 1. 更新 schemaVersion
    if data.get("schemaVersion") == "1.0":
        data["schemaVersion"] = "1.1"
        notes.append("schemaVersion: 1.0 → 1.1")

    # 2. valuation.estimatedDate — 可选，不自动填充，仅标注
    #    用户需根据实际情况填写

    # 3. result.calculationMode — 可选，根据 determinationMethod 推断默认值
    result = data.get("result") or {}
    det_method = result.get("determinationMethod", "")
    if "calculationMode" not in result:
        if "加权平均" in det_method:
            result["calculationMode"] = "weightedAverage"
            notes.append("result.calculationMode: 推断为 weightedAverage")
        elif "算术平均" in det_method:
            result["calculationMode"] = "arithmeticMean"
            notes.append("result.calculationMode: 推断为 arithmeticMean")
        elif "为主" in det_method:
            result["calculationMode"] = "primaryMethodDominant"
            notes.append("result.calculationMode: 推断为 primaryMethodDominant")
        else:
            result["calculationMode"] = "expertJudgment"
            notes.append("result.calculationMode: 默认 expertJudgment")

    # 4. crossMethodNotes — 可选，不自动填充

    return data, notes


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Schema 版本迁移工具")
    parser.add_argument("--input", required=True, help="输入 JSON 文件路径")
    parser.add_argument("--output", help="输出 JSON 文件路径（默认覆盖输入）")
    parser.add_argument("--preview", action="store_true", help="仅预览，不写文件")
    parser.add_argument("--list", action="store_true", help="列出支持的迁移路径")
    args = parser.parse_args()

    if args.list:
        print("支持的迁移路径:")
        for from_v, to_v in MIGRATIONS.items():
            print(f"  {from_v} → {to_v}")
        return

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    from_version = data.get("schemaVersion", "unknown")
    to_version = MIGRATIONS.get(from_version)

    if to_version is None:
        print(f"错误: 不支持从 {from_version} 迁移。"
              f"已知迁移: {list(MIGRATIONS.keys())}")
        sys.exit(1)

    migrated, notes = migrate(data, from_version, to_version)

    if args.preview:
        print(f"迁移: {from_version} → {to_version}")
        print(f"补全备注 ({len(notes)} 条):")
        for note in notes:
            print(f"  - {note}")
        print("\n预览输出 (前 20 行):")
        print(json.dumps(migrated, ensure_ascii=False, indent=2)[:500])
        return

    out_path = args.output or args.input
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(migrated, f, ensure_ascii=False, indent=2)

    print(f"✅ 迁移完成: {from_version} → {to_version}")
    print(f"📝 补全备注: {len(notes)} 条")
    for note in notes:
        print(f"   - {note}")
    print(f"💾 输出: {out_path}")


if __name__ == "__main__":
    main()
