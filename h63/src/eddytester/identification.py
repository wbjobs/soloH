import numpy as np
import joblib
from typing import List, Tuple, Dict, Optional, Union
from sklearn.svm import SVC, SVR
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, mean_squared_error, classification_report
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.pipeline import Pipeline
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from .config import Config
from .data_io import EddyCurrentData
from .features import FeatureExtractor
from .preprocessing import Preprocessor


class SVMClassifier:
    def __init__(self, kernel: str = Config.SVM_KERNEL, C: float = 1.0, gamma: str = 'scale'):
        self.kernel = kernel
        self.C = C
        self.gamma = gamma
        self.pipeline = None
        self.feature_extractor = FeatureExtractor()

    def _prepare_features(self, data_list: List[EddyCurrentData]) -> np.ndarray:
        features = []
        for data in data_list:
            feat = self.feature_extractor.extract_single(data)
            features.append(feat)
        return np.array(features)

    def _prepare_labels(self, data_list: List[EddyCurrentData]) -> np.ndarray:
        labels = []
        for data in data_list:
            if data.labels is not None and data.labels.ndim >= 2:
                has_crack = np.max(data.labels[:, 0]) > 0.5
                labels.append(1 if has_crack else 0)
            else:
                labels.append(0)
        return np.array(labels)

    def fit(self, data_list: List[EddyCurrentData]) -> 'SVMClassifier':
        X = self._prepare_features(data_list)
        y = self._prepare_labels(data_list)
        
        self.pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('svm', SVC(kernel=self.kernel, C=self.C, gamma=self.gamma,
                        probability=True, random_state=Config.RANDOM_SEED))
        ])
        
        self.pipeline.fit(X, y)
        return self

    def predict(self, data: Union[EddyCurrentData, List[EddyCurrentData]]) -> np.ndarray:
        if isinstance(data, EddyCurrentData):
            data = [data]
        
        X = self._prepare_features(data)
        return self.pipeline.predict(X)

    def predict_proba(self, data: Union[EddyCurrentData, List[EddyCurrentData]]) -> np.ndarray:
        if isinstance(data, EddyCurrentData):
            data = [data]
        
        X = self._prepare_features(data)
        return self.pipeline.predict_proba(X)

    def score(self, data_list: List[EddyCurrentData]) -> float:
        X = self._prepare_features(data_list)
        y = self._prepare_labels(data_list)
        return self.pipeline.score(X, y)

    def save(self, filepath: str) -> None:
        joblib.dump(self.pipeline, filepath)

    def load(self, filepath: str) -> 'SVMClassifier':
        self.pipeline = joblib.load(filepath)
        return self


class SVMRegressor:
    def __init__(self, kernel: str = 'rbf', C: float = 1.0, epsilon: float = 0.1):
        self.kernel = kernel
        self.C = C
        self.epsilon = epsilon
        self.pipelines = {}
        self.feature_extractor = FeatureExtractor()

    def _prepare_features(self, data_list: List[EddyCurrentData]) -> np.ndarray:
        features = []
        for data in data_list:
            feat = self.feature_extractor.extract_single(data)
            features.append(feat)
        return np.array(features)

    def _prepare_targets(self, data_list: List[EddyCurrentData], target: str = 'depth') -> np.ndarray:
        targets = []
        for data in data_list:
            if data.labels is not None and data.labels.ndim >= 2:
                if target == 'depth':
                    val = np.max(data.labels[:, 1])
                elif target == 'length':
                    val = np.max(data.labels[:, 2])
                elif target == 'position':
                    val = data.labels[0, 3] if len(data.labels) > 0 else 0
                else:
                    val = 0
                targets.append(val)
            else:
                targets.append(0)
        return np.array(targets)

    def fit(self, data_list: List[EddyCurrentData], targets: List[str] = None) -> 'SVMRegressor':
        targets = targets or ['depth', 'length', 'position']
        X = self._prepare_features(data_list)
        
        for target in targets:
            y = self._prepare_targets(data_list, target)
            
            pipeline = Pipeline([
                ('scaler', StandardScaler()),
                ('svr', SVR(kernel=self.kernel, C=self.C, epsilon=self.epsilon))
            ])
            
            pipeline.fit(X, y)
            self.pipelines[target] = pipeline
        
        return self

    def predict(self, data: Union[EddyCurrentData, List[EddyCurrentData]], target: str = 'depth') -> np.ndarray:
        if isinstance(data, EddyCurrentData):
            data = [data]
        
        X = self._prepare_features(data)
        
        if target not in self.pipelines:
            raise ValueError(f"No trained model for target: {target}")
        
        return self.pipelines[target].predict(X)

    def predict_all(self, data: Union[EddyCurrentData, List[EddyCurrentData]]) -> Dict[str, np.ndarray]:
        if isinstance(data, EddyCurrentData):
            data = [data]
        
        X = self._prepare_features(data)
        results = {}
        
        for target, pipeline in self.pipelines.items():
            results[target] = pipeline.predict(X)
        
        return results

    def score(self, data_list: List[EddyCurrentData], target: str = 'depth') -> float:
        X = self._prepare_features(data_list)
        y = self._prepare_targets(data_list, target)
        return self.pipelines[target].score(X, y)

    def save(self, filepath: str) -> None:
        joblib.dump(self.pipelines, filepath)

    def load(self, filepath: str) -> 'SVMRegressor':
        self.pipelines = joblib.load(filepath)
        return self


if TORCH_AVAILABLE:
    class EddyCurrentCNN(nn.Module):
        def __init__(self, n_freqs: int = 4, n_points: int = 500, dropout: float = 0.3):
            super().__init__()
            
            self.conv1 = nn.Conv1d(2 * n_freqs, 32, kernel_size=7, padding=3)
            self.bn1 = nn.BatchNorm1d(32)
            self.pool1 = nn.MaxPool1d(2)
            
            self.conv2 = nn.Conv1d(32, 64, kernel_size=5, padding=2)
            self.bn2 = nn.BatchNorm1d(64)
            self.pool2 = nn.MaxPool1d(2)
            
            self.conv3 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
            self.bn3 = nn.BatchNorm1d(128)
            self.pool3 = nn.MaxPool1d(2)
            
            self.conv4 = nn.Conv1d(128, 128, kernel_size=3, padding=1)
            self.bn4 = nn.BatchNorm1d(128)
            self.pool4 = nn.MaxPool1d(2)
            
            self.dropout = nn.Dropout(dropout)
            
            self._calculate_flat_size(n_points)
            
            self.fc1 = nn.Linear(self.flat_size, 256)
            self.fc2 = nn.Linear(256, 128)
            
            self.classifier = nn.Linear(128, 2)
            self.regressor_depth = nn.Linear(128, 1)
            self.regressor_length = nn.Linear(128, 1)

        def _calculate_flat_size(self, n_points: int):
            x = torch.randn(1, 8, n_points)
            x = self.pool1(torch.relu(self.bn1(self.conv1(x))))
            x = self.pool2(torch.relu(self.bn2(self.conv2(x))))
            x = self.pool3(torch.relu(self.bn3(self.conv3(x))))
            x = self.pool4(torch.relu(self.bn4(self.conv4(x))))
            self.flat_size = x.size(1) * x.size(2)

        def forward(self, x):
            x = self.pool1(torch.relu(self.bn1(self.conv1(x))))
            x = self.pool2(torch.relu(self.bn2(self.conv2(x))))
            x = self.pool3(torch.relu(self.bn3(self.conv3(x))))
            x = self.pool4(torch.relu(self.bn4(self.conv4(x))))
            
            x = x.flatten(1)
            x = self.dropout(x)
            
            x = torch.relu(self.fc1(x))
            x = self.dropout(x)
            features = torch.relu(self.fc2(x))
            
            class_logits = self.classifier(features)
            depth_pred = self.regressor_depth(features).squeeze(-1)
            length_pred = self.regressor_length(features).squeeze(-1)
            
            return class_logits, depth_pred, length_pred


class EddyCurrentDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = self._prepare_input(X)
        self.y = y
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def _prepare_input(self, X: np.ndarray) -> np.ndarray:
        n_samples, n_points, n_freqs = X.shape
        X_real = np.real(X)
        X_imag = np.imag(X)
        return np.concatenate([X_real, X_imag], axis=2).transpose(0, 2, 1)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        x = torch.tensor(self.X[idx], dtype=torch.float32)
        y_cls = torch.tensor(int(self.y[idx, 0] > 0.5), dtype=torch.long)
        y_depth = torch.tensor(self.y[idx, 1], dtype=torch.float32)
        y_length = torch.tensor(self.y[idx, 2], dtype=torch.float32)
        return x, (y_cls, y_depth, y_length)


class CNNModel:
    def __init__(self, n_freqs: int = 4, n_points: int = 500, device: Optional[str] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is not available. Install with: pip install torch")
        
        self.device = torch.device(device if device else ('cuda' if torch.cuda.is_available() else 'cpu'))
        self.model = EddyCurrentCNN(n_freqs=n_freqs, n_points=n_points).to(self.device)
        self.n_freqs = n_freqs
        self.n_points = n_points
        self.preprocessor = Preprocessor(normalize=False)
        self.trained = False

    def _prepare_array(self, X: np.ndarray) -> np.ndarray:
        if X.ndim == 2:
            X = X[np.newaxis, ...]
        
        if X.shape[2] != self.n_freqs:
            raise ValueError(f"Expected {self.n_freqs} frequencies, got {X.shape[2]}")
        
        if X.shape[1] != self.n_points:
            X = self._interpolate(X, self.n_points)
        
        return X

    def _interpolate(self, X: np.ndarray, target_len: int) -> np.ndarray:
        from scipy import interpolate
        n_samples, n_points, n_freqs = X.shape
        result = np.zeros((n_samples, target_len, n_freqs), dtype=complex)
        
        for i in range(n_samples):
            for j in range(n_freqs):
                x_old = np.linspace(0, 1, n_points)
                x_new = np.linspace(0, 1, target_len)
                
                f_real = interpolate.interp1d(x_old, np.real(X[i, :, j]), kind='linear')
                f_imag = interpolate.interp1d(x_old, np.imag(X[i, :, j]), kind='linear')
                
                result[i, :, j] = f_real(x_new) + 1j * f_imag(x_new)
        
        return result

    def _prepare_input_tensor(self, X: np.ndarray) -> torch.Tensor:
        X = self._prepare_array(X)
        X_real = np.real(X)
        X_imag = np.imag(X)
        X_input = np.concatenate([X_real, X_imag], axis=2).transpose(0, 2, 1)
        return torch.tensor(X_input, dtype=torch.float32).to(self.device)

    def fit(self,
            X_train: np.ndarray,
            y_train: np.ndarray,
            X_val: Optional[np.ndarray] = None,
            y_val: Optional[np.ndarray] = None,
            epochs: int = Config.CNN_EPOCHS,
            batch_size: int = Config.CNN_BATCH_SIZE,
            lr: float = 0.001) -> Dict[str, List[float]]:
        
        X_train = self._prepare_array(X_train)
        
        if X_val is not None:
            X_val = self._prepare_array(X_val)
        
        train_dataset = EddyCurrentDataset(X_train, y_train)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        
        val_loader = None
        if X_val is not None and y_val is not None:
            val_dataset = EddyCurrentDataset(X_val, y_val)
            val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        optimizer = optim.Adam(self.model.parameters(), lr=lr)
        criterion_cls = nn.CrossEntropyLoss()
        criterion_reg = nn.MSELoss()
        
        history = {'train_loss': [], 'train_acc': [], 'val_loss': [], 'val_acc': []}
        
        for epoch in range(epochs):
            self.model.train()
            total_loss = 0
            correct = 0
            total = 0
            
            for batch_x, (batch_cls, batch_depth, batch_length) in train_loader:
                batch_x = batch_x.to(self.device)
                batch_cls = batch_cls.to(self.device)
                batch_depth = batch_depth.to(self.device)
                batch_length = batch_length.to(self.device)
                
                optimizer.zero_grad()
                
                cls_logits, depth_pred, length_pred = self.model(batch_x)
                
                has_crack = batch_cls == 1
                loss_cls = criterion_cls(cls_logits, batch_cls)
                
                loss_depth = torch.tensor(0.0, device=self.device)
                loss_length = torch.tensor(0.0, device=self.device)
                
                if has_crack.sum() > 0:
                    loss_depth = criterion_reg(depth_pred[has_crack], batch_depth[has_crack])
                    loss_length = criterion_reg(length_pred[has_crack], batch_length[has_crack])
                
                loss = loss_cls + 0.5 * loss_depth + 0.3 * loss_length
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
                _, predicted = torch.max(cls_logits.data, 1)
                total += batch_cls.size(0)
                correct += (predicted == batch_cls).sum().item()
            
            avg_loss = total_loss / len(train_loader)
            avg_acc = correct / total
            history['train_loss'].append(avg_loss)
            history['train_acc'].append(avg_acc)
            
            if val_loader:
                self.model.eval()
                val_loss = 0
                val_correct = 0
                val_total = 0
                
                with torch.no_grad():
                    for batch_x, (batch_cls, batch_depth, batch_length) in val_loader:
                        batch_x = batch_x.to(self.device)
                        batch_cls = batch_cls.to(self.device)
                        batch_depth = batch_depth.to(self.device)
                        batch_length = batch_length.to(self.device)
                        
                        cls_logits, depth_pred, length_pred = self.model(batch_x)
                        
                        has_crack = batch_cls == 1
                        loss_cls = criterion_cls(cls_logits, batch_cls)
                        
                        loss_depth = torch.tensor(0.0, device=self.device)
                        loss_length = torch.tensor(0.0, device=self.device)
                        
                        if has_crack.sum() > 0:
                            loss_depth = criterion_reg(depth_pred[has_crack], batch_depth[has_crack])
                            loss_length = criterion_reg(length_pred[has_crack], batch_length[has_crack])
                        
                        loss = loss_cls + 0.5 * loss_depth + 0.3 * loss_length
                        val_loss += loss.item()
                        
                        _, predicted = torch.max(cls_logits.data, 1)
                        val_total += batch_cls.size(0)
                        val_correct += (predicted == batch_cls).sum().item()
                
                avg_val_loss = val_loss / len(val_loader)
                avg_val_acc = val_correct / val_total
                history['val_loss'].append(avg_val_loss)
                history['val_acc'].append(avg_val_acc)
                
                print(f"Epoch {epoch+1}/{epochs}: train_loss={avg_loss:.4f}, train_acc={avg_acc:.4f}, "
                      f"val_loss={avg_val_loss:.4f}, val_acc={avg_val_acc:.4f}")
            else:
                print(f"Epoch {epoch+1}/{epochs}: train_loss={avg_loss:.4f}, train_acc={avg_acc:.4f}")
        
        self.trained = True
        return history

    def predict(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        if not self.trained:
            raise ValueError("Model not trained. Call fit() first.")
        
        self.model.eval()
        X_tensor = self._prepare_input_tensor(X)
        
        with torch.no_grad():
            cls_logits, depth_pred, length_pred = self.model(X_tensor)
            
            probs = torch.softmax(cls_logits, dim=1)
            _, predicted = torch.max(cls_logits.data, 1)
        
        return {
            'has_crack': predicted.cpu().numpy(),
            'confidence': probs[:, 1].cpu().numpy(),
            'depth': depth_pred.cpu().numpy(),
            'length': length_pred.cpu().numpy(),
        }

    def predict_single(self, data: EddyCurrentData) -> Dict[str, float]:
        X = data.impedance[np.newaxis, ...]
        result = self.predict(X)
        return {
            'has_crack': bool(result['has_crack'][0]),
            'confidence': float(result['confidence'][0]),
            'depth': float(result['depth'][0]),
            'length': float(result['length'][0]),
        }

    def save(self, filepath: str) -> None:
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'n_freqs': self.n_freqs,
            'n_points': self.n_points,
        }, filepath)

    def load(self, filepath: str) -> 'CNNModel':
        checkpoint = torch.load(filepath, map_location=self.device)
        self.n_freqs = checkpoint.get('n_freqs', self.n_freqs)
        self.n_points = checkpoint.get('n_points', self.n_points)
        self.model = EddyCurrentCNN(n_freqs=self.n_freqs, n_points=self.n_points).to(self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.trained = True
        return self


class CrackIdentifier:
    def __init__(self, method: str = 'svm', use_cnn: bool = False):
        self.method = method
        self.classifier = SVMClassifier()
        self.regressor = SVMRegressor()
        self.cnn = CNNModel() if (use_cnn and TORCH_AVAILABLE) else None
        self.preprocessor = Preprocessor()
        self.is_trained = False

    def fit(self, data_list: List[EddyCurrentData], use_cnn: bool = False) -> 'CrackIdentifier':
        processed_data = [self.preprocessor.process(d) for d in data_list]
        
        if use_cnn and self.cnn is not None:
            X = np.array([d.impedance for d in processed_data])
            y = np.array([d.labels[np.argmax(d.labels[:, 0])] if d.labels is not None else np.zeros(4) for d in processed_data])
            
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.2, random_state=Config.RANDOM_SEED
            )
            self.cnn.fit(X_train, y_train, X_val, y_val)
        else:
            self.classifier.fit(processed_data)
            self.regressor.fit(processed_data)
        
        self.is_trained = True
        return self

    def identify(self, data: EddyCurrentData, use_cnn: bool = False) -> Dict:
        processed = self.preprocessor.process(data)
        
        result = {}
        
        if use_cnn and self.cnn is not None:
            cnn_result = self.cnn.predict_single(processed)
            result.update(cnn_result)
        else:
            has_crack = self.classifier.predict(processed)[0]
            confidence = self.classifier.predict_proba(processed)[0, 1]
            
            predictions = self.regressor.predict_all(processed)
            
            result = {
                'has_crack': bool(has_crack),
                'confidence': float(confidence),
                'depth': float(predictions['depth'][0]),
                'length': float(predictions['length'][0]),
                'position': float(predictions['position'][0]) if 'position' in predictions else 0.5,
            }
        
        if data.positions is not None and result['has_crack']:
            crack_info = self._detect_crack_edges(data)
            if crack_info is not None:
                result['position_mm'] = crack_info['center_position']
                result['crack_start_idx'] = crack_info['start_idx']
                result['crack_end_idx'] = crack_info['end_idx']
                result['crack_start_mm'] = crack_info['start_position']
                result['crack_end_mm'] = crack_info['end_position']
                result['estimated_length_mm'] = crack_info['length']
                result['edge_confidence'] = crack_info['confidence']
        
        return result

    def _detect_crack_edges(self, data: EddyCurrentData) -> Optional[Dict]:
        amp = np.abs(data.impedance)
        mean_amp = np.mean(amp, axis=1)
        
        from scipy import signal as sp_signal
        
        window = Config.EDGE_DETECTION_WINDOW
        if window % 2 == 0:
            window += 1
        
        if len(mean_amp) < window * 3:
            return self._find_crack_position_simple(data)
        
        try:
            smoothed = sp_signal.savgol_filter(mean_amp, window, 2)
        except:
            smoothed = mean_amp
        
        first_deriv = np.gradient(smoothed)
        second_deriv = np.gradient(first_deriv)
        
        threshold = Config.EDGE_DETECTION_THRESHOLD
        std_deriv = np.std(first_deriv)
        
        if std_deriv < 1e-10:
            return self._find_crack_position_simple(data)
        
        baseline = np.median(mean_amp)
        std_amp = np.std(mean_amp)
        amp_threshold = baseline + 0.3 * std_amp
        
        above_threshold = np.where(mean_amp > amp_threshold)[0]
        
        if len(above_threshold) < Config.MIN_CRACK_LENGTH_POINTS:
            return self._find_crack_position_simple(data)
        
        groups = []
        current_group = [above_threshold[0]]
        
        for i in range(1, len(above_threshold)):
            if above_threshold[i] - above_threshold[i-1] <= 10:
                current_group.append(above_threshold[i])
            else:
                if len(current_group) >= Config.MIN_CRACK_LENGTH_POINTS:
                    groups.append(current_group)
                current_group = [above_threshold[i]]
        
        if len(current_group) >= Config.MIN_CRACK_LENGTH_POINTS:
            groups.append(current_group)
        
        if not groups:
            return self._find_crack_position_simple(data)
        
        best_group = None
        best_score = -1
        
        for group in groups:
            start_idx = group[0]
            end_idx = group[-1]
            
            if end_idx - start_idx < Config.MIN_CRACK_LENGTH_POINTS:
                continue
            
            search_range = 20
            while start_idx > 0 and search_range > 0:
                if mean_amp[start_idx - 1] > baseline + 0.1 * std_amp:
                    start_idx -= 1
                else:
                    break
                search_range -= 1
            
            search_range = 20
            while end_idx < len(mean_amp) - 1 and search_range > 0:
                if mean_amp[end_idx + 1] > baseline + 0.1 * std_amp:
                    end_idx += 1
                else:
                    break
                search_range -= 1
            
            crack_signal = mean_amp[start_idx:end_idx]
            pre_baseline = np.mean(mean_amp[max(0, start_idx - 20):start_idx]) if start_idx > 0 else baseline
            post_baseline = np.mean(mean_amp[end_idx:min(len(mean_amp), end_idx + 20)]) if end_idx < len(mean_amp) else baseline
            local_baseline = (pre_baseline + post_baseline) / 2
            
            amplitude = np.max(crack_signal) - local_baseline
            length = end_idx - start_idx
            
            deriv_in_region = np.max(np.abs(first_deriv[start_idx:end_idx])) / std_deriv if std_deriv > 0 else 0
            
            score = amplitude * (1 + length / 10) * (1 + deriv_in_region)
            
            if score > best_score:
                best_score = score
                best_group = (start_idx, end_idx)
        
        if best_group is None:
            return self._find_crack_position_simple(data)
        
        start_idx, end_idx = best_group
        
        positions = data.positions
        if positions.ndim > 1:
            pos_1d = positions[:, 0]
        else:
            pos_1d = positions
        
        if len(pos_1d) != len(mean_amp):
            return self._find_crack_position_simple(data)
        
        start_position = float(pos_1d[start_idx])
        end_position = float(pos_1d[end_idx])
        center_position = (start_position + end_position) / 2
        length = abs(end_position - start_position)
        
        peak_amp = np.max(mean_amp[start_idx:end_idx])
        confidence = min(1.0, (peak_amp - baseline) / (std_amp * 3))
        
        return {
            'start_idx': int(start_idx),
            'end_idx': int(end_idx),
            'start_position': start_position,
            'end_position': end_position,
            'center_position': center_position,
            'length': length,
            'confidence': max(0.3, confidence)
        }

    def _find_crack_position_simple(self, data: EddyCurrentData) -> Optional[Dict]:
        amp = np.abs(data.impedance)
        mean_amp = np.mean(amp, axis=1)
        threshold = np.mean(mean_amp) + 2 * np.std(mean_amp)
        peaks = np.where(mean_amp > threshold)[0]
        
        if len(peaks) == 0:
            peaks = np.where(mean_amp > np.mean(mean_amp) + np.std(mean_amp))[0]
        
        if len(peaks) == 0:
            max_idx = np.argmax(mean_amp)
            half_width = max(Config.MIN_CRACK_LENGTH_POINTS, len(mean_amp) // 10)
            start_idx = max(0, max_idx - half_width)
            end_idx = min(len(mean_amp) - 1, max_idx + half_width)
            peaks = np.array([start_idx, end_idx])
        
        positions = data.positions
        if positions is None:
            return {
                'start_idx': int(peaks[0]),
                'end_idx': int(peaks[-1]),
                'start_position': 0.0,
                'end_position': 0.0,
                'center_position': 0.0,
                'length': 0.0,
                'confidence': 0.3
            }
        
        if positions.ndim > 1:
            pos_1d = positions[:, 0]
        else:
            pos_1d = positions
        
        if len(pos_1d) != len(mean_amp):
            center_idx = int(np.median(peaks))
            return {
                'start_idx': int(peaks[0]),
                'end_idx': int(peaks[-1]),
                'start_position': 0.0,
                'end_position': 0.0,
                'center_position': 0.0,
                'length': 0.0,
                'confidence': 0.5
            }
        
        start_idx = int(peaks[0])
        end_idx = int(peaks[-1])
        start_position = float(pos_1d[start_idx])
        end_position = float(pos_1d[end_idx])
        center_position = (start_position + end_position) / 2
        length = abs(end_position - start_position)
        
        return {
            'start_idx': start_idx,
            'end_idx': end_idx,
            'start_position': start_position,
            'end_position': end_position,
            'center_position': center_position,
            'length': length,
            'confidence': 0.6
        }

    def _find_crack_position(self, data: EddyCurrentData) -> Optional[int]:
        crack_info = self._detect_crack_edges(data)
        if crack_info is not None:
            return int((crack_info['start_idx'] + crack_info['end_idx']) / 2)
        return None

    def save_models(self, model_dir: str) -> None:
        import os
        os.makedirs(model_dir, exist_ok=True)
        
        self.classifier.save(os.path.join(model_dir, 'svm_classifier.joblib'))
        self.regressor.save(os.path.join(model_dir, 'svm_regressor.joblib'))
        
        if self.cnn is not None:
            self.cnn.save(os.path.join(model_dir, 'cnn_model.pth'))

    def load_models(self, model_dir: str) -> 'CrackIdentifier':
        import os
        
        self.classifier.load(os.path.join(model_dir, 'svm_classifier.joblib'))
        self.regressor.load(os.path.join(model_dir, 'svm_regressor.joblib'))
        
        cnn_path = os.path.join(model_dir, 'cnn_model.pth')
        if os.path.exists(cnn_path) and self.cnn is not None:
            self.cnn.load(cnn_path)
        
        self.is_trained = True
        return self
