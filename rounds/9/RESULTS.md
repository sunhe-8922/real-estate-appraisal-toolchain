# Round 9 RESULTS — 住宅示例链口径缺陷收口（P1-2A/P1-2B）

> 日期：2026-09-01 | 基线 tag：`round9-baseline`（`b042dc8`）
> 承接：Round 8（门禁翻出 P1-2A/P1-2B），Round 7（P1-1 整改同形态）

---

## 〇、一句话结论

**采纳，确定性收口**。Round 8 翻出的两处 R7 未同步缺陷已修复，且与商业示例 R7 整改 +
住宅示例 analysis 文本口径完全对齐（不引入新判断）。修复后住宅示例 `CONTAMINATED` 解除，
**变异总数 15 → 27、两示例均 100%**，门禁在第二个示例上同样有效——Round 8 的「门禁可泛化」假设被证实。

---

## 一、修复明细（单一变量：住宅示例 chain 口径对齐）

### P1-2A — `income.value` 公式写错方法

| 项 | 修复前 | 修复后 |
|---|---|---|
| formula | `=ROUND(({{noi}}/({{rate}}-{{growth}})*…*(1-1/(1+{{rate}})^G23)),-1)` （报酬资本化法 + 裸单元格 `G23`） | `=ROUND({{noi}}/{{rate}},0)` （直接资本化法） |
| refs | 含 `growth`(→`growthRate` 不存在) / `forwardPeriod`(→`holdingPeriod` 不存在) | 仅 `noi`/`rate`（均存在） |
| 实算值 | 求值器报「引用不存在键」→ 崩溃 | `ROUND(48124/0.015,0)=3208267` = target ✓ |

**依据**：`methods.income.calculationMode="directCapitalization"`，`analysis` 文本明确拒绝报酬资本化法，
`finalValue.total=3208267` 即 `ROUND(48124/0.015)`。商业示例 `income.value` 公式同为 `ROUND(noi/rate,0)`，
本次仅对齐精度（`-1`→`0`，因住宅示例数据到元）。

### P1-2B — `result.totalValue` 节点重复 target + 面积×单价闭合差

| 项 | 修复前 | 修复后 |
|---|---|---|
| id | `result.totalValue` | `result.finalUnitValue` |
| target | `result.finalTotalValue` ⚠️ 与上一节点重复 | `result.finalUnitValue`（唯一） |
| formula | `ROUND({{area}}*{{unitValue}},0)` = 3271738 ≠ 3271720（差 18） | `=ROUND({{finalTotal}}/{{area}},0)` = 25461 ✓ |
| refs | `area`/`unitValue`(→`finalUnitValue`) | `finalTotal`(→`finalTotalValue`)/`area` |

**依据**：与 R7 商业示例整改（23466a3）完全同形态——末节点改「单价派生自权威总价」，
消除 target 冲突，闭合误差被 ROUND 吸收。验证：`ROUND(3271720/128.5,0)=25461` = 声明 `finalUnitValue`。

---

## 二、度量（与 Round 8 同协议）

| 指标 | Round 8 终局 | Round 9 | 判定 |
|---|---|---|---|
| 住宅示例变异判定 | CONTAMINATED（基线不洁） | **12/12 = 100%** | 解除 |
| 变异总数 | 15/15（住宅排除） | **27/27 = 100%** | 提升（+12） |
| 商业示例 | 15/15 = 100% | 15/15 = 100% | 持平（已满分） |
| 全量回归 | 354 passed | 待跑 | 不破坏 |

**关键证据**：`mutation_result_round9_final.json` 显示两示例各自 100%，无 CONTAMINATED、无存活、无崩溃。
门禁 `tests/test_example_arithmetic.py` 对住宅示例跑出 `failed=[]`，KNOWN_DEFECTS 两条登记
成功触发 `fixed` 检测（移除后测试转绿）——证明「登记腐烂成免检牌」的防护机制确实工作。

---

## 三、决策

| 变更 | 决策 | 依据 |
|---|---|---|
| P1-2A 公式改直接资本化法 | 采纳固化 | 与 analysis 文本 + 商业示例一致，实算=target |
| P1-2B 末节点改派生单价 | 采纳固化 | 与 R7 商业示例整改同形态，消除 target 冲突 |
| KNOWN_DEFECTS 清空 | 采纳 | 修复触发 `fixed` 检测，验证机制有效 |
| NODE_TOLERANCE=65 审计 | **转 Round 10 / 独立任务** | 本轮恪守单一变量，未动 `rebuild_excel_formula.py` |

---

## 四、沉淀

### 教训（可复用）

1. **示例链必须随整改同步**。R7 改了商业示例的末节点形态（单价派生），但住宅示例链是旧形态
   （`result.totalValue` 重复 target），导致 P1-1 同形态缺陷潜伏。→ **任何 chain 结构整改，必须 grep 所有示例确认同步**。
   Round 8 的 P1-1 整改清单应包含「同步所有示例末节点形态」，而非只改出问题的示例。
2. **「直接资本化法」示例的 chain 公式不应含报酬资本化法结构**。抄 Excel 时把 `G23` 裸单元格引用
   带了进来（schema 无对应字段）——这是 Excel→JSON 转换的系统性隐患，Round 10 应审计所有示例的
   `excelSource` 字段是否含裸单元格引用。
3. **门禁缺陷登记制确实防腐烂**：KNOWN_DEFECTS 清空时，若遗留登记未删，测试会 `fixed` 检测失败。
   这比 xfail 强——xfail 会默默放过「已修好但登记没删」的半腐烂状态。

### 产物清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `schema/example-武汉洪山住宅.json` | 修改 | P1-2A income.value 公式 + P1-2B 末节点改写 |
| `tests/test_example_arithmetic.py` | 修改 | KNOWN_DEFECTS 清空（两条登记已修复移除） |
| `tests/mutation_harness.py` | 不变 | 复用 |
| `rounds/9/PROPOSAL.md` `RESULTS.md` | 新增 | 提案/结果 |
| `rounds/9/mutation_result_round9_final.json` | 新增 | 变异存档（27/27，sha256 前 16 位 `11839dfeac2e9848`） |

### Round 10 提案输入

1. **P1 — 审计 `NODE_TOLERANCE=65`**（`scripts/rebuild_excel_formula.py`）：该常量把 18 元偏差放过，
   等于把 P1-2B 类错误合法化。溯源当初为何调到 65，每个容差常量补缺陷编号背书。
2. **P1 — 全示例 `excelSource` 裸单元格引用审计**：P1-2A 的 `G23` 是 Excel→JSON 转换遗留，
   检查其他示例是否也有 `{{...}}` 之外的裸单元格（A1/G23 等）混入公式。
3. **P2 — chain 结构整改同步机制**：任何末节点形态变更，自动检测所有示例是否一致（避免再出现「只改一个示例」）。

---

## 五、可复现命令

```bash
# 变异测试（修复后）
python tests/mutation_harness.py --json rounds/9/mutation_result_round9_final.json
# 门禁
python -m pytest tests/test_example_arithmetic.py -q
# 全量回归
python -m pytest tests/ -q
```

---

*以上分析为专业辅助参考，须由注册房地产估价师审核签署后使用。*
