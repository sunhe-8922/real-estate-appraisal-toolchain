# Changelog — 房地产估价 JSON Schema

所有版本变更均遵循 [Semantic Versioning](https://semver.org/) 原则（大版本不兼容，次版本兼容扩展）。

---

## [1.5] — 2026-08-19（evidenceItem.sourceGrade 信源等级结构化）

### 新增（兼容 v1.4，可选）

| 字段 | 类型 | 说明 |
|------|------|------|
| `evidenceItem.sourceGrade` | `string` enum (T0/T1/T2) | 证据信源等级：T0 官方/一手资料，T1 头部平台交叉验证，T2 仅供参考。与 `comparableInstances[].sourceGrade` 同构。旧数据 source 文本内的 `(T0)` 等标记保留，迁移不自动推断 |

### 语义说明（P2-4）

`calculationChain.version` 为计算链格式版本，独立于顶层 `schemaVersion`（schema 版本）。计算链格式演进频率低于 schema，两者解耦；当前 `calculationChain.version` 恒为 `"1.2"`，不随 schema 升级而改变。

### 配套更新

| 变更 | 说明 |
|------|------|
| 根目录 schema 升级 | `schema/appraisal-result.schema.json` v1.4 → v1.5 |
| 版本化副本 | `schema/v1.5/appraisal-result.schema.json`（root 一致性验证 PASS） |
| 迁移脚本 | `migrate_schema.py` 新增 1.4→1.5 路径（仅更新 schemaVersion，sourceGrade 不自动填充） |
| 测试 helper 去重 | `tests/helpers.py` 新增共享模块（P1-3）：`strip_v12_fields` / `strip_v13_fields` / `make_minimal_decision_point` / `make_comp_decision_point`，消除 migration/v12/v13/v14 四文件重复定义 |
| 前端内嵌数据同步 | `app/js/example-data.js` 同步 v1.5（22/22 evidence 含 sourceGrade），由 `tests/test_example_data_sync.py` 锁定 |

### ⚠️ 发布清单（升级 schema 必读）

升级 schema 版本时必须同步以下四处，否则测试失败或前后端脱节：

1. **根 schema** `schema/appraisal-result.schema.json`（`schemaVersion.pattern` + 字段变更）
2. **版本化副本** `schema/v<N>/appraisal-result.schema.json`（新建）
3. **迁移脚本** `scripts/migrate_schema.py`（MIGRATIONS + 迁移函数）
4. **前端内嵌数据** `app/js/example-data.js`（schemaVersion + decisionPoints，由 `tests/test_example_data_sync.py` 强制）

校验：`python -m pytest tests/test_schema_v15.py tests/test_example_data_sync.py -q`

### 测试

- `tests/test_schema_v15.py`：19 用例（schema 合法性 / sourceGrade 约束 / 向后兼容 / 版本隔离 / 迁移 / CHANGELOG）
- `tests/test_example_data_sync.py`：3 用例（前端内嵌数据与 schema/示例数据同步锁定，第四轮审查 P1-1 沉淀）
- 全量回归：`python -m pytest tests/ -q` 273 → 308 passed

---

## [1.4] — 2026-08-18（决策链建模）

### 新增（兼容 v1.3，全部可选）

| 字段 | 类型 | 说明 |
|------|------|------|
| `decisionPoint.supersedes` | `string` | 被本决策点取代的前一个决策点 id。仅驳回后继决策点使用：`status=rejected` 的旧 DP 保留为不可变审计记录，AI 创建新 DP 时通过 `supersedes` 指向它形成决策链 |
| `decisionPoint.attempt` | `integer` (min 1) | 决策链内尝试序号（1 起）。首个 DP 可省略或 1；有 `supersedes` 时须等于被取代 DP 的 `attempt+1` |

### 决策链业务校验（C1-C6，`scripts/validate_appraisal_json.py` `_check_decision_chain()`）

JSON Schema 无法表达数组级约束，由业务校验强制：

| 编号 | 约束 | 说明 |
|------|------|------|
| C1 | `supersedes` 存在性 | 引用的 DP id 必须存在于 decisionPoints |
| C2 | 不自引用 | `supersedes` 不得指向自身 |
| C3 | 被取代者必须 rejected | 链上前驱必须 `status=rejected` |
| C4 | 1:1 后继 | 同一 DP 最多被一个后继取代（防分叉） |
| C5 | 不得成环 | 沿 supersedes 回溯不得回到自身 |
| C6 | attempt 一致性 | 后继 attempt = 前驱 attempt + 1 |

### 配套更新

| 变更 | 说明 |
|------|------|
| 根目录 schema 升级 | `schema/appraisal-result.schema.json` v1.3.1 → v1.4 |
| 版本化副本 | `schema/v1.4/appraisal-result.schema.json`（root 一致性验证 PASS） |
| 迁移脚本 | `migrate_schema.py` 新增 1.3→1.4 路径（仅更新 schemaVersion，supersedes/attempt 不自动填充） |
| 示例数据 | `example-武汉洪山住宅.json` 升级 v1.4，新增完整驳回链演示：DP-comp（rejected，comment 记录驳回理由）→ DP-comp-2（approved，supersedes=DP-comp，attempt=2） |
| 决策点规格文档 | `outputs/决策点规格定义.md`：8 个 DP 全规格 + 决策链模型（4.2 规则 / 4.3 状态机 / 4.4 Schema 建模 / 5 章场景演练） |
| 文档一致性 | `outputs/人工决策点架构设计.md`：sourceGrade 统一（链家/贝壳=T1）、DP-income 命名统一为"收益率确定"、Phase 1-2 标记完成、驳回行为表更新为决策链模型 |

### 测试

- `tests/test_schema_v14.py` 新增 27 个用例：TestV14Schema（9）/ TestDecisionChainValidation（11，C1-C6 反面 + 4 正例）/ TestVersionRoutingV14（3）/ TestMigrationV14（4）/ TestChangelogV14（1）

### Phase 3 编排层接入（2026-08-18）

| 变更 | 说明 |
|------|------|
| 编排层 skill | `skills/appraisal-orchestrator/SKILL.md`：估价任务总编排（调用 7 个现有技能的时序 + 8 个 DP 暂停点 + 决策包五段式生成规范 + 三分支响应处理 + 驳回自动建链规则） |
| 决策核心库 | `app/js/dp-core.js`：决策状态机、applyDecision、buildSuccessorShell、validateChain（C1-C6 JS 等价实现）、resolveChain；浏览器 + Node 双模，配 `tests/test_dp_core.js` 27 个 Node 单测 |
| 决策包控制台 | `app/dp-console.html`：离线零构建前端，渲染决策包（结论优先 + 风险颜色编码 P0红/P1橙/P2灰）、批准/调整（必填 modifications）/驳回（必填 comment + 后继预览）、决策链可视化、导出决策响应 JSON |
| 前端示例数据 | `app/js/example-data.js` 内嵌示例工程决策链部分；`example-武汉洪山住宅.json` DP-income 命名统一为"收益率确定" |
| 合规 fixture | `tests/fixtures/orchestrator_pending_comps.json` 用于前端流程验证 |
| 安装脚本 | `install.sh` 补录 `appraisal-orchestrator`；skill 三处同步（`skills/`、`G:/gujia开发/.workbuddy/skills/`、`~/.workbuddy/skills/`） |
| 对抗式审查 | `outputs/对抗式审查报告（第三轮）.md`：发现并修复 2 个前端缺陷（驳回预览/驳回建链），前端产物 JSON 通过 schema v1.4 + C1-C6 验证 |

### 测试

- Python 全量回归：`273 passed`
- Node 单测：`tests/test_dp_core.js` `27 pass / 0 fail`
- 前端产物验证：`scripts/validate_appraisal_json.py` 对驳回→建链→批准后的 JSON **✅ 验证通过**

---

## [1.3.1] — 2026-08-18（对抗式审查修复）

### 修复：decisionPoint 跨字段条件约束（P0-1 ~ P0-8）

v1.3 初版的条件约束只写在 `description` 文本里，验证器不执行。v1.3.1 起由 `allOf` 内的 8 组 `if/then/else` 强制：

| 编号 | 约束 | 违反示例 | 拒绝方式 |
|------|------|----------|----------|
| P0-1 | 非 pending 状态必须有人类决策记录 | `status=approved` 但无 `humanDecision` | `then: required humanDecision` |
| P0-2 | `action=modified` 必须填写非空 `modifications` | `action=modified` 无/空 `modifications` | `if/then + minLength: 1` |
| P0-3 | `trigger=method:xxx` 必须填写 `method` | `trigger=method:comps` 无 `method` | `then: required method` |
| P0-4 | `status=pending` 禁止有人类决策记录 | `status=pending` 却有 `humanDecision` | `else: not required humanDecision` |
| P0-5 | `trigger` 限定枚举：`always` 或 `method:(comps\|income\|cost\|hypotheticalDev)` | `trigger="whatever"` | `pattern` 约束 |
| P0-6 | `status` 与 `humanDecision.action` 必须一致 | `status=rejected` + `action=approved` | 3 组 `if/then` 分别锁定 approved/modified/rejected |
| P0-7 | `riskLevel` 必须等于 `risks[]` 中的最高等级 | `riskLevel=P0` 但 risks 全为 P2 | 嵌套 `if/then/else` + `contains` |
| P0-8 | `trigger=always` → 阶段非 `inMethod`；`trigger=method:xxx` → 阶段必须 `inMethod` | `phase=postReport` + `trigger=method:comps` | `if/then/else` 锁定 phase |

### 修复：业务校验（P0-9）

- `scripts/validate_appraisal_json.py` 新增 `_check_decision_point_uniqueness()`：`decisionPoints[].id` 必须唯一（JSON Schema 无法表达数组元素唯一性）

### 修复：测试假阳性（P1-1）

- `test_migrated_data_passes_v13_schema` 原先直接用 v1.3 示例数据迁移（no-op 假阳性）；现先剥离 `decisionPoints` 并还原 `schemaVersion=1.2` 再走迁移路径，真实覆盖 1.2→1.3

### 修复：示例数据（P1-4 / P1-5）

- `example-武汉洪山住宅.json` 的 DP-comp `comparison` 移除无法从结构化数据溯源的虚构信息（"楼层差 2 层"、"装修标准略高"、"距地铁站 200m"）和语义矛盾（"同栋" 但实例实际位于不同小区）；改用可溯源差异：小区名、面积差（area 字段）、建筑规模/区位修正指数（physicalDetails/locationDetails）

### 修复：文档（P2-1）

- `outputs/人工决策点架构设计.md` 移除 `"comparison": null`（schema 类型为 array，null 不合法，固定 DP 应省略字段）；`humanDecision` 描述改为"pending 时不存在，null 不合法"

### 测试

- `tests/test_schema_v13.py` 新增 16 个用例（`TestConditionalConstraints` 13 个 + `TestBusinessValidation` 3 个），v1.3 套件 44 → 60
- `scripts/adversarial_review.py` 升级为可持续回归验证工具（第 10/14 条改为验证修复结果）

---

## [1.3] — 2026-08-18

### 新增（兼容 v1.2，全部可选）

| 字段 | 类型 | 说明 |
|------|------|------|
| `decisionPoints` | `array` ($ref: decisionPoint) | 人工决策点列表：AI 在关键专业判断节点暂停，呈现"决策包"等待估价师批准/调整/驳回 |

- 新增 `$defs.decisionPoint`：`required: [id, name, phase, trigger, riskLevel, status, conclusion, evidence, reasoning, risks]`，`additionalProperties: false`
- 新增 `$defs.evidenceItem`：`required: [item, source]`，`additionalProperties: false`
- 新增 `$defs.riskItem`：`required: [description, level]`，`additionalProperties: false`
- 新增 `$defs.comparisonItem`：`required: [instance, differences]`，`additionalProperties: false`（方法特定 DP 使用）

### decisionPoint 结构

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | `string` | 是 | 决策点标识（DP1 / DP-comp 等） |
| `name` | `string` | 是 | 决策点名称 |
| `phase` | `enum` | 是 | `preCalculation` / `inMethod` / `postMethod` / `postReport` |
| `trigger` | `string` | 是 | 触发条件描述（`always` 或 `method:comps` 等） |
| `method` | `string` | 否 | 关联方法（条件 DP 使用） |
| `riskLevel` | `enum` | 是 | `P0`（必须人工确认）/ `P1`（建议人工确认）/ `P2`（知会即可） |
| `status` | `enum` | 是 | `pending` / `approved` / `modified` / `rejected` |
| `conclusion` | `string` | 是 | AI 结论（结论先行） |
| `evidence` | `array` (minItems: 1) | 是 | 证据列表，每项含 `item` + `source` |
| `reasoning` | `string` | 是 | 推理过程 |
| `risks` | `array` (minItems: 1) | 是 | 风险列表，每项含 `description` + `level` + 可选 `mitigation` |
| `comparison` | `array` | 否 | 与估价对象差异（方法特定 DP 使用） |
| `humanDecision` | `object` | 否 | 人类决策记录（pending 时可不存在） |

### 设计原则

- **结论先行**：每个决策点必须先给结论，再展开证据和理由
- **风险分级**：P0 = 错误代价不可逆（必须人工确认），P1 = 建议确认，P2 = 知会即可
- **向后兼容**：`decisionPoints` 为可选字段，v1.2 数据迁移到 v1.3 仅更新版本号，不自动填充

### 变更

| 字段 | 旧约束 | 新约束 | 原因 |
|------|--------|--------|------|
| `schemaVersion` | `pattern: "^1\\.2$"` | `pattern: "^1\\.3$"` | 版本号升级 |

### 迁移

- 运行 `python scripts/migrate_schema.py --input <file.json>` 自动将 v1.2 升级为 v1.3（仅更新版本号）
- `decisionPoints` 为运行时字段，由 AI 在估价流程中动态生成，不通过迁移填充

### 测试

- 新增 `tests/test_schema_v13.py`：44 个测试用例（7 个测试类）
- 覆盖维度：schema 合法性 / decisionPoint 约束 / 子项约束 / 版本路由 / 迁移 / 完整决策包 / CHANGELOG

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
v1.0 (2026-08-11) ──▶ v1.1 (2026-08-13) ──▶ v1.2 (2026-08-14) ──▶ v1.3 (2026-08-18) ──▶ v1.3.1 (2026-08-18) ──▶ v1.4 (2026-08-18)
```

迁移命令：
```bash
python scripts/migrate_schema.py --input schema/example-武汉洪山住宅.json --output example-v1.1.json
```
