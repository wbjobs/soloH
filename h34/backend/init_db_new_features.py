import asyncio
import sys
import os
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base, engine, AsyncSessionLocal
from app.db.models import (
    CropType,
    GridCell,
    WeatherStation,
    WeatherData,
    SporeSensor,
    SporeData,
    RiskGrid,
    ForecastData,
    User,
    UserConfig,
)
from app.core.config import settings
from app.services.risk_engine import RiskEngine


async def create_tables():
    """创建所有数据库表"""
    print("正在创建数据库表...")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await conn.run_sync(Base.metadata.create_all)
        print("✓ 数据库表创建完成")
        return True
    except Exception as e:
        print(f"⚠ 创建表失败: {e}")
        print("请确保PostgreSQL服务已启动并正确配置")
        return False


async def init_grid_cells(db: AsyncSession):
    """初始化1km网格数据（北京周边区域）"""
    print("\n正在初始化网格数据...")

    result = await db.execute(text("SELECT COUNT(*) FROM grid_cells"))
    count = result.scalar_one()
    if count > 0:
        print(f"✓ 网格已存在 ({count} 个)，跳过初始化")
        return

    center_lon, center_lat = 116.4, 39.9
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * 0.777

    grid_size = 0.01

    grid_x_range = range(-15, 16)
    grid_y_range = range(-15, 16)

    grid_cells = []
    for gx in grid_x_range:
        for gy in grid_y_range:
            lon = center_lon + gx * grid_size
            lat = center_lat + gy * grid_size

            half_size = grid_size / 2
            bounds_wkt = (
                f"POLYGON(({lon - half_size} {lat - half_size}, "
                f"{lon + half_size} {lat - half_size}, "
                f"{lon + half_size} {lat + half_size}, "
                f"{lon - half_size} {lat + half_size}, "
                f"{lon - half_size} {lat - half_size}))"
            )

            grid_cells.append({
                "grid_x": gx,
                "grid_y": gy,
                "centroid": f"SRID=4326;POINT({lon} {lat})",
                "bounds": f"SRID=4326;{bounds_wkt}",
                "resolution_km": 1.0,
            })

    for gc in grid_cells:
        stmt = text("""
            INSERT INTO grid_cells (grid_x, grid_y, centroid, bounds, resolution_km, created_at)
            VALUES (:grid_x, :grid_y, ST_GeomFromText(:centroid, 4326),
                    ST_GeomFromText(:bounds, 4326), :resolution_km, :created_at)
        """)
        await db.execute(stmt, {**gc, "created_at": datetime.utcnow()})

    await db.commit()
    print(f"✓ 初始化网格完成，共 {len(grid_cells)} 个 1km 网格")


async def init_weather_stations(db: AsyncSession):
    """初始化气象站数据"""
    print("\n正在初始化气象站数据...")

    result = await db.execute(text("SELECT COUNT(*) FROM weather_stations"))
    count = result.scalar_one()
    if count > 0:
        print(f"✓ 气象站已存在 ({count} 个)，跳过初始化")
        return

    stations = [
        {"name": "北京站", "code": "BJ001", "lon": 116.4, "lat": 39.9, "elevation": 43.5},
        {"name": "海淀站", "code": "BJ002", "lon": 116.3, "lat": 39.95, "elevation": 52.0},
        {"name": "朝阳站", "code": "BJ003", "lon": 116.5, "lat": 39.92, "elevation": 38.0},
        {"name": "丰台站", "code": "BJ004", "lon": 116.3, "lat": 39.85, "elevation": 48.0},
        {"name": "通州站", "code": "BJ005", "lon": 116.7, "lat": 39.9, "elevation": 35.0},
    ]

    for s in stations:
        stmt = text("""
            INSERT INTO weather_stations (name, code, location, elevation, is_active, created_at)
            VALUES (:name, :code, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    :elevation, :is_active, :created_at)
        """)
        await db.execute(stmt, {
            **s,
            "is_active": True,
            "created_at": datetime.utcnow()
        })

    await db.commit()
    print(f"✓ 初始化气象站完成，共 {len(stations)} 个")


async def init_spore_sensors(db: AsyncSession):
    """初始化孢子传感器数据"""
    print("\n正在初始化孢子传感器数据...")

    result = await db.execute(text("SELECT COUNT(*) FROM spore_sensors"))
    count = result.scalar_one()
    if count > 0:
        print(f"✓ 孢子传感器已存在 ({count} 个)，跳过初始化")
        return

    sensors = [
        {"name": "小麦孢子监测1号", "code": "SP001", "lon": 116.4, "lat": 39.92,
         "crop_type": "WHEAT", "spore_type": "Puccinia_striiformis"},
        {"name": "小麦孢子监测2号", "code": "SP002", "lon": 116.45, "lat": 39.88,
         "crop_type": "WHEAT", "spore_type": "Puccinia_recondita"},
        {"name": "马铃薯孢子监测1号", "code": "SP003", "lon": 116.35, "lat": 39.95,
         "crop_type": "POTATO", "spore_type": "Phytophthora_infestans"},
        {"name": "马铃薯孢子监测2号", "code": "SP004", "lon": 116.5, "lat": 39.95,
         "crop_type": "POTATO", "spore_type": "Alternaria_solani"},
    ]

    for s in sensors:
        stmt = text("""
            INSERT INTO spore_sensors (name, code, location, crop_type, spore_type,
                                       is_active, created_at)
            VALUES (:name, :code, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    :crop_type::croptype, :spore_type, :is_active, :created_at)
        """)
        await db.execute(stmt, {
            **s,
            "is_active": True,
            "created_at": datetime.utcnow()
        })

    await db.commit()
    print(f"✓ 初始化孢子传感器完成，共 {len(sensors)} 个")


async def init_historical_weather_data(db: AsyncSession):
    """初始化历史气象数据（最近30天）"""
    print("\n正在初始化历史气象数据...")

    result = await db.execute(text("SELECT COUNT(*) FROM weather_data"))
    count = result.scalar_one()
    if count > 0:
        print(f"✓ 气象数据已存在 ({count} 条)，跳过初始化")
        return

    station_result = await db.execute(text("SELECT id FROM weather_stations"))
    station_ids = [row[0] for row in station_result.fetchall()]

    if not station_ids:
        print("⚠ 无气象站数据，跳过气象数据初始化")
        return

    start_date = datetime.utcnow() - timedelta(days=30)
    weather_data = []

    for station_id in station_ids:
        current_date = start_date
        while current_date < datetime.utcnow():
            temp_base = 18 + 10 * random.random()
            humid_base = 50 + 40 * random.random()

            weather_data.append({
                "station_id": station_id,
                "timestamp": current_date,
                "temperature": round(temp_base + random.uniform(-5, 5), 1),
                "relative_humidity": round(max(0, min(100, humid_base + random.uniform(-15, 15))), 1),
                "rainfall": round(max(0, random.expovariate(0.5) if random.random() < 0.3 else 0), 2),
                "leaf_wetness_duration": round(random.uniform(0, 18), 1),
                "wind_speed": round(random.uniform(0, 12), 1),
                "solar_radiation": round(random.uniform(50, 800), 1),
            })
            current_date += timedelta(hours=3)

    for wd in weather_data:
        stmt = text("""
            INSERT INTO weather_data (station_id, timestamp, temperature, relative_humidity,
                                      rainfall, leaf_wetness_duration, wind_speed, solar_radiation)
            VALUES (:station_id, :timestamp, :temperature, :relative_humidity,
                    :rainfall, :leaf_wetness_duration, :wind_speed, :solar_radiation)
        """)
        await db.execute(stmt, wd)

    await db.commit()
    print(f"✓ 初始化气象数据完成，共 {len(weather_data)} 条")


async def init_spore_data(db: AsyncSession):
    """初始化历史孢子数据（最近30天）"""
    print("\n正在初始化孢子数据...")

    result = await db.execute(text("SELECT COUNT(*) FROM spore_data"))
    count = result.scalar_one()
    if count > 0:
        print(f"✓ 孢子数据已存在 ({count} 条)，跳过初始化")
        return

    sensor_result = await db.execute(text("SELECT id FROM spore_sensors"))
    sensor_ids = [row[0] for row in sensor_result.fetchall()]

    if not sensor_ids:
        print("⚠ 无孢子传感器数据，跳过孢子数据初始化")
        return

    start_date = datetime.utcnow() - timedelta(days=30)
    spore_data = []

    for sensor_id in sensor_ids:
        current_date = start_date
        while current_date < datetime.utcnow():
            base_concentration = random.uniform(50, 500)
            if random.random() < 0.15:
                base_concentration *= random.uniform(3, 8)

            spore_data.append({
                "sensor_id": sensor_id,
                "timestamp": current_date,
                "concentration": round(base_concentration, 2),
                "created_at": datetime.utcnow(),
            })
            current_date += timedelta(hours=12)

    for sd in spore_data:
        stmt = text("""
            INSERT INTO spore_data (sensor_id, timestamp, concentration, created_at)
            VALUES (:sensor_id, :timestamp, :concentration, :created_at)
        """)
        await db.execute(stmt, sd)

    await db.commit()
    print(f"✓ 初始化孢子数据完成，共 {len(spore_data)} 条")


async def init_forecast_data(db: AsyncSession):
    """初始化预报数据（未来7天）"""
    print("\n正在初始化预报数据...")

    result = await db.execute(text("SELECT COUNT(*) FROM forecast_data"))
    count = result.scalar_one()
    if count > 0:
        print(f"✓ 预报数据已存在 ({count} 条)，跳过初始化")
        return

    grid_result = await db.execute(text("SELECT id FROM grid_cells LIMIT 50"))
    grid_ids = [row[0] for row in grid_result.fetchall()]

    if not grid_ids:
        print("⚠ 无网格数据，跳过预报数据初始化")
        return

    forecast_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    forecast_data = []

    for grid_id in grid_ids:
        for lead_hours in range(0, 169, 6):
            temp_base = 20 + 8 * random.random()
            hour_of_day = lead_hours % 24
            temp_variation = -5 * (hour_of_day < 6 or hour_of_day > 20) + 5 * (10 < hour_of_day < 16)

            forecast_data.append({
                "grid_id": grid_id,
                "forecast_date": forecast_date,
                "lead_time_hours": lead_hours,
                "temperature": round(temp_base + temp_variation + random.uniform(-2, 2), 1),
                "humidity": round(max(0, min(100, 60 + random.uniform(-20, 20))), 1),
                "rainfall": round(max(0, random.expovariate(1.0) if random.random() < 0.2 else 0), 2),
                "wind_speed": round(random.uniform(1, 10), 1),
                "created_at": datetime.utcnow(),
            })

    for fd in forecast_data:
        stmt = text("""
            INSERT INTO forecast_data (grid_id, forecast_date, lead_time_hours, temperature,
                                       humidity, rainfall, wind_speed, created_at)
            VALUES (:grid_id, :forecast_date, :lead_time_hours, :temperature,
                    :humidity, :rainfall, :wind_speed, :created_at)
        """)
        await db.execute(stmt, fd)

    await db.commit()
    print(f"✓ 初始化预报数据完成，共 {len(forecast_data)} 条")


async def calculate_initial_risk(db: AsyncSession):
    """计算初始风险地图"""
    print("\n正在计算初始风险地图...")

    result = await db.execute(text("SELECT COUNT(*) FROM risk_grids"))
    count = result.scalar_one()
    if count > 0:
        print(f"✓ 风险数据已存在 ({count} 条)，跳过计算")
        return

    engine = RiskEngine(db)

    for crop_type in [CropType.wheat, CropType.potato]:
        print(f"  计算 {crop_type.value} 风险...")
        await engine.calculate_risk_map(
            crop_type=crop_type,
            forecast_date=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
            resistance_level=3,
        )

    print("✓ 初始风险地图计算完成")


async def init_test_user(db: AsyncSession):
    """初始化测试用户"""
    print("\n正在初始化测试用户...")

    result = await db.execute(text("SELECT COUNT(*) FROM users WHERE email = :email"),
                              {"email": "test@example.com"})
    count = result.scalar_one()
    if count > 0:
        print("✓ 测试用户已存在，跳过初始化")
        return

    from app.core.security import get_password_hash

    hashed_pwd = get_password_hash("test123")

    stmt = text("""
        INSERT INTO users (email, hashed_password, full_name, is_active, created_at)
        VALUES (:email, :hashed_password, :full_name, :is_active, :created_at)
        RETURNING id
    """)
    result = await db.execute(stmt, {
        "email": "test@example.com",
        "hashed_password": hashed_pwd,
        "full_name": "测试用户",
        "is_active": True,
        "created_at": datetime.utcnow()
    })
    user_id = result.scalar_one()

    config_stmt = text("""
        INSERT INTO user_configs (user_id, crop_type, variety_name, resistance_level,
                                  risk_threshold, notification_email, created_at, updated_at)
        VALUES (:user_id, :crop_type::croptype, :variety_name, :resistance_level,
                :risk_threshold, :notification_email, :created_at, :updated_at)
    """)

    for crop in ["WHEAT", "POTATO"]:
        await db.execute(config_stmt, {
            "user_id": user_id,
            "crop_type": crop,
            "variety_name": "济麦22" if crop == "WHEAT" else "克新1号",
            "resistance_level": 3,
            "risk_threshold": 40.0,
            "notification_email": "test@example.com",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

    await db.commit()
    print("✓ 初始化测试用户完成 (邮箱: test@example.com, 密码: test123)")


async def main():
    """主初始化函数"""
    print("=" * 80)
    print("  农业病害预警系统 - 数据库初始化（含新功能表）")
    print("=" * 80)
    print(f"\n数据库: {settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}")
    print(f"用户: {settings.DATABASE_USER}")

    try:
        if not await create_tables():
            return 1

        async with AsyncSessionLocal() as db:
            await init_grid_cells(db)
            await init_weather_stations(db)
            await init_spore_sensors(db)
            await init_historical_weather_data(db)
            await init_spore_data(db)
            await init_forecast_data(db)
            await calculate_initial_risk(db)
            await init_test_user(db)

        print("\n" + "=" * 80)
        print("✅ 数据库初始化完成！")
        print("\n新增功能表已创建:")
        print("  - risk_attributions  (风险归因分析)")
        print("  - drone_flights       (无人机飞行记录)")
        print("  - drone_images        (无人机影像)")
        print("  - drone_disease_detections  (无人机病害检测)")
        print("  - pesticide_products  (农药产品库)")
        print("  - spray_recommendations  (喷洒建议)")
        print("\n现在可以运行: python test_new_features.py")
        print("=" * 80)

        return 0

    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
