import numpy as np
from typing import Tuple, List, Optional, Union
import warnings

from .preprocessing import Preprocessor, BearingFaultFrequency
from .feature_extraction import FeatureExtractor


def generate_bearing_signal(fs: float, duration: float,
                           fault_type: Union[str, List[str]] = 'normal',
                           severity: Union[str, List[str]] = 'normal',
                           n_channels: int = 1,
                           rotational_speed: float = 50.0,
                           n_rolling_elements: int = 9,
                           pitch_diameter: float = 39.04,
                           rolling_element_diameter: float = 7.94,
                           contact_angle: float = 0.0,
                           noise_level: float = 0.5,
                           random_state: Optional[int] = None) -> np.ndarray:
    """
    生成模拟的轴承振动信号（支持多故障同时存在）
    
    Args:
        fs: 采样频率 (Hz)
        duration: 信号时长 (秒)
        fault_type: 故障类型，支持字符串或列表（如 ['outer_race', 'rolling_element']）
        severity: 严重程度，与fault_type对应（如 ['early', 'medium']）
        n_channels: 通道数
        rotational_speed: 转速 (Hz)
        n_rolling_elements: 滚动体数量
        pitch_diameter: 节径 (mm)
        rolling_element_diameter: 滚动体直径 (mm)
        contact_angle: 接触角 (度)
        noise_level: 噪声水平
        random_state: 随机种子
    
    Returns:
        振动信号 (n_samples, n_channels)
    """
    if random_state is not None:
        np.random.seed(random_state)
    
    if isinstance(fault_type, str):
        fault_type = [fault_type]
    if isinstance(severity, str):
        severity = [severity] * len(fault_type)
    
    if len(severity) != len(fault_type):
        severity = severity * len(fault_type)
        severity = severity[:len(fault_type)]
    
    n_samples = int(fs * duration)
    t = np.arange(n_samples) / fs
    
    bearing = BearingFaultFrequency(
        n_rolling_elements=n_rolling_elements,
        pitch_diameter=pitch_diameter,
        rolling_element_diameter=rolling_element_diameter,
        contact_angle=contact_angle
    )
    fault_freqs = bearing.calculate(rotational_speed)
    
    fault_freq_map = {
        'inner_race': 'bpfi',
        'outer_race': 'bpfo',
        'rolling_element': 'bsf',
        'cage': 'ftf'
    }
    
    amplitude_factor_map = {'normal': 0.1, 'early': 0.3, 'medium': 0.6, 'late': 1.0}
    
    signals = []
    
    for ch in range(n_channels):
        signal = np.zeros(n_samples)
        
        signal += np.sin(2 * np.pi * rotational_speed * t) * 0.5
        signal += np.sin(2 * np.pi * 2 * rotational_speed * t) * 0.2
        signal += np.sin(2 * np.pi * 3 * rotational_speed * t) * 0.1
        
        for ft, sev in zip(fault_type, severity):
            if ft == 'normal':
                continue
            
            fault_freq_key = fault_freq_map.get(ft)
            if fault_freq_key is None:
                continue
            fault_freq = fault_freqs[fault_freq_key]
            
            amplitude_factor = amplitude_factor_map.get(sev, 0.3)
            
            n_harmonics = 5
            for h in range(1, n_harmonics + 1):
                amplitude = amplitude_factor / (h ** 0.8)
                signal += amplitude * np.sin(2 * np.pi * h * fault_freq * t)
                
                for s in [-2, -1, 1, 2]:
                    side_freq = h * fault_freq + s * rotational_speed
                    signal += amplitude * 0.3 * np.sin(2 * np.pi * side_freq * t)
            
            if sev in ['medium', 'late']:
                modulation_freq = rotational_speed
                modulation = 1 + 0.3 * np.sin(2 * np.pi * modulation_freq * t)
                signal = signal * modulation
            
            if sev == 'late':
                impulse_intensity = amplitude_factor * 2
                impulse_interval = int(fs / fault_freq)
                for i in range(0, n_samples, impulse_interval):
                    if i + 50 < n_samples:
                        impulse = impulse_intensity * np.exp(-np.arange(50) / 10) \
                                * np.sin(2 * np.pi * 5000 * np.arange(50) / fs)
                        signal[i:i+50] += impulse
        
        noise = np.random.randn(n_samples) * noise_level
        signal += noise
        
        signals.append(signal)
    
    return np.array(signals).T


def generate_bearing_dataset(n_samples: int,
                            n_channels: int = 1,
                            fs: float = 25600.0,
                            duration: float = 1.0,
                            extract_features: bool = True,
                            wavelet: str = 'db4',
                            wavelet_level: int = 4,
                            include_multi_fault: bool = True,
                            multi_fault_ratio: float = 0.2,
                            random_state: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str], List[List[str]]]:
    """
    生成完整的轴承故障数据集（支持多故障样本）
    
    Args:
        n_samples: 样本数量
        n_channels: 通道数
        fs: 采样频率 (Hz)
        duration: 信号时长 (秒)
        extract_features: 是否提取特征
        wavelet: 小波基函数
        wavelet_level: 小波包分解层数
        include_multi_fault: 是否包含多故障样本
        multi_fault_ratio: 多故障样本占比
        random_state: 随机种子
    
    Returns:
        (X, y_type, y_severity, feature_names, y_type_multi)
        y_type: 主故障类型标签（用于单标签分类）
        y_type_multi: 所有故障类型列表（用于多标签参考）
    """
    if random_state is not None:
        np.random.seed(random_state)
    
    fault_types = ['normal', 'inner_race', 'outer_race', 'rolling_element', 'cage']
    severities = ['normal', 'early', 'medium', 'late']
    
    n_multi_fault = int(n_samples * multi_fault_ratio) if include_multi_fault else 0
    n_single_fault = n_samples - n_multi_fault
    
    n_per_class = n_single_fault // (len(fault_types) * len(severities))
    
    X_list = []
    y_type_list = []
    y_severity_list = []
    y_type_multi_list = []
    
    preprocessor = Preprocessor(fs=fs)
    
    bearing = BearingFaultFrequency(
        n_rolling_elements=9,
        pitch_diameter=39.04,
        rolling_element_diameter=7.94,
        contact_angle=0.0
    )
    fault_freqs = bearing.calculate(50.0)
    low_freq, high_freq = bearing.get_filter_band(50.0)
    
    feature_names = []
    
    for fault_type in fault_types:
        for severity in severities:
            actual_severity = 'normal' if fault_type == 'normal' else severity
            
            for _ in range(n_per_class):
                signal = generate_bearing_signal(
                    fs=fs,
                    duration=duration,
                    fault_type=fault_type,
                    severity=actual_severity,
                    n_channels=n_channels
                )
                
                processed = preprocessor.preprocess(
                    signal, low_freq=low_freq, high_freq=high_freq,
                    enhance_early_fault=True
                )
                
                if extract_features:
                    extractor = FeatureExtractor(
                        fs=fs,
                        wavelet=wavelet,
                        wavelet_level=wavelet_level
                    )
                    features, feature_names = extractor.extract(processed, fault_freqs)
                    X_list.append(features.flatten())
                else:
                    X_list.append(processed.flatten())
                
                y_type_list.append(fault_type)
                y_severity_list.append(actual_severity)
                y_type_multi_list.append([fault_type])
    
    if include_multi_fault:
        single_faults = ['inner_race', 'outer_race', 'rolling_element', 'cage']
        
        for _ in range(n_multi_fault):
            n_faults = np.random.randint(2, 4)
            selected_faults = np.random.choice(single_faults, size=n_faults, replace=False).tolist()
            selected_severities = np.random.choice(
                ['early', 'medium', 'late'],
                size=n_faults,
                replace=True
            ).tolist()
            
            signal = generate_bearing_signal(
                fs=fs,
                duration=duration,
                fault_type=selected_faults,
                severity=selected_severities,
                n_channels=n_channels
            )
            
            processed = preprocessor.preprocess(
                signal, low_freq=low_freq, high_freq=high_freq,
                enhance_early_fault=True
            )
            
            if extract_features:
                extractor = FeatureExtractor(
                    fs=fs,
                    wavelet=wavelet,
                    wavelet_level=wavelet_level
                )
                features, feature_names = extractor.extract(processed, fault_freqs)
                X_list.append(features.flatten())
            else:
                X_list.append(processed.flatten())
            
            main_fault = selected_faults[0]
            main_severity = selected_severities[0]
            y_type_list.append(main_fault)
            y_severity_list.append(main_severity)
            y_type_multi_list.append(selected_faults)
    
    X = np.array(X_list)
    y_type = np.array(y_type_list)
    y_severity = np.array(y_severity_list)
    y_type_multi = [y_type_multi_list[i] for i in range(len(y_type_multi_list))]
    
    shuffle_idx = np.random.permutation(len(X))
    X = X[shuffle_idx]
    y_type = y_type[shuffle_idx]
    y_severity = y_severity[shuffle_idx]
    y_type_multi = [y_type_multi_list[i] for i in shuffle_idx]
    
    return X, y_type, y_severity, feature_names, y_type_multi
