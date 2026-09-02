# hypotheses.md — 假设登记表（唯一防重复机制）

> 状态：proposed / testing / adopted / refuted / deferred。
> 新假设先查表再立项；refuted 假设非经新证据不得重提。
> 本表于 Round 10 补建（此前缺失——协议缺口本身已登记为 H0）。
> 历史条目由 rounds/1-9 档案（README 索引 + 各轮 PROPOSAL/RESULTS）回填，一句话结论取自各轮 RESULTS。

| # | 轮次 | 维度 | 假设（一句话） | 状态 | 一句话结论 |
|---|---|---|---|---|---|
| H0 | R10 | 流程 | 协议要求的假设登记表必须存在并作为唯一防重复机制 | adopted | R10 补建本表；此前 9 轮靠 PROPOSAL 显式引用上轮结论防重复，未失守但属纸面合规 |
| H1 | R1 | 评估体系 | 差分测试（Python vs JS 链执行）能量化双端实现一致率 | adopted | 基线 90.7%（93 例），归因 2 根因 + 1 生成器缺口 |
| H2 | R2 | 底层算子 | C5/C6 自引用跳过 + C6 attempt 语义对齐 + 生成器修复可将一致率提至 100% | adopted | 一致率 100%；暴露 c4 条数差 58 例（新问题移交） |
| H3 | R3 | 底层算子 | Python 端 C4 去重可消除条数差 | adopted | 条数 100%（885=885），第一阶段目标终止 |
| H4 | R4 | 底层算子 | P0-1 浮点 attempt 修复 + ghost_fork 对齐可消除对抗审查翻出的漂移 | adopted | 100%；条数 912=912；回归 315 passed |
| H5 | R5 | 评估体系 | 决策链函数差分覆盖扩展 + 消息层机器码可证明函数侧零漂移 | adopted | 函数侧 1000/1000；码级 0 漂移；327 passed |
| H6 | R6 | 评估体系 | 畸形输入 string-only 对齐 + 结构化导出 + 存档指纹可消除全部漂移 | adopted | 4 漂移全消；21-kind 差分 100%；327 passed |
| H7 | R7 | 评估体系 | 独立 oracle 三方比对能捕获差分测试漏掉的隐性不一致 | adopted | 三方 0 分歧；343 passed；但翻出 P1-1 数值自洽盲区（差分只证一致、不证正确） |
| H8 | R8 | 评估体系 | 公式↔target 断言 + 变异测试可把数值自洽从人工审查升级为常驻门禁 | adopted | 检出率 93.3%→100%；354 passed；翻出 P1-2A/P1-2B（住宅示例链未随 R7 整改同步） |
| H9 | R9 | 数据策略 | 住宅示例 chain 同步直接资本化法 + 末节点派生单价后，门禁可泛化到第二示例 | adopted | CONTAMINATED 解除；变异总数 15→27 且两示例均 100% |
| H10 | R10 | 评估体系 | 删除 `NODE_TOLERANCE["result.totalValue"]=65` 并同步冻结 fixture 末节点形态，可消除 P1-2B 形态错误的合法化外衣，且不破坏回归 | **adopted** | 豁免 1→0，三载体末节点形态统一；变异 27/27 持平（基线/终局 sha256 相同 `11839dfeac2e9848`）；回归 354 不破坏。溯源修正：65 非"调大"而是创建日（659e9e3）写死 |
| H10a | R10 | 数据策略 | 全示例 `excelSource` 裸单元格引用审计（R9 输入 2） | adopted | 两示例 19 节点 0 处裸引用（G23 已随 R9 消除）——审计闭环，无需修复 |
| H11 | R11 | 底层算子 | `extract_calculation_chain.py` 生成器仍产出旧形态 `result.totalValue`（ROUND(面积×单价) + 重复 target），应与整改形态同步 | proposed | R8 教训 5 的直接延伸：容差删除后旧形态再生成会被门禁拦（diff 18 > 尾阈值 1），但生成器本身仍是缺陷源 |
| H12 | R11 | 数据策略 | 冻结 fixture `outputs/calculation_chain.json` 的 `income.value` 仍是报酬资本化法旧形态（P1-2A 同形态残留），测试目前以 SKIP 容忍 | proposed | R9 只同步了示例 JSON 未同步 fixture；不产生红灯但保持两载体口径分裂 |
| H13 | — | 评估体系 | 「写入即校验」前移：schema 写入/保存路径挂同一校验器，把拦截从 CI 时提前到编辑时 | proposed | R8 P2 建议，未立项 |
| H14 | — | 评估体系 | chain 结构整改同步机制：末节点形态变更时自动检测所有示例/载体一致性 | proposed | R9 P2 建议；R10 再证必要性（fixture 与生成器都是漏同步载体），可升优先级 |

## 登记规则

1. 每轮提案前查本表：撞车（同根因同手段）→ 不立项；相关但不同手段 → 新编号。
2. 状态流转：proposed → testing（立项当轮）→ adopted/refuted（当轮决策）；搁置 → deferred（注明唤醒条件）。
3. refuted 重提必须附新证据编号（rounds/N/... 路径）并显式说明。
4. 连续 3 轮无提升 → 强制换维度或提反向假设（见递归规则）；当前无此情形。
