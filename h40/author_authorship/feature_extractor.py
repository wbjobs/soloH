"""
风格特征提取模块
提取句长分布、词汇丰富度、功能词频率、n-gram、标点模式等特征
"""

import re
import string
import numpy as np
import spacy
from collections import Counter
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from typing import List, Dict, Tuple, Optional


class FeatureExtractor:
    """
    文本风格特征提取器
    
    提取的特征类别:
    1. 句长分布特征 (14维)
    2. 词汇丰富度特征 (8维)
    3. 功能词频率特征 (100维)
    4. 标点模式特征 (20维)
    5. 字符n-gram特征 (200维)
    总计: 342维
    """

    FUNCTION_WORDS = [
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
        'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'shall', 'can', 'must', 'ought', 'i', 'you',
        'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
        'my', 'your', 'his', 'its', 'our', 'their', 'this', 'that', 'these', 'those',
        'who', 'whom', 'whose', 'which', 'what', 'where', 'when', 'why', 'how', 'all',
        'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
        'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
        'because', 'as', 'until', 'while', 'although', 'though', 'if', 'then', 'else', 'also'
    ]

    PUNCTUATION_LIST = list(string.punctuation) + ['...', '!!', '??', '?!', '!?']

    def __init__(self, spacy_model: str = 'en_core_web_sm'):
        """
        初始化特征提取器
        
        Args:
            spacy_model: spaCy模型名称
        """
        try:
            self.nlp = spacy.load(spacy_model)
        except OSError:
            self.nlp = spacy.load('en_core_web_sm')
        
        self.char_vectorizer = TfidfVectorizer(
            analyzer='char',
            ngram_range=(2, 4),
            max_features=200,
            lowercase=True
        )
        
        self._fitted = False
        self.feature_names = self._build_feature_names()

    def _build_feature_names(self) -> List[str]:
        """构建特征名称列表"""
        names = []
        
        names.extend([
            'sent_len_mean', 'sent_len_median', 'sent_len_std',
            'sent_len_min', 'sent_len_max',
            'sent_len_q25', 'sent_len_q75', 'sent_len_q90',
            'sent_len_skew', 'sent_len_kurt',
            'short_sent_ratio', 'long_sent_ratio',
            'avg_words_per_sent', 'avg_chars_per_word'
        ])
        
        names.extend([
            'dialogue_ratio', 'narrative_ratio',
            'text_type_confidence'
        ])
        
        names.extend([
            'type_token_ratio', 'type_token_ratio_cond',
            'hapax_legomena_ratio', 'hapax_legomena_ratio_cond',
            'dis_legomena_ratio', 'yules_k', 'yules_k_cond',
            'honores_r', 'simpsons_d',
            'brunets_w', 'vocab_size', 'vocab_size_per_1000'
        ])
        
        names.extend([
            'genre_poetry_score', 'genre_prose_score',
            'line_length_mean', 'stanza_count',
            'rhyme_density', 'rhythm_regularity'
        ])
        
        for word in self.FUNCTION_WORDS:
            names.append(f'func_{word}')
        
        for punct in self.PUNCTUATION_LIST:
            names.append(f'punct_{punct}')
        
        for i in range(200):
            names.append(f'char_ngram_{i}')
        
        return names

    def _sentence_length_features(self, doc) -> np.ndarray:
        """提取句长分布特征"""
        sent_lengths = [len(sent) for sent in doc.sents if len(sent) > 0]
        
        if not sent_lengths:
            return np.zeros(14)
        
        lengths = np.array(sent_lengths)
        n = len(lengths)
        
        mean = np.mean(lengths)
        median = np.median(lengths)
        std = np.std(lengths)
        min_len = np.min(lengths)
        max_len = np.max(lengths)
        q25 = np.percentile(lengths, 25)
        q75 = np.percentile(lengths, 75)
        q90 = np.percentile(lengths, 90)
        
        skew = np.mean(((lengths - mean) ** 3)) / (std ** 3) if std > 0 else 0
        kurt = np.mean(((lengths - mean) ** 4)) / (std ** 4) - 3 if std > 0 else 0
        
        short_ratio = np.sum(lengths < 10) / n
        long_ratio = np.sum(lengths > 30) / n
        
        total_words = sum(1 for token in doc if not token.is_punct and not token.is_space)
        total_chars = sum(len(token.text) for token in doc if not token.is_punct and not token.is_space)
        avg_words = total_words / max(n, 1)
        avg_chars = total_chars / max(total_words, 1)
        
        return np.array([
            mean, median, std, min_len, max_len,
            q25, q75, q90, skew, kurt,
            short_ratio, long_ratio, avg_words, avg_chars
        ])

    def _lexical_richness_features(self, doc) -> np.ndarray:
        """提取词汇丰富度特征"""
        words = [token.text.lower() for token in doc 
                if not token.is_punct and not token.is_space and not token.is_stop]
        
        if not words:
            return np.zeros(8)
        
        word_counts = Counter(words)
        n = len(words)
        v = len(word_counts)
        
        type_token_ratio = v / n
        
        hapax = sum(1 for count in word_counts.values() if count == 1)
        hapax_ratio = hapax / n
        
        dis = sum(1 for count in word_counts.values() if count == 2)
        dis_ratio = dis / n
        
        m1 = hapax
        m2 = sum(count * (count - 1) for count in word_counts.values())
        yules_k = 10000 * (m2 - m1 + n) / (n * n) if n > 0 else 0
        
        honores_r = 100 * hapax * hapax / (2 * dis * n) if dis > 0 else 0
        
        simpsons_d = 1 - sum(count * (count - 1) for count in word_counts.values()) / (n * (n - 1)) if n > 1 else 0
        
        brunets_w = (v - 1) / np.log(n) if n > 1 else 0
        
        vocab_size = v
        
        return np.array([
            type_token_ratio, hapax_ratio, dis_ratio, yules_k,
            honores_r, simpsons_d, brunets_w, vocab_size
        ])

    def _function_word_features(self, doc) -> np.ndarray:
        """提取功能词频率特征"""
        words = [token.text.lower() for token in doc if not token.is_space]
        total_words = len(words)
        
        if total_words == 0:
            return np.zeros(len(self.FUNCTION_WORDS))
        
        word_counts = Counter(words)
        features = np.array([
            word_counts.get(word, 0) / total_words
            for word in self.FUNCTION_WORDS
        ])
        
        return features

    def _detect_text_type(self, doc) -> Tuple[float, float, float]:
        """
        检测文本类型：对话 vs 叙述
        
        Returns:
            (dialogue_ratio, narrative_ratio, confidence)
        """
        text = doc.text
        total_sents = len(list(doc.sents))
        
        if total_sents == 0:
            return 0.5, 0.5, 0.0
        
        dialogue_markers = 0
        dialogue_quotes = len(re.findall(r'[""''`]', text))
        short_sents = sum(1 for sent in doc.sents if len(sent) < 10)
        first_person_pronouns = sum(1 for token in doc 
                                    if token.text.lower() in ['i', 'me', 'my', 'mine', 'you', 'your', 'yours'])
        
        avg_sent_len = np.mean([len(sent) for sent in doc.sents if len(sent) > 0])
        
        dialogue_score = (
            0.4 * min(dialogue_quotes / max(total_sents, 1) / 4, 1.0) +
            0.3 * min(short_sents / max(total_sents, 1), 1.0) +
            0.2 * min(first_person_pronouns / max(total_sents * 3, 1), 1.0) +
            0.1 * max(0, 1 - avg_sent_len / 25)
        )
        
        dialogue_score = max(0.0, min(1.0, dialogue_score))
        narrative_score = 1.0 - dialogue_score
        
        if avg_sent_len < 8 or avg_sent_len > 30:
            confidence = 0.8
        elif 12 <= avg_sent_len <= 20:
            confidence = 0.5
        else:
            confidence = 0.6
        
        return dialogue_score, narrative_score, confidence

    def _detect_genre(self, doc) -> Dict[str, float]:
        """
        检测文本体裁：诗歌 vs 散文
        
        Returns:
            包含体裁分数和韵律特征的字典
        """
        text = doc.text
        lines = text.split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        
        if len(lines) == 0:
            return {
                'poetry_score': 0.0,
                'prose_score': 1.0,
                'line_length_mean': 0.0,
                'stanza_count': 0.0,
                'rhyme_density': 0.0,
                'rhythm_regularity': 0.0
            }
        
        line_lengths = [len(line.split()) for line in lines]
        line_length_mean = np.mean(line_lengths) if line_lengths else 0
        line_length_std = np.std(line_lengths) if len(line_lengths) > 1 else 0
        
        short_lines = sum(1 for l in line_lengths if l <= 10)
        line_length_variation = line_length_std / (line_length_mean + 1e-10)
        
        stanza_breaks = len(re.findall(r'\n\s*\n', text))
        stanza_count = stanza_breaks + 1
        
        words = [token.text.lower() for token in doc 
                if not token.is_punct and not token.is_space]
        
        rhyme_density = 0.0
        if len(words) >= 10:
            last_words = []
            for line in lines:
                line_words = line.split()
                if line_words:
                    last_word = re.sub(r'[^a-zA-Z]', '', line_words[-1].lower())
                    if len(last_word) >= 2:
                        last_words.append(last_word)
            
            if len(last_words) >= 4:
                rhymes = 0
                for i in range(len(last_words) - 1):
                    for j in range(i + 1, min(i + 3, len(last_words))):
                        if last_words[i][-3:] == last_words[j][-3:] and last_words[i] != last_words[j]:
                            rhymes += 1
                rhyme_density = rhymes / max(len(last_words), 1)
        
        rhythm_regularity = 0.0
        if len(line_lengths) >= 4:
            rhythm_regularity = max(0, 1 - line_length_variation)
        
        poetry_score = (
            0.35 * min(short_lines / max(len(lines), 1), 1.0) +
            0.25 * min(line_length_mean / 30, 1.0) if line_length_mean <= 30 else 0.25 * max(0, 1 - (line_length_mean - 30) / 30) +
            0.2 * min(stanza_count / 5, 1.0) +
            0.1 * min(rhyme_density * 5, 1.0) +
            0.1 * rhythm_regularity
        )
        
        poetry_score = max(0.0, min(1.0, poetry_score))
        prose_score = 1.0 - poetry_score
        
        return {
            'poetry_score': poetry_score,
            'prose_score': prose_score,
            'line_length_mean': float(line_length_mean / 100),
            'stanza_count': float(min(stanza_count / 20, 1.0)),
            'rhyme_density': float(rhyme_density),
            'rhythm_regularity': float(rhythm_regularity)
        }

    def _lexical_richness_features(self, doc, 
                                    dialogue_ratio: float = 0.5,
                                    narrative_ratio: float = 0.5) -> np.ndarray:
        """提取词汇丰富度特征（支持条件归一化）"""
        words = [token.text.lower() for token in doc 
                if not token.is_punct and not token.is_space and not token.is_stop]
        
        if not words:
            return np.zeros(12)
        
        word_counts = Counter(words)
        n = len(words)
        v = len(word_counts)
        
        type_token_ratio = v / n
        
        hapax = sum(1 for count in word_counts.values() if count == 1)
        hapax_ratio = hapax / n
        
        dis = sum(1 for count in word_counts.values() if count == 2)
        dis_ratio = dis / n
        
        m1 = hapax
        m2 = sum(count * (count - 1) for count in word_counts.values())
        yules_k = 10000 * (m2 - m1 + n) / (n * n) if n > 0 else 0
        
        honores_r = 100 * hapax * hapax / (2 * dis * n) if dis > 0 else 0
        
        simpsons_d = 1 - sum(count * (count - 1) for count in word_counts.values()) / (n * (n - 1)) if n > 1 else 0
        
        brunets_w = (v - 1) / np.log(n) if n > 1 else 0
        
        vocab_size = v
        vocab_size_per_1000 = v * 1000 / max(n, 1)
        
        dialogue_correction_factor = 1.0 + 0.3 * (narrative_ratio - 0.5)
        type_token_ratio_cond = type_token_ratio * dialogue_correction_factor
        type_token_ratio_cond = max(0.0, min(1.0, type_token_ratio_cond))
        
        hapax_ratio_cond = hapax_ratio * dialogue_correction_factor
        hapax_ratio_cond = max(0.0, min(1.0, hapax_ratio_cond))
        
        yules_k_cond = yules_k / dialogue_correction_factor
        
        return np.array([
            type_token_ratio, type_token_ratio_cond,
            hapax_ratio, hapax_ratio_cond,
            dis_ratio, yules_k, yules_k_cond,
            honores_r, simpsons_d,
            brunets_w, vocab_size, vocab_size_per_1000
        ])

    def _function_word_features(self, doc, 
                                 poetry_score: float = 0.0,
                                 prose_score: float = 1.0) -> np.ndarray:
        """提取功能词频率特征（体裁感知权重）"""
        words = [token.text.lower() for token in doc if not token.is_space]
        total_words = len(words)
        
        if total_words == 0:
            return np.zeros(len(self.FUNCTION_WORDS))
        
        word_counts = Counter(words)
        
        genre_weight = prose_score + 0.3 * poetry_score
        
        features = []
        for word in self.FUNCTION_WORDS:
            raw_freq = word_counts.get(word, 0) / total_words
            
            if poetry_score > 0.5:
                if word in ['the', 'a', 'an', 'is', 'are', 'was', 'were']:
                    weight = 0.3 + 0.7 * prose_score
                elif word in ['i', 'you', 'he', 'she', 'we', 'they', 'me', 'him', 'her']:
                    weight = 0.6 + 0.4 * prose_score
                else:
                    weight = 0.8 + 0.2 * prose_score
            else:
                weight = 1.0
            
            weighted_freq = raw_freq * weight
            features.append(weighted_freq)
        
        return np.array(features)

    def _punctuation_features(self, doc) -> np.ndarray:
        """提取标点模式特征"""
        text = doc.text
        total_chars = len(text)
        
        if total_chars == 0:
            return np.zeros(len(self.PUNCTUATION_LIST))
        
        features = []
        for punct in self.PUNCTUATION_LIST:
            count = len(re.findall(re.escape(punct), text))
            features.append(count / total_chars)
        
        return np.array(features)

    def _char_ngram_features(self, texts: List[str]) -> np.ndarray:
        """提取字符n-gram特征"""
        if not self._fitted:
            self.char_vectorizer.fit(texts)
            self._fitted = True
        
        return self.char_vectorizer.transform(texts).toarray()

    def extract_features(self, text: str, all_texts: Optional[List[str]] = None) -> np.ndarray:
        """
        提取单篇文本的完整特征向量
        
        Args:
            text: 输入文本
            all_texts: 所有文本列表（用于拟合n-gram特征）
            
        Returns:
            特征向量
        """
        doc = self.nlp(text)
        
        sent_features = self._sentence_length_features(doc)
        
        dialogue_ratio, narrative_ratio, text_type_conf = self._detect_text_type(doc)
        text_type_features = np.array([dialogue_ratio, narrative_ratio, text_type_conf])
        
        lexical_features = self._lexical_richness_features(
            doc, dialogue_ratio=dialogue_ratio, narrative_ratio=narrative_ratio
        )
        
        genre_info = self._detect_genre(doc)
        genre_features = np.array([
            genre_info['poetry_score'],
            genre_info['prose_score'],
            genre_info['line_length_mean'],
            genre_info['stanza_count'],
            genre_info['rhyme_density'],
            genre_info['rhythm_regularity']
        ])
        
        func_features = self._function_word_features(
            doc, poetry_score=genre_info['poetry_score'], 
            prose_score=genre_info['prose_score']
        )
        punct_features = self._punctuation_features(doc)
        
        if all_texts is None:
            all_texts = [text]
        
        if not self._fitted:
            self._char_ngram_features(all_texts)
        
        ngram_features = self._char_ngram_features([text])[0]
        
        return np.concatenate([
            sent_features,
            text_type_features,
            lexical_features,
            genre_features,
            func_features,
            punct_features,
            ngram_features
        ])
    
    def get_text_metadata(self, text: str) -> Dict[str, float]:
        """
        获取文本元数据（用于置信度校正）
        
        Args:
            text: 输入文本
            
        Returns:
            包含文本长度、对话比例、体裁分数等元数据
        """
        doc = self.nlp(text)
        word_count = sum(1 for token in doc if not token.is_punct and not token.is_space)
        char_count = len(text)
        sent_count = len(list(doc.sents))
        
        dialogue_ratio, narrative_ratio, text_type_conf = self._detect_text_type(doc)
        genre_info = self._detect_genre(doc)
        
        return {
            'word_count': word_count,
            'char_count': char_count,
            'sent_count': sent_count,
            'dialogue_ratio': dialogue_ratio,
            'narrative_ratio': narrative_ratio,
            'text_type_confidence': text_type_conf,
            'poetry_score': genre_info['poetry_score'],
            'prose_score': genre_info['prose_score'],
            'is_poetry': genre_info['poetry_score'] > 0.5
        }

    def extract_batch(self, texts: List[str]) -> np.ndarray:
        """
        批量提取特征
        
        Args:
            texts: 文本列表
            
        Returns:
            特征矩阵 (n_samples, n_features)
        """
        self._fitted = False
        self._char_ngram_features(texts)
        
        features = []
        for text in texts:
            feat = self.extract_features(text, all_texts=texts)
            features.append(feat)
        
        return np.array(features)

    def get_feature_names(self) -> List[str]:
        """获取特征名称列表"""
        return self.feature_names

    def get_feature_groups(self) -> Dict[str, List[str]]:
        """获取特征分组信息"""
        return {
            'sentence_length': self.feature_names[:14],
            'text_type': self.feature_names[14:17],
            'lexical_richness': self.feature_names[17:29],
            'genre_features': self.feature_names[29:35],
            'function_words': self.feature_names[35:135],
            'punctuation': self.feature_names[135:172],
            'char_ngram': self.feature_names[172:]
        }
    
    def get_feature_dim(self) -> int:
        """获取特征维度"""
        return len(self.feature_names)
