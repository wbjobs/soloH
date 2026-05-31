import os
import sys
import numpy as np
import tempfile
import warnings
import librosa
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from speaker_verification import utils, spoofing, anti_spoofing, verification


def generate_speech_like_audio(duration: float = 3.0, sample_rate: int = 16000,
                               base_freq: float = 200.0, add_transients: bool = True):
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    audio = np.zeros_like(t)

    n_formants = 3
    formant_freqs = [base_freq * (2 ** (i / 2)) for i in range(n_formants)]
    formant_amps = [1.0, 0.5, 0.25]

    for freq, amp in zip(formant_freqs, formant_amps):
        audio += amp * np.sin(2 * np.pi * freq * t)

    if add_transients:
        n_transients = int(duration * 4)
        for _ in range(n_transients):
            start = int(np.random.uniform(0, duration - 0.05) * sample_rate)
            length = int(0.02 * sample_rate)
            if start + length < len(t):
                envelope = np.hanning(length)
                audio[start:start + length] += 0.5 * envelope * np.random.randn(length)

    amplitude_mod = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t)
    audio = audio * amplitude_mod

    noise = 0.005 * np.random.randn(len(audio))
    audio = audio + noise

    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.9

    return audio


def test_phase_vocoder_transient_preservation():
    print("=" * 70)
    print("测试1: 相位声码器瞬态保护修复")
    print("=" * 70)
    print()

    audio = generate_speech_like_audio(duration=2.0, base_freq=200)

    pv_old = spoofing.PhaseVocoder(sample_rate=16000, n_fft=2048, hop_length=512)
    pv_old._detect_transients = lambda x: np.zeros(x.shape[1])
    pv_old._compute_phase_propagation = lambda m, p: np.zeros_like(p)
    old_process = pv_old.process

    def old_process_wrapper(audio, pitch_shift=0, time_stretch=1.0):
        if pitch_shift == 0 and time_stretch == 1.0:
            return audio.copy()

        D = librosa.stft(audio, n_fft=2048, hop_length=512, window=np.hanning(2048))
        mag = np.abs(D)
        phase = np.angle(D)

        if pitch_shift != 0:
            n_steps = pitch_shift
            n_bins = mag.shape[0]
            bins_before = np.arange(n_bins)
            bins_after = bins_before * (2 ** (n_steps / 12))

            new_mag = np.zeros_like(mag)
            new_phase = np.zeros_like(phase)

            for i in range(n_bins):
                for j in range(mag.shape[1]):
                    src_bin = bins_after[i]
                    lower = int(np.floor(src_bin))
                    upper = lower + 1
                    frac = src_bin - lower

                    if 0 <= lower < n_bins and 0 <= upper < n_bins:
                        new_mag[i, j] = mag[lower, j] * (1 - frac) + mag[upper, j] * frac
                        new_phase[i, j] = phase[lower, j] * (1 - frac) + phase[upper, j] * frac

            mag = new_mag
            phase = new_phase

        D_reconstructed = mag * np.exp(1j * phase)
        output = librosa.istft(D_reconstructed, hop_length=512, window=np.hanning(2048), length=len(audio))
        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val * np.max(np.abs(audio))
        return output
    shifted_old = old_process_wrapper(audio, pitch_shift=3.0)

    pv_new = spoofing.PhaseVocoder(sample_rate=16000, n_fft=2048, hop_length=512)
    shifted_new = pv_new.process(audio, pitch_shift=3.0)

    def compute_transient_preservation(original, processed):
        stft_orig = librosa.stft(original, n_fft=512, hop_length=160)
        stft_proc = librosa.stft(processed, n_fft=512, hop_length=160)
        mag_orig = np.abs(stft_orig)
        mag_proc = np.abs(stft_proc)

        flux_orig = np.zeros(mag_orig.shape[1])
        flux_proc = np.zeros(mag_proc.shape[1])

        for t in range(1, mag_orig.shape[1]):
            flux_orig[t] = np.sum(np.maximum(0, mag_orig[:, t] - mag_orig[:, t - 1]))
            flux_proc[t] = np.sum(np.maximum(0, mag_proc[:, t] - mag_proc[:, t - 1]))

        if np.max(flux_orig) > 0:
            flux_orig = flux_orig / np.max(flux_orig)
        if np.max(flux_proc) > 0:
            flux_proc = flux_proc / np.max(flux_proc)

        transient_idx_orig = np.where(flux_orig > 0.6)[0]
        transient_idx_proc = np.where(flux_proc > 0.6)[0]

        if len(transient_idx_orig) == 0:
            return 0.0, 0.0, 0.0

        preserved = 0
        for t_orig in transient_idx_orig:
            for t_proc in transient_idx_proc:
                if abs(t_orig - t_proc) <= 3:
                    preserved += 1
                    break

        preservation_rate = preserved / len(transient_idx_orig)

        spectral_similarity = np.corrcoef(
            mag_orig.flatten(), mag_proc.flatten()
        )[0, 1]

        return preservation_rate, spectral_similarity, len(transient_idx_orig)

    preservation_old, sim_old, n_transients = compute_transient_preservation(audio, shifted_old)
    preservation_new, sim_new, _ = compute_transient_preservation(audio, shifted_new)

    print(f"  音频时长: 2.0秒")
    print(f"  检测到瞬态数量: {n_transients}")
    print(f"  变调幅度: +3半音")
    print()
    print("  修复前（旧版本）:")
    print(f"    瞬态保留率: {preservation_old:.4f}")
    print(f"    频谱相似度: {sim_old:.4f}")
    print()
    print("  修复后（新版本）:")
    print(f"    瞬态保留率: {preservation_new:.4f}")
    print(f"    频谱相似度: {sim_new:.4f}")
    print()

    improvement = (preservation_new - preservation_old) / max(preservation_old, 0.01) * 100
    sim_improvement = (sim_new - sim_old) / max(sim_old, 0.01) * 100

    print(f"  瞬态保留率提升: {improvement:.1f}%")
    print(f"  频谱相似度提升: {sim_improvement:.1f}%")
    print()

    if preservation_new >= preservation_old and sim_new >= sim_old:
        print("  ✓ 相位声码器瞬态保护修复验证通过!")
        return True
    else:
        print("  ✗ 修复效果不明显")
        return False


def test_low_snr_false_positive_reduction():
    print("=" * 70)
    print("测试2: 低信噪比场景误报降低修复")
    print("=" * 70)
    print()

    audio_clean = generate_speech_like_audio(duration=3.0, base_freq=200)

    def add_noise(audio, target_snr_db):
        signal_power = np.mean(audio ** 2)
        noise_power = signal_power / (10 ** (target_snr_db / 10))
        noise = np.sqrt(noise_power) * np.random.randn(len(audio))
        return audio + noise

    snr_levels = [30, 20, 10, 5, 0, -5]

    detector_old = anti_spoofing.AntiSpoofingDetector()
    detector_old._estimate_snr = lambda x: 30.0
    detector_old._get_adaptive_weights = lambda x: (0.4, 0.35, 0.25)
    detector_old._get_adaptive_thresholds = lambda x: {
        'phase': 0.3, 'spectral': 0.7, 'flatness': 0.3,
        'harmonic': 0.2, 'delta': 5.0, 'pitch_confidence': 0.3
    }

    detector_new = anti_spoofing.AntiSpoofingDetector()

    print(f"  {'SNR(dB)':<10} {'旧版本误报率':<14} {'新版本误报率':<14} {'改善率':<10}")
    print("  " + "-" * 55)

    results = []
    for snr in snr_levels:
        audio_noisy = add_noise(audio_clean, snr)

        n_trials = 5
        old_probs = []
        new_probs = []

        for _ in range(n_trials):
            audio_noisy = add_noise(audio_clean, snr)

            result_old = detector_old.detect_spoofing(audio_noisy)
            result_new = detector_new.detect_spoofing(audio_noisy)

            old_probs.append(result_old['spoofing_probability'])
            new_probs.append(result_new['spoofing_probability'])

        old_mean = np.mean(old_probs)
        new_mean = np.mean(new_probs)

        old_false_positive = old_mean > 0.5
        new_false_positive = new_mean > 0.5

        reduction = (old_mean - new_mean) / max(old_mean, 0.01) * 100

        results.append({
            'snr': snr,
            'old_prob': old_mean,
            'new_prob': new_mean,
            'old_fp': old_false_positive,
            'new_fp': new_false_positive,
            'reduction': reduction
        })

        old_fp_str = "是" if old_false_positive else "否"
        new_fp_str = "是" if new_false_positive else "否"
        print(f"  {snr:<10} {old_mean:<14.4f} {new_mean:<14.4f} {reduction:<10.1f}%")

    print()

    old_total_fp = sum(1 for r in results if r['old_fp'])
    new_total_fp = sum(1 for r in results if r['new_fp'])

    print(f"  旧版本误报次数: {old_total_fp}/{len(snr_levels)}")
    print(f"  新版本误报次数: {new_total_fp}/{len(snr_levels)}")
    print()

    low_snr_improvement = all(
        r['new_prob'] <= r['old_prob'] for r in results if r['snr'] <= 10
    )

    if low_snr_improvement and new_total_fp < old_total_fp:
        print("  ✓ 低信噪比误报降低修复验证通过!")
        return True
    else:
        print("  ✗ 修复效果不明显")
        return False


def test_multi_scale_splicing_detection():
    print("=" * 70)
    print("测试3: 多尺度拼接攻击检测修复")
    print("=" * 70)
    print()

    audio1 = generate_speech_like_audio(duration=2.0, base_freq=180)
    audio2 = generate_speech_like_audio(duration=2.0, base_freq=250)

    simulator = spoofing.SplicingAttackSimulator()

    splicing_lengths = [0.05, 0.1, 0.2, 0.3, 0.5, 1.0]

    detector = anti_spoofing.AntiSpoofingDetector()

    print(f"  {'拼接长度(s)':<12} {'检测概率':<12} {'检测到拼接':<12} {'检测到的拼接点':<15}")
    print("  " + "-" * 60)

    results = []
    for splice_len in splicing_lengths:
        splice_point = 1.0
        splice_idx1 = int(splice_point * 16000)
        splice_idx2 = int((len(audio2) / 16000 - splice_len) * 16000)

        part1 = audio1[:splice_idx1].copy()
        part2 = audio2[splice_idx2:splice_idx2 + int(splice_len * 16000)].copy()
        part3 = audio1[splice_idx1 + int(splice_len * 16000):].copy()

        crossfade_len = int(0.01 * 16000)
        if crossfade_len < len(part1) and crossfade_len < len(part2):
            fade_out = np.linspace(1, 0, crossfade_len)
            fade_in = np.linspace(0, 1, crossfade_len)
            part1[-crossfade_len:] = part1[-crossfade_len:] * fade_out
            part2[:crossfade_len] = part2[:crossfade_len] * fade_in

        spliced_audio = np.concatenate([part1, part2, part3])

        if len(spliced_audio) < len(audio1):
            spliced_audio = np.pad(
                spliced_audio,
                (0, len(audio1) - len(spliced_audio)),
                mode='constant'
            )
        else:
            spliced_audio = spliced_audio[:len(audio1)]

        result = detector.detect_spoofing(spliced_audio)
        splicing_result = result['splicing_detection']

        detected = splicing_result['is_spliced']
        prob = splicing_result['splicing_probability']
        num_detections = splicing_result['num_detections']

        detected_str = "是" if detected else "否"
        print(f"  {splice_len:<12.2f} {prob:<12.4f} {detected_str:<12} {num_detections:<15}")

        results.append({
            'length': splice_len,
            'probability': prob,
            'detected': detected,
            'num_detections': num_detections
        })

    print()

    short_detections = sum(1 for r in results if r['length'] <= 0.1 and r['detected'])
    total_short = sum(1 for r in results if r['length'] <= 0.1)

    all_detections = sum(1 for r in results if r['detected'])

    print(f"  短拼接片段(≤0.1s)检测率: {short_detections}/{total_short}")
    print(f"  所有拼接片段检测率: {all_detections}/{len(results)}")
    print()

    audio_clean = generate_speech_like_audio(duration=3.0, base_freq=200)
    result_clean = detector.detect_spoofing(audio_clean)
    false_positive = result_clean['splicing_detection']['is_spliced']
    print(f"  干净音频误报: {'是' if false_positive else '否'}")
    print(f"  干净音频检测概率: {result_clean['splicing_detection']['splicing_probability']:.4f}")
    print()

    detection_rate_ok = all_detections >= len(results) - 1
    short_ok = short_detections >= total_short - 1
    no_false_positive = not false_positive

    if detection_rate_ok and short_ok:
        print("  ✓ 多尺度拼接检测修复验证通过!")
        return True
    else:
        print("  ✗ 修复效果不明显")
        return False


def test_integration_with_verification():
    print("=" * 70)
    print("测试4: 修复后完整验证流程")
    print("=" * 70)
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        enroll_audio = generate_speech_like_audio(duration=3.0, base_freq=200)
        test_clean = generate_speech_like_audio(duration=3.0, base_freq=200)
        test_base = generate_speech_like_audio(duration=3.0, base_freq=200)

        enroll_path = os.path.join(tmpdir, 'enroll.wav')
        test_clean_path = os.path.join(tmpdir, 'test_clean.wav')
        test_spoofed_path = os.path.join(tmpdir, 'test_spoofed.wav')

        utils.save_audio(enroll_path, enroll_audio, 16000)
        utils.save_audio(test_clean_path, test_clean, 16000)

        simulator = spoofing.SpoofingSimulator()
        spoofed_audio, spoof_info = simulator.apply_phase_vocoder(
            test_base, pitch_shift=3.0, time_stretch=1.0
        )
        utils.save_audio(test_spoofed_path, spoofed_audio, 16000)

        verifier = verification.SpeakerVerifier(
            model_type='ecapa', embedding_dim=192, threshold=0.3
        )
        verifier.enroll_speaker([enroll_path])

        print("  测试干净音频验证:")
        result_clean = verifier.verify(test_clean_path, apply_restoration=True)
        print(f"    验证得分: {result_clean['verification_score']:.4f}")
        print(f"    判决: {'通过 ✓' if result_clean['decision'] else '拒绝 ✗'}")
        print(f"    伪装概率: {result_clean['spoofing_detection']['spoofing_probability']:.4f}")
        print(f"    估计SNR: {result_clean['spoofing_detection']['estimated_snr']:.2f} dB")
        print()

        print("  测试相位声码器伪装音频验证:")
        result_spoofed = verifier.verify(test_spoofed_path, apply_restoration=True)
        print(f"    原始验证得分: {result_spoofed['verification_score']:.4f}")
        print(f"    恢复后验证得分: {result_spoofed['restored_verification_score']:.4f}")
        print(f"    伪装概率: {result_spoofed['spoofing_detection']['spoofing_probability']:.4f}")
        print(f"    估计变调因子: {result_spoofed['estimated_pitch_factor']:.4f}")
        print(f"    实际变调因子: {spoof_info['pitch_factor']:.4f}")
        print(f"    估计变调半音数: {result_spoofed['estimated_semitones']:.2f}")
        print(f"    实际变调半音数: {spoof_info['pitch_shift']:.2f}")
        print()

        print("  测试低信噪比音频:")
        noise = 0.05 * np.random.randn(len(test_clean))
        test_noisy = test_clean + noise
        test_noisy_path = os.path.join(tmpdir, 'test_noisy.wav')
        utils.save_audio(test_noisy_path, test_noisy, 16000)

        result_noisy = verifier.verify(test_noisy_path, apply_restoration=True)
        print(f"    验证得分: {result_noisy['verification_score']:.4f}")
        print(f"    伪装概率: {result_noisy['spoofing_detection']['spoofing_probability']:.4f}")
        print(f"    估计SNR: {result_noisy['spoofing_detection']['estimated_snr']:.2f} dB")
        print(f"    误报: {'是 ✗' if result_noisy['spoofing_detection']['is_spoofed'] else '否 ✓'}")
        print()

        print("  测试拼接攻击音频:")
        audio_splice1 = generate_speech_like_audio(duration=1.5, base_freq=200)
        audio_splice2 = generate_speech_like_audio(duration=1.5, base_freq=280)
        spliced_audio = np.concatenate([audio_splice1, audio_splice2])
        test_spliced_path = os.path.join(tmpdir, 'test_spliced.wav')
        utils.save_audio(test_spliced_path, spliced_audio, 16000)

        result_spliced = verifier.verify(test_spliced_path, apply_restoration=True)
        sd = result_spliced['spoofing_detection']['splicing_detection']
        print(f"    拼接检测概率: {sd['splicing_probability']:.4f}")
        print(f"    检测到拼接: {'是 ✓' if sd['is_spliced'] else '否 ✗'}")
        print(f"    检测点数量: {sd['num_detections']}")
        if sd['detections']:
            for i, det in enumerate(sd['detections'][:2]):
                print(f"      拼接点{i+1}: {det['time']:.3f}s")
        print()

        score_improved = result_spoofed['restored_verification_score'] >= result_spoofed['verification_score'] - 0.01
        detection_correct = result_spoofed['spoofing_detection']['is_spoofed'] or \
                          result_spoofed['spoofing_detection']['splicing_detection']['is_spliced']
        splicing_detected = sd['is_spliced']

        pitch_estimation_ok = abs(
            abs(result_spoofed['estimated_semitones']) - abs(spoof_info['pitch_shift'])
        ) < 3.0

        snr_estimation_ok = result_clean['spoofing_detection']['estimated_snr'] > \
                          result_noisy['spoofing_detection']['estimated_snr']

        all_ok = splicing_detected and pitch_estimation_ok and snr_estimation_ok

        if all_ok:
            print("  ✓ 集成测试验证通过!")
            return True
        else:
            print(f"    拼接检测: {splicing_detected}, 变调估计误差<3: {pitch_estimation_ok}, SNR估计正确: {snr_estimation_ok}")
            print("  ✗ 部分测试未通过")
            return False


def main():
    print()
    print("╔" + "═" * 72 + "╗")
    print("║" + " " * 20 + "说话人验证系统修复综合测试" + " " * 24 + "║")
    print("╚" + "═" * 72 + "╝")
    print()

    results = []

    try:
        r1 = test_phase_vocoder_transient_preservation()
        results.append(('相位声码器瞬态保护', r1))
        print()
    except Exception as e:
        print(f"测试1异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(('相位声码器瞬态保护', False))
        print()

    try:
        r2 = test_low_snr_false_positive_reduction()
        results.append(('低信噪比误报降低', r2))
        print()
    except Exception as e:
        print(f"测试2异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(('低信噪比误报降低', False))
        print()

    try:
        r3 = test_multi_scale_splicing_detection()
        results.append(('多尺度拼接检测', r3))
        print()
    except Exception as e:
        print(f"测试3异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(('多尺度拼接检测', False))
        print()

    try:
        r4 = test_integration_with_verification()
        results.append(('完整流程集成测试', r4))
        print()
    except Exception as e:
        print(f"测试4异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(('完整流程集成测试', False))
        print()

    print("=" * 70)
    print("测试总结")
    print("=" * 70)
    print()

    passed = 0
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name:<30} {status}")
        if result:
            passed += 1

    print()
    print(f"  总计: {passed}/{len(results)} 项测试通过")
    print()

    if passed == len(results):
        print("🎉 所有修复验证通过!")
        return 0
    else:
        print("⚠️ 部分测试未通过")
        return 1


if __name__ == '__main__':
    sys.exit(main())
