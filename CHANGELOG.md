# Changelog — 房地产估价 JSON Schema

所有版本变更均遵循 [Semantic Versioning](https://semver.org/) 原则（大版本不兼容，次版本兼容扩展）。

---

## [1.2] — 2026-08-14

### 新增（兼容 v1.1，全部可选）

| 字段 | 类型 | 说明 |
|------|------|------|
| `adjustments.locationDetails` | `array` ($ref: factorDetail) | 区位状况修正子项明细（12 项，100 基准指数：100=相同，>100=优，<100=劣），保留 Excel 子项粒度 |
| `adjustments.physicalDetails` | `array` ($ref: factorDetail) | 实物状况修正子项明细（8 项） |
| `adjustments.interestDetails` | `array` ($ref: factorDetail) | 权益状况修正子项明细（5 项） |
| `calculationChain` | `object` | 计算链：提取自 Excel 模板的公式逻辑（8 节点），每个节点描述一个可从 Schema 字段重建为 Excel 公式的计算步骤 |

- 新增 `$defs.factorDetail`：`required: [name, factor]`，`additionalProperties: false`
- 新增 `$defs.calculationNode`：`required: [id, formula, refs, description]`
- 配套脚本：`scripts/extract_calculation_chain.py`（Excel → JSON 计算链）、`scripts/rebuild_excel_formula.py`（JSON 计算链 → Excel 公式，cells/values 双模式）

### 变更

| 字段 | 旧约束 | 新约束 | 原因 |
|------|--------|--------|------|
| `schemaVersion` | `pattern: "^1\\.1$"` | `pattern: "^1\\.2$"` | 版本号升级 |
| 顶层系数合并口径 | （无明确说明） | 偏差加总法 `100/(100+Σ(factor-100))` | 与 Excel 模板实际算法一致：`100/(SUM(子项)-（n-1)*100)`，非连乘法 |

### 迁移

- 运行 `python scripts/migrate_schema.py --input <file.json>` 自动将 v1.1 升级为 v1.2（仅更新版本号）
- 子项明细与计算链为增强字段，无法从 v1.1 数据自动推断（需 Excel 子项粒度），由用户按需补充

---

## [1.1] — 2026-08-13

### 新增（兼容 v1.0，全部可选）

| 字段 | 类型 | 说明 |
|------|------|------|
| `valuation.estimatedDate` | `string` (date format) | 预计成交日期，适用于抵押估价等需要预测成交日的场景 |
| `result.calculationMode` | `enum` | 结果确定方式：`weightedAverage` / `arithmeticMean` / `primaryMethodDominant` / `expertJudgment`。当 `determinationMethod` 已明确时自动推断 |
| `crossMethodNotes` | `string` | 跨方法综合讨论笔记，对应报告第 7.0.15 节文字内容 |

### 变更

| 字段 | 旧约束 | 新约束 | 原因 |
|------|--------|--------|------|
| `schemaVersion` | `const: "1.0"` | `pattern: "^1\\.1$"` | 解锁版本号约束，支持未来升级（v1.0 历史数据仍有效） |

### 迁移

- 运行 `python scripts/migrate_schema.py --input <file.json>` 自动补全 v1.1 新增字段默认值
- v1.0 数据可直接用 v1.1 schema 验证（新增字段均为 optional）

---

## [1.0] — 2026-08-11（对抗式审查固化版）

### 首次公开版本

- JSON Schema draft 2020-12，394 行
- 七大顶层字段：`schemaVersion` / `project` / `property` / `valuation` / `methods` / `result` / `crossMethodConsistency`
- 四方法嵌套对象（comps / income / cost / hypotheticalDev），各含红线检查数组
- 对抗式审查加固 6 处约束：
  - `methods.minProperties: 1` + `additionalProperties: false`
  - `result.weightSum.const: 1.0`
  - `comps.comparableInstances.minItems: 3`
  - 4 方法各加 `redLineChecks.minItems: 1`
  - `project` / `property` / `valuation` / `result` 各加 `additionalProperties: false`
- 验证脚本 `scripts/validate_appraisal_json.py`：完整对象 / 单方法片段 / 降级模式三种入口
- 测试覆盖：88 pytest 用例（含 10 个对抗测试）

### 配套更新

| 变更 | 说明 |
|------|------|
| 根目录 schema 升级 | `schema/appraisal-result.schema.json` 从 v1.0 (const "1.0") 升级为 v1.1 (pattern "^1.1$")，与 `v1.1/` 子目录内容一致 |
| 示例文件升级 | `schema/example-武汉洪山住宅.json` schemaVersion → "1.1" |
| 测试 fixture 升级 | `tests/fixtures/degradation_natural_language.json` schemaVersion → "1.1" |
| Excel 模板使用说明 | `outputs/房地产评估明细表-计算模板.xlsx` 新增「使用说明」sheet（首位），含 sheet 目录、公式逻辑、使用流程、注意事项 |
| 模糊化规则配置化 | `scripts/anonymize_rules.yaml` 独立配置文件，`anonymize_template.py` 改为 YAML 驱动 |

---

## 迁移路径

```
v1.0 (2026-08-11) ──▶ v1.1 (2026-08-13) ──▶ v1.2 (2026-08-14)
```

迁移命令：
```bash
python scripts/migrate_schema.py --input schema/example-武汉洪山住宅.json --output example-v1.1.json
```
