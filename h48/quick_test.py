import numpy as np
import sys
import os

def test_imports():
    """测试模块导入"""
    print("测试1: 模块导入...", end=" ")
    try:
        from data_reader import FOGDataReader, load_sample_data
        from wavelet_denoiser import WaveletDenoiser, ThresholdType
        from allan_variance import AllanVarianceAnalyzer
        from visualizer import DataVisualizer
        from fog_processor import FOGDataProcessor
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_data_reader():
    """测试数据读取模块"""
    print("测试2: 数据读取模块...", end=" ")
    try:
        from data_reader import load_sample_data
        t, rate = load_sample_data(duration=10, sample_rate=100, noise_level=1.0)
        assert len(t) == len(rate) == 1000
        assert np.allclose(t[1] - t[0], 0.01)
        print("[PASS] (生成了1000个数据点)")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_wavelet_denoiser():
    """测试小波包去噪模块"""
    print("测试3: 小波包去噪模块...", end=" ")
    try:
        from data_reader import load_sample_data
        from wavelet_denoiser import WaveletDenoiser, ThresholdType

        t, rate = load_sample_data(duration=10, sample_rate=100, noise_level=1.0)

        for threshold_type in [ThresholdType.SOFT, ThresholdType.HARD, ThresholdType.SURE]:
            denoiser = WaveletDenoiser(
                wavelet='db4', level=4, threshold_type=threshold_type
            )
            denoised = denoiser.denoise(rate)
            assert len(denoised) == len(rate)
            assert not np.any(np.isnan(denoised))

        print("[PASS] (支持软/硬/SURE阈值)")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_allan_variance():
    """测试Allan方差分析模块"""
    print("测试4: Allan方差分析模块...", end=" ")
    try:
        from data_reader import load_sample_data
        from allan_variance import AllanVarianceAnalyzer

        t, rate = load_sample_data(duration=50, sample_rate=100, noise_level=1.0)

        analyzer = AllanVarianceAnalyzer(sample_rate=100.0)
        results = analyzer.analyze(rate, tau_points=50)

        required_keys = [
            'quantization_noise', 'angle_random_walk', 'bias_instability',
            'rate_random_walk', 'rate_ramp', 'tau', 'allan_std', 'fitted_curve'
        ]
        for key in required_keys:
            assert key in results, f"缺少键: {key}"

        assert len(results['tau']) == len(results['allan_std'])
        assert all(results[k] > 0 for k in
                   ['quantization_noise', 'angle_random_walk', 'bias_instability',
                    'rate_random_walk', 'rate_ramp'])

        print(f"[PASS] (计算了5种噪声系数, 拟合状态: {results.get('success', '未知')})")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_visualizer():
    """测试可视化模块"""
    print("测试5: 可视化模块...", end=" ")
    try:
        from data_reader import load_sample_data
        from allan_variance import AllanVarianceAnalyzer
        from visualizer import DataVisualizer
        import tempfile

        t, rate = load_sample_data(duration=10, sample_rate=100, noise_level=1.0)

        analyzer = AllanVarianceAnalyzer(sample_rate=100.0)
        allan_results = analyzer.analyze(rate, tau_points=30)

        visualizer = DataVisualizer(sample_rate=100.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            signals = {'原始': rate, '降噪': rate * 0.9 + np.random.randn(len(rate)) * 0.01}

            visualizer.plot_time_series(t, signals, save_path=os.path.join(tmpdir, 'ts.png'))
            visualizer.plot_spectrum(signals, save_path=os.path.join(tmpdir, 'spec.png'))
            visualizer.plot_allan_variance({'测试': allan_results},
                                            save_path=os.path.join(tmpdir, 'allan.png'))

            assert os.path.exists(os.path.join(tmpdir, 'ts.png'))
            assert os.path.exists(os.path.join(tmpdir, 'spec.png'))
            assert os.path.exists(os.path.join(tmpdir, 'allan.png'))

        print("[PASS] (生成了时域/频域/Allan方差图)")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_processor():
    """测试主处理器模块"""
    print("测试6: 主处理器模块...", end=" ")
    try:
        from data_reader import load_sample_data
        from fog_processor import FOGDataProcessor
        from wavelet_denoiser import ThresholdType
        import tempfile

        t, rate = load_sample_data(duration=10, sample_rate=100, noise_level=1.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            processor = FOGDataProcessor(
                sample_rate=100.0,
                wavelet='db4',
                level=3,
                threshold_type=ThresholdType.SOFT,
                output_dir=tmpdir
            )

            results = processor.process_single(
                t, rate,
                data_name='test',
                generate_plots=True,
                save_denoised=True
            )

            assert 'original_data' in results
            assert 'denoised_data' in results
            assert 'allan_before' in results
            assert 'allan_after' in results

            assert os.path.exists(os.path.join(tmpdir, 'data', 'test_denoised.csv'))
            assert os.path.exists(os.path.join(tmpdir, 'figures', 'test_time_series.png'))

        print("[PASS] (完整处理流程)")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_processing():
    """测试批量处理功能"""
    print("测试7: 批量处理功能...", end=" ")
    try:
        from data_reader import load_sample_data
        from fog_processor import FOGDataProcessor
        from wavelet_denoiser import ThresholdType
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            import pandas as pd
            for i in range(3):
                t, rate = load_sample_data(duration=5, sample_rate=100, noise_level=0.5 + i * 0.5)
                df = pd.DataFrame({'t': t, 'rate': rate})
                df.to_csv(os.path.join(tmpdir, f'test_{i}.csv'), index=False)

            processor = FOGDataProcessor(
                sample_rate=100.0,
                output_dir='output_test_batch'
            )

            results = processor.process_directory(
                tmpdir,
                generate_plots=False,
                save_denoised=False
            )

            assert len(results) == 3
            print(f"[PASS] (处理了{len(results)}个文件)")

        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("光纤陀螺数据处理系统 - 快速测试")
    print("=" * 60)

    tests = [
        test_imports,
        test_data_reader,
        test_wavelet_denoiser,
        test_allan_variance,
        test_visualizer,
        test_processor,
        test_batch_processing
    ]

    results = []
    for test in tests:
        result = test()
        results.append(result)

    print("\n" + "=" * 60)
    print(f"测试完成: {sum(results)}/{len(results)} 通过")
    print("=" * 60)

    if all(results):
        print("\n✓ 所有测试通过！系统功能正常。")
        return 0
    else:
        print(f"\n✗ 有 {len(results) - sum(results)} 个测试失败，请检查错误信息。")
        return 1


if __name__ == '__main__':
    sys.exit(main())
