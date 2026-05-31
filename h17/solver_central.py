import numpy as np
import time
from numba import njit, prange
from typing import Callable, Optional, List, Tuple, Dict

from config import SimulationConfig
from fd_coefficients import get_fd_coefficients
from cpml import CPML
from medium import Medium
from source import Source
from receiver import ReceiverArray, ParticleMotionRecorder


@njit(parallel=True, fastmath=True)
def _compute_derivatives_central(field: np.ndarray, dx: float, dz: float,
                                ddx: np.ndarray, ddz: np.ndarray,
                                coeffs: np.ndarray, half_order: int):
    nz, nx = field.shape
    
    for z in prange(half_order, nz - half_order):
        for x in range(half_order, nx - half_order):
            d = 0.0
            for m in range(1, half_order + 1):
                d += coeffs[m-1] * (field[z, x + m] - field[z, x - m])
            ddx[z, x] = d / (2 * dx)
            
            d2 = 0.0
            for m in range(1, half_order + 1):
                d2 += coeffs[m-1] * (field[z + m, x] - field[z - m, x])
            ddz[z, x] = d2 / (2 * dz)


class CentralElasticSolver:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.dtype = config.dtype
        
        self.fd_coeffs = get_fd_coefficients(config.space_order)
        self.half_order = config.space_order // 2
        
        self.medium = Medium(
            nx=config.nx, nz=config.nz,
            dx=config.dx, dz=config.dz,
            vp=config.vp, vs=config.vs, rho=config.rho,
            anisotropy_type=config.anisotropy_type,
            epsilon=config.epsilon, delta=config.delta, gamma=config.gamma,
            theta=config.theta, phi=config.phi,
            dtype=self.dtype
        )
        
        self.cpml = CPML(
            nx=config.nx, nz=config.nz,
            dx=config.dx, dz=config.dz, dt=config.dt,
            width=config.cpml_width,
            max_power=config.cpml_max_power,
            reflection_coef=config.cpml_reflection_coef,
            dtype=self.dtype
        )
        
        self.source = Source(
            nx=config.nx, nz=config.nz,
            dx=config.dx, dz=config.dz, dt=config.dt, nt=config.nt,
            source_type=config.source_type,
            sx=config.source_x, sz=config.source_z,
            f0=config.source_f0,
            amplitude=config.source_amplitude,
            t0=config.source_time_delay,
            dtype=self.dtype
        )
        
        self.receivers = ReceiverArray(
            nx=config.nx, nz=config.nz,
            dx=config.dx, dz=config.dz, dt=config.dt, nt=config.nt,
            array_type=config.receiver_array_type,
            rx_start=config.receiver_x_start,
            rx_end=config.receiver_x_end,
            rz=config.receiver_z,
            spacing=config.receiver_spacing,
            dtype=self.dtype
        )
        
        self.particle_motion: Optional[ParticleMotionRecorder] = None
        self._init_wavefields()
        self._init_derivatives()
    
    def _init_wavefields(self):
        config = self.config
        nz, nx = config.nz, config.nx
        
        self.vx = np.zeros((nz, nx), dtype=self.dtype)
        self.vz = np.zeros((nz, nx), dtype=self.dtype)
        self.tau_xx = np.zeros((nz, nx), dtype=self.dtype)
        self.tau_zz = np.zeros((nz, nx), dtype=self.dtype)
        self.tau_xz = np.zeros((nz, nx), dtype=self.dtype)
        
        self.snapshots: List[dict] = []
    
    def _init_derivatives(self):
        config = self.config
        nz, nx = config.nz, config.nx
        
        self.dvx_dx = np.zeros((nz, nx), dtype=self.dtype)
        self.dvx_dz = np.zeros((nz, nx), dtype=self.dtype)
        self.dvz_dx = np.zeros((nz, nx), dtype=self.dtype)
        self.dvz_dz = np.zeros((nz, nx), dtype=self.dtype)
        
        self.dtau_xx_dx = np.zeros((nz, nx), dtype=self.dtype)
        self.dtau_xx_dz = np.zeros((nz, nx), dtype=self.dtype)
        self.dtau_zz_dx = np.zeros((nz, nx), dtype=self.dtype)
        self.dtau_zz_dz = np.zeros((nz, nx), dtype=self.dtype)
        self.dtau_xz_dx = np.zeros((nz, nx), dtype=self.dtype)
        self.dtau_xz_dz = np.zeros((nz, nx), dtype=self.dtype)
    
    def set_particle_motion_points(self, points: List[Tuple[int, int]]):
        config = self.config
        self.particle_motion = ParticleMotionRecorder(
            nx=config.nx, nz=config.nz,
            dx=config.dx, dz=config.dz, dt=config.dt, nt=config.nt,
            points=points,
            dtype=self.dtype
        )
    
    def solve(self, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> dict:
        config = self.config
        nx, nz, nt = config.nx, config.nz, config.nt
        dt = config.dt
        dx, dz = config.dx, config.dz
        half_order = self.half_order
        coeffs = self.fd_coeffs
        
        c11 = self.medium.c11
        c13 = self.medium.c13
        c33 = self.medium.c33
        c55 = self.medium.c55
        rho_inv = self.medium.rho_inv
        
        start_time = time.time()
        
        for it in range(nt):
            self.dvx_dx.fill(0)
            self.dvx_dz.fill(0)
            self.dvz_dx.fill(0)
            self.dvz_dz.fill(0)
            
            _compute_derivatives_central(self.vx, dx, dz, self.dvx_dx, self.dvx_dz, coeffs, half_order)
            _compute_derivatives_central(self.vz, dx, dz, self.dvz_dx, self.dvz_dz, coeffs, half_order)
            
            self.cpml.apply_velocity_correction(
                self.dvx_dx, self.dvx_dz, self.dvz_dx, self.dvz_dz
            )
            
            for z in range(half_order, nz - half_order):
                for x in range(half_order, nx - half_order):
                    sxx = c11[z, x] * self.dvx_dx[z, x] + c13[z, x] * self.dvz_dz[z, x]
                    self.tau_xx[z, x] += dt * sxx
                    szz = c13[z, x] * self.dvx_dx[z, x] + c33[z, x] * self.dvz_dz[z, x]
                    self.tau_zz[z, x] += dt * szz
                    sxz = c55[z, x] * (self.dvx_dz[z, x] + self.dvz_dx[z, x])
                    self.tau_xz[z, x] += dt * sxz
            
            self.source.add_source(
                self.tau_xx, self.tau_zz, self.tau_xz,
                self.vx, self.vz, it
            )
            
            self.dtau_xx_dx.fill(0)
            self.dtau_xx_dz.fill(0)
            self.dtau_zz_dx.fill(0)
            self.dtau_zz_dz.fill(0)
            self.dtau_xz_dx.fill(0)
            self.dtau_xz_dz.fill(0)
            
            _compute_derivatives_central(self.tau_xx, dx, dz, self.dtau_xx_dx, self.dtau_xx_dz, coeffs, half_order)
            _compute_derivatives_central(self.tau_zz, dx, dz, self.dtau_zz_dx, self.dtau_zz_dz, coeffs, half_order)
            _compute_derivatives_central(self.tau_xz, dx, dz, self.dtau_xz_dx, self.dtau_xz_dz, coeffs, half_order)
            
            self.cpml.apply_stress_correction(
                self.dtau_xx_dx, self.dtau_xx_dz,
                self.dtau_zz_dx, self.dtau_zz_dz,
                self.dtau_xz_dx, self.dtau_xz_dz
            )
            
            for z in range(half_order, nz - half_order):
                for x in range(half_order, nx - half_order):
                    dvx = (self.dtau_xx_dx[z, x] + self.dtau_xz_dz[z, x]) * rho_inv[z, x]
                    self.vx[z, x] += dt * dvx
                    dvz = (self.dtau_zz_dz[z, x] + self.dtau_xz_dx[z, x]) * rho_inv[z, x]
                    self.vz[z, x] += dt * dvz
            
            self.receivers.record(
                self.vx, self.vz,
                self.tau_xx, self.tau_zz, self.tau_xz,
                it
            )
            
            if self.particle_motion is not None:
                self.particle_motion.record(self.vx, self.vz, it)
            
            if it % config.snapshot_interval == 0:
                self._save_snapshot(it)
            
            if progress_callback is not None and (it % max(1, nt // 100) == 0 or it == nt - 1):
                elapsed = time.time() - start_time
                progress_callback(it + 1, nt, elapsed)
        
        if progress_callback is not None:
            elapsed = time.time() - start_time
            progress_callback(nt, nt, elapsed)
        
        return self._collect_results()
    
    def _save_snapshot(self, it: int):
        config = self.config
        snapshot = {
            'time': it * config.dt,
            'vx': self.vx.copy(),
            'vz': self.vz.copy(),
            'tau_xx': self.tau_xx.copy(),
            'tau_zz': self.tau_zz.copy(),
            'tau_xz': self.tau_xz.copy()
        }
        self.snapshots.append(snapshot)
    
    def _collect_results(self) -> dict:
        results = {
            'receivers': self.receivers,
            'snapshots': self.snapshots,
            'config': self.config,
            'medium': self.medium,
            'source': self.source
        }
        if self.particle_motion is not None:
            results['particle_motion'] = self.particle_motion
        return results
