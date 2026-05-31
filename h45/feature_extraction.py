import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
from config import FeatureExtractionConfig
from utils import preemphasis, framing, windowing, softmax
from event_detection import KeyEvent


@dataclass
class RobustFeatures:
    spectral_centroid: float
    spectral_bandwidth: float
    spectral_rolloff: float
    mfcc: np.ndarray
    decay_rate: float
    attack_time: float
    zero_crossing_rate: float
    spectral_centroid_history: np.ndarray


@dataclass
class KeyFeatures:
    mel_spectrogram: np.ndarray
    tdoa_features: np.ndarray
    robust_features: RobustFeatures
    combined_features: np.ndarray
    whitened_features: np.ndarray
    event: KeyEvent


class SpectralWhitener:
    def __init__(self, epsilon: float = 1e-6):
        self.epsilon = epsilon
        self.mean = None
        self.std = None
        self.whitening_matrix = None
        self.is_fitted = False

    def fit(self, features: np.ndarray):
        n_samples = features.shape[0]
        
        self.mean = np.mean(features, axis=0)
        centered = features - self.mean
        
        self.std = np.std(features, axis=0) + self.epsilon
        normalized = centered / self.std
        
        cov_matrix = np.dot(normalized.T, normalized) / (n_samples - 1)
        
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        eigenvalues = np.maximum(eigenvalues, self.epsilon)
        
        self.whitening_matrix = np.dot(
            eigenvectors,
            np.dot(np.diag(1.0 / np.sqrt(eigenvalues)), eigenvectors.T)
        )
        
        self.is_fitted = True

    def transform(self, features: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            return features
        
        if len(features.shape) == 1:
            features = features.reshape(1, -1)
        
        centered = features - self.mean
        normalized = centered / self.std
        whitened = np.dot(normalized, self.whitening_matrix)
        
        return whitened


class MelSpectrogramExtractor:
    def __init__(self, config: FeatureExtractionConfig, sample_rate: int):
        self.config = config
        self.sample_rate = sample_rate
        self.mel_filterbank = self._create_mel_filterbank()
        self.dct_matrix = self._create_dct_matrix()

    def _create_mel_filterbank(self) -> np.ndarray:
        n_mels = self.config.n_mels
        n_fft = self.config.n_fft
        sample_rate = self.sample_rate
        fmin = self.config.fmin
        fmax = self.config.fmax if self.config.fmax else sample_rate / 2

        def hz_to_mel(hz):
            return 2595 * np.log10(1 + hz / 700)

        def mel_to_hz(mel):
            return 700 * (10 ** (mel / 2595) - 1)

        mel_min = hz_to_mel(fmin)
        mel_max = hz_to_mel(fmax)
        mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
        hz_points = mel_to_hz(mel_points)

        bin_points = np.floor((n_fft + 1) * hz_points / sample_rate).astype(int)

        filterbank = np.zeros((n_mels, int(n_fft / 2 + 1)))

        for m in range(1, n_mels + 1):
            f_m_minus = bin_points[m - 1]
            f_m = bin_points[m]
            f_m_plus = bin_points[m + 1]

            for k in range(f_m_minus, f_m):
                filterbank[m - 1, k] = (k - bin_points[m - 1]) / (bin_points[m] - bin_points[m - 1])
            for k in range(f_m, f_m_plus):
                filterbank[m - 1, k] = (bin_points[m + 1] - k) / (bin_points[m + 1] - bin_points[m])

        return filterbank

    def _create_dct_matrix(self) -> np.ndarray:
        n_mfcc = self.config.mfcc_coeffs
        n_mels = self.config.n_mels
        
        dct_matrix = np.zeros((n_mfcc, n_mels))
        for i in range(n_mfcc):
            for j in range(n_mels):
                dct_matrix[i, j] = np.cos(np.pi * i * (j + 0.5) / n_mels)
        
        dct_matrix[0] *= np.sqrt(1.0 / n_mels)
        dct_matrix[1:] *= np.sqrt(2.0 / n_mels)
        
        return dct_matrix

    def extract(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        audio_pre = preemphasis(audio)
        
        frames = framing(audio_pre, self.config.n_fft, self.config.hop_length)
        frames = windowing(frames, 'hamming')
        
        magnitude_spectrum = np.abs(np.fft.rfft(frames, axis=1))
        power_spectrum = magnitude_spectrum ** 2
        
        mel_spectrum = np.dot(power_spectrum, self.mel_filterbank.T)
        log_mel_spectrum = np.log(mel_spectrum + 1e-10)
        
        mfcc = np.dot(log_mel_spectrum, self.dct_matrix.T)
        
        mean = np.mean(log_mel_spectrum)
        std = np.std(log_mel_spectrum) + 1e-10
        normalized_mel = (log_mel_spectrum - mean) / std
        
        return normalized_mel, mfcc


class RobustFeatureExtractor:
    def __init__(self, config: FeatureExtractionConfig, sample_rate: int):
        self.config = config
        self.sample_rate = sample_rate
        self.whitener = SpectralWhitener(config.whitening_epsilon)

    def extract(self, audio: np.ndarray, mel_spectrum: np.ndarray) -> RobustFeatures:
        n_fft = self.config.n_fft
        hop_length = self.config.hop_length
        sample_rate = self.sample_rate
        
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
        
        frames = framing(audio, n_fft, hop_length)
        frames = windowing(frames, 'hamming')
        magnitude_spectrum = np.abs(np.fft.rfft(frames, axis=1))
        
        spectral_centroid = self._compute_spectral_centroid(
            magnitude_spectrum, freqs, self.config.spectral_centroid_order
        )
        spectral_bandwidth = self._compute_spectral_bandwidth(
            magnitude_spectrum, freqs, spectral_centroid
        )
        spectral_rolloff = self._compute_spectral_rolloff(
            magnitude_spectrum, freqs
        )
        zero_crossing_rate = self._compute_zero_crossing_rate(audio)
        decay_rate = self._compute_decay_rate(audio)
        attack_time = self._compute_attack_time(audio)
        
        mfcc = self._compute_mfcc_from_mel(mel_spectrum)
        
        return RobustFeatures(
            spectral_centroid=np.mean(spectral_centroid),
            spectral_bandwidth=np.mean(spectral_bandwidth),
            spectral_rolloff=np.mean(spectral_rolloff),
            mfcc=mfcc,
            decay_rate=decay_rate,
            attack_time=attack_time,
            zero_crossing_rate=zero_crossing_rate,
            spectral_centroid_history=spectral_centroid
        )

    def _compute_spectral_centroid(self, magnitude_spectrum: np.ndarray, 
                                     freqs: np.ndarray, order: int = 2) -> np.ndarray:
        weights = magnitude_spectrum ** order
        total_weight = np.sum(weights, axis=1) + 1e-10
        centroid = np.sum(weights * freqs, axis=1) / total_weight
        return centroid

    def _compute_spectral_bandwidth(self, magnitude_spectrum: np.ndarray,
                                    freqs: np.ndarray, centroid: np.ndarray) -> np.ndarray:
        weights = magnitude_spectrum ** 2
        total_weight = np.sum(weights, axis=1) + 1e-10
        
        diff = (freqs[np.newaxis, :] - centroid[:, np.newaxis]) ** 2
        bandwidth = np.sqrt(np.sum(weights * diff, axis=1) / total_weight)
        return bandwidth

    def _compute_spectral_rolloff(self, magnitude_spectrum: np.ndarray,
                                   freqs: np.ndarray, percentile: float = 0.85) -> np.ndarray:
        total_energy = np.sum(magnitude_spectrum, axis=1) + 1e-10
        cumulative_energy = np.cumsum(magnitude_spectrum, axis=1)
        
        rolloff = np.zeros(magnitude_spectrum.shape[0])
        for i in range(magnitude_spectrum.shape[0]):
            threshold = percentile * total_energy[i]
            idx = np.where(cumulative_energy[i] >= threshold)[0]
            if len(idx) > 0:
                rolloff[i] = freqs[idx[0]]
            else:
                rolloff[i] = freqs[-1]
        
        return rolloff

    def _compute_zero_crossing_rate(self, audio: np.ndarray) -> float:
        crossings = np.sum(np.abs(np.diff(np.sign(audio))))
        return crossings / (2 * len(audio))

    def _compute_decay_rate(self, audio: np.ndarray) -> float:
        energy = audio ** 2
        peak_idx = np.argmax(energy)
        
        if peak_idx >= len(energy) - 1:
            return 0.0
        
        decay_curve = energy[peak_idx:]
        if len(decay_curve) < 2:
            return 0.0
        
        log_decay = np.log(decay_curve + 1e-10)
        
        t = np.arange(len(log_decay))
        slope = np.polyfit(t, log_decay, 1)[0]
        
        return -slope * self.sample_rate

    def _compute_attack_time(self, audio: np.ndarray) -> float:
        energy = audio ** 2
        peak_idx = np.argmax(energy)
        peak_energy = energy[peak_idx]
        
        threshold = 0.1 * peak_energy
        start_idx = 0
        
        for i in range(peak_idx, -1, -1):
            if energy[i] < threshold:
                start_idx = i
                break
        
        attack_samples = peak_idx - start_idx
        return attack_samples / self.sample_rate

    def _compute_mfcc_from_mel(self, mel_spectrum: np.ndarray) -> np.ndarray:
        if len(mel_spectrum) == 0:
            return np.zeros(self.config.mfcc_coeffs)
        
        n_mfcc = self.config.mfcc_coeffs
        n_mels = mel_spectrum.shape[1]
        
        dct_matrix = np.zeros((n_mfcc, n_mels))
        for i in range(n_mfcc):
            for j in range(n_mels):
                dct_matrix[i, j] = np.cos(np.pi * i * (j + 0.5) / n_mels)
        
        dct_matrix[0] *= np.sqrt(1.0 / n_mels)
        dct_matrix[1:] *= np.sqrt(2.0 / n_mels)
        
        mfcc = np.dot(np.mean(mel_spectrum, axis=0), dct_matrix.T)
        
        return mfcc

    def fit_whitener(self, all_features: np.ndarray):
        self.whitener.fit(all_features)


class TDOAExtractor:
    def __init__(self, config: FeatureExtractionConfig, sample_rate: int, num_channels: int):
        self.config = config
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.max_delay_bins = config.tdoa_max_delay_bins
        self.window_size = config.tdoa_window_size

    def extract(self, multi_channel_audio: np.ndarray, reference_channel: int = 0) -> np.ndarray:
        if len(multi_channel_audio.shape) == 1:
            return np.zeros(self.max_delay_bins * 2)
        
        num_channels = multi_channel_audio.shape[0]
        tdoa_features = []
        
        ref_audio = multi_channel_audio[reference_channel]
        
        for ch in range(num_channels):
            if ch == reference_channel:
                continue
            
            ch_audio = multi_channel_audio[ch]
            
            tdoa = self._compute_tdoa_gcc_phat(ref_audio, ch_audio)
            tdoa_features.extend(tdoa)
        
        return np.array(tdoa_features)

    def _compute_tdoa_gcc_phat(self, sig1: np.ndarray, sig2: np.ndarray) -> np.ndarray:
        max_len = max(len(sig1), len(sig2))
        pad_len = 1
        while pad_len < 2 * max_len - 1:
            pad_len *= 2
        
        sig1_pad = np.zeros(pad_len)
        sig2_pad = np.zeros(pad_len)
        sig1_pad[:len(sig1)] = sig1
        sig2_pad[:len(sig2)] = sig2
        
        X1 = np.fft.fft(sig1_pad)
        X2 = np.fft.fft(sig2_pad)
        
        X = X1 * np.conj(X2)
        denom = np.abs(X) + 1e-10
        X = X / denom
        
        correlation = np.fft.ifft(X)
        correlation = np.real(correlation)
        correlation = np.fft.fftshift(correlation)
        
        center = len(correlation) // 2
        start = center - self.max_delay_bins
        end = center + self.max_delay_bins
        tdoa = correlation[start:end]
        
        tdoa = tdoa / (np.max(np.abs(tdoa)) + 1e-10)
        
        return tdoa

    def extract_peak_tdoa(self, multi_channel_audio: np.ndarray, 
                          reference_channel: int = 0) -> np.ndarray:
        tdoa_features = self.extract(multi_channel_audio, reference_channel)
        
        feature_len = self.max_delay_bins * 2
        num_pairs = len(tdoa_features) // feature_len
        
        peak_delays = []
        
        for i in range(num_pairs):
            start = i * feature_len
            end = start + feature_len
            pair_feature = tdoa_features[start:end]
            
            peak_idx = np.argmax(np.abs(pair_feature))
            delay = (peak_idx - self.max_delay_bins) / self.sample_rate
            peak_delays.append(delay)
            peak_delays.append(pair_feature[peak_idx])
        
        return np.array(peak_delays)


class FeatureExtractor:
    def __init__(self, config: FeatureExtractionConfig, sample_rate: int, num_channels: int):
        self.config = config
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.mel_extractor = MelSpectrogramExtractor(config, sample_rate)
        self.tdoa_extractor = TDOAExtractor(config, sample_rate, num_channels)
        self.robust_extractor = RobustFeatureExtractor(config, sample_rate)

    def extract(self, event: KeyEvent, multi_channel_audio: Optional[np.ndarray] = None) -> KeyFeatures:
        mel_spec, _ = self.mel_extractor.extract(event.audio)
        
        if multi_channel_audio is not None and len(multi_channel_audio.shape) > 1:
            start = event.start_sample
            end = event.end_sample
            event_multi_channel = multi_channel_audio[:, start:end]
            tdoa_features = self.tdoa_extractor.extract(event_multi_channel)
        else:
            tdoa_features = np.zeros(self.tdoa_extractor.max_delay_bins * 2 * (self.num_channels - 1))
        
        if self.config.extract_robust_features:
            robust_features = self.robust_extractor.extract(event.audio, mel_spec)
        else:
            robust_features = RobustFeatures(
                spectral_centroid=0.0,
                spectral_bandwidth=0.0,
                spectral_rolloff=0.0,
                mfcc=np.zeros(self.config.mfcc_coeffs),
                decay_rate=0.0,
                attack_time=0.0,
                zero_crossing_rate=0.0,
                spectral_centroid_history=np.zeros(1)
            )
        
        mel_mean = np.mean(mel_spec, axis=0)
        mel_std = np.std(mel_spec, axis=0)
        
        robust_flat = np.array([
            robust_features.spectral_centroid / 1000.0,
            robust_features.spectral_bandwidth / 1000.0,
            robust_features.spectral_rolloff / 1000.0,
            robust_features.decay_rate * 100.0,
            robust_features.attack_time * 1000.0,
            robust_features.zero_crossing_rate * 100.0
        ])
        
        combined = np.concatenate([
            mel_mean,
            mel_std,
            robust_flat,
            robust_features.mfcc,
            tdoa_features
        ])
        
        if self.config.use_whitening and self.robust_extractor.whitener.is_fitted:
            whitened = self.robust_extractor.whitener.transform(combined.reshape(1, -1)).flatten()
        else:
            whitened = combined.copy()
        
        return KeyFeatures(
            mel_spectrogram=mel_spec,
            tdoa_features=tdoa_features,
            robust_features=robust_features,
            combined_features=combined,
            whitened_features=whitened,
            event=event
        )

    def extract_batch(self, events: List[KeyEvent], 
                      multi_channel_audio: Optional[np.ndarray] = None,
                      fit_whitener: bool = False) -> List[KeyFeatures]:
        features_list = [self.extract(event, multi_channel_audio) for event in events]
        
        if fit_whitener and self.config.use_whitening:
            all_combined = np.array([f.combined_features for f in features_list])
            self.robust_extractor.fit_whitener(all_combined)
            
            for i, features in enumerate(features_list):
                features.whitened_features = self.robust_extractor.whitener.transform(
                    features.combined_features.reshape(1, -1)
                ).flatten()
        
        return features_list


def extract_mel_spectrogram(audio: np.ndarray, sample_rate: int,
                            n_mels: int = 128, n_fft: int = 2048,
                            hop_length: int = 512) -> np.ndarray:
    config = FeatureExtractionConfig(n_mels=n_mels, n_fft=n_fft, hop_length=hop_length)
    extractor = MelSpectrogramExtractor(config, sample_rate)
    mel_spec, _ = extractor.extract(audio)
    return mel_spec


def extract_tdoa(audio: np.ndarray, sample_rate: int, num_channels: int,
                 max_delay_bins: int = 128) -> np.ndarray:
    config = FeatureExtractionConfig(tdoa_max_delay_bins=max_delay_bins)
    extractor = TDOAExtractor(config, sample_rate, num_channels)
    return extractor.extract(audio)
