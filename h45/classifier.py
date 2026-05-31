import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
from config import ClassifierConfig, KEYBOARD_KEYS
from utils import softmax, get_key_name, get_key_index
from feature_extraction import KeyFeatures


@dataclass
class ClassificationResult:
    key_index: int
    key_name: str
    confidence: float
    logits: np.ndarray
    top_k_predictions: List[Tuple[int, str, float]]


class CNNLayer:
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3, stride: int = 1, padding: int = 1):
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        
        limit = np.sqrt(2.0 / (in_channels * kernel_size * kernel_size))
        self.weights = np.random.uniform(-limit, limit, (out_channels, in_channels, kernel_size, kernel_size))
        self.bias = np.zeros(out_channels)
        
        self.dw = np.zeros_like(self.weights)
        self.db = np.zeros_like(self.bias)
        
        self.input_cache = None
        self.output_cache = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        batch_size, in_channels, height, width = x.shape
        self.input_cache = x
        
        out_height = (height + 2 * self.padding - self.kernel_size) // self.stride + 1
        out_width = (width + 2 * self.padding - self.kernel_size) // self.stride + 1
        
        if self.padding > 0:
            x_pad = np.pad(x, ((0, 0), (0, 0), (self.padding, self.padding), (self.padding, self.padding)), mode='constant')
        else:
            x_pad = x
        
        output = np.zeros((batch_size, self.out_channels, out_height, out_width))
        
        for i in range(out_height):
            for j in range(out_width):
                h_start = i * self.stride
                h_end = h_start + self.kernel_size
                w_start = j * self.stride
                w_end = w_start + self.kernel_size
                
                receptive_field = x_pad[:, :, h_start:h_end, w_start:w_end]
                
                for k in range(self.out_channels):
                    output[:, k, i, j] = np.sum(receptive_field * self.weights[k], axis=(1, 2, 3)) + self.bias[k]
        
        self.output_cache = output
        return output

    def backward(self, doutput: np.ndarray, learning_rate: float) -> np.ndarray:
        batch_size, _, out_height, out_width = doutput.shape
        x = self.input_cache
        
        if self.padding > 0:
            x_pad = np.pad(x, ((0, 0), (0, 0), (self.padding, self.padding), (self.padding, self.padding)), mode='constant')
            dx_pad = np.zeros_like(x_pad)
        else:
            x_pad = x
            dx_pad = np.zeros_like(x)
        
        self.dw.fill(0)
        self.db.fill(0)
        
        for i in range(out_height):
            for j in range(out_width):
                h_start = i * self.stride
                h_end = h_start + self.kernel_size
                w_start = j * self.stride
                w_end = w_start + self.kernel_size
                
                receptive_field = x_pad[:, :, h_start:h_end, w_start:w_end]
                
                for k in range(self.out_channels):
                    doutput_k = doutput[:, k, i, j].reshape(batch_size, 1, 1, 1)
                    self.dw[k] += np.sum(doutput_k * receptive_field, axis=0)
                    self.db[k] += np.sum(doutput[:, k, i, j])
                    dx_pad[:, :, h_start:h_end, w_start:w_end] += doutput_k * self.weights[k]
        
        if self.padding > 0:
            dx = dx_pad[:, :, self.padding:-self.padding, self.padding:-self.padding]
        else:
            dx = dx_pad
        
        self.weights -= learning_rate * self.dw
        self.bias -= learning_rate * self.db
        
        return dx


class MaxPool2DLayer:
    def __init__(self, pool_size: int = 2, stride: int = 2):
        self.pool_size = pool_size
        self.stride = stride
        self.input_cache = None
        self.mask_cache = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        self.input_cache = x
        batch_size, channels, height, width = x.shape
        
        out_height = height // self.pool_size
        out_width = width // self.pool_size
        
        output = np.zeros((batch_size, channels, out_height, out_width))
        self.mask_cache = np.zeros_like(x, dtype=bool)
        
        for i in range(out_height):
            for j in range(out_width):
                h_start = i * self.pool_size
                h_end = h_start + self.pool_size
                w_start = j * self.pool_size
                w_end = w_start + self.pool_size
                
                patch = x[:, :, h_start:h_end, w_start:w_end]
                max_vals = np.max(patch, axis=(2, 3), keepdims=True)
                output[:, :, i, j] = max_vals.squeeze()
                
                max_mask = (patch == max_vals)
                self.mask_cache[:, :, h_start:h_end, w_start:w_end] |= max_mask
        
        return output

    def backward(self, doutput: np.ndarray) -> np.ndarray:
        x = self.input_cache
        batch_size, channels, height, width = x.shape
        
        out_height = height // self.pool_size
        out_width = width // self.pool_size
        
        dx = np.zeros_like(x)
        
        for i in range(out_height):
            for j in range(out_width):
                h_start = i * self.pool_size
                h_end = h_start + self.pool_size
                w_start = j * self.pool_size
                w_end = w_start + self.pool_size
                
                dx[:, :, h_start:h_end, w_start:w_end] += (
                    doutput[:, :, i:i+1, j:j+1] * 
                    self.mask_cache[:, :, h_start:h_end, w_start:w_end]
                )
        
        return dx


class ReLULayer:
    def __init__(self):
        self.cache = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        self.cache = x
        return np.maximum(0, x)

    def backward(self, doutput: np.ndarray) -> np.ndarray:
        return doutput * (self.cache > 0)


class DropoutLayer:
    def __init__(self, dropout_rate: float = 0.1):
        self.dropout_rate = dropout_rate
        self.mask = None
        self.training = True

    def forward(self, x: np.ndarray) -> np.ndarray:
        if not self.training:
            return x
        
        self.mask = np.random.binomial(1, 1 - self.dropout_rate, size=x.shape)
        return x * self.mask / (1 - self.dropout_rate)

    def backward(self, doutput: np.ndarray) -> np.ndarray:
        if not self.training:
            return doutput
        return doutput * self.mask / (1 - self.dropout_rate)


class LinearLayer:
    def __init__(self, in_features: int, out_features: int):
        limit = np.sqrt(2.0 / in_features)
        self.weights = np.random.uniform(-limit, limit, (in_features, out_features))
        self.bias = np.zeros(out_features)
        
        self.dw = np.zeros_like(self.weights)
        self.db = np.zeros_like(self.bias)
        
        self.input_cache = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        self.input_cache = x
        return np.dot(x, self.weights) + self.bias

    def backward(self, doutput: np.ndarray, learning_rate: float) -> np.ndarray:
        x = self.input_cache
        batch_size = x.shape[0]
        
        self.dw = np.dot(x.T, doutput) / batch_size
        self.db = np.mean(doutput, axis=0)
        
        dx = np.dot(doutput, self.weights.T)
        
        self.weights -= learning_rate * self.dw
        self.bias -= learning_rate * self.db
        
        return dx


class LayerNorm:
    def __init__(self, normalized_shape: int, eps: float = 1e-5):
        self.gamma = np.ones(normalized_shape)
        self.beta = np.zeros(normalized_shape)
        self.eps = eps
        
        self.dgamma = np.zeros_like(self.gamma)
        self.dbeta = np.zeros_like(self.beta)
        
        self.cache = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        mean = np.mean(x, axis=-1, keepdims=True)
        var = np.var(x, axis=-1, keepdims=True)
        
        x_normalized = (x - mean) / np.sqrt(var + self.eps)
        output = self.gamma * x_normalized + self.beta
        
        self.cache = (x, mean, var, x_normalized)
        return output

    def backward(self, doutput: np.ndarray, learning_rate: float) -> np.ndarray:
        x, mean, var, x_normalized = self.cache
        batch_size, seq_len, features = doutput.shape
        
        self.dgamma = np.sum(doutput * x_normalized, axis=(0, 1))
        self.dbeta = np.sum(doutput, axis=(0, 1))
        
        dx_normalized = doutput * self.gamma
        
        dvar = np.sum(dx_normalized * (x - mean) * -0.5 * np.power(var + self.eps, -1.5), axis=-1, keepdims=True)
        dmean = np.sum(dx_normalized * -1 / np.sqrt(var + self.eps), axis=-1, keepdims=True) + dvar * np.mean(-2 * (x - mean), axis=-1, keepdims=True)
        
        dx = dx_normalized / np.sqrt(var + self.eps) + dvar * 2 * (x - mean) / features + dmean / features
        
        self.gamma -= learning_rate * self.dgamma
        self.beta -= learning_rate * self.dbeta
        
        return dx


class MultiHeadAttention:
    def __init__(self, embed_dim: int, num_heads: int, dropout: float = 0.1):
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        
        self.q_proj = LinearLayer(embed_dim, embed_dim)
        self.k_proj = LinearLayer(embed_dim, embed_dim)
        self.v_proj = LinearLayer(embed_dim, embed_dim)
        self.out_proj = LinearLayer(embed_dim, embed_dim)
        
        self.dropout = DropoutLayer(dropout)
        
        self.cache = None

    def forward(self, x: np.ndarray, mask: Optional[np.ndarray] = None) -> np.ndarray:
        batch_size, seq_len, embed_dim = x.shape
        
        q = self.q_proj.forward(x)
        k = self.k_proj.forward(x)
        v = self.v_proj.forward(x)
        
        q = q.reshape(batch_size, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        k = k.reshape(batch_size, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        v = v.reshape(batch_size, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        
        scores = np.matmul(q, k.transpose(0, 1, 3, 2)) / np.sqrt(self.head_dim)
        
        if mask is not None:
            scores = scores * mask + (1 - mask) * -1e9
        
        attn_weights = softmax(scores, axis=-1)
        attn_weights = self.dropout.forward(attn_weights)
        
        output = np.matmul(attn_weights, v)
        output = output.transpose(0, 2, 1, 3).reshape(batch_size, seq_len, embed_dim)
        
        output = self.out_proj.forward(output)
        
        self.cache = (q, k, v, attn_weights, x)
        return output

    def backward(self, doutput: np.ndarray, learning_rate: float) -> np.ndarray:
        q, k, v, attn_weights, x = self.cache
        batch_size, seq_len, embed_dim = x.shape
        
        doutput = doutput.reshape(batch_size, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        doutput = self.out_proj.backward(doutput.reshape(batch_size, seq_len, embed_dim), learning_rate)
        doutput = doutput.reshape(batch_size, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        
        dv = np.matmul(attn_weights.transpose(0, 1, 3, 2), doutput)
        dattn = np.matmul(doutput, v.transpose(0, 1, 3, 2))
        
        dattn = self.dropout.backward(dattn)
        dattn = dattn * attn_weights * (1 - attn_weights)
        
        dq = np.matmul(dattn, k) / np.sqrt(self.head_dim)
        dk = np.matmul(q.transpose(0, 1, 3, 2), dattn).transpose(0, 1, 3, 2) / np.sqrt(self.head_dim)
        
        dq = dq.transpose(0, 2, 1, 3).reshape(batch_size, seq_len, embed_dim)
        dk = dk.transpose(0, 2, 1, 3).reshape(batch_size, seq_len, embed_dim)
        dv = dv.transpose(0, 2, 1, 3).reshape(batch_size, seq_len, embed_dim)
        
        dq = self.q_proj.backward(dq, learning_rate)
        dk = self.k_proj.backward(dk, learning_rate)
        dv = self.v_proj.backward(dv, learning_rate)
        
        return dq + dk + dv


class TransformerEncoderLayer:
    def __init__(self, embed_dim: int, num_heads: int, dim_feedforward: int, dropout: float = 0.1):
        self.self_attn = MultiHeadAttention(embed_dim, num_heads, dropout)
        self.norm1 = LayerNorm(embed_dim)
        self.norm2 = LayerNorm(embed_dim)
        
        self.linear1 = LinearLayer(embed_dim, dim_feedforward)
        self.linear2 = LinearLayer(dim_feedforward, embed_dim)
        
        self.dropout1 = DropoutLayer(dropout)
        self.dropout2 = DropoutLayer(dropout)
        self.dropout3 = DropoutLayer(dropout)
        
        self.activation = ReLULayer()

    def forward(self, x: np.ndarray) -> np.ndarray:
        attn_output = self.self_attn.forward(x)
        attn_output = self.dropout1.forward(attn_output)
        x = self.norm1.forward(x + attn_output)
        
        ff_output = self.linear1.forward(x)
        ff_output = self.activation.forward(ff_output)
        ff_output = self.dropout2.forward(ff_output)
        ff_output = self.linear2.forward(ff_output)
        ff_output = self.dropout3.forward(ff_output)
        
        x = self.norm2.forward(x + ff_output)
        return x

    def backward(self, doutput: np.ndarray, learning_rate: float) -> np.ndarray:
        d_ff = self.norm2.backward(doutput, learning_rate)
        d_x2 = d_ff
        
        d_ff = self.dropout3.backward(d_ff)
        d_ff = self.linear2.backward(d_ff, learning_rate)
        d_ff = self.dropout2.backward(d_ff)
        d_ff = self.activation.backward(d_ff)
        d_ff = self.linear1.backward(d_ff, learning_rate)
        
        d_x2 += d_ff
        
        d_attn = self.norm1.backward(d_x2, learning_rate)
        d_x1 = d_attn
        
        d_attn = self.dropout1.backward(d_attn)
        d_attn = self.self_attn.backward(d_attn, learning_rate)
        
        d_x1 += d_attn
        
        return d_x1


class CNNTransformerClassifier:
    def __init__(self, config: ClassifierConfig, mel_shape: Tuple[int, int], tdoa_dim: int):
        self.config = config
        self.mel_shape = mel_shape
        self.tdoa_dim = tdoa_dim
        
        self.cnn_layers = []
        in_channels = 1
        current_height, current_width = mel_shape
        
        for out_channels in config.cnn_channels:
            self.cnn_layers.append(CNNLayer(in_channels, out_channels, kernel_size=3, stride=1, padding=1))
            self.cnn_layers.append(ReLULayer())
            self.cnn_layers.append(MaxPool2DLayer(pool_size=2, stride=2))
            in_channels = out_channels
            current_height //= 2
            current_width //= 2
        
        self.cnn_output_dim = in_channels * current_height * current_width
        
        total_feature_dim = self.cnn_output_dim + tdoa_dim
        
        if total_feature_dim < config.transformer_dim:
            self.projection = LinearLayer(total_feature_dim, config.transformer_dim)
            self.transformer_input_dim = config.transformer_dim
        else:
            self.projection = None
            self.transformer_input_dim = total_feature_dim
        
        self.transformer_layers = []
        for _ in range(config.transformer_layers):
            self.transformer_layers.append(TransformerEncoderLayer(
                self.transformer_input_dim, config.transformer_heads, 
                self.transformer_input_dim * 4, config.dropout
            ))
        
        self.classifier = LinearLayer(self.transformer_input_dim, config.num_classes)
        
        self.dropout = DropoutLayer(config.dropout)
        self.training = True

    def _set_training(self, training: bool):
        self.training = training
        for layer in self.cnn_layers:
            if hasattr(layer, 'training'):
                layer.training = training
        for layer in self.transformer_layers:
            if hasattr(layer, 'training'):
                layer.training = training
            layer.self_attn.dropout.training = training
            layer.dropout1.training = training
            layer.dropout2.training = training
            layer.dropout3.training = training
        self.dropout.training = training

    def _prepare_features(self, features: List[KeyFeatures]) -> Tuple[np.ndarray, np.ndarray]:
        batch_size = len(features)
        
        mel_batch = np.zeros((batch_size, 1) + self.mel_shape)
        tdoa_batch = np.zeros((batch_size, self.tdoa_dim))
        
        for i, feat in enumerate(features):
            mel = feat.mel_spectrogram
            if mel.shape[0] > self.mel_shape[0]:
                mel = mel[:self.mel_shape[0]]
            elif mel.shape[0] < self.mel_shape[0]:
                pad = np.zeros((self.mel_shape[0] - mel.shape[0], mel.shape[1]))
                mel = np.vstack([mel, pad])
            
            if mel.shape[1] > self.mel_shape[1]:
                mel = mel[:, :self.mel_shape[1]]
            elif mel.shape[1] < self.mel_shape[1]:
                pad = np.zeros((mel.shape[0], self.mel_shape[1] - mel.shape[1]))
                mel = np.hstack([mel, pad])
            
            mel_batch[i, 0] = mel
            
            tdoa = feat.tdoa_features
            if len(tdoa) > self.tdoa_dim:
                tdoa = tdoa[:self.tdoa_dim]
            elif len(tdoa) < self.tdoa_dim:
                tdoa = np.pad(tdoa, (0, self.tdoa_dim - len(tdoa)))
            tdoa_batch[i] = tdoa
        
        return mel_batch, tdoa_batch

    def forward(self, features: List[KeyFeatures]) -> np.ndarray:
        mel_batch, tdoa_batch = self._prepare_features(features)
        
        x = mel_batch
        for layer in self.cnn_layers:
            x = layer.forward(x)
        
        batch_size = x.shape[0]
        x_flat = x.reshape(batch_size, -1)
        
        combined = np.concatenate([x_flat, tdoa_batch], axis=1)
        
        if self.projection is not None:
            combined = self.projection.forward(combined)
        
        transformer_input = combined.reshape(batch_size, 1, -1)
        
        for layer in self.transformer_layers:
            transformer_input = layer.forward(transformer_input)
        
        pooled = transformer_input.mean(axis=1)
        pooled = self.dropout.forward(pooled)
        
        logits = self.classifier.forward(pooled)
        
        return logits

    def predict(self, features: List[KeyFeatures], top_k: int = 5) -> List[ClassificationResult]:
        was_training = self.training
        self._set_training(False)
        
        logits = self.forward(features)
        probabilities = softmax(logits, axis=-1)
        
        results = []
        for i in range(len(features)):
            probs = probabilities[i]
            top_indices = np.argsort(probs)[::-1][:top_k]
            
            top_k_preds = []
            for idx in top_indices:
                key_name = get_key_name(int(idx)) or f"Unknown_{idx}"
                top_k_preds.append((int(idx), key_name, float(probs[idx])))
            
            pred_idx = top_indices[0]
            key_name = get_key_name(int(pred_idx)) or f"Unknown_{pred_idx}"
            
            results.append(ClassificationResult(
                key_index=int(pred_idx),
                key_name=key_name,
                confidence=float(probs[pred_idx]),
                logits=logits[i],
                top_k_predictions=top_k_preds
            ))
        
        self._set_training(was_training)
        return results

    def train_step(self, features: List[KeyFeatures], labels: List[int], 
                   learning_rate: float = None) -> Tuple[float, np.ndarray]:
        if learning_rate is None:
            learning_rate = self.config.learning_rate
        
        if not self.training:
            self._set_training(True)
        
        logits = self.forward(features)
        probabilities = softmax(logits, axis=-1)
        
        batch_size = len(labels)
        labels_onehot = np.zeros_like(logits)
        for i, label in enumerate(labels):
            labels_onehot[i, label] = 1
        
        eps = 1e-10
        loss = -np.mean(np.sum(labels_onehot * np.log(probabilities + eps), axis=-1))
        
        dlogits = (probabilities - labels_onehot) / batch_size
        
        dpooled = self.classifier.backward(dlogits, learning_rate)
        dpooled = self.dropout.backward(dpooled)
        
        dtransformer = dpooled.reshape(batch_size, 1, -1)
        
        for layer in reversed(self.transformer_layers):
            dtransformer = layer.backward(dtransformer, learning_rate)
        
        dcombined = dtransformer.reshape(batch_size, -1)
        
        if self.projection is not None:
            dcombined = self.projection.backward(dcombined, learning_rate)
        
        d_cnn = dcombined[:, :self.cnn_output_dim]
        d_tdoa = dcombined[:, self.cnn_output_dim:]
        
        d_cnn = d_cnn.reshape(batch_size, self.cnn_output_dim // (self.cnn_layers[-3].out_channels * 
                              (self.mel_shape[0] // 2**len(self.config.cnn_channels)) *
                              (self.mel_shape[1] // 2**len(self.config.cnn_channels))),
                              self.mel_shape[0] // 2**len(self.config.cnn_channels),
                              self.mel_shape[1] // 2**len(self.config.cnn_channels))
        
        d_cnn = d_cnn.reshape_as(self._get_cnn_output_shape(batch_size))
        
        for layer in reversed(self.cnn_layers):
            if isinstance(layer, (CNNLayer,)):
                d_cnn = layer.backward(d_cnn, learning_rate)
            else:
                d_cnn = layer.backward(d_cnn)
        
        return loss, probabilities

    def _get_cnn_output_shape(self, batch_size):
        channels = self.config.cnn_channels[-1]
        h = self.mel_shape[0] // (2 ** len(self.config.cnn_channels))
        w = self.mel_shape[1] // (2 ** len(self.config.cnn_channels))
        return (batch_size, channels, h, w)

    def save(self, filepath: str):
        import pickle
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)
    
    @staticmethod
    def load(filepath: str) -> 'CNNTransformerClassifier':
        import pickle
        with open(filepath, 'rb') as f:
            return pickle.load(f)


class KNNClassifier:
    def __init__(self, num_classes: int = 104, k: int = 5):
        self.num_classes = num_classes
        self.k = k
        self.train_features = None
        self.train_labels = None
    
    def fit(self, features: List[KeyFeatures], labels: List[int]):
        has_whitened = all(hasattr(f, 'whitened_features') and f.whitened_features is not None for f in features)
        
        if has_whitened:
            X = np.array([f.whitened_features for f in features])
        else:
            X = np.array([f.combined_features for f in features])
        y = np.array(labels)
        
        mean = np.mean(X, axis=0)
        std = np.std(X, axis=0) + 1e-10
        self.mean = mean
        self.std = std
        self.use_whitened = has_whitened
        
        self.train_features = (X - mean) / std
        self.train_labels = y
    
    def predict(self, features: List[KeyFeatures], top_k: int = 5) -> List[ClassificationResult]:
        if self.use_whitened and all(hasattr(f, 'whitened_features') and f.whitened_features is not None for f in features):
            X = np.array([f.whitened_features for f in features])
        else:
            X = np.array([f.combined_features for f in features])
        X = (X - self.mean) / self.std
        
        results = []
        for i, x in enumerate(X):
            distances = np.sqrt(np.sum((self.train_features - x) ** 2, axis=1))
            
            neighbor_indices = np.argsort(distances)[:self.k]
            neighbor_labels = self.train_labels[neighbor_indices]
            
            label_counts = np.bincount(neighbor_labels, minlength=self.num_classes)
            probabilities = label_counts / self.k
            
            top_indices = np.argsort(probabilities)[::-1][:top_k]
            
            top_k_preds = []
            for idx in top_indices:
                key_name = get_key_name(int(idx)) or f"Unknown_{idx}"
                top_k_preds.append((int(idx), key_name, float(probabilities[idx])))
            
            pred_idx = top_indices[0]
            key_name = get_key_name(int(pred_idx)) or f"Unknown_{pred_idx}"
            
            results.append(ClassificationResult(
                key_index=int(pred_idx),
                key_name=key_name,
                confidence=float(probabilities[pred_idx]),
                logits=probabilities,
                top_k_predictions=top_k_preds
            ))
        
        return results
