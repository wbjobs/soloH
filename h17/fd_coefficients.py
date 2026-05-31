import numpy as np
from numba import njit, prange
from typing import Dict, Tuple


FD_COEFFICIENTS: Dict[int, np.ndarray] = {
    2: np.array([1.0]),
    4: np.array([9.0/8.0, -1.0/24.0]),
    6: np.array([75.0/64.0, -25.0/384.0, 3.0/640.0]),
    8: np.array([1225.0/1024.0, -245.0/3072.0, 49.0/5120.0, -5.0/7168.0]),
    10: np.array([19845.0/16384.0, -735.0/8192.0, 567.0/40960.0, -405.0/229376.0, 35.0/294912.0]),
    12: np.array([160083.0/131072.0, -12705.0/131072.0, 22869.0/1310720.0, -5445.0/1835008.0,
                   847.0/2359296.0, -63.0/2883584.0])
}

CENTRAL_FD_COEFFICIENTS: Dict[int, np.ndarray] = {
    2: np.array([1.0]),
    4: np.array([4.0/3.0, -1.0/6.0]),
    6: np.array([3.0/2.0, -3.0/10.0, 1.0/30.0]),
    8: np.array([8.0/5.0, -4.0/5.0, 8.0/35.0, -1.0/28.0]),
    10: np.array([5.0/4.0, -5.0/8.0, 5.0/21.0, -5.0/112.0, 1.0/126.0]),
    12: np.array([12.0/7.0, -15.0/28.0, 10.0/63.0, -1.0/28.0, 2.0/385.0, -1.0/2772.0])
}


def get_fd_coefficients(order: int) -> np.ndarray:
    if order not in FD_COEFFICIENTS:
        raise ValueError(f"Finite difference order {order} not supported. "
                         f"Supported orders: {list(FD_COEFFICIENTS.keys())}")
    return FD_COEFFICIENTS[order].copy()


def get_central_fd_coefficients(order: int) -> np.ndarray:
    if order not in CENTRAL_FD_COEFFICIENTS:
        raise ValueError(f"Central finite difference order {order} not supported. "
                         f"Supported orders: {list(CENTRAL_FD_COEFFICIENTS.keys())}")
    return CENTRAL_FD_COEFFICIENTS[order].copy()


@njit
def compute_derivative_x(field: np.ndarray, coeffs: np.ndarray, dx: float, 
                         out: np.ndarray, half_order: int) -> None:
    nz, nx = field.shape
    for z in prange(nz):
        for x in range(half_order, nx - half_order):
            deriv = 0.0
            for m in range(half_order):
                deriv += coeffs[m] * (field[z, x + m + 1] - field[z, x - m])
            out[z, x] = deriv / dx


@njit
def compute_derivative_z(field: np.ndarray, coeffs: np.ndarray, dz: float,
                         out: np.ndarray, half_order: int) -> None:
    nz, nx = field.shape
    for z in prange(half_order, nz - half_order):
        for x in range(nx):
            deriv = 0.0
            for m in range(half_order):
                deriv += coeffs[m] * (field[z + m + 1, x] - field[z - m, x])
            out[z, x] = deriv / dz


@njit
def compute_derivative_x_staggered(field: np.ndarray, coeffs: np.ndarray, dx: float,
                                   out: np.ndarray, half_order: int) -> None:
    nz, nx = field.shape
    for z in prange(nz):
        for x in range(half_order, nx - half_order - 1):
            deriv = 0.0
            for m in range(half_order):
                deriv += coeffs[m] * (field[z, x + m + 1] - field[z, x - m])
            out[z, x] = deriv / dx


@njit
def compute_derivative_z_staggered(field: np.ndarray, coeffs: np.ndarray, dz: float,
                                   out: np.ndarray, half_order: int) -> None:
    nz, nx = field.shape
    for z in prange(half_order, nz - half_order - 1):
        for x in range(nx):
            deriv = 0.0
            for m in range(half_order):
                deriv += coeffs[m] * (field[z + m + 1, x] - field[z - m, x])
            out[z, x] = deriv / dz


@njit(parallel=True, fastmath=True)
def compute_derivatives_central(field: np.ndarray, dx: float, dz: float,
                                ddx: np.ndarray, ddz: np.ndarray,
                                coeffs: np.ndarray, half_order: int):
    nz, nx = field.shape
    for z in prange(half_order, nz - half_order):
        for x in range(half_order, nx - half_order):
            d = 0.0
            for m in range(1, half_order + 1):
                d += coeffs[m-1] * (field[z, x + m] - field[z, x - m])
            ddx[z, x] = d / (2 * dx)
            
            d = 0.0
            for m in range(1, half_order + 1):
                d += coeffs[m-1] * (field[z + m, x] - field[z - m, x])
            ddz[z, x] = d / (2 * dz)


class StaggeredGrid:
    def __init__(self, nx: int, nz: int, dx: float, dz: float, dtype=np.float64):
        self.nx = nx
        self.nz = nz
        self.dx = dx
        self.dz = dz
        self.dtype = dtype
        
        self.x_centered = np.arange(nx) * dx
        self.z_centered = np.arange(nz) * dz
        
        self.x_staggered_x = (np.arange(nx) + 0.5) * dx
        self.z_staggered_z = (np.arange(nz) + 0.5) * dz
    
    def create_field(self, staggered: str = 'none') -> np.ndarray:
        if staggered == 'none':
            return np.zeros((self.nz, self.nx), dtype=self.dtype)
        elif staggered == 'x':
            return np.zeros((self.nz, self.nx), dtype=self.dtype)
        elif staggered == 'z':
            return np.zeros((self.nz, self.nx), dtype=self.dtype)
        elif staggered == 'xz':
            return np.zeros((self.nz, self.nx), dtype=self.dtype)
        else:
            raise ValueError(f"Unknown staggering: {staggered}")
    
    def get_position(self, field_type: str, ix: int, iz: int) -> Tuple[float, float]:
        if field_type in ['vx', 'tau_xx', 'tau_zz']:
            x = self.x_staggered_x[ix]
            z = self.z_centered[iz]
        elif field_type in ['vz', 'tau_xz']:
            x = self.x_centered[ix]
            z = self.z_staggered_z[iz]
        else:
            x = self.x_centered[ix]
            z = self.z_centered[iz]
        return x, z
