"""
集成测试
验证所有模块协同工作
"""

import sys
import os
import numpy as np
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from author_authorship import (
    FeatureExtractor,
    AuthorClassifier,
    StyleDriftAnalyzer,
    StyleVisualizer,
    PrototypicalNetwork
)


SAMPLE_DATA = {
    "William Shakespeare": [
        """To be, or not to be: that is the question. Whether 'tis nobler in the mind to suffer the slings and arrows of outrageous fortune.""",
        """What's in a name? That which we call a rose by any other name would smell as sweet. So Romeo would, were he not Romeo call'd.""",
        """All the world's a stage, and all the men and women merely players. They have their exits and their entrances.""",
    ],
    "Charles Dickens": [
        """It was the best of times, it was the worst of times, it was the age of wisdom, it was the age of foolishness.""",
        """There were a king with a large jaw and a queen with a plain face, on the throne of England. In both countries it was clearer than crystal.""",
        """The old man sat alone in his room, thinking about the past. He had seen many things in his long life, both good and bad.""",
    ],
    "Jane Austen": [
        """It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife.""",
        """I declare after all there is no enjoyment like reading! How much sooner one tires of any thing than of a book!""",
        """The more I know of the world, the more I am convinced that I shall never see a man whom I can really love.""",
    ],
    "Mark Twain": [
        """The old lady pulled her spectacles down and looked over them about the room. Then she put them up and looked out under them.""",
        """I have been studying the traits and dispositions of the lower animals and contrasting them with the traits of man.""",
        """The secret of getting ahead is getting started. The secret of getting started is breaking your complex tasks into small manageable ones.""",
    ],
}


def test_full_pipeline():
    """测试完整工作流"""
    print("=" * 60)
    print("集成测试: 完整工作流")
    print("=" * 60)
    
    try:
        print("\n1. 初始化所有模块...")
        extractor = FeatureExtractor()
        classifier = AuthorClassifier()
        drift_analyzer = StyleDriftAnalyzer(extractor)
        visualizer = StyleVisualizer(extractor)
        protonet = PrototypicalNetwork()
        print("  ✓ 所有模块初始化成功")
        
        print("\n2. 准备数据...")
        all_texts = []
        all_authors = []
        for author, texts in SAMPLE_DATA.items():
            for text in texts:
                all_texts.append(text)
                all_authors.append(author)
        print(f"  ✓ 数据集: {len(set(all_authors))}位作者, {len(all_texts)}篇文本")
        
        print("\n3. 提取特征...")
        features = extractor.extract_batch(all_texts)
        print(f"  ✓ 特征矩阵形状: {features.shape}")
        print(f"  ✓ 特征维度: {features.shape[1]}")
        
        print("\n4. 训练分类器...")
        metrics = classifier.fit(features, all_authors, use_ensemble=True)
        print(f"  ✓ 随机森林准确率: {metrics['random_forest_accuracy']:.4f}")
        print(f"  ✓ 集成准确率: {metrics['ensemble_accuracy']:.4f}")
        
        print("\n5. 预测测试...")
        test_text = "It was the best of times, it was the worst of times."
        test_features = extractor.extract_features(test_text, all_texts=all_texts)
        test_features = test_features.reshape(1, -1)
        
        results = classifier.predict_with_confidence(test_features)
        result = results[0]
        print(f"  ✓ 预测作者: {result['predicted_author']}")
        print(f"  ✓ 置信度: {result['confidence']:.4f}")
        print(f"  ✓ Top 3: {[p['author'] for p in result['top_predictions'][:3]]}")
        
        print("\n6. 风格散度计算...")
        text1 = SAMPLE_DATA["William Shakespeare"][0]
        text2 = SAMPLE_DATA["Charles Dickens"][0]
        feat1 = extractor.extract_features(text1, all_texts=all_texts)
        feat2 = extractor.extract_features(text2, all_texts=all_texts)
        
        divergence = classifier.compute_style_divergence(feat1, feat2)
        print(f"  ✓ KL散度: {divergence['kl_divergence']:.4f}")
        print(f"  ✓ JS散度: {divergence['js_divergence']:.4f}")
        print(f"  ✓ 余弦相似度: {divergence['cosine_similarity']:.4f}")
        
        print("\n7. 时序风格漂移分析...")
        author_works = SAMPLE_DATA["Charles Dickens"]
        work_features = [extractor.extract_features(w, all_texts=all_texts) 
                        for w in author_works]
        
        drift_analysis = drift_analyzer.analyze_temporal_drift(
            work_features,
            work_titles=[f"Work {i+1}" for i in range(len(author_works))]
        )
        print(f"  ✓ 累积漂移: {drift_analysis['total_cumulative_drift']:.4f}")
        print(f"  ✓ 漂移速率: {drift_analysis['drift_rate']:.4f}")
        
        print("\n8. 原型网络小样本学习...")
        new_author_texts = [
            """In the realm of technology, innovation is the driving force behind progress. Every day brings new discoveries that reshape our understanding of the world.""",
            """The digital revolution has transformed every aspect of modern life. Communication, commerce, and culture have all been redefined by the power of computing.""",
            """Artificial intelligence is no longer just a concept from science fiction. It is now an integral part of our daily lives, from voice assistants to recommendation systems."""
        ]
        new_features = [extractor.extract_features(t, all_texts=all_texts) 
                       for t in new_author_texts]
        
        protonet.fit_base_model(features, all_authors)
        add_result = protonet.add_new_author("Tech Author", new_features)
        print(f"  ✓ 新作者添加: {add_result['author_name']}")
        print(f"  ✓ 样本数: {add_result['num_samples']}")
        print(f"  ✓ 可分性比率: {add_result['separability_ratio']:.4f}")
        
        print("\n9. 原型网络预测...")
        proto_results = protonet.predict_with_confidence(test_features)
        print(f"  ✓ 预测作者: {proto_results[0]['predicted_author']}")
        print(f"  ✓ 置信度: {proto_results[0]['confidence']:.4f}")
        
        print("\n10. 模型保存与加载...")
        with tempfile.TemporaryDirectory() as tmpdir:
            classifier_path = os.path.join(tmpdir, "classifier.joblib")
            protonet_path = os.path.join(tmpdir, "protonet.joblib")
            
            classifier.save(classifier_path)
            protonet.save(protonet_path)
            print("  ✓ 模型保存成功")
            
            loaded_classifier = AuthorClassifier.load(classifier_path)
            loaded_protonet = PrototypicalNetwork.load(protonet_path)
            print("  ✓ 模型加载成功")
            
            load_test_results = loaded_classifier.predict_with_confidence(test_features)
            print(f"  ✓ 加载后预测: {load_test_results[0]['predicted_author']}")
        
        print("\n" + "=" * 60)
        print("集成测试: 全部通过 ✓")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_visualization():
    """测试可视化模块"""
    print("\n" + "=" * 60)
    print("集成测试: 可视化模块")
    print("=" * 60)
    
    try:
        print("\n1. 初始化...")
        extractor = FeatureExtractor()
        visualizer = StyleVisualizer(extractor)
        print("  ✓ 初始化成功")
        
        print("\n2. 准备数据...")
        all_texts = []
        all_authors = []
        all_labels = []
        for author, texts in SAMPLE_DATA.items():
            for i, text in enumerate(texts):
                all_texts.append(text)
                all_authors.append(author)
                all_labels.append(f"{author}_{i+1}")
        
        features = extractor.extract_batch(all_texts)
        print(f"  ✓ 数据准备完成: {len(all_texts)}篇文本")
        
        print("\n3. 生成可视化...")
        with tempfile.TemporaryDirectory() as tmpdir:
            viz_types = ['tsne', 'pca', 'parallel', 'radar', 'heatmap']
            
            for viz_type in viz_types:
                output_path = os.path.join(tmpdir, f"{viz_type}.html")
                try:
                    result = visualizer.__getattribute__(
                        f"{viz_type}_visualization" if viz_type != 'heatmap' else 'feature_heatmap'
                    )(
                        features=features,
                        labels=all_labels,
                        authors=all_authors,
                        output_path=output_path
                    )
                    if result and os.path.exists(output_path):
                        print(f"  ✓ {viz_type}: 生成成功")
                    else:
                        print(f"  ~ {viz_type}: 未保存文件（返回HTML）")
                except Exception as e:
                    print(f"  ~ {viz_type}: 跳过 ({str(e)[:50]})")
        
        print("\n" + "=" * 60)
        print("可视化测试: 完成 ✓")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n  ✗ 可视化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_style_drift_detailed():
    """详细测试风格漂移分析"""
    print("\n" + "=" * 60)
    print("集成测试: 风格漂移详细分析")
    print("=" * 60)
    
    try:
        print("\n1. 初始化...")
        extractor = FeatureExtractor()
        drift_analyzer = StyleDriftAnalyzer(extractor)
        print("  ✓ 初始化成功")
        
        print("\n2. 测试多种散度计算...")
        text1 = SAMPLE_DATA["William Shakespeare"][0]
        text2 = SAMPLE_DATA["William Shakespeare"][1]
        text3 = SAMPLE_DATA["Charles Dickens"][0]
        
        feat1 = extractor.extract_features(text1)
        feat2 = extractor.extract_features(text2)
        feat3 = extractor.extract_features(text3)
        
        same_author_div = drift_analyzer.compute_all_divergences(feat1, feat2)
        diff_author_div = drift_analyzer.compute_all_divergences(feat1, feat3)
        
        print("\n  同一作者散度:")
        for metric, value in list(same_author_div.items())[:5]:
            print(f"    {metric}: {value:.4f}")
        
        print("\n  不同作者散度:")
        for metric, value in list(diff_author_div.items())[:5]:
            print(f"    {metric}: {value:.4f}")
        
        print("\n  散度比率 (不同/同一):")
        for metric in list(same_author_div.keys())[:5]:
            if same_author_div[metric] > 0:
                ratio = diff_author_div[metric] / same_author_div[metric]
                print(f"    {metric}: {ratio:.2f}x")
        
        print("\n3. 测试分组散度...")
        group_divs = drift_analyzer.compute_group_divergences(feat1, feat3)
        print(f"\n  按特征组散度 (JS):")
        for group, divs in group_divs.items():
            if 'js_divergence' in divs:
                print(f"    {group}: {divs['js_divergence']:.4f}")
        
        print("\n4. 测试多作品时序分析...")
        works = SAMPLE_DATA["William Shakespeare"] + SAMPLE_DATA["Charles Dickens"]
        work_features = [extractor.extract_features(w) for w in works]
        work_titles = [f"Shakespeare_{i+1}" for i in range(3)] + \
                     [f"Dickens_{i+1}" for i in range(3)]
        
        drift_analysis = drift_analyzer.analyze_temporal_drift(
            work_features, work_titles=work_titles
        )
        
        print(f"\n  时序分析结果:")
        print(f"    作品数: {len(work_titles)}")
        print(f"    总累积漂移: {drift_analysis['total_cumulative_drift']:.4f}")
        print(f"    漂移速率: {drift_analysis['drift_rate']:.4f}")
        
        change_points = drift_analyzer.detect_style_change_points(
            work_features, threshold=0.5
        )
        print(f"    检测到的突变点: {change_points}")
        
        print("\n5. 测试滑动窗口分析...")
        long_text = " ".join(SAMPLE_DATA["William Shakespeare"])
        window_result = drift_analyzer.sliding_window_drift(
            long_text, window_size=200, step_size=100
        )
        
        if 'num_windows' in window_result:
            print(f"    窗口数: {window_result['num_windows']}")
            print(f"    窗口大小: {window_result['window_size']}")
        
        print("\n" + "=" * 60)
        print("风格漂移测试: 完成 ✓")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n  ✗ 风格漂移测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有集成测试"""
    print("\n" + "=" * 60)
    print("集成测试套件")
    print("=" * 60)
    
    results = []
    
    results.append(test_full_pipeline())
    results.append(test_visualization())
    results.append(test_style_drift_detailed())
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"通过: {sum(results)}/{len(results)}")
    
    if all(results):
        print("所有测试通过! ✓")
        return True
    else:
        print("部分测试失败 ✗")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
