from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

import numpy as np
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CropType,
    GridCell,
    RiskGrid,
    WeatherStation,
    WeatherData,
    SporeSensor,
    SporeData,
    ForecastData,
    UserConfig,
)
from app.models import JensenModel, BlightcastModel, DiseaseModel
from app.services.grid_service import GridService


class RiskEngine:
    """风险计算引擎服务

    负责病害风险的空间插值、单点计算、批量计算、风险地图生成
    和多日预报等核心功能。集成多种病害预测模型，支持不同作物类型。
    """

    MODEL_VERSION: str = "2.0.0"

    _model_cache: Dict[str, DiseaseModel] = {}

    def __init__(self, db: AsyncSession):
        self.db = db
        self.grid_service = GridService(db)

    @classmethod
    def get_model_for_crop(cls, crop_type: CropType) -> DiseaseModel:
        """根据作物类型返回对应病害预测模型

        模型映射规则:
        - 小麦(wheat) -> JensenModel (小麦锈病模型)
        - 马铃薯(potato) -> BlightcastModel (马铃薯晚疫病模型)
        - 其他作物 -> 默认JensenModel

        Args:
            crop_type: 作物类型枚举值

        Returns:
            DiseaseModel: 对应病害预测模型实例
        """
        crop_str = crop_type.value if isinstance(crop_type, CropType) else crop_type

        if crop_str in cls._model_cache:
            return cls._model_cache[crop_str]

        if crop_str == CropType.WHEAT.value:
            model = JensenModel()
        elif crop_str == CropType.POTATO.value:
            model = BlightcastModel()
        else:
            model = JensenModel()

        cls._model_cache[crop_str] = model
        return model

    @staticmethod
    def idw_interpolation(
        points: List[Tuple[float, float]],
        values: List[float],
        target_point: Tuple[float, float],
        power: float = 2.0,
    ) -> float:
        """反距离加权插值 (Inverse Distance Weighting)

        根据已知点的坐标和数值，对目标点进行空间插值计算。
        距离越近的点权重越大，权重与距离的power次方成反比。

        算法公式:
        Z_target = Σ(wi * Zi) / Σ(wi)
        其中 wi = 1 / (di^power), di为第i个点到目标点的距离

        Args:
            points: 已知点坐标列表 [(lon1, lat1), (lon2, lat2), ...]
            values: 对应点的数值列表 [v1, v2, ...]
            target_point: 目标点坐标 (lon, lat)
            power: 距离幂次参数，默认2.0，值越大局部影响越强

        Returns:
            float: 插值后的数值

        Raises:
            ValueError: 当点数与值数不匹配或无有效数据时
        """
        if len(points) != len(values):
            raise ValueError("points和values长度必须相同")

        if len(points) == 0:
            raise ValueError("至少需要一个已知点进行插值")

        points_arr = np.array(points, dtype=np.float64)
        values_arr = np.array(values, dtype=np.float64)
        target_arr = np.array(target_point, dtype=np.float64)

        EARTH_RADIUS_KM = 6371.0088

        lon1_rad = np.radians(points_arr[:, 0])
        lat1_rad = np.radians(points_arr[:, 1])
        lon2_rad = np.radians(target_arr[0])
        lat2_rad = np.radians(target_arr[1])

        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad

        a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        distances = EARTH_RADIUS_KM * c

        valid_mask = ~np.isnan(distances) & (distances >= 0)
        distances = distances[valid_mask]
        values_arr = values_arr[valid_mask]

        if len(distances) == 0:
            raise ValueError("没有有效的距离数据进行插值")

        zero_mask = distances < 1e-6
        if np.any(zero_mask):
            return float(values_arr[zero_mask][0])

        weights = 1.0 / (distances ** power)
        weights_sum = np.sum(weights)

        if weights_sum < 1e-10:
            return float(np.mean(values_arr))

        interpolated_value = np.sum(weights * values_arr) / weights_sum
        return float(interpolated_value)

    async def _get_nearby_weather_data(
        self,
        lon: float,
        lat: float,
        forecast_date: datetime,
        max_distance_km: float = 50.0,
        max_stations: int = 10,
    ) -> List[Dict[str, Any]]:
        """获取目标点周围的气象站数据

        Args:
            lon: 目标点经度
            lat: 目标点纬度
            forecast_date: 预报日期
            max_distance_km: 最大搜索距离（公里）
            max_stations: 最大返回气象站数量

        Returns:
            List[Dict]: 气象站数据列表，包含位置、距离和气象要素
        """
        date_start = forecast_date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)

        query = (
            select(WeatherStation, WeatherData)
            .join(WeatherData, WeatherStation.id == WeatherData.station_id)
            .where(
                and_(
                    WeatherStation.is_active == True,
                    WeatherData.timestamp >= date_start,
                    WeatherData.timestamp < date_end,
                )
            )
        )

        result = await self.db.execute(query)
        rows = result.all()

        weather_list = []
        for station, weather_data in rows:
            station_lon = station.longitude
            station_lat = station.latitude

            if station_lon is None or station_lat is None:
                continue

            distance = GridService.calculate_haversine_distance(
                lon, lat, station_lon, station_lat
            )

            if distance <= max_distance_km:
                weather_list.append({
                    "station_id": station.id,
                    "station_name": station.name,
                    "lon": station_lon,
                    "lat": station_lat,
                    "distance_km": distance,
                    "temperature": weather_data.temperature,
                    "humidity": weather_data.relative_humidity,
                    "rainfall": weather_data.rainfall,
                    "leaf_wetness": weather_data.leaf_wetness_duration,
                    "wind_speed": weather_data.wind_speed,
                    "solar_radiation": weather_data.solar_radiation,
                })

        weather_list.sort(key=lambda x: x["distance_km"])
        return weather_list[:max_stations]

    async def _get_nearest_spore_data(
        self,
        lon: float,
        lat: float,
        crop_type: CropType,
        forecast_date: datetime,
        max_distance_km: float = 100.0,
    ) -> Optional[Dict[str, Any]]:
        """获取最近的孢子传感器数据

        Args:
            lon: 目标点经度
            lat: 目标点纬度
            crop_type: 作物类型
            forecast_date: 预报日期
            max_distance_km: 最大搜索距离（公里）

        Returns:
            Optional[Dict]: 孢子数据，包含位置、距离和浓度
        """
        date_start = forecast_date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        crop_str = crop_type.value if isinstance(crop_type, CropType) else crop_type

        query = (
            select(SporeSensor, SporeData)
            .join(SporeData, SporeSensor.id == SporeData.sensor_id)
            .where(
                and_(
                    SporeSensor.is_active == True,
                    SporeSensor.crop_type == crop_str,
                    SporeData.timestamp >= date_start,
                    SporeData.timestamp < date_end,
                )
            )
        )

        result = await self.db.execute(query)
        rows = result.all()

        nearest_spore = None
        min_distance = float("inf")

        for sensor, spore_data in rows:
            sensor_lon = sensor.longitude
            sensor_lat = sensor.latitude

            if sensor_lon is None or sensor_lat is None:
                continue

            distance = GridService.calculate_haversine_distance(
                lon, lat, sensor_lon, sensor_lat
            )

            if distance <= max_distance_km and distance < min_distance:
                min_distance = distance
                nearest_spore = {
                    "sensor_id": sensor.id,
                    "sensor_name": sensor.name,
                    "lon": sensor_lon,
                    "lat": sensor_lat,
                    "distance_km": distance,
                    "spore_type": sensor.spore_type,
                    "concentration": spore_data.concentration,
                }

        return nearest_spore

    async def _interpolate_weather_for_point(
        self,
        lon: float,
        lat: float,
        forecast_date: datetime,
    ) -> Dict[str, float]:
        """对目标点进行气象要素空间插值

        Args:
            lon: 目标点经度
            lat: 目标点纬度
            forecast_date: 预报日期

        Returns:
            Dict: 插值后的气象要素字典
        """
        weather_data = await self._get_nearby_weather_data(lon, lat, forecast_date)

        if not weather_data:
            return {
                "temperature": 15.0,
                "humidity": 70.0,
                "rainfall": 0.0,
                "leaf_wetness": 0.0,
            }

        temp_points = []
        temp_values = []
        hum_points = []
        hum_values = []
        rain_points = []
        rain_values = []
        wetness_points = []
        wetness_values = []

        for wd in weather_data:
            point = (wd["lon"], wd["lat"])

            if wd["temperature"] is not None and not np.isnan(wd["temperature"]):
                temp_points.append(point)
                temp_values.append(wd["temperature"])

            if wd["humidity"] is not None and not np.isnan(wd["humidity"]):
                hum_points.append(point)
                hum_values.append(wd["humidity"])

            if wd["rainfall"] is not None and not np.isnan(wd["rainfall"]):
                rain_points.append(point)
                rain_values.append(wd["rainfall"])

            if wd["leaf_wetness"] is not None and not np.isnan(wd["leaf_wetness"]):
                wetness_points.append(point)
                wetness_values.append(wd["leaf_wetness"])

        try:
            temperature = self.idw_interpolation(temp_points, temp_values, (lon, lat)) if temp_points else 15.0
        except ValueError:
            temperature = np.mean(temp_values) if temp_values else 15.0

        try:
            humidity = self.idw_interpolation(hum_points, hum_values, (lon, lat)) if hum_points else 70.0
        except ValueError:
            humidity = np.mean(hum_values) if hum_values else 70.0

        try:
            rainfall = self.idw_interpolation(rain_points, rain_values, (lon, lat)) if rain_points else 0.0
        except ValueError:
            rainfall = np.mean(rain_values) if rain_values else 0.0

        try:
            leaf_wetness = self.idw_interpolation(wetness_points, wetness_values, (lon, lat)) if wetness_points else 0.0
        except ValueError:
            leaf_wetness = np.mean(wetness_values) if wetness_values else 0.0

        return {
            "temperature": float(temperature),
            "humidity": float(humidity),
            "rainfall": float(rainfall),
            "leaf_wetness": float(leaf_wetness),
        }

    async def calculate_point_risk(
        self,
        lon: float,
        lat: float,
        crop_type: CropType,
        forecast_date: datetime,
        resistance_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """计算单点风险指数

        执行流程:
        1. 查找该点所属格点
        2. 查询周围气象站数据进行空间插值
        3. 查询最近的孢子传感器数据
        4. 调用对应病害模型计算风险
        5. 返回风险指数、感染概率和详细信息

        Args:
            lon: 经度
            lat: 纬度
            crop_type: 作物类型
            forecast_date: 预报日期
            resistance_level: 抗性级别 (1-5)，可选

        Returns:
            Dict: 包含风险计算结果的字典
                - risk_index: 风险指数 (0-100)
                - risk_level: 风险等级
                - infection_probability: 感染概率 (0-1)
                - details: 详细计算信息
                - grid_id: 所属格点ID
                - model_version: 模型版本
        """
        grid_cell = await self.grid_service.get_or_create_grid_cell(lon, lat)

        if resistance_level is None:
            centroid = to_shape(grid_cell.centroid)
            grid_lon, grid_lat = centroid.x, centroid.y

            user_config = await self._get_user_config_for_location(
                grid_lon, grid_lat, crop_type
            )
            if user_config:
                resistance_level = user_config.resistance_level

        weather_data_list = await self._get_nearby_weather_data(lon, lat, forecast_date)
        weather = await self._interpolate_weather_for_point(lon, lat, forecast_date)
        spore_data = await self._get_nearest_spore_data(lon, lat, crop_type, forecast_date)

        spore_concentration = spore_data["concentration"] if spore_data else None

        model = self.get_model_for_crop(crop_type)

        risk_index, infection_probability, details = model.calculate_risk(
            temperature=weather["temperature"],
            humidity=weather["humidity"],
            rainfall=weather["rainfall"],
            leaf_wetness=weather["leaf_wetness"],
            spore_concentration=spore_concentration,
            resistance_level=resistance_level,
        )

        risk_level = self.get_risk_level(risk_index)

        return {
            "risk_index": risk_index,
            "risk_level": risk_level,
            "infection_probability": infection_probability,
            "details": details,
            "grid_id": grid_cell.id,
            "grid_x": grid_cell.grid_x,
            "grid_y": grid_cell.grid_y,
            "lon": lon,
            "lat": lat,
            "crop_type": crop_type,
            "forecast_date": forecast_date,
            "model_version": self.MODEL_VERSION,
            "calculated_at": datetime.utcnow(),
            "weather_source": "idw_interpolated",
            "weather_stations_used": len(weather_data_list),
            "spore_sensor_used": spore_data["sensor_name"] if spore_data else None,
        }

    async def _get_user_config_for_location(
        self,
        lon: float,
        lat: float,
        crop_type: CropType,
    ) -> Optional[UserConfig]:
        """获取指定位置和作物类型的用户配置

        Args:
            lon: 经度
            lat: 纬度
            crop_type: 作物类型

        Returns:
            Optional[UserConfig]: 用户配置对象（如果存在）
        """
        point_wkt = f"POINT({lon} {lat})"
        point_geom = WKTElement(point_wkt, srid=4326)

        query = (
            select(UserConfig)
            .join(GridCell, func.ST_Contains(GridCell.bounds, point_geom))
            .where(UserConfig.crop_type == crop_type)
            .limit(1)
        )

        result = await self.db.execute(query)
        return result.scalars().first()

    async def calculate_grid_risk_batch(
        self,
        grid_cells: List[GridCell],
        crop_type: CropType,
        forecast_date: datetime,
        weather_data_by_grid: Dict[int, List[ForecastData]],
        spore_data_by_grid: Dict[int, float],
        user_configs: Optional[Dict[int, UserConfig]] = None,
    ) -> List[RiskGrid]:
        """批量计算多个格点的风险

        使用numpy向量化计算提高效率，支持用户配置的抗性级别。

        Args:
            grid_cells: 格点列表
            crop_type: 作物类型
            forecast_date: 预报日期
            weather_data_by_grid: 按格点ID分组的天气预报数据
            spore_data_by_grid: 按格点ID分组的孢子浓度数据
            user_configs: 按格点ID分组的用户配置（可选）

        Returns:
            List[RiskGrid]: 风险网格对象列表
        """
        if not grid_cells:
            return []

        n = len(grid_cells)
        grid_ids = np.array([cell.id for cell in grid_cells])

        temperatures = np.full(n, np.nan, dtype=np.float64)
        humidities = np.full(n, np.nan, dtype=np.float64)
        rainfalls = np.full(n, np.nan, dtype=np.float64)
        leaf_wetness = np.full(n, np.nan, dtype=np.float64)
        spore_concentrations = np.full(n, np.nan, dtype=np.float64)
        resistance_levels = np.full(n, 2, dtype=np.int32)

        for i, cell in enumerate(grid_cells):
            weather_list = weather_data_by_grid.get(cell.id, [])
            if weather_list:
                temps = [w.temperature for w in weather_list if w.temperature is not None]
                hums = [w.humidity for w in weather_list if w.humidity is not None]
                rains = [w.rainfall for w in weather_list if w.rainfall is not None]

                if temps:
                    temperatures[i] = np.mean(temps)
                if hums:
                    humidities[i] = np.mean(hums)
                if rains:
                    rainfalls[i] = np.sum(rains)
                    leaf_wetness[i] = np.mean(hums) * 0.1 if hums else 0.0

            spore_concentrations[i] = spore_data_by_grid.get(cell.id, np.nan)

            if user_configs and cell.id in user_configs:
                resistance_levels[i] = user_configs[cell.id].resistance_level

        temp_mean = np.nanmean(temperatures) if not np.all(np.isnan(temperatures)) else 15.0
        hum_mean = np.nanmean(humidities) if not np.all(np.isnan(humidities)) else 70.0
        rain_mean = np.nanmean(rainfalls) if not np.all(np.isnan(rainfalls)) else 0.0
        wet_mean = np.nanmean(leaf_wetness) if not np.all(np.isnan(leaf_wetness)) else 0.0
        spore_mean = np.nanmean(spore_concentrations) if not np.all(np.isnan(spore_concentrations)) else 30.0

        temperatures = np.where(np.isnan(temperatures), temp_mean, temperatures)
        humidities = np.where(np.isnan(humidities), hum_mean, humidities)
        rainfalls = np.where(np.isnan(rainfalls), rain_mean, rainfalls)
        leaf_wetness = np.where(np.isnan(leaf_wetness), wet_mean, leaf_wetness)
        spore_concentrations = np.where(np.isnan(spore_concentrations), spore_mean, spore_concentrations)

        model = self.get_model_for_crop(crop_type)

        risk_grids = []
        now = datetime.utcnow()

        for i, cell in enumerate(grid_cells):
            risk_index, infection_probability, _ = model.calculate_risk(
                temperature=float(temperatures[i]),
                humidity=float(humidities[i]),
                rainfall=float(rainfalls[i]),
                leaf_wetness=float(leaf_wetness[i]),
                spore_concentration=float(spore_concentrations[i]),
                resistance_level=int(resistance_levels[i]),
            )

            risk_grid = RiskGrid(
                grid_id=cell.id,
                forecast_date=forecast_date,
                crop_type=crop_type,
                risk_index=risk_index,
                infection_probability=infection_probability,
                model_version=self.MODEL_VERSION,
                calculated_at=now,
            )
            risk_grids.append(risk_grid)

        return risk_grids

    async def generate_risk_map(
        self,
        crop_type: CropType,
        forecast_date: datetime,
        bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> Dict[str, Any]:
        """生成风险地图GeoJSON

        Args:
            crop_type: 作物类型
            forecast_date: 预报日期
            bounds: 经纬度范围 (lon_min, lat_min, lon_max, lat_max)，可选

        Returns:
            Dict: GeoJSON FeatureCollection格式的风险地图
        """
        if bounds:
            lon_min, lat_min, lon_max, lat_max = bounds
            grid_cells = await self.grid_service.get_grid_cells_in_bounds(
                lon_min, lon_max, lat_min, lat_max
            )
        else:
            all_grids_query = select(GridCell).order_by(GridCell.grid_y, GridCell.grid_x)
            result = await self.db.execute(all_grids_query)
            grid_cells = list(result.scalars().all())

        if not grid_cells:
            return {
                "type": "FeatureCollection",
                "features": [],
                "forecast_date": forecast_date.isoformat(),
                "crop_type": crop_type.value if isinstance(crop_type, CropType) else crop_type,
                "generated_at": datetime.utcnow().isoformat(),
                "model_version": self.MODEL_VERSION,
                "grid_count": 0,
            }

        grid_ids = [cell.id for cell in grid_cells]

        date_start = forecast_date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)

        weather_query = (
            select(ForecastData)
            .where(
                and_(
                    ForecastData.grid_id.in_(grid_ids),
                    ForecastData.forecast_date >= date_start,
                    ForecastData.forecast_date < date_end,
                )
            )
        )
        weather_result = await self.db.execute(weather_query)
        weather_data = weather_result.scalars().all()

        weather_data_by_grid: Dict[int, List[ForecastData]] = {}
        for wd in weather_data:
            if wd.grid_id not in weather_data_by_grid:
                weather_data_by_grid[wd.grid_id] = []
            weather_data_by_grid[wd.grid_id].append(wd)

        spore_data_by_grid: Dict[int, float] = {}
        spore_distance_by_grid: Dict[int, float] = {}
        crop_str = crop_type.value if isinstance(crop_type, CropType) else crop_type

        spore_query = (
            select(SporeData, SporeSensor)
            .join(SporeSensor, SporeData.sensor_id == SporeSensor.id)
            .where(
                and_(
                    SporeSensor.crop_type == crop_str,
                    SporeData.timestamp >= date_start,
                    SporeData.timestamp < date_end,
                )
            )
        )
        spore_result = await self.db.execute(spore_query)
        spore_rows = spore_result.all()

        for spore_data, sensor in spore_rows:
            for cell in grid_cells:
                centroid = to_shape(cell.centroid)
                dist = GridService.calculate_haversine_distance(
                    centroid.x, centroid.y,
                    sensor.longitude, sensor.latitude
                )
                if dist < 50.0:
                    if cell.id not in spore_data_by_grid or dist < spore_distance_by_grid.get(cell.id, 1e9):
                        spore_data_by_grid[cell.id] = spore_data.concentration
                        spore_distance_by_grid[cell.id] = dist

        risk_grids = await self.calculate_grid_risk_batch(
            grid_cells=grid_cells,
            crop_type=crop_type,
            forecast_date=forecast_date,
            weather_data_by_grid=weather_data_by_grid,
            spore_data_by_grid=spore_data_by_grid,
        )

        risk_by_grid_id = {rg.grid_id: rg for rg in risk_grids}

        features = []
        for cell in grid_cells:
            risk_grid = risk_by_grid_id.get(cell.id)
            if not risk_grid:
                continue

            centroid = to_shape(cell.centroid)
            bounds_geom = to_shape(cell.bounds)

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [list(bounds_geom.exterior.coords)],
                },
                "properties": {
                    "grid_id": cell.id,
                    "grid_x": cell.grid_x,
                    "grid_y": cell.grid_y,
                    "centroid_lon": centroid.x,
                    "centroid_lat": centroid.y,
                    "risk_index": risk_grid.risk_index,
                    "risk_level": self.get_risk_level(risk_grid.risk_index),
                    "infection_probability": risk_grid.infection_probability,
                    "crop_type": crop_type.value if isinstance(crop_type, CropType) else crop_type,
                    "forecast_date": forecast_date.isoformat(),
                    "model_version": self.MODEL_VERSION,
                    "calculated_at": risk_grid.calculated_at.isoformat() if risk_grid.calculated_at else None,
                },
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features,
            "forecast_date": forecast_date.isoformat(),
            "crop_type": crop_type.value if isinstance(crop_type, CropType) else crop_type,
            "generated_at": datetime.utcnow().isoformat(),
            "model_version": self.MODEL_VERSION,
            "grid_count": len(features),
        }

    async def calculate_forecast_risk(
        self,
        lon: float,
        lat: float,
        crop_type: CropType,
        days: int = 7,
        resistance_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """计算未来多天的风险预报

        获取该格点的WRF预报数据，逐日计算风险指数。

        Args:
            lon: 经度
            lat: 纬度
            crop_type: 作物类型
            days: 预报天数，默认7天
            resistance_level: 抗性级别 (1-5)，可选

        Returns:
            Dict: 包含每日风险预报的字典
                - lon, lat: 坐标
                - crop_type: 作物类型
                - forecast: 逐日预报列表
                    - date: 日期
                    - risk_index: 风险指数
                    - risk_level: 风险等级
                    - temperature: 平均温度
                    - humidity: 平均湿度
                    - rainfall: 总降雨量
                    - infection_probability: 感染概率
        """
        grid_cell = await self.grid_service.get_or_create_grid_cell(lon, lat)

        if resistance_level is None:
            user_config = await self._get_user_config_for_location(lon, lat, crop_type)
            if user_config:
                resistance_level = user_config.resistance_level

        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=days)

        forecast_query = (
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

        forecast_result = await self.db.execute(forecast_query)
        forecast_data = forecast_result.scalars().all()

        daily_data: Dict[str, Dict[str, List[float]]] = {}
        for fd in forecast_data:
            date_key = fd.forecast_date.date().isoformat()
            if date_key not in daily_data:
                daily_data[date_key] = {
                    "temperatures": [],
                    "humidities": [],
                    "rainfalls": [],
                    "wind_speeds": [],
                }
            if fd.temperature is not None:
                daily_data[date_key]["temperatures"].append(fd.temperature)
            if fd.humidity is not None:
                daily_data[date_key]["humidities"].append(fd.humidity)
            if fd.rainfall is not None:
                daily_data[date_key]["rainfalls"].append(fd.rainfall)
            if fd.wind_speed is not None:
                daily_data[date_key]["wind_speeds"].append(fd.wind_speed)

        model = self.get_model_for_crop(crop_type)
        forecast_list = []

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            date_key = current_date.date().isoformat()

            data = daily_data.get(date_key, {})
            temps = data.get("temperatures", [])
            hums = data.get("humidities", [])
            rains = data.get("rainfalls", [])

            avg_temp = float(np.mean(temps)) if temps else 15.0
            avg_humidity = float(np.mean(hums)) if hums else 70.0
            total_rainfall = float(np.sum(rains)) if rains else 0.0
            leaf_wetness = avg_humidity * 0.1 if hums else 0.0

            risk_index, infection_probability, _ = model.calculate_risk(
                temperature=avg_temp,
                humidity=avg_humidity,
                rainfall=total_rainfall,
                leaf_wetness=leaf_wetness,
                spore_concentration=None,
                resistance_level=resistance_level,
                consecutive_wet_days=min(i + 1, 7),
            )

            forecast_list.append({
                "date": current_date,
                "risk_index": risk_index,
                "risk_level": self.get_risk_level(risk_index),
                "temperature": avg_temp if temps else None,
                "humidity": avg_humidity if hums else None,
                "rainfall": total_rainfall if rains else None,
                "infection_probability": infection_probability,
            })

        return {
            "lon": lon,
            "lat": lat,
            "grid_id": grid_cell.id,
            "crop_type": crop_type,
            "forecast_days": days,
            "model_version": self.MODEL_VERSION,
            "forecast": forecast_list,
        }

    @staticmethod
    def get_risk_level(risk_index: float) -> str:
        """根据风险指数判定风险等级（中文标签）

        等级划分（与前端统一阈值）:
        - 风险指数 < 15: 无风险
        - 15 <= 风险指数 < 40: 低风险
        - 40 <= 风险指数 < 70: 中风险
        - 风险指数 >= 70: 高风险

        Args:
            risk_index: 风险指数 (0-100)

        Returns:
            str: 风险等级描述
        """
        from app.core.constants import get_risk_level
        return get_risk_level(risk_index, use_chinese=True)

    @staticmethod
    def get_risk_level_en(risk_index: float) -> str:
        """根据风险指数判定风险等级（英文标签，用于API响应）

        等级划分（与前端统一阈值）:
        - 风险指数 < 15: low
        - 15 <= 风险指数 < 40: medium
        - 40 <= 风险指数 < 70: high
        - 风险指数 >= 70: extreme

        Args:
            risk_index: 风险指数 (0-100)

        Returns:
            str: 风险等级英文标签
        """
        from app.core.constants import get_risk_level_en
        return get_risk_level_en(risk_index)
