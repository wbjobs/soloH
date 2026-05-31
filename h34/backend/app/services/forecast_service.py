from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import to_shape

from app.db.models import ForecastData, GridCell
from app.schemas.forecast import ForecastDataCreate
from app.services.grid_service import GridService


class ForecastService:
    """WRF预报数据服务

    负责WRF数值预报数据的导入、查询和7天预报生成。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.grid_service = GridService(db)

    async def create_forecast_data_batch(
        self,
        data_list: List[ForecastDataCreate]
    ) -> int:
        """批量导入WRF预报数据"""
        forecast_data_list = [
            ForecastData(
                grid_id=data.grid_id,
                forecast_date=data.forecast_date,
                lead_time_hours=data.lead_time_hours,
                temperature=data.temperature,
                humidity=data.humidity,
                rainfall=data.rainfall,
                wind_speed=data.wind_speed,
            )
            for data in data_list
        ]

        self.db.add_all(forecast_data_list)
        await self.db.commit()

        return len(forecast_data_list)

    async def get_forecast_data(
        self,
        grid_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        lead_time_hours: Optional[int] = None,
        skip: int = 0,
        limit: int = 1000,
    ) -> Tuple[List[ForecastData], int]:
        """获取预报数据列表"""
        query = select(ForecastData)
        count_query = select(func.count(ForecastData.id))

        if grid_id is not None:
            query = query.where(ForecastData.grid_id == grid_id)
            count_query = count_query.where(ForecastData.grid_id == grid_id)

        if start_date is not None:
            query = query.where(ForecastData.forecast_date >= start_date)
            count_query = count_query.where(ForecastData.forecast_date >= start_date)

        if end_date is not None:
            query = query.where(ForecastData.forecast_date <= end_date)
            count_query = count_query.where(ForecastData.forecast_date <= end_date)

        if lead_time_hours is not None:
            query = query.where(ForecastData.lead_time_hours == lead_time_hours)
            count_query = count_query.where(ForecastData.lead_time_hours == lead_time_hours)

        query = query.order_by(
            ForecastData.forecast_date,
            ForecastData.lead_time_hours
        ).offset(skip).limit(limit)

        result = await self.db.execute(query)
        forecast_data = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        return forecast_data, total

    async def get_seven_day_forecast(
        self,
        lon: float,
        lat: float,
        days: int = 7,
    ) -> Optional[Dict[str, Any]]:
        """获取指定格点的7天天气预报

        Args:
            lon: 经度
            lat: 纬度
            days: 预报天数，默认7天

        Returns:
            包含7天逐日预报的字典，或None
        """
        grid_cell = await self.grid_service.get_grid_cell_by_point(lon, lat)
        if not grid_cell:
            return None

        centroid = to_shape(grid_cell.centroid)

        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=days)

        query = (
            select(ForecastData)
            .where(
                and_(
                    ForecastData.grid_id == grid_cell.id,
                    ForecastData.forecast_date >= start_date,
                    ForecastData.forecast_date < end_date,
                )
            )
            .order_by(ForecastData.forecast_date, ForecastData.lead_time_hours)
        )

        result = await self.db.execute(query)
        forecast_data = list(result.scalars().all())

        if not forecast_data:
            return await self._generate_simulated_forecast(
                grid_cell, centroid.x, centroid.y, days
            )

        daily_forecast = self._aggregate_daily_forecast(forecast_data, days)

        return {
            "grid_id": grid_cell.id,
            "lat": centroid.y,
            "lon": centroid.x,
            "start_date": start_date,
            "end_date": end_date - timedelta(days=1),
            "forecasts": daily_forecast,
            "generated_at": datetime.utcnow(),
        }

    def _aggregate_daily_forecast(
        self,
        forecast_data: List[ForecastData],
        days: int,
    ) -> List[Dict[str, Any]]:
        """聚合逐日预报数据"""
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        by_date: Dict[datetime, List[ForecastData]] = {}
        for fd in forecast_data:
            date_key = fd.forecast_date.replace(hour=0, minute=0, second=0, microsecond=0)
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append(fd)

        result = []
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            day_data = by_date.get(current_date, [])

            if not day_data:
                result.append(self._generate_simulated_day(current_date))
                continue

            temperatures = [d.temperature for d in day_data if d.temperature is not None]
            humidities = [d.humidity for d in day_data if d.humidity is not None]
            rainfalls = [d.rainfall for d in day_data if d.rainfall is not None]
            wind_speeds = [d.wind_speed for d in day_data if d.wind_speed is not None]

            result.append({
                "id": None,
                "grid_id": day_data[0].grid_id if day_data else None,
                "forecast_date": current_date,
                "lead_time_hours": 0,
                "temperature": round(np.mean(temperatures), 1) if temperatures else None,
                "humidity": round(np.mean(humidities), 1) if humidities else None,
                "rainfall": round(np.sum(rainfalls), 1) if rainfalls else None,
                "wind_speed": round(np.mean(wind_speeds), 1) if wind_speeds else None,
                "created_at": day_data[0].created_at if day_data else datetime.utcnow(),
                "temperature_range": {
                    "min": round(np.min(temperatures), 1) if len(temperatures) > 1 else None,
                    "max": round(np.max(temperatures), 1) if len(temperatures) > 1 else None,
                } if len(temperatures) > 1 else None,
                "data_points": len(day_data),
            })

        return result

    async def _generate_simulated_forecast(
        self,
        grid_cell: GridCell,
        lon: float,
        lat: float,
        days: int,
    ) -> Dict[str, Any]:
        """生成模拟预报数据（当没有真实数据时）"""
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        centroid = to_shape(grid_cell.centroid)

        daily_forecast = []
        day_of_year = start_date.timetuple().tm_yday
        seasonal_temp = 15 + 10 * np.sin(2 * np.pi * (day_of_year - 80) / 365)

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            hour_variation = 5 * np.sin(2 * np.pi * (12 - 6) / 24)

            temp_base = seasonal_temp + random.gauss(0, 1.5)
            temp_max = temp_base + hour_variation
            temp_min = temp_base - hour_variation
            humidity = 65 - hour_variation * 2.5 + random.gauss(0, 8)

            rainfall = 0.0
            if random.random() < 0.25:
                rainfall = max(0, random.gauss(6, 5))

            wind_speed = max(0, random.gauss(3.5, 2))

            daily_forecast.append({
                "id": None,
                "grid_id": grid_cell.id,
                "forecast_date": current_date,
                "lead_time_hours": 0,
                "temperature": round((temp_min + temp_max) / 2, 1),
                "humidity": round(humidity, 1),
                "rainfall": round(rainfall, 1),
                "wind_speed": round(wind_speed, 1),
                "created_at": datetime.utcnow(),
                "temperature_range": {
                    "min": round(temp_min, 1),
                    "max": round(temp_max, 1),
                },
                "data_points": 4,
                "is_simulated": True,
            })

        return {
            "grid_id": grid_cell.id,
            "lat": centroid.y,
            "lon": centroid.x,
            "start_date": start_date,
            "end_date": start_date + timedelta(days=days - 1),
            "forecasts": daily_forecast,
            "generated_at": datetime.utcnow(),
            "note": "使用模拟数据，建议接入真实WRF数据源",
        }

    def _generate_simulated_day(self, date: datetime) -> Dict[str, Any]:
        """生成单天模拟数据"""
        day_of_year = date.timetuple().tm_yday
        seasonal_temp = 15 + 10 * np.sin(2 * np.pi * (day_of_year - 80) / 365)

        temp = seasonal_temp + random.gauss(0, 2)
        humidity = max(20, min(98, 65 + random.gauss(0, 10)))
        rainfall = max(0, random.gauss(3, 5)) if random.random() < 0.25 else 0
        wind_speed = max(0, random.gauss(3.5, 2))

        return {
            "id": None,
            "grid_id": None,
            "forecast_date": date,
            "lead_time_hours": 0,
            "temperature": round(temp, 1),
            "humidity": round(humidity, 1),
            "rainfall": round(rainfall, 1),
            "wind_speed": round(wind_speed, 1),
            "created_at": datetime.utcnow(),
            "temperature_range": {
                "min": round(temp - 5, 1),
                "max": round(temp + 5, 1),
            },
            "data_points": 4,
            "is_simulated": True,
        }

    async def sync_wrf_data(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """同步WRF预报数据

        从外部API获取最新的WRF预报数据并导入数据库。
        这是一个占位实现，实际使用时需要根据具体的WRF数据源API进行适配。

        Args:
            api_url: WRF API地址
            api_key: API密钥
            days: 同步天数

        Returns:
            同步结果统计
        """
        from app.core.config import settings

        api_url = api_url or settings.WRF_API_URL
        api_key = api_key or settings.WRF_API_KEY

        if not api_url:
            return {
                "success": False,
                "message": "未配置WRF API地址",
                "imported_count": 0,
            }

        try:
            import httpx

            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    api_url,
                    headers=headers,
                    params={"days": days},
                )
                response.raise_for_status()

                forecast_data_list = response.json()

            imported = 0
            for item in forecast_data_list:
                forecast_create = ForecastDataCreate(
                    grid_id=item.get("grid_id"),
                    forecast_date=datetime.fromisoformat(item.get("forecast_date")),
                    lead_time_hours=item.get("lead_time_hours", 0),
                    temperature=item.get("temperature"),
                    humidity=item.get("humidity"),
                    rainfall=item.get("rainfall"),
                    wind_speed=item.get("wind_speed"),
                )
                await self.create_forecast_data_batch([forecast_create])
                imported += 1

            return {
                "success": True,
                "message": f"成功导入 {imported} 条预报数据",
                "imported_count": imported,
                "source": api_url,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"同步失败: {str(e)}",
                "imported_count": 0,
                "error": str(e),
            }


import random
