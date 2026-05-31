from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.db.models import CropType


class PesticideProductBase(BaseModel):
    product_name: str = Field(..., description="产品名称", max_length=200)
    registration_number: str = Field(..., description="农药登记号", max_length=50)
    active_ingredient: str = Field(..., description="有效成分", max_length=200)
    formulation: Optional[str] = Field(None, description="剂型", max_length=50)
    target_crops: Optional[str] = Field(None, description="适用作物", max_length=500)
    target_diseases: Optional[str] = Field(None, description="防治对象", max_length=500)
    recommended_dosage: Optional[str] = Field(None, description="推荐用量", max_length=200)
    dosage_ha: float = Field(..., description="每公顷用量", ge=0)
    unit: str = Field(..., description="单位: 公斤/升等", max_length=20)
    pre_harvest_interval_days: Optional[int] = Field(None, description="收获间隔期(天)", ge=0)
    safety_interval_days: Optional[int] = Field(None, description="安全间隔期(天)", ge=0)
    rainfastness_hours: Optional[int] = Field(None, description="耐雨水冲刷时间(小时)", ge=0)
    price_per_unit: Optional[float] = Field(None, description="单价(元)", ge=0)
    efficacy_rating: Optional[float] = Field(None, description="效果评级(0-100)", ge=0, le=100)
    resistance_risk: Optional[str] = Field(None, description="抗性风险: 低/中/高", max_length=20)
    restricted_use: bool = Field(False, description="是否限制使用")
    notes: Optional[str] = Field(None, description="备注")


class PesticideProductResponse(PesticideProductBase):
    id: int = Field(..., description="产品ID")
    is_active: bool = Field(..., description="是否启用")
    created_at: datetime = Field(..., description="创建时间")


class EconomicThresholdRequest(BaseModel):
    crop_type: CropType = Field(..., description="作物类型")
    yield_tons_ha: Optional[float] = Field(None, description="预期产量(吨/公顷)", ge=0)
    price_yuan_ton: Optional[float] = Field(None, description="产品价格(元/吨)", ge=0)
    control_cost_yuan_ha: Optional[float] = Field(None, description="防治成本(元/公顷)", ge=0)
    efficacy: float = Field(0.85, description="防治效果(0-1)", ge=0.1, le=1.0)


class EconomicThresholdResponse(BaseModel):
    economic_threshold: float = Field(..., description="经济阈值(风险指数0-100)")
    yield_tons_ha: float = Field(..., description="预期产量(吨/公顷)")
    price_yuan_ton: float = Field(..., description="产品价格(元/吨)")
    control_cost_yuan_ha: float = Field(..., description="防治成本(元/公顷)")
    efficacy: float = Field(..., description="防治效果")
    break_even_severity: float = Field(..., description="收支平衡严重度(%)")
    expected_yield_loss_tons: float = Field(..., description="预期损失产量(吨/公顷)")
    expected_yield_loss_yuan: float = Field(..., description="预期损失金额(元/公顷)")
    formula: str = Field(..., description="计算公式")
    formula_explanation: Dict[str, str] = Field(..., description="公式参数说明")


class SprayRecommendationRequest(BaseModel):
    lon: float = Field(..., description="经度", ge=-180, le=180)
    lat: float = Field(..., description="纬度", ge=-90, le=90)
    crop_type: CropType = Field(..., description="作物类型")
    forecast_date: Optional[datetime] = Field(None, description="预报日期")
    area_ha: Optional[float] = Field(None, description="防治面积(公顷)", ge=0)
    yield_tons_ha: Optional[float] = Field(None, description="预期产量(吨/公顷)", ge=0)
    price_yuan_ton: Optional[float] = Field(None, description="产品价格(元/吨)", ge=0)
    max_cost_yuan_ha: Optional[float] = Field(None, description="最大成本限制(元/公顷)", ge=0)
    last_used_ingredient: Optional[str] = Field(None, description="上次使用的有效成分", max_length=100)
    forecast_risk_trend: Optional[str] = Field("stable", description="风险趋势: rising/stable/falling")


class UrgencyInfo(BaseModel):
    level: str = Field(..., description="紧急程度: immediate/high/medium/low")
    name: str = Field(..., description="紧急程度名称")
    color: str = Field(..., description="颜色代码")
    time_window: str = Field(..., description="时间窗口")


class RecommendedProduct(BaseModel):
    id: int = Field(..., description="产品ID")
    product_name: str = Field(..., description="产品名称")
    registration_number: str = Field(..., description="登记号")
    active_ingredient: str = Field(..., description="有效成分")
    formulation: Optional[str] = Field(None, description="剂型")
    target_diseases: Optional[str] = Field(None, description="防治对象")
    recommended_dosage: Optional[str] = Field(None, description="推荐用量")
    dosage_ha: float = Field(..., description="每公顷用量")
    unit: str = Field(..., description="单位")
    total_dosage: float = Field(..., description="总用量")
    estimated_cost: float = Field(..., description="预估成本(元)")
    application_rate: Optional[str] = Field(None, description="施药量")
    pre_harvest_interval_days: Optional[int] = Field(None, description="收获间隔期")
    safety_interval_days: Optional[int] = Field(None, description="安全间隔期")
    price_per_unit: Optional[float] = Field(None, description="单价")
    efficacy_rating: Optional[float] = Field(None, description="效果评级")
    resistance_risk: Optional[str] = Field(None, description="抗性风险")
    notes: Optional[str] = Field(None, description="备注")


class CostBenefitAnalysis(BaseModel):
    risk_index: float = Field(..., description="风险指数")
    effective_risk: float = Field(..., description="有效风险")
    yield_loss_ratio: float = Field(..., description="产量损失率")
    efficacy: float = Field(..., description="防治效果")
    expected_loss_tons_ha: float = Field(..., description="预期损失(吨/公顷)")
    prevented_loss_tons_ha: float = Field(..., description="挽回损失(吨/公顷)")
    revenue_gain_yuan_ha: float = Field(..., description="挽回收益(元/公顷)")
    cost_yuan_ha: float = Field(..., description="防治成本(元/公顷)")
    net_benefit_yuan_ha: float = Field(..., description="净收益(元/公顷)")
    area_ha: float = Field(..., description="防治面积(公顷)")
    total_cost_yuan: float = Field(..., description="总成本(元)")
    total_revenue_gain_yuan: float = Field(..., description="总挽回收益(元)")
    total_net_benefit_yuan: float = Field(..., description="总净收益(元)")
    benefit_cost_ratio: float = Field(..., description="投入产出比")
    recommendation: str = Field(..., description="建议: 划算/不划算")


class SprayRecommendationResponse(BaseModel):
    recommendation_id: Optional[int] = Field(None, description="建议记录ID")
    grid_id: int = Field(..., description="网格ID")
    lon: float = Field(..., description="经度")
    lat: float = Field(..., description="纬度")
    crop_type: str = Field(..., description="作物类型")
    forecast_date: str = Field(..., description="预报日期")

    risk_index: float = Field(..., description="风险指数")
    risk_level: str = Field(..., description="风险等级")
    drone_detected_severity: Optional[float] = Field(None, description="无人机检测严重度")
    drone_detections_count: int = Field(..., description="无人机检测数量")

    economic_threshold: EconomicThresholdResponse = Field(..., description="经济阈值分析")

    spray_needed: bool = Field(..., description="是否需要施药")
    urgency: UrgencyInfo = Field(..., description="紧急程度")

    recommended_product: Optional[RecommendedProduct] = Field(None, description="推荐农药")
    alternative_product: Optional[RecommendedProduct] = Field(None, description="备选农药")

    cost_benefit_analysis: Optional[CostBenefitAnalysis] = Field(None, description="成本收益分析")

    application_timing: Dict[str, Any] = Field(..., description="施药时间建议")
    application_method: str = Field(..., description="施药方法")
    safety_precautions: List[str] = Field(..., description="安全注意事项")
    resistance_management: List[str] = Field(..., description="抗性管理建议")
    environmental_impact: List[str] = Field(..., description="环境保护建议")

    generated_at: Optional[str] = Field(None, description="生成时间")
    expires_at: Optional[str] = Field(None, description="过期时间")
