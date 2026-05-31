import numpy as np
import sys
from config import Config
from data_loader import generate_synthetic_waveform
from deep_learning_detector import (
    DeepLearningPDetector,
    create_pretrained_detector,
    hybrid_detection
)
from focal_mechanism import FocalMechanismEstimator, format_focal_mechanism
from warning_zone import (
    WarningZoneCalculator,
    SeismicWaveModel,
    StationInfo,
    format_warning_zone
)


def test_seismic_wave_model():
    print("\n" + "="*80)
    print("测试1: 地震波传播模型")
    print("="*80)

    model = SeismicWaveModel()

    print(f"\n地壳P波速度: {model.vp_crust} km/s")
    print(f"地壳S波速度: {model.vs_crust} km/s")
    print(f"地幔P波速度: {model.vp_mantle} km/s")
    print(f"地幔S波速度: {model.vs_mantle} km/s")
    print(f"Vs/Vp比值: {model.get_vs_over_vp(10):.4f}")

    distances = [10, 50, 100, 200]
    depth = 10.0

    print(f"\n不同距离的走时预测 (深度={depth}km):")
    print(f"{'距离(km)':<12} {'P波走时(s)':<12} {'S波走时(s)':<12} {'S-P间隔(s)':<12}")
    print("-" * 50)

    for dist in distances:
        t_p = model.estimate_travel_time(dist, depth, 'P')
        t_s = model.estimate_travel_time(dist, depth, 'S')
        print(f"{dist:<12} {t_p:<12.2f} {t_s:<12.2f} {t_s - t_p:<12.2f}")

    print("\n✓ 地震波模型测试完成")


def test_deep_learning_detector():
    print("\n" + "="*80)
    print("测试2: 深度学习P波检测 (CNN+LSTM)")
    print("="*80)

    Config.dl_window_size = 200
    sampling_rate = 100.0

    print("\n正在创建深度学习检测器...")
    detector = DeepLearningPDetector(
        window_size=Config.dl_window_size,
        sampling_rate=sampling_rate,
        threshold=0.5
    )

    print(f"模型结构:")
    total_params = sum(p.numel() for p in detector.model.parameters())
    trainable_params = sum(p.numel() for p in detector.model.parameters() if p.requires_grad)
    print(f"  总参数量: {total_params:,}")
    print(f"  可训练参数量: {trainable_params:,}")
    print(f"  输入窗口: {Config.dl_window_size} 样本 × 3分量")
    print(f"  CNN滤波器: [32, 64, 128]")
    print(f"  LSTM隐藏层: 64 (双向)")

    print("\n生成合成训练数据...")
    waveforms, labels = detector.generate_synthetic_training_data(num_samples=500)
    print(f"  训练样本数: {len(waveforms)}")
    print(f"  正样本(P波): {np.sum(labels == 1)}")
    print(f"  负样本(噪声): {np.sum(labels == 0)}")

    print("\n快速训练演示 (5个epoch)...")
    from torch.utils.data import DataLoader
    from deep_learning_detector import EarthquakeDataset

    split = int(0.8 * len(waveforms))
    train_dataset = EarthquakeDataset(waveforms[:split], labels[:split], Config.dl_window_size)
    val_dataset = EarthquakeDataset(waveforms[split:], labels[split:], Config.dl_window_size)

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)

    class_counts = np.bincount(labels[:split])
    class_weights = len(labels[:split]) / (2 * class_counts)

    history = detector.train(
        train_loader, val_loader,
        num_epochs=5,
        learning_rate=0.001,
        class_weights=class_weights,
        save_path='test_detector.pth'
    )

    print(f"\n最优验证准确率: {history['best_val_acc']:.4f}")

    print("\n测试检测功能...")
    waveform = generate_synthetic_waveform(
        duration=60.0,
        sampling_rate=sampling_rate,
        p_arrival=30.0,
        s_arrival=33.0,
        magnitude=5.5,
        noise_level=0.01
    )

    detections = detector.detect_p_arrival(waveform.data, times=waveform.times)
    print(f"  检测到 {len(detections)} 个P波")
    for i, det in enumerate(detections):
        print(f"    检测 #{i+1}: t={det['arrival_time']:.2f}s, 置信度={det['confidence']:.3f}")

    print("\n✓ 深度学习检测器测试完成")
    return detector


def test_hybrid_detection():
    print("\n" + "="*80)
    print("测试3: 混合检测 (STA/LTA + CNN+LSTM)")
    print("="*80)

    sampling_rate = 100.0
    waveform = generate_synthetic_waveform(
        duration=120.0,
        sampling_rate=sampling_rate,
        p_arrival=30.0,
        s_arrival=33.0,
        magnitude=5.5,
        noise_level=0.01
    )

    from sta_lta import compute_sta_lta, detect_p_arrival
    combined_amp = np.sqrt(np.sum(waveform.data ** 2, axis=1))
    sta, lta, sta_lta_ratio = compute_sta_lta(combined_amp, sampling_rate)
    sta_lta_detections = detect_p_arrival(sta_lta_ratio, waveform.times, threshold=3.0)

    print(f"\nSTA/LTA检测: {len(sta_lta_detections)} 个")
    for det in sta_lta_detections:
        print(f"  t={det['arrival_time']:.2f}s, STA/LTA={det['sta_lta_ratio']:.2f}")

    Config.dl_window_size = 200
    dl_detector = DeepLearningPDetector(
        window_size=Config.dl_window_size,
        sampling_rate=sampling_rate,
        threshold=0.7
    )

    waveforms, labels = dl_detector.generate_synthetic_training_data(num_samples=300)
    split = int(0.8 * len(waveforms))
    from torch.utils.data import DataLoader
    from deep_learning_detector import EarthquakeDataset
    train_dataset = EarthquakeDataset(waveforms[:split], labels[:split], Config.dl_window_size)
    val_dataset = EarthquakeDataset(waveforms[split:], labels[split:], Config.dl_window_size)
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    class_counts = np.bincount(labels[:split])
    class_weights = len(labels[:split]) / (2 * class_counts)
    dl_detector.train(train_loader, val_loader, num_epochs=3, class_weights=class_weights, save_path='hybrid_test.pth')

    dl_detections = dl_detector.detect_p_arrival(waveform.data, times=waveform.times)
    print(f"\nCNN+LSTM检测: {len(dl_detections)} 个")
    for det in dl_detections:
        print(f"  t={det['arrival_time']:.2f}s, 置信度={det['confidence']:.3f}")

    hybrid = hybrid_detection(sta_lta_detections, dl_detections, time_tolerance=1.0)
    print(f"\n混合检测: {len(hybrid)} 个")
    for det in hybrid:
        methods = det.get('detection_methods', [det.get('method', 'unknown')])
        print(f"  t={det['arrival_time']:.2f}s, 方法={', '.join(methods)}, "
              f"置信度={det.get('overall_confidence', 0):.3f}")

    print("\n✓ 混合检测测试完成")


def test_focal_mechanism():
    print("\n" + "="*80)
    print("测试4: 震源机制（断裂方向）快速估计")
    print("="*80)

    sampling_rate = 100.0
    estimator = FocalMechanismEstimator(sampling_rate=sampling_rate, p_window=0.5)

    print(f"\n震源机制估计器配置:")
    print(f"  采样率: {sampling_rate} Hz")
    print(f"  分析窗口: {estimator.p_window} s")

    waveform = generate_synthetic_waveform(
        duration=60.0,
        sampling_rate=sampling_rate,
        p_arrival=30.0,
        s_arrival=33.0,
        magnitude=6.0,
        noise_level=0.005
    )

    from polarization import compute_polarization_parameters
    pol_params = compute_polarization_parameters(waveform.data, sampling_rate)

    arrival_idx = int(30.0 * sampling_rate)
    print(f"\nP波到时索引: {arrival_idx} (t=30.0s)")

    print("\n估计震源机制...")
    fm = estimator.estimate_focal_mechanism(waveform.data, arrival_idx, pol_params)

    for line in format_focal_mechanism(fm):
        print(line)

    amp_ratios = fm.get('amplitude_ratios', {})
    print(f"\n  振幅比细节:")
    print(f"    Z/H: {amp_ratios.get('z_over_h', 0):.3f}")
    print(f"    N/Z: {amp_ratios.get('n_over_z', 0):.3f}")
    print(f"    E/Z: {amp_ratios.get('e_over_z', 0):.3f}")
    print(f"    N/E: {amp_ratios.get('n_over_e', 0):.3f}")

    spectral = fm.get('spectral_features', {})
    if 'Z_peak_freq' in spectral:
        print(f"\n  频谱特征:")
        print(f"    Z分量峰值频率: {spectral['Z_peak_freq']:.2f} Hz")
        print(f"    N分量峰值频率: {spectral.get('N_peak_freq', 0):.2f} Hz")
        print(f"    E分量峰值频率: {spectral.get('E_peak_freq', 0):.2f} Hz")
        print(f"    Z分量谱质心: {spectral['Z_spectral_centroid']:.2f} Hz")

    rupture = fm.get('rupture_direction', {})
    print(f"\n  破裂方向估计:")
    print(f"    方位角: {rupture.get('azimuth', 0):.1f}°")
    print(f"    与走向夹角: {rupture.get('relative_to_strike', 0):.1f}°")
    print(f"    多普勒效应: {rupture.get('doppler_effect_hint', 'N/A')}")
    print(f"    方向置信度: {rupture.get('direction_confidence', 0):.2f}")

    print("\n✓ 震源机制估计测试完成")
    return fm


def test_warning_zone():
    print("\n" + "="*80)
    print("测试5: 预警盲区范围动态计算")
    print("="*80)

    calculator = WarningZoneCalculator()

    stations = [
        StationInfo('STA01', 0.005, 0.005, site_class='A'),
        StationInfo('STA02', 0.010, 0.000, site_class='B'),
        StationInfo('STA03', 0.000, 0.010, site_class='C'),
        StationInfo('STA04', -0.005, -0.005, site_class='D'),
        StationInfo('STA05', 0.015, -0.010, site_class='E'),
        StationInfo('STA06', -0.010, 0.005, site_class='F'),
    ]
    calculator.set_stations(stations)
    print(f"\n已配置 {len(stations)} 个台站")

    calculator.set_earthquake_location(
        lat=0.0, lon=0.0, depth=10.0,
        origin_time=25.0, magnitude=6.5
    )
    print(f"地震位置: 纬度=0.0°, 经度=0.0°, 深度=10.0km, M=6.5")

    p_arrival_time = 30.0
    s_arrival_time = 33.0

    print(f"\nP波到时: {p_arrival_time}s")
    print(f"S波到时: {s_arrival_time}s (S-P={s_arrival_time - p_arrival_time}s)")

    print(f"\n预警盲区随时间演化:")
    print(f"{'时间(s)':<10} {'P波后(s)':<12} {'盲域半径(km)':<14} {'预警范围(km)':<14} {'S波剩余(s)':<12}")
    print("-" * 70)

    for t_offset in [0, 2, 5, 10, 15, 20, 25]:
        current_time = p_arrival_time + t_offset
        wz = calculator.calculate_warning_zone(
            current_time,
            p_arrival_time=p_arrival_time,
            s_arrival_time=s_arrival_time
        )
        time_to_s = wz.estimated_s_arrival_time - current_time
        print(f"{current_time:<10.1f} {t_offset:<12.1f} {wz.blind_zone_radius:<14.1f} "
              f"{wz.warning_zone_radius:<14.1f} {time_to_s:<12.1f}")

    current_time = p_arrival_time + 10.0
    wz = calculator.calculate_warning_zone(
        current_time,
        p_arrival_time=p_arrival_time,
        s_arrival_time=s_arrival_time
    )

    for line in format_warning_zone(wz, include_stations=True):
        print(line)

    print(f"\n台站预警时间:")
    print(f"{'台站':<10} {'距离(km)':<12} {'烈度':<10} {'破坏级别':<14} {'预警时间(s)':<14}")
    print("-" * 60)

    for station in stations:
        dist = calculator.haversine_distance(
            0.0, 0.0, station.latitude, station.longitude
        )
        intensity = calculator.estimate_intensity(dist, 6.5, station.site_class)
        damage_level, damage_desc = calculator.get_damage_potential(intensity)
        lead_time, _ = calculator.calculate_lead_time(dist, current_time, p_arrival_time)

        print(f"{station.id:<10} {dist:<12.1f} {intensity:<10.1f} {damage_desc:<14} {lead_time:<14.1f}")

    print("\n生成时间序列...")
    times, wz_series = calculator.generate_time_series(
        p_arrival_time, duration=30.0, time_step=2.0,
        s_arrival_time=s_arrival_time
    )

    print(f"\n盲域面积变化:")
    for t, wz in zip(times[::2], wz_series[::2]):
        print(f"  t={t:.1f}s: 盲域={wz.blind_zone_area:.0f} km², "
              f"预警区={wz.warning_zone_area:.0f} km²")

    print("\n✓ 预警盲区计算测试完成")
    return calculator


def test_integration():
    print("\n" + "="*80)
    print("测试6: 所有新功能集成测试")
    print("="*80)

    Config.dl_detector_enabled = True
    Config.focal_mechanism_enabled = True
    Config.warning_zone_enabled = True
    Config.dl_window_size = 200

    sampling_rate = 100.0
    waveform = generate_synthetic_waveform(
        duration=120.0,
        sampling_rate=sampling_rate,
        p_arrival=30.0,
        s_arrival=32.0,
        magnitude=5.8,
        noise_level=0.01
    )

    print(f"\n测试数据: M5.8, P波t=30.0s, S波t=32.0s, S-P=2.0s")

    print("\n[步骤1] 初始化所有模块...")
    dl_detector = DeepLearningPDetector(
        window_size=Config.dl_window_size,
        sampling_rate=sampling_rate,
        threshold=0.6
    )
    waveforms, labels = dl_detector.generate_synthetic_training_data(num_samples=400)
    split = int(0.8 * len(waveforms))
    from torch.utils.data import DataLoader
    from deep_learning_detector import EarthquakeDataset
    train_dataset = EarthquakeDataset(waveforms[:split], labels[:split], Config.dl_window_size)
    val_dataset = EarthquakeDataset(waveforms[split:], labels[split:], Config.dl_window_size)
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    class_counts = np.bincount(labels[:split])
    class_weights = len(labels[:split]) / (2 * class_counts)
    dl_detector.train(train_loader, val_loader, num_epochs=5, class_weights=class_weights, save_path='integration_test.pth')

    focal_estimator = FocalMechanismEstimator(sampling_rate=sampling_rate)

    warning_calculator = WarningZoneCalculator()
    stations = [
        StationInfo('STA01', 0.005, 0.005, site_class='C'),
        StationInfo('STA02', 0.010, 0.000, site_class='C'),
    ]
    warning_calculator.set_stations(stations)
    warning_calculator.set_earthquake_location(
        lat=0.0, lon=0.0, depth=10.0,
        origin_time=28.0, magnitude=5.8
    )

    print("\n[步骤2] STA/LTA检测...")
    from sta_lta import compute_sta_lta, detect_p_arrival
    combined_amp = np.sqrt(np.sum(waveform.data ** 2, axis=1))
    sta, lta, sta_lta_ratio = compute_sta_lta(combined_amp, sampling_rate)
    sta_detections = detect_p_arrival(sta_lta_ratio, waveform.times, threshold=3.0)
    print(f"  STA/LTA检测到 {len(sta_detections)} 个事件")

    print("\n[步骤3] 深度学习检测...")
    dl_detections = dl_detector.detect_p_arrival(waveform.data, times=waveform.times)
    print(f"  CNN+LSTM检测到 {len(dl_detections)} 个事件")

    print("\n[步骤4] 混合检测融合...")
    detections = hybrid_detection(sta_detections, dl_detections, time_tolerance=1.0)
    print(f"  融合后 {len(detections)} 个事件")

    print("\n[步骤5] 极化分析与震级估算...")
    from polarization import compute_polarization_parameters, verify_p_wave
    from magnitude import estimate_magnitude

    pol_params = compute_polarization_parameters(waveform.data, sampling_rate)

    for det in detections:
        verif = verify_p_wave(pol_params, det['arrival_idx'])
        det.update(verif)

        mag_result = estimate_magnitude(
            waveform.data, waveform.dt, det['arrival_idx'],
            method='combined', polarization_params=pol_params
        )
        det.update(mag_result)

    print("\n[步骤6] 震源机制估计...")
    for det in detections:
        fm = focal_estimator.estimate_focal_mechanism(
            waveform.data, det['arrival_idx'], pol_params
        )
        det['focal_mechanism'] = fm
        print(f"  事件t={det['arrival_time']:.1f}s: "
              f"M={det.get('magnitude', 0):.1f}, "
              f"断层类型={fm.get('fault_type', 'unknown')}, "
              f"质量={fm.get('quality_level', 'poor')}")

    print("\n[步骤7] 预警盲区计算...")
    for det in detections:
        current_time = det['arrival_time'] + 5.0
        wz = warning_calculator.calculate_warning_zone(
            current_time,
            p_arrival_time=det['arrival_time']
        )
        det['warning_zone'] = wz
        print(f"  事件t={det['arrival_time']:.1f}s: "
              f"盲域={wz.blind_zone_radius:.1f}km, "
              f"预警范围={wz.warning_zone_radius:.1f}km")

    print("\n✓ 集成测试完成")
    print(f"\n最终检测结果:")
    for i, det in enumerate(detections):
        method = det.get('method', 'unknown')
        print(f"  检测#{i+1}: t={det['arrival_time']:.2f}s, "
              f"M={det.get('magnitude', 0):.1f}, "
              f"方法={method}, "
              f"置信度={det.get('overall_confidence', 0):.3f}")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("地震预警系统新增功能综合测试")
    print("="*80)
    print("\n新增功能列表:")
    print("  1. 基于深度学习的P波检测 (CNN+LSTM模型)")
    print("  2. 震源机制（断裂方向）快速估计")
    print("  3. 预警盲区（S波到达前）范围动态计算")
    print("  4. STA/LTA与深度学习的混合检测融合")

    try:
        test_seismic_wave_model()
        test_deep_learning_detector()
        test_hybrid_detection()
        test_focal_mechanism()
        test_warning_zone()
        test_integration()

        print("\n" + "="*80)
        print("所有测试完成!")
        print("="*80)
        print("\n新增功能总结:")
        print("  ✓ 深度学习P波检测 (CNN+LSTM) - 支持模型训练、预测、混合融合")
        print("  ✓ 震源机制快速估计 - 初动极性、振幅比、频谱特征、断层参数")
        print("  ✓ 预警盲区动态计算 - 地震波模型、盲域/预警区、台站分类")
        print("  ✓ 完整集成 - 与现有STA/LTA、极化分析、震级估算无缝集成")
        print("\n新增文件:")
        print("  - deep_learning_detector.py  - CNN+LSTM深度学习检测模块")
        print("  - focal_mechanism.py         - 震源机制估计模块")
        print("  - warning_zone.py            - 预警盲区计算模块")
        print("  - test_new_features.py       - 新功能综合测试脚本")
        print("\n新增命令行参数:")
        print("  --disable-dl-detection       禁用深度学习检测")
        print("  --disable-focal-mechanism    禁用震源机制估计")
        print("  --disable-warning-zone       禁用预警盲区计算")
        print("  --dl-threshold VALUE         设置深度学习检测阈值")
        print("  --pretrain-model             预训练深度学习模型")

    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
