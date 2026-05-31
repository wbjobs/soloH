from typing import Annotated, Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import get_address_service, get_graph_service
from app.services import AddressService, GraphService
from app.schemas import (
    AddressResponse,
    AddressListResponse,
    PaginatedResponse,
    PaginationParams,
    TransactionListResponse,
    SuspiciousScoreResponse,
    SubgraphResponse,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AddressListResponse])
async def get_addresses(
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[AddressService, Depends(get_address_service)],
    minBalance: Optional[float] = Query(None, ge=0, description="最小余额"),
    minSuspiciousScore: Optional[float] = Query(None, ge=0, le=100, description="最小可疑分数"),
    addressType: Optional[str] = Query(None, description="地址类型"),
):
    """获取地址列表"""
    return await service.get_addresses(
        page=pagination.page,
        page_size=pagination.pageSize,
        min_balance=minBalance,
        min_suspicious_score=minSuspiciousScore,
        address_type=addressType,
    )


@router.get("/top", response_model=List[AddressListResponse])
async def get_top_addresses(
    service: Annotated[AddressService, Depends(get_address_service)],
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    sortBy: str = Query(
        "balance",
        pattern="^(balance|tx_count|suspicious_score|received|sent)$",
        description="排序字段",
    ),
):
    """获取TOP地址"""
    return await service.get_top_addresses(limit=limit, sort_by=sortBy)


@router.get("/{address}", response_model=AddressResponse)
async def get_address_detail(
    address: str,
    service: Annotated[AddressService, Depends(get_address_service)],
):
    """获取地址详情"""
    addr = await service.get_address_detail(address)
    if not addr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Address {address} not found",
        )
    return addr


@router.get("/{address}/subgraph", response_model=SubgraphResponse)
async def get_address_subgraph(
    address: str,
    service: Annotated[AddressService, Depends(get_address_service)],
    depth: int = Query(2, ge=1, le=5, description="遍历深度"),
    minValue: Optional[float] = Query(None, ge=0, description="最小交易金额"),
):
    """获取地址关联子图"""
    return await service.get_address_subgraph(
        address=address,
        depth=depth,
        min_value=minValue,
    )


@router.get("/{address}/suspicious-score", response_model=SuspiciousScoreResponse)
async def get_suspicious_score(
    address: str,
    service: Annotated[AddressService, Depends(get_address_service)],
):
    """获取可疑评分"""
    score = await service.get_suspicious_score(address)
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Address {address} not found",
        )
    return score


@router.get("/{address}/transactions", response_model=PaginatedResponse[TransactionListResponse])
async def get_address_transactions(
    address: str,
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[AddressService, Depends(get_address_service)],
):
    """获取地址交易历史"""
    addr = await service.get_address_detail(address)
    if not addr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Address {address} not found",
        )

    return await service.get_address_transactions(
        address=address,
        page=pagination.page,
        page_size=pagination.pageSize,
    )
