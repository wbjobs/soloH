"""
API使用示例
展示如何直接调用相位解缠库的各个功能模块
"""

import numpy as np
from pathlib import Path

from phase_unwrapping.data_io import read_interferogram, write_envi, write_geotiff
from phase_unwrapping.unwrapping_algorithms import (
    PhaseUnwrapper, detect_residues, estimate_unwrapping_error, phase_wrap
)
from phase_unwrapping.quality_and_snaphu import QualityMapGenerator, get_snaphu_unwrapper
from phase_unwrapping.mask_processing import MaskProcessor, AutoMaskGenerator


def example_1_basic_unwrapping():
    """示例1: 基本相位解缠流程"""
    print('=' * 60)
    print('示例1: 基本相位解缠流程')
    print('=' * 60)

    test_file = Path('test_data/wrapped_phase.tif')
    if not test_file.exists():
        print('测试数据不存在，请先运行 generate_test_data.py')
        return

    wrapped_phase, metadata = read_interferogram(str(test_file))
    print(f'加载数据: {wrapped_phase.shape}')
    print(f'相位范围: [{wrapped_phase.min():.4f}, {wrapped_phase.max():.4f}]')

    quality_map = QualityMapGenerator.generate(
        wrapped_phase,
        method='pseudo_coherence',
        window_size=5
    )
    print(f'质量图平均质量: {np.nanmean(quality_map):.4f}')

    mask = MaskProcessor.create_valid_mask(wrapped_phase)
    print(f'有效像素: {mask.sum()} / {mask.size}')

    print('\n执行最小二乘相位解缠...')
    unwrapper = PhaseUnwrapper('least_squares')
    unwrapped, info = unwrapper.unwrap(
        wrapped_phase,
        mask=mask,
        quality_map=quality_map
    )

    print(f'解缠完成: {info["algorithm_name"]}')
    print(f'正残差点: {info["num_positive_residues"]}')
    print(f'负残差点: {info["num_negative_residues"]}')
    print(f'平均误差: {info["mean_error"]:.6f} 弧度')

    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    write_envi(unwrapped, str(output_dir / 'unwrapped_phase.dat'),
               metadata, band_names=['解缠相位'])
    print(f'结果已保存到: {output_dir / "unwrapped_phase.dat"}')


def example_2_compare_algorithms():
    """示例2: 比较不同的相位解缠算法"""
    print('\n' + '=' * 60)
    print('示例2: 比较不同相位解缠算法')
    print('=' * 60)

    test_file = Path('test_data/wrapped_phase.tif')
    if not test_file.exists():
        print('测试数据不存在，请先运行 generate_test_data.py')
        return

    wrapped_phase, metadata = read_interferogram(str(test_file))
    quality_map = QualityMapGenerator.generate(wrapped_phase, 'pseudo_coherence')
    mask = MaskProcessor.create_valid_mask(wrapped_phase)

    algorithms = [
        ('branch_cut', '分支切割法'),
        ('least_squares', '最小二乘法(无权重)'),
        ('weighted_least_squares', '最小二乘法(加权)'),
    ]

    results = {}
    for algo_key, algo_name in algorithms:
        print(f'\n执行 {algo_name}...')
        try:
            unwrapper = PhaseUnwrapper(algo_key)
            unwrapped, info = unwrapper.unwrap(
                wrapped_phase,
                mask=mask,
                quality_map=quality_map
            )
            results[algo_key] = info
            print(f'  平均误差: {info["mean_error"]:.6f}')
            print(f'  最大误差: {info["max_error"]:.6f}')
            print(f'  残差点总数: {info["num_positive_residues"] + info["num_negative_residues"]}')
        except Exception as e:
            print(f'  错误: {e}')

    if results:
        best = min(results.items(), key=lambda x: x[1]['mean_error'])
        print(f'\n最优算法: {best[1]["algorithm_name"]}')
        print(f'最小平均误差: {best[1]["mean_error"]:.6f}')


def example_3_mask_processing():
    """示例3: 掩膜处理功能"""
    print('\n' + '=' * 60)
    print('示例3: 掩膜处理功能')
    print('=' * 60)

    test_file = Path('test_data/wrapped_phase.tif')
    if not test_file.exists():
        print('测试数据不存在，请先运行 generate_test_data.py')
        return

    wrapped_phase, metadata = read_interferogram(str(test_file))
    amplitude_file = Path('test_data/amplitude.tif')

    amplitude = None
    if amplitude_file.exists():
        amplitude, _ = read_interferogram(str(amplitude_file))
        print('已加载振幅图')

    quality_map = QualityMapGenerator.generate(wrapped_phase, 'pseudo_coherence')

    print('\n自动生成综合掩膜...')
    auto_mask = AutoMaskGenerator()
    valid_mask, results = auto_mask.generate(
        wrapped_phase,
        amplitude_image=amplitude,
        coherence_map=quality_map,
        enable_water=True,
        enable_shadow=True,
        enable_low_coherence=True,
        coherence_threshold=0.3,
        dilation_radius=2
    )

    stats = MaskProcessor.get_mask_stats(valid_mask)
    print(f'掩膜统计:')
    print(f'  总像素数: {stats["total_pixels"]}')
    print(f'  有效像素: {stats["valid_pixels"]}')
    print(f'  掩膜像素: {stats["masked_pixels"]}')
    print(f'  掩膜比例: {stats["masked_ratio"]*100:.1f}%')

    print(f'\n各类掩膜区域大小:')
    print(f'  水体: {np.sum(results["water"])} 像素')
    print(f'  阴影: {np.sum(results["shadow"])} 像素')
    print(f'  低相干: {np.sum(results["low_coherence"])} 像素')

    print('\n执行带掩膜的相位解缠...')
    unwrapper = PhaseUnwrapper('weighted_least_squares')
    unwrapped, info = unwrapper.unwrap(
        wrapped_phase,
        mask=valid_mask,
        quality_map=quality_map
    )
    print(f'解缠完成，平均误差: {info["mean_error"]:.6f}')

    masked_phase = MaskProcessor.apply_mask(unwrapped, valid_mask)
    print(f'应用掩膜后有效像素: {np.sum(~np.isnan(masked_phase))}')


def example_4_quality_maps():
    """示例4: 生成不同类型的质量图"""
    print('\n' + '=' * 60)
    print('示例4: 不同类型质量图比较')
    print('=' * 60)

    test_file = Path('test_data/wrapped_phase.tif')
    if not test_file.exists():
        print('测试数据不存在，请先运行 generate_test_data.py')
        return

    wrapped_phase, metadata = read_interferogram(str(test_file))

    methods = [
        ('pseudo_coherence', '伪相关系数'),
        ('phase_derivative_variance', '相位导数方差'),
        ('max_phase_gradient', '最大相位梯度'),
    ]

    results = {}
    for method_key, method_name in methods:
        print(f'\n生成 {method_name} 质量图...')
        quality = QualityMapGenerator.generate(
            wrapped_phase,
            method=method_key,
            window_size=5
        )
        results[method_key] = quality
        print(f'  范围: [{quality.min():.4f}, {quality.max():.4f}]')
        print(f'  均值: {np.nanmean(quality):.4f}')
        print(f'  标准差: {np.nanstd(quality):.4f}')


def example_5_snaphu():
    """示例5: 使用SNAPHU进行相位解缠"""
    print('\n' + '=' * 60)
    print('示例5: SNAPHU相位解缠')
    print('=' * 60)

    test_file = Path('test_data/wrapped_phase.tif')
    if not test_file.exists():
        print('测试数据不存在，请先运行 generate_test_data.py')
        return

    wrapped_phase, metadata = read_interferogram(str(test_file))
    quality_map = QualityMapGenerator.generate(wrapped_phase, 'pseudo_coherence')
    mask = MaskProcessor.create_valid_mask(wrapped_phase)

    print('获取SNAPHU解缠器...')
    snaphu = get_snaphu_unwrapper()

    if hasattr(snaphu, 'available') and snaphu.available:
        print('SNAPHU可用，执行SNAPHU解缠...')
    else:
        print('SNAPHU不可用，使用模拟器 (加权最小二乘)...')

    try:
        unwrapped, info = snaphu.unwrap(
            wrapped_phase,
            mask=mask,
            quality_map=quality_map,
            cost_mode='DEFO'
        )

        print(f'解缠完成: {info["algorithm_name"]}')
        print(f'平均误差: {info["mean_error"]:.6f}')
        if 'note' in info:
            print(f'提示: {info["note"]}')

    except Exception as e:
        print(f'错误: {e}')


def example_6_residue_analysis():
    """示例6: 残差点分析"""
    print('\n' + '=' * 60)
    print('示例6: 残差点分析')
    print('=' * 60)

    test_file = Path('test_data/wrapped_phase.tif')
    if not test_file.exists():
        print('测试数据不存在，请先运行 generate_test_data.py')
        return

    wrapped_phase, metadata = read_interferogram(str(test_file))
    mask = MaskProcessor.create_valid_mask(wrapped_phase)

    print('检测残差点...')
    pos_res, neg_res, charge_map = detect_residues(wrapped_phase, mask)

    print(f'正残差点数量: {len(pos_res)}')
    print(f'负残差点数量: {len(neg_res)}')
    print(f'残差点总数: {len(pos_res) + len(neg_res)}')

    if len(pos_res) > 0:
        print(f'\n前5个正残差点位置:')
        for i, pos in enumerate(pos_res[:5]):
            print(f'  ({pos[0]}, {pos[1]})')

    if len(neg_res) > 0:
        print(f'\n前5个负残差点位置:')
        for i, pos in enumerate(neg_res[:5]):
            print(f'  ({pos[0]}, {pos[1]})')

    unique_charges, counts = np.unique(charge_map[charge_map != 0], return_counts=True)
    print(f'\n电荷分布:')
    for charge, count in zip(unique_charges, counts):
        print(f'  电荷 {charge}: {count} 个')

    unwrapper = PhaseUnwrapper('weighted_least_squares')
    unwrapped, info = unwrapper.unwrap(wrapped_phase, mask=mask)

    error = estimate_unwrapping_error(unwrapped, wrapped_phase, mask)
    print(f'\n解缠误差估计:')
    print(f'  平均误差: {np.nanmean(error):.6f} 弧度')
    print(f'  最大误差: {np.nanmax(error):.6f} 弧度')
    print(f'  误差标准差: {np.nanstd(error):.6f} 弧度')


def main():
    """运行所有示例"""
    print('InSAR相位解缠库 - API使用示例')
    print('=' * 60)

    try:
        example_1_basic_unwrapping()
        example_2_compare_algorithms()
        example_3_mask_processing()
        example_4_quality_maps()
        example_5_snaphu()
        example_6_residue_analysis()

        print('\n' + '=' * 60)
        print('所有示例运行完成！')
        print('=' * 60)

    except KeyboardInterrupt:
        print('\n用户中断')
    except Exception as e:
        print(f'\n运行出错: {e}')
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
