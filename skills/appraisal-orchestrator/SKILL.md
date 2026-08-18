---
name: appraisal-orchestrator
description: >
  估价任务总编排——AI 作为执行主体，在 8 个人工决策点（DP）暂停生成决策包等待估价师判断，
  其余流程连续执行不打断。决策点管理全部在编排层，7 个方法/报告技能保持不变。

  **Perfect for:**
  - 从"用户目标输入"到"报告交付"的完整估价任务编排
  - 需要人工决策点介入的高可控估价流程（固定 DP1-DP4 + 条件 DP-comp/DP-income/DP-cost/DP-hypoth）
  - 决策链管理：驳回后自动创建新 DP（supersedes + attempt），旧 DP 保留为审计记录
  - 生成符合 schema v1.4 的决策包（结论/证据/理由/风险/比较 五段式）

  **Not ideal for:**
  - 单一方法测算（直接用 comps-method 等技能）
  - 纯资料搜集（用 appraisal-data-collection）
  - 单份报告排版（用 appraisal-report）

  **关联**：
  - 决策点规格：《决策点规格定义.md》（六要素 + 决策链模型，本 skill 的实施依据）
  - 设计总纲：《人工决策点架构设计.md》（9 维偏好矩阵）
  - 共享逻辑：`app/js/dp-core.js`（状态机 + 建链纯函数，Node 双模）
  - 人类决策界面：`app/dp-console.html`（决策包渲染 + 决策链可视化 + 决策响应导出）
  - Schema：v1.4（decisionPoint + supersedes/attempt），校验见 scripts/validate_appraisal_json.py
---

## ⚠️ CRITICAL: 编排铁律 (READ FIRST)

1. **决策点管理只在编排层**。绝不修改 7 个技能（appraisal-data-collection / comps-method / income-method / cost-method / hypothetical-dev-method / appraisal-report / web-research-methodology）的 SKILL.md 或工作流。
2. **DP 必须暂停，不可跳过**。到达任一决策点，必须先暂停、生成决策包、等待估价师响应，才能继续。批准/调整/驳回三分支见第四章。
3. **驳回不可修改旧 DP**。`status=rejected` 后旧 DP 为不可变审计记录，只允许创建新 DP 沿 `supersedes` 建链（决策链模型 4.2）。禁止"改回 pending 再改结论"式覆盖。
4. **证据溯源红线**。决策包的每个断言必须能从工程 JSON 结构化字段验证（如面积差 = `property.area − comparableInstances[i].area`）。禁止编造结构化数据中不存在的信息。
5. **提交前校验**。每次生成/更新决策包后运行 `validate_appraisal_json.py`；链式约束 C1-C6 由 `_check_decision_chain()` 强制。

---

## 一、工作流总编排

以"比较法 + 收益法"抵押估价为例（最常见场景）：

```
用户目标输入
  → [DP1] 估价事项确认 (P0, trigger=always)          ← 必须暂停
  → appraisal-data-collection 资料搜集 + 方法预判
  → [DP2] 测算方案确认 (P1, trigger=always)          ← 必须暂停
  → 按方案启动方法测算：
      比较法 comps-method
        → Step 2 选取可比实例完成后
        → [DP-comp] 可比实例选取 (P1, method:comps)   ← 必须暂停（仅 comps.applicable=true 时）
        → Step 3-7 建立比较基础/修正调整/计算价值 + 红线校验
      收益法 income-method
        → 收益率确定后
        → [DP-income] 收益率确定 (P1, method:income)  ← 必须暂停（仅 income.applicable=true 时）
        → 收益价值测算 + 红线校验
  → [DP3] 测算结果审核 (P1, trigger=always)          ← 必须暂停
  → appraisal-report 报告生成
  → [DP4] 报告签发 (P0, trigger=always)              ← 必须暂停
  → 交付
```

**节点间连续执行**：两个 DP 之间 AI 不被打断，自主完成全部中间步骤（数据搜集、测算、红线校验、报告草拟）。用户只描述目标（如"帮我做一份抵押估价报告"），不描述步骤。

**条件 DP 触发规则**：DP-comp / DP-income / DP-cost / DP-hypoth 仅在对应方法 `applicable=true` 且到达规格定义的位置时触发；不采用的方法不产生决策点、不增加打断次数。触发后按《决策点规格定义.md》第三、四节各 DP 的"输入条件/内容模板/输出动作"生成。

---

## 二、决策包生成协议（所有 DP 通用）

### 2.1 五段式结构（按此顺序呈现，结论先行）

```
conclusion  一句话结论（不堆砌信息）
evidence    每条 = item（内容）+ source（信源），可溯源
reasoning   为什么（引用 GB/T 50291-2015 条文 / 方法逻辑）
risks       按错误代价分级 P0/P1/P2，每条含 mitigation
comparison  仅方法特定 DP（DP-comp 等）：逐实例 vs 估价对象差异，必须可从结构化数据溯源
```

### 2.2 证据溯源红线（P1-4 教训）

- `evidence` / `comparison` 中的每个断言必须能从工程文件结构化字段验证（如面积差 = `property.area − comparableInstances[i].area`）。
- **禁止编造**结构化数据中不存在的信息（历史教训：楼层差曾因无法溯源被对抗式审查揪出）。
- 信源等级标注必须与结构化 `sourceGrade` 一致：T0=官方/一手（不动产权证、政府公告、成交登记）；T1=平台/机构（链家、贝壳成交记录）；T2=口头/间接（中介实测、电话询价）。

### 2.3 风险分级与 riskLevel

- P0 = 不可逆/高代价（如四要素错误、用成本法测开发完成后价值——违反 4.5.7 条红线）；P1 = 可修正/中等代价（如修正接近 20% 上限）；P2 = 低风险/监控（如信源 T2 待交叉验证）。
- `riskLevel` 必须 = `risks[]` 中的最高等级（schema P0-7 约束，校验强制）。

### 2.4 决策包写入位置

决策包 = `decisionPoints[]` 中的一个对象（schema `$defs.decisionPoint`）。字段：id/name/phase/trigger/method(条件DP)/riskLevel/status/conclusion/evidence/reasoning/risks/comparison(可选)。呈现给估价师时用五段式（可参考 `app/dp-console.html` 的渲染样式，或直接建议用户打开该页面操作）。

---

## 三、等待人类响应

生成决策包后**暂停**，等待估价师以下任一动作（不得自行假设通过）：

| 动作 | 语义 | 落库 |
|------|------|------|
| 批准 | 接受 AI 推荐内容 | `status=approved` + `humanDecision{action:approved}` |
| 调整 | 内容基本可用，估价师给出修改意见 | `status=modified` + `humanDecision{action:modified, modifications 必填}` |
| 驳回 | 内容不可用，整体否决重做 | `status=rejected` + `humanDecision{action:rejected, comment 必填否决原因}` |

- `humanDecision` 必填 `decidedBy`（估价师姓名）+ `timestamp`（ISO 8601）。
- 调整（modified）与驳回（rejected）边界由估价师按问题严重度判断，AI 不代做决定（《决策点规格定义.md》1.3）。
- 无 `humanDecision` 交互界面时（纯对话模式），在回复中呈现五段式决策包 + 三个动作选项，等待用户明确选择。

---

## 四、响应处理：三分支状态机

```
                ┌── approved（终结）→ 按 DP 的"批准后"动作继续执行
pending ────────┼── modified（终结）→ 落地 modifications 后继续；不产生新 DP
                └── rejected（非终结）→ 自动建链生成新 DP → pending → 重新呈现决策包
```

### 4.1 approved → 继续

按《决策点规格定义.md》各 DP 输出动作表的"approved"分支继续（如 DP-comp approved → 进入 Step 3 建立比较基础）。写入 `humanDecision` 后立即继续，不重复确认。

### 4.2 modified → 落地，不建链

1. 解析 `modifications`（如"实例 B 换为同小区 D；权重 0.6/0.4"）。
2. AI 落地修改（换实例/调权重/调参数/改报告段落），重新计算相关结果。
3. 更新原 DP：`status=modified` + `humanDecision{action:modified, modifications}`。
4. **不创建新 DP**（1.3 语义：局部修正即定稿）。
5. 继续执行。若估价师再次提出修改，仍在原 DP 上更新（不新建）。

### 4.3 rejected → 自动建链（核心）

按《决策点规格定义.md》第四章决策链模型执行：

1. 标记旧 DP：`status=rejected` + `humanDecision{action:rejected, comment: 否决原因}`。**旧 DP 保留，禁止修改/删除其他内容**（审计证据，GB/T 50291 过程可追溯）。
2. 创建新 DP：
   - `id` = 基础 id + `-` + 尝试序号（`DP-comp` → `DP-comp-2` → `DP-comp-3`；`DP1` → `DP1-2`）
   - `attempt` = 被取代 DP 的 attempt（缺失视作 1）+ 1
   - `supersedes` = 被取代 DP 的 id
   - `status` = `pending`
   - 其余标识字段复制（name/phase/trigger/method/riskLevel）
   - 五段式内容**必须重写以回应否决原因**（4.2 规则 5）：conclusion 更新；evidence 补充或更换；原风险项标注 mitigation 状态；comparison 同步更新
3. 将新 DP 追加到 `decisionPoints[]`，重新生成决策包呈现给估价师，等待响应。
4. 链式约束 C1-C6 由校验强制（见第六章）；骨架可用 `app/js/dp-core.js` 的 `buildSuccessorShell()` 计算（浏览器/Node 双模）。

**回应否决原因示例**（DP-comp rejected "实例 C 信源 T2 不可靠，换同小区实例"）：

```
DP-comp-2:
  conclusion: "推荐选取实例 A/B/D（3 个），D 为同小区 2026-07 成交，信源 T1"
  evidence:   [A, B 不变, D: "成交 2026-07-10, 25100 元/m², 链家成交记录 (T1)"]
  reasoning:  "已替换信源 T2 的实例 C 为同小区 T1 实例 D（回应否决原因）"
  risks:      [{description: "实例 B 区位修正 18%", level: P1, mitigation: "接近 20% 上限，密切关注"},
               {description: "实例 D 楼层差 5 层", level: P2, mitigation: "楼层修正系数量化"}]
```

---

## 五、决策点管理（编排层专属，不动技能）

| 管理职责 | 编排层动作 | 技能是否参与 |
|---------|-----------|:---:|
| DP 触发判断 | 按规格六要素（trigger/phase/暂停位置）判断是否暂停 | 否 |
| 决策包生成 | 按五段式 + 输入条件（schema JSONPath）生成 | 否 |
| 响应收集 | 等待估价师 approved/modified/rejected | 否 |
| 落地执行 | approved 继续 / modified 落地 / rejected 重生成 | 部分（重算走方法技能） |
| 决策链维护 | 驳回建链、attempt/supersedes 写入、C1-C6 自检 | 否 |
| 决策历史 | `decisionPoints[]` 随工程 JSON 保存 | 否 |

方法技能（comps/income/cost/hypoth/report/data-collection）只负责各自测算/搜集/报告，**不感知决策点存在**。技能输出 JSON 后，编排层在暂停位置插入决策包，再决定继续或重算。

---

## 六、决策链校验与自检

生成/更新 `decisionPoints[]` 后，运行：

```bash
python scripts/validate_appraisal_json.py <工程.json>     # 全量校验（schema + 业务 + 红线）
python scripts/validate_appraisal_json.py --fragment decisionPoints <文件>  # 仅决策点
```

链式约束 C1-C6（`_check_decision_chain()` 强制，前端 JS 等价实现 `DPCore.validateChain()`）：

| # | 约束 | 违规示例 |
|---|------|---------|
| C1 | `supersedes` 引用的 id 必须存在 | 引用不存在的 DP |
| C2 | 不得自引用 | DP 的 supersedes 指向自己 |
| C3 | 被取代的 DP 必须 `status=rejected` | 取代一个 approved 的 DP |
| C4 | 1:1 后继（防分叉） | 两个 DP 都 supersedes 同一 DP |
| C5 | 不得成环 | A→B→A |
| C6 | `attempt` 一致性（若提供须 = 前驱 attempt+1） | 前驱 attempt=1 而新 DP attempt=3 |

**AI 自检清单**（每次决策后）：
- [ ] 五段式齐全且结论先行；`riskLevel` = risks 最高级（P0-7）
- [ ] evidence/comparison 全部可溯源，sourceGrade 与结构化一致
- [ ] `status` 与 `humanDecision.action` 一致（P0-6a/b/c）；modified 有 modifications（P0-2）
- [ ] 驳回后：旧 DP 未改、新 DP 已建链、attempt 递增、内容回应否决原因
- [ ] 校验脚本通过（schema + C1-C6）

---

## 七、人类决策界面（可选但推荐）

`app/dp-console.html`（浏览器双击打开，零构建离线）提供完整决策界面：

1. **载入示例 / 打开工程 JSON**：加载含 `decisionPoints` 的工程文件。
2. **决策链可视化**：SVG/卡片式链（DP-comp [rejected] → DP-comp-2 [approved]），风险等级 P0 红 / P1 橙 / P2 灰。
3. **决策包渲染**：结论优先，证据/理由/风险（颜色编码）/比较逐段呈现。
4. **批准 / 调整 / 驳回按钮**：调整强制填 modifications；驳回强制填否决原因并预览将创建的后继 DP（id/supersedes/attempt）。
5. **导出决策响应 JSON**：把人类决策写回 `decisionPoints[]` 后导出，AI 读取继续执行（approved 继续 / modified 落地 / rejected 重生成）。

共享逻辑 `app/js/dp-core.js`（Node 双模，`node --test tests/test_dp_core.js` 可自测）：`applyDecision()` 状态机转换、`buildSuccessorShell()` 建链骨架、`validateChain()` C1-C6、`resolveChain()` 链解析。编排层在对话模式下手动建链时，可先在 Node 中调用验证。

---

## 八、典型场景速查

| 场景 | 决策链 | 说明 |
|------|--------|------|
| 顺利流程（比较法+收益法） | DP1→DP2→DP-comp→DP-income→DP3→DP4 | 6 DP 无迭代 |
| DP-comp 驳回一次 | DP-comp [rejected] → DP-comp-2 [approved] | 7 DP，含完整决策链 |
| DP1 驳回（四要素错误） | DP1 [rejected] → DP1-2 [approved] | 重述目标后重生成 |
| modified 局部修正 | DP 直接更新为 modified | 不产生新 DP |

完整规格（触发条件/内容模板/输入条件/输出动作逐 DP）：见《决策点规格定义.md》。本 skill 与规格文档如有出入，以规格文档为准。
