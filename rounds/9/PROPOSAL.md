# Round 9 PROPOSAL — 修复 Round 8 翻出的 P1-2A/P1-2B 住宅示例链口径缺陷

> 承接：Round 8 HANDOFF（2026-09-01）第四节「迭代建议」P0 项
> 基线 tag：`round9-baseline`（`b042dc8`，即 Round 8 完成点）

---

## 一、引用 Round 8 结论（强制）

Round 8 把数值自洽做成常驻门禁（`tests/test_example_arithmetic.py` + `mutation_harness.py`），
在干净示例上把变异检出率从 93.3% 提升到 100%，并**翻出两处 R7 未收口的同类缺陷**（住宅示例）：

- **P1-2A**：`income.value` chain 节点公式写的是**报酬资本化法**（含 `growth`/`holdingPeriod`/`G23` 裸单元格引用），
  但数据 `methods.income.calculationMode = "directCapitalization"`，且 `crossMethodDifference.analysis` 文本
  **明确拒绝报酬资本化法**（"全剩余寿命模式测算约 146 万元，严重低估…故不采用"）。公式引用了数据中不存在的键 `growthRate`。
- **P1-2B**：`result.totalValue` 节点与 `result.finalTotalValue` 节点**写同一个 target**（R7 P1-1 同形态），
  且用 `ROUND(area×unit)` 反算总价 = 3271738 ≠ 权威加权总价 3271720（差 18 元取整传播）。

两处缺陷**同一根因**：住宅示例的 `calculationChain` 未随 R7 商业示例整改（23466a3）同步。

---

## 二、假设

**修复 P1-2A/P1-2B（与商业示例 R7 整改 + 住宅示例 analysis 文本口径对齐）后，
住宅示例从 `CONTAMINATED` → 干净，变异总数 15 → 27，门禁在两个示例上同样有效。**

| 项 | 内容 |
|---|---|
| 改什么 | ① `income.value` 公式改直接资本化法 `=ROUND({{noi}}/{{rate}},0)`；② `result.totalValue` 节点改 `result.finalUnitValue` 派生单价 `=ROUND({{finalTotal}}/{{area}},0)`，消除 target 冲突 |
| 为什么 | R7 商业示例已用同形态整改（末节点改单价派生自权威总价）；住宅示例分析文本自认证为直接资本化法 3208267 |
| 预期收益 | 消除 R7 遗留盲区；变异总数回到理论最大值 27；验证门禁可复用于第二示例 |
| 风险 | 低——修复方向与估价师已写 analysis 文本 + 商业示例整改一致，**不引入新专业判断**；仅精度对齐（到元） |

**单一变量**：本次只修「住宅示例 chain 与数据口径不符」这一根因，不动其他示例、不动校验器、不动门禁。

---

## 三、度量协议（与 Round 8 完全一致）

1. 修复前：住宅示例 `CONTAMINATED`（基线不洁），变异总数 15/15（住宅被排除）。
2. 修复后：`mutation_harness.py` 全量重跑，预期 27/27、住宅 12/12、无 CONTAMINATED。
3. 门禁：`tests/test_example_arithmetic.py` 全绿；并把 KNOWN_DEFECTS 中两条登记移除（修复后应触发 `fixed` 检测，验证登记会腐烂成免检牌的机制确实工作）。
4. 回归：全量 pytest 不破坏。

---

## 四、中止条件检查

- 未达目标指标：修复后若仍 `CONTAMINATED` 或变异未 100% → 根因分析 + 回滚。
- 连续 3 轮无提升：不适用（本轮是 Round 8 缺陷的确定性收口，非新假设探索）。
