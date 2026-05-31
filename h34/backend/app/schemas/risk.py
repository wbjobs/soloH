from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.db.models import CropType


class RiskQueryParams(BaseModel):
    crop_type: CropType = Field(..., description="作物类型")
    forecast_date: Optional[datetime] = Field(None, description="预报日期")
    min_risk: Optional[float] = Field(None, ge=0, le=100, description="最小风险指数")
    max_risk: Optional[float] = Field(None, ge=0, le=100, description="最大风险指数")
    lat_min: Optional[float] = Field(None, ge=-90, le=90, description="最小纬度")
    lat_max: Optional[float] = Field(None, ge=-90, le=90, description="最大纬度")
    lon_min: Optional[float] = Field(None, ge=-180, le=180, description="最小经度")
    lon_max: Optional[float] = Field(None, ge=-180, le=180, description="最大经度")

    @field_validator("max_risk")
    @classmethod
    def check_risk_range(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None and info.data.get("min_risk") is not None:
            if v < info.data["min_risk"]:
                raise ValueError("最大风险指数不能小于最小风险指数")
        return v

    @field_validator("lat_max")
    @classmethod
    def check_lat_range(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None and info.data.get("lat_min") is not None:
            if v < info.data["lat_min"]:
                raise ValueError("最大纬度不能小于最小纬度")
        return v

    @field_validator("lon_max")
    @classmethod
    def check_lon_range(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None and info.data.get("lon_min") is not None:
            if v < info.data["lon_min"]:
                raise ValueError("最大经度不能小于最小经度")
        return v


class RiskGridResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="风险网格ID")
    grid_id: int = Field(..., description="网格单元ID")
    forecast_date: datetime = Field(..., description="预报日期")
    crop_type: CropType = Field(..., description="作物类型")
    risk_index: float = Field(..., description="风险指数（0-100）")
    infection_probability: Optional[float] = Field(None, description="感染概率")
    model_version: Optional[str] = Field(None, description="模型版本")
    calculated_at: datetime = Field(..., description="计算时间")
    lat: float = Field(..., description="纬度")
    lon: float = Field(..., description="经度")
    grid_x: int = Field(..., description="网格X坐标")
    grid_y: int = Field(..., description="网格Y坐标")


class RiskGridGeoJSONFeature(BaseModel):
    type: str = Field(default="Feature", description="GeoJSON 类型")
    geometry: Dict[str, Any] = Field(..., description="几何形状")
    properties: Dict[str, Any] = Field(..., description="属性数据")


class RiskMapResponse(BaseModel):
    type: str = Field(default="FeatureCollection", description="GeoJSON 类型")
    features: List[RiskGridGeoJSONFeature] = Field(..., description="风险网格要素列表")
    forecast_date: datetime = Field(..., description="预报日期")
    crop_type: CropType = Field(..., description="作物类型")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="生成时间"
    )
    model_version: Optional[str] = Field(None, description="模型版本")
