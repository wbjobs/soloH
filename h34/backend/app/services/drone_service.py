from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import io
import os
import uuid
import numpy as np

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape

from app.db.models import (
    CropType,
    GridCell,
    DroneFlight,
    DroneImage,
    DroneDiseaseDetection,
    RiskGrid,
)
from app.services.grid_service import GridService
from app.services.risk_engine import RiskEngine


class DroneService:
    """无人机多光谱影像病害检测与数据融合服务

    核心功能:
    - 多光谱影像植被指数计算 (NDVI, NDRE, GNDVI, PRI)
    - 病害症状检测与严重度评估
    - 检测结果与气象模型风险的数据融合
    - 空间关联网格单元，更新风险估计

    多光谱波段说明:
    - Blue (450-520nm): 叶绿素吸收、土壤背景
    - Green (520-600nm): 植被健康、黄化检测
    - Red (630-680nm): 叶绿素强吸收、胁迫检测
    - RedEdge (700-740nm): 植被胁迫早期检测
    - NIR (770-900nm): 生物量、叶面积指数

    参考文献:
    - Mulla, D. J. (2013). Twenty five years of remote sensing in precision agriculture:
      Key advances and remaining knowledge gaps. Biosystems engineering, 114(4), 358-371.
    - Mahlein, A. K., et al. (2018). Recent advances in sensing plant diseases
      for precision crop protection. European Journal of Plant Pathology, 152(3), 513-529.
    """

    VEGETATION_INDICES = {
        "NDVI": {
            "name": "归一化差异植被指数",
            "formula": "(NIR - Red) / (NIR + Red)",
            "range": [-1, 1],
            "healthy_threshold": 0.7,
            "stress_threshold": 0.4,
        },
        "NDRE": {
            "name": "归一化差异红边指数",
            "formula": "(NIR - RedEdge) / (NIR + RedEdge)",
            "range": [-1, 1],
            "healthy_threshold": 0.5,
            "stress_threshold": 0.25,
        },
        "GNDVI": {
            "name": "绿色归一化差异植被指数",
            "formula": "(NIR - Green) / (NIR + Green)",
            "range": [-1, 1],
            "healthy_threshold": 0.6,
            "stress_threshold": 0.35,
        },
        "PRI": {
            "name": "光化学反射指数",
            "formula": "(Green - Blue) / (Green + Blue)",
            "range": [-1, 1],
            "healthy_threshold": 0.05,
            "stress_threshold": -0.05,
        },
    }

    DISEASE_SPECTRAL_SIGNATURES = {
        "wheat_rust": {
            "name": "小麦锈病",
            "ndvi_drop": 0.25,
            "ndre_drop": 0.2,
            "gndvi_drop": 0.18,
            "red_increase": 0.15,
            "severity_factor": 1.0,
        },
        "potato_blight": {
            "name": "马铃薯晚疫病",
            "ndvi_drop": 0.3,
            "ndre_drop": 0.25,
            "gndvi_drop": 0.22,
            "red_increase": 0.2,
            "severity_factor": 1.2,
        },
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.grid_service = GridService(db)
        self.risk_engine = RiskEngine(db)
        self.upload_dir = "drone_uploads"
        os.makedirs(self.upload_dir, exist_ok=True)

    @staticmethod
    def calculate_vegetation_indices(
        band_data: Dict[str, np.ndarray]
    ) -> Dict[str, float]:
        """计算植被指数

        Args:
            band_data: 波段数据字典，键为波段名，值为反射率数组

        Returns:
            Dict: 各植被指数的平均值
        """
        indices = {}

        def safe_divide(a, b):
            with np.errstate(divide='ignore', invalid='ignore'):
                result = np.where(
                    (np.abs(b) < 1e-6) | np.isnan(a) | np.isnan(b),
                    np.nan,
                    a / b
                )
            return result

        if "NIR" in band_data and "Red" in band_data:
            nir = band_data["NIR"].astype(np.float64)
            red = band_data["Red"].astype(np.float64)
            ndvi = safe_divide(nir - red, nir + red)
            indices["NDVI"] = float(np.nanmean(ndvi))

        if "NIR" in band_data and "RedEdge" in band_data:
            nir = band_data["NIR"].astype(np.float64)
            rededge = band_data["RedEdge"].astype(np.float64)
            ndre = safe_divide(nir - rededge, nir + rededge)
            indices["NDRE"] = float(np.nanmean(ndre))

        if "NIR" in band_data and "Green" in band_data:
            nir = band_data["NIR"].astype(np.float64)
            green = band_data["Green"].astype(np.float64)
            gndvi = safe_divide(nir - green, nir + green)
            indices["GNDVI"] = float(np.nanmean(gndvi))

        if "Green" in band_data and "Blue" in band_data:
            green = band_data["Green"].astype(np.float64)
            blue = band_data["Blue"].astype(np.float64)
            pri = safe_divide(green - blue, green + blue)
            indices["PRI"] = float(np.nanmean(pri))

        return indices

    def detect_disease_from_indices(
        self,
        indices: Dict[str, float],
        crop_type: CropType,
        baseline_indices: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, str, float, float]:
        """基于植被指数检测病害

        Args:
            indices: 当前植被指数
            crop_type: 作物类型
            baseline_indices: 健康植被基线指数（可选）

        Returns:
            Tuple: (是否检测到病害, 病害名称, 置信度, 严重度)
        """
        crop_str = crop_type.value if isinstance(crop_type, CropType) else crop_type

        if crop_str == "wheat":
            signature = self.DISEASE_SPECTRAL_SIGNATURES["wheat_rust"]
            disease_name = "小麦锈病"
        elif crop_str == "potato":
            signature = self.DISEASE_SPECTRAL_SIGNATURES["potato_blight"]
            disease_name = "马铃薯晚疫病"
        else:
            signature = self.DISEASE_SPECTRAL_SIGNATURES["wheat_rust"]
            disease_name = "未知病害"

        if baseline_indices is None:
            baseline_indices = {
                "NDVI": self.VEGETATION_INDICES["NDVI"]["healthy_threshold"],
                "NDRE": self.VEGETATION_INDICES["NDRE"]["healthy_threshold"],
                "GNDVI": self.VEGETATION_INDICES["GNDVI"]["healthy_threshold"],
                "PRI": self.VEGETATION_INDICES["PRI"]["healthy_threshold"],
            }

        stress_scores = []
        for idx_name, idx_value in indices.items():
            if idx_name in baseline_indices and idx_name in self.VEGETATION_INDICES:
                baseline = baseline_indices[idx_name]
                drop = max(0, baseline - idx_value)
                threshold = self.VEGETATION_INDICES[idx_name]["healthy_threshold"] - \
                           self.VEGETATION_INDICES[idx_name]["stress_threshold"]
                if threshold > 0:
                    normalized_stress = min(1.0, drop / threshold)
                    stress_scores.append(normalized_stress)

        if not stress_scores:
            return False, disease_name, 0.0, 0.0

        avg_stress = np.mean(stress_scores)
        max_stress = np.max(stress_scores)

        confidence = min(1.0, (avg_stress * 0.6 + max_stress * 0.4) * 1.2)
        severity = min(100.0, avg_stress * 100 * signature["severity_factor"])

        detected = confidence > 0.3

        return detected, disease_name, float(confidence), float(severity)

    def generate_mock_band_data(
        self,
        width: int = 100,
        height: int = 100,
        disease_present: bool = False,
        disease_severity: float = 0.5,
    ) -> Dict[str, np.ndarray]:
        """生成模拟的多光谱波段数据（用于演示和测试）

        Args:
            width: 图像宽度
            height: 图像高度
            disease_present: 是否包含病害症状
            disease_severity: 病害严重度 (0-1)

        Returns:
            Dict: 各波段的反射率数组
        """
        np.random.seed(42)

        base_reflectance = {
            "Blue": np.random.normal(0.05, 0.01, (height, width)),
            "Green": np.random.normal(0.15, 0.02, (height, width)),
            "Red": np.random.normal(0.10, 0.02, (height, width)),
            "RedEdge": np.random.normal(0.25, 0.03, (height, width)),
            "NIR": np.random.normal(0.45, 0.05, (height, width)),
        }

        if disease_present:
            center_y, center_x = height // 2, width // 2
            y, x = np.ogrid[:height, :width]
            dist_from_center = np.sqrt((x - center_x)**2 + (y - center_y)**2)
            max_dist = np.sqrt(center_x**2 + center_y**2)
            disease_mask = np.exp(-(dist_from_center / (max_dist * 0.3))**2)
            disease_mask = disease_mask * disease_severity

            base_reflectance["Red"] += disease_mask * 0.15
            base_reflectance["Green"] += disease_mask * 0.08
            base_reflectance["RedEdge"] -= disease_mask * 0.10
            base_reflectance["NIR"] -= disease_mask * 0.20

        for band in base_reflectance:
            base_reflectance[band] = np.clip(base_reflectance[band], 0, 1)

        return base_reflectance

    def analyze_image(
        self,
        image_data: Optional[bytes] = None,
        crop_type: CropType = CropType.WHEAT,
        lat: float = 0.0,
        lon: float = 0.0,
        use_mock: bool = True,
        disease_severity: float = 0.5,
    ) -> Dict[str, Any]:
        """分析无人机多光谱影像，检测病害

        Args:
            image_data: 图像二进制数据（可选，None时使用模拟数据）
            crop_type: 作物类型
            lat: 影像中心纬度
            lon: 影像中心经度
            use_mock: 是否使用模拟数据
            disease_severity: 模拟病害严重度

        Returns:
            Dict: 分析结果
                - indices: 各植被指数值
                - disease_detected: 是否检测到病害
                - disease_name: 病害名称
                - detection_confidence: 检测置信度
                - severity: 病害严重度
                - risk_boost_factor: 风险提升因子
                - pixel_count: 总像素数
                - affected_pixels: 受影响像素数
        """
        if use_mock or image_data is None:
            band_data = self.generate_mock_band_data(
                disease_present=True,
                disease_severity=disease_severity,
            )
            detected = True
        else:
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(image_data))
                img_array = np.array(img).astype(np.float64) / 255.0

                if len(img_array.shape) == 3:
                    band_data = {
                        "Blue": img_array[:, :, 0],
                        "Green": img_array[:, :, 1],
                        "Red": img_array[:, :, 2],
                    }
                    if img_array.shape[2] >= 4:
                        band_data["NIR"] = img_array[:, :, 3]
                    if img_array.shape[2] >= 5:
                        band_data["RedEdge"] = img_array[:, :, 4]
                else:
                    band_data = {
                        "Gray": img_array,
                    }
            except Exception as e:
                return {
                    "error": f"图像解析失败: {str(e)}",
                    "indices": {},
                    "disease_detected": False,
                    "disease_name": "",
                    "detection_confidence": 0.0,
                    "severity": 0.0,
                }

            detected = True

        indices = self.calculate_vegetation_indices(band_data)

        if detected:
            disease_detected, disease_name, confidence, severity = \
                self.detect_disease_from_indices(indices, crop_type)
        else:
            disease_detected = False
            disease_name = ""
            confidence = 0.0
            severity = 0.0

        if severity > 0:
            if severity > 60:
                risk_boost = 2.5
            elif severity > 30:
                risk_boost = 1.8
            elif severity > 10:
                risk_boost = 1.3
            else:
                risk_boost = 1.0
        else:
            risk_boost = 1.0

        total_pixels = band_data.get("Red", np.array([])).size
        affected_pixels = int(total_pixels * severity / 100) if severity > 0 else 0

        return {
            "indices": indices,
            "indices_description": {
                k: v["name"] for k, v in self.VEGETATION_INDICES.items()
            },
            "disease_detected": disease_detected,
            "disease_name": disease_name,
            "detection_confidence": round(confidence, 4),
            "severity": round(severity, 2),
            "risk_boost_factor": risk_boost,
            "pixel_count": total_pixels,
            "affected_pixels": affected_pixels,
            "analysis_method": "spectral_index_based" if detected else "mock_demo",
            "center_lat": lat,
            "center_lon": lon,
        }

    async def create_flight(
        self,
        flight_code: str,
        drone_id: str,
        crop_type: CropType,
        flight_date: datetime,
        pilot_name: Optional[str] = None,
        area_covered_ha: Optional[float] = None,
        altitude_m: Optional[float] = None,
    ) -> DroneFlight:
        """创建无人机飞行记录

        Args:
            flight_code: 飞行编号（唯一）
            drone_id: 无人机ID
            crop_type: 作物类型
            flight_date: 飞行日期
            pilot_name: 飞行员姓名
            area_covered_ha: 覆盖面积（公顷）
            altitude_m: 飞行高度（米）

        Returns:
            DroneFlight: 创建后的飞行记录
        """
        flight = DroneFlight(
            flight_code=flight_code,
            drone_id=drone_id,
            pilot_name=pilot_name,
            crop_type=crop_type,
            flight_date=flight_date,
            area_covered_ha=area_covered_ha,
            altitude_m=altitude_m,
            bands="RGB,NIR,RedEdge",
        )
        self.db.add(flight)
        await self.db.commit()
        await self.db.refresh(flight)
        return flight

    async def add_image(
        self,
        flight_id: int,
        file_name: str,
        file_path: str,
        image_type: str,
        center_lon: float,
        center_lat: float,
        capture_time: Optional[datetime] = None,
    ) -> DroneImage:
        """添加无人机影像记录

        Args:
            flight_id: 飞行记录ID
            file_name: 文件名
            file_path: 文件路径
            image_type: 影像类型 (RGB, Multispectral, Thermal)
            center_lon: 中心经度
            center_lat: 中心纬度
            capture_time: 拍摄时间

        Returns:
            DroneImage: 创建后的影像记录
        """
        center_wkt = f"POINT({center_lon} {center_lat})"
        center_geom = WKTElement(center_wkt, srid=4326)

        delta = 0.001
        corners_wkt = (
            f"POLYGON(({center_lon - delta} {center_lat - delta}, "
            f"{center_lon + delta} {center_lat - delta}, "
            f"{center_lon + delta} {center_lat + delta}, "
            f"{center_lon - delta} {center_lat + delta}, "
            f"{center_lon - delta} {center_lat - delta}))"
        )
        corners_geom = WKTElement(corners_wkt, srid=4326)

        image = DroneImage(
            flight_id=flight_id,
            file_path=file_path,
            file_name=file_name,
            image_type=image_type,
            center_location=center_geom,
            corners=corners_geom,
            capture_time=capture_time or datetime.utcnow(),
            band_count=5,
        )
        self.db.add(image)
        await self.db.commit()
        await self.db.refresh(image)
        return image

    async def save_detection(
        self,
        flight_id: int,
        image_id: int,
        crop_type: CropType,
        disease_name: str,
        detection_confidence: float,
        severity: float,
        lon: float,
        lat: float,
        ndvi_value: Optional[float] = None,
        ndre_value: Optional[float] = None,
        gndvi_value: Optional[float] = None,
        pri_value: Optional[float] = None,
        fused_risk_boost: float = 1.0,
        area_affected_m2: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> DroneDiseaseDetection:
        """保存病害检测结果

        Args:
            flight_id: 飞行记录ID
            image_id: 影像ID
            crop_type: 作物类型
            disease_name: 病害名称
            detection_confidence: 检测置信度 (0-1)
            severity: 严重度 (0-100)
            lon: 检测点经度
            lat: 检测点纬度
            ndvi_value: NDVI值
            ndre_value: NDRE值
            gndvi_value: GNDVI值
            pri_value: PRI值
            fused_risk_boost: 风险提升因子
            area_affected_m2: 受影响面积（平方米）
            notes: 备注

        Returns:
            DroneDiseaseDetection: 保存后的检测记录
        """
        grid_cell = await self.grid_service.get_or_create_grid_cell(lon, lat)

        location_wkt = f"POINT({lon} {lat})"
        location_geom = WKTElement(location_wkt, srid=4326)

        detection = DroneDiseaseDetection(
            flight_id=flight_id,
            image_id=image_id,
            grid_id=grid_cell.id,
            crop_type=crop_type,
            disease_name=disease_name,
            detection_confidence=detection_confidence,
            severity=severity,
            location=location_geom,
            ndvi_value=ndvi_value,
            ndre_value=ndre_value,
            gndvi_value=gndvi_value,
            pri_value=pri_value,
            fused_risk_boost=fused_risk_boost,
            model_used="spectral_index_v1",
            area_affected_m2=area_affected_m2,
            notes=notes,
        )
        self.db.add(detection)

        if fused_risk_boost > 1.0:
            await self._fuse_with_risk_model(grid_cell.id, crop_type, severity, fused_risk_boost)

        await self.db.commit()
        await self.db.refresh(detection)
        return detection

    async def _fuse_with_risk_model(
        self,
        grid_id: int,
        crop_type: CropType,
        severity: float,
        risk_boost: float,
    ) -> None:
        """将无人机检测结果与气象模型风险融合

        融合策略:
        1. 查询该网格最近的风险计算结果
        2. 应用风险提升因子: fused_risk = min(100, original_risk * boost_factor)
        3. 更新风险网格记录，标记为数据融合结果

        Args:
            grid_id: 网格ID
            crop_type: 作物类型
            severity: 检测到的病害严重度
            risk_boost: 风险提升因子
        """
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(RiskGrid).where(
                and_(
                    RiskGrid.grid_id == grid_id,
                    RiskGrid.crop_type == crop_type,
                    func.date(RiskGrid.forecast_date) == func.date(today),
                )
            )
        )
        risk_grid = result.scalar_one_or_none()

        if risk_grid:
            original_risk = risk_grid.risk_index
            fused_risk = min(100.0, original_risk * risk_boost)
            risk_grid.risk_index = fused_risk
            risk_grid.model_version = f"{risk_grid.model_version}_drone_fused"
            risk_grid.calculated_at = datetime.utcnow()

            await self.db.commit()

    async def process_flight(
        self,
        flight_id: int,
        crop_type: Optional[CropType] = None,
    ) -> Dict[str, Any]:
        """处理整个飞行的影像，批量检测病害

        Args:
            flight_id: 飞行记录ID
            crop_type: 作物类型（可选，默认从飞行记录获取）

        Returns:
            Dict: 处理结果统计
        """
        flight_result = await self.db.execute(
            select(DroneFlight).where(DroneFlight.id == flight_id)
        )
        flight = flight_result.scalar_one_or_none()

        if not flight:
            return {"error": "飞行记录不存在"}

        if crop_type is None:
            crop_type = flight.crop_type

        images_result = await self.db.execute(
            select(DroneImage).where(
                and_(
                    DroneImage.flight_id == flight_id,
                    DroneImage.processed == False,
                )
            )
        )
        images = images_result.scalars().all()

        detections = []
        for image in images:
            center = to_shape(image.center_location)
            lon, lat = center.x, center.y

            analysis = self.analyze_image(
                crop_type=crop_type,
                lat=lat,
                lon=lon,
                use_mock=True,
                disease_severity=0.4 + np.random.random() * 0.4,
            )

            if analysis.get("disease_detected", False):
                detection = await self.save_detection(
                    flight_id=flight_id,
                    image_id=image.id,
                    crop_type=crop_type,
                    disease_name=analysis["disease_name"],
                    detection_confidence=analysis["detection_confidence"],
                    severity=analysis["severity"],
                    lon=lon,
                    lat=lat,
                    ndvi_value=analysis["indices"].get("NDVI"),
                    ndre_value=analysis["indices"].get("NDRE"),
                    gndvi_value=analysis["indices"].get("GNDVI"),
                    pri_value=analysis["indices"].get("PRI"),
                    fused_risk_boost=analysis["risk_boost_factor"],
                    area_affected_m2=analysis.get("affected_pixels", 0) * 0.01,
                )
                detections.append({
                    "detection_id": detection.id,
                    "image_id": image.id,
                    "disease": analysis["disease_name"],
                    "severity": analysis["severity"],
                    "confidence": analysis["detection_confidence"],
                    "risk_boost": analysis["risk_boost_factor"],
                })

            image.processed = True
            await self.db.commit()

        flight.processed = True
        await self.db.commit()

        return {
            "flight_id": flight_id,
            "flight_code": flight.flight_code,
            "processed_images": len(images),
            "detections_count": len(detections),
            "detections": detections,
            "average_severity": np.mean([d["severity"] for d in detections]) if detections else 0,
            "average_risk_boost": np.mean([d["risk_boost"] for d in detections]) if detections else 1.0,
        }

    async def get_detections_for_grid(
        self,
        grid_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """获取指定网格的无人机检测结果

        Args:
            grid_id: 网格ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            List[Dict]: 检测结果列表
        """
        query = select(DroneDiseaseDetection).where(
            DroneDiseaseDetection.grid_id == grid_id
        )

        if start_date:
            query = query.where(DroneDiseaseDetection.detection_time >= start_date)
        if end_date:
            query = query.where(DroneDiseaseDetection.detection_time <= end_date)

        query = query.order_by(DroneDiseaseDetection.detection_time.desc())

        result = await self.db.execute(query)
        detections = result.scalars().all()

        detection_list = []
        for det in detections:
            loc = to_shape(det.location)
            detection_list.append({
                "id": det.id,
                "flight_id": det.flight_id,
                "image_id": det.image_id,
                "grid_id": det.grid_id,
                "crop_type": det.crop_type.value if isinstance(det.crop_type, CropType) else det.crop_type,
                "disease_name": det.disease_name,
                "detection_confidence": det.detection_confidence,
                "severity": det.severity,
                "area_affected_m2": det.area_affected_m2,
                "lon": loc.x,
                "lat": loc.y,
                "ndvi": det.ndvi_value,
                "ndre": det.ndre_value,
                "gndvi": det.gndvi_value,
                "pri": det.pri_value,
                "risk_boost": det.fused_risk_boost,
                "verified": det.verified,
                "notes": det.notes,
                "detection_time": det.detection_time.isoformat() if det.detection_time else None,
            })

        return detection_list

    async def get_detection_heatmap(
        self,
        crop_type: CropType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """生成病害检测热图数据

        Args:
            crop_type: 作物类型
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Dict: GeoJSON格式的热图数据
        """
        query = select(DroneDiseaseDetection).where(
            DroneDiseaseDetection.crop_type == crop_type
        )

        if start_date:
            query = query.where(DroneDiseaseDetection.detection_time >= start_date)
        if end_date:
            query = query.where(DroneDiseaseDetection.detection_time <= end_date)

        result = await self.db.execute(query)
        detections = result.scalars().all()

        features = []
        for det in detections:
            loc = to_shape(det.location)

            if det.severity >= 60:
                color = "#ef4444"
            elif det.severity >= 30:
                color = "#f97316"
            elif det.severity >= 10:
                color = "#eab308"
            else:
                color = "#22c55e"

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [loc.x, loc.y],
                },
                "properties": {
                    "id": det.id,
                    "disease": det.disease_name,
                    "severity": det.severity,
                    "confidence": det.detection_confidence,
                    "risk_boost": det.fused_risk_boost,
                    "color": color,
                    "verified": det.verified,
                    "detection_time": det.detection_time.isoformat() if det.detection_time else None,
                },
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features,
            "crop_type": crop_type.value if isinstance(crop_type, CropType) else crop_type,
            "total_detections": len(detections),
            "average_severity": np.mean([d.severity for d in detections]) if detections else 0,
            "high_risk_count": sum(1 for d in detections if d.severity >= 60),
            "medium_risk_count": sum(1 for d in detections if 30 <= d.severity < 60),
            "low_risk_count": sum(1 for d in detections if d.severity < 30),
        }
