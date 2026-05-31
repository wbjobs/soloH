from datetime import datetime
from typing import Annotated, Optional, List, Dict

from fastapi import APIRouter, Depends, Query, HTTPException, status
from geoalchemy2 import WKTElement
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models import SporeData, SporeSensor
from app.schemas.auth import CurrentUser
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.spore import (
    SporeDataCreate,
    SporeDataBatchCreate,
    SporeDataResponse,
    SporeSensorCreate,
    SporeSensorResponse,
)

router = APIRouter()


@router.get(
    "/sensors",
    response_model=ApiResponse[PaginatedResponse[SporeSensorResponse]],
    summary="孢子传感器列表",
)
async def get_sensors(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    is_active: Annotated[Optional[bool], Query(description="是否仅显示活跃传感器")] = None,
) -> ApiResponse[PaginatedResponse[SporeSensorResponse]]:
    query = select(SporeSensor)

    if is_active is not None:
        query = query.where(SporeSensor.is_active == is_active)

    count_query = select(func.count(SporeSensor.id)).select_from(
        query.subquery()
    )
    total = await db.scalar(count_query) or 0

    query = query.order_by(SporeSensor.id).offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    sensors = result.scalars().all()

    items = []
    for s in sensors:
        sensor_data = SporeSensorResponse(
            id=s.id,
            name=s.name,
            code=s.code,
            lat=s.latitude or 0.0,
            lon=s.longitude or 0.0,
            crop_type=s.crop_type,
            spore_type=s.spore_type,
            is_active=s.is_active,
            created_at=s.created_at,
        )
        items.append(sensor_data)

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
    "/sensors",
    response_model=ApiResponse[SporeSensorResponse],
    summary="创建传感器",
)
async def create_sensor(
    sensor_in: SporeSensorCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[SporeSensorResponse]:
    existing_query = select(SporeSensor).where(SporeSensor.code == sensor_in.code)
    existing_result = await db.execute(existing_query)
    existing_sensor = existing_result.scalar_one_or_none()

    if existing_sensor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="传感器编码已存在",
        )

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

    db.add(sensor)
    await db.commit()
    await db.refresh(sensor)

    response = SporeSensorResponse(
        id=sensor.id,
        name=sensor.name,
        code=sensor.code,
        lat=sensor.latitude or 0.0,
        lon=sensor.longitude or 0.0,
        crop_type=sensor.crop_type,
        spore_type=sensor.spore_type,
        is_active=sensor.is_active,
        created_at=sensor.created_at,
    )

    return ApiResponse(data=response)


@router.get(
    "/data",
    response_model=ApiResponse[PaginatedResponse[SporeDataResponse]],
    summary="孢子数据列表",
)
async def get_spore_data(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    sensor_id: Annotated[Optional[int], Query(description="传感器ID")] = None,
    start_date: Annotated[Optional[datetime], Query(description="开始时间")] = None,
    end_date: Annotated[Optional[datetime], Query(description="结束时间")] = None,
) -> ApiResponse[PaginatedResponse[SporeDataResponse]]:
    query = select(SporeData)

    if sensor_id:
        query = query.where(SporeData.sensor_id == sensor_id)
    if start_date:
        query = query.where(SporeData.timestamp >= start_date)
    if end_date:
        query = query.where(SporeData.timestamp <= end_date)

    count_query = select(func.count(SporeData.id)).select_from(
        query.subquery()
    )
    total = await db.scalar(count_query) or 0

    query = query.order_by(SporeData.timestamp.desc()).offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    data = result.scalars().all()

    items = [SporeDataResponse.model_validate(d) for d in data]

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
    response_model=ApiResponse[SporeDataResponse],
    summary="单条孢子数据",
)
async def create_spore_data(
    data_in: SporeDataCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[SporeDataResponse]:
    sensor_query = select(SporeSensor).where(SporeSensor.id == data_in.sensor_id)
    sensor_result = await db.execute(sensor_query)
    sensor = sensor_result.scalar_one_or_none()

    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="孢子传感器不存在",
        )

    existing_query = select(SporeData).where(
        and_(
            SporeData.sensor_id == data_in.sensor_id,
            SporeData.timestamp == data_in.timestamp,
        )
    )
    existing_result = await db.execute(existing_query)
    existing_data = existing_result.scalar_one_or_none()

    if existing_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该时间点的孢子数据已存在",
        )

    spore_data = SporeData(
        sensor_id=data_in.sensor_id,
        timestamp=data_in.timestamp,
        concentration=data_in.concentration,
    )

    db.add(spore_data)
    await db.commit()
    await db.refresh(spore_data)

    return ApiResponse(data=SporeDataResponse.model_validate(spore_data))


@router.post(
    "/data/batch",
    response_model=ApiResponse[Dict[str, int]],
    summary="批量孢子数据",
)
async def create_spore_data_batch(
    batch_in: SporeDataBatchCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[Dict[str, int]]:
    sensor_ids = {d.sensor_id for d in batch_in.data}

    sensors_query = select(SporeSensor.id).where(
        SporeSensor.id.in_(list(sensor_ids))
    )
    sensors_result = await db.execute(sensors_query)
    existing_sensor_ids = set(sensors_result.scalars().all())

    missing_sensors = sensor_ids - existing_sensor_ids
    if missing_sensors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"孢子传感器ID不存在: {missing_sensors}",
        )

    created_count = 0
    skipped_count = 0

    for data_in in batch_in.data:
        existing_query = select(SporeData).where(
            and_(
                SporeData.sensor_id == data_in.sensor_id,
                SporeData.timestamp == data_in.timestamp,
            )
        )
        existing_result = await db.execute(existing_query)
        existing_data = existing_result.scalar_one_or_none()

        if existing_data:
            skipped_count += 1
            continue

        spore_data = SporeData(
            sensor_id=data_in.sensor_id,
            timestamp=data_in.timestamp,
            concentration=data_in.concentration,
        )

        db.add(spore_data)
        created_count += 1

    await db.commit()

    return ApiResponse(
        data={
            "created": created_count,
            "skipped": skipped_count,
            "total": len(batch_in.data),
        }
    )
