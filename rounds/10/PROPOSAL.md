# Round 10 PROPOSAL — 容差退役：删除 `NODE_TOLERANCE["result.totalValue"]=65` 并同步冻结 fixture 末节点形态

> 基线 tag：`round10-baseline`（`8ce8121`，即 Round 9 完成点）
> 回归前置：全量 354 passed + node 32 passed + 变异基线 27/27（本轮开始前已跑，日志 `logs/`）

---

## 〇、冷启动状态摘要（唯一事实源，≤10 行）

1. 最新轮次 = 9，已收口：`round9-done`（8ce8121）= HEAD，变异 27/27，回归 354。
2. **`hypotheses.md` 此前不存在——协议缺口，本轮补建**（登记 H0-H14，H10=本假设）。
3. Round 8/9 对 65 的判断「容差被调大以容纳错误」**部分失实**：git 溯源（659e9e3）显示 65 自文件创建日写死，从未调整；真实机制 = 回乘闭合差上界（面积 128.5㎡ → 上界 ≈ area/2 = 64.25，取整 65）。
4. 但该容差在 R7/R9 整改后**已成为死代码**：两个示例 JSON 均无 `result.totalValue` 节点，唯一被其覆盖的是冻结 fixture `outputs/calculation_chain.json`——18 元 P1-2B 形态错误在其中被 ±65 豁免静默 PASS（变更前 CLI 证据已存档 `logs/cli_values_BEFORE.log`）。
5. H10a（裸单元格审计，R9 输入 2）本轮以零成本证据闭环：两示例 19 节点 0 处裸引用，无需修复。
6. 新翻出两条遗留（不在本轮变量内，已登记）：H11 生成器仍产出旧形态节点；H12 fixture `income.value` 仍是 P1-2A 旧形态（测试以 SKIP 容忍）。

---

## 一、引用上轮结论（强制）

基于 Round 9 的结论（RESULTS.md §三「转 Round 10」+ §四教训 2）：
- 「`NODE_TOLERANCE=65` 审计：该常量把 18 元偏差放过，等于把 P1-2B 类错误合法化」；
- Round 8 教训 5：「提容差是最隐蔽的技术债。容差调整必须有缺陷编号背书，否则等于把 bug 合法化」。

本轮执行审计。审计结果分两半：**来源判断修正**（见摘要 3，非"调大"而是"出生即错"），
**危害判断成立且比预估更重**——它不仅放过错误，还制造**载体分裂**：示例 JSON 已按 R7 形态整改，
冻结 fixture 却留在旧形态靠 65 豁免续命。这正是 R9 教训 1「chain 结构整改必须同步所有载体」的又一次活体证据。

## 二、假设（H10）

**删除 65 豁免 + 把冻结 fixture 末节点同步为 R7 形态（单价派生自权威总价）后：
① 示例与 fixture 的末节点载体统一；② P1-2B 形态错误重新变为可检出（默认容差 ±1、尾节点阈值 1）；
③ 27/27 变异分数与 354 回归不破坏。**

| 项 | 内容 |
|---|---|
| 改什么 | ① `scripts/rebuild_excel_formula.py` 删 `result.totalValue: 65` 条目，剩余两条 ±10 容差补缺陷编号背书（P1-1 事件 + ROUND(...,-1) 十位语义）；② `outputs/calculation_chain.json` 末节点改写为 `result.finalUnitValue`（公式 `=ROUND({{finalTotal}}/{{area}},0)`，target 唯一，与示例 JSON 逐字同形态）；③ `tests/test_schema_v12.py` 两处断言同步；④ `verify_example_arithmetic.py` 中引用 65 的过时注释更新 |
| 为什么 | R8 教训 5（容差须有缺陷编号背书）+ R9 教训 1（整改必须同步所有载体）；65 无缺陷编号、其豁免对象正是 P1-2B 形态错误本身 |
| 预期收益 | 容差合法化外衣消除（18 元错误从静默 PASS → FAIL）；载体统一（示例/测试同形态）；为 H11（生成器同步）铺路——容差删除后生成器若再生成旧形态将被门禁拦截 |
| 风险 | 低。变更可逆（tag `round10-baseline` 已打）；主要风险是 fixture 消费方排查不全 → 已排查（`test_schema_v12.py` 为唯一 Python 消费方；orchestrator fixture 不走 `rebuild_values`） |
| 验证成本 | 极低：本地 3 次变异重跑 + 全量回归 + CLI 前后对比，无外部依赖 |

**优先级** = 收益（消除合法化机制，防 H11 再生成被掩盖）× 置信度（高，变更对象证据链闭合）÷ 成本（极低）→ 高于 H11/H12（后两者需要动生成器/fixture 的 income 节点，变更面更大，留 R11）。

**单一变量**：「末节点旧形态及其无背书容差」一个根因。fixture 改写不是第二个变量——它是同一根因在第二载体上的表现（与 R9 同轮修 P1-2A+P1-2B 一个道理）。**不动**生成器（H11）、**不动** fixture 的 income.value（H12）、**不动**示例 JSON。

## 三、度量协议（与 Round 8/9 完全一致）

1. 修复后：`mutation_harness.py` 重复评估 ×3（均值±std，确定性工具预期 std=0），存档 `mutation_result_round10_final.json`，预期 27/27。
2. 全量回归 pytest（预期 354 passed，不破坏）+ node 测试 32 passed。
3. CLI values 模式前后对比：修复前 `result.totalValue PASS diff=18 (±65)`（已存档），修复后该节点消失、替换为 `result.finalUnitValue` diff=0 (±1)。
4. 门禁 `tests/test_example_arithmetic.py` 全绿。
5. 判定标准：提升幅度小于 2×std → 持平。本轮核心指标是「合法化豁免数 1→0」与「载体形态一致率」，变异分数与回归为不破坏约束。

## 四、预算检查点（每 3 轮核算：R10/R11/R12 周期起点）

- 用户未设硬预算；成本全为本地计算（单轮 <5 分钟），资源充裕。
- **收益递减核算**：变异分数已连续 3 轮（R8-R10）处 100% 上限，「检出率」维度边际收益归零；后续价值来源 = 盲区消除（H11/H12）与机制硬化（H13/H14）。若 R10-R12 连续无实质缺陷消除，触发递归规则：换维度或反向假设。

## 五、中止条件

- 回归破坏 → 立即回滚至 `round10-baseline`，本轮记回退。
- 变异分数 <27 → 根因分析；若因容差删除误伤 → 回滚并证明该容差有正当背书（补编号而非恢复 65）。
