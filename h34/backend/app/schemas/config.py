from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict, EmailStr, AnyUrl

from app.db.models import CropType


class UserConfigCreate(BaseModel):
    crop_type: CropType = Field(..., description="作物类型")
    variety_name: str = Field(..., max_length=100, description="品种名称")
    resistance_level: int = Field(..., ge=1, le=5, description="抗性等级（1-5）")
    risk_threshold: float = Field(..., ge=0, le=100, description="风险阈值（0-100）")
    notification_email: Optional[EmailStr] = Field(None, description="通知邮箱")
    webhook_url: Optional[AnyUrl] = Field(None, description="Webhook URL")

    @field_validator("resistance_level")
    @classmethod
    def check_resistance_level(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("抗性等级必须在1-5之间")
        return v

    @field_validator("risk_threshold")
    @classmethod
    def check_risk_threshold(cls, v: float) -> float:
        if v < 0 or v > 100:
            raise ValueError("风险阈值必须在0-100之间")
        return v


class UserConfigUpdate(BaseModel):
    variety_name: Optional[str] = Field(None, max_length=100, description="品种名称")
    resistance_level: Optional[int] = Field(None, ge=1, le=5, description="抗性等级（1-5）")
    risk_threshold: Optional[float] = Field(None, ge=0, le=100, description="风险阈值（0-100）")
    notification_email: Optional[EmailStr] = Field(None, description="通知邮箱")
    webhook_url: Optional[AnyUrl] = Field(None, description="Webhook URL")

    @field_validator("resistance_level")
    @classmethod
    def check_resistance_level(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 5):
            raise ValueError("抗性等级必须在1-5之间")
        return v

    @field_validator("risk_threshold")
    @classmethod
    def check_risk_threshold(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("风险阈值必须在0-100之间")
        return v


class UserConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="配置ID")
    user_id: int = Field(..., description="用户ID")
    crop_type: CropType = Field(..., description="作物类型")
    variety_name: str = Field(..., description="品种名称")
    resistance_level: int = Field(..., description="抗性等级（1-5）")
    risk_threshold: float = Field(..., description="风险阈值（0-100）")
    notification_email: Optional[str] = Field(None, description="通知邮箱")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
