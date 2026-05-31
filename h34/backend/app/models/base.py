from abc import ABC, abstractmethod
from typing import Tuple, Dict, Optional
import numpy as np


class DiseaseModel(ABC):
    """病害预测模型抽象基类

    所有病害预测模型必须继承此类并实现抽象方法。
    定义了病害风险计算的通用接口。
    """

    model_name: str = "DiseaseModel"
    model_description: str = "病害预测模型基类"
    target_disease: str = "Unknown"
    target_crop: str = "Unknown"

    @abstractmethod
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
        """计算病害风险指数

        Args:
            temperature: 环境温度 (°C)
            humidity: 相对湿度 (%)
            rainfall: 降雨量 (mm)，可选
            leaf_wetness: 叶面湿润时长 (小时)，可选
            spore_concentration: 孢子浓度 (个/m³)，可选
            resistance_level: 品种抗性级别 (1-5，1为高感，5为高抗)，可选
            **kwargs: 其他模型特定参数

        Returns:
            Tuple[float, float, Dict]:
                - risk_index: 风险指数，范围 0-100
                - infection_probability: 感染概率，范围 0-1
                - details: 详细计算过程和中间结果
        """
        pass

    def get_model_info(self) -> Dict:
        """获取模型基本信息

        Returns:
            Dict: 包含模型名称、描述、适用作物和病害的字典
        """
        return {
            "model_name": self.model_name,
            "model_description": self.model_description,
            "target_disease": self.target_disease,
            "target_crop": self.target_crop,
        }

    def validate_inputs(
        self,
        temperature: float,
        humidity: float,
        rainfall: Optional[float] = None,
        leaf_wetness: Optional[float] = None,
        spore_concentration: Optional[float] = None,
        resistance_level: Optional[int] = None,
        **kwargs
    ) -> Tuple[bool, str]:
        """验证输入参数的有效性

        Args:
            temperature: 环境温度 (°C)
            humidity: 相对湿度 (%)
            rainfall: 降雨量 (mm)，可选
            leaf_wetness: 叶面湿润时长 (小时)，可选
            spore_concentration: 孢子浓度 (个/m³)，可选
            resistance_level: 品种抗性级别 (1-5)，可选
            **kwargs: 其他参数

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        if not isinstance(temperature, (int, float)) or np.isnan(temperature):
            return False, "温度必须为有效数值"
        if temperature < -50 or temperature > 60:
            return False, f"温度 {temperature}°C 超出合理范围 (-50°C ~ 60°C)"

        if not isinstance(humidity, (int, float)) or np.isnan(humidity):
            return False, "湿度必须为有效数值"
        if humidity < 0 or humidity > 100:
            return False, f"湿度 {humidity}% 超出合理范围 (0% ~ 100%)"

        if rainfall is not None:
            if not isinstance(rainfall, (int, float)) or np.isnan(rainfall):
                return False, "降雨量必须为有效数值"
            if rainfall < 0:
                return False, f"降雨量 {rainfall}mm 不能为负值"

        if leaf_wetness is not None:
            if not isinstance(leaf_wetness, (int, float)) or np.isnan(leaf_wetness):
                return False, "叶面湿润时长必须为有效数值"
            if leaf_wetness < 0 or leaf_wetness > 24:
                return False, f"叶面湿润时长 {leaf_wetness}小时 超出合理范围 (0 ~ 24小时)"

        if spore_concentration is not None:
            if not isinstance(spore_concentration, (int, float)) or np.isnan(spore_concentration):
                return False, "孢子浓度必须为有效数值"
            if spore_concentration < 0:
                return False, f"孢子浓度 {spore_concentration} 不能为负值"

        if resistance_level is not None:
            if not isinstance(resistance_level, int):
                return False, "抗性级别必须为整数"
            if resistance_level < 1:
                return False, f"抗性级别 {resistance_level} 必须大于等于 1"

        return True, "参数验证通过"
