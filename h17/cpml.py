import numpy as np
from numba import njit, prange
from typing import Tuple


class CPML:
    def __init__(self, nx: int, nz: int, dx: float, dz: float, dt: float,
                 width: int = 30, max_power: float = 3.0,
                 reflection_coef: float = 0.001, dtype=np.float64):
        self.nx = nx
        self.nz = nz
        self.dx = dx
        self.dz = dz
        self.dt = dt
        self.width = width
        self.max_power = max_power
        self.reflection_coef = reflection_coef
        self.dtype = dtype
        
        self._init_profiles()
        self._init_memory_variables()
    
    def _init_profiles(self):
        nx, nz = self.nx, self.nz
        width = self.width
        
        self.kappa_x = np.ones(nx, dtype=self.dtype)
        self.alpha_x = np.zeros(nx, dtype=self.dtype)
        self.b_x = np.ones(nx, dtype=self.dtype)
        self.a_x = np.zeros(nx, dtype=self.dtype)
        
        self.kappa_z = np.ones(nz, dtype=self.dtype)
        self.alpha_z = np.zeros(nz, dtype=self.dtype)
        self.b_z = np.ones(nz, dtype=self.dtype)
        self.a_z = np.zeros(nz, dtype=self.dtype)
        
        self.kappa_x_half = np.ones(nx, dtype=self.dtype)
        self.alpha_x_half = np.zeros(nx, dtype=self.dtype)
        self.b_x_half = np.ones(nx, dtype=self.dtype)
        self.a_x_half = np.zeros(nx, dtype=self.dtype)
        
        self.kappa_z_half = np.ones(nz, dtype=self.dtype)
        self.alpha_z_half = np.zeros(nz, dtype=self.dtype)
        self.b_z_half = np.ones(nz, dtype=self.dtype)
        self.a_z_half = np.zeros(nz, dtype=self.dtype)
        
        self._compute_profile('x', self.kappa_x, self.alpha_x, self.b_x, self.a_x, 0.0)
        self._compute_profile('x', self.kappa_x_half, self.alpha_x_half, 
                              self.b_x_half, self.a_x_half, 0.5)
        self._compute_profile('z', self.kappa_z, self.alpha_z, self.b_z, self.a_z, 0.0)
        self._compute_profile('z', self.kappa_z_half, self.alpha_z_half,
                              self.b_z_half, self.a_z_half, 0.5)
    
    def _compute_profile(self, direction: str, kappa: np.ndarray, alpha: np.ndarray,
                         b: np.ndarray, a: np.ndarray, half_offset: float):
        n = self.nx if direction == 'x' else self.nz
        d = self.dx if direction == 'x' else self.dz
        width = self.width
        
        vmax = 3000.0
        d0 = -(self.max_power + 1) * vmax * np.log(self.reflection_coef) / (2 * width * d)
        
        for i in range(width):
            for side in [0, 1]:
                if side == 0:
                    idx = i
                    dist = (width - i - 0.5 - half_offset) * d
                else:
                    idx = n - 1 - i
                    dist = (width - i - 0.5 - half_offset) * d
                
                if dist < 0:
                    dist = 0
                
                sigma = d0 * (dist / (width * d)) ** self.max_power
                kappa[idx] = 1.0
                alpha[idx] = 0.1 * sigma if sigma > 0 else 0.0
                
                b[idx] = np.exp(-(sigma / kappa[idx] + alpha[idx]) * self.dt)
                if abs(sigma) > 1e-10:
                    a[idx] = sigma * (b[idx] - 1.0) / (kappa[idx] * (sigma + kappa[idx] * alpha[idx]))
                else:
                    a[idx] = 0.0
    
    def _init_memory_variables(self):
        nz, nx = self.nz, self.nx
        
        self.psi_dvx_dx = np.zeros((nz, nx), dtype=self.dtype)
        self.psi_dvx_dz = np.zeros((nz, nx), dtype=self.dtype)
        self.psi_dvz_dx = np.zeros((nz, nx), dtype=self.dtype)
        self.psi_dvz_dz = np.zeros((nz, nx), dtype=self.dtype)
        
        self.psi_dtau_xx_dx = np.zeros((nz, nx), dtype=self.dtype)
        self.psi_dtau_xx_dz = np.zeros((nz, nx), dtype=self.dtype)
        self.psi_dtau_zz_dx = np.zeros((nz, nx), dtype=self.dtype)
        self.psi_dtau_zz_dz = np.zeros((nz, nx), dtype=self.dtype)
        self.psi_dtau_xz_dx = np.zeros((nz, nx), dtype=self.dtype)
        self.psi_dtau_xz_dz = np.zeros((nz, nx), dtype=self.dtype)
    
    def reset_memory(self):
        self.psi_dvx_dx.fill(0)
        self.psi_dvx_dz.fill(0)
        self.psi_dvz_dx.fill(0)
        self.psi_dvz_dz.fill(0)
        self.psi_dtau_xx_dx.fill(0)
        self.psi_dtau_xx_dz.fill(0)
        self.psi_dtau_zz_dx.fill(0)
        self.psi_dtau_zz_dz.fill(0)
        self.psi_dtau_xz_dx.fill(0)
        self.psi_dtau_xz_dz.fill(0)
    
    def apply_velocity_correction(self, dvx_dx: np.ndarray, dvx_dz: np.ndarray,
                                   dvz_dx: np.ndarray, dvz_dz: np.ndarray) -> None:
        _apply_cpml_velocity(dvx_dx, dvx_dz, dvz_dx, dvz_dz,
                            self.psi_dvx_dx, self.psi_dvx_dz,
                            self.psi_dvz_dx, self.psi_dvz_dz,
                            self.b_x, self.a_x, self.kappa_x,
                            self.b_z, self.a_z, self.kappa_z,
                            self.b_x_half, self.a_x_half, self.kappa_x_half,
                            self.b_z_half, self.a_z_half, self.kappa_z_half,
                            self.width)
    
    def apply_stress_correction(self, dtau_xx_dx: np.ndarray, dtau_xx_dz: np.ndarray,
                                 dtau_zz_dx: np.ndarray, dtau_zz_dz: np.ndarray,
                                 dtau_xz_dx: np.ndarray, dtau_xz_dz: np.ndarray) -> None:
        _apply_cpml_stress(dtau_xx_dx, dtau_xx_dz,
                          dtau_zz_dx, dtau_zz_dz,
                          dtau_xz_dx, dtau_xz_dz,
                          self.psi_dtau_xx_dx, self.psi_dtau_xx_dz,
                          self.psi_dtau_zz_dx, self.psi_dtau_zz_dz,
                          self.psi_dtau_xz_dx, self.psi_dtau_xz_dz,
                          self.b_x, self.a_x, self.kappa_x,
                          self.b_z, self.a_z, self.kappa_z,
                          self.b_x_half, self.a_x_half, self.kappa_x_half,
                          self.b_z_half, self.a_z_half, self.kappa_z_half,
                          self.width)


@njit(parallel=True)
def _apply_cpml_velocity(dvx_dx, dvx_dz, dvz_dx, dvz_dz,
                         psi_dvx_dx, psi_dvx_dz, psi_dvz_dx, psi_dvz_dz,
                         b_x, a_x, kappa_x, b_z, a_z, kappa_z,
                         b_x_half, a_x_half, kappa_x_half,
                         b_z_half, a_z_half, kappa_z_half, width):
    nz, nx = dvx_dx.shape
    
    for z in prange(nz):
        for x in range(width):
            psi_dvx_dx[z, x] = b_x_half[x] * psi_dvx_dx[z, x] + a_x_half[x] * dvx_dx[z, x]
            dvx_dx[z, x] = dvx_dx[z, x] / kappa_x_half[x] + psi_dvx_dx[z, x]
            
            idx = nx - 1 - x
            psi_dvx_dx[z, idx] = b_x_half[idx] * psi_dvx_dx[z, idx] + a_x_half[idx] * dvx_dx[z, idx]
            dvx_dx[z, idx] = dvx_dx[z, idx] / kappa_x_half[idx] + psi_dvx_dx[z, idx]
            
            psi_dvz_dx[z, x] = b_x[x] * psi_dvz_dx[z, x] + a_x[x] * dvz_dx[z, x]
            dvz_dx[z, x] = dvz_dx[z, x] / kappa_x[x] + psi_dvz_dx[z, x]
            
            psi_dvz_dx[z, idx] = b_x[idx] * psi_dvz_dx[z, idx] + a_x[idx] * dvz_dx[z, idx]
            dvz_dx[z, idx] = dvz_dx[z, idx] / kappa_x[idx] + psi_dvz_dx[z, idx]
    
    for z in prange(width):
        for x in range(nx):
            psi_dvx_dz[z, x] = b_z[z] * psi_dvx_dz[z, x] + a_z[z] * dvx_dz[z, x]
            dvx_dz[z, x] = dvx_dz[z, x] / kappa_z[z] + psi_dvx_dz[z, x]
            
            idx = nz - 1 - z
            psi_dvx_dz[idx, x] = b_z[idx] * psi_dvx_dz[idx, x] + a_z[idx] * dvx_dz[idx, x]
            dvx_dz[idx, x] = dvx_dz[idx, x] / kappa_z[idx] + psi_dvx_dz[idx, x]
            
            psi_dvz_dz[z, x] = b_z_half[z] * psi_dvz_dz[z, x] + a_z_half[z] * dvz_dz[z, x]
            dvz_dz[z, x] = dvz_dz[z, x] / kappa_z_half[z] + psi_dvz_dz[z, x]
            
            psi_dvz_dz[idx, x] = b_z_half[idx] * psi_dvz_dz[idx, x] + a_z_half[idx] * dvz_dz[idx, x]
            dvz_dz[idx, x] = dvz_dz[idx, x] / kappa_z_half[idx] + psi_dvz_dz[idx, x]


@njit(parallel=True)
def _apply_cpml_stress(dtau_xx_dx, dtau_xx_dz, dtau_zz_dx, dtau_zz_dz,
                       dtau_xz_dx, dtau_xz_dz,
                       psi_dtau_xx_dx, psi_dtau_xx_dz, psi_dtau_zz_dx, psi_dtau_zz_dz,
                       psi_dtau_xz_dx, psi_dtau_xz_dz,
                       b_x, a_x, kappa_x, b_z, a_z, kappa_z,
                       b_x_half, a_x_half, kappa_x_half,
                       b_z_half, a_z_half, kappa_z_half, width):
    nz, nx = dtau_xx_dx.shape
    
    for z in prange(nz):
        for x in range(width):
            psi_dtau_xx_dx[z, x] = b_x[x] * psi_dtau_xx_dx[z, x] + a_x[x] * dtau_xx_dx[z, x]
            dtau_xx_dx[z, x] = dtau_xx_dx[z, x] / kappa_x[x] + psi_dtau_xx_dx[z, x]
            
            psi_dtau_zz_dx[z, x] = b_x[x] * psi_dtau_zz_dx[z, x] + a_x[x] * dtau_zz_dx[z, x]
            dtau_zz_dx[z, x] = dtau_zz_dx[z, x] / kappa_x[x] + psi_dtau_zz_dx[z, x]
            
            psi_dtau_xz_dx[z, x] = b_x_half[x] * psi_dtau_xz_dx[z, x] + a_x_half[x] * dtau_xz_dx[z, x]
            dtau_xz_dx[z, x] = dtau_xz_dx[z, x] / kappa_x_half[x] + psi_dtau_xz_dx[z, x]
            
            idx = nx - 1 - x
            psi_dtau_xx_dx[z, idx] = b_x[idx] * psi_dtau_xx_dx[z, idx] + a_x[idx] * dtau_xx_dx[z, idx]
            dtau_xx_dx[z, idx] = dtau_xx_dx[z, idx] / kappa_x[idx] + psi_dtau_xx_dx[z, idx]
            
            psi_dtau_zz_dx[z, idx] = b_x[idx] * psi_dtau_zz_dx[z, idx] + a_x[idx] * dtau_zz_dx[z, idx]
            dtau_zz_dx[z, idx] = dtau_zz_dx[z, idx] / kappa_x[idx] + psi_dtau_zz_dx[z, idx]
            
            psi_dtau_xz_dx[z, idx] = b_x_half[idx] * psi_dtau_xz_dx[z, idx] + a_x_half[idx] * dtau_xz_dx[z, idx]
            dtau_xz_dx[z, idx] = dtau_xz_dx[z, idx] / kappa_x_half[idx] + psi_dtau_xz_dx[z, idx]
    
    for z in prange(width):
        for x in range(nx):
            psi_dtau_xx_dz[z, x] = b_z[z] * psi_dtau_xx_dz[z, x] + a_z[z] * dtau_xx_dz[z, x]
            dtau_xx_dz[z, x] = dtau_xx_dz[z, x] / kappa_z[z] + psi_dtau_xx_dz[z, x]
            
            psi_dtau_zz_dz[z, x] = b_z[z] * psi_dtau_zz_dz[z, x] + a_z[z] * dtau_zz_dz[z, x]
            dtau_zz_dz[z, x] = dtau_zz_dz[z, x] / kappa_z[z] + psi_dtau_zz_dz[z, x]
            
            psi_dtau_xz_dz[z, x] = b_z_half[z] * psi_dtau_xz_dz[z, x] + a_z_half[z] * dtau_xz_dz[z, x]
            dtau_xz_dz[z, x] = dtau_xz_dz[z, x] / kappa_z_half[z] + psi_dtau_xz_dz[z, x]
            
            idx = nz - 1 - z
            psi_dtau_xx_dz[idx, x] = b_z[idx] * psi_dtau_xx_dz[idx, x] + a_z[idx] * dtau_xx_dz[idx, x]
            dtau_xx_dz[idx, x] = dtau_xx_dz[idx, x] / kappa_z[idx] + psi_dtau_xx_dz[idx, x]
            
            psi_dtau_zz_dz[idx, x] = b_z[idx] * psi_dtau_zz_dz[idx, x] + a_z[idx] * dtau_zz_dz[idx, x]
            dtau_zz_dz[idx, x] = dtau_zz_dz[idx, x] / kappa_z[idx] + psi_dtau_zz_dz[idx, x]
            
            psi_dtau_xz_dz[idx, x] = b_z_half[idx] * psi_dtau_xz_dz[idx, x] + a_z_half[idx] * dtau_xz_dz[idx, x]
            dtau_xz_dz[idx, x] = dtau_xz_dz[idx, x] / kappa_z_half[idx] + psi_dtau_xz_dz[idx, x]
