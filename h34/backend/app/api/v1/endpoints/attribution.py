from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models import CropType
from app.schemas.auth import CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.attribution import (
    AttributionBase,
    AttributionResponse,
    AttributionSummaryResponse,
)
from app.services.attribution_service import AttributionService

router = APIRouter()


@router.post(
    "/calculate",
    response_model=ApiResponse[AttributionResponse],
    summary="计算单点风险归因分析",
)
async def calculate_attribution(
    params: AttributionBase,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[AttributionResponse]:
    """
    计算指定坐标点的风险归因分析

    使用SHAP值解释各因素（温度、湿度、叶面湿润、孢子浓度、抗性）对风险的贡献
    """
    service = AttributionService(db)
    result = await service.calculate_point_attribution(
        lon=params.lon,
        lat=params.lat,
        crop_type=params.crop_type,
        forecast_date=params.forecast_date,
        resistance_level=params.resistance_level,
    )

    return ApiResponse(data=AttributionResponse(**result))


@router.get(
    "/point",
    response_model=ApiResponse[AttributionResponse],
    summary="获取单点归因分析结果",
)
async def get_attribution(
    lon: Annotated[float, Query(..., description="经度", ge=-180, le=180)],
    lat: Annotated[float, Query(..., description="纬度", ge=-90, le=90)],
    crop_type: Annotated[CropType, Query(..., description="作物类型")],
    forecast_date: Annotated[
        Optional[datetime], Query(description="预报日期")
    ] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[AttributionResponse]:
    """
    获取已保存的指定坐标点归因分析结果
    """
    service = AttributionService(db)
    result = await service.get_attribution_for_point(
        lon=lon,
        lat=lat,
        crop_type=crop_type,
        forecast_date=forecast_date,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该点的归因分析结果",
        )

    return ApiResponse(data=AttributionResponse(**result))


@router.get(
    "/dominant-summary",
    response_model=ApiResponse[AttributionSummaryResponse],
    summary="获取区域主导因素统计",
)
async def get_dominant_factors_summary(
    crop_type: Annotated[CropType, Query(..., description="作物类型")],
    forecast_date: Annotated[
        Optional[datetime], Query(description="预报日期")
    ] = None,
    lon_min: Annotated[Optional[float], Query(description="最小经度", ge=-180, le=180)] = None,
    lat_min: Annotated[Optional[float], Query(description="最小纬度", ge=-90, le=90)] = None,
    lon_max: Annotated[Optional[float], Query(description="最大经度", ge=-180, le=180)] = None,
    lat_max: Annotated[Optional[float], Query(description="最大纬度", ge=-90, le=90)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[AttributionSummaryResponse]:
    """
    统计分析区域内各因素作为主导因素的分布情况

    用于了解当前病害风险主要由哪些因素驱动
    """
    bounds = None
    if lon_min is not None and lat_min is not None and lon_max is not None and lat_max is not None:
        bounds = (lon_min, lat_min, lon_max, lat_max)

    service = AttributionService(db)
    result = await service.analyze_dominant_factors(
        crop_type=crop_type,
        forecast_date=forecast_date,
        bounds=bounds,
    )

    return ApiResponse(data=AttributionSummaryResponse(**result))


@router.post(
    "/save",
    response_model=ApiResponse[dict],
    summary="保存归因分析结果",
)
async def save_attribution(
    params: AttributionBase,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[dict]:
    """
    计算并保存单点风险归因分析结果到数据库
    """
    service = AttributionService(db)

    result = await service.calculate_point_attribution(
        lon=params.lon,
        lat=params.lat,
        crop_type=params.crop_type,
        forecast_date=params.forecast_date,
        resistance_level=params.resistance_level,
    )

    saved = await service.save_attribution(
        grid_id=result["grid_id"],
        forecast_date=params.forecast_date or datetime.utcnow(),
        crop_type=params.crop_type,
        risk_index=result["risk_index"],
        attribution=result["attribution"],
    )

    return ApiResponse(data={
        "attribution_id": saved.id,
        "grid_id": saved.grid_id,
        "dominant_factor": saved.dominant_factor,
        "dominant_factor_contribution": saved.dominant_factor_contribution,
        "risk_index": saved.risk_index,
    })
