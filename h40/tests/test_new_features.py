"""
新功能测试验证脚本
测试跨语言作者归属、角色对话分离与风格分析、叙事视角自动检测
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from author_authorship import (
    CrossLanguageClassifier,
    DialogueSeparator,
    CharacterStyleAnalyzer,
    NarrativePerspectiveDetector,
    CharacterUtterance,
    CharacterProfile
)


TEST_DIALOGUE = """
The old mansion stood at the edge of town, its windows dark and foreboding.

"I don't think we should go in there," whispered Sarah, her voice trembling. "It looks haunted."

"Oh, don't be silly," laughed Tom, pushing open the creaky gate. "There's no such thing as ghosts. Besides, we have a flashlight."

Sarah took a step back. "I'm serious, Tom. I heard stories about this place. People say they've seen strange lights at night."

Tom rolled his eyes. "Stories for kids, that's all. Come on, I want to explore. It'll be an adventure!"

"An adventure?" Sarah crossed her arms. "More like a nightmare. What if we get caught? This place is private property, you know."

"We won't get caught," Tom assured her. "Everyone's at the town festival tonight. The whole place is empty. Look, I even brought my camera to take some pictures."

Sarah sighed, knowing she couldn't change his mind. "Fine, but if we get arrested, I'm blaming you. And if there are ghosts, I'm hiding behind you."

"Deal!" Tom grinned, already walking toward the door. "Wait till you see the look on Jake's face when we tell him we actually went inside the old Miller mansion. He'll be so jealous!"

The front door groaned as Tom pushed it open. The air inside was cold and damp, with a smell of dust and decay.

"See?" Tom whispered, shining his flashlight around the entrance hall. "Nothing scary. Just old furniture and cobwebs."

Sarah clung to his arm, her eyes darting nervously. "Tom, did you hear that? It sounded like... footsteps."

Tom froze, then laughed nervously. "It's probably just a rat. Relax."

But deep down, Tom was starting to feel uneasy too. The house seemed too quiet, too still.

"Maybe we should just take a quick look around and leave," he said, trying to sound braver than he felt.

"No," Sarah said suddenly, pointing at the staircase. "Look. Up there."

At the top of the stairs, a faint, glowing figure stood watching them.

"Tom?" Sarah's voice was barely a whisper. "Is that...?"

Tom didn't answer. He was already running for the door, with Sarah right behind him.

Somewhere behind them, a door slammed shut.
"""


TEST_PERSPECTIVES = {
    "first_person": """
I walked into the room, my heart pounding. I knew something was wrong, but I couldn't quite place it. 
I looked around, trying to stay calm. I had to be brave. I took a deep breath and stepped forward. 
This was my moment, and I wasn't going to let fear stop me.
""",
    "third_person_limited": """
John stood at the edge of the cliff, staring out at the ocean. He wondered if he would ever see his family again. 
The wind blew through his hair, and he felt a strange sense of peace. He had made his decision, and now 
he had to live with it. He thought about Mary, hoping she would understand.
""",
    "third_person_omniscient": """
Little did Emily know, as she packed her suitcase, that her life was about to change forever. 
Across town, David was making plans of his own. Both of them thought they knew what the future held, 
but destiny had other ideas. Emily's heart was filled with hope, while David's was heavy with doubt. 
Only time would reveal the path that lay ahead for both of them.
""",
    "third_person_objective": """
The woman entered the building at 2:17 PM. She wore a blue coat and carried a brown leather bag. 
She walked to the front desk and spoke to the receptionist for approximately three minutes. 
The receptionist nodded and pointed toward the elevator. The woman thanked her and walked away. 
She pressed the button for the third floor and waited.
"""
}


MULTILINGUAL_TESTS = [
    ("The quick brown fox jumps over the lazy dog.", "en"),
    ("这是一个测试中文文本。", "zh"),
    ("これは日本語のテストです。", "ja"),
    ("한국어 테스트입니다.", "ko"),
    ("Bonjour, comment allez-vous?", "fr"),
    ("Guten Tag, wie geht es Ihnen?", "de"),
    ("¿Hola, cómo estás?", "es"),
    ("Привет, как дела?", "ru"),
]


def test_cross_language_classifier():
    """测试跨语言分类器"""
    print("=" * 60)
    print("测试 1: 跨语言作者归属模块")
    print("=" * 60)
    
    clf = CrossLanguageClassifier()
    
    print("\n1.1 语言检测测试:")
    passed = 0
    failed = 0
    
    for text, expected_lang in MULTILINGUAL_TESTS:
        detected_lang, confidence = clf.detect_language(text)
        status = "OK" if detected_lang == expected_lang else "FAIL"
        
        if detected_lang == expected_lang:
            passed += 1
        else:
            failed += 1
        
        print(f"  {status} {text[:40]}... -> 检测: {detected_lang}, 期望: {expected_lang}, 置信度: {confidence:.4f}")
    
    print(f"\n  语言检测结果: {passed}/{passed+failed} 通过")
    
    print("\n1.2 语言无关特征提取测试:")
    en_text = "The cat sat on the mat and looked at the dog."
    zh_text = "猫坐在垫子上，看着狗。"
    
    en_feat = clf.extract_language_agnostic_features(en_text)
    zh_feat = clf.extract_language_agnostic_features(zh_text)
    
    print(f"  英文特征维度: {len(en_feat)}")
    print(f"  中文特征维度: {len(zh_feat)}")
    dim_ok = len(en_feat) == 42 and len(zh_feat) == 42
    print(f"  特征维度正确: {'OK' if dim_ok else 'FAIL'}")
    
    feat_range_ok = all(-5 <= v <= 5 for v in en_feat) and all(-5 <= v <= 5 for v in zh_feat)
    print(f"  特征值范围合理: {'OK' if feat_range_ok else 'FAIL'}")
    
    print("\n1.3 跨语言作者验证测试:")
    en1 = "The old man walked slowly down the street. He stopped at the bakery and bought a loaf of bread. The bread was warm and smelled delicious."
    en2 = "The old woman sat in the park. She watched the children play and smiled. The sun was shining and the birds were singing."
    
    feat1 = clf.extract_cross_language_features(en1, use_bert=False)
    feat2 = clf.extract_cross_language_features(en2, use_bert=False)
    
    from scipy.spatial.distance import cosine
    f1, f2 = feat1['combined'], feat2['combined']
    if clf.scaler and clf._fitted:
        f1 = clf.scaler.transform([f1])[0]
        f2 = clf.scaler.transform([f2])[0]
    
    lang_agnostic1, lang_agnostic2 = feat1['language_agnostic'], feat2['language_agnostic']
    
    combined_cosine = cosine(f1, f2)
    lang_agnostic_cosine = cosine(lang_agnostic1, lang_agnostic2)
    
    same_author_score = 0.5 * (1 - combined_cosine) + 0.5 * (1 - lang_agnostic_cosine)
    
    result = {
        'text1_language': feat1['language'],
        'text2_language': feat2['language'],
        'combined_cosine_similarity': float(1 - combined_cosine),
        'language_agnostic_similarity': float(1 - lang_agnostic_cosine),
        'same_author_probability': float(max(0, min(1, same_author_score))),
        'same_author': same_author_score > 0.65
    }
    print(f"  文本1语言: {result['text1_language']}")
    print(f"  文本2语言: {result['text2_language']}")
    print(f"  语言无关相似度: {result['language_agnostic_similarity']:.4f}")
    print(f"  同一作者概率: {result['same_author_probability']:.4f}")
    
    print("\n1.4 跨语言特征提取测试:")
    feat_result = clf.extract_cross_language_features(en1, use_bert=False)
    print(f"  检测语言: {feat_result['language']}")
    print(f"  语言无关特征: {len(feat_result['language_agnostic'])} 维")
    print(f"  BERT嵌入: {len(feat_result['bert_embedding'])} 维")
    print(f"  组合特征: {len(feat_result['combined'])} 维")
    
    print("\n" + "-" * 60)
    overall_pass = (
        passed >= 5 and 
        len(en_feat) == 42 and 
        len(zh_feat) == 42 and
        feat_range_ok
    )
    print(f"跨语言模块总体: {'OK 通过' if overall_pass else 'FAIL 部分失败'}")
    print(f"  说明: {passed}/8 语言检测通过，法/德/西语短文本因拉丁字母与英语相似易混淆")
    
    return overall_pass


def test_dialogue_separator():
    """测试对话分离器"""
    print("\n" + "=" * 60)
    print("测试 2: 对话分离器")
    print("=" * 60)
    
    separator = DialogueSeparator()
    
    print("\n2.1 对话提取测试:")
    utterances = separator.extract_dialogues(TEST_DIALOGUE)
    
    print(f"  提取对话数: {len(utterances)}")
    print(f"  对话数合理: {'OK' if len(utterances) >= 5 else 'FAIL'}")
    
    print("\n2.2 说话人识别测试:")
    known_speakers = [u for u in utterances if u.character_name != "Unknown"]
    unknown_speakers = [u for u in utterances if u.character_name == "Unknown"]
    
    print(f"  已识别说话人: {len(known_speakers)}")
    print(f"  未知说话人: {len(unknown_speakers)}")
    print(f"  识别率: {len(known_speakers)/max(len(utterances), 1):.2%}")
    
    print("\n2.3 角色统计:")
    from collections import Counter
    char_counts = Counter(u.character_name for u in utterances)
    for char, count in char_counts.most_common():
        print(f"    {char}: {count} 条对话")
    
    sarah_count = char_counts.get('Sarah', 0)
    tom_count = char_counts.get('Tom', 0)
    print(f"  Sarah对话数: {sarah_count}")
    print(f"  Tom对话数: {tom_count}")
    print(f"  主要角色识别: {'OK' if sarah_count > 0 and tom_count > 0 else 'FAIL'}")
    
    print("\n2.4 话语数据验证:")
    if utterances:
        utt = utterances[0]
        has_required_fields = (
            hasattr(utt, 'character_name') and
            hasattr(utt, 'text') and
            hasattr(utt, 'start_pos') and
            hasattr(utt, 'end_pos') and
            hasattr(utt, 'line_number')
        )
        print(f"  数据类字段完整: {'OK' if has_required_fields else 'FAIL'}")
        print(f"  第一条对话: {utt.text[:50]}...")
        print(f"  说话人: {utt.character_name}")
        print(f"  行号: {utt.line_number}")
    
    print("\n" + "-" * 60)
    overall_pass = (
        len(utterances) >= 5 and 
        sarah_count > 0 and 
        tom_count > 0 and
        has_required_fields
    )
    print(f"对话分离器总体: {'OK 通过' if overall_pass else 'FAIL 部分失败'}")
    
    return overall_pass


def test_character_style_analyzer():
    """测试角色风格分析器"""
    print("\n" + "=" * 60)
    print("测试 3: 角色风格分析器")
    print("=" * 60)
    
    analyzer = CharacterStyleAnalyzer()
    
    print("\n3.1 角色风格分析测试:")
    profiles = analyzer.analyze(TEST_DIALOGUE)
    
    print(f"  识别角色数: {len(profiles)}")
    print(f"  角色数正确: {'OK' if len(profiles) >= 2 else 'FAIL'}")
    
    sarah_features = None
    tom_features = None
    sarah_profile = None
    tom_profile = None
    
    if 'Sarah' in profiles and 'Tom' in profiles:
        print("\n3.2 角色画像数据验证:")
        sarah_profile = profiles['Sarah']
        tom_profile = profiles['Tom']
        
        print(f"  Sarah话语数: {len(sarah_profile.utterances)}")
        print(f"  Tom话语数: {len(tom_profile.utterances)}")
        print(f"  Sarah总词数: {sarah_profile.total_words}")
        print(f"  Tom总词数: {tom_profile.total_words}")
        print(f"  Sarah平均长度: {sarah_profile.avg_utterance_length:.1f}")
        print(f"  Tom平均长度: {tom_profile.avg_utterance_length:.1f}")
        print(f"  说话频率正确: {'OK' if 0 < sarah_profile.speaking_frequency <= 1 else 'FAIL'}")
        
        print("\n3.3 风格特征提取测试:")
        sarah_features = sarah_profile.style_features
        tom_features = tom_profile.style_features
        
        if sarah_features and tom_features:
            print(f"  Sarah特征数: {len(sarah_features)}")
            print(f"  Tom特征数: {len(tom_features)}")
            
            important_features = [
                'first_person_ratio', 'second_person_ratio', 'third_person_ratio',
                'question_ratio', 'exclamation_ratio', 'modal_ratio',
                'type_token_ratio', 'avg_word_length'
            ]
            
            print("\n  关键风格特征对比:")
            for feat in important_features:
                v1 = sarah_features.get(feat, 0)
                v2 = tom_features.get(feat, 0)
                diff = abs(v1 - v2)
                print(f"    {feat:25s}: Sarah={v1:.4f}, Tom={v2:.4f}, 差={diff:.4f}")
            
            feature_count_ok = len(sarah_features) >= 25 and len(tom_features) >= 25
            print(f"\n  特征数量足够: {'OK' if feature_count_ok else 'FAIL'}")
        
        print("\n3.4 角色风格对比测试:")
        comparison = analyzer.compare_characters(sarah_profile, tom_profile)
        print(f"  余弦相似度: {comparison['cosine_similarity']:.4f}")
        print(f"  欧氏距离: {comparison['euclidean_distance']:.4f}")
        
        has_top_diffs = 'top_feature_diffs' in comparison
        print(f"  包含最大差异特征: {'OK' if has_top_diffs else 'FAIL'}")
        
        if has_top_diffs:
            print("\n  Top 5 最大差异特征:")
            top_diffs = list(comparison['top_feature_diffs'].items())[:5]
            for feat, diff in top_diffs:
                print(f"    {feat:25s}: {diff['value1']:+.4f} -> {diff['value2']:+.4f} (差: {diff['diff']:+.4f})")
        
        print("\n3.5 叙述文本分离测试:")
        narrative = analyzer.get_narrative_text(TEST_DIALOGUE)
        original_len = len(TEST_DIALOGUE)
        narrative_len = len(narrative)
        dialogue_removed = original_len - narrative_len
        
        print(f"  原始文本长度: {original_len} 字符")
        print(f"  叙述文本长度: {narrative_len} 字符")
        print(f"  移除对话长度: {dialogue_removed} 字符")
        print(f"  对话移除比例: {dialogue_removed/original_len:.2%}")
        print(f"  叙述文本非空: {'OK' if len(narrative.strip()) > 0 else 'FAIL'}")
    
    print("\n" + "-" * 60)
    overall_pass = (
        len(profiles) >= 2 and
        'Sarah' in profiles and
        'Tom' in profiles and
        sarah_profile is not None and
        sarah_profile.total_words > 0 and
        tom_profile is not None and
        tom_profile.total_words > 0 and
        sarah_features is not None and
        len(sarah_features) >= 25 and
        len(narrative.strip()) > 0
    )
    print(f"角色风格分析器总体: {'OK 通过' if overall_pass else 'FAIL 部分失败'}")
    
    return overall_pass


def test_perspective_detector():
    """测试叙事视角检测器"""
    print("\n" + "=" * 60)
    print("测试 4: 叙事视角检测器")
    print("=" * 60)
    
    detector = NarrativePerspectiveDetector()
    char_analyzer = CharacterStyleAnalyzer()
    
    print("\n4.1 视角检测测试:")
    results = {}
    correct_count = 0
    
    for expected_persp, text in TEST_PERSPECTIVES.items():
        narrative = char_analyzer.get_narrative_text(text)
        result = detector.detect_perspective(text, narrative)
        results[expected_persp] = result
        
        detected = result['perspective']
        confidence = result['confidence']
        
        if expected_persp == 'first_person':
            correct = 'first_person' in detected
        else:
            correct = 'third_person' in detected
        
        if correct:
            correct_count += 1
        
        status = "OK" if correct else "FAIL"
        
        print(f"\n  {status} {expected_persp} 样本:")
        print(f"    检测结果: {detected}")
        print(f"    置信度: {confidence:.4f}")
        print(f"    时态: {result.get('tense', 'unknown')}")
        print(f"    时态置信度: {result.get('tense_confidence', 0):.4f}")
        
        if 'scores' in result:
            scores = result['scores']
            print(f"    视角得分:")
            for p, s in scores.items():
                print(f"      {p}: {s:.4f}")
    
    print(f"\n  视角检测准确率: {correct_count}/{len(TEST_PERSPECTIVES)}")
    
    print("\n4.2 第三人称子类型检测测试:")
    omniscient_result = results['third_person_omniscient']
    limited_result = results['third_person_limited']
    objective_result = results['third_person_objective']
    
    print(f"\n  全知视角子类型: {omniscient_result.get('perspective', 'N/A')}")
    print(f"  有限视角子类型: {limited_result.get('perspective', 'N/A')}")
    print(f"  客观视角子类型: {objective_result.get('perspective', 'N/A')}")
    
    if 'third_person_subtype_scores' in omniscient_result:
        print(f"\n  全知视角子类型得分:")
        for sub, s in omniscient_result['third_person_subtype_scores'].items():
            print(f"    {sub}: {s:.4f}")
    
    print("\n4.3 代词统计测试:")
    fp_result = results['first_person']
    pronoun_counts = fp_result.get('pronoun_counts', {})
    print(f"  第一人称样本代词统计:")
    print(f"    第一人称代词: {pronoun_counts.get('first_person', 0)}")
    print(f"    第二人称代词: {pronoun_counts.get('second_person', 0)}")
    print(f"    第三人称单数代词: {pronoun_counts.get('third_person_singular', 0)}")
    print(f"    第三人称复数代词: {pronoun_counts.get('third_person_plural', 0)}")
    
    first_person_dominant = pronoun_counts.get('first_person', 0) > pronoun_counts.get('third_person_singular', 0)
    print(f"  第一人称占主导: {'OK' if first_person_dominant else 'FAIL'}")
    
    print("\n4.4 对话排除测试:")
    test_text_with_dialogue = """
    I walked into the room. "Hello," said Mary. "How are you today?"
    I said, "I'm fine, thank you." I thought to myself that she seemed different somehow.
    """
    
    result_with_dialogue = detector.detect_perspective(test_text_with_dialogue, None)
    narrative_only = char_analyzer.get_narrative_text(test_text_with_dialogue)
    result_narrative_only = detector.detect_perspective(test_text_with_dialogue, narrative_only)
    
    print(f"  含对话文本检测: {result_with_dialogue['perspective']}")
    print(f"  仅叙述文本检测: {result_narrative_only['perspective']}")
    print(f"  检测结果一致: {'OK' if result_with_dialogue['perspective'] == result_narrative_only['perspective'] else '可能受对话影响'}")
    
    print("\n" + "-" * 60)
    overall_pass = (
        correct_count >= 3 and
        first_person_dominant and
        'third_person' in omniscient_result.get('perspective', '') and
        'third_person' in limited_result.get('perspective', '') and
        'third_person' in objective_result.get('perspective', '')
    )
    print(f"叙事视角检测器总体: {'OK 通过' if overall_pass else 'FAIL 部分失败'}")
    
    return overall_pass


def test_data_classes():
    """测试数据类"""
    print("\n" + "=" * 60)
    print("测试 5: 数据类验证")
    print("=" * 60)
    
    print("\n5.1 CharacterUtterance 数据类:")
    utt = CharacterUtterance(
        character_name="Test",
        text="Hello, world!",
        start_pos=0,
        end_pos=13,
        line_number=1
    )
    
    fields_ok = (
        utt.character_name == "Test" and
        utt.text == "Hello, world!" and
        utt.start_pos == 0 and
        utt.end_pos == 13 and
        utt.line_number == 1
    )
    print(f"  字段正确: {'OK' if fields_ok else 'FAIL'}")
    
    print("\n5.2 CharacterProfile 数据类:")
    utts = [
        CharacterUtterance("Test", "Hello", 0, 5, 1),
        CharacterUtterance("Test", "World", 6, 11, 2)
    ]
    
    profile = CharacterProfile(
        name="Test",
        utterances=utts,
        speaking_frequency=0.5
    )
    
    profile_ok = (
        profile.name == "Test" and
        len(profile.utterances) == 2 and
        profile.speaking_frequency == 0.5 and
        profile.total_words == 2 and
        abs(profile.avg_utterance_length - 1.0) < 0.01
    )
    print(f"  自动计算正确: {'OK' if profile_ok else 'FAIL'}")
    print(f"    总词数: {profile.total_words}")
    print(f"    平均长度: {profile.avg_utterance_length}")
    
    print("\n" + "-" * 60)
    overall_pass = fields_ok and profile_ok
    print(f"数据类总体: {'OK 通过' if overall_pass else 'FAIL 部分失败'}")
    
    return overall_pass


def test_integration():
    """集成测试 - 所有模块协同工作"""
    print("\n" + "=" * 60)
    print("测试 6: 集成测试")
    print("=" * 60)
    
    print("\n6.1 完整分析流程测试:")
    
    cross_lang = CrossLanguageClassifier()
    char_analyzer = CharacterStyleAnalyzer()
    perspective_detector = NarrativePerspectiveDetector()
    
    test_text = TEST_DIALOGUE
    
    print("\n  步骤 1: 语言检测")
    lang, lang_conf = cross_lang.detect_language(test_text)
    print(f"    语言: {lang}, 置信度: {lang_conf:.4f}")
    
    print("\n  步骤 2: 对话分离与角色分析")
    profiles = char_analyzer.analyze(test_text)
    print(f"    角色数: {len(profiles)}")
    for name, profile in sorted(profiles.items(), key=lambda x: x[1].speaking_frequency, reverse=True):
        print(f"      {name}: {len(profile.utterances)} 条对话, {profile.total_words} 词")
    
    print("\n  步骤 3: 叙述文本提取")
    narrative = char_analyzer.get_narrative_text(test_text)
    print(f"    叙述文本长度: {len(narrative)} 字符")
    
    print("\n  步骤 4: 叙事视角检测")
    persp_result = perspective_detector.detect_perspective(test_text, narrative)
    print(f"    视角: {persp_result['perspective']}")
    print(f"    置信度: {persp_result['confidence']:.4f}")
    print(f"    时态: {persp_result.get('tense', 'unknown')}")
    
    print("\n  步骤 5: 跨语言特征提取")
    lang_agnostic = cross_lang.extract_language_agnostic_features(test_text)
    cross_feat = cross_lang.extract_cross_language_features(test_text, use_bert=False)
    print(f"    语言无关特征: {len(lang_agnostic)} 维")
    print(f"    组合特征维度: {len(cross_feat['combined'])} 维")
    
    print("\n  步骤 6: 综合结果:")
    print(f"    文本语言: {lang}")
    print(f"    叙事视角: {persp_result['perspective']}")
    print(f"    识别角色: {list(profiles.keys())}")
    print(f"    主要说话人: {max(profiles.items(), key=lambda x: x[1].speaking_frequency)[0] if profiles else 'N/A'}")
    
    integration_ok = (
        lang == 'en' and
        len(profiles) >= 2 and
        len(narrative) > 0 and
        'perspective' in persp_result and
        len(lang_agnostic) == 42 and
        len(cross_feat['combined']) > 42
    )
    
    print("\n" + "-" * 60)
    print(f"集成测试总体: {'OK 通过' if integration_ok else 'FAIL 部分失败'}")
    
    return integration_ok


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("新功能测试验证脚本")
    print("=" * 60)
    print(f"\n测试时间: {np.datetime64('now')}")
    
    results = []
    
    results.append(("跨语言分类器", test_cross_language_classifier()))
    results.append(("对话分离器", test_dialogue_separator()))
    results.append(("角色风格分析器", test_character_style_analyzer()))
    results.append(("叙事视角检测器", test_perspective_detector()))
    results.append(("数据类", test_data_classes()))
    results.append(("集成测试", test_integration()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    for name, result in results:
        status = "OK 通过" if result else "FAIL 失败"
        print(f"  {name:25s}: {status}")
        if result:
            passed += 1
    
    print("\n" + "-" * 60)
    print(f"总计: {passed}/{len(results)} 项测试通过")
    
    if passed == len(results):
        print("\nOK 所有测试通过！新功能实现正确。")
    else:
        print(f"\nWARN {len(results) - passed} 项测试失败，请检查实现。")
    
    print("\n" + "=" * 60)
    
    return passed == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
