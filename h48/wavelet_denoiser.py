import numpy as np
import pywt
from typing import Tuple, List, Dict, Optional
from enum import Enum


class ThresholdType(Enum):
    """阈值类型枚举"""
    SOFT = 'soft'
    HARD = 'hard'
    SURE = 'sure'
    SEMISOFT = 'semisoft'
    GARROTE = 'garrote'
    HARD_SMOOTH = 'hard_smooth'


class WaveletDenoiser:
    """
    小波包去噪器
    支持Daubechies小波族，多种阈值去噪方法
    """

    DAUBECHIES_WAVELETS = ['db1', 'db2', 'db3', 'db4', 'db5', 'db6', 'db7', 'db8', 'db9', 'db10']

    def __init__(self, wavelet: str = 'db4', level: int = 4,
                 threshold_type: ThresholdType = ThresholdType.SOFT,
                 threshold_mode: str = 'sln'):
        """
        初始化小波包去噪器

        Args:
            wavelet: 小波基名称，默认'db4'
            level: 分解层数，默认4层
            threshold_type: 阈值类型 (SOFT, HARD, SURE)
            threshold_mode: 阈值模式 ('universal', 'sln', 'mln', 'sqrt')
        """
        self.wavelet = wavelet
        self.level = level
        self.threshold_type = threshold_type
        self.threshold_mode = threshold_mode
        self._validate_wavelet()

    def set_wavelet(self, wavelet: str):
        """设置小波基

        Args:
            wavelet: 新的小波基名称
        """
        old_wavelet = self.wavelet
        self.wavelet = wavelet
        try:
            self._validate_wavelet()
        except Exception as e:
            self.wavelet = old_wavelet
            raise ValueError(f"无效的小波基: {wavelet}. 错误: {e}")

    def set_level(self, level: int):
        """设置分解层数

        Args:
            level: 新的分解层数
        """
        if level < 1:
            raise ValueError(f"分解层数必须大于0, 得到: {level}")
        self.level = level

    def set_threshold_type(self, threshold_type: ThresholdType):
        """设置阈值类型

        Args:
            threshold_type: 新的阈值类型
        """
        self.threshold_type = threshold_type

    def _validate_wavelet(self):
        """验证小波基是否有效"""
        try:
            pywt.Wavelet(self.wavelet)
        except ValueError:
            raise ValueError(f"无效的小波基: {self.wavelet}")

    def _adjust_signal_length(self, signal: np.ndarray) -> Tuple[np.ndarray, int]:
        """
        调整信号长度为2^level的倍数，避免边界混叠

        Args:
            signal: 输入信号

        Returns:
            (调整后的信号, 原始长度)
        """
        original_len = len(signal)
        target_len = int(2 ** np.ceil(np.log2(original_len)))
        required_len = int(2 ** self.level) * (target_len // int(2 ** self.level))

        if original_len < required_len:
            pad_len = required_len - original_len
            signal_padded = np.pad(signal, (0, pad_len), mode='symmetric')
        elif original_len > required_len:
            signal_padded = signal[:required_len]
        else:
            signal_padded = signal.copy()

        return signal_padded, original_len

    def _get_freq_order_indices(self, n_nodes: int) -> np.ndarray:
        """
        生成正确的频率顺序索引，解决频带交错问题

        Args:
            n_nodes: 节点数量

        Returns:
            按频率从低到高排序的索引
        """
        if n_nodes <= 1:
            return np.array([0])

        indices = np.zeros(n_nodes, dtype=int)
        indices[0] = 0
        indices[1] = 1

        current_len = 2
        while current_len < n_nodes:
            new_indices = np.zeros(2 * current_len, dtype=int)
            for i in range(current_len):
                new_indices[2 * i] = indices[i]
                new_indices[2 * i + 1] = 2 * current_len - 1 - indices[i]
            indices = new_indices
            current_len *= 2

        return indices[:n_nodes]

    def wpd_decompose(self, signal: np.ndarray) -> Tuple[List[np.ndarray], np.ndarray, int]:
        """
        小波包分解（修复频带交错问题）

        Args:
            signal: 输入信号

        Returns:
            (节点系数列表, 频率排序索引, 调整后的信号长度)
        """
        signal_adjusted, original_len = self._adjust_signal_length(signal)
        self._original_len = original_len

        wp = pywt.WaveletPacket(data=signal_adjusted, wavelet=self.wavelet, mode='symmetric')
        nodes_natural = [node.data for node in wp.get_level(self.level, 'natural')]

        n_nodes = len(nodes_natural)
        freq_order = self._get_freq_order_indices(n_nodes)
        nodes_freq_ordered = [nodes_natural[i] for i in freq_order]

        self._freq_order = freq_order
        self._wp_tree = wp

        return nodes_freq_ordered, freq_order, len(signal_adjusted)

    def wpd_reconstruct(self, nodes: List[np.ndarray], freq_order: np.ndarray,
                        signal_len: int, original_len: int) -> np.ndarray:
        """
        小波包重构（修复频带交错问题）

        Args:
            nodes: 按频率顺序排列的节点系数列表
            freq_order: 频率排序索引
            signal_len: 调整后的信号长度
            original_len: 原始信号长度

        Returns:
            重构信号（长度与原始信号一致）
        """
        n_nodes = len(nodes)
        nodes_natural = [None] * n_nodes
        for i, idx in enumerate(freq_order):
            nodes_natural[idx] = nodes[i]

        wp = pywt.WaveletPacket(data=np.zeros(signal_len), wavelet=self.wavelet, mode='symmetric')
        level_nodes = wp.get_level(self.level, 'natural')

        for i, node in enumerate(level_nodes):
            if nodes_natural[i] is not None:
                expected_len = len(node.data)
                actual_len = len(nodes_natural[i])
                if actual_len != expected_len:
                    if actual_len > expected_len:
                        nodes_natural[i] = nodes_natural[i][:expected_len]
                    else:
                        nodes_natural[i] = np.pad(nodes_natural[i],
                                                  (0, expected_len - actual_len),
                                                  mode='constant')
                node.data = nodes_natural[i]

        reconstructed = wp.reconstruct()

        if len(reconstructed) > original_len:
            reconstructed = reconstructed[:original_len]
        elif len(reconstructed) < original_len:
            reconstructed = np.pad(reconstructed,
                                   (0, original_len - len(reconstructed)),
                                   mode='symmetric')

        return reconstructed

    def _calculate_threshold(self, coeffs: np.ndarray) -> float:
        """
        计算去噪阈值

        Args:
            coeffs: 小波系数

        Returns:
            阈值
        """
        sigma = np.median(np.abs(coeffs)) / 0.6745

        if self.threshold_mode == 'universal':
            threshold = sigma * np.sqrt(2 * np.log(len(coeffs)))
        elif self.threshold_mode == 'sln':
            threshold = sigma
        elif self.threshold_mode == 'mln':
            level_coeffs = coeffs
            if len(level_coeffs) > 0:
                sigma = np.median(np.abs(level_coeffs)) / 0.6745
                threshold = sigma * np.sqrt(2 * np.log(len(level_coeffs)))
            else:
                threshold = sigma
        elif self.threshold_mode == 'sqrt':
            threshold = sigma * np.sqrt(2)
        else:
            threshold = sigma * np.sqrt(2 * np.log(len(coeffs)))

        return threshold

    def _sure_threshold(self, coeffs: np.ndarray) -> float:
        """
        基于SURE（Stein无偏风险估计）计算最优阈值

        Args:
            coeffs: 小波系数

        Returns:
            SURE最优阈值
        """
        n = len(coeffs)
        if n == 0:
            return 0.0

        sigma = np.median(np.abs(coeffs)) / 0.6745
        if sigma == 0:
            sigma = 1e-10

        coeffs_normalized = coeffs / sigma
        coeffs_sorted = np.sort(np.abs(coeffs_normalized)) ** 2
        c = np.linspace(n - 1, 0, n)
        s = np.cumsum(coeffs_sorted) + c * coeffs_sorted
        risk = (n - 2 * np.arange(1, n + 1) + s) / n
        idx = np.argmin(risk)
        threshold = np.sqrt(coeffs_sorted[idx]) * sigma if idx > 0 else 0

        return threshold

    def _semisoft_threshold(self, coeffs: np.ndarray, threshold: float,
                            alpha: float = 0.5) -> np.ndarray:
        """
        半软阈值函数，在软阈值和硬阈值之间取得平衡

        Args:
            coeffs: 小波系数
            threshold: 阈值
            alpha: 平滑参数 (0=硬阈值, 1=软阈值)

        Returns:
            阈值处理后的系数
        """
        alpha = np.clip(alpha, 0.0, 1.0)
        abs_coeffs = np.abs(coeffs)
        sign = np.sign(coeffs)

        result = np.zeros_like(coeffs)

        mask1 = abs_coeffs <= threshold
        mask2 = (abs_coeffs > threshold) & (abs_coeffs <= 2 * threshold)
        mask3 = abs_coeffs > 2 * threshold

        result[mask2] = sign[mask2] * (abs_coeffs[mask2] - alpha * threshold)
        result[mask3] = coeffs[mask3]

        return result

    def _garrote_threshold(self, coeffs: np.ndarray, threshold: float) -> np.ndarray:
        """
        Garrote阈值函数，连续性好，去噪效果优异

        Args:
            coeffs: 小波系数
            threshold: 阈值

        Returns:
            阈值处理后的系数
        """
        abs_coeffs = np.abs(coeffs)
        sign = np.sign(coeffs)

        result = np.where(
            abs_coeffs > threshold,
            sign * (abs_coeffs - threshold ** 2 / abs_coeffs),
            0.0
        )

        return result

    def _hard_smooth_threshold(self, coeffs: np.ndarray, threshold: float,
                                width: float = 0.2) -> np.ndarray:
        """
        平滑硬阈值函数，在阈值附近使用sigmoid平滑过渡，消除阶梯状抖动

        Args:
            coeffs: 小波系数
            threshold: 阈值
            width: 过渡带宽度比例 (0-0.5)

        Returns:
            阈值处理后的系数
        """
        width = np.clip(width, 0.01, 0.5)
        abs_coeffs = np.abs(coeffs)
        sign = np.sign(coeffs)

        lower = threshold * (1 - width)
        upper = threshold * (1 + width)

        result = np.zeros_like(coeffs)

        mask_below = abs_coeffs <= lower
        mask_above = abs_coeffs >= upper
        mask_transition = ~mask_below & ~mask_above

        result[mask_above] = coeffs[mask_above]

        if np.any(mask_transition):
            x = abs_coeffs[mask_transition]
            k = 10.0 / (width * threshold)
            sigmoid = 1.0 / (1.0 + np.exp(-k * (x - threshold)))
            result[mask_transition] = sign[mask_transition] * x * sigmoid

        return result

    def _apply_threshold(self, coeffs: np.ndarray, threshold: float) -> np.ndarray:
        """
        应用阈值函数（修复硬阈值不连续性问题）

        Args:
            coeffs: 小波系数
            threshold: 阈值

        Returns:
            阈值处理后的系数
        """
        if threshold <= 0:
            return coeffs.copy()

        if self.threshold_type == ThresholdType.SOFT:
            return pywt.threshold(coeffs, threshold, mode='soft')
        elif self.threshold_type == ThresholdType.HARD:
            return self._hard_smooth_threshold(coeffs, threshold, width=0.15)
        elif self.threshold_type == ThresholdType.SURE:
            return pywt.threshold(coeffs, threshold, mode='soft')
        elif self.threshold_type == ThresholdType.SEMISOFT:
            return self._semisoft_threshold(coeffs, threshold, alpha=0.5)
        elif self.threshold_type == ThresholdType.GARROTE:
            return self._garrote_threshold(coeffs, threshold)
        elif self.threshold_type == ThresholdType.HARD_SMOOTH:
            return self._hard_smooth_threshold(coeffs, threshold, width=0.2)
        else:
            return pywt.threshold(coeffs, threshold, mode='soft')

    def denoise(self, signal: np.ndarray) -> np.ndarray:
        """
        对信号进行小波包去噪（修复频带交错和硬阈值不连续性问题）

        Args:
            signal: 输入信号

        Returns:
            去噪后的信号
        """
        original_len = len(signal)
        nodes, freq_order, adjusted_len = self.wpd_decompose(signal)

        denoised_nodes = []
        for i, node in enumerate(nodes):
            if i == 0:
                denoised_nodes.append(node.copy())
                continue

            coeffs = node.copy()

            if self.threshold_type == ThresholdType.SURE:
                threshold = self._sure_threshold(coeffs)
            else:
                threshold = self._calculate_threshold(coeffs)

            denoised_coeffs = self._apply_threshold(coeffs, threshold)
            denoised_nodes.append(denoised_coeffs)

        denoised_signal = self.wpd_reconstruct(
            denoised_nodes, freq_order, adjusted_len, original_len
        )

        return denoised_signal

    def get_wavelet_info(self) -> Dict:
        """
        获取当前小波基的信息

        Returns:
            小波基信息字典
        """
        wavelet = pywt.Wavelet(self.wavelet)
        return {
            'name': wavelet.name,
            'family_name': wavelet.family_name,
            'dec_lo': wavelet.dec_lo,
            'dec_hi': wavelet.dec_hi,
            'rec_lo': wavelet.rec_lo,
            'rec_hi': wavelet.rec_hi,
            'vanishing_moments_psi': wavelet.vanishing_moments_psi,
            'vanishing_moments_phi': wavelet.vanishing_moments_phi
        }

    @classmethod
    def compare_wavelets(cls, signal: np.ndarray, wavelets: List[str] = None,
                         level: int = 4, threshold_type: ThresholdType = ThresholdType.SOFT,
                         metrics: List[str] = None) -> Dict:
        """
        对比不同小波基的去噪效果

        Args:
            signal: 输入信号
            wavelets: 小波基列表，默认使用所有Daubechies小波
            level: 分解层数
            threshold_type: 阈值类型
            metrics: 评估指标列表，支持['snr', 'rmse', 'smoothness']

        Returns:
            各小波基的评估结果字典
        """
        if wavelets is None:
            wavelets = cls.DAUBECHIES_WAVELETS

        if metrics is None:
            metrics = ['snr', 'rmse', 'smoothness']

        results = {}

        for wavelet in wavelets:
            try:
                denoiser = cls(wavelet=wavelet, level=level, threshold_type=threshold_type)
                denoised = denoiser.denoise(signal)

                result = {'denoised': denoised}

                for metric in metrics:
                    if metric == 'snr':
                        result['snr'] = cls._calculate_snr(signal, denoised)
                    elif metric == 'rmse':
                        result['rmse'] = cls._calculate_rmse(signal, denoised)
                    elif metric == 'smoothness':
                        result['smoothness'] = cls._calculate_smoothness(denoised)

                results[wavelet] = result
            except Exception as e:
                print(f"小波基 {wavelet} 处理失败: {e}")

        return results

    @staticmethod
    def _calculate_snr(original: np.ndarray, denoised: np.ndarray) -> float:
        """计算信噪比 (dB)"""
        noise = original - denoised
        signal_power = np.sum(original ** 2)
        noise_power = np.sum(noise ** 2)
        if noise_power == 0:
            return float('inf')
        return 10 * np.log10(signal_power / noise_power)

    @staticmethod
    def _calculate_rmse(original: np.ndarray, denoised: np.ndarray) -> float:
        """计算均方根误差"""
        return np.sqrt(np.mean((original - denoised) ** 2))

    @staticmethod
    def _calculate_smoothness(signal: np.ndarray) -> float:
        """计算信号平滑度（二阶差分的范数）"""
        return np.linalg.norm(np.diff(signal, n=2))

    @staticmethod
    def _shannon_entropy(coeffs: np.ndarray) -> float:
        """
        计算Shannon熵

        Args:
            coeffs: 小波系数

        Returns:
            Shannon熵值
        """
        coeffs = coeffs[coeffs != 0]
        energy = np.sum(coeffs ** 2)
        if energy == 0:
            return 0.0
        p = (coeffs ** 2) / energy
        p = p[p > 0]
        return -np.sum(p * np.log2(p))

    @staticmethod
    def _threshold_entropy(coeffs: np.ndarray, threshold: float = None) -> float:
        """
        计算阈值熵

        Args:
            coeffs: 小波系数
            threshold: 熵阈值

        Returns:
            阈值熵值
        """
        if threshold is None:
            sigma = np.median(np.abs(coeffs)) / 0.6745
            threshold = sigma * np.sqrt(2 * np.log(len(coeffs)))

        abs_coeffs = np.abs(coeffs)
        s = np.where(abs_coeffs > threshold,
                     np.log2(abs_coeffs ** 2),
                     np.log2(threshold ** 2))
        return float(np.sum(s))

    @staticmethod
    def _log_energy_entropy(coeffs: np.ndarray) -> float:
        """
        计算对数能量熵

        Args:
            coeffs: 小波系数

        Returns:
            对数能量熵值
        """
        coeffs_sq = coeffs ** 2
        epsilon = np.finfo(float).eps
        return -float(np.sum(np.log(coeffs_sq + epsilon)))

    def adaptive_wavelet_selection(self, signal: np.ndarray,
                                    wavelet_list: List[str] = None,
                                    criterion: str = 'shannon',
                                    level: int = 4,
                                    return_all: bool = False) -> Dict:
        """
        自适应小波包基选择（基于熵准则）

        为输入信号选择最优的小波基，通过最小化小波包系数的熵值，
        实现信号的最稀疏表示，从而获得更好的去噪效果。

        Args:
            signal: 输入信号
            wavelet_list: 候选小波基列表，默认使用Daubechies家族
            criterion: 熵准则: 'shannon', 'threshold', 'log_energy'
            level: 分解层数
            return_all: 是否返回所有候选小波的评估结果

        Returns:
            包含最优小波基信息和评估结果的字典
        """
        if wavelet_list is None:
            wavelet_list = self.DAUBECHIES_WAVELETS

        criterion_functions = {
            'shannon': self._shannon_entropy,
            'threshold': self._threshold_entropy,
            'log_energy': self._log_energy_entropy
        }

        if criterion not in criterion_functions:
            raise ValueError(f"不支持的熵准则: {criterion}。支持: {list(criterion_functions.keys())}")

        entropy_func = criterion_functions[criterion]

        print(f"\n自适应小波基选择 (准则: {criterion})")
        print("-" * 60)

        results = {}
        entropies = []

        for wavelet in wavelet_list:
            try:
                temp_denoiser = self.__class__(
                    wavelet=wavelet, level=level,
                    threshold_type=self.threshold_type,
                    threshold_mode=self.threshold_mode
                )

                nodes, freq_order, adjusted_len = temp_denoiser.wpd_decompose(signal)

                total_entropy = 0.0
                total_energy = 0.0

                for node in nodes[1:]:
                    node_energy = np.sum(node ** 2)
                    node_entropy = entropy_func(node)
                    total_entropy += node_entropy * node_energy
                    total_energy += node_energy

                if total_energy > 0:
                    avg_entropy = total_entropy / total_energy
                else:
                    avg_entropy = float('inf')

                denoised = temp_denoiser.denoise(signal)
                noise = signal - denoised
                snr = 10 * np.log10(np.sum(signal ** 2) / (np.sum(noise ** 2) + 1e-20))
                rmse = np.sqrt(np.mean(noise ** 2))

                results[wavelet] = {
                    'entropy': avg_entropy,
                    'snr': snr,
                    'rmse': rmse,
                    'denoised': denoised
                }
                entropies.append(avg_entropy)

                print(f"  {wavelet:6s}: 熵={avg_entropy:.4f}, SNR={snr:.2f} dB, RMSE={rmse:.6f}")

            except Exception as e:
                print(f"  {wavelet:6s}: 处理失败 - {e}")
                results[wavelet] = {
                    'entropy': float('inf'),
                    'snr': -float('inf'),
                    'rmse': float('inf'),
                    'denoised': None
                }
                entropies.append(float('inf'))

        if not entropies or all(np.isinf(entropies)):
            raise RuntimeError("所有小波基处理失败")

        valid_indices = [i for i, e in enumerate(entropies) if not np.isinf(e)]
        best_idx = valid_indices[np.argmin([entropies[i] for i in valid_indices])]
        best_wavelet = wavelet_list[best_idx]
        best_result = results[best_wavelet]

        print("-" * 60)
        print(f"最优小波基: {best_wavelet}")
        print(f"  熵值: {best_result['entropy']:.4f}")
        print(f"  SNR:  {best_result['snr']:.2f} dB")
        print(f"  RMSE: {best_result['rmse']:.6f}")

        self.wavelet = best_wavelet
        self._validate_wavelet()

        output = {
            'best_wavelet': best_wavelet,
            'best_result': best_result,
            'criterion': criterion,
            'level': level
        }

        if return_all:
            output['all_results'] = results

        return output
