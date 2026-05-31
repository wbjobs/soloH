from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import numpy as np

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import to_shape

from app.db.models import (
    CropType,
    GridCell,
    RiskGrid,
    DroneDiseaseDetection,
    PesticideProduct,
    SprayRecommendation,
    UserConfig,
)
from app.services.grid_service import GridService
from app.services.risk_engine import RiskEngine
from app.core.constants import RISK_THRESHOLDS


class PesticideService:
    """农药喷洒建议服务

    基于风险指数、无人机检测结果和经济阈值，提供科学的农药喷洒建议。

    核心算法:
    - 经济阈值计算: ET = (C * 100) / (Y * P * E)
      其中: C=防治成本, Y=预期产量, P=产品价格, E=防治效果
    - 风险-收益分析: 比较防治成本与预期挽回损失
    - 抗性管理: 轮换作用机制、限制施用次数
    - 天气适应性: 避免雨天、高温时段施药

    参考文献:
    - Pedigo, L. P., et al. (1986). Economic injury levels in theory and practice.
      Annual Review of Entomology, 31(1), 341-368.
    - Brent, K. J., & Hollomon, D. W. (2007). Fungicide resistance:
      the assessment of risk. FRAC Monograph No. 1.
    """

    ECONOMIC_THRESHOLD_DEFAULTS = {
        "wheat": {
            "yield_tons_ha": 6.0,
            "price_yuan_ton": 2500.0,
            "control_cost_yuan_ha": 150.0,
        },
        "potato": {
            "yield_tons_ha": 25.0,
            "price_yuan_ton": 1200.0,
            "control_cost_yuan_ha": 300.0,
        },
    }

    URGENCY_LEVELS = {
        "immediate": {
            "name": "立即施药",
            "color": "#ef4444",
            "time_window": "24小时内",
            "risk_min": RISK_THRESHOLDS["high"],
        },
        "high": {
            "name": "尽快施药",
            "color": "#f97316",
            "time_window": "3天内",
            "risk_min": RISK_THRESHOLDS["medium"],
        },
        "medium": {
            "name": "准备施药",
            "color": "#eab308",
            "time_window": "7天内",
            "risk_min": RISK_THRESHOLDS["low"],
        },
        "low": {
            "name": "观察监测",
            "color": "#22c55e",
            "time_window": "暂不需施药",
            "risk_min": 0,
        },
    }

    APPLICATION_TIMING_ADVICE = {
        "morning": {
            "name": "清晨",
            "time_range": "6:00-10:00",
            "conditions": "气温15-25°C，风速<3m/s，露水未干时更佳",
            "suitability": 90,
        },
        "evening": {
            "name": "傍晚",
            "time_range": "16:00-20:00",
            "conditions": "气温下降，风速减小，避免露水影响",
            "suitability": 85,
        },
        "cloudy": {
            "name": "阴天",
            "time_range": "全天",
            "conditions": "无直射阳光，温度适中，避免雨天",
            "suitability": 75,
        },
        "avoid": {
            "name": "避免时段",
            "time_range": "10:00-16:00",
            "conditions": "高温强光、风速>5m/s、预计6小时内降雨",
            "suitability": 10,
        },
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.grid_service = GridService(db)
        self.risk_engine = RiskEngine(db)

    async def init_default_products(self) -> List[PesticideProduct]:
        """初始化默认农药产品数据

        Returns:
            List[PesticideProduct]: 创建的农药产品列表
        """
        default_products = [
            {
                "product_name": "三唑酮",
                "registration_number": "PD20083685",
                "active_ingredient": "三唑酮 20%",
                "formulation": "可湿性粉剂",
                "concentration": "20%",
                "target_crops": "小麦",
                "target_diseases": "小麦锈病、白粉病",
                "recommended_dosage": "750-1050克/公顷",
                "dosage_ha": 0.9,
                "unit": "公斤",
                "pre_harvest_interval_days": 20,
                "safety_interval_days": 7,
                "rainfastness_hours": 6,
                "price_per_unit": 25.0,
                "efficacy_rating": 85.0,
                "resistance_risk": "中等",
                "restricted_use": False,
                "notes": "作用机制：麦角甾醇生物合成抑制剂。与其他类型杀菌剂轮换使用。",
            },
            {
                "product_name": "丙环唑",
                "registration_number": "PD20091865",
                "active_ingredient": "丙环唑 250克/升",
                "formulation": "乳油",
                "concentration": "250g/L",
                "target_crops": "小麦",
                "target_diseases": "小麦锈病、白粉病、纹枯病",
                "recommended_dosage": "450-600毫升/公顷",
                "dosage_ha": 0.525,
                "unit": "升",
                "pre_harvest_interval_days": 28,
                "safety_interval_days": 10,
                "rainfastness_hours": 4,
                "price_per_unit": 45.0,
                "efficacy_rating": 90.0,
                "resistance_risk": "中等",
                "restricted_use": False,
                "notes": "作用机制：三唑类，内吸传导性好。避免作物敏感期使用。",
            },
            {
                "product_name": "代森锰锌",
                "registration_number": "PD85155-32",
                "active_ingredient": "代森锰锌 80%",
                "formulation": "可湿性粉剂",
                "concentration": "80%",
                "target_crops": "小麦、马铃薯",
                "target_diseases": "锈病、晚疫病、早疫病",
                "recommended_dosage": "1800-2400克/公顷",
                "dosage_ha": 2.1,
                "unit": "公斤",
                "pre_harvest_interval_days": 15,
                "safety_interval_days": 5,
                "rainfastness_hours": 8,
                "price_per_unit": 18.0,
                "efficacy_rating": 75.0,
                "resistance_risk": "低",
                "restricted_use": False,
                "notes": "作用机制：多作用位点保护性杀菌剂。抗性风险低，适合轮换使用。",
            },
            {
                "product_name": "代森锰锌·甲霜灵",
                "registration_number": "PD20050278",
                "active_ingredient": "代森锰锌 64% + 甲霜灵 8%",
                "formulation": "可湿性粉剂",
                "concentration": "72%（64%+8%）",
                "target_crops": "马铃薯",
                "target_diseases": "马铃薯晚疫病、早疫病",
                "recommended_dosage": "2250-3000克/公顷",
                "dosage_ha": 2.625,
                "unit": "公斤",
                "pre_harvest_interval_days": 14,
                "safety_interval_days": 7,
                "rainfastness_hours": 6,
                "price_per_unit": 35.0,
                "efficacy_rating": 88.0,
                "resistance_risk": "中等",
                "restricted_use": False,
                "notes": "作用机制：保护+治疗复配制剂。甲霜灵为内吸性，注意抗性管理。",
            },
            {
                "product_name": "氟啶胺",
                "registration_number": "PD20131025",
                "active_ingredient": "氟啶胺 500克/升",
                "formulation": "悬浮剂",
                "concentration": "500g/L",
                "target_crops": "马铃薯",
                "target_diseases": "马铃薯晚疫病",
                "recommended_dosage": "300-450毫升/公顷",
                "dosage_ha": 0.375,
                "unit": "升",
                "pre_harvest_interval_days": 14,
                "safety_interval_days": 7,
                "rainfastness_hours": 4,
                "price_per_unit": 120.0,
                "efficacy_rating": 92.0,
                "resistance_risk": "低",
                "restricted_use": False,
                "notes": "作用机制：氧化磷酸化解偶联剂。抗性风险低，对卵菌特效。",
            },
            {
                "product_name": "吡唑醚菌酯",
                "registration_number": "PD20093880",
                "active_ingredient": "吡唑醚菌酯 250克/升",
                "formulation": "乳油",
                "concentration": "250g/L",
                "target_crops": "小麦、马铃薯",
                "target_diseases": "锈病、白粉病、晚疫病",
                "recommended_dosage": "600-900毫升/公顷",
                "dosage_ha": 0.75,
                "unit": "升",
                "pre_harvest_interval_days": 21,
                "safety_interval_days": 14,
                "rainfastness_hours": 4,
                "price_per_unit": 80.0,
                "efficacy_rating": 90.0,
                "resistance_risk": "中等",
                "restricted_use": False,
                "notes": "作用机制：QoI类杀菌剂，具有植物健康效应。注意抗药性风险。",
            },
        ]

        created_products = []
        for product_data in default_products:
            existing = await self.db.execute(
                select(PesticideProduct).where(
                    PesticideProduct.registration_number == product_data["registration_number"]
                )
            )
            if existing.scalar_one_or_none() is None:
                product = PesticideProduct(**product_data)
                self.db.add(product)
                created_products.append(product)

        if created_products:
            await self.db.commit()
            for product in created_products:
                await self.db.refresh(product)

        return created_products

    async def get_available_products(
        self,
        crop_type: Optional[CropType] = None,
        disease_name: Optional[str] = None,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        """获取可用的农药产品列表

        Args:
            crop_type: 作物类型筛选
            disease_name: 防治对象筛选
            include_inactive: 是否包含已停用产品

        Returns:
            List[Dict]: 农药产品列表
        """
        query = select(PesticideProduct)
        if not include_inactive:
            query = query.where(PesticideProduct.is_active == True)

        result = await self.db.execute(query)
        products = result.scalars().all()

        product_list = []
        for p in products:
            if crop_type:
                crop_str = crop_type.value if isinstance(crop_type, CropType) else crop_type
                if crop_str == "wheat" and "小麦" not in p.target_crops:
                    continue
                if crop_str == "potato" and "马铃薯" not in p.target_crops:
                    continue

            if disease_name and disease_name not in p.target_diseases:
                continue

            product_list.append({
                "id": p.id,
                "product_name": p.product_name,
                "registration_number": p.registration_number,
                "active_ingredient": p.active_ingredient,
                "formulation": p.formulation,
                "target_crops": p.target_crops,
                "target_diseases": p.target_diseases,
                "recommended_dosage": p.recommended_dosage,
                "dosage_ha": p.dosage_ha,
                "unit": p.unit,
                "pre_harvest_interval_days": p.pre_harvest_interval_days,
                "safety_interval_days": p.safety_interval_days,
                "rainfastness_hours": p.rainfastness_hours,
                "price_per_unit": p.price_per_unit,
                "efficacy_rating": p.efficacy_rating,
                "resistance_risk": p.resistance_risk,
                "restricted_use": p.restricted_use,
                "notes": p.notes,
            })

        return product_list

    def calculate_economic_threshold(
        self,
        crop_type: CropType,
        yield_tons_ha: Optional[float] = None,
        price_yuan_ton: Optional[float] = None,
        control_cost_yuan_ha: Optional[float] = None,
        efficacy: float = 0.85,
    ) -> Dict[str, Any]:
        """计算经济阈值

        经济阈值（Economic Threshold）是指病害严重度达到某一水平时，
        防治收益等于防治成本，此时开始防治可获得最大经济效益。

        计算公式:
        ET = (C × 100) / (Y × P × E)

        其中:
        - C: 防治成本 (元/公顷)
        - Y: 预期产量 (吨/公顷)
        - P: 产品价格 (元/吨)
        - E: 防治效果 (0-1)

        Args:
            crop_type: 作物类型
            yield_tons_ha: 预期产量（吨/公顷），None时使用默认值
            price_yuan_ton: 产品价格（元/吨），None时使用默认值
            control_cost_yuan_ha: 防治成本（元/公顷），None时使用默认值
            efficacy: 预期防治效果（0-1），默认0.85

        Returns:
            Dict: 经济阈值计算结果
                - economic_threshold: 经济阈值（风险指数0-100）
                - yield_tons_ha: 预期产量
                - price_yuan_ton: 产品价格
                - control_cost_yuan_ha: 防治成本
                - expected_yield_loss_yuan: 阈值点的预期损失金额
                - break_even_severity: 收支平衡的病害严重度(%)
        """
        crop_str = crop_type.value if isinstance(crop_type, CropType) else crop_type
        defaults = self.ECONOMIC_THRESHOLD_DEFAULTS.get(crop_str, {})

        Y = yield_tons_ha if yield_tons_ha is not None else defaults.get("yield_tons_ha", 5.0)
        P = price_yuan_ton if price_yuan_ton is not None else defaults.get("price_yuan_ton", 2000.0)
        C = control_cost_yuan_ha if control_cost_yuan_ha is not None else defaults.get("control_cost_yuan_ha", 200.0)
        E = max(0.1, min(1.0, efficacy))

        break_even_severity = (C * 100) / (Y * P * E) if Y * P * E > 0 else 50.0

        expected_yield_loss_tons = Y * (break_even_severity / 100)
        expected_yield_loss_yuan = expected_yield_loss_tons * P

        et_risk_index = min(100.0, break_even_severity * 1.2)

        return {
            "economic_threshold": round(et_risk_index, 2),
            "yield_tons_ha": Y,
            "price_yuan_ton": P,
            "control_cost_yuan_ha": C,
            "efficacy": E,
            "break_even_severity": round(break_even_severity, 2),
            "expected_yield_loss_tons": round(expected_yield_loss_tons, 4),
            "expected_yield_loss_yuan": round(expected_yield_loss_yuan, 2),
            "formula": "ET = (C × 100) / (Y × P × E)",
            "formula_explanation": {
                "C": "防治成本 (元/公顷)",
                "Y": "预期产量 (吨/公顷)",
                "P": "产品价格 (元/吨)",
                "E": "防治效果 (0-1)",
            },
        }

    def determine_urgency(
        self,
        risk_index: float,
        drone_severity: Optional[float] = None,
        forecast_risk_trend: Optional[str] = "stable",
    ) -> Tuple[str, Dict[str, Any]]:
        """确定施药紧急程度

        Args:
            risk_index: 风险指数（0-100）
            drone_severity: 无人机检测的病害严重度（0-100），可选
            forecast_risk_trend: 风险趋势: rising, stable, falling

        Returns:
            Tuple: (紧急程度key, 紧急程度详情)
        """
        effective_risk = risk_index
        if drone_severity is not None:
            effective_risk = max(risk_index, drone_severity)

        if forecast_risk_trend == "rising":
            effective_risk = min(100.0, effective_risk * 1.15)
        elif forecast_risk_trend == "falling":
            effective_risk = max(0.0, effective_risk * 0.85)

        if effective_risk >= self.URGENCY_LEVELS["immediate"]["risk_min"]:
            return "immediate", self.URGENCY_LEVELS["immediate"]
        elif effective_risk >= self.URGENCY_LEVELS["high"]["risk_min"]:
            return "high", self.URGENCY_LEVELS["high"]
        elif effective_risk >= self.URGENCY_LEVELS["medium"]["risk_min"]:
            return "medium", self.URGENCY_LEVELS["medium"]
        else:
            return "low", self.URGENCY_LEVELS["low"]

    def select_optimal_product(
        self,
        products: List[Dict[str, Any]],
        risk_index: float,
        urgency: str,
        drone_severity: Optional[float] = None,
        max_cost_yuan_ha: Optional[float] = None,
        last_used_ingredient: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """选择最优的农药产品

        选择策略:
        1. 根据风险等级和严重度选择合适的效果等级
        2. 考虑抗性管理，避免连续使用相同作用机制
        3. 考虑成本约束
        4. 推荐主选和备选产品

        Args:
            products: 可用产品列表
            risk_index: 风险指数
            urgency: 紧急程度
            drone_severity: 无人机检测严重度
            max_cost_yuan_ha: 最大成本限制（元/公顷）
            last_used_ingredient: 上次使用的有效成分，用于抗性轮换

        Returns:
            Tuple: (推荐产品, 备选产品)
        """
        if not products:
            return None, None

        effective_severity = risk_index
        if drone_severity is not None:
            effective_severity = max(effective_severity, drone_severity)

        scored_products = []
        for product in products:
            score = 0.0

            if effective_severity >= 60:
                if product["efficacy_rating"] >= 85:
                    score += 40
                elif product["efficacy_rating"] >= 75:
                    score += 20
            elif effective_severity >= 30:
                if product["efficacy_rating"] >= 75:
                    score += 35
                else:
                    score += 15
            else:
                if product["efficacy_rating"] >= 70:
                    score += 30
                else:
                    score += 15

            cost_ha = product["dosage_ha"] * product["price_per_unit"]
            if max_cost_yuan_ha is not None and cost_ha > max_cost_yuan_ha:
                score -= 20

            if last_used_ingredient and last_used_ingredient in product["active_ingredient"]:
                score -= 25

            if product["resistance_risk"] == "低":
                score += 15
            elif product["resistance_risk"] == "中等":
                score += 5

            score += (product["efficacy_rating"] / 100) * 20

            cost_score = max(0, 10 - cost_ha / 100) * 2
            score += cost_score

            scored_products.append((score, product, cost_ha))

        scored_products.sort(key=lambda x: -x[0])

        if not scored_products:
            return None, None

        recommended = scored_products[0]
        alternative = scored_products[1] if len(scored_products) > 1 else None

        return recommended, alternative

    def calculate_cost_benefit(
        self,
        risk_index: float,
        product: Dict[str, Any],
        yield_tons_ha: float,
        price_yuan_ton: float,
        drone_severity: Optional[float] = None,
        area_ha: float = 1.0,
    ) -> Dict[str, Any]:
        """计算成本收益分析

        Args:
            risk_index: 风险指数
            product: 农药产品信息
            yield_tons_ha: 预期产量（吨/公顷）
            price_yuan_ton: 产品价格（元/吨）
            drone_severity: 无人机检测严重度
            area_ha: 防治面积（公顷）

        Returns:
            Dict: 成本收益分析结果
        """
        effective_risk = risk_index
        if drone_severity is not None:
            effective_risk = max(risk_index, drone_severity)

        yield_loss_ratio = effective_risk / 100.0
        efficacy = product["efficacy_rating"] / 100.0

        expected_loss_tons_ha = yield_tons_ha * yield_loss_ratio
        prevented_loss_tons_ha = expected_loss_tons_ha * efficacy
        revenue_gain_ha = prevented_loss_tons_ha * price_yuan_ton

        cost_ha = product["dosage_ha"] * product["price_per_unit"]
        total_cost = cost_ha * area_ha
        total_revenue_gain = revenue_gain_ha * area_ha

        net_benefit = total_revenue_gain - total_cost
        benefit_cost_ratio = total_revenue_gain / total_cost if total_cost > 0 else 0

        return {
            "risk_index": risk_index,
            "effective_risk": effective_risk,
            "yield_loss_ratio": round(yield_loss_ratio, 4),
            "efficacy": efficacy,
            "expected_loss_tons_ha": round(expected_loss_tons_ha, 4),
            "prevented_loss_tons_ha": round(prevented_loss_tons_ha, 4),
            "revenue_gain_yuan_ha": round(revenue_gain_ha, 2),
            "cost_yuan_ha": round(cost_ha, 2),
            "net_benefit_yuan_ha": round(revenue_gain_ha - cost_ha, 2),
            "area_ha": area_ha,
            "total_cost_yuan": round(total_cost, 2),
            "total_revenue_gain_yuan": round(total_revenue_gain, 2),
            "total_net_benefit_yuan": round(net_benefit, 2),
            "benefit_cost_ratio": round(benefit_cost_ratio, 2),
            "recommendation": "划算" if net_benefit > 0 else "不划算",
        }

    async def generate_spray_recommendation(
        self,
        lon: float,
        lat: float,
        crop_type: CropType,
        forecast_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        area_ha: Optional[float] = None,
        yield_tons_ha: Optional[float] = None,
        price_yuan_ton: Optional[float] = None,
        max_cost_yuan_ha: Optional[float] = None,
        last_used_ingredient: Optional[str] = None,
        forecast_risk_trend: Optional[str] = "stable",
    ) -> Dict[str, Any]:
        """生成农药喷洒建议

        综合考虑:
        1. 气象模型计算的风险指数
        2. 无人机检测的实际病害情况
        3. 经济阈值分析
        4. 成本收益分析
        5. 抗性管理策略

        Args:
            lon: 经度
            lat: 纬度
            crop_type: 作物类型
            forecast_date: 预报日期
            user_id: 用户ID
            area_ha: 防治面积（公顷），默认1平方公里=100公顷
            yield_tons_ha: 预期产量（吨/公顷）
            price_yuan_ton: 产品价格（元/吨）
            max_cost_yuan_ha: 最大成本限制（元/公顷）
            last_used_ingredient: 上次使用的有效成分
            forecast_risk_trend: 风险趋势

        Returns:
            Dict: 完整的喷洒建议
        """
        forecast_date = forecast_date or datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        grid_cell = await self.grid_service.get_or_create_grid_cell(lon, lat)
        grid_id = grid_cell.id

        if area_ha is None:
            area_ha = 100.0

        risk_result = await self.risk_engine.calculate_point_risk(
            lon=lon, lat=lat, crop_type=crop_type,
            forecast_date=forecast_date,
        )
        risk_index = risk_result["risk_index"]

        today_start = forecast_date - timedelta(days=7)
        from app.services.drone_service import DroneService
        drone_service = DroneService(self.db)
        drone_detections = await drone_service.get_detections_for_grid(
            grid_id=grid_id, start_date=today_start, end_date=forecast_date
        )

        drone_severity = None
        if drone_detections:
            valid_detections = [d for d in drone_detections if d.get("severity") is not None]
            if valid_detections:
                drone_severity = max(d["severity"] for d in valid_detections)

        products = await self.get_available_products(crop_type=crop_type)

        urgency_key, urgency_info = self.determine_urgency(
            risk_index=risk_index,
            drone_severity=drone_severity,
            forecast_risk_trend=forecast_risk_trend,
        )

        economic_threshold = self.calculate_economic_threshold(
            crop_type=crop_type,
            yield_tons_ha=yield_tons_ha,
            price_yuan_ton=price_yuan_ton,
        )

        et_value = economic_threshold["economic_threshold"]
        spray_needed = (risk_index >= et_value) or (drone_severity is not None and drone_severity >= 30)

        if urgency_key == "immediate":
            spray_needed = True

        recommended_product = None
        alternative_product = None
        cost_benefit = None

        if spray_needed and products:
            recommended, alternative = self.select_optimal_product(
                products=products,
                risk_index=risk_index,
                urgency=urgency_key,
                drone_severity=drone_severity,
                max_cost_yuan_ha=max_cost_yuan_ha,
                last_used_ingredient=last_used_ingredient,
            )

            if recommended:
                score, product, cost_ha = recommended
                recommended_product = product
                recommended_product["total_dosage"] = round(product["dosage_ha"] * area_ha, 2)
                recommended_product["estimated_cost"] = round(cost_ha * area_ha, 2)
                recommended_product["application_rate"] = product["recommended_dosage"]

                cost_benefit = self.calculate_cost_benefit(
                    risk_index=risk_index,
                    product=product,
                    yield_tons_ha=economic_threshold["yield_tons_ha"],
                    price_yuan_ton=economic_threshold["price_yuan_ton"],
                    drone_severity=drone_severity,
                    area_ha=area_ha,
                )

            if alternative:
                alt_score, alt_product, alt_cost_ha = alternative
                alternative_product = alt_product
                alternative_product["total_dosage"] = round(alt_product["dosage_ha"] * area_ha, 2)
                alternative_product["estimated_cost"] = round(alt_cost_ha * area_ha, 2)

        timing = self._recommend_timing()
        safety = self._get_safety_precautions(recommended_product)
        resistance = self._get_resistance_management_advice(recommended_product, alternative_product)

        recommendation = SprayRecommendation(
            grid_id=grid_id,
            forecast_date=forecast_date,
            crop_type=crop_type,
            user_id=user_id,
            risk_index=risk_index,
            risk_level=RiskEngine.get_risk_level(risk_index),
            drone_detected_severity=drone_severity,
            economic_threshold=et_value,
            spray_needed=spray_needed,
            urgency=urgency_key,
            recommended_product_id=recommended_product["id"] if recommended_product else None,
            alternative_product_id=alternative_product["id"] if alternative_product else None,
            application_rate=recommended_product["dosage_ha"] if recommended_product else None,
            application_rate_unit=recommended_product["unit"] if recommended_product else None,
            total_area_ha=area_ha,
            total_product_needed=recommended_product["total_dosage"] if recommended_product else None,
            estimated_cost=recommended_product["estimated_cost"] if recommended_product else None,
            application_timing=timing["best_timing"],
            application_method=self._get_application_method(crop_type),
            pre_harvest_interval=recommended_product["pre_harvest_interval_days"] if recommended_product else None,
            reentry_interval=recommended_product["safety_interval_days"] if recommended_product else None,
            weather_conditions=timing["weather_conditions"],
            expected_efficacy=recommended_product["efficacy_rating"] if recommended_product else None,
            resistance_management=resistance,
            environmental_impact=self._get_environmental_advice(),
            safety_precautions=safety,
            expires_at=forecast_date + timedelta(days=7),
        )

        self.db.add(recommendation)
        await self.db.commit()
        await self.db.refresh(recommendation)

        return {
            "recommendation_id": recommendation.id,
            "grid_id": grid_id,
            "lon": lon,
            "lat": lat,
            "crop_type": crop_type.value if isinstance(crop_type, CropType) else crop_type,
            "forecast_date": forecast_date.isoformat(),
            "risk_index": risk_index,
            "risk_level": risk_result["risk_level"],
            "drone_detected_severity": drone_severity,
            "drone_detections_count": len(drone_detections),
            "economic_threshold": economic_threshold,
            "spray_needed": spray_needed,
            "urgency": {
                "level": urgency_key,
                "name": urgency_info["name"],
                "color": urgency_info["color"],
                "time_window": urgency_info["time_window"],
            },
            "recommended_product": recommended_product,
            "alternative_product": alternative_product,
            "cost_benefit_analysis": cost_benefit,
            "application_timing": timing,
            "application_method": self._get_application_method(crop_type),
            "safety_precautions": safety,
            "resistance_management": resistance,
            "environmental_impact": self._get_environmental_advice(),
            "generated_at": recommendation.generated_at.isoformat() if recommendation.generated_at else None,
            "expires_at": recommendation.expires_at.isoformat() if recommendation.expires_at else None,
        }

    def _recommend_timing(self) -> Dict[str, Any]:
        """推荐施药时间

        Returns:
            Dict: 施药时间建议
        """
        return {
            "best_timing": "清晨或傍晚",
            "best_timing_description": "选择无风或微风、气温15-25°C的时段施药",
            "time_windows": [
                {
                    "period": self.APPLICATION_TIMING_ADVICE["morning"]["name"],
                    "time": self.APPLICATION_TIMING_ADVICE["morning"]["time_range"],
                    "conditions": self.APPLICATION_TIMING_ADVICE["morning"]["conditions"],
                    "suitability": self.APPLICATION_TIMING_ADVICE["morning"]["suitability"],
                },
                {
                    "period": self.APPLICATION_TIMING_ADVICE["evening"]["name"],
                    "time": self.APPLICATION_TIMING_ADVICE["evening"]["time_range"],
                    "conditions": self.APPLICATION_TIMING_ADVICE["evening"]["conditions"],
                    "suitability": self.APPLICATION_TIMING_ADVICE["evening"]["suitability"],
                },
            ],
            "avoid": {
                "period": self.APPLICATION_TIMING_ADVICE["avoid"]["name"],
                "time": self.APPLICATION_TIMING_ADVICE["avoid"]["time_range"],
                "conditions": self.APPLICATION_TIMING_ADVICE["avoid"]["conditions"],
            },
            "weather_conditions": "施药前查看天气预报，确保施药后6小时内无降雨；风速低于3级（<5m/s）；避免高温强光时段",
            "rainfastness_hours": 6,
        }

    def _get_application_method(self, crop_type: CropType) -> str:
        """获取施药方法建议

        Args:
            crop_type: 作物类型

        Returns:
            str: 施药方法描述
        """
        crop_str = crop_type.value if isinstance(crop_type, CropType) else crop_type

        if crop_str == "wheat":
            return "茎叶喷雾法：使用背负式喷雾器或机动喷雾机，采用圆锥雾喷头，每亩喷液量30-45公斤。雾滴直径150-300微米，确保叶片正反两面均匀着药。"
        elif crop_str == "potato":
            return "茎叶喷雾法：使用机引喷雾机或无人机喷雾，每亩喷液量40-60公斤。重点喷施叶片背面和植株中下部。根据病害发生情况，可适当增加喷液量。"
        else:
            return "茎叶均匀喷雾，确保作物各部位着药均匀。根据作物长势和病害情况调整喷液量和喷雾压力。"

    def _get_safety_precautions(self, product: Optional[Dict[str, Any]]) -> List[str]:
        """获取安全防护措施

        Args:
            product: 农药产品信息

        Returns:
            List[str]: 安全注意事项列表
        """
        precautions = [
            "施药人员必须穿戴防护服、口罩、护目镜、手套等防护用品",
            "施药期间禁止饮食、吸烟、饮水",
            "施药后及时清洗手脸、更换衣物",
            "农药应存放在儿童、牲畜接触不到的安全地方",
            "避免农药污染水源、池塘、蜜蜂活动区域",
            "严格遵守农药安全间隔期和收获间隔期规定",
            "如不慎接触皮肤，立即用大量清水冲洗；如溅入眼睛，用清水冲洗15分钟以上并就医",
            "农药包装物应妥善处理，禁止随意丢弃",
        ]

        if product and product.get("safety_interval_days"):
            precautions.append(
                f"施药后 {product['safety_interval_days']} 天内禁止进入田间作业"
            )
        if product and product.get("pre_harvest_interval_days"):
            precautions.append(
                f"收获前 {product['pre_harvest_interval_days']} 天禁止施用本品"
            )

        return precautions

    def _get_resistance_management_advice(
        self,
        recommended: Optional[Dict[str, Any]],
        alternative: Optional[Dict[str, Any]],
    ) -> List[str]:
        """获取抗性管理建议

        Args:
            recommended: 推荐产品
            alternative: 备选产品

        Returns:
            List[str]: 抗性管理建议列表
        """
        advice = [
            "严格按照推荐剂量施药，避免随意加大或减少用量",
            "同一生长季内，同一作用机制的农药施用次数不超过3次",
            "不同作用机制的农药轮换使用，避免连续使用同一类型药剂",
            "提倡预防性用药，在病害发生初期或低风险时施药，降低抗性选择压",
            "采用综合防治措施，结合抗病品种、栽培措施、生物防治等方法",
        ]

        if recommended and alternative:
            advice.append(
                f"建议与 '{alternative['product_name']}' 轮换使用，避免连续使用 '{recommended['product_name']}'"
            )

        if recommended and recommended.get("resistance_risk"):
            risk_level = recommended["resistance_risk"]
            if risk_level == "高":
                advice.append(f"注意：本品抗性风险为{risk_level}，请严格控制施用次数")
            elif risk_level == "中等":
                advice.append(f"本品抗性风险为{risk_level}，建议与低抗性风险药剂轮换")

        return advice

    def _get_environmental_advice(self) -> List[str]:
        """获取环境保护建议

        Returns:
            List[str]: 环境保护建议列表
        """
        return [
            "避免在蜜蜂活动频繁时期施药，开花期禁用对蜜蜂高毒的农药",
            "远离水源地、水产养殖区施药，防止农药污染水体",
            "注意保护鸟类、天敌昆虫等有益生物",
            "严格按照推荐剂量施药，避免过量施用造成环境污染",
            "农药包装废弃物应按规定回收处理，不可随意丢弃",
            "优先选择低毒、低残留、环境友好型农药产品",
        ]

    async def get_recommendation_for_point(
        self,
        lon: float,
        lat: float,
        crop_type: CropType,
        forecast_date: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """获取指定点的喷洒建议

        Args:
            lon: 经度
            lat: 纬度
            crop_type: 作物类型
            forecast_date: 预报日期

        Returns:
            Optional[Dict]: 喷洒建议，若不存在则返回None
        """
        forecast_date = forecast_date or datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        grid_cell = await self.grid_service.get_or_create_grid_cell(lon, lat)

        result = await self.db.execute(
            select(SprayRecommendation).where(
                and_(
                    SprayRecommendation.grid_id == grid_cell.id,
                    func.date(SprayRecommendation.forecast_date) == func.date(forecast_date),
                    SprayRecommendation.crop_type == crop_type,
                )
            )
        )
        rec = result.scalar_one_or_none()

        if not rec:
            return None

        recommended_product = None
        if rec.recommended_product_id:
            product_result = await self.db.execute(
                select(PesticideProduct).where(PesticideProduct.id == rec.recommended_product_id)
            )
            product = product_result.scalar_one_or_none()
            if product:
                recommended_product = {
                    "id": product.id,
                    "product_name": product.product_name,
                    "active_ingredient": product.active_ingredient,
                    "recommended_dosage": product.recommended_dosage,
                }

        urgency_info = self.URGENCY_LEVELS.get(rec.urgency, self.URGENCY_LEVELS["low"])

        return {
            "id": rec.id,
            "grid_id": rec.grid_id,
            "lon": lon,
            "lat": lat,
            "crop_type": rec.crop_type.value if isinstance(rec.crop_type, CropType) else rec.crop_type,
            "forecast_date": rec.forecast_date.isoformat(),
            "risk_index": rec.risk_index,
            "risk_level": rec.risk_level,
            "drone_detected_severity": rec.drone_detected_severity,
            "economic_threshold": rec.economic_threshold,
            "spray_needed": rec.spray_needed,
            "urgency": {
                "level": rec.urgency,
                "name": urgency_info["name"],
                "color": urgency_info["color"],
                "time_window": urgency_info["time_window"],
            },
            "recommended_product": recommended_product,
            "application_rate": rec.application_rate,
            "total_product_needed": rec.total_product_needed,
            "estimated_cost": rec.estimated_cost,
            "application_timing": rec.application_timing,
            "safety_precautions": rec.safety_precautions,
            "generated_at": rec.generated_at.isoformat() if rec.generated_at else None,
            "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
            "is_applied": rec.is_applied,
            "applied_at": rec.applied_at.isoformat() if rec.applied_at else None,
        }
