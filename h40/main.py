"""
主程序入口
小说作者归属分析系统 - 使用示例
"""

import os
import sys
import numpy as np
from typing import List, Dict, Optional
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from author_authorship import (
    FeatureExtractor,
    AuthorClassifier,
    StyleDriftAnalyzer,
    StyleVisualizer,
    PrototypicalNetwork,
    CrossLanguageClassifier,
    DialogueSeparator,
    CharacterStyleAnalyzer,
    NarrativePerspectiveDetector
)


SAMPLE_TEXTS = {
    "William Shakespeare": [
        """To be, or not to be: that is the question:
        Whether 'tis nobler in the mind to suffer
        The slings and arrows of outrageous fortune,
        Or to take arms against a sea of troubles,
        And by opposing end them? To die: to sleep;
        No more; and by a sleep to say we end
        The heart-ache and the thousand natural shocks
        That flesh is heir to, 'tis a consummation
        Devoutly to be wish'd. To die, to sleep;
        To sleep: perchance to dream: ay, there's the rub.""",
        
        """What's in a name? That which we call a rose
        By any other name would smell as sweet;
        So Romeo would, were he not Romeo call'd,
        Retain that dear perfection which he owes
        Without that title. Romeo, doff thy name,
        And for that name which is no part of thee
        Take all myself."""
    ],
    
    "Charles Dickens": [
        """It was the best of times, it was the worst of times,
        it was the age of wisdom, it was the age of foolishness,
        it was the epoch of belief, it was the epoch of incredulity,
        it was the season of Light, it was the season of Darkness,
        it was the spring of hope, it was the winter of despair,
        we had everything before us, we had nothing before us,
        we were all going direct to Heaven, we were all going direct
        the other way--in short, the period was so far like the present
        period, that some of its noisiest authorities insisted on its
        being received, for good or for evil, in the superlative degree
        of comparison only.""",
        
        """There were a king with a large jaw and a queen with a plain face,
        on the throne of England; there were a king with a large jaw and
        a queen with a fair face, on the throne of France. In both
        countries it was clearer than crystal to the lords of the State
        preserves of loaves and fishes, that things in general were
        settled for ever."""
    ],
    
    "Jane Austen": [
        """It is a truth universally acknowledged, that a single man in
        possession of a good fortune, must be in want of a wife.
        However little known the feelings or views of such a man may be
        on his first entering a neighbourhood, this truth is so well
        fixed in the minds of the surrounding families, that he is
        considered the rightful property of some one or other of their
        daughters.""",
        
        """I declare after all there is no enjoyment like reading! How much
        sooner one tires of any thing than of a book! -- When I have a
        house of my own, I shall be miserable if I have not an excellent
        library."""
    ],
    
    "Mark Twain": [
        """The old lady pulled her spectacles down and looked over them
        about the room; then she put them up and looked out under them.
        She seldom or never looked through them for so small a thing as
        a boy; they were her state pair, the pride of her heart, and
        were built for "style," not service--she could have seen through
        a pair of stove-lids just as well. She looked perplexed for a
        moment, and then said, not fiercely, but still loud enough for
        the furniture to hear: "Well, I lay if I get hold of you I'll--"
        She did not finish, for by this time she was bending down and
        punching under the bed with the broom, and so she needed breath
        to punctuate the punches with.""",
        
        """I have been studying the traits and dispositions of the
        "lower animals" (so called) and contrasting them with the
        traits and dispositions of man. I find the result humiliating
        to me. For it obliges me to renounce my allegiance to the
        Darwinian theory of the Ascent of Man from the Lower Animals;
        since it now seems plain to me that that theory ought to be
        vacated in favor of a new and truer one, to be named the
        Descent of Man from the Higher Animals."""
    ],
    
    "Ernest Hemingway": [
        """The old man was thin and gaunt with deep wrinkles in the back
        of his neck. The brown blotches of the benevolent skin cancer
        the sun brings from its reflection on the tropic sea were on
        his cheeks. The blotches ran well down the sides of his face
        and his hands had the deep-creased scars from handling heavy
        fish on the cords. But none of these scars were fresh. They
        were as old as erosions in a fishless desert.""",
        
        """I drink to make other people more interesting. When you are
        older, you will see what I mean. You should write it down. But
        then you are not a writer. I am a writer, and it is my
        responsibility to write things down. I will write it down now,
        so that you will have it to remember. The world is a fine place
        and worth the fighting for, and I hate very much to leave it."""
    ],
    
    "Emily Dickinson": [
        """I'm Nobody! Who are you?
        Are you--Nobody--too?
        Then there's a pair of us!
        Don't tell! they'd advertise--you know!

        How dreary--to be--Somebody!
        How public--like a Frog--
        To tell one's name--the livelong June--
        To an admiring Bog!""",
        
        """"Hope" is the thing with feathers--
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
        It asked a crumb--of me."""
    ]
}


MULTILINGUAL_SAMPLES = {
    "Lu Xun (Chinese)": [
        """这是民国六年的冬天，大北风刮得正猛，我因为生计关系，不得不一早在路上走。
        一路几乎遇不见人，好容易才雇定了一辆人力车，教他拉到S门去。
        不一会，北风小了，路上浮尘早已刮净，剩下一条洁白的大道来，车夫也跑得更快。
        刚近S门，忽而车把上带着一个人，慢慢地倒了。""",
        
        """我翻开历史一查，这历史没有年代，歪歪斜斜的每叶上都写着"仁义道德"几个字。
        我横竖睡不着，仔细看了半夜，才从字缝里看出字来，满本都写着两个字是"吃人"！"""
    ],
    "Haruki Murakami (Japanese)": [
        """僕は三十七歳で、そのときボーイング747のシートに座っていた。
        その巨大な飛行機はぶ厚い雨雲をくぐり抜けて降下し、ハンブルク空港に着陸しようとしているところだった。
        十一月の冷ややかな雨が大地を暗く染め、雨合羽を着た整備工たちや、のっぺりとした空港ビルの上に立った旗や、
        BMWの広告板や、何もかもがやはりフランダース派の絵画のように見えた。""",
        
        """「永遠のヴァージンであり続けることはできないけれど、永遠のセミバージンであることはできるわ」
        と彼女は言った。そして静かに笑った。それは心からの笑いではなかったけれど、
        少なくともそこには何かしらの真実のかけらのようなものが含まれていた。"""
    ]
}


CHARACTER_DIALOGUE_SAMPLE = """
The sun was setting over the small town, painting the sky in shades of orange and purple.

"Hey, Alice! Wait up!" shouted Tom, running down the street. "I've been looking everywhere for you."

Alice turned around, her blue eyes sparkling. "Tom! What are you doing here? I thought you were working late at the shop today."

"I got off early," said Tom, catching his breath. "Mr. Johnson said I could leave once the inventory was done. So, I was thinking... maybe we could get some ice cream? My treat."

"Oh, that sounds wonderful!" Alice exclaimed. "But wait, I need to check with my mom first. She might need help with dinner."

"Just give her a quick call," Tom suggested. "I'll wait right here. I promise not to go anywhere."

Alice nodded and pulled out her phone. As she dialed, Tom looked around at the familiar streets. He had grown up in this town, and every corner held a memory.

"Mom says it's fine!" Alice said happily, hanging up the phone. "But we have to be back by seven. We're having her famous meatloaf tonight."

"Meatloaf? I love your mom's meatloaf!" Tom said, grinning. "Maybe she'll even let me stay for dinner?"

"Maybe," Alice said playfully. "But only if you buy me double chocolate ice cream. With sprinkles."

"Deal!" Tom said, holding out his hand. "Double chocolate with sprinkles, coming right up."

As they walked towards the ice cream shop, the old streetlights flickered on, casting a warm glow on the sidewalk.

"You know," Alice said quietly, "I really like spending time with you, Tom. Even if we're just walking around town."

Tom felt his cheeks turn red. "I like spending time with you too, Alice. More than you know."

They walked in comfortable silence for a moment, watching the stars begin to appear in the darkening sky.

"Hey, look!" Alice said suddenly, pointing upwards. "Is that a shooting star?"

Tom followed her gaze. "I think it is! Quick, make a wish!"

They both closed their eyes for a moment, each making their own silent wish.

"What did you wish for?" Alice asked.

"If I tell you, it won't come true," Tom said mysteriously. "But I can tell you this... it involved you, me, and a lifetime of double chocolate ice cream."

Alice laughed, a sound that Tom thought was more beautiful than any music. "You're so silly, Tom. But... I wished for the same thing."

The shooting star streaked across the sky, carrying two hopeful wishes into the night.
"""


PERSPECTIVE_SAMPLES = {
    "first_person": """
I woke up this morning with a strange feeling in my bones. Something was different, 
but I couldn't quite put my finger on it. I stretched my arms above my head and 
yawned, watching the sunlight filter through the curtains. I had a long day ahead of me, 
but for once, I felt ready to face whatever came my way. I threw back the covers and 
swung my legs over the edge of the bed. This was going to be my day, I decided. 
Nothing was going to stop me.
""",
    "third_person_omniscient": """
Mary sat at her desk, staring at the letter in her hand. What she didn't know was that 
across town, John was doing the exact same thing. Both of them held the same secret, 
yet neither dared to speak it aloud. Mary's hands trembled as she re-read the words 
for the hundredth time. In another part of the city, John paced back and forth in his 
small apartment, wondering if he should call her. The universe had brought them together 
once before, and now it seemed fate was giving them a second chance. Only time would tell 
if they would have the courage to seize it.
""",
    "third_person_limited": """
Sarah watched the door intently, her fingers tapping nervously on the table. She had 
been waiting for over an hour, and still there was no sign of him. She checked her phone 
again—no messages, no missed calls. Where could he be? She tried to tell herself that 
he was probably just stuck in traffic, but a nagging voice in the back of her mind 
whispered that something was wrong. She took a sip of her cold coffee and tried to 
calm her racing heart. The door opened suddenly, and she looked up with a mixture of 
hope and fear.
""",
    "third_person_objective": """
The man walked into the bank at exactly 9:15 AM. He wore a dark suit and carried a 
black leather briefcase. He approached the teller's window and placed the briefcase 
on the counter. The teller looked up from her computer screen. The man spoke quietly, 
his expression remaining neutral throughout the conversation. The teller nodded and 
began typing on her keyboard. Five minutes later, the man picked up the briefcase, 
turned, and walked out of the bank. He hailed a taxi on the sidewalk and gave the 
driver an address. The taxi pulled away from the curb and disappeared into the midday traffic.
"""
}


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="小说作者归属分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--mode',
        choices=['demo', 'train', 'predict', 'add_author', 'drift', 'visualize', 'server'],
        default='demo',
        help='运行模式'
    )
    
    parser.add_argument(
        '--input',
        type=str,
        help='输入文本文件路径 (predict模式)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='output',
        help='输出目录路径'
    )
    
    parser.add_argument(
        '--author-name',
        type=str,
        help='新作者名称 (add_author模式)'
    )
    
    parser.add_argument(
        '--samples',
        type=str,
        nargs='+',
        help='新作者样本文件路径列表 (add_author模式)'
    )
    
    parser.add_argument(
        '--viz-type',
        choices=['tsne', 'pca', 'parallel', 'radar', 'heatmap'],
        default='tsne',
        help='可视化类型'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='API服务端口'
    )
    
    return parser.parse_args()


def run_demo(output_dir: str):
    """运行演示程序"""
    print("=" * 60)
    print("小说作者归属分析系统 - 演示模式")
    print("=" * 60)
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n1. 初始化模块...")
    try:
        extractor = FeatureExtractor()
    except Exception as e:
        print(f"  警告: 加载spaCy模型失败: {e}")
        print("  使用备用方案初始化...")
        extractor = FeatureExtractor(spacy_model='en_core_web_sm')
    
    classifier = AuthorClassifier()
    drift_analyzer = StyleDriftAnalyzer(extractor)
    visualizer = StyleVisualizer(extractor)
    protonet = PrototypicalNetwork()
    
    print("   模块初始化完成")
    
    print("\n2. 准备示例数据...")
    all_texts = []
    all_authors = []
    
    for author, texts in SAMPLE_TEXTS.items():
        for text in texts:
            all_texts.append(text)
            all_authors.append(author)
    
    print(f"   共加载 {len(SAMPLE_TEXTS)} 位作者，{len(all_texts)} 篇文本")
    
    print("\n3. 提取风格特征和文本元数据...")
    features = extractor.extract_batch(all_texts)
    print(f"   特征维度: {features.shape[1]}")
    print(f"   特征分组: {list(extractor.get_feature_groups().keys())}")
    
    text_metadata_list = [extractor.get_text_metadata(text) for text in all_texts]
    text_word_counts = [meta['word_count'] for meta in text_metadata_list]
    
    print("\n   文本类型和体裁检测:")
    for i, (author, meta) in enumerate(zip(all_authors, text_metadata_list)):
        text_type = "对话" if meta['dialogue_ratio'] > 0.6 else \
                    "叙述" if meta['narrative_ratio'] > 0.6 else "混合"
        genre = "诗歌" if meta['poetry_score'] > 0.5 else "散文"
        print(f"     {author} 文本{i+1}: {text_type} | {genre} | {meta['word_count']}词")
    
    print("\n4. 训练分类器（含文本长度归一化）...")
    metrics = classifier.fit(
        features, all_authors, 
        use_ensemble=True,
        text_word_counts=text_word_counts
    )
    print(f"   随机森林准确率: {metrics['random_forest_accuracy']:.4f}")
    if metrics.get('svc_accuracy'):
        print(f"   SVC准确率: {metrics['svc_accuracy']:.4f}")
    print(f"   集成准确率: {metrics['ensemble_accuracy']:.4f}")
    print(f"   长度归一化: {'已启用' if metrics.get('length_normalization_enabled') else '未启用'}")
    
    print("\n5. 测试预测（含置信度校准）...")
    test_text = """It was the best of times, it was the worst of times."""
    test_metadata = extractor.get_text_metadata(test_text)
    test_features = extractor.extract_features(test_text, all_texts=all_texts)
    test_features = test_features.reshape(1, -1)
    
    results = classifier.predict_with_confidence(
        test_features, text_metadata=[test_metadata]
    )
    result = results[0]
    
    print(f"\n   测试文本: \"{test_text}\"")
    print(f"   文本类型: {'对话' if test_metadata['dialogue_ratio'] > 0.6 else '叙述' if test_metadata['narrative_ratio'] > 0.6 else '混合'}")
    print(f"   体裁: {'诗歌' if test_metadata['poetry_score'] > 0.5 else '散文'}")
    print(f"   词数: {test_metadata['word_count']}")
    print(f"\n   预测作者: {result['predicted_author']}")
    print(f"   原始置信度: {result['raw_confidence']:.4f}")
    print(f"   校准后置信度: {result['confidence']:.4f}")
    
    calib = result.get('confidence_calibration', {})
    if calib:
        print(f"\n   置信度校准因子:")
        print(f"     长度因子: {calib.get('length_factor', 1.0):.4f}")
        print(f"     体裁因子: {calib.get('genre_factor', 1.0):.4f}")
        print(f"     文本类型因子: {calib.get('text_type_factor', 1.0):.4f}")
    
    print("\n   Top 5 预测:")
    for i, pred in enumerate(result['top_predictions']):
        calib_prob = pred.get('calibrated_probability', pred['probability'])
        print(f"     {i+1}. {pred['author']}: 原始={pred['probability']:.4f}, 校准后={calib_prob:.4f}")
    
    print("\n   长文本vs短文本置信度校准对比:")
    long_text = test_text * 10
    long_metadata = extractor.get_text_metadata(long_text)
    long_features = extractor.extract_features(long_text, all_texts=all_texts)
    long_results = classifier.predict_with_confidence(
        long_features.reshape(1, -1), text_metadata=[long_metadata]
    )
    long_result = long_results[0]
    print(f"     短文本 ({test_metadata['word_count']}词): 原始={result['raw_confidence']:.4f}, 校准后={result['confidence']:.4f}")
    print(f"     长文本 ({long_metadata['word_count']}词): 原始={long_result['raw_confidence']:.4f}, 校准后={long_result['confidence']:.4f}")
    
    print("\n6. 原型网络小样本学习演示...")
    print("\n   添加新作者 'New Author':")
    new_author_samples = [
        """In the beginning, there was only darkness. Then came the light,
        and with it, the promise of a new day. The mountains stood tall
        and proud, their peaks touching the clouds. Below, the river
        flowed like a silver serpent through the green valley.""",
        
        """The old man sat by the window, watching the world go by. He
        had seen many things in his long life--wars and peace, joy and
        sorrow, love and loss. Now, in his twilight years, he found
        peace in the simple things: a cup of tea, a good book, the
        sound of rain on the roof.""",
        
        """Technology had transformed the world in ways no one could
        have imagined. The lines between human and machine blurred,
        and reality became indistinguishable from virtuality. Yet,
        amidst all this change, some things remained constant: the
        human desire for connection, the search for meaning, the
        eternal struggle between good and evil."""
    ]
    
    new_features = [extractor.extract_features(t, all_texts=all_texts) 
                   for t in new_author_samples]
    
    protonet.fit_base_model(features, all_authors)
    add_result = protonet.add_new_author("New Author", new_features)
    
    print(f"   添加成功! 样本数: {add_result['num_samples']}")
    print(f"   类内平均距离: {add_result['mean_intra_class_distance']:.4f}")
    print(f"   类间平均距离: {add_result['mean_inter_class_distance']:.4f}")
    print(f"   可分性比率: {add_result['separability_ratio']:.4f}")
    
    print("\n   使用原型网络预测测试文本:")
    proto_results = protonet.predict_with_confidence(test_features)
    print(f"   预测作者: {proto_results[0]['predicted_author']}")
    print(f"   置信度: {proto_results[0]['confidence']:.4f}")
    
    print("\n7. 时序风格漂移分析...")
    print("\n   分析 Charles Dickens 不同作品的风格漂移:")
    dickens_works = SAMPLE_TEXTS["Charles Dickens"]
    dickens_features = [extractor.extract_features(t, all_texts=all_texts) 
                       for t in dickens_works]
    
    drift_analysis = drift_analyzer.analyze_temporal_drift(
        dickens_features,
        work_titles=["A Tale of Two Cities (excerpt 1)", 
                    "A Tale of Two Cities (excerpt 2)"]
    )
    
    print(f"   总累积漂移: {drift_analysis['total_cumulative_drift']:.4f}")
    print(f"   漂移速率: {drift_analysis['drift_rate']:.4f}")
    
    print("\n   两两作品散度:")
    for pair, divs in list(drift_analysis['pairwise_divergences'].items())[:3]:
        print(f"     {pair}:")
        print(f"       JS散度: {divs['js_divergence']:.4f}")
        print(f"       KL散度: {divs['kl_divergence']:.4f}")
        print(f"       余弦不相似度: {divs['cosine_dissimilarity']:.4f}")
    
    print("\n8. 生成可视化...")
    viz_output = os.path.join(output_dir, "visualizations")
    os.makedirs(viz_output, exist_ok=True)
    
    print("\n   生成 t-SNE 聚类图...")
    tsne_path = os.path.join(viz_output, "tsne_clustering.html")
    visualizer.tsne_visualization(
        features=features,
        labels=[f"Text_{i}" for i in range(len(all_texts))],
        authors=all_authors,
        output_path=tsne_path
    )
    print(f"   已保存: {tsne_path}")
    
    print("\n   生成平行坐标图...")
    parallel_path = os.path.join(viz_output, "parallel_coordinates.html")
    visualizer.parallel_coordinates(
        features=features,
        labels=[f"Text_{i}" for i in range(len(all_texts))],
        authors=all_authors,
        output_path=parallel_path
    )
    print(f"   已保存: {parallel_path}")
    
    print("\n   生成雷达图...")
    radar_path = os.path.join(viz_output, "radar_chart.html")
    visualizer.radar_chart(
        features=features,
        labels=[f"Text_{i}" for i in range(len(all_texts))],
        authors=all_authors,
        output_path=radar_path
    )
    print(f"   已保存: {radar_path}")
    
    print("\n   生成PCA可视化...")
    pca_path = os.path.join(viz_output, "pca_visualization.html")
    visualizer.pca_visualization(
        features=features,
        labels=[f"Text_{i}" for i in range(len(all_texts))],
        authors=all_authors,
        output_path=pca_path
    )
    print(f"   已保存: {pca_path}")
    
    print("\n   生成风格漂移趋势图...")
    drift_plot_path = os.path.join(viz_output, "style_drift.html")
    visualizer.drift_trend_plot(
        drift_analysis=drift_analysis,
        output_path=drift_plot_path
    )
    print(f"   已保存: {drift_plot_path}")
    
    print("\n9. 保存模型...")
    model_dir = os.path.join(output_dir, "models")
    os.makedirs(model_dir, exist_ok=True)
    
    classifier.save(os.path.join(model_dir, "classifier.joblib"))
    protonet.save(os.path.join(model_dir, "prototypical_network.joblib"))
    print(f"   模型已保存到: {model_dir}")
    
    print("\n" + "=" * 60)
    print("10. 跨语言作者归属演示")
    print("=" * 60)
    
    print("\n   初始化跨语言分类器...")
    cross_lang_clf = CrossLanguageClassifier()
    
    print("\n   10.1 语言检测:")
    test_langs = [
        ("Hello, this is English text.", "English"),
        ("你好，这是中文文本。", "Chinese"),
        ("こんにちは、これは日本語のテキストです。", "Japanese"),
    ]
    for text, expected in test_langs:
        lang, conf = cross_lang_clf.detect_language(text)
        print(f"     {expected}: 检测为 {lang} (置信度: {conf:.4f})")
    
    print("\n   10.2 提取跨语言特征:")
    en_text = SAMPLE_TEXTS["Charles Dickens"][0]
    zh_text = MULTILINGUAL_SAMPLES["Lu Xun (Chinese)"][0]
    
    en_feat = cross_lang_clf.extract_language_agnostic_features(en_text)
    zh_feat = cross_lang_clf.extract_language_agnostic_features(zh_text)
    
    print(f"     英文特征维度: {len(en_feat)}")
    print(f"     中文特征维度: {len(zh_feat)}")
    
    from scipy.spatial.distance import cosine
    en_zh_sim = 1 - cosine(en_feat, zh_feat)
    print(f"     中英语言无关特征相似度: {en_zh_sim:.4f}")
    
    print("\n   10.3 跨语言作者验证 (仅使用手工特征):")
    print("     正在验证同一作者的不同语言文本...")
    
    en_text1 = SAMPLE_TEXTS["Charles Dickens"][0]
    en_text2 = SAMPLE_TEXTS["Charles Dickens"][1]
    
    verify_result = cross_lang_clf.cross_language_verify(en_text1, en_text2)
    print(f"     文本1语言: {verify_result['text1_language']}")
    print(f"     文本2语言: {verify_result['text2_language']}")
    print(f"     同一作者概率: {verify_result['same_author_probability']:.4f}")
    print(f"     是否判定为同一作者: {verify_result['same_author']}")
    
    print("\n" + "=" * 60)
    print("11. 角色对话分离与风格分析演示")
    print("=" * 60)
    
    print("\n   初始化角色分析器...")
    char_analyzer = CharacterStyleAnalyzer(extractor)
    
    print("\n   11.1 提取对话:")
    utterances = char_analyzer.dialogue_separator.extract_dialogues(CHARACTER_DIALOGUE_SAMPLE)
    print(f"   共提取到 {len(utterances)} 条对话")
    
    print("\n   11.2 角色分析:")
    character_profiles = char_analyzer.analyze(CHARACTER_DIALOGUE_SAMPLE)
    print(f"   识别到 {len(character_profiles)} 个角色")
    
    for name, profile in sorted(character_profiles.items(), 
                               key=lambda x: x[1].speaking_frequency, 
                               reverse=True):
        print(f"\n     角色: {name}")
        print(f"       话语数: {len(profile.utterances)}")
        print(f"       总词数: {profile.total_words}")
        print(f"       平均话语长度: {profile.avg_utterance_length:.1f} 词")
        print(f"       说话频率: {profile.speaking_frequency:.4f}")
        
        features = profile.style_features
        if features:
            print(f"       主要风格特征:")
            print(f"         - 语气词比例: {features.get('filler_ratio', 0):.4f}")
            print(f"         - 情态动词比例: {features.get('modal_ratio', 0):.4f}")
            print(f"         - 强调词比例: {features.get('intensifier_ratio', 0):.4f}")
            print(f"         - 疑问句比例: {features.get('question_ratio', 0):.4f}")
            print(f"         - 感叹句比例: {features.get('exclamation_ratio', 0):.4f}")
            print(f"         - 第一人称比例: {features.get('first_person_ratio', 0):.4f}")
            print(f"         - 第二人称比例: {features.get('second_person_ratio', 0):.4f}")
            print(f"         - 缩写词比例: {features.get('contraction_ratio', 0):.4f}")
    
    print("\n   11.3 角色风格对比 (Alice vs Tom):")
    if 'Alice' in character_profiles and 'Tom' in character_profiles:
        comparison = char_analyzer.compare_characters(
            character_profiles['Alice'],
            character_profiles['Tom']
        )
        print(f"     余弦相似度: {comparison['cosine_similarity']:.4f}")
        print(f"     欧氏距离: {comparison['euclidean_distance']:.4f}")
        print(f"\n     最大差异特征:")
        for feat, diffs in comparison.get('top_feature_diffs', {}).items():
            print(f"       {feat}: Alice={diffs['value1']:.4f}, Tom={diffs['value2']:.4f}, 差={diffs['diff']:+.4f}")
    
    print("\n   11.4 分离叙述文本:")
    narrative_text = char_analyzer.get_narrative_text(CHARACTER_DIALOGUE_SAMPLE)
    print(f"   叙述文本长度: {len(narrative_text)} 字符")
    print(f"   叙述文本预览: {narrative_text[:150]}...")
    
    print("\n" + "=" * 60)
    print("12. 叙事视角自动检测演示")
    print("=" * 60)
    
    print("\n   初始化视角检测器...")
    perspective_detector = NarrativePerspectiveDetector()
    
    perspective_cn = {
        'first_person': '第一人称',
        'second_person': '第二人称',
        'third_person_singular': '第三人称单数',
        'third_person_plural': '第三人称复数',
        'third_person_mixed': '第三人称混合',
        'third_person_singular_omniscient': '第三人称单数全知视角',
        'third_person_singular_limited': '第三人称单数有限视角',
        'third_person_singular_objective': '第三人称单数客观视角',
        'third_person_plural_omniscient': '第三人称复数全知视角',
        'third_person_plural_limited': '第三人称复数有限视角',
        'third_person_plural_objective': '第三人称复数客观视角',
        'third_person_mixed_omniscient': '第三人称混合全知视角',
        'third_person_mixed_limited': '第三人称混合有限视角',
        'third_person_mixed_objective': '第三人称混合客观视角',
        'mixed_or_unknown': '混合或未知'
    }
    
    print("\n   检测不同文本的叙事视角:")
    for persp_name, text in PERSPECTIVE_SAMPLES.items():
        narrative = char_analyzer.get_narrative_text(text)
        result = perspective_detector.detect_perspective(text, narrative)
        
        detected_persp = perspective_cn.get(result['perspective'], result['perspective'])
        expected_persp = {
            'first_person': '第一人称',
            'third_person_omniscient': '第三人称全知视角',
            'third_person_limited': '第三人称有限视角',
            'third_person_objective': '第三人称客观视角'
        }[persp_name]
        
        print(f"\n     {expected_persp} 样本:")
        print(f"       检测结果: {detected_persp}")
        print(f"       检测置信度: {result['confidence']:.4f}")
        print(f"       叙事时态: {result.get('tense', 'unknown')}")
        print(f"       时态置信度: {result.get('tense_confidence', 0):.4f}")
        print(f"       代词统计: {result.get('pronoun_counts', {})}")
        
        scores = result.get('scores', {})
        print(f"       视角得分:")
        for p, s in scores.items():
            print(f"         {p}: {s:.4f}")
        
        if 'third_person_subtype_scores' in result:
            sub_scores = result['third_person_subtype_scores']
            print(f"       第三人称子类型得分:")
            for sub, s in sub_scores.items():
                print(f"         {sub}: {s:.4f}")
    
    print("\n" + "=" * 60)
    print("13. 完整系统功能演示 - 综合分析")
    print("=" * 60)
    
    print("\n   对对话样本进行完整分析:")
    
    print("\n   13.1 叙事视角检测:")
    sample_narrative = char_analyzer.get_narrative_text(CHARACTER_DIALOGUE_SAMPLE)
    persp_result = perspective_detector.detect_perspective(
        CHARACTER_DIALOGUE_SAMPLE, sample_narrative
    )
    tense_cn = {'present': '现在时', 'past': '过去时'}
    tense = persp_result.get('tense', 'unknown')
    print(f"     视角: {perspective_cn.get(persp_result['perspective'], persp_result['perspective'])}")
    print(f"     置信度: {persp_result['confidence']:.4f}")
    print(f"     时态: {tense_cn.get(tense, tense)}")
    
    print("\n   13.2 文本元数据:")
    sample_meta = extractor.get_text_metadata(CHARACTER_DIALOGUE_SAMPLE)
    print(f"     词数: {sample_meta['word_count']}")
    print(f"     字符数: {sample_meta['char_count']}")
    print(f"     对话比例: {sample_meta['dialogue_ratio']:.4f}")
    print(f"     叙述比例: {sample_meta['narrative_ratio']:.4f}")
    print(f"     诗歌得分: {sample_meta['poetry_score']:.4f}")
    print(f"     文本类型: {'对话' if sample_meta['dialogue_ratio'] > 0.6 else '叙述' if sample_meta['narrative_ratio'] > 0.6 else '混合'}")
    
    print("\n   13.3 语言检测:")
    lang, lang_conf = cross_lang_clf.detect_language(CHARACTER_DIALOGUE_SAMPLE)
    print(f"     语言: {lang}")
    print(f"     置信度: {lang_conf:.4f}")
    
    print("\n   13.4 作者归属预测:")
    if classifier._fitted:
        sample_features = extractor.extract_features(CHARACTER_DIALOGUE_SAMPLE, all_texts=all_texts)
        sample_features = sample_features.reshape(1, -1)
        pred_results = classifier.predict_with_confidence(
            sample_features, text_metadata=[sample_meta]
        )
        pred = pred_results[0]
        print(f"     预测作者: {pred['predicted_author']}")
        print(f"     原始置信度: {pred['raw_confidence']:.4f}")
        print(f"     校准后置信度: {pred['confidence']:.4f}")
    
    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)
    print(f"\n输出目录: {os.path.abspath(output_dir)}")
    print("\n可运行的其他模式:")
    print("  python main.py --mode server --port 8000    # 启动API服务")
    print("  python main.py --mode predict --input test.txt")
    print("  python main.py --mode add_author --author-name 'My Author' --samples 1.txt 2.txt 3.txt")
    print("  python main.py --mode drift")
    print("  python main.py --mode visualize --viz-type tsne")


def predict_from_file(input_path: str, output_dir: str):
    """从文件预测作者"""
    if not os.path.exists(input_path):
        print(f"错误: 文件不存在: {input_path}")
        return
    
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    print(f"加载文本: {input_path}")
    print(f"文本长度: {len(text)} 字符")
    
    extractor = FeatureExtractor()
    
    model_path = os.path.join(output_dir, "models", "classifier.joblib")
    if os.path.exists(model_path):
        classifier = AuthorClassifier.load(model_path)
        print("加载已训练的分类器")
    else:
        print("警告: 未找到训练好的模型，请先运行 demo 模式")
        return
    
    features = extractor.extract_features(text)
    features = features.reshape(1, -1)
    
    results = classifier.predict_with_confidence(features)
    result = results[0]
    
    print("\n" + "=" * 50)
    print("预测结果")
    print("=" * 50)
    print(f"预测作者: {result['predicted_author']}")
    print(f"置信度: {result['confidence']:.4f}")
    print("\nTop 5 预测:")
    for i, pred in enumerate(result['top_predictions']):
        print(f"  {i+1}. {pred['author']}: {pred['probability']:.4f}")
    
    print("\n" + "=" * 50)
    print("风格特征向量 (前20维):")
    print("=" * 50)
    feature_names = extractor.get_feature_names()
    for i in range(min(20, len(features[0]))):
        print(f"  {feature_names[i]:30s}: {features[0][i]:.6f}")
    
    print(f"\n完整特征向量长度: {len(features[0])} 维")


def add_new_author_cli(author_name: str, sample_files: List[str], output_dir: str):
    """通过命令行添加新作者"""
    if not author_name:
        print("错误: 请指定作者名称")
        return
    
    if not sample_files or len(sample_files) < 1:
        print("错误: 请至少提供一个样本文件")
        return
    
    extractor = FeatureExtractor()
    
    model_path = os.path.join(output_dir, "models", "prototypical_network.joblib")
    if os.path.exists(model_path):
        protonet = PrototypicalNetwork.load(model_path)
        print("加载已有的原型网络")
    else:
        protonet = PrototypicalNetwork()
        print("创建新的原型网络")
    
    print(f"\n添加作者: {author_name}")
    print(f"样本文件: {sample_files}")
    
    sample_features = []
    for file_path in sample_files:
        if not os.path.exists(file_path):
            print(f"警告: 文件不存在，跳过: {file_path}")
            continue
        
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        feat = extractor.extract_features(text)
        sample_features.append(feat)
        print(f"  已加载: {file_path} ({len(text)} 字符)")
    
    if len(sample_features) < 1:
        print("错误: 没有有效样本")
        return
    
    result = protonet.add_new_author(author_name, sample_features)
    
    print("\n" + "=" * 50)
    print("添加成功!")
    print("=" * 50)
    print(f"作者名称: {result['author_name']}")
    print(f"样本数量: {result['num_samples']}")
    print(f"类内平均距离: {result['mean_intra_class_distance']:.4f}")
    print(f"类间平均距离: {result['mean_inter_class_distance']:.4f}")
    print(f"可分性比率: {result['separability_ratio']:.4f}")
    print(f"总作者数: {result['total_authors']}")
    
    os.makedirs(os.path.join(output_dir, "models"), exist_ok=True)
    protonet.save(model_path)
    print(f"\n模型已保存: {model_path}")


def run_style_drift(output_dir: str):
    """运行风格漂移分析演示"""
    print("\n" + "=" * 60)
    print("时序风格漂移分析")
    print("=" * 60)
    
    extractor = FeatureExtractor()
    drift_analyzer = StyleDriftAnalyzer(extractor)
    visualizer = StyleVisualizer(extractor)
    
    author_works = {}
    for author, texts in SAMPLE_TEXTS.items():
        if len(texts) >= 2:
            author_works[author] = texts
    
    all_features = []
    all_labels = []
    all_authors = []
    
    for author, texts in SAMPLE_TEXTS.items():
        for text in texts:
            all_features.append(text)
            all_labels.append(f"{author}_{len(all_authors)}")
            all_authors.append(author)
    
    print("\n提取特征...")
    features = extractor.extract_batch(all_features)
    
    for author, works in author_works.items():
        print(f"\n分析 {author} 的风格漂移...")
        
        work_features = [extractor.extract_features(w, all_texts=all_features) 
                        for w in works]
        
        drift_analysis = drift_analyzer.analyze_temporal_drift(
            work_features,
            work_titles=[f"Work {i+1}" for i in range(len(works))]
        )
        
        print(f"  作品数量: {len(works)}")
        print(f"  总累积漂移 (JS): {drift_analysis['total_cumulative_drift']:.4f}")
        print(f"  漂移速率: {drift_analysis['drift_rate']:.4f}")
        
        change_points = drift_analyzer.detect_style_change_points(work_features)
        if change_points:
            print(f"  检测到风格突变点: {change_points}")
    
    print("\n生成可视化...")
    viz_output = os.path.join(output_dir, "drift_analysis")
    os.makedirs(viz_output, exist_ok=True)
    
    for author, works in author_works.items():
        work_features = [extractor.extract_features(w, all_texts=all_features) 
                        for w in works]
        
        drift_analysis = drift_analyzer.analyze_temporal_drift(
            work_features,
            work_titles=[f"Work {i+1}" for i in range(len(works))]
        )
        
        drift_path = os.path.join(viz_output, f"{author}_drift.html")
        visualizer.drift_trend_plot(drift_analysis, output_path=drift_path)
        print(f"  {author}: {drift_path}")
    
    print(f"\n分析完成，结果保存在: {viz_output}")


def run_visualization(viz_type: str, output_dir: str):
    """运行可视化"""
    print("\n" + "=" * 60)
    print(f"生成可视化: {viz_type}")
    print("=" * 60)
    
    extractor = FeatureExtractor()
    visualizer = StyleVisualizer(extractor)
    
    all_texts = []
    all_authors = []
    all_labels = []
    
    for author, texts in SAMPLE_TEXTS.items():
        for i, text in enumerate(texts):
            all_texts.append(text)
            all_authors.append(author)
            all_labels.append(f"{author}_{i+1}")
    
    print(f"加载 {len(all_texts)} 篇文本，来自 {len(set(all_authors))} 位作者")
    
    print("\n提取特征...")
    features = extractor.extract_batch(all_texts)
    print(f"特征维度: {features.shape}")
    
    print(f"\n生成 {viz_type} 可视化...")
    viz_output = os.path.join(output_dir, "visualizations")
    os.makedirs(viz_output, exist_ok=True)
    
    viz_funcs = {
        'tsne': visualizer.tsne_visualization,
        'pca': visualizer.pca_visualization,
        'parallel': visualizer.parallel_coordinates,
        'radar': visualizer.radar_chart,
        'heatmap': visualizer.feature_heatmap
    }
    
    if viz_type not in viz_funcs:
        print(f"错误: 不支持的可视化类型: {viz_type}")
        return
    
    output_path = os.path.join(viz_output, f"{viz_type}_visualization.html")
    viz_funcs[viz_type](
        features=features,
        labels=all_labels,
        authors=all_authors,
        output_path=output_path
    )
    
    print(f"可视化已保存: {output_path}")


def start_server(port: int):
    """启动API服务"""
    import uvicorn
    from api import app
    
    print(f"启动API服务，端口: {port}")
    print(f"API文档: http://localhost:{port}/docs")
    print(f"API文档 (ReDoc): http://localhost:{port}/redoc")
    
    uvicorn.run(app, host="0.0.0.0", port=port)


def main():
    """主函数"""
    args = parse_args()
    
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)
    
    if args.mode == 'demo':
        run_demo(output_dir)
    elif args.mode == 'predict':
        if not args.input:
            print("错误: predict 模式需要 --input 参数")
            return
        predict_from_file(args.input, output_dir)
    elif args.mode == 'add_author':
        add_new_author_cli(args.author_name, args.samples, output_dir)
    elif args.mode == 'drift':
        run_style_drift(output_dir)
    elif args.mode == 'visualize':
        run_visualization(args.viz_type, output_dir)
    elif args.mode == 'server':
        start_server(args.port)
    elif args.mode == 'train':
        print("训练模式: 请准备好您的数据集后使用 API 接口 /train")
        print("或者运行 demo 模式查看示例训练流程")


if __name__ == "__main__":
    main()
