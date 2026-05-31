"""
作者归属预测模型
基于scikit-learn的分类器，支持200位作家的归属预测
"""

import os
import numpy as np
import joblib
from typing import List, Dict, Tuple, Optional
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from scipy.spatial.distance import cosine, euclidean, mahalanobis
from scipy.stats import entropy


AUTHOR_LIST = [
    "William Shakespeare", "Charles Dickens", "Jane Austen", "Mark Twain", "Ernest Hemingway",
    "F. Scott Fitzgerald", "George Orwell", "Virginia Woolf", "Leo Tolstoy", "Fyodor Dostoevsky",
    "James Joyce", "Franz Kafka", "Albert Camus", "Gabriel García Márquez", "Jorge Luis Borges",
    "Haruki Murakami", "J.K. Rowling", "Stephen King", "Agatha Christie", "Arthur Conan Doyle",
    "Edgar Allan Poe", "Oscar Wilde", "Lewis Carroll", "J.R.R. Tolkien", "C.S. Lewis",
    "H.G. Wells", "George R.R. Martin", "Tolkien", "Herman Melville", "Nathaniel Hawthorne",
    "Emily Dickinson", "Robert Frost", "Walt Whitman", "T.S. Eliot", "Ezra Pound",
    "Samuel Beckett", "Bertrand Russell", "Sigmund Freud", "Karl Marx", "Friedrich Nietzsche",
    "Immanuel Kant", "Aristotle", "Plato", "Socrates", "Confucius",
    "Laozi", "Zhuangzi", "Mencius", "Sun Tzu", "Machiavelli",
    "Voltaire", "Rousseau", "Montesquieu", "Diderot", "Goethe",
    "Schiller", "Kafka", "Proust", "Flaubert", "Balzac",
    "Victor Hugo", "Stendhal", "Guy de Maupassant", "Émile Zola", "Simone de Beauvoir",
    "Jean-Paul Sartre", "Albert Camus", "André Gide", "Marcel Proust", "Gustave Flaubert",
    "Honoré de Balzac", "Alexandre Dumas", "Victor Hugo", "Jules Verne", "Gaston Leroux",
    "Antoine de Saint-Exupéry", "Jean Cocteau", "Jean Genet", "Marguerite Duras", "Simone Weil",
    "Dante Alighieri", "Petrarch", "Boccaccio", "Machiavelli", "Alessandro Manzoni",
    "Luigi Pirandello", "Italo Calvino", "Umberto Eco", "Primo Levi", "Giorgio Manganelli",
    "Federico García Lorca", "Miguel de Cervantes", "Gabriel García Márquez", "Jorge Luis Borges", "Julio Cortázar",
    "Carlos Fuentes", "Mario Vargas Llosa", "Gabriel García Márquez", "Isabel Allende", "Pablo Neruda",
    "Octavio Paz", "Juan Rulfo", "Guillermo Cabrera Infante", "José Saramago", "Fernando Pessoa",
    "Eça de Queirós", "Luís de Camões", "Fernando Pessoa", "José Saramago", "Jorge Amado",
    "Tolstoy", "Dostoevsky", "Chekhov", "Turgenev", "Gogol",
    "Pushkin", "Lermontov", "Bulgakov", "Solzhenitsyn", "Pasternak",
    "Nabokov", "Kafka", "Mann", "Goethe", "Hesse",
    "Brecht", "Grass", "Böll", "Kleist", "Schopenhauer",
    "Hegel", "Heidegger", "Wittgenstein", "Habermas", "Benjamin",
    "Ibsen", "Kierkegaard", "Andersen", "Strindberg", "Munch",
    "Ingmar Bergman", "Astrid Lindgren", "Tove Jansson", "Knut Hamsun", "Henrik Ibsen",
    "Thomas Hardy", "D.H. Lawrence", "Virginia Woolf", "E.M. Forster", "Aldous Huxley",
    "George Orwell", "Graham Greene", "Evelyn Waugh", "W.H. Auden", "Philip Larkin",
    "John le Carré", "Salman Rushdie", "Ian McEwan", "Kazuo Ishiguro", "Hilary Mantel",
    "Zadie Smith", "Hanif Kureishi", "Martin Amis", "Julian Barnes", "A.S. Byatt",
    "Edith Wharton", "Henry James", "Willa Cather", "Gertrude Stein", "Toni Morrison",
    "Alice Walker", "Maya Angelou", "Ralph Ellison", "James Baldwin", "Harper Lee",
    "Truman Capote", "Carson McCullers", "Flannery O'Connor", "Eudora Welty", "Joan Didion",
    "Don DeLillo", "Thomas Pynchon", "Philip Roth", "John Updike", "Saul Bellow",
    "J.D. Salinger", "Ray Bradbury", "Kurt Vonnegut", "Joseph Heller", "Norman Mailer",
    "Margaret Atwood", "Alice Munro", "Michael Ondaatje", "Yann Martel", "Douglas Adams",
    "Terry Pratchett", "Neil Gaiman", "Philip K. Dick", "Robert A. Heinlein", "Isaac Asimov",
    "Arthur C. Clarke", "Frank Herbert", "Ursula K. Le Guin", "Octavia Butler", "Samuel R. Delany",
    "Rumi", "Omar Khayyam", "Hafez", "Saadi", "Nizami",
    "Rabindranath Tagore", "Kalidasa", "Valmiki", "Vyasa", "Premchand",
    "Murasaki Shikibu", "Bashō", "Natsume Sōseki", "Yukio Mishima", "Kawabata Yasunari",
    "Oe Kenzaburo", "Banana Yoshimoto", "Haruki Murakami", "Mishima Yukio", "Tanizaki Jun'ichirō",
    "Du Fu", "Li Bai", "Su Shi", "Cao Xueqin", "Lu Xun",
    "Mo Yan", "Yu Hua", "Gao Xingjian", "Can Xue", "Wang Anyi"
]


class AuthorClassifier:
    """
    作者归属分类器
    
    支持:
    - 200位作家的多分类预测
    - 预测置信度计算（文本长度归一化）
    - 风格距离计算
    - 模型训练与持久化
    """

    def __init__(self, feature_dim: int = 372):
        """
        初始化分类器
        
        Args:
            feature_dim: 特征维度 (默认372: 14+3+12+6+100+37+200)
        """
        self.feature_dim = feature_dim
        self.scaler = StandardScaler()
        
        self.ref_word_counts = {}
        self.train_text_length_stats = None
        
        self.classifier = RandomForestClassifier(
            n_estimators=200,
            max_depth=None,
            min_samples_split=2,
            min_samples_leaf=1,
            random_state=42,
            n_jobs=-1
        )
        
        self.secondary_classifier = SVC(
            kernel='rbf',
            probability=True,
            random_state=42
        )
        
        self.ensemble_classifier = LogisticRegression(
            max_iter=1000,
            random_state=42
        )
        
        self.authors = []
        self.author_to_idx = {}
        self.idx_to_author = {}
        self.author_prototypes = {}
        self._fitted = False
        self._cov_matrix = None

    def _encode_authors(self, authors: List[str]) -> np.ndarray:
        """将作者名称编码为整数标签"""
        unique_authors = sorted(list(set(authors)))
        
        if not self.authors:
            self.authors = unique_authors
            self.author_to_idx = {a: i for i, a in enumerate(self.authors)}
            self.idx_to_author = {i: a for i, a in enumerate(self.authors)}
        
        return np.array([self.author_to_idx[a] for a in authors if a in self.author_to_idx])

    def _compute_prototypes(self, X: np.ndarray, y: np.ndarray):
        """计算每个作者的特征原型（均值向量）"""
        self.author_prototypes = {}
        
        for author_idx in np.unique(y):
            author_features = X[y == author_idx]
            if len(author_features) > 0:
                prototype = np.mean(author_features, axis=0)
                self.author_prototypes[author_idx] = prototype
        
        self._cov_matrix = np.cov(X.T) + 1e-6 * np.eye(X.shape[1])

    def fit(self, X: np.ndarray, y: List[str], 
            use_ensemble: bool = True,
            text_word_counts: Optional[List[int]] = None) -> Dict[str, float]:
        """
        训练分类器
        
        Args:
            X: 特征矩阵 (n_samples, n_features)
            y: 作者标签列表
            use_ensemble: 是否使用集成分类
            text_word_counts: 各训练文本的单词数列表（用于置信度归一化）
            
        Returns:
            训练指标字典
        """
        if X.shape[1] != self.feature_dim:
            raise ValueError(f"Expected {self.feature_dim} features, got {X.shape[1]}")
        
        y_encoded = self._encode_authors(y)
        
        if text_word_counts is not None and len(text_word_counts) == len(y):
            self.train_text_length_stats = {
                'mean': float(np.mean(text_word_counts)),
                'std': float(np.std(text_word_counts)),
                'min': float(np.min(text_word_counts)),
                'max': float(np.max(text_word_counts)),
                'percentiles': {
                    '25': float(np.percentile(text_word_counts, 25)),
                    '50': float(np.percentile(text_word_counts, 50)),
                    '75': float(np.percentile(text_word_counts, 75))
                }
            }
            
            for author_idx in np.unique(y_encoded):
                mask = y_encoded == author_idx
                author_counts = [text_word_counts[i] for i in range(len(text_word_counts)) if mask[i]]
                if author_counts:
                    author_name = self.idx_to_author[author_idx]
                    self.ref_word_counts[author_name] = {
                        'mean': float(np.mean(author_counts)),
                        'std': float(np.std(author_counts))
                    }
        
        X_train, X_val, y_train, y_val = train_test_split(
            X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
        )
        
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        self.classifier.fit(X_train_scaled, y_train)
        rf_acc = self.classifier.score(X_val_scaled, y_val)
        
        if use_ensemble and len(np.unique(y_train)) > 2:
            self.secondary_classifier.fit(X_train_scaled, y_train)
            svc_acc = self.secondary_classifier.score(X_val_scaled, y_val)
            
            rf_train_proba = self.classifier.predict_proba(X_train_scaled)
            svc_train_proba = self.secondary_classifier.predict_proba(X_train_scaled)
            ensemble_train = np.hstack([rf_train_proba, svc_train_proba])
            
            rf_val_proba = self.classifier.predict_proba(X_val_scaled)
            svc_val_proba = self.secondary_classifier.predict_proba(X_val_scaled)
            ensemble_val = np.hstack([rf_val_proba, svc_val_proba])
            
            self.ensemble_classifier.fit(ensemble_train, y_train)
            ensemble_acc = self.ensemble_classifier.score(ensemble_val, y_val)
            final_acc = ensemble_acc
        else:
            final_acc = rf_acc
        
        X_all_scaled = self.scaler.transform(X)
        self._compute_prototypes(X_all_scaled, y_encoded)
        
        self._fitted = True
        
        metrics = {
            'random_forest_accuracy': rf_acc,
            'svc_accuracy': svc_acc if use_ensemble else None,
            'ensemble_accuracy': final_acc if use_ensemble else rf_acc,
            'num_authors': len(self.authors),
            'num_samples': X.shape[0],
            'length_normalization_enabled': self.train_text_length_stats is not None
        }
        
        return metrics

    def _compute_length_normalization_factor(self, word_count: int, 
                                             predicted_author: Optional[str] = None) -> float:
        """
        计算文本长度归一化因子
        
        对于较短的文本，模型置信度会自然降低，需要上调；
        对于较长的文本，模型置信度会自然偏高，需要下调。
        
        Args:
            word_count: 文本单词数
            predicted_author: 预测的作者名称（可选，用于作者特定的长度基准）
            
        Returns:
            归一化因子 (0.5 - 1.5)
        """
        if self.train_text_length_stats is None:
            return 1.0
        
        ref_mean = self.train_text_length_stats['mean']
        ref_std = self.train_text_length_stats['std'] or 1.0
        
        if predicted_author and predicted_author in self.ref_word_counts:
            author_ref = self.ref_word_counts[predicted_author]
            ref_mean = author_ref['mean']
            ref_std = author_ref['std'] or 1.0
        
        if word_count <= 0:
            return 0.5
        
        log_ratio = np.log(word_count / max(ref_mean, 1))
        z_score = log_ratio / max(np.log(max(ref_std, 2)), 0.5)
        
        factor = 1.0 - 0.35 * np.tanh(z_score)
        factor = max(0.5, min(1.5, factor))
        
        return factor

    def _calibrate_confidence(self, raw_confidence: float, word_count: int,
                               poetry_score: float = 0.0,
                               dialogue_ratio: float = 0.5,
                               predicted_author: Optional[str] = None) -> float:
        """
        校准置信度，消除文本长度、体裁、文本类型的影响
        
        Args:
            raw_confidence: 原始置信度
            word_count: 文本单词数
            poetry_score: 诗歌体裁分数 (0-1)
            dialogue_ratio: 对话比例 (0-1)
            predicted_author: 预测作者名称
            
        Returns:
            校准后的置信度
        """
        length_factor = self._compute_length_normalization_factor(word_count, predicted_author)
        
        genre_factor = 1.0 - 0.2 * poetry_score
        
        text_type_factor = 0.9 + 0.2 * max(dialogue_ratio, 1 - dialogue_ratio)
        
        calibrated = raw_confidence * length_factor * genre_factor * text_type_factor
        calibrated = max(0.01, min(0.99, calibrated))
        
        return calibrated

    def predict(self, X: np.ndarray, 
                return_all: bool = False) -> Tuple[List[str], np.ndarray]:
        """
        预测作者
        
        Args:
            X: 特征矩阵 (n_samples, n_features)
            return_all: 是否返回所有作者的概率
            
        Returns:
            (预测作者列表, 概率矩阵或top概率)
        """
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        
        if X.shape[1] != self.feature_dim:
            raise ValueError(f"Expected {self.feature_dim} features, got {X.shape[1]}")
        
        X_scaled = self.scaler.transform(X)
        
        rf_proba = self.classifier.predict_proba(X_scaled)
        
        if hasattr(self, 'secondary_classifier') and self._fitted:
            try:
                svc_proba = self.secondary_classifier.predict_proba(X_scaled)
                ensemble_features = np.hstack([rf_proba, svc_proba])
                final_proba = self.ensemble_classifier.predict_proba(ensemble_features)
            except:
                final_proba = rf_proba
        else:
            final_proba = rf_proba
        
        top_indices = np.argmax(final_proba, axis=1)
        predicted_authors = [self.idx_to_author[i] for i in top_indices]
        
        if return_all:
            return predicted_authors, final_proba
        else:
            top_proba = np.max(final_proba, axis=1)
            return predicted_authors, top_proba

    def predict_with_confidence(self, X: np.ndarray,
                                 text_metadata: Optional[List[Dict[str, float]]] = None) -> List[Dict]:
        """
        预测并返回详细置信度信息（支持文本长度归一化）
        
        Args:
            X: 特征矩阵 (n_samples, n_features)
            text_metadata: 文本元数据列表，每个元素包含:
                - word_count: 单词数
                - poetry_score: 诗歌体裁分数 (0-1)
                - dialogue_ratio: 对话比例 (0-1)
                
        Returns:
            预测结果列表，每个元素包含:
            - predicted_author: 预测作者
            - confidence: 校准后的置信度 (0-1)
            - raw_confidence: 原始置信度
            - confidence_calibration: 校准因子详情
            - top_predictions: Top 5预测及其概率
            - style_distances: 到各作者原型的风格距离
        """
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        
        predicted_authors, all_proba = self.predict(X, return_all=True)
        X_scaled = self.scaler.transform(X)
        
        results = []
        
        for i in range(X.shape[0]):
            proba = all_proba[i]
            feature_vec = X_scaled[i]
            
            top_indices = np.argsort(proba)[::-1][:5]
            raw_confidence = float(proba[top_indices[0]])
            predicted_author = predicted_authors[i]
            
            word_count = 0
            poetry_score = 0.0
            dialogue_ratio = 0.5
            
            if text_metadata and i < len(text_metadata):
                meta = text_metadata[i]
                word_count = meta.get('word_count', 0)
                poetry_score = meta.get('poetry_score', 0.0)
                dialogue_ratio = meta.get('dialogue_ratio', 0.5)
            
            calibrated_confidence = self._calibrate_confidence(
                raw_confidence, word_count, poetry_score, dialogue_ratio, predicted_author
            )
            
            length_factor = self._compute_length_normalization_factor(word_count, predicted_author)
            genre_factor = 1.0 - 0.2 * poetry_score
            text_type_factor = 0.9 + 0.2 * max(dialogue_ratio, 1 - dialogue_ratio)
            
            top_predictions = [
                {
                    'author': self.idx_to_author[idx],
                    'probability': float(proba[idx]),
                    'calibrated_probability': float(self._calibrate_confidence(
                        float(proba[idx]), word_count, poetry_score, 
                        dialogue_ratio, self.idx_to_author[idx]
                    ))
                }
                for idx in top_indices
            ]
            
            style_distances = self._compute_style_distances(feature_vec)
            
            result = {
                'predicted_author': predicted_author,
                'confidence': calibrated_confidence,
                'raw_confidence': raw_confidence,
                'confidence_calibration': {
                    'length_factor': float(length_factor),
                    'genre_factor': float(genre_factor),
                    'text_type_factor': float(text_type_factor),
                    'word_count': word_count,
                    'poetry_score': poetry_score,
                    'dialogue_ratio': dialogue_ratio
                },
                'top_predictions': top_predictions,
                'style_distances': style_distances
            }
            
            results.append(result)
        
        return results

    def _compute_style_distances(self, feature_vec: np.ndarray) -> Dict[str, Dict[str, float]]:
        """计算特征向量到各作者原型的距离"""
        distances = {}
        
        for author_idx, prototype in self.author_prototypes.items():
            author_name = self.idx_to_author[author_idx]
            
            cosine_dist = cosine(feature_vec, prototype)
            euclidean_dist = euclidean(feature_vec, prototype)
            
            try:
                mahalanobis_dist = mahalanobis(
                    feature_vec, prototype, np.linalg.inv(self._cov_matrix)
                )
            except:
                mahalanobis_dist = euclidean_dist
            
            distances[author_name] = {
                'cosine': float(cosine_dist),
                'euclidean': float(euclidean_dist),
                'mahalanobis': float(mahalanobis_dist)
            }
        
        return distances

    def compute_style_divergence(self, text_features1: np.ndarray, 
                                  text_features2: np.ndarray) -> Dict[str, float]:
        """
        计算两篇文本之间的风格散度
        
        Args:
            text_features1: 文本1的特征向量
            text_features2: 文本2的特征向量
            
        Returns:
            各种散度指标
        """
        f1 = self.scaler.transform([text_features1])[0]
        f2 = self.scaler.transform([text_features2])[0]
        
        f1_norm = f1 / (np.sum(f1) + 1e-10)
        f2_norm = f2 / (np.sum(f2) + 1e-10)
        
        kl_div = entropy(f1_norm + 1e-10, f2_norm + 1e-10)
        js_div = 0.5 * entropy(f1_norm + 1e-10, 0.5 * (f1_norm + f2_norm) + 1e-10) + \
                 0.5 * entropy(f2_norm + 1e-10, 0.5 * (f1_norm + f2_norm) + 1e-10)
        
        cosine_sim = 1 - cosine(f1, f2)
        euclidean_dist = euclidean(f1, f2)
        correlation = np.corrcoef(f1, f2)[0, 1]
        
        return {
            'kl_divergence': float(kl_div),
            'js_divergence': float(js_div),
            'cosine_similarity': float(cosine_sim),
            'euclidean_distance': float(euclidean_dist),
            'correlation': float(correlation)
        }

    def save(self, path: str):
        """保存模型到文件"""
        model_data = {
            'classifier': self.classifier,
            'secondary_classifier': self.secondary_classifier,
            'ensemble_classifier': self.ensemble_classifier,
            'scaler': self.scaler,
            'authors': self.authors,
            'author_to_idx': self.author_to_idx,
            'idx_to_author': self.idx_to_author,
            'author_prototypes': self.author_prototypes,
            'cov_matrix': self._cov_matrix,
            'feature_dim': self.feature_dim,
            '_fitted': self._fitted
        }
        joblib.dump(model_data, path)

    @classmethod
    def load(cls, path: str) -> 'AuthorClassifier':
        """从文件加载模型"""
        model_data = joblib.load(path)
        classifier = cls(feature_dim=model_data['feature_dim'])
        classifier.classifier = model_data['classifier']
        classifier.secondary_classifier = model_data['secondary_classifier']
        classifier.ensemble_classifier = model_data['ensemble_classifier']
        classifier.scaler = model_data['scaler']
        classifier.authors = model_data['authors']
        classifier.author_to_idx = model_data['author_to_idx']
        classifier.idx_to_author = model_data['idx_to_author']
        classifier.author_prototypes = model_data['author_prototypes']
        classifier._cov_matrix = model_data['cov_matrix']
        classifier._fitted = model_data['_fitted']
        return classifier

    def get_author_list(self) -> List[str]:
        """获取所有作者列表"""
        return self.authors.copy()

    def get_feature_dim(self) -> int:
        """获取特征维度"""
        return self.feature_dim
