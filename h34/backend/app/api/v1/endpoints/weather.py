from datetime import datetime
from typing import Annotated, Optional, List, Dict

from fastapi import APIRouter, Depends, Query, HTTPException, status
from geoalchemy2 import WKTElement
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models import WeatherData, WeatherStation
from app.schemas.auth import CurrentUser
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.weather import (
    WeatherDataCreate,
    WeatherDataBatchCreate,
    WeatherDataResponse,
    WeatherStationCreate,
    WeatherStationResponse,
)

router = APIRouter()


@router.get(
    "/stations",
    response_model=ApiResponse[PaginatedResponse[WeatherStationResponse]],
    summary="气象站列表（分页）",
)
async def get_stations(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    is_active: Annotated[Optional[bool], Query(description="是否仅显示活跃站点")] = None,
) -> ApiResponse[PaginatedResponse[WeatherStationResponse]]:
    query = select(WeatherStation)

    if is_active is not None:
        query = query.where(WeatherStation.is_active == is_active)

    count_query = select(func.count(WeatherStation.id)).select_from(
        query.subquery()
    )
    total = await db.scalar(count_query) or 0

    query = query.order_by(WeatherStation.id).offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    stations = result.scalars().all()

    items = []
    for s in stations:
        station_data = WeatherStationResponse(
            id=s.id,
            name=s.name,
            code=s.code,
            lat=s.latitude or 0.0,
            lon=s.longitude or 0.0,
            elevation=s.elevation,
            is_active=s.is_active,
            created_at=s.created_at,
        )
        items.append(station_data)

    return ApiResponse(
        data=PaginatedResponse(
            items=items,
            page=pagination.page,
            page_size=pagination.page_size,
            total=total,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size,
        )
    )


@router.post(
    "/stations",
    response_model=ApiResponse[WeatherStationResponse],
    summary="创建气象站",
)
async def create_station(
    station_in: WeatherStationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[WeatherStationResponse]:
    existing_query = select(WeatherStation).where(WeatherStation.code == station_in.code)
    existing_result = await db.execute(existing_query)
    existing_station = existing_result.scalar_one_or_none()

    if existing_station:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="气象站编码已存在",
        )

    location_wkt = f"POINT({station_in.lon} {station_in.lat})"
    location_geom = WKTElement(location_wkt, srid=4326)

    station = WeatherStation(
        name=station_in.name,
        code=station_in.code,
        location=location_geom,
        elevation=station_in.elevation,
        is_active=station_in.is_active,
    )

    db.add(station)
    await db.commit()
    await db.refresh(station)

    response = WeatherStationResponse(
        id=station.id,
        name=station.name,
        code=station.code,
        lat=station.latitude or 0.0,
        lon=station.longitude or 0.0,
        elevation=station.elevation,
        is_active=station.is_active,
        created_at=station.created_at,
    )

    return ApiResponse(data=response)


@router.get(
    "/stations/{station_id}",
    response_model=ApiResponse[WeatherStationResponse],
    summary="获取单个气象站",
)
async def get_station(
    station_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[WeatherStationResponse]:
    query = select(WeatherStation).where(WeatherStation.id == station_id)
    result = await db.execute(query)
    station = result.scalar_one_or_none()

    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="气象站不存在",
        )

    response = WeatherStationResponse(
        id=station.id,
        name=station.name,
        code=station.code,
        lat=station.latitude or 0.0,
        lon=station.longitude or 0.0,
        elevation=station.elevation,
        is_active=station.is_active,
        created_at=station.created_at,
    )

    return ApiResponse(data=response)


@router.get(
    "/data",
    response_model=ApiResponse[PaginatedResponse[WeatherDataResponse]],
    summary="气象数据列表",
)
async def get_weather_data(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    station_id: Annotated[Optional[int], Query(description="站点ID")] = None,
    start_date: Annotated[Optional[datetime], Query(description="开始时间")] = None,
    end_date: Annotated[Optional[datetime], Query(description="结束时间")] = None,
) -> ApiResponse[PaginatedResponse[WeatherDataResponse]]:
    query = select(WeatherData)

    if station_id:
        query = query.where(WeatherData.station_id == station_id)
    if start_date:
        query = query.where(WeatherData.timestamp >= start_date)
    if end_date:
        query = query.where(WeatherData.timestamp <= end_date)

    count_query = select(func.count(WeatherData.id)).select_from(
        query.subquery()
    )
    total = await db.scalar(count_query) or 0

    query = query.order_by(WeatherData.timestamp.desc()).offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    data = result.scalars().all()

    items = [WeatherDataResponse.model_validate(d) for d in data]

    return ApiResponse(
        data=PaginatedResponse(
            items=items,
            page=pagination.page,
            page_size=pagination.page_size,
            total=total,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size,
        )
    )


@router.post(
    "/data",
    response_model=ApiResponse[WeatherDataResponse],
    summary="单条气象数据",
)
async def create_weather_data(
    data_in: WeatherDataCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[WeatherDataResponse]:
    station_query = select(WeatherStation).where(WeatherStation.id == data_in.station_id)
    station_result = await db.execute(station_query)
    station = station_result.scalar_one_or_none()

    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="气象站不存在",
        )

    existing_query = select(WeatherData).where(
        and_(
            WeatherData.station_id == data_in.station_id,
            WeatherData.timestamp == data_in.timestamp,
        )
    )
    existing_result = await db.execute(existing_query)
    existing_data = existing_result.scalar_one_or_none()

    if existing_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该时间点的气象数据已存在",
        )

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

    db.add(weather_data)
    await db.commit()
    await db.refresh(weather_data)

    return ApiResponse(data=WeatherDataResponse.model_validate(weather_data))


@router.post(
    "/data/batch",
    response_model=ApiResponse[Dict[str, int]],
    summary="批量气象数据",
)
async def create_weather_data_batch(
    batch_in: WeatherDataBatchCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[Dict[str, int]]:
    station_ids = {d.station_id for d in batch_in.data}

    stations_query = select(WeatherStation.id).where(
        WeatherStation.id.in_(list(station_ids))
    )
    stations_result = await db.execute(stations_query)
    existing_station_ids = set(stations_result.scalars().all())

    missing_stations = station_ids - existing_station_ids
    if missing_stations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"气象站ID不存在: {missing_stations}",
        )

    created_count = 0
    skipped_count = 0

    for data_in in batch_in.data:
        existing_query = select(WeatherData).where(
            and_(
                WeatherData.station_id == data_in.station_id,
                WeatherData.timestamp == data_in.timestamp,
            )
        )
        existing_result = await db.execute(existing_query)
        existing_data = existing_result.scalar_one_or_none()

        if existing_data:
            skipped_count += 1
            continue

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

        db.add(weather_data)
        created_count += 1

    await db.commit()

    return ApiResponse(
        data={
            "created": created_count,
            "skipped": skipped_count,
            "total": len(batch_in.data),
        }
    )


@router.get(
    "/data/latest",
    response_model=ApiResponse[List[WeatherDataResponse]],
    summary="各站最新数据",
)
async def get_latest_weather_data(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[List[WeatherDataResponse]]:
    subquery = (
        select(
            WeatherData.station_id,
            func.max(WeatherData.timestamp).label("latest_timestamp"),
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
                WeatherData.timestamp == subquery.c.latest_timestamp,
            ),
        )
        .order_by(WeatherData.station_id)
    )

    result = await db.execute(query)
    latest_data = result.scalars().all()

    items = [WeatherDataResponse.model_validate(d) for d in latest_data]

    return ApiResponse(data=items)
