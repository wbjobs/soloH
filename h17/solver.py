import numpy as np
from numba import njit, prange
from typing import Optional, Tuple, Callable, List
import time

from config import SimulationConfig
from fd_coefficients import get_central_fd_coefficients, compute_derivatives_central
from cpml import CPML
from medium import Medium
from source import Source, MultipleSources
from receiver import ReceiverArray, ParticleMotionRecorder


class ElasticSolver:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.dtype = config.dtype
        
        self._init_components()
        self._init_wavefields()
        self._init_derivatives()
        
        if config.use_gpu:
            self._init_gpu()
        
        if config.use_mpi:
            self._init_mpi()
    
    def _init_components(self):
        config = self.config
        
        self.fd_coeffs = get_central_fd_coefficients(config.space_order)
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
    
    def _init_gpu(self):
        try:
            import cupy as cp
            self.xp = cp
            
            self.vx = cp.asarray(self.vx)
            self.vz = cp.asarray(self.vz)
            self.tau_xx = cp.asarray(self.tau_xx)
            self.tau_zz = cp.asarray(self.tau_zz)
            self.tau_xz = cp.asarray(self.tau_xz)
            
            self.dvx_dx = cp.asarray(self.dvx_dx)
            self.dvx_dz = cp.asarray(self.dvx_dz)
            self.dvz_dx = cp.asarray(self.dvz_dx)
            self.dvz_dz = cp.asarray(self.dvz_dz)
            
            self.dtau_xx_dx = cp.asarray(self.dtau_xx_dx)
            self.dtau_xx_dz = cp.asarray(self.dtau_xx_dz)
            self.dtau_zz_dx = cp.asarray(self.dtau_zz_dx)
            self.dtau_zz_dz = cp.asarray(self.dtau_zz_dz)
            self.dtau_xz_dx = cp.asarray(self.dtau_xz_dx)
            self.dtau_xz_dz = cp.asarray(self.dtau_xz_dz)
            
            print("GPU mode enabled with CuPy")
        except ImportError:
            print("CuPy not available, falling back to CPU")
            self.config.use_gpu = False
            self.xp = np
    
    def _init_mpi(self):
        try:
            from mpi4py import MPI
            self.comm = MPI.COMM_WORLD
            self.rank = self.comm.Get_rank()
            self.size = self.comm.Get_size()
            
            print(f"MPI mode enabled, rank {self.rank}/{self.size}")
        except ImportError:
            print("mpi4py not available, falling back to serial")
            self.config.use_mpi = False
            self.rank = 0
            self.size = 1
    
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
        c12 = self.medium.c12
        c13 = self.medium.c13
        c33 = self.medium.c33
        c44 = self.medium.c44
        c55 = self.medium.c55
        c66 = self.medium.c66
        rho_inv = self.medium.rho_inv
        
        start_time = time.time()
        
        for it in range(nt):
            self.dvx_dx.fill(0)
            self.dvx_dz.fill(0)
            self.dvz_dx.fill(0)
            self.dvz_dz.fill(0)
            
            compute_derivatives_central(
                self.vx, dx, dz,
                self.dvx_dx, self.dvx_dz,
                coeffs, half_order
            )
            compute_derivatives_central(
                self.vz, dx, dz,
                self.dvz_dx, self.dvz_dz,
                coeffs, half_order
            )
            
            self.cpml.apply_velocity_correction(
                self.dvx_dx, self.dvx_dz, self.dvz_dx, self.dvz_dz
            )
            
            _update_stress_central(
                self.tau_xx, self.tau_zz, self.tau_xz,
                self.dvx_dx, self.dvx_dz, self.dvz_dx, self.dvz_dz,
                c11, c13, c33, c55, rho_inv,
                dt, half_order
            )
            
            if isinstance(self.source, MultipleSources):
                self.source.add_sources(
                    self.tau_xx, self.tau_zz, self.tau_xz,
                    self.vx, self.vz, it
                )
            else:
                self.source.add_source(
                    self.tau_xx, self.tau_zz, self.tau_xz,
                    self.vx, self.vz, it
                )
            
            self._apply_boundary_conditions()
            
            self.dtau_xx_dx.fill(0)
            self.dtau_xx_dz.fill(0)
            self.dtau_zz_dx.fill(0)
            self.dtau_zz_dz.fill(0)
            self.dtau_xz_dx.fill(0)
            self.dtau_xz_dz.fill(0)
            
            compute_derivatives_central(
                self.tau_xx, dx, dz,
                self.dtau_xx_dx, self.dtau_xx_dz,
                coeffs, half_order
            )
            compute_derivatives_central(
                self.tau_zz, dx, dz,
                self.dtau_zz_dx, self.dtau_zz_dz,
                coeffs, half_order
            )
            compute_derivatives_central(
                self.tau_xz, dx, dz,
                self.dtau_xz_dx, self.dtau_xz_dz,
                coeffs, half_order
            )
            
            self.cpml.apply_stress_correction(
                self.dtau_xx_dx, self.dtau_xx_dz,
                self.dtau_zz_dx, self.dtau_zz_dz,
                self.dtau_xz_dx, self.dtau_xz_dz
            )
            
            _update_velocity_central(
                self.vx, self.vz,
                self.dtau_xx_dx, self.dtau_zz_dz,
                self.dtau_xz_dx, self.dtau_xz_dz,
                rho_inv,
                dt, half_order
            )
            
            self._apply_boundary_conditions()
            
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
        import copy
        if self.config.use_gpu:
            import cupy as cp
            snapshot = {
                'it': it,
                'time': it * self.config.dt,
                'vx': cp.asnumpy(self.vx).copy(),
                'vz': cp.asnumpy(self.vz).copy(),
                'tau_xx': cp.asnumpy(self.tau_xx).copy(),
                'tau_zz': cp.asnumpy(self.tau_zz).copy(),
                'tau_xz': cp.asnumpy(self.tau_xz).copy(),
            }
        else:
            snapshot = {
                'it': it,
                'time': it * self.config.dt,
                'vx': self.vx.copy(),
                'vz': self.vz.copy(),
                'tau_xx': self.tau_xx.copy(),
                'tau_zz': self.tau_zz.copy(),
                'tau_xz': self.tau_xz.copy(),
            }
        self.snapshots.append(snapshot)
    
    def _apply_boundary_conditions(self):
        config = self.config
        nx, nz = config.nx, config.nz
        half_order = self.half_order
        
        if config.top_boundary == 'free_surface':
            self._apply_free_surface_top(half_order, nx, nz)
        if config.bottom_boundary == 'free_surface':
            self._apply_free_surface_bottom(half_order, nx, nz)
        if config.left_boundary == 'free_surface':
            self._apply_free_surface_left(half_order, nx, nz)
        if config.right_boundary == 'free_surface':
            self._apply_free_surface_right(half_order, nx, nz)
        
        if config.top_boundary == 'reflecting':
            self._apply_reflecting_top(half_order, nx, nz)
        if config.bottom_boundary == 'reflecting':
            self._apply_reflecting_bottom(half_order, nx, nz)
        if config.left_boundary == 'reflecting':
            self._apply_reflecting_left(half_order, nx, nz)
        if config.right_boundary == 'reflecting':
            self._apply_reflecting_right(half_order, nx, nz)
    
    def _apply_free_surface_top(self, half_order: int, nx: int, nz: int):
        _apply_free_surface_top_numba(
            self.vx, self.vz,
            self.tau_xx, self.tau_zz, self.tau_xz,
            half_order, nx, nz
        )
    
    def _apply_free_surface_bottom(self, half_order: int, nx: int, nz: int):
        _apply_free_surface_bottom_numba(
            self.vx, self.vz,
            self.tau_xx, self.tau_zz, self.tau_xz,
            half_order, nx, nz
        )
    
    def _apply_free_surface_left(self, half_order: int, nx: int, nz: int):
        _apply_free_surface_left_numba(
            self.vx, self.vz,
            self.tau_xx, self.tau_zz, self.tau_xz,
            half_order, nx, nz
        )
    
    def _apply_free_surface_right(self, half_order: int, nx: int, nz: int):
        _apply_free_surface_right_numba(
            self.vx, self.vz,
            self.tau_xx, self.tau_zz, self.tau_xz,
            half_order, nx, nz
        )
    
    def _apply_reflecting_top(self, half_order: int, nx: int, nz: int):
        _apply_reflecting_top_numba(
            self.vx, self.vz,
            self.tau_xx, self.tau_zz, self.tau_xz,
            half_order, nx, nz
        )
    
    def _apply_reflecting_bottom(self, half_order: int, nx: int, nz: int):
        _apply_reflecting_bottom_numba(
            self.vx, self.vz,
            self.tau_xx, self.tau_zz, self.tau_xz,
            half_order, nx, nz
        )
    
    def _apply_reflecting_left(self, half_order: int, nx: int, nz: int):
        _apply_reflecting_left_numba(
            self.vx, self.vz,
            self.tau_xx, self.tau_zz, self.tau_xz,
            half_order, nx, nz
        )
    
    def _apply_reflecting_right(self, half_order: int, nx: int, nz: int):
        _apply_reflecting_right_numba(
            self.vx, self.vz,
            self.tau_xx, self.tau_zz, self.tau_xz,
            half_order, nx, nz
        )
    
    def _collect_results(self) -> dict:
        results = {
            'receivers': self.receivers,
            'snapshots': self.snapshots,
            'source': self.source,
            'medium': self.medium,
            'config': self.config,
        }
        
        if self.particle_motion is not None:
            results['particle_motion'] = self.particle_motion
        
        return results
    
    def reset(self):
        self.vx.fill(0)
        self.vz.fill(0)
        self.tau_xx.fill(0)
        self.tau_zz.fill(0)
        self.tau_xz.fill(0)
        
        self.cpml.reset_memory()
        self.snapshots = []
        
        if hasattr(self, 'receivers'):
            self.receivers._init_seismograms()
        
        if self.particle_motion is not None:
            config = self.config
            self.particle_motion = ParticleMotionRecorder(
                nx=config.nx, nz=config.nz,
                dx=config.dx, dz=config.dz, dt=config.dt, nt=config.nt,
                points=self.particle_motion.points,
                dtype=self.dtype
            )


@njit(parallel=True, fastmath=True)
def _update_stress_central(tau_xx: np.ndarray, tau_zz: np.ndarray, tau_xz: np.ndarray,
                           dvx_dx: np.ndarray, dvx_dz: np.ndarray,
                           dvz_dx: np.ndarray, dvz_dz: np.ndarray,
                           c11: np.ndarray, c13: np.ndarray, c33: np.ndarray, c55: np.ndarray,
                           rho_inv: np.ndarray,
                           dt: float, half_order: int):
    nz, nx = tau_xx.shape
    
    for z in prange(half_order, nz - half_order):
        for x in range(half_order, nx - half_order):
            sxx = c11[z, x] * dvx_dx[z, x] + c13[z, x] * dvz_dz[z, x]
            tau_xx[z, x] += dt * sxx
            
            szz = c13[z, x] * dvx_dx[z, x] + c33[z, x] * dvz_dz[z, x]
            tau_zz[z, x] += dt * szz
            
            sxz = c55[z, x] * (dvx_dz[z, x] + dvz_dx[z, x])
            tau_xz[z, x] += dt * sxz


@njit(parallel=True, fastmath=True)
def _update_velocity_central(vx: np.ndarray, vz: np.ndarray,
                             dtau_xx_dx: np.ndarray, dtau_zz_dz: np.ndarray,
                             dtau_xz_dx: np.ndarray, dtau_xz_dz: np.ndarray,
                             rho_inv: np.ndarray,
                             dt: float, half_order: int):
    nz, nx = vx.shape
    
    for z in prange(half_order, nz - half_order):
        for x in range(half_order, nx - half_order):
            dvx = (dtau_xx_dx[z, x] + dtau_xz_dz[z, x]) * rho_inv[z, x]
            vx[z, x] += dt * dvx
            
            dvz = (dtau_zz_dz[z, x] + dtau_xz_dx[z, x]) * rho_inv[z, x]
            vz[z, x] += dt * dvz


@njit(parallel=True)
def _apply_free_surface_top_numba(vx, vz, tau_xx, tau_zz, tau_xz, half_order, nx, nz):
    n_ghost = half_order + 2
    for z in prange(n_ghost):
        mirror_z = 2 * n_ghost - 1 - z
        if mirror_z >= nz:
            mirror_z = nz - 1
        for x in prange(half_order, nx - half_order):
            tau_zz[z, x] = -tau_zz[mirror_z, x]
            tau_xz[z, x] = -tau_xz[mirror_z, x]
            tau_xx[z, x] = tau_xx[mirror_z, x]
            vx[z, x] = vx[mirror_z, x]
            vz[z, x] = -vz[mirror_z, x]
    
    for x in prange(half_order, nx - half_order):
        tau_zz[0, x] = 0.0
        tau_xz[0, x] = 0.0


@njit(parallel=True)
def _apply_free_surface_bottom_numba(vx, vz, tau_xx, tau_zz, tau_xz, half_order, nx, nz):
    n_ghost = half_order + 2
    for z in prange(nz - n_ghost, nz):
        mirror_z = 2 * (nz - n_ghost) - z
        if mirror_z < 0:
            mirror_z = 0
        for x in prange(half_order, nx - half_order):
            tau_zz[z, x] = -tau_zz[mirror_z, x]
            tau_xz[z, x] = -tau_xz[mirror_z, x]
            tau_xx[z, x] = tau_xx[mirror_z, x]
            vx[z, x] = vx[mirror_z, x]
            vz[z, x] = -vz[mirror_z, x]
    
    for x in prange(half_order, nx - half_order):
        tau_zz[nz-1, x] = 0.0
        tau_xz[nz-1, x] = 0.0


@njit(parallel=True)
def _apply_free_surface_left_numba(vx, vz, tau_xx, tau_zz, tau_xz, half_order, nx, nz):
    n_ghost = half_order + 2
    for z in prange(half_order, nz - half_order):
        for x in prange(n_ghost):
            mirror_x = 2 * n_ghost - 1 - x
            if mirror_x >= nx:
                mirror_x = nx - 1
            tau_xx[z, x] = -tau_xx[z, mirror_x]
            tau_xz[z, x] = -tau_xz[z, mirror_x]
            tau_zz[z, x] = tau_zz[z, mirror_x]
            vz[z, x] = vz[z, mirror_x]
            vx[z, x] = -vx[z, mirror_x]
    
    for z in prange(half_order, nz - half_order):
        tau_xx[z, 0] = 0.0
        tau_xz[z, 0] = 0.0


@njit(parallel=True)
def _apply_free_surface_right_numba(vx, vz, tau_xx, tau_zz, tau_xz, half_order, nx, nz):
    n_ghost = half_order + 2
    for z in prange(half_order, nz - half_order):
        for x in prange(nx - n_ghost, nx):
            mirror_x = 2 * (nx - n_ghost) - x
            if mirror_x < 0:
                mirror_x = 0
            tau_xx[z, x] = -tau_xx[z, mirror_x]
            tau_xz[z, x] = -tau_xz[z, mirror_x]
            tau_zz[z, x] = tau_zz[z, mirror_x]
            vz[z, x] = vz[z, mirror_x]
            vx[z, x] = -vx[z, mirror_x]
    
    for z in prange(half_order, nz - half_order):
        tau_xx[z, nx-1] = 0.0
        tau_xz[z, nx-1] = 0.0


@njit(parallel=True)
def _apply_reflecting_top_numba(vx, vz, tau_xx, tau_zz, tau_xz, half_order, nx, nz):
    for z in prange(half_order):
        mirror_z = 2 * half_order - z
        for x in prange(half_order, nx - half_order):
            tau_zz[z, x] = tau_zz[mirror_z, x]
            tau_xz[z, x] = -tau_xz[mirror_z, x]
            tau_xx[z, x] = tau_xx[mirror_z, x]
            vx[z, x] = vx[mirror_z, x]
            vz[z, x] = -vz[mirror_z, x]


@njit(parallel=True)
def _apply_reflecting_bottom_numba(vx, vz, tau_xx, tau_zz, tau_xz, half_order, nx, nz):
    for z in prange(nz - half_order, nz):
        mirror_z = 2 * (nz - half_order - 1) - z
        for x in prange(half_order, nx - half_order):
            tau_zz[z, x] = tau_zz[mirror_z, x]
            tau_xz[z, x] = -tau_xz[mirror_z, x]
            tau_xx[z, x] = tau_xx[mirror_z, x]
            vx[z, x] = vx[mirror_z, x]
            vz[z, x] = -vz[mirror_z, x]


@njit(parallel=True)
def _apply_reflecting_left_numba(vx, vz, tau_xx, tau_zz, tau_xz, half_order, nx, nz):
    for z in prange(half_order, nz - half_order):
        for x in prange(half_order):
            mirror_x = 2 * half_order - x
            tau_xx[z, x] = tau_xx[z, mirror_x]
            tau_xz[z, x] = -tau_xz[z, mirror_x]
            tau_zz[z, x] = tau_zz[z, mirror_x]
            vz[z, x] = vz[z, mirror_x]
            vx[z, x] = -vx[z, mirror_x]


@njit(parallel=True)
def _apply_reflecting_right_numba(vx, vz, tau_xx, tau_zz, tau_xz, half_order, nx, nz):
    for z in prange(half_order, nz - half_order):
        for x in prange(nx - half_order, nx):
            mirror_x = 2 * (nx - half_order - 1) - x
            tau_xx[z, x] = tau_xx[z, mirror_x]
            tau_xz[z, x] = -tau_xz[z, mirror_x]
            tau_zz[z, x] = tau_zz[z, mirror_x]
            vz[z, x] = vz[z, mirror_x]
            vx[z, x] = -vx[z, mirror_x]


class CheckpointManager:
    def __init__(self, nx: int, nz: int, nt: int,
                 checkpoint_interval: int = 10,
                 max_checkpoints: int = 100,
                 storage_dir: Optional[str] = None,
                 dtype=np.float64):
        self.nx = nx
        self.nz = nz
        self.nt = nt
        self.checkpoint_interval = checkpoint_interval
        self.max_checkpoints = max_checkpoints
        self.storage_dir = storage_dir
        self.dtype = dtype
        
        self.checkpoints: dict = {}
        self.disk_checkpoints: List[str] = []
        
        if storage_dir is not None:
            import os
            os.makedirs(storage_dir, exist_ok=True)
    
    def should_checkpoint(self, it: int) -> bool:
        if it % self.checkpoint_interval != 0:
            return False
        if it == 0 or it >= self.nt:
            return False
        if len(self.checkpoints) >= self.max_checkpoints and self.storage_dir is None:
            return False
        return True
    
    def save_checkpoint(self, it: int, vx: np.ndarray, vz: np.ndarray,
                        tau_xx: np.ndarray, tau_zz: np.ndarray, tau_xz: np.ndarray) -> None:
        checkpoint_data = {
            'it': it,
            'vx': vx.copy(),
            'vz': vz.copy(),
            'tau_xx': tau_xx.copy(),
            'tau_zz': tau_zz.copy(),
            'tau_xz': tau_xz.copy(),
        }
        
        if self.storage_dir is not None:
            import os
            filename = os.path.join(self.storage_dir, f'checkpoint_{it:08d}.npz')
            np.savez(filename, **checkpoint_data)
            self.disk_checkpoints.append(filename)
            if it in self.checkpoints:
                del self.checkpoints[it]
        else:
            self.checkpoints[it] = checkpoint_data
    
    def load_checkpoint(self, it: int) -> dict:
        if it in self.checkpoints:
            return self.checkpoints[it]
        
        if self.storage_dir is not None:
            import os
            filename = os.path.join(self.storage_dir, f'checkpoint_{it:08d}.npz')
            if os.path.exists(filename):
                data = np.load(filename)
                return {
                    'it': it,
                    'vx': data['vx'],
                    'vz': data['vz'],
                    'tau_xx': data['tau_xx'],
                    'tau_zz': data['tau_zz'],
                    'tau_xz': data['tau_xz'],
                }
        
        raise ValueError(f"Checkpoint for iteration {it} not found")
    
    def get_nearest_checkpoint(self, it: int) -> int:
        if it in self.checkpoints:
            return it
        
        all_times = list(self.checkpoints.keys())
        if self.storage_dir is not None:
            import re
            for f in self.disk_checkpoints:
                m = re.search(r'checkpoint_(\d+)\.npz', f)
                if m:
                    all_times.append(int(m.group(1)))
        
        all_times = sorted(set(all_times))
        if not all_times:
            return 0
        
        for t in reversed(all_times):
            if t <= it:
                return t
        
        return all_times[0]
    
    def restore_from_checkpoint(self, it: int, solver: 'ElasticSolver') -> int:
        ckpt_it = self.get_nearest_checkpoint(it)
        ckpt = self.load_checkpoint(ckpt_it)
        
        solver.vx[:] = ckpt['vx']
        solver.vz[:] = ckpt['vz']
        solver.tau_xx[:] = ckpt['tau_xx']
        solver.tau_zz[:] = ckpt['tau_zz']
        solver.tau_xz[:] = ckpt['tau_xz']
        
        solver.cpml.reset_memory()
        return ckpt_it
    
    def clear_memory(self) -> None:
        self.checkpoints.clear()
    
    def clear_all(self) -> None:
        self.clear_memory()
        if self.storage_dir is not None:
            import os, glob
            for f in glob.glob(os.path.join(self.storage_dir, 'checkpoint_*.npz')):
                os.remove(f)
            self.disk_checkpoints.clear()
    
    def get_checkpoint_times(self) -> List[int]:
        times = list(self.checkpoints.keys())
        if self.storage_dir is not None:
            import re
            for f in self.disk_checkpoints:
                m = re.search(r'checkpoint_(\d+)\.npz', f)
                if m:
                    times.append(int(m.group(1)))
        return sorted(set(times))


class ForwardEngineFWI:
    def __init__(self, solver: 'ElasticSolver',
                 checkpoint_interval: int = 50,
                 use_checkpointing: bool = True,
                 max_checkpoints: int = 50,
                 checkpoint_dir: Optional[str] = None):
        self.solver = solver
        self.config = solver.config
        self.use_checkpointing = use_checkpointing
        self.checkpoint_interval = checkpoint_interval
        
        self.checkpoint_manager = CheckpointManager(
            nx=self.config.nx, nz=self.config.nz, nt=self.config.nt,
            checkpoint_interval=checkpoint_interval,
            max_checkpoints=max_checkpoints,
            storage_dir=checkpoint_dir,
            dtype=self.config.dtype
        )
        
        self.forward_wavefields: dict = {}
        self.receiver_data: Optional[np.ndarray] = None
    
    def run_forward(self,
                   save_wavefield_steps: Optional[List[int]] = None,
                   progress_callback: Optional[Callable] = None,
                   save_checkpoints: bool = True) -> dict:
        config = self.config
        nx, nz, nt = config.nx, config.nz, config.nt
        dt = config.dt
        dx, dz = config.dx, config.dz
        half_order = self.solver.half_order
        coeffs = self.solver.fd_coeffs
        
        c11 = self.solver.medium.c11
        c13 = self.solver.medium.c13
        c33 = self.solver.medium.c33
        c55 = self.solver.medium.c55
        rho_inv = self.solver.medium.rho_inv
        
        self.solver.reset()
        self.forward_wavefields.clear()
        
        if save_wavefield_steps is None:
            save_wavefield_steps = []
        
        save_wavefield_set = set(save_wavefield_steps)
        start_time = time.time()
        
        for it in range(nt):
            self.solver.dvx_dx.fill(0)
            self.solver.dvx_dz.fill(0)
            self.solver.dvz_dx.fill(0)
            self.solver.dvz_dz.fill(0)
            
            compute_derivatives_central(
                self.solver.vx, dx, dz,
                self.solver.dvx_dx, self.solver.dvx_dz,
                coeffs, half_order
            )
            compute_derivatives_central(
                self.solver.vz, dx, dz,
                self.solver.dvz_dx, self.solver.dvz_dz,
                coeffs, half_order
            )
            
            self.solver.cpml.apply_velocity_correction(
                self.solver.dvx_dx, self.solver.dvx_dz,
                self.solver.dvz_dx, self.solver.dvz_dz
            )
            
            _update_stress_central(
                self.solver.tau_xx, self.solver.tau_zz, self.solver.tau_xz,
                self.solver.dvx_dx, self.solver.dvx_dz,
                self.solver.dvz_dx, self.solver.dvz_dz,
                c11, c13, c33, c55, rho_inv,
                dt, half_order
            )
            
            if isinstance(self.solver.source, MultipleSources):
                self.solver.source.add_sources(
                    self.solver.tau_xx, self.solver.tau_zz, self.solver.tau_xz,
                    self.solver.vx, self.solver.vz, it
                )
            else:
                self.solver.source.add_source(
                    self.solver.tau_xx, self.solver.tau_zz, self.solver.tau_xz,
                    self.solver.vx, self.solver.vz, it
                )
            
            self.solver._apply_boundary_conditions()
            
            self.solver.dtau_xx_dx.fill(0)
            self.solver.dtau_xx_dz.fill(0)
            self.solver.dtau_zz_dx.fill(0)
            self.solver.dtau_zz_dz.fill(0)
            self.solver.dtau_xz_dx.fill(0)
            self.solver.dtau_xz_dz.fill(0)
            
            compute_derivatives_central(
                self.solver.tau_xx, dx, dz,
                self.solver.dtau_xx_dx, self.solver.dtau_xx_dz,
                coeffs, half_order
            )
            compute_derivatives_central(
                self.solver.tau_zz, dx, dz,
                self.solver.dtau_zz_dx, self.solver.dtau_zz_dz,
                coeffs, half_order
            )
            compute_derivatives_central(
                self.solver.tau_xz, dx, dz,
                self.solver.dtau_xz_dx, self.solver.dtau_xz_dz,
                coeffs, half_order
            )
            
            self.solver.cpml.apply_stress_correction(
                self.solver.dtau_xx_dx, self.solver.dtau_xx_dz,
                self.solver.dtau_zz_dx, self.solver.dtau_zz_dz,
                self.solver.dtau_xz_dx, self.solver.dtau_xz_dz
            )
            
            _update_velocity_central(
                self.solver.vx, self.solver.vz,
                self.solver.dtau_xx_dx, self.solver.dtau_zz_dz,
                self.solver.dtau_xz_dx, self.solver.dtau_xz_dz,
                rho_inv,
                dt, half_order
            )
            
            self.solver._apply_boundary_conditions()
            
            self.solver.receivers.record(
                self.solver.vx, self.solver.vz,
                self.solver.tau_xx, self.solver.tau_zz, self.solver.tau_xz,
                it
            )
            
            if self.solver.particle_motion is not None:
                self.solver.particle_motion.record(self.solver.vx, self.solver.vz, it)
            
            if it in save_wavefield_set:
                self.forward_wavefields[it] = {
                    'vx': self.solver.vx.copy(),
                    'vz': self.solver.vz.copy(),
                    'tau_xx': self.solver.tau_xx.copy(),
                    'tau_zz': self.solver.tau_zz.copy(),
                    'tau_xz': self.solver.tau_xz.copy(),
                }
            
            if save_checkpoints and self.use_checkpointing:
                if self.checkpoint_manager.should_checkpoint(it):
                    self.checkpoint_manager.save_checkpoint(
                        it, self.solver.vx, self.solver.vz,
                        self.solver.tau_xx, self.solver.tau_zz, self.solver.tau_xz
                    )
            
            if progress_callback is not None and (it % max(1, nt // 100) == 0 or it == nt - 1):
                elapsed = time.time() - start_time
                progress_callback(it + 1, nt, elapsed)
        
        n_rec = len(self.solver.receivers.receiver_indices)
        self.receiver_data = np.zeros((n_rec, nt, 3), dtype=config.dtype)
        self.receiver_data[:, :, 0] = self.solver.receivers.seismograms['vx']
        self.receiver_data[:, :, 1] = self.solver.receivers.seismograms['vz']
        self.receiver_data[:, :, 2] = self.solver.receivers.seismograms['pressure']
        
        return {
            'receiver_data': self.receiver_data,
            'forward_wavefields': self.forward_wavefields,
            'checkpoint_times': self.checkpoint_manager.get_checkpoint_times(),
            'receivers': self.solver.receivers,
        }
    
    def compute_misfit(self, observed_data: np.ndarray,
                      misfit_type: str = 'l2') -> Tuple[float, np.ndarray]:
        if self.receiver_data is None:
            raise ValueError("Forward simulation not run yet")
        
        if observed_data.shape != self.receiver_data.shape:
            raise ValueError(f"Shape mismatch: observed {observed_data.shape} "
                           f"!= synthetic {self.receiver_data.shape}")
        
        residual = self.receiver_data - observed_data
        
        if misfit_type == 'l2':
            misfit = 0.5 * np.sum(residual**2)
            adj_source = residual
        elif misfit_type == 'l1':
            misfit = np.sum(np.abs(residual))
            adj_source = np.sign(residual)
        elif misfit_type == 'cross_correlation':
            misfit = 0.0
            adj_source = np.zeros_like(residual)
            for i in range(residual.shape[0]):
                for c in range(residual.shape[2]):
                    cc = np.correlate(observed_data[i, :, c], 
                                     self.receiver_data[i, :, c], mode='full')
                    misfit -= np.max(cc)
                    max_idx = np.argmax(cc) - len(observed_data[i, :, c]) + 1
                    adj_source[i, :, c] = np.roll(observed_data[i, :, c], max_idx)
        else:
            raise ValueError(f"Unknown misfit type: {misfit_type}")
        
        return misfit, adj_source
    
    def get_wavefield(self, it: int, component: str = 'vx') -> np.ndarray:
        if it in self.forward_wavefields:
            return self.forward_wavefields[it][component]
        else:
            raise ValueError(f"Wavefield at iteration {it} not saved")
    
    def clear(self) -> None:
        self.forward_wavefields.clear()
        self.checkpoint_manager.clear_all()
        self.receiver_data = None
