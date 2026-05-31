from typing import Tuple, Dict, Optional
import numpy as np
from .base import DiseaseModel


class JensenModel(DiseaseModel):
    """小麦锈病Jensen预测模型

    Jensen模型是小麦锈病预测的经典经验模型，由Jensen于1968年提出。
    该模型基于温度和叶面湿润时长的交互效应预测锈病感染风险。

    参考文献:
    - Jensen, N. F. (1968). A computer model to predict epidemics of cereal rusts.
      Phytopathology, 58(8), 1099-1104.
    - Cooke, B. M., et al. (2006). The epidemiology of plant diseases. Springer.

    核心公式:
    R = f(T) × f(W) × f(S) × f(Rg)

    其中:
    - f(T): 温度优化因子，正态分布形式，15-20°C最优
    - f(W): 湿润时长因子，S型增长函数，>6小时显著增加
    - f(S): 孢子浓度因子，Michaelis-Menten型饱和曲线
    - f(Rg): 品种抗性调节系数
    """

    model_name: str = "JensenModel"
    model_description: str = "小麦锈病Jensen预测模型，基于温度和叶面湿润时长的经典流行病学模型"
    target_disease: str = "小麦锈病"
    target_crop: str = "小麦"

    def __init__(self):
        self._temp_optimal = 17.5
        self._temp_min = 10.0
        self._temp_max = 25.0
        self._wetness_threshold = 6.0
        self._spore_half_saturation = 50.0

    def _temperature_factor(self, temperature: float) -> float:
        """计算温度优化因子 f(T)

        采用高斯分布模拟温度对锈菌孢子萌发的影响：
        f(T) = exp[-(T - T_opt)² / (2σ²)]

        15-20°C为最适温度范围，此时因子接近1.0
        温度低于10°C或高于25°C时，因子降为0

        Args:
            temperature: 环境温度 (°C)

        Returns:
            float: 温度因子，范围 0-1
        """
        if temperature < self._temp_min or temperature > self._temp_max:
            return 0.0

        sigma = 5.0
        exponent = -(temperature - self._temp_optimal) ** 2 / (2 * sigma ** 2)
        return float(np.exp(exponent))

    def _wetness_factor(self, leaf_wetness: float, temperature: Optional[float] = None, humidity: Optional[float] = None) -> float:
        """计算叶面湿润时长因子 f(W)

        采用修正的逻辑斯蒂曲线模拟湿润时长对感染的影响，
        并基于温度和湿度进行经验校正，解决高温高湿下的饱和错误：

        核心公式:
        f(W) = [1 / {1 + exp[-k × (W_eff - W_threshold)]}] × f(T) × f(VPD)

        其中:
        - W_eff: 有效湿润时长，考虑温度蒸发效应
        - f(T): 温度校正因子，>25°C时抑制，>30°C时显著下降
        - f(VPD): 水汽压亏缺校正因子，VPD>1kPa时抑制

        湿润时长<6小时：感染概率极低
        湿润时长6-12小时：感染概率快速上升
        湿润时长>12小时：感染概率趋于饱和（但受温湿度调节）

        Args:
            leaf_wetness: 叶面湿润时长 (小时)
            temperature: 环境温度 (°C)，用于蒸发校正
            humidity: 相对湿度 (%)，用于VPD计算

        Returns:
            float: 湿润时长因子，范围 0-1
        """
        if leaf_wetness <= 0:
            return 0.0

        effective_wetness = leaf_wetness

        if temperature is not None:
            if temperature > 25:
                evaporation_factor = max(0.3, 1.0 - (temperature - 25) * 0.08)
                effective_wetness *= evaporation_factor
            elif temperature < 5:
                cold_inhibition = max(0.2, 1.0 + (temperature - 5) * 0.05)
                effective_wetness *= cold_inhibition

        if temperature is not None and humidity is not None:
            sat_vp = 0.6108 * np.exp(17.27 * temperature / (temperature + 237.3))
            actual_vp = sat_vp * (humidity / 100.0)
            vpd = sat_vp - actual_vp
            if vpd > 1.0:
                vpd_factor = max(0.4, 1.0 - (vpd - 1.0) * 0.15)
                effective_wetness *= vpd_factor

        effective_wetness = max(0.0, min(24.0, effective_wetness))

        k = 0.8
        exponent = -k * (effective_wetness - self._wetness_threshold)
        base_factor = float(1.0 / (1.0 + np.exp(exponent)))

        if temperature is not None:
            if temperature > 28:
                high_temp_suppression = max(0.2, 1.0 - (temperature - 28) * 0.1)
                base_factor *= high_temp_suppression

        return base_factor

    def _spore_factor(self, spore_concentration: float) -> float:
        """计算孢子浓度因子 f(S)

        采用Michaelis-Menten型饱和曲线：
        f(S) = S / (S + K_m)

        孢子浓度较低时，感染风险随浓度线性增加
        孢子浓度较高时，感染风险趋于饱和

        Args:
            spore_concentration: 空气中孢子浓度 (个/m³)

        Returns:
            float: 孢子浓度因子，范围 0-1
        """
        if spore_concentration <= 0:
            return 0.0

        return float(spore_concentration / (spore_concentration + self._spore_half_saturation))

    def _resistance_factor(self, resistance_level: int) -> float:
        """计算品种抗性调节因子 f(Rg)

        采用反比例缩放算法，确保抗性加倍时风险减半：
        f(Rg) = 2.0 / resistance_level

        标准级别对应值:
        1 - 高感病: 风险 × 2.00
        2 - 感病:   风险 × 1.00 (基准线)
        3 - 中抗:   风险 × 0.67
        4 - 抗病:   风险 × 0.50 (抗性加倍，风险减半)
        5 - 高抗:   风险 × 0.40

        支持自定义抗性级别（>5的级别也适用同一公式）

        Args:
            resistance_level: 抗性级别 (1或更高)

        Returns:
            float: 抗性调节系数
        """
        if resistance_level < 1:
            resistance_level = 1

        base_factor = 2.0 / float(resistance_level)

        return float(max(0.05, min(5.0, base_factor)))

    def calculate_risk(
        self,
        temperature: float,
        humidity: float,
        rainfall: Optional[float] = None,
        leaf_wetness: Optional[float] = None,
        spore_concentration: Optional[float] = None,
        resistance_level: Optional[int] = None,
        **kwargs
    ) -> Tuple[float, float, Dict]:
        """计算小麦锈病风险指数

        综合温度、湿润时长、孢子浓度和品种抗性计算感染风险。

        Args:
            temperature: 环境温度 (°C)
            humidity: 相对湿度 (%)
            rainfall: 降雨量 (mm)，可选，用于辅助估算叶面湿润
            leaf_wetness: 叶面湿润时长 (小时)，None时根据湿度和降雨估算
            spore_concentration: 孢子浓度 (个/m³)，None时默认中等值
            resistance_level: 品种抗性级别 (1-5)，None时默认感病(2)
            **kwargs: 连续湿润天数等附加参数

        Returns:
            Tuple[float, float, Dict]:
                - risk_index: 风险指数，范围 0-100
                - infection_probability: 感染概率，范围 0-1
                - details: 详细计算过程和中间结果
        """
        valid, msg = self.validate_inputs(
            temperature, humidity, rainfall, leaf_wetness,
            spore_concentration, resistance_level, **kwargs
        )
        if not valid:
            return 0.0, 0.0, {"error": msg}

        details = {
            "inputs": {
                "temperature": temperature,
                "humidity": humidity,
                "rainfall": rainfall,
                "leaf_wetness": leaf_wetness,
                "spore_concentration": spore_concentration,
                "resistance_level": resistance_level,
            },
            "model_info": self.get_model_info(),
        }

        if leaf_wetness is None:
            if rainfall is not None and rainfall > 0:
                leaf_wetness = min(24.0, 8.0 + rainfall * 0.5)
                if temperature > 25:
                    leaf_wetness *= max(0.4, 1.0 - (temperature - 25) * 0.06)
            elif humidity > 90:
                leaf_wetness = 10.0
                if temperature > 28:
                    leaf_wetness *= max(0.5, 1.0 - (temperature - 28) * 0.08)
            elif humidity > 80:
                leaf_wetness = 4.0
                if temperature > 25:
                    leaf_wetness *= max(0.5, 1.0 - (temperature - 25) * 0.05)
            else:
                leaf_wetness = 0.0
            leaf_wetness = max(0.0, leaf_wetness)
            details["estimated_leaf_wetness"] = round(leaf_wetness, 2)

        if spore_concentration is None:
            spore_concentration = 30.0
            details["default_spore_concentration"] = spore_concentration

        if resistance_level is None:
            resistance_level = 2
            details["default_resistance_level"] = resistance_level

        temp_factor = self._temperature_factor(temperature)
        wetness_factor = self._wetness_factor(leaf_wetness, temperature, humidity)
        spore_factor = self._spore_factor(spore_concentration)
        resistance_factor = self._resistance_factor(resistance_level)

        consecutive_days = kwargs.get("consecutive_wet_days", 1)
        cumulative_factor = min(1.0 + (consecutive_days - 1) * 0.15, 2.0)

        raw_risk = temp_factor * wetness_factor * spore_factor * resistance_factor * cumulative_factor

        humidity_correction = 1.0
        if temp_factor > 0 and humidity < 70:
            humidity_correction = humidity / 70.0
            raw_risk *= humidity_correction

        risk_index = min(100.0, raw_risk * 100.0)
        infection_probability = min(1.0, raw_risk)

        from app.core.constants import RISK_THRESHOLDS, get_risk_level
        risk_level = get_risk_level(risk_index, use_chinese=True)

        if risk_index >= RISK_THRESHOLDS["high"]:
            recommendation = "立即喷施杀菌剂，加强田间监测"
        elif risk_index >= RISK_THRESHOLDS["medium"]:
            recommendation = "准备药剂，关注天气变化，适时防治"
        elif risk_index >= RISK_THRESHOLDS["low"]:
            recommendation = "定期巡查，保持田间通风透光"
        else:
            recommendation = "无需特殊防治措施"

        details.update({
            "factors": {
                "temperature_factor": round(temp_factor, 4),
                "wetness_factor": round(wetness_factor, 4),
                "spore_factor": round(spore_factor, 4),
                "resistance_factor": round(resistance_factor, 4),
                "cumulative_factor": round(cumulative_factor, 4),
                "humidity_correction": round(humidity_correction, 4),
            },
            "raw_risk": round(raw_risk, 4),
            "risk_level": risk_level,
            "recommendation": recommendation,
            "infection_conditions": {
                "temperature_suitable": temp_factor > 0,
                "wetness_sufficient": wetness_factor > 0.1,
                "spore_available": spore_factor > 0.1,
            },
            "formula": "R = f(T) × f(W) × f(S) × f(Rg) × f(C)",
            "formula_explanation": {
                "f(T)": "温度因子 - 高斯分布，15-20°C最优",
                "f(W)": "湿润时长因子 - 逻辑斯蒂曲线，>6小时快速上升",
                "f(S)": "孢子浓度因子 - Michaelis-Menten饱和曲线",
                "f(Rg)": "抗性调节系数 - 根据品种抗性级别调整",
                "f(C)": "累积效应因子 - 连续湿润天数的影响",
            },
        })

        return round(risk_index, 2), round(infection_probability, 4), details
