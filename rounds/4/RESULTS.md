# Round 4 RESULTS — P0-1 浮点漂移修复 + 护栏扩展（对抗式审查整改）

> 日期：2026-08-30 | 输入：`outputs/对抗式审查-双端校验迭代-20260830.md`（1 P0 / 3 P1 / 4 P2）
> 继承：Round 1-3（见 `rounds/1..3/`）+ `outputs/HANDOFF-2026-08-30.md`

## 假设 → 动作 → 结果

| # | 假设 | 动作 | 结果 |
|---|---|---|---|
| 1 | Python C6 排除浮点导致双端漂移（P0-1） | Python C6 入口改为接受全部实数（`isinstance(attempt,(int,float)) and not isinstance(attempt,bool)`），prev_attempt 同理，与 JS `typeof number` 完全镜像 | 探测 S2(2.5)/S3(2.0→3)/S4(2.0→2)/S5(1.5→2.5) 双端全部一致；16-kind 差分 N=1000 重跑 **100% / 885=885 不变**（`diff_result_round4_p0fix.json`） |
| 2 | ghost 分叉双端漂移：JS C4 对不存在 id 也报（P1-2 实证） | JS C4 跳过 ghost key（`counted[key]>1 && byId[key]`），对齐 Python 权威语义（C1 已报存在性，不重复归因） | 探测 GHOST_fork 双端均 **仅 C1×2** |
| 3 | 固化测试对新回归失明（P1-3） | 生成器 KINDS 16→18（补 `attempt_float` / `ghost_fork`）；新增确定性对抗形状测试 `test_frozen_adversarial_shapes`（S2/S3/S4/GHOST 四锚点） | 18-kind 差分 N=1000 **100% / 912=912**（`diff_result_round4.json`） |

## 回归基线（2026-08-30 实测）

| 指标 | 修复前 | 修复后 |
|---|---|---|
| Python 全量 | 314 passed | **315 passed**（+1 固化对抗形状测试） |
| Node 全量 | 32 pass | **32 pass / 0 fail** |
| 差分 N=1000（16 kind） | 100% / 885=885 | 100% / 885=885（不变，整数形状零扰动） |
| 差分 N=1000（18 kind） | — | 100% / 912=912 |
| P0-1 探测（S2/S3/S4） | 双端漂移 | 双端一致 |

## 修复语义说明（为什么不用 is_integer() 门）

审查报告 §五建议 `float(attempt).is_integer()` 门。该条件会把 2.5 排除出检查
（继续静默），与报告自己的验证预期"S2: 2.5 → 双端均报 C6"矛盾。
实际采用与 JS 的**完全镜像**：所有实数（int/float，bool 除外）进入 C6 检查，
整数数值浮点与整数同权（2.0 ≡ 2），非整数浮点按数值比较（2.5 ≠ 2 → C6）。

## 遗留

- P2 批量（占位符回填 / intent 基线 / 死代码 / decisions 登记 / tag 推送）见本轮提交。
- ~~tests/ 反向依赖 rounds/1/ 实验文件~~ **已解耦（2026-08-30 同日）**：生成器/执行器迁至
  `tests/diff_chain_generator.py` + `tests/chain_runner.js`（唯一事实源），
  `rounds/1/diff_check_chain.py` 改 CLI 薄壳；解耦后 N=1000 复跑 100%（912=912）逐位一致，
  存档 `diff_result_round4_decoupled.json`。
- 未检查边界（下轮假设池）：`buildSuccessorShell` / `resolveChain` 双端等价性、
  消息层机器可比对编码、id 唯一性校验的 JS 等价实现。
