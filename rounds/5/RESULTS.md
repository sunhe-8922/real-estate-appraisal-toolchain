# Round 5 RESULTS — 决策链函数（resolveChain / buildSuccessorShell）差分覆盖扩展

> 日期：2026-08-30 | 输入：`outputs/HANDOFF-2026-08-30-round4.md` 假设池 #10 / 审查未检查边界
> 前提修正：**这两个函数在 Python 端没有生产实现**，因此"双端差分"的第二端改为
> 按《决策点规格定义》4.2 独立写的参考实现（oracle），见 `tests/dp_chain_oracle.py`。

## 一、做了什么

| 件 | 位置 | 说明 |
|---|---|---|
| 分层生成器 | `tests/chain_shapes.py` | 22 个形状 kind（链/环/分叉/ghost/浮点 attempt/富字段/重复 id/weird id/null/空/外部 DP…），`SHAPE_KINDS` 与 validateChain 的 `DIFF_KINDS` **刻意分开**（避免扰动 885/912 固���语料，Round 4 R7） |
| Node 执行器 | `tests/dp_chain_runner.js` | 输出规范形态：resolve（byId/roots/chains，只留 id）+ successor（ok/机器码/全字段，去 undefined） |
| 参考实现 | `tests/dp_chain_oracle.py` | 按规格 4.2 独立实现，纪律：不照抄 JS 代码，分歧即发现 |
| 固化测试 | `tests/test_dp_chain_vs_oracle.py` | 四断言：① resolveChain 一致 ② buildSuccessorShell 一致 ③ 每 kind 触发 ④ 规格直译锚点（9 条手写期望） |
| 差分 CLI | `tests/dp_chain_diff.py` | 与 validateChain 侧对称，常驻 tests/（P2-2 后脚本不进 rounds/） |

## 二、结果

| 指标 | 值 |
|---|---|
| 双端一致率（N=1000，seed 20260830，22 kind） | **1000/1000 = 1.0000** |
| 分支覆盖 | OK / C3 / C4 / C5 / E_DP_NO_ID 全部命中；chains 长度 0/1/2 均出现 |
| 固化测试 | 4 passed（语料 300 例 + 9 条锚点） |
| 回归 | Python 319 passed / Node 32 pass |

## 三、发现（F1–F4）

**F1：`buildSuccessorShell` 的 C5 分支对多节点环不可达（防御性代码）**
环中每个节点必有一个后继，所以对环上任一点建链，C4（防分叉）检查都先命中；
C5 只在**自引用**（`dp.supersedes === dp.id`）场景触发。当前实现无缺陷（顺序合理），
但若将来调整 C4/C5 检查顺序，C5 会从"死代码"变成活跃分支——改动前必须重跑本差分。

**F2：`resolveChain` 遇分叉会静默丢弃第二个后继**
一个 DP 有两个后继时，只取数组中第一个进 chains；第二个后继既有 supersedes（不成 root）
又不进任何链 → 可视化里彻底消失。当前由 `validateChain` 的 C4 兜底报错，可接受，
但**若 C4 未来被放宽，可视化就会出现静默丢数据**。已在 oracle 文档字符串记录为已知行为。

**F3：浮点 attempt 下 successor.id 的数字渲染**
schema 规定 `attempt` 为 integer ≥1，浮点属越界输入。JS 拼接时 `2.0 + 1 = 3.0` 渲染为 `"3"`
→ id 为 `DP-a-3`（2.5 则为 `DP-a-3.5`）。Python 侧用 `str(3.0)` 会得到 `"3.0"`，
故 oracle 用 `_js_num()` 复现 JS 渲染语义（已注释说明）。双端一致。

**F4：语料"覆盖了"但没有真覆盖（方法论教训）**
首版 `attempt_float` 形状的 `dpIndex` 恒落在已有后继的节点上 → 100% 被 C4 拦截，
浮点 id 渲染路径**一次都没执行**。修正后（单节点无后继 + `_pick_rejected` 三路混合
选点：40% 末个 rejected / 30% 数组尾部 / 30% 随机）才真正覆盖到 OK 路径。
**教训：覆盖率要按「kind × 结果分支」统计，不能只看 kind 是否触发**——
本轮 CLI 的分布输出（`outcome_distribution`）就是为把这类盲点显性化。

## 四、声明边界（Round 4 R1 教训：不许越界声明）

本轮证明的是「**JS 实现 ≡ 规格参考实现**」，**不是**「JS ≡ Python 生产实现」——
后者目前不存在。若未来 Python 端补上生产实现（假设池候选），需重跑本差分并重新界定声明。
此外：oracle 由同一作者按同一份规格写成，存在"共同误解规格"的残留风险，
故第 ④ 组锚点刻意写成不依赖 oracle 的手工期望值（从规格直译），作为独立的第二重校验。

## 五、证据

- `rounds/5/diff_result_round5.json`：决策链函数侧 N=1000 完整存档（一致率、分支分布、mismatches 全量）。
- `rounds/5/diff_result_round5_codes.json`：validateChain 侧 N=1000 存档（码级比对生效后）。
- 复跑：`python tests/dp_chain_diff.py --count 1000 --seed 20260830 --out <file>`

---

## 六、同轮并行完成的两项（交接文档「下一步」第 2-4 条）

### 6.1 CLI 薄壳 NODE 路径可移植化（下一步 #2）

`rounds/1/diff_check_chain.py` 的 NODE 常量原先硬编码本机受管路径（换机即失效），
现改为 `WORKBUDDY_NODE` 环境变量 → PATH 探测 → 硬编码兜底；解析逻辑收敛到
`tests/diff_chain_generator.find_node()`（单一事实源，CLI 与固化测试共用，
测试侧原有的私有 `_find_node()` 已删除）。

### 6.2 证据机制常态化自查（下一步 #3）

新增 `tests/test_rounds_evidence.py`（6 项常驻断言）：命名规则文档在位 /
文件名合规 `diff_result_roundN[_suffix].json`（`rounds/1/diff_result.json` 为
P1-1 事故遗留白名单）/ 轮次号与目录一致 / 存档可解析且字段完整 /
每轮有 RESULTS.md / 无 tmp_* 残留。**规则由"有人记得看"变成"红灯即失败"。**
`rounds/README.md` 另补人工自查清单两件（机器管不到的部分）。

### 6.3 消息层机器可比对编码（下一步 #4，假设池 #6）

双端违规统一为 `C<n>:key=<id>` 码：

| 端 | 改动 |
|---|---|
| Python | `_make_error(..., code=...)`，C1-C6 六处挂码（`C4:key=DP-comp`）；**人类可读文案不变**，报告/命令行输出零影响 |
| JS | 消息前缀由 `C4: …` 改为 `C4:key=DP-comp: …`（Node 测试只做 `/C1/` 正则、`dp-console.html` 只显示计数，均不受影响） |

连带收益：Python 端分类**不再靠关键词猜文本**（原 `classify_py` 用
"只能被一个后继取代"等子串匹配），改由 `error.code` 精确派生；
差分新增两条断言——①b 违规码（含 key）逐一一致、①c 每条违规都必须带 key 码。
validateChain 侧 N=1000 复跑：类别 100% / **违规码 0 不一致** / 条数 912=912。

### 6.4 回归基线（2026-08-30 实测）

| 指标 | 值 |
|---|---|
| Python 全量 | **327 passed**（315 + 决策链函数 4 + 证据自查 6 + 码级 2） |
| Node 全量 | **32 pass / 0 fail** |
| validateChain 差分 N=1000 | 100% / 码级 0 漂移 / 912=912 |
| 决策链函数差分 N=1000 | 1000/1000 一致 |

