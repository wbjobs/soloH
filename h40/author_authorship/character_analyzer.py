"""
角色对话分离与角色风格分析模块
自动分离小说中的角色对话，分析每个角色的语言风格特征
"""

import re
import numpy as np
from typing import List, Dict, Tuple, Optional, Union
from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class CharacterUtterance:
    """角色话语数据类"""
    character_name: str
    text: str
    start_pos: int
    end_pos: int
    line_number: int
    preceding_text: str = ""
    following_text: str = ""


@dataclass
class CharacterProfile:
    """角色风格画像数据类"""
    name: str
    utterances: List[CharacterUtterance] = field(default_factory=list)
    style_features: Dict[str, float] = field(default_factory=dict)
    speaking_frequency: float = 0.0
    avg_utterance_length: float = 0.0
    total_words: int = 0
    
    def __post_init__(self):
        if self.utterances:
            self._compute_stats()
    
    def _compute_stats(self):
        """计算统计信息"""
        self.total_words = sum(len(u.text.split()) for u in self.utterances)
        self.avg_utterance_length = np.mean([len(u.text.split()) for u in self.utterances])


class DialogueSeparator:
    """对话分离器 - 从文本中提取角色对话"""
    
    QUOTE_PATTERNS = [
        r'"([^"]+)"',
        r'"([^"]+)"',
        r'`([^`]+)`',
        r"'([^']+)'",
        r"''([^']+)''",
        r'""([^"]+)"",',
    ]
    
    SPEAKER_PATTERNS = [
        r'[,;.]\s*[""]([^""]+)[""]\s*said\s+(\w+)',
        r'[,;.]\s*[""]([^""]+)[""]\s*(\w+)\s+said',
        r'(\w+)\s+said\s*[,;.]\s*[""]([^""]+)[""]',
        r'"([^"]+)"\s*,\s*said\s+(\w+)',
        r'"([^"]+)"\s*,\s*(\w+)\s+said',
        r'(\w+):\s*[""]([^""]+)[""]',
        r'[""]([^""]+)[""]\s*,\s*replied\s+(\w+)',
        r'[""]([^""]+)[""]\s*,\s*asked\s+(\w+)',
        r'[""]([^""]+)[""]\s*,\s*shouted\s+(\w+)',
    ]
    
    def __init__(self):
        """初始化对话分离器"""
        self.compiled_quote_patterns = [re.compile(p, re.DOTALL) for p in self.QUOTE_PATTERNS]
        self.compiled_speaker_patterns = [re.compile(p, re.IGNORECASE) for p in self.SPEAKER_PATTERNS]
    
    def extract_dialogues(self, text: str) -> List[CharacterUtterance]:
        """
        从文本中提取所有对话
        
        Args:
            text: 小说文本
            
        Returns:
            角色话语列表
        """
        utterances = []
        
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines):
            for pattern in self.compiled_quote_patterns:
                for match in pattern.finditer(line):
                    dialogue_text = match.group(1).strip()
                    
                    if len(dialogue_text) < 3:
                        continue
                    
                    start_pos = match.start()
                    end_pos = match.end()
                    
                    speaker = self._identify_speaker(line, dialogue_text, match)
                    
                    context_before = line[max(0, start_pos - 50):start_pos].strip()
                    context_after = line[end_pos:min(len(line), end_pos + 50)].strip()
                    
                    utterance = CharacterUtterance(
                        character_name=speaker,
                        text=dialogue_text,
                        start_pos=start_pos,
                        end_pos=end_pos,
                        line_number=line_num,
                        preceding_text=context_before,
                        following_text=context_after
                    )
                    
                    utterances.append(utterance)
        
        utterances = self._resolve_unknown_speakers(utterances, lines)
        
        return utterances
    
    def _identify_speaker(self, line: str, dialogue: str, match) -> str:
        """
        识别说话人
        
        Args:
            line: 当前行文本
            dialogue: 对话内容
            match: 匹配对象
            
        Returns:
            说话人名称（未知则返回"Unknown"）
        """
        for pattern in self.compiled_speaker_patterns:
            speaker_match = pattern.search(line)
            if speaker_match:
                if len(speaker_match.groups()) >= 2:
                    if speaker_match.group(2).isalpha() and speaker_match.group(2)[0].isupper():
                        return speaker_match.group(2)
                    elif speaker_match.group(1).isalpha() and speaker_match.group(1)[0].isupper():
                        return speaker_match.group(1)
        
        speaker_pattern = r'\b([A-Z][a-z]+)\s+(said|replied|asked|shouted|cried|whispered|muttered|screamed|called|sighed)\b'
        speaker_match = re.search(speaker_pattern, line, re.IGNORECASE)
        if speaker_match:
            return speaker_match.group(1)
        
        dash_pattern = r'^[-—]\s*[""]([^""]+)[""]\s*[-—]'
        dash_match = re.search(dash_pattern, line)
        if dash_match:
            return "Unknown"
        
        return "Unknown"
    
    def _resolve_unknown_speakers(self, utterances: List[CharacterUtterance], 
                                   lines: List[str]) -> List[CharacterUtterance]:
        """
        基于上下文解析未知说话人
        
        Args:
            utterances: 话语列表
            lines: 所有行
            
        Returns:
            更新后的话语列表
        """
        known_speakers = [u for u in utterances if u.character_name != "Unknown"]
        
        for i, utterance in enumerate(utterances):
            if utterance.character_name == "Unknown":
                if i > 0 and utterances[i-1].character_name != "Unknown":
                    if i + 1 < len(utterances) and utterances[i+1].character_name != "Unknown":
                        if utterances[i-1].line_number == utterance.line_number or \
                           abs(utterances[i-1].line_number - utterance.line_number) <= 1:
                            continue
                    
                    prev_speaker = utterances[i-1].character_name
                    next_unknown = i + 1
                    while next_unknown < len(utterances) and utterances[next_unknown].character_name == "Unknown":
                        next_unknown += 1
                    
                    if next_unknown < len(utterances):
                        next_speaker = utterances[next_unknown].character_name
                    else:
                        next_speaker = None
                    
                    if next_speaker and next_speaker != prev_speaker:
                        turn = i - list(u.character_name != "Unknown" for u in utterances[:i]).count(True)
                        if turn % 2 == 1:
                            utterance.character_name = prev_speaker
                        else:
                            utterance.character_name = next_speaker if next_speaker else prev_speaker
                    else:
                        utterance.character_name = prev_speaker
        
        return utterances


class CharacterStyleAnalyzer:
    """角色风格分析器 - 分析每个角色的语言风格"""
    
    FUNCTION_WORDS = {
        'filler': ['um', 'uh', 'er', 'ah', 'oh', 'well', 'like', 'you know', 'i mean'],
        'polite': ['please', 'thank', 'thanks', 'sorry', 'excuse', 'pardon'],
        'modal': ['can', 'could', 'may', 'might', 'shall', 'should', 'will', 'would', 'must'],
        'intensifier': ['very', 'really', 'extremely', 'absolutely', 'totally', 'completely', 'highly'],
        'swear': ['damn', 'hell', 'fuck', 'shit', 'crap', 'bastard', 'bitch'],
        'interjection': ['wow', 'oops', 'ouch', 'ah', 'oh', 'hey', 'hi', 'hello', 'bye', 'goodbye']
    }
    
    def __init__(self, feature_extractor=None):
        """
        初始化角色风格分析器
        
        Args:
            feature_extractor: 可选的特征提取器实例
        """
        self.feature_extractor = feature_extractor
        self.dialogue_separator = DialogueSeparator()
    
    def extract_character_style_features(self, utterances: List[CharacterUtterance]) -> Dict[str, float]:
        """
        提取角色语言风格特征
        
        Args:
            utterances: 该角色的话语列表
            
        Returns:
            风格特征字典
        """
        if not utterances:
            return {}
        
        all_text = ' '.join([u.text for u in utterances])
        total_words = len(all_text.split())
        
        if total_words == 0:
            return {}
        
        features = {}
        
        features['num_utterances'] = len(utterances)
        features['total_words'] = total_words
        
        utterance_lengths = [len(u.text.split()) for u in utterances]
        features['avg_utterance_length'] = float(np.mean(utterance_lengths))
        features['utterance_length_std'] = float(np.std(utterance_lengths))
        features['utterance_length_max'] = float(np.max(utterance_lengths))
        features['utterance_length_min'] = float(np.min(utterance_lengths))
        
        words = all_text.lower().split()
        word_counts = Counter(words)
        
        features['vocab_size'] = len(word_counts)
        features['type_token_ratio'] = len(word_counts) / max(total_words, 1)
        
        hapax = sum(1 for c in word_counts.values() if c == 1)
        features['hapax_legomena_ratio'] = hapax / max(total_words, 1)
        
        for category, word_list in self.FUNCTION_WORDS.items():
            count = sum(word_counts.get(w.lower(), 0) for w in word_list)
            features[f'{category}_ratio'] = count / max(total_words, 1)
        
        sentence_count = len(re.findall(r'[.!?]+', all_text))
        features['sentences_per_utterance'] = sentence_count / max(len(utterances), 1)
        
        questions = len(re.findall(r'\?', all_text))
        exclamations = len(re.findall(r'!', all_text))
        features['question_ratio'] = questions / max(sentence_count, 1)
        features['exclamation_ratio'] = exclamations / max(sentence_count, 1)
        
        contractions = len(re.findall(r"\b(can't|don't|won't|isn't|aren't|wasn't|weren't|haven't|hasn't|hadn't|wouldn't|couldn't|shouldn't|didn't|doesn't|ain't|gonna|wanna|gotta)\b", 
                                 all_text.lower()))
        features['contraction_ratio'] = contractions / max(total_words, 1)
        
        first_person = sum(1 for w in words if w.lower() in ['i', 'me', 'my', 'mine', 'myself'])
        second_person = sum(1 for w in words if w.lower() in ['you', 'your', 'yours', 'yourself', 'yourselves'])
        third_person = sum(1 for w in words if w.lower() in ['he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves'])
        
        features['first_person_ratio'] = first_person / max(total_words, 1)
        features['second_person_ratio'] = second_person / max(total_words, 1)
        features['third_person_ratio'] = third_person / max(total_words, 1)
        
        pronoun_ratio = (first_person + second_person + third_person) / max(total_words, 1)
        features['pronoun_ratio'] = pronoun_ratio
        
        avg_word_length = np.mean([len(w) for w in words])
        features['avg_word_length'] = float(avg_word_length)
        
        long_words = sum(1 for w in words if len(w) > 7)
        features['long_word_ratio'] = long_words / max(total_words, 1)
        
        short_words = sum(1 for w in words if len(w) < 3)
        features['short_word_ratio'] = short_words / max(total_words, 1)
        
        uppercase_words = sum(1 for w in all_text.split() if w.isupper() and len(w) > 1)
        features['uppercase_ratio'] = uppercase_words / max(total_words, 1)
        
        ellipsis = len(re.findall(r'\.\.\.', all_text))
        features['ellipsis_ratio'] = ellipsis / max(len(utterances), 1)
        
        pauses = len(re.findall(r'[,-]\s*$', all_text, re.MULTILINE))
        features['pause_ratio'] = pauses / max(len(utterances), 1)
        
        return features
    
    def analyze(self, text: str) -> Dict[str, CharacterProfile]:
        """
        完整分析文本中的角色对话和风格
        
        Args:
            text: 小说文本
            
        Returns:
            角色名到角色画像的映射字典
        """
        utterances = self.dialogue_separator.extract_dialogues(text)
        
        character_utterances = defaultdict(list)
        for utterance in utterances:
            character_utterances[utterance.character_name].append(utterance)
        
        total_utterances = len(utterances)
        
        character_profiles = {}
        for name, utts in character_utterances.items():
            style_features = self.extract_character_style_features(utts)
            
            profile = CharacterProfile(
                name=name,
                utterances=utts,
                style_features=style_features,
                speaking_frequency=len(utts) / max(total_utterances, 1)
            )
            
            character_profiles[name] = profile
        
        return character_profiles
    
    def compare_characters(self, profile1: CharacterProfile, 
                            profile2: CharacterProfile) -> Dict[str, float]:
        """
        比较两个角色的风格差异
        
        Args:
            profile1: 角色1画像
            profile2: 角色2画像
            
        Returns:
            差异度字典
        """
        from scipy.spatial.distance import cosine, euclidean
        
        features1 = []
        features2 = []
        
        all_keys = set(profile1.style_features.keys()) | set(profile2.style_features.keys())
        
        for key in sorted(all_keys):
            features1.append(profile1.style_features.get(key, 0))
            features2.append(profile2.style_features.get(key, 0))
        
        if not features1 or not features2:
            return {'cosine_similarity': 0, 'euclidean_distance': 0}
        
        cosine_sim = 1 - cosine(features1, features2)
        euclidean_dist = euclidean(features1, features2)
        
        feature_diffs = {}
        for key in sorted(all_keys):
            v1 = profile1.style_features.get(key, 0)
            v2 = profile2.style_features.get(key, 0)
            feature_diffs[key] = {'value1': v1, 'value2': v2, 'diff': v2 - v1}
        
        top_diffs = sorted(
            feature_diffs.items(), 
            key=lambda x: abs(x[1]['diff']), 
            reverse=True
        )[:10]
        
        return {
            'cosine_similarity': float(cosine_sim),
            'euclidean_distance': float(euclidean_dist),
            'top_feature_diffs': dict(top_diffs)
        }
    
    def get_narrative_text(self, text: str) -> str:
        """
        从文本中提取叙述部分（移除对话）
        
        Args:
            text: 原始文本
            
        Returns:
            叙述文本
        """
        utterances = self.dialogue_separator.extract_dialogues(text)
        
        narrative_parts = []
        last_end = 0
        
        sorted_utterances = sorted(utterances, key=lambda u: u.start_pos)
        
        for utterance in sorted_utterances:
            if utterance.start_pos > last_end:
                narrative_parts.append(text[last_end:utterance.start_pos])
            last_end = utterance.end_pos
        
        if last_end < len(text):
            narrative_parts.append(text[last_end:])
        
        return ' '.join(narrative_parts).strip()


class NarrativePerspectiveDetector:
    """叙事视角检测器 - 检测第一/第二/第三人称叙事"""
    
    POV_FIRST_PERSON = ['i', 'me', 'my', 'mine', 'myself', 'we', 'us', 'our', 'ours', 'ourselves']
    POV_SECOND_PERSON = ['you', 'your', 'yours', 'yourself', 'yourselves']
    POV_THIRD_PERSON_SINGULAR = ['he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself']
    POV_THIRD_PERSON_PLURAL = ['they', 'them', 'their', 'theirs', 'themselves']
    
    NARRATIVE_TENSES = {
        'present': ['am', 'is', 'are', 'do', 'does', 'have', 'has', 'go', 'goes', 'say', 'says', 'tell', 'tells'],
        'past': ['was', 'were', 'did', 'had', 'went', 'said', 'told', 'saw', 'heard', 'felt', 'knew', 'thought']
    }
    
    def __init__(self):
        """初始化叙事视角检测器"""
        pass
    
    def detect_perspective(self, text: str, 
                            narrative_text: Optional[str] = None) -> Dict[str, Union[str, float, Dict]]:
        """
        检测叙事视角
        
        Args:
            text: 完整文本
            narrative_text: 可选，已分离的叙述文本
            
        Returns:
            包含视角信息的字典
        """
        if narrative_text is None:
            separator = DialogueSeparator()
            utterances = separator.extract_dialogues(text)
            narrative_parts = []
            last_end = 0
            sorted_utterances = sorted(utterances, key=lambda u: u.start_pos)
            for utterance in sorted_utterances:
                if utterance.start_pos > last_end:
                    narrative_parts.append(text[last_end:utterance.start_pos])
                last_end = utterance.end_pos
            if last_end < len(text):
                narrative_parts.append(text[last_end:])
            narrative_text = ' '.join(narrative_parts).strip()
        
        words = narrative_text.lower().split()
        total_words = len(words)
        
        if total_words == 0:
            return {
                'perspective': 'unknown',
                'confidence': 0.0,
                'scores': {}
            }
        
        word_counts = Counter(words)
        
        first_person_count = sum(word_counts.get(w, 0) for w in self.POV_FIRST_PERSON)
        second_person_count = sum(word_counts.get(w, 0) for w in self.POV_SECOND_PERSON)
        third_person_singular_count = sum(word_counts.get(w, 0) for w in self.POV_THIRD_PERSON_SINGULAR)
        third_person_plural_count = sum(word_counts.get(w, 0) for w in self.POV_THIRD_PERSON_PLURAL)
        
        third_person_count = third_person_singular_count + third_person_plural_count
        
        total_pov = first_person_count + second_person_count + third_person_count
        
        first_person_score = first_person_count / max(total_pov, 1)
        second_person_score = second_person_count / max(total_pov, 1)
        third_person_score = third_person_count / max(total_pov, 1)
        
        first_person_instances = []
        for i, word in enumerate(words[:100]):
            if word in self.POV_FIRST_PERSON:
                context_start = max(0, i - 5)
                context_end = min(len(words), i + 6)
                context = ' '.join(words[context_start:context_end])
                if not re.search(r'[""`]', context):
                    first_person_instances.append((i, word, context))
        
        if len(first_person_instances) >= 3 and first_person_count > second_person_count and first_person_count > third_person_singular_count:
            first_person_score *= 1.3
        elif first_person_count < 5 and third_person_singular_count > first_person_count * 2:
            first_person_score *= 0.5
        
        scores = {
            'first_person': float(first_person_score),
            'second_person': float(second_person_score),
            'third_person': float(third_person_score)
        }
        
        if third_person_score > first_person_score and third_person_score > second_person_score:
            if third_person_singular_count > third_person_plural_count * 2:
                perspective = 'third_person_singular'
            elif third_person_plural_count > third_person_singular_count * 2:
                perspective = 'third_person_plural'
            else:
                perspective = 'third_person_mixed'
        elif first_person_score > second_person_score and first_person_score > third_person_score:
            perspective = 'first_person'
        elif second_person_score > first_person_score and second_person_score > third_person_score:
            perspective = 'second_person'
        else:
            perspective = 'mixed_or_unknown'
        
        max_score = max(scores.values())
        second_max = sorted(scores.values())[-2]
        confidence = max_score - second_max
        
        if perspective in ['third_person_singular', 'third_person_plural', 'third_person_mixed']:
            sub_scores = {
                'omniscient': 0.0,
                'limited': 0.0,
                'objective': 0.0
            }
            
            thoughts = len(re.findall(r'\b(thought|knew|felt|wondered|realized|understood|believed|hoped|feared)\w*\b', narrative_text, re.IGNORECASE))
            if thoughts > 5:
                sub_scores['omniscient'] += 0.3
                sub_scores['limited'] += 0.5
            
            character_names = re.findall(r'\b([A-Z][a-z]+)\b', narrative_text)
            char_counter = Counter(character_names)
            main_chars = char_counter.most_common(5)
            if main_chars and main_chars[0][1] > sum(c[1] for c in main_chars[1:]) * 0.5:
                sub_scores['limited'] += 0.4
                sub_scores['omniscient'] -= 0.2
            
            actions = len(re.findall(r'\b(walk|run|jump|sit|stand|eat|drink|say|tell|ask|reply|answer|look|see|hear)\w*\b', narrative_text, re.IGNORECASE))
            if actions > thoughts * 2:
                sub_scores['objective'] += 0.6
            
            sub_perspective = max(sub_scores.items(), key=lambda x: x[1])
            perspective = f"{perspective}_{sub_perspective[0]}"
            confidence = (confidence + sub_scores[sub_perspective[0]]) / 2
        
        present_tense = sum(word_counts.get(w, 0) for w in self.NARRATIVE_TENSES['present'])
        past_tense = sum(word_counts.get(w, 0) for w in self.NARRATIVE_TENSES['past'])
        
        tense = 'present' if present_tense > past_tense else 'past'
        tense_confidence = abs(present_tense - past_tense) / max(present_tense + past_tense, 1)
        
        result = {
            'perspective': perspective,
            'confidence': float(min(confidence, 1.0)),
            'scores': scores,
            'pronoun_counts': {
                'first_person': first_person_count,
                'second_person': second_person_count,
                'third_person_singular': third_person_singular_count,
                'third_person_plural': third_person_plural_count
            },
            'tense': tense,
            'tense_confidence': float(min(tense_confidence, 1.0)),
            'narrative_word_count': total_words
        }
        
        if 'sub_scores' in locals():
            result['third_person_subtype_scores'] = sub_scores
        
        return result
