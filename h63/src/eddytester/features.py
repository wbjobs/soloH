import numpy as np
from typing import Union, List, Tuple, Dict, Optional
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from scipy import signal
from scipy.stats import skew, kurtosis
from .data_io import EddyCurrentData
from .config import Config


class ImpedanceFeatures:
    @staticmethod
    def extract_amplitude(impedance: np.ndarray) -> np.ndarray:
        return np.abs(impedance)

    @staticmethod
    def extract_phase(impedance: np.ndarray) -> np.ndarray:
        return np.angle(impedance)

    @staticmethod
    def extract_phase_degrees(impedance: np.ndarray) -> np.ndarray:
        return np.degrees(np.angle(impedance))

    @staticmethod
    def extract_rotating_phase(impedance: np.ndarray, reference_idx: int = 0) -> np.ndarray:
        phase = np.angle(impedance)
        reference_phase = phase[reference_idx]
        return phase - reference_phase

    @staticmethod
    def extract_trajectory_length(impedance: np.ndarray) -> np.ndarray:
        if impedance.ndim == 1:
            impedance = impedance.reshape(-1, 1)
        
        real = np.real(impedance)
        imag = np.imag(impedance)
        lengths = np.zeros_like(impedance, dtype=float)
        
        for freq in range(impedance.shape[1]):
            dx = np.diff(real[:, freq], prepend=real[0, freq])
            dy = np.diff(imag[:, freq], prepend=imag[0, freq])
            lengths[:, freq] = np.sqrt(dx**2 + dy**2)
        
        return lengths

    @staticmethod
    def extract_derivatives(impedance: np.ndarray, order: int = 1) -> np.ndarray:
        real = np.real(impedance)
        imag = np.imag(impedance)
        
        d_real = np.zeros_like(real)
        d_imag = np.zeros_like(imag)
        
        for i in range(real.shape[1]):
            d_real[:, i] = np.gradient(real[:, i], edge_order=2)
            d_imag[:, i] = np.gradient(imag[:, i], edge_order=2)
        
        if order == 1:
            return d_real + 1j * d_imag
        else:
            second_deriv = np.zeros_like(real, dtype=complex)
            for i in range(real.shape[1]):
                d2_real = np.gradient(d_real[:, i], edge_order=2)
                d2_imag = np.gradient(d_imag[:, i], edge_order=2)
                second_deriv[:, i] = d2_real + 1j * d2_imag
            return second_deriv

    @staticmethod
    def extract_statistical_features(impedance: np.ndarray, window_size: int = 50) -> np.ndarray:
        n_samples, n_freqs = impedance.shape
        features = []
        
        for freq in range(n_freqs):
            real = np.real(impedance[:, freq])
            imag = np.imag(impedance[:, freq])
            amp = np.abs(impedance[:, freq])
            ph = np.angle(impedance[:, freq])
            
            for sig, name in [(real, 'real'), (imag, 'imag'), (amp, 'amp'), (ph, 'phase')]:
                features.extend([
                    np.mean(sig),
                    np.std(sig),
                    np.min(sig),
                    np.max(sig),
                    np.ptp(sig),
                    np.median(sig),
                    skew(sig),
                    kurtosis(sig),
                    np.sqrt(np.mean(sig**2)),
                ])
        
        return np.array(features)

    @staticmethod
    def extract_spectral_features(impedance: np.ndarray, fs: float = Config.SAMPLING_RATE) -> np.ndarray:
        n_samples, n_freqs = impedance.shape
        features = []
        
        for freq in range(n_freqs):
            real = np.real(impedance[:, freq])
            imag = np.imag(impedance[:, freq])
            
            for sig in [real, imag]:
                freqs, psd = signal.welch(sig, fs=fs, nperseg=min(256, n_samples))
                spectral_centroid = np.sum(freqs * psd) / np.sum(psd) if np.sum(psd) > 0 else 0
                spectral_spread = np.sqrt(np.sum(((freqs - spectral_centroid)**2) * psd) / np.sum(psd)) if np.sum(psd) > 0 else 0
                spectral_rolloff = freqs[np.where(np.cumsum(psd) >= 0.85 * np.sum(psd))[0][0]] if np.sum(psd) > 0 else 0
                
                features.extend([spectral_centroid, spectral_spread, spectral_rolloff])
        
        return np.array(features)


class MultiFrequencyFusion:
    def __init__(self, n_components: int = Config.PCA_N_COMPONENTS, method: str = 'pca'):
        self.n_components = n_components
        self.method = method
        self.pca = None
        self.scaler = StandardScaler()
        self.fitted = False
        self.actual_n_components = n_components

    def fit(self, data: Union[EddyCurrentData, np.ndarray]) -> 'MultiFrequencyFusion':
        features = self._extract_features_for_fusion(data)
        scaled_features = self.scaler.fit_transform(features)
        
        n_samples, n_features = scaled_features.shape
        self.actual_n_components = min(self.n_components, n_samples - 1, n_features)
        if self.actual_n_components < 1:
            self.actual_n_components = 1
        
        self.pca = PCA(n_components=self.actual_n_components)
        self.pca.fit(scaled_features)
        self.fitted = True
        return self

    def transform(self, data: Union[EddyCurrentData, np.ndarray]) -> np.ndarray:
        if not self.fitted:
            raise ValueError("MultiFrequencyFusion not fitted. Call fit() first.")
        
        features = self._extract_features_for_fusion(data)
        scaled_features = self.scaler.transform(features)
        return self.pca.transform(scaled_features)

    def fit_transform(self, data: Union[EddyCurrentData, np.ndarray]) -> np.ndarray:
        return self.fit(data).transform(data)

    def _extract_features_for_fusion(self, data: Union[EddyCurrentData, np.ndarray]) -> np.ndarray:
        if isinstance(data, EddyCurrentData):
            impedance = data.impedance
        else:
            impedance = data
        
        if impedance.ndim == 3:
            n_samples, n_positions, n_freqs = impedance.shape
            features_list = []
            for i in range(n_samples):
                sample_feats = []
                for f in range(n_freqs):
                    real = np.real(impedance[i, :, f])
                    imag = np.imag(impedance[i, :, f])
                    amp = np.abs(impedance[i, :, f])
                    ph = np.angle(impedance[i, :, f])
                    for sig in [real, imag, amp, ph]:
                        sample_feats.extend([
                            np.mean(sig), np.std(sig), np.max(sig), np.min(sig),
                            np.median(sig), np.ptp(sig)
                        ])
                features_list.append(sample_feats)
            features = np.array(features_list)
        elif impedance.ndim == 2:
            n_points, n_freqs = impedance.shape
            features_list = []
            for f in range(n_freqs):
                real = np.real(impedance[:, f])
                imag = np.imag(impedance[:, f])
                amp = np.abs(impedance[:, f])
                ph = np.angle(impedance[:, f])
                for sig in [real, imag, amp, ph]:
                    features_list.extend([
                        np.mean(sig), np.std(sig), np.max(sig), np.min(sig),
                        np.median(sig), np.ptp(sig)
                    ])
            features = np.array(features_list).reshape(1, -1)
        else:
            raise ValueError(f"Unsupported impedance dimension: {impedance.ndim}")
        
        return features

    def get_explained_variance_ratio(self) -> np.ndarray:
        if not self.fitted:
            raise ValueError("MultiFrequencyFusion not fitted.")
        return self.pca.explained_variance_ratio_


class FeatureExtractor:
    def __init__(self,
                 include_amplitude: bool = True,
                 include_phase: bool = True,
                 include_derivatives: bool = True,
                 include_trajectory: bool = True,
                 include_statistics: bool = False,
                 fusion: Optional[MultiFrequencyFusion] = None):
        self.include_amplitude = include_amplitude
        self.include_phase = include_phase
        self.include_derivatives = include_derivatives
        self.include_trajectory = include_trajectory
        self.include_statistics = include_statistics
        self.fusion = fusion or MultiFrequencyFusion()

    def extract(self, data: EddyCurrentData) -> Dict[str, np.ndarray]:
        impedance = data.impedance
        features = {}
        
        if self.include_amplitude:
            features['amplitude'] = ImpedanceFeatures.extract_amplitude(impedance)
        
        if self.include_phase:
            features['phase'] = ImpedanceFeatures.extract_phase(impedance)
            features['phase_degrees'] = ImpedanceFeatures.extract_phase_degrees(impedance)
            features['rotating_phase'] = ImpedanceFeatures.extract_rotating_phase(impedance)
        
        if self.include_derivatives:
            features['derivative_1st'] = ImpedanceFeatures.extract_derivatives(impedance, order=1)
            features['derivative_2nd'] = ImpedanceFeatures.extract_derivatives(impedance, order=2)
        
        if self.include_trajectory:
            features['trajectory_length'] = ImpedanceFeatures.extract_trajectory_length(impedance)
        
        if self.include_statistics:
            features['statistics'] = ImpedanceFeatures.extract_statistical_features(impedance)
            features['spectral'] = ImpedanceFeatures.extract_spectral_features(impedance)
        
        features['fused'] = self.fusion.fit_transform(data)
        
        return features

    def extract_for_classification(self, data: EddyCurrentData, window_size: int = 50, step: int = 25) -> np.ndarray:
        impedance = data.impedance
        n_samples, n_freqs = impedance.shape
        
        features_list = []
        
        for start in range(0, n_samples - window_size + 1, step):
            end = start + window_size
            window = impedance[start:end]
            
            feat = []
            
            for freq in range(n_freqs):
                w = window[:, freq]
                real = np.real(w)
                imag = np.imag(w)
                amp = np.abs(w)
                ph = np.angle(w)
                
                feat.extend([
                    np.mean(real), np.std(real), np.max(real), np.min(real),
                    np.mean(imag), np.std(imag), np.max(imag), np.min(imag),
                    np.mean(amp), np.std(amp), np.max(amp), np.min(amp),
                    np.mean(ph), np.std(ph), np.ptp(ph), np.ptp(amp),
                ])
            
            features_list.append(feat)
        
        return np.array(features_list)

    def extract_single(self, data: EddyCurrentData) -> np.ndarray:
        features = self.extract(data)
        
        flat_features = []
        
        for key in ['amplitude', 'phase', 'phase_degrees', 'rotating_phase', 'trajectory_length']:
            if key in features:
                feat = features[key]
                flat_features.extend([
                    np.mean(feat),
                    np.std(feat),
                    np.max(feat),
                    np.min(feat),
                    np.median(feat),
                ])
        
        if 'derivative_1st' in features:
            d1 = features['derivative_1st']
            flat_features.append(np.mean(np.abs(d1)))
            flat_features.append(np.std(np.abs(d1)))
        
        if 'fused' in features:
            flat_features.extend(features['fused'].flatten())
        
        return np.array(flat_features)
