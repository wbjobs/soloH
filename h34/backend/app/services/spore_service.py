from typing import List, Optional, Tuple
from datetime import datetime, timedelta

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import to_shape

from app.db.models import SporeSensor, SporeData, CropType
from app.schemas.spore import SporeSensorCreate, SporeDataCreate


class SporeService:
    """孢子数据服务

    负责孢子传感器管理、孢子浓度数据CRUD和空间查询。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_sensor(self, sensor_in: SporeSensorCreate) -> SporeSensor:
        """创建孢子传感器"""
        from geoalchemy2 import WKTElement

        location_wkt = f"POINT({sensor_in.lon} {sensor_in.lat})"
        location_geom = WKTElement(location_wkt, srid=4326)

        sensor = SporeSensor(
            name=sensor_in.name,
            code=sensor_in.code,
            location=location_geom,
            crop_type=sensor_in.crop_type,
            spore_type=sensor_in.spore_type,
            is_active=sensor_in.is_active,
        )

        self.db.add(sensor)
        await self.db.commit()
        await self.db.refresh(sensor)

        return sensor

    async def get_sensor(self, sensor_id: int) -> Optional[SporeSensor]:
        """获取单个孢子传感器"""
        query = select(SporeSensor).where(SporeSensor.id == sensor_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_sensors(
        self,
        crop_type: Optional[CropType] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[SporeSensor], int]:
        """获取孢子传感器列表"""
        query = select(SporeSensor)
        count_query = select(func.count(SporeSensor.id))

        if crop_type is not None:
            query = query.where(SporeSensor.crop_type == crop_type)
            count_query = count_query.where(SporeSensor.crop_type == crop_type)

        if is_active is not None:
            query = query.where(SporeSensor.is_active == is_active)
            count_query = count_query.where(SporeSensor.is_active == is_active)

        query = query.order_by(SporeSensor.name).offset(skip).limit(limit)

        result = await self.db.execute(query)
        sensors = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        return sensors, total

    async def get_nearby_sensors(
        self,
        lon: float,
        lat: float,
        crop_type: Optional[CropType] = None,
        radius_km: float = 100.0,
        limit: int = 5,
    ) -> List[Tuple[SporeSensor, float]]:
        """获取指定半径内的孢子传感器

        返回 (传感器, 距离公里) 列表，按距离排序。
        """
        point_wkt = f"POINT({lon} {lat})"

        query = (
            select(
                SporeSensor,
                (func.ST_Distance(
                    SporeSensor.location,
                    func.ST_GeographyFromText(point_wkt, 4326)
                ) / 1000.0).label("distance_km")
            )
            .where(
                and_(
                    SporeSensor.is_active == True,
                    func.ST_DWithin(
                        SporeSensor.location,
                        func.ST_GeographyFromText(point_wkt, 4326),
                        radius_km * 1000
                    )
                )
            )
            .order_by("distance_km")
            .limit(limit)
        )

        if crop_type is not None:
            query = query.where(SporeSensor.crop_type == crop_type)

        result = await self.db.execute(query)
        return [(row[0], row[1]) for row in result.all()]

    async def get_nearest_sensor(
        self,
        lon: float,
        lat: float,
        crop_type: Optional[CropType] = None,
        max_distance_km: float = 200.0,
    ) -> Optional[Tuple[SporeSensor, float]]:
        """获取最近的孢子传感器"""
        sensors = await self.get_nearby_sensors(
            lon=lon,
            lat=lat,
            crop_type=crop_type,
            radius_km=max_distance_km,
            limit=1
        )

        return sensors[0] if sensors else None

    async def create_spore_data(self, data_in: SporeDataCreate) -> SporeData:
        """创建单条孢子数据"""
        spore_data = SporeData(
            sensor_id=data_in.sensor_id,
            timestamp=data_in.timestamp,
            concentration=data_in.concentration,
        )

        self.db.add(spore_data)
        await self.db.commit()
        await self.db.refresh(spore_data)

        return spore_data

    async def create_spore_data_batch(
        self,
        data_list: List[SporeDataCreate]
    ) -> int:
        """批量创建孢子数据"""
        spore_data_list = [
            SporeData(
                sensor_id=data.sensor_id,
                timestamp=data.timestamp,
                concentration=data.concentration,
            )
            for data in data_list
        ]

        self.db.add_all(spore_data_list)
        await self.db.commit()

        return len(spore_data_list)

    async def get_spore_data(
        self,
        sensor_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 1000,
    ) -> Tuple[List[SporeData], int]:
        """获取孢子数据列表"""
        query = select(SporeData)
        count_query = select(func.count(SporeData.id))

        if sensor_id is not None:
            query = query.where(SporeData.sensor_id == sensor_id)
            count_query = count_query.where(SporeData.sensor_id == sensor_id)

        if start_date is not None:
            query = query.where(SporeData.timestamp >= start_date)
            count_query = count_query.where(SporeData.timestamp >= start_date)

        if end_date is not None:
            query = query.where(SporeData.timestamp <= end_date)
            count_query = count_query.where(SporeData.timestamp <= end_date)

        query = query.order_by(SporeData.timestamp.desc()).offset(skip).limit(limit)

        result = await self.db.execute(query)
        spore_data = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        return spore_data, total

    async def get_latest_spore_concentration(
        self,
        lon: float,
        lat: float,
        crop_type: Optional[CropType] = None,
        hours: int = 24,
    ) -> Optional[dict]:
        """获取指定位置最新的孢子浓度（空间加权平均）

        使用距离加权计算周围传感器的平均浓度。
        """
        sensors = await self.get_nearby_sensors(
            lon=lon,
            lat=lat,
            crop_type=crop_type,
            radius_km=150.0,
            limit=5
        )

        if not sensors:
            return None

        sensor_ids = [s[0].id for s in sensors]
        start_time = datetime.utcnow() - timedelta(hours=hours)

        query = (
            select(SporeData)
            .where(
                and_(
                    SporeData.sensor_id.in_(sensor_ids),
                    SporeData.timestamp >= start_time
                )
            )
            .order_by(SporeData.timestamp.desc())
        )

        result = await self.db.execute(query)
        all_data = list(result.scalars().all())

        if not all_data:
            return None

        latest_by_sensor = {}
        for data in all_data:
            if data.sensor_id not in latest_by_sensor:
                latest_by_sensor[data.sensor_id] = data

        sensor_distances = {s[0].id: s[1] for s in sensors}

        weights = []
        concentrations = []
        sensor_info = []

        for sensor_id, data in latest_by_sensor.items():
            distance = sensor_distances.get(sensor_id, 1.0)
            weight = 1.0 / (max(distance, 0.1) ** 2)

            weights.append(weight)
            concentrations.append(data.concentration)

            sensor = next((s[0] for s in sensors if s[0].id == sensor_id), None)
            if sensor:
                point = to_shape(sensor.location)
                sensor_info.append({
                    "sensor_id": sensor_id,
                    "sensor_name": sensor.name,
                    "distance_km": round(distance, 2),
                    "concentration": data.concentration,
                    "timestamp": data.timestamp,
                    "lon": point.x,
                    "lat": point.y,
                })

        total_weight = sum(weights)
        if total_weight == 0:
            return None

        weighted_concentration = sum(w * c for w, c in zip(weights, concentrations)) / total_weight
        max_concentration = max(concentrations)
        min_concentration = min(concentrations)

        return {
            "weighted_concentration": round(weighted_concentration, 2),
            "max_concentration": max_concentration,
            "min_concentration": min_concentration,
            "sensor_count": len(sensor_info),
            "sensors": sensor_info,
            "time_window_hours": hours,
        }
