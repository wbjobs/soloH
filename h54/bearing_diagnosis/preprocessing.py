import numpy as np
from scipy import signal
from scipy.signal import butter, filtfilt, detrend
from typing import Tuple, Optional, Union, List
import warnings


class BearingFaultFrequency:
    """
    轴承故障特征频率计算
    
    基于轴承几何参数计算各部件的故障特征频率
    """
    
    def __init__(self, n_rolling_elements: int, pitch_diameter: float,
                 rolling_element_diameter: float, contact_angle: float = 0.0):
        """
        Args:
            n_rolling_elements: 滚动体数量
            pitch_diameter: 节径 (mm)
            rolling_element_diameter: 滚动体直径 (mm)
            contact_angle: 接触角 (度)
        """
        self.n_rolling_elements = n_rolling_elements
        self.pitch_diameter = pitch_diameter
        self.rolling_element_diameter = rolling_element_diameter
        self.contact_angle = np.deg2rad(contact_angle)
        
        self._calculate_coefficients()
    
    def _calculate_coefficients(self) -> None:
        """计算频率系数（归一化系数，乘以转速得到实际频率）"""
        n = self.n_rolling_elements
        d = self.rolling_element_diameter
        D = self.pitch_diameter
        theta = self.contact_angle
        
        self.coeff_ftf = 0.5 * (1 - (d / D) * np.cos(theta))
        self.coeff_bpfi = 0.5 * n * (1 + (d / D) * np.cos(theta))
        self.coeff_bpfo = 0.5 * n * (1 - (d / D) * np.cos(theta))
        self.coeff_bsf = (D / (2 * d)) * (1 - ((d / D) * np.cos(theta)) ** 2)
        
        self.fault_coefficients = {
            'ftf': self.coeff_ftf,
            'bpfi': self.coeff_bpfi,
            'bpfo': self.coeff_bpfo,
            'bsf': self.coeff_bsf
        }
    
    def calculate(self, rotational_speed: float) -> dict:
        """
        根据转速计算故障特征频率
        
        Args:
            rotational_speed: 转速 (Hz 或 RPM，如果是RPM会自动除以60)
        
        Returns:
            包含各故障频率的字典，同时包含归一化系数
        """
        if rotational_speed > 1000:
            warnings.warn("转速值较大，假设为RPM，将转换为Hz")
            rotational_speed = rotational_speed / 60.0
        
        fr = rotational_speed
        
        return {
            'rotational_frequency': fr,
            'ftf': fr * self.coeff_ftf,
            'bpfi': fr * self.coeff_bpfi,
            'bpfo': fr * self.coeff_bpfo,
            'bsf': fr * self.coeff_bsf,
            'coefficients': self.fault_coefficients,
            'normalized': {
                'ftf': self.coeff_ftf,
                'bpfi': self.coeff_bpfi,
                'bpfo': self.coeff_bpfo,
                'bsf': self.coeff_bsf
            }
        }
    
    def get_normalized_frequency(self, fault_type: str) -> float:
        """
        获取归一化故障频率系数（与转速无关）
        
        Args:
            fault_type: 故障类型 ('ftf', 'bpfi', 'bpfo', 'bsf')
        
        Returns:
            归一化频率系数（实际频率 = 系数 × 转速）
        """
        return self.fault_coefficients.get(fault_type, 0.0)
    
    def get_filter_band(self, rotational_speed: float,
                       fault_type: str = 'all',
                       bandwidth: float = 2.0) -> Tuple[float, float]:
        """
        获取带通滤波的频带范围
        
        Args:
            rotational_speed: 转速 (Hz)
            fault_type: 故障类型 ('all', 'inner', 'outer', 'rolling', 'cage')
            bandwidth: 带宽倍数
        
        Returns:
            (low_freq, high_freq) 滤波范围
        """
        freqs = self.calculate(rotational_speed)
        
        if fault_type == 'all':
            target_freqs = [freqs['bpfi'], freqs['bpfo'],
                           freqs['bsf'], freqs['ftf']]
            center_freq = np.mean(target_freqs)
            freq_range = max(target_freqs) - min(target_freqs)
        elif fault_type == 'inner':
            center_freq = freqs['bpfi']
        elif fault_type == 'outer':
            center_freq = freqs['bpfo']
        elif fault_type == 'rolling':
            center_freq = freqs['bsf']
        elif fault_type == 'cage':
            center_freq = freqs['ftf']
        else:
            raise ValueError(f"未知的故障类型: {fault_type}")
        
        low_freq = max(1.0, center_freq - bandwidth * freqs['rotational_frequency'])
        high_freq = center_freq + bandwidth * freqs['rotational_frequency'] * 5
        
        return low_freq, high_freq


class Preprocessor:
    """
    振动信号预处理
    
    包含去趋势、带通滤波、包络解调、自适应去噪等功能
    增强的早期故障检测能力：谱峭度、自适应滤波、同步平均
    """
    
    def __init__(self, fs: float, detrend_method: str = 'linear',
                 use_spectral_kurtosis: bool = True,
                 use_adaptive_filter: bool = False,
                 n_fft_kurtosis: int = 1024):
        """
        Args:
            fs: 采样频率 (Hz)
            detrend_method: 去趋势方法 ('linear', 'constant')
            use_spectral_kurtosis: 是否使用谱峭度寻找最优滤波频带（默认启用，对早期故障有效）
            use_adaptive_filter: 是否使用自适应滤波增强早期故障（默认禁用，可能削除微弱信号）
            n_fft_kurtosis: 谱峭度计算的FFT长度
        """
        self.fs = fs
        self.detrend_method = detrend_method
        self.use_spectral_kurtosis = use_spectral_kurtosis
        self.use_adaptive_filter = use_adaptive_filter
        self.n_fft_kurtosis = n_fft_kurtosis
        self.optimal_band_: Optional[Tuple[float, float]] = None
        self.spectral_kurtosis_: Optional[np.ndarray] = None
    
    def remove_trend(self, signal_data: np.ndarray) -> np.ndarray:
        """
        去趋势处理
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
        
        Returns:
            去趋势后的信号
        """
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(-1, 1)
        
        detrended = np.zeros_like(signal_data)
        for i in range(signal_data.shape[1]):
            if self.detrend_method == 'linear':
                detrended[:, i] = detrend(signal_data[:, i], type='linear')
            elif self.detrend_method == 'constant':
                detrended[:, i] = detrend(signal_data[:, i], type='constant')
            else:
                raise ValueError(f"未知的去趋势方法: {self.detrend_method}")
        
        return detrended
    
    def bandpass_filter(self, signal_data: np.ndarray,
                       low_freq: float, high_freq: float,
                       order: int = 4) -> np.ndarray:
        """
        带通滤波
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
            low_freq: 低截止频率 (Hz)
            high_freq: 高截止频率 (Hz)
            order: 滤波器阶数
        
        Returns:
            滤波后的信号
        """
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(-1, 1)
        
        nyquist = 0.5 * self.fs
        low = low_freq / nyquist
        high = high_freq / nyquist
        
        if low <= 0 or high >= 1:
            warnings.warn(f"滤波范围 [{low_freq}, {high_freq}] Hz 超出有效范围，"
                         f"将自动调整")
            low = max(0.001, low)
            high = min(0.999, high)
        
        b, a = butter(order, [low, high], btype='band')
        
        filtered = np.zeros_like(signal_data)
        for i in range(signal_data.shape[1]):
            filtered[:, i] = filtfilt(b, a, signal_data[:, i])
        
        return filtered
    
    def envelope_detection(self, signal_data: np.ndarray) -> np.ndarray:
        """
        包络检测（希尔伯特变换）
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
        
        Returns:
            包络信号
        """
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(-1, 1)
        
        envelope = np.zeros_like(signal_data)
        for i in range(signal_data.shape[1]):
            analytic = signal.hilbert(signal_data[:, i])
            envelope[:, i] = np.abs(analytic)
        
        return envelope
    
    def compute_spectral_kurtosis(self, signal_data: np.ndarray,
                                  window: str = 'hann') -> Tuple[np.ndarray, np.ndarray]:
        """
        计算谱峭度，用于寻找最优共振频带（增强早期故障检测）
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
            window: 窗函数类型
        
        Returns:
            (freq_axis, spectral_kurtosis) - 每个频段的峭度值
        """
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(-1, 1)
        
        n_samples = signal_data.shape[0]
        nfft = self.n_fft_kurtosis
        hop_length = nfft // 4
        
        freq_axis = np.fft.rfftfreq(nfft, 1.0 / self.fs)
        sk = np.zeros((len(freq_axis), signal_data.shape[1]))
        
        for chan in range(signal_data.shape[1]):
            x = signal_data[:, chan]
            
            n_frames = (n_samples - nfft) // hop_length + 1
            frames = np.zeros((n_frames, nfft // 2 + 1), dtype=np.complex128)
            
            win = signal.get_window(window, nfft)
            
            for i in range(n_frames):
                start = i * hop_length
                frame = x[start:start + nfft] * win
                frames[i, :] = np.fft.rfft(frame)
            
            spec_mag = np.abs(frames)
            
            with np.errstate(divide='ignore', invalid='ignore'):
                mean_mag = np.mean(spec_mag, axis=0)
                var_mag = np.var(spec_mag, axis=0)
                kurt = np.where(mean_mag > 0,
                               var_mag / (mean_mag ** 2) - 2,
                               0)
            
            sk[:, chan] = kurt
        
        self.spectral_kurtosis_ = sk
        return freq_axis, sk
    
    def find_optimal_resonance_band(self, signal_data: np.ndarray,
                                    min_bandwidth: float = 200.0,
                                    max_bandwidth: float = 2000.0,
                                    threshold: float = 0.5) -> Tuple[float, float]:
        """
        基于谱峭度寻找最优共振频带（用于早期故障的带通滤波）
        
        Args:
            signal_data: 输入信号
            min_bandwidth: 最小带宽 (Hz)
            max_bandwidth: 最大带宽 (Hz)
            threshold: 峭度阈值（相对于最大值）
        
        Returns:
            (low_freq, high_freq) 最优频带
        """
        freq_axis, sk = self.compute_spectral_kurtosis(signal_data)
        
        sk_mean = np.mean(sk, axis=1)
        max_sk = np.max(sk_mean)
        
        if max_sk < 1e-6:
            nyquist = self.fs / 2
            return nyquist * 0.1, nyquist * 0.4
        
        threshold_value = max_sk * threshold
        mask = sk_mean >= threshold_value
        
        if not np.any(mask):
            nyquist = self.fs / 2
            return nyquist * 0.1, nyquist * 0.4
        
        freq_indices = np.where(mask)[0]
        center_idx = freq_indices[np.argmax(sk_mean[freq_indices])]
        center_freq = freq_axis[center_idx]
        
        bandwidth = min(max_bandwidth, max(min_bandwidth, center_freq * 0.5))
        
        low_freq = max(1.0, center_freq - bandwidth / 2)
        high_freq = min(self.fs / 2 - 1.0, center_freq + bandwidth / 2)
        
        self.optimal_band_ = (low_freq, high_freq)
        return low_freq, high_freq
    
    def adaptive_line_enhancer(self, signal_data: np.ndarray,
                               order: int = 16, mu: float = 0.001) -> np.ndarray:
        """
        自适应谱线增强器 (ALE) - 抑制噪声，增强周期性分量
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
            order: 滤波器阶数
            mu: 学习率（需要小一些避免发散）
        
        Returns:
            增强后的信号
        """
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(-1, 1)
        
        n_samples, n_channels = signal_data.shape
        enhanced = np.zeros_like(signal_data)
        
        for chan in range(n_channels):
            x = signal_data[:, chan]
            delay = max(1, int(self.fs / 1000))
            
            y = np.zeros(n_samples)
            w = np.zeros(order)
            
            max_val = np.max(np.abs(x))
            if max_val > 1e-6:
                x_norm = x / max_val
            else:
                x_norm = x
            
            for i in range(order + delay, n_samples):
                start_idx = i - order - delay
                end_idx = i - delay
                x_vec = x_norm[start_idx:end_idx][::-1].copy()
                
                x_vec_norm = np.linalg.norm(x_vec)
                if x_vec_norm > 1e-6:
                    x_vec_normalized = x_vec / x_vec_norm
                else:
                    x_vec_normalized = x_vec
                
                y[i] = np.dot(w, x_vec_normalized)
                error = x_norm[i] - y[i]
                
                w = w + 2 * mu * error * x_vec_normalized
                
                w = np.clip(w, -10, 10)
            
            enhanced[:, chan] = y * max_val
        
        return enhanced
    
    def synchronous_average(self, signal_data: np.ndarray,
                           rotational_speed: float,
                           n_rotations: int = 10) -> np.ndarray:
        """
        同步平均 - 按旋转周期平均，抑制非同步噪声
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
            rotational_speed: 转速 (Hz)
            n_rotations: 平均的旋转周期数
        
        Returns:
            同步平均后的信号
        """
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(-1, 1)
        
        n_samples, n_channels = signal_data.shape
        samples_per_rotation = int(self.fs / rotational_speed)
        
        usable_samples = (n_samples // samples_per_rotation) * samples_per_rotation
        signal_reshaped = signal_data[:usable_samples].reshape(
            -1, samples_per_rotation, n_channels
        )
        
        if len(signal_reshaped) >= n_rotations:
            n_segments = len(signal_reshaped) // n_rotations
            averaged = np.zeros((n_segments * samples_per_rotation, n_channels))
            
            for i in range(n_segments):
                segment = signal_reshaped[i * n_rotations:(i + 1) * n_rotations]
                averaged[i * samples_per_rotation:(i + 1) * samples_per_rotation] = \
                    np.mean(segment, axis=0)
            
            return averaged
        else:
            return np.mean(signal_reshaped, axis=0).reshape(-1, n_channels)
    
    def envelope_spectrum(self, signal_data: np.ndarray,
                         low_freq: Optional[float] = None,
                         high_freq: Optional[float] = None,
                         enhance: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算包络谱（增强版，支持早期故障）
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
            low_freq: 低截止频率 (Hz)，用于共振解调
            high_freq: 高截止频率 (Hz)，用于共振解调
            enhance: 是否启用增强处理（自适应滤波等）
        
        Returns:
            (freq_axis, envelope_spectrum)
        """
        processed = signal_data.copy()
        
        if enhance and self.use_adaptive_filter:
            try:
                processed = self.adaptive_line_enhancer(processed)
            except:
                pass
        
        if low_freq is None and high_freq is None and self.use_spectral_kurtosis:
            try:
                low_freq, high_freq = self.find_optimal_resonance_band(processed)
            except:
                pass
        
        if low_freq is not None and high_freq is not None:
            processed = self.bandpass_filter(processed, low_freq, high_freq)
        
        envelope = self.envelope_detection(processed)
        envelope_detrended = self.remove_trend(envelope)
        
        n_samples = envelope_detrended.shape[0]
        nfft = n_samples
        freq_axis = np.fft.rfftfreq(nfft, 1.0 / self.fs)
        
        spec = np.zeros((len(freq_axis), envelope_detrended.shape[1]))
        for i in range(envelope_detrended.shape[1]):
            spec[:, i] = np.abs(np.fft.rfft(envelope_detrended[:, i], n=nfft))
        
        return freq_axis, spec
    
    def preprocess(self, signal_data: np.ndarray,
                  low_freq: Optional[float] = None,
                  high_freq: Optional[float] = None,
                  rotational_speed: Optional[float] = None,
                  enhance_early_fault: bool = True,
                  return_envelope: bool = False) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """
        完整的预处理流程（增强版，支持早期故障检测）
        
        Args:
            signal_data: 输入信号 (n_samples, n_channels)
            low_freq: 带通滤波低截止频率 (Hz)，None则自动计算
            high_freq: 带通滤波高截止频率 (Hz)
            rotational_speed: 转速 (Hz)，用于同步平均
            enhance_early_fault: 是否启用早期故障增强处理
            return_envelope: 是否返回包络信号
        
        Returns:
            预处理后的信号，或 (预处理信号, 包络信号)
        """
        processed = self.remove_trend(signal_data)
        
        if enhance_early_fault and self.use_spectral_kurtosis:
            try:
                low_freq, high_freq = self.find_optimal_resonance_band(processed)
            except:
                pass
        
        if low_freq is not None and high_freq is not None:
            processed = self.bandpass_filter(processed, low_freq, high_freq)
        
        if enhance_early_fault and rotational_speed is not None:
            try:
                processed = self.synchronous_average(processed, rotational_speed)
            except:
                pass
        
        if enhance_early_fault and self.use_adaptive_filter:
            try:
                enhanced = self.adaptive_line_enhancer(processed)
                max_processed = np.max(np.abs(processed))
                max_enhanced = np.max(np.abs(enhanced))
                if max_enhanced > 1e-6 and max_enhanced < max_processed * 100:
                    processed = 0.3 * processed + 0.7 * enhanced
            except:
                pass
        
        if return_envelope:
            envelope = self.envelope_detection(processed)
            return processed, envelope
        
        return processed
