import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple, List
import os


@dataclass
class SimulationConfig:
    nx: int = 401
    nz: int = 401
    dx: float = 10.0
    dz: float = 10.0
    dt: float = 0.001
    nt: int = 1000
    space_order: int = 12
    time_order: int = 2
    
    cpml_width: int = 30
    cpml_max_power: float = 3.0
    cpml_reflection_coef: float = 0.001
    
    top_boundary: str = 'cpml'
    bottom_boundary: str = 'cpml'
    left_boundary: str = 'cpml'
    right_boundary: str = 'cpml'
    
    vp: float = 3000.0
    vs: float = 1732.0
    rho: float = 2500.0
    
    anisotropy_type: str = 'isotropic'
    epsilon: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    phi: float = 0.0
    
    source_type: str = 'explosive'
    source_x: int = 200
    source_z: int = 200
    source_f0: float = 20.0
    source_amplitude: float = 1e9
    source_time_delay: float = 0.05
    
    receiver_array_type: str = 'surface'
    receiver_x_start: int = 50
    receiver_x_end: int = 350
    receiver_z: int = 5
    receiver_spacing: int = 10
    
    snapshot_interval: int = 20
    output_dir: str = 'output'
    
    use_mpi: bool = False
    use_gpu: bool = False
    numba_parallel: bool = True
    numba_fastmath: bool = True
    
    dtype: np.dtype = field(default_factory=lambda: np.float64)
    
    def __post_init__(self):
        if self.anisotropy_type not in ['isotropic', 'vti', 'tti']:
            raise ValueError(f"Unknown anisotropy type: {self.anisotropy_type}")
        
        if self.source_type not in ['explosive', 'shear_x', 'shear_z', 'shear']:
            raise ValueError(f"Unknown source type: {self.source_type}")
        
        valid_boundaries = ['cpml', 'free_surface', 'reflecting']
        for bname in ['top_boundary', 'bottom_boundary', 'left_boundary', 'right_boundary']:
            bval = getattr(self, bname)
            if bval not in valid_boundaries:
                raise ValueError(f"Unknown boundary type for {bname}: {bval}. "
                               f"Valid types: {valid_boundaries}")
        
        if self.space_order % 2 != 0 or self.space_order < 2 or self.space_order > 12:
            raise ValueError("Space order must be even and between 2 and 12")
        
        if self.time_order not in [2]:
            raise ValueError("Only 2nd order time discretization is supported")
        
        os.makedirs(self.output_dir, exist_ok=True)
        self._validate_stability()
    
    def _validate_stability(self):
        vmax = max(self.vp, self.vs)
        if self.anisotropy_type != 'isotropic':
            vmax = self.vp * np.sqrt(1 + 2 * self.epsilon)
        
        dx_min = min(self.dx, self.dz)
        dt_stable = self.dx * self.dz / (vmax * np.sqrt(self.dx**2 + self.dz**2))
        
        if self.dt > dt_stable * 0.9:
            print(f"Warning: dt={self.dt} may be unstable. Max stable dt ~ {dt_stable:.6f}")
        
        fmax = self.source_f0 * 3
        lambda_min = min(self.vp, self.vs) / fmax
        ppw = lambda_min / dx_min
        if ppw < 5:
            print(f"Warning: Grid resolution may be too coarse. Points per wavelength: {ppw:.1f}")
    
    @property
    def shape(self) -> Tuple[int, int]:
        return (self.nz, self.nx)
    
    @property
    def cfl(self) -> float:
        vmax = max(self.vp, self.vs)
        return self.dt * vmax / min(self.dx, self.dz)
    
    def get_axis(self, axis: str) -> np.ndarray:
        if axis == 'x':
            return np.arange(self.nx) * self.dx
        elif axis == 'z':
            return np.arange(self.nz) * self.dz
        elif axis == 't':
            return np.arange(self.nt) * self.dt
        else:
            raise ValueError(f"Unknown axis: {axis}")
