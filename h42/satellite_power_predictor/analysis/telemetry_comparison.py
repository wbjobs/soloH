"""
遥测数据对比与误差统计模块
Telemetry Comparison and Error Statistics Module

功能：
- 预测结果与遥测数据对比
- 误差统计分析 (MAE, MSE, RMSE, MAPE)
- 相关性分析
- 偏差分析
- 统计检验
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Union
import numpy as np
import pandas as pd
from datetime import datetime
from scipy import stats

from ..power.power_predictor import PowerPredictionResult


@dataclass
class TelemetryData:
    """遥测数据结构"""
    time: List[datetime]
    current: np.ndarray  # A, 母线电流
    voltage: np.ndarray  # V, 母线电压
    power: np.ndarray  # W, 输出功率
    temperature: Optional[np.ndarray] = None  # K, 电池温度
    irradiance: Optional[np.ndarray] = None  # W/m^2, 实测辐照度
    flags: Optional[np.ndarray] = None  # 数据质量标记

    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame"""
        data = {
            'time': self.time,
            'current_A': self.current,
            'voltage_V': self.voltage,
            'power_W': self.power,
        }
        if self.temperature is not None:
            data['temperature_K'] = self.temperature
        if self.irradiance is not None:
            data['irradiance_Wm2'] = self.irradiance
        if self.flags is not None:
            data['flags'] = self.flags
        return pd.DataFrame(data)


@dataclass
class ErrorStatistics:
    """误差统计结果"""
    parameter: str  # 'current', 'power', 'voltage', 'temperature'
    n_samples: int
    
    # 绝对误差
    mae: float  # Mean Absolute Error
    mse: float  # Mean Squared Error
    rmse: float  # Root Mean Squared Error
    mae_percent: float  # MAE百分比 (相对于均值)
    rmse_percent: float  # RMSE百分比
    
    # 相对误差
    mape: float  # Mean Absolute Percentage Error
    smape: float  # Symmetric Mean Absolute Percentage Error
    
    # 偏差分析
    mean_bias: float  # 平均偏差 (预测 - 实测)
    mean_bias_percent: float  # 平均偏差百分比
    max_error: float  # 最大绝对误差
    min_error: float  # 最小绝对误差
    std_error: float  # 误差标准差
    
    # 相关性
    correlation_coefficient: float  # Pearson相关系数
    spearman_rho: float  # Spearman秩相关系数
    r_squared: float  # 决定系数 R²
    
    # 统计检验
    t_statistic: float  # t检验统计量
    p_value: float  # t检验p值
    shapiro_stat: float  # Shapiro-Wilk正态性检验
    shapiro_p: float  # 正态性检验p值
    
    # 分位数误差
    error_percentiles: Dict[float, float]  # {5: err, 25: err, 50: err, 75: err, 95: err}
    
    # 原始数据
    predicted: np.ndarray
    measured: np.ndarray
    errors: np.ndarray
    time: List[datetime]


@dataclass
class ComparisonResult:
    """完整对比结果"""
    satellite_name: str
    comparison_period: Tuple[datetime, datetime]
    n_matching_points: int
    
    current_stats: Optional[ErrorStatistics]
    power_stats: Optional[ErrorStatistics]
    voltage_stats: Optional[ErrorStatistics]
    temperature_stats: Optional[ErrorStatistics]
    
    summary: Dict[str, float]
    
    def get_summary_dataframe(self) -> pd.DataFrame:
        """获取汇总DataFrame"""
        data = []
        for param in ['current', 'power', 'voltage', 'temperature']:
            stats = getattr(self, f'{param}_stats')
            if stats is not None:
                data.append({
                    'parameter': param,
                    'n_samples': stats.n_samples,
                    'MAE': stats.mae,
                    'RMSE': stats.rmse,
                    'MAPE_%': stats.mape,
                    'SMAPE_%': stats.smape,
                    'Mean_Bias': stats.mean_bias,
                    'Mean_Bias_%': stats.mean_bias_percent,
                    'Correlation': stats.correlation_coefficient,
                    'R_squared': stats.r_squared,
                    'p_value': stats.p_value,
                })
        return pd.DataFrame(data)


class TelemetryComparator:
    """
    遥测数据比较器
    对比预测结果与实际遥测数据，计算误差统计
    """

    def __init__(self):
        """初始化比较器"""
        pass

    def _align_time_series(self,
                            pred_times: List[datetime],
                            pred_values: np.ndarray,
                            telem_times: List[datetime],
                            telem_values: np.ndarray,
                            max_time_diff_sec: float = 5.0) -> Tuple[np.ndarray, np.ndarray, List[datetime]]:
        """
        时间序列对齐
        
        参数:
            pred_times: 预测时间点
            pred_values: 预测值
            telem_times: 遥测时间点
            telem_values: 遥测值
            max_time_diff_sec: 最大允许时间差 (秒)
            
        返回:
            (对齐后的预测值, 对齐后的遥测值, 对齐后的时间点)
        """
        pred_times_arr = np.array(pred_times)
        telem_times_arr = np.array(telem_times)
        
        aligned_pred = []
        aligned_telem = []
        aligned_times = []
        
        for i, p_time in enumerate(pred_times_arr):
            time_diffs = np.abs([(t - p_time).total_seconds() for t in telem_times_arr])
            min_idx = np.argmin(time_diffs)
            
            if time_diffs[min_idx] <= max_time_diff_sec:
                aligned_pred.append(pred_values[i])
                aligned_telem.append(telem_values[min_idx])
                aligned_times.append(p_time)
        
        return (np.array(aligned_pred), 
                np.array(aligned_telem), 
                aligned_times)

    def _calculate_error_stats(self,
                                predicted: np.ndarray,
                                measured: np.ndarray,
                                times: List[datetime],
                                parameter_name: str) -> ErrorStatistics:
        """
        计算误差统计量
        
        参数:
            predicted: 预测值
            measured: 实测值
            times: 时间点
            parameter_name: 参数名称
            
        返回:
            ErrorStatistics
        """
        n = len(predicted)
        if n == 0:
            return ErrorStatistics(
                parameter=parameter_name,
                n_samples=0,
                mae=0, mse=0, rmse=0, mae_percent=0, rmse_percent=0,
                mape=0, smape=0,
                mean_bias=0, mean_bias_percent=0,
                max_error=0, min_error=0, std_error=0,
                correlation_coefficient=0, spearman_rho=0, r_squared=0,
                t_statistic=0, p_value=1.0,
                shapiro_stat=0, shapiro_p=1.0,
                error_percentiles={},
                predicted=predicted, measured=measured,
                errors=np.array([]), time=times
            )
        
        errors = predicted - measured
        abs_errors = np.abs(errors)
        
        mae = np.mean(abs_errors)
        mse = np.mean(errors ** 2)
        rmse = np.sqrt(mse)
        
        measured_mean = np.mean(measured)
        mae_percent = (mae / measured_mean * 100) if measured_mean != 0 else 0
        rmse_percent = (rmse / measured_mean * 100) if measured_mean != 0 else 0
        
        # MAPE和SMAPE
        with np.errstate(divide='ignore', invalid='ignore'):
            mape = np.mean(np.abs(errors) / np.abs(measured) * 100)
            smape = np.mean(2 * abs_errors / (np.abs(predicted) + np.abs(measured)) * 100)
        
        mape = 0 if np.isnan(mape) else min(mape, 1000)
        smape = 0 if np.isnan(smape) else min(smape, 1000)
        
        mean_bias = np.mean(errors)
        mean_bias_percent = (mean_bias / measured_mean * 100) if measured_mean != 0 else 0
        
        max_error = np.max(abs_errors)
        min_error = np.min(abs_errors)
        std_error = np.std(errors, ddof=1)
        
        # 相关性
        if np.std(predicted) > 0 and np.std(measured) > 0:
            corr, _ = stats.pearsonr(predicted, measured)
            spearman, _ = stats.spearmanr(predicted, measured)
        else:
            corr = 0
            spearman = 0
        
        # R²
        ss_res = np.sum(errors ** 2)
        ss_tot = np.sum((measured - measured_mean) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # t检验 (检验误差均值是否显著不为零)
        if std_error > 0 and n > 1:
            t_stat, p_val = stats.ttest_1samp(errors, 0)
        else:
            t_stat = 0
            p_val = 1.0
        
        # 正态性检验
        if n >= 3:
            shapiro_stat, shapiro_p = stats.shapiro(errors)
        else:
            shapiro_stat = 0
            shapiro_p = 1.0
        
        # 误差分位数
        percentiles = [5, 25, 50, 75, 95]
        error_percentiles = {p: np.percentile(errors, p) for p in percentiles}
        
        return ErrorStatistics(
            parameter=parameter_name,
            n_samples=n,
            mae=mae, mse=mse, rmse=rmse,
            mae_percent=mae_percent, rmse_percent=rmse_percent,
            mape=mape, smape=smape,
            mean_bias=mean_bias, mean_bias_percent=mean_bias_percent,
            max_error=max_error, min_error=min_error, std_error=std_error,
            correlation_coefficient=corr, spearman_rho=spearman, r_squared=r_squared,
            t_statistic=t_stat, p_value=p_val,
            shapiro_stat=shapiro_stat, shapiro_p=shapiro_p,
            error_percentiles=error_percentiles,
            predicted=predicted, measured=measured,
            errors=errors, time=times
        )

    def compare(self,
                 prediction_result: PowerPredictionResult,
                 telemetry_data: TelemetryData,
                 max_time_diff_sec: float = 5.0,
                 parameters: List[str] = None) -> ComparisonResult:
        """
        执行预测结果与遥测数据的对比
        
        参数:
            prediction_result: 功率预测结果
            telemetry_data: 遥测数据
            max_time_diff_sec: 最大允许时间差 (秒)
            parameters: 要对比的参数列表
            
        返回:
            ComparisonResult
        """
        if parameters is None:
            parameters = ['current', 'power', 'voltage']
        
        pred_times = [pt.time for pt in prediction_result.time_series]
        pred_currents = np.array([pt.array_current for pt in prediction_result.time_series])
        pred_voltages = np.array([pt.array_voltage for pt in prediction_result.time_series])
        pred_powers = np.array([pt.array_power for pt in prediction_result.time_series])
        pred_temps = np.array([pt.cell_temperature for pt in prediction_result.time_series])
        
        period_start = min(pred_times[0], telemetry_data.time[0])
        period_end = max(pred_times[-1], telemetry_data.time[-1])
        
        stats = {}
        n_matching = 0
        
        if 'current' in parameters and telemetry_data.current is not None:
            pred_aligned, telem_aligned, times_aligned = self._align_time_series(
                pred_times, pred_currents,
                telemetry_data.time, telemetry_data.current,
                max_time_diff_sec
            )
            n_matching = len(times_aligned)
            stats['current'] = self._calculate_error_stats(
                pred_aligned, telem_aligned, times_aligned, 'current'
            )
        else:
            stats['current'] = None
        
        if 'power' in parameters and telemetry_data.power is not None:
            pred_aligned, telem_aligned, times_aligned = self._align_time_series(
                pred_times, pred_powers,
                telemetry_data.time, telemetry_data.power,
                max_time_diff_sec
            )
            if n_matching == 0:
                n_matching = len(times_aligned)
            stats['power'] = self._calculate_error_stats(
                pred_aligned, telem_aligned, times_aligned, 'power'
            )
        else:
            stats['power'] = None
        
        if 'voltage' in parameters and telemetry_data.voltage is not None:
            pred_aligned, telem_aligned, times_aligned = self._align_time_series(
                pred_times, pred_voltages,
                telemetry_data.time, telemetry_data.voltage,
                max_time_diff_sec
            )
            if n_matching == 0:
                n_matching = len(times_aligned)
            stats['voltage'] = self._calculate_error_stats(
                pred_aligned, telem_aligned, times_aligned, 'voltage'
            )
        else:
            stats['voltage'] = None
        
        if 'temperature' in parameters and telemetry_data.temperature is not None:
            pred_aligned, telem_aligned, times_aligned = self._align_time_series(
                pred_times, pred_temps,
                telemetry_data.time, telemetry_data.temperature,
                max_time_diff_sec
            )
            if n_matching == 0:
                n_matching = len(times_aligned)
            stats['temperature'] = self._calculate_error_stats(
                pred_aligned, telem_aligned, times_aligned, 'temperature'
            )
        else:
            stats['temperature'] = None
        
        # 生成汇总
        summary = {}
        for param in ['current', 'power', 'voltage', 'temperature']:
            if stats[param] is not None:
                summary[f'{param}_mae'] = stats[param].mae
                summary[f'{param}_rmse'] = stats[param].rmse
                summary[f'{param}_mape'] = stats[param].mape
                summary[f'{param}_correlation'] = stats[param].correlation_coefficient
                summary[f'{param}_r2'] = stats[param].r_squared
                summary[f'{param}_mean_bias'] = stats[param].mean_bias
        
        return ComparisonResult(
            satellite_name=prediction_result.satellite_name,
            comparison_period=(period_start, period_end),
            n_matching_points=n_matching,
            current_stats=stats['current'],
            power_stats=stats['power'],
            voltage_stats=stats['voltage'],
            temperature_stats=stats['temperature'],
            summary=summary
        )

    def compare_batch(self,
                       batch_result: 'BatchResult',
                       telemetry_data_dict: Dict[str, TelemetryData],
                       **kwargs) -> Dict[str, ComparisonResult]:
        """
        批量对比多颗卫星的预测结果
        
        参数:
            batch_result: 批量预测结果
            telemetry_data_dict: {卫星ID: 遥测数据} 字典
            **kwargs: 其他compare方法参数
            
        返回:
            {卫星ID: ComparisonResult} 字典
        """
        results = {}
        for sat_id, pred_result in batch_result.satellite_results.items():
            if sat_id in telemetry_data_dict:
                results[sat_id] = self.compare(
                    pred_result, telemetry_data_dict[sat_id], **kwargs
                )
        return results

    def generate_comparison_report(self,
                                    comparison_result: ComparisonResult,
                                    output_path: str = None) -> str:
        """
        生成对比报告文本
        
        参数:
            comparison_result: 对比结果
            output_path: 输出文件路径
            
        返回:
            报告文本
        """
        lines = []
        lines.append("=" * 80)
        lines.append("卫星功率预测与遥测数据对比报告")
        lines.append("=" * 80)
        lines.append(f"卫星名称: {comparison_result.satellite_name}")
        lines.append(f"对比周期: {comparison_result.comparison_period[0]} ~ {comparison_result.comparison_period[1]}")
        lines.append(f"匹配数据点: {comparison_result.n_matching_points}")
        lines.append("")
        
        for param in ['current', 'power', 'voltage', 'temperature']:
            stats = getattr(comparison_result, f'{param}_stats')
            if stats is None or stats.n_samples == 0:
                continue
            
            lines.append("-" * 80)
            lines.append(f"{param.upper()} 误差统计")
            lines.append("-" * 80)
            lines.append(f"样本数: {stats.n_samples}")
            lines.append("")
            lines.append("绝对误差:")
            lines.append(f"  平均绝对误差 (MAE): {stats.mae:.6f}")
            lines.append(f"  均方误差 (MSE): {stats.mse:.6f}")
            lines.append(f"  均方根误差 (RMSE): {stats.rmse:.6f}")
            lines.append(f"  MAE/均值: {stats.mae_percent:.2f}%")
            lines.append(f"  RMSE/均值: {stats.rmse_percent:.2f}%")
            lines.append("")
            lines.append("相对误差:")
            lines.append(f"  平均绝对百分比误差 (MAPE): {stats.mape:.2f}%")
            lines.append(f"  对称平均绝对百分比误差 (SMAPE): {stats.smape:.2f}%")
            lines.append("")
            lines.append("偏差分析:")
            lines.append(f"  平均偏差 (预测-实测): {stats.mean_bias:.6f}")
            lines.append(f"  平均偏差百分比: {stats.mean_bias_percent:.2f}%")
            lines.append(f"  最大绝对误差: {stats.max_error:.6f}")
            lines.append(f"  最小绝对误差: {stats.min_error:.6f}")
            lines.append(f"  误差标准差: {stats.std_error:.6f}")
            lines.append("")
            lines.append("相关性:")
            lines.append(f"  Pearson相关系数: {stats.correlation_coefficient:.6f}")
            lines.append(f"  Spearman秩相关系数: {stats.spearman_rho:.6f}")
            lines.append(f"  决定系数 R²: {stats.r_squared:.6f}")
            lines.append("")
            lines.append("统计检验:")
            lines.append(f"  t检验统计量: {stats.t_statistic:.6f}")
            lines.append(f"  t检验p值: {stats.p_value:.6f}")
            lines.append(f"  显著性: {'是' if stats.p_value < 0.05 else '否'} (α=0.05)")
            lines.append(f"  Shapiro-Wilk统计量: {stats.shapiro_stat:.6f}")
            lines.append(f"  正态性检验p值: {stats.shapiro_p:.6f}")
            lines.append(f"  正态分布: {'是' if stats.shapiro_p > 0.05 else '否'} (α=0.05)")
            lines.append("")
            lines.append("误差分位数:")
            for p in [5, 25, 50, 75, 95]:
                lines.append(f"  {p}%分位数: {stats.error_percentiles[p]:.6f}")
            lines.append("")
        
        report = "\n".join(lines)
        
        if output_path is not None:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"报告已保存至: {output_path}")
        
        return report

    def load_telemetry_from_csv(self, csv_path: str,
                                 time_col: str = 'time',
                                 current_col: str = 'current_A',
                                 voltage_col: str = 'voltage_V',
                                 power_col: str = 'power_W',
                                 temp_col: str = None,
                                 irradiance_col: str = None,
                                 time_format: str = '%Y-%m-%d %H:%M:%S') -> TelemetryData:
        """
        从CSV文件加载遥测数据
        
        参数:
            csv_path: CSV文件路径
            time_col: 时间列名
            current_col: 电流列名
            voltage_col: 电压列名
            power_col: 功率列名
            temp_col: 温度列名
            irradiance_col: 辐照位列名
            time_format: 时间格式
            
        返回:
            TelemetryData
        """
        df = pd.read_csv(csv_path)
        
        times = pd.to_datetime(df[time_col], format=time_format).tolist()
        currents = df[current_col].values
        voltages = df[voltage_col].values
        powers = df[power_col].values
        
        temperatures = df[temp_col].values if temp_col and temp_col in df.columns else None
        irradiances = df[irradiance_col].values if irradiance_col and irradiance_col in df.columns else None
        
        return TelemetryData(
            time=times,
            current=currents,
            voltage=voltages,
            power=powers,
            temperature=temperatures,
            irradiance=irradiances
        )
