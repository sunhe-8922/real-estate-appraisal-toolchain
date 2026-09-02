# Round 10 RESULTS — 容差退役：`NODE_TOLERANCE["result.totalValue"]=65` 删除 + 冻结载体形态同步

> 日期：2026-09-02 | 基线 tag：`round10-baseline`（`8ce8121`）
> 承接：Round 9（§三转办 + 教训 1/2），Round 8（教训 5）

---

## 〇、一句话结论

**采纳，结构性收口**。65 容差的「被调大」叙事被 git 溯源**证伪一半**（自创建日写死、从未调整），
但其**危害判断成立且比预估更重**——它是 P1-2B 形态错误的豁免外衣，并制造载体分裂。
删除后：合法化豁免 1→0，示例 JSON/冻结 fixture/测试断言三载体末节点形态统一，
变异 27/27 与回归均不破坏（基线与终局存档字节级相同 = 检出能力零扰动）。

## 一、审计发现（先审计后动手，本轮核心增量）

1. **溯源修正（推翻 R8/R9 的归因）**：`git log -S NODE_TOLERANCE` 显示 65 出自 `659e9e3`（v1.2 创建），
   从未被调整。真实机制可重算：回乘闭合差上界 = 面积/2 = 128.5/2 = 64.25 → 取整 65。
   **错误不在"调大"，在出生即豁免了一个本不该存在的口径**。
2. **死代码 + 豁免活靶**：R7/R9 整改后两示例 JSON 均无 `result.totalValue` 节点，65 唯一覆盖对象
   = 冻结 fixture `outputs/calculation_chain.json`——其旧形态节点 `ROUND(面积×单价)` 差 18 元被 ±65
   豁免静默 PASS（变更前证据 `logs/cli_values_BEFORE.log`）。
3. **载体分裂活体证据**（R9 教训 1 复发形态）：示例 JSON 已整改，冻结 fixture 与生成器
   `extract_calculation_chain.py` 仍是旧形态。后两者登记为 H11/H12，不在本轮变量内。
4. **H10a（裸单元格审计）零成本闭环**：两示例 19 个节点公式 0 处裸单元格引用（G23 已随 R9 消除）。

## 二、变更明细（单一变量：末节点旧形态及其无背书容差）

| # | 文件 | 变更 |
|---|---|---|
| 1 | `scripts/rebuild_excel_formula.py` | 删除 `NODE_TOLERANCE["result.totalValue"]: 65`；剩余 ±10 容差补背书注释（ROUND(...,-1) 十位语义 + P1-1 事件 23466a3）；被删条目的完整理由写入注释（防复活） |
| 2 | `outputs/calculation_chain.json` | 末节点同步 R7 形态：`result.totalValue`→`result.finalUnitValue`，公式 `=ROUND({{finalTotal}}/{{area}},0)`，target 唯一 |
| 3 | `tests/test_schema_v12.py` | 两处断言同步（`test_final_unit_value_formula` 断言 `=ROUND(O6/M6,0)`；PASS 节点列表） |
| 4 | `scripts/verify_example_arithmetic.py` | `CHAIN_TAIL_TOLERANCE` 注释更新（65 已退役的史实） |

**未动**：生成器（H11）、fixture `income.value`（H12）、两示例 JSON、门禁与变异器。

## 三、度量（与 Round 8/9 同协议）

| 指标 | 基线（变更前） | Round 10 | 判定 |
|---|---|---|---|
| 合法化豁免数 | 1（±65 豁免 18 元） | **0** | 提升（机制清除） |
| 变异测试（×3 重复） | 27/27 = 100% | **27/27，均值 100.0 ± 0.0** | 持平（上限，不破坏） |
| 全量回归 | 354 passed | **354 passed**（RESULTS.md 落盘后复验全绿；中途 1 failed 是轮目录缺 RESULTS.md 的中间态，流程性预期） | 不破坏 |
| CLI values 模式 | `result.totalValue PASS diff=18 (±65)` | `result.finalUnitValue PASS diff=0 (±1)` | 提升（错误形态从豁免 → 可检出） |

**关键证据**：`mutation_result_round10_baseline.json` 与 `_final.json` **sha256 完全相同**
（`11839dfeac2e9848`）——本轮是纯结构性清除，检出能力零扰动，非度量漂移。
变更前/后 CLI 证据分别存 `logs/cli_values_BEFORE.log` / `cli_values_AFTER.log`。

## 四、决策

| 项 | 决策 | 依据 |
|---|---|---|
| 删除 65 容差 | **采纳固化** | 无缺陷编号背书（违反 R8 教训 5）；豁免对象即缺陷本身 |
| fixture 末节点同步 | **采纳固化** | 载体统一（R9 教训 1）；与示例 JSON 逐字同形态 |
| ±10 容差保留 | 采纳 | 有正当背书（十位舍入语义），非拍脑袋常量 |
| H11 生成器同步 | **转 Round 11** | 变更面更大（动生成器 + 可能动 Excel 映射），恪守单一变量 |
| H12 fixture income.value | **转 Round 11** | 同上，且当前以 SKIP 容忍不产生红灯 |

## 五、沉淀

1. **审计先于修复，溯源可以推翻归因**：「容差被调大」听了两轮，一查 git 是自创建日写死。
   提案里的「为什么」若来自记忆而非证据，就要做好被证伪的准备——证伪归因不推翻危害，
   两者分开记。
2. **死容差比活容差更危险**：65 在示例上已是死代码，但测试载体还活着——它不动声色地
   维持着一个已整改形态的旧副本。**任何整改后应 grep 容差表，确认没有条目在保护已删除的节点形态**。
3. **豁免即欠账**：变异分数持平（100→100）不代表本轮无提升——提升在机制层（豁免数 1→0）。
   度量协议须能表达这类结构性指标，否则「持平」会掩盖真实进展。

### 产物清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `hypotheses.md` | 新增 | 假设登记表补建（协议缺口），H0-H14 |
| `rounds/10/PROPOSAL.md` `RESULTS.md` | 新增 | 提案/结果 |
| `rounds/10/mutation_result_round10_baseline.json` `_final.json` | 新增 | 变异存档（指纹均为 `11839dfeac2e9848`） |
| `rounds/10/logs/cli_values_BEFORE.log` `cli_values_AFTER.log` | 新增 | CLI 前后对比证据 |
| `scripts/rebuild_excel_formula.py` `outputs/calculation_chain.json` `tests/test_schema_v12.py` `scripts/verify_example_arithmetic.py` | 修改 | 见二 |

### Round 11 提案输入

1. **H11 — 生成器形态同步**：`extract_calculation_chain.py` 的 `CORE_NODES`/`_NODE_OVERRIDE_REFS`
   仍产出旧形态 `result.totalValue`（ROUND(面积×单价) + 重复 target）。本轮删除 65 后，
   若再生成将直接撞门禁（尾阈值 1 < 18）——**门禁已就位，生成器是唯一缺口**。
2. **H12 — fixture `income.value` 报酬资本化法残留**（P1-2A 同形态），与示例 JSON 的直接资本化法口径分裂。
3. **H14 — 载体一致性机制**（可升优先级）：R9/R10 连续两轮证明「整改漏同步载体」是系统性的，
   值得做成自动检测（末节点形态 × 所有载体）。

## 六、可复现命令

```bash
# 变异测试（应与基线字节级相同）
python tests/mutation_harness.py --json rounds/10/mutation_result_round10_final.json
# CLI values 模式（应无 ±65 豁免，result.finalUnitValue diff=0）
python scripts/rebuild_excel_formula.py --mode values --chain outputs/calculation_chain.json --data schema/example-武汉洪山住宅.json
# 全量回归
python -m pytest tests/ -q
```

---

*以上分析为专业辅助参考，须由注册房地产估价师审核签署后使用。*
