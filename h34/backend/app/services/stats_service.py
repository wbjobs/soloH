from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, date

import numpy as np
from sqlalchemy import select, and_, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RiskGrid, Alert, UserConfig, CropType, GridCell
from app.schemas.stats import (
    RiskStatsResponse,
    AlertStatsResponse,
    MonthlyStats,
    DailyRiskTrend,
)


class StatsService:
    """统计分析服务

    负责风险统计、预警统计、历史趋势分析等统计功能。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_risk_stats(
        self,
        crop_type: CropType,
        period_start: date,
        period_end: date,
        user_id: Optional[int] = None,
    ) -> RiskStatsResponse:
        """获取风险统计数据

        Args:
            crop_type: 作物类型
            period_start: 统计开始日期
            period_end: 统计结束日期
            user_id: 可选的用户过滤

        Returns:
            风险统计响应
        """
        query = (
            select(
                RiskGrid.risk_index,
                RiskGrid.forecast_date,
                RiskGrid.grid_id,
            )
            .where(
                and_(
                    RiskGrid.crop_type == crop_type,
                    func.date(RiskGrid.forecast_date) >= period_start,
                    func.date(RiskGrid.forecast_date) <= period_end,
                )
            )
            .order_by(RiskGrid.forecast_date)
        )

        if user_id is not None:
            query = query.join(GridCell, RiskGrid.grid_id == GridCell.id)

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return RiskStatsResponse(
                crop_type=crop_type,
                period_start=period_start,
                period_end=period_end,
                overall_avg_risk=0.0,
                overall_max_risk=0.0,
                overall_min_risk=0.0,
                high_risk_area_count=0,
                medium_risk_area_count=0,
                low_risk_area_count=0,
                monthly_stats=[],
                daily_trend=[],
            )

        risk_values = [row.risk_index for row in rows if row.risk_index is not None]
        grid_ids = set(row.grid_id for row in rows)

        high_risk_count = sum(1 for r in risk_values if r >= 70)
        medium_risk_count = sum(1 for r in risk_values if 40 <= r < 70)
        low_risk_count = sum(1 for r in risk_values if r < 40)

        monthly_stats = await self._calculate_monthly_stats(
            crop_type, period_start, period_end
        )

        daily_trend = await self._calculate_daily_trend(
            crop_type, period_start, period_end
        )

        from app.core.constants import RISK_THRESHOLDS
        return RiskStatsResponse(
            crop_type=crop_type,
            period_start=period_start,
            period_end=period_end,
            overall_avg_risk=round(float(np.mean(risk_values)), 2),
            overall_max_risk=round(float(np.max(risk_values)), 2),
            overall_min_risk=round(float(np.min(risk_values)), 2),
            high_risk_area_count=len(set(
                row.grid_id for row in rows if row.risk_index >= RISK_THRESHOLDS["high"]
            )),
            medium_risk_area_count=len(set(
                row.grid_id for row in rows if RISK_THRESHOLDS["medium"] <= row.risk_index < RISK_THRESHOLDS["high"]
            )),
            low_risk_area_count=len(set(
                row.grid_id for row in rows if row.risk_index < RISK_THRESHOLDS["medium"]
            )),
            monthly_stats=monthly_stats,
            daily_trend=daily_trend,
            generated_at=datetime.utcnow(),
        )

    async def _calculate_monthly_stats(
        self,
        crop_type: CropType,
        period_start: date,
        period_end: date,
    ) -> List[MonthlyStats]:
        """计算月度统计数据"""
        from app.core.constants import RISK_THRESHOLDS
        query = (
            select(
                func.to_char(RiskGrid.forecast_date, 'YYYY-MM').label('month'),
                func.avg(RiskGrid.risk_index).label('avg_risk'),
                func.max(RiskGrid.risk_index).label('max_risk'),
                func.min(RiskGrid.risk_index).label('min_risk'),
                func.count(case(
                    (RiskGrid.risk_index >= RISK_THRESHOLDS["high"], 1)
                )).label('high_risk_days'),
                func.count(RiskGrid.id).label('data_points'),
            )
            .where(
                and_(
                    RiskGrid.crop_type == crop_type,
                    func.date(RiskGrid.forecast_date) >= period_start,
                    func.date(RiskGrid.forecast_date) <= period_end,
                )
            )
            .group_by(func.to_char(RiskGrid.forecast_date, 'YYYY-MM'))
            .order_by('month')
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            MonthlyStats(
                month=row.month,
                avg_risk=round(float(row.avg_risk or 0), 2),
                max_risk=round(float(row.max_risk or 0), 2),
                min_risk=round(float(row.min_risk or 0), 2),
                high_risk_days=int(row.high_risk_days or 0),
                data_points=int(row.data_points or 0),
            )
            for row in rows
        ]

    async def _calculate_daily_trend(
        self,
        crop_type: CropType,
        period_start: date,
        period_end: date,
    ) -> List[DailyRiskTrend]:
        """计算每日风险趋势"""
        query = (
            select(
                func.date(RiskGrid.forecast_date).label('date'),
                func.avg(RiskGrid.risk_index).label('avg_risk'),
            )
            .where(
                and_(
                    RiskGrid.crop_type == crop_type,
                    func.date(RiskGrid.forecast_date) >= period_start,
                    func.date(RiskGrid.forecast_date) <= period_end,
                )
            )
            .group_by(func.date(RiskGrid.forecast_date))
            .order_by('date')
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            DailyRiskTrend(
                date=row.date,
                avg_risk=round(float(row.avg_risk or 0), 2),
                risk_level=self._get_risk_level(float(row.avg_risk or 0)),
                crop_type=crop_type,
            )
            for row in rows
        ]

    async def get_alert_stats(
        self,
        period_start: date,
        period_end: date,
        user_id: Optional[int] = None,
    ) -> AlertStatsResponse:
        """获取预警统计数据

        Args:
            period_start: 统计开始日期
            period_end: 统计结束日期
            user_id: 可选的用户过滤

        Returns:
            预警统计响应
        """
        base_query = Alert.__table__.select().where(
            and_(
                func.date(Alert.triggered_at) >= period_start,
                func.date(Alert.triggered_at) <= period_end,
            )
        )

        if user_id is not None:
            base_query = base_query.where(Alert.user_id == user_id)

        result = await self.db.execute(base_query)
        all_alerts = list(result.scalars().all())

        total_alerts = len(all_alerts)

        alerts_by_type: Dict[str, int] = {}
        alerts_by_severity: Dict[str, int] = {}
        alerts_by_crop: Dict[str, int] = {}
        read_count = 0
        unread_count = 0

        for alert in all_alerts:
            alert_type = str(alert.alert_type) if alert.alert_type else 'unknown'
            alerts_by_type[alert_type] = alerts_by_type.get(alert_type, 0) + 1

            severity = alert.severity or 'unknown'
            alerts_by_severity[severity] = alerts_by_severity.get(severity, 0) + 1

            if alert.grid_cell and hasattr(alert.grid_cell, 'risk_grids'):
                for rg in alert.grid_cell.risk_grids:
                    crop = str(rg.crop_type) if rg.crop_type else 'unknown'
                    alerts_by_crop[crop] = alerts_by_crop.get(crop, 0) + 1
                    break

            if alert.is_read:
                read_count += 1
            else:
                unread_count += 1

        if not alerts_by_crop:
            alerts_by_crop = {c.value: 0 for c in CropType}

        notification_success_rate = await self._calculate_notification_success_rate(
            period_start, period_end, user_id
        )

        avg_response_time = await self._calculate_avg_response_time(
            period_start, period_end, user_id
        )

        return AlertStatsResponse(
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            total_alerts=total_alerts,
            alerts_by_type=alerts_by_type,
            alerts_by_severity=alerts_by_severity,
            alerts_by_crop=alerts_by_crop,
            read_alerts=read_count,
            unread_alerts=unread_count,
            notification_success_rate=round(notification_success_rate, 2),
            avg_response_time_minutes=avg_response_time,
            generated_at=datetime.utcnow(),
        )

    async def _calculate_notification_success_rate(
        self,
        period_start: date,
        period_end: date,
        user_id: Optional[int] = None,
    ) -> float:
        """计算通知成功率"""
        from app.db.models import NotificationLog

        query = select(NotificationLog).where(
            and_(
                func.date(NotificationLog.sent_at) >= period_start,
                func.date(NotificationLog.sent_at) <= period_end,
            )
        )

        if user_id is not None:
            query = query.join(Alert, NotificationLog.alert_id == Alert.id)
            query = query.where(Alert.user_id == user_id)

        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        if not logs:
            return 0.0

        success_count = sum(1 for log in logs if log.status == 'success')
        return (success_count / len(logs)) * 100

    async def _calculate_avg_response_time(
        self,
        period_start: date,
        period_end: date,
        user_id: Optional[int] = None,
    ) -> Optional[float]:
        """计算平均响应时间（分钟）"""
        query = (
            select(Alert)
            .where(
                and_(
                    Alert.is_read == True,
                    Alert.triggered_at is not None,
                    Alert.notified_at is not None,
                    func.date(Alert.triggered_at) >= period_start,
                    func.date(Alert.triggered_at) <= period_end,
                )
            )
        )

        if user_id is not None:
            query = query.where(Alert.user_id == user_id)

        result = await self.db.execute(query)
        alerts = list(result.scalars().all())

        if not alerts:
            return None

        response_times = []
        for alert in alerts:
            if alert.triggered_at and alert.notified_at:
                diff = (alert.notified_at - alert.triggered_at).total_seconds() / 60
                response_times.append(diff)

        if not response_times:
            return None

        return round(float(np.mean(response_times)), 2)

    async def get_risk_trend_data(
        self,
        crop_type: CropType,
        grid_id: Optional[int] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """获取风险趋势数据（用于图表）

        Args:
            crop_type: 作物类型
            grid_id: 可选的格点过滤
            days: 统计天数

        Returns:
            趋势数据列表，每个元素包含日期和风险指数
        """
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days - 1)

        query = (
            select(
                func.date(RiskGrid.forecast_date).label('date'),
                func.avg(RiskGrid.risk_index).label('avg_risk'),
                func.max(RiskGrid.risk_index).label('max_risk'),
                func.min(RiskGrid.risk_index).label('min_risk'),
                func.count(RiskGrid.id).label('count'),
            )
            .where(
                and_(
                    RiskGrid.crop_type == crop_type,
                    func.date(RiskGrid.forecast_date) >= start_date,
                    func.date(RiskGrid.forecast_date) <= end_date,
                )
            )
        )

        if grid_id is not None:
            query = query.where(RiskGrid.grid_id == grid_id)

        query = query.group_by(func.date(RiskGrid.forecast_date)).order_by('date')

        result = await self.db.execute(query)
        rows = result.all()

        data = []
        for row in rows:
            risk_level = self._get_risk_level(float(row.avg_risk or 0))
            data.append({
                "date": row.date.isoformat(),
                "label": row.date.strftime("%m/%d"),
                "avg_risk": round(float(row.avg_risk or 0), 2),
                "max_risk": round(float(row.max_risk or 0), 2),
                "min_risk": round(float(row.min_risk or 0), 2),
                "risk_level": risk_level,
                "count": int(row.count or 0),
            })

        return data

    @staticmethod
    def _get_risk_level(risk_index: float) -> str:
        """获取风险等级（英文标签，与前端阈值完全一致）

        使用统一的阈值配置，确保跨日期、跨模块的颜色图例一致性。

        Args:
            risk_index: 风险指数 (0-100)

        Returns:
            str: 风险等级 (low, medium, high, extreme)
        """
        from app.core.constants import get_risk_level_en
        return get_risk_level_en(risk_index)
