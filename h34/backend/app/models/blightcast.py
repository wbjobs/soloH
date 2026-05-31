from typing import Tuple, Dict, Optional
import numpy as np
from .base import DiseaseModel


class BlightcastModel(DiseaseModel):
    """马铃薯晚疫病Blightcast预测模型

    Blightcast模型由美国马铃薯研究中心开发，是全球广泛使用的
    马铃薯晚疫病预测系统。该模型基于温度和相对湿度的组合计算
    感染严重值（Severity Value, SV），并考虑连续湿润条件的累积效应。

    参考文献:
    - Hyre, R. A. (1954). Forecasting late blight of potato and tomato.
      Plant Disease Reporter, 38(12), 583-588.
    - Wallin, J. R. (1962). A method of forecasting late blight severity.
      Plant Disease Reporter, 46(10), 717-721.
    - Cooke, B. M., et al. (2006). The epidemiology of plant diseases. Springer.

    核心算法:
    1. 根据温度(T)和相对湿度(RH)计算每日严重值SV
    2. 计算连续湿润天数的累积严重值CSV
    3. 结合孢子浓度和品种抗性计算最终风险

    严重值(SV)矩阵 (行=温度，列=湿度):
    - SV < 6: 低风险
    - 6 ≤ SV < 18: 中风险
    - SV ≥ 18: 高风险
    """

    model_name: str = "BlightcastModel"
    model_description: str = "马铃薯晚疫病Blightcast预测模型，基于温湿度组合和连续湿润条件的经典预测系统"
    target_disease: str = "马铃薯晚疫病"
    target_crop: str = "马铃薯"

    def __init__(self):
        self._temp_bins = np.array([0, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31])
        self._rh_bins = np.array([0, 70, 75, 80, 85, 90, 95, 101])

        self._sv_matrix = np.array([
            [0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 1, 2, 3],
            [0, 0, 1, 2, 3, 5, 7],
            [0, 1, 2, 4, 6, 9, 12],
            [0, 2, 4, 7, 10, 14, 18],
            [0, 3, 6, 10, 15, 20, 24],
            [0, 2, 5, 9, 14, 18, 22],
            [0, 1, 3, 6, 10, 14, 17],
            [0, 0, 1, 3, 5, 8, 10],
            [0, 0, 0, 0, 1, 2, 3],
        ])

        self._high_risk_threshold = 18.0
        self._medium_risk_threshold = 6.0

    def _get_severity_value(self, temperature: float, humidity: float) -> float:
        """计算单日严重值 (Severity Value, SV)

        根据温度和相对湿度，通过查表和双线性插值计算SV值。
        SV范围: 0-24

        Args:
            temperature: 环境温度 (°C)
            humidity: 相对湿度 (%)

        Returns:
            float: 单日严重值 SV
        """
        if temperature < 0 or temperature > 30 or humidity < 70:
            return 0.0

        temp_idx = np.searchsorted(self._temp_bins, temperature, side="right") - 1
        temp_idx = np.clip(temp_idx, 0, len(self._temp_bins) - 2)

        rh_idx = np.searchsorted(self._rh_bins, humidity, side="right") - 1
        rh_idx = np.clip(rh_idx, 0, len(self._rh_bins) - 2)

        t1 = self._temp_bins[temp_idx]
        t2 = self._temp_bins[temp_idx + 1]
        h1 = self._rh_bins[rh_idx]
        h2 = self._rh_bins[rh_idx + 1]

        if t2 == t1:
            ft = 0
        else:
            ft = (temperature - t1) / (t2 - t1)

        if h2 == h1:
            fh = 0
        else:
            fh = (humidity - h1) / (h2 - h1)

        sv00 = self._sv_matrix[temp_idx, rh_idx]
        sv10 = self._sv_matrix[temp_idx + 1, rh_idx] if temp_idx + 1 < len(self._sv_matrix) else sv00
        sv01 = self._sv_matrix[temp_idx, rh_idx + 1] if rh_idx + 1 < self._sv_matrix.shape[1] else sv00
        sv11 = self._sv_matrix[temp_idx + 1, rh_idx + 1] if (temp_idx + 1 < len(self._sv_matrix) and rh_idx + 1 < self._sv_matrix.shape[1]) else sv00

        sv = (1 - ft) * (1 - fh) * sv00 + ft * (1 - fh) * sv10 + (1 - ft) * fh * sv01 + ft * fh * sv11

        return float(sv)

    def _cumulative_severity(self, daily_sv: float, consecutive_days: int, history_sv: Optional[np.ndarray] = None) -> float:
        """计算累积严重值 (Cumulative Severity Value, CSV)

        考虑连续湿润天数的累积效应，近期的SV值权重更高。

        权重公式: w_i = 0.5^((n-1-i)/3)
        其中 n 为连续天数，i 为第i天 (0=今天, n-1=n天前)

        Args:
            daily_sv: 当日严重值
            consecutive_days: 连续湿润天数
            history_sv: 历史SV值数组（从最近到最远）

        Returns:
            float: 累积严重值 CSV
        """
        if consecutive_days <= 1:
            return daily_sv

        if history_sv is not None and len(history_sv) > 0:
            n = min(consecutive_days, len(history_sv) + 1)
            sv_values = np.zeros(n)
            sv_values[0] = daily_sv
            for i in range(1, n):
                if i - 1 < len(history_sv):
                    sv_values[i] = history_sv[i - 1]
                else:
                    sv_values[i] = daily_sv
        else:
            sv_values = np.full(consecutive_days, daily_sv)

        weights = np.power(0.5, np.arange(len(sv_values)) / 3.0)
        weights = weights / weights.sum()

        csv = float(np.sum(sv_values * weights))
        return csv

    def _spore_weight_factor(self, spore_concentration: float) -> float:
        """计算孢子浓度加权因子

        采用S型曲线描述孢子浓度对感染的影响：
        f(S) = 1 / {1 + exp[-0.03 × (S - 50)]}

        Args:
            spore_concentration: 孢子浓度 (个/m³)

        Returns:
            float: 孢子加权因子，范围 0.2-1.2
        """
        if spore_concentration <= 0:
            return 0.2

        k = 0.03
        midpoint = 50.0
        exponent = -k * (spore_concentration - midpoint)
        base = 1.0 / (1.0 + np.exp(exponent))

        return float(0.2 + base * 1.0)

    def _resistance_factor(self, resistance_level: int) -> float:
        """计算品种抗性调节因子

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
        """计算马铃薯晚疫病风险指数

        基于Blightcast模型，综合温湿度组合、连续湿润天数、
        孢子浓度和品种抗性计算感染风险。

        Args:
            temperature: 环境温度 (°C)
            humidity: 相对湿度 (%)
            rainfall: 降雨量 (mm)，可选，用于辅助判断湿润条件
            leaf_wetness: 叶面湿润时长 (小时)，可选，用于确认感染条件
            spore_concentration: 孢子浓度 (个/m³)，None时默认中等值
            resistance_level: 品种抗性级别 (1-5)，None时默认感病(2)
            **kwargs: 附加参数
                - consecutive_wet_days: 连续湿润天数，默认1
                - history_sv: 历史严重值数组
                - hours_rh_gt_90: 相对湿度>90%的小时数

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

        if spore_concentration is None:
            spore_concentration = 40.0
            details["default_spore_concentration"] = spore_concentration

        if resistance_level is None:
            resistance_level = 2
            details["default_resistance_level"] = resistance_level

        consecutive_days = kwargs.get("consecutive_wet_days", 1)
        history_sv = kwargs.get("history_sv", None)
        hours_rh_gt_90 = kwargs.get("hours_rh_gt_90", None)

        effective_humidity = humidity
        if hours_rh_gt_90 is not None:
            if hours_rh_gt_90 >= 10:
                effective_humidity = max(humidity, 92.0)
            elif hours_rh_gt_90 >= 5:
                effective_humidity = max(humidity, 88.0)
            details["effective_humidity"] = effective_humidity

        if rainfall is not None and rainfall > 0:
            effective_humidity = max(effective_humidity, min(100.0, humidity + 5.0))
            details["rainfall_humidity_adjustment"] = effective_humidity

        if leaf_wetness is not None:
            adjusted_wetness = leaf_wetness
            if temperature > 25:
                evaporation_factor = max(0.3, 1.0 - (temperature - 25) * 0.07)
                adjusted_wetness *= evaporation_factor
                details["high_temp_evaporation_correction"] = round(evaporation_factor, 4)

            sat_vp = 0.6108 * np.exp(17.27 * temperature / (temperature + 237.3))
            actual_vp = sat_vp * (effective_humidity / 100.0)
            vpd = sat_vp - actual_vp
            if vpd > 1.2:
                vpd_factor = max(0.4, 1.0 - (vpd - 1.2) * 0.12)
                adjusted_wetness *= vpd_factor
                details["vpd_correction"] = round(vpd_factor, 4)

            adjusted_wetness = max(0.0, adjusted_wetness)
            details["adjusted_leaf_wetness"] = round(adjusted_wetness, 2)

            if adjusted_wetness >= 12:
                effective_humidity = max(effective_humidity, 95.0)
            elif adjusted_wetness >= 6:
                effective_humidity = max(effective_humidity, 88.0)
            elif adjusted_wetness >= 3:
                effective_humidity = max(effective_humidity, 82.0)
            details["wetness_humidity_adjustment"] = effective_humidity

        daily_sv = self._get_severity_value(temperature, effective_humidity)
        csv = self._cumulative_severity(daily_sv, consecutive_days, history_sv)
        spore_factor = self._spore_weight_factor(spore_concentration)
        resistance_factor = self._resistance_factor(resistance_level)

        adjusted_csv = csv * spore_factor * resistance_factor

        max_possible_csv = 24.0 * 1.2 * 1.3
        risk_index = min(100.0, (adjusted_csv / max_possible_csv) * 100.0)

        if adjusted_csv >= self._high_risk_threshold:
            infection_probability = min(1.0, 0.6 + (adjusted_csv - 18) / 24.0)
        elif adjusted_csv >= self._medium_risk_threshold:
            infection_probability = 0.2 + (adjusted_csv - 6) / 30.0
        else:
            infection_probability = adjusted_csv / 30.0

        infection_probability = min(1.0, max(0.0, infection_probability))

        from app.core.constants import RISK_THRESHOLDS, get_risk_level
        risk_level = get_risk_level(risk_index, use_chinese=True)

        if risk_index >= RISK_THRESHOLDS["high"] or adjusted_csv >= 18:
            recommendation = "立即喷施保护性+治疗性杀菌剂，5-7天后复喷"
        elif risk_index >= RISK_THRESHOLDS["medium"] or adjusted_csv >= 10:
            recommendation = "喷施保护性杀菌剂，加强监测，雨后及时补喷"
        elif risk_index >= RISK_THRESHOLDS["low"] or adjusted_csv >= 4:
            recommendation = "定期巡查，及时清除中心病株，保持田间通风"
        else:
            recommendation = "无需特殊防治，注意排水降湿"

        details.update({
            "factors": {
                "daily_severity_value": round(daily_sv, 4),
                "cumulative_severity_value": round(csv, 4),
                "spore_weight_factor": round(spore_factor, 4),
                "resistance_factor": round(resistance_factor, 4),
                "adjusted_csv": round(adjusted_csv, 4),
            },
            "risk_thresholds": {
                "low": RISK_THRESHOLDS["low"],
                "medium": RISK_THRESHOLDS["medium"],
                "high": RISK_THRESHOLDS["high"],
                "extreme": RISK_THRESHOLDS["extreme"],
            },
            "risk_level": risk_level,
            "recommendation": recommendation,
            "infection_conditions": {
                "temperature_suitable": temperature >= 7 and temperature <= 25,
                "humidity_sufficient": effective_humidity >= 85,
                "continuous_wet_days": consecutive_days,
            },
            "algorithm": "Blightcast严重值矩阵 + 双线性插值 + 加权累积",
            "algorithm_steps": {
                "step1": "根据温度和相对湿度通过查表和双线性插值计算单日严重值(SV)",
                "step2": "考虑连续湿润天数，使用指数衰减权重计算累积严重值(CSV)",
                "step3": "根据孢子浓度应用加权因子",
                "step4": "根据品种抗性级别应用调节系数",
                "step5": "将调整后的CSV归一化为0-100的风险指数",
            },
            "sv_matrix_reference": {
                "description": "严重值矩阵 (行:温度0-30°C, 列:相对湿度70-100%)",
                "temperature_bins": [0, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31],
                "humidity_bins": [0, 70, 75, 80, 85, 90, 95, 101],
                "max_sv": 24,
            },
        })

        return round(risk_index, 2), round(infection_probability, 4), details
