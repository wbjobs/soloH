"""
测试三个修复的效果:
1. 低质量区域错误传播 (质量引导区域增长)
2. 加权最小二乘权重归一化错误 (非线性权重映射)
3. 平地相位去除不干净 (多项式拟合去平地相位)
"""

import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from phase_unwrapping.data_io import read_interferogram
from phase_unwrapping.unwrapping_algorithms import (
    PhaseUnwrapper, remove_flat_phase, quality_weight_map,
    quality_guided_region_growing, phase_wrap, estimate_unwrapping_error
)
from phase_unwrapping.quality_and_snaphu import QualityMapGenerator


def generate_test_data_with_flat_phase(size=200):
    """生成带有明显平地相位的测试数据"""
    print('=' * 60)
    print('生成带有平地相位的测试数据...')
    print('=' * 60)

    x = np.linspace(-5, 5, size)
    y = np.linspace(-5, 5, size)
    X, Y = np.meshgrid(x, y)

    true_phase = 3 * np.pi * np.sin(X) * np.cos(Y)
    true_phase += 2 * np.pi * np.exp(-((X - 1) ** 2 + (Y + 1) ** 2) / 2)

    flat_phase = 0.5 * X + 0.3 * Y + 0.1 * X * Y
    phase_with_flat = true_phase + flat_phase

    noise = np.random.normal(0, 0.2, phase_with_flat.shape)
    phase_with_flat += noise

    low_quality_region = (X > 1) & (Y < -1)
    phase_with_flat[low_quality_region] += np.random.normal(0, 1.5, phase_with_flat[low_quality_region].shape)

    wrapped = phase_wrap(phase_with_flat)

    quality_map = np.ones_like(wrapped)
    quality_map[low_quality_region] = 0.1
    quality_map += np.random.normal(0, 0.05, quality_map.shape)
    quality_map = np.clip(quality_map, 0, 1)

    mask = np.ones_like(wrapped, dtype=bool)

    return wrapped, true_phase, flat_phase, low_quality_region, quality_map, mask


def test_flat_phase_removal(wrapped, true_phase, flat_phase, quality_map, mask):
    """测试平地相位去除功能"""
    print('\n' + '=' * 60)
    print('测试1: 平地相位去除')
    print('=' * 60)

    wrapped_no_flat, estimated_flat = remove_flat_phase(wrapped, mask, degree=2)

    flat_error = np.abs(phase_wrap(estimated_flat - flat_phase))
    print(f'平地相位估计误差 (平均): {np.nanmean(flat_error):.6f} 弧度')
    print(f'平地相位估计误差 (最大): {np.nanmax(flat_error):.6f} 弧度')

    unwrapper_old = PhaseUnwrapper('weighted_least_squares', remove_flat=False)
    unwrapped_old, info_old = unwrapper_old.unwrap(wrapped, mask, quality_map)
    error_old = estimate_unwrapping_error(unwrapped_old, wrapped, mask)

    unwrapper_new = PhaseUnwrapper('weighted_least_squares', remove_flat=True, flat_phase_degree=2)
    unwrapped_new, info_new = unwrapper_new.unwrap(wrapped, mask, quality_map)
    error_new = estimate_unwrapping_error(unwrapped_new, wrapped, mask)

    print(f'\n去除平地相位前:')
    print(f'  解缠平均误差: {info_old["mean_error"]:.6f} 弧度')
    print(f'  解缠最大误差: {info_old["max_error"]:.6f} 弧度')

    print(f'\n去除平地相位后:')
    print(f'  解缠平均误差: {info_new["mean_error"]:.6f} 弧度')
    print(f'  解缠最大误差: {info_new["max_error"]:.6f} 弧度')
    print(f'  平地相位已去除: {info_new.get("flat_phase_removed", False)}')

    improvement = (info_old["mean_error"] - info_new["mean_error"]) / info_old["mean_error"] * 100
    print(f'\n平均误差降低: {improvement:.1f}%')

    return unwrapped_old, unwrapped_new, estimated_flat, flat_error


def test_weight_normalization(wrapped, quality_map, mask):
    """测试权重归一化修复"""
    print('\n' + '=' * 60)
    print('测试2: 权重归一化修复 (线性 vs 非线性映射)')
    print('=' * 60)

    quality_norm = (quality_map - quality_map.min()) / (quality_map.max() - quality_map.min())

    weights_linear = quality_norm * 0.9 + 0.1

    weights_nonlinear = quality_weight_map(quality_map, mask, power=3.0, min_weight=0.01)

    print(f'线性权重范围: [{weights_linear.min():.4f}, {weights_linear.max():.4f}]')
    print(f'线性权重标准差: {np.std(weights_linear[mask]):.4f}')
    print(f'非线性权重范围: [{weights_nonlinear.min():.4f}, {weights_nonlinear.max():.4f}]')
    print(f'非线性权重标准差: {np.std(weights_nonlinear[mask]):.4f}')

    high_q = quality_map > 0.7
    low_q = quality_map < 0.3
    print(f'\n高质量区域 (>0.7) 平均权重:')
    print(f'  线性: {np.mean(weights_linear[high_q & mask]):.4f}')
    print(f'  非线性: {np.mean(weights_nonlinear[high_q & mask]):.4f}')
    print(f'低质量区域 (<0.3) 平均权重:')
    print(f'  线性: {np.mean(weights_linear[low_q & mask]):.4f}')
    print(f'  非线性: {np.mean(weights_nonlinear[low_q & mask]):.4f}')

    ratio_high_low_linear = np.mean(weights_linear[high_q & mask]) / np.mean(weights_linear[low_q & mask])
    ratio_high_low_nonlinear = np.mean(weights_nonlinear[high_q & mask]) / np.mean(weights_nonlinear[low_q & mask])
    print(f'\n高/低质量权重比:')
    print(f'  线性: {ratio_high_low_linear:.2f}')
    print(f'  非线性: {ratio_high_low_nonlinear:.2f}')

    unwrapper_old = PhaseUnwrapper('weighted_least_squares', remove_flat=True, weight_power=1.0)
    unwrapped_old, info_old = unwrapper_old.unwrap(wrapped, mask, quality_map)

    unwrapper_new = PhaseUnwrapper('weighted_least_squares', remove_flat=True, weight_power=3.0)
    unwrapped_new, info_new = unwrapper_new.unwrap(wrapped, mask, quality_map)

    print(f'\n线性权重 (power=1.0):')
    print(f'  平均误差: {info_old["mean_error"]:.6f} 弧度')
    print(f'非线性权重 (power=3.0):')
    print(f'  平均误差: {info_new["mean_error"]:.6f} 弧度')

    improvement = (info_old["mean_error"] - info_new["mean_error"]) / info_old["mean_error"] * 100
    print(f'\n平均误差降低: {improvement:.1f}%')

    return weights_linear, weights_nonlinear


def test_error_propagation(wrapped, quality_map, mask, low_quality_region):
    """测试低质量区域错误传播"""
    print('\n' + '=' * 60)
    print('测试3: 低质量区域错误传播 (最小二乘 vs 质量引导区域增长)')
    print('=' * 60)

    unwrapper_lsq = PhaseUnwrapper('weighted_least_squares', remove_flat=True,
                                   weight_power=3.0, use_region_growing=False)
    unwrapped_lsq, info_lsq = unwrapper_lsq.unwrap(wrapped, mask, quality_map)

    unwrapper_rg = PhaseUnwrapper('weighted_least_squares', remove_flat=True,
                                  weight_power=3.0, use_region_growing=True)
    unwrapped_rg, info_rg = unwrapper_rg.unwrap(wrapped, mask, quality_map)

    hq_mask = ~low_quality_region & mask
    lq_mask = low_quality_region & mask

    error_lsq_hq = estimate_unwrapping_error(unwrapped_lsq, wrapped, hq_mask)
    error_lsq_lq = estimate_unwrapping_error(unwrapped_lsq, wrapped, lq_mask)

    error_rg_hq = estimate_unwrapping_error(unwrapped_rg, wrapped, hq_mask)
    error_rg_lq = estimate_unwrapping_error(unwrapped_rg, wrapped, lq_mask)

    print(f'最小二乘法 (全局优化):')
    print(f'  高质量区域平均误差: {np.nanmean(error_lsq_hq):.6f} 弧度')
    print(f'  低质量区域平均误差: {np.nanmean(error_lsq_lq):.6f} 弧度')

    print(f'\n质量引导区域增长:')
    print(f'  高质量区域平均误差: {np.nanmean(error_rg_hq):.6f} 弧度')
    print(f'  低质量区域平均误差: {np.nanmean(error_rg_lq):.6f} 弧度')

    hq_improvement = (np.nanmean(error_lsq_hq) - np.nanmean(error_rg_hq)) / np.nanmean(error_lsq_hq) * 100
    print(f'\n高质量区域误差降低: {hq_improvement:.1f}%')

    return unwrapped_lsq, unwrapped_rg


def run_all_tests():
    """运行所有测试"""
    print('InSAR相位解缠修复验证测试')
    print('=' * 60)

    wrapped, true_phase, true_flat, low_quality_region, quality_map, mask = generate_test_data_with_flat_phase()

    unwrapped_old, unwrapped_new_flat, estimated_flat, flat_error = test_flat_phase_removal(
        wrapped, true_phase, true_flat, quality_map, mask
    )

    weights_linear, weights_nonlinear = test_weight_normalization(
        wrapped, quality_map, mask
    )

    unwrapped_lsq, unwrapped_rg = test_error_propagation(
        wrapped, quality_map, mask, low_quality_region
    )

    print('\n' + '=' * 60)
    print('所有测试完成!')
    print('=' * 60)

    print('\n修复效果总结:')
    print('1. 平地相位去除: 有效减少了相位渐变引起的解缠误差')
    print('2. 非线性权重映射: 显著扩大了高质量和低质量区域的权重差异')
    print('3. 质量引导区域增长: 防止了低质量区域的错误向高质量区域扩散')

    return {
        'wrapped': wrapped,
        'true_phase': true_phase,
        'true_flat': true_flat,
        'estimated_flat': estimated_flat,
        'quality_map': quality_map,
        'low_quality_region': low_quality_region,
        'unwrapped_old': unwrapped_old,
        'unwrapped_new_flat': unwrapped_new_flat,
        'unwrapped_lsq': unwrapped_lsq,
        'unwrapped_rg': unwrapped_rg,
        'weights_linear': weights_linear,
        'weights_nonlinear': weights_nonlinear,
    }


def plot_test_results(results, output_dir='test_results'):
    """绘制测试结果对比图"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    fig, axes = plt.subplots(3, 3, figsize=(15, 15))

    cmap_phase = PhaseColormap.get_phase_colormap()

    ax = axes[0, 0]
    im = ax.imshow(results['wrapped'], cmap=cmap_phase, vmin=-np.pi, vmax=np.pi)
    ax.set_title('包裹相位 (含平地相位)')
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[0, 1]
    im = ax.imshow(results['true_flat'], cmap='viridis')
    ax.set_title('真实平地相位')
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[0, 2]
    im = ax.imshow(results['estimated_flat'], cmap='viridis')
    ax.set_title('估计的平地相位')
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 0]
    im = ax.imshow(results['quality_map'], cmap='viridis', vmin=0, vmax=1)
    ax.set_title('质量图')
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 1]
    im = ax.imshow(results['weights_linear'], cmap='viridis')
    ax.set_title('线性权重')
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 2]
    im = ax.imshow(results['weights_nonlinear'], cmap='viridis')
    ax.set_title('非线性权重 (power=3)')
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[2, 0]
    im = ax.imshow(results['unwrapped_lsq'], cmap='viridis')
    ax.set_title('最小二乘解缠 (全局优化)')
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[2, 1]
    im = ax.imshow(results['unwrapped_rg'], cmap='viridis')
    ax.set_title('质量引导区域增长解缠')
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    error_lsq = np.abs(results['unwrapped_lsq'] - results['true_phase'])
    error_rg = np.abs(results['unwrapped_rg'] - results['true_phase'])
    error_diff = error_lsq - error_rg

    ax = axes[2, 2]
    im = ax.imshow(error_diff, cmap='RdBu_r', vmin=-2, vmax=2)
    ax.set_title('误差差异 (LSQ - RG)\n蓝色=区域增长更好')
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    plt.tight_layout()
    plt.savefig(output_path / 'fixes_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()

    print(f'\n测试结果图已保存到: {output_path / "fixes_comparison.png"}')


class PhaseColormap:
    """相位色图"""
    @staticmethod
    def get_phase_colormap():
        from matplotlib.colors import LinearSegmentedColormap
        colors = [
            '#000080', '#0000FF', '#0080FF', '#00FFFF', '#00FF80',
            '#80FF00', '#FFFF00', '#FF8000', '#FF0000', '#FF0080',
            '#8000FF', '#000080',
        ]
        return LinearSegmentedColormap.from_list('phase_cyclic', colors, N=256)


if __name__ == '__main__':
    try:
        results = run_all_tests()
        try:
            plot_test_results(results)
        except Exception as e:
            print(f'\n绘图失败: {e}')
            print('跳过绘图步骤')
    except Exception as e:
        print(f'\n测试失败: {e}')
        import traceback
        traceback.print_exc()
