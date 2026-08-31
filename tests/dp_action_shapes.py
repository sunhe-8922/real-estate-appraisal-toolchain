"""
dp_action_shapes.py — 决策动作（applyDecision）/ 状态机（isTerminal）差分语料生成器

覆盖此前零机械验证的决策点核心逻辑（Round 7 / 假设池 #3）。
每个 case = {"kind", "dp", "action", "status", ["opts"]}
  dp      传给 applyDecision 的决策点（可为 None / 非对象，测防御）
  action  决策动作（可为非法值）
  status  传给 isTerminal 的状态（可与 dp.status 不同，独立覆盖状态机）
  opts    可选；缺该键即模拟 JS 的 undefined
"""
import random

ACTION_KINDS = [
    "approve", "modify", "modify_blank_mods", "reject", "reject_no_comment",
    "reject_blank_comment", "double_decision", "double_decision_modified",
    "bad_action", "dp_null", "dp_not_object", "comment_padded",
    "comment_nonstring", "decided_by", "timestamp_given", "opts_missing",
    "status_edge", "modify_null_mods",
    # P1-1 整改（Round 7 审查）：对象/数组语义（F4 教训——新增边界必须入库）
    "comment_obj", "mods_obj",
]


def _dp(status="pending", **extra):
    d = {
        "id": "DP-comp",
        "name": "可比实例选取",
        "phase": "inMethod",
        "trigger": "method:comps",
        "riskLevel": "P1",
        "status": status,
        "conclusion": "建议选取 3 个可比实例",
        "evidence": [{"item": "同小区成交", "source": "中原地产"}],
        "reasoning": "同小区、近半年",
        "risks": [{"description": "楼层差异", "level": "P1", "mitigation": "楼层修正"}],
    }
    d.update(extra)
    return d


def gen_action_case(rng, kind):
    """按 kind 生成一个决策动作 case。"""
    if kind == "approve":
        return {"dp": _dp(), "action": "approved", "status": "pending",
                "opts": {"comment": "同意"}}
    if kind == "modify":
        return {"dp": _dp(), "action": "modified", "status": "pending",
                "opts": {"comment": "微调", "modifications": "换 2 号实例"}}
    if kind == "modify_blank_mods":  # 空白 modifications → 应被拒
        return {"dp": _dp(), "action": "modified", "status": "pending",
                "opts": {"modifications": "   "}}
    if kind == "modify_null_mods":  # null → JS String(null)="null" 非空 → 通过（对齐点）
        return {"dp": _dp(), "action": "modified", "status": "pending",
                "opts": {"modifications": None}}
    if kind == "reject":
        return {"dp": _dp(), "action": "rejected", "status": "pending",
                "opts": {"comment": "实例 C 信源等级低"}}
    if kind == "reject_no_comment":  # 驳回缺 comment → 应被拒
        return {"dp": _dp(), "action": "rejected", "status": "pending", "opts": {}}
    if kind == "reject_blank_comment":  # 空白 comment → 应被拒
        return {"dp": _dp(), "action": "rejected", "status": "pending",
                "opts": {"comment": " \t "}}
    if kind == "double_decision":  # 已 approved → 不可重复决策
        return {"dp": _dp("approved", humanDecision={"action": "approved",
                                                     "decidedBy": "sun",
                                                     "timestamp": "2026-08-18T10:30:00+08:00"}),
                "action": "approved", "status": "approved"}
    if kind == "double_decision_modified":  # 已 modified（终结）→ 同样拒绝
        return {"dp": _dp("modified", humanDecision={"action": "modified",
                                                     "decidedBy": "sun",
                                                     "modifications": "换实例"}),
                "action": "rejected", "status": "modified", "opts": {"comment": "再想想"}}
    if kind == "bad_action":
        return {"dp": _dp(), "action": rng.choice(["cancel", "", "APPROVED", 1]),
                "status": "pending"}
    if kind == "dp_null":
        return {"dp": None, "action": "approved", "status": "pending"}
    if kind == "dp_not_object":  # 非对象（schema 层之外直调的防御）
        return {"dp": rng.choice(["DP-comp", 42, ["a"]]), "action": "approved",
                "status": "pending"}
    if kind == "comment_padded":  # 前后空白 → 应 trim
        return {"dp": _dp(), "action": "approved", "status": "pending",
                "opts": {"comment": "  同意，但请补充信源  "}}
    if kind == "comment_nonstring":  # 非字符串 → String() 后 trim
        val = rng.choice([123, True, 2.0])
        return {"dp": _dp(), "action": "approved", "status": "pending",
                "opts": {"comment": val}}
    if kind == "comment_obj":  # 对象/数组 comment → String() 渲染（P1-1 整改边界）
        # dict → "[object Object]"；数组 → 逗号 join 扁平，元素 null → ""（[null,"a"] → ",a"）
        # 空数组/空元素组合可能渲染为空串 → comment 被省略
        val = rng.choice([
            {"来源": "中原地产"},
            {"nested": {"deep": 1}},
            ["同小区成交", "近半年"],
            [[1, 2], 3],                # 嵌套扁平化 → "1,2,3"
            [{"a": 1}, "x"],            # → "[object Object],x"
            [None, "a"],                # → ",a"（null 元素为空串，非 "null"）
            [],                         # → "" → comment 被省略
            [None, None],               # → "," → 非空，comment=","
        ])
        return {"dp": _dp(), "action": "approved", "status": "pending",
                "opts": {"comment": val}}
    if kind == "mods_obj":  # modifications 传对象/数组 → 渲染结果决定必填通过与否
        val = rng.choice([
            {"实例": "C"},              # → "[object Object]" → 通过
            ["换", "2号实例"],           # → "换,2号实例" → 通过
            [],                         # → "" → 拒绝 E_MODIFIED_REQUIRES_MODIFICATIONS
            [None, None],               # → "," → 非空 → 通过
        ])
        return {"dp": _dp(), "action": "modified", "status": "pending",
                "opts": {"modifications": val, "comment": "调整"}}

    if kind == "decided_by":
        return {"dp": _dp(), "action": "approved", "status": "pending",
                "opts": {"decidedBy": sun_alias(rng)}}
    if kind == "timestamp_given":  # 显式 timestamp → 比对时保留
        return {"dp": _dp(), "action": "approved", "status": "pending",
                "opts": {"timestamp": "2026-08-31T10:00:00+08:00", "comment": "ok"}}
    if kind == "opts_missing":  # 完全不传 opts（模拟 undefined）
        return {"dp": _dp(), "action": "approved", "status": "pending"}
    if kind == "status_edge":  # isTerminal 边界（dp 与 status 独立，专测状态机）
        return {"dp": _dp(), "action": "approved",
                "status": rng.choice(["approved", "modified", "rejected", "pending",
                                      "unknown", "", None, 42])}
    raise ValueError("unknown kind: " + kind)


def sun_alias(rng):
    return rng.choice(["估价师", "sun", "注册房地产估价师", ""])
