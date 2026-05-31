import numpy as np
import os
import pandas as pd
from typing import Dict, List, Tuple, Optional
import json
import time

from data_reader import FOGDataReader, load_sample_data
from wavelet_denoiser import WaveletDenoiser, ThresholdType
from allan_variance import AllanVarianceAnalyzer
from visualizer import DataVisualizer
from temperature_compensation import TemperatureCompensator, CompensationModelType
from streaming_processor import StreamingDenoiser, StreamingMode


class FOGDataProcessor:
    """
    光纤陀螺数据处理主类
    整合数据读取、去噪、Allan方差分析和可视化功能
    """

    def __init__(self, sample_rate: float = 100.0,
                 wavelet: str = 'db4',
                 level: int = 4,
                 threshold_type: ThresholdType = ThresholdType.SOFT,
                 output_dir: str = 'output'):
        """
        初始化处理器

        Args:
            sample_rate: 采样频率 (Hz)
            wavelet: 小波基名称
            level: 小波包分解层数
            threshold_type: 阈值类型
            output_dir: 输出目录
        """
        self.sample_rate = sample_rate
        self.output_dir = output_dir

        self.reader = FOGDataReader(sample_rate=sample_rate)
        self.denoiser = WaveletDenoiser(
            wavelet=wavelet, level=level, threshold_type=threshold_type
        )
        self.analyzer = AllanVarianceAnalyzer(sample_rate=sample_rate)
        self.visualizer = DataVisualizer(sample_rate=sample_rate)

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'figures'), exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'data'), exist_ok=True)

    def process_single(self, time: np.ndarray, rate_data: np.ndarray,
                       data_name: str = 'data',
                       generate_plots: bool = True,
                       save_denoised: bool = True) -> Dict:
        """
        处理单组数据

        Args:
            time: 时间数组
            rate_data: 角速率数据
            data_name: 数据名称，用于保存文件
            generate_plots: 是否生成图表
            save_denoised: 是否保存降噪后的数据

        Returns:
            处理结果字典
        """
        print(f"\n{'=' * 60}")
        print(f"处理数据: {data_name}")
        print(f"{'=' * 60}")
        print(f"数据点数: {len(rate_data)}")
        print(f"采样频率: {self.sample_rate} Hz")
        print(f"数据时长: {len(rate_data) / self.sample_rate:.2f} s")

        print("\n正在进行小波包去噪...")
        denoised_data = self.denoiser.denoise(rate_data)

        print("正在进行Allan方差分析（原始信号）...")
        allan_before = self.analyzer.analyze(rate_data)

        print("正在进行Allan方差分析（降噪信号）...")
        allan_after = self.analyzer.analyze(denoised_data)

        print("\n" + self.analyzer.format_results(allan_before))
        print("\n降噪后：")
        print(self.analyzer.format_results(allan_after))

        print("\n" + self.analyzer.compare_results(allan_before, allan_after))

        snr_before = self._calculate_snr(rate_data)
        snr_after = self._calculate_snr(denoised_data)
        print(f"\n信噪比估计: 原始 {snr_before:.2f} dB -> 降噪后 {snr_after:.2f} dB")

        data_dir = os.path.join(self.output_dir, 'data')
        if save_denoised:
            self._save_denoised_data(time, rate_data, denoised_data, data_name, data_dir)
            self._save_noise_coefficients(allan_before, allan_after, data_name, data_dir)

        if generate_plots:
            fig_dir = os.path.join(self.output_dir, 'figures')
            self._generate_plots(time, rate_data, denoised_data,
                                 allan_before, allan_after, data_name, fig_dir)

        results = {
            'data_name': data_name,
            'original_data': rate_data,
            'denoised_data': denoised_data,
            'time': time,
            'allan_before': allan_before,
            'allan_after': allan_after,
            'snr_before': snr_before,
            'snr_after': snr_after,
            'denoiser_config': {
                'wavelet': self.denoiser.wavelet,
                'level': self.denoiser.level,
                'threshold_type': self.denoiser.threshold_type.value
            }
        }

        return results

    def process_file(self, file_path: str, **kwargs) -> Optional[Dict]:
        """
        处理单个文件

        Args:
            file_path: 文件路径
            **kwargs: 传递给 process_single 的其他参数

        Returns:
            处理结果字典，失败返回None
        """
        try:
            time, rate_data = self.reader.read_file(file_path)
            data_name = os.path.splitext(os.path.basename(file_path))[0]
            return self.process_single(time, rate_data, data_name=data_name, **kwargs)
        except Exception as e:
            print(f"处理文件 {file_path} 失败: {e}")
            return None

    def process_batch(self, file_paths: List[str], **kwargs) -> List[Dict]:
        """
        批量处理多个文件

        Args:
            file_paths: 文件路径列表
            **kwargs: 传递给 process_single 的其他参数

        Returns:
            处理结果列表
        """
        results = []
        for i, file_path in enumerate(file_paths, 1):
            print(f"\n批量处理进度: {i}/{len(file_paths)}")
            result = self.process_file(file_path, **kwargs)
            if result:
                results.append(result)

        if len(results) > 1:
            self._generate_batch_summary(results)

        return results

    def process_directory(self, directory: str, recursive: bool = False,
                          extensions: List[str] = None, **kwargs) -> List[Dict]:
        """
        处理目录下的所有数据文件

        Args:
            directory: 目录路径
            recursive: 是否递归读取子目录
            extensions: 需要处理的文件扩展名列表
            **kwargs: 传递给 process_single 的其他参数

        Returns:
            处理结果列表
        """
        data_list = self.reader.read_directory(directory, extensions, recursive)

        results = []
        for i, (file_name, time, rate_data) in enumerate(data_list, 1):
            print(f"\n批量处理进度: {i}/{len(data_list)}")
            data_name = os.path.splitext(file_name)[0]
            result = self.process_single(time, rate_data, data_name=data_name, **kwargs)
            if result:
                results.append(result)

        if len(results) > 1:
            self._generate_batch_summary(results)

        return results

    def compare_wavelets(self, rate_data: np.ndarray,
                         wavelets: List[str] = None,
                         level: int = 4,
                         threshold_type: ThresholdType = ThresholdType.SOFT,
                         data_name: str = 'wavelet_comparison') -> Dict:
        """
        对比不同小波基的去噪效果

        Args:
            rate_data: 输入数据
            wavelets: 小波基列表，默认使用所有Daubechies小波
            level: 分解层数
            threshold_type: 阈值类型
            data_name: 数据名称

        Returns:
            对比结果字典
        """
        print(f"\n{'=' * 60}")
        print("小波基去噪效果对比")
        print(f"{'=' * 60}")

        comparison = WaveletDenoiser.compare_wavelets(
            rate_data, wavelets=wavelets, level=level,
            threshold_type=threshold_type
        )

        fig_dir = os.path.join(self.output_dir, 'figures')
        for metric in ['snr', 'rmse', 'smoothness']:
            self.visualizer.plot_wavelet_comparison(
                comparison, metric=metric,
                title=f"小波基去噪效果对比 - {metric.upper()}",
                save_path=os.path.join(fig_dir, f'{data_name}_{metric}_comparison.png')
            )

        print("\n小波基去噪效果排名 (按SNR):")
        sorted_wavelets = sorted(comparison.items(),
                                  key=lambda x: x[1].get('snr', 0), reverse=True)
        for i, (wavelet, res) in enumerate(sorted_wavelets, 1):
            print(f"{i}. {wavelet}: SNR={res.get('snr', 0):.2f} dB, "
                  f"RMSE={res.get('rmse', 0):.6f}, "
                  f"Smoothness={res.get('smoothness', 0):.6f}")

        return comparison

    def compare_threshold_methods(self, rate_data: np.ndarray,
                                  wavelet: str = 'db4',
                                  level: int = 4,
                                  data_name: str = 'threshold_comparison') -> Dict:
        """
        对比不同阈值方法的去噪效果

        Args:
            rate_data: 输入数据
            wavelet: 小波基
            level: 分解层数
            data_name: 数据名称

        Returns:
            对比结果字典
        """
        print(f"\n{'=' * 60}")
        print("阈值去噪方法对比")
        print(f"{'=' * 60}")

        methods = [
            (ThresholdType.SOFT, '软阈值'),
            (ThresholdType.HARD, '硬阈值'),
            (ThresholdType.SURE, 'SURE阈值')
        ]

        results = {}
        denoised_signals = {'原始信号': rate_data}

        for threshold_type, name in methods:
            denoiser = WaveletDenoiser(
                wavelet=wavelet, level=level, threshold_type=threshold_type
            )
            denoised = denoiser.denoise(rate_data)
            snr = WaveletDenoiser._calculate_snr(rate_data, denoised)
            rmse = WaveletDenoiser._calculate_rmse(rate_data, denoised)
            smoothness = WaveletDenoiser._calculate_smoothness(denoised)

            results[name] = {
                'denoised': denoised,
                'snr': snr,
                'rmse': rmse,
                'smoothness': smoothness
            }
            denoised_signals[name] = denoised
            print(f"{name}: SNR={snr:.2f} dB, RMSE={rmse:.6f}, Smoothness={smoothness:.6f}")

        time = np.arange(len(rate_data)) / self.sample_rate
        fig_dir = os.path.join(self.output_dir, 'figures')

        self.visualizer.plot_time_series(
            time, denoised_signals,
            title="不同阈值方法去噪效果对比",
            save_path=os.path.join(fig_dir, f'{data_name}_time_series.png')
        )

        self.visualizer.plot_spectrum(
            denoised_signals,
            title="不同阈值方法频谱对比",
            save_path=os.path.join(fig_dir, f'{data_name}_spectrum.png')
        )

        return results

    def _generate_plots(self, time: np.ndarray, original: np.ndarray,
                        denoised: np.ndarray, allan_before: Dict, allan_after: Dict,
                        data_name: str, fig_dir: str):
        """生成所有分析图表"""
        signals = {'原始信号': original, '降噪信号': denoised}

        self.visualizer.plot_time_series(
            time, signals,
            title=f"{data_name} - 时域信号对比",
            save_path=os.path.join(fig_dir, f'{data_name}_time_series.png')
        )

        self.visualizer.plot_spectrum(
            signals,
            title=f"{data_name} - 频谱对比",
            save_path=os.path.join(fig_dir, f'{data_name}_spectrum.png')
        )

        self.visualizer.plot_psd(
            signals,
            title=f"{data_name} - 功率谱密度对比",
            save_path=os.path.join(fig_dir, f'{data_name}_psd.png')
        )

        self.visualizer.plot_allan_variance(
            {'原始信号': allan_before, '降噪信号': allan_after},
            title=f"{data_name} - Allan 方差对比",
            save_path=os.path.join(fig_dir, f'{data_name}_allan_variance.png')
        )

        self.visualizer.plot_noise_coefficients_bar(
            allan_before, allan_after,
            title=f"{data_name} - 降噪前后噪声系数对比",
            save_path=os.path.join(fig_dir, f'{data_name}_noise_coefficients.png')
        )

        self.visualizer.plot_comprehensive(
            time, original, denoised, allan_before, allan_after,
            title_prefix=f"{data_name}_",
            save_dir=fig_dir
        )

        nodes = self.denoiser.wpd_decompose(original)
        self.visualizer.plot_wavelet_coefficients(
            nodes, self.denoiser.level,
            title=f"{data_name} - 小波包分解系数",
            save_path=os.path.join(fig_dir, f'{data_name}_wavelet_coefficients.png')
        )

    def _save_denoised_data(self, time: np.ndarray, original: np.ndarray,
                            denoised: np.ndarray, data_name: str, data_dir: str):
        """保存降噪后的数据"""
        output_file = os.path.join(data_dir, f'{data_name}_denoised.csv')
        df = pd.DataFrame({
            '时间(s)': time,
            '原始信号': original,
            '降噪信号': denoised,
            '噪声': original - denoised
        })
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n降噪数据已保存到: {output_file}")

        np.savez(os.path.join(data_dir, f'{data_name}_denoised.npz'),
                 time=time, original=original, denoised=denoised)

    def _save_noise_coefficients(self, before: Dict, after: Dict,
                                  data_name: str, data_dir: str):
        """保存噪声系数"""
        output_file = os.path.join(data_dir, f'{data_name}_noise_coefficients.csv')

        params = [
            ('quantization_noise', '量化噪声'),
            ('angle_random_walk', '角度随机游走'),
            ('bias_instability', '零偏不稳定性'),
            ('rate_random_walk', '速率随机游走'),
            ('rate_ramp', '速率斜坡')
        ]

        data = []
        for key, name in params:
            b = before.get(key, 0)
            a = after.get(key, 0)
            change = (a - b) / b * 100 if b != 0 else 0
            data.append({
                '噪声类型': name,
                '降噪前': b,
                '降噪后': a,
                '变化率(%)': change
            })

        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"噪声系数已保存到: {output_file}")

    def _generate_batch_summary(self, results: List[Dict]):
        """生成批量处理汇总报告"""
        summary_file = os.path.join(self.output_dir, 'data', 'batch_summary.csv')

        data = []
        for result in results:
            row = {
                '数据名称': result['data_name'],
                'SNR_前(dB)': result['snr_before'],
                'SNR_后(dB)': result['snr_after'],
                'SNR提升(dB)': result['snr_after'] - result['snr_before']
            }
            for key, name in [
                ('quantization_noise', '量化噪声'),
                ('angle_random_walk', '角度随机游走'),
                ('bias_instability', '零偏不稳定性'),
                ('rate_random_walk', '速率随机游走'),
                ('rate_ramp', '速率斜坡')
            ]:
                b = result['allan_before'].get(key, 0)
                a = result['allan_after'].get(key, 0)
                row[f'{name}_前'] = b
                row[f'{name}_后'] = a
                row[f'{name}_变化率(%)'] = (a - b) / b * 100 if b != 0 else 0

            data.append(row)

        df = pd.DataFrame(data)
        df.to_csv(summary_file, index=False, encoding='utf-8-sig')

        json_file = os.path.join(self.output_dir, 'data', 'batch_summary.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'num_files': len(results),
                'avg_snr_improvement': float(np.mean([r['snr_after'] - r['snr_before'] for r in results])),
                'results': [{
                    'data_name': r['data_name'],
                    'snr_before': float(r['snr_before']),
                    'snr_after': float(r['snr_after']),
                    'noise_coefficients': {
                        'before': {k: float(r['allan_before'].get(k, 0)) for k in
                                  ['quantization_noise', 'angle_random_walk', 'bias_instability',
                                   'rate_random_walk', 'rate_ramp']},
                        'after': {k: float(r['allan_after'].get(k, 0)) for k in
                                 ['quantization_noise', 'angle_random_walk', 'bias_instability',
                                  'rate_random_walk', 'rate_ramp']}
                    }
                } for r in results]
            }, f, ensure_ascii=False, indent=2)

        print(f"\n批量处理汇总已保存到: {summary_file}")

    def adaptive_wavelet_selection(self, rate_data: np.ndarray,
                                    criterion: str = 'shannon',
                                    wavelet_list: List[str] = None,
                                    data_name: str = 'adaptive_selection') -> Dict:
        """
        自适应小波包基选择（基于熵准则）

        Args:
            rate_data: 输入角速率数据
            criterion: 熵准则: 'shannon', 'threshold', 'log_energy'
            wavelet_list: 候选小波基列表，默认使用Daubechies家族
            data_name: 数据名称，用于保存结果

        Returns:
            包含最优小波基信息的字典
        """
        print(f"\n{'=' * 60}")
        print(f"自适应小波基选择 - {data_name}")
        print(f"{'=' * 60}")

        result = self.denoiser.adaptive_wavelet_selection(
            rate_data,
            wavelet_list=wavelet_list,
            criterion=criterion,
            level=self.denoiser.level,
            return_all=True
        )

        best_wavelet = result['best_wavelet']
        best_result = result['best_result']

        print(f"\n最优小波基已设置为: {best_wavelet}")
        print(f"熵值: {best_result['entropy']:.4f}")
        print(f"SNR: {best_result['snr']:.2f} dB")

        if 'all_results' in result:
            fig_dir = os.path.join(self.output_dir, 'figures')
            for metric in ['snr', 'entropy']:
                self.visualizer.plot_wavelet_comparison(
                    result['all_results'], metric=metric,
                    title=f"小波基对比 - {metric.upper()} ({criterion}准则)",
                    save_path=os.path.join(fig_dir, f'{data_name}_wavelet_{metric}_{criterion}.png')
                )

            comparison_df = pd.DataFrame([
                {
                    '小波基': w,
                    '熵值': res.get('entropy', 0),
                    'SNR(dB)': res.get('snr', 0),
                    'RMSE': res.get('rmse', 0)
                }
                for w, res in result['all_results'].items()
            ])
            comparison_df.to_csv(
                os.path.join(self.output_dir, 'data', f'{data_name}_wavelet_comparison.csv'),
                index=False, encoding='utf-8-sig'
            )

        return result

    def temperature_compensation(self, temperature: np.ndarray, rate_data: np.ndarray,
                                  model_type: CompensationModelType = CompensationModelType.POLYNOMIAL,
                                  compare_models: bool = False,
                                  data_name: str = 'temp_compensation',
                                  **kwargs) -> Dict:
        """
        陀螺温度补偿（去除温度与噪声的耦合）

        Args:
            temperature: 温度数据 (°C)
            rate_data: 角速率数据
            model_type: 补偿模型类型
            compare_models: 是否对比所有模型
            data_name: 数据名称
            **kwargs: 模型训练参数

        Returns:
            补偿结果字典
        """
        print(f"\n{'=' * 60}")
        print(f"温度补偿 - {data_name}")
        print(f"{'=' * 60}")

        if compare_models:
            results = TemperatureCompensator.compare_models(
                temperature, rate_data, plot=True, **kwargs
            )

            best_name = max(results.keys(),
                           key=lambda k: results[k]['eval_result']['std_reduction_percent'])
            best_compensator = results[best_name]['compensator']
            compensated = results[best_name]['eval_result']['compensated']

            print(f"\n最优模型: {best_name}")
            print(f"标准差降低: {results[best_name]['eval_result']['std_reduction_percent']:.2f}%")
        else:
            compensator = TemperatureCompensator(model_type=model_type)
            fit_result = compensator.fit(temperature, rate_data, **kwargs)
            eval_result = compensator.evaluate(temperature, rate_data)
            compensated = eval_result['compensated']

            results = {
                'compensator': compensator,
                'fit_result': fit_result,
                'eval_result': eval_result,
                'compensated': compensated,
                'drift': eval_result['drift']
            }
            best_compensator = compensator

        data_dir = os.path.join(self.output_dir, 'data')
        time = np.arange(len(rate_data)) / self.sample_rate

        compensation_df = pd.DataFrame({
            '时间(s)': time,
            '温度(°C)': temperature,
            '原始角速率': rate_data,
            '补偿后角速率': compensated,
            '漂移': rate_data - compensated
        })
        compensation_df.to_csv(
            os.path.join(data_dir, f'{data_name}_temperature_compensation.csv'),
            index=False, encoding='utf-8-sig'
        )

        return {
            'results': results,
            'compensated_data': compensated,
            'best_compensator': best_compensator if compare_models else None
        }

    def stream_denoise_offline(self, rate_data: np.ndarray,
                                mode: StreamingMode = StreamingMode.OVERLAP_ADD,
                                window_size: int = 1024,
                                overlap: float = 0.5,
                                compare_modes: bool = False,
                                data_name: str = 'streaming') -> Dict:
        """
        流式实时降噪（离线模拟流式处理）

        Args:
            rate_data: 输入角速率数据
            mode: 流式处理模式
            window_size: 窗口大小
            overlap: 重叠比例
            compare_modes: 是否对比所有模式
            data_name: 数据名称

        Returns:
            流式处理结果字典
        """
        print(f"\n{'=' * 60}")
        print(f"流式实时降噪 - {data_name}")
        print(f"{'=' * 60}")
        print(f"处理模式: {mode.value}")
        print(f"窗口大小: {window_size}")
        print(f"重叠比例: {overlap * 100:.1f}%")

        if compare_modes:
            results = StreamingDenoiser.compare_modes(
                rate_data,
                wavelet=self.denoiser.wavelet,
                level=self.denoiser.level,
                window_size=window_size,
                overlap=overlap
            )

            best_name = max(results.keys(),
                           key=lambda k: results[k]['snr'])
            denoised = results[best_name]['denoised']
            stats = results[best_name]['stats']

            print(f"\n最优模式: {best_name}")
            print(f"SNR: {results[best_name]['snr']:.2f} dB")
            print(f"延迟: {stats['latency_samples']} 样本")
        else:
            processor = StreamingDenoiser(
                window_size=window_size,
                overlap=overlap,
                wavelet=self.denoiser.wavelet,
                level=self.denoiser.level,
                threshold_type=self.denoiser.threshold_type,
                mode=mode
            )

            start_time = time.time()
            denoised = processor.process_offline(rate_data, verbose=True)
            elapsed = time.time() - start_time
            stats = processor.get_stats()

            print(f"\n处理完成！")
            print(f"总耗时: {elapsed:.3f} s")
            print(f"吞吐量: {len(rate_data) / elapsed:.1f} 样本/秒")

            results = {'denoised': denoised, 'stats': stats}

        data_dir = os.path.join(self.output_dir, 'data')
        time_axis = np.arange(len(rate_data)) / self.sample_rate

        stream_df = pd.DataFrame({
            '时间(s)': time_axis,
            '原始信号': rate_data,
            '降噪信号': denoised
        })
        stream_df.to_csv(
            os.path.join(data_dir, f'{data_name}_streaming_denoised.csv'),
            index=False, encoding='utf-8-sig'
        )

        return {
            'denoised_data': denoised,
            'stats': stats,
            'all_results': results if compare_modes else None
        }

    @staticmethod
    def _calculate_snr(signal: np.ndarray) -> float:
        """估计信号信噪比"""
        signal_power = np.mean(signal ** 2)
        noise = np.diff(signal)
        noise_power = np.mean(noise ** 2) / 2
        if noise_power == 0:
            return float('inf')
        return 10 * np.log10(signal_power / noise_power)
