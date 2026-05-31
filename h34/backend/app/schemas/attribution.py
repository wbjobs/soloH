from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

from app.db.models import CropType


class AttributionBase(BaseModel):
    lon: float = Field(..., description="经度", ge=-180, le=180)
    lat: float = Field(..., description="纬度", ge=-90, le=90)
    crop_type: CropType = Field(..., description="作物类型")
    forecast_date: Optional[datetime] = Field(None, description="预报日期")
    resistance_level: Optional[int] = Field(None, description="抗性级别", ge=1)


class AttributionSHAPValues(BaseModel):
    temperature: float = Field(..., description="温度SHAP值")
    humidity: float = Field(..., description="湿度SHAP值")
    leaf_wetness: float = Field(..., description="叶面湿润SHAP值")
    spore_concentration: float = Field(..., description="孢子浓度SHAP值")
    resistance_level: float = Field(..., description="抗性SHAP值")


class AttributionResponse(BaseModel):
    id: Optional[int] = Field(None, description="归因记录ID")
    grid_id: int = Field(..., description="网格ID")
    lon: float = Field(..., description="经度")
    lat: float = Field(..., description="纬度")
    crop_type: str = Field(..., description="作物类型")
    forecast_date: str = Field(..., description="预报日期")
    risk_index: float = Field(..., description="风险指数")
    risk_level: str = Field(..., description="风险等级")
    infection_probability: Optional[float] = Field(None, description="感染概率")

    attribution: Dict[str, Any] = Field(..., description="SHAP归因分析结果")

    model_version: Optional[str] = Field(None, description="模型版本")
    calculated_at: Optional[str] = Field(None, description="计算时间")


class DominantFactorDistribution(BaseModel):
    count: int = Field(..., description="网格数")
    percentage: float = Field(..., description="占比%")


class AttributionSummaryResponse(BaseModel):
    total_grids: int = Field(..., description="总网格数")
    dominant_distribution: Dict[str, DominantFactorDistribution] = Field(..., description="各因素作为主导的分布")
    average_contribution: Dict[str, float] = Field(..., description="各因素平均贡献度")
    high_risk_dominant: Dict[str, DominantFactorDistribution] = Field(..., description="高风险区域主导因素分布")
    high_risk_total: int = Field(..., description="高风险网格总数")
    forecast_date: str = Field(..., description="预报日期")
    crop_type: str = Field(..., description="作物类型")
