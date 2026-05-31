from datetime import datetime, timedelta, date
from typing import Annotated, Optional, List, Dict

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func, and_, case, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models import (
    Alert,
    AlertType,
    CropType,
    NotificationLog,
    RiskGrid,
    GridCell,
)
from app.schemas.auth import CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.stats import (
    AlertStatsResponse,
    DailyRiskTrend,
    MonthlyStats,
    RiskStatsResponse,
)
from app.services import RiskEngine

router = APIRouter()


@router.get(
    "/risk",
    response_model=ApiResponse[RiskStatsResponse],
    summary="风险统计（按区域、时间）",
)
async def get_risk_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    crop_type: Annotated[CropType, Query(description="作物类型")],
    days: Annotated[int, Query(ge=1, le=365, description="统计天数")] = 30,
) -> ApiResponse[RiskStatsResponse]:
    end_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days - 1)

    query = select(RiskGrid).where(
        and_(
            RiskGrid.crop_type == crop_type,
            RiskGrid.forecast_date >= start_date,
            RiskGrid.forecast_date <= end_date,
        )
    )

    result = await db.execute(query)
    risk_data = result.scalars().all()

    if not risk_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到指定条件的风险数据",
        )

    risk_indices = [r.risk_index for r in risk_data]
    overall_avg_risk = sum(risk_indices) / len(risk_indices)
    overall_max_risk = max(risk_indices)
    overall_min_risk = min(risk_indices)

    high_risk_area_count = sum(1 for r in risk_indices if r >= 70)
    medium_risk_area_count = sum(1 for r in risk_indices if 40 <= r < 70)
    low_risk_area_count = sum(1 for r in risk_indices if r < 40)

    monthly_data: Dict[str, List[float]] = {}
    daily_data: Dict[date, Dict[str, List[float]]] = {}

    for r in risk_data:
        forecast_date = r.forecast_date.date()
        month_key = forecast_date.strftime("%Y-%m")

        if month_key not in monthly_data:
            monthly_data[month_key] = []
        monthly_data[month_key].append(r.risk_index)

        if forecast_date not in daily_data:
            daily_data[forecast_date] = {}
        if crop_type not in daily_data[forecast_date]:
            daily_data[forecast_date][crop_type] = []
        daily_data[forecast_date][crop_type].append(r.risk_index)

    monthly_stats: List[MonthlyStats] = []
    for month_key, values in sorted(monthly_data.items()):
        avg_risk = sum(values) / len(values)
        max_risk = max(values)
        min_risk = min(values)
        high_risk_days = sum(1 for v in values if v >= 70)

        monthly_stats.append(
            MonthlyStats(
                month=month_key,
                avg_risk=avg_risk,
                max_risk=max_risk,
                min_risk=min_risk,
                high_risk_days=high_risk_days,
                data_points=len(values),
            )
        )

    daily_trend: List[DailyRiskTrend] = []
    for d in sorted(daily_data.keys()):
        for ct, values in daily_data[d].items():
            avg_risk = sum(values) / len(values)
            risk_level = RiskEngine.get_risk_level(avg_risk)

            daily_trend.append(
                DailyRiskTrend(
                    date=d,
                    avg_risk=avg_risk,
                    risk_level=risk_level,
                    crop_type=ct,
                )
            )

    response = RiskStatsResponse(
        crop_type=crop_type,
        period_start=start_date.date(),
        period_end=end_date.date(),
        overall_avg_risk=overall_avg_risk,
        overall_max_risk=overall_max_risk,
        overall_min_risk=overall_min_risk,
        high_risk_area_count=high_risk_area_count,
        medium_risk_area_count=medium_risk_area_count,
        low_risk_area_count=low_risk_area_count,
        monthly_stats=monthly_stats,
        daily_trend=daily_trend,
    )

    return ApiResponse(data=response)


@router.get(
    "/alerts",
    response_model=ApiResponse[AlertStatsResponse],
    summary="预警统计",
)
async def get_alert_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    days: Annotated[int, Query(ge=1, le=365, description="统计天数")] = 30,
) -> ApiResponse[AlertStatsResponse]:
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days - 1)

    base_query = select(Alert).where(
        and_(
            Alert.user_id == current_user.id,
            Alert.triggered_at >= start_date,
            Alert.triggered_at <= end_date,
        )
    )

    result = await db.execute(base_query)
    alerts = result.scalars().all()

    total_alerts = len(alerts)

    alerts_by_type: Dict[AlertType, int] = {}
    alerts_by_severity: Dict[str, int] = {}
    alerts_by_crop: Dict[CropType, int] = {}
    read_alerts = 0
    unread_alerts = 0

    for alert in alerts:
        if alert.alert_type not in alerts_by_type:
            alerts_by_type[alert.alert_type] = 0
        alerts_by_type[alert.alert_type] += 1

        if alert.severity not in alerts_by_severity:
            alerts_by_severity[alert.severity] = 0
        alerts_by_severity[alert.severity] += 1

        risk_query = (
            select(RiskGrid)
            .where(
                and_(
                    RiskGrid.grid_id == alert.grid_id,
                    func.date(RiskGrid.forecast_date) == func.date(alert.triggered_at),
                )
            )
            .limit(1)
        )
        risk_result = await db.execute(risk_query)
        risk_data = risk_result.scalar_one_or_none()

        if risk_data:
            crop_type = risk_data.crop_type
            if crop_type not in alerts_by_crop:
                alerts_by_crop[crop_type] = 0
            alerts_by_crop[crop_type] += 1

        if alert.is_read:
            read_alerts += 1
        else:
            unread_alerts += 1

    for at in AlertType:
        if at not in alerts_by_type:
            alerts_by_type[at] = 0

    for ct in CropType:
        if ct not in alerts_by_crop:
            alerts_by_crop[ct] = 0

    log_query = (
        select(NotificationLog)
        .join(Alert, NotificationLog.alert_id == Alert.id)
        .where(
            and_(
                Alert.user_id == current_user.id,
                NotificationLog.sent_at >= start_date,
                NotificationLog.sent_at <= end_date,
            )
        )
    )
    log_result = await db.execute(log_query)
    notification_logs = log_result.scalars().all()

    total_notifications = len(notification_logs)
    if total_notifications > 0:
        successful_notifications = sum(
            1 for log in notification_logs if log.status == "success"
        )
        notification_success_rate = (successful_notifications / total_notifications) * 100
    else:
        notification_success_rate = 0.0

    avg_response_time_minutes: Optional[float] = None
    read_alerts_with_times = [
        a for a in alerts if a.is_read and a.notified_at is not None
    ]
    if read_alerts_with_times:
        response_times = []
        for a in read_alerts_with_times:
            if a.notified_at:
                response_time = (a.triggered_at - a.notified_at).total_seconds() / 60
                response_times.append(abs(response_time))
        if response_times:
            avg_response_time_minutes = sum(response_times) / len(response_times)

    response = AlertStatsResponse(
        user_id=current_user.id,
        period_start=start_date.date(),
        period_end=end_date.date(),
        total_alerts=total_alerts,
        alerts_by_type=alerts_by_type,
        alerts_by_severity=alerts_by_severity,
        alerts_by_crop=alerts_by_crop,
        read_alerts=read_alerts,
        unread_alerts=unread_alerts,
        notification_success_rate=notification_success_rate,
        avg_response_time_minutes=avg_response_time_minutes,
    )

    return ApiResponse(data=response)


@router.get(
    "/trend",
    response_model=ApiResponse[List[DailyRiskTrend]],
    summary="风险趋势数据（用于图表）",
)
async def get_risk_trend(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    crop_type: Annotated[CropType, Query(description="作物类型")],
    days: Annotated[int, Query(ge=1, le=365, description="统计天数")] = 30,
) -> ApiResponse[List[DailyRiskTrend]]:
    end_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days - 1)

    query = (
        select(
            func.date(RiskGrid.forecast_date).label("forecast_date"),
            func.avg(RiskGrid.risk_index).label("avg_risk"),
            RiskGrid.crop_type,
        )
        .where(
            and_(
                RiskGrid.crop_type == crop_type,
                RiskGrid.forecast_date >= start_date,
                RiskGrid.forecast_date <= end_date,
            )
        )
        .group_by(func.date(RiskGrid.forecast_date), RiskGrid.crop_type)
        .order_by(func.date(RiskGrid.forecast_date))
    )

    result = await db.execute(query)
    trend_data = result.all()

    if not trend_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到指定条件的风险趋势数据",
        )

    daily_trend: List[DailyRiskTrend] = []
    for row in trend_data:
        forecast_date = row.forecast_date
        avg_risk = float(row.avg_risk)
        risk_level = RiskEngine.get_risk_level(avg_risk)

        daily_trend.append(
            DailyRiskTrend(
                date=forecast_date,
                avg_risk=avg_risk,
                risk_level=risk_level,
                crop_type=row.crop_type,
            )
        )

    return ApiResponse(data=daily_trend)
