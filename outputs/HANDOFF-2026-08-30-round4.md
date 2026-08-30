# 任务交接文档 — 2026-08-30 Round 4（审查整改 + 解耦）

> **生成时间**：2026-08-30 12:50
> **继承自**：`outputs/HANDOFF-2026-08-30.md`（该文件为"3 轮迭代 + 对抗式审查"交接，本轮是其整改轮）
> **状态**：审查发现 **1 P0 / 3 P1 / 4 P2 全部处理完毕**，另完成 P2-2 解耦；提交 `7077818` + `dba608b`（连同本文档推送）
> **⚠️ 更新（2026-08-30 14:20）**：本文「四、后续迭代建议」的**下一步 1-4 已全部完成**（Round 5）：① 决策链函数差分扩展（oracle 方案）② CLI NODE 可移植化 ③ 证据机制自查常驻 ④ 消息层机器码。回归 327 passed / 32 pass。详见 **`rounds/5/RESULTS.md`**；本文其余内容（未解决/风险/假设池）仍为最新状态源。
> **前置文档**：`outputs/对抗式审查-双端校验迭代-20260830.md`（审查证据）、`outputs/递归自我改进-双端校验一致性-3轮总结.md`、`rounds/1..4/`、`rounds/README.md`
> **用途**：作为下一个相关任务（双端一致性扩展 / 假设池立项 / 证据治理）的唯一输入，**不依赖任何对话上下文**

---

## 一、已完成的功能点

### 1.1 P0-1：浮点 attempt 双端漂移修复（提交 `7077818`）

**问题**：Round 2 把 Python C6 入口收窄为 `isinstance(attempt, int)`，浮点被排除出检查；JS `typeof number` 仍含浮点 → `attempt=2.5` 时 PY 静默通过/JS 报 C6，`attempt=2.0` 前驱时反向漂移。真实暴露面：jsonschema 4.26 对整数值浮点 2.0 **接受** `type: integer`，且 `dp-console.html` 直调 `validateChain()` 无 schema 层 → 同一份工程 JSON 浏览器与命令行结论不同。

**修复**：`scripts/validate_appraisal_json.py` C6 入口与 `prev_attempt` 均改为接受**全部实数**（`isinstance(x, (int, float)) and not isinstance(x, bool)`），与 JS `typeof number` 完全镜像：整数值浮点与整数同权（2.0 ≡ 2），非整数浮点按数值比较（2.5 ≠ 2 → C6）。

**⚠️ 对审查建议的偏离（重要裁决）**：审查报告 §五 建议用 `float(attempt).is_integer()` 门。该条件会把 2.5 排除出检查（继续静默），与审查报告**自己的验证预期**"S2: 2.5 → 双端均报 C6"直接矛盾。**裁决原则：修复建议与验证预期冲突时以预期为准**（登记于 `decisions.md` D-010）。

### 1.2 ghost 分叉双端对齐（P1-2 实证修复）

探测确认漂移：两 DP 指向同一不存在 id 时，JS 报 C1×2+C4、Python 仅报 C1×2。修复 `app/js/dp-core.js` C4——跳过 ghost key（`counted[key] > 1 && byId[key]`），理由：C1 已报存在性，C4（防分叉）对不存在的 id 无意义，避免同一问题双报。修复后双端均**仅 C1×2**。

### 1.3 固化护栏扩展（P1-3）

| 项 | 内容 |
|---|---|
| 生成器 kind | 16 → 18：`attempt_float`（前驱整数值浮点通过 / 后继非整数浮点报 C6）、`ghost_fork` |
| 新增测试 | `tests/test_diff_chain_consistency.py::test_frozen_adversarial_shapes`——S2/S3/S4/GHOST 四个确定性锚点（随机语料之外的第二道网） |
| 清单单一事实源 | 测试 `KINDS = list(dict.fromkeys(DIFF_KINDS))`，由生成器派生，杜绝"清单漏项"型失明 |

### 1.4 证据机制修复（P1-1）

- `rounds/1/EVIDENCE-RECONSTRUCTED.md`：92 例基线不一致的**抢救性重建**（重建方法 + kind 分布 c2×57 / attemptneg×19 / attempt0×16 + 92 vs 93 差 1 例说明）。
- `rounds/README.md`：存档命名规则——`diff_result_roundN.json` 按轮独立命名，**禁止原地覆盖**；中间探测脚本 `tmp_*` 用后即删。
- `rounds/4/`（RESULTS + 3 份差分存档）：`diff_result_round4_p0fix.json`（16-kind 回归 885=885）、`diff_result_round4.json`（18-kind 912=912）、`diff_result_round4_decoupled.json`（解耦后复跑 912=912）。

### 1.5 P2 批量（同 `7077818`）

`<round3>` 占位符回填为 `630392c`（并修正同行"均未推送"的过期表述）；`intent.md` 测试基线 311 → **315**；删除测试死代码（未使用的 `NODE` 变量）；`decisions.md` 新增 D-010（含同日修订）；`CHANGELOG.md` 新增未发布节；推送 tag `round0-baseline`（→c6d5af2）/ `round3-done`（→630392c）。

### 1.6 tests/ 反向依赖解耦（P2-2，提交 `dba608b`）

| 角色 | 位置 | 说明 |
|---|---|---|
| 生成器/分类器 | `tests/diff_chain_generator.py` | 唯一事实源：`gen_case` / `DIFF_KINDS` / `classify_py` |
| Node 执行器 | `tests/chain_runner.js` | 唯一事实源（require 路径已改为 `../app/js/dp-core.js`） |
| 固化回归测试 | `tests/test_diff_chain_consistency.py` | 不再依赖 `rounds/` |
| CLI 薄壳 | `rounds/1/diff_check_chain.py` | 导入 tests 事实源；历史命令 `cd rounds/1 && python diff_check_chain.py --count 1000 --seed 20260828` 继续可用 |
| 冻结存档 | `rounds/1/chain_runner.js` | Round 1 存档，无依赖方，勿改动 |

解耦后差分 N=1000 复跑：100% / 912=912，**与解耦前逐位一致**（固化语料未变，因 `KINDS` 去重保序后序列与旧清单相同）。

### 1.7 测试基线（2026-08-30 实测，当前权威值）

| 指标 | 值 |
|---|---|
| Python 全量 | **315 passed** |
| Node 全量 | **32 pass / 0 fail / 0 skipped** |
| 差分 CLI N=1000（18 kind） | 100% / 912=912 |
| 差分 16-kind 基线 | 100% / 885=885（P0-1 修复前后不变，整数形状零扰动） |
| 固化对抗形状 | S2/S3/S4/GHOST 双端一致 |

---

## 二、未解决的问题

### 2.1 未检查边界（审查报告 §六 已标注，本轮未动）

| 项 | 说明 |
|---|---|
| `buildSuccessorShell()` / `resolveChain()` 双端等价性 | 本轮差分**只覆盖 `validateChain`**，其余两个函数从未做双端对照 |
| `_check_decision_point_uniqueness` | id 唯一性校验仅 Python 端，无 JS 等价实现，未评估是否需要 |
| schema 层 ↔ 前端校验一致性 | jsonschema（Python）与前端校验之间无机械一致性验证（P0-1 暴露面正是此缺口） |
| `dp-console.html` 浏览器端行为 | 仅确认了调用点，未做浏览器实测 |

### 2.2 证据与文档

- **92 vs 93 差 1 例**：原因永久不可考（Round 1 原始档案已被 Round 2 原地覆盖，生成器在 Round 2 被改过，重放语料无法保证逐例相同）。这是 P1-1 的代价，已如实记入 `EVIDENCE-RECONSTRUCTED.md`，置信中等。
- **历史存档估算数未改**：`rounds/1/RESULTS.md`、`rounds/2/PROPOSAL.md` 中的 "~56/~18/~19" 为前 50 例外推（重建实测 57/19/16）。**有意不改**——历史存档保持原样，勘误已写入 `EVIDENCE-RECONSTRUCTED.md`。

### 2.3 历史遗留（自 `outputs/HANDOFF-2026-08-24.md` §二，仍未动）

真实对话演练（编排层）、固定 DP 浏览器验证、多方法工程示例、R2 `redLineChecks` 语义、git 历史 PII 方案 B/C。

### 2.4 工程瑕疵（本轮发现，未处理）

- `rounds/1/diff_check_chain.py` 的 `NODE` 常量硬编码 `C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2\node.exe`（换机即失效）；测试侧已支持 `WORKBUDDY_NODE` 环境变量与 PATH 探测，CLI 薄壳尚未对齐。
- `rounds/1/chain_runner.js` 与 `tests/chain_runner.js` 两份内容重复（前者为冻结存档），若误改会引入分叉。

---

## 三、需要注意的风险

| # | 风险 | 影响 | 应对 |
|---|------|------|------|
| R1 | **"100% 一致"的声明边界**：仅在 `validateChain` + 18 kind 语料 + 4 个固化形状内成立（P1-2 教训：声称已验证却未说明覆盖什么） | 越界声明会重复 P1-2 的错误 | 任何"双端一致"声明必须写明覆盖函数与语料范围；扩展覆盖后再提高声明 |
| R2 | **依赖方向反转**：解耦后是 `rounds/1/diff_check_chain.py`（薄壳）依赖 `tests/`，而非反向。清理/重构 tests/ 时需同步薄壳 | CLI 薄壳失效（但正式回归测试不受影响） | 重构 tests/ 后跑一次 CLI 冒烟 |
| R3 | **工作区存在其他会话的未提交改动**：`CLAUDE.md`（已修改）、`outputs/CLAUDE.md`（未跟踪，与根目录双副本）、格力海岸 3105 产物 6 个未跟踪文件 | 与本任务无关，误提交会污染提交历史 | 本轮两笔提交均已显式排除；`outputs/CLAUDE.md` 双副本问题需 sun 另行决策 |
| R4 | **沙箱跨目录写静默失败**：本次实测 `diff --out` 写绝对路径 `rounds/4/...` 失败、写 cwd 正常；`mv` 报错但实际生效 | 验证产物丢失 / 误判结果 | 产物先写 cwd 或项目内目录，写完 `ls` 确认；跨目录操作后**必须二次确认** |
| R5 | **浮点形状漂移易复发**：任何一端再改 C6 类型判定（或 schema 层收紧 `type: integer` 实现）都可能复活漂移 | 用户可见的双端结论不一致 | `test_frozen_adversarial_shapes` 是唯一拦网；如需改 C6 语义，先改该测试的预期再改实现 |
| R6 | **git 远程跟踪引用不持久**（环境已知现象）：`git status` 的 ahead/behind 不可信 | 误判推送状态 | 用 `[ "$(git ls-remote origin master \| cut -f1)" = "$(git rev-parse HEAD)" ]` 核对 |
| R7 | **基线总数随 kind 清单变化**：新增 kind 会改变抽样序列，差分总条数随之改变（885 → 912 已发生一次） | "总数不变"类验证在 kind 清单变更后失效 | 做"不变"验证前先确认 kind 清单未变；否则只断言"双端一致 + 条数双端相等" |

---

## 四、后续迭代建议

### 4.1 建议的下一步（按优先级）

1. **扩展差分覆盖到 `buildSuccessorShell` / `resolveChain`**（假设池 #10，审查未检查边界）：这两个函数当前零机械验证，是"100% 一致"声明的最大盲区。做法照搬 Round 1 协议：分层生成器 + 双端 runner + 固化测试。
2. **CLI 薄壳 NODE 路径可移植化**（§2.4）：改为 `WORKBUDDY_NODE` 环境变量 → PATH 探测 → 硬编码兜底，与测试侧一致。5 行改动，换机即稳。
3. **证据机制常态化自查**：下一轮开始前先确认 `rounds/N/diff_result_roundN.json` 命名规则被执行（P1-1 复发过一次）。
4. **消息层机器可比对编码**（假设池 #6）：双端错误消息统一为 `C4:key=<id>` 形式，消除人工读差。

### 4.2 递归改进的新假设池（引用上轮，不重复已证伪项）

5. **id 唯一性校验的 JS 等价实现**：评估是否补齐（当前仅 Python）。
6. **schema 层差分锚定**：jsonschema（Python）与前端校验之间的机械一致性验证（P0-1 的暴露面就在这一层）。
7. **AI 重写 successor 的 riskLevel 同步率**：对应 `intent.md` R2 风险，可作为训练方法维度的新核心指标。
8. **浏览器端实测**（需人工/浏览器自动化）：`dp-console.html` 的 `validateChain` 调用路径从未实测。

### 4.3 方法论教训（本轮沉淀，写进下一轮的 PROPOSAL）

- **建议与预期冲突时以预期为准**（P0-1 裁决）：审查报告也会自相矛盾，验证预期是更高优先级的裁决标准。
- **随机语料之外必须有确定性锚点**：P0-1 能溜过 16-kind 语料，正是因为没有固化形状测试；新增 kind 与新增锚点测试应成对出现。
- **度量脚本的清单也要被度量**：测试 KINDS 由生成器派生，避免"清单漏项"型失明。

---

## 五、验证命令

```bash
# Python 全量（315/315）
python -m pytest tests/ -q

# Node 全量（32/32）
node --test tests/test_dp_core.js tests/test_e2e_orchestrator.js

# 固化测试（差分 3 断言 + 对抗形状锚点；无 node 时自动 skip）
python -m pytest tests/test_diff_chain_consistency.py -v

# 差分 CLI N=1000（历史命令，走 rounds/1 薄壳）
# 注意 R4：--out 写 cwd 内路径，跨目录写可能静默失败
cd rounds/1 && python diff_check_chain.py --count 1000 --seed 20260828 --out diff_result_roundN.json

# P0-1 / ghost 漂移探针（应全部一致）
python -m pytest tests/test_diff_chain_consistency.py -v -k frozen

# 远程同步核对（勿信 git status 的 ahead/behind）
[ "$(git ls-remote origin master | cut -f1)" = "$(git rev-parse HEAD)" ] && echo 已推送
```

---

## 六、交付物清单

| 文件 | 类型 | 状态 |
|---|---|---|
| `scripts/validate_appraisal_json.py` | 修改：C6 接受全部实数（P0-1） | `7077818`，已推送 |
| `app/js/dp-core.js` | 修改：C4 跳过 ghost key | `7077818`，已推送 |
| `tests/diff_chain_generator.py` | 新增：生成器/分类器唯一事实源（解耦） | `dba608b`，随本文档推送 |
| `tests/chain_runner.js` | 新增：Node 执行器唯一事实源（解耦） | `dba608b`，随本文档推送 |
| `tests/test_diff_chain_consistency.py` | 修改：KINDS 18→派生、新增固化对抗形状测试、删死代码 | `7077818` + `dba608b` |
| `rounds/1/diff_check_chain.py` | 改为 CLI 薄壳（依赖 tests 事实源） | `dba608b` |
| `rounds/1/EVIDENCE-RECONSTRUCTED.md` | 新增：92 例重建档案（方法 + kind 分布） | `7077818`，已推送 |
| `rounds/README.md` | 新增：存档命名规则 + 解耦后关系说明 | `7077818` + `dba608b` |
| `rounds/4/RESULTS.md` + 3 份 `diff_result_round4*.json` | 新增：Round 4 结果与差分存档 | `7077818` + `dba608b` |
| `intent.md` / `decisions.md` / `CHANGELOG.md` | 修改：基线 315 / D-010 / 未发布节 | `7077818` + `dba608b` |
| `outputs/递归自我改进-双端校验一致性-3轮总结.md` | 修改：`<round3>` → `630392c` | `7077818`，已推送 |
| `outputs/HANDOFF-2026-08-30-round4.md` | 新增：本交接文档 | 随本次提交推送 |

---

## 七、Git 状态

```
提交链（本轮 2 笔）:
  7077818 fix(chain): P0-1 float attempt semantics aligned both ends + guardrail extension (Round 4)  [已推送]
  dba608b refactor(tests): decouple diff-chain harness from rounds/ archive (P2-2)                    [随本文档推送]
tag: round0-baseline (→c6d5af2) / round3-done (→630392c)  均已推送
远程核对: git ls-remote origin master 应等于本地 HEAD（见 R6）
工作区: 有其他会话的未提交改动（R3）——本轮两笔提交均已排除
```

---

*本交接文档独立于对话上下文，接手者可仅凭本文档 + `outputs/对抗式审查-双端校验迭代-20260830.md` + `rounds/README.md` + `rounds/1..4/` 恢复全部任务状态。*
