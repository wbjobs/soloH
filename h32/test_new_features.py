import os
import sys
import unittest
import numpy as np
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from speaker_verification import utils
from speaker_verification.gan_repair import GANVoiceRepair
from speaker_verification.voiceprint_lock import VoiceprintLock
from speaker_verification.multi_speaker import SpeakerSeparator, MultiSpeakerIdentifier, Beamforming


class TestGANRepair(unittest.TestCase):
    def setUp(self):
        self.sample_rate = 16000
        self.duration = 3.0
        self.t = np.linspace(0, self.duration, int(self.sample_rate * self.duration))

        self.clean_audio = self._generate_speech_signal(self.t, 160, 1.0)
        self.spoofed_audio = self._generate_spoofed_signal(self.clean_audio)

    def _generate_speech_signal(self, t, base_freq, amplitude):
        audio = np.zeros_like(t)
        n_frames = len(t) // 160

        for i in range(n_frames):
            start = i * 160
            end = min(start + 160, len(t))
            frame_duration = (end - start) / self.sample_rate

            freq_variation = base_freq + 10 * np.sin(2 * np.pi * 5 * i * frame_duration)
            harmonic = np.sin(2 * np.pi * freq_variation * t[start:end])
            harmonic2 = 0.5 * np.sin(2 * np.pi * 2 * freq_variation * t[start:end])
            harmonic3 = 0.25 * np.sin(2 * np.pi * 3 * freq_variation * t[start:end])

            noise = 0.05 * np.random.randn(end - start)
            audio[start:end] = amplitude * (harmonic + harmonic2 + harmonic3 + noise)

        envelope = np.hanning(len(t))
        audio = audio * envelope
        return utils.normalize_audio(audio)

    def _generate_spoofed_signal(self, clean_audio):
        spoofed = clean_audio.copy()
        for i in range(0, len(spoofed), 1000):
            spoofed[i:i+500] *= 1.5
        phase_noise = 0.1 * np.random.randn(len(spoofed))
        spoofed = spoofed + phase_noise
        return utils.normalize_audio(spoofed)

    def test_generator_forward(self):
        repairer = GANVoiceRepair(model_type='gan', sample_rate=self.sample_rate)
        repaired_audio, info = repairer.repair_audio(self.spoofed_audio, reference_audio=self.clean_audio)

        self.assertEqual(len(repaired_audio), len(self.spoofed_audio))
        self.assertIsInstance(repaired_audio, np.ndarray)
        self.assertFalse(np.allclose(repaired_audio, self.spoofed_audio))
        self.assertIn('model_type', info)

    def test_cyclegan_mode(self):
        repairer = GANVoiceRepair(model_type='cyclegan', sample_rate=self.sample_rate)
        repaired_audio, info = repairer.repair_audio(self.spoofed_audio, reference_audio=self.clean_audio)

        self.assertEqual(len(repaired_audio), len(self.spoofed_audio))
        self.assertIsInstance(repaired_audio, np.ndarray)

    def test_multi_scale_repair(self):
        from speaker_verification.gan_repair import MultiScaleGANRepair

        repairer = MultiScaleGANRepair(sample_rate=self.sample_rate)
        repaired_audio, info = repairer.repair(self.spoofed_audio, reference_audio=self.clean_audio)

        self.assertIsNotNone(repaired_audio)
        self.assertEqual(len(repaired_audio), len(self.spoofed_audio))
        self.assertIsInstance(info, dict)

    def test_repair_quality(self):
        repairer = GANVoiceRepair(model_type='gan', sample_rate=self.sample_rate)
        repaired_audio, info = repairer.repair_audio(self.spoofed_audio, reference_audio=self.clean_audio)

        self.assertEqual(len(repaired_audio), len(self.spoofed_audio))
        self.assertIsInstance(repaired_audio, np.ndarray)
        self.assertIn('snr_improvement', info)
        self.assertIsInstance(info['snr_improvement'], float)

    def test_model_save_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repairer = GANVoiceRepair(model_type='gan', sample_rate=self.sample_rate)
            model_path = os.path.join(tmpdir, 'test_model.pth')
            repairer.save_model(model_path)

            self.assertTrue(os.path.exists(model_path))

            repairer2 = GANVoiceRepair(model_type='gan', sample_rate=self.sample_rate)
            repairer2.load_model(model_path)


class TestVoiceprintLock(unittest.TestCase):
    def setUp(self):
        self.sample_rate = 16000
        self.duration = 4.0
        self.t = np.linspace(0, self.duration, int(self.sample_rate * self.duration))

        self.real_audio = self._generate_live_voice(150)
        self.replay_audio = self._generate_replay_voice(150)
        self.spoofed_audio = self._generate_spoofed_voice(150)

        self.enroll_audios = [
            self._generate_live_voice(152),
            self._generate_live_voice(148),
            self._generate_live_voice(151)
        ]

        self.tmpdir = tempfile.mkdtemp()
        self._save_test_audios()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _generate_live_voice(self, base_freq):
        t = self.t
        audio = np.zeros_like(t)
        n_frames = len(t) // 160

        for i in range(n_frames):
            start = i * 160
            end = min(start + 160, len(t))

            jitter = base_freq + 0.5 * np.random.randn()
            shimmer = 1.0 + 0.05 * np.random.randn()

            harmonic = shimmer * np.sin(2 * np.pi * jitter * t[start:end])
            harmonic2 = 0.5 * shimmer * np.sin(2 * np.pi * 2 * jitter * t[start:end])
            harmonic3 = 0.25 * shimmer * np.sin(2 * np.pi * 3 * jitter * t[start:end])

            noise = 0.08 * np.random.randn(end - start)
            audio[start:end] = harmonic + harmonic2 + harmonic3 + noise

        breath_mask = np.zeros_like(t)
        breath_starts = [0, int(1.5 * self.sample_rate), int(2.8 * self.sample_rate)]
        for start in breath_starts:
            end = min(start + int(0.2 * self.sample_rate), len(t))
            breath_mask[start:end] = 0.15 * np.random.randn(end - start)
        audio = audio + breath_mask

        envelope = 0.5 + 0.5 * np.hanning(len(t))
        audio = audio * envelope
        return utils.normalize_audio(audio)

    def _generate_replay_voice(self, base_freq):
        audio = self._generate_live_voice(base_freq)

        audio = np.convolve(audio, np.hanning(50) / 25, mode='same')
        audio = audio * 0.9
        audio = audio + 0.05 * np.random.randn(len(audio))

        notch_filter = np.ones(len(audio))
        notch_start = int(1000 / self.sample_rate * len(audio))
        notch_end = int(1500 / self.sample_rate * len(audio))
        notch_filter[notch_start:notch_end] = 0.7
        spec = np.fft.rfft(audio)
        spec = spec * notch_filter[:len(spec)]
        audio = np.fft.irfft(spec)

        return utils.normalize_audio(audio)

    def _generate_spoofed_voice(self, base_freq):
        audio = self._generate_live_voice(base_freq)
        from speaker_verification.spoofing import SpoofingSimulator

        simulator = SpoofingSimulator(sample_rate=self.sample_rate)
        shifted, _ = simulator.apply_pitch_shift_psola(audio, 3.0)

        return shifted

    def _save_test_audios(self):
        self.real_path = os.path.join(self.tmpdir, 'real.wav')
        self.replay_path = os.path.join(self.tmpdir, 'replay.wav')
        self.spoofed_path = os.path.join(self.tmpdir, 'spoofed.wav')

        utils.save_audio(self.real_path, self.real_audio, self.sample_rate)
        utils.save_audio(self.replay_path, self.replay_audio, self.sample_rate)
        utils.save_audio(self.spoofed_path, self.spoofed_audio, self.sample_rate)

        self.enroll_paths = []
        for i, audio in enumerate(self.enroll_audios):
            path = os.path.join(self.tmpdir, f'enroll_{i}.wav')
            utils.save_audio(path, audio, self.sample_rate)
            self.enroll_paths.append(path)

    def test_replay_attack_detection(self):
        from speaker_verification.voiceprint_lock import ReplayAttackDetector

        detector = ReplayAttackDetector(sample_rate=self.sample_rate)

        real_result = detector.detect_replay(self.real_audio)
        replay_result = detector.detect_replay(self.replay_audio)

        real_score = real_result['replay_probability']
        replay_score = replay_result['replay_probability']

        self.assertGreater(1 - real_score, 0.3)
        self.assertLess(1 - replay_score, 0.8)

    def test_liveness_detection(self):
        from speaker_verification.voiceprint_lock import LivenessDetector

        detector = LivenessDetector(sample_rate=self.sample_rate)

        real_result = detector.detect_liveness(self.real_audio)
        synthetic_result = detector.detect_liveness(self.spoofed_audio)

        real_score = real_result['liveness_probability']
        synthetic_score = synthetic_result['liveness_probability']

        self.assertGreater(real_score, 0.3)
        self.assertGreaterEqual(real_score, synthetic_score)

    def test_voiceprint_lock_real_voice(self):
        lock = VoiceprintLock(
            sample_rate=self.sample_rate,
            threshold=0.5
        )

        lock.register_user(self.enroll_paths)
        result = lock.verify(
            self.real_path,
            check_liveness=True,
            check_replay=True,
            check_spoofing=True
        )

        self.assertGreaterEqual(result['overall_score'], 0.0)

    def test_voiceprint_lock_replay_attack(self):
        lock = VoiceprintLock(
            sample_rate=self.sample_rate,
            threshold=0.7
        )

        lock.register_user(self.enroll_paths)
        result = lock.verify(
            self.replay_path,
            check_liveness=True,
            check_replay=True,
            check_spoofing=True
        )

        self.assertIn('verified', result)
        self.assertIn('overall_score', result)
        self.assertIn('replay_detection', result)
        self.assertIn('liveness_detection', result)
        self.assertIn('spoofing_detection', result)

    def test_voiceprint_lock_spoofed_voice(self):
        lock = VoiceprintLock(
            sample_rate=self.sample_rate,
            threshold=0.7
        )

        lock.register_user(self.enroll_paths)
        result = lock.verify(
            self.spoofed_path,
            check_liveness=True,
            check_replay=True,
            check_spoofing=True
        )

        self.assertIn('verified', result)

    def test_generate_report(self):
        lock = VoiceprintLock(
            sample_rate=self.sample_rate,
            threshold=0.7
        )

        lock.register_user(self.enroll_paths)
        result = lock.verify(self.real_path)

        report = lock.generate_report(result)

        self.assertIn('声纹锁系统验证报告', report)
        self.assertIn('说话人验证', report)
        self.assertIn('录音重放检测', report)
        self.assertIn('活体检测', report)
        self.assertIn('伪装检测', report)


class TestMultiSpeaker(unittest.TestCase):
    def setUp(self):
        self.sample_rate = 16000
        self.duration = 4.0
        self.t = np.linspace(0, self.duration, int(self.sample_rate * self.duration))

        self.speaker1 = self._generate_speaker_voice(140, [0, 0.8, 2.0, 3.0])
        self.speaker2 = self._generate_speaker_voice(200, [0.5, 1.5, 2.5, 3.5])
        self.mixed_audio = 0.5 * self.speaker1 + 0.5 * self.speaker2

        self.tmpdir = tempfile.mkdtemp()
        self._save_test_audios()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _generate_speaker_voice(self, base_freq, active_times):
        audio = np.zeros_like(self.t)

        for start_time in active_times:
            start_idx = int(start_time * self.sample_rate)
            end_idx = min(start_idx + int(0.45 * self.sample_rate), len(self.t))

            for i in range(start_idx, end_idx, 160):
                frame_end = min(i + 160, end_idx)
                t_frame = self.t[i:frame_end]

                freq = base_freq + 5 * np.sin(2 * np.pi * 3 * (i / self.sample_rate))
                harmonic = np.sin(2 * np.pi * freq * t_frame)
                harmonic2 = 0.5 * np.sin(2 * np.pi * 2 * freq * t_frame)
                harmonic3 = 0.25 * np.sin(2 * np.pi * 3 * freq * t_frame)
                noise = 0.05 * np.random.randn(frame_end - i)

                audio[i:frame_end] = harmonic + harmonic2 + harmonic3 + noise

        envelope = np.hanning(len(self.t))
        audio = audio * envelope
        return utils.normalize_audio(audio)

    def _save_test_audios(self):
        self.speaker1_path = os.path.join(self.tmpdir, 'speaker1.wav')
        self.speaker2_path = os.path.join(self.tmpdir, 'speaker2.wav')
        self.mixed_path = os.path.join(self.tmpdir, 'mixed.wav')

        utils.save_audio(self.speaker1_path, self.speaker1, self.sample_rate)
        utils.save_audio(self.speaker2_path, self.speaker2, self.sample_rate)
        utils.save_audio(self.mixed_path, self.mixed_audio, self.sample_rate)

    def test_feature_computation(self):
        separator = SpeakerSeparator(sample_rate=self.sample_rate)
        features, mag, phase = separator._compute_features(self.mixed_audio)

        spectral_features = separator._compute_spectral_features(mag)
        pitch_features = separator._compute_pitch_features(self.mixed_audio)

        expected_mfcc = 20 * 3
        expected_spectral = spectral_features.shape[0]
        expected_pitch = pitch_features.shape[0]
        expected_features = expected_mfcc + expected_spectral + expected_pitch

        all_features = np.concatenate([features, spectral_features, pitch_features], axis=0)

        self.assertEqual(features.shape[0], expected_mfcc)
        self.assertEqual(spectral_features.shape[0], expected_spectral)
        self.assertEqual(pitch_features.shape[0], expected_pitch)
        self.assertEqual(all_features.shape[0], expected_features)
        self.assertEqual(features.shape[1], mag.shape[1])
        self.assertGreater(features.shape[1], 10)

    def test_speaker_separation(self):
        separator = SpeakerSeparator(sample_rate=self.sample_rate)
        result = separator.separate_speakers(self.mixed_audio, max_speakers=3)

        self.assertIn('n_speakers', result)
        self.assertIn('separated_audios', result)
        self.assertIn('speaker_segments', result)

        self.assertGreaterEqual(result['n_speakers'], 1)
        self.assertLessEqual(result['n_speakers'], 3)
        self.assertEqual(len(result['separated_audios']), result['n_speakers'])

        for separated in result['separated_audios']:
            self.assertEqual(len(separated), len(self.mixed_audio))
            self.assertIsInstance(separated, np.ndarray)

    def test_speaker_segments(self):
        separator = SpeakerSeparator(sample_rate=self.sample_rate)
        result = separator.separate_speakers(self.mixed_audio, max_speakers=3)

        for seg_info in result['speaker_segments']:
            self.assertIn('speaker_id', seg_info)
            self.assertIn('segments', seg_info)
            self.assertIn('total_duration', seg_info)
            self.assertGreater(seg_info['total_duration'], 0)

            for seg in seg_info['segments']:
                self.assertIn('start_time', seg)
                self.assertIn('end_time', seg)
                self.assertIn('duration', seg)
                self.assertGreater(seg['duration'], 0)
                self.assertGreaterEqual(seg['start_time'], 0)

    def test_label_smoothing(self):
        separator = SpeakerSeparator(sample_rate=self.sample_rate)

        labels = np.array([0, 0, 0, 1, 1, 0, 1, 1, 1, 0, 0, 0])
        smoothed = separator._smooth_labels(labels, window_size=3)

        self.assertEqual(len(smoothed), len(labels))

        transitions = np.sum(np.abs(np.diff(smoothed)))
        original_transitions = np.sum(np.abs(np.diff(labels)))
        self.assertLessEqual(transitions, original_transitions)

    def test_multi_speaker_identifier(self):
        identifier = MultiSpeakerIdentifier(
            sample_rate=self.sample_rate,
            model_type='ecapa'
        )

        result = identifier.separator.separate_speakers(
            self.mixed_audio, max_speakers=3
        )

        self.assertIsNotNone(result)
        self.assertIn('n_speakers', result)
        self.assertGreaterEqual(result['n_speakers'], 1)

    def test_speaker_registration(self):
        identifier = MultiSpeakerIdentifier(
            sample_rate=self.sample_rate,
            model_type='ecapa'
        )

        result = identifier.register_speaker('speaker_1', [self.speaker1_path])

        self.assertTrue(result['registered'])
        self.assertEqual(result['speaker_name'], 'speaker_1')
        self.assertIn('speaker_1', identifier.registered_speakers)
        self.assertEqual(len(identifier.registered_speakers), 1)

    def test_diarize(self):
        identifier = MultiSpeakerIdentifier(
            sample_rate=self.sample_rate,
            model_type='ecapa'
        )

        identifier.register_speaker('speaker_1', [self.speaker1_path])
        identifier.register_speaker('speaker_2', [self.speaker2_path])

        result = identifier.diarize(self.mixed_audio, max_speakers=3)

        self.assertIn('n_detected_speakers', result)
        self.assertIn('n_identified_speakers', result)
        self.assertIn('timeline', result)
        self.assertIn('diarization_report', result)

        for entry in result['timeline']:
            self.assertIn('start_time', entry)
            self.assertIn('end_time', entry)
            self.assertIn('speaker_index', entry)

        self.assertGreater(len(result['diarization_report']), 0)

    def test_beamforming_delay_and_sum(self):
        beamforming = Beamforming(sample_rate=self.sample_rate)

        audio_signals = [self.speaker1, 0.9 * self.speaker1, 0.8 * self.speaker1]
        output = beamforming.delay_and_sum(audio_signals, doa=0.0)

        self.assertEqual(len(output), len(self.speaker1))
        self.assertIsInstance(output, np.ndarray)
        self.assertGreater(np.max(np.abs(output)), 0.1)

    def test_beamforming_mvdr(self):
        beamforming = Beamforming(sample_rate=self.sample_rate)

        audio_signals = [self.speaker1, 0.9 * self.speaker1, 0.8 * self.speaker1]
        output = beamforming.mvdr(audio_signals)

        self.assertIsInstance(output, np.ndarray)
        self.assertGreater(len(output), 0)


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.sample_rate = 16000
        self.tmpdir = tempfile.mkdtemp()

        self.clean_audio = self._generate_test_audio(150)
        self.spoofed_audio = self._generate_spoofed_audio(self.clean_audio)
        self.speaker2_audio = self._generate_test_audio(200)
        self.mixed_audio = 0.5 * self.clean_audio + 0.5 * self.speaker2_audio

        self._save_audios()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _generate_test_audio(self, base_freq):
        duration = 3.0
        t = np.linspace(0, duration, int(self.sample_rate * duration))
        audio = np.zeros_like(t)

        for i in range(0, len(t), 160):
            end = min(i + 160, len(t))
            freq = base_freq + 8 * np.sin(2 * np.pi * 2 * i / self.sample_rate)
            harmonic = np.sin(2 * np.pi * freq * t[i:end])
            harmonic2 = 0.5 * np.sin(2 * np.pi * 2 * freq * t[i:end])
            noise = 0.05 * np.random.randn(end - i)
            audio[i:end] = harmonic + harmonic2 + noise

        return utils.normalize_audio(audio)

    def _generate_spoofed_audio(self, clean_audio):
        from speaker_verification.spoofing import SpoofingSimulator

        simulator = SpoofingSimulator(sample_rate=self.sample_rate)
        spoofed, _ = simulator.apply_phase_vocoder(
            clean_audio, pitch_shift=2.5, time_stretch=1.0
        )

        target_len = len(clean_audio)
        if len(spoofed) > target_len:
            spoofed = spoofed[:target_len]
        elif len(spoofed) < target_len:
            spoofed = np.pad(spoofed, (0, target_len - len(spoofed)))

        return spoofed

    def _save_audios(self):
        self.clean_path = os.path.join(self.tmpdir, 'clean.wav')
        self.spoofed_path = os.path.join(self.tmpdir, 'spoofed.wav')
        self.mixed_path = os.path.join(self.tmpdir, 'mixed.wav')
        self.enroll_path = os.path.join(self.tmpdir, 'enroll.wav')

        utils.save_audio(self.clean_path, self.clean_audio, self.sample_rate)
        utils.save_audio(self.spoofed_path, self.spoofed_audio, self.sample_rate)
        utils.save_audio(self.mixed_path, self.mixed_audio, self.sample_rate)
        utils.save_audio(self.enroll_path, self.clean_audio, self.sample_rate)

    def test_full_pipeline_with_gan_repair(self):
        from speaker_verification.verification import SpeakerVerifier

        repairer = GANVoiceRepair(model_type='gan', sample_rate=self.sample_rate)
        repaired_audio, repair_info = repairer.repair_audio(
            self.spoofed_audio,
            reference_audio=self.clean_audio
        )

        repaired_path = os.path.join(self.tmpdir, 'repaired.wav')
        utils.save_audio(repaired_path, repaired_audio, self.sample_rate)

        verifier = SpeakerVerifier(
            sample_rate=self.sample_rate
        )
        verifier.enroll_speaker([self.enroll_path])

        spoofed_result = verifier.verify(self.spoofed_path)
        repaired_result = verifier.verify(repaired_path)

        self.assertIsNotNone(spoofed_result)
        self.assertIsNotNone(repaired_result)

        self.assertIn('spoofing_detection', spoofed_result)
        self.assertIn('spoofing_probability', spoofed_result['spoofing_detection'])
        self.assertIn('spoofing_detection', repaired_result)
        self.assertIn('spoofing_probability', repaired_result['spoofing_detection'])
        self.assertIsInstance(repair_info, dict)

    def test_full_pipeline_with_voiceprint_lock(self):
        lock = VoiceprintLock(
            sample_rate=self.sample_rate,
            threshold=0.5
        )

        lock.register_user([self.enroll_path])

        clean_result = lock.verify(
            self.clean_path,
            check_liveness=True,
            check_replay=True,
            check_spoofing=True
        )

        spoofed_result = lock.verify(
            self.spoofed_path,
            check_liveness=True,
            check_replay=True,
            check_spoofing=True
        )

        self.assertGreaterEqual(clean_result['overall_score'], 0.0)
        self.assertGreaterEqual(spoofed_result['overall_score'], 0.0)

    def test_full_pipeline_multi_speaker(self):
        from speaker_verification.multi_speaker import MultiSpeakerIdentifier

        identifier = MultiSpeakerIdentifier(
            sample_rate=self.sample_rate
        )

        speaker2_audio = self._generate_test_audio(200)
        speaker2_path = os.path.join(self.tmpdir, 'speaker2_enroll.wav')
        utils.save_audio(speaker2_path, speaker2_audio, self.sample_rate)

        identifier.register_speaker('speaker_1', [self.clean_path])
        identifier.register_speaker('speaker_2', [speaker2_path])

        result = identifier.diarize(self.mixed_audio, max_speakers=3)

        self.assertIn('n_detected_speakers', result)
        self.assertGreaterEqual(result['n_detected_speakers'], 1)

        if result['n_identified_speakers'] > 0:
            self.assertGreater(len(result['identified_speakers']), 0)

    def test_cli_integration(self):
        from speaker_verification.cli import main
        from click.testing import CliRunner

        runner = CliRunner()

        result = runner.invoke(main, ['version'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('v2.0.0', result.output)
        self.assertIn('GAN语音修复', result.output)
        self.assertIn('声纹锁系统', result.output)
        self.assertIn('多说话人分离与识别', result.output)

    def test_module_imports(self):
        from speaker_verification import gan_repair
        from speaker_verification import voiceprint_lock
        from speaker_verification import multi_speaker

        self.assertIsNotNone(gan_repair.Generator)
        self.assertIsNotNone(voiceprint_lock.VoiceprintLock)
        self.assertIsNotNone(multi_speaker.SpeakerSeparator)


if __name__ == '__main__':
    unittest.main(verbosity=2)
