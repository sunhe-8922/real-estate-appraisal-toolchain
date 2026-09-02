# Round 11 RESULTS — 生成器形态同步（H11）：最后一个载体分裂源头收口

> 日期：2026-09-02 | 基线 tag：`round11-baseline`（`dcd602c`）
> 承接：Round 10（豁免删除，门禁就位），Round 9 教训 1 / Round 10 教训 2（整改必须同步所有载体）

---

## 〇、一句话结论

**采纳**。生成器末节点同步为整改形态，冻结载体由修复后的生成器重写（字段级全等，
字节级一致），载体分裂三例（R9 示例 / R10 fixture / R11 生成器）全部收口；
新增奇偶+形态+负向验证门禁 5 用例全绿，变异 27/27 与回归不破坏。

## 一、变更前证据（单一变量锁定）

逐节点比对生成器输出（变更前重生成，`logs/generate_BEFORE.log`）↔ 冻结载体：
8 节点中**唯一漂移 = 末节点**——生成器仍发 `result.totalValue`（ROUND(面积×单价) +
重复 target），载体已是 `result.finalUnitValue` 新形态；其余 7 节点逐字一致。
漂移面收敛到一个节点，单一变量实验成立。

## 二、变更明细（单一变量：生成器末节点旧形态）

| # | 文件 | 变更 |
|---|---|---|
| 1 | `scripts/extract_calculation_chain.py` | `CORE_NODES` 末项 → `result.finalUnitValue`（target 唯一、派生单价语义）；`_NODE_OVERRIDE_REFS` 末项公式 → `=ROUND({{finalTotal}}/{{area}},0)`；两处注释写明整改来源（R7 P1-1 形态 / R10 豁免删除 / 尾阈值拦截机制） |
| 2 | `outputs/calculation_chain.json` | 由修复后生成器重生成覆盖——与生成器输出**字段级全等**（`logs/parity_check.log`: True），此后任一方独自漂移即红灯 |
| 3 | `tests/test_generator_fixture_parity.py` | 新增 5 用例：① 奇偶（生成器输出 == 冻结载体）② 旧节点 id 不复发 ③ 末节点形态机器定义 ④ 全链 target 唯一 ⑤ 负向验证（旧形态注入必 FAIL 且 diff=18） |

**未动**：模板 xlsx（只读，其 `评估明细表!O6` 的 `==ROUND(M6*N6,0)` 双等号旧形态物理遗迹仅登记观察）；
fixture `income.value`（H12，转下轮）；示例 JSON、门禁、变异器。

## 三、度量（与 Round 8-10 同协议）

| 指标 | Round 10 终局 | Round 11 | 判定 |
|---|---|---|---|
| 载体分裂源头 | 1（生成器） | **0**（生成器输出 == 载体） | 提升（结构性清除） |
| 门禁用例 | — | **5 passed**（新文件） | 提升（防再漂移常驻） |
| 变异测试 ×3 | 27/27 (100.0±0.0) | **27/27，均值 100.0 ± 0.0** | 持平（上限，不破坏） |
| 全量回归 | 354 passed | **359 passed**（354+5，RESULTS 落盘后复验） | 提升（新增，不破坏） |
| node 测试 | 32 passed | 32 passed | 持平 |

**关键证据**：
- 变异存档指纹 `11839dfeac2e9848`——与 R9/R10 终局**逐字节相同**，连续三轮证明
  结构整改对检出能力零扰动；
- 负向验证（门禁用例 ⑤）：旧形态节点注入求值器判 FAIL、diff=18——R10 删除的
  ±65 豁免若被复活，此用例与尾阈值将同时失守，双重防线。

## 四、决策

| 项 | 决策 | 依据 |
|---|---|---|
| 生成器末节点同步 + 载体重写 | **采纳固化** | 漂移面单一；奇偶证明；三例载体分裂终结 |
| 奇偶/形态/负向门禁 | **采纳固化** | 与 H8「人工审查→机器拦截」同构；防再漂移唯一机制 |
| 模板 O6 双等号遗迹 | **观察，不立项** | 生成器不读该公式形态（override 覆盖）；动模板 = 扩大变更面 |
| H12（fixture income.value 报酬资本化法残留） | **转 Round 12** | 不同根因（收益法口径），恪守单一变量 |

## 五、沉淀

1. **同步的终点是"不可能不同步"**：R9-R11 三连证明手工同步载体必然遗漏——
   第三例之后正确做法不是"再仔细同步一遍"，而是让机器证明全等（奇偶断言）。
   本轮起，生成器与冻结载体任何一方单独变更都直接红灯。
2. **负向验证要绑在门禁上而不是实验里**：旧形态注入必红的证明若只出现在
   RESULTS.md，下轮没人跑；固化成测试用例才不会被遗忘（R8 教训 4 的又一次应用）。
3. **描述字段也是漂移**：比对时生成器与载体的唯一结构外差异是 description 文本——
   奇偶断言包含描述，意味着描述必须从生成器流出，不允许手写载体时随手改描述。
   这是对的：描述是口径判断的一部分（R9 P1-2A 就是描述与公式打架）。

### 产物清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `scripts/extract_calculation_chain.py` | 修改 | 末节点形态同步（两处 + 注释） |
| `outputs/calculation_chain.json` | 重生成 | 生成器输出覆盖，字段级全等 |
| `tests/test_generator_fixture_parity.py` | 新增 | 5 用例门禁 |
| `rounds/11/PROPOSAL.md` `RESULTS.md` `diff.patch` | 新增 | 提案/结果/变更集 |
| `rounds/11/logs/` | 新增 | `generate_BEFORE.log`（旧形态证据）/ `generate_AFTER.log` / `parity_check.log` |
| `rounds/11/mutation_result_round11_final.json` | 新增 | 变异存档（指纹 `11839dfeac2e9848`） |

### Round 12 提案输入

1. **H12 — fixture `income.value` 口径分裂**：冻结载体与示例 JSON 的直接资本化法
   不一致（载体仍是报酬资本化法旧公式，测试以 SKIP 容忍）。同步需先裁决：
   载体应表达哪种口径——建议与两示例对齐（直接资本化法），变更面小。
2. **H14 — 载体一致性机制的剩余缺口**：示例 JSON（schema/example-*.json）的 chain
   尚无奇偶类门禁——生成器管不了它们（手维护载体）。可评估把示例 JSON 的末节点
   形态断言并入 `test_example_arithmetic.py`。
3. 模板 `评估明细表!O6` 双等号旧形态遗迹（观察项，低优先级）。

## 六、可复现命令

```bash
# 奇偶验证（生成器输出应 == 冻结载体）
python -m pytest tests/test_generator_fixture_parity.py -q
# 变异测试（应与 R9/R10 字节级相同）
python tests/mutation_harness.py --json rounds/11/mutation_result_round11_final.json
# 全量回归
python -m pytest tests/ -q
```

---

*以上分析为专业辅助参考，须由注册房地产估价师审核签署后使用。*
