from typing import Dict, Tuple

RISK_THRESHOLDS: Dict[str, float] = {
    "low": 15.0,
    "medium": 40.0,
    "high": 70.0,
    "extreme": 100.0,
}

RISK_LEVELS: Dict[str, Tuple[float, float]] = {
    "low": (0.0, RISK_THRESHOLDS["low"] - 0.01),
    "medium": (RISK_THRESHOLDS["low"], RISK_THRESHOLDS["medium"] - 0.01),
    "high": (RISK_THRESHOLDS["medium"], RISK_THRESHOLDS["high"] - 0.01),
    "extreme": (RISK_THRESHOLDS["high"], RISK_THRESHOLDS["extreme"]),
}

RISK_LEVEL_LABELS_CN: Dict[str, str] = {
    "low": "低风险",
    "medium": "中风险",
    "high": "高风险",
    "extreme": "极高风险",
    "none": "无风险",
}

RISK_LEVEL_LABELS_EN: Dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "extreme": "extreme",
    "none": "none",
}

RISK_COLORS: Dict[str, str] = {
    "low": "#22c55e",
    "medium": "#eab308",
    "high": "#f97316",
    "extreme": "#ef4444",
    "none": "#9ca3af",
}


def get_risk_level(risk_index: float, use_chinese: bool = True) -> str:
    """根据风险指数获取风险等级

    Args:
        risk_index: 风险指数 (0-100)
        use_chinese: 是否返回中文标签

    Returns:
        str: 风险等级标签
    """
    if risk_index < RISK_THRESHOLDS["low"]:
        level = "none" if use_chinese else "low"
    elif risk_index < RISK_THRESHOLDS["medium"]:
        level = "low"
    elif risk_index < RISK_THRESHOLDS["high"]:
        level = "medium"
    else:
        level = "high" if use_chinese else "extreme"

    if use_chinese:
        return RISK_LEVEL_LABELS_CN.get(level, "无风险")
    return RISK_LEVEL_LABELS_EN.get(level, "low")


def get_risk_level_en(risk_index: float) -> str:
    """获取英文风险等级（用于API响应和前端匹配）

    Args:
        risk_index: 风险指数 (0-100)

    Returns:
        str: 风险等级 (low, medium, high, extreme)
    """
    if risk_index < RISK_THRESHOLDS["low"]:
        return "low"
    elif risk_index < RISK_THRESHOLDS["medium"]:
        return "medium"
    elif risk_index < RISK_THRESHOLDS["high"]:
        return "high"
    else:
        return "extreme"


def get_risk_color(risk_index: float) -> str:
    """根据风险指数获取对应颜色

    Args:
        risk_index: 风险指数 (0-100)

    Returns:
        str: 十六进制颜色代码
    """
    level = get_risk_level_en(risk_index)
    return RISK_COLORS.get(level, "#9ca3af")
