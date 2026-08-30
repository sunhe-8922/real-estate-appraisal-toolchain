# EVIDENCE-RECONSTRUCTED — Round 1 基线不一致证据（抢救性重建）

> 重建日期：2026-08-30（对抗式审查期间）| 登记：2026-08-30（Round 4，P1-1 补救）
> 性质：**抢救性重建，非原始档案**。原始 93 例 mismatch 明细已因存档被覆盖而永久丢失。

## 一、发生了什么

`rounds/1/diff_result.json` 被 Round 2 重跑**原地覆盖**；git 历史中该文件仅有 2 次提交
（`5b40f41`、`529d187`），两次内容均为 `rate=1.0, mismatches=[]`。
Round 1 实测的 **93 例双端不一致**（一致率 90.70%）的原始档案从未进入任何可追溯存档。

违反：闭环协议第 5 条（"每轮经验结构化沉淀为下一轮上下文"）与 Round 1 RESULTS.md
自己的"全量存档"声明。详见 `outputs/对抗式审查-双端校验迭代-20260830.md` P1-1。

## 二、重建方法（可复现）

用"**修复前代码 + 同种子 + 同协议**"重放：

1. 取 `tag round0-baseline` 的双端实现：
   - Python：`git show round0-baseline:scripts/validate_appraisal_json.py`（C6 入口 `attempt is not None` 旧语义）
   - JS：`git show round0-baseline:app/js/dp-core.js`（C5/C6 未跳过自引用节点旧语义）
2. 用 `rounds/1/diff_check_chain.py` 生成器（种子 20260828，N=1000）重放。
3. 结果：一致 908/1000，**不一致 92 例**。

验证锚点：用修复后代码（`5b40f41`+）重放同一场景 → 0 例不一致，
证明 92 例不一致全部由 Round 2 修复消除（原漂移真实存在）。

## 三、92 例 kind 分布

| kind | 例数 | 根因 |
|---|---|---|
| c2 | 57 | JS C5/C6 未跳过自引用节点（Round 2 修复①） |
| attemptneg | 19 | Python C6 对 `attempt<1` 的视作 1 语义与 JS 不一致（Round 2 修复②） |
| attempt0 | 16 | 同上 |
| **合计** | **92** | |

（Round 1 文档记载 "~56/~18/~19" 为前 50 例外推估算；重建重放实测 57/19/16。）

## 四、92 vs 93：差 1 例，原因不可考

- 重建所用生成器在 Round 2 被修改过（c4 修复 + 新增 attempt_str），重放语料与
  Round 1 原始语料**不能保证逐例相同**；
- 原始 93 例明细没有存档，无法逐例比对；
- 这 1 例差异本身就是 P1-1（证据管理失败）的代价。**置信：中等**。

## 五、防复发规则

见 `rounds/README.md` §存档命名规则：差分结果按轮次独立命名
（`diff_result_roundN.json`），**禁止原地覆盖**；本轮（Round 4）起已执行。
