import numpy as np
from typing import Optional, Tuple, Dict, Union, List
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm
import warnings


FAULT_TYPES = ['normal', 'inner_race', 'outer_race', 'rolling_element', 'cage']
SEVERITY_LEVELS = ['normal', 'early', 'medium', 'late']


class CNN1D(nn.Module):
    """1D CNN 分类器，用于处理原始信号或特征序列"""
    
    def __init__(self, n_channels: int, n_classes_type: int = 5,
                 n_classes_severity: int = 4,
                 n_features: Optional[int] = None):
        """
        Args:
            n_channels: 输入通道数
            n_classes_type: 故障类型类别数
            n_classes_severity: 严重程度类别数
            n_features: 特征数量（如果输入是特征向量而非原始信号）
        """
        super(CNN1D, self).__init__()
        
        self.use_raw_signal = n_features is None
        
        if self.use_raw_signal:
            self.feature_extractor = nn.Sequential(
                nn.Conv1d(n_channels, 32, kernel_size=7, stride=2, padding=3),
                nn.BatchNorm1d(32),
                nn.ReLU(),
                nn.MaxPool1d(2),
                
                nn.Conv1d(32, 64, kernel_size=5, stride=2, padding=2),
                nn.BatchNorm1d(64),
                nn.ReLU(),
                nn.MaxPool1d(2),
                
                nn.Conv1d(64, 128, kernel_size=3, stride=2, padding=1),
                nn.BatchNorm1d(128),
                nn.ReLU(),
                nn.MaxPool1d(2),
                
                nn.Conv1d(128, 256, kernel_size=3, stride=2, padding=1),
                nn.BatchNorm1d(256),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.fc_input_dim = 256
        else:
            self.feature_extractor = nn.Sequential(
                nn.Linear(n_features, 512),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(512, 256),
                nn.ReLU(),
                nn.Dropout(0.3),
            )
            self.fc_input_dim = 256
        
        self.type_classifier = nn.Sequential(
            nn.Linear(self.fc_input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, n_classes_type)
        )
        
        self.severity_classifier = nn.Sequential(
            nn.Linear(self.fc_input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, n_classes_severity)
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        if self.use_raw_signal:
            x = x.transpose(1, 2)
        
        features = self.feature_extractor(x)
        
        if self.use_raw_signal:
            features = features.flatten(1)
        
        type_out = self.type_classifier(features)
        severity_out = self.severity_classifier(features)
        
        return type_out, severity_out


class RandomForestModel:
    """随机森林分类器封装"""
    
    def __init__(self, n_estimators: int = 200, max_depth: Optional[int] = None,
                 min_samples_split: int = 2, random_state: int = 42):
        """
        Args:
            n_estimators: 树的数量
            max_depth: 最大深度
            min_samples_split: 最小分裂样本数
            random_state: 随机种子
        """
        self.type_classifier = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            random_state=random_state,
            n_jobs=-1
        )
        
        self.severity_classifier = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            random_state=random_state,
            n_jobs=-1
        )
        
        self.scaler = StandardScaler()
        self.feature_importances_: Optional[np.ndarray] = None
    
    def fit(self, X: np.ndarray, y_type: np.ndarray, y_severity: np.ndarray,
            cv: Optional[int] = None) -> Dict:
        """
        训练模型
        
        Args:
            X: 特征矩阵 (n_samples, n_features)
            y_type: 故障类型标签
            y_severity: 严重程度标签
            cv: 交叉验证折数
        
        Returns:
            训练结果字典
        """
        X_scaled = self.scaler.fit_transform(X)
        
        results = {}
        
        if cv is not None:
            type_scores = cross_val_score(self.type_classifier, X_scaled, y_type, cv=cv)
            severity_scores = cross_val_score(self.severity_classifier, X_scaled, y_severity, cv=cv)
            results['cv_type_accuracy'] = type_scores.mean()
            results['cv_type_std'] = type_scores.std()
            results['cv_severity_accuracy'] = severity_scores.mean()
            results['cv_severity_std'] = severity_scores.std()
        
        self.type_classifier.fit(X_scaled, y_type)
        self.severity_classifier.fit(X_scaled, y_severity)
        
        type_importance = self.type_classifier.feature_importances_
        severity_importance = self.severity_classifier.feature_importances_
        self.feature_importances_ = (type_importance + severity_importance) / 2
        
        results['train_type_accuracy'] = self.type_classifier.score(X_scaled, y_type)
        results['train_severity_accuracy'] = self.severity_classifier.score(X_scaled, y_severity)
        
        return results
    
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        预测
        
        Args:
            X: 特征矩阵 (n_samples, n_features)
        
        Returns:
            (type_pred, type_proba, severity_pred, severity_proba)
        """
        X_scaled = self.scaler.transform(X)
        
        type_pred = self.type_classifier.predict(X_scaled)
        type_proba = self.type_classifier.predict_proba(X_scaled)
        
        severity_pred = self.severity_classifier.predict(X_scaled)
        severity_proba = self.severity_classifier.predict_proba(X_scaled)
        
        return type_pred, type_proba, severity_pred, severity_proba


class CNNModel:
    """CNN分类器封装"""
    
    def __init__(self, n_channels: int, n_features: Optional[int] = None,
                 n_classes_type: int = 5, n_classes_severity: int = 4,
                 device: Optional[str] = None, learning_rate: float = 1e-3,
                 batch_size: int = 32, epochs: int = 50):
        """
        Args:
            n_channels: 输入通道数
            n_features: 特征数量（None表示使用原始信号）
            n_classes_type: 故障类型类别数
            n_classes_severity: 严重程度类别数
            device: 计算设备 ('cuda' 或 'cpu')
            learning_rate: 学习率
            batch_size: 批次大小
            epochs: 训练轮数
        """
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        
        self.model = CNN1D(
            n_channels=n_channels,
            n_classes_type=n_classes_type,
            n_classes_severity=n_classes_severity,
            n_features=n_features
        ).to(self.device)
        
        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        self.scaler = StandardScaler()
        self.use_raw_signal = n_features is None
    
    def fit(self, X: np.ndarray, y_type: np.ndarray, y_severity: np.ndarray,
            X_val: Optional[np.ndarray] = None,
            y_val_type: Optional[np.ndarray] = None,
            y_val_severity: Optional[np.ndarray] = None) -> Dict:
        """
        训练模型
        
        Args:
            X: 训练数据 (n_samples, n_channels) 或 (n_samples, n_features)
            y_type: 故障类型标签
            y_severity: 严重程度标签
            X_val: 验证数据
            y_val_type: 验证集类型标签
            y_val_severity: 验证集严重程度标签
        
        Returns:
            训练历史字典
        """
        if not self.use_raw_signal:
            X = self.scaler.fit_transform(X)
            if X_val is not None:
                X_val = self.scaler.transform(X_val)
        
        if X.ndim == 2 and self.use_raw_signal:
            X = X.reshape(X.shape[0], 1, X.shape[1])
        
        X_tensor = torch.FloatTensor(X).to(self.device)
        y_type_tensor = torch.LongTensor(y_type).to(self.device)
        y_severity_tensor = torch.LongTensor(y_severity).to(self.device)
        
        dataset = TensorDataset(X_tensor, y_type_tensor, y_severity_tensor)
        dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        
        history = {'train_loss': [], 'train_type_acc': [], 'train_severity_acc': []}
        
        if X_val is not None:
            if X_val.ndim == 2 and self.use_raw_signal:
                X_val = X_val.reshape(X_val.shape[0], 1, X_val.shape[1])
            X_val_tensor = torch.FloatTensor(X_val).to(self.device)
            y_val_type_tensor = torch.LongTensor(y_val_type).to(self.device)
            y_val_severity_tensor = torch.LongTensor(y_val_severity).to(self.device)
            history.update({'val_loss': [], 'val_type_acc': [], 'val_severity_acc': []})
        
        for epoch in tqdm(range(self.epochs), desc='Training CNN'):
            self.model.train()
            total_loss = 0
            correct_type = 0
            correct_severity = 0
            total = 0
            
            for batch_X, batch_y_type, batch_y_severity in dataloader:
                self.optimizer.zero_grad()
                
                type_out, severity_out = self.model(batch_X)
                
                loss_type = self.criterion(type_out, batch_y_type)
                loss_severity = self.criterion(severity_out, batch_y_severity)
                loss = loss_type + loss_severity
                
                loss.backward()
                self.optimizer.step()
                
                total_loss += loss.item()
                total += batch_X.size(0)
                
                _, pred_type = torch.max(type_out, 1)
                _, pred_severity = torch.max(severity_out, 1)
                correct_type += (pred_type == batch_y_type).sum().item()
                correct_severity += (pred_severity == batch_y_severity).sum().item()
            
            avg_loss = total_loss / len(dataloader)
            type_acc = correct_type / total
            severity_acc = correct_severity / total
            
            history['train_loss'].append(avg_loss)
            history['train_type_acc'].append(type_acc)
            history['train_severity_acc'].append(severity_acc)
            
            if X_val is not None:
                self.model.eval()
                with torch.no_grad():
                    type_out, severity_out = self.model(X_val_tensor)
                    loss_type = self.criterion(type_out, y_val_type_tensor)
                    loss_severity = self.criterion(severity_out, y_val_severity_tensor)
                    val_loss = (loss_type + loss_severity).item()
                    
                    _, pred_type = torch.max(type_out, 1)
                    _, pred_severity = torch.max(severity_out, 1)
                    val_type_acc = (pred_type == y_val_type_tensor).float().mean().item()
                    val_severity_acc = (pred_severity == y_val_severity_tensor).float().mean().item()
                
                history['val_loss'].append(val_loss)
                history['val_type_acc'].append(val_type_acc)
                history['val_severity_acc'].append(val_severity_acc)
        
        return history
    
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        预测
        
        Args:
            X: 输入数据
        
        Returns:
            (type_pred, type_proba, severity_pred, severity_proba)
        """
        self.model.eval()
        
        if not self.use_raw_signal:
            X = self.scaler.transform(X)
        
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        if X.ndim == 2 and self.use_raw_signal:
            X = X.reshape(X.shape[0], 1, X.shape[1])
        
        X_tensor = torch.FloatTensor(X).to(self.device)
        
        with torch.no_grad():
            type_out, severity_out = self.model(X_tensor)
            
            type_proba = torch.softmax(type_out, dim=1).cpu().numpy()
            severity_proba = torch.softmax(severity_out, dim=1).cpu().numpy()
            
            type_pred = np.argmax(type_proba, axis=1)
            severity_pred = np.argmax(severity_proba, axis=1)
        
        return type_pred, type_proba, severity_pred, severity_proba
    
    def save(self, path: str) -> None:
        """保存模型"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scaler': self.scaler,
            'use_raw_signal': self.use_raw_signal
        }, path)
    
    def load(self, path: str) -> None:
        """加载模型"""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.scaler = checkpoint['scaler']
        self.use_raw_signal = checkpoint['use_raw_signal']


class BearingClassifier:
    """轴承故障分类器 - 支持随机森林和CNN"""
    
    def __init__(self, classifier_type: str = 'random_forest', **kwargs):
        """
        Args:
            classifier_type: 分类器类型 ('random_forest' 或 'cnn')
            **kwargs: 传递给具体分类器的参数
        """
        self.classifier_type = classifier_type
        self.classes_type_ = FAULT_TYPES
        self.classes_severity_ = SEVERITY_LEVELS
        self._model = None
        self._model_kwargs = kwargs
    
    def _init_model(self, n_channels: Optional[int] = None,
                   n_features: Optional[int] = None) -> None:
        """初始化模型"""
        if self.classifier_type == 'random_forest':
            self._model = RandomForestModel(**self._model_kwargs)
        elif self.classifier_type == 'cnn':
            if n_channels is None:
                n_channels = 1
            self._model = CNNModel(
                n_channels=n_channels,
                n_features=n_features,
                **self._model_kwargs
            )
        else:
            raise ValueError(f"未知的分类器类型: {self.classifier_type}")
    
    def fit(self, X: np.ndarray, y_type: Union[np.ndarray, List[str]],
            y_severity: Union[np.ndarray, List[str]], **kwargs) -> Dict:
        """
        训练模型
        
        Args:
            X: 特征矩阵 (n_samples, n_features) 或原始信号
            y_type: 故障类型标签（字符串或整数）
            y_severity: 严重程度标签（字符串或整数）
            **kwargs: 其他训练参数
        
        Returns:
            训练结果字典
        """
        y_type_encoded = self._encode_labels(y_type, self.classes_type_)
        y_severity_encoded = self._encode_labels(y_severity, self.classes_severity_)
        
        if self._model is None:
            if X.ndim == 3:
                n_channels = X.shape[1]
                n_features = None
            else:
                n_channels = 1
                n_features = X.shape[1] if X.ndim > 1 else X.shape[0]
            self._init_model(n_channels=n_channels, n_features=n_features)
        
        return self._model.fit(X, y_type_encoded, y_severity_encoded, **kwargs)
    
    def predict(self, X: np.ndarray,
                multi_fault_threshold: float = 0.15,
                detect_multiple: bool = True) -> Dict:
        """
        预测（支持多故障检测）
        
        Args:
            X: 输入数据
            multi_fault_threshold: 多故障检测的概率阈值（默认15%）
            detect_multiple: 是否启用多故障检测
        
        Returns:
            预测结果字典，包含多故障信息
        """
        type_pred, type_proba, severity_pred, severity_proba = self._model.predict(X)
        
        n_samples = type_proba.shape[0]
        
        results = {
            'fault_type': [self.classes_type_[int(p)] for p in type_pred],
            'fault_type_probability': type_proba.max(axis=1),
            'fault_type_probabilities': {
                cls: type_proba[:, i] for i, cls in enumerate(self.classes_type_)
            },
            'severity': [self.classes_severity_[int(p)] for p in severity_pred],
            'severity_probability': severity_proba.max(axis=1),
            'severity_probabilities': {
                cls: severity_proba[:, i] for i, cls in enumerate(self.classes_severity_)
            }
        }
        
        if detect_multiple:
            all_faults = []
            all_faults_proba = []
            all_faults_list = []
            
            fault_classes = [c for c in self.classes_type_ if c != 'normal']
            fault_indices = [i for i, c in enumerate(self.classes_type_) if c != 'normal']
            
            for i in range(n_samples):
                sample_probs = type_proba[i, fault_indices]
                detected = [fault_classes[j] for j, p in enumerate(sample_probs) if p >= multi_fault_threshold]
                detected_probs = [float(sample_probs[j]) for j, p in enumerate(sample_probs) if p >= multi_fault_threshold]
                
                sorted_pairs = sorted(zip(detected, detected_probs), key=lambda x: x[1], reverse=True)
                sorted_faults = [f for f, _ in sorted_pairs]
                sorted_probs = [p for _, p in sorted_pairs]
                
                if len(sorted_faults) == 0:
                    sorted_faults = ['normal']
                    normal_idx = self.classes_type_.index('normal')
                    sorted_probs = [float(type_proba[i, normal_idx])]
                
                all_faults.append(sorted_faults)
                all_faults_proba.append(sorted_probs)
                all_faults_list.append([
                    {'fault_type': f, 'probability': p}
                    for f, p in zip(sorted_faults, sorted_probs)
                ])
            
            results['all_detected_faults'] = all_faults
            results['all_detected_probabilities'] = all_faults_proba
            results['multi_fault_details'] = all_faults_list
            results['is_multi_fault'] = [len(f) > 1 for f in all_faults]
        
        return results
    
    def predict_single(self, X: np.ndarray,
                      multi_fault_threshold: float = 0.15,
                      detect_multiple: bool = True) -> Dict:
        """
        预测单个样本（支持多故障检测）
        
        Args:
            X: 输入数据
            multi_fault_threshold: 多故障检测阈值
            detect_multiple: 是否启用多故障检测
        
        Returns:
            预测结果字典
        """
        results = self.predict(
            X.reshape(1, -1) if X.ndim == 1 else X,
            multi_fault_threshold=multi_fault_threshold,
            detect_multiple=detect_multiple
        )
        
        output = {
            'fault_type': results['fault_type'][0],
            'fault_type_probability': float(results['fault_type_probability'][0]),
            'fault_type_probabilities': {
                k: float(v[0]) for k, v in results['fault_type_probabilities'].items()
            },
            'severity': results['severity'][0],
            'severity_probability': float(results['severity_probability'][0]),
            'severity_probabilities': {
                k: float(v[0]) for k, v in results['severity_probabilities'].items()
            }
        }
        
        if detect_multiple:
            output['all_detected_faults'] = results['all_detected_faults'][0]
            output['all_detected_probabilities'] = results['all_detected_probabilities'][0]
            output['multi_fault_details'] = results['multi_fault_details'][0]
            output['is_multi_fault'] = bool(results['is_multi_fault'][0])
        
        return output
    
    def detect_multi_fault_from_features(self, feature_values: np.ndarray,
                                        feature_names: List[str],
                                        threshold: float = 0.5) -> Dict:
        """
        基于特征值规则的多故障辅助检测
        用于补充模型检测，提高多故障识别率
        
        Args:
            feature_values: 特征值数组
            feature_names: 特征名称列表
            threshold: 检测阈值
        
        Returns:
            各故障的可能性得分
        """
        fault_scores = {
            'inner_race': 0.0,
            'outer_race': 0.0,
            'rolling_element': 0.0,
            'cage': 0.0
        }
        
        fault_prefixes = {
            'inner_race': 'bpfi',
            'outer_race': 'bpfo',
            'rolling_element': 'bsf',
            'cage': 'ftf'
        }
        
        feature_dict = dict(zip(feature_names, feature_values))
        
        for fault, prefix in fault_prefixes.items():
            energy_key = f'freq_{prefix}_energy_ratio'
            if energy_key in feature_dict:
                fault_scores[fault] += feature_dict[energy_key] * 2
            
            for h in range(1, 5):
                amp_key = f'freq_{prefix}_{h}x_amp_norm'
                if amp_key in feature_dict:
                    fault_scores[fault] += feature_dict[amp_key]
        
        max_score = max(fault_scores.values()) if max(fault_scores.values()) > 0 else 1.0
        normalized_scores = {k: v / max_score for k, v in fault_scores.items()}
        
        detected = [
            {'fault_type': k, 'score': v, 'detected': v >= threshold}
            for k, v in normalized_scores.items()
            if v >= threshold
        ]
        
        return {
            'fault_scores': normalized_scores,
            'detected_faults': sorted(detected, key=lambda x: x['score'], reverse=True)
        }
    
    def get_feature_importance(self) -> Optional[np.ndarray]:
        """获取特征重要性（仅随机森林）"""
        if hasattr(self._model, 'feature_importances_'):
            return self._model.feature_importances_
        return None
    
    def _encode_labels(self, labels: Union[np.ndarray, List[str]],
                      classes: List[str]) -> np.ndarray:
        """标签编码"""
        if isinstance(labels, np.ndarray) and np.issubdtype(labels.dtype, np.integer):
            return labels
        
        label_to_idx = {cls: idx for idx, cls in enumerate(classes)}
        return np.array([label_to_idx[label] for label in labels])
    
    def save(self, path: str) -> None:
        """保存模型"""
        if self.classifier_type == 'cnn':
            self._model.save(path)
        else:
            import joblib
            joblib.dump(self._model, path)
    
    def load(self, path: str, n_channels: int = 1,
             n_features: Optional[int] = None) -> None:
        """加载模型"""
        self._init_model(n_channels=n_channels, n_features=n_features)
        
        if self.classifier_type == 'cnn':
            self._model.load(path)
        else:
            import joblib
            self._model = joblib.load(path)
