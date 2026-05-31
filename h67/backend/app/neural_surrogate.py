import numpy as np
from typing import Tuple, Optional, List, Dict
from .models import SimulationParameters, JunctionType
from .droplet_model import DropletFormationModel


class NeuralNetwork:
    def __init__(self, layer_sizes: List[int], activation: str = 'relu', seed: int = 42):
        self.layer_sizes = layer_sizes
        self.activation = activation
        self.weights = []
        self.biases = []
        self._rng = np.random.default_rng(seed)

        for i in range(len(layer_sizes) - 1):
            limit = np.sqrt(6 / (layer_sizes[i] + layer_sizes[i + 1]))
            W = self._rng.uniform(-limit, limit, (layer_sizes[i], layer_sizes[i + 1]))
            b = np.zeros(layer_sizes[i + 1])
            self.weights.append(W)
            self.biases.append(b)

        self._normalization_params = None

    def _activate(self, x: np.ndarray) -> np.ndarray:
        if self.activation == 'relu':
            return np.maximum(0, x)
        elif self.activation == 'tanh':
            return np.tanh(x)
        elif self.activation == 'sigmoid':
            return 1 / (1 + np.exp(-x))
        elif self.activation == 'leaky_relu':
            return np.where(x > 0, x, 0.01 * x)
        else:
            return x

    def _activate_derivative(self, x: np.ndarray) -> np.ndarray:
        if self.activation == 'relu':
            return np.where(x > 0, 1, 0)
        elif self.activation == 'tanh':
            return 1 - np.tanh(x) ** 2
        elif self.activation == 'sigmoid':
            s = 1 / (1 + np.exp(-x))
            return s * (1 - s)
        elif self.activation == 'leaky_relu':
            return np.where(x > 0, 1, 0.01)
        else:
            return np.ones_like(x)

    def forward(self, x: np.ndarray) -> np.ndarray:
        if self._normalization_params is not None:
            x = self._normalize_input(x)

        self._activations = [x]
        self._z_values = []

        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            z = self._activations[-1] @ W + b
            self._z_values.append(z)

            if i < len(self.weights) - 1:
                a = self._activate(z)
            else:
                a = z

            self._activations.append(a)

        if self._normalization_params is not None:
            return self._denormalize_output(self._activations[-1])
        return self._activations[-1]

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 1000,
            lr: float = 0.001, batch_size: int = 32, verbose: bool = True):

        self._compute_normalization_params(X, y)
        X_norm = self._normalize_input(X)
        y_norm = self._normalize_output(y)

        n_samples = X.shape[0]
        losses = []

        for epoch in range(epochs):
            indices = self._rng.permutation(n_samples)
            X_shuffled = X_norm[indices]
            y_shuffled = y_norm[indices]

            epoch_loss = 0.0
            n_batches = 0

            for i in range(0, n_samples, batch_size):
                X_batch = X_shuffled[i:i + batch_size]
                y_batch = y_shuffled[i:i + batch_size]

                y_pred = self.forward(X_batch)

                if self._normalization_params is not None:
                    y_pred_norm = self._normalize_output(y_pred, inverse=False)
                else:
                    y_pred_norm = y_pred

                loss = np.mean((y_pred_norm - y_batch) ** 2)
                epoch_loss += loss
                n_batches += 1

                dL_dy = 2 * (y_pred_norm - y_batch) / len(y_batch)

                for layer_idx in range(len(self.weights) - 1, -1, -1):
                    if layer_idx < len(self.weights) - 1:
                        dL_dz = dL_dy * self._activate_derivative(self._z_values[layer_idx])
                    else:
                        dL_dz = dL_dy

                    dL_dW = self._activations[layer_idx].T @ dL_dz
                    dL_db = np.sum(dL_dz, axis=0)

                    dL_dy = dL_dz @ self.weights[layer_idx].T

                    self.weights[layer_idx] -= lr * dL_dW
                    self.biases[layer_idx] -= lr * dL_db

            avg_loss = epoch_loss / max(n_batches, 1)
            losses.append(avg_loss)

            if verbose and (epoch + 1) % 100 == 0:
                print(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.6f}")

        return losses

    def _compute_normalization_params(self, X: np.ndarray, y: np.ndarray):
        self._normalization_params = {
            'X_mean': np.mean(X, axis=0),
            'X_std': np.std(X, axis=0) + 1e-8,
            'y_mean': np.mean(y, axis=0),
            'y_std': np.std(y, axis=0) + 1e-8
        }

    def _normalize_input(self, X: np.ndarray, inverse: bool = False) -> np.ndarray:
        if self._normalization_params is None:
            return X
        if inverse:
            return X * self._normalization_params['X_std'] + self._normalization_params['X_mean']
        return (X - self._normalization_params['X_mean']) / self._normalization_params['X_std']

    def _normalize_output(self, y: np.ndarray, inverse: bool = False) -> np.ndarray:
        if self._normalization_params is None:
            return y
        if inverse:
            return y * self._normalization_params['y_std'] + self._normalization_params['y_mean']
        return (y - self._normalization_params['y_mean']) / self._normalization_params['y_std']

    def _denormalize_output(self, y: np.ndarray) -> np.ndarray:
        return self._normalize_output(y, inverse=True)


class DropletNeuralSurrogate:
    def __init__(self, hidden_layers: List[int] = [64, 32, 16]):
        self.input_features = [
            'Qc', 'Qd', 'mu_c', 'mu_d', 'sigma', 'W', 'H',
            'junction_T', 'junction_flow_focusing', 'junction_co_flow'
        ]
        self.output_features = ['droplet_size', 'frequency']

        layer_sizes = [len(self.input_features)] + hidden_layers + [len(self.output_features)]
        self.nn = NeuralNetwork(layer_sizes, activation='leaky_relu')

        self.droplet_model = DropletFormationModel()
        self._trained = False
        self._training_losses = []
        self._validation_losses = []
        self._test_metrics = {}

    def generate_training_data(self, n_samples: int = 10000,
                               noise_level: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(42)

        X = np.zeros((n_samples, len(self.input_features)))
        y = np.zeros((n_samples, len(self.output_features)))

        param_ranges = {
            'Qc': (1, 100),
            'Qd': (0.5, 50),
            'mu_c': (0.5, 10),
            'mu_d': (1, 50),
            'sigma': (5, 70),
            'W': (30, 300),
            'H': (10, 200)
        }

        for i in range(n_samples):
            Qc = rng.uniform(*param_ranges['Qc'])
            Qd = rng.uniform(*param_ranges['Qd'])
            mu_c = rng.uniform(*param_ranges['mu_c'])
            mu_d = rng.uniform(*param_ranges['mu_d'])
            sigma = rng.uniform(*param_ranges['sigma'])
            W = rng.uniform(*param_ranges['W'])
            H = rng.uniform(*param_ranges['H'])

            junction_idx = rng.integers(0, 3)
            junction_types = [JunctionType.T, JunctionType.FLOW_FOCUSING, JunctionType.CO_FLOW]
            junction_type = junction_types[junction_idx]

            D = self.droplet_model.predict_droplet_size(
                Qc=Qc, Qd=Qd, muc=mu_c, mud=mu_d, sigma=sigma,
                W=W, H=H, junction_type=junction_type, add_noise=False
            )

            Q_ratio = Qd / Qc if Qc > 0 else 0
            Ca_c = (mu_c * Qc * 1e3) / (60 * W * H * sigma) if sigma > 0 else 0
            f = self.droplet_model.predict_frequency(Qc, Qd, D, W, H)

            D += rng.normal(0, noise_level * D)
            f += rng.normal(0, noise_level * f)

            X[i] = [Qc, Qd, mu_c, mu_d, sigma, W, H,
                    1 if junction_idx == 0 else 0,
                    1 if junction_idx == 1 else 0,
                    1 if junction_idx == 2 else 0]
            y[i] = [D, f]

        return X, y

    def train(self, n_samples: int = 10000, epochs: int = 2000,
              lr: float = 0.001, batch_size: int = 64,
              validation_split: float = 0.2) -> Dict:

        print("Generating training data from empirical model...")
        X, y = self.generate_training_data(n_samples)

        split_idx = int(n_samples * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        print(f"Training with {len(X_train)} samples, validating with {len(X_val)} samples...")

        self._training_losses = self.nn.fit(
            X_train, y_train, epochs=epochs, lr=lr, batch_size=batch_size, verbose=True
        )

        val_preds = self.nn.forward(X_val)
        self._validation_losses = np.mean((val_preds - y_val) ** 2, axis=0)

        y_test_pred = self.nn.forward(X_val)
        size_mape = np.mean(np.abs((y_test_pred[:, 0] - y_val[:, 0]) / y_val[:, 0])) * 100
        freq_mape = np.mean(np.abs((y_test_pred[:, 1] - y_val[:, 1]) / y_val[:, 1])) * 100
        size_r2 = 1 - np.sum((y_test_pred[:, 0] - y_val[:, 0]) ** 2) / np.sum((y_val[:, 0] - np.mean(y_val[:, 0])) ** 2)
        freq_r2 = 1 - np.sum((y_test_pred[:, 1] - y_val[:, 1]) ** 2) / np.sum((y_val[:, 1] - np.mean(y_val[:, 1])) ** 2)

        self._test_metrics = {
            'size_mape': float(size_mape),
            'frequency_mape': float(freq_mape),
            'size_r2': float(size_r2),
            'frequency_r2': float(freq_r2),
            'n_training_samples': split_idx,
            'n_validation_samples': len(X_val),
            'n_epochs': epochs
        }

        self._trained = True
        print("\nTraining complete!")
        print(f"Droplet Size MAPE: {size_mape:.2f}%, R²: {size_r2:.4f}")
        print(f"Frequency MAPE: {freq_mape:.2f}%, R²: {freq_r2:.4f}")

        return self._test_metrics

    def predict(self, params: SimulationParameters,
                Qc_actual: Optional[float] = None,
                Qd_actual: Optional[float] = None) -> Tuple[float, float]:

        if not self._trained:
            raise RuntimeError("Model not trained. Call train() first.")

        Qc = Qc_actual if Qc_actual is not None else params.continuousPhase.flowRate
        Qd = Qd_actual if Qd_actual is not None else params.dispersedPhase.flowRate

        junction_onehot = [0, 0, 0]
        if params.channel.junctionType == JunctionType.T:
            junction_onehot[0] = 1
        elif params.channel.junctionType == JunctionType.FLOW_FOCUSING:
            junction_onehot[1] = 1
        else:
            junction_onehot[2] = 1

        X = np.array([[
            Qc, Qd,
            params.continuousPhase.viscosity,
            params.dispersedPhase.viscosity,
            params.interfacialTension,
            params.channel.width,
            params.channel.height,
            *junction_onehot
        ]])

        y_pred = self.nn.forward(X)[0]
        D = max(y_pred[0], 0.1 * params.channel.width)
        f = max(y_pred[1], 0.01)

        return float(D), float(f)

    def predict_batch(self, params_list: List[SimulationParameters]) -> np.ndarray:
        if not self._trained:
            raise RuntimeError("Model not trained. Call train() first.")

        X_batch = []
        for params in params_list:
            junction_onehot = [0, 0, 0]
            if params.channel.junctionType == JunctionType.T:
                junction_onehot[0] = 1
            elif params.channel.junctionType == JunctionType.FLOW_FOCUSING:
                junction_onehot[1] = 1
            else:
                junction_onehot[2] = 1

            X_batch.append([
                params.continuousPhase.flowRate,
                params.dispersedPhase.flowRate,
                params.continuousPhase.viscosity,
                params.dispersedPhase.viscosity,
                params.interfacialTension,
                params.channel.width,
                params.channel.height,
                *junction_onehot
            ])

        X_batch = np.array(X_batch)
        return self.nn.forward(X_batch)

    def get_model_info(self) -> Dict:
        return {
            'trained': self._trained,
            'architecture': {
                'input_features': self.input_features,
                'hidden_layers': self.nn.layer_sizes[1:-1],
                'output_features': self.output_features,
                'activation': self.nn.activation,
                'total_parameters': sum(W.size + b.size for W, b in zip(self.nn.weights, self.nn.biases))
            },
            'metrics': self._test_metrics,
            'training_losses': self._training_losses[-100:] if self._training_losses else [],
            'validation_loss': self._validation_losses.tolist() if hasattr(self._validation_losses, 'tolist') else self._validation_losses
        }
