import numpy as np
from typing import List, Tuple, Optional, Callable, Dict
from dataclasses import dataclass, field
from .models import (VelocityModel, Shot, Receiver, TravelTimeData,
                     InversionConfig, UncertaintyConfig, AnisotropicParams)
from .ray_tracing import ShortestPathRayTracer
from .anisotropic import VTIRayTracer
from .inversion import TomographicInversion


@dataclass
class MonteCarloResult:
    n_samples: int
    velocity_mean: np.ndarray
    velocity_std: np.ndarray
    velocity_median: np.ndarray
    velocity_percentile_5: np.ndarray
    velocity_percentile_95: np.ndarray
    rms_mean: float
    rms_std: float
    rms_distribution: np.ndarray
    all_models: List[VelocityModel] = field(default_factory=list)
    epsilon_mean: Optional[np.ndarray] = None
    epsilon_std: Optional[np.ndarray] = None
    delta_mean: Optional[np.ndarray] = None
    delta_std: Optional[np.ndarray] = None


def add_gaussian_noise(data: List[TravelTimeData], std: float,
                       relative: bool = False) -> List[TravelTimeData]:
    import copy
    noisy_data = []
    
    for d in data:
        noise_std = std * d.travel_time if relative else std
        noisy_tt = d.travel_time + np.random.normal(0, noise_std)
        new_d = copy.deepcopy(d)
        new_d.travel_time = noisy_tt
        new_d.uncertainty = noise_std
        noisy_data.append(new_d)
    
    return noisy_data


def perturb_velocity_model(model: VelocityModel, prior_std: float,
                          spatial_correlation: float = 0.0) -> VelocityModel:
    perturbed = model.copy()
    
    if spatial_correlation > 0:
        from scipy.ndimage import gaussian_filter
        noise = np.random.normal(0, prior_std, model.velocity.shape)
        sigma = spatial_correlation / min(model.dx, model.dz)
        noise = gaussian_filter(noise, sigma=sigma)
    else:
        noise = np.random.normal(0, prior_std, model.velocity.shape)
    
    perturbed.velocity += noise
    perturbed.velocity = np.clip(perturbed.velocity, 1000.0, 5000.0)
    perturbed.slowness = 1.0 / perturbed.velocity
    
    return perturbed


def perturb_travel_times(data: List[TravelTimeData],
                         std: float, relative: bool = False) -> List[TravelTimeData]:
    return add_gaussian_noise(data, std, relative)


def compute_posterior_statistics(models: List[VelocityModel]) -> Dict[str, np.ndarray]:
    if not models:
        return {}
    
    velocities = np.array([m.velocity for m in models])
    
    stats = {
        'mean': np.mean(velocities, axis=0),
        'std': np.std(velocities, axis=0),
        'median': np.median(velocities, axis=0),
        'p5': np.percentile(velocities, 5, axis=0),
        'p95': np.percentile(velocities, 95, axis=0),
    }
    
    if models[0].is_anisotropic and models[0].anisotropy is not None:
        epsilons = np.array([m.anisotropy.epsilon for m in models])
        deltas = np.array([m.anisotropy.delta for m in models])
        
        stats['epsilon_mean'] = np.mean(epsilons, axis=0)
        stats['epsilon_std'] = np.std(epsilons, axis=0)
        stats['delta_mean'] = np.mean(deltas, axis=0)
        stats['delta_std'] = np.std(deltas, axis=0)
    
    return stats


def compute_resolution_matrix(G: np.ndarray, damping: float = 0.01) -> np.ndarray:
    n_data, n_model = G.shape
    
    GtG = G.T @ G
    if damping > 0:
        GtG += damping ** 2 * np.eye(n_model)
    
    try:
        GtG_inv = np.linalg.inv(GtG)
        resolution = GtG_inv @ G.T @ G
    except np.linalg.LinAlgError:
        GtG_inv = np.linalg.pinv(GtG)
        resolution = GtG_inv @ G.T @ G
    
    return resolution


def compute_covariance_matrix(G: np.ndarray, data_std: float,
                              damping: float = 0.01) -> np.ndarray:
    n_data, n_model = G.shape
    
    Cd = data_std ** 2 * np.eye(n_data)
    
    GtG = G.T @ G
    if damping > 0:
        GtG += damping ** 2 * np.eye(n_model)
    
    try:
        GtG_inv = np.linalg.inv(GtG)
    except np.linalg.LinAlgError:
        GtG_inv = np.linalg.pinv(GtG)
    
    Cm = GtG_inv @ G.T @ Cd @ G @ GtG_inv
    
    return Cm


def compute_uncertainty_from_covariance(Cm: np.ndarray, nx: int, nz: int) -> np.ndarray:
    return np.sqrt(np.diag(Cm)).reshape((nz, nx))


class MonteCarloAnalysis:
    def __init__(self, base_model: VelocityModel,
                 config: Optional[UncertaintyConfig] = None,
                 inversion_config: Optional[InversionConfig] = None):
        self.base_model = base_model
        self.config = config if config else UncertaintyConfig()
        self.inversion_config = inversion_config if inversion_config else InversionConfig()
        self.result: Optional[MonteCarloResult] = None
    
    def run_linear_uncertainty(self, shots: List[Shot],
                               receivers: List[Receiver],
                               data: List[TravelTimeData]) -> np.ndarray:
        if self.base_model.is_anisotropic:
            ray_tracer = VTIRayTracer(self.base_model)
        else:
            ray_tracer = ShortestPathRayTracer(self.base_model)
        
        _, sensitivity = ray_tracer.forward_modeling(
            shots, receivers, data, compute_rays=True, update_density=True
        )
        
        valid = [i for i, d in enumerate(data) if np.isfinite(d.residual)]
        G = sensitivity[valid, :]
        G = G[:, :self.base_model.nx * self.base_model.nz]
        
        Cm = compute_covariance_matrix(
            G, self.config.travel_time_std, self.inversion_config.damping
        )
        
        return compute_uncertainty_from_covariance(
            Cm, self.base_model.nx, self.base_model.nz
        )
    
    def run_monte_carlo(self, shots: List[Shot],
                        receivers: List[Receiver],
                        data: List[TravelTimeData],
                        n_samples: Optional[int] = None,
                        progress_callback: Optional[Callable] = None,
                        use_anisotropic: bool = False,
                        invert_epsilon: bool = True,
                        invert_delta: bool = True) -> MonteCarloResult:
        if n_samples is None:
            n_samples = self.config.n_monte_carlo_samples
        
        all_models = []
        all_rms = []
        
        for i in range(n_samples):
            perturbed_model = perturb_velocity_model(
                self.base_model, self.config.velocity_prior_std
            )
            
            if use_anisotropic:
                perturbed_model.is_anisotropic = True
                if perturbed_model.anisotropy is None:
                    perturbed_model.anisotropy = AnisotropicParams.create_isotropic(
                        perturbed_model.nx, perturbed_model.nz
                    )
                perturbed_model.anisotropy.epsilon += np.random.normal(
                    0, self.config.epsilon_prior_std,
                    perturbed_model.anisotropy.epsilon.shape
                )
                perturbed_model.anisotropy.delta += np.random.normal(
                    0, self.config.delta_prior_std,
                    perturbed_model.anisotropy.delta.shape
                )
            
            noisy_data = perturb_travel_times(
                data, self.config.travel_time_std
            )
            
            if use_anisotropic:
                from .anisotropic import AnisotropicTomography
                inv = AnisotropicTomography(perturbed_model, self.inversion_config)
                history = inv.run_full_inversion(
                    shots, receivers, noisy_data,
                    progress_callback=None,
                    invert_epsilon=invert_epsilon,
                    invert_delta=invert_delta
                )
            else:
                inv = TomographicInversion(perturbed_model, self.inversion_config)
                history = inv.run_full_inversion(
                    shots, receivers, noisy_data,
                    progress_callback=None
                )
            
            if history and 'rms_after' in history[-1]:
                all_rms.append(history[-1]['rms_after'])
                all_models.append(inv.model)
            
            if progress_callback:
                progress_callback({
                    'sample': i + 1,
                    'total': n_samples,
                    'rms': history[-1]['rms_after'] if history else None
                })
        
        stats = compute_posterior_statistics(all_models)
        
        result = MonteCarloResult(
            n_samples=len(all_models),
            velocity_mean=stats.get('mean', self.base_model.velocity),
            velocity_std=stats.get('std', np.zeros_like(self.base_model.velocity)),
            velocity_median=stats.get('median', self.base_model.velocity),
            velocity_percentile_5=stats.get('p5', self.base_model.velocity),
            velocity_percentile_95=stats.get('p95', self.base_model.velocity),
            rms_mean=np.mean(all_rms) if all_rms else 0.0,
            rms_std=np.std(all_rms) if all_rms else 0.0,
            rms_distribution=np.array(all_rms),
            all_models=all_models,
            epsilon_mean=stats.get('epsilon_mean'),
            epsilon_std=stats.get('epsilon_std'),
            delta_mean=stats.get('delta_mean'),
            delta_std=stats.get('delta_std')
        )
        
        self.result = result
        return result
    
    def compute_uncertainty_bounds(self, result: Optional[MonteCarloResult] = None,
                                    confidence: float = 0.95) -> Tuple[np.ndarray, np.ndarray]:
        if result is None:
            result = self.result
        if result is None:
            raise ValueError("No Monte Carlo result available")
        
        alpha = (1 - confidence) / 2
        lower = np.percentile([m.velocity for m in result.all_models], alpha * 100, axis=0)
        upper = np.percentile([m.velocity for m in result.all_models], (1 - alpha) * 100, axis=0)
        
        return lower, upper
    
    def compute_parameter_correlation(self, result: Optional[MonteCarloResult] = None,
                                       ix1: int = 0, iz1: int = 0,
                                       ix2: int = 1, iz2: int = 1) -> float:
        if result is None:
            result = self.result
        if result is None:
            raise ValueError("No Monte Carlo result available")
        
        v1 = np.array([m.velocity[iz1, ix1] for m in result.all_models])
        v2 = np.array([m.velocity[iz2, ix2] for m in result.all_models])
        
        return np.corrcoef(v1, v2)[0, 1]
    
    def run_bootstrap(self, shots: List[Shot],
                      receivers: List[Receiver],
                      data: List[TravelTimeData],
                      n_bootstrap: int = 100,
                      progress_callback: Optional[Callable] = None) -> MonteCarloResult:
        all_models = []
        all_rms = []
        
        for i in range(n_bootstrap):
            indices = np.random.choice(len(data), size=len(data), replace=True)
            boot_data = [data[j] for j in indices]
            
            inv = TomographicInversion(self.base_model.copy(), self.inversion_config)
            history = inv.run_full_inversion(shots, receivers, boot_data)
            
            if history and 'rms_after' in history[-1]:
                all_rms.append(history[-1]['rms_after'])
                all_models.append(inv.model)
            
            if progress_callback:
                progress_callback({
                    'sample': i + 1,
                    'total': n_bootstrap,
                    'rms': history[-1]['rms_after'] if history else None
                })
        
        stats = compute_posterior_statistics(all_models)
        
        return MonteCarloResult(
            n_samples=len(all_models),
            velocity_mean=stats.get('mean', self.base_model.velocity),
            velocity_std=stats.get('std', np.zeros_like(self.base_model.velocity)),
            velocity_median=stats.get('median', self.base_model.velocity),
            velocity_percentile_5=stats.get('p5', self.base_model.velocity),
            velocity_percentile_95=stats.get('p95', self.base_model.velocity),
            rms_mean=np.mean(all_rms) if all_rms else 0.0,
            rms_std=np.std(all_rms) if all_rms else 0.0,
            rms_distribution=np.array(all_rms),
            all_models=all_models
        )
