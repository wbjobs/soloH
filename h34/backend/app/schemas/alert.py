from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, ConfigDict, AnyUrl

from app.db.models import AlertType, NotificationChannel, CropType


class AlertQueryParams(BaseModel):
    user_id: Optional[int] = Field(None, gt=0, description="用户ID")
    alert_type: Optional[AlertType] = Field(None, description="预警类型")
    severity: Optional[str] = Field(None, description="严重程度")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    is_read: Optional[bool] = Field(None, description="是否已读")
    crop_type: Optional[CropType] = Field(None, description="作物类型")

    @field_validator("end_date")
    @classmethod
    def check_date_range(cls, v: Optional[datetime], info) -> Optional[datetime]:
        if v is not None and info.data.get("start_date") is not None:
            if v < info.data["start_date"]:
                raise ValueError("结束日期不能早于开始日期")
        return v


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="预警ID")
    user_id: int = Field(..., description="用户ID")
    grid_id: int = Field(..., description="网格单元ID")
    alert_type: AlertType = Field(..., description="预警类型")
    severity: str = Field(..., description="严重程度")
    threshold_exceeded: Optional[float] = Field(None, description="超出的阈值")
    message: str = Field(..., description="预警消息")
    triggered_at: datetime = Field(..., description="触发时间")
    notified_at: Optional[datetime] = Field(None, description="通知时间")
    is_read: bool = Field(..., description="是否已读")
    lat: Optional[float] = Field(None, description="纬度")
    lon: Optional[float] = Field(None, description="经度")
    crop_type: Optional[CropType] = Field(None, description="作物类型")


class NotificationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="通知日志ID")
    alert_id: int = Field(..., description="预警ID")
    channel: NotificationChannel = Field(..., description="通知渠道")
    recipient: str = Field(..., description="接收者")
    status: str = Field(..., description="状态")
    error_message: Optional[str] = Field(None, description="错误消息")
    sent_at: datetime = Field(..., description="发送时间")


class WebhookTestRequest(BaseModel):
    webhook_url: AnyUrl = Field(..., description="Webhook URL")
    payload: Optional[dict] = Field(None, description="测试载荷")


class AlertConfig(BaseModel):
    user_id: int = Field(..., gt=0, description="用户ID")
    crop_type: CropType = Field(..., description="作物类型")
    risk_threshold: float = Field(..., ge=0, le=100, description="风险阈值")
    alert_type: AlertType = Field(..., description="预警类型")
    channels: List[NotificationChannel] = Field(..., description="通知渠道列表")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("channels")
    @classmethod
    def check_channels_not_empty(cls, v: List[NotificationChannel]) -> List[NotificationChannel]:
        if len(v) == 0:
            raise ValueError("通知渠道列表不能为空")
        return v
