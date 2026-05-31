"""
功率预测主模块
Power Prediction Main Module

功能：
- 整合轨道、天体、遮挡、电池模型、辐射降解模块
- 温度模型（太阳能电池板温度预测）
- 完整的功率/电流时序计算
- 帆板姿态序列处理
- 轨道周期平均功率计算
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Union
import numpy as np
from datetime import datetime, timedelta
import pandas as pd

from ..orbit.tle_propagator import TLEPropagator, TLEData, OrbitState
from ..astronomy.celestial_calculator import CelestialCalculator, CelestialState
from ..occlusion.shadow_calculator import (
    ShadowCalculator, SolarArray, GeometryObject,
    transform_eci_to_body, create_default_satellite_model
)
from ..solar_cell.diode_model import (
    SolarArrayModel, SolarArrayConfig, CellParameters,
    OperatingConditions
)
from ..solar_cell.radiation_degradation import (
    RadiationDegradation, RadiationEnvironment, DegradationState
)
from ..utils.constants import STC_TEMPERATURE, SOLAR_CONSTANT, SEC_PER_DAY


@dataclass
class AttitudePoint:
    """姿态序列点"""
    time: datetime
    sa_normal: np.ndarray  # 帆板法向量 (本体坐标系, 单位矢量)


@dataclass
class PowerTimePoint:
    """功率时间序列点"""
    time: datetime
    position_eci: np.ndarray  # km
    velocity_eci: np.ndarray  # km/s
    sun_vector_eci: np.ndarray
    sun_vector_body: np.ndarray
    sa_normal_body: np.ndarray
    solar_irradiance: float  # W/m^2
    eclipse_factor: float
    is_umbra: bool
    is_penumbra: bool
    albedo_flux: float  # W/m^2
    earth_ir_flux: float  # W/m^2
    incidence_angle: float  # deg, 太阳光入射角
    occlusion_factor: float
    visible_area_ratio: float
    effective_irradiance: float  # W/m^2, 考虑遮挡后的有效辐照度
    cell_temperature: float  # K
    array_current: float  # A
    array_voltage: float  # V
    array_power: float  # W
    remaining_factor: float
    ddd_cumulative: float  # MeV/g


@dataclass
class OrbitAveragePower:
    """轨道周期平均功率"""
    period_seconds: float
    average_power: float  # W
    average_current: float  # A
    peak_power: float  # W
    minimum_power: float  # W
    eclipse_duration: float  # s
    sunlit_duration: float  # s
    total_energy: float  # Wh


@dataclass
class PowerPredictionResult:
    """功率预测结果"""
    satellite_name: str
    time_series: List[PowerTimePoint]
    orbit_average: OrbitAveragePower
    degradation_state: DegradationState
    input_parameters: Dict

    def to_dataframe(self) -> pd.DataFrame:
        """转换为pandas DataFrame"""
        data = []
        for pt in self.time_series:
            data.append({
                'time': pt.time,
                'pos_x_km': pt.position_eci[0],
                'pos_y_km': pt.position_eci[1],
                'pos_z_km': pt.position_eci[2],
                'sun_x_body': pt.sun_vector_body[0],
                'sun_y_body': pt.sun_vector_body[1],
                'sun_z_body': pt.sun_vector_body[2],
                'solar_irradiance_Wm2': pt.solar_irradiance,
                'eclipse_factor': pt.eclipse_factor,
                'is_umbra': pt.is_umbra,
                'is_penumbra': pt.is_penumbra,
                'albedo_flux_Wm2': pt.albedo_flux,
                'earth_ir_flux_Wm2': pt.earth_ir_flux,
                'incidence_angle_deg': pt.incidence_angle,
                'occlusion_factor': pt.occlusion_factor,
                'visible_area_ratio': pt.visible_area_ratio,
                'effective_irradiance_Wm2': pt.effective_irradiance,
                'cell_temperature_K': pt.cell_temperature,
                'array_current_A': pt.array_current,
                'array_voltage_V': pt.array_voltage,
                'array_power_W': pt.array_power,
                'remaining_factor': pt.remaining_factor,
                'ddd_cumulative_MeVg': pt.ddd_cumulative
            })
        return pd.DataFrame(data)


class TemperatureModel:
    """
    太阳能电池温度模型
    基于热平衡计算电池温度
    """

    def __init__(self,
                 absorptivity: float = 0.92,
                 emissivity: float = 0.85,
                 thermal_mass: float = 0.5,  # J/K per cell
                 heat_capacity: float = 800.0):  # J/kg·K
        """
        初始化温度模型
        
        参数:
            absorptivity: 太阳吸收率
            emissivity: 红外发射率
            thermal_mass: 单位面积热质量 (J/K/m^2)
            heat_capacity: 比热容 (J/kg·K)
        """
        self.alpha_s = absorptivity
        self.epsilon = emissivity
        self.thermal_mass = thermal_mass
        self.heat_capacity = heat_capacity
        self._sigma = 5.670374419e-8  # Stefan-Boltzmann常数, W/(m^2·K^4)

    def calculate_equilibrium_temperature(self,
                                            total_irradiance: float,
                                            albedo_flux: float,
                                            earth_ir_flux: float,
                                            eclipse_factor: float) -> float:
        """
        计算平衡温度 (稳态)
        
        参数:
            total_irradiance: 总入射辐照度 (W/m^2)
            albedo_flux: 地球反照通量 (W/m^2)
            earth_ir_flux: 地球红外通量 (W/m^2)
            eclipse_factor: 地影因子
            
        返回:
            平衡温度 (K)
        """
        # 吸收的热量
        q_absorbed = (
            self.alpha_s * total_irradiance * eclipse_factor +
            self.alpha_s * albedo_flux +
            self.epsilon * earth_ir_flux
        )
        
        # 辐射散热 (假设背面也辐射)
        # T^4 = q_absorbed / (2 * epsilon * sigma)
        if q_absorbed <= 0:
            return 250.0  # 最低温度
        
        T4 = q_absorbed / (2 * self.epsilon * self._sigma)
        return T4 ** 0.25

    def calculate_transient_temperature(self,
                                         current_temp: float,
                                         total_irradiance: float,
                                         albedo_flux: float,
                                         earth_ir_flux: float,
                                         eclipse_factor: float,
                                         time_step: float) -> float:
        """
        计算瞬态温度
        
        参数:
            current_temp: 当前温度 (K)
            total_irradiance: 总入射辐照度 (W/m^2)
            albedo_flux: 地球反照通量 (W/m^2)
            earth_ir_flux: 地球红外通量 (W/m^2)
            eclipse_factor: 地影因子
            time_step: 时间步长 (s)
            
        返回:
            新的温度 (K)
        """
        T_eq = self.calculate_equilibrium_temperature(
            total_irradiance, albedo_flux, earth_ir_flux, eclipse_factor
        )
        
        # 热时间常数
        tau = self.thermal_mass * self.heat_capacity / (2 * self.epsilon * self._sigma * T_eq ** 3)
        
        # 一阶热响应
        T_new = T_eq + (current_temp - T_eq) * np.exp(-time_step / tau)
        
        return T_new


class PowerPredictor:
    """
    功率预测器
    整合所有模块，执行完整的功率预测流程
    """

    def __init__(self,
                 tle_data: TLEData,
                 solar_array: SolarArray = None,
                 occlusion_objects: List[GeometryObject] = None,
                 array_config: SolarArrayConfig = None,
                 f107: float = 100.0,
                 f107_avg: float = 100.0,
                 shield_thickness_mm: float = 2.0):
        """
        初始化功率预测器
        
        参数:
            tle_data: TLE数据
            solar_array: 太阳能帆板模型
            occlusion_objects: 遮挡物体列表
            array_config: 太阳能阵列配置
            f107: F10.7太阳活动指数
            f107_avg: 81天平均F10.7
            shield_thickness_mm: 屏蔽层厚度 (mm)
        """
        if solar_array is None or occlusion_objects is None:
            solar_array, occlusion_objects = create_default_satellite_model()
        
        if array_config is None:
            array_config = SolarArrayConfig()
        
        self.tle_data = tle_data
        self.orbit_propagator = TLEPropagator(tle_data)
        self.celestial_calculator = CelestialCalculator()
        self.shadow_calculator = ShadowCalculator(solar_array, occlusion_objects)
        self.solar_array_model = SolarArrayModel(array_config)
        self.radiation_model = RadiationDegradation()
        self.temperature_model = TemperatureModel()
        
        self.f107 = f107
        self.f107_avg = f107_avg
        self.shield_thickness_mm = shield_thickness_mm
        
        self._solar_array = solar_array
        self._array_config = array_config

    def _interpolate_attitude(self,
                               attitude_sequence: List[AttitudePoint],
                               target_time: datetime) -> np.ndarray:
        """
        插值获取指定时间的帆板姿态
        
        参数:
            attitude_sequence: 姿态序列
            target_time: 目标时间
            
        返回:
            帆板法向量 (本体坐标系)
        """
        if len(attitude_sequence) == 0:
            return self._solar_array.normal
        
        if len(attitude_sequence) == 1:
            return attitude_sequence[0].sa_normal
        
        times = np.array([(ap.time - attitude_sequence[0].time).total_seconds() 
                        for ap in attitude_sequence])
        target_sec = (target_time - attitude_sequence[0].time).total_seconds()
        
        if target_sec <= times[0]:
            return attitude_sequence[0].sa_normal
        if target_sec >= times[-1]:
            return attitude_sequence[-1].sa_normal
        
        idx = np.searchsorted(times, target_sec) - 1
        idx = max(0, min(idx, len(times) - 2))
        
        t0, t1 = times[idx], times[idx + 1]
        frac = (target_sec - t0) / (t1 - t0)
        
        n0 = attitude_sequence[idx].sa_normal
        n1 = attitude_sequence[idx + 1].sa_normal
        
        n = (1 - frac) * n0 + frac * n1
        return n / np.linalg.norm(n)

    def predict(self,
                start_time: datetime,
                end_time: datetime,
                time_step_sec: float = 1.0,
                attitude_sequence: List[AttitudePoint] = None,
                initial_temperature: float = STC_TEMPERATURE,
                initial_degradation: DegradationState = None,
                operating_voltage: float = None) -> PowerPredictionResult:
        """
        执行功率预测
        
        参数:
            start_time: 开始时间
            end_time: 结束时间
            time_step_sec: 时间步长 (秒)
            attitude_sequence: 帆板姿态序列
            initial_temperature: 初始电池温度 (K)
            initial_degradation: 初始退化状态
            operating_voltage: 工作电压 (V), None表示工作在MPP
            
        返回:
            PowerPredictionResult
        """
        if attitude_sequence is None:
            attitude_sequence = [AttitudePoint(
                time=start_time,
                sa_normal=self._solar_array.normal
            )]
        
        if initial_degradation is None:
            initial_degradation = DegradationState(
                cumulative_ddd=0.0,
                remaining_factor=1.0,
                remaining_factor_isc=1.0,
                remaining_factor_voc=1.0,
                remaining_factor_pmax=1.0,
                elapsed_days=0.0
            )
        
        # 生成时间序列
        duration = (end_time - start_time).total_seconds()
        n_steps = int(duration / time_step_sec) + 1
        times = [start_time + timedelta(seconds=i * time_step_sec) for i in range(n_steps)]
        
        # 轨道传播
        orbit_states = self.orbit_propagator.propagate(times)
        
        # 计算辐射环境
        orbit_elements = self.orbit_propagator.get_orbital_elements()
        altitude = self.tle_data.get_altitude()
        inclination = self.tle_data.inclination
        
        rad_env = RadiationEnvironment(
            altitude=altitude,
            inclination=inclination,
            f107=self.f107,
            f107_avg=self.f107_avg,
            mission_duration_days=duration / SEC_PER_DAY
        )
        
        flux = self.radiation_model.calculate_natural_environment_flux(rad_env)
        ddd_rate = self.radiation_model.calculate_ddd_rate(flux, self.shield_thickness_mm)
        
        # 准备结果列表
        time_series = []
        current_temp = initial_temperature
        current_degradation = initial_degradation
        
        # 遍历每个时间点
        for i, (time, orbit_state) in enumerate(zip(times, orbit_states)):
            if orbit_state.error != 0:
                continue
            
            # 获取帆板姿态
            sa_normal = self._interpolate_attitude(attitude_sequence, time)
            
            # 计算天体状态
            celestial_state = self.celestial_calculator.calculate_state(
                time, orbit_state.position, sa_normal
            )
            
            # 转换太阳矢量到本体坐标系
            sun_vector_body = transform_eci_to_body(
                celestial_state.sun_vector_eci,
                orbit_state.position,
                orbit_state.velocity
            )
            
            # 计算遮挡
            effective_irradiance, occlusion = self.shadow_calculator.calculate_effective_irradiance(
                sun_vector_body,
                celestial_state.solar_irradiance,
                sa_normal
            )
            
            # 计算总入射辐照度 (考虑地影)
            total_irradiance = effective_irradiance * celestial_state.eclipse_factor
            
            # 计算电池温度
            if i == 0:
                cell_temp = self.temperature_model.calculate_equilibrium_temperature(
                    total_irradiance,
                    celestial_state.albedo_flux,
                    celestial_state.earth_ir_flux,
                    celestial_state.eclipse_factor
                )
            else:
                cell_temp = self.temperature_model.calculate_transient_temperature(
                    current_temp,
                    total_irradiance,
                    celestial_state.albedo_flux,
                    celestial_state.earth_ir_flux,
                    celestial_state.eclipse_factor,
                    time_step_sec
                )
            current_temp = cell_temp
            
            # 更新退化状态
            if i > 0:
                current_degradation = self.radiation_model.update_degradation_state(
                    current_degradation, ddd_rate, time_step_sec
                )
            
            # 准备电池工作条件
            conditions = OperatingConditions(
                irradiance=total_irradiance,
                temperature=cell_temp,
                remaining_factor=current_degradation.remaining_factor
            )
            
            # 计算阵列性能
            if operating_voltage is None:
                I_mpp, V_mpp, P_mpp, _ = self.solar_array_model.calculate_array_performance(
                    conditions, current_degradation.remaining_factor
                )
                array_current = I_mpp
                array_voltage = V_mpp
                array_power = P_mpp
            else:
                array_current = self.solar_array_model.calculate_operating_current(
                    conditions, operating_voltage, current_degradation.remaining_factor
                )
                array_voltage = operating_voltage
                array_power = array_current * array_voltage
            
            # 计算入射角
            incidence_angle = np.arccos(max(0.0, np.dot(sun_vector_body, sa_normal))) * 180.0 / np.pi
            
            # 保存结果
            time_series.append(PowerTimePoint(
                time=time,
                position_eci=orbit_state.position,
                velocity_eci=orbit_state.velocity,
                sun_vector_eci=celestial_state.sun_vector_eci,
                sun_vector_body=sun_vector_body,
                sa_normal_body=sa_normal,
                solar_irradiance=celestial_state.solar_irradiance,
                eclipse_factor=celestial_state.eclipse_factor,
                is_umbra=celestial_state.is_umbra,
                is_penumbra=celestial_state.is_penumbra,
                albedo_flux=celestial_state.albedo_flux,
                earth_ir_flux=celestial_state.earth_ir_flux,
                incidence_angle=incidence_angle,
                occlusion_factor=occlusion.occlusion_factor,
                visible_area_ratio=occlusion.visible_area_ratio,
                effective_irradiance=total_irradiance,
                cell_temperature=cell_temp,
                array_current=array_current,
                array_voltage=array_voltage,
                array_power=array_power,
                remaining_factor=current_degradation.remaining_factor,
                ddd_cumulative=current_degradation.cumulative_ddd
            ))
        
        # 计算轨道周期平均功率
        orbit_average = self._calculate_orbit_average(time_series, time_step_sec)
        
        # 准备输入参数记录
        input_params = {
            'tle_name': self.tle_data.name,
            'norad_id': self.tle_data.norad_id,
            'start_time': start_time,
            'end_time': end_time,
            'time_step_sec': time_step_sec,
            'f107': self.f107,
            'f107_avg': self.f107_avg,
            'shield_thickness_mm': self.shield_thickness_mm,
            'operating_voltage': operating_voltage,
            'n_cells_series': self._array_config.n_cells_series,
            'n_strings_parallel': self._array_config.n_strings_parallel
        }
        
        return PowerPredictionResult(
            satellite_name=self.tle_data.name,
            time_series=time_series,
            orbit_average=orbit_average,
            degradation_state=current_degradation,
            input_parameters=input_params
        )

    def _calculate_orbit_average(self,
                                  time_series: List[PowerTimePoint],
                                  time_step_sec: float) -> OrbitAveragePower:
        """
        计算轨道周期平均功率
        
        参数:
            time_series: 功率时间序列
            time_step_sec: 时间步长
            
        返回:
            OrbitAveragePower
        """
        powers = np.array([pt.array_power for pt in time_series])
        currents = np.array([pt.array_current for pt in time_series])
        eclipse_factors = np.array([pt.eclipse_factor for pt in time_series])
        
        orbit_period = self.orbit_propagator.get_orbit_period()
        n_points_per_orbit = int(orbit_period / time_step_sec)
        
        if len(powers) >= n_points_per_orbit:
            powers_orbit = powers[:n_points_per_orbit]
            currents_orbit = currents[:n_points_per_orbit]
            eclipse_orbit = eclipse_factors[:n_points_per_orbit]
        else:
            powers_orbit = powers
            currents_orbit = currents
            eclipse_orbit = eclipse_factors
        
        avg_power = np.mean(powers_orbit)
        avg_current = np.mean(currents_orbit)
        peak_power = np.max(powers_orbit)
        min_power = np.min(powers_orbit)
        
        # 计算地影时间
        eclipse_duration = np.sum(eclipse_orbit < 0.99) * time_step_sec
        sunlit_duration = len(eclipse_orbit) * time_step_sec - eclipse_duration
        
        # 总能量 (Wh)
        total_energy = np.sum(powers_orbit) * time_step_sec / 3600.0
        
        return OrbitAveragePower(
            period_seconds=orbit_period,
            average_power=avg_power,
            average_current=avg_current,
            peak_power=peak_power,
            minimum_power=min_power,
            eclipse_duration=eclipse_duration,
            sunlit_duration=sunlit_duration,
            total_energy=total_energy
        )

    def predict_multi_orbit(self,
                             n_orbits: int,
                             start_time: datetime,
                             time_step_sec: float = 1.0,
                             attitude_sequence: List[AttitudePoint] = None,
                             **kwargs) -> PowerPredictionResult:
        """
        预测多个轨道周期
        
        参数:
            n_orbits: 轨道周期数
            start_time: 开始时间
            time_step_sec: 时间步长
            attitude_sequence: 姿态序列
            **kwargs: 其他预测参数
            
        返回:
            PowerPredictionResult
        """
        orbit_period = self.orbit_propagator.get_orbit_period()
        end_time = start_time + timedelta(seconds=n_orbits * orbit_period)
        
        return self.predict(
            start_time=start_time,
            end_time=end_time,
            time_step_sec=time_step_sec,
            attitude_sequence=attitude_sequence,
            **kwargs
        )
