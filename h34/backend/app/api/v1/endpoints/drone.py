from datetime import datetime
from typing import Annotated, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models import CropType
from app.schemas.auth import CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.drone import (
    DroneFlightCreate,
    DroneFlightResponse,
    DroneImageAdd,
    ImageAnalysisResponse,
    DetectionSave,
    DetectionResponse,
    FlightProcessResponse,
    DetectionHeatmapResponse,
)
from app.services.drone_service import DroneService

router = APIRouter()


@router.post(
    "/flight",
    response_model=ApiResponse[DroneFlightResponse],
    summary="创建无人机飞行记录",
)
async def create_flight(
    params: DroneFlightCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[DroneFlightResponse]:
    """
    创建新的无人机飞行记录
    """
    service = DroneService(db)
    flight = await service.create_flight(
        flight_code=params.flight_code,
        drone_id=params.drone_id,
        crop_type=params.crop_type,
        flight_date=params.flight_date,
        pilot_name=params.pilot_name,
        area_covered_ha=params.area_covered_ha,
        altitude_m=params.altitude_m,
    )

    return ApiResponse(data=DroneFlightResponse(
        id=flight.id,
        flight_code=flight.flight_code,
        drone_id=flight.drone_id,
        crop_type=flight.crop_type.value,
        flight_date=flight.flight_date,
        pilot_name=flight.pilot_name,
        area_covered_ha=flight.area_covered_ha,
        altitude_m=flight.altitude_m,
        processed=flight.processed,
        created_at=flight.created_at,
    ))


@router.get(
    "/flights",
    response_model=ApiResponse[List[DroneFlightResponse]],
    summary="获取飞行记录列表",
)
async def get_flights(
    crop_type: Annotated[Optional[CropType], Query(description="作物类型过滤")] = None,
    start_date: Annotated[Optional[datetime], Query(description="开始日期")] = None,
    end_date: Annotated[Optional[datetime], Query(description="结束日期")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[List[DroneFlightResponse]]:
    """
    获取无人机飞行记录列表，支持筛选
    """
    service = DroneService(db)
    flights = await service.list_flights(
        crop_type=crop_type,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )

    return ApiResponse(data=[
        DroneFlightResponse(
            id=f.id,
            flight_code=f.flight_code,
            drone_id=f.drone_id,
            crop_type=f.crop_type.value,
            flight_date=f.flight_date,
            pilot_name=f.pilot_name,
            area_covered_ha=f.area_covered_ha,
            altitude_m=f.altitude_m,
            processed=f.processed,
            created_at=f.created_at,
        )
        for f in flights
    ])


@router.post(
    "/image",
    response_model=ApiResponse[dict],
    summary="添加影像信息",
)
async def add_image(
    params: DroneImageAdd,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[dict]:
    """
    关联影像到飞行记录
    """
    service = DroneService(db)
    image = await service.add_image(
        flight_id=params.flight_id,
        file_name=params.file_name,
        file_path=params.file_path,
        image_type=params.image_type,
        center_lon=params.center_lon,
        center_lat=params.center_lat,
        capture_time=params.capture_time,
    )

    return ApiResponse(data={
        "image_id": image.id,
        "flight_id": image.flight_id,
        "file_name": image.file_name,
        "processed": image.processed,
    })


@router.post(
    "/analyze-image",
    response_model=ApiResponse[ImageAnalysisResponse],
    summary="分析单张无人机影像",
)
async def analyze_drone_image(
    file: Annotated[UploadFile, File(description="多光谱影像文件")],
    crop_type: Annotated[CropType, Form(..., description="作物类型")],
    center_lat: Annotated[float, Form(..., description="中心纬度", ge=-90, le=90)],
    center_lon: Annotated[float, Form(..., description="中心经度", ge=-180, le=180)],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[ImageAnalysisResponse]:
    """
    分析单张无人机多光谱影像

    计算植被指数（NDVI、NDRE、GNDVI、PRI），检测病害，评估严重度
    """
    service = DroneService(db)

    result = await service.analyze_uploaded_image(
        file_content=await file.read(),
        filename=file.filename or "unknown.tif",
        crop_type=crop_type,
        center_lat=center_lat,
        center_lon=center_lon,
    )

    return ApiResponse(data=ImageAnalysisResponse(**result))


@router.post(
    "/detection",
    response_model=ApiResponse[DetectionResponse],
    summary="保存病害检测结果",
)
async def save_detection(
    params: DetectionSave,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[DetectionResponse]:
    """
    保存病害检测结果到数据库
    """
    service = DroneService(db)
    detection = await service.save_detection(
        flight_id=params.flight_id,
        image_id=params.image_id,
        crop_type=params.crop_type,
        disease_name=params.disease_name,
        detection_confidence=params.detection_confidence,
        severity=params.severity,
        lon=params.lon,
        lat=params.lat,
        ndvi_value=params.ndvi_value,
        ndre_value=params.ndre_value,
        gndvi_value=params.gndvi_value,
        pri_value=params.pri_value,
        fused_risk_boost=params.fused_risk_boost,
        area_affected_m2=params.area_affected_m2,
        notes=params.notes,
    )

    return ApiResponse(data=DetectionResponse(
        id=detection.id,
        flight_id=detection.flight_id,
        image_id=detection.image_id,
        grid_id=detection.grid_id,
        crop_type=detection.crop_type.value,
        disease_name=detection.disease_name,
        detection_confidence=detection.detection_confidence,
        severity=detection.severity,
        area_affected_m2=detection.area_affected_m2,
        lon=detection.location_coords[0],
        lat=detection.location_coords[1],
        ndvi=detection.ndvi_value,
        ndre=detection.ndre_value,
        gndvi=detection.gndvi_value,
        pri=detection.pri_value,
        risk_boost=detection.fused_risk_boost,
        verified=detection.verified,
        notes=detection.notes,
        detection_time=detection.detection_time.isoformat() if detection.detection_time else None,
    ))


@router.post(
    "/process-flight/{flight_id}",
    response_model=ApiResponse[FlightProcessResponse],
    summary="处理整个飞行的影像",
)
async def process_flight(
    flight_id: int,
    crop_type: Annotated[Optional[CropType], Query(description="作物类型（覆盖飞行记录中的类型）")] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[FlightProcessResponse]:
    """
    批量处理一个飞行任务的所有影像

    执行病害检测、数据融合、更新风险预测
    """
    service = DroneService(db)
    result = await service.process_flight(
        flight_id=flight_id,
        crop_type=crop_type,
    )

    return ApiResponse(data=FlightProcessResponse(**result))


@router.get(
    "/detection-heatmap",
    response_model=ApiResponse[DetectionHeatmapResponse],
    summary="获取病害检测热图",
)
async def get_detection_heatmap(
    crop_type: Annotated[CropType, Query(..., description="作物类型")],
    flight_id: Annotated[Optional[int], Query(description="飞行记录ID过滤")] = None,
    start_date: Annotated[Optional[datetime], Query(description="开始日期")] = None,
    end_date: Annotated[Optional[datetime], Query(description="结束日期")] = None,
    min_severity: Annotated[float, Query(description="最小严重度过滤", ge=0, le=100)] = 0,
    lon_min: Annotated[Optional[float], Query(description="最小经度", ge=-180, le=180)] = None,
    lat_min: Annotated[Optional[float], Query(description="最小纬度", ge=-90, le=90)] = None,
    lon_max: Annotated[Optional[float], Query(description="最大经度", ge=-180, le=180)] = None,
    lat_max: Annotated[Optional[float], Query(description="最大纬度", ge=-90, le=90)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[DetectionHeatmapResponse]:
    """
    获取病害检测热图（GeoJSON格式）

    用于在地图上展示无人机检测到的病害分布
    """
    bounds = None
    if lon_min is not None and lat_min is not None and lon_max is not None and lat_max is not None:
        bounds = (lon_min, lat_min, lon_max, lat_max)

    service = DroneService(db)
    result = await service.get_detection_heatmap(
        crop_type=crop_type,
        flight_id=flight_id,
        start_date=start_date,
        end_date=end_date,
        min_severity=min_severity,
        bounds=bounds,
    )

    return ApiResponse(data=DetectionHeatmapResponse(**result))


@router.get(
    "/detections",
    response_model=ApiResponse[List[DetectionResponse]],
    summary="获取病害检测列表",
)
async def list_detections(
    flight_id: Annotated[Optional[int], Query(description="飞行记录ID过滤")] = None,
    crop_type: Annotated[Optional[CropType], Query(description="作物类型过滤")] = None,
    disease_name: Annotated[Optional[str], Query(description="病害名称过滤")] = None,
    verified: Annotated[Optional[bool], Query(description="是否已验证")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)] = None,
) -> ApiResponse[List[DetectionResponse]]:
    """
    获取病害检测记录列表
    """
    service = DroneService(db)
    detections = await service.list_detections(
        flight_id=flight_id,
        crop_type=crop_type,
        disease_name=disease_name,
        verified=verified,
        skip=skip,
        limit=limit,
    )

    return ApiResponse(data=[
        DetectionResponse(
            id=d.id,
            flight_id=d.flight_id,
            image_id=d.image_id,
            grid_id=d.grid_id,
            crop_type=d.crop_type.value,
            disease_name=d.disease_name,
            detection_confidence=d.detection_confidence,
            severity=d.severity,
            area_affected_m2=d.area_affected_m2,
            lon=d.location_coords[0],
            lat=d.location_coords[1],
            ndvi=d.ndvi_value,
            ndre=d.ndre_value,
            gndvi=d.gndvi_value,
            pri=d.pri_value,
            risk_boost=d.fused_risk_boost,
            verified=d.verified,
            notes=d.notes,
            detection_time=d.detection_time.isoformat() if d.detection_time else None,
        )
        for d in detections
    ])
