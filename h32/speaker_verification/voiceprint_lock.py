import numpy as np
import librosa
from scipy import signal
from scipy.stats import kurtosis, skew
from typing import Tuple, Dict, Any, Optional, List
from . import utils
from .embedding import SpeakerEmbeddingExtractor
from .anti_spoofing import AntiSpoofingDetector


class ReplayAttackDetector:
    def __init__(self, sample_rate: int = 16000, n_fft: int = 512,
                 hop_length: int = 160):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length

    def _compute_mfcc_deltas(self, audio: np.ndarray) -> np.ndarray:
        mfcc = utils.compute_mfcc(
            audio, sample_rate=self.sample_rate,
            n_fft=self.n_fft, hop_length=self.hop_length
        )
        delta = librosa.feature.delta(mfcc)
        delta2 = librosa.feature.delta(mfcc, order=2)
        return np.concatenate([mfcc, delta, delta2], axis=0)

    def _compute_spectral_centroid_features(self, audio: np.ndarray) -> Dict[str, float]:
        mag, _ = utils.compute_stft(
            audio, n_fft=self.n_fft, hop_length=self.hop_length
        )

        centroid = librosa.feature.spectral_centroid(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        )
        bandwidth = librosa.feature.spectral_bandwidth(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        )
        rolloff = librosa.feature.spectral_rolloff(
            S=mag, sr=self.sample_rate, hop_length=self.hop_length
        )
        flatness = librosa.feature.spectral_flatness(
            S=mag, hop_length=self.hop_length
        )

        features = {
            'centroid_mean': float(np.mean(centroid)),
            'centroid_std': float(np.std(centroid)),
            'bandwidth_mean': float(np.mean(bandwidth)),
            'bandwidth_std': float(np.std(bandwidth)),
            'rolloff_mean': float(np.mean(rolloff)),
            'rolloff_std': float(np.std(rolloff)),
            'flatness_mean': float(np.mean(flatness)),
            'flatness_std': float(np.std(flatness))
        }

        return features

    def _compute_cepstral_features(self, audio: np.ndarray) -> Dict[str, float]:
        mag, phase = utils.compute_stft(
            audio, n_fft=self.n_fft, hop_length=self.hop_length
        )

        log_mag = np.log(np.abs(mag) + 1e-10)
        cepstrum = np.fft.irfft(log_mag, axis=0)

        quefrency_axis = np.arange(cepstrum.shape[0]) / self.sample_rate

        low_que_idx = (quefrency_axis >= 0.001) & (quefrency_axis <= 0.005)
        mid_que_idx = (quefrency_axis >= 0.005) & (quefrency_axis <= 0.02)
        high_que_idx = (quefrency_axis >= 0.02) & (quefrency_axis <= 0.1)

        features = {
            'cepstral_low_mean': float(np.mean(np.abs(cepstrum[low_que_idx, :]))),
            'cepstral_mid_mean': float(np.mean(np.abs(cepstrum[mid_que_idx, :]))),
            'cepstral_high_mean': float(np.mean(np.abs(cepstrum[high_que_idx, :]))),
            'cepstral_low_std': float(np.std(np.abs(cepstrum[low_que_idx, :]))),
            'cepstral_mid_std': float(np.std(np.abs(cepstrum[mid_que_idx, :]))),
            'cepstral_high_std': float(np.std(np.abs(cepstrum[high_que_idx, :])))
        }

        return features

    def _compute_phase_features(self, audio: np.ndarray) -> Dict[str, float]:
        mag, phase = utils.compute_stft(
            audio, n_fft=self.n_fft, hop_length=self.hop_length
        )

        unwrapped_phase = np.unwrap(phase, axis=1)
        group_delay = -np.diff(unwrapped_phase, axis=1)
        group_delay = np.pad(group_delay, ((0, 0), (0, 1)), mode='edge')

        phase_grad = np.diff(unwrapped_phase, axis=0)
        phase_grad = np.pad(phase_grad, ((0, 1), (0, 0)), mode='edge')

        features = {
            'phase_mean': float(np.mean(phase)),
            'phase_std': float(np.std(phase)),
            'phase_kurtosis': float(kurtosis(phase.flatten())),
            'group_delay_mean': float(np.mean(group_delay)),
            'group_delay_std': float(np.std(group_delay)),
            'phase_grad_mean': float(np.mean(phase_grad)),
            'phase_grad_std': float(np.std(phase_grad)),
            'phase_residual': float(np.mean(np.abs(phase - np.round(phase / np.pi) * np.pi)))
        }

        return features

    def _compute_harmonic_features(self, audio: np.ndarray) -> Dict[str, float]:
        harmonic, percussive = librosa.effects.hpss(audio)

        harmonic_energy = np.sum(harmonic ** 2)
        percussive_energy = np.sum(percussive ** 2)
        total_energy = harmonic_energy + percussive_energy + 1e-8

        pitches, magnitudes = librosa.piptrack(
            y=audio, sr=self.sample_rate, fmin=50, fmax=500
        )

        pitch_track = []
        for i in range(pitches.shape[1]):
            idx = magnitudes[:, i].argmax()
            if magnitudes[idx, i] > 0.1:
                pitch_track.append(pitches[idx, i])

        if len(pitch_track) < 2:
            pitch_mean = 0.0
            pitch_std = 0.0
            pitch_jitter = 0.0
        else:
            pitch_track = np.array(pitch_track)
            pitch_mean = np.mean(pitch_track)
            pitch_std = np.std(pitch_track)
            pitch_jitter = np.mean(np.abs(np.diff(pitch_track))) / (pitch_mean + 1e-8)

        features = {
            'harmonic_ratio': float(harmonic_energy / total_energy),
            'percussive_ratio': float(percussive_energy / total_energy),
            'pitch_mean': float(pitch_mean),
            'pitch_std': float(pitch_std),
            'pitch_jitter': float(pitch_jitter),
            'hnr': float(10 * np.log10(harmonic_energy / (percussive_energy + 1e-8) + 1e-8))
        }

        return features

    def detect_replay(self, audio: np.ndarray) -> Dict[str, Any]:
        audio = utils.normalize_audio(audio)

        mfcc_deltas = self._compute_mfcc_deltas(audio)
        spectral_features = self._compute_spectral_centroid_features(audio)
        cepstral_features = self._compute_cepstral_features(audio)
        phase_features = self._compute_phase_features(audio)
        harmonic_features = self._compute_harmonic_features(audio)

        score = 0.0
        weight_sum = 0.0

        if spectral_features['flatness_mean'] > 0.2:
            score += 0.2
        weight_sum += 0.2

        if cepstral_features['cepstral_high_mean'] > 0.1:
            score += 0.25
        weight_sum += 0.25

        if phase_features['phase_residual'] > 0.3:
            score += 0.2
        weight_sum += 0.2

        if harmonic_features['harmonic_ratio'] < 0.6:
            score += 0.15
        weight_sum += 0.15

        if phase_features['group_delay_std'] > 1.0:
            score += 0.2
        weight_sum += 0.2

        replay_probability = score / weight_sum if weight_sum > 0 else 0.0

        is_replay = replay_probability > 0.5

        return {
            'is_replay': bool(is_replay),
            'replay_probability': float(replay_probability),
            'spectral_features': spectral_features,
            'cepstral_features': cepstral_features,
            'phase_features': phase_features,
            'harmonic_features': harmonic_features,
            'mfcc_deltas_mean': float(np.mean(mfcc_deltas))
        }


class LivenessDetector:
    def __init__(self, sample_rate: int = 16000, n_fft: int = 512,
                 hop_length: int = 160):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length

    def _compute_breath_features(self, audio: np.ndarray) -> Dict[str, float]:
        rms = librosa.feature.rms(
            y=audio, frame_length=self.n_fft, hop_length=self.hop_length
        )[0]

        zcr = librosa.feature.zero_crossing_rate(
            audio, frame_length=self.n_fft, hop_length=self.hop_length
        )[0]

        low_energy_idx = rms < np.percentile(rms, 30)

        if np.sum(low_energy_idx) > 0:
            breath_zcr_mean = np.mean(zcr[low_energy_idx])
            breath_rms_mean = np.mean(rms[low_energy_idx])
            breath_duration_ratio = np.sum(low_energy_idx) / len(low_energy_idx)
        else:
            breath_zcr_mean = 0.0
            breath_rms_mean = 0.0
            breath_duration_ratio = 0.0

        features = {
            'breath_zcr_mean': float(breath_zcr_mean),
            'breath_rms_mean': float(breath_rms_mean),
            'breath_duration_ratio': float(breath_duration_ratio),
            'rms_mean': float(np.mean(rms)),
            'rms_std': float(np.std(rms)),
            'zcr_mean': float(np.mean(zcr)),
            'zcr_std': float(np.std(zcr))
        }

        return features

    def _compute_vibration_features(self, audio: np.ndarray) -> Dict[str, float]:
        pitches, magnitudes = librosa.piptrack(
            y=audio, sr=self.sample_rate, fmin=80, fmax=400
        )

        pitch_track = []
        mag_track = []
        for i in range(pitches.shape[1]):
            idx = magnitudes[:, i].argmax()
            if magnitudes[idx, i] > 0.1:
                pitch_track.append(pitches[idx, i])
                mag_track.append(magnitudes[idx, i])

        if len(pitch_track) < 4:
            return {
                'vibrato_rate': 0.0,
                'vibrato_depth': 0.0,
                'jitter': 0.0,
                'shimmer': 0.0,
                'pitch_variation': 0.0
            }

        pitch_track = np.array(pitch_track)
        mag_track = np.array(mag_track)

        pitch_diff = np.diff(pitch_track)
        jitter = np.mean(np.abs(pitch_diff)) / (np.mean(pitch_track) + 1e-8)

        mag_diff = np.diff(mag_track)
        shimmer = np.mean(np.abs(mag_diff)) / (np.mean(mag_track) + 1e-8)

        if len(pitch_track) > 10:
            pitch_normalized = (pitch_track - np.mean(pitch_track)) / (np.std(pitch_track) + 1e-8)
            autocorr = np.correlate(pitch_normalized, pitch_normalized, mode='full')
            autocorr = autocorr[len(autocorr) // 2:]

            peaks, _ = signal.find_peaks(autocorr, distance=5, height=0.3)
            if len(peaks) >= 2:
                vibrato_rate = float(self.sample_rate / self.hop_length / (peaks[1] - peaks[0]))
                vibrato_depth = float(np.std(pitch_track) / (np.mean(pitch_track) + 1e-8) * 100)
            else:
                vibrato_rate = 0.0
                vibrato_depth = 0.0
        else:
            vibrato_rate = 0.0
            vibrato_depth = 0.0

        pitch_variation = float(np.std(pitch_track) / (np.mean(pitch_track) + 1e-8))

        features = {
            'vibrato_rate': float(vibrato_rate),
            'vibrato_depth': float(vibrato_depth),
            'jitter': float(jitter),
            'shimmer': float(shimmer),
            'pitch_variation': float(pitch_variation)
        }

        return features

    def _compute_voice_activity_features(self, audio: np.ndarray) -> Dict[str, float]:
        intervals = librosa.effects.split(audio, top_db=20)

        if len(intervals) == 0:
            return {
                'speech_duration_ratio': 0.0,
                'silence_duration_ratio': 1.0,
                'num_speech_segments': 0,
                'avg_speech_duration': 0.0,
                'avg_silence_duration': 0.0
            }

        total_duration = len(audio) / self.sample_rate

        speech_durations = []
        silence_durations = []

        prev_end = 0
        for start, end in intervals:
            speech_durations.append((end - start) / self.sample_rate)
            if start > prev_end:
                silence_durations.append((start - prev_end) / self.sample_rate)
            prev_end = end

        if len(audio) > prev_end:
            silence_durations.append((len(audio) - prev_end) / self.sample_rate)

        total_speech = sum(speech_durations)
        total_silence = sum(silence_durations) if silence_durations else 0.0

        features = {
            'speech_duration_ratio': float(total_speech / total_duration),
            'silence_duration_ratio': float(total_silence / total_duration),
            'num_speech_segments': int(len(intervals)),
            'avg_speech_duration': float(np.mean(speech_durations)) if speech_durations else 0.0,
            'avg_silence_duration': float(np.mean(silence_durations)) if silence_durations else 0.0
        }

        return features

    def _compute_spectral_temporal_features(self, audio: np.ndarray) -> Dict[str, float]:
        mag, _ = utils.compute_stft(
            audio, n_fft=self.n_fft, hop_length=self.hop_length
        )

        spectral_flux = np.zeros(mag.shape[1])
        for t in range(1, mag.shape[1]):
            diff = mag[:, t] - mag[:, t - 1]
            spectral_flux[t] = np.sum(np.maximum(0, diff))

        if np.max(spectral_flux) > 0:
            spectral_flux = spectral_flux / np.max(spectral_flux)

        mel_spec = utils.compute_mel_spectrogram(
            audio, sample_rate=self.sample_rate, n_fft=self.n_fft,
            hop_length=self.hop_length
        )

        delta_mel = librosa.feature.delta(mel_spec)
        delta2_mel = librosa.feature.delta(mel_spec, order=2)

        features = {
            'spectral_flux_mean': float(np.mean(spectral_flux)),
            'spectral_flux_std': float(np.std(spectral_flux)),
            'spectral_flux_max': float(np.max(spectral_flux)),
            'delta_mel_mean': float(np.mean(np.abs(delta_mel))),
            'delta2_mel_mean': float(np.mean(np.abs(delta2_mel))),
            'mel_dynamic_range': float(np.max(mel_spec) - np.min(mel_spec))
        }

        return features

    def detect_liveness(self, audio: np.ndarray) -> Dict[str, Any]:
        audio = utils.normalize_audio(audio)

        breath_features = self._compute_breath_features(audio)
        vibration_features = self._compute_vibration_features(audio)
        activity_features = self._compute_voice_activity_features(audio)
        spectral_features = self._compute_spectral_temporal_features(audio)

        liveness_score = 0.0
        weight_sum = 0.0

        if vibration_features['jitter'] > 0.001 and vibration_features['jitter'] < 0.05:
            liveness_score += 0.25
        weight_sum += 0.25

        if vibration_features['shimmer'] > 0.01 and vibration_features['shimmer'] < 0.1:
            liveness_score += 0.2
        weight_sum += 0.2

        if vibration_features['pitch_variation'] > 0.02 and vibration_features['pitch_variation'] < 0.2:
            liveness_score += 0.2
        weight_sum += 0.2

        if breath_features['breath_duration_ratio'] > 0.05 and breath_features['breath_duration_ratio'] < 0.4:
            liveness_score += 0.15
        weight_sum += 0.15

        if activity_features['num_speech_segments'] >= 2 and activity_features['num_speech_segments'] <= 20:
            liveness_score += 0.1
        weight_sum += 0.1

        if spectral_features['spectral_flux_std'] > 0.1:
            liveness_score += 0.1
        weight_sum += 0.1

        liveness_probability = liveness_score / weight_sum if weight_sum > 0 else 0.0

        is_live = liveness_probability > 0.5

        return {
            'is_live': bool(is_live),
            'liveness_probability': float(liveness_probability),
            'breath_features': breath_features,
            'vibration_features': vibration_features,
            'activity_features': activity_features,
            'spectral_features': spectral_features
        }


class VoiceprintLock:
    def __init__(self, sample_rate: int = 16000,
                 model_type: str = 'ecapa', embedding_dim: int = 192,
                 device: str = 'cpu', threshold: float = 0.5,
                 liveness_threshold: float = 0.5, replay_threshold: float = 0.5):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.liveness_threshold = liveness_threshold
        self.replay_threshold = replay_threshold

        self.embedding_extractor = SpeakerEmbeddingExtractor(
            model_type=model_type, embedding_dim=embedding_dim,
            sample_rate=sample_rate, device=device
        )

        self.replay_detector = ReplayAttackDetector(
            sample_rate=sample_rate
        )

        self.liveness_detector = LivenessDetector(
            sample_rate=sample_rate
        )

        self.anti_spoofing_detector = AntiSpoofingDetector(
            sample_rate=sample_rate
        )

        self.registered_embedding: Optional[np.ndarray] = None
        self.registered_audio: Optional[np.ndarray] = None

    def register_user(self, audio_paths: List[str]) -> Dict[str, Any]:
        audio_samples = []
        for path in audio_paths:
            audio, _ = utils.load_audio(path, sample_rate=self.sample_rate)
            audio = utils.normalize_audio(audio)
            audio = utils.apply_vad(audio, sample_rate=self.sample_rate)
            audio_samples.append(audio)

        self.registered_embedding = self.embedding_extractor.enroll_speaker(audio_samples)
        self.registered_audio = audio_samples[0] if audio_samples else None

        return {
            'registration_successful': True,
            'num_enrollment_samples': len(audio_samples),
            'embedding_dim': len(self.registered_embedding),
            'registered': True
        }

    def set_registered_embedding(self, embedding: np.ndarray,
                                 registered_audio: Optional[np.ndarray] = None) -> None:
        self.registered_embedding = embedding
        self.registered_audio = registered_audio

    def verify(self, test_audio_path: str,
               check_liveness: bool = True,
               check_replay: bool = True,
               check_spoofing: bool = True) -> Dict[str, Any]:
        if self.registered_embedding is None:
            raise ValueError("未注册用户，请先调用 register_user")

        test_audio, _ = utils.load_audio(test_audio_path, sample_rate=self.sample_rate)
        test_audio = utils.normalize_audio(test_audio)
        test_audio_vad = utils.apply_vad(test_audio, sample_rate=self.sample_rate)

        result = {
            'audio_path': test_audio_path,
            'audio_duration': float(len(test_audio) / self.sample_rate),
            'verified': False,
            'overall_score': 0.0
        }

        if len(test_audio_vad) < 0.5 * self.sample_rate:
            result['error'] = '语音太短，无法进行验证'
            result['verified'] = False
            return result

        test_embedding = self.embedding_extractor.extract_embedding(test_audio_vad)
        verification_score = utils.cosine_similarity(
            self.registered_embedding, test_embedding
        )

        result['verification_score'] = float(verification_score)
        result['speaker_verified'] = bool(verification_score > self.threshold)

        if check_replay:
            replay_result = self.replay_detector.detect_replay(test_audio)
            result['replay_detection'] = replay_result
            result['is_replay'] = bool(
                replay_result['replay_probability'] > self.replay_threshold
            )
        else:
            result['is_replay'] = False

        if check_liveness:
            liveness_result = self.liveness_detector.detect_liveness(test_audio)
            result['liveness_detection'] = liveness_result
            result['is_live'] = bool(
                liveness_result['liveness_probability'] > self.liveness_threshold
            )
        else:
            result['is_live'] = True

        if check_spoofing:
            spoofing_result = self.anti_spoofing_detector.detect_spoofing(
                test_audio, self.registered_audio
            )
            result['spoofing_detection'] = spoofing_result
            result['is_spoofed'] = bool(spoofing_result['is_spoofed'])
        else:
            result['is_spoofed'] = False

        passed_checks = 0
        total_checks = 0
        overall_score = 0.0

        if result['speaker_verified']:
            passed_checks += 1
            overall_score += verification_score * 0.4
        total_checks += 1

        if check_replay:
            if not result['is_replay']:
                passed_checks += 1
                overall_score += (1 - replay_result['replay_probability']) * 0.25
            total_checks += 1

        if check_liveness:
            if result['is_live']:
                passed_checks += 1
                overall_score += liveness_result['liveness_probability'] * 0.25
            total_checks += 1

        if check_spoofing:
            if not result['is_spoofed']:
                passed_checks += 1
                overall_score += (1 - spoofing_result['spoofing_probability']) * 0.1
            total_checks += 1

        result['passed_checks'] = int(passed_checks)
        result['total_checks'] = int(total_checks)
        result['overall_score'] = float(overall_score)
        result['verified'] = bool(passed_checks == total_checks)

        result['decision'] = '通过' if result['verified'] else '拒绝'
        if result['is_replay']:
            result['reject_reason'] = '检测到录音重放'
        elif not result['is_live']:
            result['reject_reason'] = '未通过活体检测'
        elif result['is_spoofed']:
            result['reject_reason'] = '检测到语音伪装'
        elif not result['speaker_verified']:
            result['reject_reason'] = '说话人不匹配'
        else:
            result['reject_reason'] = None

        return result

    def unlock(self, test_audio_path: str, **kwargs) -> Dict[str, Any]:
        return self.verify(test_audio_path, **kwargs)

    def generate_report(self, result: Dict[str, Any]) -> str:
        report = []
        report.append("=" * 60)
        report.append("声纹锁系统验证报告")
        report.append("=" * 60)
        report.append("")

        report.append(f"音频文件: {result['audio_path']}")
        report.append(f"音频时长: {result['audio_duration']:.2f}秒")
        report.append("")

        report.append(f"最终结果: {'✅ 验证通过' if result['verified'] else '❌ 验证拒绝'}")
        report.append(f"综合得分: {result['overall_score']:.4f}")
        report.append(f"通过检查: {result['passed_checks']}/{result['total_checks']}")
        if result.get('reject_reason'):
            report.append(f"拒绝原因: {result['reject_reason']}")
        report.append("")

        report.append("1. 说话人验证")
        report.append("-" * 40)
        report.append(f"  得分: {result['verification_score']:.4f}")
        report.append(f"  阈值: {self.threshold:.4f}")
        report.append(f"  结果: {'✅ 通过' if result['speaker_verified'] else '❌ 失败'}")
        report.append("")

        if 'replay_detection' in result:
            report.append("2. 录音重放检测")
            report.append("-" * 40)
            rd = result['replay_detection']
            report.append(f"  重放概率: {rd['replay_probability']:.4f}")
            report.append(f"  阈值: {self.replay_threshold:.4f}")
            report.append(f"  结果: {'✅ 非重放' if not result['is_replay'] else '❌ 检测到重放'}")
            report.append(f"  谐波比: {rd['harmonic_features']['harmonic_ratio']:.4f}")
            report.append(f"  频谱平坦度: {rd['spectral_features']['flatness_mean']:.4f}")
            report.append("")

        if 'liveness_detection' in result:
            report.append("3. 活体检测")
            report.append("-" * 40)
            ld = result['liveness_detection']
            report.append(f"  活体概率: {ld['liveness_probability']:.4f}")
            report.append(f"  阈值: {self.liveness_threshold:.4f}")
            report.append(f"  结果: {'✅ 活体' if result['is_live'] else '❌ 非活体'}")
            report.append(f"  基音抖动: {ld['vibration_features']['jitter']:.6f}")
            report.append(f"  振幅抖动: {ld['vibration_features']['shimmer']:.6f}")
            report.append(f"  呼吸段占比: {ld['breath_features']['breath_duration_ratio']:.4f}")
            report.append("")

        if 'spoofing_detection' in result:
            report.append("4. 伪装检测")
            report.append("-" * 40)
            sd = result['spoofing_detection']
            report.append(f"  伪装概率: {sd['spoofing_probability']:.4f}")
            report.append(f"  结果: {'✅ 无伪装' if not result['is_spoofed'] else '❌ 检测到伪装'}")
            report.append(f"  估计SNR: {sd.get('estimated_snr', 0):.2f} dB")
            if sd.get('splicing_detection'):
                sd_det = sd['splicing_detection']
                report.append(f"  拼接检测: {'是' if sd_det['is_spliced'] else '否'}")
                report.append(f"  拼接概率: {sd_det['splicing_probability']:.4f}")
            report.append("")

        report.append("=" * 60)

        return "\n".join(report)
