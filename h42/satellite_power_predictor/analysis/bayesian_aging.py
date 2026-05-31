"""
贝叶斯老化预测模块
Bayesian Aging Prediction Module

功能：
- 基于遥测数据的贝叶斯参数更新
- 太阳能电池老化模型的实时校正
- 剩余寿命预测（RUL）
- 不确定性量化
- 多源数据融合（功率、电流、电压、温度）
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Union
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm, gamma, beta
from scipy.optimize import minimize


@dataclass
class AgingParameters:
    """
    老化模型参数
    
    描述太阳能电池阵列的老化状态参数
    """
    # 基础老化参数
    ddd_coefficient: float = 1.0e-9  # DDD系数 (1/(MeV/g))
    ao_erosion_coefficient: float = 1.0e-24  # 原子氧侵蚀系数 (cm³/atom)
    thermal_cycle_factor: float = 1.0e-6  # 热循环因子 (1/周期)
    uv_degradation_rate: float = 1.0e-9  # UV退化率 (1/s)
    
    # 模型不确定性参数
    process_noise: float = 0.01  # 过程噪声标准差
    measurement_noise: float = 0.02  # 测量噪声标准差
    
    # 剩余因子先验
    remaining_factor_prior_mean: float = 1.0
    remaining_factor_prior_std: float = 0.1
    
    # 参数协方差矩阵（对数空间）
    covariance_matrix: np.ndarray = field(default_factory=lambda: np.eye(4) * 0.01)


@dataclass
class TelemetryObservation:
    """
    遥测观测数据
    
    包含单次观测的所有相关数据
    """
    time: datetime  # 观测时间
    array_power: float  # 观测功率 (W)
    array_current: float  # 观测电流 (A)
    array_voltage: float  # 观测电压 (V)
    cell_temperature: float  # 电池温度 (K)
    solar_irradiance: float  # 太阳辐照度 (W/m²)
    incidence_angle: float  # 太阳光入射角 (deg)
    eclipse_factor: float = 0.0  # 地影因子 (0-1)
    measurement_uncertainty: float = 0.02  # 测量不确定度


@dataclass
class BayesianUpdateResult:
    """
    贝叶斯更新结果
    
    包含单次更新后的参数后验分布
    """
    time: datetime  # 更新时间
    parameters: AgingParameters  # 更新后的参数
    remaining_factor_posterior_mean: float  # 剩余因子后验均值
    remaining_factor_posterior_std: float  # 剩余因子后验标准差
    log_likelihood: float  # 对数似然
    innovation: float  # 新息（观测值与预测值之差）
    innovation_covariance: float  # 新息协方差
    kalman_gain: np.ndarray  # 卡尔曼增益
    parameter_uncertainty_reduction: np.ndarray  # 参数不确定度降低比例


@dataclass
class RemainingUsefulLife:
    """
    剩余使用寿命预测
    
    包含RUL的概率分布信息
    """
    mean_rul_days: float  # 平均剩余寿命 (天)
    median_rul_days: float  # 中位剩余寿命 (天)
    std_rul_days: float  # 剩余寿命标准差 (天)
    confidence_95_low: float  # 95%置信区间下限 (天)
    confidence_95_high: float  # 95%置信区间上限 (天)
    failure_threshold: float  # 失效阈值（剩余因子）
    time_of_prediction: datetime  # 预测时间


@dataclass
class AgingTrend:
    """
    老化趋势数据
    
    包含一段时间的老化状态序列
    """
    times: List[datetime]  # 时间点列表
    remaining_factor_mean: List[float]  # 剩余因子均值序列
    remaining_factor_std: List[float]  # 剩余因子标准差序列
    predicted_power: List[float]  # 预测功率序列 (W)
    measured_power: List[float]  # 实测功率序列 (W)
    parameter_evolution: List[Dict[str, float]]  # 参数演化序列


class BayesianAgingPredictor:
    """
    贝叶斯老化预测器
    
    基于遥测数据实时更新老化模型参数，预测剩余寿命
    
    方法：
    - 扩展卡尔曼滤波（EKF）用于非线性模型的参数估计
    - 马尔可夫链蒙特卡洛（MCMC）用于复杂后验分布采样
    - 贝叶斯模型平均用于多模型融合
    - 失效物理模型（PoF）用于RUL预测
    """
    
    def __init__(self,
                 initial_parameters: AgingParameters = None,
                 array_area: float = 3.0,
                 reference_efficiency: float = 0.225,
                 failure_threshold: float = 0.7):
        """
        初始化贝叶斯老化预测器
        
        参数:
            initial_parameters: 初始老化参数
            array_area: 太阳能阵列面积 (m²)
            reference_efficiency: 参考效率 (STC)
            failure_threshold: 失效阈值（剩余因子）
        """
        self.parameters = initial_parameters or AgingParameters()
        self.array_area = array_area
        self.reference_efficiency = reference_efficiency
        self.failure_threshold = failure_threshold
        
        # 历史数据存储
        self.observation_history: List[TelemetryObservation] = []
        self.update_history: List[BayesianUpdateResult] = []
        self.aging_trend = AgingTrend(
            times=[],
            remaining_factor_mean=[],
            remaining_factor_std=[],
            predicted_power=[],
            measured_power=[],
            parameter_evolution=[]
        )
        
        # 参数名称（用于协方差矩阵索引）
        self.param_names = [
            'ddd_coefficient',
            'ao_erosion_coefficient', 
            'thermal_cycle_factor',
            'uv_degradation_rate'
        ]
        
        # 粒子滤波器粒子（用于非线性/非高斯情况）
        self.particles: Optional[np.ndarray] = None
        self.particle_weights: Optional[np.ndarray] = None
        
    def predict_power(self,
                       observation: TelemetryObservation,
                       remaining_factor: float = None) -> float:
        """
        预测太阳能阵列功率
        
        参数:
            observation: 观测条件
            remaining_factor: 剩余因子（如果为None则使用当前参数计算）
            
        返回:
            预测功率 (W)
        """
        if remaining_factor is None:
            remaining_factor = self.parameters.remaining_factor_prior_mean
        
        # 考虑入射角的有效辐照度
        cos_incidence = np.cos(np.radians(observation.incidence_angle))
        effective_irradiance = observation.solar_irradiance * cos_incidence
        
        # 温度修正
        temp_ref = 298.15
        temp_coeff = 1.0 - 0.005 * (observation.cell_temperature - temp_ref)
        
        # 地影因子
        sunlit_factor = 1.0 - observation.eclipse_factor
        
        # 理论功率
        theoretical_power = (effective_irradiance * self.array_area * 
                           self.reference_efficiency * temp_coeff * sunlit_factor)
        
        # 应用剩余因子
        predicted_power = theoretical_power * remaining_factor
        
        return max(0.0, predicted_power)
    
    def calculate_likelihood(self,
                              observation: TelemetryObservation,
                              predicted_power: float) -> float:
        """
        计算观测的对数似然
        
        参数:
            observation: 观测数据
            predicted_power: 预测功率
            
        返回:
            对数似然值
        """
        measurement_std = max(observation.measurement_uncertainty, 
                             self.parameters.measurement_noise) * predicted_power
        
        # 避免除零
        measurement_std = max(measurement_std, 0.1)
        
        # 正态分布对数似然
        log_likelihood = norm.logpdf(
            observation.array_power,
            loc=predicted_power,
            scale=measurement_std
        )
        
        return float(log_likelihood)
    
    def _calculate_jacobian(self,
                            observation: TelemetryObservation,
                            remaining_factor: float) -> np.ndarray:
        """
        计算观测方程关于参数的雅可比矩阵
        
        参数:
            observation: 观测条件
            remaining_factor: 当前剩余因子
            
        返回:
            雅可比矩阵 (1 x 4)
        """
        # 数值计算雅可比（简化实现）
        eps = 1e-8
        jacobian = np.zeros(4)
        
        base_power = self.predict_power(observation, remaining_factor)
        
        # 对每个参数求偏导
        for i, name in enumerate(self.param_names):
            old_val = getattr(self.parameters, name)
            setattr(self.parameters, name, old_val + eps)
            
            # 扰动后重新计算剩余因子
            new_remaining = remaining_factor * (1.0 - eps * old_val)
            new_power = self.predict_power(observation, new_remaining)
            
            jacobian[i] = (new_power - base_power) / eps
            
            # 恢复原值
            setattr(self.parameters, name, old_val)
        
        return jacobian.reshape(1, -1)
    
    def update_with_ekf(self,
                         observation: TelemetryObservation,
                         remaining_factor_estimate: float = None) -> BayesianUpdateResult:
        """
        使用扩展卡尔曼滤波（EKF）更新参数
        
        参数:
            observation: 遥测观测数据
            remaining_factor_estimate: 剩余因子估计值（可选）
            
        返回:
            BayesianUpdateResult
        """
        # 预测步骤
        if remaining_factor_estimate is None:
            remaining_factor_estimate = self.parameters.remaining_factor_prior_mean
        
        # 1. 预测功率
        predicted_power = self.predict_power(observation, remaining_factor_estimate)
        
        # 2. 计算雅可比矩阵
        H = self._calculate_jacobian(observation, remaining_factor_estimate)
        
        # 3. 预测协方差
        P = self.parameters.covariance_matrix
        Q = np.eye(4) * self.parameters.process_noise ** 2
        P_pred = P + Q
        
        # 4. 计算新息
        innovation = observation.array_power - predicted_power
        
        # 5. 计算新息协方差
        R = (observation.measurement_uncertainty * predicted_power) ** 2
        R = max(R, 0.1 ** 2)  # 最小协方差
        # 明确提取标量值 (1x1矩阵 → 标量)
        S_matrix = H @ P_pred @ H.T
        S = float(S_matrix[0, 0]) + R  # 转换为标量
        
        # 6. 计算卡尔曼增益
        K = P_pred @ H.T / S  # H是行向量，S是标量
        
        # 7. 更新参数
        param_update = K.flatten() * innovation
        
        # 约束参数为正值（使用对数空间更新）
        for i, name in enumerate(self.param_names):
            old_val = getattr(self.parameters, name)
            # 确保参数为正
            new_val = max(old_val * (1.0 + param_update[i] / max(old_val, 1e-12)), 1e-12)
            setattr(self.parameters, name, new_val)
        
        # 8. 更新协方差矩阵
        I = np.eye(4)
        P_new = (I - K @ H) @ P_pred
        
        # 保证协方差矩阵对称正定
        P_new = (P_new + P_new.T) / 2
        self.parameters.covariance_matrix = P_new
        
        # 9. 更新剩余因子的后验分布
        log_likelihood = self.calculate_likelihood(observation, predicted_power)
        
        # 根据观测更新剩余因子
        rf_std = self.parameters.remaining_factor_prior_std
        rf_innovation_std = abs(innovation / predicted_power) * remaining_factor_estimate
        combined_std = 1.0 / np.sqrt(1.0 / rf_std ** 2 + 1.0 / rf_innovation_std ** 2)
        
        kalman_gain_rf = (rf_std ** 2) / (rf_std ** 2 + rf_innovation_std ** 2)
        rf_posterior_mean = remaining_factor_estimate + kalman_gain_rf * (innovation / predicted_power) * remaining_factor_estimate
        rf_posterior_mean = max(0.0, min(1.0, rf_posterior_mean))
        
        # 计算参数不确定度降低
        old_diag = np.diag(P)
        new_diag = np.diag(P_new)
        uncertainty_reduction = (old_diag - new_diag) / old_diag
        
        # 创建结果
        result = BayesianUpdateResult(
            time=observation.time,
            parameters=self.parameters,
            remaining_factor_posterior_mean=rf_posterior_mean,
            remaining_factor_posterior_std=combined_std,
            log_likelihood=log_likelihood,
            innovation=innovation,
            innovation_covariance=float(S),
            kalman_gain=K.flatten(),
            parameter_uncertainty_reduction=uncertainty_reduction
        )
        
        # 更新内部状态
        self.parameters.remaining_factor_prior_mean = rf_posterior_mean
        self.parameters.remaining_factor_prior_std = combined_std
        
        # 记录历史
        self.observation_history.append(observation)
        self.update_history.append(result)
        
        # 更新老化趋势
        self.aging_trend.times.append(observation.time)
        self.aging_trend.remaining_factor_mean.append(rf_posterior_mean)
        self.aging_trend.remaining_factor_std.append(combined_std)
        self.aging_trend.predicted_power.append(predicted_power)
        self.aging_trend.measured_power.append(observation.array_power)
        self.aging_trend.parameter_evolution.append({
            name: getattr(self.parameters, name) for name in self.param_names
        })
        
        return result
    
    def batch_update(self,
                      observations: List[TelemetryObservation]) -> List[BayesianUpdateResult]:
        """
        批量更新（处理一系列观测数据）
        
        参数:
            observations: 观测数据列表
            
        返回:
            更新结果列表
        """
        results = []
        for obs in observations:
            result = self.update_with_ekf(obs)
            results.append(result)
        return results
    
    def predict_rul(self,
                     cumulative_degradation_rate: float = 1.0e-5,
                     mission_days_elapsed: float = 0.0,
                     n_samples: int = 10000) -> RemainingUsefulLife:
        """
        预测剩余使用寿命（RUL）
        
        参数:
            cumulative_degradation_rate: 累积退化率 (1/天)
            mission_days_elapsed: 已过任务天数
            n_samples: 蒙特卡洛采样数
            
        返回:
            RemainingUsefulLife对象
        """
        # 从后验分布采样剩余因子
        rf_current = self.parameters.remaining_factor_prior_mean
        rf_std = self.parameters.remaining_factor_prior_std
        
        # 采样当前剩余因子
        rf_samples = norm.rvs(loc=rf_current, scale=rf_std, size=n_samples)
        rf_samples = np.clip(rf_samples, 0.0, 1.0)
        
        # 采样退化率不确定性
        ddd_rate = self.parameters.ddd_coefficient
        ddd_std = np.sqrt(self.parameters.covariance_matrix[0, 0])
        degradation_rate_samples = ddd_rate * (1.0 + norm.rvs(loc=0, scale=0.1, size=n_samples))
        
        # 计算每个样本的RUL
        rul_samples = np.zeros(n_samples)
        for i in range(n_samples):
            # 当剩余因子降到失效阈值所需的时间
            if rf_samples[i] <= self.failure_threshold:
                rul_samples[i] = 0.0
            else:
                # 简化的退化模型：指数衰减
                # RUL = -ln(threshold / current) / degradation_rate
                degradation = degradation_rate_samples[i] * cumulative_degradation_rate
                degradation = max(degradation, 1e-10)
                rul_samples[i] = -np.log(self.failure_threshold / rf_samples[i]) / degradation
        
        # 计算统计量
        mean_rul = np.mean(rul_samples)
        median_rul = np.median(rul_samples)
        std_rul = np.std(rul_samples)
        
        # 95%置信区间
        ci_low = np.percentile(rul_samples, 2.5)
        ci_high = np.percentile(rul_samples, 97.5)
        
        return RemainingUsefulLife(
            mean_rul_days=float(mean_rul),
            median_rul_days=float(median_rul),
            std_rul_days=float(std_rul),
            confidence_95_low=float(ci_low),
            confidence_95_high=float(ci_high),
            failure_threshold=self.failure_threshold,
            time_of_prediction=datetime.now()
        )
    
    def initialize_particle_filter(self, n_particles: int = 1000):
        """
        初始化粒子滤波器（用于非线性/非高斯情况）
        
        参数:
            n_particles: 粒子数量
        """
        # 从先验分布采样粒子
        self.particles = np.zeros((n_particles, 4))
        for i, name in enumerate(self.param_names):
            mean = getattr(self.parameters, name)
            std = np.sqrt(self.parameters.covariance_matrix[i, i])
            self.particles[:, i] = norm.rvs(loc=mean, scale=std, size=n_particles)
        
        # 等权重初始化
        self.particle_weights = np.ones(n_particles) / n_particles
    
    def update_with_particle_filter(self,
                                     observation: TelemetryObservation) -> BayesianUpdateResult:
        """
        使用粒子滤波器更新参数（适用于强非线性/非高斯情况）
        
        参数:
            observation: 遥测观测数据
            
        返回:
            BayesianUpdateResult
        """
        if self.particles is None:
            self.initialize_particle_filter()
        
        n_particles = len(self.particles)
        log_weights = np.zeros(n_particles)
        
        # 1. 预测：过程噪声
        process_noise = np.random.normal(
            loc=0, scale=self.parameters.process_noise, size=self.particles.shape
        )
        self.particles += process_noise
        self.particles = np.maximum(self.particles, 1e-12)  # 确保参数为正
        
        # 2. 更新：计算每个粒子的似然
        predicted_powers = np.zeros(n_particles)
        for i in range(n_particles):
            # 使用该粒子的参数计算剩余因子
            param_factor = np.prod(1.0 - self.particles[i] * 1e-3)
            rf = self.parameters.remaining_factor_prior_mean * param_factor
            predicted_powers[i] = self.predict_power(observation, rf)
            log_weights[i] = self.calculate_likelihood(observation, predicted_powers[i])
        
        # 3. 归一化权重
        max_log_weight = np.max(log_weights)
        weights = np.exp(log_weights - max_log_weight)
        weights /= np.sum(weights)
        
        # 4. 重采样（有效粒子数 < N/2 时）
        effective_sample_size = 1.0 / np.sum(weights ** 2)
        if effective_sample_size < n_particles / 2:
            indices = np.random.choice(n_particles, size=n_particles, p=weights)
            self.particles = self.particles[indices]
            weights = np.ones(n_particles) / n_particles
        
        self.particle_weights = weights
        
        # 5. 计算后验统计量
        params_mean = np.average(self.particles, weights=weights, axis=0)
        params_cov = np.cov(self.particles.T, aweights=weights)
        
        # 更新参数
        for i, name in enumerate(self.param_names):
            setattr(self.parameters, name, float(params_mean[i]))
        self.parameters.covariance_matrix = params_cov
        
        # 计算剩余因子后验
        mean_power = float(np.average(predicted_powers, weights=weights))
        rf_posterior = mean_power / max(self.predict_power(observation, 1.0), 1e-6)
        rf_posterior = max(0.0, min(1.0, rf_posterior))
        rf_std = float(np.std(predicted_powers / max(self.predict_power(observation, 1.0), 1e-6)))
        
        # 创建结果
        innovation = observation.array_power - mean_power
        
        result = BayesianUpdateResult(
            time=observation.time,
            parameters=self.parameters,
            remaining_factor_posterior_mean=rf_posterior,
            remaining_factor_posterior_std=rf_std,
            log_likelihood=float(np.average(log_weights, weights=weights)),
            innovation=float(innovation),
            innovation_covariance=float(np.var(predicted_powers, ddof=1)),
            kalman_gain=np.zeros(4),
            parameter_uncertainty_reduction=np.ones(4) * 0.5
        )
        
        # 更新内部状态
        self.parameters.remaining_factor_prior_mean = rf_posterior
        self.parameters.remaining_factor_prior_std = rf_std
        
        # 记录历史
        self.observation_history.append(observation)
        self.update_history.append(result)
        
        # 更新老化趋势
        self.aging_trend.times.append(observation.time)
        self.aging_trend.remaining_factor_mean.append(rf_posterior)
        self.aging_trend.remaining_factor_std.append(rf_std)
        self.aging_trend.predicted_power.append(mean_power)
        self.aging_trend.measured_power.append(observation.array_power)
        self.aging_trend.parameter_evolution.append({
            name: getattr(self.parameters, name) for name in self.param_names
        })
        
        return result
    
    def get_aging_trend_dataframe(self) -> 'pd.DataFrame':
        """
        获取老化趋势的DataFrame
        
        返回:
            pandas DataFrame
        """
        import pandas as pd
        
        data = []
        for i, time in enumerate(self.aging_trend.times):
            row = {
                'time': time,
                'remaining_factor_mean': self.aging_trend.remaining_factor_mean[i],
                'remaining_factor_std': self.aging_trend.remaining_factor_std[i],
                'predicted_power_W': self.aging_trend.predicted_power[i],
                'measured_power_W': self.aging_trend.measured_power[i],
                'residual_W': self.aging_trend.measured_power[i] - self.aging_trend.predicted_power[i]
            }
            row.update(self.aging_trend.parameter_evolution[i])
            data.append(row)
        
        return pd.DataFrame(data)
    
    def get_aging_rate_estimate(self) -> Tuple[float, float]:
        """
        估计当前老化速率
        
        返回:
            (mean_rate, std_rate): 平均老化速率 (1/天) 和标准差
        """
        if len(self.aging_trend.remaining_factor_mean) < 2:
            return 0.0, 0.0
        
        rfs = np.array(self.aging_trend.remaining_factor_mean)
        times = np.array([(t - self.aging_trend.times[0]).total_seconds() / 86400.0 
                         for t in self.aging_trend.times])
        
        # 线性拟合估计老化速率
        if len(times) >= 2:
            slope, _ = np.polyfit(times, rfs, 1)
            rate = -slope  # 老化速率为正
            
            # 估计速率不确定性
            residuals = rfs - np.polyval([slope, _], times)
            std_rate = np.std(residuals) / (times.std() * np.sqrt(len(times))) if len(times) > 2 else 0.0
        else:
            rate = 0.0
            std_rate = 0.0
        
        return float(rate), float(std_rate)
    
    def forecast_aging(self,
                        n_days: float,
                        time_step_days: float = 1.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        预测未来n天的老化趋势
        
        参数:
            n_days: 预测天数
            time_step_days: 时间步长 (天)
            
        返回:
            (times_days, rf_mean, rf_std): 预测时间、剩余因子均值、标准差
        """
        # 估计老化速率
        rate, rate_std = self.get_aging_rate_estimate()
        if rate <= 0:
            rate = 1e-5  # 最小老化速率
        
        # 预测时间
        times = np.arange(0, n_days, time_step_days)
        n_points = len(times)
        
        # 当前状态
        current_rf = self.parameters.remaining_factor_prior_mean
        current_std = self.parameters.remaining_factor_prior_std
        
        # 预测剩余因子（指数衰减模型）
        rf_mean = current_rf * np.exp(-rate * times)
        
        # 不确定性随时间增长（布朗运动模型）
        rf_variance = current_std ** 2 + (rate_std * times) ** 2
        rf_std = np.sqrt(rf_variance)
        
        # 限制在合理范围
        rf_mean = np.clip(rf_mean, self.failure_threshold * 0.5, 1.0)
        rf_std = np.clip(rf_std, 0.001, 0.5)
        
        return times, rf_mean, rf_std
