from datetime import datetime, timedelta
from typing import Annotated, Optional, Dict, Any

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models import Alert, GridCell, UserConfig, CropType, AlertType
from app.schemas.auth import CurrentUser
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.alert import (
    AlertResponse,
    AlertQueryParams,
    WebhookTestRequest,
)
from app.services import NotificationService, RiskEngine

router = APIRouter()


@router.get(
    "/list",
    response_model=ApiResponse[PaginatedResponse[AlertResponse]],
    summary="用户预警列表（分页、筛选）",
)
async def get_alerts(
    pagination: Annotated[PaginationParams, Depends()],
    query_params: Annotated[AlertQueryParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[PaginatedResponse[AlertResponse]]:
    query = select(Alert).where(Alert.user_id == current_user.id)

    if query_params.alert_type:
        query = query.where(Alert.alert_type == query_params.alert_type)
    if query_params.severity:
        query = query.where(Alert.severity == query_params.severity)
    if query_params.is_read is not None:
        query = query.where(Alert.is_read == query_params.is_read)
    if query_params.start_date:
        query = query.where(Alert.triggered_at >= query_params.start_date)
    if query_params.end_date:
        query = query.where(Alert.triggered_at <= query_params.end_date)

    count_query = select(func.count(Alert.id)).select_from(
        query.subquery()
    )
    total = await db.scalar(count_query) or 0

    query = query.order_by(Alert.triggered_at.desc()).offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    alerts = result.scalars().all()

    items = []
    for alert in alerts:
        grid_cell = alert.grid_cell
        alert_data = AlertResponse(
            id=alert.id,
            user_id=alert.user_id,
            grid_id=alert.grid_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            threshold_exceeded=alert.threshold_exceeded,
            message=alert.message,
            triggered_at=alert.triggered_at,
            notified_at=alert.notified_at,
            is_read=alert.is_read,
            lat=grid_cell.lat if grid_cell else None,
            lon=grid_cell.lon if grid_cell else None,
        )
        items.append(alert_data)

    return ApiResponse(
        data=PaginatedResponse(
            items=items,
            page=pagination.page,
            page_size=pagination.page_size,
            total=total,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size,
        )
    )


@router.get(
    "/{alert_id}",
    response_model=ApiResponse[AlertResponse],
    summary="预警详情",
)
async def get_alert_detail(
    alert_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[AlertResponse]:
    query = select(Alert).where(
        and_(
            Alert.id == alert_id,
            Alert.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="预警不存在或无权限访问",
        )

    grid_cell = alert.grid_cell
    response = AlertResponse(
        id=alert.id,
        user_id=alert.user_id,
        grid_id=alert.grid_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        threshold_exceeded=alert.threshold_exceeded,
        message=alert.message,
        triggered_at=alert.triggered_at,
        notified_at=alert.notified_at,
        is_read=alert.is_read,
        lat=grid_cell.lat if grid_cell else None,
        lon=grid_cell.lon if grid_cell else None,
    )

    return ApiResponse(data=response)


@router.put(
    "/{alert_id}/read",
    response_model=ApiResponse[AlertResponse],
    summary="标记已读",
)
async def mark_alert_read(
    alert_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[AlertResponse]:
    query = select(Alert).where(
        and_(
            Alert.id == alert_id,
            Alert.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="预警不存在或无权限访问",
        )

    alert.is_read = True
    await db.commit()
    await db.refresh(alert)

    grid_cell = alert.grid_cell
    response = AlertResponse(
        id=alert.id,
        user_id=alert.user_id,
        grid_id=alert.grid_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        threshold_exceeded=alert.threshold_exceeded,
        message=alert.message,
        triggered_at=alert.triggered_at,
        notified_at=alert.notified_at,
        is_read=alert.is_read,
        lat=grid_cell.lat if grid_cell else None,
        lon=grid_cell.lon if grid_cell else None,
    )

    return ApiResponse(data=response)


@router.put(
    "/read-all",
    response_model=ApiResponse[Dict[str, int]],
    summary="全部标记已读",
)
async def mark_all_alerts_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[Dict[str, int]]:
    update_stmt = (
        update(Alert)
        .where(
            and_(
                Alert.user_id == current_user.id,
                Alert.is_read == False,
            )
        )
        .values(is_read=True)
        .execution_options(synchronize_session="fetch")
    )

    result = await db.execute(update_stmt)
    await db.commit()

    updated_count = result.rowcount or 0

    return ApiResponse(
        data={
            "marked_read": updated_count,
        }
    )


@router.get(
    "/unread-count",
    response_model=ApiResponse[Dict[str, int]],
    summary="未读数量",
)
async def get_unread_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[Dict[str, int]]:
    count_query = select(func.count(Alert.id)).where(
        and_(
            Alert.user_id == current_user.id,
            Alert.is_read == False,
        )
    )
    unread_count = await db.scalar(count_query) or 0

    return ApiResponse(
        data={
            "unread_count": unread_count,
        }
    )


@router.post(
    "/test-webhook",
    response_model=ApiResponse[Dict[str, Any]],
    summary="测试Webhook",
)
async def test_webhook(
    request: WebhookTestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[Dict[str, Any]]:
    notification_service = NotificationService(db)

    webhook_url = str(request.webhook_url)
    success = await notification_service.test_webhook(webhook_url)

    if success:
        return ApiResponse(
            data={
                "success": True,
                "message": "Webhook测试成功",
                "webhook_url": webhook_url,
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook测试失败，请检查URL是否正确",
        )


@router.post(
    "/trigger-check",
    response_model=ApiResponse[Dict[str, Any]],
    summary="手动触发预警检查",
)
async def trigger_alert_check(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    crop_type: Annotated[
        Optional[CropType], Query(description="作物类型，不指定则检查所有作物")
    ] = None,
    forecast_date: Annotated[
        Optional[datetime], Query(description="预报日期，默认为今天")
    ] = None,
) -> ApiResponse[Dict[str, Any]]:
    if forecast_date is None:
        forecast_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    notification_service = NotificationService(db)
    risk_engine = RiskEngine(db)

    crop_types_to_check = [crop_type] if crop_type else list(CropType)

    total_triggered = 0
    results_by_crop: Dict[str, int] = {}

    for ct in crop_types_to_check:
        crop_str = ct.value if isinstance(ct, CropType) else ct
        triggered = await notification_service.check_and_trigger_alerts(
            crop_type=crop_str,
            forecast_date=forecast_date,
        )
        results_by_crop[crop_str] = triggered
        total_triggered += triggered

    return ApiResponse(
        data={
            "message": "预警检查完成",
            "forecast_date": forecast_date.isoformat(),
            "total_triggered": total_triggered,
            "results_by_crop": results_by_crop,
        }
    )
