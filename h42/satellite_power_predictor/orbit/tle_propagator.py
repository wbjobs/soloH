"""
轨道计算模块
Orbit Calculation Module

功能：
- TLE (Two-Line Element) 解析
- SGP4 (Simplified General Perturbations 4) 轨道传播
- 卫星位置、速度、轨道周期计算
- 坐标系转换 (TEME -> ECI -> 卫星本体坐标系)
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Union
import numpy as np
from datetime import datetime, timedelta

from sgp4.api import Satrec, jday
from sgp4 import exporter

from ..utils.constants import EARTH_MU, DEG2RAD, RAD2DEG, SEC_PER_DAY


@dataclass
class TLEData:
    """TLE数据结构"""
    name: str
    line1: str
    line2: str
    epoch: datetime = None
    norad_id: int = None
    inclination: float = None  # deg
    raan: float = None  # deg, 升交点赤经
    eccentricity: float = None
    arg_perigee: float = None  # deg, 近地点幅角
    mean_anomaly: float = None  # deg, 平近点角
    mean_motion: float = None  # rev/day, 平均运动
    bstar: float = None  # 大气阻力系数

    def __post_init__(self):
        self._parse_tle()

    def _parse_tle(self):
        """解析TLE两行数据"""
        try:
            self.norad_id = int(self.line1[2:7])
            epoch_year = int(self.line1[18:20])
            epoch_day = float(self.line1[20:32])
            
            if epoch_year < 57:
                epoch_year += 2000
            else:
                epoch_year += 1900
            
            self.epoch = datetime(epoch_year, 1, 1) + timedelta(days=epoch_day - 1)
            self.bstar = float(self.line1[53:59] + 'e' + self.line1[59:61])
            
            self.inclination = float(self.line2[8:16])
            self.raan = float(self.line2[17:25])
            self.eccentricity = float('0.' + self.line2[26:33])
            self.arg_perigee = float(self.line2[34:42])
            self.mean_anomaly = float(self.line2[43:51])
            self.mean_motion = float(self.line2[52:63])
            
        except Exception as e:
            raise ValueError(f"TLE解析失败: {e}")

    def get_orbital_period(self) -> float:
        """计算轨道周期 (秒)"""
        return SEC_PER_DAY / self.mean_motion

    def get_semi_major_axis(self) -> float:
        """计算半长轴 (km)"""
        n_rad_s = self.mean_motion * 2 * np.pi / SEC_PER_DAY
        return (EARTH_MU / n_rad_s ** 2) ** (1.0 / 3.0)

    def get_altitude(self) -> float:
        """计算平均轨道高度 (km)"""
        from ..utils.constants import EARTH_RADIUS
        a = self.get_semi_major_axis()
        return a * (1 - self.eccentricity ** 2) - EARTH_RADIUS


@dataclass
class OrbitState:
    """轨道状态数据结构"""
    time: datetime
    position: np.ndarray  # km, ECI坐标系
    velocity: np.ndarray  # km/s, ECI坐标系
    error: int = 0

    @property
    def altitude(self) -> float:
        """轨道高度 (km)"""
        from ..utils.constants import EARTH_RADIUS
        return np.linalg.norm(self.position) - EARTH_RADIUS

    @property
    def speed(self) -> float:
        """速度大小 (km/s)"""
        return np.linalg.norm(self.velocity)


class TLEPropagator:
    """
    TLE轨道传播器
    使用SGP4模型进行轨道传播
    """

    def __init__(self, tle: TLEData):
        """
        初始化轨道传播器
        
        参数:
            tle: TLEData对象
        """
        self.tle = tle
        self.satellite = Satrec.twoline2rv(tle.line1, tle.line2)

    @classmethod
    def from_lines(cls, name: str, line1: str, line2: str) -> 'TLEPropagator':
        """
        从TLE两行创建传播器
        
        参数:
            name: 卫星名称
            line1: TLE第一行
            line2: TLE第二行
            
        返回:
            TLEPropagator实例
        """
        tle = TLEData(name=name, line1=line1, line2=line2)
        return cls(tle)

    def propagate(self, time: Union[datetime, List[datetime]]) -> Union[OrbitState, List[OrbitState]]:
        """
        传播轨道到指定时间
        
        参数:
            time: 单个datetime或datetime列表
            
        返回:
            单个OrbitState或OrbitState列表
        """
        if isinstance(time, (list, np.ndarray)):
            return [self._propagate_single(t) for t in time]
        return self._propagate_single(time)

    def _propagate_single(self, time: datetime) -> OrbitState:
        """传播到单个时间点"""
        jd, fr = jday(time.year, time.month, time.day, 
                      time.hour, time.minute, 
                      time.second + time.microsecond / 1e6)
        
        e, r, v = self.satellite.sgp4(jd, fr)
        
        return OrbitState(
            time=time,
            position=np.array(r),
            velocity=np.array(v),
            error=e
        )

    def propagate_sequence(self, start_time: datetime, 
                           end_time: datetime, 
                           step_sec: float = 1.0) -> Tuple[List[datetime], List[OrbitState]]:
        """
        传播一段时间序列
        
        参数:
            start_time: 开始时间
            end_time: 结束时间
            step_sec: 时间步长 (秒)
            
        返回:
            (时间列表, 轨道状态列表)
        """
        duration = (end_time - start_time).total_seconds()
        n_steps = int(duration / step_sec) + 1
        
        times = [start_time + timedelta(seconds=i * step_sec) for i in range(n_steps)]
        states = self.propagate(times)
        
        return times, states

    def get_orbit_period(self) -> float:
        """获取轨道周期 (秒)"""
        return self.tle.get_orbital_period()

    def get_orbital_elements(self, time: Optional[datetime] = None) -> dict:
        """
        获取指定时刻的轨道根数
        
        参数:
            time: 时间点，None表示使用TLE历元
            
        返回:
            轨道参数字典
        """
        if time is None:
            return {
                'inclination': self.tle.inclination * DEG2RAD,
                'raan': self.tle.raan * DEG2RAD,
                'eccentricity': self.tle.eccentricity,
                'arg_perigee': self.tle.arg_perigee * DEG2RAD,
                'mean_anomaly': self.tle.mean_anomaly * DEG2RAD,
                'semi_major_axis': self.tle.get_semi_major_axis()
            }
        
        state = self._propagate_single(time)
        r = state.position
        v = state.velocity
        
        h = np.cross(r, v)
        h_mag = np.linalg.norm(h)
        
        k = np.array([0, 0, 1])
        n = np.cross(k, h)
        n_mag = np.linalg.norm(n)
        
        r_mag = np.linalg.norm(r)
        v_mag = np.linalg.norm(v)
        
        e_vec = (v_mag ** 2 - EARTH_MU / r_mag) * r / EARTH_MU - np.dot(r, v) * v / EARTH_MU
        e = np.linalg.norm(e_vec)
        
        a = 1 / (2 / r_mag - v_mag ** 2 / EARTH_MU)
        
        i = np.arccos(h[2] / h_mag)
        
        raan = np.arccos(n[0] / n_mag) if n_mag > 0 else 0
        if n[1] < 0:
            raan = 2 * np.pi - raan
        
        argp = np.arccos(np.dot(n, e_vec) / (n_mag * e)) if n_mag > 0 and e > 0 else 0
        if e_vec[2] < 0:
            argp = 2 * np.pi - argp
        
        nu = np.arccos(np.dot(e_vec, r) / (e * r_mag)) if e > 0 else 0
        if np.dot(r, v) < 0:
            nu = 2 * np.pi - nu
        
        M = nu - 2 * e * np.sin(nu) + (3 * e ** 2 / 4 - e ** 4 / 8) * np.sin(2 * nu)
        
        return {
            'inclination': i,
            'raan': raan,
            'eccentricity': e,
            'arg_perigee': argp,
            'mean_anomaly': M,
            'semi_major_axis': a,
            'true_anomaly': nu
        }

    def export_tle(self) -> Tuple[str, str]:
        """导出当前TLE"""
        return exporter.export_tle(self.satellite)
