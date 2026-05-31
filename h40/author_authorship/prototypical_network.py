"""
原型网络小样本学习模块
支持使用少量样本快速添加新作者
基于Prototypical Networks for Few-shot Learning (Snell et al., 2017)
"""

import numpy as np
import joblib
from typing import List, Dict, Tuple, Optional
from scipy.spatial.distance import cdist
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score
import warnings


class PrototypicalNetwork:
    """
    原型网络小样本学习器
    
    支持:
    - 小样本学习添加新作者
    - 基于距离的分类预测
    - 增量学习
    - 模型持久化
    - 文本长度归一化的置信度校准
    """

    def __init__(self, feature_dim: int = 372, 
                 distance_metric: str = 'mahalanobis'):
        """
        初始化原型网络
        
        Args:
            feature_dim: 特征维度
            distance_metric: 距离度量方式
                - 'euclidean': 欧氏距离
                - 'cosine': 余弦距离
                - 'mahalanobis': 马氏距离
                - 'manhattan': 曼哈顿距离
        """
        self.feature_dim = feature_dim
        self.distance_metric = distance_metric
        self.scaler = StandardScaler()
        
        self.prototypes = {}
        self.author_samples = {}
        self.cov_matrix = None
        self.inv_cov_matrix = None
        self._fitted = False
        self._author_indices = {}

    def _compute_distance(self, x: np.ndarray, prototype: np.ndarray) -> float:
        """计算样本到原型的距离"""
        if self.distance_metric == 'euclidean':
            return np.sqrt(np.sum((x - prototype) ** 2))
        elif self.distance_metric == 'cosine':
            return 1 - np.dot(x, prototype) / (np.linalg.norm(x) * np.linalg.norm(prototype) + 1e-10)
        elif self.distance_metric == 'mahalanobis':
            if self.inv_cov_matrix is not None:
                diff = x - prototype
                return np.sqrt(diff @ self.inv_cov_matrix @ diff.T)
            else:
                return np.sqrt(np.sum((x - prototype) ** 2))
        elif self.distance_metric == 'manhattan':
            return np.sum(np.abs(x - prototype))
        else:
            raise ValueError(f"Unknown distance metric: {self.distance_metric}")

    def _compute_distances_batch(self, X: np.ndarray, 
                                  prototypes: np.ndarray) -> np.ndarray:
        """批量计算距离矩阵"""
        if self.distance_metric == 'euclidean':
            return cdist(X, prototypes, metric='euclidean')
        elif self.distance_metric == 'cosine':
            return cdist(X, prototypes, metric='cosine')
        elif self.distance_metric == 'mahalanobis':
            if self.inv_cov_matrix is not None:
                return cdist(X, prototypes, metric='mahalanobis', VI=self.inv_cov_matrix)
            else:
                return cdist(X, prototypes, metric='euclidean')
        elif self.distance_metric == 'manhattan':
            return cdist(X, prototypes, metric='cityblock')
        else:
            raise ValueError(f"Unknown distance metric: {self.distance_metric}")

    def fit_base_model(self, X: np.ndarray, y: List[str]):
        """
        在基础数据集上拟合模型，计算协方差矩阵和全局统计量
        
        Args:
            X: 特征矩阵 (n_samples, n_features)
            y: 作者标签列表
        """
        if X.shape[1] != self.feature_dim:
            raise ValueError(f"Expected {self.feature_dim} features, got {X.shape[1]}")
        
        X_scaled = self.scaler.fit_transform(X)
        
        self.cov_matrix = np.cov(X_scaled.T) + 1e-6 * np.eye(X_scaled.shape[1])
        self.inv_cov_matrix = np.linalg.inv(self.cov_matrix)
        
        unique_authors = sorted(list(set(y)))
        for author in unique_authors:
            mask = [a == author for a in y]
            author_features = X_scaled[mask]
            if len(author_features) > 0:
                self.prototypes[author] = np.mean(author_features, axis=0)
                self.author_samples[author] = author_features
        
        self._author_indices = {author: i for i, author in enumerate(self.prototypes.keys())}
        self._fitted = True

    def add_new_author(self, author_name: str, 
                        sample_features: List[np.ndarray],
                        update_global_stats: bool = False) -> Dict:
        """
        添加新作者（小样本学习）
        
        Args:
            author_name: 新作者名称
            sample_features: 样本特征向量列表（建议3-5个样本）
            update_global_stats: 是否更新全局统计量（需要足够多样本）
            
        Returns:
            添加结果信息
        """
        if len(sample_features) < 1:
            raise ValueError("At least one sample is required to add a new author")
        
        if author_name in self.prototypes:
            warnings.warn(f"Author '{author_name}' already exists. Updating prototype.")
        
        sample_array = np.array(sample_features)
        
        if not self._fitted:
            self.scaler.fit(sample_array)
            self.cov_matrix = np.cov(sample_array.T) + 1e-6 * np.eye(sample_array.shape[1])
            self.inv_cov_matrix = np.linalg.inv(self.cov_matrix)
            self._fitted = True
        
        scaled_samples = self.scaler.transform(sample_array)
        
        prototype = np.mean(scaled_samples, axis=0)
        self.prototypes[author_name] = prototype
        self.author_samples[author_name] = scaled_samples
        
        if update_global_stats and len(sample_features) >= 5:
            all_samples = np.vstack([s for s in self.author_samples.values()])
            self.cov_matrix = np.cov(all_samples.T) + 1e-6 * np.eye(all_samples.shape[1])
            self.inv_cov_matrix = np.linalg.inv(self.cov_matrix)
        
        self._author_indices = {author: i for i, author in enumerate(self.prototypes.keys())}
        
        intra_class_distances = []
        for i in range(len(scaled_samples)):
            for j in range(i + 1, len(scaled_samples)):
                dist = self._compute_distance(scaled_samples[i], scaled_samples[j])
                intra_class_distances.append(dist)
        
        mean_intra_dist = np.mean(intra_class_distances) if intra_class_distances else 0.0
        
        inter_class_distances = []
        for other_author, other_prototype in self.prototypes.items():
            if other_author != author_name:
                dist = self._compute_distance(prototype, other_prototype)
                inter_class_distances.append(dist)
        
        mean_inter_dist = np.mean(inter_class_distances) if inter_class_distances else 0.0
        
        result = {
            'author_name': author_name,
            'num_samples': len(sample_features),
            'feature_dim': self.feature_dim,
            'mean_intra_class_distance': float(mean_intra_dist),
            'mean_inter_class_distance': float(mean_inter_dist),
            'separability_ratio': float(mean_inter_dist / (mean_intra_dist + 1e-10)),
            'total_authors': len(self.prototypes),
            'prototype_updated': author_name in self.prototypes
        }
        
        return result

    def predict(self, X: np.ndarray, 
                return_all_distances: bool = False) -> Tuple[List[str], np.ndarray]:
        """
        预测作者归属
        
        Args:
            X: 特征矩阵 (n_samples, n_features)
            return_all_distances: 是否返回所有距离
            
        Returns:
            (预测作者列表, 距离矩阵或概率矩阵)
        """
        if not self._fitted or len(self.prototypes) == 0:
            raise RuntimeError("Model not fitted. Call fit_base_model() or add_new_author() first.")
        
        if X.shape[1] != self.feature_dim:
            raise ValueError(f"Expected {self.feature_dim} features, got {X.shape[1]}")
        
        X_scaled = self.scaler.transform(X)
        
        author_list = list(self.prototypes.keys())
        prototype_matrix = np.array([self.prototypes[author] for author in author_list])
        
        distances = self._compute_distances_batch(X_scaled, prototype_matrix)
        
        min_indices = np.argmin(distances, axis=1)
        predicted_authors = [author_list[i] for i in min_indices]
        
        if return_all_distances:
            return predicted_authors, distances
        else:
            min_distances = np.min(distances, axis=1)
            return predicted_authors, min_distances

    def predict_with_confidence(self, X: np.ndarray) -> List[Dict]:
        """
        预测并返回置信度信息
        
        Args:
            X: 特征矩阵 (n_samples, n_features)
            
        Returns:
            预测结果列表，每个元素包含:
            - predicted_author: 预测作者
            - confidence: 置信度 (基于距离转换)
            - top_predictions: Top 5预测
            - distances: 到各作者的距离
        """
        predicted_authors, all_distances = self.predict(X, return_all_distances=True)
        author_list = list(self.prototypes.keys())
        
        results = []
        
        for i in range(X.shape[0]):
            distances = all_distances[i]
            
            sorted_indices = np.argsort(distances)
            sorted_distances = distances[sorted_indices]
            
            sigma = np.mean(sorted_distances) + 1e-10
            probabilities = np.exp(-sorted_distances / sigma)
            probabilities = probabilities / np.sum(probabilities)
            
            top_predictions = [
                {
                    'author': author_list[idx],
                    'distance': float(distances[idx]),
                    'probability': float(probabilities[j])
                }
                for j, idx in enumerate(sorted_indices[:5])
            ]
            
            confidence = float(probabilities[0])
            
            distances_dict = {
                author_list[j]: float(distances[j])
                for j in range(len(author_list))
            }
            
            result = {
                'predicted_author': predicted_authors[i],
                'confidence': confidence,
                'top_predictions': top_predictions,
                'distances': distances_dict,
                'distance_metric': self.distance_metric
            }
            
            results.append(result)
        
        return results

    def incremental_update(self, author_name: str, 
                            new_features: List[np.ndarray],
                            alpha: float = 0.3) -> Dict:
        """
        增量更新作者原型（移动平均）
        
        Args:
            author_name: 作者名称
            new_features: 新的样本特征
            alpha: 更新率 (0-1)，越大越重视新样本
            
        Returns:
            更新信息
        """
        if author_name not in self.prototypes:
            raise ValueError(f"Author '{author_name}' not found. Use add_new_author() first.")
        
        scaled_new = self.scaler.transform(np.array(new_features))
        new_prototype = np.mean(scaled_new, axis=0)
        
        old_prototype = self.prototypes[author_name]
        updated_prototype = (1 - alpha) * old_prototype + alpha * new_prototype
        
        self.prototypes[author_name] = updated_prototype
        
        if author_name in self.author_samples:
            self.author_samples[author_name] = np.vstack(
                [self.author_samples[author_name], scaled_new]
            )
        else:
            self.author_samples[author_name] = scaled_new
        
        distance = float(np.sqrt(np.sum((old_prototype - updated_prototype) ** 2)))
        
        return {
            'author_name': author_name,
            'update_distance': distance,
            'alpha': alpha,
            'num_new_samples': len(new_features),
            'total_samples': len(self.author_samples[author_name])
        }

    def remove_author(self, author_name: str) -> bool:
        """
        删除作者
        
        Args:
            author_name: 作者名称
            
        Returns:
            是否成功删除
        """
        if author_name in self.prototypes:
            del self.prototypes[author_name]
            if author_name in self.author_samples:
                del self.author_samples[author_name]
            self._author_indices = {a: i for i, a in enumerate(self.prototypes.keys())}
            return True
        return False

    def compute_similarity_matrix(self) -> np.ndarray:
        """计算作者之间的相似度矩阵"""
        author_list = list(self.prototypes.keys())
        prototype_matrix = np.array([self.prototypes[author] for author in author_list])
        
        distances = self._compute_distances_batch(prototype_matrix, prototype_matrix)
        similarities = 1 / (1 + distances)
        np.fill_diagonal(similarities, 1.0)
        
        return similarities

    def evaluate(self, X: np.ndarray, y: List[str]) -> Dict[str, float]:
        """
        评估模型性能
        
        Args:
            X: 特征矩阵
            y: 真实标签
            
        Returns:
            评估指标
        """
        predictions, _ = self.predict(X)
        
        accuracy = accuracy_score(y, predictions)
        f1_macro = f1_score(y, predictions, average='macro', zero_division=0)
        f1_weighted = f1_score(y, predictions, average='weighted', zero_division=0)
        
        return {
            'accuracy': float(accuracy),
            'f1_macro': float(f1_macro),
            'f1_weighted': float(f1_weighted),
            'num_samples': len(y),
            'num_classes': len(set(y))
        }

    def save(self, path: str):
        """保存模型到文件"""
        model_data = {
            'feature_dim': self.feature_dim,
            'distance_metric': self.distance_metric,
            'scaler': self.scaler,
            'prototypes': self.prototypes,
            'author_samples': self.author_samples,
            'cov_matrix': self.cov_matrix,
            'inv_cov_matrix': self.inv_cov_matrix,
            '_fitted': self._fitted,
            '_author_indices': self._author_indices
        }
        joblib.dump(model_data, path)

    @classmethod
    def load(cls, path: str) -> 'PrototypicalNetwork':
        """从文件加载模型"""
        model_data = joblib.load(path)
        network = cls(
            feature_dim=model_data['feature_dim'],
            distance_metric=model_data['distance_metric']
        )
        network.scaler = model_data['scaler']
        network.prototypes = model_data['prototypes']
        network.author_samples = model_data['author_samples']
        network.cov_matrix = model_data['cov_matrix']
        network.inv_cov_matrix = model_data['inv_cov_matrix']
        network._fitted = model_data['_fitted']
        network._author_indices = model_data['_author_indices']
        return network

    def get_author_list(self) -> List[str]:
        """获取所有作者列表"""
        return list(self.prototypes.keys())

    def get_author_prototype(self, author_name: str) -> Optional[np.ndarray]:
        """获取作者原型向量"""
        return self.prototypes.get(author_name)

    def get_num_authors(self) -> int:
        """获取作者数量"""
        return len(self.prototypes)
