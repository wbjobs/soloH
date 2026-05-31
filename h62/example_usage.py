#!/usr/bin/env python
"""
情感语音合成使用示例
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.inference.tts_engine import TTSEngine


def main():
    print("=" * 60)
    print("Emotional TTS - 使用示例")
    print("=" * 60)
    
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    
    print("\n1. 初始化TTS引擎...")
    engine = TTSEngine(
        config_path=config_path,
        device="cpu",
        vocoder_type="waveglow",
    )
    print("   ✓ 引擎初始化完成")
    
    print(f"\n2. 可用情感: {engine.get_available_emotions()}")
    
    print("\n3. 测试单情感处理...")
    emotion_emb, prosody = engine.emotion_controller.process_emotion_input("happy", 0.8)
    print(f"   情感: happy, 强度: 0.8")
    print(f"   情感嵌入维度: {emotion_emb.shape}")
    print(f"   韵律特征维度: {prosody.shape}")
    print(f"   韵律特征 (音高/能量/时长): {prosody.detach().cpu().numpy()}")
    
    print("\n4. 测试混合情感处理...")
    mixed_emotion = {"happy": 0.7, "surprise": 0.3}
    emotion_emb, prosody = engine.emotion_controller.process_emotion_input(mixed_emotion, 1.0)
    print(f"   混合情感: {mixed_emotion}")
    print(f"   情感嵌入维度: {emotion_emb.shape}")
    
    print("\n5. 测试情感字符串解析...")
    test_cases = [
        "happy",
        "sad:0.5",
        "happy:0.7+surprise:0.3",
        "angry:0.6+sad:0.4",
    ]
    
    for test in test_cases:
        emotion, intensity = engine.emotion_controller.parse_emotion_string(test)
        print(f"   输入: {test:40s} -> 情感: {emotion}, 强度: {intensity}")
    
    print("\n6. 测试韵律调节...")
    import torch
    dummy_mel = torch.randn(80, 100)
    adjusted_mel = engine.emotion_controller.prosody_regulator.adjust_prosody(
        dummy_mel,
        pitch_shift=0.5,
        energy_scale=1.2,
        duration_scale=0.9,
    )
    print(f"   原始Mel形状: {dummy_mel.shape}")
    print(f"   调整后Mel形状: {adjusted_mel.shape}")
    
    print("\n" + "=" * 60)
    print("示例运行完成！")
    print("=" * 60)
    print("\n下一步:")
    print("  1. 安装依赖: pip install -r requirements.txt")
    print("  2. 下载预训练模型到 ./pretrained/ 目录")
    print("  3. 运行合成命令:")
    print('     python main.py synthesize --text "Hello" --emotion happy')
    print("\n命令行工具帮助:")
    print("  python main.py --help")
    print("  python main.py synthesize --help")
    print("  python main.py validate --help")
    print("  python main.py adapt --help")


if __name__ == "__main__":
    main()
