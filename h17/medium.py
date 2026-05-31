import numpy as np
from numba import njit, prange
from typing import Optional, Tuple


class Medium:
    def __init__(self, nx: int, nz: int, dx: float, dz: float,
                 vp: float = 3000.0, vs: float = 1732.0, rho: float = 2500.0,
                 anisotropy_type: str = 'isotropic',
                 epsilon: float = 0.0, delta: float = 0.0, gamma: float = 0.0,
                 theta: float = 0.0, phi: float = 0.0,
                 dtype=np.float64):
        self.nx = nx
        self.nz = nz
        self.dx = dx
        self.dz = dz
        self.dtype = dtype
        
        self.vp = vp
        self.vs = vs
        self.rho = rho
        
        self.anisotropy_type = anisotropy_type
        self.epsilon = epsilon
        self.delta = delta
        self.gamma = gamma
        self.theta = theta
        self.phi = phi
        
        self._init_elastic_parameters()
    
    def _init_elastic_parameters(self):
        nx, nz = self.nx, self.nz
        
        self.rho_field = np.full((nz, nx), self.rho, dtype=self.dtype)
        self.rho_inv = 1.0 / self.rho_field
        
        if self.anisotropy_type == 'isotropic':
            self._init_isotropic()
        elif self.anisotropy_type == 'vti':
            self._init_vti()
        elif self.anisotropy_type == 'tti':
            self._init_tti()
        else:
            raise ValueError(f"Unknown anisotropy type: {self.anisotropy_type}")
    
    def _init_isotropic(self):
        vp, vs, rho = self.vp, self.vs, self.rho
        
        lambda_ = rho * (vp**2 - 2 * vs**2)
        mu = rho * vs**2
        
        self.c11 = np.full((self.nz, self.nx), lambda_ + 2 * mu, dtype=self.dtype)
        self.c13 = np.full((self.nz, self.nx), lambda_, dtype=self.dtype)
        self.c33 = np.full((self.nz, self.nx), lambda_ + 2 * mu, dtype=self.dtype)
        self.c55 = np.full((self.nz, self.nx), mu, dtype=self.dtype)
        self.c66 = np.full((self.nz, self.nx), mu, dtype=self.dtype)
        self.c12 = np.full((self.nz, self.nx), lambda_, dtype=self.dtype)
        self.c23 = np.full((self.nz, self.nx), lambda_, dtype=self.dtype)
        self.c44 = np.full((self.nz, self.nx), mu, dtype=self.dtype)
    
    def _init_vti(self):
        vp, vs, rho = self.vp, self.vs, self.rho
        epsilon, delta, gamma = self.epsilon, self.delta, self.gamma
        
        c33 = rho * vp**2
        c44 = rho * vs**2
        c11 = c33 * (1 + 2 * epsilon)
        c66 = c44 * (1 + 2 * gamma)
        c13 = np.sqrt(c33 * (c33 - 2 * c44) * delta + c44**2) - c44
        c12 = c11 - 2 * c66
        c23 = c13
        
        self.c11 = np.full((self.nz, self.nx), c11, dtype=self.dtype)
        self.c13 = np.full((self.nz, self.nx), c13, dtype=self.dtype)
        self.c33 = np.full((self.nz, self.nx), c33, dtype=self.dtype)
        self.c55 = np.full((self.nz, self.nx), c44, dtype=self.dtype)
        self.c66 = np.full((self.nz, self.nx), c66, dtype=self.dtype)
        self.c12 = np.full((self.nz, self.nx), c12, dtype=self.dtype)
        self.c23 = np.full((self.nz, self.nx), c23, dtype=self.dtype)
        self.c44 = np.full((self.nz, self.nx), c44, dtype=self.dtype)
    
    def _init_tti(self):
        self._init_vti()
        theta_rad = np.radians(self.theta)
        phi_rad = np.radians(self.phi)
        
        self._rotate_stiffness_tensor(theta_rad, phi_rad)
    
    def _rotate_stiffness_tensor(self, theta: float, phi: float):
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        cos_p = np.cos(phi)
        sin_p = np.sin(phi)
        
        R = np.array([
            [cos_t * cos_p, -sin_p, sin_t * cos_p],
            [cos_t * sin_p, cos_p, sin_t * sin_p],
            [-sin_t, 0, cos_t]
        ], dtype=self.dtype)
        
        voigt_map = [
            (0, 0),
            (1, 1),
            (2, 2),
            (1, 2),
            (0, 2),
            (0, 1)
        ]
        
        M = np.zeros((6, 6), dtype=self.dtype)
        for k in range(6):
            alpha, beta = voigt_map[k]
            M[k, 0] = R[alpha, 0] * R[beta, 0]
            M[k, 1] = R[alpha, 1] * R[beta, 1]
            M[k, 2] = R[alpha, 2] * R[beta, 2]
            M[k, 3] = R[alpha, 1] * R[beta, 2] + R[alpha, 2] * R[beta, 1]
            M[k, 4] = R[alpha, 0] * R[beta, 2] + R[alpha, 2] * R[beta, 0]
            M[k, 5] = R[alpha, 0] * R[beta, 1] + R[alpha, 1] * R[beta, 0]
        
        c_original = np.zeros((6, 6), dtype=self.dtype)
        c_original[0, 0] = self.c11[0, 0]
        c_original[0, 1] = self.c12[0, 0]
        c_original[0, 2] = self.c13[0, 0]
        c_original[1, 0] = self.c12[0, 0]
        c_original[1, 1] = self.c11[0, 0]
        c_original[1, 2] = self.c13[0, 0]
        c_original[2, 0] = self.c13[0, 0]
        c_original[2, 1] = self.c13[0, 0]
        c_original[2, 2] = self.c33[0, 0]
        c_original[3, 3] = self.c44[0, 0]
        c_original[4, 4] = self.c55[0, 0]
        c_original[5, 5] = self.c66[0, 0]
        
        c_rotated = M @ c_original @ M.T
        
        self.c11[:] = c_rotated[0, 0]
        self.c12[:] = c_rotated[0, 1]
        self.c13[:] = c_rotated[0, 2]
        self.c23[:] = c_rotated[1, 2]
        self.c33[:] = c_rotated[2, 2]
        self.c44[:] = c_rotated[3, 3]
        self.c55[:] = c_rotated[4, 4]
        self.c66[:] = c_rotated[5, 5]
    
    def set_heterogeneous_model(self, vp_model: np.ndarray, vs_model: np.ndarray,
                                rho_model: Optional[np.ndarray] = None,
                                epsilon_model: Optional[np.ndarray] = None,
                                delta_model: Optional[np.ndarray] = None,
                                gamma_model: Optional[np.ndarray] = None) -> None:
        if vp_model.shape != (self.nz, self.nx):
            raise ValueError("Model shape mismatch")
        
        if rho_model is None:
            rho_model = np.full_like(vp_model, self.rho)
        
        self.rho_field = rho_model.astype(self.dtype)
        self.rho_inv = 1.0 / self.rho_field
        
        if self.anisotropy_type == 'isotropic':
            self._set_isotropic_model(vp_model, vs_model, rho_model)
        elif self.anisotropy_type == 'vti':
            if epsilon_model is None:
                epsilon_model = np.full_like(vp_model, self.epsilon)
            if delta_model is None:
                delta_model = np.full_like(vp_model, self.delta)
            if gamma_model is None:
                gamma_model = np.full_like(vp_model, self.gamma)
            self._set_vti_model(vp_model, vs_model, rho_model,
                               epsilon_model, delta_model, gamma_model)
    
    def _set_isotropic_model(self, vp: np.ndarray, vs: np.ndarray, rho: np.ndarray):
        lambda_ = rho * (vp**2 - 2 * vs**2)
        mu = rho * vs**2
        
        self.c11 = (lambda_ + 2 * mu).astype(self.dtype)
        self.c13 = lambda_.astype(self.dtype)
        self.c33 = (lambda_ + 2 * mu).astype(self.dtype)
        self.c55 = mu.astype(self.dtype)
        self.c66 = mu.astype(self.dtype)
        self.c12 = lambda_.astype(self.dtype)
        self.c23 = lambda_.astype(self.dtype)
        self.c44 = mu.astype(self.dtype)
    
    def _set_vti_model(self, vp: np.ndarray, vs: np.ndarray, rho: np.ndarray,
                       epsilon: np.ndarray, delta: np.ndarray, gamma: np.ndarray):
        c33 = rho * vp**2
        c44 = rho * vs**2
        c11 = c33 * (1 + 2 * epsilon)
        c66 = c44 * (1 + 2 * gamma)
        c13 = np.sqrt(c33 * (c33 - 2 * c44) * delta + c44**2) - c44
        c12 = c11 - 2 * c66
        c23 = c13
        
        self.c11 = c11.astype(self.dtype)
        self.c13 = c13.astype(self.dtype)
        self.c33 = c33.astype(self.dtype)
        self.c55 = c44.astype(self.dtype)
        self.c66 = c66.astype(self.dtype)
        self.c12 = c12.astype(self.dtype)
        self.c23 = c23.astype(self.dtype)
        self.c44 = c44.astype(self.dtype)
    
    def get_velocity(self, kind: str = 'p') -> np.ndarray:
        if kind == 'p':
            return np.sqrt(self.c33 / self.rho_field)
        elif kind == 's':
            return np.sqrt(self.c55 / self.rho_field)
        else:
            raise ValueError(f"Unknown velocity type: {kind}")
    
    def stagger(self, field: np.ndarray, direction: str) -> np.ndarray:
        if direction == 'x':
            return stagger_x(field)
        elif direction == 'z':
            return stagger_z(field)
        else:
            raise ValueError(f"Unknown direction: {direction}")
    
    def compute_phase_velocity(self, theta: float, wave_type: str = 'p') -> float:
        if self.anisotropy_type == 'isotropic':
            if wave_type == 'p':
                return self.vp
            elif wave_type == 's':
                return self.vs
            else:
                raise ValueError(f"Unknown wave type: {wave_type}")
        elif self.anisotropy_type in ['vti', 'tti']:
            if self.anisotropy_type == 'tti':
                theta = theta - np.radians(self.theta)
            
            return self._compute_vti_phase_velocity(theta, wave_type)
        else:
            raise ValueError(f"Unsupported anisotropy type: {self.anisotropy_type}")
    
    def _compute_vti_phase_velocity(self, theta: float, wave_type: str) -> float:
        rho = self.rho
        vp0 = self.vp
        vs0 = self.vs
        epsilon = self.epsilon
        delta = self.delta
        
        sin_theta = np.sin(theta)
        cos_theta = np.cos(theta)
        sin2 = sin_theta ** 2
        cos2 = cos_theta ** 2
        
        if wave_type == 'p':
            term1 = 1 + epsilon * sin2
            term2 = 0.5 * (epsilon - delta) * np.sin(2 * theta) ** 2
            return vp0 * np.sqrt(term1 + term2)
        elif wave_type == 'qS1' or wave_type == 'qS':
            sin_eps = 1e-6
            if abs(theta) < sin_eps or abs(theta - np.pi) < sin_eps:
                return vs0 * np.sqrt(1 + 2 * self.gamma)
            
            sin_theta = np.sin(theta)
            cos_theta = np.cos(theta)
            
            A = (1 + 2 * epsilon) * sin_theta**2 + (1 + 2 * self.gamma) * cos_theta**2
            B = (1 + 2 * epsilon) * sin_theta**2 - (1 + 2 * self.gamma) * cos_theta**2
            C = (epsilon - delta) * np.sin(2 * theta)**2
            
            D = B**2 + C
            D_safe = max(D, 1e-10)
            sqrt_D = np.sqrt(D_safe)
            
            smoothing = 1.0 - np.exp(-(abs(theta) / sin_eps)**2)
            
            vS1_sq = 0.5 * vs0**2 * (A - sqrt_D) * smoothing + vs0**2 * (1 + 2 * self.gamma) * (1 - smoothing)
            return np.sqrt(max(vS1_sq, vs0**2 * 0.01))
        elif wave_type == 'qS2':
            sin_eps = 1e-6
            if abs(theta) < sin_eps or abs(theta - np.pi) < sin_eps:
                return vs0
            
            sin_theta = np.sin(theta)
            cos_theta = np.cos(theta)
            
            A = (1 + 2 * epsilon) * sin_theta**2 + (1 + 2 * self.gamma) * cos_theta**2
            B = (1 + 2 * epsilon) * sin_theta**2 - (1 + 2 * self.gamma) * cos_theta**2
            C = (epsilon - delta) * np.sin(2 * theta)**2
            
            D = B**2 + C
            D_safe = max(D, 1e-10)
            sqrt_D = np.sqrt(D_safe)
            
            smoothing = 1.0 - np.exp(-(abs(theta) / sin_eps)**2)
            
            vS2_sq = 0.5 * vs0**2 * (A + sqrt_D) * smoothing + vs0**2 * (1 - smoothing)
            return np.sqrt(max(vS2_sq, vs0**2 * 0.01))
        else:
            raise ValueError(f"Unknown wave type: {wave_type}")
    
    def compute_group_velocity(self, theta: float, wave_type: str = 'p') -> Tuple[float, float]:
        sin_eps = 1e-8
        dtheta = 1e-6
        
        if abs(theta) < sin_eps:
            theta1 = dtheta
            theta2 = -dtheta
        else:
            theta1 = theta - dtheta
            theta2 = theta + dtheta
        
        v1 = self.compute_phase_velocity(theta1, wave_type)
        v2 = self.compute_phase_velocity(theta2, wave_type)
        dv_dtheta = (v2 - v1) / (2 * dtheta)
        
        v = self.compute_phase_velocity(theta, wave_type)
        
        vg_x = v * np.cos(theta) - dv_dtheta * np.sin(theta)
        vg_z = v * np.sin(theta) + dv_dtheta * np.cos(theta)
        
        return vg_x, vg_z
    
    def get_polarization_vector(self, theta: float, wave_type: str = 'p') -> Tuple[float, float]:
        if self.anisotropy_type == 'isotropic':
            if wave_type == 'p':
                return np.cos(theta), np.sin(theta)
            elif wave_type == 's':
                return -np.sin(theta), np.cos(theta)
            else:
                raise ValueError(f"Unknown wave type: {wave_type}")
        
        sin_eps = 1e-8
        if abs(theta) < sin_eps or abs(theta - np.pi) < sin_eps:
            if wave_type == 'p' or wave_type == 'qS':
                return 0.0, 1.0
            else:
                return 1.0, 0.0
        
        if wave_type == 'p':
            vp = self.compute_phase_velocity(theta, 'p')
            rho = self.rho
            c11 = self.c11[0, 0]
            c13 = self.c13[0, 0]
            c33 = self.c33[0, 0]
            c55 = self.c55[0, 0]
            
            sin_theta = np.sin(theta)
            cos_theta = np.cos(theta)
            
            denom = (c11 * cos_theta**2 + c55 * sin_theta**2 - rho * vp**2)
            denom_safe = max(abs(denom), 1e-10)
            ratio = (c13 + c55) * sin_theta * cos_theta / denom_safe
            
            ux = 1.0
            uz = ratio
            norm = np.sqrt(ux**2 + uz**2)
            if norm < 1e-10:
                return cos_theta, sin_theta
            return ux / norm, uz / norm
        elif wave_type == 'qS' or wave_type == 'qS1' or wave_type == 'qS2':
            vs = self.compute_phase_velocity(theta, wave_type)
            rho = self.rho
            c11 = self.c11[0, 0]
            c13 = self.c13[0, 0]
            c33 = self.c33[0, 0]
            c55 = self.c55[0, 0]
            
            sin_theta = np.sin(theta)
            cos_theta = np.cos(theta)
            
            denom = (c13 + c55) * sin_theta * cos_theta
            denom_safe = max(abs(denom), 1e-10)
            ratio = (c55 * cos_theta**2 + c33 * sin_theta**2 - rho * vs**2) / denom_safe
            
            ux = 1.0
            uz = ratio
            norm = np.sqrt(ux**2 + uz**2)
            if norm < 1e-10:
                return -sin_theta, cos_theta
            return ux / norm, uz / norm
        else:
            raise ValueError(f"Unknown wave type: {wave_type}")


@njit
def stagger_x(field: np.ndarray) -> np.ndarray:
    nz, nx = field.shape
    out = np.zeros_like(field)
    for z in prange(nz):
        for x in prange(nx - 1):
            out[z, x] = 0.5 * (field[z, x] + field[z, x + 1])
    return out


@njit
def stagger_z(field: np.ndarray) -> np.ndarray:
    nz, nx = field.shape
    out = np.zeros_like(field)
    for z in prange(nz - 1):
        for x in prange(nx):
            out[z, x] = 0.5 * (field[z, x] + field[z + 1, x])
    return out
