from datetime import datetime
from typing import Annotated, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models import CropType
from app.schemas.auth import CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.pesticide import (
    PesticideProductBase,
    PesticideProductResponse,
    EconomicThresholdRequest,
    EconomicThresholdResponse,
    SprayRecommendationRequest,
    SprayRecommendationResponse,
)
from app.services.pesticide_service import PesticideService

router = APIRouter()


@router.get(
    "/products",
    response_model=ApiResponse[List[PesticideProductResponse]],
    summary="获取农药产品列表",
)
async def get_products(
    crop_type: Annotated[Optional[CropType], Query(description="作物类型过滤")] = None,
    disease: Annotated[Optional[str], Query(description="病害名称过滤")] = None,
    resistance_risk: Annotated[Optional[str], Query(description="抗性风险过滤")] = None,
    active_only: Annotated[bool, Query(description="仅显示启用的")] = True,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[List[PesticideProductResponse]]:
    """
    获取农药产品列表
    """
    service = PesticideService(db)
    products = await service.list_products(
        crop_type=crop_type,
        disease=disease,
        resistance_risk=resistance_risk,
        active_only=active_only,
    )

    return ApiResponse(data=[
        PesticideProductResponse(
            id=p.id,
            product_name=p.product_name,
            registration_number=p.registration_number or "",
            active_ingredient=p.active_ingredient,
            formulation=p.formulation,
            target_crops=p.target_crops,
            target_diseases=p.target_diseases,
            recommended_dosage=p.recommended_dosage,
            dosage_ha=p.dosage_ha,
            unit=p.unit,
            pre_harvest_interval_days=p.pre_harvest_interval_days,
            safety_interval_days=p.safety_interval_days,
            rainfastness_hours=p.rainfastness_hours,
            price_per_unit=p.price_per_unit,
            efficacy_rating=p.efficacy_rating,
            resistance_risk=p.resistance_risk,
            restricted_use=p.restricted_use,
            notes=p.notes,
            is_active=p.is_active,
            created_at=p.created_at,
        )
        for p in products
    ])


@router.post(
    "/products",
    response_model=ApiResponse[PesticideProductResponse],
    summary="添加农药产品",
)
async def add_product(
    params: PesticideProductBase,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[PesticideProductResponse]:
    """
    添加新的农药产品
    """
    service = PesticideService(db)
    product = await service.add_product(
        product_name=params.product_name,
        registration_number=params.registration_number,
        active_ingredient=params.active_ingredient,
        formulation=params.formulation,
        target_crops=params.target_crops,
        target_diseases=params.target_diseases,
        recommended_dosage=params.recommended_dosage,
        dosage_ha=params.dosage_ha,
        unit=params.unit,
        pre_harvest_interval_days=params.pre_harvest_interval_days,
        safety_interval_days=params.safety_interval_days,
        rainfastness_hours=params.rainfastness_hours,
        price_per_unit=params.price_per_unit,
        efficacy_rating=params.efficacy_rating,
        resistance_risk=params.resistance_risk,
        restricted_use=params.restricted_use,
        notes=params.notes,
    )

    return ApiResponse(data=PesticideProductResponse(
        id=product.id,
        product_name=product.product_name,
        registration_number=product.registration_number or "",
        active_ingredient=product.active_ingredient,
        formulation=product.formulation,
        target_crops=product.target_crops,
        target_diseases=product.target_diseases,
        recommended_dosage=product.recommended_dosage,
        dosage_ha=product.dosage_ha,
        unit=product.unit,
        pre_harvest_interval_days=product.pre_harvest_interval_days,
        safety_interval_days=product.safety_interval_days,
        rainfastness_hours=product.rainfastness_hours,
        price_per_unit=product.price_per_unit,
        efficacy_rating=product.efficacy_rating,
        resistance_risk=product.resistance_risk,
        restricted_use=product.restricted_use,
        notes=product.notes,
        is_active=product.is_active,
        created_at=product.created_at,
    ))


@router.post(
    "/economic-threshold",
    response_model=ApiResponse[EconomicThresholdResponse],
    summary="计算经济阈值",
)
async def calculate_economic_threshold(
    params: EconomicThresholdRequest,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[EconomicThresholdResponse]:
    """
    计算经济阈值

    使用经典经济学模型：ET = (C × 100) / (Y × P × E)
    - C: 防治成本(元/公顷)
    - Y: 预期产量(吨/公顷)
    - P: 产品价格(元/吨)
    - E: 防治效果(0-1)
    """
    service = PesticideService(db)
    result = service.calculate_economic_threshold(
        crop_type=params.crop_type,
        yield_tons_ha=params.yield_tons_ha,
        price_yuan_ton=params.price_yuan_ton,
        control_cost_yuan_ha=params.control_cost_yuan_ha,
        efficacy=params.efficacy,
    )

    return ApiResponse(data=EconomicThresholdResponse(**result))


@router.post(
    "/recommendation",
    response_model=ApiResponse[SprayRecommendationResponse],
    summary="生成农药喷洒建议",
)
async def generate_spray_recommendation(
    params: SprayRecommendationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[SprayRecommendationResponse]:
    """
    综合生成农药喷洒建议

    综合考虑：
    - 气象模型风险指数
    - 无人机病害检测结果
    - 经济阈值分析
    - 成本收益分析
    - 农药选择（效果、成本、抗性管理）
    - 安全与环保建议
    """
    service = PesticideService(db)

    result = await service.generate_spray_recommendation(
        lon=params.lon,
        lat=params.lat,
        crop_type=params.crop_type,
        forecast_date=params.forecast_date,
        area_ha=params.area_ha,
        yield_tons_ha=params.yield_tons_ha,
        price_yuan_ton=params.price_yuan_ton,
        max_cost_yuan_ha=params.max_cost_yuan_ha,
        last_used_ingredient=params.last_used_ingredient,
        forecast_risk_trend=params.forecast_risk_trend,
    )

    return ApiResponse(data=SprayRecommendationResponse(**result))


@router.get(
    "/recommendation/point",
    response_model=ApiResponse[SprayRecommendationResponse],
    summary="获取单点喷洒建议",
)
async def get_recommendation_for_point(
    lon: Annotated[float, Query(..., description="经度", ge=-180, le=180)],
    lat: Annotated[float, Query(..., description="纬度", ge=-90, le=90)],
    crop_type: Annotated[CropType, Query(..., description="作物类型")],
    forecast_date: Annotated[Optional[datetime], Query(description="预报日期")] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[SprayRecommendationResponse]:
    """
    获取已保存的指定坐标点喷洒建议
    """
    service = PesticideService(db)
    result = await service.get_recommendation_for_point(
        lon=lon,
        lat=lat,
        crop_type=crop_type,
        forecast_date=forecast_date,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该点的喷洒建议",
        )

    return ApiResponse(data=SprayRecommendationResponse(**result))


@router.post(
    "/init-defaults",
    response_model=ApiResponse[dict],
    summary="初始化默认农药产品",
)
async def init_default_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[dict]:
    """
    初始化6种默认农药产品
    """
    service = PesticideService(db)
    products = await service.init_default_products()

    return ApiResponse(data={
        "initialized_count": len(products),
        "products": [
            {
                "id": p.id,
                "product_name": p.product_name,
                "active_ingredient": p.active_ingredient,
            }
            for p in products
        ],
    })


@router.post(
    "/recommendation/{recommendation_id}/mark-applied",
    response_model=ApiResponse[dict],
    summary="标记喷洒建议为已施药",
)
async def mark_recommendation_applied(
    recommendation_id: int,
    applied_at: Annotated[Optional[datetime], Query(description="施药时间")] = None,
    actual_dosage: Annotated[Optional[float], Query(description="实际用量", ge=0)] = None,
    notes: Annotated[Optional[str], Query(description="备注")] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[dict]:
    """
    标记喷洒建议为已施药
    """
    service = PesticideService(db)
    updated = await service.mark_recommendation_applied(
        recommendation_id=recommendation_id,
        applied_at=applied_at or datetime.utcnow(),
        actual_dosage=actual_dosage,
        notes=notes,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该喷洒建议",
        )

    return ApiResponse(data={
        "recommendation_id": updated.id,
        "is_applied": updated.is_applied,
        "applied_at": updated.applied_at.isoformat() if updated.applied_at else None,
        "actual_dosage": updated.actual_dosage,
        "notes": updated.notes,
    })
