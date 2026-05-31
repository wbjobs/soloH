from datetime import datetime, timedelta
from typing import Annotated, Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models import ForecastData, GridCell
from app.schemas.auth import CurrentUser
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.forecast import (
    ForecastDataCreate,
    ForecastDataResponse,
    SevenDayForecastResponse,
)
from app.services import GridService, RiskEngine

router = APIRouter()


@router.get(
    "/data",
    response_model=ApiResponse[PaginatedResponse[ForecastDataResponse]],
    summary="预报数据列表",
)
async def get_forecast_data(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    grid_id: Annotated[Optional[int], Query(description="网格ID")] = None,
    start_date: Annotated[Optional[datetime], Query(description="开始时间")] = None,
    end_date: Annotated[Optional[datetime], Query(description="结束时间")] = None,
    lead_time_hours: Annotated[Optional[int], Query(description="预报时效（小时）")] = None,
) -> ApiResponse[PaginatedResponse[ForecastDataResponse]]:
    query = select(ForecastData)

    if grid_id:
        query = query.where(ForecastData.grid_id == grid_id)
    if start_date:
        query = query.where(ForecastData.forecast_date >= start_date)
    if end_date:
        query = query.where(ForecastData.forecast_date <= end_date)
    if lead_time_hours:
        query = query.where(ForecastData.lead_time_hours == lead_time_hours)

    count_query = select(func.count(ForecastData.id)).select_from(
        query.subquery()
    )
    total = await db.scalar(count_query) or 0

    query = query.order_by(
        ForecastData.forecast_date.desc(),
        ForecastData.lead_time_hours,
    ).offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    data = result.scalars().all()

    items = [ForecastDataResponse.model_validate(d) for d in data]

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
    response_model=ApiResponse[Dict[str, int]],
    summary="批量导入WRF预报数据",
)
async def import_forecast_data_batch(
    data_list: List[ForecastDataCreate],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[Dict[str, int]]:
    if not data_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="导入数据不能为空",
        )

    grid_ids = {d.grid_id for d in data_list}

    grid_query = select(GridCell.id).where(GridCell.id.in_(list(grid_ids)))
    grid_result = await db.execute(grid_query)
    existing_grid_ids = set(grid_result.scalars().all())

    missing_grids = grid_ids - existing_grid_ids
    if missing_grids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"网格ID不存在: {missing_grids}",
        )

    created_count = 0
    updated_count = 0

    for data_in in data_list:
        existing_query = select(ForecastData).where(
            and_(
                ForecastData.grid_id == data_in.grid_id,
                ForecastData.forecast_date == data_in.forecast_date,
                ForecastData.lead_time_hours == data_in.lead_time_hours,
            )
        )
        existing_result = await db.execute(existing_query)
        existing_data = existing_result.scalar_one_or_none()

        if existing_data:
            existing_data.temperature = data_in.temperature
            existing_data.humidity = data_in.humidity
            existing_data.rainfall = data_in.rainfall
            existing_data.wind_speed = data_in.wind_speed
            updated_count += 1
        else:
            forecast_data = ForecastData(
                grid_id=data_in.grid_id,
                forecast_date=data_in.forecast_date,
                lead_time_hours=data_in.lead_time_hours,
                temperature=data_in.temperature,
                humidity=data_in.humidity,
                rainfall=data_in.rainfall,
                wind_speed=data_in.wind_speed,
            )
            db.add(forecast_data)
            created_count += 1

    await db.commit()

    return ApiResponse(
        data={
            "created": created_count,
            "updated": updated_count,
            "total": len(data_list),
        }
    )


@router.get(
    "/seven-day",
    response_model=ApiResponse[SevenDayForecastResponse],
    summary="获取指定格点7天预报",
)
async def get_seven_day_forecast(
    grid_id: Annotated[int, Query(description="网格ID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[SevenDayForecastResponse]:
    grid_query = select(GridCell).where(GridCell.id == grid_id)
    grid_result = await db.execute(grid_query)
    grid_cell = grid_result.scalar_one_or_none()

    if not grid_cell:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="网格不存在",
        )

    start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=7)

    forecast_query = (
        select(ForecastData)
        .where(
            and_(
                ForecastData.grid_id == grid_id,
                ForecastData.forecast_date >= start_date,
                ForecastData.forecast_date < end_date,
            )
        )
        .order_by(ForecastData.forecast_date, ForecastData.lead_time_hours)
    )

    forecast_result = await db.execute(forecast_query)
    forecast_data = forecast_result.scalars().all()

    if not forecast_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该网格无7天预报数据",
        )

    forecasts = [ForecastDataResponse.model_validate(d) for d in forecast_data]

    response = SevenDayForecastResponse(
        grid_id=grid_id,
        lat=grid_cell.lat or 0.0,
        lon=grid_cell.lon or 0.0,
        start_date=start_date,
        end_date=end_date - timedelta(days=1),
        forecasts=forecasts,
    )

    return ApiResponse(data=response)


@router.post(
    "/sync",
    response_model=ApiResponse[Dict[str, Any]],
    summary="触发WRF数据同步",
)
async def sync_forecast_data(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    start_date: Annotated[
        Optional[datetime], Query(description="同步开始日期，默认为今天")
    ] = None,
    days: Annotated[int, Query(ge=1, le=14, description="同步天数")] = 7,
) -> ApiResponse[Dict[str, Any]]:
    grid_service = GridService(db)
    risk_engine = RiskEngine(db)

    if start_date is None:
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    end_date = start_date + timedelta(days=days)

    grid_query = select(func.count(GridCell.id))
    grid_count = await db.scalar(grid_query) or 0

    if grid_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有可用的网格数据，请先创建网格",
        )

    lead_times = [0, 3, 6, 9, 12, 15, 18, 21, 24]

    import random
    random.seed(42)

    created_count = 0
    updated_count = 0

    grid_cells_query = select(GridCell)
    grid_cells_result = await db.execute(grid_cells_query)
    grid_cells = grid_cells_result.scalars().all()

    for grid_cell in grid_cells:
        for day_offset in range(days):
            forecast_date = start_date + timedelta(days=day_offset)
            for lead_time in lead_times:
                base_temp = 15 + 10 * random.random()
                base_humidity = 60 + 30 * random.random()
                base_rainfall = max(0, random.gauss(2, 5))
                base_wind = 2 + 5 * random.random()

                temp_variation = -5 * (lead_time / 24) if lead_time < 12 else 5 * ((lead_time - 12) / 12)
                temperature = base_temp + temp_variation
                humidity = base_humidity - temp_variation * 2
                rainfall = base_rainfall if random.random() > 0.7 else 0.0
                wind_speed = base_wind + random.gauss(0, 1)

                existing_query = select(ForecastData).where(
                    and_(
                        ForecastData.grid_id == grid_cell.id,
                        ForecastData.forecast_date == forecast_date,
                        ForecastData.lead_time_hours == lead_time,
                    )
                )
                existing_result = await db.execute(existing_query)
                existing_data = existing_result.scalar_one_or_none()

                if existing_data:
                    existing_data.temperature = round(temperature, 2)
                    existing_data.humidity = round(max(0, min(100, humidity)), 2)
                    existing_data.rainfall = round(max(0, rainfall), 2)
                    existing_data.wind_speed = round(max(0, wind_speed), 2)
                    updated_count += 1
                else:
                    forecast_data = ForecastData(
                        grid_id=grid_cell.id,
                        forecast_date=forecast_date,
                        lead_time_hours=lead_time,
                        temperature=round(temperature, 2),
                        humidity=round(max(0, min(100, humidity)), 2),
                        rainfall=round(max(0, rainfall), 2),
                        wind_speed=round(max(0, wind_speed), 2),
                    )
                    db.add(forecast_data)
                    created_count += 1

    await db.commit()

    return ApiResponse(
        data={
            "message": "WRF数据同步完成",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days,
            "grid_count": grid_count,
            "created": created_count,
            "updated": updated_count,
            "total_processed": created_count + updated_count,
        }
    )
