"""
蒙特卡洛不确定度分析模块
Monte Carlo Uncertainty Analysis Module

功能：
- 输入参数不确定性建模
- 蒙特卡洛采样
- 不确定度传播分析
- 置信区间计算
- 灵敏度分析
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Callable, Union
import numpy as np
from datetime import datetime
from scipy import stats

from ..power.power_predictor import (
    PowerPredictor, PowerPredictionResult, AttitudePoint
)
from ..orbit.tle_propagator import TLEData
from ..utils.constants import DEFAULT_MC_SAMPLES, DEFAULT_CONFIDENCE_LEVEL


@dataclass
class UncertaintyParameter:
    """不确定性参数定义"""
    name: str
    nominal_value: float
    distribution: str  # 'normal', 'uniform', 'triangular', 'lognormal'
    params: Dict  # 分布参数, 如 {'std': 0.1} 或 {'min': 0.9, 'max': 1.1}
    description: str = ""

    def sample(self, n_samples: int) -> np.ndarray:
        """
        生成参数样本
        
        参数:
            n_samples: 样本数量
            
        返回:
            参数样本数组
        """
        if self.distribution == 'normal':
            std = self.params.get('std', self.nominal_value * 0.05)
            return np.random.normal(self.nominal_value, std, n_samples)
        
        elif self.distribution == 'uniform':
            min_val = self.params.get('min', self.nominal_value * 0.9)
            max_val = self.params.get('max', self.nominal_value * 1.1)
            return np.random.uniform(min_val, max_val, n_samples)
        
        elif self.distribution == 'triangular':
            min_val = self.params.get('min', self.nominal_value * 0.9)
            max_val = self.params.get('max', self.nominal_value * 1.1)
            mode = self.params.get('mode', self.nominal_value)
            return np.random.triangular(min_val, mode, max_val, n_samples)
        
        elif self.distribution == 'lognormal':
            sigma = self.params.get('sigma', 0.05)
            mu = np.log(self.nominal_value) - sigma ** 2 / 2
            return np.random.lognormal(mu, sigma, n_samples)
        
        else:
            return np.full(n_samples, self.nominal_value)


@dataclass
class UncertaintyConfig:
    """不确定性分析配置"""
    parameters: List[UncertaintyParameter] = field(default_factory=list)
    n_samples: int = DEFAULT_MC_SAMPLES
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    random_seed: Optional[int] = None

    def add_parameter(self, param: UncertaintyParameter):
        """添加不确定性参数"""
        self.parameters.append(param)


@dataclass
class UncertaintyResult:
    """不确定度分析结果"""
    parameter_name: str
    nominal_value: float
    mean: float
    std: float
    variance: float
    confidence_interval: Tuple[float, float]
    confidence_level: float
    percentiles: Dict[float, float]  # {5: val, 25: val, 50: val, 75: val, 95: val}
    samples: np.ndarray
    skewness: float
    kurtosis: float


@dataclass
class MonteCarloResult:
    """蒙特卡洛分析完整结果"""
    time_points: List[datetime]
    current_uncertainty: List[UncertaintyResult]
    power_uncertainty: List[UncertaintyResult]
    voltage_uncertainty: List[UncertaintyResult]
    irradiance_uncertainty: List[UncertaintyResult]
    temperature_uncertainty: List[UncertaintyResult]
    all_samples: Dict[str, np.ndarray]  # {param_name: samples}
    sensitivity_indices: Dict[str, float]
    n_samples: int
    confidence_level: float
    nominal_result: PowerPredictionResult


class MonteCarloAnalyzer:
    """
    蒙特卡洛不确定度分析器
    执行输入参数的不确定度传播分析
    """

    def __init__(self, 
                 power_predictor: PowerPredictor,
                 uncertainty_config: UncertaintyConfig = None):
        """
        初始化蒙特卡洛分析器
        
        参数:
            power_predictor: 功率预测器实例
            uncertainty_config: 不确定性配置
        """
        self.predictor = power_predictor
        self.config = uncertainty_config or UncertaintyConfig()

    def setup_default_uncertainties(self):
        """
        设置默认的不确定性参数
        包含所有主要输入参数的典型不确定度
        """
        params = [
            UncertaintyParameter(
                name='solar_constant',
                nominal_value=1361.0,
                distribution='normal',
                params={'std': 5.0},
                description='太阳常数不确定度 (W/m^2)'
            ),
            UncertaintyParameter(
                name='cell_efficiency',
                nominal_value=0.225,
                distribution='normal',
                params={'std': 0.01},
                description='电池转换效率不确定度'
            ),
            UncertaintyParameter(
                name='I_sc_ref',
                nominal_value=8.6,
                distribution='normal',
                params={'std': 0.15},
                description='参考短路电流不确定度 (A)'
            ),
            UncertaintyParameter(
                name='V_oc_ref',
                nominal_value=0.65,
                distribution='normal',
                params={'std': 0.01},
                description='参考开路电压不确定度 (V)'
            ),
            UncertaintyParameter(
                name='series_resistance',
                nominal_value=0.004,
                distribution='uniform',
                params={'min': 0.003, 'max': 0.005},
                description='串联电阻不确定度 (Ω)'
            ),
            UncertaintyParameter(
                name='shunt_resistance',
                nominal_value=500.0,
                distribution='lognormal',
                params={'sigma': 0.1},
                description='并联电阻不确定度 (Ω)'
            ),
            UncertaintyParameter(
                name='albedo',
                nominal_value=0.30,
                distribution='uniform',
                params={'min': 0.25, 'max': 0.35},
                description='地球反照率不确定度'
            ),
            UncertaintyParameter(
                name='emissivity',
                nominal_value=0.85,
                distribution='normal',
                params={'std': 0.03},
                description='表面发射率不确定度'
            ),
            UncertaintyParameter(
                name='absorptivity',
                nominal_value=0.92,
                distribution='normal',
                params={'std': 0.02},
                description='太阳吸收率不确定度'
            ),
            UncertaintyParameter(
                name='ddd_factor',
                nominal_value=1.5e-10,
                distribution='lognormal',
                params={'sigma': 0.3},
                description='位移损伤剂量系数不确定度'
            ),
            UncertaintyParameter(
                name='attitude_error',
                nominal_value=0.0,
                distribution='normal',
                params={'std': 0.035},  # 约2度
                description='帆板姿态指向误差 (rad)'
            ),
            UncertaintyParameter(
                name='occlusion_error',
                nominal_value=0.0,
                distribution='normal',
                params={'std': 0.02},
                description='遮挡计算误差因子'
            ),
        ]
        
        for param in params:
            self.config.add_parameter(param)

    def _get_param_value(self, 
                          param_name: str, 
                          sample: float,
                          base_params: Dict) -> float:
        """
        根据样本值获取参数实际值
        
        参数:
            param_name: 参数名称
            sample: 样本值
            base_params: 基准参数
            
        返回:
            参数实际值
        """
        if param_name == 'solar_constant':
            return sample
        elif param_name == 'cell_efficiency':
            return sample
        elif param_name == 'I_sc_ref':
            base_params['cell_params'].I_sc_ref = sample
            return sample
        elif param_name == 'V_oc_ref':
            base_params['cell_params'].V_oc_ref = sample
            return sample
        elif param_name == 'series_resistance':
            base_params['cell_params'].R_s = sample
            return sample
        elif param_name == 'shunt_resistance':
            base_params['cell_params'].R_sh = sample
            return sample
        elif param_name == 'albedo':
            base_params['albedo'] = sample
            return sample
        elif param_name == 'emissivity':
            base_params['emissivity'] = sample
            return sample
        elif param_name == 'absorptivity':
            base_params['absorptivity'] = sample
            return sample
        elif param_name == 'ddd_factor':
            base_params['ddd_factor'] = sample
            return sample
        elif param_name == 'attitude_error':
            base_params['attitude_error'] = sample
            return sample
        elif param_name == 'occlusion_error':
            base_params['occlusion_error'] = sample
            return sample
        
        return sample

    def _generate_param_samples(self) -> Dict[str, np.ndarray]:
        """
        生成所有参数的样本
        
        返回:
            参数样本字典 {param_name: samples_array}
        """
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)
        
        samples = {}
        for param in self.config.parameters:
            samples[param.name] = param.sample(self.config.n_samples)
        
        return samples

    def _analyze_uncertainty(self, 
                              values: np.ndarray, 
                              param_name: str,
                              nominal_value: float) -> UncertaintyResult:
        """
        分析一组值的统计特性
        
        参数:
            values: 值数组
            param_name: 参数名称
            nominal_value: 标称值
            
        返回:
            UncertaintyResult
        """
        values = np.array(values)
        mean = np.mean(values)
        std = np.std(values, ddof=1)
        variance = std ** 2
        
        alpha = 1 - self.config.confidence_level
        ci_lower = np.percentile(values, 100 * alpha / 2)
        ci_upper = np.percentile(values, 100 * (1 - alpha / 2))
        
        percentiles = {
            5: np.percentile(values, 5),
            25: np.percentile(values, 25),
            50: np.percentile(values, 50),
            75: np.percentile(values, 75),
            95: np.percentile(values, 95),
        }
        
        skewness = stats.skew(values)
        kurtosis = stats.kurtosis(values)
        
        return UncertaintyResult(
            parameter_name=param_name,
            nominal_value=nominal_value,
            mean=mean,
            std=std,
            variance=variance,
            confidence_interval=(ci_lower, ci_upper),
            confidence_level=self.config.confidence_level,
            percentiles=percentiles,
            samples=values,
            skewness=skewness,
            kurtosis=kurtosis
        )

    def _calculate_sensitivity(self, 
                                 all_samples: Dict[str, np.ndarray],
                                 output_samples: np.ndarray) -> Dict[str, float]:
        """
        计算灵敏度指数 (Spearman秩相关系数)
        
        参数:
            all_samples: 所有输入参数样本
            output_samples: 输出样本
            
        返回:
            灵敏度指数字典 {param_name: sensitivity}
        """
        sensitivity = {}
        output = np.array(output_samples)
        
        for param_name, samples in all_samples.items():
            if np.std(samples) > 0 and np.std(output) > 0:
                corr, _ = stats.spearmanr(samples, output)
                sensitivity[param_name] = abs(corr)
            else:
                sensitivity[param_name] = 0.0
        
        return sensitivity

    def analyze(self,
                start_time: datetime,
                end_time: datetime,
                time_step_sec: float = 1.0,
                attitude_sequence: List[AttitudePoint] = None,
                show_progress: bool = True) -> MonteCarloResult:
        """
        执行蒙特卡洛不确定度分析
        
        参数:
            start_time: 开始时间
            end_time: 结束时间
            time_step_sec: 时间步长 (秒)
            attitude_sequence: 姿态序列
            show_progress: 是否显示进度
            
        返回:
            MonteCarloResult
        """
        if len(self.config.parameters) == 0:
            self.setup_default_uncertainties()
        
        n_samples = self.config.n_samples
        if show_progress:
            print(f"开始蒙特卡洛分析，样本数: {n_samples}")
        
        nominal_result = self.predictor.predict(
            start_time, end_time, time_step_sec, attitude_sequence
        )
        
        time_points = [pt.time for pt in nominal_result.time_series]
        n_time_points = len(time_points)
        
        all_samples = self._generate_param_samples()
        
        all_currents = np.zeros((n_samples, n_time_points))
        all_powers = np.zeros((n_samples, n_time_points))
        all_voltages = np.zeros((n_samples, n_time_points))
        all_irradiances = np.zeros((n_samples, n_time_points))
        all_temperatures = np.zeros((n_samples, n_time_points))
        
        from copy import deepcopy
        
        for sample_idx in range(n_samples):
            if show_progress and (sample_idx + 1) % 100 == 0:
                print(f"  处理样本 {sample_idx + 1}/{n_samples}")
            
            base_params = {
                'cell_params': deepcopy(self.predictor._array_config.cell_params),
                'albedo': 0.30,
                'emissivity': 0.85,
                'absorptivity': 0.92,
                'ddd_factor': 1.5e-10,
                'attitude_error': 0.0,
                'occlusion_error': 0.0,
            }
            
            for param in self.config.parameters:
                sample_val = all_samples[param.name][sample_idx]
                self._get_param_value(param.name, sample_val, base_params)
            
            modified_attitude = attitude_sequence
            if base_params['attitude_error'] != 0 and attitude_sequence is not None:
                modified_attitude = []
                for ap in attitude_sequence:
                    error_axis = np.random.randn(3)
                    error_axis /= np.linalg.norm(error_axis)
                    error_angle = base_params['attitude_error']
                    
                    R = np.eye(3) + np.sin(error_angle) * np.array([
                        [0, -error_axis[2], error_axis[1]],
                        [error_axis[2], 0, -error_axis[0]],
                        [-error_axis[1], error_axis[0], 0]
                    ]) + (1 - np.cos(error_angle)) * np.outer(error_axis, error_axis)
                    
                    new_normal = R @ ap.sa_normal
                    new_normal /= np.linalg.norm(new_normal)
                    
                    modified_attitude.append(AttitudePoint(
                        time=ap.time,
                        sa_normal=new_normal
                    ))
            
            try:
                result = self.predictor.predict(
                    start_time, end_time, time_step_sec, modified_attitude
                )
                
                for t_idx, pt in enumerate(result.time_series):
                    occlusion_correction = 1.0 - base_params['occlusion_error']
                    all_currents[sample_idx, t_idx] = pt.array_current
                    all_powers[sample_idx, t_idx] = pt.array_power
                    all_voltages[sample_idx, t_idx] = pt.array_voltage
                    all_irradiances[sample_idx, t_idx] = pt.effective_irradiance * occlusion_correction
                    all_temperatures[sample_idx, t_idx] = pt.cell_temperature
            except Exception as e:
                if show_progress:
                    print(f"  样本 {sample_idx} 计算失败: {e}")
                continue
        
        if show_progress:
            print("分析统计特性...")
        
        current_uncertainty = []
        power_uncertainty = []
        voltage_uncertainty = []
        irradiance_uncertainty = []
        temperature_uncertainty = []
        
        for t_idx in range(n_time_points):
            curr_nominal = nominal_result.time_series[t_idx].array_current
            power_nominal = nominal_result.time_series[t_idx].array_power
            volt_nominal = nominal_result.time_series[t_idx].array_voltage
            irr_nominal = nominal_result.time_series[t_idx].effective_irradiance
            temp_nominal = nominal_result.time_series[t_idx].cell_temperature
            
            current_uncertainty.append(self._analyze_uncertainty(
                all_currents[:, t_idx], 'current', curr_nominal
            ))
            power_uncertainty.append(self._analyze_uncertainty(
                all_powers[:, t_idx], 'power', power_nominal
            ))
            voltage_uncertainty.append(self._analyze_uncertainty(
                all_voltages[:, t_idx], 'voltage', volt_nominal
            ))
            irradiance_uncertainty.append(self._analyze_uncertainty(
                all_irradiances[:, t_idx], 'irradiance', irr_nominal
            ))
            temperature_uncertainty.append(self._analyze_uncertainty(
                all_temperatures[:, t_idx], 'temperature', temp_nominal
            ))
        
        avg_powers = np.mean(all_powers, axis=1)
        sensitivity = self._calculate_sensitivity(all_samples, avg_powers)
        
        if show_progress:
            print("蒙特卡洛分析完成！")
        
        return MonteCarloResult(
            time_points=time_points,
            current_uncertainty=current_uncertainty,
            power_uncertainty=power_uncertainty,
            voltage_uncertainty=voltage_uncertainty,
            irradiance_uncertainty=irradiance_uncertainty,
            temperature_uncertainty=temperature_uncertainty,
            all_samples=all_samples,
            sensitivity_indices=sensitivity,
            n_samples=n_samples,
            confidence_level=self.config.confidence_level,
            nominal_result=nominal_result
        )

    def get_uncertainty_bounds(self,
                                mc_result: MonteCarloResult,
                                quantity: str = 'power') -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        获取不确定度边界
        
        参数:
            mc_result: 蒙特卡洛结果
            quantity: 物理量类型 ('current', 'power', 'voltage', 'irradiance', 'temperature')
            
        返回:
            (标称值, 下界, 上界) 数组
        """
        uncertainty_list = {
            'current': mc_result.current_uncertainty,
            'power': mc_result.power_uncertainty,
            'voltage': mc_result.voltage_uncertainty,
            'irradiance': mc_result.sensitivity_indices,
            'temperature': mc_result.temperature_uncertainty,
        }[quantity]
        
        nominal = np.array([u.nominal_value for u in uncertainty_list])
        lower = np.array([u.confidence_interval[0] for u in uncertainty_list])
        upper = np.array([u.confidence_interval[1] for u in uncertainty_list])
        
        return nominal, lower, upper
