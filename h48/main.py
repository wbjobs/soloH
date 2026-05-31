import argparse
import os
import sys
from data_reader import load_sample_data
from fog_processor import FOGDataProcessor
from wavelet_denoiser import ThresholdType


def run_single_demo():
    """运行单组数据处理演示"""
    print("\n" + "=" * 60)
    print("模式1: 单组数据处理演示（使用模拟数据）")
    print("=" * 60)

    t, rate_data = load_sample_data(duration=100, sample_rate=100, noise_level=1.0)

    processor = FOGDataProcessor(
        sample_rate=100.0,
        wavelet='db4',
        level=4,
        threshold_type=ThresholdType.SOFT,
        output_dir='output_demo'
    )

    results = processor.process_single(
        t, rate_data,
        data_name='demo_single',
        generate_plots=True,
        save_denoised=True
    )

    print("\n" + "=" * 60)
    print("单组数据处理完成！")
    print(f"处理结果保存在: {processor.output_dir}")
    print("=" * 60)

    return results


def run_batch_demo():
    """运行批量数据处理演示"""
    print("\n" + "=" * 60)
    print("模式2: 批量数据处理演示")
    print("=" * 60)

    sample_data_dir = 'sample_data'

    if not os.path.exists(sample_data_dir):
        print(f"\n示例数据目录 {sample_data_dir} 不存在")
        print("正在生成示例数据...")
        from generate_sample_data import generate_multiple_samples
        generate_multiple_samples(output_dir=sample_data_dir, num_files=3)

    processor = FOGDataProcessor(
        sample_rate=100.0,
        wavelet='db4',
        level=4,
        threshold_type=ThresholdType.SOFT,
        output_dir='output_batch'
    )

    print(f"\n开始处理目录 {sample_data_dir} 中的数据...")
    results = processor.process_directory(
        sample_data_dir,
        recursive=False,
        extensions=['.csv', '.txt'],
        generate_plots=True,
        save_denoised=True
    )

    print("\n" + "=" * 60)
    print(f"批量处理完成！共处理 {len(results)} 组数据")
    print(f"处理结果保存在: {processor.output_dir}")
    print("=" * 60)

    return results


def run_wavelet_comparison():
    """运行小波基对比演示"""
    print("\n" + "=" * 60)
    print("模式3: 不同小波基去噪效果对比")
    print("=" * 60)

    t, rate_data = load_sample_data(duration=100, sample_rate=100, noise_level=1.0)

    processor = FOGDataProcessor(
        sample_rate=100.0,
        output_dir='output_wavelet_compare'
    )

    wavelets = ['db1', 'db2', 'db3', 'db4', 'db5', 'db6', 'db7', 'db8']

    comparison = processor.compare_wavelets(
        rate_data,
        wavelets=wavelets,
        level=4,
        threshold_type=ThresholdType.SOFT,
        data_name='demo'
    )

    print("\n" + "=" * 60)
    print("小波基对比完成！")
    print(f"对比图表保存在: {processor.output_dir}/figures")
    print("=" * 60)

    return comparison


def run_threshold_comparison():
    """运行阈值方法对比演示"""
    print("\n" + "=" * 60)
    print("模式4: 不同阈值去噪方法对比")
    print("=" * 60)

    t, rate_data = load_sample_data(duration=100, sample_rate=100, noise_level=1.0)

    processor = FOGDataProcessor(
        sample_rate=100.0,
        output_dir='output_threshold_compare'
    )

    comparison = processor.compare_threshold_methods(
        rate_data,
        wavelet='db4',
        level=4,
        data_name='demo'
    )

    print("\n" + "=" * 60)
    print("阈值方法对比完成！")
    print(f"对比图表保存在: {processor.output_dir}/figures")
    print("=" * 60)

    return comparison


def run_process_file(file_path: str, wavelet: str, level: int,
                     threshold_type: str, sample_rate: float):
    """处理指定的单个文件"""
    print(f"\n处理文件: {file_path}")

    threshold_map = {
        'soft': ThresholdType.SOFT,
        'hard': ThresholdType.HARD,
        'sure': ThresholdType.SURE
    }
    th_type = threshold_map.get(threshold_type.lower(), ThresholdType.SOFT)

    processor = FOGDataProcessor(
        sample_rate=sample_rate,
        wavelet=wavelet,
        level=level,
        threshold_type=th_type,
        output_dir='output_file'
    )

    results = processor.process_file(file_path)

    if results:
        print(f"\n处理完成！结果保存在: {processor.output_dir}")
    else:
        print("处理失败！")

    return results


def run_process_directory(directory: str, wavelet: str, level: int,
                          threshold_type: str, sample_rate: float):
    """处理指定目录下的所有文件"""
    print(f"\n处理目录: {directory}")

    threshold_map = {
        'soft': ThresholdType.SOFT,
        'hard': ThresholdType.HARD,
        'sure': ThresholdType.SURE
    }
    th_type = threshold_map.get(threshold_type.lower(), ThresholdType.SOFT)

    processor = FOGDataProcessor(
        sample_rate=sample_rate,
        wavelet=wavelet,
        level=level,
        threshold_type=th_type,
        output_dir='output_directory'
    )

    results = processor.process_directory(
        directory,
        recursive=False,
        extensions=['.csv', '.txt', '.xlsx', '.dat']
    )

    print(f"\n处理完成！共处理 {len(results)} 组数据")
    print(f"结果保存在: {processor.output_dir}")

    return results


def print_menu():
    """打印主菜单"""
    print("\n" + "=" * 60)
    print("光纤陀螺数据处理系统")
    print("=" * 60)
    print("1. 单组数据处理演示（使用模拟数据）")
    print("2. 批量数据处理演示（使用示例数据）")
    print("3. 不同小波基去噪效果对比")
    print("4. 不同阈值去噪方法对比")
    print("5. 处理指定文件")
    print("6. 处理指定目录下的所有文件")
    print("7. 运行所有演示")
    print("0. 退出")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='光纤陀螺数据处理系统')
    parser.add_argument('--mode', type=int, default=None,
                        help='运行模式 (1-7, 0=退出)')
    parser.add_argument('--file', type=str, default=None,
                        help='要处理的文件路径 (模式5)')
    parser.add_argument('--dir', type=str, default=None,
                        help='要处理的目录路径 (模式6)')
    parser.add_argument('--wavelet', type=str, default='db4',
                        help='小波基 (默认: db4)')
    parser.add_argument('--level', type=int, default=4,
                        help='小波包分解层数 (默认: 4)')
    parser.add_argument('--threshold', type=str, default='soft',
                        help='阈值类型: soft, hard, sure (默认: soft)')
    parser.add_argument('--sample-rate', type=float, default=100.0,
                        help='采样频率 Hz (默认: 100.0)')

    args = parser.parse_args()

    if args.mode is not None:
        mode = args.mode
    else:
        print_menu()
        mode = int(input("请选择运行模式 (0-7): "))

    while mode != 0:
        if mode == 1:
            run_single_demo()
        elif mode == 2:
            run_batch_demo()
        elif mode == 3:
            run_wavelet_comparison()
        elif mode == 4:
            run_threshold_comparison()
        elif mode == 5:
            file_path = args.file if args.file else input("请输入文件路径: ")
            if os.path.exists(file_path):
                run_process_file(file_path, args.wavelet, args.level,
                                 args.threshold, args.sample_rate)
            else:
                print(f"错误: 文件不存在: {file_path}")
        elif mode == 6:
            directory = args.dir if args.dir else input("请输入目录路径: ")
            if os.path.isdir(directory):
                run_process_directory(directory, args.wavelet, args.level,
                                      args.threshold, args.sample_rate)
            else:
                print(f"错误: 目录不存在: {directory}")
        elif mode == 7:
            print("\n" + "=" * 60)
            print("运行所有演示模式")
            print("=" * 60)
            run_single_demo()
            run_batch_demo()
            run_wavelet_comparison()
            run_threshold_comparison()
            print("\n所有演示完成！")
        else:
            print("无效的模式选择，请重新输入！")

        if args.mode is not None:
            break

        print_menu()
        mode = int(input("请选择运行模式 (0-7): "))

    print("\n感谢使用光纤陀螺数据处理系统！")


if __name__ == '__main__':
    main()
