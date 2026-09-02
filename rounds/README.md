# rounds/ — 递归自我改进迭代存档

每轮迭代一个目录（`rounds/N/`），含 PROPOSAL / RESULTS / 差分脚本 / 结果存档，
每轮独立可复现。P1-1 教训（93 例基线档案被原地覆盖丢失）后立本规则。

## 目录

| 轮 | 主题 | 结果 |
|---|---|---|
| 1 | 建差分测试，发现一致率 90.70%（93 例） | 归因 2 根因 + 1 生成器缺口 |
| 2 | C5/C6 自引用跳过 + C6 attempt 语义对齐 + 生成器修复 | 一致率 100%；暴露 c4 条数差 58 例 |
| 3 | Python C4 去重 + 差分测试固化常驻 | 条数 100%（885=885），终止 |
| 4 | P0-1 浮点 attempt 修复 + ghost_fork 对齐 + 固化测试加固（对抗式审查 P0/P1 整改） | 100%；条数 912=912；回归 315 passed |
| 5 | 决策链函数（resolveChain/buildSuccessorShell）差分覆盖扩展 + 消息层机器码 + 证据机制自查常驻 | 函数侧 1000/1000 一致；码级 0 漂移；回归 327 passed |
| 6 | 对抗式审查整改：畸形输入 string-only 对齐 + 码结构化导出 + 存档指纹机制 | 4 漂移全消；21-kind 差分 100%（912=912）；回归 327 passed |
| 7 | oracle 交叉验证（独立实现三方比对）+ schema 层畸形输入断言 + 决策动作/状态机差分 | 三方 0 分歧；343 passed；两处规格未定义分歧已裁决 |
| 8 | 数值自洽协议：校验器泛化 + calculationChain 公式↔target 断言 + 变异测试量化 + pytest 常驻门禁 | 变异检出率 93.3%→100%；覆盖 1/3→3/3；354 passed；翻出 P1-2A/P1-2B 两处 R7 未收口缺陷 |
| 9 | 住宅示例链口径缺陷收口（P1-2A 公式改直接资本化法 + P1-2B 末节点改派生单价消除 target 冲突） | 变异总数 15→27 且两示例均 100%；CONTAMINATED 解除；门禁第二示例验证有效 |
| 10 | 容差退役：删除 `NODE_TOLERANCE["result.totalValue"]=65`（无缺陷编号背书）+ 冻结 fixture 末节点同步 R7 形态；补建 hypotheses.md | 豁免 1→0；变异 27/27 持平（基线/终局字节级相同）；354 passed；审计修正归因（65 系创建日写死非调大）；H11/H12 转下轮 |

## 存档命名规则（P1-1 教训，强制）

### 存档类型（Round 8 起，不止一种）

评估体系不再只有"差分一致率"一个指标，故存档也不再只有一种。类型由文件名决定，
各类型有各自的必需字段——**不允许用差分字段去套变异存档**（那会逼出伪造字段）。

| kind | 文件名 | 必需顶层字段 | 产出者 |
|---|---|---|---|
| diff | `diff_result_roundN[_suffix].json` | seed/count/rate/mismatch_count | `*_diff.py` |
| mutation | `mutation_result_roundN[_suffix].json` | examples/totals(+totals.score) | `tests/mutation_harness.py` |

1. **差分结果按轮次独立命名**：`rounds/N/diff_result_roundN.json`，由
   `diff_check_chain.py --out` 显式指定。**禁止原地覆盖**任何已存在的存档文件。
2. 重跑同一轮产生新证据时，追加后缀区分（如 `diff_result_round4_p0fix.json`），
   不覆盖；旧文件保留即历史。**后缀为单段字母数字**（正则 `_[a-z0-9]+`，
   如 `_p0fix` / `_codes`）——多段（`_codes_rerun`）会被自查红灯
   （Round 6 审查 P2-2 实测踩中）。
3. mismatch 明细、重建证据（如 `rounds/1/EVIDENCE-RECONSTRUCTED.md`）同样按轮次
   归档，随代码一并提交——**只写 stdout 不算存档**。
4. 中间探测脚本用 `tmp_*` 前缀，验证后删除，不入库。
5. **存档指纹**（Round 6 / P1-2 起）：两个差分 CLI 落盘时自动输出存档 sha256，
   当轮 RESULTS.md 须登记（前 16 位即可）。指纹不符 = 内容被覆盖——
   这是机器能抓到的"内容级覆盖"唯一防线。

### 常态化自查（`tests/test_rounds_evidence.py` 已常驻，2026-08-30 Round 5）

规则写在文档里只在"有人记得看"时生效，故上述 1-4 条 + 目录完整性已固化为机器断言：
命名规则在位 / 文件名合规 / 轮次号与目录一致 / 存档可解析且字段完整 /
每轮有 RESULTS.md / 无 tmp_* 残留。

**声明边界（Round 6 审查 P1-2 收窄，勿再越界）**：自查覆盖的是**命名类违规**
（文件名/轮次归属/字段完整性/tmp 残留）——这类 P1-1 复发即红灯；
**内容级原地覆盖**（用合法 JSON 覆盖旧存档，P1-1 原始模式）自查**检测不到**，
防线是第 5 条指纹登记 + git 历史审计。

每轮开始与结束时，人工仍需确认三件机器管不到的事：

- [ ] **开始前**：本轮差分结果准备写到哪个文件名？若与既有存档同名 → 加后缀，别覆盖。
- [ ] **结束时**：本轮的 mismatch 明细 / 重建证据是否随代码一起提交（只写 stdout 不算）。
- [ ] **结束时**：CLI 输出的存档 sha256 是否已登记进当轮 RESULTS.md。

## 与 tests/ 的关系（P2-2 已解耦，2026-08-30）

差分协议的唯一事实源已迁移至 tests/：

- **生成器/分类器**：`tests/diff_chain_generator.py`（gen_case / DIFF_KINDS / classify_py）
- **Node 执行器**：`tests/chain_runner.js`
- **固化回归测试**：`tests/test_diff_chain_consistency.py`（KINDS 由 DIFF_KINDS 派生，去重保序，固化语料序列不变）

`rounds/1/diff_check_chain.py` 保留为 CLI 薄壳（导入 tests/ 的事实源），
历史验证命令 `cd rounds/1 && python diff_check_chain.py --count 1000 --seed 20260828`
继续可用；`rounds/1/chain_runner.js` 为 Round 1 冻结存档（无依赖方，勿改动）。
归档/清理 rounds/ 不再影响正式回归测试。
