# Changelog — 房地产估价 JSON Schema

所有版本变更均遵循 [Semantic Versioning](https://semver.org/) 原则（大版本不兼容，次版本兼容扩展）。

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

---

## 迁移路径

```
v1.0 (2026-08-11) ──▶ v1.1 (2026-08-13)
```

迁移命令：
```bash
python scripts/migrate_schema.py --input schema/example-武汉洪山住宅.json --output example-v1.1.json
```
