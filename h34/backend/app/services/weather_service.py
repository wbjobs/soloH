from typing import List, Optional, Tuple
from datetime import datetime, timedelta

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import to_shape

from app.db.models import WeatherStation, WeatherData
from app.schemas.weather import WeatherStationCreate, WeatherDataCreate
from app.services.grid_service import GridService


class WeatherService:
    """气象数据服务

    负责气象站管理、气象数据CRUD、空间查询和数据插值。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.grid_service = GridService(db)

    async def create_station(self, station_in: WeatherStationCreate) -> WeatherStation:
        """创建气象站"""
        from geoalchemy2 import WKTElement

        location_wkt = f"POINT({station_in.lon} {station_in.lat})"
        location_geom = WKTElement(location_wkt, srid=4326)

        station = WeatherStation(
            name=station_in.name,
            code=station_in.code,
            location=location_geom,
            elevation=station_in.elevation,
            is_active=station_in.is_active,
        )

        self.db.add(station)
        await self.db.commit()
        await self.db.refresh(station)

        return station

    async def get_station(self, station_id: int) -> Optional[WeatherStation]:
        """获取单个气象站"""
        query = select(WeatherStation).where(WeatherStation.id == station_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_stations(
        self,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[WeatherStation], int]:
        """获取气象站列表"""
        query = select(WeatherStation)
        count_query = select(func.count(WeatherStation.id))

        if is_active is not None:
            query = query.where(WeatherStation.is_active == is_active)
            count_query = count_query.where(WeatherStation.is_active == is_active)

        query = query.order_by(WeatherStation.name).offset(skip).limit(limit)

        result = await self.db.execute(query)
        stations = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        return stations, total

    async def get_nearby_stations(
        self,
        lon: float,
        lat: float,
        radius_km: float = 50.0,
        limit: int = 10,
    ) -> List[WeatherStation]:
        """获取指定半径内的气象站

        使用Haversine公式计算距离，按距离排序。
        """
        point_wkt = f"POINT({lon} {lat})"

        query = (
            select(
                WeatherStation,
                func.ST_Distance(
                    WeatherStation.location,
                    func.ST_GeographyFromText(point_wkt, 4326)
                ).label("distance")
            )
            .where(
                and_(
                    WeatherStation.is_active == True,
                    func.ST_DWithin(
                        WeatherStation.location,
                        func.ST_GeographyFromText(point_wkt, 4326),
                        radius_km * 1000
                    )
                )
            )
            .order_by("distance")
            .limit(limit)
        )

        result = await self.db.execute(query)
        return [row[0] for row in result.all()]

    async def create_weather_data(self, data_in: WeatherDataCreate) -> WeatherData:
        """创建单条气象数据"""
        weather_data = WeatherData(
            station_id=data_in.station_id,
            timestamp=data_in.timestamp,
            temperature=data_in.temperature,
            relative_humidity=data_in.relative_humidity,
            rainfall=data_in.rainfall,
            leaf_wetness_duration=data_in.leaf_wetness_duration,
            wind_speed=data_in.wind_speed,
            solar_radiation=data_in.solar_radiation,
        )

        self.db.add(weather_data)
        await self.db.commit()
        await self.db.refresh(weather_data)

        return weather_data

    async def create_weather_data_batch(
        self,
        data_list: List[WeatherDataCreate]
    ) -> int:
        """批量创建气象数据"""
        weather_data_list = [
            WeatherData(
                station_id=data.station_id,
                timestamp=data.timestamp,
                temperature=data.temperature,
                relative_humidity=data.relative_humidity,
                rainfall=data.rainfall,
                leaf_wetness_duration=data.leaf_wetness_duration,
                wind_speed=data.wind_speed,
                solar_radiation=data.solar_radiation,
            )
            for data in data_list
        ]

        self.db.add_all(weather_data_list)
        await self.db.commit()

        return len(weather_data_list)

    async def get_latest_weather_data(
        self,
        station_id: Optional[int] = None,
    ) -> List[WeatherData]:
        """获取各气象站最新数据"""
        subquery = (
            select(
                WeatherData.station_id,
                func.max(WeatherData.timestamp).label("max_timestamp")
            )
            .group_by(WeatherData.station_id)
            .subquery()
        )

        query = (
            select(WeatherData)
            .join(
                subquery,
                and_(
                    WeatherData.station_id == subquery.c.station_id,
                    WeatherData.timestamp == subquery.c.max_timestamp
                )
            )
            .order_by(WeatherData.station_id)
        )

        if station_id is not None:
            query = query.where(WeatherData.station_id == station_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_weather_data_for_grid(
        self,
        grid_id: int,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> List[WeatherData]:
        """获取指定格点的气象数据（从周围气象站插值）"""
        grid_cell = await self.grid_service.get_grid_cell_by_point(0, 0)
        if not grid_cell:
            return []

        centroid = to_shape(grid_cell.centroid)
        stations = await self.get_nearby_stations(
            lon=centroid.x,
            lat=centroid.y,
            radius_km=100.0
        )

        if not stations:
            return []

        station_ids = [s.id for s in stations]

        if end_date is None:
            end_date = start_date + timedelta(days=1)

        query = (
            select(WeatherData)
            .where(
                and_(
                    WeatherData.station_id.in_(station_ids),
                    WeatherData.timestamp >= start_date,
                    WeatherData.timestamp < end_date
                )
            )
            .order_by(WeatherData.timestamp)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def interpolate_weather_for_point(
        self,
        lon: float,
        lat: float,
        timestamp: datetime,
        radius_km: float = 50.0,
    ) -> dict:
        """对指定点进行气象要素空间插值

        使用反距离加权(IDW)插值周围气象站数据。
        """
        stations = await self.get_nearby_stations(lon, lat, radius_km)

        if not stations:
            return {
                "temperature": None,
                "relative_humidity": None,
                "rainfall": None,
                "leaf_wetness_duration": None,
                "wind_speed": None,
                "solar_radiation": None,
                "source_stations": 0,
            }

        station_ids = [s.id for s in stations]
        start_time = timestamp - timedelta(hours=1)
        end_time = timestamp + timedelta(hours=1)

        query = (
            select(WeatherData, WeatherStation)
            .join(WeatherStation, WeatherData.station_id == WeatherStation.id)
            .where(
                and_(
                    WeatherData.station_id.in_(station_ids),
                    WeatherData.timestamp >= start_time,
                    WeatherData.timestamp <= end_time
                )
            )
            .order_by(func.abs(func.extract('epoch', WeatherData.timestamp - timestamp)))
        )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return {
                "temperature": None,
                "relative_humidity": None,
                "rainfall": None,
                "leaf_wetness_duration": None,
                "wind_speed": None,
                "solar_radiation": None,
                "source_stations": 0,
            }

        points = []
        values = {
            "temperature": [],
            "relative_humidity": [],
            "rainfall": [],
            "leaf_wetness_duration": [],
            "wind_speed": [],
            "solar_radiation": [],
        }

        for weather_data, station in rows:
            station_point = to_shape(station.location)
            points.append((station_point.x, station_point.y))

            if weather_data.temperature is not None:
                values["temperature"].append((station_point.x, station_point.y, weather_data.temperature))
            if weather_data.relative_humidity is not None:
                values["relative_humidity"].append((station_point.x, station_point.y, weather_data.relative_humidity))
            if weather_data.rainfall is not None:
                values["rainfall"].append((station_point.x, station_point.y, weather_data.rainfall))
            if weather_data.leaf_wetness_duration is not None:
                values["leaf_wetness_duration"].append((station_point.x, station_point.y, weather_data.leaf_wetness_duration))
            if weather_data.wind_speed is not None:
                values["wind_speed"].append((station_point.x, station_point.y, weather_data.wind_speed))
            if weather_data.solar_radiation is not None:
                values["solar_radiation"].append((station_point.x, station_point.y, weather_data.solar_radiation))

        def idw_interpolate(data_points, target_lon, target_lat):
            if not data_points:
                return None

            if len(data_points) == 1:
                return data_points[0][2]

            import math

            weights = []
            values_list = []

            for px, py, val in data_points:
                dist = GridService.calculate_haversine_distance(px, py, target_lon, target_lat)
                if dist < 0.001:
                    return val

                weight = 1.0 / (dist ** 2)
                weights.append(weight)
                values_list.append(val)

            total_weight = sum(weights)
            if total_weight == 0:
                return None

            return sum(w * v for w, v in zip(weights, values_list)) / total_weight

        result = {
            "temperature": idw_interpolate(values["temperature"], lon, lat),
            "relative_humidity": idw_interpolate(values["relative_humidity"], lon, lat),
            "rainfall": idw_interpolate(values["rainfall"], lon, lat),
            "leaf_wetness_duration": idw_interpolate(values["leaf_wetness_duration"], lon, lat),
            "wind_speed": idw_interpolate(values["wind_speed"], lon, lat),
            "solar_radiation": idw_interpolate(values["solar_radiation"], lon, lat),
            "source_stations": len(set(station_ids)),
        }

        return result
