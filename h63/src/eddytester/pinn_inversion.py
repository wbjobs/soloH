import numpy as np
from typing import List, Optional, Tuple, Dict, Union, Callable
from dataclasses import dataclass, field
import time

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from .data_io import EddyCurrentData
from .config import Config
from .preprocessing import Preprocessor


@dataclass
class PINNConfig:
    hidden_layers: List[int] = field(default_factory=lambda: Config.PINN_HIDDEN_LAYERS)
    learning_rate: float = Config.PINN_LEARNING_RATE
    epochs: int = Config.PINN_EPOCHS
    pde_weight: float = Config.PINN_PDE_WEIGHT
    data_weight: float = Config.PINN_DATA_WEIGHT
    device: str = 'cuda' if (TORCH_AVAILABLE and torch.cuda.is_available()) else 'cpu'
    seed: int = Config.RANDOM_SEED


class HelmholtzPDE:
    def __init__(self,
                 frequency: float,
                 conductivity: float,
                 permeability: float,
                 permittivity: float = 8.854e-12):
        self.frequency = frequency
        self.omega = 2 * np.pi * frequency
        self.sigma = conductivity
        self.mu = permeability
        self.epsilon = permittivity
        
        self.k_squared = self.omega ** 2 * self.mu * self.epsilon - 1j * self.omega * self.mu * self.sigma

    def compute_residual(self,
                         positions: 'torch.Tensor',
                         predictions: 'torch.Tensor',
                         grad_predictions: 'torch.Tensor',
                         hessian_predictions: 'torch.Tensor') -> 'torch.Tensor':
        laplacian = hessian_predictions.sum(dim=-1)
        
        residual = laplacian + self.k_squared * predictions
        
        return residual


class PINNNetwork(nn.Module):
    def __init__(self,
                 input_dim: int = 3,
                 output_dim: int = 2,
                 hidden_layers: List[int] = None):
        super().__init__()
        
        if hidden_layers is None:
            hidden_layers = Config.PINN_HIDDEN_LAYERS
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_layers:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.Tanh())
            prev_dim = hidden_dim
        
        layers.append(nn.Linear(prev_dim, output_dim))
        self.network = nn.Sequential(*layers)
        
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_normal_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, x: 'torch.Tensor') -> 'torch.Tensor':
        return self.network(x)


class CrackReconstructorPINN:
    def __init__(self, config: Optional[PINNConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for PINN inversion. Install with: pip install torch")
        
        self.config = config or PINNConfig()
        torch.manual_seed(self.config.seed)
        np.random.seed(self.config.seed)
        
        self.network = None
        self.pde = None
        self.trained = False
        self.training_history = {}

    def prepare_data(self,
                     data: EddyCurrentData,
                     freq_idx: int = 0,
                     conductivity: float = Config.REFERENCE_CONDUCTIVITY,
                     permeability: float = Config.REFERENCE_PERMEABILITY) -> Dict:
        positions = data.positions
        impedance = data.impedance[:, freq_idx]
        
        if positions.ndim == 1:
            positions = positions.reshape(-1, 1)
        
        if positions.shape[1] == 1:
            x_coords = positions[:, 0]
            y_coords = np.zeros_like(x_coords)
            z_coords = np.zeros_like(x_coords)
        elif positions.shape[1] == 2:
            x_coords = positions[:, 0]
            y_coords = positions[:, 1]
            z_coords = np.zeros_like(x_coords)
        else:
            x_coords = positions[:, 0]
            y_coords = positions[:, 1]
            z_coords = positions[:, 2]
        
        real_part = np.real(impedance)
        imag_part = np.imag(impedance)
        
        x_train = np.column_stack([x_coords, y_coords, z_coords])
        y_train = np.column_stack([real_part, imag_part])
        
        freq = data.frequencies[freq_idx] if data.frequencies else Config.DEFAULT_FREQUENCIES[freq_idx]
        self.pde = HelmholtzPDE(freq, conductivity, permeability)
        
        x_bounds = np.column_stack([x_train.min(axis=0), x_train.max(axis=0)])
        
        return {
            'x_train': x_train,
            'y_train': y_train,
            'x_bounds': x_bounds,
            'freq': freq,
            'conductivity': conductivity,
            'permeability': permeability
        }

    def generate_collocation_points(self,
                                    x_bounds: np.ndarray,
                                    n_points: int = 1000) -> np.ndarray:
        collocation = np.random.uniform(
            x_bounds[:, 0],
            x_bounds[:, 1],
            size=(n_points, x_bounds.shape[0])
        )
        return collocation

    def train(self,
              data: EddyCurrentData,
              freq_idx: int = 0,
              conductivity: Optional[float] = None,
              permeability: Optional[float] = None,
              verbose: bool = True) -> Dict:
        sigma = conductivity or data.conductivity or Config.REFERENCE_CONDUCTIVITY
        mu = permeability or data.permeability or Config.REFERENCE_PERMEABILITY
        
        prepared = self.prepare_data(data, freq_idx, sigma, mu)
        
        x_train = torch.tensor(prepared['x_train'], dtype=torch.float32, device=self.config.device, requires_grad=True)
        y_train = torch.tensor(prepared['y_train'], dtype=torch.float32, device=self.config.device)
        
        collocation = self.generate_collocation_points(prepared['x_bounds'])
        x_colloc = torch.tensor(collocation, dtype=torch.float32, device=self.config.device, requires_grad=True)
        
        input_dim = x_train.shape[1]
        output_dim = y_train.shape[1]
        
        self.network = PINNNetwork(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_layers=self.config.hidden_layers
        ).to(self.config.device)
        
        optimizer = optim.Adam(self.network.parameters(), lr=self.config.learning_rate)
        
        scheduler = optim.lr_scheduler.ExponentialLR(optimizer, gamma=0.999)
        
        history = {
            'total_loss': [],
            'data_loss': [],
            'pde_loss': [],
            'lr': []
        }
        
        start_time = time.time()
        
        for epoch in range(self.config.epochs):
            optimizer.zero_grad()
            
            pred_data = self.network(x_train)
            data_loss = nn.MSELoss()(pred_data, y_train)
            
            pred_colloc = self.network(x_colloc)
            
            grad_pred = torch.autograd.grad(
                pred_colloc.sum(),
                x_colloc,
                create_graph=True,
                retain_graph=True
            )[0]
            
            hessian = torch.zeros_like(x_colloc)
            for i in range(input_dim):
                hessian[:, i] = torch.autograd.grad(
                    grad_pred[:, i].sum(),
                    x_colloc,
                    create_graph=True,
                    retain_graph=True
                )[0][:, i]
            
            pde_residual = self.pde.compute_residual(x_colloc, pred_colloc[:, 0], grad_pred, hessian)
            pde_loss = torch.mean(torch.abs(pde_residual) ** 2)
            
            total_loss = (self.config.data_weight * data_loss + 
                         self.config.pde_weight * pde_loss)
            
            total_loss.backward(retain_graph=True)
            torch.nn.utils.clip_grad_norm_(self.network.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()
            
            current_lr = scheduler.get_last_lr()[0]
            
            history['total_loss'].append(total_loss.item())
            history['data_loss'].append(data_loss.item())
            history['pde_loss'].append(pde_loss.item())
            history['lr'].append(current_lr)
            
            if verbose and epoch % 100 == 0:
                elapsed = time.time() - start_time
                print(f"Epoch {epoch:5d}/{self.config.epochs:5d} | "
                      f"Total: {total_loss.item():.6f} | "
                      f"Data: {data_loss.item():.6f} | "
                      f"PDE: {pde_loss.item():.6f} | "
                      f"LR: {current_lr:.2e} | "
                      f"Time: {elapsed:.1f}s")
        
        self.trained = True
        self.training_history = history
        
        return {
            'history': history,
            'final_loss': total_loss.item(),
            'training_time': time.time() - start_time,
            'freq': prepared['freq'],
            'conductivity': sigma,
            'permeability': mu
        }

    def predict(self, positions: np.ndarray) -> np.ndarray:
        if not self.trained or self.network is None:
            raise ValueError("Model not trained. Call train() first.")
        
        if positions.ndim == 1:
            positions = positions.reshape(-1, 1)
        
        if positions.shape[1] == 1:
            x = positions[:, 0]
            y = np.zeros_like(x)
            z = np.zeros_like(x)
            positions = np.column_stack([x, y, z])
        
        x_tensor = torch.tensor(positions, dtype=torch.float32, device=self.config.device)
        
        with torch.no_grad():
            predictions = self.network(x_tensor).cpu().numpy()
        
        complex_predictions = predictions[:, 0] + 1j * predictions[:, 1]
        
        return complex_predictions

    def reconstruct_crack_profile(self,
                                  data: EddyCurrentData,
                                  grid_resolution: int = 100,
                                  threshold_sigma: float = 2.0) -> Dict:
        if not self.trained:
            raise ValueError("Model not trained. Call train() first.")
        
        positions = data.positions
        if positions.ndim == 1:
            positions = positions.reshape(-1, 1)
        
        x_min, x_max = positions[:, 0].min(), positions[:, 0].max()
        
        if positions.shape[1] >= 2:
            y_min, y_max = positions[:, 1].min(), positions[:, 1].max()
        else:
            y_min, y_max = -0.01, 0.01
        
        grid_x = np.linspace(x_min, x_max, grid_resolution)
        grid_y = np.linspace(y_min, y_max, grid_resolution)
        X, Y = np.meshgrid(grid_x, grid_y)
        
        grid_points = np.column_stack([X.ravel(), Y.ravel(), np.zeros_like(X.ravel())])
        
        predicted_impedance = self.predict(grid_points)
        predicted_amplitude = np.abs(predicted_impedance).reshape(grid_resolution, grid_resolution)
        
        baseline = np.median(predicted_amplitude)
        std_val = np.std(predicted_amplitude)
        threshold = baseline + threshold_sigma * std_val
        
        anomaly_mask = predicted_amplitude > threshold
        
        from scipy.ndimage import label, find_objects, center_of_mass
        
        labeled, num_regions = label(anomaly_mask)
        
        cracks = []
        if num_regions > 0:
            regions = find_objects(labeled)
            
            for i, region in enumerate(regions):
                region_data = predicted_amplitude[region]
                max_val = np.max(region_data)
                
                cm = center_of_mass(labeled == (i + 1))
                center_x = grid_x[int(cm[1])]
                center_y = grid_y[int(cm[0])]
                
                length_x = (grid_x[region[1].stop] - grid_x[region[1].start])
                length_y = (grid_y[region[0].stop] - grid_y[region[0].start])
                
                max_depth_idx = np.unravel_index(np.argmax(region_data), region_data.shape)
                estimated_depth = (max_val - baseline) / std_val * 0.001
                
                cracks.append({
                    'crack_id': i,
                    'center': (center_x, center_y),
                    'length_x': length_x,
                    'length_y': length_y,
                    'max_amplitude': float(max_val),
                    'estimated_depth': float(estimated_depth),
                    'area': int(np.sum(labeled[region] == (i + 1))),
                    'confidence': float(min(1.0, (max_val - baseline) / (threshold_sigma * std_val)))
                })
        
        return {
            'grid_x': grid_x,
            'grid_y': grid_y,
            'reconstructed_amplitude': predicted_amplitude,
            'anomaly_mask': anomaly_mask,
            'cracks': cracks,
            'baseline': float(baseline),
            'threshold': float(threshold)
        }

    def save_model(self, filepath: str) -> None:
        if self.network is None:
            raise ValueError("No model to save.")
        
        torch.save({
            'model_state_dict': self.network.state_dict(),
            'config': self.config,
            'pde': {
                'frequency': self.pde.frequency if self.pde else None,
                'conductivity': self.pde.sigma if self.pde else None,
                'permeability': self.pde.mu if self.pde else None,
            },
            'trained': self.trained,
            'training_history': self.training_history
        }, filepath)

    def load_model(self, filepath: str) -> None:
        checkpoint = torch.load(filepath, map_location=self.config.device)
        
        config = checkpoint['config']
        if isinstance(config, dict):
            config = PINNConfig(**config)
        self.config = config
        
        self.network = PINNNetwork(
            input_dim=3,
            output_dim=2,
            hidden_layers=self.config.hidden_layers
        ).to(self.config.device)
        
        self.network.load_state_dict(checkpoint['model_state_dict'])
        
        pde_data = checkpoint.get('pde', {})
        if pde_data.get('frequency') is not None:
            self.pde = HelmholtzPDE(
                pde_data['frequency'],
                pde_data['conductivity'],
                pde_data['permeability']
            )
        
        self.trained = checkpoint.get('trained', True)
        self.training_history = checkpoint.get('training_history', {})


class PINNInverter:
    def __init__(self, config: Optional[PINNConfig] = None):
        self.config = config or PINNConfig()
        self.models = {}
        self.preprocessor = Preprocessor()

    def invert(self,
               data: EddyCurrentData,
               freq_indices: Optional[List[int]] = None,
               use_multi_freq: bool = True,
               preprocess: bool = True,
               verbose: bool = True) -> Dict:
        if freq_indices is None:
            freq_indices = list(range(len(data.frequencies)))
        
        if use_multi_freq and len(freq_indices) > 1:
            results = []
            for freq_idx in freq_indices:
                if verbose:
                    print(f"\n=== Training PINN for frequency {data.frequencies[freq_idx]/1000:.1f} kHz ===")
                
                model = CrackReconstructorPINN(self.config)
                train_result = model.train(data, freq_idx, verbose=verbose)
                reconstruct_result = model.reconstruct_crack_profile(data)
                
                self.models[freq_idx] = model
                
                results.append({
                    'freq_idx': freq_idx,
                    'freq_hz': data.frequencies[freq_idx],
                    'training': train_result,
                    'reconstruction': reconstruct_result
                })
            
            return self._fuse_multi_freq_results(results)
        else:
            freq_idx = freq_indices[0]
            if verbose:
                print(f"\n=== Training PINN for frequency {data.frequencies[freq_idx]/1000:.1f} kHz ===")
            
            model = CrackReconstructorPINN(self.config)
            train_result = model.train(data, freq_idx, verbose=verbose)
            reconstruct_result = model.reconstruct_crack_profile(data)
            
            self.models[freq_idx] = model
            
            return {
                'freq_idx': freq_idx,
                'freq_hz': data.frequencies[freq_idx],
                'training': train_result,
                'reconstruction': reconstruct_result,
                'multi_freq': False
            }

    def _fuse_multi_freq_results(self, results: List[Dict]) -> Dict:
        n_results = len(results)
        if n_results == 0:
            return {}
        
        reference = results[0]['reconstruction']
        grid_x = reference['grid_x']
        grid_y = reference['grid_y']
        n_x, n_y = len(grid_x), len(grid_y)
        
        fused_amplitude = np.zeros((n_y, n_x))
        fused_mask = np.zeros((n_y, n_x), dtype=bool)
        
        weights = []
        for result in results:
            final_loss = result['training']['final_loss']
            weight = 1.0 / (final_loss + 1e-10)
            weights.append(weight)
        
        weights = np.array(weights)
        weights /= weights.sum()
        
        for i, result in enumerate(results):
            recon = result['reconstruction']
            fused_amplitude += recon['reconstructed_amplitude'] * weights[i]
            fused_mask = fused_mask | recon['anomaly_mask']
        
        baseline = np.median(fused_amplitude)
        std_val = np.std(fused_amplitude)
        threshold_sigma = 2.0
        threshold = baseline + threshold_sigma * std_val
        
        from scipy.ndimage import label, find_objects, center_of_mass
        
        labeled, num_regions = label(fused_mask)
        
        cracks = []
        if num_regions > 0:
            regions = find_objects(labeled)
            
            for i, region in enumerate(regions):
                region_data = fused_amplitude[region]
                max_val = np.max(region_data)
                
                cm = center_of_mass(labeled == (i + 1))
                center_x = grid_x[int(cm[1])]
                center_y = grid_y[int(cm[0])]
                
                length_x = (grid_x[region[1].stop] - grid_x[region[1].start])
                length_y = (grid_y[region[0].stop] - grid_y[region[0].start])
                
                estimated_depth = (max_val - baseline) / std_val * 0.001
                
                cracks.append({
                    'crack_id': i,
                    'center': (center_x, center_y),
                    'length_x': length_x,
                    'length_y': length_y,
                    'max_amplitude': float(max_val),
                    'estimated_depth': float(estimated_depth),
                    'area': int(np.sum(labeled[region] == (i + 1))),
                    'confidence': float(min(1.0, (max_val - baseline) / (threshold_sigma * std_val)))
                })
        
        return {
            'multi_freq': True,
            'n_frequencies': n_results,
            'per_freq_results': results,
            'weights': weights.tolist(),
            'fused': {
                'grid_x': grid_x,
                'grid_y': grid_y,
                'reconstructed_amplitude': fused_amplitude,
                'anomaly_mask': fused_mask,
                'cracks': cracks,
                'baseline': float(baseline),
                'threshold': float(threshold)
            }
        }

    def save_all_models(self, directory: str) -> None:
        import os
        os.makedirs(directory, exist_ok=True)
        
        for freq_idx, model in self.models.items():
            filepath = os.path.join(directory, f'pinn_model_freq_{freq_idx}.pt')
            model.save_model(filepath)

    def load_all_models(self, directory: str) -> None:
        import os
        import glob
        
        model_files = glob.glob(os.path.join(directory, 'pinn_model_freq_*.pt'))
        
        for filepath in model_files:
            filename = os.path.basename(filepath)
            freq_idx = int(filename.replace('pinn_model_freq_', '').replace('.pt', ''))
            
            model = CrackReconstructorPINN(self.config)
            model.load_model(filepath)
            self.models[freq_idx] = model
