from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.db.models import CropType


class SporeSensorCreate(BaseModel):
    name: str = Field(..., max_length=100, description="孢子传感器名称")
    code: str = Field(..., max_length=50, description="孢子传感器编码")
    lat: float = Field(..., ge=-90, le=90, description="纬度")
    lon: float = Field(..., ge=-180, le=180, description="经度")
    crop_type: CropType = Field(..., description="作物类型")
    spore_type: str = Field(..., max_length=50, description="孢子类型")
    is_active: bool = Field(default=True, description="是否激活")

    @property
    def location(self) -> Dict[str, Any]:
        return {
            "type": "Point",
            "coordinates": [self.lon, self.lat]
        }


class SporeDataCreate(BaseModel):
    sensor_id: int = Field(..., gt=0, description="孢子传感器ID")
    timestamp: datetime = Field(..., description="数据时间戳")
    concentration: float = Field(..., ge=0, description="孢子浓度（个/立方米）")

    @field_validator("concentration")
    @classmethod
    def check_concentration(cls, v: float) -> float:
        if v < 0:
            raise ValueError("孢子浓度不能为负数")
        return v


class SporeDataBatchCreate(BaseModel):
    data: List[SporeDataCreate] = Field(..., description="批量孢子数据")

    @field_validator("data")
    @classmethod
    def check_data_not_empty(cls, v: List[SporeDataCreate]) -> List[SporeDataCreate]:
        if len(v) == 0:
            raise ValueError("批量数据不能为空")
        return v


class SporeSensorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="孢子传感器ID")
    name: str = Field(..., description="孢子传感器名称")
    code: str = Field(..., description="孢子传感器编码")
    lat: float = Field(..., description="纬度")
    lon: float = Field(..., description="经度")
    crop_type: CropType = Field(..., description="作物类型")
    spore_type: str = Field(..., description="孢子类型")
    is_active: bool = Field(..., description="是否激活")
    created_at: datetime = Field(..., description="创建时间")


class SporeDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="数据ID")
    sensor_id: int = Field(..., description="孢子传感器ID")
    timestamp: datetime = Field(..., description="数据时间戳")
    concentration: float = Field(..., description="孢子浓度（个/立方米）")
    created_at: datetime = Field(..., description="创建时间")
