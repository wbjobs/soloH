from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator, ConfigDict


class WeatherStationCreate(BaseModel):
    name: str = Field(..., max_length=100, description="气象站名称")
    code: str = Field(..., max_length=50, description="气象站编码")
    lat: float = Field(..., ge=-90, le=90, description="纬度")
    lon: float = Field(..., ge=-180, le=180, description="经度")
    elevation: Optional[float] = Field(None, description="海拔高度（米）")
    is_active: bool = Field(default=True, description="是否激活")

    @property
    def location(self) -> Dict[str, Any]:
        return {
            "type": "Point",
            "coordinates": [self.lon, self.lat]
        }


class WeatherDataCreate(BaseModel):
    station_id: int = Field(..., gt=0, description="气象站ID")
    timestamp: datetime = Field(..., description="数据时间戳")
    temperature: Optional[float] = Field(None, ge=-50, le=60, description="温度（摄氏度）")
    relative_humidity: Optional[float] = Field(None, ge=0, le=100, description="相对湿度（%）")
    rainfall: Optional[float] = Field(None, ge=0, description="降雨量（毫米）")
    leaf_wetness_duration: Optional[float] = Field(None, ge=0, le=24, description="叶片湿润时长（小时）")
    wind_speed: Optional[float] = Field(None, ge=0, description="风速（m/s）")
    solar_radiation: Optional[float] = Field(None, ge=0, description="太阳辐射（W/m²）")

    @field_validator("relative_humidity")
    @classmethod
    def check_humidity_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("相对湿度必须在0-100之间")
        return v


class WeatherDataBatchCreate(BaseModel):
    data: List[WeatherDataCreate] = Field(..., description="批量气象数据")

    @field_validator("data")
    @classmethod
    def check_data_not_empty(cls, v: List[WeatherDataCreate]) -> List[WeatherDataCreate]:
        if len(v) == 0:
            raise ValueError("批量数据不能为空")
        return v


class WeatherStationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="气象站ID")
    name: str = Field(..., description="气象站名称")
    code: str = Field(..., description="气象站编码")
    lat: float = Field(..., description="纬度")
    lon: float = Field(..., description="经度")
    elevation: Optional[float] = Field(None, description="海拔高度（米）")
    is_active: bool = Field(..., description="是否激活")
    created_at: datetime = Field(..., description="创建时间")

    @field_validator("lat", "lon", mode="before")
    @classmethod
    def extract_coordinates(cls, v, info):
        if hasattr(v, "__class__") and hasattr(v, "latitude"):
            return v
        return v


class WeatherDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="数据ID")
    station_id: int = Field(..., description="气象站ID")
    timestamp: datetime = Field(..., description="数据时间戳")
    temperature: Optional[float] = Field(None, description="温度（摄氏度）")
    relative_humidity: Optional[float] = Field(None, description="相对湿度（%）")
    rainfall: Optional[float] = Field(None, description="降雨量（毫米）")
    leaf_wetness_duration: Optional[float] = Field(None, description="叶片湿润时长（小时）")
    wind_speed: Optional[float] = Field(None, description="风速（m/s）")
    solar_radiation: Optional[float] = Field(None, description="太阳辐射（W/m²）")
