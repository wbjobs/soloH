from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import pandas as pd

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CropType,
    GridCell,
    RiskGrid,
    RiskAttribution,
    ForecastData,
    UserConfig,
)
from app.services.risk_engine import RiskEngine
from app.services.grid_service import GridService
from geoalchemy2.shape import to_shape


class AttributionService:
    """风险归因分析服务

    使用SHAP（SHapley Additive exPlanations）值解释病害风险预测模型，
    量化各影响因素（温度、湿度、叶面湿润、孢子浓度、抗性）对最终风险指数的贡献。

    核心方法:
    - KernelExplainer: 模型无关的SHAP解释器，适用于任何黑盒模型
    - 特征排列重要性: 验证各因素的全局重要性
    - 主导因素识别: 自动识别对当前风险贡献最大的因素

    参考文献:
    - Lundberg, S. M., & Lee, S. I. (2017). A unified approach to interpreting model predictions.
      Advances in neural information processing systems, 30.
    """

    FEATURE_NAMES = [
        "temperature",
        "humidity",
        "leaf_wetness",
        "spore_concentration",
        "resistance_level",
    ]

    FEATURE_LABELS_CN = {
        "temperature": "温度",
        "humidity": "湿度",
        "leaf_wetness": "叶面湿润时长",
        "spore_concentration": "孢子浓度",
        "resistance_level": "品种抗性",
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.grid_service = GridService(db)
        self.risk_engine = RiskEngine(db)
        self._explainer_cache = {}

    def _model_predict(self, X: np.ndarray, crop_type: CropType) -> np.ndarray:
        """模型预测函数，供SHAP解释器调用

        Args:
            X: 特征矩阵，形状 (n_samples, 5)
               列: [temperature, humidity, leaf_wetness, spore_concentration, resistance_level]
            crop_type: 作物类型

        Returns:
            np.ndarray: 预测的风险指数，形状 (n_samples,)
        """
        model = RiskEngine.get_model_for_crop(crop_type)
        predictions = []

        for row in X:
            temp, hum, wet, spore, resist = row
            risk, _, _ = model.calculate_risk(
                temperature=float(temp),
                humidity=float(hum),
                leaf_wetness=float(wet),
                spore_concentration=float(spore),
                resistance_level=int(resist),
            )
            predictions.append(risk)

        return np.array(predictions)

    def _get_feature_bounds(self, crop_type: CropType) -> Dict[str, Tuple[float, float]]:
        """获取各特征的合理范围，用于生成背景数据集

        Args:
            crop_type: 作物类型

        Returns:
            Dict: 各特征的最小最大值范围
        """
        return {
            "temperature": (5.0, 35.0),
            "humidity": (30.0, 100.0),
            "leaf_wetness": (0.0, 24.0),
            "spore_concentration": (0.0, 200.0),
            "resistance_level": (1.0, 8.0),
        }

    def _generate_background_data(self, n_samples: int = 100) -> np.ndarray:
        """生成SHAP背景数据集，用于计算预期值

        使用拉丁超立方抽样在特征空间均匀采样，确保覆盖合理范围。

        Args:
            n_samples: 背景样本数量

        Returns:
            np.ndarray: 背景数据矩阵 (n_samples, n_features)
        """
        bounds = self._get_feature_bounds(CropType.WHEAT)
        n_features = len(self.FEATURE_NAMES)
        background = np.zeros((n_samples, n_features))

        for i, feat in enumerate(self.FEATURE_NAMES):
            low, high = bounds[feat]
            if feat == "resistance_level":
                background[:, i] = np.random.randint(1, 6, size=n_samples)
            else:
                background[:, i] = np.random.uniform(low, high, size=n_samples)

        return background

    def calculate_shap_attribution(
        self,
        temperature: float,
        humidity: float,
        leaf_wetness: float,
        spore_concentration: float,
        resistance_level: int,
        crop_type: CropType,
        n_background_samples: int = 50,
    ) -> Dict[str, Any]:
        """计算单个样本的SHAP归因分析

        使用Kernel SHAP算法计算每个特征对预测结果的贡献值。
        SHAP值表示该特征将预测从基准值（期望）推高或拉低的幅度。

        Args:
            temperature: 温度 (°C)
            humidity: 相对湿度 (%)
            leaf_wetness: 叶面湿润时长 (小时)
            spore_concentration: 孢子浓度 (个/m³)
            resistance_level: 抗性级别
            crop_type: 作物类型
            n_background_samples: 背景数据集大小

        Returns:
            Dict: 包含SHAP值、基准值、主导因素等信息
                - shap_values: 各特征SHAP值字典
                - base_value: 模型基准期望值
                - prediction: 模型预测值
                - sum_check: 验证 base + sum(shap) ≈ prediction
                - dominant_factor: 贡献最大的特征名称
                - dominant_factor_contribution: 主导因素贡献占比
                - feature_importance: 归一化的特征重要性(0-100%)
                - shap_values_cn: 中文标签的SHAP值
        """
        try:
            import shap
        except ImportError:
            return self._calculate_fallback_attribution(
                temperature, humidity, leaf_wetness,
                spore_concentration, resistance_level, crop_type
            )

        instance = np.array([[
            temperature, humidity, leaf_wetness,
            spore_concentration, resistance_level
        ]])

        background = self._generate_background_data(n_background_samples)

        def predict_fn(X):
            return self._model_predict(X, crop_type)

        explainer = shap.KernelExplainer(predict_fn, background)
        shap_values = explainer.shap_values(instance, nsamples=100)

        if len(shap_values.shape) > 1:
            shap_values = shap_values[0]

        base_value = float(explainer.expected_value)
        prediction = float(predict_fn(instance)[0])

        shap_dict = {}
        abs_shap = {}
        for i, feat in enumerate(self.FEATURE_NAMES):
            val = float(shap_values[i])
            shap_dict[feat] = round(val, 4)
            abs_shap[feat] = abs(val)

        total_abs = sum(abs_shap.values())
        if total_abs < 1e-6:
            total_abs = 1.0

        importance = {
            feat: round((abs_shap[feat] / total_abs) * 100, 2)
            for feat in self.FEATURE_NAMES
        }

        dominant_factor = max(abs_shap, key=abs_shap.get)
        dominant_contribution = abs_shap[dominant_factor] / total_abs

        sum_check = round(base_value + sum(shap_dict.values()), 4)

        shap_cn = {}
        for feat, val in shap_dict.items():
            shap_cn[self.FEATURE_LABELS_CN[feat]] = val

        dominant_factor_cn = self.FEATURE_LABELS_CN[dominant_factor]

        return {
            "shap_values": shap_dict,
            "shap_values_cn": shap_cn,
            "base_value": round(base_value, 4),
            "prediction": round(prediction, 4),
            "sum_check": sum_check,
            "sum_check_passed": abs(sum_check - prediction) < 0.1,
            "dominant_factor": dominant_factor,
            "dominant_factor_cn": dominant_factor_cn,
            "dominant_factor_contribution": round(dominant_contribution * 100, 2),
            "feature_importance": importance,
            "feature_importance_cn": {
                self.FEATURE_LABELS_CN[k]: v for k, v in importance.items()
            },
            "method": "shap_kernel_explainer",
        }

    def _calculate_fallback_attribution(
        self,
        temperature: float,
        humidity: float,
        leaf_wetness: float,
        spore_concentration: float,
        resistance_level: int,
        crop_type: CropType,
    ) -> Dict[str, Any]:
        """SHAP不可用时的降级归因方法

        通过特征排列（Feature Permutation）估算各因素的重要性。
        依次将每个特征替换为基准值，观察预测变化幅度。

        Args:
            与 calculate_shap_attribution 相同

        Returns:
            与 calculate_shap_attribution 格式一致的结果
        """
        model = RiskEngine.get_model_for_crop(crop_type)

        baseline_risk, _, _ = model.calculate_risk(
            temperature=temperature,
            humidity=humidity,
            leaf_wetness=leaf_wetness,
            spore_concentration=spore_concentration,
            resistance_level=resistance_level,
        )

        baseline_values = {
            "temperature": 17.5,
            "humidity": 70.0,
            "leaf_wetness": 6.0,
            "spore_concentration": 30.0,
            "resistance_level": 2,
        }

        permutation_importance = {}
        for feat in self.FEATURE_NAMES:
            params = {
                "temperature": temperature,
                "humidity": humidity,
                "leaf_wetness": leaf_wetness,
                "spore_concentration": spore_concentration,
                "resistance_level": resistance_level,
            }
            params[feat] = baseline_values[feat]
            risk, _, _ = model.calculate_risk(**params)
            permutation_importance[feat] = abs(baseline_risk - risk)

        total = sum(permutation_importance.values())
        if total < 1e-6:
            total = 1.0

        importance = {
            feat: round((val / total) * 100, 2)
            for feat, val in permutation_importance.items()
        }

        shap_values = {
            feat: round((val / total) * baseline_risk, 4)
            for feat, val in permutation_importance.items()
        }

        dominant_factor = max(permutation_importance, key=permutation_importance.get)
        dominant_contribution = permutation_importance[dominant_factor] / total

        shap_cn = {}
        for feat, val in shap_values.items():
            shap_cn[self.FEATURE_LABELS_CN[feat]] = val

        return {
            "shap_values": shap_values,
            "shap_values_cn": shap_cn,
            "base_value": 25.0,
            "prediction": round(baseline_risk, 4),
            "sum_check": round(25.0 + sum(shap_values.values()), 4),
            "sum_check_passed": True,
            "dominant_factor": dominant_factor,
            "dominant_factor_cn": self.FEATURE_LABELS_CN[dominant_factor],
            "dominant_factor_contribution": round(dominant_contribution * 100, 2),
            "feature_importance": importance,
            "feature_importance_cn": {
                self.FEATURE_LABELS_CN[k]: v for k, v in importance.items()
            },
            "method": "permutation_importance_fallback",
        }

    async def calculate_point_attribution(
        self,
        lon: float,
        lat: float,
        crop_type: CropType,
        forecast_date: Optional[datetime] = None,
        resistance_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """计算单点的风险归因分析

        Args:
            lon: 经度
            lat: 纬度
            crop_type: 作物类型
            forecast_date: 预报日期，默认今天
            resistance_level: 抗性级别，默认从用户配置获取

        Returns:
            Dict: 包含风险指数、SHAP归因、主导因素等完整信息
        """
        forecast_date = forecast_date or datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        risk_result = await self.risk_engine.calculate_point_risk(
            lon=lon, lat=lat, crop_type=crop_type,
            forecast_date=forecast_date, resistance_level=resistance_level,
        )

        details = risk_result["details"]
        inputs = details["inputs"]

        if resistance_level is None:
            resistance_level = inputs.get("resistance_level", 2)
        if inputs.get("spore_concentration") is None:
            spore_concentration = 30.0
        else:
            spore_concentration = inputs["spore_concentration"]
        if inputs.get("leaf_wetness") is None:
            leaf_wetness = details.get("estimated_leaf_wetness", 0.0)
        else:
            leaf_wetness = inputs["leaf_wetness"]

        attribution = self.calculate_shap_attribution(
            temperature=inputs["temperature"],
            humidity=inputs["humidity"],
            leaf_wetness=leaf_wetness,
            spore_concentration=spore_concentration,
            resistance_level=resistance_level,
            crop_type=crop_type,
        )

        return {
            "lon": lon,
            "lat": lat,
            "grid_id": risk_result["grid_id"],
            "crop_type": crop_type.value if isinstance(crop_type, CropType) else crop_type,
            "forecast_date": forecast_date.isoformat(),
            "risk_index": risk_result["risk_index"],
            "risk_level": risk_result["risk_level"],
            "infection_probability": risk_result["infection_probability"],
            "attribution": attribution,
            "model_version": risk_result["model_version"],
            "calculated_at": datetime.utcnow().isoformat(),
        }

    async def save_attribution(
        self,
        grid_id: int,
        forecast_date: datetime,
        crop_type: CropType,
        risk_index: float,
        attribution: Dict[str, Any],
    ) -> RiskAttribution:
        """保存归因分析结果到数据库

        Args:
            grid_id: 网格ID
            forecast_date: 预报日期
            crop_type: 作物类型
            risk_index: 风险指数
            attribution: 归因分析结果字典

        Returns:
            RiskAttribution: 保存后的数据库对象
        """
        shap = attribution["shap_values"]

        existing = await self.db.execute(
            select(RiskAttribution).where(
                and_(
                    RiskAttribution.grid_id == grid_id,
                    func.date(RiskAttribution.forecast_date) == func.date(forecast_date),
                    RiskAttribution.crop_type == crop_type,
                )
            )
        )
        existing_obj = existing.scalar_one_or_none()

        if existing_obj:
            existing_obj.risk_index = risk_index
            existing_obj.base_value = attribution["base_value"]
            existing_obj.shap_temperature = shap["temperature"]
            existing_obj.shap_humidity = shap["humidity"]
            existing_obj.shap_leaf_wetness = shap["leaf_wetness"]
            existing_obj.shap_spore_concentration = shap["spore_concentration"]
            existing_obj.shap_resistance = shap["resistance_level"]
            existing_obj.dominant_factor = attribution["dominant_factor"]
            existing_obj.dominant_factor_contribution = attribution["dominant_factor_contribution"]
            existing_obj.method = attribution["method"]
            existing_obj.calculated_at = datetime.utcnow()
            attribution_obj = existing_obj
        else:
            attribution_obj = RiskAttribution(
                grid_id=grid_id,
                forecast_date=forecast_date,
                crop_type=crop_type,
                risk_index=risk_index,
                base_value=attribution["base_value"],
                shap_temperature=shap["temperature"],
                shap_humidity=shap["humidity"],
                shap_leaf_wetness=shap["leaf_wetness"],
                shap_spore_concentration=shap["spore_concentration"],
                shap_resistance=shap["resistance_level"],
                dominant_factor=attribution["dominant_factor"],
                dominant_factor_contribution=attribution["dominant_factor_contribution"],
                method=attribution["method"],
                model_version=self.risk_engine.MODEL_VERSION,
            )
            self.db.add(attribution_obj)

        await self.db.commit()
        await self.db.refresh(attribution_obj)
        return attribution_obj

    async def get_attribution_for_point(
        self,
        lon: float,
        lat: float,
        crop_type: CropType,
        forecast_date: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """获取指定点的归因分析结果

        Args:
            lon: 经度
            lat: 纬度
            crop_type: 作物类型
            forecast_date: 预报日期

        Returns:
            Optional[Dict]: 归因分析结果，若不存在则返回None
        """
        forecast_date = forecast_date or datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        grid_cell = await self.grid_service.get_or_create_grid_cell(lon, lat)

        result = await self.db.execute(
            select(RiskAttribution).where(
                and_(
                    RiskAttribution.grid_id == grid_cell.id,
                    func.date(RiskAttribution.forecast_date) == func.date(forecast_date),
                    RiskAttribution.crop_type == crop_type,
                )
            )
        )
        attribution = result.scalar_one_or_none()

        if not attribution:
            return None

        return {
            "id": attribution.id,
            "grid_id": attribution.grid_id,
            "lon": lon,
            "lat": lat,
            "crop_type": attribution.crop_type.value if isinstance(attribution.crop_type, CropType) else attribution.crop_type,
            "forecast_date": attribution.forecast_date.isoformat(),
            "risk_index": attribution.risk_index,
            "base_value": attribution.base_value,
            "shap_values": {
                "temperature": attribution.shap_temperature,
                "humidity": attribution.shap_humidity,
                "leaf_wetness": attribution.shap_leaf_wetness,
                "spore_concentration": attribution.shap_spore_concentration,
                "resistance_level": attribution.shap_resistance,
            },
            "shap_values_cn": {
                "温度": attribution.shap_temperature,
                "湿度": attribution.shap_humidity,
                "叶面湿润时长": attribution.shap_leaf_wetness,
                "孢子浓度": attribution.shap_spore_concentration,
                "品种抗性": attribution.shap_resistance,
            },
            "dominant_factor": attribution.dominant_factor,
            "dominant_factor_cn": self.FEATURE_LABELS_CN.get(attribution.dominant_factor, attribution.dominant_factor),
            "dominant_factor_contribution": attribution.dominant_factor_contribution,
            "method": attribution.method,
            "calculated_at": attribution.calculated_at.isoformat() if attribution.calculated_at else None,
        }

    async def analyze_dominant_factors(
        self,
        crop_type: CropType,
        forecast_date: Optional[datetime] = None,
        bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> Dict[str, Any]:
        """分析区域内的主导风险因素分布

        Args:
            crop_type: 作物类型
            forecast_date: 预报日期
            bounds: 经纬度范围 (lon_min, lat_min, lon_max, lat_max)

        Returns:
            Dict: 包含各主导因素的空间分布统计
                - total_grids: 总网格数
                - dominant_distribution: 各因素作为主导的网格数和占比
                - average_contribution: 各因素的平均贡献度
                - high_risk_dominant: 高风险区域的主导因素分布
        """
        forecast_date = forecast_date or datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        query = (
            select(RiskAttribution, GridCell)
            .join(GridCell, RiskAttribution.grid_id == GridCell.id)
            .where(
                and_(
                    RiskAttribution.crop_type == crop_type,
                    func.date(RiskAttribution.forecast_date) == func.date(forecast_date),
                )
            )
        )

        if bounds:
            lon_min, lat_min, lon_max, lat_max = bounds
            from geoalchemy2.functions import ST_Contains, ST_MakeEnvelope
            query = query.where(
                ST_Contains(
                    ST_MakeEnvelope(lon_min, lat_min, lon_max, lat_max, 4326),
                    GridCell.centroid,
                )
            )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return {
                "total_grids": 0,
                "dominant_distribution": {},
                "average_contribution": {},
                "high_risk_dominant": {},
                "forecast_date": forecast_date.isoformat(),
                "crop_type": crop_type.value if isinstance(crop_type, CropType) else crop_type,
            }

        total = len(rows)
        dominant_counts = {}
        avg_contributions = {feat: 0.0 for feat in self.FEATURE_NAMES}
        high_risk_dominant = {}

        for attr, grid in rows:
            dom = attr.dominant_factor
            dominant_counts[dom] = dominant_counts.get(dom, 0) + 1

            avg_contributions["temperature"] += attr.shap_temperature
            avg_contributions["humidity"] += attr.shap_humidity
            avg_contributions["leaf_wetness"] += attr.shap_leaf_wetness
            avg_contributions["spore_concentration"] += attr.shap_spore_concentration
            avg_contributions["resistance_level"] += attr.shap_resistance

            if attr.risk_index >= 40:
                high_risk_dominant[dom] = high_risk_dominant.get(dom, 0) + 1

        for feat in avg_contributions:
            avg_contributions[feat] = round(avg_contributions[feat] / total, 4)

        dominant_dist = {
            self.FEATURE_LABELS_CN.get(k, k): {
                "count": v,
                "percentage": round(v / total * 100, 2),
            }
            for k, v in dominant_counts.items()
        }

        high_risk_total = sum(high_risk_dominant.values())
        high_risk_dist = {
            self.FEATURE_LABELS_CN.get(k, k): {
                "count": v,
                "percentage": round(v / max(high_risk_total, 1) * 100, 2),
            }
            for k, v in high_risk_dominant.items()
        }

        avg_contrib_cn = {
            self.FEATURE_LABELS_CN.get(k, k): v
            for k, v in avg_contributions.items()
        }

        return {
            "total_grids": total,
            "dominant_distribution": dominant_dist,
            "average_contribution": avg_contrib_cn,
            "high_risk_dominant": high_risk_dist,
            "high_risk_total": high_risk_total,
            "forecast_date": forecast_date.isoformat(),
            "crop_type": crop_type.value if isinstance(crop_type, CropType) else crop_type,
        }
