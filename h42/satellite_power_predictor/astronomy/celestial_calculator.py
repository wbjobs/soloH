"""
天体计算模块
Celestial Calculation Module

功能：
- 太阳位置矢量计算 (ECI坐标系)
- 地影检测 (本影/半影)
- 地球反照辐射计算
- 地球红外辐射计算
- 太阳辐照度计算 (考虑日地距离变化)
"""

from dataclasses import dataclass
from typing import List, Union, Tuple
import numpy as np
from datetime import datetime

from astropy.coordinates import get_sun, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u

from ..utils.constants import (
    SOLAR_CONSTANT, EARTH_RADIUS, EARTH_ALBEDO, 
    EARTH_IR_FLUX, AU, DEG2RAD
)


@dataclass
class CelestialState:
    """天体状态数据结构"""
    time: datetime
    sun_vector_eci: np.ndarray  # 太阳方向矢量 (ECI, 单位矢量)
    sun_distance_au: float  # 日地距离 (AU)
    solar_irradiance: float  # 太阳辐照度 (W/m^2)
    eclipse_factor: float  # 地影因子: 1=完全光照, 0=完全本影
    is_umbra: bool  # 是否在本影中
    is_penumbra: bool  # 是否在半影中
    albedo_flux: float  # 地球反照通量 (W/m^2)
    earth_ir_flux: float  # 地球红外通量 (W/m^2)


class CelestialCalculator:
    """
    天体计算器
    计算太阳位置、地影、地球反照等天文参数
    """

    def __init__(self):
        """初始化天体计算器"""
        self._sun_radius = 695700.0  # km, 太阳半径
        self._earth_radius = EARTH_RADIUS  # km

    def calculate_sun_position(self, time: Union[datetime, List[datetime]]) -> Union[np.ndarray, List[np.ndarray]]:
        """
        计算太阳在ECI坐标系中的位置矢量
        
        参数:
            time: 单个datetime或datetime列表
            
        返回:
            太阳位置单位矢量 (ECI坐标系)
        """
        if isinstance(time, (list, np.ndarray)):
            return np.array([self._calc_sun_single(t) for t in time])
        return self._calc_sun_single(time)

    def _calc_sun_single(self, time: datetime) -> np.ndarray:
        """计算单个时间点的太阳位置"""
        t = Time(time)
        sun = get_sun(t)
        
        ra = sun.ra.rad
        dec = sun.dec.rad
        
        x = np.cos(dec) * np.cos(ra)
        y = np.cos(dec) * np.sin(ra)
        z = np.sin(dec)
        
        return np.array([x, y, z])

    def calculate_sun_distance(self, time: Union[datetime, List[datetime]]) -> Union[float, np.ndarray]:
        """
        计算日地距离 (AU)
        
        参数:
            time: 单个datetime或datetime列表
            
        返回:
            日地距离 (AU)
        """
        if isinstance(time, (list, np.ndarray)):
            return np.array([self._calc_sun_dist_single(t) for t in time])
        return self._calc_sun_dist_single(time)

    def _calc_sun_dist_single(self, time: datetime) -> float:
        """计算单个时间点的日地距离"""
        t = Time(time)
        sun = get_sun(t)
        return sun.distance.to(u.AU).value

    def calculate_solar_irradiance(self, time: Union[datetime, List[datetime]]) -> Union[float, np.ndarray]:
        """
        计算太阳辐照度 (考虑日地距离变化)
        
        参数:
            time: 单个datetime或datetime列表
            
        返回:
            太阳辐照度 (W/m^2)
        """
        distance_au = self.calculate_sun_distance(time)
        return SOLAR_CONSTANT / (distance_au ** 2)

    def calculate_eclipse(self, 
                          sat_position: np.ndarray, 
                          sun_vector: np.ndarray,
                          sun_distance_au: float) -> Tuple[float, bool, bool]:
        """
        计算地影因子 (圆柱近似模型 + 精确圆锥模型)
        
        参数:
            sat_position: 卫星位置矢量 (km, ECI)
            sun_vector: 太阳方向单位矢量 (ECI)
            sun_distance_au: 日地距离 (AU)
            
        返回:
            (eclipse_factor, is_umbra, is_penumbra)
            eclipse_factor: 1=完全光照, 0=完全本影, 中间值为半影
        """
        sun_distance = sun_distance_au * AU / 1000.0  # 转换为km
        
        sat_to_sun = sun_vector * sun_distance
        sat_mag = np.linalg.norm(sat_position)
        
        # 卫星到太阳方向的投影 (沿反太阳方向)
        proj = -np.dot(sat_position, sun_vector)
        
        if proj <= 0:
            return 1.0, False, False
        
        # 垂直距离
        perp_dist = np.sqrt(sat_mag ** 2 - proj ** 2)
        
        # 本影圆锥半顶角
        sun_angular_radius = np.arctan(self._sun_radius / sun_distance)
        earth_angular_radius = np.arctan(self._earth_radius / proj)
        
        # 本影和半影判断
        if perp_dist > self._earth_radius + self._sun_radius * proj / sun_distance:
            return 1.0, False, False
        elif perp_dist < self._earth_radius - self._sun_radius * proj / sun_distance:
            return 0.0, True, False
        else:
            # 半影区 - 计算被遮挡的太阳圆盘面积比例
            d = perp_dist
            R_s = self._sun_radius * proj / sun_distance
            R_e = self._earth_radius
            
            # 使用圆相交面积公式
            if d >= R_s + R_e:
                frac = 0.0
            elif d <= abs(R_e - R_s):
                r = min(R_s, R_e)
                frac = np.pi * r ** 2
            else:
                d_sq = d ** 2
                R_s_sq = R_s ** 2
                R_e_sq = R_e ** 2
                
                part1 = R_s_sq * np.arccos((d_sq + R_s_sq - R_e_sq) / (2 * d * R_s))
                part2 = R_e_sq * np.arccos((d_sq + R_e_sq - R_s_sq) / (2 * d * R_e))
                part3 = 0.5 * np.sqrt((-d + R_s + R_e) * (d + R_s - R_e) * (d - R_s + R_e) * (d + R_s + R_e))
                frac = part1 + part2 - part3
            
            sun_disk_area = np.pi * R_s ** 2
            eclipse_factor = 1.0 - frac / sun_disk_area
            
            return max(0.0, min(1.0, eclipse_factor)), False, True

    def calculate_albedo(self, 
                         sat_position: np.ndarray, 
                         sun_vector: np.ndarray,
                         surface_normal: np.ndarray = None) -> float:
        """
        计算地球反照辐射通量
        考虑各向异性反射模型 (忽略热点效应)
        
        参数:
            sat_position: 卫星位置矢量 (km, ECI)
            sun_vector: 太阳方向单位矢量 (ECI)
            surface_normal: 接收表面法向量 (单位矢量), None表示半球空间
            
        返回:
            反照辐射通量 (W/m^2)
        """
        sat_mag = np.linalg.norm(sat_position)
        sat_unit = sat_position / sat_mag
        
        # 计算地球圆盘对卫星的立体角
        earth_angular_radius = np.arcsin(self._earth_radius / sat_mag)
        sin_theta = np.sin(earth_angular_radius)
        projected_area = np.pi * (self._earth_radius * 1000) ** 2  # 转换为m^2
        r_squared = (sat_mag * 1000) ** 2
        
        # 计算太阳光照下的地球区域
        cos_sun_zenith = np.dot(-sat_unit, sun_vector)
        cos_sun_zenith = max(-1.0, min(1.0, cos_sun_zenith))
        
        if cos_sun_zenith <= 0:
            return 0.0
        
        # 各向异性反照模型
        # 考虑不同地表类型的反射特性和太阳天顶角影响
        # 参数来自MODIS观测数据统计，忽略热点效应
        solar_irradiance = SOLAR_CONSTANT
        
        # 地表类型加权平均 (海洋20%, 陆地40%, 云层40%)
        albedo_ocean = 0.06 + 0.08 * np.exp(-1.5 * (1.0 - cos_sun_zenith))
        albedo_land = 0.20 + 0.05 * cos_sun_zenith
        albedo_cloud = 0.45 + 0.08 * cos_sun_zenith ** 2
        
        weight_ocean = 0.20
        weight_land = 0.40
        weight_cloud = 0.40
        
        effective_albedo = (weight_ocean * albedo_ocean + 
                          weight_land * albedo_land + 
                          weight_cloud * albedo_cloud)
        
        # 限制有效反照率在合理范围内
        effective_albedo = min(effective_albedo, 0.45)
        
        # 各向异性反射的相位函数 (基于Hapke近似，忽略热点)
        # 观测角 (相对于地心方向)
        phase_angle = np.arccos(max(-1.0, min(1.0, cos_sun_zenith)))
        
        # 各向异性因子: 适度调整，避免过度校正
        # 在正午(小相位角)时略有增强，大相位角时有所衰减
        anisotropy_factor = (1.0 + 0.15 * np.exp(-phase_angle / 1.2) - 
                            0.05 * np.cos(phase_angle) ** 2)
        
        # 太阳天顶角的修正 (朗伯假设的修正)
        # 正午时略有增加，避免低估
        if cos_sun_zenith > 0.1:
            cos_correction = 1.0 + 0.15 * (1.0 - np.exp(-3.0 * cos_sun_zenith))
        else:
            cos_correction = 1.0
        
        # 限制校正因子范围
        cos_correction = min(max(cos_correction, 0.8), 1.3)
        anisotropy_factor = min(max(anisotropy_factor, 0.8), 1.3)
        
        albedo_intensity = (effective_albedo * solar_irradiance * cos_sun_zenith * 
                          cos_correction * anisotropy_factor / np.pi)
        
        # 几何因子
        if surface_normal is None:
            view_factor = sin_theta ** 2
        else:
            cos_view = max(0.0, np.dot(-sat_unit, surface_normal))
            view_factor = cos_view * sin_theta ** 2
        
        return albedo_intensity * projected_area / r_squared * view_factor * np.pi

    def calculate_earth_ir(self, 
                           sat_position: np.ndarray,
                           surface_normal: np.ndarray = None) -> float:
        """
        计算地球红外辐射通量
        
        参数:
            sat_position: 卫星位置矢量 (km, ECI)
            surface_normal: 接收表面法向量 (单位矢量), None表示半球空间
            
        返回:
            地球红外辐射通量 (W/m^2)
        """
        sat_mag = np.linalg.norm(sat_position)
        sat_unit = sat_position / sat_mag
        
        # 地球圆盘的立体角
        earth_angular_radius = np.arcsin(self._earth_radius / sat_mag)
        sin_theta = np.sin(earth_angular_radius)
        
        # 地球红外辐射 (假设为黑体辐射)
        earth_ir_intensity = EARTH_IR_FLUX / np.pi
        
        # 几何因子
        if surface_normal is None:
            view_factor = sin_theta ** 2
        else:
            cos_view = max(0.0, np.dot(-sat_unit, surface_normal))
            view_factor = cos_view * sin_theta ** 2
        
        return earth_ir_intensity * view_factor * np.pi

    def calculate_state(self, 
                        time: Union[datetime, List[datetime]],
                        sat_positions: Union[np.ndarray, List[np.ndarray]],
                        surface_normal: np.ndarray = None) -> Union[CelestialState, List[CelestialState]]:
        """
        计算完整的天体状态
        
        参数:
            time: 单个datetime或datetime列表
            sat_positions: 卫星位置 (km, ECI)
            surface_normal: 接收表面法向量
            
        返回:
            CelestialState或其列表
        """
        if isinstance(time, (list, np.ndarray)):
            return [self._calc_state_single(t, p, surface_normal) 
                   for t, p in zip(time, sat_positions)]
        return self._calc_state_single(time, sat_positions, surface_normal)

    def _calc_state_single(self, 
                           time: datetime, 
                           sat_position: np.ndarray,
                           surface_normal: np.ndarray) -> CelestialState:
        """计算单个时间点的天体状态"""
        sun_vector = self._calc_sun_single(time)
        sun_distance = self._calc_sun_dist_single(time)
        solar_irradiance = SOLAR_CONSTANT / (sun_distance ** 2)
        
        eclipse_factor, is_umbra, is_penumbra = self.calculate_eclipse(
            sat_position, sun_vector, sun_distance
        )
        
        albedo_flux = self.calculate_albedo(sat_position, sun_vector, surface_normal)
        earth_ir_flux = self.calculate_earth_ir(sat_position, surface_normal)
        
        return CelestialState(
            time=time,
            sun_vector_eci=sun_vector,
            sun_distance_au=sun_distance,
            solar_irradiance=solar_irradiance,
            eclipse_factor=eclipse_factor,
            is_umbra=is_umbra,
            is_penumbra=is_penumbra,
            albedo_flux=albedo_flux,
            earth_ir_flux=earth_ir_flux
        )

    def calculate_incident_irradiance(self, 
                                       sun_vector: np.ndarray,
                                       surface_normal: np.ndarray,
                                       solar_irradiance: float,
                                       eclipse_factor: float,
                                       albedo_flux: float = 0.0,
                                       earth_ir_flux: float = 0.0,
                                       include_environment: bool = True) -> float:
        """
        计算表面接收到的总辐照度
        
        参数:
            sun_vector: 太阳方向单位矢量
            surface_normal: 表面法向单位矢量
            solar_irradiance: 太阳辐照度 (W/m^2)
            eclipse_factor: 地影因子
            albedo_flux: 地球反照通量
            earth_ir_flux: 地球红外通量
            include_environment: 是否包含环境辐射
            
        返回:
            总辐照度 (W/m^2)
        """
        cos_incidence = np.dot(sun_vector, surface_normal)
        cos_incidence = max(0.0, cos_incidence)
        
        direct_irradiance = solar_irradiance * cos_incidence * eclipse_factor
        
        if include_environment:
            total = direct_irradiance + albedo_flux + earth_ir_flux
        else:
            total = direct_irradiance
        
        return max(0.0, total)
