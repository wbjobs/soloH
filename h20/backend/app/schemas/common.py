from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel, Field, field_validator

T = TypeVar('T')


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    pageSize: int = Field(default=20, ge=1, le=100, description="每页数量")

    @field_validator('pageSize')
    def check_page_size(cls, v):
        if v > 100:
            return 100
        return v


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T] = Field(description="数据列表")
    total: int = Field(description="总条数")
    page: int = Field(description="当前页码")
    pageSize: int = Field(description="每页数量")
    totalPages: int = Field(description="总页数")

    model_config = {
        "arbitrary_types_allowed": True,
        "from_attributes": True
    }
