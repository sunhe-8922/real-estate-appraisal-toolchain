# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## 项目是什么

基于 **GB/T 50291-2015《房地产估价规范》** 的房地产估价 AI 工具链（WorkBuddy 技能体系 + 本地零构建前端）。
规范原文在仓库根：`房地产估价规范GBT 50291-2015.docx`（被 .gitignore 排除，仅本地参考）。

形态：**本地单机、零构建、可离线**。浏览器直接打开 `app/dp-console.html` 即用；无后端、无数据库，
**一个 JSON 文件 = 一个估价工程**。

> 仓库内所有示例、fixtures 及 git 历史中的人名/证件/地址/房产数据均为**虚构测试数据**（README 数据声明），不代表真实标的。

## 环境前置

无 `requirements.txt` / `package.json` / Makefile / CI 配置，也没有项目虚拟环境。依赖装在 WorkBuddy 受管 venv，
**必须用绝对路径解释器**，不要依赖 PATH 上的 `python` / `node`。

| 用途 | 解释器（已验证） | 已装依赖 |
|---|---|---|
| Python 测试/脚本 | `C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe` | pytest 9.1.1、jsonschema 4.26.0、openpyxl 3.1.5 |
| Node 测试 | `C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2-2/node.exe` | 无第三方依赖（node:test 内置） |

下文用 `$PY` / `$NODE` 代指上面两个路径。所有命令在仓库根 `G:/gujia开发` 执行。

## 常用命令

### 测试（当前全绿基线）

```bash
$PY -m pytest tests/ -q                       # 359 passed ≈36s（rounds/11 关门时基线）
$PY -m pytest tests/test_schema_v13.py -q     # 单文件（最大套件 60 用例）
$PY -m pytest tests/ -q -k "decision_chain"   # 按名筛选单用例
$PY -m pytest tests/test_fixtures.py::test_x  # 精确单用例

$NODE --test tests/test_dp_core.js tests/test_e2e_orchestrator.js   # 32 pass / 0 fail
```

两个套件必须都跑：Python 管 schema/决策链/Excel 模板，Node 管前端决策链状态机与编排闭环。
`tests/conftest.py` 会在 session 内自动调用 `scripts/gen_*_template.py` 生成 4 个 xlsx 到 `outputs/templates/`
（openpyxl fixture 依赖），因此根目录直接跑 pytest 即可，不需要手工预生成。

### 校验工程 JSON（`scripts/validate_appraisal_json.py` — 手写 `sys.argv` 解析，非 argparse）

```bash
$PY scripts/validate_appraisal_json.py <工程.json>          # 全量：schema + 业务 + C1-C6
$PY scripts/validate_appraisal_json.py --degraded <文件>     # 自然语言降级工况
$PY scripts/validate_appraisal_json.py --fragment <method> <文件>
# ⚠️ method 只支持 comps / income / cost / hypotheticalDev；传 decisionPoints 会抛 ValueError
```

退出码 0 = 通过，1 = 有错。任何修改了 `decisionPoints[]` / 方法输出的任务，交付前必跑。

> ⚠️ **存在两个同名校验器，`--fragment` 语义不同**：上面是仓库根的 jsonschema 版（受 359 用例回归保护）；
> `skills/appraisal-orchestrator/scripts/` 下还有一份 skill 自带的轻量版，它支持 `--fragment decisionPoints`
> 但只跑 DP 结构 + C1-C6，**不覆盖 schema 与业务红线**。用相对路径 `scripts/validate_appraisal_json.py` 时
> 会解析到当前目录下的那一份，注意区分。决策点的权威校验 = 仓库根全量模式。


### Schema 迁移与其他工具

```bash
$PY scripts/migrate_schema.py --input <文件> --list                       # 列出迁移路径（--list 也必须有 --input）
$PY scripts/migrate_schema.py --input <文件> --preview                    # 干跑预览
$PY scripts/migrate_schema.py --input <文件> [--output <文件>]            # 执行迁移，缺省覆盖输入
$PY scripts/verify_example_arithmetic.py <示例json>          # 示例数值自洽 + 节点口径校验
$PY tests/mutation_harness.py [--json out.json] [--verbose]  # 变异测试：度量上面那个校验器的缺陷检出率
$PY scripts/gen_{comps,income,cost,hypo_dev}_template.py     # 生成 4 个测算 xlsx 模板
```

Excel ↔ JSON 双向链路（改任一模板都要整条重跑）：
`scripts/extract_calculation_chain.py`（Excel→calculationChain.json）→
`scripts/rebuild_excel_formula.py --mode values|cells`（JSON→Excel 公式重建+比对）→
`scripts/populate_excel_from_schema.py --verify-only|--backfill`（Schema↔Excel 同步）→
`scripts/excel_to_json_mapping.py`（字段映射验证）。

### 安装（技能/专家分发，非代码构建）

```bash
./install.sh                    # 或 Windows PowerShell: .\install.ps1
./install.sh --skills-only | --experts-only | --check | --force    # ps1 用 -SkillsOnly 等
```

安装器把 `skills/` 下 7 技能 + 编排层复制到项目级 `.workbuddy/skills/` 与用户级 `~/.workbuddy/skills/`，
专家复制到 `~/.workbuddy/plugins/marketplaces/my-experts/plugins/`。
**会话中新增/修改技能后必须重启 WorkBuddy**（技能索引启动时一次性构建），否则 `Skill` 工具看不到。

### 子项目 storm-deep-research（独立 git 仓库，已被根 .gitignore 排除）

```bash
cd storm-deep-research && PYTHONPATH=src $PY -m pytest tests/ -q    # 120 passed
```

**不要 `pip install -e .`**（会在 `src/` 生成 .egg-info 污染工作区），用 `PYTHONPATH=src` 引入包。

## 架构总览

```
schema/         数据契约 —— 单一事实源，版本化不可变
scripts/        领域引擎 + 工具链（Python 纯函数）
skills/         WorkBuddy 技能：工作流知识（What/How），不执行计算
experts/        房地产估价合规审查专家
app/            前端决策包控制台（零构建），dp-core.js 浏览器/Node 双模
tests/          三端回归 + 差分/Oracle/变异 度量工具
rounds/         递归自我改进迭代存档（每轮独立目录，禁止覆盖）
cases/          真实委托 case 的工作目录（工程 json + 一次性填表脚本）
outputs/        交付产物：报告 / xlsx 模板 / 审查报告 / 交接文档
```

**依赖方向单向：`schema ← scripts / app / tests`**；skills 只消费契约，禁止反向依赖与循环。

| 文件 | 职责 |
|---|---|
| `schema/appraisal-result.schema.json` | 根 schema，永远指向最新版；`v1.0…v1.5/` 为不可变副本 |
| `scripts/validate_appraisal_json.py` | 版本路由 + C1-C6 决策链业务校验（JSON Schema 表达不了的部分） |
| `scripts/migrate_schema.py` | v1.0→v1.5 逐级迁移，**只改版本号，不自动推断新字段**（D-006 保守决策） |
| `app/js/dp-core.js` | 决策链纯逻辑，UMD 工厂双模导出（`window.DPCore` / `module.exports`） |
| `app/js/example-data.js` | 前端内嵌演示数据，须与 `schema/` 示例同步（由测试锁定） |
| `skills/appraisal-orchestrator/SKILL.md` | 编排层：8 个人工决策点在哪里暂停、怎么生成决策包 |

## 关键机制（容易踩的部分）

1. **Schema 四处同步**：升级版本 = 改根 schema + 新建 `v<N>/` 副本 + 加迁移函数 + 同步前端内嵌数据，共 4 处，
   遗漏由 `tests/test_example_data_sync.py` 与 CHANGELOG 发布清单双机制兜底。
2. **决策链不可变审计**：DP 被驳回**不删除**（`status=rejected` 留作审计），新 DP 用 `supersedes` 指前驱 + `attempt` 递增
   （`DP-comp` → `DP-comp-2`）。C1-C6 校验存在性/不自引用/前驱必须 rejected/1:1 后继/无环/attempt 一致；
   Python 端 `_check_decision_chain()` 与前端 `DPCore.validateChain()` 必须等价，差分别由 `test_dp_chain_*` 锁定。
3. **P0-7 铁律**：`riskLevel` 必须等于 `risks[]` 中最高级——AI 重写 successor 后极易漏同步，已有 e2e 断言锁定。
4. **sourceGrade**：证据信源质量 T0/T1/T2 结构化字段（可选），迁移时**不自动推断**，避免把猜测当事实。
5. **差分 + Oracle 测试风格**：`tests/` 里成对出现 diff（生成器 vs 实现）与 oracle（独立第三方实现）脚本，
   外加 `mutation_harness.py` 量化"测试到底能抓到多少缺陷"。改动 `dp-core.js` 或 `calculate*Chain` 后，
   只跑 pytest 不够——确认是否还要跑对应的差分/`--json` 度量脚本并更新 `rounds/N/` 存档。
6. **rounds/ 从不覆盖**：迭代结果必须新建 `rounds/<N>/`（含 PROPOSAL/RESULTS/差分脚本/结果 json），
   原地覆盖历史档案是已发生过的事故（P1-1 教训）。

## 约束红线（写入校验器 + 单测，违反即拒绝）

可比实例 ≥ 3；成交距价值时点 ≤ 2 年；单因素修正 ≤ 20%；综合修正 ≤ 30%；最高/最低价比 ≤ 1.2；
至少采用两种估价方法；报告使用期限 ≤ 1 年。

## 本项目工作纪律（摘自 CLAUDE.md，冲突时以此为准）

- **动手前**：读 `intent.md`（目标/成功标准/非目标）→ `CLAUDE.md`（规则）→ 目标文件；`architecture.md`（目录与模块职责）、`decisions.md`（ADR）是架构的事实来源。
- **交付**：面向用户的产物一律放 `outputs/`，**不放 `.workbuddy/`**（内置查看器渲染不了那里的 md）。
- **Git**：commit 用英文 Conventional 风格，一个 commit 一个意图；**`git push` 禁止自动执行**，只在 sun 明确要求同步时才推。
- **交付格式**：`## Result / ## Changes / ## Verification / ## Risks / ## Next Action`；必答 Why / What / How verified / What's next。DoD 满足才可宣称 DONE——"测试通过 ≠ 完成"，结果须经四级验证（目标/行为/回归/运行安全）。
- **交接文档：`outputs/HANDOFF-*.md` 是每个任务的事实输入**（当前最新 `outputs/HANDOFF-2026-09-01-round7.md`），要求 Git 入仓、自洽、独立于聊天上下文；新任务开始前先读它。

## 已知 CLI 怪癖

- `scripts/migrate_schema.py --list` 单独用会报缺 `--input`（argparse 声明为 required），必须 `--input <文件> --list`。
- `scripts/validate_appraisal_json.py` 用**手写 `sys.argv` 解析**而非 argparse（见上文校验命令一节），
  参数顺序固定为 `--fragment <method> <文件>`，不支持 `--key=value` 形式。

## 环境坑（本机特有，会浪费大量时间）

- **heredoc 反斜杠被转成正斜杠**：经 Bash 工具传 `python - <<'EOF'` 时，脚本里的 `\n` `\t` 到达 Python 会变成 `/n` `/t`，
  字符串匹配静默失败（加引号的 heredoc 也躲不掉）。脚本内改用 `chr(10)` / `chr(9)`，或写成 `.py` 文件再执行。
- **沙箱跨目录写可能静默失败**：写绝对路径到 cwd 之外会报 `open` 失败；先写 cwd 内再 `mv`。
  `mv` / `rm` 存在"报错但生效"和"静默成功"，任何写/移/删之后必须 `ls` 二次确认。
- **Bash 工作目录跨调用持久**：`cd` 后会残留，可疑时先 `pwd`。
- **git 远程 tracking refs 不持久**：`git status -sb` 常显示 `[gone]`，不代表推送失败。用
  `[ "$(git ls-remote origin master | cut -f1)" = "$(git rev-parse HEAD)" ]` 判断真实推送状态。
- **后台常驻进程会被回收**：WorkBuddy bash 命令结束时回收全部子进程，daemon 类进程改用 Windows 计划任务拉起。
