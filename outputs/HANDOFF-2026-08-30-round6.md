# 任务交接文档 — 2026-08-30 Round 5-6（差分扩展 + 机器码 + 审查整改）

> **生成时间**：2026-08-30 17:25
> **继承自**：`outputs/HANDOFF-2026-08-30-round4.md`（其「下一步 1-4」已全部完成并整改完毕，见本文）
> **状态**：假设池 #6（消息层机器码）/ #10（决策链函数差分）已落地；Round 5 对抗式审查（0 P0 / 2 P1 / 3 P2）发现的问题**已全部整改**；提交 `2e99ca3` / `675a0f2` / `d2b0328` 均已推送（`ls-remote` 复核远程 = 本地 HEAD `d2b0328`）
> **前置文档**：`outputs/对抗式审查-决策链差分与机器码-20260830.md`（审查证据）、`rounds/5/RESULTS.md`、`rounds/6/RESULTS.md`、`rounds/README.md`、`decisions.md` D-011~D-014
> **用途**：作为下一个相关任务的唯一输入，**不依赖任何对话上下文**

---

## 一、已完成的功能点

### 1.1 决策链函数差分扩展（假设池 #10，D-012）

`resolveChain` / `buildSuccessorShell` 原先只有 JS 单端实现 + 手写断言，零机械验证。
**前提修正**：Python 端没有这两个函数的生产实现，"双端差分"没有第二端——按 sun 裁定，
按《决策点规格定义》4.2 **独立写规格参考实现**作 oracle（`tests/dp_chain_oracle.py`，
仅测试用；文件头纪律：按规格实现、禁止照抄 JS，否则退化为恒真断言）。

四件套：`tests/chain_shapes.py`（22 形状 kind，与 validateChain 的 `DIFF_KINDS` 刻意分开，
避免扰动固化语料）+ `tests/dp_chain_runner.js` + oracle + `tests/test_dp_chain_vs_oracle.py`
（四断言：resolveChain 一致 / buildSuccessorShell 一致 / 每 kind 触发 / 8 条规格直译锚点）+
`tests/dp_chain_diff.py`（CLI）。**N=1000 → 1000/1000 逐字段全等。**

差分即发现（F1–F4，详见 `rounds/5/RESULTS.md`）：
- **F1**：`buildSuccessorShell` 的 C5 分支对多节点环**不可达**（C4 先命中），仅自引用可达——防御性代码，改检查顺序前必须重跑差分；
- **F2**：`resolveChain` 遇分叉**静默丢弃第二个后继**（不进 chains 也不成 root），现靠 C4 兜底；
- **F3**：浮点 attempt（越界输入）下 successor.id 按 JS 数字渲染（2.0→"3"），oracle 用 `_js_num()` 同构；
- **F4**：语料盲点——`attempt_float` 的 dpIndex 恒落有后继节点 → 100% 被 C4 拦截，浮点路径从未执行。**教训：覆盖率按 kind × 结果分支统计，CLI 的分布输出就是为显性化这类盲点。**

### 1.2 消息层机器码（假设池 #6，D-011 → D-013 演进）

双端违规统一为 `C<n>:key=<id>` 机器码。Round 6 起码升级为**结构化导出**：
- Python：`_make_error(..., code=...)`，C1-C6 六处挂码（`C4:key=DP-comp`），**人类可读文案一字未改**（报告/命令行输出零影响）；
- JS：`validateChain` 重构为 `validateChainEntries` 同源生成 `{code, message}`，新增导出 `validateChainCodes`；执行器（`chain_runner.js`）改用码源、**彻底放弃消息文本解析**——含冒号等特殊字符的 key 不再有歧义；
- 分类器 `classify_py` 由码派生（删除关键词子串匹配）。

### 1.3 畸形输入类型语义对齐（审查 P1-1 整改，D-013）

审查实测 4 处双端漂移（数值 supersedes / 缺 id 假阳性 C5 / key 渲染 None vs undefined / 冒号 key 截断），全部修复：
- Python：by_id / supersedes 收紧 `isinstance(str)`（对齐 JS string-only）；C5 先验 dp_id 为 str（**只包 C5 块，不能用 continue——JS 端 C6 对缺 id dp 照查**）；码层 key 哨兵 `_code_key()`（非字符串 id → `<no-id>`，与 JS `codeKey()` 同构）；
- 畸形形状入库：`num_supersedes` / `no_id` / `colon_id` 3 kind（DIFF_KINDS 18→21）+ 固化锚点 4→7，且锚点升级为**类别 + 违规码 + 条数三重断言**。

### 1.4 证据机制（审查 P1-2 整改，D-014）

- `tests/test_rounds_evidence.py`（Round 5 建，6 项常驻断言）：命名规则在位 / 文件名合规 / 轮次号=目录号 / 存档可解析且字段完整 / 每轮 RESULTS.md / 无 tmp_* 残留；
- **存档指纹**（Round 6 补）：两个差分 CLI 落盘即输出 sha256，当轮 RESULTS 登记前 16 位，指纹不符 = 内容被覆盖；
- **声明已收窄**（勿再越界）：自查只覆盖**命名类违规**；**内容级原地覆盖**（P1-1 原始模式，用合法 JSON 覆盖旧档）检测不到——防线是指纹登记 + git 历史审计（审查伪造实验实证）。

### 1.5 其他

CLI 薄壳 NODE 路径可移植化（`WORKBUDDY_NODE` → PATH → 兜底，解析收敛到 `tests/diff_chain_generator.find_node()` 单一事实源）。

### 1.6 测试基线（2026-08-30 实测，当前权威值）

| 指标 | 值 |
|---|---|
| Python 全量 | **327 passed** |
| Node 全量 | **32 pass / 0 fail** |
| validateChain 差分 N=1000（21 kind） | 100% / 违规码 0 不一致 / 912=912 |
| 决策链函数差分 N=1000（22 kind） | 1000/1000 |
| 固化锚点 | validateChain 侧 7 条 + oracle 侧 8 条，全部双端一致 |

---

## 二、未解决的问题

| # | 项 | 说明 |
|---|---|---|
| 1 | **oracle 独立性（P2-3，已入假设池 #9）** | "按规格独立实现、未照抄 JS"无法机械验证，只有文件头纪律声明 + 锚点对冲，中置信。建议换实现者/换会话重写一版 oracle 做交叉差分 |
| 2 | **无 Python 生产实现** | `buildSuccessorShell` / `resolveChain` 的 oracle 只是测试件；若编排层/命令行需要这两个能力，需先确认需求再落地生产实现——届时差分声明可从「JS ≡ oracle」升级为「JS ≡ Python 生产实现」 |
| 3 | **畸形输入的 schema 层断言** | 缺 id / 数值 supersedes 在 schema 即拦截的行为未逐一断言（validateChain 直调路径已由固化锚点覆盖）→ 假设池 #10 |
| 4 | **未检查边界（延续）** | `applyDecision` / `isTerminal` / 状态机部分从未做差分；`dp-console.html` 仅核对调用点与渲染方式（只显示计数，码前缀对 UI 零影响），未做浏览器实测 |
| 5 | **历史遗留（自 HANDOFF-2026-08-24）** | 真实对话演练（编排层）、固定 DP 浏览器验证、多方法工程示例、R2 redLineChecks 语义、git 历史 PII 方案 B/C——状态未变 |
| 6 | **工作区其他会话改动** | `CLAUDE.md`（已修改）、`outputs/CLAUDE.md`（未跟踪，双副本问题）、格力海岸 3105 产物 7 个未跟踪文件——与本任务无关，历次提交均已排除，待 sun 指令 |

---

## 三、需要注意的风险

| # | 风险 | 应对 |
|---|------|------|
| R1 | **"100% 一致"的声明边界（最重要）**：当前证明的是「JS validateChain ≡ Python `_check_decision_chain`」（21 kind 语料 + 7 锚点）+「JS 决策链函数 ≡ 规格参考实现」（22 kind + 8 锚点）。**不是**「JS ≡ Python 生产实现」（后者不存在），也未覆盖 `applyDecision`/状态机 | 任何一致性声明必须写明：哪些函数、对面是谁、语料范围。扩展覆盖后再提高声明 |
| R2 | **kind 清单变更会改变差分抽样序列**：总数随之变化（885→912→912，最后一次"不变"属巧合而非不变量） | 断言只写"双端一致 + 条数双端相等"；做"总数不变"验证前先确认清单未变 |
| R3 | **指纹机制的局限**：sha256 由 CLI 输出、RESULTS 登记是**人工层**，没有机器断言"指纹已登记/相符"；漏登记则退化回 git 审计 | 每轮 RESULTS 必须登记（README 自查清单第 3 项）；下轮可考虑把指纹校验做成测试 |
| R4 | **依赖方向**：`rounds/1/diff_check_chain.py`（CLI 薄壳）依赖 `tests/` 事实源——重构 tests/ 后须跑一次 CLI 冒烟 | 已在 rounds/README 记录 |
| R5 | **C6 对缺 id dp 仍报警**（双端一致地报 `C6:key=<no-id>`）：这是修复后的**有意行为**（JS 原本就查），消息文本里 id 渲染为 undefined 属正常 | 勿"顺手"改成跳过——会破坏与 JS 的对齐 |
| R6 | **git 推送网络不稳**（今日两次阻塞：Connection reset / SSL 握手失败 / 超时） | 推送后必须 `git ls-remote origin master` 对比本地 HEAD（远程跟踪引用不持久，勿信 `git status` ahead/behind） |
| R7 | **沙箱跨目录写静默失败 + mv/rm 报错与实际生效不一致**（今日实测：`--out` 写跨目录绝对路径失败、写 cwd 正常） | 产物先写 cwd 或项目内，写/移/删后 `ls` 二次确认 |
| R8 | **工作区其他会话改动**（见二.6） | 提交时显式列出文件路径，勿用 `git add .` |

---

## 四、后续迭代建议（按优先级）

1. **oracle 交叉验证**（假设池 #9）：换实现者/换会话独立重写 `dp_chain_oracle.py`，与现有 oracle 互差 + 与 JS 三方差分——消除"共同误解规格"残留风险。
2. **schema 层畸形输入断言**（假设池 #10）：缺 id / 数值 supersedes / 非字符串 attempt 在 schema 的拦截行为逐一测试，与 validateChain 层的固化锚点形成双层防线。
3. **差分扩展到 `applyDecision` / `isTerminal` / 状态机**：validateChain 与两个建链函数已覆盖，决策点核心逻辑剩这两块零机械验证。
4. **Python 生产实现评估**：若编排层确需在命令行侧建链/解析，把 `buildSuccessorShell`/`resolveChain` 落到 `scripts/`（可直接以 oracle 为底），声明随之升级；**需 sun 确认需求后立项**。
5. **前端可选用码**：`dp-console.html` 若要按码分类显示违规，可直接消费 `validateChainCodes`，无需解析文本。
6. **历史遗留**（二.5）与 `outputs/CLAUDE.md` 双副本决策——均等 sun 指令。

---

## 五、验证命令

```bash
# Python 全量（327/327）
python -m pytest tests/ -q

# Node 全量（32/32）
node --test tests/test_dp_core.js tests/test_e2e_orchestrator.js

# validateChain 差分（固化版 N=300 + 码级断言；无 node 自动 skip）
python -m pytest tests/test_diff_chain_consistency.py -v

# 决策链函数差分（oracle 版固化测试）
python -m pytest tests/test_dp_chain_vs_oracle.py -v

# 存档证据自查（6 项）
python -m pytest tests/test_rounds_evidence.py -v

# 差分 CLI（完整版；注意 R7——--out 写 cwd 内路径）
cd rounds/1 && python diff_check_chain.py --count 1000 --seed 20260828 --out diff_result_roundN.json
python tests/dp_chain_diff.py --count 1000 --seed 20260830 --out <file>.json

# 远程同步核对（勿信 git status 的 ahead/behind）
[ "$(git ls-remote origin master | cut -f1)" = "$(git rev-parse HEAD)" ] && echo 已推送
```

---

## 六、交付物清单（本任务周期：2026-08-30 下午）

| 文件 | 类型 | 提交 |
|---|---|---|
| `tests/chain_shapes.py` / `tests/dp_chain_runner.js` / `tests/dp_chain_oracle.py` / `tests/test_dp_chain_vs_oracle.py` / `tests/dp_chain_diff.py` | 新增：决策链函数差分四件套 + CLI | `2e99ca3` |
| `tests/test_rounds_evidence.py` | 新增：存档证据自查（6 项断言） | `2e99ca3` |
| `scripts/validate_appraisal_json.py` | 修改：code 字段（R5）+ string-only/C5 先验/key 哨兵（R6） | `2e99ca3` + `d2b0328` |
| `app/js/dp-core.js` | 修改：消息码前缀（R5）→ `validateChainEntries`/`validateChainCodes` 结构化导出（R6） | `2e99ca3` + `d2b0328` |
| `tests/chain_runner.js` / `tests/diff_chain_generator.py` / `tests/test_diff_chain_consistency.py` | 修改：码源结构化 / DIFF_KINDS 18→21 / 码级+锚点断言 | `2e99ca3` + `d2b0328` |
| `rounds/1/diff_check_chain.py` | 修改：NODE 可移植化 + 码级比对 + sha256 输出 | `2e99ca3` + `d2b0328` |
| `rounds/5/`（RESULTS + 2 存档）、`rounds/6/`（RESULTS + 2 存档） | 新增：迭代结果与差分存档（含指纹登记） | `2e99ca3` + `d2b0328` |
| `rounds/README.md` | 修改：后缀约束 / 声明收窄 / 指纹规则 / 轮次表 | `2e99ca3` + `d2b0328` |
| `outputs/对抗式审查-决策链差分与机器码-20260830.md` | 新增：审查报告（0 P0 / 2 P1 / 3 P2） | `675a0f2` |
| `decisions.md`（D-011~D-014）/ `CHANGELOG.md` / `intent.md`（基线 327） | 修改 | `2e99ca3` + `d2b0328` |
| `outputs/HANDOFF-2026-08-30-round6.md` | 新增：本交接文档 | 随本次提交 |

---

## 七、Git 状态

```
本轮提交链（3 笔，均已推送）:
  2e99ca3 feat(chain): 决策链函数差分扩展 + 消息层机器码 + 证据自查（Round 5）
  675a0f2 docs(review): Round 5 对抗式审查报告（0 P0 / 2 P1 / 3 P2）
  d2b0328 fix(chain): 畸形输入语义加固 + 存档指纹（Round 6 整改）
远程核对: git ls-remote origin master = d2b0328（2026-08-30 17:22 实测）
tag: round0-baseline / round3-done 均在远程（Round 4 推送）
工作区: 其他会话未提交改动仍在（R8）——本轮所有提交均显式排除
```

---

*本交接文档独立于对话上下文。接手者凭本文档 + `outputs/对抗式审查-决策链差分与机器码-20260830.md` + `rounds/5..6/` + `rounds/README.md` 可恢复全部任务状态；更早历史见 `outputs/HANDOFF-2026-08-30-round4.md` 及其继承链。*
