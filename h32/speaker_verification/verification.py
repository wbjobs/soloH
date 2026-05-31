import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from . import utils
from .embedding import SpeakerEmbeddingExtractor
from .anti_spoofing import AntiSpoofingDetector
from .pitch_recovery import AudioRestoration


class SpeakerVerifier:
    def __init__(self, model_type: str = 'ecapa', embedding_dim: int = 192,
                 sample_rate: int = 16000, device: str = 'cpu',
                 phase_threshold: float = 0.3, spectral_threshold: float = 0.7,
                 scoring: str = 'cosine', threshold: float = 0.5):
        self.sample_rate = sample_rate
        self.scoring = scoring
        self.threshold = threshold

        self.embedding_extractor = SpeakerEmbeddingExtractor(
            model_type=model_type, embedding_dim=embedding_dim,
            sample_rate=sample_rate, device=device
        )

        self.anti_spoofing_detector = AntiSpoofingDetector(
            sample_rate=sample_rate,
            phase_residual_threshold=phase_threshold,
            spectral_consistency_threshold=spectral_threshold
        )

        self.audio_restoration = AudioRestoration(
            sample_rate=sample_rate, wavelet='morlet',
            n_scales=32, n_fft=512, hop_length=160
        )

        self.enrolled_embedding: Optional[np.ndarray] = None
        self.enrolled_audio: Optional[np.ndarray] = None

    def enroll_speaker(self, audio_paths: List[str]) -> Dict[str, Any]:
        audio_samples = []
        for path in audio_paths:
            audio, _ = utils.load_audio(path, sample_rate=self.sample_rate)
            audio = utils.normalize_audio(audio)
            audio = utils.apply_vad(audio, sample_rate=self.sample_rate)
            audio_samples.append(audio)

        self.enrolled_embedding = self.embedding_extractor.enroll_speaker(audio_samples)
        self.enrolled_audio = audio_samples[0] if audio_samples else None

        return {
            'enrollment_successful': True,
            'num_enrollment_samples': len(audio_samples),
            'embedding_dim': len(self.enrolled_embedding),
            'enrolled': True
        }

    def set_enrolled_embedding(self, embedding: np.ndarray,
                               enrolled_audio: Optional[np.ndarray] = None) -> None:
        self.enrolled_embedding = embedding
        self.enrolled_audio = enrolled_audio

    def verify(self, test_audio_path: str,
               apply_restoration: bool = True) -> Dict[str, Any]:
        if self.enrolled_embedding is None:
            raise ValueError("未注册说话人，请先调用 enroll_speaker")

        test_audio, _ = utils.load_audio(test_audio_path, sample_rate=self.sample_rate)
        test_audio = utils.normalize_audio(test_audio)
        test_audio = utils.apply_vad(test_audio, sample_rate=self.sample_rate)

        spoofing_result = self.anti_spoofing_detector.detect_spoofing(
            test_audio, self.enrolled_audio
        )

        estimated_pitch_factor = spoofing_result['estimated_pitch_factor']

        restored_audio = None
        restoration_info = {}

        if apply_restoration and spoofing_result['is_spoofed']:
            restored_audio, restoration_info = self.audio_restoration.restore_audio(
                test_audio,
                estimated_pitch_factor=estimated_pitch_factor,
                reference_audio=self.enrolled_audio,
                use_iterative=False
            )

        test_embedding = self.embedding_extractor.extract_embedding(test_audio)

        if restored_audio is not None:
            restored_embedding = self.embedding_extractor.extract_embedding(restored_audio)
        else:
            restored_embedding = test_embedding

        verification_score = self._compute_score(
            self.enrolled_embedding, test_embedding
        )

        restored_score = self._compute_score(
            self.enrolled_embedding, restored_embedding
        )

        decision = verification_score > self.threshold
        restored_decision = restored_score > self.threshold

        result = {
            'verification_score': float(verification_score),
            'restored_verification_score': float(restored_score),
            'decision': bool(decision),
            'restored_decision': bool(restored_decision),
            'threshold': float(self.threshold),
            'scoring_method': self.scoring,
            'spoofing_detection': spoofing_result,
            'audio_restoration': restoration_info,
            'estimated_pitch_factor': float(estimated_pitch_factor),
            'estimated_semitones': float(spoofing_result['estimated_semitones']),
            'embedding_similarity_raw': float(verification_score),
            'embedding_similarity_restored': float(restored_score)
        }

        return result

    def verify_with_spoofing_simulation(self, enroll_audio_path: str,
                                        test_audio_path: str,
                                        spoofing_type: str = 'random',
                                        **kwargs) -> Dict[str, Any]:
        from .spoofing import SpoofingSimulator

        enroll_result = self.enroll_speaker([enroll_audio_path])

        test_audio, _ = utils.load_audio(test_audio_path, sample_rate=self.sample_rate)
        test_audio = utils.normalize_audio(test_audio)

        simulator = SpoofingSimulator(sample_rate=self.sample_rate)

        if spoofing_type == 'pitch_shift':
            n_steps = kwargs.get('n_steps', 2.0)
            spoofed_audio, spoofing_info = simulator.apply_pitch_shift_psola(test_audio, n_steps)
        elif spoofing_type == 'time_stretch':
            rate = kwargs.get('rate', 1.2)
            spoofed_audio, spoofing_info = simulator.apply_time_stretch_resample(test_audio, rate)
        elif spoofing_type == 'phase_vocoder':
            pitch_shift = kwargs.get('pitch_shift', 2.0)
            time_stretch = kwargs.get('time_stretch', 1.0)
            spoofed_audio, spoofing_info = simulator.apply_phase_vocoder(test_audio, pitch_shift, time_stretch)
        elif spoofing_type == 'replay':
            quality = kwargs.get('quality', 'medium')
            spoofed_audio, spoofing_info = simulator.apply_replay_attack(test_audio, quality)
        elif spoofing_type == 'random':
            spoofed_audio, spoofing_info = simulator.apply_random_spoofing(test_audio)
        else:
            spoofed_audio = test_audio
            spoofing_info = {'type': 'none'}

        temp_path = 'temp_spoofed.wav'
        utils.save_audio(temp_path, spoofed_audio, self.sample_rate)

        verification_result = self.verify(temp_path, apply_restoration=True)

        import os
        if os.path.exists(temp_path):
            os.remove(temp_path)

        result = {
            'enrollment': enroll_result,
            'applied_spoofing': spoofing_info,
            'verification': verification_result
        }

        return result

    def _compute_score(self, embedding1: np.ndarray,
                       embedding2: np.ndarray) -> float:
        if self.scoring == 'cosine':
            return utils.cosine_similarity(embedding1, embedding2)
        elif self.scoring == 'l2':
            dist = utils.l2_distance(embedding1, embedding2)
            return 1.0 / (1.0 + dist)
        else:
            return utils.cosine_similarity(embedding1, embedding2)

    def compute_similarity_matrix(self, embeddings: List[np.ndarray]) -> np.ndarray:
        n = len(embeddings)
        matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(n):
                matrix[i, j] = self._compute_score(embeddings[i], embeddings[j])

        return matrix

    def adaptive_threshold_update(self, genuine_scores: List[float],
                                  impostor_scores: List[float],
                                  target_far: float = 0.01) -> float:
        all_scores = genuine_scores + impostor_scores
        labels = [1] * len(genuine_scores) + [0] * len(impostor_scores)

        sorted_scores = sorted(all_scores, reverse=True)

        far = 1.0
        threshold = sorted_scores[0]

        for score in sorted_scores:
            current_far = sum(1 for s, l in zip(all_scores, labels)
                            if s >= score and l == 0) / max(len(impostor_scores), 1)
            if current_far <= target_far:
                threshold = score
                far = current_far
                break

        self.threshold = threshold
        return threshold


class VerificationReport:
    @staticmethod
    def generate(result: Dict[str, Any]) -> str:
        report = []
        report.append("=" * 60)
        report.append("说话人验证报告")
        report.append("=" * 60)
        report.append("")

        report.append("1. 验证结果")
        report.append("-" * 40)
        report.append(f"   原始验证得分: {result['verification_score']:.4f}")
        report.append(f"   恢复后验证得分: {result['restored_verification_score']:.4f}")
        report.append(f"   判决阈值: {result['threshold']:.4f}")
        report.append(f"   原始判决: {'通过' if result['decision'] else '拒绝'}")
        report.append(f"   恢复后判决: {'通过' if result['restored_decision'] else '拒绝'}")
        report.append("")

        report.append("2. 反伪装检测")
        report.append("-" * 40)
        spoofing = result['spoofing_detection']
        report.append(f"   伪装存在概率: {spoofing['spoofing_probability']:.4f}")
        report.append(f"   是否检测到伪装: {'是' if spoofing['is_spoofed'] else '否'}")
        report.append(f"   估计变调因子: {result['estimated_pitch_factor']:.4f}")
        report.append(f"   估计变调半音数: {result['estimated_semitones']:.2f} 半音")
        if 'estimated_snr' in spoofing:
            report.append(f"   估计信噪比: {spoofing['estimated_snr']:.2f} dB")
        if spoofing.get('splicing_detection'):
            sd = spoofing['splicing_detection']
            report.append(f"   拼接检测概率: {sd['splicing_probability']:.4f}")
            report.append(f"   是否检测到拼接: {'是' if sd['is_spliced'] else '否'}")
            report.append(f"   拼接点数量: {sd['num_detections']}")
            if sd['detections']:
                for i, det in enumerate(sd['detections'][:3]):
                    report.append(f"     拼接点{i+1}: {det['time']:.3f}s (得分: {det['score']:.3f})")
        report.append("")

        report.append("3. 相位残差特征")
        report.append("-" * 40)
        phase = spoofing['phase_features']
        report.append(f"   平均相位残差: {phase['mean_phase_residual']:.4f}")
        report.append(f"   相位残差标准差: {phase['std_phase_residual']:.4f}")
        report.append(f"   最大相位残差: {phase['max_phase_residual']:.4f}")
        report.append(f"   群延迟方差: {phase['group_delay_variance']:.4f}")
        report.append("")

        report.append("4. 频谱一致性特征")
        report.append("-" * 40)
        spectral = spoofing['spectral_features']
        report.append(f"   频谱平坦度: {spectral['spectral_flatness']:.4f}")
        report.append(f"   相邻帧相关性: {spectral['adjacent_spectral_correlation']:.4f}")
        report.append(f"   谐波失真度: {spectral['harmonic_distortion']:.4f}")
        report.append(f"   频谱质心: {spectral['spectral_centroid']:.2f} Hz")
        report.append("")

        if result.get('audio_restoration'):
            report.append("5. 音频恢复信息")
            report.append("-" * 40)
            restoration = result['audio_restoration']
            if restoration.get('pitch_recovery'):
                pr = restoration['pitch_recovery']
                report.append(f"   音调恢复: {'已执行' if pr.get('recovered') else '未执行'}")
                if pr.get('applied_semitones') is not None:
                    report.append(f"   应用变调补偿: {pr['applied_semitones']:.2f} 半音")
            if restoration.get('spectral_restoration'):
                sr_info = restoration['spectral_restoration']
                report.append(f"   频谱修复: {'已执行' if sr_info.get('restored') else '未执行'}")
                report.append(f"   频谱匹配: {'已应用' if sr_info.get('spectral_matching') else '未应用'}")
            if restoration.get('final_snr_improvement') is not None:
                report.append(f"   SNR改善: {restoration['final_snr_improvement']:.2f} dB")
            report.append("")

        report.append("6. 嵌入相似度")
        report.append("-" * 40)
        report.append(f"   原始嵌入相似度: {result['embedding_similarity_raw']:.4f}")
        report.append(f"   恢复后嵌入相似度: {result['embedding_similarity_restored']:.4f}")
        report.append(f"   相似度提升: {result['embedding_similarity_restored'] - result['embedding_similarity_raw']:.4f}")
        report.append("")
        report.append("=" * 60)

        return "\n".join(report)

    @staticmethod
    def to_dict(result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'verification_score': result['verification_score'],
            'restored_verification_score': result['restored_verification_score'],
            'decision': result['decision'],
            'restored_decision': result['restored_decision'],
            'threshold': result['threshold'],
            'spoofing_probability': result['spoofing_detection']['spoofing_probability'],
            'is_spoofed': result['spoofing_detection']['is_spoofed'],
            'estimated_pitch_factor': result['estimated_pitch_factor'],
            'estimated_semitones': result['estimated_semitones'],
            'estimated_snr': result['spoofing_detection'].get('estimated_snr'),
            'embedding_similarity_raw': result['embedding_similarity_raw'],
            'embedding_similarity_restored': result['embedding_similarity_restored'],
            'phase_features': result['spoofing_detection']['phase_features'],
            'spectral_features': result['spoofing_detection']['spectral_features'],
            'pitch_estimation': result['spoofing_detection']['pitch_estimation'],
            'splicing_detection': result['spoofing_detection'].get('splicing_detection'),
            'audio_restoration': result.get('audio_restoration', {})
        }
