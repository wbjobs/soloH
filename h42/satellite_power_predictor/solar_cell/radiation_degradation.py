"""
辐射降解模型模块
Radiation Degradation Module

功能：
- 位移损伤剂量 (Displacement Damage Dose, DDD) 计算
- 质子、电子辐射通量计算
- 剩余因子 (Remaining Factor) 模型
- 太阳能电池性能退化预测
- F10.7太阳活动指数相关的辐射环境模型
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional, List, Union
import numpy as np
from datetime import datetime, timedelta

from ..utils.constants import DEFAULT_DDD_FACTOR, DEFAULT_REMAINING_FACTOR_INITIAL


@dataclass
class ParticleFlux:
    """粒子通量数据"""
    proton_flux: np.ndarray  # 质子通量 (cm^-2 s^-1 MeV^-1)
    electron_flux: np.ndarray  # 电子通量 (cm^-2 s^-1 MeV^-1)
    proton_energies: np.ndarray  # 质子能量 (MeV)
    electron_energies: np.ndarray  # 电子能量 (MeV)


@dataclass
class RadiationEnvironment:
    """辐射环境参数"""
    altitude: float  # 轨道高度 (km)
    inclination: float  # 轨道倾角 (deg)
    f107: float  # F10.7太阳活动指数 (solar flux unit, SFU)
    f107_avg: float  # 81天平均F10.7
    kp: float = 3.0  # Kp地磁指数
    mission_duration_days: float = 365.0  # 任务持续时间 (天)


@dataclass
class DegradationState:
    """退化状态"""
    cumulative_ddd: float  # 累积位移损伤剂量 (MeV/g)
    remaining_factor: float  # 剩余因子
    remaining_factor_isc: float  # 短路电流剩余因子
    remaining_factor_voc: float  # 开路电压剩余因子
    remaining_factor_pmax: float  # 最大功率剩余因子
    elapsed_days: float  # 已过天数
    cumulative_atomic_oxygen: float = 0.0  # 累积原子氧通量 (atoms/cm²)
    surface_transmittance: float = 1.0  # 表面透射率 (0-1)
    contamination_thickness: float = 0.0  # 污染物厚度 (nm)
    surface_roughness: float = 0.0  # 表面粗糙度 (nm)


class RadiationDegradation:
    """
    辐射退化模型
    基于位移损伤剂量 (DDD) 方法计算太阳能电池的性能退化
    """

    def __init__(self, 
                 ddd_factor: float = DEFAULT_DDD_FACTOR,
                 initial_remaining_factor: float = DEFAULT_REMAINING_FACTOR_INITIAL):
        """
        初始化辐射退化模型
        
        参数:
            ddd_factor: 位移损伤剂量系数 (MeV/g)^-1
            initial_remaining_factor: 初始剩余因子
        """
        self.ddd_factor = ddd_factor
        self.initial_remaining_factor = initial_remaining_factor
        
        self._proton_damage_coeff = 9.5e-6  # 质子损伤系数 (MeV cm^2 / g)
        self._electron_damage_coeff = 2.1e-7  # 电子损伤系数 (MeV cm^2 / g)

    def calculate_natural_environment_flux(self,
                                           env: RadiationEnvironment,
                                           use_ae8_ap8: bool = True) -> ParticleFlux:
        """
        计算天然辐射环境通量 (AE-8/AP-8模型简化版)
        
        参数:
            env: 辐射环境参数
            use_ae8_ap8: 是否使用AE-8/AP-8模型
            
        返回:
            ParticleFlux对象
        """
        if use_ae8_ap8:
            return self._calculate_ae8_ap8_flux(env)
        else:
            return self._calculate_simplified_flux(env)

    def _calculate_simplified_flux(self, env: RadiationEnvironment) -> ParticleFlux:
        """
        简化的辐射环境通量模型
        基于轨道高度和倾角的经验模型
        """
        altitude = env.altitude
        inclination = env.inclination * np.pi / 180.0
        
        proton_energies = np.logspace(-1, 3, 50)
        electron_energies = np.logspace(-2, 2, 50)
        
        L_shell = 1 + altitude / 6378.0
        B_field = 3.12e-5 * (1 / L_shell ** 3)  # 特斯拉, 偶极子近似
        
        solar_modulation = (env.f107 / 100.0) ** 0.5
        
        # 质子通量 - 南大西洋异常区 (SAA) 模型简化
        saa_factor = np.exp(-(inclination - 0.4) ** 2 / 0.1) if inclination < 1.0 else 0.1
        proton_flux = np.zeros_like(proton_energies)
        
        for i, E in enumerate(proton_energies):
            if E < 1.0:
                flux = 1e5 * np.exp(-E / 0.5)
            elif E < 10.0:
                flux = 1e4 * (E / 1.0) ** -2.5
            else:
                flux = 1e3 * (E / 10.0) ** -3.0
            
            flux *= saa_factor * solar_modulation
            proton_flux[i] = flux
        
        # 电子通量 - 范艾伦带模型简化
        electron_flux = np.zeros_like(electron_energies)
        radiation_belt_factor = 0
        if 1.2 < L_shell < 6.0:
            radiation_belt_factor = np.exp(-(L_shell - 3.5) ** 2 / 2.0) + 0.1
        
        for i, E in enumerate(electron_energies):
            if E < 0.1:
                flux = 1e7 * np.exp(-E / 0.05)
            elif E < 1.0:
                flux = 1e6 * (E / 0.1) ** -1.8
            else:
                flux = 1e5 * (E / 1.0) ** -2.2
            
            flux *= radiation_belt_factor * solar_modulation
            electron_flux[i] = flux
        
        return ParticleFlux(
            proton_flux=proton_flux,
            electron_flux=electron_flux,
            proton_energies=proton_energies,
            electron_energies=electron_energies
        )

    def _calculate_ae8_ap8_flux(self, env: RadiationEnvironment) -> ParticleFlux:
        """
        AE-8/AP-8模型的简化实现
        实际应用中建议使用SPENVIS或CREME软件
        """
        return self._calculate_simplified_flux(env)

    def calculate_ddd_rate(self,
                            flux: ParticleFlux,
                            shield_thickness_mm: float = 2.0) -> float:
        """
        计算位移损伤剂量率 (DDD rate)
        
        参数:
            flux: 粒子通量
            shield_thickness_mm: 屏蔽层厚度 (mm)
            
        返回:
            DDD率 (MeV/g/s)
        """
        # 屏蔽层衰减因子 (简化模型)
        shield_att_proton = np.exp(-shield_thickness_mm / 5.0)
        shield_att_electron = np.exp(-shield_thickness_mm / 1.0)
        
        # 计算质子对DDD的贡献
        proton_contribution = 0.0
        for i, E in enumerate(flux.proton_energies):
            if E > 1.0:
                non_ionizing_energy_loss = self._calculate_niol_proton(E)
                proton_contribution += (
                    flux.proton_flux[i] * shield_att_proton *
                    non_ionizing_energy_loss * self._proton_damage_coeff
                )
        
        # 计算电子对DDD的贡献
        electron_contribution = 0.0
        for i, E in enumerate(flux.electron_energies):
            if E > 0.1:
                non_ionizing_energy_loss = self._calculate_niol_electron(E)
                electron_contribution += (
                    flux.electron_flux[i] * shield_att_electron *
                    non_ionizing_energy_loss * self._electron_damage_coeff
                )
        
        # 转换单位: 1e4是cm^2到m^2的转换
        total_ddd_rate = (proton_contribution + electron_contribution) * 1e4
        
        return total_ddd_rate

    def _calculate_niol_proton(self, energy_MeV: float) -> float:
        """
        计算质子的非电离能量损失 (NIOL)
        单位: MeV cm^2 / g
        
        参考文献: Jun et al., 2003
        """
        if energy_MeV < 1.0:
            return 60.0 * energy_MeV ** 0.5
        elif energy_MeV < 10.0:
            return 60.0 * (energy_MeV / 1.0) ** -0.8
        else:
            return 25.0 * (energy_MeV / 10.0) ** -0.5

    def _calculate_niol_electron(self, energy_MeV: float) -> float:
        """
        计算电子的非电离能量损失 (NIOL)
        单位: MeV cm^2 / g
        """
        if energy_MeV < 0.1:
            return 0.0
        elif energy_MeV < 1.0:
            return 0.01 * energy_MeV ** 1.5
        else:
            return 0.01 * (energy_MeV / 1.0) ** 0.3

    def calculate_cumulative_ddd(self,
                                  ddd_rate: float,
                                  elapsed_seconds: float) -> float:
        """
        计算累积位移损伤剂量
        
        参数:
            ddd_rate: DDD率 (MeV/g/s)
            elapsed_seconds: 经过的时间 (秒)
            
        返回:
            累积DDD (MeV/g)
        """
        return ddd_rate * elapsed_seconds

    def calculate_remaining_factor(self,
                                    cumulative_ddd: float,
                                    cell_type: str = 'triple_junction') -> Tuple[float, float, float, float]:
        """
        计算剩余因子
        
        参数:
            cumulative_ddd: 累积DDD (MeV/g)
            cell_type: 电池类型 ('si', 'gaas', 'triple_junction')
            
        返回:
            (综合剩余因子, Isc剩余因子, Voc剩余因子, Pmax剩余因子)
        """
        if cell_type == 'si':
            C_isc = 4.0e-10
            C_voc = 2.0e-9
            C_pmax = 2.5e-9
        elif cell_type == 'gaas':
            C_isc = 2.0e-10
            C_voc = 1.0e-9
            C_pmax = 1.2e-9
        else:
            C_isc = 1.5e-10
            C_voc = 8.0e-10
            C_pmax = 1.0e-9
        
        remaining_isc = np.exp(-C_isc * cumulative_ddd)
        remaining_voc = np.exp(-C_voc * cumulative_ddd ** 0.75)
        remaining_pmax = np.exp(-C_pmax * cumulative_ddd ** 0.85)
        
        # 综合剩余因子 (取最小值)
        remaining_factor = min(remaining_isc, remaining_voc, remaining_pmax)
        
        return (
            self.initial_remaining_factor * remaining_factor,
            self.initial_remaining_factor * remaining_isc,
            self.initial_remaining_factor * remaining_voc,
            self.initial_remaining_factor * remaining_pmax
        )

    def update_degradation_state(self,
                                   current_state: DegradationState,
                                   ddd_rate: float,
                                   time_step_seconds: float,
                                   cell_type: str = 'triple_junction') -> DegradationState:
        """
        更新退化状态
        
        参数:
            current_state: 当前退化状态
            ddd_rate: DDD率 (MeV/g/s)
            time_step_seconds: 时间步长 (秒)
            cell_type: 电池类型
            
        返回:
            更新后的DegradationState
        """
        delta_ddd = self.calculate_cumulative_ddd(ddd_rate, time_step_seconds)
        new_cumulative_ddd = current_state.cumulative_ddd + delta_ddd
        
        remaining_factor, remaining_isc, remaining_voc, remaining_pmax = (
            self.calculate_remaining_factor(new_cumulative_ddd, cell_type)
        )
        
        return DegradationState(
            cumulative_ddd=new_cumulative_ddd,
            remaining_factor=remaining_factor,
            remaining_factor_isc=remaining_isc,
            remaining_factor_voc=remaining_voc,
            remaining_factor_pmax=remaining_pmax,
            elapsed_days=current_state.elapsed_days + time_step_seconds / 86400.0
        )

    def calculate_time_series_degradation(self,
                                           env: RadiationEnvironment,
                                           time_points: List[datetime],
                                           shield_thickness_mm: float = 2.0,
                                           cell_type: str = 'triple_junction') -> List[DegradationState]:
        """
        计算时间序列的退化状态
        
        参数:
            env: 辐射环境参数
            time_points: 时间点列表
            shield_thickness_mm: 屏蔽层厚度
            cell_type: 电池类型
            
        返回:
            DegradationState列表
        """
        flux = self.calculate_natural_environment_flux(env)
        ddd_rate = self.calculate_ddd_rate(flux, shield_thickness_mm)
        
        states = []
        current_state = DegradationState(
            cumulative_ddd=0.0,
            remaining_factor=self.initial_remaining_factor,
            remaining_factor_isc=self.initial_remaining_factor,
            remaining_factor_voc=self.initial_remaining_factor,
            remaining_factor_pmax=self.initial_remaining_factor,
            elapsed_days=0.0
        )
        
        states.append(current_state)
        
        for i in range(1, len(time_points)):
            delta_t = (time_points[i] - time_points[i-1]).total_seconds()
            current_state = self.update_degradation_state(
                current_state, ddd_rate, delta_t, cell_type
            )
            states.append(current_state)
        
        return states

    def calculate_solar_cell_degradation(self,
                                          env: RadiationEnvironment,
                                          mission_days: float,
                                          shield_thickness_mm: float = 2.0,
                                          cell_type: str = 'triple_junction') -> DegradationState:
        """
        计算任务结束时的太阳能电池退化状态
        
        参数:
            env: 辐射环境参数
            mission_days: 任务天数
            shield_thickness_mm: 屏蔽层厚度
            cell_type: 电池类型
            
        返回:
            任务结束时的DegradationState
        """
        flux = self.calculate_natural_environment_flux(env)
        ddd_rate = self.calculate_ddd_rate(flux, shield_thickness_mm)
        
        total_seconds = mission_days * 86400.0
        cumulative_ddd = self.calculate_cumulative_ddd(ddd_rate, total_seconds)
        
        remaining_factor, remaining_isc, remaining_voc, remaining_pmax = (
            self.calculate_remaining_factor(cumulative_ddd, cell_type)
        )
        
        return DegradationState(
            cumulative_ddd=cumulative_ddd,
            remaining_factor=remaining_factor,
            remaining_factor_isc=remaining_isc,
            remaining_factor_voc=remaining_voc,
            remaining_factor_pmax=remaining_pmax,
            elapsed_days=mission_days
        )

    def get_f107_radiation_scaling(self, f107: float, f107_avg: float) -> float:
        """
        根据F10.7指数计算辐射环境缩放因子
        
        参数:
            f107: 当日F10.7指数
            f107_avg: 81天平均F10.7指数
            
        返回:
            辐射缩放因子
        """
        # 太阳活动极大年辐射增强
        solar_max_factor = (f107 / 70.0) ** 0.3
        solar_avg_factor = (f107_avg / 100.0) ** 0.2
        
        return solar_max_factor * solar_avg_factor


class SolarCellDegradationModel:
    """
    综合太阳能电池退化模型
    结合辐射退化和温度循环等因素
    """

    def __init__(self,
                 radiation_model: RadiationDegradation = None,
                 cell_type: str = 'triple_junction'):
        """
        初始化综合退化模型
        
        参数:
            radiation_model: 辐射退化模型
            cell_type: 电池类型
        """
        self.radiation_model = radiation_model or RadiationDegradation()
        self.cell_type = cell_type
        
        self._thermal_cycle_degradation_rate = 1e-6  # 每次热循环的退化率
        self._uv_degradation_rate = 2e-9  # UV辐照退化率 (1/s)

    def calculate_total_degradation(self,
                                     env: RadiationEnvironment,
                                     mission_days: float,
                                     shield_thickness_mm: float = 2.0,
                                     thermal_cycles_per_day: int = 1) -> DegradationState:
        """
        计算总退化 (辐射 + 热循环 + UV)
        
        参数:
            env: 辐射环境参数
            mission_days: 任务天数
            shield_thickness_mm: 屏蔽层厚度
            thermal_cycles_per_day: 每天热循环次数
            
        返回:
            DegradationState
        """
        rad_state = self.radiation_model.calculate_solar_cell_degradation(
            env, mission_days, shield_thickness_mm, self.cell_type
        )
        
        # 热循环退化
        total_cycles = mission_days * thermal_cycles_per_day
        thermal_factor = np.exp(-self._thermal_cycle_degradation_rate * total_cycles ** 0.5)
        
        # UV退化
        total_seconds = mission_days * 86400.0
        uv_factor = np.exp(-self._uv_degradation_rate * total_seconds)
        
        # 综合退化
        combined_factor = thermal_factor * uv_factor
        
        return DegradationState(
            cumulative_ddd=rad_state.cumulative_ddd,
            remaining_factor=rad_state.remaining_factor * combined_factor,
            remaining_factor_isc=rad_state.remaining_factor_isc * thermal_factor,
            remaining_factor_voc=rad_state.remaining_factor_voc * combined_factor,
            remaining_factor_pmax=rad_state.remaining_factor_pmax * combined_factor,
            elapsed_days=mission_days
        )


@dataclass
class AtomicOxygenState:
    """原子氧侵蚀状态"""
    flux: float  # 原子氧通量 (atoms/cm²/s)
    cumulative_flux: float  # 累积通量 (atoms/cm²)
    erosion_depth: float  # 侵蚀深度 (μm)
    surface_transmittance: float  # 表面透射率 (0-1)
    contamination_thickness: float  # 污染物厚度 (nm)
    surface_roughness: float  # 表面粗糙度 (nm, RMS)


class AtomicOxygenErosionModel:
    """
    原子氧侵蚀与表面除尘效应模型
    
    功能：
    - 轨道高度依赖的原子氧通量计算
    - 表面减反射膜侵蚀导致的透射率退化
    - 表面除尘效应（高速原子氧碰撞清除表面污染物）
    - 表面粗糙度演化
    - 与辐射退化模型的综合效应
    """
    
    def __init__(self, 
                 surface_material: str = 'sio2',
                 initial_transmittance: float = 0.95,
                 initial_roughness: float = 1.0):
        """
        初始化原子氧侵蚀模型
        
        参数:
            surface_material: 表面材料类型 ('sio2', 'mgf2', 'ta2o5', 'polyimide')
            initial_transmittance: 初始表面透射率 (0-1)
            initial_roughness: 初始表面粗糙度 (nm, RMS)
        """
        self.surface_material = surface_material
        self.initial_transmittance = initial_transmittance
        self.initial_roughness = initial_roughness
        
        # 材料侵蚀系数 (cm³/atom) 来自NASA SP-8007
        self._erosion_coefficients = {
            'sio2': 3.0e-24,
            'mgf2': 2.5e-24,
            'ta2o5': 4.0e-24,
            'polyimide': 3.0e-23,
            'coverglass': 2.0e-24
        }
        
        # 除尘效率系数
        self._cleaning_efficiency = 0.7  # 原子氧碰撞清除污染物的效率
        
        # 透射率退化系数
        self._transmittance_erosion_factor = 0.15  # 每μm侵蚀导致的透射率下降比例
        self._transmittance_roughness_factor = 0.08  # 每nm粗糙度增加导致的透射率下降比例
        self._contamination_absorption_coeff = 0.01  # 每nm污染物厚度的吸收率 (1/nm)
        
        # 污染物沉积率 (nm/s) - 简化模型
        self._contamination_deposition_rate = 1.0e-11
    
    def calculate_atomic_oxygen_flux(self, 
                                       altitude_km: float, 
                                       solar_f107: float = 100.0,
                                       spacecraft_velocity: float = 7.7) -> float:
        """
        计算原子氧通量
        
        参数:
            altitude_km: 轨道高度 (km)
            solar_f107: F10.7太阳活动指数 (SFU)
            spacecraft_velocity: 航天器速度 (km/s)
            
        返回:
            原子氧通量 (atoms/cm²/s)
        """
        # 基于MSIS-00模型的简化参数化
        # 热原子氧数密度 (cm^-3)
        if altitude_km < 200:
            n_O = 1e10 * np.exp(-(altitude_km - 200) / 50)
        elif altitude_km < 500:
            n_O = 5e9 * np.exp(-(altitude_km - 200) / 80)
        elif altitude_km < 1000:
            n_O = 1e9 * np.exp(-(altitude_km - 500) / 150)
        else:
            n_O = 1e8 * np.exp(-(altitude_km - 1000) / 300)
        
        # 太阳活动修正
        solar_factor = 1.0 + 0.5 * (solar_f107 - 100) / 100
        solar_factor = max(0.5, min(2.0, solar_factor))
        n_O *= solar_factor
        
        # 通量 = 数密度 × 速度 (转换单位: km/s → cm/s)
        velocity_cms = spacecraft_velocity * 1e5
        flux = n_O * velocity_cms
        
        return max(1.0, flux)
    
    def calculate_erosion_rate(self,
                                flux: float,
                                incidence_angle_deg: float = 0.0) -> float:
        """
        计算表面侵蚀速率
        
        参数:
            flux: 原子氧通量 (atoms/cm²/s)
            incidence_angle_deg: 入射角 (度)
            
        返回:
            侵蚀速率 (μm/s)
        """
        if self.surface_material in self._erosion_coefficients:
            erosion_coeff = self._erosion_coefficients[self.surface_material]
        else:
            erosion_coeff = self._erosion_coefficients['coverglass']
        
        # 入射角修正 (余弦法则)
        cos_theta = np.cos(np.radians(incidence_angle_deg))
        cos_theta = max(0.0, cos_theta)
        
        # 侵蚀速率 (cm/s) = 侵蚀系数 × 通量 × cos(theta)
        erosion_rate_cms = erosion_coeff * flux * cos_theta
        
        # 转换为 μm/s (1 cm = 10^4 μm)
        erosion_rate_um_s = erosion_rate_cms * 1e4
        
        return erosion_rate_um_s
    
    def calculate_surface_transmittance(self,
                                          erosion_depth: float,
                                          surface_roughness: float,
                                          contamination_thickness: float) -> float:
        """
        计算表面透射率
        
        参数:
            erosion_depth: 累积侵蚀深度 (μm)
            surface_roughness: 表面粗糙度 (nm, RMS)
            contamination_thickness: 污染物厚度 (nm)
            
        返回:
            表面透射率 (0-1)
        """
        # 基础透射率
        transmittance = self.initial_transmittance
        
        # 侵蚀导致的透射率下降
        transmittance *= (1.0 - self._transmittance_erosion_factor * 
                         np.tanh(erosion_depth / 5.0))
        
        # 表面粗糙度导致的散射损失
        roughness_loss = self._transmittance_roughness_factor * (surface_roughness / 10.0)
        transmittance *= np.exp(-roughness_loss)
        
        # 污染物吸收损失 (Beer-Lambert定律)
        absorption = np.exp(-self._contamination_absorption_coeff * contamination_thickness)
        transmittance *= absorption
        
        # 限制在合理范围内
        transmittance = max(0.5, min(self.initial_transmittance, transmittance))
        
        return transmittance
    
    def calculate_contamination_evolution(self,
                                            current_thickness: float,
                                            ao_flux: float,
                                            time_step_seconds: float) -> float:
        """
        计算污染物厚度演化（沉积 + 原子氧除尘）
        
        参数:
            current_thickness: 当前污染物厚度 (nm)
            ao_flux: 原子氧通量 (atoms/cm²/s)
            time_step_seconds: 时间步长 (秒)
            
        返回:
            新的污染物厚度 (nm)
        """
        # 沉积量
        deposition = self._contamination_deposition_rate * time_step_seconds
        
        # 除尘量（原子氧碰撞清除）
        # 除尘速率与通量成正比
        cleaning_rate = self._cleaning_efficiency * 1e-16 * ao_flux  # nm/s per atoms/cm²/s
        cleaning = cleaning_rate * current_thickness * time_step_seconds
        
        new_thickness = max(0.0, current_thickness + deposition - cleaning)
        
        return new_thickness
    
    def calculate_roughness_evolution(self,
                                       current_roughness: float,
                                       erosion_rate: float,
                                       time_step_seconds: float) -> float:
        """
        计算表面粗糙度演化
        
        参数:
            current_roughness: 当前粗糙度 (nm, RMS)
            erosion_rate: 侵蚀速率 (μm/s)
            time_step_seconds: 时间步长 (秒)
            
        返回:
            新的表面粗糙度 (nm)
        """
        # 侵蚀初期粗糙度增加，达到峰值后逐渐稳定
        eroded = erosion_rate * time_step_seconds  # 本步长侵蚀量 (μm)
        
        # 粗糙度演化模型
        # 初始阶段: 粗糙度随侵蚀增加
        # 后期: 粗糙度趋于饱和
        peak_roughness = 20.0  # 峰值粗糙度 (nm)
        saturation_erosion = 2.0  # 达到饱和所需的侵蚀深度 (μm)
        
        roughness_increase = peak_roughness * (1.0 - np.exp(-eroded / saturation_erosion))
        
        new_roughness = self.initial_roughness + roughness_increase
        
        return new_roughness
    
    def update_state(self,
                       current_state: DegradationState,
                       altitude_km: float,
                       incidence_angle_deg: float,
                       time_step_seconds: float,
                       solar_f107: float = 100.0,
                       spacecraft_velocity: float = 7.7) -> DegradationState:
        """
        更新原子氧侵蚀状态（集成到DegradationState）
        
        参数:
            current_state: 当前退化状态
            altitude_km: 轨道高度 (km)
            incidence_angle_deg: 帆板法线与原子氧入射角 (度)
            time_step_seconds: 时间步长 (秒)
            solar_f107: F10.7太阳活动指数
            spacecraft_velocity: 航天器速度 (km/s)
            
        返回:
            更新后的DegradationState
        """
        # 计算原子氧通量
        ao_flux = self.calculate_atomic_oxygen_flux(
            altitude_km, solar_f107, spacecraft_velocity
        )
        
        # 计算侵蚀速率
        erosion_rate = self.calculate_erosion_rate(ao_flux, incidence_angle_deg)
        
        # 累积侵蚀深度
        total_eroded = erosion_rate * time_step_seconds
        
        # 累积原子氧通量
        new_cumulative_ao = current_state.cumulative_atomic_oxygen + ao_flux * time_step_seconds
        
        # 污染物厚度演化（考虑除尘效应）
        new_contamination = self.calculate_contamination_evolution(
            current_state.contamination_thickness, ao_flux, time_step_seconds
        )
        
        # 表面粗糙度演化
        new_roughness = self.calculate_roughness_evolution(
            current_state.surface_roughness, erosion_rate, time_step_seconds
        )
        
        # 计算总侵蚀深度（基于累积原子氧通量）
        # 侵蚀深度 = 侵蚀系数 × 累积通量 × cos(theta)
        cos_theta = max(0.0, np.cos(np.radians(incidence_angle_deg)))
        erosion_coeff = self._erosion_coefficients.get(self.surface_material, 2.0e-24)
        total_erosion_depth_cm = erosion_coeff * new_cumulative_ao * cos_theta
        total_erosion_depth_um = total_erosion_depth_cm * 1e4  # cm → μm
        
        # 计算表面透射率（使用总侵蚀深度、粗糙度、污染物厚度）
        new_transmittance = self.calculate_surface_transmittance(
            total_erosion_depth_um,
            new_roughness,
            new_contamination
        )
        
        # 更新退化状态
        return DegradationState(
            cumulative_ddd=current_state.cumulative_ddd,
            remaining_factor=current_state.remaining_factor,
            remaining_factor_isc=current_state.remaining_factor_isc * 
                (new_transmittance / max(current_state.surface_transmittance, 1e-6)),
            remaining_factor_voc=current_state.remaining_factor_voc,
            remaining_factor_pmax=current_state.remaining_factor_pmax *
                (new_transmittance / max(current_state.surface_transmittance, 1e-6)),
            elapsed_days=current_state.elapsed_days + time_step_seconds / 86400.0,
            cumulative_atomic_oxygen=new_cumulative_ao,
            surface_transmittance=new_transmittance,
            contamination_thickness=new_contamination,
            surface_roughness=new_roughness
        )
    
    def get_effective_irradiance_factor(self, state: DegradationState) -> float:
        """
        获取有效的辐照度因子（考虑表面透射率）
        
        参数:
            state: 退化状态
            
        返回:
            辐照度乘数因子
        """
        return state.surface_transmittance / self.initial_transmittance
