import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from microstate import (Preprocessor, GFPAnalyzer, MicrostateClustering, 
                        TemplateFitting, StatisticsAnalyzer)


def generate_test_data(n_channels=32, sfreq=250, duration=10):
    n_samples = int(sfreq * duration)
    times = np.linspace(0, duration, n_samples)
    
    data = np.zeros((n_channels, n_samples))
    
    freqs = np.array([2, 4, 6, 8])
    phases = np.linspace(0, 2*np.pi, n_channels)
    
    for ch in range(n_channels):
        for state_idx, freq in enumerate(freqs):
            amplitude = np.sin(phases[ch] + state_idx * np.pi/2) * 5
            data[ch] += amplitude * np.sin(2 * np.pi * freq * times)
    
    noise = np.random.randn(n_channels, n_samples) * 0.5
    data += noise
    
    ch_names = [f'EEG{i:03d}' for i in range(1, n_channels+1)]
    
    return data, ch_names, sfreq, times


def test_pipeline():
    print("=" * 60)
    print("EEG微状态分析 - 算法测试")
    print("=" * 60)
    
    print("\n1. 生成测试数据...")
    data, ch_names, sfreq, times = generate_test_data()
    print(f"   数据形状: {data.shape}")
    print(f"   通道数: {len(ch_names)}")
    print(f"   采样率: {sfreq} Hz")
    print(f"   时长: {times[-1]:.2f} s")
    
    print("\n2. 预处理（带通滤波1-40Hz + 平均参考）...")
    preprocessor = Preprocessor(low_freq=1.0, high_freq=40.0, sfreq=sfreq)
    processed_data = preprocessor.preprocess(data, reference_type='average')
    print(f"   预处理后数据形状: {processed_data.shape}")
    print(f"   幅值范围: [{processed_data.min():.2f}, {processed_data.max():.2f}] μV")
    
    print("\n3. GFP计算与峰值提取...")
    gfp_analyzer = GFPAnalyzer(sfreq=sfreq)
    gfp, peak_indices, peak_times, peak_data, _ = gfp_analyzer.analyze(
        processed_data, min_distance_ms=20
    )
    print(f"   GFP形状: {gfp.shape}")
    print(f"   提取的峰值数量: {len(peak_indices)}")
    print(f"   峰值数据形状: {peak_data.shape}")
    
    print("\n4. K-means聚类 (k=4)...")
    clustering = MicrostateClustering(n_clusters=4, n_init=50, max_iter=1000)
    templates, labels = clustering.fit(peak_data)
    print(f"   模板形状: {templates.shape}")
    print(f"   聚类标签形状: {labels.shape}")
    print(f"   解释方差: {clustering.explained_variance:.4f} ({clustering.explained_variance*100:.2f}%)")
    
    for i in range(4):
        count = np.sum(labels == i)
        print(f"   微状态 {i+1}: {count} 个峰值 ({count/len(labels)*100:.1f}%)")
    
    print("\n5. 模板拟合（空间相关性）...")
    template_fitting = TemplateFitting(templates, sfreq=sfreq)
    microstate_sequence, correlation_values = template_fitting.fit(processed_data)
    print(f"   微状态序列形状: {microstate_sequence.shape}")
    print(f"   相关值形状: {correlation_values.shape}")
    print(f"   平均分配相关性: {template_fitting.assignment_correlation.mean():.4f}")
    
    print("\n6. 统计分析...")
    stats_analyzer = StatisticsAnalyzer(sfreq=sfreq, n_clusters=4)
    stats = stats_analyzer.analyze(microstate_sequence)
    print("\n   --- 平均持续时间 (ms) ---")
    for i in range(4):
        print(f"   微状态 {i+1}: {stats['mean_durations'][i]:.2f} ± {stats['std_durations'][i]:.2f} ms")
    
    print("\n   --- 出现频率 (%) ---")
    for i in range(4):
        print(f"   微状态 {i+1}: {stats['frequencies'][i]*100:.2f}%")
    
    print("\n   --- 转换概率矩阵 ---")
    print("   " + "".join([f"状态{j+1:>7}" for j in range(4)]))
    for i in range(4):
        row = "".join([f"{stats['transition_probabilities'][i,j]:>7.3f}" for j in range(4)])
        print(f"   状态{i+1} {row}")
    
    print("\n" + "=" * 60)
    print("算法测试通过!")
    print("=" * 60)
    
    return True


if __name__ == '__main__':
    try:
        test_pipeline()
        sys.exit(0)
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
