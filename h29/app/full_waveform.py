import numpy as np
from typing import List, Tuple, Optional, Callable
from scipy.signal import ricker, hilbert
from .models import VelocityModel, Shot, Receiver, TravelTimeData


class WaveSolver2D:
    def __init__(self, model: VelocityModel, dt: float = 0.0005,
                 t_max: float = 1.0, pml_width: int = 20):
        self.model = model
        self.nx = model.nx
        self.nz = model.nz
        self.dx = model.dx
        self.dz = model.dz
        self.dt = dt
        self.t_max = t_max
        self.pml_width = pml_width
        self.nt = int(t_max / dt) + 1
        
        self.nx_pml = self.nx + 2 * pml_width
        self.nz_pml = self.nz + 2 * pml_width
        
        self._build_pml_profiles()
    
    def _build_pml_profiles(self):
        self.sigma_x = np.zeros((self.nz_pml, self.nx_pml))
        self.sigma_z = np.zeros((self.nz_pml, self.nx_pml))
        
        max_sigma = 3.0 / (2 * self.dx)
        
        for i in range(self.pml_width):
            profile = max_sigma * (1.0 - np.cos(np.pi * i / (2 * self.pml_width))) ** 2
            
            self.sigma_x[:, i] = profile
            self.sigma_x[:, -i-1] = profile
            
            self.sigma_z[i, :] = profile
            self.sigma_z[-i-1, :] = profile
    
    def _extend_model(self, velocity: np.ndarray) -> np.ndarray:
        vel = np.ones((self.nz_pml, self.nx_pml)) * velocity[0, 0]
        vel[self.pml_width:-self.pml_width, self.pml_width:-self.pml_width] = velocity
        
        for i in range(self.pml_width):
            vel[self.pml_width:-self.pml_width, i] = velocity[:, 0]
            vel[self.pml_width:-self.pml_width, -i-1] = velocity[:, -1]
            vel[i, self.pml_width:-self.pml_width] = velocity[0, :]
            vel[-i-1, self.pml_width:-self.pml_width] = velocity[-1, :]
        
        return vel
    
    def _inject_source(self, p: np.ndarray, source_amplitude: float,
                       shot: Shot, it: int, wavelet: np.ndarray):
        ix = int(round((shot.x - self.model.x0) / self.dx)) + self.pml_width
        iz = int(round((shot.z - self.model.z0) / self.dz)) + self.pml_width
        
        if 0 <= ix < self.nx_pml and 0 <= iz < self.nz_pml:
            p[iz, ix] += source_amplitude * wavelet[it]
    
    def _record_seismogram(self, p: np.ndarray, receivers: List[Receiver]) -> np.ndarray:
        n_rec = len(receivers)
        seismogram = np.zeros(n_rec)
        
        for i, rec in enumerate(receivers):
            ix = int(round((rec.x - self.model.x0) / self.dx)) + self.pml_width
            iz = int(round((rec.z - self.model.z0) / self.dz)) + self.pml_width
            
            if 0 <= ix < self.nx_pml and 0 <= iz < self.nz_pml:
                seismogram[i] = p[iz, ix]
        
        return seismogram
    
    def forward_propagate(self, shot: Shot, receivers: List[Receiver],
                          wavelet: np.ndarray,
                          save_wavefield: bool = False,
                          save_interval: int = 10) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        velocity = self._extend_model(self.model.velocity)
        
        p = np.zeros((self.nz_pml, self.nx_pml))
        p_prev = np.zeros((self.nz_pml, self.nx_pml))
        p_next = np.zeros((self.nz_pml, self.nx_pml))
        
        n_rec = len(receivers)
        seismograms = np.zeros((self.nt, n_rec))
        
        wavefield_snapshots = None
        if save_wavefield:
            n_snap = self.nt // save_interval + 1
            wavefield_snapshots = np.zeros((n_snap, self.nz, self.nx))
        
        c2 = (velocity * self.dt) ** 2
        
        for it in range(self.nt):
            laplacian = (p[1:-1, 2:] - 2 * p[1:-1, 1:-1] + p[1:-1, :-2]) / self.dx ** 2 + \
                       (p[2:, 1:-1] - 2 * p[1:-1, 1:-1] + p[:-2, 1:-1]) / self.dz ** 2
            
            damping = self.sigma_z[1:-1, 1:-1] * (p[1:-1, 1:-1] - p_prev[1:-1, 1:-1]) / self.dt + \
                      self.sigma_x[1:-1, 1:-1] * (p[1:-1, 1:-1] - p_prev[1:-1, 1:-1]) / self.dt
            
            p_next[1:-1, 1:-1] = 2 * p[1:-1, 1:-1] - p_prev[1:-1, 1:-1] + \
                                 c2[1:-1, 1:-1] * laplacian - \
                                 self.dt * damping
            
            self._inject_source(p_next, 1.0, shot, it, wavelet)
            
            seismograms[it, :] = self._record_seismogram(p_next, receivers)
            
            if save_wavefield and it % save_interval == 0:
                snap_idx = it // save_interval
                wavefield_snapshots[snap_idx, :, :] = \
                    p_next[self.pml_width:-self.pml_width, self.pml_width:-self.pml_width]
            
            p_prev, p, p_next = p, p_next, p_prev
            p_next.fill(0)
        
        return seismograms, wavefield_snapshots
    
    def backward_propagate(self, residual_wavefield: np.ndarray,
                           receivers: List[Receiver],
                           time_reverse: bool = True) -> np.ndarray:
        velocity = self._extend_model(self.model.velocity)
        
        p = np.zeros((self.nz_pml, self.nx_pml))
        p_prev = np.zeros((self.nz_pml, self.nx_pml))
        p_next = np.zeros((self.nz_pml, self.nx_pml))
        
        c2 = (velocity * self.dt) ** 2
        
        gradient = np.zeros((self.nz, self.nx))
        
        rec_indices = []
        for rec in receivers:
            ix = int(round((rec.x - self.model.x0) / self.dx)) + self.pml_width
            iz = int(round((rec.z - self.model.z0) / self.dz)) + self.pml_width
            rec_indices.append((ix, iz))
        
        time_indices = np.arange(self.nt)
        if time_reverse:
            time_indices = time_indices[::-1]
        
        for it_idx, it in enumerate(time_indices):
            laplacian = (p[1:-1, 2:] - 2 * p[1:-1, 1:-1] + p[1:-1, :-2]) / self.dx ** 2 + \
                       (p[2:, 1:-1] - 2 * p[1:-1, 1:-1] + p[:-2, 1:-1]) / self.dz ** 2
            
            damping = self.sigma_z[1:-1, 1:-1] * (p[1:-1, 1:-1] - p_prev[1:-1, 1:-1]) / self.dt + \
                      self.sigma_x[1:-1, 1:-1] * (p[1:-1, 1:-1] - p_prev[1:-1, 1:-1]) / self.dt
            
            p_next[1:-1, 1:-1] = 2 * p[1:-1, 1:-1] - p_prev[1:-1, 1:-1] + \
                                 c2[1:-1, 1:-1] * laplacian - \
                                 self.dt * damping
            
            for i, (ix, iz) in enumerate(rec_indices):
                if 0 <= ix < self.nx_pml and 0 <= iz < self.nz_pml:
                    p_next[iz, ix] += self.dt ** 2 * residual_wavefield[it, i]
            
            if it_idx > 0:
                p_prev_inner = p_prev[self.pml_width:-self.pml_width, self.pml_width:-self.pml_width]
                p_inner = p[self.pml_width:-self.pml_width, self.pml_width:-self.pml_width]
                dp_dt = (p_inner - p_prev_inner) / self.dt
                gradient += dp_dt ** 2
            
            p_prev, p, p_next = p, p_next, p_prev
            p_next.fill(0)
        
        return gradient


class FullWaveformInversion:
    def __init__(self, model: VelocityModel, dt: float = 0.0005,
                 t_max: float = 1.0, f0: float = 30.0):
        self.model = model
        self.dt = dt
        self.t_max = t_max
        self.f0 = f0
        self.nt = int(t_max / dt) + 1
        self.solver = WaveSolver2D(model, dt, t_max)
        
        self.wavelet = self._generate_wavelet()
        
        self.forward_wavefield = None
        self.gradient = None
        self.objective_history = []
    
    def _generate_wavelet(self) -> np.ndarray:
        t = np.arange(self.nt) * self.dt
        t0 = 2.5 / self.f0
        tau = np.pi * self.f0 * (t - t0)
        wavelet = (1.0 - 2.0 * tau ** 2) * np.exp(-tau ** 2)
        return wavelet
    
    def _compute_objective(self, observed: np.ndarray,
                           synthetic: np.ndarray) -> Tuple[float, np.ndarray]:
        residual = synthetic - observed
        objective = 0.5 * np.sum(residual ** 2)
        return objective, residual
    
    def compute_gradient_adjoint(self, shot: Shot, receivers: List[Receiver],
                                 observed_seismograms: np.ndarray) -> Tuple[float, np.ndarray]:
        synthetic, forward_snapshots = self.solver.forward_propagate(
            shot, receivers, self.wavelet,
            save_wavefield=True, save_interval=1
        )
        
        objective, residual = self._compute_objective(observed_seismograms, synthetic)
        
        adjoint_source = residual
        
        backward_gradient = self.solver.backward_propagate(
            adjoint_source, receivers, time_reverse=True
        )
        
        gradient = -backward_gradient
        
        self.forward_wavefield = forward_snapshots
        self.gradient = gradient
        
        return objective, gradient
    
    def compute_steepest_descent_direction(self, shots: List[Shot],
                                            receivers: List[Receiver],
                                            observed_data: dict) -> Tuple[float, np.ndarray]:
        total_objective = 0.0
        total_gradient = np.zeros_like(self.model.velocity)
        
        for shot in shots:
            if shot.id not in observed_data:
                continue
            
            obj, grad = self.compute_gradient_adjoint(
                shot, receivers, observed_data[shot.id]
            )
            total_objective += obj
            total_gradient += grad
        
        grad_norm = np.linalg.norm(total_gradient)
        if grad_norm > 0:
            direction = -total_gradient / grad_norm
        else:
            direction = np.zeros_like(total_gradient)
        
        return total_objective, direction
    
    def line_search(self, shots: List[Shot], receivers: List[Receiver],
                    observed_data: dict, direction: np.ndarray,
                    initial_step: float = 10.0, max_steps: int = 10) -> Tuple[float, np.ndarray]:
        step = initial_step
        prev_obj = None
        
        for i in range(max_steps):
            test_model = self.model.copy()
            test_model.velocity += step * direction
            test_solver = WaveSolver2D(test_model, self.dt, self.t_max)
            
            test_obj = 0.0
            for shot in shots:
                if shot.id not in observed_data:
                    continue
                synth, _ = test_solver.forward_propagate(
                    shot, receivers, self.wavelet
                )
                obj, _ = self._compute_objective(observed_data[shot.id], synth)
                test_obj += obj
            
            if prev_obj is None or test_obj < prev_obj:
                prev_obj = test_obj
                best_step = step
            else:
                step *= 0.5
                if step < 0.1:
                    break
        
        return best_step, prev_obj
    
    def run_iteration(self, shots: List[Shot], receivers: List[Receiver],
                      observed_data: dict) -> dict:
        obj, direction = self.compute_steepest_descent_direction(
            shots, receivers, observed_data
        )
        
        step, new_obj = self.line_search(
            shots, receivers, observed_data, direction
        )
        
        velocity_update = step * direction
        self.model.velocity += velocity_update
        self.model.slowness = 1.0 / self.model.velocity
        
        self.objective_history.append(obj)
        
        return {
            'objective': obj,
            'objective_new': new_obj,
            'step_length': step,
            'gradient_norm': np.linalg.norm(self.gradient),
            'update_norm': np.linalg.norm(velocity_update)
        }
    
    def generate_synthetic_seismograms(self, shots: List[Shot],
                                        receivers: List[Receiver]) -> dict:
        seismograms = {}
        for shot in shots:
            synth, _ = self.solver.forward_propagate(
                shot, receivers, self.wavelet
            )
            seismograms[shot.id] = synth
        return seismograms
    
    def compute_first_arrival_times(self, seismograms: np.ndarray,
                                     threshold: float = 0.01) -> np.ndarray:
        n_rec = seismograms.shape[1]
        arrival_times = np.zeros(n_rec)
        
        for i in range(n_rec):
            trace = np.abs(seismograms[:, i])
            max_amp = trace.max()
            if max_amp > 0:
                idx = np.where(trace > threshold * max_amp)[0]
                if len(idx) > 0:
                    arrival_times[i] = idx[0] * self.dt
                else:
                    arrival_times[i] = np.nan
            else:
                arrival_times[i] = np.nan
        
        return arrival_times
