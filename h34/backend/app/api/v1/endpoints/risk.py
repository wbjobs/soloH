from datetime import datetime, timedelta
from typing import Annotated, Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.functions import ST_AsGeoJSON, ST_Contains, ST_MakePoint, ST_SetSRID
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models import CropType, ForecastData, GridCell, RiskGrid
from app.schemas.auth import CurrentUser
from app.schemas.common import ApiResponse, PaginationParams
from app.schemas.risk import RiskMapResponse, RiskGridGeoJSONFeature

router = APIRouter()


class PointRiskDetail(BaseModel):
    lat: float
    lon: float
    crop_type: CropType
    risk_index: float
    risk_level: str
    infection_probability: Optional[float]
    grid_id: int
    forecast_date: datetime
    model_version: Optional[str]
    calculated_at: datetime


class RiskCalculateResponse(BaseModel):
    status: str
    message: str
    crop_type: CropType
    forecast_date: datetime
    calculated_count: int
    model_version: str


class RiskForecastItem(BaseModel):
    date: datetime
    risk_index: float
    risk_level: str
    temperature: Optional[float]
    humidity: Optional[float]
    rainfall: Optional[float]


class RiskForecastResponse(BaseModel):
    lat: float
    lon: float
    crop_type: CropType
    forecast: List[RiskForecastItem]


class RiskHistoryItem(BaseModel):
    date: datetime
    risk_index: float
    risk_level: str
    infection_probability: Optional[float]


class RiskHistoryResponse(BaseModel):
    grid_id: int
    crop_type: CropType
    start_date: datetime
    end_date: datetime
    history: List[RiskHistoryItem]


class RiskMapQueryParams(BaseModel):
    crop_type: CropType
    forecast_date: Optional[datetime] = None
    lat_min: Optional[float] = Query(None, ge=-90, le=90)
    lat_max: Optional[float] = Query(None, ge=-90, le=90)
    lon_min: Optional[float] = Query(None, ge=-180, le=180)
    lon_max: Optional[float] = Query(None, ge=-180, le=180)


def get_risk_level(risk_index: float) -> str:
    if risk_index < 20:
        return "低"
    elif risk_index < 40:
        return "较低"
    elif risk_index < 60:
        return "中"
    elif risk_index < 80:
        return "较高"
    else:
        return "高"


@router.get(
    "/map",
    response_model=ApiResponse[RiskMapResponse],
    summary="获取风险地图GeoJSON",
)
async def get_risk_map(
    params: Annotated[RiskMapQueryParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[RiskMapResponse]:
    forecast_date = params.forecast_date or datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    query = (
        select(
            RiskGrid,
            GridCell,
            ST_AsGeoJSON(GridCell.bounds).label("bounds_geojson"),
        )
        .join(GridCell, RiskGrid.grid_id == GridCell.id)
        .where(
            and_(
                RiskGrid.crop_type == params.crop_type,
                func.date(RiskGrid.forecast_date) == func.date(forecast_date),
            )
        )
    )

    if params.lat_min is not None and params.lat_max is not None:
        query = query.where(
            and_(
                GridCell.centroid.ST_Y() >= params.lat_min,
                GridCell.centroid.ST_Y() <= params.lat_max,
            )
        )

    if params.lon_min is not None and params.lon_max is not None:
        query = query.where(
            and_(
                GridCell.centroid.ST_X() >= params.lon_min,
                GridCell.centroid.ST_X() <= params.lon_max,
            )
        )

    result = await db.execute(query)
    rows = result.all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到指定条件的风险数据",
        )

    features = []
    model_version = None

    for risk_grid, grid_cell, bounds_geojson in rows:
        if model_version is None:
            model_version = risk_grid.model_version

        feature = RiskGridGeoJSONFeature(
            geometry=bounds_geojson,
            properties={
                "grid_id": grid_cell.id,
                "grid_x": grid_cell.grid_x,
                "grid_y": grid_cell.grid_y,
                "risk_index": risk_grid.risk_index,
                "risk_level": get_risk_level(risk_grid.risk_index),
                "infection_probability": risk_grid.infection_probability,
                "lat": grid_cell.lat,
                "lon": grid_cell.lon,
            },
        )
        features.append(feature)

    response = RiskMapResponse(
        features=features,
        forecast_date=forecast_date,
        crop_type=params.crop_type,
        model_version=model_version,
    )

    return ApiResponse(data=response)


@router.get(
    "/point",
    response_model=ApiResponse[PointRiskDetail],
    summary="获取单点风险",
)
async def get_point_risk(
    lat: Annotated[float, Query(..., ge=-90, le=90, description="纬度")],
    lon: Annotated[float, Query(..., ge=-180, le=180, description="经度")],
    crop_type: Annotated[CropType, Query(..., description="作物类型")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    forecast_date: Annotated[
        Optional[datetime], Query(description="预报日期")
    ] = None,
) -> ApiResponse[PointRiskDetail]:
    forecast_date = forecast_date or datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)

    query = (
        select(RiskGrid, GridCell)
        .join(GridCell, RiskGrid.grid_id == GridCell.id)
        .where(
            and_(
                RiskGrid.crop_type == crop_type,
                func.date(RiskGrid.forecast_date) == func.date(forecast_date),
                ST_Contains(GridCell.bounds, point),
            )
        )
    )

    result = await db.execute(query)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该坐标点无风险数据",
        )

    risk_grid, grid_cell = row

    response = PointRiskDetail(
        lat=lat,
        lon=lon,
        crop_type=crop_type,
        risk_index=risk_grid.risk_index,
        risk_level=get_risk_level(risk_grid.risk_index),
        infection_probability=risk_grid.infection_probability,
        grid_id=grid_cell.id,
        forecast_date=risk_grid.forecast_date,
        model_version=risk_grid.model_version,
        calculated_at=risk_grid.calculated_at,
    )

    return ApiResponse(data=response)


@router.post(
    "/calculate",
    response_model=ApiResponse[RiskCalculateResponse],
    summary="手动触发风险计算",
)
async def calculate_risk(
    crop_type: Annotated[CropType, Query(..., description="作物类型")],
    forecast_date: Annotated[
        Optional[datetime], Query(description="预报日期")
    ] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[RiskCalculateResponse]:
    forecast_date = forecast_date or datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    grid_query = select(func.count(GridCell.id))
    grid_result = await db.execute(grid_query)
    total_grids = grid_result.scalar_one()

    if total_grids == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有可用的网格数据",
        )

    from app.models import JensenModel

    model = JensenModel()
    model_version = "1.0.0"
    calculated_count = 0

    weather_query = select(ForecastData).where(
        func.date(ForecastData.forecast_date) == func.date(forecast_date)
    )
    weather_result = await db.execute(weather_query)
    forecast_data = weather_result.scalars().all()

    weather_by_grid = {}
    for fd in forecast_data:
        if fd.grid_id not in weather_by_grid:
            weather_by_grid[fd.grid_id] = []
        weather_by_grid[fd.grid_id].append(fd)

    grid_cells_query = select(GridCell)
    grid_cells_result = await db.execute(grid_cells_query)
    grid_cells = grid_cells_result.scalars().all()

    for grid_cell in grid_cells:
        grid_weather = weather_by_grid.get(grid_cell.id, [])

        if not grid_weather:
            continue

        avg_temp = sum(w.temperature or 0 for w in grid_weather) / len(grid_weather)
        avg_humidity = sum(w.humidity or 0 for w in grid_weather) / len(grid_weather)
        total_rainfall = sum(w.rainfall or 0 for w in grid_weather)

        risk_index = model.predict(
            temperature=avg_temp,
            relative_humidity=avg_humidity,
            rainfall=total_rainfall,
            leaf_wetness_duration=avg_humidity * 0.1,
        )

        infection_probability = model.calculate_infection_probability(
            temperature=avg_temp,
            relative_humidity=avg_humidity,
        )

        existing_query = select(RiskGrid).where(
            and_(
                RiskGrid.grid_id == grid_cell.id,
                RiskGrid.crop_type == crop_type,
                func.date(RiskGrid.forecast_date) == func.date(forecast_date),
            )
        )
        existing_result = await db.execute(existing_query)
        existing_risk = existing_result.scalar_one_or_none()

        if existing_risk:
            existing_risk.risk_index = risk_index
            existing_risk.infection_probability = infection_probability
            existing_risk.model_version = model_version
            existing_risk.calculated_at = datetime.utcnow()
        else:
            new_risk = RiskGrid(
                grid_id=grid_cell.id,
                forecast_date=forecast_date,
                crop_type=crop_type,
                risk_index=risk_index,
                infection_probability=infection_probability,
                model_version=model_version,
            )
            db.add(new_risk)

        calculated_count += 1

    await db.commit()

    response = RiskCalculateResponse(
        status="success",
        message=f"成功计算 {calculated_count} 个网格的风险数据",
        crop_type=crop_type,
        forecast_date=forecast_date,
        calculated_count=calculated_count,
        model_version=model_version,
    )

    return ApiResponse(data=response)


@router.get(
    "/forecast",
    response_model=ApiResponse[RiskForecastResponse],
    summary="获取未来7天风险预测",
)
async def get_risk_forecast(
    lat: Annotated[float, Query(..., ge=-90, le=90, description="纬度")],
    lon: Annotated[float, Query(..., ge=-180, le=180, description="经度")],
    crop_type: Annotated[CropType, Query(..., description="作物类型")],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[RiskForecastResponse]:
    point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)

    grid_query = select(GridCell).where(ST_Contains(GridCell.bounds, point))
    grid_result = await db.execute(grid_query)
    grid_cell = grid_result.scalar_one_or_none()

    if not grid_cell:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该坐标点不在任何网格内",
        )

    start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=7)

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

    forecast_result = await db.execute(forecast_query)
    forecast_data = forecast_result.scalars().all()

    if not forecast_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该区域无预报数据",
        )

    daily_data = {}
    for fd in forecast_data:
        date_key = fd.forecast_date.date()
        if date_key not in daily_data:
            daily_data[date_key] = {
                "temperatures": [],
                "humidities": [],
                "rainfalls": [],
            }
        if fd.temperature is not None:
            daily_data[date_key]["temperatures"].append(fd.temperature)
        if fd.humidity is not None:
            daily_data[date_key]["humidities"].append(fd.humidity)
        if fd.rainfall is not None:
            daily_data[date_key]["rainfalls"].append(fd.rainfall)

    from app.models import JensenModel

    model = JensenModel()
    forecast_items = []

    for i in range(7):
        current_date = start_date + timedelta(days=i)
        date_key = current_date.date()

        data = daily_data.get(date_key, {})
        avg_temp = sum(data.get("temperatures", [0])) / max(len(data.get("temperatures", [])), 1)
        avg_humidity = sum(data.get("humidities", [0])) / max(len(data.get("humidities", [])), 1)
        total_rainfall = sum(data.get("rainfalls", [0]))

        risk_index = model.predict(
            temperature=avg_temp,
            relative_humidity=avg_humidity,
            rainfall=total_rainfall,
            leaf_wetness_duration=avg_humidity * 0.1,
        )

        forecast_items.append(
            RiskForecastItem(
                date=current_date,
                risk_index=risk_index,
                risk_level=get_risk_level(risk_index),
                temperature=avg_temp if data.get("temperatures") else None,
                humidity=avg_humidity if data.get("humidities") else None,
                rainfall=total_rainfall if data.get("rainfalls") else None,
            )
        )

    response = RiskForecastResponse(
        lat=lat,
        lon=lon,
        crop_type=crop_type,
        forecast=forecast_items,
    )

    return ApiResponse(data=response)


@router.get(
    "/history",
    response_model=ApiResponse[RiskHistoryResponse],
    summary="获取历史风险数据",
)
async def get_risk_history(
    grid_id: Annotated[int, Query(..., description="网格ID")],
    start_date: Annotated[datetime, Query(..., description="开始日期")],
    end_date: Annotated[datetime, Query(..., description="结束日期")],
    crop_type: Annotated[CropType, Query(..., description="作物类型")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    pagination: Annotated[PaginationParams, Depends()] = None,
) -> ApiResponse[RiskHistoryResponse]:
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="开始日期不能大于结束日期",
        )

    grid_query = select(GridCell).where(GridCell.id == grid_id)
    grid_result = await db.execute(grid_query)
    grid_cell = grid_result.scalar_one_or_none()

    if not grid_cell:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="网格不存在",
        )

    count_query = select(func.count(RiskGrid.id)).where(
        and_(
            RiskGrid.grid_id == grid_id,
            RiskGrid.crop_type == crop_type,
            RiskGrid.forecast_date >= start_date,
            RiskGrid.forecast_date <= end_date,
        )
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到历史风险数据",
        )

    history_query = (
        select(RiskGrid)
        .where(
            and_(
                RiskGrid.grid_id == grid_id,
                RiskGrid.crop_type == crop_type,
                RiskGrid.forecast_date >= start_date,
                RiskGrid.forecast_date <= end_date,
            )
        )
        .order_by(RiskGrid.forecast_date)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )

    history_result = await db.execute(history_query)
    risk_history = history_result.scalars().all()

    history_items = []
    for rh in risk_history:
        history_items.append(
            RiskHistoryItem(
                date=rh.forecast_date,
                risk_index=rh.risk_index,
                risk_level=get_risk_level(rh.risk_index),
                infection_probability=rh.infection_probability,
            )
        )

    response = RiskHistoryResponse(
        grid_id=grid_id,
        crop_type=crop_type,
        start_date=start_date,
        end_date=end_date,
        history=history_items,
    )

    return ApiResponse(data=response)
