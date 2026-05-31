import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.db.models import CropType, AlertType


class MonthlyStats(BaseModel):
    month: str = Field(..., description="月份")
    avg_risk: float = Field(..., ge=0, le=100, description="平均风险指数")
    max_risk: float = Field(..., ge=0, le=100, description="最大风险指数")
    min_risk: float = Field(..., ge=0, le=100, description="最小风险指数")
    high_risk_days: int = Field(..., ge=0, description="高风险天数")
    data_points: int = Field(..., ge=0, description="数据点数量")


class DailyRiskTrend(BaseModel):
    date: datetime.date = Field(..., description="日期")
    avg_risk: float = Field(..., ge=0, le=100, description="平均风险指数")
    risk_level: str = Field(..., description="风险等级")
    crop_type: CropType = Field(..., description="作物类型")


class RiskStatsResponse(BaseModel):
    crop_type: CropType = Field(..., description="作物类型")
    period_start: datetime.date = Field(..., description="统计周期开始")
    period_end: datetime.date = Field(..., description="统计周期结束")
    overall_avg_risk: float = Field(..., ge=0, le=100, description="总体平均风险指数")
    overall_max_risk: float = Field(..., ge=0, le=100, description="总体最大风险指数")
    overall_min_risk: float = Field(..., ge=0, le=100, description="总体最小风险指数")
    high_risk_area_count: int = Field(..., ge=0, description="高风险区域数量")
    medium_risk_area_count: int = Field(..., ge=0, description="中风险区域数量")
    low_risk_area_count: int = Field(..., ge=0, description="低风险区域数量")
    monthly_stats: List[MonthlyStats] = Field(..., description="月度统计数据")
    daily_trend: List[DailyRiskTrend] = Field(..., description="每日风险趋势")
    generated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(),
        description="生成时间"
    )

    @field_validator("overall_max_risk")
    @classmethod
    def check_max_risk(cls, v: float, info) -> float:
        if v < info.data.get("overall_min_risk", 0):
            raise ValueError("最大风险不能小于最小风险")
        return v


class AlertStatsResponse(BaseModel):
    user_id: Optional[int] = Field(None, description="用户ID（可选，系统统计时为空）")
    period_start: datetime.date = Field(..., description="统计周期开始")
    period_end: datetime.date = Field(..., description="统计周期结束")
    total_alerts: int = Field(..., ge=0, description="预警总数")
    alerts_by_type: Dict[AlertType, int] = Field(..., description="按类型分类的预警数量")
    alerts_by_severity: Dict[str, int] = Field(..., description="按严重程度分类的预警数量")
    alerts_by_crop: Dict[CropType, int] = Field(..., description="按作物分类的预警数量")
    read_alerts: int = Field(..., ge=0, description="已读预警数量")
    unread_alerts: int = Field(..., ge=0, description="未读预警数量")
    notification_success_rate: float = Field(..., ge=0, le=100, description="通知成功率（%）")
    avg_response_time_minutes: Optional[float] = Field(None, ge=0, description="平均响应时间（分钟）")
    generated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(),
        description="生成时间"
    )

    @field_validator("notification_success_rate")
    @classmethod
    def check_success_rate(cls, v: float) -> float:
        if v < 0 or v > 100:
            raise ValueError("成功率必须在0-100之间")
        return v
