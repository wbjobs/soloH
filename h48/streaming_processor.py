import numpy as np
from typing import Optional, Dict, List, Callable, Tuple
from collections import deque
from enum import Enum
import time

from wavelet_denoiser import WaveletDenoiser, ThresholdType


class StreamingMode(Enum):
    """流式处理模式"""
    SLIDING_WINDOW = 'sliding_window'
    OVERLAP_ADD = 'overlap_add'
    ONLINE_UPDATE = 'online_update'


class StreamingDenoiser:
    """
    流式实时降噪处理器

    实现三种流式处理模式：
    1. 滑动窗口模式 (Sliding Window)
    2. 重叠相加模式 (Overlap-Add)
    3. 在线更新模式 (Online Update)

    支持实时数据接入、延迟控制、吞吐量统计等功能
    """

    def __init__(self,
                 window_size: int = 1024,
                 overlap: float = 0.5,
                 wavelet: str = 'db4',
                 level: int = 4,
                 threshold_type: ThresholdType = ThresholdType.SOFT,
                 mode: StreamingMode = StreamingMode.OVERLAP_ADD,
                 adaptive_wavelet: bool = False):
        """
        初始化流式降噪器

        Args:
            window_size: 窗口大小（采样点数）
            overlap: 重叠比例 (0-1)，默认50%重叠
            wavelet: 小波基名称
            level: 分解层数
            threshold_type: 阈值类型
            mode: 流式处理模式
            adaptive_wavelet: 是否启用自适应小波基选择
        """
        if not (0 <= overlap < 1):
            raise ValueError("重叠比例必须在 [0, 1) 范围内")

        self.window_size = window_size
        self.overlap = overlap
        self.step_size = int(window_size * (1 - overlap))
        self.mode = mode
        self.adaptive_wavelet = adaptive_wavelet

        self.denoiser = WaveletDenoiser(
            wavelet=wavelet,
            level=level,
            threshold_type=threshold_type
        )

        self._input_buffer = deque(maxlen=window_size * 2)
        self._output_buffer = []
        self._overlap_buffer = np.zeros(window_size)

        self._window_count = 0
        self._total_samples_processed = 0
        self._processing_times = []

        self._is_initialized = False
        self._first_window = True

        self._input_callback: Optional[Callable] = None
        self._output_callback: Optional[Callable] = None

        self._stats = {
            'total_samples_in': 0,
            'total_samples_out': 0,
            'avg_processing_time': 0.0,
            'max_processing_time': 0.0,
            'min_processing_time': float('inf'),
            'throughput': 0.0
        }

    def set_callbacks(self,
                      input_callback: Optional[Callable] = None,
                      output_callback: Optional[Callable] = None):
        """
        设置回调函数

        Args:
            input_callback: 数据输入回调，函数签名: (samples) -> None
            output_callback: 结果输出回调，函数签名: (denoised_samples, metadata) -> None
        """
        self._input_callback = input_callback
        self._output_callback = output_callback

    def feed(self, samples: np.ndarray) -> int:
        """
        输入新的数据样本

        Args:
            samples: 新的样本数据

        Returns:
            缓冲区内当前样本数
        """
        samples = np.asarray(samples, dtype=np.float64)

        if self._input_callback is not None:
            self._input_callback(samples)

        self._input_buffer.extend(samples)
        self._stats['total_samples_in'] += len(samples)

        return len(self._input_buffer)

    def process(self) -> Optional[np.ndarray]:
        """
        处理缓冲区中的数据

        Returns:
            去噪后的输出数据，如果缓冲区数据不足则返回None
        """
        if len(self._input_buffer) < self.window_size:
            return None

        if self.mode == StreamingMode.SLIDING_WINDOW:
            output = self._process_sliding_window()
        elif self.mode == StreamingMode.OVERLAP_ADD:
            output = self._process_overlap_add()
        elif self.mode == StreamingMode.ONLINE_UPDATE:
            output = self._process_online_update()
        else:
            raise ValueError(f"不支持的处理模式: {self.mode}")

        return output

    def _process_sliding_window(self) -> Optional[np.ndarray]:
        """
        滑动窗口模式处理

        每次处理一个完整窗口，输出一个窗口的去噪结果
        """
        if len(self._input_buffer) < self.window_size:
            return None

        window_data = np.array(list(self._input_buffer))[:self.window_size]

        if self.adaptive_wavelet and self._first_window:
            self._perform_adaptive_selection(window_data)

        start_time = time.perf_counter()

        if self._first_window:
            self._precompute_wavelet_params(window_data)

        denoised_window = self.denoiser.denoise(window_data)

        processing_time = time.perf_counter() - start_time
        self._update_stats(processing_time, self.window_size)

        for _ in range(self.step_size):
            if self._input_buffer:
                self._input_buffer.popleft()

        self._first_window = False
        self._window_count += 1

        if self._window_count == 1:
            output = denoised_window[:self.step_size].copy()
        else:
            output = denoised_window[self.window_size - self.step_size:].copy()

        self._stats['total_samples_out'] += len(output)

        if self._output_callback is not None:
            metadata = {
                'window_index': self._window_count,
                'processing_time': processing_time,
                'mode': 'sliding_window'
            }
            self._output_callback(denoised_window, metadata)

        return output

    def _process_overlap_add(self) -> Optional[np.ndarray]:
        """
        重叠相加模式处理 (Overlap-Add)

        处理重叠窗口，通过加权叠加消除边界效应，
        输出连续的数据流，延迟 = window_size * (1 - overlap)
        """
        if len(self._input_buffer) < self.window_size:
            return None

        window_data = np.array(list(self._input_buffer))[:self.window_size]

        if self.adaptive_wavelet and self._first_window:
            self._perform_adaptive_selection(window_data)

        start_time = time.perf_counter()

        if self._first_window:
            self._precompute_wavelet_params(window_data)

        window = np.hanning(self.window_size)
        windowed_data = window_data * window

        denoised_window = self.denoiser.denoise(windowed_data)

        processing_time = time.perf_counter() - start_time
        self._update_stats(processing_time, self.window_size)

        output_len = self.step_size

        if self._first_window:
            self._overlap_buffer[:self.window_size] = denoised_window
            self._first_window = False
            output = None
        else:
            self._overlap_buffer[:self.window_size] += denoised_window
            output = self._overlap_buffer[:output_len].copy()
            self._overlap_buffer = np.roll(self._overlap_buffer, -output_len)
            self._overlap_buffer[-output_len:] = 0
            self._stats['total_samples_out'] += len(output)

        for _ in range(self.step_size):
            if self._input_buffer:
                self._input_buffer.popleft()

        self._window_count += 1

        if output is not None and self._output_callback is not None:
            metadata = {
                'window_index': self._window_count,
                'processing_time': processing_time,
                'mode': 'overlap_add'
            }
            self._output_callback(output, metadata)

        return output

    def _process_online_update(self) -> Optional[np.ndarray]:
        """
        在线更新模式处理

        针对每个新样本进行实时处理，使用递归更新策略，
        延迟最低（样本级延迟），适合真正时应用
        """
        if len(self._input_buffer) < self.window_size:
            return None

        outputs = []

        while len(self._input_buffer) >= self.window_size:
            window_data = np.array(list(self._input_buffer))[:self.window_size]

            if self.adaptive_wavelet and self._first_window:
                self._perform_adaptive_selection(window_data)
                self._precompute_wavelet_params(window_data)

            start_time = time.perf_counter()

            denoised_window = self.denoiser.denoise(window_data)

            processing_time = time.perf_counter() - start_time
            self._update_stats(processing_time, 1)

            output_sample = denoised_window[self.step_size - 1]
            outputs.append(output_sample)

            for _ in range(self.step_size):
                if self._input_buffer:
                    self._input_buffer.popleft()

            self._first_window = False
            self._window_count += 1
            self._stats['total_samples_out'] += 1

        if outputs:
            output_array = np.array(outputs)

            if self._output_callback is not None:
                metadata = {
                    'window_index': self._window_count,
                    'processing_time': processing_time,
                    'mode': 'online_update',
                    'num_samples': len(output_array)
                }
                self._output_callback(output_array, metadata)

            return output_array

        return None

    def _perform_adaptive_selection(self, data: np.ndarray):
        """执行自适应小波基选择"""
        print("\n执行自适应小波基选择...")
        result = self.denoiser.adaptive_wavelet_selection(
            data, criterion='shannon', level=self.denoiser.level
        )
        print(f"自适应选择的小波基: {result['best_wavelet']}\n")

    def _precompute_wavelet_params(self, data: np.ndarray):
        """预计算小波分解参数"""
        self.denoiser.wpd_decompose(data)

    def _update_stats(self, processing_time: float, samples_processed: int):
        """更新处理统计信息"""
        self._processing_times.append(processing_time)
        self._total_samples_processed += samples_processed

        if len(self._processing_times) > 1000:
            self._processing_times = self._processing_times[-1000:]

        self._stats['avg_processing_time'] = np.mean(self._processing_times)
        self._stats['max_processing_time'] = max(self._stats['max_processing_time'], processing_time)
        self._stats['min_processing_time'] = min(self._stats['min_processing_time'], processing_time)

        total_time = sum(self._processing_times)
        if total_time > 0:
            self._stats['throughput'] = self._total_samples_processed / total_time

    def flush(self) -> Optional[np.ndarray]:
        """
        刷新缓冲区，处理剩余数据

        Returns:
            剩余数据的去噪结果
        """
        if len(self._input_buffer) == 0:
            return None

        remaining = np.array(list(self._input_buffer))
        pad_len = self.window_size - len(remaining)

        if pad_len > 0:
            remaining = np.pad(remaining, (0, pad_len), mode='symmetric')

        denoised = self.denoiser.denoise(remaining)
        output = denoised[:len(remaining) - pad_len] if pad_len > 0 else denoised

        self._input_buffer.clear()
        self._stats['total_samples_out'] += len(output)

        if self._output_callback is not None:
            metadata = {
                'window_index': self._window_count + 1,
                'processing_time': 0.0,
                'mode': 'flush',
                'note': '缓冲区刷新'
            }
            self._output_callback(output, metadata)

        return output

    def get_stats(self) -> Dict:
        """
        获取处理统计信息

        Returns:
            统计信息字典
        """
        stats = self._stats.copy()
        stats.update({
            'window_count': self._window_count,
            'buffer_size': len(self._input_buffer),
            'mode': self.mode.value,
            'window_size': self.window_size,
            'overlap': self.overlap,
            'step_size': self.step_size,
            'current_wavelet': self.denoiser.wavelet,
            'decomposition_level': self.denoiser.level,
            'threshold_type': self.denoiser.threshold_type.value,
            'latency_samples': self._get_latency(),
            'latency_seconds': self._get_latency() / 100.0
        })
        return stats

    def _get_latency(self) -> int:
        """获取处理延迟（样本数）"""
        if self.mode == StreamingMode.ONLINE_UPDATE:
            return self.step_size
        elif self.mode == StreamingMode.OVERLAP_ADD:
            return self.window_size - self.step_size
        elif self.mode == StreamingMode.SLIDING_WINDOW:
            return self.window_size
        else:
            return self.window_size

    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        print("\n" + "=" * 60)
        print("流式降噪处理器统计")
        print("=" * 60)
        print(f"处理模式: {stats['mode']}")
        print(f"窗口大小: {stats['window_size']} 样本")
        print(f"重叠比例: {stats['overlap'] * 100:.1f}%")
        print(f"步长: {stats['step_size']} 样本")
        print(f"当前小波基: {stats['current_wavelet']}")
        print(f"分解层数: {stats['decomposition_level']}")
        print(f"阈值类型: {stats['threshold_type']}")
        print("-" * 60)
        print(f"已处理窗口数: {stats['window_count']}")
        print(f"输入样本总数: {stats['total_samples_in']}")
        print(f"输出样本总数: {stats['total_samples_out']}")
        print("-" * 60)
        print(f"平均处理时间: {stats['avg_processing_time'] * 1000:.3f} ms")
        print(f"最大处理时间: {stats['max_processing_time'] * 1000:.3f} ms")
        print(f"最小处理时间: {stats['min_processing_time'] * 1000:.3f} ms")
        print(f"吞吐量: {stats['throughput']:.1f} 样本/秒")
        print(f"处理延迟: {stats['latency_samples']} 样本 ({stats['latency_seconds'] * 1000:.1f} ms @ 100Hz)")
        print("=" * 60)

    def process_offline(self, data: np.ndarray,
                         verbose: bool = True) -> np.ndarray:
        """
        离线处理完整数据（模拟流式处理）

        Args:
            data: 完整的输入数据
            verbose: 是否打印进度

        Returns:
            去噪后的完整数据
        """
        self.reset()

        denoised = []
        chunk_size = max(1, self.step_size // 4)

        total_samples = len(data)
        processed = 0

        for i in range(0, total_samples, chunk_size):
            chunk = data[i:i + chunk_size]
            self.feed(chunk)

            while True:
                output = self.process()
                if output is None:
                    break
                denoised.extend(output)
                processed += len(output)

                if verbose and processed % (total_samples // 10) == 0:
                    progress = processed / total_samples * 100
                    print(f"处理进度: {progress:.1f}% ({processed}/{total_samples})")

        remaining = self.flush()
        if remaining is not None and len(remaining) > 0:
            denoised.extend(remaining)

        denoised_array = np.array(denoised)

        if len(denoised_array) > len(data):
            denoised_array = denoised_array[:len(data)]
        elif len(denoised_array) < len(data):
            denoised_array = np.pad(denoised_array,
                                    (0, len(data) - len(denoised_array)),
                                    mode='edge')

        if verbose:
            self.print_stats()

        return denoised_array

    def reset(self):
        """重置处理器状态"""
        self._input_buffer.clear()
        self._output_buffer = []
        self._overlap_buffer = np.zeros(self.window_size)
        self._window_count = 0
        self._total_samples_processed = 0
        self._processing_times = []
        self._is_initialized = False
        self._first_window = True
        self._stats = {
            'total_samples_in': 0,
            'total_samples_out': 0,
            'avg_processing_time': 0.0,
            'max_processing_time': 0.0,
            'min_processing_time': float('inf'),
            'throughput': 0.0
        }

    @staticmethod
    def compare_modes(data: np.ndarray,
                      wavelet: str = 'db4',
                      level: int = 4,
                      window_size: int = 1024,
                      overlap: float = 0.5) -> Dict:
        """
        对比不同流式处理模式的性能

        Args:
            data: 测试数据
            wavelet: 小波基
            level: 分解层数
            window_size: 窗口大小
            overlap: 重叠比例

        Returns:
            各模式的性能对比结果
        """
        modes = [
            (StreamingMode.SLIDING_WINDOW, '滑动窗口'),
            (StreamingMode.OVERLAP_ADD, '重叠相加'),
            (StreamingMode.ONLINE_UPDATE, '在线更新')
        ]

        results = {}

        for mode, name in modes:
            print(f"\n{'=' * 60}")
            print(f"模式: {name}")
            print("=" * 60)

            processor = StreamingDenoiser(
                window_size=window_size,
                overlap=overlap,
                wavelet=wavelet,
                level=level,
                mode=mode
            )

            start_time = time.perf_counter()
            denoised = processor.process_offline(data, verbose=False)
            total_time = time.perf_counter() - start_time

            stats = processor.get_stats()

            noise = data - denoised
            snr = 10 * np.log10(np.sum(data ** 2) / (np.sum(noise ** 2) + 1e-20))
            rmse = np.sqrt(np.mean(noise ** 2))

            results[name] = {
                'denoised': denoised,
                'stats': stats,
                'snr': snr,
                'rmse': rmse,
                'total_time': total_time,
                'throughput_real_time': len(data) / total_time
            }

            print(f"  SNR: {snr:.2f} dB")
            print(f"  RMSE: {rmse:.6f}")
            print(f"  总耗时: {total_time:.3f} s")
            print(f"  实时吞吐量: {len(data) / total_time:.1f} 样本/秒")
            print(f"  延迟: {stats['latency_samples']} 样本")

        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        axes[0, 0].plot(data[:2000], 'b-', alpha=0.5, label='原始信号')
        for name, res in results.items():
            axes[0, 0].plot(res['denoised'][:2000], label=name, linewidth=1.2)
        axes[0, 0].set_xlabel('样本点', fontsize=12)
        axes[0, 0].set_ylabel('角速率 (deg/h)', fontsize=12)
        axes[0, 0].set_title('各模式去噪效果对比 (前2000样本)', fontsize=14, fontweight='bold')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)

        mode_names = list(results.keys())
        snr_values = [results[n]['snr'] for n in mode_names]
        axes[0, 1].bar(mode_names, snr_values,
                       color=['#1f77b4', '#ff7f0e', '#2ca02c'], alpha=0.7)
        axes[0, 1].set_ylabel('SNR (dB)', fontsize=12)
        axes[0, 1].set_title('信噪比对比', fontsize=14, fontweight='bold')
        axes[0, 1].grid(True, alpha=0.3, axis='y')
        for i, v in enumerate(snr_values):
            axes[0, 1].text(i, v, f'{v:.2f}', ha='center', va='bottom')

        latencies = [results[n]['stats']['latency_samples'] for n in mode_names]
        axes[1, 0].bar(mode_names, latencies,
                       color=['#1f77b4', '#ff7f0e', '#2ca02c'], alpha=0.7)
        axes[1, 0].set_ylabel('延迟 (样本)', fontsize=12)
        axes[1, 0].set_title('处理延迟对比', fontsize=14, fontweight='bold')
        axes[1, 0].grid(True, alpha=0.3, axis='y')
        for i, v in enumerate(latencies):
            axes[1, 0].text(i, v, f'{v}', ha='center', va='bottom')

        throughputs = [results[n]['throughput_real_time'] for n in mode_names]
        axes[1, 1].bar(mode_names, throughputs,
                       color=['#1f77b4', '#ff7f0e', '#2ca02c'], alpha=0.7)
        axes[1, 1].set_ylabel('吞吐量 (样本/秒)', fontsize=12)
        axes[1, 1].set_title('处理吞吐量对比', fontsize=14, fontweight='bold')
        axes[1, 1].grid(True, alpha=0.3, axis='y')
        for i, v in enumerate(throughputs):
            axes[1, 1].text(i, v, f'{v:.0f}', ha='center', va='bottom')

        plt.tight_layout()
        plt.savefig('streaming_mode_comparison.png', dpi=150, bbox_inches='tight')
        plt.close()

        return results
