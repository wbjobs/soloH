from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, ConfigDict


class ForecastDataCreate(BaseModel):
    grid_id: int = Field(..., gt=0, description="网格单元ID")
    forecast_date: datetime = Field(..., description="预报日期")
    lead_time_hours: int = Field(..., ge=0, le=240, description="预报提前时间（小时）")
    temperature: Optional[float] = Field(None, ge=-50, le=60, description="温度（摄氏度）")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="湿度（%）")
    rainfall: Optional[float] = Field(None, ge=0, description="降雨量（毫米）")
    wind_speed: Optional[float] = Field(None, ge=0, description="风速（m/s）")

    @field_validator("humidity")
    @classmethod
    def check_humidity(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("湿度必须在0-100之间")
        return v


class ForecastDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="预报数据ID")
    grid_id: int = Field(..., description="网格单元ID")
    forecast_date: datetime = Field(..., description="预报日期")
    lead_time_hours: int = Field(..., description="预报提前时间（小时）")
    temperature: Optional[float] = Field(None, description="温度（摄氏度）")
    humidity: Optional[float] = Field(None, description="湿度（%）")
    rainfall: Optional[float] = Field(None, description="降雨量（毫米）")
    wind_speed: Optional[float] = Field(None, description="风速（m/s）")
    created_at: datetime = Field(..., description="创建时间")


class SevenDayForecastResponse(BaseModel):
    grid_id: int = Field(..., description="网格单元ID")
    lat: float = Field(..., description="纬度")
    lon: float = Field(..., description="经度")
    start_date: datetime = Field(..., description="预报起始日期")
    end_date: datetime = Field(..., description="预报结束日期")
    forecasts: List[ForecastDataResponse] = Field(..., description="7天预报数据列表")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="生成时间"
    )

    @field_validator("forecasts")
    @classmethod
    def check_forecast_count(cls, v: List[ForecastDataResponse]) -> List[ForecastDataResponse]:
        if len(v) > 7:
            raise ValueError("7天预报最多包含7天的数据")
        return v
