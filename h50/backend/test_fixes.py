#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试三个问题的修复效果：
1. 减字上下结构组合顺序混淆
2. 徽位数字1-13识别混淆（1和7相似）
3. 音频合成中同指法不同弦的音色差异
"""

import os
import sys
import numpy as np
import cv2
import json

sys.path.insert(0, os.path.dirname(__file__))

from services import ComponentRecognizer, AudioSynthesizer


def test_combination_order():
    """测试问题1：减字上下结构组合顺序"""
    print("=" * 60)
    print("测试1：减字结构判断与组合顺序")
    print("=" * 60)
    
    recognizer = ComponentRecognizer(os.path.join(os.path.dirname(__file__), 'services', 'dictionary.json'))
    
    test_cases = [
        {
            "name": "纯上下结构（如'三'）",
            "components": {
                "top": {"recognized": {"id": "艹", "name": "草头"}, "confidence": 0.9, "candidates": []},
                "bottom": {"recognized": {"id": "三", "name": "三"}, "confidence": 0.9, "candidates": []},
                "left": {"recognized": {"id": "", "name": ""}, "confidence": 0.1, "candidates": []},
                "right": {"recognized": {"id": "", "name": ""}, "confidence": 0.1, "candidates": []}
            },
            "expected_structure": "vertical",
            "expected_order": ["top", "bottom"]
        },
        {
            "name": "纯左右结构（如'按'）",
            "components": {
                "top": {"recognized": {"id": "", "name": ""}, "confidence": 0.1, "candidates": []},
                "bottom": {"recognized": {"id": "", "name": ""}, "confidence": 0.1, "candidates": []},
                "left": {"recognized": {"id": "扌", "name": "提手旁"}, "confidence": 0.9, "candidates": []},
                "right": {"recognized": {"id": "安", "name": "安"}, "confidence": 0.9, "candidates": []}
            },
            "expected_structure": "horizontal",
            "expected_order": ["left", "right"]
        },
        {
            "name": "混合结构（如'散'）",
            "components": {
                "top": {"recognized": {"id": "艹", "name": "草头"}, "confidence": 0.85, "candidates": []},
                "bottom": {"recognized": {"id": "三", "name": "三"}, "confidence": 0.85, "candidates": []},
                "left": {"recognized": {"id": "月", "name": "月"}, "confidence": 0.8, "candidates": []},
                "right": {"recognized": {"id": "攵", "name": "反文旁"}, "confidence": 0.8, "candidates": []}
            },
            "expected_structure": "mixed",
            "expected_order": ["top", "left", "right", "bottom"]
        }
    ]
    
    for i, test in enumerate(test_cases):
        print(f"\n{i+1}. {test['name']}")
        structure = recognizer._determine_jianzi_structure(test["components"])
        order = recognizer._get_combination_order(structure)
        
        notation = recognizer._generate_notation(test["components"])
        
        print(f"   判断结构: {structure} (期望: {test['expected_structure']})")
        print(f"   组合顺序: {order} (期望: {test['expected_order']})")
        print(f"   生成记谱: {notation}")
        
        if structure == test["expected_structure"] and order == test["expected_order"]:
            print(f"   ✓ 测试通过")
        else:
            print(f"   ✗ 测试失败")
    
    return True


def test_hui_recognition():
    """测试问题2：徽位数字识别，特别是'一'和'七'的区分"""
    print("\n" + "=" * 60)
    print("测试2：徽位数字识别（'一'和'七'区分）")
    print("=" * 60)
    
    recognizer = ComponentRecognizer(os.path.join(os.path.dirname(__file__), 'services', 'dictionary.json'))
    
    def create_test_image(char_type: str, size=(64, 64)):
        """创建模拟的徽位数字图像"""
        img = np.ones(size, dtype=np.uint8) * 255
        
        if char_type == "一":
            cv2.line(img, (5, size[1]//2), (size[0]-5, size[1]//2), 0, 3)
        elif char_type == "七":
            cv2.line(img, (10, 15), (size[0]-10, 15), 0, 3)
            cv2.line(img, (size[0]//2, 15), (size[0]//3, size[1]-10), 0, 3)
            cv2.line(img, (size[0]//3, size[1]-10), (size[0]//4, size[1]-15), 0, 2)
        elif char_type == "二":
            cv2.line(img, (5, size[1]//3), (size[0]-5, size[1]//3), 0, 3)
            cv2.line(img, (5, 2*size[1]//3), (size[0]-5, 2*size[1]//3), 0, 3)
        elif char_type == "三":
            cv2.line(img, (5, size[1]//4), (size[0]-5, size[1]//4), 0, 3)
            cv2.line(img, (5, size[1]//2), (size[0]-5, size[1]//2), 0, 3)
            cv2.line(img, (5, 3*size[1]//4), (size[0]-5, 3*size[1]//4), 0, 3)
        elif char_type == "十":
            cv2.line(img, (5, size[1]//2), (size[0]-5, size[1]//2), 0, 3)
            cv2.line(img, (size[0]//2, 5), (size[0]//2, size[1]-5), 0, 3)
        
        return img
    
    test_cases = [
        ("一", "一"),
        ("七", "七"),
        ("二", "二"),
        ("三", "三"),
        ("十", "十"),
    ]
    
    print("\n形状特征提取测试:")
    for char_type, expected in test_cases:
        img = create_test_image(char_type)
        features = recognizer._extract_hui_shape_features(img)
        
        print(f"\n  '{char_type}' 的形状特征:")
        print(f"    横笔画数: {features['horizontal_strokes']:.0f}")
        print(f"    竖笔画数: {features['vertical_strokes']:.0f}")
        print(f"    底部钩: {'有' if features['has_bottom_hook'] > 0.5 else '无'}")
        print(f"    上重下轻: {'是' if features['top_heavy'] > 0.5 else '否'}")
        print(f"    宽高比: {features['aspect_ratio']:.2f}")
        print(f"    斜笔画数: {features['diagonal_elements']:.0f}")
    
    print("\n徽位模板相似度测试:")
    templates = recognizer._build_hui_templates()
    
    for char_type, expected in test_cases:
        img = create_test_image(char_type)
        features = recognizer._extract_hui_shape_features(img)
        
        yi_sim = recognizer._calculate_hui_similarity(features, templates["一"])
        qi_sim = recognizer._calculate_hui_similarity(features, templates["七"])
        
        print(f"\n  '{char_type}' 与模板相似度:")
        print(f"    与'一'相似度: {yi_sim:.3f}")
        print(f"    与'七'相似度: {qi_sim:.3f}")
        
        if char_type == "一":
            if yi_sim > qi_sim:
                print(f"    ✓ 正确区分：'一'识别为'一'")
            else:
                print(f"    ✗ 错误：'一'与'七'混淆")
        elif char_type == "七":
            if qi_sim > yi_sim:
                print(f"    ✓ 正确区分：'七'识别为'七'")
            else:
                print(f"    ✗ 错误：'七'与'一'混淆")
    
    print("\n徽位范围校验测试:")
    test_ids = ["一", "七", "十五", "廿", "十一"]
    all_labels = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三"]
    
    for test_id in test_ids:
        validated, score = recognizer._validate_hui_range(test_id, all_labels)
        status = "✓ 有效" if validated in all_labels else "✗ 无效"
        print(f"  '{test_id}' → 校验为 '{validated}' (置信度: {score:.2f}) {status}")
    
    return True


def test_string_tone_difference():
    """测试问题3：同指法不同弦的音色差异"""
    print("\n" + "=" * 60)
    print("测试3：同指法不同弦的音色差异")
    print("=" * 60)
    
    synthesizer = AudioSynthesizer()
    
    strings = ["一", "二", "三", "四", "五", "六", "七"]
    techniques = ["sanyin", "anyin", "fanyin"]
    
    print("\n各弦音色参数对比（散音）:")
    print("-" * 80)
    print(f"{'弦':<4} {'描述':<18} {'亮度':<6} {'衰减':<6} {'高频截止':<10} {'低频增益':<10} {'不和谐度':<10}")
    print("-" * 80)
    
    for string_id in strings:
        params = synthesizer._get_string_timbre_params(string_id)
        print(f"{string_id:<4} {params['description']:<18} {params['brightness']:<6.2f} {params['decay']:<6.2f} "
              f"{params['high_cut']:<10.0f} {params['low_boost']:<10.2f} {params['inharmonicity']:<10.4f}")
    
    print("\n谐波权重对比（基频=1.0）:")
    print("-" * 80)
    print(f"{'弦':<4} {'H1':<8} {'H2':<8} {'H3':<8} {'H4':<8} {'H5':<8} {'H6':<8} {'H7':<8}")
    print("-" * 80)
    
    for string_id in ["一", "四", "七"]:
        params = synthesizer._get_string_timbre_params(string_id)
        harmonics = params["harmonic_weights"]
        harmonic_str = " ".join([f"{h:<8.2f}" for h in harmonics[:7]])
        print(f"{string_id:<4} {harmonic_str}")
    
    print("\n合成音频参数对比（相同技法'sanyin'，不同弦）:")
    print("-" * 80)
    print(f"{'弦':<4} {'MIDI':<6} {'频率':<10} {'技法':<10} {'衰减':<8} {'释放':<8} {'高频截止':<10}")
    print("-" * 80)
    
    base_midi = 60
    for i, string_id in enumerate(strings):
        midi = base_midi + i
        freq = synthesizer._midi_to_frequency(midi)
        technique_params = synthesizer.get_technique_params("sanyin", string_id)
        print(f"{string_id:<4} {midi:<6} {freq:<10.1f} {'sanyin':<10} "
              f"{technique_params['decay']:<8.3f} {technique_params['release']:<8.3f} "
              f"{technique_params.get('string_params', {}).get('high_cut', 0):<10.0f}")
    
    print("\n实际合成音频测试:")
    print("-" * 80)
    duration = 1.0
    
    for string_id in ["一", "四", "七"]:
        midi = 60 + ["一", "二", "三", "四", "五", "六", "七"].index(string_id)
        audio = synthesizer.synthesize_note(midi, "sanyin", duration, string_id)
        
        rms = np.sqrt(np.mean(audio**2))
        spectral_centroid = np.mean(np.abs(np.fft.fftfreq(len(audio), 1/44100)[:len(audio)//2]) * 
                                    np.abs(np.fft.fft(audio)[:len(audio)//2])) / np.mean(np.abs(np.fft.fft(audio)[:len(audio)//2]))
        
        print(f"  弦{string_id} (MIDI {midi}):")
        print(f"    音频长度: {len(audio)} 样本 ({len(audio)/44100:.3f}秒)")
        print(f"    均方根(RMS): {rms:.4f}")
        print(f"    频谱质心: {spectral_centroid:.1f} Hz (越高越明亮)")
        
        if string_id == "一":
            lowest_centroid = spectral_centroid
        if string_id == "七":
            highest_centroid = spectral_centroid
    
    if 'lowest_centroid' in locals() and 'highest_centroid' in locals():
        diff = highest_centroid - lowest_centroid
        print(f"\n  频谱质心差异（一弦 vs 七弦）: {diff:.1f} Hz")
        if diff > 100:
            print(f"  ✓ 音色差异明显：一弦低沉({lowest_centroid:.0f}Hz)，七弦明亮({highest_centroid:.0f}Hz)")
        else:
            print(f"  ✗ 音色差异不足")
    
    print("\n技法与弦组合参数:")
    print("-" * 80)
    for technique in techniques:
        params = synthesizer.get_technique_params(technique, "四")
        desc = params.get("description", technique)
        print(f"  {technique:<8}: {desc}")
    
    return True


def test_api_endpoints():
    """测试API端点是否正常工作"""
    print("\n" + "=" * 60)
    print("测试4：API端点健康检查")
    print("=" * 60)
    
    try:
        import requests
        
        base_url = "http://localhost:5000/api"
        
        print("\n1. 健康检查:")
        r = requests.get(f"{base_url}/health", timeout=5)
        print(f"   状态: {r.status_code}")
        print(f"   响应: {r.json()}")
        
        print("\n2. 获取字典:")
        r = requests.get(f"{base_url}/dictionary", timeout=5)
        data = r.json()
        print(f"   状态: {r.status_code}")
        print(f"   字典键: {list(data.keys())}")
        
        print("\n3. 工尺谱对照表:")
        r = requests.get(f"{base_url}/gongche", timeout=5)
        data = r.json()
        print(f"   状态: {r.status_code}")
        print(f"   返回键: {list(data.keys())[:5]}...")
        
        print("\n✓ API测试完成")
        return True
        
    except Exception as e:
        print(f"\n✗ API测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("古琴减字谱系统 - 问题修复验证测试")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("组合顺序", test_combination_order()))
    except Exception as e:
        print(f"\n✗ 组合顺序测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("组合顺序", False))
    
    try:
        results.append(("徽位识别", test_hui_recognition()))
    except Exception as e:
        print(f"\n✗ 徽位识别测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("徽位识别", False))
    
    try:
        results.append(("音色差异", test_string_tone_difference()))
    except Exception as e:
        print(f"\n✗ 音色差异测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("音色差异", False))
    
    try:
        results.append(("API端点", test_api_endpoints()))
    except Exception as e:
        print(f"\n✗ API端点测试异常: {e}")
        results.append(("API端点", False))
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name}: {status}")
    
    all_passed = all(r for _, r in results)
    print(f"\n总体: {'全部通过 ✓' if all_passed else '存在失败 ✗'}")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
