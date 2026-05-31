import numpy as np
from typing import List, Tuple, Callable, Optional
from .models import VelocityModel, InversionConfig, TravelTimeData, Shot, Receiver
from .ray_tracing import ShortestPathRayTracer


def lsqr(A: np.ndarray, b: np.ndarray, damp: float = 0.0, atol: float = 1e-6,
         btol: float = 1e-6, conlim: float = 1e8, maxiter: int = 100,
         show: bool = False) -> Tuple[np.ndarray, dict]:
    m, n = A.shape
    
    x = np.zeros(n)
    
    if damp < 0.0:
        damp = 0.0
    
    u = b.copy()
    beta = np.linalg.norm(u)
    if beta > 0:
        u = u / beta
    
    v = A.T @ u
    alpha = np.linalg.norm(v)
    if alpha > 0:
        v = v / alpha
    
    w = v.copy()
    
    rhobar = alpha
    phibar = beta
    bnorm = beta
    rnorm = beta
    r1norm = rnorm
    r2norm = rnorm
    ddnorm = 0.0
    xnorm = 0.0
    xxnorm = 0.0
    z = 0.0
    cs2 = -1.0
    sn2 = 0.0
    
    istop = 0
    itn = 0
    
    anorm = 0.0
    acond = 0.0
    arnorm = alpha * beta
    
    if arnorm == 0.0:
        return x, {
            'istop': 0, 'itn': 0, 'r1norm': 0.0, 'r2norm': 0.0,
            'anorm': 0.0, 'acond': 0.0, 'arnorm': 0.0, 'xnorm': 0.0
        }
    
    while itn < maxiter:
        itn += 1
        
        u = A @ v - alpha * u
        beta = np.linalg.norm(u)
        if beta > 0:
            u = u / beta
        
        anorm = np.sqrt(anorm ** 2 + alpha ** 2 + beta ** 2 + damp ** 2)
        
        v = A.T @ u - beta * v
        alpha = np.linalg.norm(v)
        if alpha > 0:
            v = v / alpha
        
        rhobar1 = np.sqrt(rhobar ** 2 + damp ** 2)
        cs1 = rhobar / rhobar1
        sn1 = damp / rhobar1
        psi = sn1 * phibar
        phibar = cs1 * phibar
        
        rho = np.sqrt(rhobar1 ** 2 + beta ** 2)
        cs = rhobar1 / rho
        sn = beta / rho
        theta = sn * alpha
        rhobar = -cs * alpha
        phi = cs * phibar
        phibar = sn * phibar
        
        tau = sn * phi
        
        t1 = phi / rho
        t2 = -theta / rho
        
        dk = w / rho
        ddnorm = ddnorm + np.linalg.norm(dk) ** 2
        
        x = x + t1 * w
        w = v + t2 * w
        
        delta = sn2 * rho
        gambar = -cs2 * rho
        rhs = phi - delta * z
        zbar = rhs / gambar
        xnorm = np.sqrt(xxnorm + zbar ** 2)
        gamma = np.sqrt(gambar ** 2 + theta ** 2)
        cs2 = gambar / gamma
        sn2 = theta / gamma
        z = rhs / gamma
        xxnorm = xxnorm + z ** 2
        
        acond = anorm * np.sqrt(ddnorm)
        res1 = phibar ** 2
        res2 = psi ** 2
        rnorm = np.sqrt(res1 + res2)
        arnorm = alpha * abs(tau)
        
        if itn == 1:
            r1norm = rnorm
            r2norm = rnorm
        
        test1 = rnorm / bnorm
        test2 = arnorm / (anorm * rnorm + 1e-30)
        test3 = 1.0 / acond
        
        t1 = test1 / (1.0 + anorm * xnorm / bnorm)
        rtol = btol + atol * anorm * xnorm / bnorm
        
        if itn >= maxiter:
            istop = 6
        if acond >= conlim:
            istop = 4
        if test3 <= 1e-12:
            istop = 5
        if test2 <= atol:
            istop = 2
        if test1 <= rtol:
            istop = 1
        
        if show and itn % 10 == 0:
            print(f"LSQR iter {itn}: r1norm={r1norm:.4e}, r2norm={r2norm:.4e}, "
                  f"arnorm={arnorm:.4e}, xnorm={xnorm:.4e}")
        
        if istop != 0:
            break
    
    r1norm = np.sqrt(phibar ** 2 + psi ** 2)
    r2norm = r1norm
    
    return x, {
        'istop': istop, 'itn': itn, 'r1norm': r1norm, 'r2norm': r2norm,
        'anorm': anorm, 'acond': acond, 'arnorm': arnorm, 'xnorm': xnorm
    }


def build_regularization_matrix(nx: int, nz: int, lambda_reg: float,
                                 ray_density: Optional[np.ndarray] = None,
                                 use_ray_weighting: bool = False,
                                 curvature: bool = False,
                                 second_deriv_weight: float = 0.5) -> np.ndarray:
    n = nx * nz
    
    if use_ray_weighting and ray_density is not None:
        density_flat = ray_density.flatten()
        max_density = density_flat.max()
        if max_density > 0:
            weights = 1.0 / (1.0 + density_flat / max_density)
            weights = weights / weights.mean()
        else:
            weights = np.ones(n)
    else:
        weights = np.ones(n)
    
    rows = []
    
    for ix in range(nx - 1):
        for iz in range(nz):
            idx = iz * nx + ix
            w = lambda_reg * np.sqrt(weights[idx] * weights[idx + 1])
            row = np.zeros(n)
            row[idx] = -w
            row[idx + 1] = w
            rows.append(row)
    
    for ix in range(nx):
        for iz in range(nz - 1):
            idx = iz * nx + ix
            w = lambda_reg * np.sqrt(weights[idx] * weights[idx + nx])
            row = np.zeros(n)
            row[idx] = -w
            row[idx + nx] = w
            rows.append(row)
    
    if curvature:
        lambda2 = lambda_reg * second_deriv_weight
        for ix in range(1, nx - 1):
            for iz in range(nz):
                idx = iz * nx + ix
                w = lambda2 * weights[idx]
                row = np.zeros(n)
                row[idx - 1] = w
                row[idx] = -2 * w
                row[idx + 1] = w
                rows.append(row)
        
        for ix in range(nx):
            for iz in range(1, nz - 1):
                idx = iz * nx + ix
                w = lambda2 * weights[idx]
                row = np.zeros(n)
                row[idx - nx] = w
                row[idx] = -2 * w
                row[idx + nx] = w
                rows.append(row)
    
    return np.vstack(rows) if rows else np.zeros((0, n))


def compute_optimal_regularization(G: np.ndarray, dt: np.ndarray,
                                   nx: int, nz: int,
                                   ray_density: Optional[np.ndarray] = None,
                                   config: Optional[InversionConfig] = None) -> Tuple[float, float]:
    if config is None:
        config = InversionConfig()
    
    if not config.adaptive_regularization:
        return config.regularization, config.damping
    
    sigma_d = np.std(dt)
    if sigma_d < 1e-10:
        sigma_d = 1e-10
    
    G_norm = np.linalg.norm(G, 'fro')
    n_data, n_model = G.shape
    
    ratio = n_data / n_model
    
    if ratio < 0.5:
        base_reg = config.reg_max
    elif ratio < 1.0:
        base_reg = 0.5 * (config.reg_min + config.reg_max)
    else:
        base_reg = config.reg_min
    
    try:
        GtG = G.T @ G
        eigenvalues = np.linalg.eigvalsh(GtG)
        eigenvalues = eigenvalues[eigenvalues > 0]
        
        if len(eigenvalues) > 0:
            cond_num = np.sqrt(eigenvalues.max() / eigenvalues.min())
            
            if cond_num > 1e4:
                base_reg = min(config.reg_max, base_reg * 2.0)
            elif cond_num > 1e3:
                base_reg = min(config.reg_max, base_reg * 1.5)
            elif cond_num < 100:
                base_reg = max(config.reg_min, base_reg * 0.7)
    except:
        pass
    
    if ray_density is not None:
        coverage_fraction = np.sum(ray_density > 0) / (nx * nz)
        if coverage_fraction < 0.3:
            base_reg = min(config.reg_max, base_reg * 1.5)
        elif coverage_fraction > 0.7:
            base_reg = max(config.reg_min, base_reg * 0.8)
    
    damping = config.damping_min + 0.5 * (config.damping_max - config.damping_min) * (1.0 - ratio)
    damping = max(config.damping_min, min(config.damping_max, damping))
    
    base_reg = max(config.reg_min, min(config.reg_max, base_reg))
    
    return base_reg, damping


def lcurve_criterion(G: np.ndarray, dt: np.ndarray, nx: int, nz: int,
                     ray_density: Optional[np.ndarray] = None,
                     config: Optional[InversionConfig] = None) -> Tuple[float, float]:
    if config is None:
        config = InversionConfig()
    
    reg_values = np.logspace(
        np.log10(max(config.reg_min, 1e-4)),
        np.log10(min(config.reg_max, 10.0)),
        10
    )
    
    residuals = []
    solutions = []
    
    for reg in reg_values:
        L = build_regularization_matrix(
            nx, nz, reg, ray_density,
            use_ray_weighting=config.use_ray_weighted_reg,
            curvature=config.curvature_regularization,
            second_deriv_weight=config.second_derivative_weight
        )
        
        G_aug = np.vstack([G, L])
        dt_aug = np.hstack([dt, np.zeros(L.shape[0])])
        
        x, _ = lsqr(G_aug, dt_aug, damp=config.damping, maxiter=50)
        
        Gx = G @ x
        residual = np.linalg.norm(Gx - dt)
        model_norm = np.linalg.norm(x)
        
        residuals.append(residual)
        solutions.append(model_norm)
    
    residuals = np.array(residuals)
    solutions = np.array(solutions)
    
    log_res = np.log10(residuals + 1e-30)
    log_sol = np.log10(solutions + 1e-30)
    
    curvature = np.zeros_like(log_res)
    for i in range(1, len(log_res) - 1):
        d1 = (log_res[i] - log_res[i-1]) / (log_sol[i] - log_sol[i-1] + 1e-10)
        d2 = (log_res[i+1] - log_res[i]) / (log_sol[i+1] - log_sol[i] + 1e-10)
        curvature[i] = abs(d2 - d1) / (1 + d1**2)**1.5
    
    best_idx = np.argmax(curvature[1:-1]) + 1
    optimal_reg = reg_values[best_idx]
    
    optimal_reg = max(config.reg_min, min(config.reg_max, optimal_reg))
    
    return optimal_reg, config.damping


class TomographicInversion:
    def __init__(self, model: VelocityModel, config: Optional[InversionConfig] = None):
        self.model = model
        self.config = config if config else InversionConfig()
        self.initial_model = model.copy()
        self.history: List[dict] = []
        self.current_iteration = 0

    def reset(self):
        self.model = self.initial_model.copy()
        self.history = []
        self.current_iteration = 0

    def compute_residuals(self, data: List[TravelTimeData]) -> np.ndarray:
        residuals = []
        for d in data:
            if np.isfinite(d.residual):
                residuals.append(d.residual)
        return np.array(residuals)

    def compute_rms(self, residuals: np.ndarray) -> float:
        if len(residuals) == 0:
            return 0.0
        return np.sqrt(np.mean(residuals ** 2))

    def run_iteration(self, shots: List[Shot], receivers: List[Receiver],
                      data: List[TravelTimeData]) -> dict:
        self.current_iteration += 1
        
        ray_tracer = ShortestPathRayTracer(self.model)
        updated_data, sensitivity = ray_tracer.forward_modeling(
            shots, receivers, data, compute_rays=True, update_density=True
        )
        
        residuals = self.compute_residuals(updated_data)
        rms_obs = self.compute_rms(residuals)
        
        valid_indices = [i for i, d in enumerate(updated_data) if np.isfinite(d.residual)]
        if len(valid_indices) < self.model.nx * self.model.nz * 0.1:
            return {
                'iteration': self.current_iteration,
                'rms_before': rms_obs,
                'rms_after': rms_obs,
                'error': 'Not enough valid data'
            }
        
        G = sensitivity[valid_indices, :]
        dt = residuals[valid_indices]
        
        ray_density = self.model.ray_density.copy()
        
        if self.config.adaptive_regularization:
            if self.current_iteration == 1 or self.current_iteration % 3 == 0:
                try:
                    if len(valid_indices) < 100:
                        reg, damp = compute_optimal_regularization(
                            G, dt, self.model.nx, self.model.nz,
                            ray_density, self.config
                        )
                    else:
                        subset = np.random.choice(len(valid_indices), size=min(100, len(valid_indices)), replace=False)
                        reg, damp = compute_optimal_regularization(
                            G[subset, :], dt[subset], self.model.nx, self.model.nz,
                            ray_density, self.config
                        )
                    self.config.regularization = reg
                    self.config.damping = damp
                except:
                    pass
        
        iter_info_extra = {
            'regularization_used': self.config.regularization,
            'damping_used': self.config.damping
        }
        
        if self.config.regularization > 0:
            L = build_regularization_matrix(
                self.model.nx, self.model.nz, self.config.regularization,
                ray_density=ray_density,
                use_ray_weighting=self.config.use_ray_weighted_reg,
                curvature=self.config.curvature_regularization,
                second_deriv_weight=self.config.second_derivative_weight
            )
            G_aug = np.vstack([G, L])
            dt_aug = np.hstack([dt, np.zeros(L.shape[0])])
        else:
            G_aug = G
            dt_aug = dt
        
        slowness_update, lsqr_info = lsqr(
            G_aug, dt_aug,
            damp=self.config.damping,
            atol=self.config.lsqr_tol,
            btol=self.config.lsqr_tol,
            maxiter=self.config.max_iterations,
            show=False
        )
        
        slowness_update_2d = slowness_update.reshape((self.model.nz, self.model.nx))
        slowness_update_2d *= self.config.update_scale
        
        new_slowness = self.model.slowness + slowness_update_2d
        new_velocity = 1.0 / new_slowness
        new_velocity = np.clip(new_velocity, self.config.min_velocity, self.config.max_velocity)
        
        velocity_update = new_velocity - self.model.velocity
        
        self.model.update_velocity(velocity_update)
        
        ray_tracer2 = ShortestPathRayTracer(self.model)
        final_data, _ = ray_tracer2.forward_modeling(
            shots, receivers, updated_data, compute_rays=False, update_density=False
        )
        
        final_residuals = self.compute_residuals(final_data)
        rms_final = self.compute_rms(final_residuals)
        
        iter_info = {
            'iteration': self.current_iteration,
            'rms_before': rms_obs,
            'rms_after': rms_final,
            'rms_reduction': (rms_obs - rms_final) / rms_obs * 100 if rms_obs > 0 else 0,
            'velocity_update_norm': np.linalg.norm(velocity_update),
            'slowness_update_norm': np.linalg.norm(slowness_update_2d),
            'lsqr_info': lsqr_info,
            'n_valid_data': len(valid_indices),
            'final_data': final_data,
            'velocity_update': velocity_update
        }
        iter_info.update(iter_info_extra)
        
        self.history.append(iter_info)
        
        return iter_info

    def run_full_inversion(self, shots: List[Shot], receivers: List[Receiver],
                           data: List[TravelTimeData],
                           progress_callback: Optional[Callable] = None) -> List[dict]:
        self.reset()
        
        for i in range(self.config.max_iterations):
            info = self.run_iteration(shots, receivers, data)
            
            if progress_callback:
                progress_callback(info)
            
            if 'error' in info:
                break
            
            if info['rms_reduction'] < 0.1 and i > 2:
                break
            
            if i > 0 and abs(self.history[i]['rms_after'] - self.history[i-1]['rms_after']) < 1e-5:
                break
        
        return self.history
