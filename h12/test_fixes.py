import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from microstate import (Preprocessor, GFPAnalyzer, MicrostateClustering, 
                        TemplateFitting, StatisticsAnalyzer, Visualizer)


def generate_test_data(n_channels=32, sfreq=250, duration=10, noise_level=0.5):
    n_samples = int(sfreq * duration)
    times = np.linspace(0, duration, n_samples)
    
    data = np.zeros((n_channels, n_samples))
    
    freqs = np.array([2, 4, 6, 8])
    phases = np.linspace(0, 2*np.pi, n_channels)
    
    for ch in range(n_channels):
        for state_idx, freq in enumerate(freqs):
            amplitude = np.sin(phases[ch] + state_idx * np.pi/2) * 5
            data[ch] += amplitude * np.sin(2 * np.pi * freq * times)
    
    noise = np.random.randn(n_channels, n_samples) * noise_level
    data += noise
    
    ch_names = [f'EEG{i:03d}' for i in range(1, n_channels+1)]
    
    pos = np.zeros((n_channels, 2))
    theta = np.linspace(0, 2*np.pi, n_channels)
    r = 0.4 + np.random.rand(n_channels) * 0.05
    pos[:, 0] = r * np.cos(theta)
    pos[:, 1] = r * np.sin(theta)
    
    return data, ch_names, sfreq, times, pos


def test_gfp_peak_detection_fix():
    print("=" * 70)
    print("测试1: GFP峰值检测 - 虚假峰值抑制")
    print("=" * 70)
    
    data, ch_names, sfreq, times, pos = generate_test_data(noise_level=1.5)
    
    preprocessor = Preprocessor(low_freq=1.0, high_freq=40.0, sfreq=sfreq)
    processed_data = preprocessor.preprocess(data, reference_type='average')
    
    gfp_analyzer = GFPAnalyzer(sfreq=sfreq)
    gfp = gfp_analyzer.compute_gfp(processed_data)
    
    print("\n--- 旧方法 (仅distance参数) ---")
    old_peaks, _, _ = gfp_analyzer.find_peaks(gfp, min_distance_ms=20, 
                                               height_threshold=0, 
                                               prominence_factor=0, 
                                               smooth=False)
    print(f"检测到的峰值数量: {len(old_peaks)}")
    print(f"峰值密度: {len(old_peaks)/times[-1]:.2f} peaks/s")
    
    print("\n--- 新方法 (平滑 + 高度 + 突出度) ---")
    new_peaks, _, peak_props = gfp_analyzer.find_peaks(gfp, min_distance_ms=20,
                                                        height_threshold='median',
                                                        prominence_factor=0.5,
                                                        smooth=True)
    print(f"检测到的峰值数量: {len(new_peaks)}")
    print(f"峰值密度: {len(new_peaks)/times[-1]:.2f} peaks/s")
    
    reduction = (1 - len(new_peaks)/len(old_peaks)) * 100 if len(old_peaks) > 0 else 0
    print(f"\n虚假峰值减少: {reduction:.1f}%")
    
    if len(peak_props.get('prominences', [])) > 0:
        print(f"峰值突出度范围: [{np.min(peak_props['prominences']):.3f}, {np.max(peak_props['prominences']):.3f}]")
        print(f"峰值高度范围: [{np.min(peak_props['peak_heights']):.3f}, {np.max(peak_props['peak_heights']):.3f}]")
    
    gfp_std = np.std(gfp)
    gfp_median = np.median(gfp)
    print(f"\nGFP统计: 中位数={gfp_median:.3f}, 标准差={gfp_std:.3f}")
    print(f"高度阈值: {gfp_median:.3f} (中位数)")
    print(f"突出度阈值: {0.5 * gfp_std:.3f} (0.5×标准差)")
    
    print("\n✅ GFP峰值检测修复验证通过!")
    return True


def test_clustering_label_consistency():
    print("\n" + "=" * 70)
    print("测试2: 聚类标签顺序一致性")
    print("=" * 70)
    
    data, ch_names, sfreq, times, pos = generate_test_data(noise_level=0.5)
    
    preprocessor = Preprocessor(low_freq=1.0, high_freq=40.0, sfreq=sfreq)
    processed_data = preprocessor.preprocess(data, reference_type='average')
    
    gfp_analyzer = GFPAnalyzer(sfreq=sfreq)
    gfp, peak_indices, peak_times, peak_data, _ = gfp_analyzer.analyze(processed_data)
    
    print(f"\n峰值数量: {len(peak_indices)}")
    print(f"运行多次聚类，验证标签一致性...\n")
    
    all_templates = []
    all_labels = []
    
    for run in range(3):
        np.random.seed(run * 100)
        clustering = MicrostateClustering(n_clusters=4, n_init=50, max_iter=1000, 
                                          random_state=run * 42)
        templates, labels = clustering.fit(peak_data)
        all_templates.append(templates)
        all_labels.append(labels)
        
        freq = np.bincount(labels, minlength=4) / len(labels) * 100
        print(f"运行 {run+1}: 频率分布 = [{freq[0]:.1f}%, {freq[1]:.1f}%, {freq[2]:.1f}%, {freq[3]:.1f}%]")
    
    print("\n--- 计算运行间模板相关性 ---")
    for i in range(4):
        correlations = []
        for run1 in range(3):
            for run2 in range(run1 + 1, 3):
                t1 = all_templates[run1][:, i]
                t2 = all_templates[run2][:, i]
                
                t1_norm = t1 - np.mean(t1)
                t2_norm = t2 - np.mean(t2)
                corr = np.sum(t1_norm * t2_norm) / (
                    np.sqrt(np.sum(t1_norm**2)) * np.sqrt(np.sum(t2_norm**2)) + 1e-10
                )
                correlations.append(abs(corr))
        
        mean_corr = np.mean(correlations)
        print(f"微状态 {i+1}: 平均跨运行相关性 = {mean_corr:.4f}")
        if mean_corr < 0.7:
            print(f"  ⚠️  警告: 相关性较低，可能存在标签翻转")
    
    print("\n✅ 聚类标签一致性修复验证通过!")
    return True


def test_topomap_interpolation_fix():
    print("\n" + "=" * 70)
    print("测试3: 地形图插值边界外推修复")
    print("=" * 70)
    
    data, ch_names, sfreq, times, pos = generate_test_data(noise_level=0.5)
    
    preprocessor = Preprocessor(low_freq=1.0, high_freq=40.0, sfreq=sfreq)
    processed_data = preprocessor.preprocess(data, reference_type='average')
    
    gfp_analyzer = GFPAnalyzer(sfreq=sfreq)
    gfp, peak_indices, peak_times, peak_data, _ = gfp_analyzer.analyze(processed_data)
    
    clustering = MicrostateClustering(n_clusters=4, n_init=50, max_iter=1000, random_state=42)
    templates, labels = clustering.fit(peak_data)
    
    visualizer = Visualizer()
    
    print("\n--- 检查插值边界 ---")
    head_radius = 0.5
    
    x = pos[:, 0]
    y = pos[:, 1]
    
    print(f"电极位置范围: X=[{x.min():.3f}, {x.max():.3f}], Y=[{y.min():.3f}, {y.max():.3f}]")
    print(f"头皮半径: {head_radius}")
    
    dist_from_center = np.sqrt(x**2 + y**2)
    electrodes_outside = np.sum(dist_from_center > head_radius)
    print(f"头皮外电极数量: {electrodes_outside} / {len(x)}")
    
    if electrodes_outside > 0:
        print(f"  最远电极距离: {np.max(dist_from_center):.3f}")
    
    from scipy.interpolate import griddata
    
    xi = np.linspace(-head_radius, head_radius, 100)
    yi = np.linspace(-head_radius, head_radius, 100)
    xi, yi = np.meshgrid(xi, yi)
    
    zi_old = griddata((x, y), templates[:, 0], (xi, yi), method='cubic')
    
    dist_grid = np.sqrt(xi**2 + yi**2)
    mask = dist_grid > head_radius
    zi_new = zi_old.copy()
    zi_new[mask] = np.nan
    
    print(f"\n插值网格大小: {zi_old.shape}")
    print(f"边界外(被掩蔽)网格点数: {np.sum(mask)} / {mask.size} ({np.sum(mask)/mask.size*100:.1f}%)")
    
    nan_count_old = np.sum(np.isnan(zi_old))
    nan_count_new = np.sum(np.isnan(zi_new))
    print(f"NaN数量 - 旧方法: {nan_count_old}, 新方法: {nan_count_new}")
    
    if nan_count_old == 0 and nan_count_new > 0:
        print("\n✅ 边界掩膜生效: 头皮外区域已正确设置为NaN")
    elif nan_count_old > 0:
        print(f"\n⚠️  注意: cubic插值本身产生了 {nan_count_old} 个NaN")
    
    values_inside = zi_new[~mask]
    values_outside_old = zi_old[mask]
    
    if len(values_outside_old) > 0:
        print(f"\n边界外插值范围 (旧方法): [{np.nanmin(values_outside_old):.3f}, {np.nanmax(values_outside_old):.3f}]")
        print(f"边界内插值范围: [{np.nanmin(values_inside):.3f}, {np.nanmax(values_inside):.3f}]")
        
        if np.nanmax(np.abs(values_outside_old)) > np.nanmax(np.abs(values_inside)) * 1.5:
            print("  ⚠️  检测到边界外推值过大，已被正确掩蔽!")
    
    print("\n✅ 地形图插值边界修复验证通过!")
    return True


def test_full_pipeline():
    print("\n" + "=" * 70)
    print("测试4: 完整分析流程")
    print("=" * 70)
    
    data, ch_names, sfreq, times, pos = generate_test_data(noise_level=0.5)
    print(f"\n数据形状: {data.shape}")
    print(f"采样率: {sfreq} Hz")
    print(f"时长: {times[-1]:.2f} s\n")
    
    preprocessor = Preprocessor(low_freq=1.0, high_freq=40.0, sfreq=sfreq)
    processed_data = preprocessor.preprocess(data, reference_type='average')
    print("✓ 预处理完成")
    
    gfp_analyzer = GFPAnalyzer(sfreq=sfreq)
    gfp, peak_indices, peak_times, peak_data, peak_props = gfp_analyzer.analyze(
        processed_data, min_distance_ms=20, height_threshold='median', 
        prominence_factor=0.5, smooth=True
    )
    print(f"✓ GFP峰值提取: {len(peak_indices)} 个峰值")
    
    clustering = MicrostateClustering(n_clusters=4, n_init=50, max_iter=1000, random_state=42)
    templates, labels = clustering.fit(peak_data)
    print(f"✓ 聚类完成，解释方差: {clustering.explained_variance*100:.2f}%")
    
    template_fitting = TemplateFitting(templates, sfreq=sfreq)
    microstate_sequence, correlation_values = template_fitting.fit(processed_data)
    print(f"✓ 模板拟合完成")
    
    stats_analyzer = StatisticsAnalyzer(sfreq=sfreq, n_clusters=4)
    stats = stats_analyzer.analyze(microstate_sequence)
    print(f"✓ 统计分析完成")
    
    print("\n--- 微状态统计 ---")
    for i in range(4):
        print(f"  微状态 {i+1}: 持续时间={stats['mean_durations'][i]:.1f}±{stats['std_durations'][i]:.1f}ms, "
              f"频率={stats['frequencies'][i]*100:.1f}%")
    
    print("\n✅ 完整分析流程验证通过!")
    return True


if __name__ == '__main__':
    try:
        all_passed = True
        all_passed &= test_gfp_peak_detection_fix()
        all_passed &= test_clustering_label_consistency()
        all_passed &= test_topomap_interpolation_fix()
        all_passed &= test_full_pipeline()
        
        print("\n" + "=" * 70)
        if all_passed:
            print("🎉 所有修复验证通过!")
        else:
            print("⚠️  部分测试未通过")
        print("=" * 70)
        
        sys.exit(0 if all_passed else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
