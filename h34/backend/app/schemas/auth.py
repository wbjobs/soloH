from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict


class UserCreate(BaseModel):
    email: EmailStr = Field(..., description="用户邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="用户密码")
    full_name: Optional[str] = Field(None, max_length=100, description="用户全名")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码长度至少为6位")
        return v


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="用户邮箱")
    password: str = Field(..., description="用户密码")


class Token(BaseModel):
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="用户ID")
    email: EmailStr = Field(..., description="用户邮箱")
    full_name: Optional[str] = Field(None, description="用户全名")
    is_active: bool = Field(..., description="是否激活")
    created_at: datetime = Field(..., description="创建时间")


class CurrentUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="用户ID")
    email: EmailStr = Field(..., description="用户邮箱")
    full_name: Optional[str] = Field(None, description="用户全名")
    is_active: bool = Field(..., description="是否激活")
