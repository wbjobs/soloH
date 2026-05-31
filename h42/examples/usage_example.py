"""
卫星太阳能电池板功率预测系统 - 使用示例
Satellite Solar Array Power Prediction System - Usage Example
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from datetime import datetime, timedelta

from satellite_power_predictor import PowerPredictor, BatchProcessor
from satellite_power_predictor.orbit.tle_propagator import TLEData, TLEPropagator
from satellite_power_predictor.power.power_predictor import AttitudePoint
from satellite_power_predictor.parallel.batch_processor import (
    SatelliteConfig, BatchConfig, BatchResult
)
from satellite_power_predictor.uncertainty.monte_carlo import (
    MonteCarloAnalyzer, UncertaintyConfig, UncertaintyParameter
)
from satellite_power_predictor.analysis.telemetry_comparison import (
    TelemetryComparator, TelemetryData
)
from satellite_power_predictor.solar_cell.diode_model import (
    SolarArrayConfig, CellParameters
)
from satellite_power_predictor.occlusion.shadow_calculator import (
    create_default_satellite_model, SolarArray, GeometryObject, 
    GeometryType, transform_eci_to_body
)


def example_1_basic_prediction():
    """
    示例1: 基本功率预测
    单颗卫星，单个轨道周期的功率预测
    """
    print("=" * 80)
    print("示例1: 基本功率预测")
    print("=" * 80)
    
    # 样例TLE数据 (ISS国际空间站)
    tle_name = "ISS (ZARYA)"
    tle_line1 = "1 25544U 98067A   24001.50000000  .00022000  00000-0  37256-3 0  9992"
    tle_line2 = "2 25544  51.6400 208.9163 0006703  35.7657 324.4139 15.49942699  1234"
    
    tle_data = TLEData(name=tle_name, line1=tle_line1, line2=tle_line2)
    
    # 创建功率预测器
    predictor = PowerPredictor(
        tle_data=tle_data,
        f107=120.0,
        f107_avg=115.0,
        shield_thickness_mm=2.0
    )
    
    # 设置预测时间范围 (2个轨道周期)
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    
    # 预测2个轨道周期
    result = predictor.predict_multi_orbit(
        n_orbits=2,
        start_time=start_time,
        time_step_sec=5.0,  # 5秒间隔
        operating_voltage=28.0  # 28V母线电压
    )
    
    # 输出结果
    print(f"\n卫星: {result.satellite_name}")
    print(f"时间点数: {len(result.time_series)}")
    print(f"时间范围: {result.time_series[0].time} ~ {result.time_series[-1].time}")
    
    # 轨道平均功率
    oa = result.orbit_average
    print(f"\n轨道平均功率:")
    print(f"  轨道周期: {oa.period_seconds:.1f} 秒")
    print(f"  平均功率: {oa.average_power:.2f} W")
    print(f"  平均电流: {oa.average_current:.2f} A")
    print(f"  峰值功率: {oa.peak_power:.2f} W")
    print(f"  最小功率: {oa.minimum_power:.2f} W")
    print(f"  地影时间: {oa.eclipse_duration:.1f} 秒")
    print(f"  日照时间: {oa.sunlit_duration:.1f} 秒")
    print(f"  单轨总能量: {oa.total_energy:.2f} Wh")
    
    # 辐射退化状态
    ds = result.degradation_state
    print(f"\n辐射退化状态:")
    print(f"  累积DDD: {ds.cumulative_ddd:.6e} MeV/g")
    print(f"  剩余因子: {ds.remaining_factor:.4f}")
    print(f"  Pmax剩余因子: {ds.remaining_factor_pmax:.4f}")
    
    # 输出前10个时间点的数据
    print(f"\n前10个时间点的数据:")
    print(f"{'时间':^20s} {'功率(W)':^10s} {'电流(A)':^10s} {'电压(V)':^10s} "
          f"{'辐照度(W/m2)':^15s} {'地影因子':^10s} {'遮挡因子':^10s} {'温度(K)':^10s}")
    print("-" * 100)
    
    for pt in result.time_series[:10]:
        print(f"{pt.time.strftime('%Y-%m-%d %H:%M:%S'):^20s} "
              f"{pt.array_power:^10.2f} "
              f"{pt.array_current:^10.3f} "
              f"{pt.array_voltage:^10.2f} "
              f"{pt.effective_irradiance:^15.1f} "
              f"{pt.eclipse_factor:^10.3f} "
              f"{pt.occlusion_factor:^10.3f} "
              f"{pt.cell_temperature:^10.1f}")
    
    # 保存为CSV
    df = result.to_dataframe()
    df.to_csv('example_1_result.csv', index=False)
    print(f"\n结果已保存至: example_1_result.csv")
    
    return result


def example_2_attitude_sequence():
    """
    示例2: 使用帆板姿态序列
    """
    print("\n" + "=" * 80)
    print("示例2: 帆板姿态序列")
    print("=" * 80)
    
    tle_name = "TEST_SAT"
    tle_line1 = "1 12345U 24001A   24001.00000000  .00000100  00000-0  10000-3 0  0001"
    tle_line2 = "2 12345  98.0000   0.0000 0001000   0.0000   0.0000 15.00000000    01"
    
    tle_data = TLEData(name=tle_name, line1=tle_line1, line2=tle_line2)
    predictor = PowerPredictor(tle_data=tle_data, f107=100.0, f107_avg=100.0)
    
    # 创建姿态序列 (模拟帆板随时间转动)
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    attitude_sequence = []
    
    orbit_period = predictor.orbit_propagator.get_orbit_period()
    
    # 每60秒一个姿态点
    for i in range(0, int(orbit_period), 60):
        t = start_time + timedelta(seconds=i)
        angle = (i / orbit_period) * 2 * np.pi
        # 帆板法向量随轨道转动，保持对太阳定向
        normal = np.array([np.cos(angle), np.sin(angle), 0.3])
        normal = normal / np.linalg.norm(normal)
        attitude_sequence.append(AttitudePoint(time=t, sa_normal=normal))
    
    print(f"姿态序列点数: {len(attitude_sequence)}")
    print(f"时间范围: {attitude_sequence[0].time} ~ {attitude_sequence[-1].time}")
    
    # 使用姿态序列进行预测
    end_time = start_time + timedelta(seconds=orbit_period)
    result = predictor.predict(
        start_time=start_time,
        end_time=end_time,
        time_step_sec=1.0,
        attitude_sequence=attitude_sequence
    )
    
    print(f"\n预测完成，平均功率: {result.orbit_average.average_power:.2f} W")
    
    return result


def example_3_monte_carlo():
    """
    示例3: 蒙特卡洛不确定度分析
    """
    print("\n" + "=" * 80)
    print("示例3: 蒙特卡洛不确定度分析")
    print("=" * 80)
    
    tle_name = "MC_TEST"
    tle_line1 = "1 12346U 24001B   24001.00000000  .00000100  00000-0  10000-3 0  0002"
    tle_line2 = "2 12346  51.6000   0.0000 0001000   0.0000   0.0000 15.00000000    01"
    
    tle_data = TLEData(name=tle_name, line1=tle_line1, line2=tle_line2)
    predictor = PowerPredictor(tle_data=tle_data, f107=100.0, f107_avg=100.0)
    
    # 配置蒙特卡洛分析
    mc_config = UncertaintyConfig(
        n_samples=50,  # 实际使用时建议设为1000+
        confidence_level=0.95,
        random_seed=42
    )
    
    analyzer = MonteCarloAnalyzer(predictor, mc_config)
    
    # 可以添加自定义不确定性参数
    analyzer.config.add_parameter(UncertaintyParameter(
        name='custom_param',
        nominal_value=1.0,
        distribution='normal',
        params={'std': 0.05},
        description='自定义参数'
    ))
    
    # 执行分析
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    end_time = start_time + timedelta(minutes=30)  # 30分钟
    
    mc_result = analyzer.analyze(
        start_time=start_time,
        end_time=end_time,
        time_step_sec=30.0,  # 30秒间隔以加快计算
        show_progress=True
    )
    
    # 获取功率不确定度边界
    nominal, lower, upper = analyzer.get_uncertainty_bounds(mc_result, 'power')
    
    print(f"\n分析完成，样本数: {mc_result.n_samples}")
    print(f"置信水平: {mc_result.confidence_level * 100:.0f}%")
    
    # 统计平均功率的不确定度
    avg_nominal = np.mean(nominal)
    avg_lower = np.mean(lower)
    avg_upper = np.mean(upper)
    avg_std = np.mean([u.std for u in mc_result.power_uncertainty])
    
    print(f"\n平均功率统计:")
    print(f"  标称值: {avg_nominal:.2f} W")
    print(f"  不确定度: ±{avg_std:.2f} W ({avg_std/avg_nominal*100:.2f}%)")
    print(f"  置信区间: [{avg_lower:.2f}, {avg_upper:.2f}] W")
    
    # 灵敏度分析
    print(f"\n灵敏度指数 (Spearman秩相关):")
    sorted_sensitivity = sorted(
        mc_result.sensitivity_indices.items(),
        key=lambda x: x[1], reverse=True
    )
    for param, sens in sorted_sensitivity[:5]:
        if sens > 0.01:
            print(f"  {param:30s}: {sens:.4f}")
    
    return mc_result


def example_4_batch_processing():
    """
    示例4: 批量多星并行计算
    """
    print("\n" + "=" * 80)
    print("示例4: 批量多星并行计算")
    print("=" * 80)
    
    # 创建多颗卫星配置
    satellites = []
    
    # 卫星1: 低轨卫星
    satellites.append(SatelliteConfig(
        satellite_id='SAT001',
        name='LEO_SAT_1',
        tle_line1="1 40001U 14001A   24001.00000000  .00001000  00000-0  50000-4 0  0001",
        tle_line2="2 40001  97.5000   0.0000 0001000   0.0000   0.0000 15.50000000    01",
        f107=120.0,
        f107_avg=115.0
    ))
    
    # 卫星2: 中轨卫星
    satellites.append(SatelliteConfig(
        satellite_id='SAT002',
        name='MEO_SAT_1',
        tle_line1="1 40002U 14001B   24001.00000000  .00000100  00000-0  10000-4 0  0002",
        tle_line2="2 40002  55.0000   0.0000 0001000   0.0000   0.0000  2.00000000    01",
        f107=120.0,
        f107_avg=115.0
    ))
    
    # 卫星3: 高倾角卫星
    satellites.append(SatelliteConfig(
        satellite_id='SAT003',
        name='HEO_SAT_1',
        tle_line1="1 40003U 14001C   24001.00000000  .00000500  00000-0  20000-4 0  0003",
        tle_line2="2 40003  63.4000   0.0000 0.100000   0.0000   0.0000  3.00000000    01",
        f107=120.0,
        f107_avg=115.0
    ))
    
    # 配置批量计算
    batch_config = BatchConfig(
        start_time=datetime(2024, 1, 1, 0, 0, 0),
        n_orbits=1,
        time_step_sec=5.0,
        n_jobs=-1,  # 使用所有CPU核心
        backend='loky',
        verbose=1
    )
    
    # 创建批量处理器
    batch_processor = BatchProcessor(satellites, batch_config)
    
    # 执行批量计算
    batch_result = batch_processor.run()
    
    # 输出汇总
    print(f"\n批量计算完成:")
    print(f"  总耗时: {batch_result.total_compute_time:.2f} 秒")
    print(f"  成功卫星数: {batch_result.n_satellites}/{len(satellites)}")
    
    # 获取汇总DataFrame
    summary_df = batch_result.get_summary_dataframe()
    print(f"\n各卫星轨道平均功率汇总:")
    print(summary_df.to_string(index=False))
    
    # 获取所有时间序列数据
    all_ts_df = batch_result.get_all_time_series()
    print(f"\n总时间序列数据点: {len(all_ts_df)}")
    
    # 总体统计
    stats = batch_result.get_orbit_average_summary()
    print(f"\n星群总体统计:")
    print(f"  平均功率均值: {stats['mean_average_power']:.2f} W")
    print(f"  平均功率标准差: {stats['std_average_power']:.2f} W")
    print(f"  总平均功率: {stats['total_power']:.2f} W")
    
    # 保存结果
    summary_df.to_csv('example_4_summary.csv', index=False)
    all_ts_df.to_csv('example_4_timeseries.csv', index=False)
    print(f"\n结果已保存至: example_4_summary.csv, example_4_timeseries.csv")
    
    return batch_result


def example_5_telemetry_comparison():
    """
    示例5: 遥测数据对比与误差统计
    """
    print("\n" + "=" * 80)
    print("示例5: 遥测数据对比与误差统计")
    print("=" * 80)
    
    # 首先进行预测
    tle_name = "TEST_SAT"
    tle_line1 = "1 12347U 24001C   24001.00000000  .00000100  00000-0  10000-3 0  0003"
    tle_line2 = "2 12347  98.0000   0.0000 0001000   0.0000   0.0000 15.00000000    01"
    
    tle_data = TLEData(name=tle_name, line1=tle_line1, line2=tle_line2)
    predictor = PowerPredictor(tle_data=tle_data, f107=100.0, f107_avg=100.0)
    
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    end_time = start_time + timedelta(minutes=90)
    
    prediction = predictor.predict(
        start_time=start_time,
        end_time=end_time,
        time_step_sec=5.0
    )
    
    # 生成模拟遥测数据 (实际使用时从文件加载)
    telem_times = prediction.input_parameters['start_time']
    telem_times_list = [pt.time for pt in prediction.time_series]
    
    # 在预测值基础上添加噪声模拟遥测数据
    np.random.seed(42)
    pred_currents = np.array([pt.array_current for pt in prediction.time_series])
    pred_voltages = np.array([pt.array_voltage for pt in prediction.time_series])
    pred_powers = np.array([pt.array_power for pt in prediction.time_series])
    
    # 添加5%的随机噪声和2%的系统偏差
    noise_level = 0.05
    bias = 0.02
    
    telem_currents = pred_currents * (1 + bias + np.random.normal(0, noise_level, len(pred_currents)))
    telem_voltages = pred_voltages * (1 + np.random.normal(0, 0.01, len(pred_voltages)))
    telem_powers = telem_currents * telem_voltages
    telem_temps = np.array([pt.cell_temperature for pt in prediction.time_series]) + \
                 np.random.normal(0, 2, len(pred_currents))
    
    # 创建遥测数据对象
    telemetry = TelemetryData(
        time=telem_times_list,
        current=telem_currents,
        voltage=telem_voltages,
        power=telem_powers,
        temperature=telem_temps
    )
    
    # 执行对比
    comparator = TelemetryComparator()
    comparison = comparator.compare(
        prediction,
        telemetry,
        max_time_diff_sec=5.0,
        parameters=['current', 'power', 'voltage', 'temperature']
    )
    
    # 输出对比报告
    report = comparator.generate_comparison_report(comparison, 'example_5_report.txt')
    
    # 获取汇总DataFrame
    summary_df = comparison.get_summary_dataframe()
    print(f"\n误差统计汇总:")
    print(summary_df.to_string(index=False))
    
    return comparison


def example_6_custom_config():
    """
    示例6: 自定义卫星几何和电池参数
    """
    print("\n" + "=" * 80)
    print("示例6: 自定义卫星配置")
    print("=" * 80)
    
    # 自定义太阳能帆板
    solar_array = SolarArray(
        name="Custom_SA",
        position=np.array([2.0, 0.0, 0.0]),
        normal=np.array([1.0, 0.0, 0.0]),
        size=(3.0, 2.0),  # 3m x 2m
        n_cells=200,
        cell_area=0.03  # 300cm^2 per cell
    )
    
    # 自定义遮挡物体
    occlusion_objects = [
        GeometryObject(
            name="Main_Bus",
            geometry_type=GeometryType.BOX,
            position=np.array([-0.5, 0.0, 0.0]),
            orientation=np.array([0.0, 0.0, 0.0]),
            dimensions=np.array([1.5, 1.5, 2.0])
        ),
        GeometryObject(
            name="High_Gain_Antenna",
            geometry_type=GeometryType.CYLINDER,
            position=np.array([-0.8, 1.0, 0.5]),
            orientation=np.array([0.0, np.pi/4, np.pi/3]),
            dimensions=np.array([0.2, 2.5, 0.0])
        )
    ]
    
    # 自定义电池参数 (三结砷化镓电池)
    cell_params = CellParameters(
        I_sc_ref=9.5,
        V_oc_ref=0.72,
        I_mpp_ref=9.0,
        V_mpp_ref=0.60,
        n=1.2,
        R_s=0.003,
        R_sh=800.0,
        alpha_isc=0.0005,
        beta_voc=-0.0018,
        gamma_pmax=-0.0032,
        area=0.03,
        efficiency_ref=0.28
    )
    
    # 自定义阵列配置
    array_config = SolarArrayConfig(
        n_cells_series=50,
        n_strings_parallel=4,
        cell_params=cell_params,
        bus_voltage=50.0,
        degradation_factor=0.97,
        blocking_diode_drop=0.8
    )
    
    print(f"自定义配置:")
    print(f"  帆板尺寸: {solar_array.size[0]}m x {solar_array.size[1]}m")
    print(f"  电池片数: 串联{array_config.n_cells_series} x 并联{array_config.n_strings_parallel}")
    print(f"  总电池片数: {array_config.total_cells}")
    print(f"  总面积: {array_config.total_area:.2f} m²")
    print(f"  总线电压: {array_config.bus_voltage} V")
    print(f"  参考效率: {cell_params.efficiency_ref * 100:.1f}%")
    
    # 创建TLE数据
    tle_data = TLEData(
        name="CUSTOM_SAT",
        line1="1 99999U 24001D   24001.00000000  .00000100  00000-0  10000-3 0  9999",
        line2="2 99999  28.5000   0.0000 0001000   0.0000   0.0000 15.00000000    01"
    )
    
    # 使用自定义配置创建预测器
    predictor = PowerPredictor(
        tle_data=tle_data,
        solar_array=solar_array,
        occlusion_objects=occlusion_objects,
        array_config=array_config,
        f107=100.0,
        f107_avg=100.0,
        shield_thickness_mm=3.0
    )
    
    # 执行预测
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    result = predictor.predict_multi_orbit(
        n_orbits=1,
        start_time=start_time,
        time_step_sec=5.0
    )
    
    print(f"\n预测结果:")
    print(f"  平均功率: {result.orbit_average.average_power:.2f} W")
    print(f"  峰值功率: {result.orbit_average.peak_power:.2f} W")
    print(f"  单轨能量: {result.orbit_average.total_energy:.2f} Wh")
    print(f"  剩余因子: {result.degradation_state.remaining_factor:.4f}")
    
    return result


if __name__ == "__main__":
    print("卫星太阳能电池板功率预测系统")
    print("Satellite Solar Array Power Prediction System")
    print(f"版本: 1.0.0")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # 运行所有示例
        result_1 = example_1_basic_prediction()
        # result_2 = example_2_attitude_sequence()
        # result_3 = example_3_monte_carlo()
        # result_4 = example_4_batch_processing()
        # result_5 = example_5_telemetry_comparison()
        # result_6 = example_6_custom_config()
        
        print("\n" + "=" * 80)
        print("所有示例运行完成！")
        print("=" * 80)
        
    except ImportError as e:
        print(f"\n缺少依赖库: {e}")
        print("请先安装依赖: pip install -r requirements.txt")
    except Exception as e:
        print(f"\n运行出错: {e}")
        import traceback
        traceback.print_exc()
