# Architecture — 房地产估价 AI 工具链

> 目录结构与模块职责的事实来源。版本：1.0 | 2026-08-24（由第五轮审查 P1-1 补齐，从 HANDOFF-08-19 §六 + README 提取）

## 总体形态

本地零构建网页应用 + WorkBuddy 技能体系。浏览器打开 HTML 即用，可离线；无后端、无数据库、单 JSON 文件为一个工程。

```
schema/                         ← JSON 数据契约（单一事实源）
├── appraisal-result.schema.json  ← v1.5 根 schema（sourceGrade）
├── example-武汉洪山住宅.json      ← v1.5 示例工程（22/22 evidence 含 sourceGrade）
└── v1.0/ v1.1/ v1.2/ v1.3/ v1.4/ v1.5/  ← 版本化副本（root 一致性由测试锁定）

scripts/                        ← 领域引擎 + 工具链（Python）
├── validate_appraisal_json.py    ← 版本路由（含 1.5）+ C1-C6 决策链业务校验
├── migrate_schema.py             ← v1.0 → … → v1.5 迁移（仅版本号，不自动推断）
├── gen_{comps,income,cost,hypo_dev}_template.py  ← 4 方法测算 Excel 模板生成
├── adversarial_review.py         ← 对抗式审查回归用例
└── anonymize_template.py / anonymize_rules.yaml  ← 数据模糊化（YAML 驱动）

skills/                         ← WorkBuddy 技能（7 方法/报告 + 1 编排）
├── appraisal-orchestrator/SKILL.md  ← 编排层（8 决策点暂停 + 决策包五段式）
├── appraisal-data-collection/       ← 资料搜集（第 3.0.5 条）
├── web-research-methodology/        ← 联网检索方法论（T0/T1/T2 信源分级）
├── comps-method / income-method / cost-method / hypothetical-dev-method  ← 四大方法
└── appraisal-report/                ← 报告生成（第 7 章）

app/                            ← 前端（浏览器直接打开，零构建）
├── dp-console.html               ← 决策包控制台（结论先行 + 风险色标 + 决策链可视化）
└── js/
    ├── dp-core.js                ← 决策链纯逻辑（浏览器 + Node 双模）
    └── example-data.js           ← 前端内嵌演示数据（与 schema/示例数据同步，测试锁定）

tests/                          ← 测试（Python pytest + Node node --test）
├── helpers.py                    ← 共享测试 helper（v12/v13/v14 去重）
├── test_schema_v15.py            ← 19 用例（含根=副本一致性）
├── test_fixtures.py              ← 16 用例（4 条件 DP fixture + 溯源锁定）
├── test_example_data_sync.py     ← 3 用例（前端内嵌数据同步锁定）
├── test_e2e_orchestrator.js      ← 5 用例（编排闭环 + riskLevel P0-7 断言）
├── test_dp_core.js               ← 27 用例（决策链状态机）
├── conftest.py                   ← xlsx 模板预生成 fixture
└── fixtures/                     ← 4 个 pending 条件 DP + 方法片段

outputs/                        ← 交付产物（报告/模板/交接文档）
├── HANDOFF-2026-08-19.md         ← 最新交接（下一任务输入）
├── 对抗式审查报告（第五轮）.md     ← 最近一轮审查
├── 端到端联调报告（2026-08-19）.md
└── templates/                    ← 4 个测算模板 xlsx（版本控制）

README.md / intent.md / architecture.md / decisions.md / CHANGELOG.md / CLAUDE.md  ← 项目宪章与治理
```

## 模块职责与依赖方向

| 层 | 职责 | 依赖 |
|---|---|---|
| schema | 数据契约，版本化不可变 | 无（被 scripts/tests/app 依赖） |
| scripts | 校验/迁移/模板生成 | schema（只读） |
| skills | 工作流知识（What/How），不执行计算 | schema 定义、规范条款 |
| app | 前端交互与决策链状态机 | schema、example-data |
| tests | 三端回归（Python 闭环 / Node 闭环 / 浏览器实测） | 全部 |

依赖方向单向：`schema ← scripts/app/tests`；skills 只消费契约不反哺。禁止循环依赖。

## 关键机制

1. **版本化 schema**：根 schema 永远指向最新版；每次升级新建 `v<N>/` 副本 + 迁移脚本 + 更新验证器版本映射 + 同步前端内嵌数据（4 处同步，见 CHANGELOG 发布清单）。
2. **双模 dp-core**：同一份 JS 在浏览器（window）与 Node（module.exports）运行，避免两套逻辑漂移。
3. **三端互证**：Node 闭环回归 + 浏览器真实操作 + Python 端复核，任何一端不过即发布失败。
4. **决策链不可变审计**：被驳回的 DP 保留（status=rejected），新 DP 以 supersedes 指向前驱，C1-C6 保证链结构合法。
