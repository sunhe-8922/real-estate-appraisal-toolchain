"""Shared test helpers — 数据构造与字段剥离工具（P1-3 去重）。"""


def strip_v12_fields(data: dict) -> None:
    """从数据中移除 v1.2 及 v1.3 新增字段，还原为干净 v1.1 数据。"""
    # 顶层 calculationChain（v1.2 新增）
    data.pop("calculationChain", None)
    # 顶层 decisionPoints（v1.3 新增）
    data.pop("decisionPoints", None)
    # adjustments 子项 details 数组（v1.2 新增）
    for inst in data.get("methods", {}).get("comps", {}).get("comparableInstances", []):
        adj = inst.get("adjustments", {})
        for key in ("locationDetails", "physicalDetails", "interestDetails"):
            adj.pop(key, None)


def strip_v13_fields(data: dict) -> None:
    """移除 v1.3 新增字段（decisionPoints），还原为干净 v1.2 数据。"""
    data.pop("decisionPoints", None)


def make_minimal_decision_point(dp_id="DP1", status="approved", supersedes=None, attempt=None):
    """构造一个最小合法的 decisionPoint 对象（可带 supersedes/attempt）。"""
    dp = {
        "id": dp_id,
        "name": "估价事项确认",
        "phase": "preCalculation",
        "trigger": "always",
        "riskLevel": "P0",
        "status": status,
        "conclusion": "建议确认估价目的为抵押估价",
        "evidence": [
            {"item": "委托合同明确估价目的", "source": "委托合同"}
        ],
        "reasoning": "抵押估价要求市场价值",
        "risks": [
            {"description": "附属面积需确认", "level": "P0", "mitigation": "按产权证"}
        ],
    }
    if status != "pending":
        dp["humanDecision"] = {
            "action": status,
            "decidedBy": "sun",
            "timestamp": "2026-08-18T10:30:00+08:00",
        }
        if status == "modified":
            dp["humanDecision"]["modifications"] = "将估价目的改为转让估价"
    if supersedes is not None:
        dp["supersedes"] = supersedes
    if attempt is not None:
        dp["attempt"] = attempt
    return dp


def make_comp_decision_point():
    """构造一个方法特定决策点（可比实例选取）。"""
    return {
        "id": "DP-comp",
        "name": "可比实例选取",
        "phase": "inMethod",
        "trigger": "method:comps",
        "method": "comps",
        "riskLevel": "P1",
        "status": "approved",
        "conclusion": "推荐选取实例 A/B/C",
        "evidence": [
            {"item": "实例 A：XX 小区，成交 2026-06-15，25000 元/m²", "source": "链家成交记录 (T0)"},
            {"item": "实例 B：XX 小区，成交 2026-07-01，25500 元/m²", "source": "贝壳成交记录 (T1)"},
        ],
        "reasoning": "三个实例均在 6 个月内成交",
        "risks": [
            {"description": "实例 B 距地铁站远 800m", "level": "P1", "mitigation": "区位修正预计 18%"},
        ],
        "comparison": [
            {"instance": "A", "differences": "同栋同户型，楼层差 2 层"},
            {"instance": "B", "differences": "同小区不同栋，面积差 5m²"},
        ],
        "humanDecision": {
            "action": "approved",
            "decidedBy": "sun",
            "timestamp": "2026-08-18T11:00:00+08:00",
        },
    }
