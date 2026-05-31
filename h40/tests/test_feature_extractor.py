"""
特征提取模块测试
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from author_authorship.feature_extractor import FeatureExtractor


TEST_TEXT = """To be, or not to be: that is the question:
Whether 'tis nobler in the mind to suffer
The slings and arrows of outrageous fortune,
Or to take arms against a sea of troubles,
And by opposing end them? To die: to sleep;
No more; and by a sleep to say we end
The heart-ache and the thousand natural shocks
That flesh is heir to, 'tis a consummation
Devoutly to be wish'd. To die, to sleep;
To sleep: perchance to dream: ay, there's the rub."""


def test_feature_extractor_init():
    """测试特征提取器初始化"""
    print("测试1: 特征提取器初始化...")
    try:
        extractor = FeatureExtractor()
        print(f"  ✓ 初始化成功")
        print(f"  ✓ 特征维度: {len(extractor.feature_names)}")
        print(f"  ✓ 特征分组: {list(extractor.get_feature_groups().keys())}")
        return extractor
    except Exception as e:
        print(f"  ✗ 初始化失败: {e}")
        return None


def test_extract_features(extractor):
    """测试特征提取"""
    print("\n测试2: 单篇文本特征提取...")
    try:
        features = extractor.extract_features(TEST_TEXT)
        print(f"  ✓ 特征维度: {features.shape}")
        print(f"  ✓ 特征类型: {features.dtype}")
        print(f"  ✓ 包含NaN: {np.isnan(features).any()}")
        print(f"  ✓ 包含Inf: {np.isinf(features).any()}")
        
        feature_groups = extractor.get_feature_groups()
        print(f"\n  各特征组统计:")
        for group_name, feature_names in feature_groups.items():
            indices = [extractor.feature_names.index(f) for f in feature_names 
                      if f in extractor.feature_names]
            group_features = features[indices]
            print(f"    {group_name}: {len(indices)}维, "
                  f"均值={group_features.mean():.4f}, "
                  f"标准差={group_features.std():.4f}")
        
        return features
    except Exception as e:
        print(f"  ✗ 特征提取失败: {e}")
        return None


def test_extract_batch(extractor):
    """测试批量特征提取"""
    print("\n测试3: 批量特征提取...")
    try:
        texts = [
            TEST_TEXT,
            "What's in a name? That which we call a rose by any other name would smell as sweet.",
            "It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife.",
            "It was the best of times, it was the worst of times.",
            "The old man was thin and gaunt with deep wrinkles in the back of his neck."
        ]
        
        features = extractor.extract_batch(texts)
        print(f"  ✓ 特征矩阵形状: {features.shape}")
        print(f"  ✓ 样本数: {features.shape[0]}")
        print(f"  ✓ 特征数: {features.shape[1]}")
        print(f"  ✓ 包含NaN: {np.isnan(features).any()}")
        
        return features
    except Exception as e:
        print(f"  ✗ 批量提取失败: {e}")
        return None


def test_feature_groups(extractor):
    """测试特征分组"""
    print("\n测试4: 特征分组验证...")
    try:
        feature_groups = extractor.get_feature_groups()
        total_features = sum(len(f) for f in feature_groups.values())
        
        print(f"  ✓ 分组数量: {len(feature_groups)}")
        print(f"  ✓ 总特征数: {total_features}")
        print(f"  ✓ 特征名称数: {len(extractor.feature_names)}")
        
        expected_groups = {
            'sentence_length': 14,
            'lexical_richness': 8,
            'function_words': 100,
            'punctuation': 37,
            'char_ngram': 200
        }
        
        print(f"\n  各维度验证:")
        for group_name, expected_count in expected_groups.items():
            actual_count = len(feature_groups.get(group_name, []))
            status = "✓" if actual_count == expected_count else "✗"
            print(f"    {status} {group_name}: {actual_count} (预期: {expected_count})")
        
        return feature_groups
    except Exception as e:
        print(f"  ✗ 特征分组测试失败: {e}")
        return None


def test_sentence_length_features(extractor):
    """测试句长分布特征"""
    print("\n测试5: 句长分布特征...")
    try:
        doc = extractor.nlp(TEST_TEXT)
        features = extractor._sentence_length_features(doc)
        
        print(f"  ✓ 特征维度: {len(features)}")
        print(f"  ✓ 均值: {features[0]:.4f}")
        print(f"  ✓ 中位数: {features[1]:.4f}")
        print(f"  ✓ 标准差: {features[2]:.4f}")
        print(f"  ✓ 短句比例: {features[10]:.4f}")
        print(f"  ✓ 长句比例: {features[11]:.4f}")
        
        assert len(features) == 14, f"预期14维，实际{len(features)}维"
        assert not np.isnan(features).any(), "包含NaN值"
        
        return features
    except Exception as e:
        print(f"  ✗ 句长特征测试失败: {e}")
        return None


def test_lexical_richness_features(extractor):
    """测试词汇丰富度特征"""
    print("\n测试6: 词汇丰富度特征...")
    try:
        doc = extractor.nlp(TEST_TEXT)
        features = extractor._lexical_richness_features(doc)
        
        print(f"  ✓ 特征维度: {len(features)}")
        print(f"  ✓ 类符/形符比: {features[0]:.4f}")
        print(f"  ✓ Hapax Legomena比例: {features[1]:.4f}")
        print(f"  ✓ Yule's K: {features[3]:.4f}")
        print(f"  ✓ Simpson's D: {features[5]:.4f}")
        print(f"  ✓ 词汇量: {features[7]:.0f}")
        
        assert len(features) == 8, f"预期8维，实际{len(features)}维"
        assert features[0] >= 0 and features[0] <= 1, "类符/形符比应在0-1之间"
        
        return features
    except Exception as e:
        print(f"  ✗ 词汇丰富度测试失败: {e}")
        return None


def test_function_word_features(extractor):
    """测试功能词频率特征"""
    print("\n测试7: 功能词频率特征...")
    try:
        doc = extractor.nlp(TEST_TEXT)
        features = extractor._function_word_features(doc)
        
        print(f"  ✓ 特征维度: {len(features)}")
        print(f"  ✓ 非零特征数: {np.sum(features > 0)}")
        print(f"  ✓ 频率和: {features.sum():.4f}")
        print(f"  ✓ 最大值: {features.max():.4f}")
        print(f"  ✓ 'the'频率: {features[0]:.4f}")
        
        assert len(features) == 100, f"预期100维，实际{len(features)}维"
        assert features.sum() > 0, "所有功能词频率都为0"
        
        return features
    except Exception as e:
        print(f"  ✗ 功能词测试失败: {e}")
        return None


def test_punctuation_features(extractor):
    """测试标点模式特征"""
    print("\n测试8: 标点模式特征...")
    try:
        doc = extractor.nlp(TEST_TEXT)
        features = extractor._punctuation_features(doc)
        
        print(f"  ✓ 特征维度: {len(features)}")
        print(f"  ✓ 非零特征数: {np.sum(features > 0)}")
        print(f"  ✓ 逗号频率: {features[FeatureExtractor.PUNCTUATION_LIST.index(',')]:.4f}")
        print(f"  ✓ 句号频率: {features[FeatureExtractor.PUNCTUATION_LIST.index('.')]:.4f}")
        print(f"  ✓ 问号频率: {features[FeatureExtractor.PUNCTUATION_LIST.index('?')]:.4f}")
        
        assert len(features) == len(FeatureExtractor.PUNCTUATION_LIST)
        
        return features
    except Exception as e:
        print(f"  ✗ 标点模式测试失败: {e}")
        return None


def test_char_ngram_features(extractor):
    """测试字符n-gram特征"""
    print("\n测试9: 字符n-gram特征...")
    try:
        texts = [
            TEST_TEXT,
            "What's in a name? That which we call a rose.",
            "It is a truth universally acknowledged."
        ]
        
        features = extractor._char_ngram_features(texts)
        
        print(f"  ✓ 特征矩阵形状: {features.shape}")
        print(f"  ✓ 最大特征值: {features.max():.4f}")
        print(f"  ✓ 非零特征比例: {np.mean(features > 0):.4f}")
        
        assert features.shape[0] == 3, f"预期3个样本，实际{features.shape[0]}个"
        assert features.shape[1] == 200, f"预期200维，实际{features.shape[1]}维"
        
        return features
    except Exception as e:
        print(f"  ✗ 字符n-gram测试失败: {e}")
        return None


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("特征提取模块单元测试")
    print("=" * 60)
    
    extractor = test_feature_extractor_init()
    if extractor is None:
        return False
    
    test_extract_features(extractor)
    test_extract_batch(extractor)
    test_feature_groups(extractor)
    test_sentence_length_features(extractor)
    test_lexical_richness_features(extractor)
    test_function_word_features(extractor)
    test_punctuation_features(extractor)
    test_char_ngram_features(extractor)
    
    print("\n" + "=" * 60)
    print("特征提取模块测试完成")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
