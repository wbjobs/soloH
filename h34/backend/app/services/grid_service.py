import math
from typing import List, Optional, Tuple
from datetime import datetime

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape, from_shape
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GridCell


class GridService:
    """格点管理服务

    负责1km分辨率格网的创建、查询和空间几何计算。
    考虑地球曲率对经度间距的影响，实现精确的地理转换。
    """

    EARTH_RADIUS_KM = 6371.0088
    LATITUDE_DEGREE_KM = 110.574
    RESOLUTION_KM = 1.0

    def __init__(self, db: AsyncSession):
        self.db = db

    @classmethod
    def _km_to_latitude_degrees(cls, km: float) -> float:
        """将公里转换为纬度度数

        纬度方向的度数间距基本恒定，约为110.574km/度。

        Args:
            km: 公里数

        Returns:
            float: 纬度度数
        """
        return km / cls.LATITUDE_DEGREE_KM

    @classmethod
    def _km_to_longitude_degrees(cls, km: float, latitude: float) -> float:
        """将公里转换为经度度数（考虑纬度变形）

        经度方向的度数间距随纬度变化：
        1度经度 = 111.320 * cos(纬度) 公里

        Args:
            km: 公里数
            latitude: 所在纬度（度）

        Returns:
            float: 经度度数
        """
        lat_rad = math.radians(latitude)
        longitude_degree_km = 111.320 * math.cos(lat_rad)
        return km / longitude_degree_km if longitude_degree_km > 0 else 0.0

    @classmethod
    def _calculate_grid_step(
        cls,
        center_lat: float,
        resolution_km: float = 1.0
    ) -> Tuple[float, float]:
        """计算指定纬度处1km格网的经纬度步长

        Args:
            center_lat: 格网中心纬度（度）
            resolution_km: 格网分辨率（公里）

        Returns:
            Tuple[float, float]: (纬度步长, 经度步长) 单位：度
        """
        lat_step = cls._km_to_latitude_degrees(resolution_km)
        lon_step = cls._km_to_longitude_degrees(resolution_km, center_lat)
        return lat_step, lon_step

    @classmethod
    def generate_grid_geometries(
        cls,
        center_lon: float,
        center_lat: float,
        resolution_km: float = 1.0
    ) -> Tuple[Point, Polygon]:
        """生成格点的中心点和边界多边形

        以中心点为基准，向四个方向各延伸分辨率的一半，
        形成正方形格网单元。

        Args:
            center_lon: 中心点经度（度）
            center_lat: 中心点纬度（度）
            resolution_km: 格网分辨率（公里）

        Returns:
            Tuple[Point, Polygon]: (中心点, 边界多边形) WGS84坐标系
        """
        lat_step, lon_step = cls._calculate_grid_step(center_lat, resolution_km)

        half_lat = lat_step / 2.0
        half_lon = lon_step / 2.0

        min_lon = center_lon - half_lon
        max_lon = center_lon + half_lon
        min_lat = center_lat - half_lat
        max_lat = center_lat + half_lat

        centroid = Point(center_lon, center_lat)
        bounds = Polygon([
            (min_lon, min_lat),
            (max_lon, min_lat),
            (max_lon, max_lat),
            (min_lon, max_lat),
            (min_lon, min_lat)
        ])

        return centroid, bounds

    async def create_grid_for_region(
        self,
        lon_min: float,
        lon_max: float,
        lat_min: float,
        lat_max: float,
        resolution_km: float = 1.0
    ) -> List[GridCell]:
        """为指定经纬度范围创建1km分辨率格点

        算法说明：
        1. 计算区域中心纬度，确定经度方向的步长
        2. 按照步长在经纬度方向上均匀划分网格
        3. 为每个网格单元生成中心点和边界多边形
        4. 批量插入数据库，避免重复创建

        Args:
            lon_min: 最小经度（度）
            lon_max: 最大经度（度）
            lat_min: 最小纬度（度）
            lat_max: 最大纬度（度）
            resolution_km: 格网分辨率（公里），默认1km

        Returns:
            List[GridCell]: 创建的格点列表
        """
        center_lat = (lat_min + lat_max) / 2.0
        lat_step, lon_step = self._calculate_grid_step(center_lat, resolution_km)

        num_lon = int(math.ceil((lon_max - lon_min) / lon_step))
        num_lat = int(math.ceil((lat_max - lat_min) / lat_step))

        start_lon = lon_min + lon_step / 2.0
        start_lat = lat_min + lat_step / 2.0

        existing_cells = await self._get_existing_grid_cells(
            lon_min, lon_max, lat_min, lat_max
        )
        existing_keys = {(cell.grid_x, cell.grid_y) for cell in existing_cells}

        new_cells: List[GridCell] = []

        for grid_y in range(num_lat):
            center_lat = start_lat + grid_y * lat_step
            _, current_lon_step = self._calculate_grid_step(center_lat, resolution_km)
            current_start_lon = lon_min + current_lon_step / 2.0

            for grid_x in range(num_lon):
                if (grid_x, grid_y) in existing_keys:
                    continue

                center_lon = current_start_lon + grid_x * current_lon_step
                centroid, bounds = self.generate_grid_geometries(
                    center_lon, center_lat, resolution_km
                )

                cell = GridCell(
                    grid_x=grid_x,
                    grid_y=grid_y,
                    centroid=from_shape(centroid, srid=4326),
                    bounds=from_shape(bounds, srid=4326),
                    resolution_km=resolution_km,
                    created_at=datetime.utcnow()
                )
                new_cells.append(cell)

        if new_cells:
            self.db.add_all(new_cells)
            await self.db.commit()
            for cell in new_cells:
                await self.db.refresh(cell)

        return existing_cells + new_cells

    async def _get_existing_grid_cells(
        self,
        lon_min: float,
        lon_max: float,
        lat_min: float,
        lat_max: float
    ) -> List[GridCell]:
        """获取指定范围内已存在的格点"""
        bbox_wkt = f"POLYGON(({lon_min} {lat_min}, {lon_max} {lat_min}, {lon_max} {lat_max}, {lon_min} {lat_max}, {lon_min} {lat_min}))"
        bbox_geom = WKTElement(bbox_wkt, srid=4326)

        query = select(GridCell).where(
            func.ST_Intersects(GridCell.bounds, bbox_geom)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_grid_cell_by_point(
        self,
        longitude: float,
        latitude: float
    ) -> Optional[GridCell]:
        """根据经纬度点查找所属格点

        使用ST_Contains空间查询，高效定位包含该点的格网单元。

        Args:
            longitude: 经度（度）
            latitude: 纬度（度）

        Returns:
            Optional[GridCell]: 包含该点的格点，若不存在则返回None
        """
        point_wkt = f"POINT({longitude} {latitude})"
        point_geom = WKTElement(point_wkt, srid=4326)

        query = select(GridCell).where(
            func.ST_Contains(GridCell.bounds, point_geom)
        ).limit(1)

        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_or_create_grid_cell(
        self,
        longitude: float,
        latitude: float,
        resolution_km: float = 1.0
    ) -> GridCell:
        """获取或创建包含指定点的格点

        如果格点不存在，则以该点为中心创建一个新格点。

        Args:
            longitude: 经度（度）
            latitude: 纬度（度）
            resolution_km: 格网分辨率（公里）

        Returns:
            GridCell: 格点对象
        """
        cell = await self.get_grid_cell_by_point(longitude, latitude)
        if cell:
            return cell

        lat_step, lon_step = self._calculate_grid_step(latitude, resolution_km)

        grid_x = int(round((longitude + 180.0) / lon_step))
        grid_y = int(round((latitude + 90.0) / lat_step))

        aligned_lon = -180.0 + grid_x * lon_step
        aligned_lat = -90.0 + grid_y * lat_step

        centroid, bounds = self.generate_grid_geometries(
            aligned_lon, aligned_lat, resolution_km
        )

        cell = GridCell(
            grid_x=grid_x,
            grid_y=grid_y,
            centroid=from_shape(centroid, srid=4326),
            bounds=from_shape(bounds, srid=4326),
            resolution_km=resolution_km,
            created_at=datetime.utcnow()
        )

        self.db.add(cell)
        await self.db.commit()
        await self.db.refresh(cell)

        return cell

    async def get_grid_cells_in_bounds(
        self,
        lon_min: float,
        lon_max: float,
        lat_min: float,
        lat_max: float,
        resolution_km: Optional[float] = None
    ) -> List[GridCell]:
        """获取指定范围内的所有格点

        Args:
            lon_min: 最小经度（度）
            lon_max: 最大经度（度）
            lat_min: 最小纬度（度）
            lat_max: 最大纬度（度）
            resolution_km: 可选的分辨率过滤

        Returns:
            List[GridCell]: 范围内的格点列表
        """
        bbox_wkt = f"POLYGON(({lon_min} {lat_min}, {lon_max} {lat_min}, {lon_max} {lat_max}, {lon_min} {lat_max}, {lon_min} {lat_min}))"
        bbox_geom = WKTElement(bbox_wkt, srid=4326)

        query = select(GridCell).where(
            func.ST_Intersects(GridCell.bounds, bbox_geom)
        )

        if resolution_km is not None:
            query = query.where(GridCell.resolution_km == resolution_km)

        query = query.order_by(GridCell.grid_y, GridCell.grid_x)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_grid_cells_by_indices(
        self,
        grid_x_start: int,
        grid_x_end: int,
        grid_y_start: int,
        grid_y_end: int
    ) -> List[GridCell]:
        """根据网格索引范围获取格点

        Args:
            grid_x_start: 起始X索引
            grid_x_end: 结束X索引
            grid_y_start: 起始Y索引
            grid_y_end: 结束Y索引

        Returns:
            List[GridCell]: 格点列表
        """
        query = select(GridCell).where(
            and_(
                GridCell.grid_x.between(grid_x_start, grid_x_end),
                GridCell.grid_y.between(grid_y_start, grid_y_end)
            )
        ).order_by(GridCell.grid_y, GridCell.grid_x)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    @classmethod
    def calculate_haversine_distance(
        cls,
        lon1: float,
        lat1: float,
        lon2: float,
        lat2: float
    ) -> float:
        """使用Haversine公式计算两点间的大圆距离（公里）

        Args:
            lon1: 点1经度
            lat1: 点1纬度
            lon2: 点2经度
            lat2: 点2纬度

        Returns:
            float: 距离（公里）
        """
        lon1_rad = math.radians(lon1)
        lat1_rad = math.radians(lat1)
        lon2_rad = math.radians(lon2)
        lat2_rad = math.radians(lat2)

        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return cls.EARTH_RADIUS_KM * c

    def grid_to_geojson(self, cell: GridCell) -> dict:
        """将格点转换为GeoJSON格式

        Args:
            cell: 格点对象

        Returns:
            dict: GeoJSON要素
        """
        bounds_geom = to_shape(cell.bounds)
        centroid_geom = to_shape(cell.centroid)

        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [list(bounds_geom.exterior.coords)]
            },
            "properties": {
                "grid_id": cell.id,
                "grid_x": cell.grid_x,
                "grid_y": cell.grid_y,
                "centroid_lon": centroid_geom.x,
                "centroid_lat": centroid_geom.y,
                "resolution_km": cell.resolution_km,
                "created_at": cell.created_at.isoformat() if cell.created_at else None
            }
        }
