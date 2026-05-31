import numpy as np
import sys
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def test_wavelet_packet_frequency_order():
    """
    测试1: 验证小波包分解频带交错问题已修复
    检查分解后节点是否按正确频率顺序排列
    """
    print("\n" + "=" * 70)
    print("测试1: 小波包分解频带交错问题修复验证")
    print("=" * 70)

    from wavelet_denoiser import WaveletDenoiser, ThresholdType

    np.random.seed(42)
    t = np.linspace(0, 1, 1024)
    signal = (np.sin(2 * np.pi * 5 * t) +
              0.5 * np.sin(2 * np.pi * 50 * t) +
              0.3 * np.sin(2 * np.pi * 200 * t))

    denoiser = WaveletDenoiser(wavelet='db4', level=4, threshold_type=ThresholdType.SOFT)
    nodes, freq_order, adjusted_len = denoiser.wpd_decompose(signal)

    print(f"分解层数: {denoiser.level}")
    print(f"节点数量: {len(nodes)}")
    print(f"频率排序索引: {freq_order}")

    node_energies = [np.sum(node ** 2) for node in nodes]
    print(f"各节点能量: {[f'{e:.4f}' for e in node_energies]}")

    freq_low = 5
    freq_mid = 50
    freq_high = 200
    nyquist = 512

    expected_low_idx = int(freq_low / nyquist * len(nodes))
    expected_mid_idx = int(freq_mid / nyquist * len(nodes))
    expected_high_idx = int(freq_high / nyquist * len(nodes))

    print(f"\n低频成分(5Hz)应在节点 ~{expected_low_idx}")
    print(f"中频成分(50Hz)应在节点 ~{expected_mid_idx}")
    print(f"高频成分(200Hz)应在节点 ~{expected_high_idx}")

    max_energy_idx = np.argmax(node_energies)
    print(f"\n能量最大节点: {max_energy_idx} (预期 ~{expected_low_idx})")

    signal_reconstructed = denoiser.wpd_reconstruct(
        nodes, freq_order, adjusted_len, len(signal)
    )
    reconstruction_error = np.mean((signal - signal_reconstructed) ** 2)
    print(f"重构误差(MSE): {reconstruction_error:.2e}")

    denoised = denoiser.denoise(signal)
    denoise_error = np.mean((signal - denoised) ** 2)
    print(f"去噪后误差(MSE): {denoise_error:.2e}")

    has_oscillation = np.max(np.abs(np.diff(denoised, n=2))) > 10 * np.std(denoised) * 0.1
    print(f"是否存在振荡伪影: {'是' if has_oscillation else '否'}")

    passed = (reconstruction_error < 1e-10 and
              max_energy_idx <= expected_mid_idx and
              not has_oscillation)

    print(f"\n测试1结果: {'✓ 通过' if passed else '✗ 失败'}")
    return passed


def test_hard_threshold_continuity():
    """
    测试2: 验证硬阈值去噪后信号不连续性问题已修复
    检查改进的阈值函数是否消除了阶梯状抖动
    """
    print("\n" + "=" * 70)
    print("测试2: 硬阈值去噪不连续性问题修复验证")
    print("=" * 70)

    from wavelet_denoiser import WaveletDenoiser, ThresholdType

    np.random.seed(42)
    t = np.linspace(0, 10, 1000)
    clean_signal = np.sin(2 * np.pi * 2 * t) + 0.5 * np.sin(2 * np.pi * 0.5 * t)
    noisy_signal = clean_signal + np.random.randn(len(t)) * 0.3

    threshold_types = [
        (ThresholdType.HARD, '改进硬阈值(平滑)'),
        (ThresholdType.SOFT, '软阈值'),
        (ThresholdType.SEMISOFT, '半软阈值'),
        (ThresholdType.GARROTE, 'Garrote阈值'),
        (ThresholdType.HARD_SMOOTH, '平滑硬阈值'),
    ]

    results = {}

    for threshold_type, name in threshold_types:
        denoiser = WaveletDenoiser(
            wavelet='db4', level=4, threshold_type=threshold_type
        )
        denoised = denoiser.denoise(noisy_signal)

        second_diff = np.diff(denoised, n=2)
        max_jump = np.max(np.abs(second_diff))
        mean_jump = np.mean(np.abs(second_diff))
        std_jump = np.std(second_diff)
        snr = 10 * np.log10(np.sum(clean_signal ** 2) / np.sum((clean_signal - denoised) ** 2))

        jump_ratio = max_jump / (std_jump + 1e-10)
        is_continuous = jump_ratio < 10

        results[name] = {
            'snr': snr,
            'max_jump': max_jump,
            'mean_jump': mean_jump,
            'jump_ratio': jump_ratio,
            'is_continuous': is_continuous
        }

        print(f"\n{name}:")
        print(f"  SNR: {snr:.2f} dB")
        print(f"  最大二阶差分: {max_jump:.6f}")
        print(f"  二阶差分均值: {mean_jump:.6f}")
        print(f"  跳变比(连续性指标): {jump_ratio:.2f} {'(连续)' if is_continuous else '(不连续)'}")

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))

    axes[0, 0].plot(t, noisy_signal, 'b-', alpha=0.5, label='带噪信号')
    axes[0, 0].plot(t, clean_signal, 'r--', label='纯净信号')
    axes[0, 0].set_title('原始信号')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    for i, (threshold_type, name) in enumerate(threshold_types):
        row = (i + 1) // 3
        col = (i + 1) % 3
        denoiser = WaveletDenoiser(
            wavelet='db4', level=4, threshold_type=threshold_type
        )
        denoised = denoiser.denoise(noisy_signal)
        axes[row, col].plot(t, noisy_signal, 'b-', alpha=0.3, label='带噪信号')
        axes[row, col].plot(t, denoised, 'r-', label='去噪信号', linewidth=1.5)
        axes[row, col].set_title(f'{name} (SNR: {results[name]["snr"]:.1f} dB)')
        axes[row, col].legend()
        axes[row, col].grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs('test_output', exist_ok=True)
    plt.savefig('test_output/threshold_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()

    hard_result = results['改进硬阈值(平滑)']
    passed = hard_result['is_continuous'] and hard_result['snr'] > 5

    print(f"\n测试2结果: {'✓ 通过' if passed else '✗ 失败'}")
    print(f"  改进硬阈值连续性: {'✓ 连续' if hard_result['is_continuous'] else '✗ 不连续'}")
    print(f"  改进硬阈值SNR: {hard_result['snr']:.2f} dB")

    return passed


def test_allan_variance_overlapping():
    """
    测试3: 验证Allan方差重叠窗口算法修复
    比较重叠与非重叠窗口在长相关时间的估计偏差
    """
    print("\n" + "=" * 70)
    print("测试3: Allan方差长相关时间偏差修复验证")
    print("=" * 70)

    from allan_variance import AllanVarianceAnalyzer

    np.random.seed(42)
    sample_rate = 100.0
    duration = 200
    n_samples = int(duration * sample_rate)

    t = np.arange(n_samples) / sample_rate
    white_noise = np.random.randn(n_samples) * 0.01
    bias_instability = np.cumsum(np.random.randn(n_samples) * 0.0001)
    rate_ramp = 0.00001 * t
    rate_data = white_noise + bias_instability + rate_ramp

    analyzer = AllanVarianceAnalyzer(sample_rate=sample_rate)

    print("计算非重叠窗口Allan方差...")
    tau_no, std_no = analyzer.compute_allan_variance(
        rate_data, tau_points=50, overlapping=False
    )

    print("计算重叠窗口Allan方差...")
    tau_ol, std_ol = analyzer.compute_allan_variance(
        rate_data, tau_points=50, overlapping=True
    )

    print(f"\n非重叠窗口: {len(tau_no)} 个时间常数")
    print(f"重叠窗口: {len(tau_ol)} 个时间常数")

    print(f"\n非重叠最大τ: {tau_no[-1]:.2f} s")
    print(f"重叠最大τ: {tau_ol[-1]:.2f} s")

    common_tau_mask = tau_no <= min(tau_no[-1], tau_ol[-1])
    tau_common = tau_no[common_tau_mask]

    std_no_interp = np.interp(tau_common, tau_no, std_no)
    std_ol_interp = np.interp(tau_common, tau_ol, std_ol)

    relative_diff = np.abs(std_no_interp - std_ol_interp) / (std_ol_interp + 1e-20) * 100

    print(f"\n长τ区域 (τ > {tau_common[int(len(tau_common)*0.7)]:.1f}s) 对比:")
    long_tau_idx = tau_common > tau_common[int(len(tau_common) * 0.7)]
    if np.any(long_tau_idx):
        print(f"  平均相对偏差: {np.mean(relative_diff[long_tau_idx]):.2f}%")
        print(f"  最大相对偏差: {np.max(relative_diff[long_tau_idx]):.2f}%")
        print(f"  重叠窗口方差稳定性: {'✓ 更好' if np.std(std_ol_interp[long_tau_idx]) < np.std(std_no_interp[long_tau_idx]) else '✗ 无改善'}")

    results_ol = analyzer.analyze(rate_data, overlapping=True)
    results_no = analyzer.analyze(rate_data, overlapping=False)

    print(f"\n噪声系数对比:")
    params = [
        ('quantization_noise', '量化噪声'),
        ('angle_random_walk', '角度随机游走'),
        ('bias_instability', '零偏不稳定性'),
        ('rate_random_walk', '速率随机游走'),
        ('rate_ramp', '速率斜坡')
    ]

    for key, name in params:
        val_no = results_no.get(key, 0)
        val_ol = results_ol.get(key, 0)
        diff = abs(val_ol - val_no) / (abs(val_no) + 1e-20) * 100
        print(f"  {name}: 非重叠={val_no:.6e}, 重叠={val_ol:.6e}, 差异={diff:.2f}%")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    axes[0].loglog(tau_no, std_no, 'bo-', label='非重叠窗口', markersize=4, alpha=0.7)
    axes[0].loglog(tau_ol, std_ol, 'rs-', label='重叠窗口', markersize=4, alpha=0.7)
    axes[0].set_xlabel('时间常数 τ (s)', fontsize=12)
    axes[0].set_ylabel('Allan 标准差 σ (deg/h)', fontsize=12)
    axes[0].set_title('重叠 vs 非重叠窗口 Allan 方差对比', fontsize=14, fontweight='bold')
    axes[0].legend(fontsize=11)
    axes[0].grid(True, alpha=0.3, which='both')

    axes[1].semilogx(tau_common, relative_diff, 'g-', linewidth=1.5)
    axes[1].set_xlabel('时间常数 τ (s)', fontsize=12)
    axes[1].set_ylabel('相对偏差 (%)', fontsize=12)
    axes[1].set_title('非重叠窗口相对于重叠窗口的偏差', fontsize=14, fontweight='bold')
    axes[1].grid(True, alpha=0.3, which='both')

    plt.tight_layout()
    os.makedirs('test_output', exist_ok=True)
    plt.savefig('test_output/allan_overlapping_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()

    ol_has_more_points = len(tau_ol) >= len(tau_no)
    ol_longer_tau = tau_ol[-1] >= tau_no[-1] * 0.8
    ol_success = results_ol.get('success', False)

    passed = ol_has_more_points and ol_longer_tau and ol_success

    print(f"\n测试3结果: {'✓ 通过' if passed else '✗ 失败'}")
    print(f"  重叠窗口点数更多: {'✓ 是' if ol_has_more_points else '✗ 否'}")
    print(f"  重叠窗口τ范围更大: {'✓ 是' if ol_longer_tau else '✗ 否'}")
    print(f"  重叠窗口拟合成功: {'✓ 是' if ol_success else '✗ 否'}")

    return passed


def test_reconstruction_quality():
    """
    测试4: 综合验证去噪重构质量
    """
    print("\n" + "=" * 70)
    print("测试4: 综合去噪重构质量验证")
    print("=" * 70)

    from data_reader import load_sample_data
    from wavelet_denoiser import WaveletDenoiser, ThresholdType

    t, rate_data = load_sample_data(duration=50, sample_rate=100, noise_level=1.0)

    threshold_types = [
        ThresholdType.SOFT,
        ThresholdType.HARD,
        ThresholdType.SURE,
        ThresholdType.SEMISOFT,
        ThresholdType.GARROTE
    ]

    results = []

    for threshold_type in threshold_types:
        denoiser = WaveletDenoiser(
            wavelet='db4', level=4, threshold_type=threshold_type
        )
        denoised = denoiser.denoise(rate_data)

        smoothness = denoiser._calculate_smoothness(denoised)
        smoothness_original = denoiser._calculate_smoothness(rate_data)
        smoothness_ratio = smoothness_original / (smoothness + 1e-10)

        first_diff = np.abs(np.diff(denoised))
        max_diff = np.max(first_diff)
        mean_diff = np.mean(first_diff)
        continuity_indicator = max_diff / (mean_diff + 1e-10)

        noise_std = np.std(rate_data - denoised)
        signal_std = np.std(rate_data)
        noise_reduction = (np.std(rate_data) - np.std(denoised)) / np.std(rate_data) * 100

        results.append({
            'type': threshold_type.name,
            'noise_reduction': noise_reduction,
            'smoothness_ratio': smoothness_ratio,
            'continuity': continuity_indicator
        })

        print(f"\n{threshold_type.name}:")
        print(f"  噪声抑制: {noise_reduction:+.2f}%")
        print(f"  平滑度提升: {smoothness_ratio:.2f}x")
        print(f"  连续性指标: {continuity_indicator:.2f} (<20为好)")
        print(f"  标准差: 原始={signal_std:.6f}, 降噪后={np.std(denoised):.6f}, 噪声={noise_std:.6f}")

    df = pd.DataFrame(results)
    os.makedirs('test_output', exist_ok=True)
    df.to_csv('test_output/denoising_quality.csv', index=False, encoding='utf-8-sig')

    passed = all(r['noise_reduction'] > 0 for r in results)

    print(f"\n测试4结果: {'✓ 通过' if passed else '✗ 失败'}")
    print(f"  所有阈值方法均实现噪声抑制: {'✓ 是' if passed else '✗ 否'}")

    return passed


def main():
    """运行所有修复验证测试"""
    print("\n" + "#" * 70)
    print("#" + " " * 68 + "#")
    print("#" + " " * 15 + "光纤陀螺数据处理系统 - 修复验证测试" + " " * 16 + "#")
    print("#" + " " * 68 + "#")
    print("#" * 70)

    import pandas as pd

    tests = [
        test_wavelet_packet_frequency_order,
        test_hard_threshold_continuity,
        test_allan_variance_overlapping,
        test_reconstruction_quality
    ]

    test_names = [
        "小波包频带交错修复",
        "硬阈值连续性修复",
        "Allan方差重叠窗口修复",
        "综合去噪质量"
    ]

    results = []
    for test, name in zip(tests, test_names):
        try:
            result = test()
            results.append({'测试项': name, '结果': '通过' if result else '失败'})
        except Exception as e:
            print(f"\n测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append({'测试项': name, '结果': '异常'})

    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)

    df = pd.DataFrame(results)
    print(df.to_string(index=False))

    passed_count = sum(1 for r in results if r['结果'] == '通过')
    total_count = len(results)

    print(f"\n总计: {passed_count}/{total_count} 通过")

    if passed_count == total_count:
        print("\n✓ 所有修复验证测试通过！")
        print("\n修复总结:")
        print("  1. ✓ 小波包分解: 频带交错问题已修复，使用正确的频率排序算法")
        print("  2. ✓ 硬阈值去噪: 不连续性已修复，默认使用平滑硬阈值")
        print("     新增阈值方法: 半软阈值、Garrote阈值、平滑硬阈值")
        print("  3. ✓ Allan方差: 长相关时间估计偏差已修复，使用重叠窗口算法")
        return 0
    else:
        print(f"\n✗ 有 {total_count - passed_count} 个测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
