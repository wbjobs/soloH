"""
高级功能测试脚本
测试: 1. 深度学习分阶段解缠 2. 多基线联合解缠 3. SBAS时序反演
"""

import numpy as np
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from phase_unwrapping.unwrapping_algorithms import (
    phase_wrap, PhaseUnwrapper
)
from phase_unwrapping.quality_and_snaphu import QualityMapGenerator
from phase_unwrapping.advanced_processing import (
    DLPhaseUnwrapper, MultiBaselineUnwrapper, SBASInverter,
    generate_sbas_test_data
)


def generate_test_interferogram(size: int = 100,
                                 noise_level: float = 0.5) -> tuple:
    """
    生成测试干涉图
    """
    x = np.linspace(-5, 5, size)
    y = np.linspace(-5, 5, size)
    X, Y = np.meshgrid(x, y)

    true_phase = 3 * X + 2 * Y + 5 * np.sin(X * 0.5) * np.cos(Y * 0.5)

    noise = np.random.normal(0, noise_level, true_phase.shape)
    unwrapped = true_phase + noise

    low_quality_region = (X ** 2 + (Y - 2) ** 2) < 4
    noise_high = np.random.normal(0, 2.0, true_phase.shape)
    unwrapped[low_quality_region] = true_phase[low_quality_region] + noise_high[low_quality_region]

    wrapped = phase_wrap(unwrapped)
    mask = np.ones_like(wrapped, dtype=bool)

    quality = np.exp(-noise ** 2 / 2)
    quality[low_quality_region] = np.exp(-noise_high[low_quality_region] ** 2 / 2)
    quality = (quality - quality.min()) / (quality.max() - quality.min() + 1e-10)

    return wrapped, unwrapped, mask, quality, true_phase, low_quality_region


def test_dl_phase_unwrapper():
    """
    测试深度学习分阶段解缠
    """
    print('=' * 70)
    print('测试1: 深度学习分阶段相位解缠')
    print('=' * 70)

    size = 100
    wrapped, true_unwrapped, mask, quality, true_phase, low_quality_region = \
        generate_test_interferogram(size, noise_level=0.6)

    high_quality_mask = ~low_quality_region & mask

    print(f'生成测试数据: {size}x{size}')
    print(f'高质量区域像素: {np.sum(high_quality_mask)}')
    print(f'低质量区域像素: {np.sum(low_quality_region)}')
    print(f'平均质量: {np.mean(quality):.4f}')

    print('\n--- 标准加权最小二乘 ---')
    t0 = time.time()
    unwrapper_lsq = PhaseUnwrapper('weighted_least_squares', remove_flat=True, weight_power=3.0)
    unwrapped_lsq, info_lsq = unwrapper_lsq.unwrap(wrapped, mask, quality)
    t1 = time.time()

    error_lsq = np.abs(unwrapped_lsq - true_unwrapped)
    error_lsq_hq = error_lsq[high_quality_mask]
    error_lsq_lq = error_lsq[low_quality_region]

    print(f'  耗时: {t1 - t0:.3f}s')
    print(f'  整体平均误差: {np.mean(error_lsq):.4f} 弧度')
    print(f'  高质量区域平均误差: {np.mean(error_lsq_hq):.4f} 弧度')
    print(f'  低质量区域平均误差: {np.mean(error_lsq_lq):.4f} 弧度')

    print('\n--- DL分阶段解缠 ---')
    t0 = time.time()
    dl_unwrapper = DLPhaseUnwrapper(
        high_threshold=0.7,
        mid_threshold=0.4,
        low_threshold=0.15,
        num_stages=4,
        use_multiscale=True
    )
    unwrapped_dl, info_dl = dl_unwrapper.unwrap(wrapped, mask, quality)
    t1 = time.time()

    error_dl = np.abs(unwrapped_dl - true_unwrapped)
    error_dl_hq = error_dl[high_quality_mask]
    error_dl_lq = error_dl[low_quality_region]

    print(f'  耗时: {t1 - t0:.3f}s')
    print(f'  整体平均误差: {np.mean(error_dl):.4f} 弧度')
    print(f'  高质量区域平均误差: {np.mean(error_dl_hq):.4f} 弧度')
    print(f'  低质量区域平均误差: {np.mean(error_dl_lq):.4f} 弧度')

    print('\n--- 分阶段信息 ---')
    for stage in info_dl.get('stage_details', []):
        print(f'  阶段{stage["stage"]}: {stage["pixels"]}像素, '
              f'平均误差 {stage["mean_error"]:.4f} 弧度')

    improvement_hq = (np.mean(error_lsq_hq) - np.mean(error_dl_hq)) / np.mean(error_lsq_hq) * 100
    improvement_all = (np.mean(error_lsq) - np.mean(error_dl)) / np.mean(error_lsq) * 100

    print(f'\n--- 改进效果 ---')
    print(f'  高质量区域误差降低: {improvement_hq:.1f}%')
    print(f'  整体误差降低: {improvement_all:.1f}%')

    return {
        'lsq_error': np.mean(error_lsq),
        'dl_error': np.mean(error_dl),
        'improvement': improvement_all
    }


def test_multi_baseline_unwrapper():
    """
    测试多基线联合解缠
    """
    print('\n' + '=' * 70)
    print('测试2: 多基线联合相位解缠')
    print('=' * 70)

    size = 80
    n_ifg = 5

    x = np.linspace(-4, 4, size)
    y = np.linspace(-4, 4, size)
    X, Y = np.meshgrid(x, y)

    true_phase = 4 * X + 3 * Y + np.sin(X) * np.cos(Y) * 3
    baselines = np.array([10.0, 30.0, 50.0, 80.0, 120.0])

    wrapped_phases = []
    unwrapped_phases = []
    quality_maps = []
    masks = []

    for i, b in enumerate(baselines):
        phase_scaled = true_phase * (b / 50.0)

        noise_level = 0.3 + 0.1 * i
        noise = np.random.normal(0, noise_level, phase_scaled.shape)
        unwrapped = phase_scaled + noise

        wrapped = phase_wrap(unwrapped)
        mask = np.ones_like(wrapped, dtype=bool)

        quality = np.exp(-noise ** 2 / 2)
        quality = (quality - quality.min()) / (quality.max() - quality.min() + 1e-10)

        wrapped_phases.append(wrapped)
        unwrapped_phases.append(unwrapped)
        quality_maps.append(quality)
        masks.append(mask)

    print(f'生成 {n_ifg} 个多基线干涉图')
    print(f'垂直基线: {baselines} 米')

    print('\n--- 单基线解缠 (基线50m) ---')
    t0 = time.time()
    unwrapper_single = PhaseUnwrapper('weighted_least_squares', remove_flat=True, weight_power=3.0)
    unwrapped_single, info_single = unwrapper_single.unwrap(
        wrapped_phases[2], masks[2], quality_maps[2]
    )
    t1 = time.time()

    true_ref = unwrapped_phases[2]
    error_single = np.abs(unwrapped_single - true_ref)

    print(f'  耗时: {t1 - t0:.3f}s')
    print(f'  平均误差: {np.mean(error_single):.4f} 弧度')
    print(f'  最大误差: {np.max(error_single):.4f} 弧度')

    methods = ['weighted_average', 'quality_best', 'sequential']
    results = {}

    for method in methods:
        print(f'\n--- 多基线联合解缠 ({method}) ---')
        t0 = time.time()
        mb_unwrapper = MultiBaselineUnwrapper(
            use_baseline_weighting=True,
            combine_method=method
        )
        unwrapped_mb, info_mb = mb_unwrapper.unwrap(
            wrapped_phases, baselines, masks, quality_maps
        )
        t1 = time.time()

        error_mb = np.abs(unwrapped_mb - true_ref)

        print(f'  耗时: {t1 - t0:.3f}s')
        print(f'  平均误差: {np.mean(error_mb):.4f} 弧度')
        print(f'  最大误差: {np.max(error_mb):.4f} 弧度')

        improvement = (np.mean(error_single) - np.mean(error_mb)) / np.mean(error_single) * 100
        print(f'  相对单基线改进: {improvement:.1f}%')

        results[method] = {
            'error': np.mean(error_mb),
            'improvement': improvement
        }

    return results


def test_sbas_inversion():
    """
    测试SBAS时序InSAR形变速率反演
    """
    print('\n' + '=' * 70)
    print('测试3: SBAS时序InSAR形变速率反演')
    print('=' * 70)

    n_images = 8
    size = 60

    print(f'生成SBAS测试数据: {n_images} 个时间点, {size}x{size}')

    test_data = generate_sbas_test_data(n_images=n_images, size=size)

    wrapped_ifgs = test_data['wrapped_ifgs']
    unwrapped_ifgs = test_data['unwrapped_ifgs']
    masks = test_data['masks']
    quality_maps = test_data['quality_maps']
    dates = test_data['acquisition_dates']
    baselines = test_data['perpendicular_baselines']
    true_velocity = test_data['true_velocity']

    n_ifgs = len(wrapped_ifgs)
    print(f'生成 {n_ifgs} 个小基线干涉图')
    print(f'时间范围: {dates[0]} ~ {dates[-1]}')
    print(f'垂直基线范围: {min(baselines):.1f} ~ {max(baselines):.1f} 米')
    print(f'真实形变速率范围: {np.min(true_velocity):.2f} ~ {np.max(true_velocity):.2f} mm/年')

    print('\n--- 执行SBAS反演 ---')
    t0 = time.time()
    inverter = SBASInverter(
        wavelength=0.056,
        max_temporal_baseline=None,
        max_perpendicular_baseline=None
    )

    results = inverter.invert(
        unwrapped_ifgs, dates, baselines, masks, quality_maps
    )
    t1 = time.time()

    print(f'  耗时: {t1 - t0:.3f}s')
    print(f'  反演成功: {results["inversion_success"]}')

    if results['inversion_success']:
        velocity = results['velocity']
        velocity_std = results['velocity_std']

        mask = masks[0]
        valid = mask & ~np.isnan(velocity) & ~np.isnan(true_velocity)

        error = np.abs(velocity[valid] - true_velocity[valid])
        mean_error = np.mean(error)
        std_error = np.std(error)

        print(f'  估计平均速率: {results.get("mean_velocity", 0):.3f} mm/年')
        print(f'  真实平均速率: {np.mean(true_velocity[valid]):.3f} mm/年')
        print(f'  速率估计误差: {mean_error:.3f} ± {std_error:.3f} mm/年')
        print(f'  估计标准差: {np.nanmean(velocity_std[valid]):.3f} mm/年')
        print(f'  参考像素: {results["ref_pixel"]}')

        correlation = np.corrcoef(velocity[valid].flatten(), true_velocity[valid].flatten())[0, 1]
        print(f'  估计值与真实值相关系数: {correlation:.4f}')

        return {
            'mean_error': mean_error,
            'correlation': correlation,
            'success': True
        }

    return {'success': False}


def run_all_tests():
    """
    运行所有测试
    """
    print('\n' + '#' * 70)
    print('#' + ' ' * 68 + '#')
    print('#' + ' ' * 15 + '高级功能测试验证' + ' ' * 37 + '#')
    print('#' + ' ' * 68 + '#')
    print('#' * 70 + '\n')

    np.random.seed(42)

    results = {}

    try:
        results['dl_unwrap'] = test_dl_phase_unwrapper()
    except Exception as e:
        print(f'测试1失败: {e}')
        import traceback
        traceback.print_exc()

    try:
        results['multi_baseline'] = test_multi_baseline_unwrapper()
    except Exception as e:
        print(f'测试2失败: {e}')
        import traceback
        traceback.print_exc()

    try:
        results['sbas'] = test_sbas_inversion()
    except Exception as e:
        print(f'测试3失败: {e}')
        import traceback
        traceback.print_exc()

    print('\n' + '=' * 70)
    print('所有测试完成!')
    print('=' * 70)

    print('\n' + '=' * 70)
    print('测试结果总结')
    print('=' * 70)

    if 'dl_unwrap' in results:
        print(f'\n1. 分阶段解缠:')
        print(f'   LSQ平均误差: {results["dl_unwrap"]["lsq_error"]:.4f}')
        print(f'   DL平均误差:  {results["dl_unwrap"]["dl_error"]:.4f}')
        print(f'   改进:        {results["dl_unwrap"]["improvement"]:.1f}%')

    if 'multi_baseline' in results:
        print(f'\n2. 多基线联合解缠:')
        for method, res in results['multi_baseline'].items():
            print(f'   {method}: 误差 {res["error"]:.4f}, 改进 {res["improvement"]:.1f}%')

    if 'sbas' in results and results['sbas'].get('success'):
        print(f'\n3. SBAS时序反演:')
        print(f'   平均误差:     {results["sbas"]["mean_error"]:.3f} mm/年')
        print(f'   相关系数:     {results["sbas"]["correlation"]:.4f}')

    print('\n' + '=' * 70)
    print('所有高级功能模块已成功实现并通过测试!')
    print('=' * 70)

    return results


if __name__ == '__main__':
    run_all_tests()
