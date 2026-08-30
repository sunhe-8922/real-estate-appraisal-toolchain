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

## 存档命名规则（P1-1 教训，强制）

1. **差分结果按轮次独立命名**：`rounds/N/diff_result_roundN.json`，由
   `diff_check_chain.py --out` 显式指定。**禁止原地覆盖**任何已存在的存档文件。
2. 重跑同一轮产生新证据时，追加后缀区分（如 `diff_result_round4_p0fix.json`），
   不覆盖；旧文件保留即历史。
3. mismatch 明细、重建证据（如 `rounds/1/EVIDENCE-RECONSTRUCTED.md`）同样按轮次
   归档，随代码一并提交——**只写 stdout 不算存档**。
4. 中间探测脚本用 `tmp_*` 前缀，验证后删除，不入库。

## 与 tests/ 的关系（P2-2 已解耦，2026-08-30）

差分协议的唯一事实源已迁移至 tests/：

- **生成器/分类器**：`tests/diff_chain_generator.py`（gen_case / DIFF_KINDS / classify_py）
- **Node 执行器**：`tests/chain_runner.js`
- **固化回归测试**：`tests/test_diff_chain_consistency.py`（KINDS 由 DIFF_KINDS 派生，去重保序，固化语料序列不变）

`rounds/1/diff_check_chain.py` 保留为 CLI 薄壳（导入 tests/ 的事实源），
历史验证命令 `cd rounds/1 && python diff_check_chain.py --count 1000 --seed 20260828`
继续可用；`rounds/1/chain_runner.js` 为 Round 1 冻结存档（无依赖方，勿改动）。
归档/清理 rounds/ 不再影响正式回归测试。
