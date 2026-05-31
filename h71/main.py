import argparse
import numpy as np
import matplotlib.pyplot as plt

from config import Config
from data_loader import (
    generate_synthetic_waveform,
    load_from_npy,
    load_from_csv,
    RealTimeStreamSimulator
)
from sta_lta import compute_sta_lta, detect_p_arrival
from polarization import compute_polarization_parameters, verify_p_wave
from magnitude import estimate_magnitude, compute_pd, estimate_magnitude_from_pd
from online_processor import OnlineProcessor, SlidingWindowProcessor
from advanced_processing import (
    detect_s_wave,
    cluster_and_classify_events,
    deduplicate_detections
)
from deep_learning_detector import (
    DeepLearningPDetector,
    create_pretrained_detector,
    hybrid_detection
)
from focal_mechanism import FocalMechanismEstimator
from warning_zone import (
    WarningZoneCalculator,
    RealTimeWarningSystem,
    StationInfo
)
from visualization import (
    plot_waveform,
    plot_sta_lta,
    plot_polarization,
    plot_combined_analysis,
    plot_magnitude_estimation,
    plot_detection_performance,
    print_detection_summary
)


def run_offline_analysis(waveform_data, true_p_arrival=None, show_plots=True, save_plots=False,
                         site_class=None, dl_detector=None, focal_estimator=None,
                         warning_calculator=None):
    print("\n" + "="*80)
    print("离线批处理模式分析")
    print("="*80)

    if site_class:
        Config.site_class = site_class
        print(f"\n场地类别设置为: {site_class}")
        print(f"  场地放大校正因子: {Config.get_site_correction_factor(site_class):.3f}")

    if Config.s_wave_detection:
        print(f"\nS波检测: 已启用")
    else:
        print(f"\nS波检测: 已禁用")

    if Config.aftershock_detection_enabled:
        print(f"余震检测: 已启用")
    else:
        print(f"余震检测: 已禁用")

    if Config.dl_detector_enabled:
        print(f"深度学习检测: 已启用")
    else:
        print(f"深度学习检测: 已禁用")

    if Config.focal_mechanism_enabled:
        print(f"震源机制估计: 已启用")
    else:
        print(f"震源机制估计: 已禁用")

    if Config.warning_zone_enabled:
        print(f"预警盲区计算: 已启用")
    else:
        print(f"预警盲区计算: 已禁用")

    combined_amp = np.sqrt(np.sum(waveform_data.data ** 2, axis=1))

    total_steps = 8
    step = 1

    print(f"\n[{step}/{total_steps}] 执行STA/LTA检测...")
    sta, lta, sta_lta_ratio = compute_sta_lta(
        combined_amp,
        waveform_data.sampling_rate
    )
    detections_sta = detect_p_arrival(sta_lta_ratio, waveform_data.times)
    print(f"    检测到 {len(detections_sta)} 个P波到时候选 (STA/LTA)")
    step += 1

    if Config.dl_detector_enabled and dl_detector is not None:
        print(f"\n[{step}/{total_steps}] 执行深度学习检测 (CNN+LSTM)...")
        detections_dl = dl_detector.detect_p_arrival(
            waveform_data.data,
            times=waveform_data.times
        )
        print(f"    检测到 {len(detections_dl)} 个P波到时候选 (CNN+LSTM)")

        if Config.dl_hybrid_detection and len(detections_sta) > 0 and len(detections_dl) > 0:
            print(f"    执行混合检测融合...")
            detections = hybrid_detection(detections_sta, detections_dl, time_tolerance=1.0)
            print(f"    融合后 {len(detections)} 个检测")
        elif len(detections_dl) > 0:
            detections = detections_dl
        else:
            detections = detections_sta
    else:
        detections = detections_sta
    step += 1

    print(f"\n[{step}/{total_steps}] 执行极化分析验证...")
    pol_params = compute_polarization_parameters(
        waveform_data.data,
        waveform_data.sampling_rate
    )

    for det in detections:
        verif = verify_p_wave(pol_params, det['arrival_idx'])
        det.update(verif)
    step += 1

    print(f"\n[{step}/{total_steps}] 检测S波到时...")
    if Config.s_wave_detection:
        for det in detections:
            s_idx, s_time, s_info = detect_s_wave(
                waveform_data.data,
                waveform_data.sampling_rate,
                det['arrival_idx'],
                det['arrival_time'],
                polarization_params=pol_params
            )
            det['s_arrival_idx'] = s_idx
            det['s_arrival_time'] = s_time
            det['s_detection_info'] = s_info
            if s_info['method'] == 'detected':
                print(f"    P波 {det['arrival_time']:.2f}s → S波 {s_time:.2f}s, "
                      f"S-P间隔={s_time - det['arrival_time']:.2f}s")
            else:
                print(f"    P波 {det['arrival_time']:.2f}s → S波估算 {s_time:.2f}s")
    step += 1

    print(f"\n[{step}/{total_steps}] 执行震级估算（含S波校正和场地校正）...")
    for det in detections:
        mag_result = estimate_magnitude(
            waveform_data.data,
            waveform_data.dt,
            det['arrival_idx'],
            method='combined',
            polarization_params=pol_params,
            site_class=site_class
        )
        det.update(mag_result)
        det['alert_level'] = Config.get_alert_level(
            det.get('sta_lta_ratio', 3.0),
            det.get('magnitude', np.nan)
        )
        det['overall_confidence'] = min(1.0,
            0.4 * det.get('confidence', 0.5) + 0.4 * det.get('confidence', 0.5) + 0.2
        )

        if 'corrections' in det:
            corr = det['corrections']
            if corr.get('s_wave_correction', {}).get('method') == 's_wave_corrected':
                raw_mag = estimate_magnitude_from_pd(corr['raw_pd'])
                if not np.isnan(raw_mag) and not np.isnan(det['magnitude']):
                    mag_diff = raw_mag - det['magnitude']
                    print(f"    震级校正: 原始M{raw_mag:.2f} → 校正后M{det['magnitude']:.2f} "
                          f"(降低{mag_diff:.2f}级)")
            if 'site_correction' in corr and corr['site_correction'].get('correction_factor') != 1.0:
                sc = corr['site_correction']
                print(f"    场地校正: 类别={sc['site_class']}, "
                      f"因子={sc['correction_factor']:.3f}")
    step += 1

    if Config.focal_mechanism_enabled and focal_estimator is not None:
        print(f"\n[{step}/{total_steps}] 估计震源机制（断裂方向）...")
        for det in detections:
            fm = focal_estimator.estimate_focal_mechanism(
                waveform_data.data,
                det['arrival_idx'],
                polarization_params=pol_params
            )
            det['focal_mechanism'] = fm
            quality = fm.get('quality_level', 'poor')
            fault_type = fm.get('fault_type', 'unknown')
            print(f"    事件 t={det['arrival_time']:.1f}s: {quality}质量, "
                  f"断层类型={fault_type}, "
                  f"走向={fm.get('strike', 0):.0f}°, "
                  f"倾角={fm.get('dip', 0):.0f}°, "
                  f"滑动角={fm.get('rake', 0):.0f}°")
        step += 1

    if Config.warning_zone_enabled and warning_calculator is not None:
        print(f"\n[{step}/{total_steps}] 计算预警盲区与范围...")
        for det in detections:
            magnitude = det.get('magnitude', 5.0)
            if warning_calculator.earthquake_location is None:
                warning_calculator.set_earthquake_location(
                    lat=0.0, lon=0.0, depth=10.0,
                    origin_time=det['arrival_time'] - 5.0,
                    magnitude=magnitude
                )

            current_time = det.get('arrival_time', 0) + 10.0
            wz = warning_calculator.calculate_warning_zone(
                current_time,
                p_arrival_time=det['arrival_time'],
                s_arrival_time=det.get('s_arrival_time')
            )
            det['warning_zone'] = wz
            print(f"    事件 t={det['arrival_time']:.1f}s: "
                  f"盲域半径={wz.blind_zone_radius:.1f}km, "
                  f"预警范围={wz.warning_zone_radius:.1f}km, "
                  f"S波还有{wz.estimated_s_arrival_time - current_time:.1f}s到达")
        step += 1

    print(f"\n[{step}/{total_steps}] 事件聚类与余震识别...")
    if Config.aftershock_detection_enabled and len(detections) > 0:
        detections = deduplicate_detections(detections, time_tolerance=0.5)
        detections = cluster_and_classify_events(detections)
        num_clusters = len(set(d.get('cluster_id') for d in detections if d.get('cluster_id') is not None))
        print(f"    去重后事件数: {len(detections)}")
        print(f"    聚类数量: {num_clusters}")
        event_types = {}
        for d in detections:
            et = d.get('event_type', 'unknown')
            event_types[et] = event_types.get(et, 0) + 1
        for et, count in event_types.items():
            print(f"      {et}: {count} 个")
    step += 1

    print(f"\n[{total_steps}/{total_steps}] 输出检测结果...")
    print_detection_summary(detections, true_p_arrival)

    if show_plots or save_plots:
        print("\n生成可视化图表...")

        plot_combined_analysis(
            waveform_data, sta, lta, sta_lta_ratio,
            pol_params, detections,
            show=show_plots,
            save_path='combined_analysis.png' if save_plots else None
        )

        if detections and 'magnitude' in detections[0] and not np.isnan(detections[0].get('magnitude', np.nan)):
            det = detections[0]
            pd_result = compute_pd(
                waveform_data.data,
                waveform_data.dt,
                det['arrival_idx'],
                polarization_params=pol_params,
                site_class=site_class
            )
            pd = pd_result[0]
            vel = pd_result[1]
            disp = pd_result[2]
            mag = estimate_magnitude_from_pd(pd)

            plot_magnitude_estimation(
                waveform_data.times[det['arrival_idx']:det['arrival_idx']+len(disp)],
                disp, pd, det['arrival_time'], mag,
                show=show_plots,
                save_path='magnitude_estimation.png' if save_plots else None
            )

    return detections, sta, lta, sta_lta_ratio, pol_params


def run_online_simulation(waveform_data, true_p_arrival=None, chunk_size=0.5,
                          show_plots=True, save_plots=False):
    print("\n" + "="*80)
    print("在线实时流模拟分析")
    print("="*80)

    stream = RealTimeStreamSimulator(waveform_data, chunk_size=chunk_size)
    if true_p_arrival is not None:
        stream.set_true_p_arrival(true_p_arrival)

    print(f"\n数据流配置: 采样率={waveform_data.sampling_rate}Hz, 块大小={chunk_size}s")
    print(f"数据时长: {waveform_data.times[-1]:.1f}s, 总分块数: {int(np.ceil(waveform_data.npts / stream.chunk_npts))}")

    processor = OnlineProcessor(waveform_data.sampling_rate)

    print("\n开始实时流处理...")
    result = processor.process_stream(stream, verbose=True)

    print(f"\n处理完成!")
    print(f"平均处理时间: {result.avg_processing_time:.2f} ms")
    print(f"最大处理时间: {result.max_processing_time:.2f} ms")

    print_detection_summary(result.detections, true_p_arrival)

    if show_plots or save_plots:
        if result.detections:
            result_waveform = type('obj', (object,), {
                'data': result.all_data,
                'times': result.all_times,
                'sampling_rate': waveform_data.sampling_rate
            })
            result_waveform.data = np.array(result.all_data)
            result_waveform.times = np.array(result.all_times)
            result_waveform.sampling_rate = waveform_data.sampling_rate

            pol_params_result = {
                'rectilinearity': result.all_rectilinearity,
                'incidence_angle': result.all_incidence,
                'azimuth': result.all_azimuth
            }

            plot_combined_analysis(
                result_waveform,
                result.all_sta, result.all_lta, result.all_sta_lta_ratio,
                pol_params_result, result.detections,
                title='在线处理综合分析结果',
                show=show_plots,
                save_path='online_combined.png' if save_plots else None
            )

            if result.detections and 'detection_delay' in result.detections[0]:
                delays = [d['detection_delay'] for d in result.detections]
                plot_detection_performance(
                    delays,
                    title='在线检测延迟分布',
                    show=show_plots,
                    save_path='detection_delays.png' if save_plots else None
                )

    return result


def run_sliding_window_analysis(waveform_data, true_p_arrival=None,
                                window_size=60.0, overlap=55.0,
                                show_plots=True, save_plots=False, site_class=None):
    print("\n" + "="*80)
    print("滑动窗口离线模拟分析")
    print("="*80)

    if site_class:
        Config.site_class = site_class
        print(f"\n场地类别设置为: {site_class}")
        print(f"  场地放大校正因子: {Config.get_site_correction_factor(site_class):.3f}")

    processor = SlidingWindowProcessor(waveform_data, window_size, overlap)
    print(f"\n窗口配置: 窗口大小={window_size}s, 重叠={overlap}s, 步长={window_size-overlap:.1f}s")

    results = processor.process_offline(
        true_p_arrival=true_p_arrival,
        verbose=True,
        site_class=site_class
    )

    print(f"\n共处理 {len(results['windows'])} 个窗口")
    print(f"原始检测数: {len(results['all_detections'])} 个")
    print(f"去重后事件数: {len(results['detections'])} 个")
    if 'num_clusters' in results:
        print(f"聚类数量: {results['num_clusters']} 个")

    if results['avg_delay'] is not None:
        print(f"\n检测延迟统计:")
        print(f"  平均延迟: {results['avg_delay']:.2f} s")
        print(f"  最小延迟: {results['min_delay']:.2f} s")
        print(f"  最大延迟: {results['max_delay']:.2f} s")

    print_detection_summary(results['detections'], true_p_arrival)

    if show_plots or save_plots and results['detection_delays']:
        plot_detection_performance(
            results['detection_delays'],
            title='滑动窗口检测延迟分布',
            show=show_plots,
            save_path='sliding_window_delays.png' if save_plots else None
        )

    return results


def main():
    parser = argparse.ArgumentParser(description='地震波P波检测与震级估算系统')
    parser.add_argument('--mode', type=str, default='offline',
                        choices=['offline', 'online', 'sliding'],
                        help='运行模式: offline(离线批处理), online(在线模拟), sliding(滑动窗口)')
    parser.add_argument('--input', type=str, default=None,
                        help='输入文件路径 (.npy 或 .csv)，不指定则使用合成数据')
    parser.add_argument('--magnitude', type=float, default=5.0,
                        help='合成数据的震级 (默认: 5.0)')
    parser.add_argument('--p-arrival', type=float, default=30.0,
                        help='合成数据的P波到时 (默认: 30.0s)')
    parser.add_argument('--s-interval', type=float, default=2.0,
                        help='合成数据的S-P波到时差 (默认: 2.0s，模拟近震)')
    parser.add_argument('--duration', type=float, default=120.0,
                        help='合成数据时长 (默认: 120s)')
    parser.add_argument('--sampling-rate', type=float, default=100.0,
                        help='采样率 (默认: 100Hz)')
    parser.add_argument('--chunk-size', type=float, default=0.5,
                        help='在线模式的数据流块大小 (默认: 0.5s)')
    parser.add_argument('--window-size', type=float, default=60.0,
                        help='滑动窗口大小 (默认: 60s)')
    parser.add_argument('--overlap', type=float, default=55.0,
                        help='滑动窗口重叠 (默认: 55s)')
    parser.add_argument('--threshold', type=float, default=None,
                        help='STA/LTA检测阈值 (默认: 使用config中的配置)')
    parser.add_argument('--site-class', type=str, default=None,
                        choices=['A', 'B', 'C', 'D', 'E', 'F'],
                        help='场地类别 (A=硬岩, B=岩石, C=土壤, D=软土, E=非常软土, F=特殊场地)')
    parser.add_argument('--disable-s-wave-correction', action='store_true',
                        help='禁用S波校正（用于对比效果）')
    parser.add_argument('--disable-site-correction', action='store_true',
                        help='禁用场地响应校正')
    parser.add_argument('--disable-aftershock-detection', action='store_true',
                        help='禁用余震检测和事件聚类')
    parser.add_argument('--disable-dl-detection', action='store_true',
                        help='禁用深度学习P波检测')
    parser.add_argument('--disable-focal-mechanism', action='store_true',
                        help='禁用震源机制估计')
    parser.add_argument('--disable-warning-zone', action='store_true',
                        help='禁用预警盲区计算')
    parser.add_argument('--dl-threshold', type=float, default=None,
                        help='深度学习检测阈值 (默认: 0.5)')
    parser.add_argument('--pretrain-model', action='store_true',
                        help='预训练深度学习模型')
    parser.add_argument('--multi-event', action='store_true',
                        help='生成包含主震和余震的合成数据（用于测试余震检测）')
    parser.add_argument('--no-plots', action='store_true',
                        help='不显示图表')
    parser.add_argument('--save-plots', action='store_true',
                        help='保存图表为PNG文件')

    args = parser.parse_args()

    if args.disable_s_wave_correction:
        Config.s_wave_detection = False
        print("已禁用S波检测和校正")

    if args.disable_site_correction:
        Config.site_correction_enabled = False
        print("已禁用场地响应校正")

    if args.disable_aftershock_detection:
        Config.aftershock_detection_enabled = False
        print("已禁用余震检测和事件聚类")

    if args.disable_dl_detection:
        Config.dl_detector_enabled = False
        print("已禁用深度学习P波检测")

    if args.disable_focal_mechanism:
        Config.focal_mechanism_enabled = False
        print("已禁用震源机制估计")

    if args.disable_warning_zone:
        Config.warning_zone_enabled = False
        print("已禁用预警盲区计算")

    if args.threshold is not None:
        Config.sta_lta_threshold = args.threshold
        print(f"已设置STA/LTA阈值: {args.threshold}")

    if args.dl_threshold is not None:
        Config.dl_threshold = args.dl_threshold
        print(f"已设置深度学习检测阈值: {args.dl_threshold}")

    dl_detector = None
    focal_estimator = None
    warning_calculator = None

    if Config.dl_detector_enabled:
        print("\n初始化深度学习P波检测器...")
        if args.pretrain_model:
            dl_detector = create_pretrained_detector(
                window_size=Config.dl_window_size,
                sampling_rate=args.sampling_rate
            )
        else:
            dl_detector = DeepLearningPDetector(
                window_size=Config.dl_window_size,
                sampling_rate=args.sampling_rate,
                threshold=Config.dl_threshold
            )
            print("正在合成数据预训练模型...")
            waveforms, labels = dl_detector.generate_synthetic_training_data(num_samples=1000)
            split = int(0.8 * len(waveforms))
            from deep_learning_detector import EarthquakeDataset
            from torch.utils.data import DataLoader
            train_dataset = EarthquakeDataset(waveforms[:split], labels[:split], Config.dl_window_size)
            val_dataset = EarthquakeDataset(waveforms[split:], labels[split:], Config.dl_window_size)
            train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
            val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
            class_counts = np.bincount(labels[:split])
            class_weights = len(labels[:split]) / (2 * class_counts)
            dl_detector.train(
                train_loader, val_loader,
                num_epochs=10,
                learning_rate=0.001,
                class_weights=class_weights,
                save_path='quick_trained_detector.pth'
            )
        print(f"深度学习检测器初始化完成: 窗口大小={Config.dl_window_size}样本, 阈值={Config.dl_threshold}")

    if Config.focal_mechanism_enabled:
        focal_estimator = FocalMechanismEstimator(
            sampling_rate=args.sampling_rate,
            p_window=Config.focal_mechanism_window
        )
        print(f"震源机制估计器初始化完成: 分析窗口={Config.focal_mechanism_window}s")

    if Config.warning_zone_enabled:
        warning_calculator = WarningZoneCalculator()
        stations = [
            StationInfo('STA01', 0.01, 0.01, site_class='A'),
            StationInfo('STA02', 0.02, 0.00, site_class='B'),
            StationInfo('STA03', 0.00, 0.02, site_class='C'),
            StationInfo('STA04', -0.01, -0.01, site_class='D'),
            StationInfo('STA05', 0.03, -0.02, site_class='E'),
        ]
        warning_calculator.set_stations(stations)
        print(f"预警盲区计算器初始化完成: 已配置 {len(stations)} 个台站")

    print(f"\n加载波形数据...")
    if args.input:
        if args.input.endswith('.npy'):
            waveform = load_from_npy(args.input, args.sampling_rate)
        elif args.input.endswith('.csv'):
            waveform = load_from_csv(args.input, args.sampling_rate)
        else:
            waveform = load_from_npy(args.input, args.sampling_rate)
        true_p_arrival = None
        print(f"已从文件加载: {args.input}")
    else:
        if args.multi_event:
            from data_loader import WaveformData
            from utils import preprocess_waveform

            npts = int(args.duration * args.sampling_rate)
            dt = 1.0 / args.sampling_rate
            data = np.zeros((npts, 3))
            data += 0.01 * np.random.randn(npts, 3)

            events = [
                {'time': 30.0, 'mag': args.magnitude, 'inc': 30, 'az': 45},
                {'time': 45.0, 'mag': args.magnitude - 1.2, 'inc': 35, 'az': 50},
                {'time': 60.0, 'mag': args.magnitude - 0.8, 'inc': 25, 'az': 40},
                {'time': 80.0, 'mag': args.magnitude - 1.5, 'inc': 40, 'az': 55},
            ]

            for ev in events:
                p_idx = int(ev['time'] / dt)
                s_idx = int((ev['time'] + args.s_interval) / dt)
                p_amp = 10 ** (0.5 * ev['mag']) * 0.01
                s_amp = p_amp * 1.5

                p_npts = int(2.0 / dt)
                p_t = np.arange(p_npts) * dt
                p_env = p_amp * (1 - np.exp(-p_t / 0.1)) * np.exp(-p_t / 0.5)

                p_inc = np.radians(ev['inc'])
                p_az = np.radians(ev['az'])
                p_z = p_env * np.cos(p_inc)
                p_n = p_env * np.sin(p_inc) * np.cos(p_az)
                p_e = p_env * np.sin(p_inc) * np.sin(p_az)

                if p_idx + p_npts <= npts:
                    data[p_idx:p_idx + p_npts, 0] += p_z
                    data[p_idx:p_idx + p_npts, 1] += p_n
                    data[p_idx:p_idx + p_npts, 2] += p_e

                s_npts = int(3.0 / dt)
                s_t = np.arange(s_npts) * dt
                s_env = s_amp * (1 - np.exp(-s_t / 0.2)) * np.exp(-s_t / 1.0)
                if s_idx + s_npts <= npts:
                    data[s_idx:s_idx + s_npts, 1] += s_env * 0.8
                    data[s_idx:s_idx + s_npts, 2] += s_env * 0.6

            data = preprocess_waveform(data, args.sampling_rate)
            waveform = WaveformData(data, args.sampling_rate, station_name='MULTI-EVENT')
            true_p_arrival = 30.0
            print(f"已生成多事件合成波形: 主震M{args.magnitude}, 3个余震")
            for ev in events:
                print(f"  事件: t={ev['time']}s, M{ev['mag']}")
        else:
            waveform = generate_synthetic_waveform(
                duration=args.duration,
                sampling_rate=args.sampling_rate,
                p_arrival=args.p_arrival,
                s_arrival=args.p_arrival + args.s_interval,
                magnitude=args.magnitude,
                noise_level=0.01
            )
            true_p_arrival = args.p_arrival
            print(f"已生成合成波形: M{args.magnitude}, P波到时={args.p_arrival}s, S-P间隔={args.s_interval}s")

    print(f"数据信息: 采样率={waveform.sampling_rate}Hz, 时长={waveform.times[-1]:.1f}s, 采样点数={waveform.npts}")

    if args.mode == 'offline':
        run_offline_analysis(
            waveform,
            true_p_arrival=true_p_arrival,
            show_plots=not args.no_plots,
            save_plots=args.save_plots,
            site_class=args.site_class,
            dl_detector=dl_detector,
            focal_estimator=focal_estimator,
            warning_calculator=warning_calculator
        )
    elif args.mode == 'online':
        run_online_simulation(
            waveform,
            true_p_arrival=true_p_arrival,
            chunk_size=args.chunk_size,
            show_plots=not args.no_plots,
            save_plots=args.save_plots
        )
    elif args.mode == 'sliding':
        run_sliding_window_analysis(
            waveform,
            true_p_arrival=true_p_arrival,
            window_size=args.window_size,
            overlap=args.overlap,
            show_plots=not args.no_plots,
            save_plots=args.save_plots,
            site_class=args.site_class
        )

    if not args.no_plots:
        plt.show()

    print("\n分析完成!")


if __name__ == '__main__':
    main()
