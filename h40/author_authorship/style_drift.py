"""
时序风格漂移分析模块
分析同一作者不同作品之间的风格变化，计算散度指标
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy.stats import entropy, wasserstein_distance
from scipy.spatial.distance import cosine, euclidean, jensenshannon
from scipy.special import kl_div
import pandas as pd


class StyleDriftAnalyzer:
    """
    风格漂移分析器
    
    用于分析同一作者不同时期作品的风格变化，
    计算多种散度指标衡量风格漂移程度
    """

    def __init__(self, feature_extractor=None):
        """
        初始化风格漂移分析器
        
        Args:
            feature_extractor: 特征提取器实例
        """
        self.feature_extractor = feature_extractor
        self.feature_groups = None
        
        if feature_extractor is not None:
            self.feature_groups = feature_extractor.get_feature_groups()

    def _normalize(self, x: np.ndarray) -> np.ndarray:
        """归一化向量到概率分布"""
        x = np.clip(x, 0, None) + 1e-10
        return x / np.sum(x)

    def kullback_leibler_divergence(self, p: np.ndarray, q: np.ndarray) -> float:
        """
        计算Kullback-Leibler散度
        
        D_KL(P||Q) = Σ P(i) * log(P(i)/Q(i))
        """
        p_norm = self._normalize(p)
        q_norm = self._normalize(q)
        return float(np.sum(kl_div(p_norm, q_norm)))

    def jensen_shannon_divergence(self, p: np.ndarray, q: np.ndarray) -> float:
        """
        计算Jensen-Shannon散度
        
        D_JSD(P||Q) = 0.5 * D_KL(P||M) + 0.5 * D_KL(Q||M)
        其中 M = 0.5 * (P + Q)
        """
        return float(jensenshannon(p, q) ** 2)

    def hellinger_distance(self, p: np.ndarray, q: np.ndarray) -> float:
        """
        计算Hellinger距离
        
        H(P, Q) = sqrt(0.5 * Σ (sqrt(P(i)) - sqrt(Q(i)))^2)
        """
        p_norm = self._normalize(p)
        q_norm = self._normalize(q)
        return float(np.sqrt(0.5 * np.sum((np.sqrt(p_norm) - np.sqrt(q_norm)) ** 2)))

    def bhattacharyya_distance(self, p: np.ndarray, q: np.ndarray) -> float:
        """
        计算Bhattacharyya距离
        
        D_B(P, Q) = -ln(BC(P, Q))
        其中 BC(P, Q) = Σ sqrt(P(i) * Q(i))
        """
        p_norm = self._normalize(p)
        q_norm = self._normalize(q)
        bc = np.sum(np.sqrt(p_norm * q_norm))
        return float(-np.log(bc + 1e-10))

    def earth_movers_distance(self, p: np.ndarray, q: np.ndarray) -> float:
        """
        计算Earth Mover's距离 (Wasserstein距离)
        """
        p_norm = self._normalize(p)
        q_norm = self._normalize(q)
        return float(wasserstein_distance(p_norm, q_norm))

    def cosine_dissimilarity(self, p: np.ndarray, q: np.ndarray) -> float:
        """
        计算余弦不相似度 (1 - 余弦相似度)
        """
        return float(cosine(p, q))

    def total_variation_distance(self, p: np.ndarray, q: np.ndarray) -> float:
        """
        计算总变分距离
        
        TV(P, Q) = 0.5 * Σ |P(i) - Q(i)|
        """
        p_norm = self._normalize(p)
        q_norm = self._normalize(q)
        return float(0.5 * np.sum(np.abs(p_norm - q_norm)))

    def f_divergence(self, p: np.ndarray, q: np.ndarray, 
                     f_type: str = 'total_variation') -> float:
        """
        通用f-散度计算
        
        D_f(P||Q) = Σ Q(i) * f(P(i)/Q(i))
        
        Args:
            f_type: f函数类型
                - 'kl': Kullback-Leibler
                - 'reverse_kl': Reverse KL
                - 'total_variation': Total Variation
                - 'pearson': Pearson χ²
                - 'squared': Squared Hellinger
        """
        p_norm = self._normalize(p)
        q_norm = self._normalize(q)
        ratio = p_norm / (q_norm + 1e-10)
        
        if f_type == 'kl':
            f = ratio * np.log(ratio + 1e-10) - ratio + 1
        elif f_type == 'reverse_kl':
            f = -np.log(ratio + 1e-10) + ratio - 1
        elif f_type == 'total_variation':
            f = np.abs(ratio - 1)
        elif f_type == 'pearson':
            f = (ratio - 1) ** 2
        elif f_type == 'squared':
            f = (np.sqrt(ratio) - 1) ** 2
        else:
            raise ValueError(f"Unknown f-type: {f_type}")
        
        return float(np.sum(q_norm * f))

    def compute_all_divergences(self, features1: np.ndarray, 
                                 features2: np.ndarray) -> Dict[str, float]:
        """
        计算所有散度指标
        
        Args:
            features1: 作品1的特征向量
            features2: 作品2的特征向量
            
        Returns:
            包含所有散度指标的字典
        """
        divergences = {
            'kl_divergence': self.kullback_leibler_divergence(features1, features2),
            'js_divergence': self.jensen_shannon_divergence(features1, features2),
            'hellinger_distance': self.hellinger_distance(features1, features2),
            'bhattacharyya_distance': self.bhattacharyya_distance(features1, features2),
            'earth_movers_distance': self.earth_movers_distance(features1, features2),
            'cosine_dissimilarity': self.cosine_dissimilarity(features1, features2),
            'total_variation_distance': self.total_variation_distance(features1, features2),
            'pearson_chi_squared': self.f_divergence(features1, features2, 'pearson'),
            'euclidean_distance': float(euclidean(features1, features2)),
        }
        
        return divergences

    def compute_group_divergences(self, features1: np.ndarray, 
                                   features2: np.ndarray) -> Dict[str, Dict[str, float]]:
        """
        按特征分组计算散度
        
        Args:
            features1: 作品1的特征向量
            features2: 作品2的特征向量
            
        Returns:
            按特征分组的散度指标
        """
        if self.feature_groups is None:
            return {'all_features': self.compute_all_divergences(features1, features2)}
        
        group_divergences = {}
        
        for group_name, feature_names in self.feature_groups.items():
            indices = [i for i, name in enumerate(self.feature_extractor.feature_names) 
                      if name in feature_names]
            
            if indices:
                f1_sub = features1[indices]
                f2_sub = features2[indices]
                group_divergences[group_name] = self.compute_all_divergences(f1_sub, f2_sub)
        
        return group_divergences

    def analyze_temporal_drift(self, works_features: List[np.ndarray],
                                work_titles: Optional[List[str]] = None) -> Dict:
        """
        分析同一作者多部作品的时序风格漂移
        
        Args:
            works_features: 作品特征向量列表，按时间顺序排列
            work_titles: 作品标题列表（可选）
            
        Returns:
            时序分析结果，包含:
            - pairwise_divergences: 两两作品间的散度矩阵
            - drift_trend: 漂移趋势（与最早作品的散度变化）
            - cumulative_drift: 累积漂移
            - drift_rate: 漂移速率
        """
        n_works = len(works_features)
        
        if n_works < 2:
            raise ValueError("At least 2 works are required for temporal analysis")
        
        if work_titles is None:
            work_titles = [f"Work_{i}" for i in range(n_works)]
        
        pairwise_divergences = {}
        divergence_matrix = np.zeros((n_works, n_works))
        
        for i in range(n_works):
            for j in range(i + 1, n_works):
                div = self.compute_all_divergences(
                    works_features[i], works_features[j]
                )
                pairwise_divergences[f"{work_titles[i]}_vs_{work_titles[j]}"] = div
                divergence_matrix[i, j] = div['js_divergence']
                divergence_matrix[j, i] = divergence_matrix[i, j]
        
        drift_trend = []
        for i in range(1, n_works):
            div = self.compute_all_divergences(works_features[0], works_features[i])
            drift_trend.append({
                'work': work_titles[i],
                'time_index': i,
                'divergences': div
            })
        
        cumulative_drift = 0.0
        cumulative_list = []
        for i in range(1, n_works):
            div = self.jensen_shannon_divergence(works_features[i-1], works_features[i])
            cumulative_drift += div
            cumulative_list.append({
                'work': work_titles[i],
                'step_divergence': div,
                'cumulative_divergence': cumulative_drift
            })
        
        drift_rate = cumulative_drift / max(n_works - 1, 1)
        
        feature_drift = self._analyze_feature_drift(works_features)
        
        return {
            'work_titles': work_titles,
            'pairwise_divergences': pairwise_divergences,
            'divergence_matrix': divergence_matrix.tolist(),
            'drift_trend': drift_trend,
            'cumulative_drift': cumulative_list,
            'total_cumulative_drift': cumulative_drift,
            'drift_rate': drift_rate,
            'feature_drift': feature_drift
        }

    def _analyze_feature_drift(self, works_features: List[np.ndarray]) -> Dict:
        """分析各个特征维度的漂移情况"""
        feature_matrix = np.array(works_features)
        n_features = feature_matrix.shape[1]
        
        feature_vars = np.var(feature_matrix, axis=0)
        feature_means = np.mean(feature_matrix, axis=0)
        feature_cvs = feature_vars / (np.abs(feature_means) + 1e-10)
        
        top_drift_indices = np.argsort(feature_cvs)[::-1][:20]
        
        feature_names = []
        if self.feature_extractor is not None:
            feature_names = self.feature_extractor.feature_names
        
        top_drifting_features = []
        for idx in top_drift_indices:
            top_drifting_features.append({
                'feature_index': int(idx),
                'feature_name': feature_names[idx] if idx < len(feature_names) else f"feature_{idx}",
                'coefficient_of_variation': float(feature_cvs[idx]),
                'mean': float(feature_means[idx]),
                'variance': float(feature_vars[idx]),
                'values': feature_matrix[:, idx].tolist()
            })
        
        return {
            'feature_variances': feature_vars.tolist(),
            'feature_means': feature_means.tolist(),
            'coefficients_of_variation': feature_cvs.tolist(),
            'top_drifting_features': top_drifting_features
        }

    def detect_style_change_points(self, works_features: List[np.ndarray],
                                    threshold: float = 0.5) -> List[int]:
        """
        检测风格突变点
        
        使用滑动窗口检测相邻作品间的散度突变
        
        Args:
            works_features: 作品特征向量列表
            threshold: 突变阈值（标准差倍数）
            
        Returns:
            突变点索引列表
        """
        n_works = len(works_features)
        
        if n_works < 3:
            return []
        
        adjacent_divergences = []
        for i in range(n_works - 1):
            div = self.jensen_shannon_divergence(works_features[i], works_features[i+1])
            adjacent_divergences.append(div)
        
        adjacent_divergences = np.array(adjacent_divergences)
        mean_div = np.mean(adjacent_divergences)
        std_div = np.std(adjacent_divergences)
        
        change_points = []
        for i, div in enumerate(adjacent_divergences):
            if div > mean_div + threshold * std_div:
                change_points.append(i + 1)
        
        return change_points

    def sliding_window_drift(self, text: str, window_size: int = 1000,
                              step_size: int = 500) -> Dict:
        """
        对单篇文本进行滑动窗口风格漂移分析
        
        Args:
            text: 输入文本
            window_size: 窗口大小（字符数）
            step_size: 步长（字符数）
            
        Returns:
            滑动窗口分析结果
        """
        if self.feature_extractor is None:
            raise RuntimeError("Feature extractor is required for sliding window analysis")
        
        windows = []
        for i in range(0, len(text) - window_size + 1, step_size):
            window = text[i:i + window_size]
            if len(window.strip()) > 100:
                windows.append(window)
        
        if len(windows) < 2:
            return {"error": "Not enough windows for analysis"}
        
        window_features = self.feature_extractor.extract_batch(windows)
        
        reference_features = window_features[0]
        
        drift_series = []
        for i, feat in enumerate(window_features):
            div = self.compute_all_divergences(reference_features, feat)
            drift_series.append({
                'window_index': i,
                'start_char': i * step_size,
                'end_char': i * step_size + window_size,
                'divergences': div
            })
        
        return {
            'num_windows': len(windows),
            'window_size': window_size,
            'step_size': step_size,
            'drift_series': drift_series
        }
