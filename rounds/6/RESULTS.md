# Round 6 RESULTS — 对抗式审查（Round 5 报告）整改

> 日期：2026-08-30 | 输入：`outputs/对抗式审查-决策链差分与机器码-20260830.md`（0 P0 / 2 P1 / 3 P2）
> 继承：Round 5（`rounds/5/RESULTS.md`）

## 假设 → 动作 → 结果

| # | 假设/发现 | 动作 | 结果 |
|---|---|---|---|
| 1 | P1-1：畸形输入双端漂移 ×4（Python 类型防御弱于 JS string-only） | Python 5 处：by_id/supersedes 收紧 `isinstance(str)`、C5 先验 dp_id 为 str（**只包 C5 不用 continue**——JS 端 C6 对缺 id 的 dp 照查，continue 会破坏 C6 对齐）、C2/C6 key 哨兵 `_code_key()`（`<no-id>`）；JS 端 `validateChain` 重构为 `validateChainEntries` 同源生成，新增**结构化导出** `validateChainCodes`（码不再从消息文本解析——含冒号 key 的歧义根修） | 4 探针全 OK；`num_supersedes`/`no_id`/`colon_id` 3 kind 入库（DIFF_KINDS 18→21）+ 固化锚点 4→7 且升级为**码级断言** |
| 2 | P1-2：自查声明超覆盖（内容级覆盖检测不到） | 两个差分 CLI 落盘即输出存档 sha256；README 声明收窄（命名类红灯 / 内容级靠指纹+git 审计）；本轮起 RESULTS 登记指纹 | 见下方指纹表 |
| 3 | P2-1/P2-2：锚点计数 9 实为 8；后缀单段约束未文档化 | RESULTS 勘误（9→8，两处）；README 补后缀规则说明 | 完成 |
| 4 | P2-3：oracle 独立性不可机械验证 | 列入下轮假设池（换实现者重写 oracle 交叉验证），见 `outputs/HANDOFF-2026-08-30-round4.md` §4.2 | 已登记 |

## 回归基线（2026-08-30 实测）

| 指标 | 值 |
|---|---|
| Python 全量 | **327 passed**（测试函数数未变；锚点与语料增强不新增函数） |
| Node 全量 | **32 pass / 0 fail** |
| validateChain 差分 N=1000（21 kind） | 100% / 码级 0 / 912=912（语料含新 kind 后总数不变，双端相等为硬断言） |
| 决策链函数差分 N=1000 | 1000/1000（内容与 Round 5 存档逐位一致，见指纹表） |

**R7 提示**：DIFF_KINDS 18→21 改变了抽样序列——"912 不变"属巧合而非不变量，
后续以"双端一致 + 条数双端相等"为断言，勿以总数不变为断言。

## 存档指纹（P1-2 机制首次应用）

| 存档 | sha256（前 16 位） | 备注 |
|---|---|---|
| `diff_result_round6.json`（validateChain，21 kind） | `63b458703551b283` | 本轮整改后语料 |
| `diff_result_round6_dpchain.json`（决策链函数） | `4018844cd591df34` | 与 `rounds/5/diff_result_round5.json` 同指纹——函数侧零改动，重放逐位一致（确定性旁证） |

## 遗留

- **P2-3（假设池）**：换实现者/换会话重写一版 `dp_chain_oracle.py` 做交叉差分，对冲"同一作者按同一份规格写成"的共同误解风险。
- 畸形输入的 schema 层验证（缺 id / 数值 supersedes 在 schema 即拦截）未逐一断言——validateChain 直调路径已由本轮固化锚点覆盖，schema 路径属既有测试域。
- 未检查边界延续：`applyDecision`/`isTerminal`/状态机、`dp-console.html` 浏览器实测。
