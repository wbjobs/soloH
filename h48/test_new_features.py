# -*- coding: utf-8 -*-
"""
测试新增功能模块
1. 自适应小波包基选择（基于熵准则）
2. 陀螺温度补偿模型
3. 流式实时降噪（滑动窗口）
"""

import numpy as np
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from data_reader import FOGDataReader
from wavelet_denoiser import WaveletDenoiser, ThresholdType
from temperature_compensation import TemperatureCompensator, CompensationModelType
from streaming_processor import StreamingDenoiser, StreamingMode
from fog_processor import FOGDataProcessor


def generate_test_data(n_samples=20000, sample_rate=100.0, seed=42):
    """生成带噪声的测试数据"""
    np.random.seed(seed)
    t = np.arange(n_samples) / sample_rate

    true_signal = 0.5 * np.sin(2 * np.pi * 0.1 * t) + \
                  0.2 * np.sin(2 * np.pi * 0.5 * t)

    noise = np.random.normal(0, 0.3, n_samples)

    drift = np.zeros_like(t)
    for i in range(1, n_samples):
        drift[i] = drift[i-1] + np.random.normal(0, 0.005)

    rate_data = true_signal + drift + noise

    temperature = 25 + 5 * np.sin(2 * np.pi * 0.001 * t) + \
                  0.1 * np.random.normal(0, 1, n_samples)

    temp_drift = 0.1 * (temperature - 25) + 0.005 * (temperature - 25) ** 2
    rate_data_with_temp = rate_data + temp_drift

    return rate_data, rate_data_with_temp, temperature, sample_rate


def test_1_adaptive_wavelet_selection():
    """测试1: 自适应小波包基选择"""
    print("\n" + "=" * 70)
    print("测试1: 自适应小波包基选择（基于熵准则）")
    print("=" * 70)

    rate_data, _, _, sample_rate = generate_test_data()

    denoiser = WaveletDenoiser(wavelet='db4', level=4, threshold_type=ThresholdType.SOFT)

    wavelet_list = [f'db{i}' for i in range(1, 11)]
    criteria = ['shannon', 'threshold', 'log_energy']

    for criterion in criteria:
        print(f"\n--- 熵准则: {criterion} ---")
        result = denoiser.adaptive_wavelet_selection(
            rate_data,
            wavelet_list=wavelet_list,
            criterion=criterion,
            level=4,
            return_all=True
        )

        best_wavelet = result['best_wavelet']
        best_result = result['best_result']

        print(f"最优小波基: {best_wavelet}")
        print(f"熵值: {best_result['entropy']:.6f}")
        print(f"SNR: {best_result['snr']:.2f} dB")
        print(f"RMSE: {best_result['rmse']:.6f}")

        if criterion == 'shannon':
            assert 'best_wavelet' in result
            assert 'best_result' in result
            assert 'all_results' in result
            assert len(result['all_results']) == len(wavelet_list)

        print("✓ 熵准则测试通过")

    processor = FOGDataProcessor(sample_rate=sample_rate)
    proc_result = processor.adaptive_wavelet_selection(
        rate_data, criterion='shannon', data_name='test_adaptive'
    )

    assert proc_result['best_wavelet'] in wavelet_list
    print("\n✓ 自适应小波包基选择测试通过！")
    return True


def test_2_temperature_compensation():
    """测试2: 陀螺温度补偿模型"""
    print("\n" + "=" * 70)
    print("测试2: 陀螺温度补偿模型（温度与噪声的耦合去除）")
    print("=" * 70)

    rate_data, rate_data_with_temp, temperature, sample_rate = generate_test_data(
        n_samples=5000
    )

    model_types = [
        CompensationModelType.POLYNOMIAL,
        CompensationModelType.ARMA,
        CompensationModelType.LS_SVM,
        CompensationModelType.HYBRID
    ]

    for model_type in model_types:
        print(f"\n--- 模型类型: {model_type.value} ---")

        compensator = TemperatureCompensator(model_type=model_type)

        fit_result = compensator.fit(
            temperature, rate_data_with_temp,
            polynomial_order=4,
            arma_order=(2, 1),
            svm_gamma=10.0,
            svm_lambda=1.0
        )

        n_params = len(fit_result.get('coefficients', []))
        print(f"训练参数数量: {n_params}")
        print(f"R² score: {fit_result.get('r_squared', 0):.4f}")

        eval_result = compensator.evaluate(temperature, rate_data_with_temp)
        compensated = eval_result['compensated']

        print(f"原始标准差: {eval_result['std_before']:.6f}")
        print(f"补偿后标准差: {eval_result['std_after']:.6f}")
        print(f"标准差降低: {eval_result['std_reduction_percent']:.2f}%")

        assert len(compensated) == len(rate_data_with_temp)
        assert eval_result['std_reduction_percent'] > 0
        assert not np.isnan(compensated).any()

        print("✓ 模型测试通过")

    print("\n--- 模型对比测试 ---")
    compare_results = TemperatureCompensator.compare_models(
        temperature, rate_data_with_temp, plot=False
    )

    for name, result in compare_results.items():
        std_reduction = result['eval_result']['std_reduction_percent']
        print(f"  {name}: 标准差降低 {std_reduction:.2f}%")

    assert len(compare_results) == 4

    processor = FOGDataProcessor(sample_rate=sample_rate)
    proc_result = processor.temperature_compensation(
        temperature, rate_data_with_temp,
        model_type=CompensationModelType.POLYNOMIAL,
        data_name='test_temp_comp'
    )

    assert 'compensated_data' in proc_result
    assert len(proc_result['compensated_data']) == len(rate_data_with_temp)

    print("\n✓ 温度补偿模型测试通过！")
    return True


def test_3_streaming_denoiser():
    """测试3: 流式实时降噪"""
    print("\n" + "=" * 70)
    print("测试3: 流式实时降噪（滑动窗口）")
    print("=" * 70)

    rate_data, _, _, sample_rate = generate_test_data()

    modes = [
        StreamingMode.SLIDING_WINDOW,
        StreamingMode.OVERLAP_ADD,
        StreamingMode.ONLINE_UPDATE
    ]

    for mode in modes:
        print(f"\n--- 处理模式: {mode.value} ---")

        processor = StreamingDenoiser(
            window_size=1024,
            overlap=0.5,
            wavelet='db4',
            level=4,
            threshold_type=ThresholdType.SOFT,
            mode=mode
        )

        start_time = time.time()
        denoised = processor.process_offline(rate_data, verbose=False)
        elapsed = time.time() - start_time

        stats = processor.get_stats()

        print(f"输入样本数: {stats['total_samples_in']}")
        print(f"输出样本数: {stats['total_samples_out']}")
        print(f"处理窗口数: {stats['window_count']}")
        avg_time_ms = stats['avg_processing_time'] * 1000
        print(f"平均处理时间: {avg_time_ms:.3f} ms/窗口")
        print(f"总耗时: {elapsed:.3f} s")
        print(f"吞吐量: {len(rate_data) / elapsed:.1f} 样本/秒")
        print(f"延迟: {stats['latency_samples']} 样本")

        assert len(denoised) == len(rate_data)
        assert not np.isnan(denoised).any()
        assert not np.isinf(denoised).any()

        orig_std = np.std(rate_data)
        denoised_std = np.std(denoised)
        print(f"原始标准差: {orig_std:.6f}")
        print(f"降噪后标准差: {denoised_std:.6f}")
        print(f"降噪比: {orig_std / denoised_std:.2f}x")

        assert orig_std > denoised_std
        print("✓ 模式测试通过")

    print("\n--- 实时流式处理测试 ---")
    streamer = StreamingDenoiser(
        window_size=512,
        overlap=0.75,
        mode=StreamingMode.OVERLAP_ADD
    )

    chunk_size = 100
    output_batches = []

    for i in range(0, len(rate_data), chunk_size):
        chunk = rate_data[i:i + chunk_size]
        n_added = streamer.feed(chunk)
        output = streamer.process()

        if output is not None:
            output_batches.append(output)

    final_output = streamer.flush()
    if final_output is not None:
        output_batches.append(final_output)

    if output_batches:
        all_output = np.concatenate(output_batches)
        print(f"总输出样本数: {len(all_output)}")
        print(f"缓冲剩余: {len(streamer._input_buffer)}")

    stats = streamer.get_stats()
    streamer.print_stats()

    assert stats['total_samples_in'] == len(rate_data)
    print("✓ 实时流式测试通过")

    print("\n--- 模式对比测试 ---")
    compare_results = StreamingDenoiser.compare_modes(
        rate_data,
        wavelet='db4',
        level=4,
        window_size=1024,
        overlap=0.5
    )

    for name, result in compare_results.items():
        print(f"  {name}: SNR={result['snr']:.2f} dB, "
              f"延迟={result['stats']['latency_samples']} 样本")

    assert len(compare_results) == 3

    processor = FOGDataProcessor(sample_rate=sample_rate)
    proc_result = processor.stream_denoise_offline(
        rate_data,
        mode=StreamingMode.OVERLAP_ADD,
        window_size=1024,
        overlap=0.5,
        data_name='test_streaming'
    )

    assert 'denoised_data' in proc_result
    assert len(proc_result['denoised_data']) == len(rate_data)
    assert 'stats' in proc_result

    print("\n✓ 流式实时降噪测试通过！")
    return True


def test_4_integrated_workflow():
    """测试4: 综合工作流程 - 温度补偿 + 自适应小波 + 流式降噪"""
    print("\n" + "=" * 70)
    print("测试4: 综合工作流程 - 温度补偿 + 自适应小波 + 流式降噪")
    print("=" * 70)

    rate_data, rate_data_with_temp, temperature, sample_rate = generate_test_data(
        n_samples=3000
    )

    processor = FOGDataProcessor(
        sample_rate=sample_rate,
        wavelet='db4',
        level=4,
        threshold_type=ThresholdType.SOFT
    )

    print("\n步骤1: 温度补偿")
    temp_result = processor.temperature_compensation(
        temperature, rate_data_with_temp,
        model_type=CompensationModelType.POLYNOMIAL,
        data_name='integrated'
    )
    compensated = temp_result['compensated_data']

    orig_std = np.std(rate_data_with_temp)
    comp_std = np.std(compensated)
    print(f"  标准差降低: {(1 - comp_std / orig_std) * 100:.2f}%")

    print("\n步骤2: 自适应小波基选择")
    wavelet_result = processor.adaptive_wavelet_selection(
        compensated, criterion='shannon', data_name='integrated'
    )
    best_wavelet = wavelet_result['best_wavelet']
    processor.denoiser.set_wavelet(best_wavelet)
    print(f"  已设置小波基为: {best_wavelet}")

    print("\n步骤3: 流式降噪")
    stream_result = processor.stream_denoise_offline(
        compensated,
        mode=StreamingMode.OVERLAP_ADD,
        window_size=512,
        overlap=0.5,
        data_name='integrated'
    )
    denoised = stream_result['denoised_data']

    comp_std = np.std(compensated)
    denoised_std = np.std(denoised)
    print(f"  标准差降低: {(1 - denoised_std / comp_std) * 100:.2f}%")

    print("\n步骤4: Allan方差分析")
    allan_before = processor.analyzer.analyze(rate_data_with_temp)
    allan_after = processor.analyzer.analyze(denoised)

    print("\n噪声系数对比:")
    for key, name in [
        ('quantization_noise', '量化噪声'),
        ('angle_random_walk', '角度随机游走'),
        ('bias_instability', '零偏不稳定性'),
        ('rate_random_walk', '速率随机游走'),
        ('rate_ramp', '速率斜坡')
    ]:
        b = allan_before.get(key, 0)
        a = allan_after.get(key, 0)
        change = (a - b) / b * 100 if b != 0 else 0
        print(f"  {name}: {b:.2e} → {a:.2e} ({change:+.2f}%)")

    assert len(denoised) == len(rate_data_with_temp)
    assert np.std(denoised) < np.std(rate_data_with_temp)

    print("\n✓ 综合工作流程测试通过！")
    return True


def test_5_edge_cases():
    """测试5: 边界情况"""
    print("\n" + "=" * 70)
    print("测试5: 边界情况处理")
    print("=" * 70)

    print("\n--- 短数据测试 ---")
    short_data = np.random.normal(0, 0.1, 100)
    denoiser = WaveletDenoiser(level=3)

    result = denoiser.adaptive_wavelet_selection(short_data, level=3)
    assert 'best_wavelet' in result
    print("✓ 短数据自适应小波选择通过")

    print("\n--- 零信号测试 ---")
    zero_data = np.zeros(1000)
    zero_temp = np.ones(1000) * 25

    compensator = TemperatureCompensator()
    fit_result = compensator.fit(zero_temp, zero_data)
    eval_result = compensator.evaluate(zero_temp, zero_data)
    assert np.allclose(eval_result['compensated'], 0)
    print("✓ 零信号温度补偿通过")

    print("\n--- 窗口大小边界 ---")
    for window_size in [128, 256, 512, 1024, 2048]:
        streamer = StreamingDenoiser(window_size=window_size, overlap=0.5)
        test_data = np.random.normal(0, 0.1, window_size * 5)
        result = streamer.process_offline(test_data, verbose=False)
        assert len(result) == len(test_data)
        print(f"  窗口大小 {window_size}: ✓ 通过")

    print("\n--- 重叠比例边界 ---")
    for overlap in [0.0, 0.25, 0.5, 0.75, 0.9]:
        streamer = StreamingDenoiser(window_size=512, overlap=overlap)
        test_data = np.random.normal(0, 0.1, 5000)
        result = streamer.process_offline(test_data, verbose=False)
        assert len(result) == len(test_data)
        print(f"  重叠比例 {overlap * 100:.0f}%: ✓ 通过")

    print("\n✓ 边界情况测试通过！")
    return True


def main():
    """运行所有测试"""
    print("\n" + "#" * 70)
    print("# 新功能模块测试套件")
    print("#" * 70)

    tests = [
        ("自适应小波包基选择", test_1_adaptive_wavelet_selection),
        ("陀螺温度补偿模型", test_2_temperature_compensation),
        ("流式实时降噪", test_3_streaming_denoiser),
        ("综合工作流程", test_4_integrated_workflow),
        ("边界情况处理", test_5_edge_cases),
    ]

    results = []
    start_time = time.time()

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed, None))
        except Exception as e:
            import traceback
            traceback.print_exc()
            results.append((test_name, False, str(e)))

    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    print(f"总测试数: {len(tests)}")
    print(f"通过: {sum(1 for _, p, _ in results if p)}")
    print(f"失败: {sum(1 for _, p, _ in results if not p)}")
    print(f"总耗时: {elapsed:.2f} 秒")
    print("-" * 70)

    for name, passed, error in results:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}")
        if error:
            print(f"    Error: {error}")

    print("=" * 70)

    all_passed = all(p for _, p, _ in results)
    if all_passed:
        print("\n🎉 所有测试通过！新功能模块工作正常。")
    else:
        print("\n⚠️  部分测试失败，请检查错误信息。")

    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
