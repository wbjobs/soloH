import numpy as np
from typing import Optional, Tuple, List, Dict, Union
import warnings
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import pickle
import os

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from .preprocessing import Preprocessor
from .feature_extraction import FeatureExtractor
from .data_generator import generate_bearing_signal


class RULCNN(nn.Module):
    """用于RUL预测的1D CNN模型"""
    
    def __init__(self, n_features: int = 88, n_channels: int = 1):
        super(RULCNN, self).__init__()
        
        self.n_channels = n_channels
        
        self.conv_layers = nn.Sequential(
            nn.Conv1d(n_channels, 32, kernel_size=5, stride=2, padding=2),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.MaxPool1d(2),
            
            nn.Conv1d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(2),
            
            nn.Conv1d(64, 128, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        
        self.fc_layers = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 2:
            x = x.unsqueeze(1)
        
        x = x.transpose(1, 2)
        features = self.conv_layers(x)
        features = features.flatten(1)
        out = self.fc_layers(features)
        
        return out.squeeze(-1)


class RULPredictor:
    """
    剩余寿命预测（Remaining Useful Life）模型
    
    支持多种回归算法：
    - 随机森林回归 (random_forest)
    - 梯度提升回归 (gradient_boosting)
    - 岭回归 (ridge)
    - CNN回归 (cnn)
    
    输出：剩余寿命（小时或周期）及置信区间
    """
    
    def __init__(self, model_type: str = 'random_forest',
                 fs: float = 25600.0,
                 max_rul: float = 100.0,
                 n_estimators: int = 100,
                 random_state: int = 42):
        """
        Args:
            model_type: 回归模型类型 ('random_forest', 'gradient_boosting', 'ridge', 'cnn')
            fs: 采样频率 (Hz)
            max_rul: 最大剩余寿命（用于归一化）
            n_estimators: 集成学习树的数量
            random_state: 随机种子
        """
        self.model_type = model_type
        self.fs = fs
        self.max_rul = max_rul
        self.n_estimators = n_estimators
        self.random_state = random_state
        
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        
        self.feature_names_: List[str] = []
        
        if model_type == 'random_forest':
            self.model = RandomForestRegressor(
                n_estimators=n_estimators,
                random_state=random_state,
                n_jobs=-1
            )
        elif model_type == 'gradient_boosting':
            self.model = GradientBoostingRegressor(
                n_estimators=n_estimators,
                random_state=random_state
            )
        elif model_type == 'ridge':
            self.model = Ridge(alpha=1.0)
        elif model_type == 'cnn':
            if not TORCH_AVAILABLE:
                warnings.warn("PyTorch not available. Using random_forest instead.")
                self.model_type = 'random_forest'
                self.model = RandomForestRegressor(
                    n_estimators=n_estimators,
                    random_state=random_state,
                    n_jobs=-1
                )
            else:
                self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                self.model = None
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    def _extract_features_from_signal(self, signal_data: np.ndarray,
                                      preprocessor: Optional[Preprocessor] = None,
                                      feature_extractor: Optional[FeatureExtractor] = None) -> np.ndarray:
        """从原始信号提取特征"""
        if preprocessor is None:
            preprocessor = Preprocessor(fs=self.fs)
        if feature_extractor is None:
            feature_extractor = FeatureExtractor(fs=self.fs)
        
        processed = preprocessor.preprocess(signal_data)
        features, feature_names = feature_extractor.extract(processed)
        
        self.feature_names_ = feature_names
        return features
    
    def fit(self, X: np.ndarray, y: np.ndarray,
            X_test: Optional[np.ndarray] = None,
            y_test: Optional[np.ndarray] = None,
            epochs: int = 50,
            batch_size: int = 32,
            cv: int = 5,
            verbose: bool = True) -> 'RULPredictor':
        """
        训练RUL预测模型
        
        Args:
            X: 特征矩阵 (n_samples, n_features) 或原始信号 (n_samples, n_timesteps, n_channels)
            y: RUL标签 (n_samples,)
            X_test: 测试集特征（可选）
            y_test: 测试集标签（可选）
            epochs: CNN训练轮数
            batch_size: 批次大小
            cv: 交叉验证折数（仅传统模型）
            verbose: 是否显示训练进度
        
        Returns:
            self
        """
        if X.ndim == 3:
            if verbose:
                print("检测到原始信号输入，正在提取特征...")
            features_list = []
            for i in range(X.shape[0]):
                sig = X[i]
                if sig.ndim == 1:
                    sig = sig.reshape(-1, 1)
                feats = self._extract_features_from_signal(sig)
                features_list.append(feats.flatten())
            X = np.array(features_list)
        elif not self.feature_names_:
            self.feature_names_ = [f'feature_{i}' for i in range(X.shape[1])]
        
        y = np.clip(y, 0, self.max_rul)
        
        X_scaled = self.scaler.fit_transform(X)
        
        if self.model_type == 'cnn' and TORCH_AVAILABLE:
            n_features = X.shape[1]
            n_channels = 1
            
            self.model = RULCNN(n_features=n_features, n_channels=n_channels).to(self.device)
            
            X_tensor = torch.FloatTensor(X_scaled).unsqueeze(1).to(self.device)
            y_tensor = torch.FloatTensor(y).to(self.device)
            
            dataset = TensorDataset(X_tensor, y_tensor)
            dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
            
            optimizer = optim.Adam(self.model.parameters(), lr=0.001)
            criterion = nn.MSELoss()
            
            for epoch in range(epochs):
                self.model.train()
                total_loss = 0
                
                for batch_X, batch_y in dataloader:
                    optimizer.zero_grad()
                    outputs = self.model(batch_X)
                    loss = criterion(outputs, batch_y)
                    loss.backward()
                    optimizer.step()
                    total_loss += loss.item()
                
                avg_loss = total_loss / len(dataloader)
                
                if verbose and (epoch + 1) % 10 == 0:
                    print(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.4f}")
                    
                    if X_test is not None and y_test is not None:
                        test_pred = self.predict(X_test)
                        test_rmse = np.sqrt(mean_squared_error(y_test, test_pred))
                        print(f"  Test RMSE: {test_rmse:.4f}")
        
        else:
            self.model.fit(X_scaled, y)
            
            if cv > 1:
                cv_scores = cross_val_score(
                    self.model, X_scaled, y,
                    cv=cv,
                    scoring='neg_mean_squared_error'
                )
                cv_rmse = np.sqrt(-cv_scores)
                
                if verbose:
                    print(f"交叉验证 RMSE: {cv_rmse.mean():.4f} ± {cv_rmse.std():.4f}")
        
        self.is_trained = True
        
        if verbose and X_test is not None and y_test is not None and self.model_type != 'cnn':
            y_pred = self.predict(X_test)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            print(f"\n测试集性能:")
            print(f"  RMSE: {rmse:.4f}")
            print(f"  MAE:  {mae:.4f}")
            print(f"  R²:   {r2:.4f}")
        
        return self
    
    def predict(self, X: np.ndarray,
                return_confidence: bool = False,
                confidence_level: float = 0.95) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """
        预测剩余寿命
        
        Args:
            X: 特征矩阵或原始信号
            return_confidence: 是否返回置信区间
            confidence_level: 置信水平
        
        Returns:
            RUL预测值，或 (RUL预测值, 下限, 上限)
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call fit() first.")
        
        if X.ndim == 3 or (X.ndim == 2 and X.shape[1] != self.scaler.n_features_in_):
            features_list = []
            if X.ndim == 3:
                for i in range(X.shape[0]):
                    sig = X[i]
                    if sig.ndim == 1:
                        sig = sig.reshape(-1, 1)
                    feats = self._extract_features_from_signal(sig)
                    features_list.append(feats.flatten())
            else:
                for i in range(X.shape[0]):
                    sig = X[i].reshape(-1, 1)
                    feats = self._extract_features_from_signal(sig)
                    features_list.append(feats.flatten())
            X = np.array(features_list)
        
        X_scaled = self.scaler.transform(X)
        
        if self.model_type == 'cnn' and TORCH_AVAILABLE:
            self.model.eval()
            with torch.no_grad():
                X_tensor = torch.FloatTensor(X_scaled).unsqueeze(1).to(self.device)
                predictions = self.model(X_tensor).cpu().numpy()
        else:
            predictions = self.model.predict(X_scaled)
        
        predictions = np.clip(predictions, 0, self.max_rul)
        
        if return_confidence:
            n_samples = len(predictions)
            std_estimate = predictions * 0.1 + 0.5
            
            z_score = 1.96 if confidence_level == 0.95 else 1.645
            lower = np.clip(predictions - z_score * std_estimate, 0, self.max_rul)
            upper = np.clip(predictions + z_score * std_estimate, 0, self.max_rul)
            
            return predictions, lower, upper
        
        return predictions
    
    def predict_from_signal(self, signal_data: np.ndarray,
                           return_confidence: bool = False) -> Union[float, Tuple[float, float, float]]:
        """
        从原始信号直接预测RUL
        
        Args:
            signal_data: 原始信号 (n_samples, n_channels)
            return_confidence: 是否返回置信区间
        
        Returns:
            RUL预测值（小时）
        """
        if signal_data.ndim == 1:
            signal_data = signal_data.reshape(1, -1, 1)
        elif signal_data.ndim == 2:
            signal_data = signal_data.reshape(1, *signal_data.shape)
        
        if return_confidence:
            pred, lower, upper = self.predict(signal_data, return_confidence=True)
            return float(pred[0]), float(lower[0]), float(upper[0])
        
        pred = self.predict(signal_data)
        return float(pred[0])
    
    def get_feature_importance(self) -> Tuple[np.ndarray, List[str]]:
        """获取特征重要性"""
        if not self.is_trained:
            raise ValueError("Model not trained.")
        
        if hasattr(self.model, 'feature_importances_'):
            importance = self.model.feature_importances_
        else:
            importance = np.abs(self.model.coef_) if hasattr(self.model, 'coef_') else np.ones(len(self.feature_names_))
        
        return importance, self.feature_names_
    
    def generate_rul_dataset(self, n_samples: int = 200,
                            n_channels: int = 1,
                            duration: float = 0.5,
                            fault_type: str = 'inner_race',
                            max_rul: Optional[float] = None,
                            verbose: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        生成RUL训练数据集（模拟退化过程）
        
        Args:
            n_samples: 样本数
            n_channels: 通道数
            duration: 每个样本的时长（秒）
            fault_type: 故障类型
            max_rul: 最大剩余寿命
            verbose: 是否显示进度
        
        Returns:
            (features, rul_labels)
        """
        if max_rul is None:
            max_rul = self.max_rul
        
        features_list = []
        rul_labels = []
        
        preprocessor = Preprocessor(fs=self.fs)
        feature_extractor = FeatureExtractor(fs=self.fs)
        
        severity_levels = ['normal', 'early', 'medium', 'late']
        
        for i in range(n_samples):
            rul = np.random.uniform(0, max_rul)
            
            if rul > max_rul * 0.7:
                severity = 'normal'
            elif rul > max_rul * 0.4:
                severity = 'early'
            elif rul > max_rul * 0.15:
                severity = 'medium'
            else:
                severity = 'late'
            
            noise_level = 0.3 + (1 - rul / max_rul) * 1.0
            
            signal = generate_bearing_signal(
                fs=self.fs,
                duration=duration,
                fault_type='normal' if severity == 'normal' else fault_type,
                severity=severity,
                n_channels=n_channels,
                noise_level=noise_level,
                random_state=i
            )
            
            processed = preprocessor.preprocess(signal)
            features, feature_names = feature_extractor.extract(processed)
            
            features_list.append(features.flatten())
            rul_labels.append(rul)
            
            if not self.feature_names_:
                self.feature_names_ = feature_names
            
            if verbose and (i + 1) % 50 == 0:
                print(f"生成样本 {i+1}/{n_samples}")
        
        return np.array(features_list), np.array(rul_labels)
    
    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """
        评估模型性能
        
        Args:
            X_test: 测试集特征
            y_test: 测试集标签
        
        Returns:
            评估指标字典
        """
        y_pred = self.predict(X_test)
        
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mae = mean_absolute_error(y_test, y_pred)
        mape = np.mean(np.abs((y_test - y_pred) / np.maximum(y_test, 1e-8))) * 100
        r2 = r2_score(y_test, y_pred)
        
        return {
            'rmse': rmse,
            'mae': mae,
            'mape': mape,
            'r2': r2
        }
    
    def save(self, path: str) -> None:
        """保存模型"""
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        
        if self.model_type == 'cnn' and TORCH_AVAILABLE:
            torch.save({
                'model_state_dict': self.model.state_dict(),
                'scaler': self.scaler,
                'model_type': self.model_type,
                'fs': self.fs,
                'max_rul': self.max_rul,
                'is_trained': self.is_trained,
                'feature_names_': self.feature_names_
            }, path)
        else:
            with open(path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'scaler': self.scaler,
                    'model_type': self.model_type,
                    'fs': self.fs,
                    'max_rul': self.max_rul,
                    'is_trained': self.is_trained,
                    'feature_names_': self.feature_names_
                }, f)
    
    def load(self, path: str) -> 'RULPredictor':
        """加载模型"""
        if path.endswith('.pt') or path.endswith('.pth'):
            checkpoint = torch.load(path, map_location='cpu')
            self.model_type = checkpoint['model_type']
            self.fs = checkpoint['fs']
            self.max_rul = checkpoint['max_rul']
            self.is_trained = checkpoint['is_trained']
            self.feature_names_ = checkpoint['feature_names_']
            self.scaler = checkpoint['scaler']
            
            if TORCH_AVAILABLE and self.model_type == 'cnn':
                self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                n_features = len(self.feature_names_)
                self.model = RULCNN(n_features=n_features).to(self.device)
                self.model.load_state_dict(checkpoint['model_state_dict'])
        else:
            with open(path, 'rb') as f:
                checkpoint = pickle.load(f)
            
            self.model = checkpoint['model']
            self.scaler = checkpoint['scaler']
            self.model_type = checkpoint['model_type']
            self.fs = checkpoint['fs']
            self.max_rul = checkpoint['max_rul']
            self.is_trained = checkpoint['is_trained']
            self.feature_names_ = checkpoint['feature_names_']
        
        return self
