import numpy as np
from scipy import signal
from scipy.stats import kurtosis, skew
import pywt
from typing import Dict, List, Optional, Tuple, Union
import warnings


class TimeDomainFeatures:
    """时域特征提取"""
    
    @staticmethod
    def peak_to_peak(signal_data: np.ndarray) -> np.ndarray:
        """峰峰值"""
        return np.max(signal_data, axis=0) - np.min(signal_data, axis=0)
    
    @staticmethod
    def root_mean_square(signal_data: np.ndarray) -> np.ndarray:
        """均方根值 (RMS)"""
        return np.sqrt(np.mean(signal_data ** 2, axis=0))
    
    @staticmethod
    def peak_value(signal_data: np.ndarray) -> np.ndarray:
        """峰值"""
        return np.max(np.abs(signal_data), axis=0)
    
    @staticmethod
    def kurtosis(signal_data: np.ndarray) -> np.ndarray:
        """峭度"""
        return kurtosis(signal_data, axis=0, fisher=False)
    
    @staticmethod
    def skewness(signal_data: np.ndarray) -> np.ndarray:
        """偏度"""
        return skew(signal_data, axis=0)
    
    @staticmethod
    def crest_factor(signal_data: np.ndarray) -> np.ndarray:
        """峰值因子 (波峰因数)"""
        rms = TimeDomainFeatures.root_mean_square(signal_data)
        peak = TimeDomainFeatures.peak_value(signal_data)
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(rms > 0, peak / rms, 0.0)
    
    @staticmethod
    def impulse_factor(signal_data: np.ndarray) -> np.ndarray:
        """脉冲因子"""
        mean_abs = np.mean(np.abs(signal_data), axis=0)
        peak = TimeDomainFeatures.peak_value(signal_data)
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(mean_abs > 0, peak / mean_abs, 0.0)
    
    @staticmethod
    def margin_factor(signal_data: np.ndarray) -> np.ndarray:
        """裕度因子"""
        mean_sqrt = np.mean(np.sqrt(np.abs(signal_data)), axis=0) ** 2
        peak = TimeDomainFeatures.peak_value(signal_data)
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(mean_sqrt > 0, peak / mean_sqrt, 0.0)
    
    @staticmethod
    def shape_factor(signal_data: np.ndarray) -> np.ndarray:
        """波形因子"""
        rms = TimeDomainFeatures.root_mean_square(signal_data)
        mean_abs = np.mean(np.abs(signal_data), axis=0)
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(mean_abs > 0, rms / mean_abs, 0.0)
    
    @staticmethod
    def mean_value(signal_data: np.ndarray) -> np.ndarray:
        """均值"""
        return np.mean(signal_data, axis=0)
    
    @staticmethod
    def variance(signal_data: np.ndarray) -> np.ndarray:
        """方差"""
        return np.var(signal_data, axis=0)
    
    @staticmethod
    def standard_deviation(signal_data: np.ndarray) -> np.ndarray:
        """标准差"""
        return np.std(signal_data, axis=0)


class FrequencyDomainFeatures:
    """频域特征提取"""
    
    def __init__(self, fs: float):
        """
        Args:
            fs: 采样频率 (Hz)
        """
        self.fs = fs
    
    def compute_spectrum(self, signal_data: np.ndarray,
                        nfft: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        """计算频谱"""
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(-1, 1)
        
        n_samples = signal_data.shape[0]
        if nfft is None:
            nfft = n_samples
        
        freq_axis = np.fft.rfftfreq(nfft, 1.0 / self.fs)
        spectrum = np.zeros((len(freq_axis), signal_data.shape[1]))
        
        for i in range(signal_data.shape[1]):
            spectrum[:, i] = np.abs(np.fft.rfft(signal_data[:, i], n=nfft))
        
        return freq_axis, spectrum
    
    def envelope_spectrum_features(self, signal_data: np.ndarray,
                                   fault_freqs: Optional[Dict[str, float]] = None,
                                   harmonics: int = 4,
                                   normalize_by_rotation: bool = True) -> Dict[str, np.ndarray]:
        """
        包络谱特征 - 提取故障特征频率及其谐波处的幅值
        增强版：支持转速归一化和多故障识别特征
        
        Args:
            signal_data: 输入信号
            fault_freqs: 故障频率字典 {'bpfi': x, 'bpfo': x, 'bsf': x, 'ftf': x}
            harmonics: 考虑的谐波次数
            normalize_by_rotation: 是否除以转频幅值进行归一化
        
        Returns:
            包络谱特征字典，包含绝对幅值和归一化幅值
        """
        freq_axis, spec = self.compute_spectrum(signal_data)
        
        features = {}
        n_channels = spec.shape[1]
        
        features['spectral_centroid'] = self._spectral_centroid(freq_axis, spec)
        features['spectral_spread'] = self._spectral_spread(freq_axis, spec)
        features['spectral_skewness'] = self._spectral_skewness(freq_axis, spec)
        features['spectral_kurtosis'] = self._spectral_kurtosis(freq_axis, spec)
        features['spectral_rolloff'] = self._spectral_rolloff(freq_axis, spec)
        features['spectral_energy'] = np.sum(spec ** 2, axis=0)
        features['spectral_entropy'] = self._spectral_entropy(spec)
        
        if fault_freqs is not None:
            fr = fault_freqs.get('rotational_frequency', 1.0)
            fr_amp = self._get_amplitude_at_freq(freq_axis, spec, fr) if normalize_by_rotation else np.ones(n_channels)
            
            with np.errstate(divide='ignore', invalid='ignore'):
                fr_amp_safe = np.where(fr_amp > 0, fr_amp, 1.0)
            
            for fault_name, fault_freq in fault_freqs.items():
                if fault_name in ['rotational_frequency', 'coefficients', 'normalized']:
                    continue
                for h in range(1, harmonics + 1):
                    target_freq = h * fault_freq
                    amplitude = self._get_amplitude_at_freq(freq_axis, spec, target_freq)
                    features[f'{fault_name}_{h}x_amp'] = amplitude
                    
                    if normalize_by_rotation:
                        features[f'{fault_name}_{h}x_amp_norm'] = amplitude / fr_amp_safe
                    
                    for side in [-1, 1]:
                        side_freq = target_freq + side * fr
                        side_amp = self._get_amplitude_at_freq(freq_axis, spec, side_freq)
                        features[f'{fault_name}_{h}x_side{side}_amp'] = side_amp
                        
                        if normalize_by_rotation:
                            features[f'{fault_name}_{h}x_side{side}_amp_norm'] = side_amp / fr_amp_safe
            
            if harmonics >= 2:
                fault_names = ['bpfi', 'bpfo', 'bsf', 'ftf']
                for i, f1 in enumerate(fault_names):
                    if f1 not in fault_freqs:
                        continue
                    for f2 in fault_names[i+1:]:
                        if f2 not in fault_freqs:
                            continue
                        amp1 = features.get(f'{f1}_1x_amp', np.zeros(n_channels))
                        amp2 = features.get(f'{f2}_1x_amp', np.zeros(n_channels))
                        with np.errstate(divide='ignore', invalid='ignore'):
                            ratio = np.where(amp2 > 0, amp1 / amp2, 0)
                        features[f'ratio_{f1}_{f2}'] = ratio
            
            for fault_name in ['bpfi', 'bpfo', 'bsf', 'ftf']:
                if fault_name not in fault_freqs:
                    continue
                harmonic_energy = np.zeros(n_channels)
                for h in range(1, harmonics + 1):
                    amp = features.get(f'{fault_name}_{h}x_amp', np.zeros(n_channels))
                    harmonic_energy += amp ** 2
                total_energy = np.sum(spec ** 2, axis=0)
                with np.errstate(divide='ignore', invalid='ignore'):
                    ratio = np.where(total_energy > 0, harmonic_energy / total_energy, 0)
                features[f'{fault_name}_energy_ratio'] = ratio
        
        return features
    
    def _get_amplitude_at_freq(self, freq_axis: np.ndarray,
                               spectrum: np.ndarray,
                               target_freq: float,
                               tolerance: float = 0.05) -> np.ndarray:
        """获取指定频率处的幅值（取邻域最大值）"""
        bandwidth = target_freq * tolerance
        mask = (freq_axis >= target_freq - bandwidth) & (freq_axis <= target_freq + bandwidth)
        
        if np.any(mask):
            return np.max(spectrum[mask, :], axis=0)
        else:
            return np.zeros(spectrum.shape[1])
    
    def _spectral_centroid(self, freq_axis: np.ndarray, spectrum: np.ndarray) -> np.ndarray:
        """频谱质心"""
        with np.errstate(divide='ignore', invalid='ignore'):
            total = np.sum(spectrum, axis=0)
            return np.where(total > 0,
                          np.sum(freq_axis[:, None] * spectrum, axis=0) / total,
                          0.0)
    
    def _spectral_spread(self, freq_axis: np.ndarray, spectrum: np.ndarray) -> np.ndarray:
        """频谱扩展度"""
        centroid = self._spectral_centroid(freq_axis, spectrum)
        total = np.sum(spectrum, axis=0)
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(total > 0,
                          np.sqrt(np.sum((freq_axis[:, None] - centroid) ** 2 * spectrum, axis=0) / total),
                          0.0)
    
    def _spectral_skewness(self, freq_axis: np.ndarray, spectrum: np.ndarray) -> np.ndarray:
        """频谱偏度"""
        centroid = self._spectral_centroid(freq_axis, spectrum)
        spread = self._spectral_spread(freq_axis, spectrum)
        total = np.sum(spectrum, axis=0)
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where((total > 0) & (spread > 0),
                          np.sum((freq_axis[:, None] - centroid) ** 3 * spectrum, axis=0) / (total * spread ** 3),
                          0.0)
    
    def _spectral_kurtosis(self, freq_axis: np.ndarray, spectrum: np.ndarray) -> np.ndarray:
        """频谱峭度"""
        centroid = self._spectral_centroid(freq_axis, spectrum)
        spread = self._spectral_spread(freq_axis, spectrum)
        total = np.sum(spectrum, axis=0)
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where((total > 0) & (spread > 0),
                          np.sum((freq_axis[:, None] - centroid) ** 4 * spectrum, axis=0) / (total * spread ** 4),
                          0.0)
    
    def _spectral_rolloff(self, freq_axis: np.ndarray, spectrum: np.ndarray,
                         percentile: float = 0.85) -> np.ndarray:
        """频谱滚降点"""
        total_energy = np.sum(spectrum, axis=0)
        cumulative = np.cumsum(spectrum, axis=0)
        threshold = total_energy * percentile
        
        rolloff = np.zeros(spectrum.shape[1])
        for i in range(spectrum.shape[1]):
            idx = np.where(cumulative[:, i] >= threshold[i])[0]
            if len(idx) > 0:
                rolloff[i] = freq_axis[idx[0]]
        
        return rolloff
    
    def _spectral_entropy(self, spectrum: np.ndarray) -> np.ndarray:
        """频谱熵"""
        total = np.sum(spectrum, axis=0)
        with np.errstate(divide='ignore', invalid='ignore'):
            psd = np.where(total > 0, spectrum / total, 0)
            psd = np.where(psd > 0, psd, 1e-12)
            return -np.sum(psd * np.log2(psd), axis=0)


class TimeFrequencyDomainFeatures:
    """时频域特征提取 - 小波包能量"""
    
    def __init__(self, wavelet: str = 'db4', level: int = 4):
        """
        Args:
            wavelet: 小波基函数名称
            level: 分解层数
        """
        self.wavelet = wavelet
        self.level = level
    
    def wavelet_packet_decomposition(self, signal_data: np.ndarray) -> List:
        """
        小波包分解
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
        
        Returns:
            各通道的小波包分解系数列表
        """
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(-1, 1)
        
        all_coeffs = []
        for i in range(signal_data.shape[1]):
            wp = pywt.WaveletPacket(data=signal_data[:, i],
                                   wavelet=self.wavelet,
                                   mode='symmetric')
            all_coeffs.append(wp)
        
        return all_coeffs
    
    def wavelet_packet_energy(self, signal_data: np.ndarray,
                              normalize: bool = True) -> np.ndarray:
        """
        计算小波包能量特征
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
            normalize: 是否归一化能量
        
        Returns:
            小波包能量特征 (n_nodes, n_channels)
        """
        all_coeffs = self.wavelet_packet_decomposition(signal_data)
        n_nodes = 2 ** self.level
        n_channels = signal_data.shape[1]
        
        energies = np.zeros((n_nodes, n_channels))
        
        for chan_idx, wp in enumerate(all_coeffs):
            level_nodes = [node.path for node in wp.get_level(self.level, 'natural')]
            
            for node_idx, node_path in enumerate(level_nodes):
                coeffs = wp[node_path].data
                energy = np.sum(coeffs ** 2)
                energies[node_idx, chan_idx] = energy
            
            if normalize:
                total_energy = np.sum(energies[:, chan_idx])
                if total_energy > 0:
                    energies[:, chan_idx] /= total_energy
        
        return energies
    
    def wavelet_energy_entropy(self, signal_data: np.ndarray) -> np.ndarray:
        """
        小波包能量熵
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
        
        Returns:
            能量熵 (n_channels,)
        """
        energies = self.wavelet_packet_energy(signal_data, normalize=True)
        energies = np.where(energies > 0, energies, 1e-12)
        entropy = -np.sum(energies * np.log2(energies), axis=0)
        return entropy
    
    def wavelet_standard_deviation(self, signal_data: np.ndarray) -> np.ndarray:
        """
        小波包系数标准差
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
        
        Returns:
            各节点系数的标准差 (n_nodes, n_channels)
        """
        all_coeffs = self.wavelet_packet_decomposition(signal_data)
        n_nodes = 2 ** self.level
        n_channels = signal_data.shape[1]
        
        stds = np.zeros((n_nodes, n_channels))
        
        for chan_idx, wp in enumerate(all_coeffs):
            level_nodes = [node.path for node in wp.get_level(self.level, 'natural')]
            
            for node_idx, node_path in enumerate(level_nodes):
                coeffs = wp[node_path].data
                stds[node_idx, chan_idx] = np.std(coeffs)
        
        return stds


class FeatureExtractor:
    """综合特征提取器"""
    
    def __init__(self, fs: float,
                 wavelet: str = 'db4',
                 wavelet_level: int = 4,
                 extract_time: bool = True,
                 extract_frequency: bool = True,
                 extract_timefreq: bool = True):
        """
        Args:
            fs: 采样频率 (Hz)
            wavelet: 小波基函数
            wavelet_level: 小波包分解层数
            extract_time: 是否提取时域特征
            extract_frequency: 是否提取频域特征
            extract_timefreq: 是否提取时频域特征
        """
        self.fs = fs
        self.extract_time = extract_time
        self.extract_frequency = extract_frequency
        self.extract_timefreq = extract_timefreq
        
        self.time_features = TimeDomainFeatures()
        self.freq_features = FrequencyDomainFeatures(fs)
        self.tf_features = TimeFrequencyDomainFeatures(wavelet, wavelet_level)
        
        self.feature_names_: List[str] = []
    
    def extract(self, signal_data: np.ndarray,
                fault_freqs: Optional[Dict[str, float]] = None) -> Tuple[np.ndarray, List[str]]:
        """
        提取所有特征（包含数值稳定性处理）
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
            fault_freqs: 故障频率字典，用于提取包络谱特征
        
        Returns:
            (feature_matrix, feature_names)
            feature_matrix: (n_samples, n_features) 单样本则为 (1, n_features)
            feature_names: 特征名称列表
        """
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(-1, 1)
        
        max_val = np.max(np.abs(signal_data))
        if max_val > 1e6 or max_val < 1e-6:
            signal_data = np.clip(signal_data, -1e6, 1e6)
            if max_val > 1e-6:
                signal_data = signal_data / max_val * 100
        
        n_channels = signal_data.shape[1]
        all_features = []
        all_names = []
        
        if self.extract_time:
            time_feats, time_names = self._extract_time_features(signal_data)
            all_features.append(time_feats)
            all_names.extend(time_names)
        
        if self.extract_frequency:
            freq_feats, freq_names = self._extract_frequency_features(
                signal_data, fault_freqs)
            all_features.append(freq_feats)
            all_names.extend(freq_names)
        
        if self.extract_timefreq:
            tf_feats, tf_names = self._extract_timefreq_features(signal_data)
            all_features.append(tf_feats)
            all_names.extend(tf_names)
        
        feature_matrix = np.concatenate(all_features, axis=1)
        
        feature_matrix = np.nan_to_num(feature_matrix, nan=0.0, posinf=1e6, neginf=-1e6)
        feature_matrix = np.clip(feature_matrix, -1e6, 1e6)
        
        self.feature_names_ = all_names
        
        return feature_matrix, all_names
    
    def _extract_time_features(self, signal_data: np.ndarray) -> Tuple[np.ndarray, List[str]]:
        """提取时域特征"""
        n_channels = signal_data.shape[1]
        features = []
        names = []
        
        time_methods = [
            ('peak_to_peak', self.time_features.peak_to_peak),
            ('rms', self.time_features.root_mean_square),
            ('peak', self.time_features.peak_value),
            ('kurtosis', self.time_features.kurtosis),
            ('skewness', self.time_features.skewness),
            ('crest_factor', self.time_features.crest_factor),
            ('impulse_factor', self.time_features.impulse_factor),
            ('margin_factor', self.time_features.margin_factor),
            ('shape_factor', self.time_features.shape_factor),
            ('mean', self.time_features.mean_value),
            ('variance', self.time_features.variance),
            ('std', self.time_features.standard_deviation),
        ]
        
        for name, func in time_methods:
            values = func(signal_data)
            for chan in range(n_channels):
                features.append(values[chan])
                names.append(f'time_{name}_ch{chan + 1}')
        
        return np.array(features).reshape(1, -1), names
    
    def _extract_frequency_features(self, signal_data: np.ndarray,
                                    fault_freqs: Optional[Dict[str, float]] = None
                                    ) -> Tuple[np.ndarray, List[str]]:
        """提取频域特征"""
        n_channels = signal_data.shape[1]
        features = []
        names = []
        
        freq_feats = self.freq_features.envelope_spectrum_features(
            signal_data, fault_freqs)
        
        for feat_name, values in freq_feats.items():
            for chan in range(n_channels):
                features.append(values[chan])
                names.append(f'freq_{feat_name}_ch{chan + 1}')
        
        return np.array(features).reshape(1, -1), names
    
    def _extract_timefreq_features(self, signal_data: np.ndarray
                                    ) -> Tuple[np.ndarray, List[str]]:
        """提取时频域特征"""
        n_channels = signal_data.shape[1]
        features = []
        names = []
        
        wp_energy = self.tf_features.wavelet_packet_energy(signal_data)
        for node in range(wp_energy.shape[0]):
            for chan in range(n_channels):
                features.append(wp_energy[node, chan])
                names.append(f'tf_wp_energy_node{node}_ch{chan + 1}')
        
        wp_entropy = self.tf_features.wavelet_energy_entropy(signal_data)
        for chan in range(n_channels):
            features.append(wp_entropy[chan])
            names.append(f'tf_wp_entropy_ch{chan + 1}')
        
        wp_std = self.tf_features.wavelet_standard_deviation(signal_data)
        for node in range(wp_std.shape[0]):
            for chan in range(n_channels):
                features.append(wp_std[node, chan])
                names.append(f'tf_wp_std_node{node}_ch{chan + 1}')
        
        return np.array(features).reshape(1, -1), names
