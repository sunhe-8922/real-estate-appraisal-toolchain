# Round 7 RESULTS — oracle 交叉验证 + schema 层断言 + 决策动作/状态机差分

> 日期：2026-08-31 | 输入：`outputs/HANDOFF-2026-08-30-round6.md` 假设池 #9 / #10 + 建议 3
> 延续：Round 5-6（决策链函数差分、机器码、审查整改）

## 一、oracle 交叉验证（假设池 #9，P2-3 收口）

**做法**：起一个**全新会话的 Agent** 作第二实现者，隔离纪律为「只读《决策点规格定义》第四章 + 我给的函数契约」，
明令禁读 `app/`、`tests/`、`rounds/`、`scripts/` 下任何实现代码；产出 `tests/dp_chain_oracle_v2.py`
（含自测 9 组 + 附加用例，全部通过）。

**三方交叉（N=1000，seed 20260830，22 kind）**：

| 对比 | 初版 | 裁决后 |
|---|---|---|
| v1（Round 5 oracle） vs v2（独立实现） | **37 例分歧**（全部 `dup_id`） | 0 |
| v1 vs JS | 0 | 0 |
| v2 vs JS | 37 | 0 |

**唯一分歧与裁决**：
- 形状：`dup_id`——`[DP-a(rejected,1), DP-a(pending,2,supersedes="DP-a")]`，对 dps[0] 建链。
- v1/JS：`others` 按 **id** 排除自身（`d.id !== dp.id`）→ 同名元素一并排除 → 无分叉 → OK 路径（id `DP-a-2`）。
- v2 初版：按**对象同一性**（`elem is dp`）排除 → 同名的另一个对象算"他人"且 supersedes 命中 → C4。
- 裁决：规格 4.2 规则 3（"同一 DP 只能被一个后继取代"）在**重复 id 时本就无定义**；按既有惯例对齐
  生产契约（JS 以 id 为准）。v2 打补丁并保留裁决注释；固化锚点 `test_adjudicated_dup_id_anchor` 冻结该结论。

**交叉验证的独立收获**（v2 作者独立标记的规格模糊点，文件末尾 `# SPEC-AMBIGUITIES:`，共 8 条）：
其中第 3 条「C4 先于 C5，C5 实际仅自引用可达」**与我们 Round 5 的 F1 发现完全一致**——
两位实现者独立推演出同一结论，F1 的可信度因此显著提高。
其余模糊点（链行走的"未访问"作用域、重复 id 的 roots 顺序、畸形元素能否作链节点、
evidence/risks 为 None 的语义、C4 自身判定基准、attempt 非法值、C1/C2/C6 的归属层级）
已随文件入库，作为后续规格完善的输入。

**结论**：原 P2-3（"oracle 独立性无法机械验证"）**已收口**——两份独立实现 + 生产实现三方一致，
且交叉过程本身产出了一条价值发现（F1 的独立复现）与 8 条规格模糊点清单。

## 二、schema 层畸形输入断言（假设池 #10）

新增 `tests/test_schema_malformed_inputs.py`（8 条），断言的是**拦截点本身**（required/type/minimum），
不只"是否合法"——否则把 schema 改松可能仍然报错、测试却绿。

| 畸形输入 | 拦截点 | 对应 validateChain 层锚点 |
|---|---|---|
| 缺 id | `required` | `NO_ID_C6` |
| id=42 | `id` / `type` | — |
| supersedes=42 / 2.0 | `supersedes` / `type` | `NUM_SUP` |
| attempt=2.5 / "2" / true | `attempt` / `type` | — |
| attempt=0 / -1 | `attempt` / `minimum` | — |
| **attempt=2.0** | **放行**（`type: integer` 接受整数值浮点） | `S3_a2.0_b3` |

`attempt=2.0` 被放行这一条是**事实记录而非期望行为**（P0-1 的暴露面：2.0 能穿过 schema 直达 C6）。
若将来收紧，该断言会变红，提醒同步复核 C6 浮点语义与固化锚点。
至此畸形输入形成**双层防线**：schema 层（本文件，入口拦截）+ 业务校验直调层（固化锚点，覆盖无 schema 的 dp-console 路径）。

## 三、决策动作 / 状态机差分（建议 3）

`applyDecision` / `isTerminal` 此前零机械验证（只有 `tests/test_dp_core.js` 手写断言）。
按同一协议补齐：`tests/dp_action_shapes.py`（18 kind）+ `tests/dp_action_runner.js` +
`tests/dp_action_oracle.py`（规格 1.3 / 4.3 参考实现）+ `tests/test_dp_action_vs_oracle.py`
（语料 300 例 + 9 条规格直译锚点，含"输出 status 必须等于 action"的状态机不变量）。

**发现与裁决**：`dp_not_object` 形状中 dp 为**数组**时，JS 守卫 `typeof dp !== "object"` 把数组算作对象
→ 放行后落 `E_NOT_PENDING`；oracle 原判 `E_DP_NOT_OBJECT`。规格未定义"对象"边界，裁决对齐生产契约
（dict/list 视为对象），oracle 已按裁决修正并注释。

**结果**：N=1000 → applyDecision 0 分歧 / isTerminal 0 分歧。

## 四、回归基线（2026-08-31 实测）

| 指标 | 值 |
|---|---|
| Python 全量 | **343 passed**（327 + 交叉验证 4 + schema 层 8 + 决策动作 4） |
| Node 全量 | **32 pass / 0 fail** |
| 三方交叉（决策链函数，N=1000） | v1≡v2≡JS，0 分歧 |
| 决策动作差分（N=1000） | 0 分歧 |

## 五、证据与遗留

- `rounds/7/diff_result_round7.json`（sha256 见下）：三方交叉与动作差分的 N=1000 汇总 + 两处裁决前记录。
- 遗留：`applyDecision` 缺 timestamp 时 JS 取当前时间（不可复现）→ 比对时两端都不带该字段（已在 oracle/runner 注明）；
  若将来需要断言时间戳格式，须改为注入式时钟。
- 遗留：规格模糊点 8 条尚未回写《决策点规格定义》——建议下轮由 sun 确认后补进规格文档（属规格完善，非代码改动）。

### 存档指纹

| 存档 | sha256（前 16 位） |
|---|---|
| `diff_result_round7.json` | `e9e1702fbd84b6d1` |

## 六、P1-1 整改（2026-09-01，Round 7 审查）

**审查发现**：`_js_str()` 未复现 JS `String()` 的 dict/list 语义（dict → `"[object Object]"`、
list → 逗号 join），嵌套对象/数组 comment 会双端漂移。

**整改内容**：
1. `tests/dp_action_oracle.py`：`_js_str()` 补 dict/list 分支。JS 实测校准出一处
   **与整改指令的偏差**：list 元素为 null/undefined 时 JS 渲染为**空串**
   （`[null,"a"]` → `",a"`），而非 "null"——按 D-015 对齐生产契约实现。
2. `tests/dp_action_shapes.py`：新增 `comment_obj` / `mods_obj` 两 kind（F4 教训：
   新增边界必须入库），覆盖 dict/嵌套 dict/扁平数组/null 元素/空数组边界。
3. `tests/test_dp_action_vs_oracle.py`：补 3 条固化锚点（dict 渲染、数组 join、
   `modifications=[]` 渲染为空串被拒的必填边界）。

**结果**：N=1000 → applyDecision / isTerminal 仍 0 分歧（20/20 kind 全触发）；
Python 全量 343 passed；Node 27 pass。

**顺带修复（环境性回归，非差分发现）**：test_templates 28 例因
`scripts/xlsx_meta.py` 的 `save_frozen()` 整标签正则替换吞掉 openpyxl 3.1.5
内联在 `dcterms:created` 上的 `xmlns:dcterms`/`xmlns:xsi` 声明，产出非法 core.xml，
openpyxl(lxml) 读回即 XMLSyntaxError。修复为只替换时间戳文本、保留开标签原样，
4 个模板重新生成后回归全绿。教训：正则改 XML 必须复扫验证（与 D-014 同源）。
