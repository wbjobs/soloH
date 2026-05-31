"""
跨语言作者归属模块
使用多语言BERT进行跨语言文本风格特征提取

支持语言:
- 中文 (zh)
- 英文 (en)
- 日文 (ja)
- 韩文 (ko)
- 法文 (fr)
- 德文 (de)
- 西班牙文 (es)
- 俄文 (ru)
"""

import re
import numpy as np
from typing import List, Dict, Tuple, Optional, Union
from collections import Counter
import warnings


class CrossLanguageClassifier:
    """
    跨语言作者归属分类器
    
    使用多语言BERT嵌入 + 通用语言无关特征
    支持在不同语言之间进行作者归属判断
    """

    LANGUAGES = {
        'zh': 'Chinese',
        'en': 'English', 
        'ja': 'Japanese',
        'ko': 'Korean',
        'fr': 'French',
        'de': 'German',
        'es': 'Spanish',
        'ru': 'Russian',
        'other': 'Other'
    }

    UNIVERSAL_PUNCTUATION = [
        '.', ',', '!', '?', ';', ':', '-', '"', "'", '(', ')',
        '[', ']', '{', '}', '/', '\\', '@', '#', '$', '%', '&', '*', '+'
    ]

    def __init__(self, 
                 bert_model_name: str = 'distiluse-base-multilingual-cased-v2',
                 embedding_dim: int = 512):
        """
        初始化跨语言分类器
        
        Args:
            bert_model_name: 多语言BERT模型名称
            embedding_dim: 嵌入维度
        """
        self.bert_model_name = bert_model_name
        self.embedding_dim = embedding_dim
        self._bert_model = None
        self._bert_tokenizer = None
        self._bert_loaded = False
        
        self.author_prototypes = {}
        self.language_stats = {}
        self._fitted = False
        
        self.scaler = None
        try:
            from sklearn.preprocessing import StandardScaler
            self.scaler = StandardScaler()
        except ImportError:
            pass

    def _load_bert_model(self):
        """
        懒加载多语言BERT模型
        优先使用sentence-transformers，其次使用transformers
        """
        if self._bert_loaded:
            return True
        
        try:
            from sentence_transformers import SentenceTransformer
            self._bert_model = SentenceTransformer(self.bert_model_name)
            self._bert_tokenizer = None
            self._bert_loaded = True
            return True
        except ImportError:
            warnings.warn("sentence-transformers not available, trying transformers...")
        
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            
            model_name = 'distilbert-base-multilingual-cased'
            self._bert_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._bert_model = AutoModel.from_pretrained(model_name)
            self._bert_loaded = True
            return True
        except ImportError:
            warnings.warn(
                "Neither sentence-transformers nor transformers available. "
                "Falling back to language-agnostic handcrafted features only."
            )
            self._bert_loaded = False
            return False

    def detect_language(self, text: str) -> Tuple[str, float]:
        """
        检测文本语言
        
        Args:
            text: 输入文本
            
        Returns:
            (language_code, confidence)
        """
        if not text.strip():
            return 'other', 0.0
        
        zh_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        ja_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
        ko_chars = len(re.findall(r'[\uac00-\ud7af]', text))
        ru_chars = len(re.findall(r'[\u0400-\u04ff]', text))
        
        en_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        fr_words = len(re.findall(r'\b(le|la|les|de|des|du|et|ou|mais|donc|or)\b', 
                                 text.lower()))
        de_words = len(re.findall(r'\b(der|die|das|und|oder|aber|denn|wenn|dann|ist)\b',
                                 text.lower()))
        es_words = len(re.findall(r'\b(el|la|los|las|de|y|o|pero|porque|es|en)\b',
                                 text.lower()))
        
        total_chars = len(text.replace(' ', ''))
        scores = {}
        
        if zh_chars > 0:
            scores['zh'] = zh_chars / max(total_chars, 1)
        if ja_chars > 0:
            scores['ja'] = ja_chars / max(total_chars, 1)
        if ko_chars > 0:
            scores['ko'] = ko_chars / max(total_chars, 1)
        if ru_chars > 0:
            scores['ru'] = ru_chars / max(total_chars, 1)
        
        if en_words > 0 and not scores:
            scores['en'] = min(en_words / 100, 1.0)
        if fr_words > 0 and not scores.get('en', 0) > fr_words:
            scores['fr'] = min(fr_words / 50, 1.0)
        if de_words > 0:
            scores['de'] = min(de_words / 50, 1.0)
        if es_words > 0:
            scores['es'] = min(es_words / 50, 1.0)
        
        if not scores:
            return 'other', 0.3
        
        lang = max(scores.items(), key=lambda x: x[1])
        return lang[0], min(lang[1], 1.0)

    def get_bert_embedding(self, text: str, 
                           max_length: int = 512) -> np.ndarray:
        """
        获取多语言BERT嵌入
        
        Args:
            text: 输入文本
            max_length: 最大序列长度
            
        Returns:
            BERT嵌入向量
        """
        if not self._bert_loaded:
            loaded = self._load_bert_model()
            if not loaded:
                return np.zeros(self.embedding_dim)
        
        try:
            if self._bert_tokenizer is None:
                embedding = self._bert_model.encode(
                    text, 
                    show_progress_bar=False,
                    convert_to_numpy=True
                )
                if len(embedding) > self.embedding_dim:
                    embedding = embedding[:self.embedding_dim]
                elif len(embedding) < self.embedding_dim:
                    padding = np.zeros(self.embedding_dim - len(embedding))
                    embedding = np.concatenate([embedding, padding])
                return embedding
            else:
                import torch
                
                inputs = self._bert_tokenizer(
                    text,
                    max_length=max_length,
                    truncation=True,
                    padding='max_length',
                    return_tensors='pt'
                )
                
                with torch.no_grad():
                    outputs = self._bert_model(**inputs)
                
                cls_embedding = outputs.last_hidden_state[:, 0, :].numpy()[0]
                
                if len(cls_embedding) > self.embedding_dim:
                    cls_embedding = cls_embedding[:self.embedding_dim]
                elif len(cls_embedding) < self.embedding_dim:
                    padding = np.zeros(self.embedding_dim - len(cls_embedding))
                    cls_embedding = np.concatenate([cls_embedding, padding])
                
                return cls_embedding
                
        except Exception as e:
            warnings.warn(f"BERT embedding failed: {e}")
            return np.zeros(self.embedding_dim)

    def extract_language_agnostic_features(self, text: str) -> np.ndarray:
        """
        提取语言无关的通用风格特征
        
        Args:
            text: 输入文本
            
        Returns:
            语言无关特征向量 (42维)
        """
        if not text.strip():
            return np.zeros(42)
        
        chars = list(text)
        total_chars = len(chars)
        total_words = len(re.findall(r'\S+', text))
        
        char_counts = Counter(chars)
        char_types = len(char_counts)
        
        char_type_ratio = char_types / max(total_chars, 1)
        
        whitespace_ratio = text.count(' ') / max(total_chars, 1)
        
        uppercase_ratio = sum(1 for c in chars if c.isupper()) / max(total_chars, 1)
        lowercase_ratio = sum(1 for c in chars if c.islower()) / max(total_chars, 1)
        digit_ratio = sum(1 for c in chars if c.isdigit()) / max(total_chars, 1)
        
        punct_features = []
        for punct in self.UNIVERSAL_PUNCTUATION:
            count = text.count(punct)
            punct_features.append(count / max(total_chars, 1))
        
        sentence_ends = len(re.findall(r'[.!?。！？]', text))
        avg_sentence_length = total_words / max(sentence_ends, 1)
        
        line_breaks = text.count('\n')
        avg_line_length = total_chars / max(line_breaks + 1, 1)
        
        space_patterns = len(re.findall(r'  +', text)) / max(total_chars, 1)
        
        char_bigrams = Counter(zip(chars[:-1], chars[1:]))
        bigram_types = len(char_bigrams)
        bigram_ratio = bigram_types / max(total_chars, 1)
        
        digit_sequences = len(re.findall(r'\d+', text)) / max(total_words, 1)
        
        special_symbols = len(re.findall(r'[^\w\s' + re.escape(''.join(self.UNIVERSAL_PUNCTUATION)) + ']', 
                                        text)) / max(total_chars, 1)
        
        avg_word_length = total_chars / max(total_words, 1)
        
        word_lengths = [len(w) for w in re.findall(r'\S+', text)]
        word_length_std = np.std(word_lengths) if word_lengths else 0
        
        unique_words = len(set(re.findall(r'\S+', text)))
        word_type_ratio = unique_words / max(total_words, 1)
        
        features = np.concatenate([
            [
                char_type_ratio,
                whitespace_ratio,
                uppercase_ratio,
                lowercase_ratio,
                digit_ratio,
                avg_sentence_length / 100,
                avg_line_length / 100,
                space_patterns,
                bigram_ratio,
                digit_sequences,
                special_symbols,
                avg_word_length / 20,
                word_length_std / 10,
                word_type_ratio,
                total_words / 1000,
                total_chars / 5000
            ],
            punct_features,
            [
                sentence_ends / max(total_words, 1),
                line_breaks / max(total_chars, 1)
            ]
        ])
        
        return features

    def extract_cross_language_features(self, text: str,
                                         use_bert: bool = True) -> Dict[str, np.ndarray]:
        """
        提取完整的跨语言特征
        
        Args:
            text: 输入文本
            use_bert: 是否使用BERT嵌入
            
        Returns:
            包含不同类型特征的字典
        """
        lang, lang_conf = self.detect_language(text)
        
        language_agnostic = self.extract_language_agnostic_features(text)
        
        bert_embedding = self.get_bert_embedding(text) if use_bert else np.zeros(self.embedding_dim)
        
        lang_onehot = np.zeros(len(self.LANGUAGES))
        lang_idx = list(self.LANGUAGES.keys()).index(lang) if lang in self.LANGUAGES else -1
        if lang_idx >= 0:
            lang_onehot[lang_idx] = 1
        
        combined = np.concatenate([
            language_agnostic,
            bert_embedding,
            lang_onehot,
            [lang_conf]
        ])
        
        return {
            'language': lang,
            'language_confidence': lang_conf,
            'language_agnostic': language_agnostic,
            'bert_embedding': bert_embedding,
            'language_onehot': lang_onehot,
            'combined': combined
        }

    def fit(self, texts: List[str], authors: List[str], 
            languages: Optional[List[str]] = None):
        """
        训练跨语言分类器
        
        Args:
            texts: 文本列表（可跨语言）
            authors: 作者标签列表
            languages: 可选，文本语言列表
        """
        if languages is None:
            languages = []
            for text in texts:
                lang, _ = self.detect_language(text)
                languages.append(lang)
        
        features_list = []
        for text in texts:
            feat = self.extract_cross_language_features(text)
            features_list.append(feat['combined'])
        
        features_matrix = np.array(features_list)
        
        if self.scaler:
            features_matrix = self.scaler.fit_transform(features_matrix)
        
        from collections import defaultdict
        author_features = defaultdict(list)
        
        for i, author in enumerate(authors):
            author_features[author].append(features_matrix[i])
        
        self.author_prototypes = {}
        for author, feats in author_features.items():
            self.author_prototypes[author] = np.mean(feats, axis=0)
        
        self.language_stats = {}
        for author in set(authors):
            author_langs = [languages[i] for i in range(len(authors)) if authors[i] == author]
            lang_counts = Counter(author_langs)
            self.language_stats[author] = dict(lang_counts)
        
        self._fitted = True

    def predict(self, text: str, 
                return_all_distances: bool = False) -> Tuple[str, Dict]:
        """
        预测文本作者（跨语言）
        
        Args:
            text: 输入文本
            return_all_distances: 是否返回所有距离
            
        Returns:
            (预测作者, 结果字典)
        """
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        
        feat = self.extract_cross_language_features(text)
        features = feat['combined'].reshape(1, -1)
        
        if self.scaler:
            features = self.scaler.transform(features)
        
        from scipy.spatial.distance import cosine, euclidean
        
        distances = {}
        for author, prototype in self.author_prototypes.items():
            cosine_dist = cosine(features[0], prototype)
            euclidean_dist = euclidean(features[0], prototype)
            distances[author] = {
                'cosine': float(cosine_dist),
                'euclidean': float(euclidean_dist)
            }
        
        sorted_authors = sorted(distances.items(), key=lambda x: x[1]['cosine'])
        predicted_author = sorted_authors[0][0]
        
        min_dist = sorted_authors[0][1]['cosine']
        second_min_dist = sorted_authors[1][1]['cosine'] if len(sorted_authors) > 1 else min_dist + 1
        confidence = max(0, min(1, 1 - min_dist) * (1 + (second_min_dist - min_dist)))
        
        result = {
            'predicted_author': predicted_author,
            'confidence': float(confidence),
            'detected_language': feat['language'],
            'language_confidence': feat['language_confidence'],
            'top_predictions': [
                {
                    'author': author,
                    'cosine_distance': dist['cosine'],
                    'euclidean_distance': dist['euclidean']
                }
                for author, dist in sorted_authors[:5]
            ]
        }
        
        if return_all_distances:
            result['all_distances'] = distances
        
        return predicted_author, result

    def cross_language_verify(self, text1: str, text2: str,
                               author: Optional[str] = None) -> Dict[str, float]:
        """
        跨语言作者验证
        
        判断两篇不同语言的文本是否来自同一作者
        
        Args:
            text1: 文本1（语言A）
            text2: 文本2（语言B）
            author: 可选，假设的作者
            
        Returns:
            相似度和距离指标
        """
        feat1 = self.extract_cross_language_features(text1)
        feat2 = self.extract_cross_language_features(text2)
        
        f1 = feat1['combined']
        f2 = feat2['combined']
        
        if self.scaler and self._fitted:
            f1 = self.scaler.transform([f1])[0]
            f2 = self.scaler.transform([f2])[0]
        
        lang_agnostic1 = feat1['language_agnostic']
        lang_agnostic2 = feat2['language_agnostic']
        
        bert1 = feat1['bert_embedding']
        bert2 = feat2['bert_embedding']
        
        from scipy.spatial.distance import cosine
        
        combined_cosine = cosine(f1, f2)
        lang_agnostic_cosine = cosine(lang_agnostic1, lang_agnostic2)
        bert_cosine = cosine(bert1, bert2)
        
        same_author_score = 0.4 * (1 - combined_cosine) + \
                           0.3 * (1 - lang_agnostic_cosine) + \
                           0.3 * (1 - bert_cosine)
        
        result = {
            'text1_language': feat1['language'],
            'text2_language': feat2['language'],
            'combined_cosine_similarity': float(1 - combined_cosine),
            'language_agnostic_similarity': float(1 - lang_agnostic_cosine),
            'bert_similarity': float(1 - bert_cosine),
            'same_author_probability': float(max(0, min(1, same_author_score))),
            'same_author': same_author_score > 0.65
        }
        
        if author and author in self.author_prototypes:
            prototype = self.author_prototypes[author]
            d1 = cosine(f1, prototype)
            d2 = cosine(f2, prototype)
            result['author_match_text1'] = float(1 - d1)
            result['author_match_text2'] = float(1 - d2)
            result['author_match_avg'] = float(1 - (d1 + d2) / 2)
        
        return result

    def save(self, path: str):
        """保存模型"""
        import joblib
        data = {
            'bert_model_name': self.bert_model_name,
            'embedding_dim': self.embedding_dim,
            'author_prototypes': self.author_prototypes,
            'language_stats': self.language_stats,
            'scaler': self.scaler,
            '_fitted': self._fitted
        }
        joblib.dump(data, path)

    @classmethod
    def load(cls, path: str) -> 'CrossLanguageClassifier':
        """加载模型"""
        import joblib
        data = joblib.load(path)
        clf = cls(
            bert_model_name=data['bert_model_name'],
            embedding_dim=data['embedding_dim']
        )
        clf.author_prototypes = data['author_prototypes']
        clf.language_stats = data['language_stats']
        clf.scaler = data['scaler']
        clf._fitted = data['_fitted']
        return clf
