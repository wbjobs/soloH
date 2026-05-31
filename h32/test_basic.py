import os
import sys
import numpy as np
import tempfile
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from speaker_verification import utils, embedding, spoofing, anti_spoofing, pitch_recovery, verification


def generate_test_audio(duration: float = 3.0, sample_rate: int = 16000,
                        freq: float = 200.0) -> np.ndarray:
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * freq * t)

    for harmonic in [2, 3, 4]:
        audio += 0.25 * np.sin(2 * np.pi * freq * harmonic * t) / harmonic

    noise = 0.01 * np.random.randn(len(audio))
    audio = audio + noise

    envelope = np.hanning(len(audio))
    audio = audio * envelope

    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.9

    return audio


def test_utils():
    print("测试工具函数模块...")
    audio = generate_test_audio()

    normalized = utils.normalize_audio(audio)
    assert normalized.shape == audio.shape, "归一化后形状不匹配"
    assert np.abs(np.mean(normalized ** 2) - 10 ** (-20 / 10)) < 0.1, "RMS归一化失败"

    mag, phase = utils.compute_stft(audio)
    assert mag.shape[0] == 257, "STFT幅度维度错误"
    assert phase.shape == mag.shape, "STFT相位维度不匹配"

    mel_spec = utils.compute_mel_spectrogram(audio)
    assert mel_spec.shape[0] == 80, "梅尔频谱维度错误"

    mfcc = utils.compute_mfcc(audio)
    assert mfcc.shape[0] == 20, "MFCC维度错误"

    vec1 = np.random.randn(192)
    vec2 = np.random.randn(192)
    sim = utils.cosine_similarity(vec1, vec2)
    assert -1.0 <= sim <= 1.0, "余弦相似度范围错误"

    print("  ✓ 工具函数测试通过")


def test_embedding():
    print("测试说话人嵌入模块...")
    audio = generate_test_audio(duration=2.0)

    extractor_ecapa = embedding.SpeakerEmbeddingExtractor(
        model_type='ecapa', embedding_dim=192
    )
    emb_ecapa = extractor_ecapa.extract_embedding(audio)
    assert emb_ecapa.shape == (192,), "ECAPA嵌入维度错误"
    assert np.abs(np.linalg.norm(emb_ecapa) - 1.0) < 0.01, "ECAPA嵌入未归一化"

    extractor_xvector = embedding.SpeakerEmbeddingExtractor(
        model_type='xvector', embedding_dim=512
    )
    emb_xvector = extractor_xvector.extract_embedding(audio)
    assert emb_xvector.shape == (512,), "X-Vector嵌入维度错误"
    assert np.abs(np.linalg.norm(emb_xvector) - 1.0) < 0.01, "X-Vector嵌入未归一化"

    audios = [generate_test_audio(duration=2.0, freq=200 + i * 10) for i in range(3)]
    enrolled = extractor_ecapa.enroll_speaker(audios)
    assert enrolled.shape == (192,), "注册嵌入维度错误"

    print("  ✓ 说话人嵌入模块测试通过")


def test_spoofing():
    print("测试伪装变换模块...")
    audio = generate_test_audio(duration=2.0, freq=200)
    original_len = len(audio)

    simulator = spoofing.SpoofingSimulator()

    shifted, info = simulator.apply_pitch_shift_psola(audio, n_steps=2.0)
    assert info['type'] == 'pitch_shift_psola', "PSOLA类型错误"
    assert np.abs(info['factor'] - 2 ** (2 / 12)) < 0.01, "变调因子计算错误"

    stretched, info = simulator.apply_time_stretch_resample(audio, rate=1.2)
    assert info['type'] == 'time_stretch_resample', "时间拉伸类型错误"
    assert len(stretched) == int(original_len / 1.2), "时间拉伸长度错误"

    processed, info = simulator.apply_phase_vocoder(audio, pitch_shift=2.0, time_stretch=1.0)
    assert info['type'] == 'phase_vocoder', "相位声码器类型错误"

    replayed, info = simulator.apply_replay_attack(audio, quality='medium')
    assert info['type'] == 'replay_attack', "回放攻击类型错误"
    assert replayed.shape == audio.shape, "回放攻击形状错误"

    audio2 = generate_test_audio(duration=2.0, freq=300)
    spliced, info = simulator.apply_splicing_attack(audio, audio2)
    assert info['type'] == 'splicing_attack', "拼接攻击类型错误"

    print("  ✓ 伪装变换模块测试通过")


def test_anti_spoofing():
    print("测试反伪装检测模块...")
    audio = generate_test_audio(duration=3.0, freq=200)

    detector = anti_spoofing.AntiSpoofingDetector()

    result = detector.detect_spoofing(audio)
    assert 'is_spoofed' in result, "缺少is_spoofed字段"
    assert 'spoofing_probability' in result, "缺少spoofing_probability字段"
    assert 0.0 <= result['spoofing_probability'] <= 1.0, "伪装概率范围错误"
    assert 'estimated_pitch_factor' in result, "缺少estimated_pitch_factor字段"

    simulator = spoofing.SpoofingSimulator()
    spoofed_audio, _ = simulator.apply_pitch_shift_psola(audio, n_steps=3.0)
    ref_audio = generate_test_audio(duration=3.0, freq=200)

    result_spoofed = detector.detect_spoofing(spoofed_audio, ref_audio)
    assert 'estimated_semitones' in result_spoofed, "缺少estimated_semitones字段"

    print("  ✓ 反伪装检测模块测试通过")


def test_pitch_recovery():
    print("测试音调恢复模块...")
    audio = generate_test_audio(duration=2.0, freq=200)

    restorer = pitch_recovery.AudioRestoration()

    simulator = spoofing.SpoofingSimulator()
    spoofed_audio, spoof_info = simulator.apply_pitch_shift_psola(audio, n_steps=2.0)
    pitch_factor = spoof_info['factor']

    restored, info = restorer.restore_audio(
        spoofed_audio,
        estimated_pitch_factor=pitch_factor,
        reference_audio=audio
    )

    assert restored.shape == spoofed_audio.shape, "恢复后音频形状不匹配"
    assert 'pitch_recovery' in info, "缺少pitch_recovery字段"
    assert 'spectral_restoration' in info, "缺少spectral_restoration字段"

    wavelet = pitch_recovery.WaveletAnalyzer(n_scales=16)
    cwt_matrix, freqs = wavelet.compute_cwt(audio[:32000])
    assert cwt_matrix.shape[0] == 16, "CWT尺度维度错误"
    assert cwt_matrix.shape[1] == 32000, "CWT时间维度错误"

    reconstructed = wavelet.compute_inverse_cwt(cwt_matrix, freqs)
    assert len(reconstructed) == 32000, "逆CWT长度错误"

    print("  ✓ 音调恢复模块测试通过")


def test_verification():
    print("测试验证模块...")

    with tempfile.TemporaryDirectory() as tmpdir:
        enroll_audio = generate_test_audio(duration=3.0, freq=200)
        test_audio = generate_test_audio(duration=3.0, freq=200)

        enroll_path = os.path.join(tmpdir, 'enroll.wav')
        test_path = os.path.join(tmpdir, 'test.wav')

        utils.save_audio(enroll_path, enroll_audio, 16000)
        utils.save_audio(test_path, test_audio, 16000)

        verifier = verification.SpeakerVerifier(
            model_type='ecapa', embedding_dim=192
        )

        enroll_result = verifier.enroll_speaker([enroll_path])
        assert enroll_result['enrollment_successful'] is True, "注册失败"

        verify_result = verifier.verify(test_path, apply_restoration=False)
        assert 'verification_score' in verify_result, "缺少verification_score字段"
        assert 'decision' in verify_result, "缺少decision字段"
        assert 'spoofing_detection' in verify_result, "缺少spoofing_detection字段"

        report = verification.VerificationReport.generate(verify_result)
        assert isinstance(report, str), "报告生成失败"
        assert len(report) > 0, "报告为空"

        result_dict = verification.VerificationReport.to_dict(verify_result)
        assert isinstance(result_dict, dict), "结果字典生成失败"

        simulate_result = verifier.verify_with_spoofing_simulation(
            enroll_path, test_path,
            spoofing_type='pitch_shift', n_steps=2.0
        )
        assert 'applied_spoofing' in simulate_result, "缺少applied_spoofing字段"
        assert 'verification' in simulate_result, "缺少verification字段"

    print("  ✓ 验证模块测试通过")


def test_integration():
    print("测试完整集成流程...")

    with tempfile.TemporaryDirectory() as tmpdir:
        enroll_audio = generate_test_audio(duration=3.0, freq=200)
        test_clean = generate_test_audio(duration=3.0, freq=200)
        test_spoofed_base = generate_test_audio(duration=3.0, freq=200)

        simulator = spoofing.SpoofingSimulator()
        test_spoofed, spoof_info = simulator.apply_pitch_shift_psola(
            test_spoofed_base, n_steps=3.0
        )

        enroll_path = os.path.join(tmpdir, 'enroll.wav')
        test_clean_path = os.path.join(tmpdir, 'test_clean.wav')
        test_spoofed_path = os.path.join(tmpdir, 'test_spoofed.wav')

        utils.save_audio(enroll_path, enroll_audio, 16000)
        utils.save_audio(test_clean_path, test_clean, 16000)
        utils.save_audio(test_spoofed_path, test_spoofed, 16000)

        verifier = verification.SpeakerVerifier(
            model_type='ecapa', embedding_dim=192, threshold=0.3
        )
        verifier.enroll_speaker([enroll_path])

        print("  测试干净音频验证...")
        result_clean = verifier.verify(test_clean_path, apply_restoration=True)
        print(f"    验证得分: {result_clean['verification_score']:.4f}")
        print(f"    伪装概率: {result_clean['spoofing_detection']['spoofing_probability']:.4f}")

        print("  测试伪装音频验证...")
        result_spoofed = verifier.verify(test_spoofed_path, apply_restoration=True)
        print(f"    原始验证得分: {result_spoofed['verification_score']:.4f}")
        print(f"    恢复后验证得分: {result_spoofed['restored_verification_score']:.4f}")
        print(f"    伪装概率: {result_spoofed['spoofing_detection']['spoofing_probability']:.4f}")
        print(f"    估计变调因子: {result_spoofed['estimated_pitch_factor']:.4f}")
        print(f"    估计变调半音数: {result_spoofed['estimated_semitones']:.2f}")
        print(f"    实际变调因子: {spoof_info['factor']:.4f}")
        print(f"    实际变调半音数: {spoof_info['n_steps']:.2f}")

        if result_spoofed.get('audio_restoration'):
            rest_info = result_spoofed['audio_restoration']
            if rest_info.get('final_snr_improvement') is not None:
                print(f"    SNR改善: {rest_info['final_snr_improvement']:.2f} dB")

    print("  ✓ 集成流程测试通过")


def main():
    print("=" * 60)
    print("说话人验证与反伪装检测工具 - 基本测试")
    print("=" * 60)
    print()

    try:
        test_utils()
        print()
        test_embedding()
        print()
        test_spoofing()
        print()
        test_anti_spoofing()
        print()
        test_pitch_recovery()
        print()
        test_verification()
        print()
        test_integration()
        print()

        print("=" * 60)
        print("所有测试通过! ✓")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
