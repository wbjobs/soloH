#!/usr/bin/env python3
"""
初始化示例数据脚本

用于创建演示用的气象站、孢子传感器、格网和模拟数据。
使用方法: python -m scripts.init_sample_data
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import List

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import AsyncSessionLocal
from app.db.models import (
    WeatherStation, WeatherData,
    SporeSensor, SporeData,
    GridCell, RiskGrid, ForecastData,
    User, UserConfig, CropType
)
from app.services.grid_service import GridService
from app.models import JensenModel, BlightcastModel
from app.core.security import hash_password


# 示例区域：华北平原（小麦主产区）
REGION = {
    "lon_min": 114.0,
    "lon_max": 118.0,
    "lat_min": 32.0,
    "lat_max": 36.0,
}

# 示例气象站位置（模拟）
STATIONS = [
    {"name": "郑州气象站", "code": "ZZ57083", "lon": 113.66, "lat": 34.76, "elevation": 110},
    {"name": "开封气象站", "code": "KF57087", "lon": 114.35, "lat": 34.79, "elevation": 72},
    {"name": "商丘气象站", "code": "SQ57091", "lon": 115.65, "lat": 34.44, "elevation": 50},
    {"name": "徐州气象站", "code": "XZ58027", "lon": 117.18, "lat": 34.27, "elevation": 41},
    {"name": "蚌埠气象站", "code": "BB58122", "lon": 117.36, "lat": 32.92, "elevation": 21},
    {"name": "阜阳气象站", "code": "FY58108", "lon": 115.82, "lat": 32.89, "elevation": 32},
    {"name": "周口气象站", "code": "ZK57191", "lon": 114.64, "lat": 33.62, "elevation": 47},
    {"name": "漯河气象站", "code": "LH57186", "lon": 114.02, "lat": 33.58, "elevation": 61},
    {"name": "许昌气象站", "code": "XC57181", "lon": 113.86, "lat": 34.03, "elevation": 72},
    {"name": "菏泽气象站", "code": "HZ54909", "lon": 115.44, "lat": 35.24, "elevation": 49},
]

# 示例孢子传感器位置（模拟）
SPORE_SENSORS = [
    {"name": "商丘小麦锈病监测点", "code": "SQ-SP-001", "lon": 115.7, "lat": 34.5, "crop_type": CropType.WHEAT, "spore_type": "Puccinia_striiformis"},
    {"name": "周口小麦锈病监测点", "code": "ZK-SP-002", "lon": 114.7, "lat": 33.6, "crop_type": CropType.WHEAT, "spore_type": "Puccinia_striiformis"},
    {"name": "徐州小麦锈病监测点", "code": "XZ-SP-003", "lon": 117.2, "lat": 34.3, "crop_type": CropType.WHEAT, "spore_type": "Puccinia_striiformis"},
    {"name": "菏泽小麦锈病监测点", "code": "HZ-SP-004", "lon": 115.4, "lat": 35.2, "crop_type": CropType.WHEAT, "spore_type": "Puccinia_striiformis"},
    {"name": "阜阳马铃薯晚疫病监测点", "code": "FY-SP-005", "lon": 115.8, "lat": 32.9, "crop_type": CropType.POTATO, "spore_type": "Phytophthora_infestans"},
    {"name": "蚌埠马铃薯晚疫病监测点", "code": "BB-SP-006", "lon": 117.4, "lat": 32.9, "crop_type": CropType.POTATO, "spore_type": "Phytophthora_infestans"},
]


async def create_user(db: AsyncSession) -> User:
    """创建示例用户"""
    existing = await db.execute(
        User.__table__.select().where(User.email == "demo@example.com")
    )
    if existing.scalar_one_or_none():
        print("用户已存在，跳过创建")
        return await db.get(User, 1)

    user = User(
        email="demo@example.com",
        hashed_password=hash_password("demo123456"),
        full_name="演示用户",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    print(f"创建用户: {user.email}")

    config = UserConfig(
        user_id=user.id,
        crop_type=CropType.WHEAT,
        variety_name="济麦22",
        resistance_level=3,
        risk_threshold=50.0,
        notification_email=user.email,
        webhook_url=None,
    )
    db.add(config)
    await db.commit()
    print(f"创建用户配置: 小麦 - 济麦22")

    return user


async def create_weather_stations(db: AsyncSession) -> List[WeatherStation]:
    """创建示例气象站"""
    from geoalchemy2 import WKTElement

    stations = []
    for station_data in STATIONS:
        existing = await db.execute(
            WeatherStation.__table__.select().where(WeatherStation.code == station_data["code"])
        )
        if existing.scalar_one_or_none():
            print(f"气象站 {station_data['name']} 已存在，跳过")
            continue

        location_wkt = f"POINT({station_data['lon']} {station_data['lat']})"
        station = WeatherStation(
            name=station_data["name"],
            code=station_data["code"],
            location=WKTElement(location_wkt, srid=4326),
            elevation=station_data["elevation"],
            is_active=True,
        )
        db.add(station)
        stations.append(station)

    await db.commit()
    for station in stations:
        await db.refresh(station)
        print(f"创建气象站: {station.name}")

    # 获取所有气象站
    result = await db.execute(WeatherStation.__table__.select())
    return list(result.scalars().all())


async def create_spore_sensors(db: AsyncSession) -> List[SporeSensor]:
    """创建示例孢子传感器"""
    from geoalchemy2 import WKTElement

    sensors = []
    for sensor_data in SPORE_SENSORS:
        existing = await db.execute(
            SporeSensor.__table__.select().where(SporeSensor.code == sensor_data["code"])
        )
        if existing.scalar_one_or_none():
            print(f"孢子传感器 {sensor_data['name']} 已存在，跳过")
            continue

        location_wkt = f"POINT({sensor_data['lon']} {sensor_data['lat']})"
        sensor = SporeSensor(
            name=sensor_data["name"],
            code=sensor_data["code"],
            location=WKTElement(location_wkt, srid=4326),
            crop_type=sensor_data["crop_type"],
            spore_type=sensor_data["spore_type"],
            is_active=True,
        )
        db.add(sensor)
        sensors.append(sensor)

    await db.commit()
    for sensor in sensors:
        await db.refresh(sensor)
        print(f"创建孢子传感器: {sensor.name}")

    # 获取所有传感器
    result = await db.execute(SporeSensor.__table__.select())
    return list(result.scalars().all())


async def create_grid_cells(db: AsyncSession) -> List[GridCell]:
    """创建1km分辨率格网"""
    grid_service = GridService(db)

    # 检查是否已有格网
    count_result = await db.execute("SELECT COUNT(*) FROM grid_cells")
    count = count_result.scalar_one()
    if count > 0:
        print(f"格网已存在 ({count} 个)，跳过创建")
        result = await db.execute(GridCell.__table__.select().limit(100))
        return list(result.scalars().all())

    print("正在创建1km分辨率格网...")
    cells = await grid_service.create_grid_for_region(
        lon_min=REGION["lon_min"],
        lon_max=REGION["lon_max"],
        lat_min=REGION["lat_min"],
        lat_max=REGION["lat_max"],
        resolution_km=1.0,
    )
    print(f"创建格网: {len(cells)} 个1km x 1km网格单元")
    return cells


def generate_simulated_weather_data(station_id: int, days: int = 30) -> List[WeatherData]:
    """生成模拟气象数据"""
    data_list = []
    base_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for day in range(days):
        for hour in range(0, 24, 3):
            timestamp = base_date - timedelta(days=days - 1 - day) + timedelta(hours=hour)

            day_of_year = timestamp.timetuple().tm_yday

            temp_base = 15 + 10 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
            temp_hourly = 5 * np.sin(2 * np.pi * (hour - 6) / 24)
            temperature = temp_base + temp_hourly + random.gauss(0, 1.5)

            humidity_base = 60 + 20 * np.sin(2 * np.pi * (day_of_year - 200) / 365)
            humidity = max(20, min(98, humidity_base - temp_hourly * 3 + random.gauss(0, 8)))

            rainfall = 0.0
            if random.random() < 0.25:
                rainfall = max(0, random.gauss(8, 6))

            leaf_wetness = 0.0
            if rainfall > 0:
                leaf_wetness = min(12, rainfall * 1.5 + random.gauss(2, 2))
            elif humidity > 90:
                leaf_wetness = min(8, random.gauss(4, 2))

            wind_speed = max(0, random.gauss(3.5, 2))
            solar_radiation = max(0, 800 * np.sin(2 * np.pi * (hour - 6) / 12) + random.gauss(0, 100)) if 6 <= hour <= 18 else 0

            data = WeatherData(
                station_id=station_id,
                timestamp=timestamp,
                temperature=round(temperature, 1),
                relative_humidity=round(humidity, 1),
                rainfall=round(rainfall, 1),
                leaf_wetness_duration=round(leaf_wetness, 1),
                wind_speed=round(wind_speed, 1),
                solar_radiation=round(solar_radiation, 0),
            )
            data_list.append(data)

    return data_list


def generate_simulated_spore_data(sensor_id: int, days: int = 30) -> List[SporeData]:
    """生成模拟孢子浓度数据"""
    data_list = []
    base_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for day in range(days):
        timestamp = base_date - timedelta(days=days - 1 - day) + timedelta(hours=12)
        day_of_year = timestamp.timetuple().tm_yday

        seasonal_factor = max(0, np.sin(2 * np.pi * (day_of_year - 120) / 180))
        base_concentration = 10 + 80 * seasonal_factor
        concentration = max(0, base_concentration + random.gauss(0, 20))

        data = SporeData(
            sensor_id=sensor_id,
            timestamp=timestamp,
            concentration=round(concentration, 1),
        )
        data_list.append(data)

    return data_list


def generate_simulated_forecast_data(grid_cells: List[GridCell], days: int = 7) -> List[ForecastData]:
    """生成模拟WRF预报数据"""
    data_list = []
    base_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for grid_cell in grid_cells[:100]:
        for day in range(days):
            for lead_time in [0, 6, 12, 18, 24]:
                timestamp = base_date + timedelta(days=day) + timedelta(hours=lead_time)
                hour = timestamp.hour

                day_of_year = timestamp.timetuple().tm_yday
                temp_base = 15 + 10 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
                temp_hourly = 5 * np.sin(2 * np.pi * (hour - 6) / 24)
                temperature = temp_base + temp_hourly

                humidity = 65 - temp_hourly * 2.5

                rainfall = 0.0
                if random.random() < 0.2:
                    rainfall = max(0, random.gauss(5, 4))

                wind_speed = max(0, random.gauss(3, 1.5))

                data = ForecastData(
                    grid_id=grid_cell.id,
                    forecast_date=base_date + timedelta(days=day),
                    lead_time_hours=lead_time,
                    temperature=round(temperature, 1),
                    humidity=round(humidity, 1),
                    rainfall=round(rainfall, 1),
                    wind_speed=round(wind_speed, 1),
                )
                data_list.append(data)

    return data_list


def generate_risk_data(
    grid_cells: List[GridCell],
    days: int = 30
) -> List[RiskGrid]:
    """生成模拟风险数据"""
    data_list = []
    jensen_model = JensenModel()
    blightcast_model = BlightcastModel()
    base_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for day in range(days):
        forecast_date = base_date - timedelta(days=days - 1 - day)
        day_of_year = forecast_date.timetuple().tm_yday

        for grid_cell in grid_cells[:50]:
            temp = 12 + 8 * np.sin(2 * np.pi * (day_of_year - 80) / 365) + random.gauss(0, 2)
            humidity = 60 + random.gauss(0, 15)
            rainfall = max(0, random.gauss(3, 4))
            leaf_wetness = min(12, rainfall * 1.2 + random.gauss(2, 2)) if rainfall > 0 else random.gauss(2, 3)
            spore = 30 + 50 * max(0, np.sin(2 * np.pi * (day_of_year - 120) / 180))

            risk_wheat, prob_wheat, _ = jensen_model.calculate_risk(
                temperature=temp,
                humidity=humidity,
                rainfall=rainfall,
                leaf_wetness=leaf_wetness,
                spore_concentration=spore,
                resistance_level=3,
            )

            risk_potato, prob_potato, _ = blightcast_model.calculate_risk(
                temperature=temp,
                humidity=humidity,
                rainfall=rainfall,
                leaf_wetness=leaf_wetness,
                spore_concentration=spore,
                resistance_level=3,
            )

            data_list.extend([
                RiskGrid(
                    grid_id=grid_cell.id,
                    forecast_date=forecast_date,
                    crop_type=CropType.WHEAT,
                    risk_index=risk_wheat,
                    infection_probability=prob_wheat,
                    model_version="2.0.0",
                ),
                RiskGrid(
                    grid_id=grid_cell.id,
                    forecast_date=forecast_date,
                    crop_type=CropType.POTATO,
                    risk_index=risk_potato,
                    infection_probability=prob_potato,
                    model_version="2.0.0",
                ),
            ])

    return data_list


async def main():
    """主函数"""
    print("=" * 60)
    print("农业病害预警系统 - 示例数据初始化")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        print("\n1. 创建用户...")
        await create_user(db)

        print("\n2. 创建气象站...")
        stations = await create_weather_stations(db)

        print("\n3. 创建孢子传感器...")
        sensors = await create_spore_sensors(db)

        print("\n4. 创建格网...")
        grid_cells = await create_grid_cells(db)

        print("\n5. 生成模拟气象数据...")
        weather_count = 0
        for station in stations:
            data = generate_simulated_weather_data(station.id, days=30)
            db.add_all(data)
            weather_count += len(data)
        await db.commit()
        print(f"生成气象数据: {weather_count} 条")

        print("\n6. 生成模拟孢子数据...")
        spore_count = 0
        for sensor in sensors:
            data = generate_simulated_spore_data(sensor.id, days=30)
            db.add_all(data)
            spore_count += len(data)
        await db.commit()
        print(f"生成孢子数据: {spore_count} 条")

        print("\n7. 生成模拟预报数据...")
        forecast_data = generate_simulated_forecast_data(grid_cells, days=7)
        db.add_all(forecast_data)
        await db.commit()
        print(f"生成预报数据: {len(forecast_data)} 条")

        print("\n8. 生成模拟风险数据...")
        risk_data = generate_risk_data(grid_cells, days=30)
        db.add_all(risk_data)
        await db.commit()
        print(f"生成风险数据: {len(risk_data)} 条")

    print("\n" + "=" * 60)
    print("示例数据初始化完成!")
    print("=" * 60)
    print("\n登录信息:")
    print("  邮箱: demo@example.com")
    print("  密码: demo123456")
    print(f"\n数据范围: 东经{REGION['lon_min']}-{REGION['lon_max']}, 北纬{REGION['lat_min']}-{REGION['lat_max']}")
    print(f"格网分辨率: 1km x 1km")
    print(f"气象站: {len(stations)} 个")
    print(f"孢子传感器: {len(sensors)} 个")


if __name__ == "__main__":
    asyncio.run(main())
