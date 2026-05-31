import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from typing import Dict, List, Optional, Tuple
import matplotlib
matplotlib.use('Agg')

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False


class DataVisualizer:
    """
    数据可视化器
    用于绘制原始信号、降噪信号、频谱图、Allan方差曲线等
    """

    def __init__(self, sample_rate: float = 100.0, figsize: Tuple[int, int] = (12, 8)):
        """
        初始化可视化器

        Args:
            sample_rate: 采样频率 (Hz)
            figsize: 图像尺寸
        """
        self.sample_rate = sample_rate
        self.figsize = figsize

    def plot_time_series(self, time: np.ndarray, signals: Dict[str, np.ndarray],
                         title: str = "时域信号对比", xlabel: str = "时间 (s)",
                         ylabel: str = "角速率 (deg/h)",
                         xlim: Optional[Tuple[float, float]] = None,
                         save_path: Optional[str] = None):
        """
        绘制时域信号对比图

        Args:
            time: 时间数组
            signals: 信号字典，{信号名称: 信号数据}
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            xlim: X轴范围
            save_path: 保存路径，如果为None则显示
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        linestyles = ['-', '--', '-.', ':', '-']

        for i, (name, data) in enumerate(signals.items()):
            ax.plot(time, data, label=name, color=colors[i % len(colors)],
                    linestyle=linestyles[i % len(linestyles)],
                    linewidth=1.5, alpha=0.8)

        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3)

        if xlim:
            ax.set_xlim(xlim)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
        else:
            plt.show()

    def plot_spectrum(self, signals: Dict[str, np.ndarray],
                      title: str = "频谱对比",
                      xlabel: str = "频率 (Hz)",
                      ylabel: str = "幅值 (dB)",
                      freq_range: Optional[Tuple[float, float]] = None,
                      save_path: Optional[str] = None):
        """
        绘制频谱对比图

        Args:
            signals: 信号字典，{信号名称: 信号数据}
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            freq_range: 频率显示范围
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        linestyles = ['-', '--', '-.', ':', '-']

        for i, (name, data) in enumerate(signals.items()):
            n = len(data)
            freqs = np.fft.fftfreq(n, 1.0 / self.sample_rate)
            fft_vals = np.fft.fft(data)
            magnitude = 20 * np.log10(np.abs(fft_vals) / n + 1e-12)

            positive_idx = freqs >= 0
            freqs_pos = freqs[positive_idx]
            magnitude_pos = magnitude[positive_idx]

            ax.plot(freqs_pos, magnitude_pos, label=name,
                    color=colors[i % len(colors)],
                    linestyle=linestyles[i % len(linestyles)],
                    linewidth=1.5, alpha=0.8)

        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3)

        if freq_range:
            ax.set_xlim(freq_range)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
        else:
            plt.show()

    def plot_psd(self, signals: Dict[str, np.ndarray],
                 title: str = "功率谱密度 (PSD) 对比",
                 xlabel: str = "频率 (Hz)",
                 ylabel: str = "PSD (dB/Hz)",
                 freq_range: Optional[Tuple[float, float]] = None,
                 save_path: Optional[str] = None):
        """
        绘制功率谱密度对比图

        Args:
            signals: 信号字典
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            freq_range: 频率范围
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        linestyles = ['-', '--', '-.', ':', '-']

        for i, (name, data) in enumerate(signals.items()):
            f, Pxx = signal.welch(data, self.sample_rate, nperseg=min(1024, len(data)),
                                  scaling='density')
            Pxx_db = 10 * np.log10(Pxx + 1e-20)

            ax.semilogx(f, Pxx_db, label=name,
                        color=colors[i % len(colors)],
                        linestyle=linestyles[i % len(linestyles)],
                        linewidth=1.5, alpha=0.8)

        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3, which='both')

        if freq_range:
            ax.set_xlim(freq_range)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
        else:
            plt.show()

    def plot_allan_variance(self, allan_results: Dict[str, Dict],
                            title: str = "Allan 方差对比",
                            xlabel: str = "时间常数 τ (s)",
                            ylabel: str = "Allan 标准差 σ (deg/h)",
                            show_fit: bool = True,
                            save_path: Optional[str] = None):
        """
        绘制Allan方差对比曲线

        Args:
            allan_results: Allan方差分析结果字典，{名称: 结果字典}
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            show_fit: 是否显示拟合曲线
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        markers = ['o', 's', '^', 'D', 'v']

        for i, (name, results) in enumerate(allan_results.items()):
            tau = results.get('tau', [])
            allan_std = results.get('allan_std', [])

            ax.loglog(tau, allan_std, marker=markers[i % len(markers)],
                      linestyle='-', color=colors[i % len(colors)],
                      label=name, markersize=4, linewidth=1.5, alpha=0.7)

            if show_fit and 'fitted_curve' in results:
                ax.loglog(tau, results['fitted_curve'],
                          linestyle='--', color=colors[i % len(colors)],
                          linewidth=2, alpha=0.9,
                          label=f'{name} (拟合)')

        self._add_allan_slope_lines(ax, min(tau), max(tau))

        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3, which='both')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
        else:
            plt.show()

    def _add_allan_slope_lines(self, ax, tau_min: float, tau_max: float):
        """
        添加Allan方差斜率参考线
        """
        tau_ref = np.logspace(np.log10(tau_min), np.log10(tau_max), 100)

        slopes = [
            (-1, '量化噪声 Q ∝ τ⁻¹', '#aaaaaa', ':'),
            (-0.5, '角度随机游走 N ∝ τ⁻⁰·⁵', '#888888', '--'),
            (0, '零偏不稳定性 B ∝ τ⁰', '#666666', '-.'),
            (0.5, '速率随机游走 K ∝ τ⁰·⁵', '#444444', '--'),
            (1, '速率斜坡 R ∝ τ¹', '#222222', ':')
        ]

        for slope, label, color, linestyle in slopes:
            sigma_ref = 10 ** (slope * np.log10(tau_ref) + 1)
            sigma_ref = sigma_ref * 1e-4
            if np.all(np.isfinite(sigma_ref)):
                ax.loglog(tau_ref, sigma_ref, color=color, linestyle=linestyle,
                          linewidth=1, alpha=0.5, label='_nolegend_')

    def plot_wavelet_comparison(self, comparison_results: Dict,
                                metric: str = 'snr',
                                title: str = "小波基去噪效果对比",
                                save_path: Optional[str] = None):
        """
        绘制不同小波基的去噪效果对比柱状图

        Args:
            comparison_results: compare_wavelets 返回的结果字典
            metric: 对比指标 ('snr', 'rmse', 'smoothness')
            title: 图表标题
            save_path: 保存路径
        """
        wavelets = list(comparison_results.keys())
        values = [comparison_results[w].get(metric, 0) for w in wavelets]

        fig, ax = plt.subplots(figsize=(14, 6))

        bars = ax.bar(wavelets, values, color='#1f77b4', alpha=0.7, edgecolor='black')

        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2., height,
                    f'{val:.4f}',
                    ha='center', va='bottom', fontsize=10)

        metric_labels = {
            'snr': '信噪比 (dB)',
            'rmse': '均方根误差',
            'smoothness': '平滑度'
        }

        ax.set_xlabel('小波基', fontsize=12)
        ax.set_ylabel(metric_labels.get(metric, metric), fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        plt.xticks(rotation=45)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
        else:
            plt.show()

    def plot_noise_coefficients_bar(self, results_before: Dict, results_after: Dict,
                                    title: str = "降噪前后噪声系数对比",
                                    save_path: Optional[str] = None):
        """
        绘制降噪前后噪声系数对比柱状图

        Args:
            results_before: 降噪前的Allan分析结果
            results_after: 降噪后的Allan分析结果
            title: 图表标题
            save_path: 保存路径
        """
        params = [
            ('quantization_noise', '量化噪声'),
            ('angle_random_walk', '角度随机游走'),
            ('bias_instability', '零偏不稳定性'),
            ('rate_random_walk', '速率随机游走'),
            ('rate_ramp', '速率斜坡')
        ]

        param_names = [p[1] for p in params]
        values_before = [results_before.get(p[0], 0) for p in params]
        values_after = [results_after.get(p[0], 0) for p in params]

        x = np.arange(len(param_names))
        width = 0.35

        fig, ax = plt.subplots(figsize=(14, 6))

        rects1 = ax.bar(x - width / 2, values_before, width,
                        label='降噪前', color='#1f77b4', alpha=0.7, edgecolor='black')
        rects2 = ax.bar(x + width / 2, values_after, width,
                        label='降噪后', color='#ff7f0e', alpha=0.7, edgecolor='black')

        ax.set_ylabel('系数值', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(param_names, fontsize=11, rotation=15)
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_yscale('log')

        for rects in [rects1, rects2]:
            for rect in rects:
                height = rect.get_height()
                ax.text(rect.get_x() + rect.get_width() / 2., height,
                        f'{height:.2e}',
                        ha='center', va='bottom', fontsize=9)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
        else:
            plt.show()

    def plot_comprehensive(self, time: np.ndarray, original: np.ndarray,
                           denoised: np.ndarray, allan_before: Dict, allan_after: Dict,
                           title_prefix: str = "",
                           save_dir: Optional[str] = None):
        """
        生成综合分析图表（2x2子图）

        Args:
            time: 时间数组
            original: 原始信号
            denoised: 降噪后信号
            allan_before: 降噪前Allan分析结果
            allan_after: 降噪后Allan分析结果
            title_prefix: 标题前缀
            save_dir: 保存目录
        """
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        colors = ['#1f77b4', '#ff7f0e']

        ax1 = axes[0, 0]
        ax1.plot(time, original, label='原始信号', color=colors[0], alpha=0.7, linewidth=1)
        ax1.plot(time, denoised, label='降噪信号', color=colors[1], alpha=0.8, linewidth=1.2)
        ax1.set_xlabel('时间 (s)', fontsize=11)
        ax1.set_ylabel('角速率 (deg/h)', fontsize=11)
        ax1.set_title(f'{title_prefix}时域信号对比', fontsize=12, fontweight='bold')
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3)

        ax2 = axes[0, 1]
        for i, (name, data) in enumerate([('原始信号', original), ('降噪信号', denoised)]):
            n = len(data)
            freqs = np.fft.fftfreq(n, 1.0 / self.sample_rate)
            fft_vals = np.fft.fft(data)
            magnitude = 20 * np.log10(np.abs(fft_vals) / n + 1e-12)
            positive_idx = freqs >= 0
            ax2.plot(freqs[positive_idx], magnitude[positive_idx],
                     label=name, color=colors[i], alpha=0.7, linewidth=1)
        ax2.set_xlabel('频率 (Hz)', fontsize=11)
        ax2.set_ylabel('幅值 (dB)', fontsize=11)
        ax2.set_title(f'{title_prefix}频谱对比', fontsize=12, fontweight='bold')
        ax2.legend(fontsize=10)
        ax2.grid(True, alpha=0.3)

        ax3 = axes[1, 0]
        for i, (name, data) in enumerate([('原始信号', original), ('降噪信号', denoised)]):
            f, Pxx = signal.welch(data, self.sample_rate, nperseg=min(1024, len(data)))
            ax3.semilogx(f, 10 * np.log10(Pxx + 1e-20),
                         label=name, color=colors[i], alpha=0.7, linewidth=1)
        ax3.set_xlabel('频率 (Hz)', fontsize=11)
        ax3.set_ylabel('PSD (dB/Hz)', fontsize=11)
        ax3.set_title(f'{title_prefix}功率谱密度对比', fontsize=12, fontweight='bold')
        ax3.legend(fontsize=10)
        ax3.grid(True, alpha=0.3, which='both')

        ax4 = axes[1, 1]
        tau_b = allan_before.get('tau', [])
        std_b = allan_before.get('allan_std', [])
        tau_a = allan_after.get('tau', [])
        std_a = allan_after.get('allan_std', [])
        ax4.loglog(tau_b, std_b, label='原始信号', color=colors[0],
                   marker='o', markersize=3, alpha=0.6, linewidth=1)
        ax4.loglog(tau_a, std_a, label='降噪信号', color=colors[1],
                   marker='s', markersize=3, alpha=0.8, linewidth=1)
        if 'fitted_curve' in allan_after:
            ax4.loglog(tau_a, allan_after['fitted_curve'], '--',
                       color=colors[1], label='降噪信号(拟合)', linewidth=1.5)
        self._add_allan_slope_lines(ax4, min(min(tau_b), min(tau_a)), max(max(tau_b), max(tau_a)))
        ax4.set_xlabel('时间常数 τ (s)', fontsize=11)
        ax4.set_ylabel('Allan 标准差 σ (deg/h)', fontsize=11)
        ax4.set_title(f'{title_prefix}Allan 方差对比', fontsize=12, fontweight='bold')
        ax4.legend(fontsize=10)
        ax4.grid(True, alpha=0.3, which='both')

        plt.tight_layout()

        if save_dir:
            import os
            save_path = os.path.join(save_dir, f'{title_prefix}综合分析.png')
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
            plt.close()
        else:
            plt.show()

    def plot_wavelet_coefficients(self, nodes: List[np.ndarray], level: int,
                                  title: str = "小波包分解系数",
                                  save_path: Optional[str] = None):
        """
        绘制小波包分解各节点的系数

        Args:
            nodes: 小波包节点系数列表
            level: 分解层数
            title: 图表标题
            save_path: 保存路径
        """
        n_nodes = len(nodes)
        cols = min(4, n_nodes)
        rows = (n_nodes + cols - 1) // cols

        fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 3 * rows))
        axes = axes.flatten() if n_nodes > 1 else [axes]

        for i, (ax, node) in enumerate(zip(axes, nodes)):
            freq_low = i / n_nodes * self.sample_rate / 2
            freq_high = (i + 1) / n_nodes * self.sample_rate / 2
            ax.plot(node, linewidth=0.8, color='#1f77b4')
            ax.set_title(f'节点 {i} ({freq_low:.1f}-{freq_high:.1f} Hz)', fontsize=10)
            ax.grid(True, alpha=0.3)
            ax.tick_params(axis='both', labelsize=8)

        for j in range(i + 1, len(axes)):
            axes[j].set_visible(False)

        fig.suptitle(f'{title} (第{level}层分解)', fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
            plt.close()
        else:
            plt.show()
