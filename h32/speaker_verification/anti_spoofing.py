import numpy as np
import librosa
from scipy import signal
from scipy.stats import kurtosis, skew
from typing import Tuple, Dict, Any, Optional
from . import utils


class PhaseResidualAnalyzer:
    def __init__(self, sample_rate: int = 16000, n_fft: int = 512,
                 hop_length: int = 160):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length

    def _compute_group_delay(self, phase: np.ndarray) -> np.ndarray:
        group_delay = -np.diff(phase, axis=1)
        group_delay = np.pad(group_delay, ((0, 0), (0, 1)), mode='edge')
        return group_delay

    def _unwrap_phase(self, phase: np.ndarray) -> np.ndarray:
        return np.unwrap(phase, axis=1)

    def compute_phase_residual(self, audio: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
        mag, phase = utils.compute_stft(
            audio, n_fft=self.n_fft, hop_length=self.hop_length
        )

        unwrapped_phase = self._unwrap_phase(phase)
        group_delay = self._compute_group_delay(unwrapped_phase)

        min_phase = self._compute_minimum_phase(mag)
        residual_phase = unwrapped_phase - min_phase

        residual_abs = np.abs(residual_phase)
        mean_residual = np.mean(residual_abs)
        std_residual = np.std(residual_abs)
        max_residual = np.max(residual_abs)
        kurtosis_residual = kurtosis(residual_abs.flatten())
        skew_residual = skew(residual_abs.flatten())

        group_delay_var = np.var(group_delay)
        group_delay_kurtosis = kurtosis(group_delay.flatten())

        features = {
            'mean_phase_residual': float(mean_residual),
            'std_phase_residual': float(std_residual),
            'max_phase_residual': float(max_residual),
            'kurtosis_phase_residual': float(kurtosis_residual),
            'skew_phase_residual': float(skew_residual),
            'group_delay_variance': float(group_delay_var),
            'group_delay_kurtosis': float(group_delay_kurtosis)
        }

        return residual_phase, features

    def _compute_minimum_phase(self, magnitude: np.ndarray) -> np.ndarray:
        log_mag = np.log(magnitude + 1e-10)
        cepstrum = np.fft.irfft(log_mag, axis=0)

        n = cepstrum.shape[0]
        window = np.zeros(n)
        window[0] = 1
        if n % 2 == 0:
            window[n // 2] = 1
            window[1:n // 2] = 2
        else:
            window[1:(n + 1) // 2] = 2

        cepstrum = cepstrum * window[:, np.newaxis]
        min_phase = np.imag(np.fft.rfft(cepstrum, axis=0))

        return min_phase


class SpectralConsistencyAnalyzer:
    def __init__(self, sample_rate: int = 16000, n_fft: int = 512,
                 hop_length: int = 160, n_mels: int = 80):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels

    def compute_spectral_consistency(self, audio: np.ndarray) -> Dict[str, float]:
        mag, _ = utils.compute_stft(
            audio, n_fft=self.n_fft, hop_length=self.hop_length
        )

        mag_db = librosa.amplitude_to_db(mag, ref=np.max)

        spectral_flatness = np.mean(librosa.feature.spectral_flatness(
            S=mag, hop_length=self.hop_length
        ))

        spectral_centroid = np.mean(librosa.feature.spectral_centroid(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        ))

        spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        ))

        spectral_rolloff = np.mean(librosa.feature.spectral_rolloff(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        ))

        mel_spec = utils.compute_mel_spectrogram(
            audio, sample_rate=self.sample_rate, n_fft=self.n_fft,
            hop_length=self.hop_length, n_mels=self.n_mels
        )

        mel_mean = np.mean(mel_spec)
        mel_std = np.std(mel_spec)

        delta_mel = librosa.feature.delta(mel_spec)
        delta2_mel = librosa.feature.delta(mel_spec, order=2)
        delta_mean = np.mean(np.abs(delta_mel))
        delta2_mean = np.mean(np.abs(delta2_mel))

        adjacent_correlation = np.corrcoef(
            mag_db[:, :-1].flatten(), mag_db[:, 1:].flatten()
        )[0, 1]

        harmonic_distortion = self._compute_harmonic_distortion(audio)

        mfcc = utils.compute_mfcc(audio, sample_rate=self.sample_rate)
        mfcc_var = np.var(mfcc, axis=1)
        mfcc_mean_var = np.mean(mfcc_var)

        return {
            'spectral_flatness': float(spectral_flatness),
            'spectral_centroid': float(spectral_centroid),
            'spectral_bandwidth': float(spectral_bandwidth),
            'spectral_rolloff': float(spectral_rolloff),
            'mel_mean': float(mel_mean),
            'mel_std': float(mel_std),
            'delta_mean': float(delta_mean),
            'delta2_mean': float(delta2_mean),
            'adjacent_spectral_correlation': float(adjacent_correlation),
            'harmonic_distortion': float(harmonic_distortion),
            'mfcc_variance': float(mfcc_mean_var)
        }

    def _compute_harmonic_distortion(self, audio: np.ndarray) -> float:
        pitches, magnitudes = librosa.piptrack(
            y=audio, sr=self.sample_rate, fmin=50, fmax=400
        )

        pitch_track = []
        for i in range(pitches.shape[1]):
            idx = magnitudes[:, i].argmax()
            if magnitudes[idx, i] > 0.1:
                pitch_track.append(pitches[idx, i])

        if len(pitch_track) < 2:
            return 0.0

        pitch_track = np.array(pitch_track)
        harmonic_ratio = np.std(pitch_track) / (np.mean(pitch_track) + 1e-8)

        return float(harmonic_ratio)


class PitchShiftEstimator:
    def __init__(self, sample_rate: int = 16000, fmin: float = 50,
                 fmax: float = 400):
        self.sample_rate = sample_rate
        self.fmin = fmin
        self.fmax = fmax

    def estimate_pitch_shift_factor(self, test_audio: np.ndarray,
                                    reference_pitch: Optional[np.ndarray] = None) -> Dict[str, Any]:
        test_pitch = utils.estimate_pitch(
            test_audio, sample_rate=self.sample_rate,
            fmin=self.fmin, fmax=self.fmax
        )

        test_pitch = test_pitch[test_pitch > 0]

        if len(test_pitch) == 0:
            return {
                'estimated_factor': 1.0,
                'confidence': 0.0,
                'test_pitch_mean': 0.0,
                'reference_pitch_mean': 0.0
            }

        test_pitch_mean = np.median(test_pitch)

        if reference_pitch is not None:
            ref_pitch = reference_pitch[reference_pitch > 0]
            if len(ref_pitch) > 0:
                ref_pitch_mean = np.median(ref_pitch)

                ratio = test_pitch_mean / (ref_pitch_mean + 1e-8)

                if ratio > 1.5 or ratio < 0.667:
                    candidates = [ratio, 1/ratio, ratio * 2, 1/(ratio*2), ratio/2, 2/ratio]
                    best_candidate = min(candidates, key=lambda x: abs(x - 1.0))
                    if abs(best_candidate - 1.0) < abs(ratio - 1.0):
                        ratio = best_candidate

                estimated_factor = ratio
                confidence = self._estimate_confidence(test_pitch, ref_pitch)

                confidence = confidence * (1 - abs(estimated_factor - 1.0))

            else:
                estimated_factor = 1.0
                confidence = 0.0
                ref_pitch_mean = 0.0
        else:
            ref_pitch_mean = 0.0
            estimated_factor = self._estimate_factor_from_pitch_distribution(test_pitch)
            confidence = self._estimate_self_confidence(test_pitch)

        n_steps = 12 * np.log2(estimated_factor)

        return {
            'estimated_factor': float(estimated_factor),
            'estimated_semitones': float(n_steps),
            'confidence': float(confidence),
            'test_pitch_mean': float(test_pitch_mean),
            'reference_pitch_mean': float(ref_pitch_mean)
        }

    def _estimate_factor_from_pitch_distribution(self, pitch: np.ndarray) -> float:
        pitch_normalized = pitch / np.median(pitch)
        q25, q75 = np.percentile(pitch_normalized, [25, 75])
        iqr = q75 - q25

        if iqr > 0.2:
            return 1.0

        return 1.0

    def _estimate_confidence(self, test_pitch: np.ndarray,
                             ref_pitch: np.ndarray) -> float:
        if len(test_pitch) < 10 or len(ref_pitch) < 10:
            return 0.0

        test_std = np.std(test_pitch) / (np.mean(test_pitch) + 1e-8)
        ref_std = np.std(ref_pitch) / (np.mean(ref_pitch) + 1e-8)

        if test_std > 0.3 or ref_std > 0.3:
            return 0.3

        return max(0.0, 1.0 - abs(test_std - ref_std))

    def _estimate_self_confidence(self, pitch: np.ndarray) -> float:
        if len(pitch) < 10:
            return 0.0

        pitch_std = np.std(pitch) / (np.mean(pitch) + 1e-8)
        return max(0.0, 1.0 - pitch_std)


class AntiSpoofingDetector:
    def __init__(self, sample_rate: int = 16000,
                 phase_residual_threshold: float = 0.3,
                 spectral_consistency_threshold: float = 0.7,
                 enable_splicing_detection: bool = True):
        self.sample_rate = sample_rate
        self.phase_threshold = phase_residual_threshold
        self.spectral_threshold = spectral_consistency_threshold
        self.enable_splicing_detection = enable_splicing_detection

        self.phase_analyzer = PhaseResidualAnalyzer(sample_rate)
        self.spectral_analyzer = SpectralConsistencyAnalyzer(sample_rate)
        self.pitch_estimator = PitchShiftEstimator(sample_rate)
        self.splicing_detector = SplicingDetector(sample_rate) if enable_splicing_detection else None

    def _estimate_snr(self, audio: np.ndarray) -> float:
        mag, _ = utils.compute_stft(audio, n_fft=512, hop_length=160)

        signal_energy = np.sum(mag ** 2, axis=0)

        noise_floor = np.percentile(signal_energy, 10)
        signal_energy_sorted = np.sort(signal_energy)
        top_indices = int(len(signal_energy_sorted) * 0.1)
        signal_level = np.mean(signal_energy_sorted[-top_indices:])

        if noise_floor < 1e-10:
            noise_floor = 1e-10

        snr = 10 * np.log10(signal_level / noise_floor)
        return float(np.clip(snr, -10, 50))

    def _get_adaptive_weights(self, snr: float) -> Tuple[float, float, float]:
        snr_norm = np.clip((snr + 10) / 60, 0, 1)

        phase_weight = 0.4 * snr_norm + 0.2 * (1 - snr_norm)
        spectral_weight = 0.35 * snr_norm + 0.45 * (1 - snr_norm)
        pitch_weight = 0.25 * snr_norm + 0.35 * (1 - snr_norm)

        total = phase_weight + spectral_weight + pitch_weight
        return phase_weight / total, spectral_weight / total, pitch_weight / total

    def _get_adaptive_thresholds(self, snr: float) -> Dict[str, float]:
        snr_norm = np.clip((snr + 10) / 60, 0, 1)

        phase_threshold = self.phase_threshold * (0.5 + 0.5 * snr_norm) + 0.2 * (1 - snr_norm) * self.phase_threshold

        spectral_threshold = self.spectral_threshold * (0.7 + 0.3 * snr_norm)

        flatness_threshold = 0.3 * (0.6 + 0.4 * snr_norm)
        harmonic_threshold = 0.2 * (0.5 + 0.5 * snr_norm)
        delta_threshold = 5.0 * (0.7 + 0.3 * snr_norm)

        pitch_confidence_threshold = 0.3 * (0.7 + 0.3 * snr_norm)

        return {
            'phase': phase_threshold,
            'spectral': spectral_threshold,
            'flatness': flatness_threshold,
            'harmonic': harmonic_threshold,
            'delta': delta_threshold,
            'pitch_confidence': pitch_confidence_threshold
        }

    def detect_spoofing(self, test_audio: np.ndarray,
                        reference_audio: Optional[np.ndarray] = None) -> Dict[str, Any]:
        snr = self._estimate_snr(test_audio)

        _, phase_features = self.phase_analyzer.compute_phase_residual(test_audio)
        spectral_features = self.spectral_analyzer.compute_spectral_consistency(test_audio)

        ref_pitch = None
        if reference_audio is not None:
            ref_pitch = utils.estimate_pitch(
                reference_audio, sample_rate=self.sample_rate
            )

        pitch_estimation = self.pitch_estimator.estimate_pitch_shift_factor(
            test_audio, ref_pitch
        )

        splicing_result = None
        if self.enable_splicing_detection and self.splicing_detector is not None:
            splicing_result = self.splicing_detector.detect_splicing(test_audio)

        spoofing_probability = self._compute_spoofing_probability(
            phase_features, spectral_features, pitch_estimation, snr, splicing_result
        )

        is_spoofed = spoofing_probability > 0.5

        result = {
            'is_spoofed': bool(is_spoofed),
            'spoofing_probability': float(spoofing_probability),
            'estimated_snr': float(snr),
            'phase_features': phase_features,
            'spectral_features': spectral_features,
            'pitch_estimation': pitch_estimation,
            'splicing_detection': splicing_result,
            'estimated_pitch_factor': pitch_estimation['estimated_factor'],
            'estimated_semitones': pitch_estimation['estimated_semitones']
        }

        return result

    def _compute_spoofing_probability(self, phase_features: Dict[str, float],
                                      spectral_features: Dict[str, float],
                                      pitch_estimation: Dict[str, Any],
                                      snr: float,
                                      splicing_result: Optional[Dict[str, Any]] = None) -> float:
        adaptive_thresholds = self._get_adaptive_thresholds(snr)
        adaptive_weights = self._get_adaptive_weights(snr)

        phase_score = self._compute_phase_score(phase_features, adaptive_thresholds)
        spectral_score = self._compute_spectral_score(spectral_features, adaptive_thresholds)
        pitch_score = self._compute_pitch_score(pitch_estimation, adaptive_thresholds)

        total_score = (
            adaptive_weights[0] * phase_score +
            adaptive_weights[1] * spectral_score +
            adaptive_weights[2] * pitch_score
        )

        if splicing_result is not None:
            splicing_prob = splicing_result['splicing_probability']
            if splicing_prob > 0.5:
                total_score = max(total_score, splicing_prob * 0.8 + total_score * 0.2)
            elif splicing_prob > 0.3:
                total_score = total_score * 0.9 + splicing_prob * 0.1

        snr_discount = np.clip((snr + 5) / 30, 0.3, 1.0)
        if snr < 10:
            baseline = 0.3 * (1 - snr_discount)
            total_score = baseline + total_score * snr_discount

        return np.clip(total_score, 0.0, 1.0)

    def _compute_phase_score(self, features: Dict[str, float],
                             thresholds: Dict[str, float]) -> float:
        mean_residual = features['mean_phase_residual']
        std_residual = features['std_phase_residual']
        gd_variance = features['group_delay_variance']

        score = 0.0

        phase_threshold = thresholds['phase']
        if mean_residual > phase_threshold:
            score += 0.4 * min(1.0, (mean_residual - phase_threshold) / (phase_threshold + 1e-8) + 0.5)
        if std_residual > 0.5:
            score += 0.3 * min(1.0, (std_residual - 0.5) / 0.5 + 0.5)
        if gd_variance > 1.0:
            score += 0.3 * min(1.0, (gd_variance - 1.0) / 1.0 + 0.5)

        return np.clip(score, 0.0, 1.0)

    def _compute_spectral_score(self, features: Dict[str, float],
                                thresholds: Dict[str, float]) -> float:
        flatness = features['spectral_flatness']
        correlation = features['adjacent_spectral_correlation']
        harmonic_distortion = features['harmonic_distortion']
        delta_mean = features['delta_mean']

        score = 0.0

        flatness_threshold = thresholds['flatness']
        spectral_threshold = thresholds['spectral']
        harmonic_threshold = thresholds['harmonic']
        delta_threshold = thresholds['delta']

        if flatness > flatness_threshold:
            score += 0.3 * min(1.0, (flatness - flatness_threshold) / (flatness_threshold + 1e-8) + 0.5)
        if correlation < spectral_threshold:
            score += 0.3 * min(1.0, (spectral_threshold - correlation) / (spectral_threshold + 1e-8) + 0.5)
        if harmonic_distortion > harmonic_threshold:
            score += 0.2 * min(1.0, (harmonic_distortion - harmonic_threshold) / (harmonic_threshold + 1e-8) + 0.5)
        if delta_mean > delta_threshold:
            score += 0.2 * min(1.0, (delta_mean - delta_threshold) / (delta_threshold + 1e-8) + 0.5)

        return np.clip(score, 0.0, 1.0)

    def _compute_pitch_score(self, pitch_estimation: Dict[str, Any],
                             thresholds: Dict[str, float]) -> float:
        factor = pitch_estimation['estimated_factor']
        confidence = pitch_estimation['confidence']

        deviation = abs(factor - 1.0)
        confidence_threshold = thresholds['pitch_confidence']

        if confidence < confidence_threshold:
            return 0.2 + 0.1 * (1 - confidence / max(confidence_threshold, 0.01))

        if deviation > 0.2:
            return min(1.0, deviation * 2)
        elif deviation > 0.1:
            return deviation * 1.5

        return 0.1


class SplicingDetector:
    def __init__(self, sample_rate: int = 16000, n_fft: int = 512,
                 hop_length: int = 160):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.window_sizes = [0.05, 0.1, 0.2, 0.3, 0.5]
        self.window_overlap = 0.5

    def _compute_features_for_window(self, audio_segment: np.ndarray) -> Dict[str, float]:
        if len(audio_segment) < self.n_fft:
            audio_segment = np.pad(
                audio_segment,
                (0, self.n_fft - len(audio_segment)),
                mode='constant'
            )

        mag, phase = utils.compute_stft(
            audio_segment, n_fft=self.n_fft, hop_length=self.hop_length
        )

        mag_db = librosa.amplitude_to_db(mag, ref=np.max)

        mfcc = utils.compute_mfcc(
            audio_segment, sample_rate=self.sample_rate,
            n_fft=self.n_fft, hop_length=self.hop_length
        )

        spectral_flatness = np.mean(librosa.feature.spectral_flatness(
            S=mag, hop_length=self.hop_length
        ))

        spectral_centroid = np.mean(librosa.feature.spectral_centroid(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        ))

        spectral_rolloff = np.mean(librosa.feature.spectral_rolloff(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        ))

        zcr = np.mean(librosa.feature.zero_crossing_rate(
            audio_segment, hop_length=self.hop_length
        ))

        rms = np.mean(librosa.feature.rms(
            y=audio_segment, hop_length=self.hop_length
        ))

        mfcc_mean = np.mean(mfcc, axis=1)
        mfcc_std = np.std(mfcc, axis=1)

        pitch = utils.estimate_pitch(
            audio_segment, sample_rate=self.sample_rate
        )
        pitch = pitch[pitch > 0]
        pitch_mean = np.mean(pitch) if len(pitch) > 0 else 0.0
        pitch_std = np.std(pitch) if len(pitch) > 0 else 0.0

        phase_grad = np.abs(np.diff(np.unwrap(phase, axis=1), axis=1))
        phase_grad_mean = np.mean(phase_grad)

        return {
            'spectral_flatness': float(spectral_flatness),
            'spectral_centroid': float(spectral_centroid),
            'spectral_rolloff': float(spectral_rolloff),
            'zcr': float(zcr),
            'rms': float(rms),
            'mfcc_mean': mfcc_mean,
            'mfcc_std': mfcc_std,
            'pitch_mean': float(pitch_mean),
            'pitch_std': float(pitch_std),
            'phase_grad_mean': float(phase_grad_mean)
        }

    def _compute_feature_distance(self, feat1: Dict[str, float],
                                  feat2: Dict[str, float]) -> float:
        distance = 0.0
        weight_sum = 0.0

        scalar_features = [
            ('spectral_flatness', 1.2),
            ('spectral_centroid', 0.8),
            ('spectral_rolloff', 0.8),
            ('zcr', 1.2),
            ('rms', 1.2),
            ('pitch_mean', 2.0),
            ('pitch_std', 1.5),
            ('phase_grad_mean', 2.0)
        ]

        for feat_name, weight in scalar_features:
            v1 = feat1[feat_name]
            v2 = feat2[feat_name]
            if max(abs(v1), abs(v2)) > 1e-8:
                norm_dist = abs(v1 - v2) / (max(abs(v1), abs(v2)) + 1e-8)
                distance += weight * norm_dist
                weight_sum += weight

        if 'mfcc_mean' in feat1 and 'mfcc_mean' in feat2:
            mfcc_dist = np.mean(np.abs(feat1['mfcc_mean'] - feat2['mfcc_mean']))
            mfcc_std_dist = np.mean(np.abs(feat1['mfcc_std'] - feat2['mfcc_std']))
            distance += 1.5 * mfcc_dist / (np.mean(np.abs(feat1['mfcc_mean'])) + 1e-8)
            distance += 1.0 * mfcc_std_dist / (np.mean(np.abs(feat1['mfcc_std'])) + 1e-8)
            weight_sum += 2.5

        if weight_sum > 0:
            distance = distance / weight_sum

        return float(distance)

    def _multi_scale_detection(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        n_samples = len(audio)
        time_axis = np.arange(n_samples) / self.sample_rate

        all_scores = []
        all_positions = []

        for window_size_sec in self.window_sizes:
            window_size = int(window_size_sec * self.sample_rate)
            hop_size = int(window_size * self.window_overlap)

            if hop_size < 1:
                hop_size = 1

            window_scores = []
            window_positions = []

            for start in range(0, n_samples - window_size + 1, hop_size):
                mid = start + window_size // 2
                window_positions.append(mid / self.sample_rate)

                left_start = max(0, start - window_size)
                left_end = start
                right_start = start + window_size
                right_end = min(n_samples, right_start + window_size)

                if left_end - left_start < window_size // 2 or right_end - right_start < window_size // 2:
                    window_scores.append(0.0)
                    continue

                left_segment = audio[left_start:left_end]
                right_segment = audio[right_start:right_end]

                if len(left_segment) < self.n_fft // 2 or len(right_segment) < self.n_fft // 2:
                    window_scores.append(0.0)
                    continue

                feat_left = self._compute_features_for_window(left_segment)
                feat_right = self._compute_features_for_window(right_segment)

                distance = self._compute_feature_distance(feat_left, feat_right)

                center_segment = audio[start:start + window_size]
                feat_center = self._compute_features_for_window(center_segment)

                left_center_dist = self._compute_feature_distance(feat_left, feat_center)
                right_center_dist = self._compute_feature_distance(feat_right, feat_center)

                asymmetry = abs(left_center_dist - right_center_dist)
                combined_score = distance * 0.6 + asymmetry * 0.4

                window_scores.append(combined_score)

            if window_scores:
                all_scores.append(window_scores)
                all_positions.append(window_positions)

        return all_scores, all_positions

    def _aggregate_scores(self, all_scores: list, all_positions: list,
                          n_samples: int) -> Tuple[np.ndarray, float, list]:
        if not all_scores:
            return np.zeros(n_samples), 0.0, []

        time_axis = np.arange(n_samples) / self.sample_rate
        aggregated_scores = np.zeros(n_samples)
        count = np.zeros(n_samples)

        for scores, positions in zip(all_scores, all_positions):
            if len(scores) == 0:
                continue

            for i, pos in enumerate(positions):
                center_idx = int(pos * self.sample_rate)
                window_half = int(0.05 * self.sample_rate)

                start = max(0, center_idx - window_half)
                end = min(n_samples, center_idx + window_half)

                aggregated_scores[start:end] += scores[i]
                count[start:end] += 1

        count[count == 0] = 1
        aggregated_scores = aggregated_scores / count

        peaks, properties = signal.find_peaks(
            aggregated_scores,
            height=0.35,
            distance=int(0.1 * self.sample_rate),
            prominence=0.08
        )

        peak_times = peaks / self.sample_rate
        peak_scores = aggregated_scores[peaks]

        max_score = float(np.max(aggregated_scores)) if len(aggregated_scores) > 0 else 0.0

        detections = []
        for i, peak_idx in enumerate(peaks):
            window_half = int(0.05 * self.sample_rate)
            start = max(0, peak_idx - window_half)
            end = min(n_samples, peak_idx + window_half)

            detections.append({
                'time': float(peak_times[i]),
                'score': float(peak_scores[i]),
                'start_sample': int(start),
                'end_sample': int(end),
                'start_time': float(start / self.sample_rate),
                'end_time': float(end / self.sample_rate)
            })

        return aggregated_scores, max_score, detections

    def detect_splicing(self, audio: np.ndarray) -> Dict[str, Any]:
        all_scores, all_positions = self._multi_scale_detection(audio)
        aggregated_scores, max_score, detections = self._aggregate_scores(
            all_scores, all_positions, len(audio)
        )

        splicing_probability = np.clip(max_score * 1.8, 0.0, 1.0)

        is_spliced = splicing_probability > 0.55

        return {
            'is_spliced': bool(is_spliced),
            'splicing_probability': float(splicing_probability),
            'max_score': float(max_score),
            'num_detections': int(len(detections)),
            'detections': detections,
            'score_profile': aggregated_scores
        }
