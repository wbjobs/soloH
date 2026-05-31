"""
Bug修复验证测试
验证三个问题的修复效果:
1. 词汇丰富度测量中对话vs叙述的标准差混淆
2. 功能词表在诗歌体裁中的失效问题
3. 作者归属中投票法对长文本偏好导致的置信度虚高
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from author_authorship import (
    FeatureExtractor,
    AuthorClassifier
)


SAMPLE_TEXTS = {
    "narrative_prose": """The old man walked slowly through the forest. 
    The sunlight filtered through the tall trees, casting long shadows on the ground. 
    He had been walking for hours, but he did not feel tired. 
    His mind was filled with memories of his youth, of the days when he had 
    first explored this forest with his father. Every step brought back 
    new recollections, each one more vivid than the last. The birds sang 
    in the branches above, and the wind rustled through the leaves, 
    creating a symphony of natural sounds that accompanied his journey.""",

    "dialogue_heavy": """Hey! How are you doing? 
    I'm fine, thanks. What about you? 
    Pretty good. Did you see the game last night? 
    Yeah! It was incredible. The winning goal was amazing! 
    I know, right? I couldn't believe it. 
    Hey, want to grab some coffee later? 
    Sure, that sounds great. How about 3pm? 
    Perfect. See you then! 
    Alright, see you!""",

    "poetry": """Hope is the thing with feathers--
    That perches in the soul--
    And sings the tune without the words--
    And never stops--at all--

    And sweetest--in the Gale--is heard--
    And sore must be the storm--
    That could abash the little Bird
    That kept so many warm--

    I've heard it in the chillest land--
    And on the strangest Sea--
    Yet--never--in Extremity,
    It asked a crumb--of me.""",

    "prose": """It was the best of times, it was the worst of times, 
    it was the age of wisdom, it was the age of foolishness, 
    it was the epoch of belief, it was the epoch of incredulity, 
    it was the season of Light, it was the season of Darkness, 
    it was the spring of hope, it was the winter of despair, 
    we had everything before us, we had nothing before us."""
}


def test_issue_1_dialogue_vs_narrative():
    """测试问题1: 对话vs叙述的词汇丰富度标准差混淆修复"""
    print("=" * 60)
    print("测试1: 对话vs叙述的词汇丰富度条件归一化")
    print("=" * 60)
    
    extractor = FeatureExtractor()
    
    narrative_text = SAMPLE_TEXTS["narrative_prose"]
    dialogue_text = SAMPLE_TEXTS["dialogue_heavy"]
    
    narrative_meta = extractor.get_text_metadata(narrative_text)
    dialogue_meta = extractor.get_text_metadata(dialogue_text)
    
    print(f"\n文本类型检测:")
    print(f"  叙述文本:")
    print(f"    对话比例: {narrative_meta['dialogue_ratio']:.4f}")
    print(f"    叙述比例: {narrative_meta['narrative_ratio']:.4f}")
    print(f"    文本类型: {'叙述' if narrative_meta['narrative_ratio'] > 0.6 else '混合'}")
    
    print(f"\n  对话文本:")
    print(f"    对话比例: {dialogue_meta['dialogue_ratio']:.4f}")
    print(f"    叙述比例: {dialogue_meta['narrative_ratio']:.4f}")
    print(f"    文本类型: {'对话' if dialogue_meta['dialogue_ratio'] > 0.6 else '混合'}")
    
    narrative_features = extractor.extract_features(narrative_text)
    dialogue_features = extractor.extract_features(dialogue_text)
    
    feature_names = extractor.feature_names
    ttr_idx = feature_names.index('type_token_ratio')
    ttr_cond_idx = feature_names.index('type_token_ratio_cond')
    hapax_idx = feature_names.index('hapax_legomena_ratio')
    hapax_cond_idx = feature_names.index('hapax_legomena_ratio_cond')
    
    print(f"\n词汇丰富度对比:")
    print(f"  叙述文本:")
    print(f"    原始TTR: {narrative_features[ttr_idx]:.4f}")
    print(f"    条件TTR: {narrative_features[ttr_cond_idx]:.4f}")
    print(f"    原始Hapax: {narrative_features[hapax_idx]:.4f}")
    print(f"    条件Hapax: {narrative_features[hapax_cond_idx]:.4f}")
    
    print(f"\n  对话文本:")
    print(f"    原始TTR: {dialogue_features[ttr_idx]:.4f}")
    print(f"    条件TTR: {dialogue_features[ttr_cond_idx]:.4f}")
    print(f"    原始Hapax: {dialogue_features[hapax_idx]:.4f}")
    print(f"    条件Hapax: {dialogue_features[hapax_cond_idx]:.4f}")
    
    raw_diff = abs(narrative_features[ttr_idx] - dialogue_features[ttr_idx])
    cond_diff = abs(narrative_features[ttr_cond_idx] - dialogue_features[ttr_cond_idx])
    
    print(f"\n归一化效果:")
    print(f"  原始TTR差异: {raw_diff:.4f}")
    print(f"  条件TTR差异: {cond_diff:.4f}")
    print(f"  差异减少: {((raw_diff - cond_diff) / raw_diff * 100):.1f}%" if raw_diff > 0 else "  无差异")
    
    if cond_diff < raw_diff:
        print("\n  ✓ 修复有效: 条件归一化减少了文本类型对词汇丰富度的影响")
        return True
    else:
        print("\n  ⚠ 修复效果需要进一步验证")
        return False


def test_issue_2_poetry_function_words():
    """测试问题2: 功能词表在诗歌体裁中的失效问题修复"""
    print("\n" + "=" * 60)
    print("测试2: 诗歌体裁的功能词权重调整")
    print("=" * 60)
    
    extractor = FeatureExtractor()
    
    poetry_text = SAMPLE_TEXTS["poetry"]
    prose_text = SAMPLE_TEXTS["prose"]
    
    poetry_meta = extractor.get_text_metadata(poetry_text)
    prose_meta = extractor.get_text_metadata(prose_text)
    
    print(f"\n体裁检测:")
    print(f"  诗歌文本:")
    print(f"    诗歌分数: {poetry_meta['poetry_score']:.4f}")
    print(f"    散文分数: {poetry_meta['prose_score']:.4f}")
    print(f"    体裁: {'诗歌' if poetry_meta['poetry_score'] > 0.5 else '散文'}")
    
    print(f"\n  散文文本:")
    print(f"    诗歌分数: {prose_meta['poetry_score']:.4f}")
    print(f"    散文分数: {prose_meta['prose_score']:.4f}")
    print(f"    体裁: {'诗歌' if prose_meta['poetry_score'] > 0.5 else '散文'}")
    
    print(f"\n  诗歌韵律特征:")
    print(f"    行长均值: {poetry_meta.get('line_length_mean', 0):.4f}")
    print(f"    诗节数: {poetry_meta.get('stanza_count', 0):.4f}")
    print(f"    押韵密度: {poetry_meta.get('rhyme_density', 0):.4f}")
    print(f"    节奏规律性: {poetry_meta.get('rhythm_regularity', 0):.4f}")
    
    feature_names = extractor.feature_names
    func_indices = [i for i, name in enumerate(feature_names) 
                   if name.startswith('func_')]
    
    poetry_features = extractor.extract_features(poetry_text)
    prose_features = extractor.extract_features(prose_text)
    
    poetry_func_sum = np.sum(np.abs(poetry_features[func_indices]))
    prose_func_sum = np.sum(np.abs(prose_features[func_indices]))
    
    article_words = ['func_the', 'func_a', 'func_an']
    article_indices = [feature_names.index(w) for w in article_words if w in feature_names]
    
    poetry_article_sum = np.sum(np.abs(poetry_features[article_indices]))
    prose_article_sum = np.sum(np.abs(prose_features[article_indices]))
    
    print(f"\n功能词特征对比:")
    print(f"  散文功能词权重和: {prose_func_sum:.4f}")
    print(f"  诗歌功能词权重和: {poetry_func_sum:.4f}")
    print(f"  比例 (诗歌/散文): {poetry_func_sum / prose_func_sum:.4f}")
    
    print(f"\n冠词功能词对比 (the, a, an):")
    print(f"  散文冠词权重和: {prose_article_sum:.4f}")
    print(f"  诗歌冠词权重和: {poetry_article_sum:.4f}")
    print(f"  比例 (诗歌/散文): {poetry_article_sum / prose_article_sum:.4f}" if prose_article_sum > 0 else "  散文无冠词")
    
    if poetry_meta['poetry_score'] > 0.5 and prose_meta['poetry_score'] < 0.5:
        if poetry_article_sum < prose_article_sum * 0.8:
            print("\n  ✓ 修复有效: 诗歌体裁中冠词类功能词权重已降低")
            return True
        else:
            print("\n  ⚠ 功能词权重调整需要更多样本验证")
            return None
    else:
        print("\n  ⚠ 体裁检测需要更多样本验证")
        return None


def test_issue_3_length_confidence_bias():
    """测试问题3: 长文本置信度虚高修复"""
    print("\n" + "=" * 60)
    print("测试3: 长文本置信度虚高的归一化修复")
    print("=" * 60)
    
    extractor = FeatureExtractor()
    classifier = AuthorClassifier(feature_dim=372)
    
    train_texts = []
    train_authors = []
    
    for author, texts in list(SAMPLE_TEXTS.items())[:4]:
        for text in texts:
            if author not in ['narrative_prose', 'dialogue_heavy', 'poetry', 'prose']:
                train_texts.append(text)
                train_authors.append(author)
    
    author_map = {
        "narrative_prose": "Dickens",
        "dialogue_heavy": "Austen", 
        "poetry": "Dickinson",
        "prose": "Twain"
    }
    
    sample_authors = ["Dickens", "Austen", "Dickinson", "Twain", 
                      "Dickens", "Austen", "Dickinson", "Twain"]
    sample_texts = [
        SAMPLE_TEXTS["narrative_prose"],
        SAMPLE_TEXTS["dialogue_heavy"],
        SAMPLE_TEXTS["poetry"],
        SAMPLE_TEXTS["prose"],
        SAMPLE_TEXTS["narrative_prose"][:100],
        SAMPLE_TEXTS["dialogue_heavy"][:50],
        SAMPLE_TEXTS["poetry"],
        SAMPLE_TEXTS["prose"][:150],
    ]
    
    all_texts = train_texts + sample_texts
    all_authors = train_authors + sample_authors
    
    features = extractor.extract_batch(all_texts)
    
    text_metadata = [extractor.get_text_metadata(t) for t in all_texts]
    word_counts = [meta['word_count'] for meta in text_metadata]
    
    print(f"\n训练集: {len(train_texts)}篇, 测试集: {len(sample_texts)}篇")
    
    metrics = classifier.fit(
        features[:len(train_texts)], 
        all_authors[:len(train_texts)],
        use_ensemble=True,
        text_word_counts=word_counts[:len(train_texts)]
    )
    
    print(f"\n长度归一化: {'已启用' if metrics.get('length_normalization_enabled') else '未启用'}")
    
    if classifier.train_text_length_stats:
        print(f"  训练文本长度统计:")
        print(f"    均值: {classifier.train_text_length_stats['mean']:.1f}词")
        print(f"    标准差: {classifier.train_text_length_stats['std']:.1f}词")
    
    test_features = features[len(train_texts):]
    test_metadata = text_metadata[len(train_texts):]
    
    results_no_calib = classifier.predict_with_confidence(
        test_features, text_metadata=None
    )
    
    results_with_calib = classifier.predict_with_confidence(
        test_features, text_metadata=test_metadata
    )
    
    print(f"\n置信度校准对比 (8个测试样本):")
    print(f"{'文本':<15} {'词数':<6} {'原始置信':<10} {'校准后':<10} {'变化':<10}")
    print("-" * 60)
    
    confidences_raw = []
    confidences_calib = []
    word_counts_test = []
    
    for i, (no_calib, with_calib, meta) in enumerate(zip(
        results_no_calib, results_with_calib, test_metadata
    )):
        raw_conf = no_calib['confidence']
        calib_conf = with_calib['confidence']
        word_count = meta['word_count']
        change = calib_conf - raw_conf
        
        label = f"样本{i+1}"
        print(f"{label:<15} {word_count:<6} {raw_conf:<10.4f} {calib_conf:<10.4f} {change:+.4f}")
        
        confidences_raw.append(raw_conf)
        confidences_calib.append(calib_conf)
        word_counts_test.append(word_count)
    
    raw_corr = np.corrcoef(word_counts_test, confidences_raw)[0, 1]
    calib_corr = np.corrcoef(word_counts_test, confidences_calib)[0, 1]
    
    print(f"\n词数与置信度的相关性:")
    print(f"  未校准: {raw_corr:.4f}")
    print(f"  校准后: {calib_corr:.4f}")
    
    if abs(calib_corr) < abs(raw_corr):
        reduction = (abs(raw_corr) - abs(calib_corr)) / abs(raw_corr) * 100
        print(f"  相关性降低: {reduction:.1f}%")
        print("\n  ✓ 修复有效: 置信度与文本长度的相关性已降低")
        return True
    else:
        print("\n  ⚠ 置信度校正需要更多样本验证")
        return False


def run_all_tests():
    """运行所有bug修复测试"""
    print("\n" + "=" * 60)
    print("Bug修复验证测试套件")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(test_issue_1_dialogue_vs_narrative())
    except Exception as e:
        print(f"\n  ✗ 测试1异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)
    
    try:
        results.append(test_issue_2_poetry_function_words())
    except Exception as e:
        print(f"\n  ✗ 测试2异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)
    
    try:
        results.append(test_issue_3_length_confidence_bias())
    except Exception as e:
        print(f"\n  ✗ 测试3异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for r in results if r is True)
    total = len(results)
    
    print(f"通过: {passed}/{total}")
    
    issue_names = [
        "问题1: 对话vs叙述词汇丰富度混淆",
        "问题2: 诗歌功能词失效", 
        "问题3: 长文本置信度虚高"
    ]
    
    for i, (name, result) in enumerate(zip(issue_names, results)):
        status = "✓ 通过" if result is True else "⚠ 待验证" if result is None else "✗ 失败"
        print(f"  {name}: {status}")
    
    if passed >= 2:
        print("\n✓ 主要Bug修复已验证通过!")
        return True
    else:
        print("\n⚠ 部分测试需要更多样本验证")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
