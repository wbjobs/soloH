from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.db.models import CropType


class DroneFlightCreate(BaseModel):
    flight_code: str = Field(..., description="飞行编号（唯一）", max_length=50)
    drone_id: str = Field(..., description="无人机ID", max_length=50)
    crop_type: CropType = Field(..., description="作物类型")
    flight_date: datetime = Field(..., description="飞行日期")
    pilot_name: Optional[str] = Field(None, description="飞行员姓名", max_length=100)
    area_covered_ha: Optional[float] = Field(None, description="覆盖面积（公顷）", ge=0)
    altitude_m: Optional[float] = Field(None, description="飞行高度（米）", ge=0)


class DroneFlightResponse(BaseModel):
    id: int = Field(..., description="飞行记录ID")
    flight_code: str = Field(..., description="飞行编号")
    drone_id: str = Field(..., description="无人机ID")
    crop_type: str = Field(..., description="作物类型")
    flight_date: datetime = Field(..., description="飞行日期")
    pilot_name: Optional[str] = Field(None, description="飞行员姓名")
    area_covered_ha: Optional[float] = Field(None, description="覆盖面积（公顷）")
    altitude_m: Optional[float] = Field(None, description="飞行高度（米）")
    processed: bool = Field(..., description="是否已处理")
    created_at: datetime = Field(..., description="创建时间")


class DroneImageAdd(BaseModel):
    flight_id: int = Field(..., description="飞行记录ID")
    file_name: str = Field(..., description="文件名", max_length=255)
    file_path: str = Field(..., description="文件路径", max_length=500)
    image_type: str = Field(..., description="影像类型: RGB, Multispectral, Thermal", max_length=50)
    center_lon: float = Field(..., description="中心经度", ge=-180, le=180)
    center_lat: float = Field(..., description="中心纬度", ge=-90, le=90)
    capture_time: Optional[datetime] = Field(None, description="拍摄时间")


class VegetationIndices(BaseModel):
    NDVI: Optional[float] = Field(None, description="归一化差异植被指数")
    NDRE: Optional[float] = Field(None, description="归一化差异红边指数")
    GNDVI: Optional[float] = Field(None, description="绿色归一化差异植被指数")
    PRI: Optional[float] = Field(None, description="光化学反射指数")


class ImageAnalysisResponse(BaseModel):
    indices: VegetationIndices = Field(..., description="植被指数")
    indices_description: Dict[str, str] = Field(..., description="各指数说明")
    disease_detected: bool = Field(..., description="是否检测到病害")
    disease_name: str = Field(..., description="病害名称")
    detection_confidence: float = Field(..., description="检测置信度", ge=0, le=1)
    severity: float = Field(..., description="病害严重度", ge=0, le=100)
    risk_boost_factor: float = Field(..., description="风险提升因子")
    pixel_count: int = Field(..., description="总像素数")
    affected_pixels: int = Field(..., description="受影响像素数")
    analysis_method: str = Field(..., description="分析方法")
    center_lat: float = Field(..., description="中心纬度")
    center_lon: float = Field(..., description="中心经度")


class DetectionSave(BaseModel):
    flight_id: int = Field(..., description="飞行记录ID")
    image_id: int = Field(..., description="影像ID")
    crop_type: CropType = Field(..., description="作物类型")
    disease_name: str = Field(..., description="病害名称", max_length=100)
    detection_confidence: float = Field(..., description="检测置信度", ge=0, le=1)
    severity: float = Field(..., description="病害严重度", ge=0, le=100)
    lon: float = Field(..., description="检测点经度", ge=-180, le=180)
    lat: float = Field(..., description="检测点纬度", ge=-90, le=90)
    ndvi_value: Optional[float] = Field(None, description="NDVI值")
    ndre_value: Optional[float] = Field(None, description="NDRE值")
    gndvi_value: Optional[float] = Field(None, description="GNDVI值")
    pri_value: Optional[float] = Field(None, description="PRI值")
    fused_risk_boost: float = Field(1.0, description="风险提升因子", ge=1.0)
    area_affected_m2: Optional[float] = Field(None, description="受影响面积（平方米）", ge=0)
    notes: Optional[str] = Field(None, description="备注")


class DetectionResponse(BaseModel):
    id: int = Field(..., description="检测记录ID")
    flight_id: int = Field(..., description="飞行记录ID")
    image_id: Optional[int] = Field(None, description="影像ID")
    grid_id: Optional[int] = Field(None, description="网格ID")
    crop_type: str = Field(..., description="作物类型")
    disease_name: str = Field(..., description="病害名称")
    detection_confidence: float = Field(..., description="检测置信度")
    severity: float = Field(..., description="病害严重度")
    area_affected_m2: Optional[float] = Field(None, description="受影响面积（平方米）")
    lon: float = Field(..., description="经度")
    lat: float = Field(..., description="纬度")
    ndvi: Optional[float] = Field(None, description="NDVI值")
    ndre: Optional[float] = Field(None, description="NDRE值")
    gndvi: Optional[float] = Field(None, description="GNDVI值")
    pri: Optional[float] = Field(None, description="PRI值")
    risk_boost: float = Field(..., description="风险提升因子")
    verified: bool = Field(..., description="是否已验证")
    notes: Optional[str] = Field(None, description="备注")
    detection_time: Optional[str] = Field(None, description="检测时间")


class FlightProcessResponse(BaseModel):
    flight_id: int = Field(..., description="飞行记录ID")
    flight_code: str = Field(..., description="飞行编号")
    processed_images: int = Field(..., description="处理的影像数")
    detections_count: int = Field(..., description="检测到的病害数")
    detections: List[Dict[str, Any]] = Field(..., description="检测详情列表")
    average_severity: float = Field(..., description="平均严重度")
    average_risk_boost: float = Field(..., description="平均风险提升因子")


class HeatmapFeatureProperties(BaseModel):
    id: int = Field(..., description="检测ID")
    disease: str = Field(..., description="病害名称")
    severity: float = Field(..., description="严重度")
    confidence: float = Field(..., description="置信度")
    risk_boost: float = Field(..., description="风险提升")
    color: str = Field(..., description="颜色")
    verified: bool = Field(..., description="是否已验证")
    detection_time: Optional[str] = Field(None, description="检测时间")


class DetectionHeatmapResponse(BaseModel):
    type: str = Field(default="FeatureCollection", description="GeoJSON类型")
    features: List[Dict[str, Any]] = Field(..., description="要素列表")
    crop_type: str = Field(..., description="作物类型")
    total_detections: int = Field(..., description="总检测数")
    average_severity: float = Field(..., description="平均严重度")
    high_risk_count: int = Field(..., description="高风险检测数")
    medium_risk_count: int = Field(..., description="中风险检测数")
    low_risk_count: int = Field(..., description="低风险检测数")
