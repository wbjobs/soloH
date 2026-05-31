"""
批量并行计算模块
Batch Parallel Processing Module

功能：
- 多卫星批量功率预测
- 基于joblib的并行计算
- 任务调度和负载均衡
- 结果聚合和统计
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Union
import numpy as np
from datetime import datetime
import pandas as pd
from joblib import Parallel, delayed, parallel_backend
import multiprocessing

from ..orbit.tle_propagator import TLEData
from ..power.power_predictor import (
    PowerPredictor, PowerPredictionResult, AttitudePoint, OrbitAveragePower
)
from ..solar_cell.diode_model import SolarArrayConfig, CellParameters
from ..occlusion.shadow_calculator import SolarArray, GeometryObject
from ..uncertainty.monte_carlo import (
    MonteCarloAnalyzer, MonteCarloResult, UncertaintyConfig
)


@dataclass
class SatelliteConfig:
    """单颗卫星配置"""
    satellite_id: str
    name: str
    tle_line1: str
    tle_line2: str
    f107: float = 100.0
    f107_avg: float = 100.0
    shield_thickness_mm: float = 2.0
    solar_array: Optional[SolarArray] = None
    occlusion_objects: Optional[List[GeometryObject]] = None
    array_config: Optional[SolarArrayConfig] = None
    attitude_sequence: Optional[List[AttitudePoint]] = None


@dataclass
class BatchResult:
    """批量计算结果"""
    satellite_results: Dict[str, PowerPredictionResult]
    total_compute_time: float
    n_satellites: int
    n_time_points: int

    def get_summary_dataframe(self) -> pd.DataFrame:
        """生成汇总DataFrame"""
        data = []
        for sat_id, result in self.satellite_results.items():
            oa = result.orbit_average
            data.append({
                'satellite_id': sat_id,
                'satellite_name': result.satellite_name,
                'orbit_period_s': oa.period_seconds,
                'average_power_W': oa.average_power,
                'average_current_A': oa.average_current,
                'peak_power_W': oa.peak_power,
                'minimum_power_W': oa.minimum_power,
                'eclipse_duration_s': oa.eclipse_duration,
                'sunlit_duration_s': oa.sunlit_duration,
                'total_energy_Wh': oa.total_energy,
                'remaining_factor': result.degradation_state.remaining_factor,
                'cumulative_ddd_MeVg': result.degradation_state.cumulative_ddd,
            })
        return pd.DataFrame(data)

    def get_all_time_series(self) -> pd.DataFrame:
        """获取所有卫星的时间序列数据"""
        dfs = []
        for sat_id, result in self.satellite_results.items():
            df = result.to_dataframe()
            df['satellite_id'] = sat_id
            df['satellite_name'] = result.satellite_name
            dfs.append(df)
        return pd.concat(dfs, ignore_index=True)

    def get_orbit_average_summary(self) -> Dict[str, float]:
        """获取所有卫星的轨道平均统计"""
        avg_powers = [r.orbit_average.average_power for r in self.satellite_results.values()]
        avg_currents = [r.orbit_average.average_current for r in self.satellite_results.values()]
        peak_powers = [r.orbit_average.peak_power for r in self.satellite_results.values()]
        
        return {
            'mean_average_power': np.mean(avg_powers),
            'std_average_power': np.std(avg_powers),
            'min_average_power': np.min(avg_powers),
            'max_average_power': np.max(avg_powers),
            'mean_average_current': np.mean(avg_currents),
            'std_average_current': np.std(avg_currents),
            'mean_peak_power': np.mean(peak_powers),
            'total_power': np.sum(avg_powers),
        }


@dataclass
class BatchConfig:
    """批量计算配置"""
    start_time: datetime
    end_time: Optional[datetime] = None
    time_step_sec: float = 1.0
    n_orbits: Optional[int] = None
    n_jobs: int = -1  # -1表示使用所有CPU核心
    backend: str = 'loky'  # 'loky', 'multiprocessing', 'threading'
    verbose: int = 1
    include_monte_carlo: bool = False
    mc_n_samples: int = 100
    mc_confidence_level: float = 0.95
    operating_voltage: Optional[float] = None
    initial_temperature: float = 298.15  # 25°C


class BatchProcessor:
    """
    批量处理器
    支持多卫星并行功率预测
    """

    def __init__(self, 
                 satellites: List[SatelliteConfig],
                 batch_config: BatchConfig):
        """
        初始化批量处理器
        
        参数:
            satellites: 卫星配置列表
            batch_config: 批量计算配置
        """
        self.satellites = {s.satellite_id: s for s in satellites}
        self.config = batch_config
        self._available_cores = multiprocessing.cpu_count()

    def _process_single_satellite(self,
                                    sat_config: SatelliteConfig,
                                    config: BatchConfig) -> Tuple[str, PowerPredictionResult]:
        """
        处理单颗卫星的功率预测
        
        参数:
            sat_config: 卫星配置
            config: 批量配置
            
        返回:
            (卫星ID, 预测结果)
        """
        try:
            tle_data = TLEData(
                name=sat_config.name,
                line1=sat_config.tle_line1,
                line2=sat_config.tle_line2
            )
            
            predictor = PowerPredictor(
                tle_data=tle_data,
                solar_array=sat_config.solar_array,
                occlusion_objects=sat_config.occlusion_objects,
                array_config=sat_config.array_config,
                f107=sat_config.f107,
                f107_avg=sat_config.f107_avg,
                shield_thickness_mm=sat_config.shield_thickness_mm
            )
            
            if config.n_orbits is not None:
                result = predictor.predict_multi_orbit(
                    n_orbits=config.n_orbits,
                    start_time=config.start_time,
                    time_step_sec=config.time_step_sec,
                    attitude_sequence=sat_config.attitude_sequence,
                    initial_temperature=config.initial_temperature,
                    operating_voltage=config.operating_voltage
                )
            else:
                result = predictor.predict(
                    start_time=config.start_time,
                    end_time=config.end_time,
                    time_step_sec=config.time_step_sec,
                    attitude_sequence=sat_config.attitude_sequence,
                    initial_temperature=config.initial_temperature,
                    operating_voltage=config.operating_voltage
                )
            
            return sat_config.satellite_id, result
            
        except Exception as e:
            print(f"卫星 {sat_config.name} ({sat_config.satellite_id}) 计算失败: {e}")
            return sat_config.satellite_id, None

    def _process_single_satellite_mc(self,
                                      sat_config: SatelliteConfig,
                                      config: BatchConfig) -> Tuple[str, Optional[MonteCarloResult]]:
        """
        处理单颗卫星的蒙特卡洛分析
        
        参数:
            sat_config: 卫星配置
            config: 批量配置
            
        返回:
            (卫星ID, 蒙特卡洛结果)
        """
        try:
            tle_data = TLEData(
                name=sat_config.name,
                line1=sat_config.tle_line1,
                line2=sat_config.tle_line2
            )
            
            predictor = PowerPredictor(
                tle_data=tle_data,
                solar_array=sat_config.solar_array,
                occlusion_objects=sat_config.occlusion_objects,
                array_config=sat_config.array_config,
                f107=sat_config.f107,
                f107_avg=sat_config.f107_avg,
                shield_thickness_mm=sat_config.shield_thickness_mm
            )
            
            mc_config = UncertaintyConfig(
                n_samples=config.mc_n_samples,
                confidence_level=config.mc_confidence_level
            )
            
            analyzer = MonteCarloAnalyzer(predictor, mc_config)
            
            if config.n_orbits is not None:
                orbit_period = predictor.orbit_propagator.get_orbit_period()
                end_time = config.start_time + np.timedelta64(int(config.n_orbits * orbit_period), 's')
                end_time = end_time.astype(datetime)
            else:
                end_time = config.end_time
            
            mc_result = analyzer.analyze(
                start_time=config.start_time,
                end_time=end_time,
                time_step_sec=config.time_step_sec,
                attitude_sequence=sat_config.attitude_sequence,
                show_progress=False
            )
            
            return sat_config.satellite_id, mc_result
            
        except Exception as e:
            print(f"卫星 {sat_config.name} ({sat_config.satellite_id}) 蒙特卡洛分析失败: {e}")
            return sat_config.satellite_id, None

    def run(self) -> BatchResult:
        """
        执行批量功率预测
        
        返回:
            BatchResult
        """
        import time
        start_time = time.time()
        
        n_jobs = self.config.n_jobs
        if n_jobs == -1:
            n_jobs = self._available_cores
        
        if self.config.verbose > 0:
            print(f"开始批量处理 {len(self.satellites)} 颗卫星...")
            print(f"使用 {n_jobs} 个CPU核心，后端: {self.config.backend}")
        
        satellite_list = list(self.satellites.values())
        
        with parallel_backend(self.config.backend, n_jobs=n_jobs):
            results = Parallel(verbose=self.config.verbose)(
                delayed(self._process_single_satellite)(sat_config, self.config)
                for sat_config in satellite_list
            )
        
        satellite_results = {}
        for sat_id, result in results:
            if result is not None:
                satellite_results[sat_id] = result
        
        total_time = time.time() - start_time
        
        if self.config.verbose > 0:
            print(f"批量处理完成，总耗时: {total_time:.2f} 秒")
            print(f"成功处理 {len(satellite_results)}/{len(self.satellites)} 颗卫星")
        
        n_time_points = 0
        if satellite_results:
            first_result = next(iter(satellite_results.values()))
            n_time_points = len(first_result.time_series)
        
        return BatchResult(
            satellite_results=satellite_results,
            total_compute_time=total_time,
            n_satellites=len(satellite_results),
            n_time_points=n_time_points
        )

    def run_monte_carlo(self) -> Dict[str, Optional[MonteCarloResult]]:
        """
        执行批量蒙特卡洛分析
        
        返回:
            {卫星ID: MonteCarloResult} 字典
        """
        import time
        start_time = time.time()
        
        n_jobs = self.config.n_jobs
        if n_jobs == -1:
            n_jobs = self._available_cores
        
        if self.config.verbose > 0:
            print(f"开始批量蒙特卡洛分析 {len(self.satellites)} 颗卫星...")
            print(f"每颗卫星样本数: {self.config.mc_n_samples}")
            print(f"使用 {n_jobs} 个CPU核心，后端: {self.config.backend}")
        
        satellite_list = list(self.satellites.values())
        
        with parallel_backend(self.config.backend, n_jobs=n_jobs):
            results = Parallel(verbose=self.config.verbose)(
                delayed(self._process_single_satellite_mc)(sat_config, self.config)
                for sat_config in satellite_list
            )
        
        mc_results = {}
        for sat_id, result in results:
            mc_results[sat_id] = result
        
        total_time = time.time() - start_time
        
        if self.config.verbose > 0:
            n_success = sum(1 for r in mc_results.values() if r is not None)
            print(f"批量蒙特卡洛分析完成，总耗时: {total_time:.2f} 秒")
            print(f"成功处理 {n_success}/{len(self.satellites)} 颗卫星")
        
        return mc_results

    def run_combined(self) -> Tuple[BatchResult, Dict[str, Optional[MonteCarloResult]]]:
        """
        执行完整的批量计算：功率预测 + 蒙特卡洛分析
        
        返回:
            (批量结果, 蒙特卡洛结果字典)
        """
        batch_result = self.run()
        
        if self.config.include_monte_carlo:
            mc_results = self.run_monte_carlo()
        else:
            mc_results = {sat_id: None for sat_id in self.satellites.keys()}
        
        return batch_result, mc_results

    def add_satellite(self, sat_config: SatelliteConfig):
        """添加卫星配置"""
        self.satellites[sat_config.satellite_id] = sat_config

    def remove_satellite(self, satellite_id: str):
        """移除卫星配置"""
        if satellite_id in self.satellites:
            del self.satellites[satellite_id]

    def get_satellite_config(self, satellite_id: str) -> Optional[SatelliteConfig]:
        """获取卫星配置"""
        return self.satellites.get(satellite_id)

    @classmethod
    def from_tle_file(cls,
                       tle_file_path: str,
                       batch_config: BatchConfig,
                       default_f107: float = 100.0,
                       default_f107_avg: float = 100.0) -> 'BatchProcessor':
        """
        从TLE文件创建批量处理器
        
        参数:
            tle_file_path: TLE文件路径
            batch_config: 批量配置
            default_f107: 默认F10.7指数
            default_f107_avg: 默认平均F10.7指数
            
        返回:
            BatchProcessor实例
        """
        satellites = []
        
        with open(tle_file_path, 'r') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        
        i = 0
        while i < len(lines):
            if i + 2 < len(lines):
                name = lines[i] if not lines[i].startswith('1 ') else f"SAT_{i//3}"
                
                if lines[i].startswith('1 '):
                    line1 = lines[i]
                    line2 = lines[i + 1]
                    sat_id = f"SAT_{i//3}"
                    i += 2
                else:
                    line1 = lines[i + 1]
                    line2 = lines[i + 2]
                    sat_id = f"SAT_{i//3}"
                    i += 3
                
                sat_config = SatelliteConfig(
                    satellite_id=sat_id,
                    name=name,
                    tle_line1=line1,
                    tle_line2=line2,
                    f107=default_f107,
                    f107_avg=default_f107_avg
                )
                satellites.append(sat_config)
            else:
                break
        
        return cls(satellites, batch_config)
