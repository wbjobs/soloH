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
def _compute_vx_dx(vx: np.ndarray, dvx_dx: np.ndarray, coeffs: np.ndarray, dx: float, half_order: int):
    nz, nx = vx.shape
    for z in prange(nz):
        for x in range(half_order, nx - half_order):
            deriv = 0.0
            for m in range(half_order):
                deriv += coeffs[m] * (vx[z, x + m] - vx[z, x - m - 1])
            dvx_dx[z, x] = deriv / dx


@njit(parallel=True, fastmath=True)
def _compute_vz_dz(vz: np.ndarray, dvz_dz: np.ndarray, coeffs: np.ndarray, dz: float, half_order: int):
    nz, nx = vz.shape
    for z in prange(half_order, nz - half_order):
        for x in prange(nx):
            deriv = 0.0
            for m in range(half_order):
                deriv += coeffs[m] * (vz[z + m, x] - vz[z - m - 1, x])
            dvz_dz[z, x] = deriv / dz


@njit(parallel=True, fastmath=True)
def _compute_vx_dz(vx: np.ndarray, dvx_dz: np.ndarray, coeffs: np.ndarray, dz: float, half_order: int):
    nz, nx = vx.shape
    for z in prange(half_order, nz - half_order):
        for x in prange(nx):
            deriv = 0.0
            for m in range(half_order):
                deriv += coeffs[m] * (vx[z + m, x] - vx[z - m - 1, x])
            dvx_dz[z, x] = deriv / dz


@njit(parallel=True, fastmath=True)
def _compute_vz_dx(vz: np.ndarray, dvz_dx: np.ndarray, coeffs: np.ndarray, dx: float, half_order: int):
    nz, nx = vz.shape
    for z in prange(nz):
        for x in range(half_order, nx - half_order):
            deriv = 0.0
            for m in range(half_order):
                deriv += coeffs[m] * (vz[z, x + m] - vz[z, x - m - 1])
            dvz_dx[z, x] = deriv / dx


@njit(parallel=True, fastmath=True)
def _update_normal_stress(tau_xx: np.ndarray, tau_zz: np.ndarray,
                          dvx_dx: np.ndarray, dvz_dz: np.ndarray,
                          c11: np.ndarray, c13: np.ndarray, c33: np.ndarray,
                          dt: float, half_order: int):
    nz, nx = tau_xx.shape
    for z in prange(half_order, nz - half_order):
        for x in range(half_order, nx - half_order):
            sxx = c11[z, x] * dvx_dx[z, x] + c13[z, x] * dvz_dz[z, x]
            tau_xx[z, x] += dt * sxx
            szz = c13[z, x] * dvx_dx[z, x] + c33[z, x] * dvz_dz[z, x]
            tau_zz[z, x] += dt * szz


@njit(parallel=True, fastmath=True)
def _update_shear_stress(tau_xz: np.ndarray, dvx_dz: np.ndarray, dvz_dx: np.ndarray,
                         c55: np.ndarray, dt: float, half_order: int):
    nz, nx = tau_xz.shape
    for z in prange(half_order, nz - half_order):
        for x in range(half_order, nx - half_order):
            sxz = c55[z, x] * (dvx_dz[z, x] + dvz_dx[z, x])
            tau_xz[z, x] += dt * sxz


@njit(parallel=True, fastmath=True)
def _compute_tau_derivatives(tau_xx: np.ndarray, tau_zz: np.ndarray, tau_xz: np.ndarray,
                             dtau_xx_dx: np.ndarray, dtau_zz_dz: np.ndarray,
                             dtau_xz_dx: np.ndarray, dtau_xz_dz: np.ndarray,
                             coeffs: np.ndarray, dx: float, dz: float, half_order: int):
    nz, nx = tau_xx.shape
    
    for z in prange(nz):
        for x in range(half_order, nx - half_order):
            deriv = 0.0
            for m in range(half_order):
                deriv += coeffs[m] * (tau_xx[z, x + m] - tau_xx[z, x - m - 1])
            dtau_xx_dx[z, x] = deriv / dx
            
            deriv2 = 0.0
            for m in range(half_order):
                deriv2 += coeffs[m] * (tau_xz[z, x + m] - tau_xz[z, x - m - 1])
            dtau_xz_dx[z, x] = deriv2 / dx
    
    for z in prange(half_order, nz - half_order):
        for x in prange(nx):
            deriv = 0.0
            for m in range(half_order):
                deriv += coeffs[m] * (tau_zz[z + m, x] - tau_zz[z - m - 1, x])
            dtau_zz_dz[z, x] = deriv / dz
            
            deriv2 = 0.0
            for m in range(half_order):
                deriv2 += coeffs[m] * (tau_xz[z + m, x] - tau_xz[z - m - 1, x])
            dtau_xz_dz[z, x] = deriv2 / dz


@njit(parallel=True, fastmath=True)
def _update_v(vx: np.ndarray, vz: np.ndarray,
              dtau_xx_dx: np.ndarray, dtau_zz_dz: np.ndarray,
              dtau_xz_dx: np.ndarray, dtau_xz_dz: np.ndarray,
              rho_inv: np.ndarray, dt: float, half_order: int):
    nz, nx = vx.shape
    for z in prange(half_order, nz - half_order):
        for x in range(half_order, nx - half_order):
            dvx = (dtau_xx_dx[z, x] + dtau_xz_dz[z, x]) * rho_inv[z, x]
            vx[z, x] += dt * dvx
            dvz = (dtau_zz_dz[z, x] + dtau_xz_dx[z, x]) * rho_inv[z, x]
            vz[z, x] += dt * dvz


class SimpleElasticSolver:
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
            
            _compute_vx_dx(self.vx, self.dvx_dx, coeffs, dx, half_order)
            _compute_vz_dz(self.vz, self.dvz_dz, coeffs, dz, half_order)
            _compute_vx_dz(self.vx, self.dvx_dz, coeffs, dz, half_order)
            _compute_vz_dx(self.vz, self.dvz_dx, coeffs, dx, half_order)
            
            self.cpml.apply_velocity_correction(
                self.dvx_dx, self.dvx_dz, self.dvz_dx, self.dvz_dz
            )
            
            _update_normal_stress(
                self.tau_xx, self.tau_zz,
                self.dvx_dx, self.dvz_dz,
                c11, c13, c33, dt, half_order
            )
            
            _update_shear_stress(
                self.tau_xz, self.dvx_dz, self.dvz_dx,
                c55, dt, half_order
            )
            
            self.source.add_source(
                self.tau_xx, self.tau_zz, self.tau_xz,
                self.vx, self.vz, it
            )
            
            self.dtau_xx_dx.fill(0)
            self.dtau_zz_dz.fill(0)
            self.dtau_xz_dx.fill(0)
            self.dtau_xz_dz.fill(0)
            
            _compute_tau_derivatives(
                self.tau_xx, self.tau_zz, self.tau_xz,
                self.dtau_xx_dx, self.dtau_zz_dz,
                self.dtau_xz_dx, self.dtau_xz_dz,
                coeffs, dx, dz, half_order
            )
            
            self.cpml.apply_stress_correction(
                self.dtau_xx_dx, self.dtau_zz_dz,
                self.dtau_xz_dx, self.dtau_xz_dz,
                self.dtau_xz_dx, self.dtau_xz_dz
            )
            
            _update_v(
                self.vx, self.vz,
                self.dtau_xx_dx, self.dtau_zz_dz,
                self.dtau_xz_dx, self.dtau_xz_dz,
                rho_inv, dt, half_order
            )
            
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
