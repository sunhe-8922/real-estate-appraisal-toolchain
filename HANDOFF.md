# 房地产估价 AI 工具链 — 任务交接文档

> **生成日期**：2026-08-03  
> **GitHub 仓库**：https://github.com/sunhe-8922/real-estate-appraisal-toolchain  
> **适用对象**：下一个接手本项目的 AI 助手或开发者  
> **规范依据**：GB/T 50291-2015《房地产估价规范》  
> **参考模式**：Anthropic financial-services 仓库（https://github.com/anthropics/financial-services）

---

## 一、项目概览

本项目为 WorkBuddy 平台的房地产估价 AI 工具链，涵盖估价全流程（资料搜集 → 四大方法测算 → 报告生成 → 合规审查），以 **技能（Skill）+ 专家（Expert）** 形式交付。

### 技术栈

| 层级 | 技术 |
|------|------|
| 运行平台 | WorkBuddy（本地对话式 AI 助手） |
| 技能定义 | YAML frontmatter + Markdown（SKILL.md） |
| 专家定义 | JSON plugin 配置 + Markdown（agents/*.md） |
| Excel 输出 | openpyxl（Python，公式驱动，非硬编码） |
| 多格式报告 | python-docx / weasyprint / Chart.js |
| 版本管理 | Git + GitHub |

### 交付物清单

| 类型 | 名称 | 位置（仓库内） | 行数 |
|------|------|---------------|------|
| 技能 | `appraisal-data-collection` | `skills/appraisal-data-collection/SKILL.md` | 203 |
| 技能 | `web-research-methodology` | `skills/web-research-methodology/SKILL.md` | 146 |
| 技能 | `comps-method` | `skills/comps-method/SKILL.md` | 376 |
| 技能 | `income-method` | `skills/income-method/SKILL.md` | 387 |
| 技能 | `cost-method` | `skills/cost-method/SKILL.md` | 370 |
| 技能 | `hypothetical-dev-method` | `skills/hypothetical-dev-method/SKILL.md` | 390 |
| 技能 | `appraisal-report` | `skills/appraisal-report/SKILL.md` | 748 |
| 专家 | `re-appraisal-expert` | `experts/re-appraisal-expert/` | 202 |
| 报告 | 测试案例 | `outputs/武汉洪山住宅_抵押估价报告.md` | 697 |
| 文档 | README | `README.md` | — |
| 文档 | 项目上下文 | `CLAUDE.md` | — |

---

## 二、已完成功能点

### 2.1 技能体系（7 技能覆盖估价全流程）

```
资料收集层
  ├── appraisal-data-collection  — 搜集什么资料（GB/T 50291-2015 第 3.0.5 条）
  └── web-research-methodology  — 怎么搜资料（并行子 Agent + 信源分级 T0/T1/T2）

方法测算层
  ├── comps-method              — 比较法（第 4.2 节）
  ├── income-method             — 收益法（第 4.3 节）
  ├── cost-method               — 成本法（第 4.4 节）
  └── hypothetical-dev-method   — 假设开发法（第 4.5 节）

报告输出层
  └── appraisal-report          — 报告生成（第 7 章）

合规审查层
  └── re-appraisal-expert（专家）— 方法选用决策 + 报告审查
```

### 2.2 各技能详细功能

#### appraisal-data-collection（资料搜集）
- 9 步工作流：明确事项 → 方法预判 → 对象状况 → 交易实例 → 收益成本 → 区域市场 → 宏观影响 → 检查核实 → 输出清单
- 四维度资料矩阵（估价对象/同类交易/区域市场/宏观因素）× 具体内容 × 来源渠道
- 来源渠道按 T0 官方/T1 头部机构/T2 自媒体标注信源等级
- 输出：结构化资料清单 + 来源渠道指引

#### web-research-methodology（联网研究方法论）
- 并行搜索策略：纵向 Agent（历史纵深）+ 横向 Agent（竞争格局）+ 补充 Agent
- 子 Agent 启动模板（含 WebSearch/WebFetch 调用指引）
- 信源分级 T0/T1/T2 + 红线（仅 T2 支撑须标注"缺乏权威信源"）
- 充分性自检：纵向/横向/来源三维检查清单

#### comps-method（比较法测算）
- 7 步流程：搜集交易实例 → 选取可比实例 → 建立比较基础 → 交易情况修正 → 市场状况调整 → 房地产状况调整 → 计算比较价值
- 5 条红线：可比实例 ≥3、成交距价值时点 ≤2 年、单项修正 ≤20%、综合修正 ≤30%、最高最低价比 ≤1.2
- Excel 输出（openpyxl 公式驱动）：SUM/AVERAGE/IF 公式，蓝字=输入、黑字=公式、黄底=假设
- 模板自定义：增减可比实例列、数据验证、Sheet 保护

#### income-method（收益法测算）
- 6 步流程：方法选择 → 收益期确定 → 净收益测算 → 报酬率确定 → 收益价值计算 → 转售价值
- 双路径：报酬资本化法（全剩余寿命/持有加转售）+ 直接资本化法
- 收入类型覆盖：租赁收入法 + 经营收入法
- Excel 公式：NPV、等比递增折现、转售折现
- 模板自定义：切换资本化方式、拖拽扩展折现行

#### cost-method（成本法测算）
- 4 步流程：路径选择 → 7 项必要支出 → 3 类折旧 → 成本价值计算
- 双路径：房地合估 / 房地分估
- 3 类折旧（物质/功能/外部）× 3 种方法（年龄-寿命/市场提取/分解法）
- 折旧合计 IF 公式自动切换
- 模板自定义：折旧方法下拉框（3 选 1）、插入行增加成本项

#### hypothetical-dev-method（假设开发法测算）
- 8 步流程 + 动态/静态双方法 + 3 种估价前提
- 3 条红线：开发完成后价值禁用成本法、动态法不另算利息利润、前提须匹配估价目的
- 红线检查 IF 公式 + 条件格式自动标红
- 模板自定义：方法/前提下拉框、插入行增加支出项、静态法迭代计算提示

#### appraisal-report（报告生成）
- 6 步流程：确认类型 → 收集测算结果 → 撰写章节 → 整合 → 自定义 → 多格式输出
- 覆盖 GB/T 50291-2015 第 7 章全部章节：
  - **前置部分**：封面（7.0.4，含 7 项信息）+ 目录（含锚点链接 + Word 域代码 + HTML nav 三种方案）
  - **鉴证部分**：致估价委托人函（7.0.5，含币种标注）+ 注册估价师声明（7.0.6，含专业帮助说明模板）+ 假设和限制条件（7.0.16）
  - **结果报告**（7.0.17，14 项）+ 结果汇总表（7.0.17-1 格式）
  - **技术报告**：估价对象分析（7.0.9）+ 市场背景分析（7.0.10）+ 最高最佳利用分析（7.0.11）+ 方法适用性分析（7.0.14）+ 测算过程（7.0.12）+ 结果确定（7.0.15）+ 跨方法数据一致性检查
  - **附件**（7.0.18）：位置图/照片/权属证明/委托书/可比实例明细/资质证书等
- 30+ 模板变量系统（`{{项目名称}}`、`{{比较法总价}}` 等）
- **5 种输出格式**：Markdown（默认）→ Word（python-docx）→ HTML → PDF（weasyprint）→ Dashboard（Chart.js 交互式看板）
- Dashboard 特性：柱状图/饼图/雷达图/红线状态、颜色编码（绿=合规/黄=预警/红=超标）、可导出 PNG、响应式布局
- 批量生成：一套模板 + 多套数据 = 批量报告
- 上线前经过两轮评估优化（v1: 12/18 合规 → v2: 18/18 合规）

### 2.3 专家：re-appraisal-expert
- 类型：单 Agent 专家（IndustryConsultant）
- 系统提示词 202 行，内嵌规范 8 章核心知识
- 能力：方法选用决策 + 各方法测算指导 + 结果确定 + 报告合规审查
- 所有输出标注"须由注册房地产估价师审核签署后使用"

### 2.4 Excel 模板自定义（四条测算技能共有）
- **三种模板模式**：空白/示例/数据
- **数据验证**（openpyxl DataValidation）：数值范围、下拉框列表
- **单元格注释**（openpyxl Comment）：规范条文
- **Sheet 保护**：仅蓝字可编辑，公式锁定
- **颜色图例**：蓝字=用户输入、黑字=公式、黄底=关键假设、深蓝底白字=表头

### 2.5 测试验证
- 生成完整测试案例：武汉洪山区 128.50m² 住宅，抵押估价目的，比较法+收益法
- 两轮评估优化闭环（12/18 → 18/18 合规）
- 逐一验证：封面、目录、币种标注、信源等级、专业帮助说明、跨方法一致性、附件完整性

---

## 三、未解决的问题

### 3.1 收益法报酬资本化法低估问题（P1）

**现象**：报酬资本化法「全剩余寿命 59.5 年折现→146 万」与直接资本化法「→311 万」相差超过一倍。

**根因**：住宅在中国不是纯现金流资产，有限年限折现严重低估了资产本身的价值。这不是代码 bug，是方法论选择问题——真实估价实践中，收益法用于住宅时，估价师会用「持有加转售模式」（持有 10 年 + 期末按比较法转售），而不是全剩余寿命折现。

**当前处理**：测试报告中选择了直接资本化法作为主要依据，并解释了差异原因。SKILL.md 持续改进章节已记录此问题（第 6-7 条），但指令层面尚未写死"住宅默认持有加转售模式"。

**建议**：在 `income-method` 技能中增加场景判断——当估价对象为住宅时，默认推荐持有加转售模式，仅在用户明确要求时使用全剩余寿命折现。

### 3.2 技能索引非实时（WorkBuddy 平台限制，非本项目管理）

**现象**：WorkBuddy 在启动时一次性扫描技能目录并建立索引，会话中新建/修改的技能不会被实时识别。

**影响**：每次新建技能或修改 SKILL.md 后，需要：
1. 复制到用户级目录 `~/.workbuddy/skills/<name>/`
2. 重启 WorkBuddy
3. 通过 `Skill` 工具验证加载

**当前规避**：技能同时维护项目级（`G:/gujia开发/.workbuddy/skills/`）和用户级（`~/.workbuddy/skills/`）双副本。Git 仓库中的 `skills/` 是导出副本。

### 3.3 多格式输出未经端到端验证（P2）

**状态**：SKILL.md 声明支持 Markdown → Word/HTML/PDF/Dashboard 五种格式输出，但只完整测试了 Markdown（默认）格式。

**未验证项**：
- python-docx Word 输出（宋体/黑体/页眉页脚/封面排版）
- weasyprint PDF 输出（分页/页边距/中文渲染）
- Dashboard HTML 交互效果（Chart.js 实际渲染）
- 批量生成（多套数据）

**建议**：下一阶段逐一实现并测试各格式的生成脚本。

### 3.4 Excel 模板未实际生成 .xlsx 文件（P2）

**状态**：四条测算技能的 SKILL.md 中包含了详细的 openpyxl 生成指令（公式、验证、保护、注释、颜色），但**尚未在对话中实际执行过** `openpyxl` 代码生成 .xlsx 交付。

**验证方式**：用 `python -c "import openpyxl; ..."` 实际生成一个比较法模板，在 Excel 中打开确认公式运行、下拉框可用、保护生效。

### 3.5 GitHub 仓库结构 vs WorkBuddy 运行时路径不匹配（P2）

**仓库结构**：
```
skills/      ← 给用户手动复制
experts/     ← 给用户手动复制
outputs/     ← 示例报告
```

**WorkBuddy 运行时**：
```
.workbuddy/skills/   ← 项目级技能（真正生效）
~/.workbuddy/skills/  ← 用户级技能（真正生效）
~/.workbuddy/plugins/marketplaces/my-experts/...  ← 专家（真正生效）
```

**问题**：GitHub 仓库的 `skills/` 和 `experts/` 是**导出副本**，不是运行时的真实路径。如果下一个 AI 助手只看 GitHub 仓库而不了解 `.workbuddy/` 的结构，可能修改了错误的位置。

**建议**：在 README.md 中明确说明运行时路径，或编写安装脚本（`install.sh`/`install.ps1`）自动复制到正确位置。

---

## 四、需要注意的风险

### 4.1 平台依赖风险
- **WorkBuddy 技能机制变更**：如果 WorkBuddy 更新后改变技能索引方式、SKILL.md 解析规则或目录结构，所有 7 个技能可能需要适配。当前已验证的机制：YAML frontmatter + Markdown body、启动时一次性索引。
- **查看器渲染限制**：WorkBuddy 内置文件查看器无法渲染 `.workbuddy/` 目录下的文件（已验证），也无法渲染 LaTeX 数学块（`$$...$$`）。这些约束已写入技能红线，但平台更新后可能变化，也可能新增未知限制。

### 4.2 数据孤岛风险
- 7 个技能之间通过**自然语言指令**协作（如 "调用 comps-method 取比较法测算结果"），没有结构化的数据交换格式（如 JSON schema）。这意味着：
  - 跨技能的数据一致性完全依赖 AI 的理解和执行，无自动校验
  - 如果某个技能的 SKILL.md 被修改导致输出格式变化，下游技能可能失效
- **建议**：下一阶段定义标准的「测算结果 JSON Schema」，让各方法技能输出结构化数据，报告生成技能读取结构化数据而非自然语言。

### 4.3 规范合规风险
- GB/T 50291-2015 是推荐性国标，地方政府可能有补充规定或更严格的地方标准。当前工具链仅基于国标，未纳入任何地方性法规。
- 估价报告是法定文书，AI 生成的报告**必须由注册房地产估价师审核签署**后方可使用。这一条在所有技能输出中已标注，但存在被忽略的风险。

### 4.4 专家 Agent 未经实际对话测试
- `re-appraisal-expert` 的 202 行系统提示词设计已完成，但**未在实际对话中激活测试**——未验证过专家对实际估价案例的回复质量、红线执行力度、或与技能的协作效果。
- WorkBuddy 专家与技能的协作机制尚不明确：专家是否能自动调用技能？还是需要用户在对话中手动切换？

### 4.5 Git 仓库内容安全性
- 已通过 `.gitignore` 排除了 `.workbuddy/`、`*.docx`（规范原文 13MB）、`storm-deep-research/` 等敏感/大型文件
- 但未做凭证扫描——确认 `.gitignore` 外没有泄露 API key、token 或个人信息
- 建议：下次提交前运行 `git ls-files` 确认无意外文件

---

## 五、后续迭代建议

### 5.1 高优先级（v1.1）

| # | 任务 | 理由 |
|---|------|------|
| 1 | **修复收益法住宅场景默认策略** | 当前报酬资本化法低估 50%（146 万 vs 311 万），触发"持有加转售模式"作为住宅默认 |
| 2 | **实际生成可用的 .xlsx 模板** | 四条测算技能的 openpyxl 指令已完成但未执行，需要实际生成并 Excel 验证 |
| 3 | **编写安装脚本** | `install.ps1`（Windows）/ `install.sh`（Unix），自动将 `skills/` 和 `experts/` 复制到正确运行时路径 |
| 4 | **定义测算结果 JSON Schema** | 标准化各方法输出格式，消除跨技能自然语言依赖 |

### 5.2 中优先级（v1.2）

| # | 任务 | 理由 |
|---|------|------|
| 5 | **实现所有 5 种报告输出格式** | 当前仅 Markdown 验证通过，Word/HTML/PDF/Dashboard 需逐一实现和测试 |
| 6 | **激活测试 re-appraisal-expert** | 用真实案例对话验证专家回复质量 |
| 7 | **增加单元测试** | 四条测算技能的核心计算逻辑应有 Python 单测，确保公式生成的 Excel 校验通过 |
| 8 | **批量报告生成** | 一套模板 + 多套数据 = 批量报告（已设计但未实现） |

### 5.3 低优先级（v2.0）

| # | 任务 | 理由 |
|---|------|------|
| 9 | **支持地方性补充规定** | 例如深圳市估价技术指引、上海市实施细则等 |
| 10 | **估价报告对比/差异分析** | 两个版本报告的自动差异对比（类似 git diff） |
| 11 | **估价项目历史管理** | 按项目组织资料/测算/报告，支持项目间切换和复用 |
| 12 | **Web 前端集成** | 将技能能力对接到 `gujia开发` 项目的本地网页应用（index.html + engine.js） |

### 5.4 架构演进建议

当前 Architecture（技能即代码）：
```
User → [Skill A] → [Skill B] → ... → Output
         ↑ 纯自然语言协作，无结构化数据通道
```

建议 Architecture（技能 + 数据总线）：
```
User → Orchestrator
         ├── [Skill A] → JSON Schema A ─┐
         ├── [Skill B] → JSON Schema B ─┤
         ├── [Skill C] → JSON Schema C ─┤
         └── [Reporter] ← 读取所有 Schema → Output
```

这样升级后，报告生成技能可以直接校验跨方法数据一致性（面积/用途/时点/年限），而不是依赖 AI 的"理解"。

---

## 六、操作速查

### 6.1 安装到 WorkBuddy

```powershell
# 1. 克隆仓库
git clone https://github.com/sunhe-8922/real-estate-appraisal-toolchain.git

# 2. 复制技能（需要两份：项目级 + 用户级）
cp -r skills/* "G:/gujia开发/.workbuddy/skills/"
cp -r skills/* "$env:USERPROFILE/.workbuddy/skills/"

# 3. 复制专家
cp -r experts/re-appraisal-expert "$env:USERPROFILE/.workbuddy/plugins/marketplaces/my-experts/plugins/"

# 4. 重启 WorkBuddy
```

### 6.2 新建/修改技能后的验证流程

1. 修改 `skills/<name>/SKILL.md`
2. 同步到用户级：`cp -r skills/<name> "$env:USERPROFILE/.workbuddy/skills/"`
3. 重启 WorkBuddy
4. 在对话中调用 `Skill` 工具验证（如 `skill: "comps-method"`）

### 6.3 输出文件路径规则

- ✅ 用户可见文件：`G:/gujia开发/outputs/`
- ❌ 不要在 `.workbuddy/` 下放置任何用户可见文件（查看器无法渲染）
- 技能修改后同步两份：`G:/gujia开发/.workbuddy/skills/<name>/` + `~/.workbuddy/skills/<name>/`
- Git 仓库中的 `skills/` 是导出副本，不代表运行时路径

### 6.4 报告文件格式约束

- ❌ 禁止 LaTeX 数学块（`$$...$$`）→ 查看器不渲染
- ❌ 禁止 HTML 注释（`<!-- ... -->`）→ 可能导致渲染异常
- ✅ 数学公式用纯文本：`V = A / (Y - g) × [1 - ((1+g)/(1+Y))^n]`

---

## 附录 A：文件清单

```
G:/gujia开发/
├── HANDOFF.md                                    ← 本文件
├── README.md                                     ← 项目说明（GitHub 首页）
├── CLAUDE.md                                     ← 项目上下文（AI 助手读取）
├── .gitignore                                    ← Git 排除规则
├── .workbuddy/                                   ← WorkBuddy 内部目录（不提交 Git）
│   ├── memory/
│   │   ├── 2026-08-03.md                         ← 本次任务全量工作日志
│   │   └── MEMORY.md                             ← 长期项目约定
│   └── skills/                                   ← 项目级技能（真正生效）
│       ├── appraisal-data-collection/SKILL.md
│       ├── appraisal-report/SKILL.md
│       ├── comps-method/SKILL.md
│       ├── cost-method/SKILL.md
│       ├── hypothetical-dev-method/SKILL.md
│       ├── income-method/SKILL.md
│       └── web-research-methodology/SKILL.md
├── skills/                                       ← 导出副本（Git 提交用）
│   ├── appraisal-data-collection/SKILL.md
│   ├── appraisal-report/SKILL.md
│   ├── comps-method/SKILL.md
│   ├── cost-method/SKILL.md
│   ├── hypothetical-dev-method/SKILL.md
│   ├── income-method/SKILL.md
│   └── web-research-methodology/SKILL.md
├── experts/                                      ← 导出副本（Git 提交用）
│   └── re-appraisal-expert/
│       ├── plugin.json
│       ├── agents/re-appraisal-expert.md
│       └── avatars/expert.png
└── outputs/                                      ← 用户可见交付件
    └── 武汉洪山住宅_抵押估价报告.md              ← 测试案例（18/18 合规）
```

## 附录 B：关键决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-07-09 | 技术路线：本地网页 + OSS vendor + 自建 engine.js | 零构建、可离线 |
| 2026-08-03 | 技能体系不生成独立 Web 应用，以 WorkBuddy Skill 形式交付 | 用户需求是 AI 辅助估价，不是独立软件 |
| 2026-08-03 | Excel 输出用 openpyxl 公式驱动而非 Python 硬编码 | 用户可自行修改模板，不依赖 Python |
| 2026-08-03 | 输出目录迁出 `.workbuddy/` | 内置查看器无法渲染该目录下文件 |
| 2026-08-03 | 技能双副本维护（项目级 + 用户级） | 技能索引非实时，需重启生效 |
| 2026-08-03 | 禁用 LaTeX 数学块 | 查看器不渲染 `$$` |
