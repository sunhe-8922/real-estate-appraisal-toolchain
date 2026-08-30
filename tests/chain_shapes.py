"""
chain_shapes.py — 决策链函数（resolveChain / buildSuccessorShell）差分语料生成器

背景：这两个函数此前只有手写断言（tests/test_dp_core.js），零机械验证，
是"双端一致"声明的最大盲区（假设池 #10 / 审查未检查边界）。2026-08-30 起
按 Round 1 差分协议补齐：分层生成器 + 执行器 + 固化测试。

与被取代链（validateChain）的语料 `diff_chain_generator.DIFF_KINDS` **刻意分开**
——新增 kind 会改变抽样序列，若共用会扰动已固化的 885/912 基线（见 Round 4 R7）。

每个 case = {"kind": str, "dps": [...], "dpIndex": int}
  dps     作为 resolveChain(decisionPoints) 的输入
  dpIndex 作为 buildSuccessorShell(chain, dps[dpIndex]) 的被驳回 DP（可为 -1 → 传 undefined）
"""
import random

from diff_chain_generator import gen_valid_dp

SHAPE_KINDS = [
    "valid", "long", "multi", "fork", "cycle2", "cycle3", "selfref",
    "ghost", "ghost_fork", "attempt_gap", "attempt_missing", "attempt_float",
    "approved_pred", "pending_pred", "rich", "dup_id", "weird_id",
    "null_elem", "empty", "rejected_tail", "excluded_dp", "orphan_mid",
]


def _chain(n, prefix="DP"):
    """合法链：n 个节点，rejected→…→pending，attempt 递增。"""
    dps = []
    for i in range(n):
        status = "rejected" if i < n - 1 else "pending"
        dps.append(gen_valid_dp("%s-%d" % (prefix, i), status, attempt=i + 1,
                                supersedes="%s-%d" % (prefix, i - 1) if i > 0 else None))
    return dps


def _pick_rejected(dps, rng):
    """选被驳回的 DP 下标：三路混合，避免语料恒落在同一条分支上。

    - 40% 最后一个 rejected（链中通常已有后继 → C4 防分叉路径）
    - 30% 数组尾部（常无后继 → OK 建链路径）
    - 30% 随机下标（可能落到 pending/None → C3 / E_DP_NO_ID 路径）
    """
    if not dps:
        return -1
    rej = [i for i, d in enumerate(dps) if isinstance(d, dict) and d.get("status") == "rejected"]
    r = rng.random()
    if r < 0.4 and rej:
        return rej[-1]
    if r < 0.7:
        return len(dps) - 1
    return rng.randrange(len(dps))


def gen_shape(rng, kind):
    """按 kind 生成一个 case。"""
    if kind == "valid":  # 1-2 条合法链
        dps = _chain(rng.randint(1, 3))
        return {"dps": dps, "dpIndex": _pick_rejected(dps, rng)}
    if kind == "long":  # 单链 4 节点
        dps = _chain(4)
        return {"dps": dps, "dpIndex": _pick_rejected(dps, rng)}
    if kind == "multi":  # 3 条独立链（含一条 2 节点）
        dps = _chain(2, "A") + _chain(2, "B") + [gen_valid_dp("C-0", "pending", 1)]
        return {"dps": dps, "dpIndex": _pick_rejected(dps, rng)}
    if kind == "fork":  # A 已被 B 取代，再对 A 建链 → C4 防分叉
        a = gen_valid_dp("DP-a", "rejected", 1)
        b = gen_valid_dp("DP-b", "pending", 2, supersedes="DP-a")
        return {"dps": [a, b], "dpIndex": 0}
    if kind == "cycle2":  # A↔B 双向环
        a = gen_valid_dp("DP-a", "rejected", 1)
        b = gen_valid_dp("DP-b", "rejected", 2, supersedes="DP-a")
        a["supersedes"] = "DP-b"
        return {"dps": [a, b], "dpIndex": 1}
    if kind == "cycle3":  # A→B→C→A 三节点环
        a = gen_valid_dp("DP-a", "rejected", 1)
        b = gen_valid_dp("DP-b", "rejected", 2, supersedes="DP-a")
        c = gen_valid_dp("DP-c", "rejected", 3, supersedes="DP-b")
        a["supersedes"] = "DP-c"
        return {"dps": [a, b, c], "dpIndex": 0}
    if kind == "selfref":  # 自引用（validateChain 定性 C2；buildSuccessorShell 判 C5）
        a = gen_valid_dp("DP-a", "rejected", 1)
        a["supersedes"] = "DP-a"
        return {"dps": [a], "dpIndex": 0}
    if kind == "ghost":  # supersedes 指向不存在 id
        a = gen_valid_dp("DP-a", "rejected", 1)
        b = gen_valid_dp("DP-b", "pending", 2, supersedes="GHOST")
        return {"dps": [a, b], "dpIndex": 0}
    if kind == "ghost_fork":  # 双 DP 指向同一不存在 id（Round 4 P0 形状）
        return {"dps": [gen_valid_dp("DP-b", "pending", 2, supersedes="GHOST"),
                        gen_valid_dp("DP-c", "pending", 2, supersedes="GHOST")],
                "dpIndex": 0}
    if kind == "attempt_gap":  # attempt 跳号（1 → 5）
        a = gen_valid_dp("DP-a", "rejected", 1)
        b = gen_valid_dp("DP-b", "pending", 5, supersedes="DP-a")
        return {"dps": [a, b], "dpIndex": 1}
    if kind == "attempt_missing":  # 无 attempt（默认 1）
        a = gen_valid_dp("DP-a", "rejected")
        return {"dps": [a], "dpIndex": 0}
    if kind == "attempt_float":  # 浮点 attempt（P0-1 形状）：单节点无后继 → 走 OK 路径，
        # 才能覆盖 successor.id 的数字渲染（2.0+1=3.0 → JS 渲染 "3"，Python 需同构）
        a = gen_valid_dp("DP-a", "rejected", 2.0 if rng.random() < 0.5 else 2.5)
        return {"dps": [a], "dpIndex": 0}
    if kind == "approved_pred":  # 终结状态 DP → 建链应被 C3 拒绝
        a = gen_valid_dp("DP-a", "approved", 1)
        return {"dps": [a], "dpIndex": 0}
    if kind == "pending_pred":  # 非 rejected 的 pending → 同样 C3
        a = gen_valid_dp("DP-a", "pending", 1)
        return {"dps": [a], "dpIndex": 0}
    if kind == "rich":  # 富字段（method/comparison/evidence/risks）深拷贝覆盖
        a = gen_valid_dp("DP-a", "rejected", 1)
        a["method"] = "comps"
        a["comparison"] = [{"name": "实例A", "price": 12000}, {"name": "实例B", "price": 13000}]
        a["evidence"] = [{"type": "成交数据", "ref": "T1"}]
        a["risks"] = [{"desc": "信源等级低", "mitigation": ""}]
        return {"dps": [a], "dpIndex": 0}
    if kind == "dup_id":  # 重复 id（byId / find 首匹配语义）
        a = gen_valid_dp("DP-a", "rejected", 1)
        a2 = gen_valid_dp("DP-a", "pending", 2, supersedes="DP-a")
        return {"dps": [a, a2], "dpIndex": 0}
    if kind == "weird_id":  # baseIdOf 边界：DP-2 → DP；DP-a-3-2 → DP-a-3
        ids = ["DP-2", "DP-a-3-2", "DP", "1-2-3"]
        rid = rng.choice(ids)
        a = gen_valid_dp(rid, "rejected", rng.randint(1, 3))
        return {"dps": [a], "dpIndex": 0}
    if kind == "null_elem":  # 数组含 null（防御性过滤）
        dps = _chain(2) + [None]
        return {"dps": dps, "dpIndex": _pick_rejected(dps, rng)}
    if kind == "empty":  # 空数组
        return {"dps": [], "dpIndex": -1}
    if kind == "rejected_tail":  # 尾部 rejected 且无后继（正常驳回场景）
        dps = [gen_valid_dp("DP-a", "rejected", 1), gen_valid_dp("DP-b", "rejected", 2, "DP-a")]
        return {"dps": dps, "dpIndex": 1}
    if kind == "excluded_dp":  # 传入不在数组内的 DP（外部对象）
        dps = _chain(2)
        outside = gen_valid_dp("DP-x", "rejected", 1)
        return {"dps": dps, "dpIndex": -1, "outsideDp": outside}
    if kind == "orphan_mid":  # 链中段缺失（ghost 中间节点）
        a = gen_valid_dp("DP-a", "rejected", 1)
        c = gen_valid_dp("DP-c", "pending", 3, supersedes="DP-b")
        return {"dps": [a, c], "dpIndex": 0}
    raise ValueError("unknown kind: " + kind)
