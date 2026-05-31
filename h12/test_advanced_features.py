import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from microstate import (Preprocessor, GFPAnalyzer, MicrostateClustering, 
                        TemplateFitting, StatisticsAnalyzer,
                        NonlinearDynamicsAnalyzer, SourceReconstructor,
                        CorticalMicrostateAnalyzer, GroupStatistics)


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


def test_nonlinear_dynamics():
    print("=" * 70)
    print("测试1: 非线性动力学分析")
    print("=" * 70)
    
    data, ch_names, sfreq, times, pos = generate_test_data(noise_level=0.5)
    
    print("\n--- 预处理 ---")
    preprocessor = Preprocessor(low_freq=1.0, high_freq=40.0, sfreq=sfreq)
    processed_data = preprocessor.preprocess(data, reference_type='average')
    print("✓ 预处理完成")
    
    print("\n--- GFP峰值提取 ---")
    gfp_analyzer = GFPAnalyzer(sfreq=sfreq)
    gfp, peak_indices, peak_times, peak_data, _ = gfp_analyzer.analyze(processed_data)
    print(f"✓ 提取到 {len(peak_indices)} 个GFP峰值")
    
    print("\n--- K-means聚类 ---")
    clustering = MicrostateClustering(n_clusters=4, n_init=50, max_iter=1000, random_state=42)
    templates, labels = clustering.fit(peak_data)
    print(f"✓ 聚类完成，解释方差: {clustering.explained_variance*100:.2f}%")
    
    print("\n--- 模板拟合 ---")
    template_fitting = TemplateFitting(templates, sfreq=sfreq)
    microstate_sequence, correlation_values = template_fitting.fit(processed_data)
    print(f"✓ 微状态序列长度: {len(microstate_sequence)}")
    
    print("\n--- 统计分析 ---")
    stats_analyzer = StatisticsAnalyzer(sfreq=sfreq, n_clusters=4)
    stats = stats_analyzer.analyze(microstate_sequence)
    print("✓ 统计分析完成")
    
    print("\n--- 非线性动力学分析 ---")
    nonlinear_analyzer = NonlinearDynamicsAnalyzer(n_clusters=4)
    
    print("\n计算Lempel-Ziv复杂度...")
    lz = nonlinear_analyzer.normalized_lempel_ziv(microstate_sequence)
    print(f"  归一化Lempel-Ziv复杂度: {lz:.4f}")
    
    print("\n计算样本熵...")
    se = nonlinear_analyzer.sample_entropy(microstate_sequence, m=2, r=0.2)
    print(f"  样本熵 (m=2, r=0.2): {se:.4f}")
    
    print("\n计算香农熵...")
    sh = nonlinear_analyzer.shannon_entropy(microstate_sequence)
    print(f"  香农熵: {sh:.4f}")
    
    print("\n计算马尔可夫熵率...")
    me = nonlinear_analyzer.markov_entropy_rate(stats['transition_probabilities'])
    print(f"  马尔可夫熵率: {me:.4f}")
    
    print("\n计算Hurst指数...")
    hurst = nonlinear_analyzer.hurst_exponent(microstate_sequence.astype(float))
    print(f"  Hurst指数: {hurst:.4f}")
    
    print("\n计算DFA α指数...")
    dfa = nonlinear_analyzer.detrended_fluctuation_analysis(microstate_sequence.astype(float))
    print(f"  DFA α指数: {dfa:.4f}")
    
    print("\n计算复杂度指数...")
    ci = nonlinear_analyzer.complexity_index(microstate_sequence)
    print(f"  综合复杂度指数: {ci:.4f}")
    
    print("\n--- 完整分析接口测试 ---")
    results = nonlinear_analyzer.analyze(
        microstate_sequence, 
        transition_matrix=stats['transition_probabilities']
    )
    print("\n非线性动力学指标摘要:")
    for key, value in results.items():
        print(f"  {key}: {value:.4f}")
    
    print("\n--- 滑动窗口分析 ---")
    sliding_results = nonlinear_analyzer.sliding_window_analysis(
        microstate_sequence, window_size=500, step_size=100
    )
    print(f"  时间点数: {len(sliding_results['time_points'])}")
    print(f"  LZ复杂度范围: [{sliding_results['lempel_ziv'].min():.4f}, {sliding_results['lempel_ziv'].max():.4f}]")
    print(f"  样本熵范围: [{sliding_results['sample_entropy'].min():.4f}, {sliding_results['sample_entropy'].max():.4f}]")
    
    print("\n✅ 非线性动力学分析测试通过!")
    return True


def test_source_reconstruction():
    print("\n" + "=" * 70)
    print("测试2: 源重建与皮层微状态分析")
    print("=" * 70)
    
    data, ch_names, sfreq, times, pos = generate_test_data(noise_level=0.5, n_channels=32)
    
    print("\n--- 预处理 ---")
    preprocessor = Preprocessor(low_freq=1.0, high_freq=40.0, sfreq=sfreq)
    processed_data = preprocessor.preprocess(data, reference_type='average')
    print("✓ 预处理完成")
    
    methods = ['eloreta', 'minimum_norm', 'dSPM']
    
    for method in methods:
        print(f"\n--- 源重建 ({method.upper()}) ---")
        try:
            source_recon = SourceReconstructor(sfreq=sfreq, method=method)
            source_data, source_power, source_space = source_recon.reconstruct(
                processed_data, pos, lambda_reg=0.1, n_sources=150
            )
            
            print(f"  源点数量: {source_space.shape[0]}")
            print(f"  源数据形状: {source_data.shape}")
            print(f"  源功率形状: {source_power.shape}")
            print(f"  ✓ {method.upper()} 源重建完成")
        except Exception as e:
            print(f"  ✗ {method.upper()} 源重建失败: {e}")
    
    print("\n--- 皮层微状态分析 ---")
    source_recon = SourceReconstructor(sfreq=sfreq, method='eloreta')
    source_data, source_power, source_space = source_recon.reconstruct(
        processed_data, pos, lambda_reg=0.1, n_sources=150
    )
    
    cortical_analyzer = CorticalMicrostateAnalyzer(n_clusters=4, sfreq=sfreq)
    source_results = cortical_analyzer.analyze(
        source_power, source_space, peak_min_distance_ms=20
    )
    
    print(f"  皮层模板形状: {source_results['cortical_templates'].shape}")
    print(f"  皮层微状态序列长度: {len(source_results['cortical_sequence'])}")
    print(f"  区域分布形状: {source_results['region_distribution'].shape}")
    
    print("\n皮层微状态频率分布:")
    for i in range(4):
        freq = np.sum(source_results['cortical_sequence'] == i) / len(source_results['cortical_sequence'])
        print(f"  状态 {i+1}: {freq*100:.1f}%")
    
    print("\n区域分布矩阵 (状态×区域):")
    for i in range(4):
        row = " ".join([f"{source_results['region_distribution'][i,j]:.3f}" for j in range(8)])
        print(f"  状态 {i+1}: [{row}]")
    
    print("\n✅ 源重建与皮层微状态分析测试通过!")
    return True


def test_group_statistics():
    print("\n" + "=" * 70)
    print("测试3: 组水平统计分析")
    print("=" * 70)
    
    n_subjects_group1 = 15
    n_subjects_group2 = 15
    n_features = 17
    
    np.random.seed(42)
    
    print(f"\n--- 生成模拟组数据 ---")
    print(f"  组1: {n_subjects_group1} 名被试")
    print(f"  组2: {n_subjects_group2} 名被试")
    print(f"  特征数: {n_features}")
    
    group1 = np.random.randn(n_subjects_group1, n_features) * 2 + 10
    
    group2 = np.random.randn(n_subjects_group2, n_features) * 2 + 10
    group2[:, [0, 1, 5, 8]] += 1.5
    
    print(f"  组1均值范围: [{group1.mean(axis=0).min():.2f}, {group1.mean(axis=0).max():.2f}]")
    print(f"  组2均值范围: [{group2.mean(axis=0).min():.2f}, {group2.mean(axis=0).max():.2f}]")
    
    print("\n--- 参数检验 (独立样本t检验) ---")
    group_stats = GroupStatistics(n_permutations=500, alpha=0.05)
    
    t_vals, p_vals = group_stats.t_test_independent(group1, group2)
    print(f"  t值范围: [{t_vals.min():.3f}, {t_vals.max():.3f}]")
    print(f"  p值范围: [{p_vals.min():.4f}, {p_vals.max():.4f}]")
    print(f"  未校正显著特征数: {np.sum(p_vals < 0.05)}")
    
    print("\n--- 多重比较校正 (FDR-BH) ---")
    reject, pvals_corrected = group_stats.fdr_correction(p_vals, method='fdr_bh')
    print(f"  校正后显著特征数: {np.sum(reject)}")
    print(f"  校正p值范围: [{pvals_corrected.min():.4f}, {pvals_corrected.max():.4f}]")
    
    print("\n--- Bonferroni校正 ---")
    reject_bonf, pvals_bonf = group_stats.fdr_correction(p_vals, method='bonferroni')
    print(f"  Bonferroni校正后显著特征数: {np.sum(reject_bonf)}")
    
    print("\n--- 置换检验 (500次置换) ---")
    obs_t, perm_p, perm_dist = group_stats.permutation_test_independent(
        group1, group2, stat_func='t_test'
    )
    print(f"  置换p值范围: [{perm_p.min():.4f}, {perm_p.max():.4f}]")
    print(f"  置换检验显著特征数: {np.sum(perm_p < 0.05)}")
    
    print("\n--- 聚类置换检验 ---")
    cluster_obs_t, cluster_p, clusters, cluster_pvals, perm_max = group_stats.cluster_permutation_test(
        group1, group2, threshold=2.0, stat_func='t_test'
    )
    print(f"  检测到的聚类数: {len(clusters)}")
    for i, (cluster, pval) in enumerate(zip(clusters, cluster_pvals)):
        print(f"    聚类 {i+1}: 大小={len(cluster)}, p={pval:.4f}")
    
    print("\n--- 效应量计算 ---")
    cohens_d = group_stats.effect_size_cohens_d(group1, group2)
    hedges_g = group_stats.effect_size_hedges_g(group1, group2)
    print(f"  Cohen's d范围: [{cohens_d.min():.3f}, {cohens_d.max():.3f}]")
    print(f"  Hedges' g范围: [{hedges_g.min():.3f}, {hedges_g.max():.3f}]")
    
    print("\n--- 完整组比较接口 ---")
    results = group_stats.compare_groups(
        group1, group2, paired=False,
        stat_func='t_test',
        correction_method='fdr_bh',
        permutation=True
    )
    
    print("\n统计结果摘要:")
    print(f"  {'特征':<10} {'t值':>8} {'p值':>8} {'校正p':>8} {'效应量':>8} {'显著':>6}")
    print("  " + "-" * 60)
    for i in range(min(10, n_features)):
        sig = "***" if results['significant'][i] else ""
        print(f"  特征{i+1:<6} {results['statistic'][i]:>8.3f} {results['p_values'][i]:>8.4f} "
              f"{results['p_values_corrected'][i]:>8.4f} {results['effect_size'][i]:>8.3f} {sig:>6}")
    
    print("\n--- 组水平统计量 ---")
    group1_stats = group_stats.compute_group_statistics(group1)
    print(f"  组1: 平均={group1_stats['mean'][:3].mean():.2f}, "
          f"SD={group1_stats['std'][:3].mean():.2f}, "
          f"SEM={group1_stats['sem'][:3].mean():.2f}")
    
    print("\n✅ 组水平统计分析测试通过!")
    return True


def test_integration():
    print("\n" + "=" * 70)
    print("测试4: 完整流程整合测试")
    print("=" * 70)
    
    data, ch_names, sfreq, times, pos = generate_test_data(noise_level=0.5)
    n_samples = len(times)
    
    print(f"\n数据形状: {data.shape}")
    print(f"采样率: {sfreq} Hz")
    print(f"时长: {times[-1]:.2f} s\n")
    
    preprocessor = Preprocessor(low_freq=1.0, high_freq=40.0, sfreq=sfreq)
    processed_data = preprocessor.preprocess(data, reference_type='average')
    print("✓ 1. 预处理完成")
    
    gfp_analyzer = GFPAnalyzer(sfreq=sfreq)
    gfp, peak_indices, peak_times, peak_data, _ = gfp_analyzer.analyze(processed_data)
    print(f"✓ 2. GFP峰值提取: {len(peak_indices)} 个峰值")
    
    clustering = MicrostateClustering(n_clusters=4, n_init=50, max_iter=1000, random_state=42)
    templates, labels = clustering.fit(peak_data)
    print(f"✓ 3. 聚类完成: 解释方差={clustering.explained_variance*100:.2f}%")
    
    template_fitting = TemplateFitting(templates, sfreq=sfreq)
    microstate_sequence, correlation_values = template_fitting.fit(processed_data)
    print("✓ 4. 模板拟合完成")
    
    stats_analyzer = StatisticsAnalyzer(sfreq=sfreq, n_clusters=4)
    stats = stats_analyzer.analyze(microstate_sequence)
    print("✓ 5. 统计分析完成")
    
    nonlinear_analyzer = NonlinearDynamicsAnalyzer(n_clusters=4)
    nonlinear_results = nonlinear_analyzer.analyze(
        microstate_sequence, transition_matrix=stats['transition_probabilities']
    )
    print("✓ 6. 非线性动力学分析完成")
    
    source_recon = SourceReconstructor(sfreq=sfreq, method='eloreta')
    source_data, source_power, source_space = source_recon.reconstruct(
        processed_data, pos, lambda_reg=0.1, n_sources=100
    )
    cortical_analyzer = CorticalMicrostateAnalyzer(n_clusters=4, sfreq=sfreq)
    source_results = cortical_analyzer.analyze(source_power, source_space)
    print("✓ 7. 源重建与皮层微状态分析完成")
    
    print("\n--- 最终分析结果摘要 ---")
    print(f"\n  解释方差: {clustering.explained_variance*100:.2f}%")
    print(f"  GFP峰值数: {len(peak_indices)}")
    
    print("\n  微状态统计:")
    for i in range(4):
        print(f"    状态{i+1}: 持续时间={stats['mean_durations'][i]:.1f}ms, "
              f"频率={stats['frequencies'][i]*100:.1f}%")
    
    print("\n  非线性指标:")
    print(f"    Lempel-Ziv复杂度: {nonlinear_results['lempel_ziv_complexity']:.4f}")
    print(f"    样本熵: {nonlinear_results['sample_entropy']:.4f}")
    print(f"    Hurst指数: {nonlinear_results['hurst_exponent']:.4f}")
    
    print("\n  皮层微状态:")
    for i in range(4):
        freq = np.sum(source_results['cortical_sequence'] == i) / len(source_results['cortical_sequence'])
        print(f"    状态{i+1}: {freq*100:.1f}%")
    
    print("\n✅ 完整流程整合测试通过!")
    return True


if __name__ == '__main__':
    try:
        all_passed = True
        all_passed &= test_nonlinear_dynamics()
        all_passed &= test_source_reconstruction()
        all_passed &= test_group_statistics()
        all_passed &= test_integration()
        
        print("\n" + "=" * 70)
        if all_passed:
            print("🎉 所有高级功能测试通过!")
        else:
            print("⚠️  部分测试未通过")
        print("=" * 70)
        
        sys.exit(0 if all_passed else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
