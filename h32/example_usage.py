import os
import sys
import tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from speaker_verification import utils, verification, spoofing


def generate_sample_audio(duration: float = 3.0, freq: float = 200.0):
    t = np.linspace(0, duration, int(16000 * duration), endpoint=False)
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


def main():
    print("=" * 70)
    print("说话人验证与反伪装检测工具 - 使用示例")
    print("=" * 70)
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        print("步骤1: 生成测试音频...")
        enroll_audio = generate_sample_audio(duration=3.0, freq=200)
        test_clean = generate_sample_audio(duration=3.0, freq=200)
        test_base = generate_sample_audio(duration=3.0, freq=200)

        enroll_path = os.path.join(tmpdir, 'enroll.wav')
        test_clean_path = os.path.join(tmpdir, 'test_clean.wav')
        test_spoofed_path = os.path.join(tmpdir, 'test_spoofed.wav')

        utils.save_audio(enroll_path, enroll_audio, 16000)
        utils.save_audio(test_clean_path, test_clean, 16000)

        print(f"  注册音频: {enroll_path}")
        print(f"  干净测试音频: {test_clean_path}")
        print()

        print("步骤2: 模拟伪装攻击 - PSOLA变调 +2半音...")
        simulator = spoofing.SpoofingSimulator()
        spoofed_audio, spoof_info = simulator.apply_pitch_shift_psola(
            test_base, n_steps=2.0
        )
        utils.save_audio(test_spoofed_path, spoofed_audio, 16000)
        print(f"  伪装类型: {spoof_info['type']}")
        print(f"  变调因子: {spoof_info['factor']:.4f}")
        print(f"  变调半音数: {spoof_info['n_steps']:.2f}")
        print()

        print("步骤3: 初始化验证器...")
        verifier = verification.SpeakerVerifier(
            model_type='ecapa',
            embedding_dim=192,
            sample_rate=16000,
            device='cpu',
            threshold=0.3
        )
        print("  使用模型: ECAPA-TDNN")
        print("  嵌入维度: 192")
        print()

        print("步骤4: 注册说话人...")
        enroll_result = verifier.enroll_speaker([enroll_path])
        print(f"  注册成功: {enroll_result['enrollment_successful']}")
        print(f"  注册样本数: {enroll_result['num_enrollment_samples']}")
        print()

        print("步骤5: 验证干净测试音频...")
        result_clean = verifier.verify(test_clean_path, apply_restoration=True)
        print(f"  验证得分: {result_clean['verification_score']:.4f}")
        print(f"  判决: {'通过 ✓' if result_clean['decision'] else '拒绝 ✗'}")
        print(f"  伪装概率: {result_clean['spoofing_detection']['spoofing_probability']:.4f}")
        print()

        print("步骤6: 验证伪装测试音频...")
        result_spoofed = verifier.verify(test_spoofed_path, apply_restoration=True)
        print(f"  原始验证得分: {result_spoofed['verification_score']:.4f}")
        print(f"  恢复后验证得分: {result_spoofed['restored_verification_score']:.4f}")
        print(f"  原始判决: {'通过 ✓' if result_spoofed['decision'] else '拒绝 ✗'}")
        print(f"  恢复后判决: {'通过 ✓' if result_spoofed['restored_decision'] else '拒绝 ✗'}")
        print(f"  伪装存在概率: {result_spoofed['spoofing_detection']['spoofing_probability']:.4f}")
        print(f"  是否检测到伪装: {'是 ✓' if result_spoofed['spoofing_detection']['is_spoofed'] else '否 ✗'}")
        print(f"  估计变调因子: {result_spoofed['estimated_pitch_factor']:.4f}")
        print(f"  实际变调因子: {spoof_info['factor']:.4f}")
        print(f"  估计误差: {abs(result_spoofed['estimated_pitch_factor'] - spoof_info['factor']):.4f}")
        print(f"  估计变调半音数: {result_spoofed['estimated_semitones']:.2f}")
        print(f"  实际变调半音数: {spoof_info['n_steps']:.2f}")
        print()

        print("步骤7: 生成详细报告...")
        report = verification.VerificationReport.generate(result_spoofed)
        print(report)
        print()

        print("=" * 70)
        print("示例完成!")
        print("=" * 70)
        print()
        print("命令行使用示例:")
        print()
        print("  1. 注册说话人:")
        print(f'     python -m speaker_verification.cli enroll {enroll_path} -s embedding.npy')
        print()
        print("  2. 验证音频:")
        print(f'     python -m speaker_verification.cli verify {test_spoofed_path} -e {enroll_path}')
        print()
        print("  3. 模拟伪装攻击验证:")
        print(f'     python -m speaker_verification.cli simulate {enroll_path} {test_clean_path} -t pitch_shift -p 2.0')
        print()
        print("  4. 对音频应用伪装变换:")
        print(f'     python -m speaker_verification.cli transform {test_clean_path} output.wav -t pitch_shift -p 2.0')
        print()
        print("  5. 恢复被伪装的音频:")
        print(f'     python -m speaker_verification.cli restore {test_spoofed_path} restored.wav -r {enroll_path}')
        print()


if __name__ == '__main__':
    main()
