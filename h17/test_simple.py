import numpy as np
from numba import njit, prange

def test_2nd_order_derivative():
    print("Testing 2nd order staggered derivative...")
    
    nx = 100
    nz = 100
    dx = 0.1
    dz = 0.1
    
    x = np.arange(nx) * dx
    z = np.arange(nz) * dz
    X, Z = np.meshgrid(x, z)
    
    k = 2 * np.pi  # wave number
    field = np.sin(k * X) * np.cos(k * Z)
    exact_dx = k * np.cos(k * X) * np.cos(k * Z)
    exact_dz = -k * np.sin(k * X) * np.sin(k * Z)
    
    @njit
    def compute_dx_2nd(field, dx):
        nz, nx = field.shape
        out = np.zeros_like(field)
        for z in range(nz):
            for x in range(1, nx - 1):
                out[z, x] = (field[z, x + 1] - field[z, x - 1]) / (2 * dx)
        return out
    
    @njit
    def compute_dx_staggered_2nd(field, dx):
        nz, nx = field.shape
        out = np.zeros_like(field)
        for z in range(nz):
            for x in range(0, nx - 1):
                out[z, x] = (field[z, x + 1] - field[z, x]) / dx
        return out
    
    @njit
    def compute_dz_2nd(field, dz):
        nz, nx = field.shape
        out = np.zeros_like(field)
        for z in range(1, nz - 1):
            for x in range(nx):
                out[z, x] = (field[z + 1, x] - field[z - 1, x]) / (2 * dz)
        return out
    
    @njit
    def compute_dz_staggered_2nd(field, dz):
        nz, nx = field.shape
        out = np.zeros_like(field)
        for z in range(0, nz - 1):
            for x in range(nx):
                out[z, x] = (field[z + 1, x] - field[z, x]) / dz
        return out
    
    num_dx = compute_dx_2nd(field, dx)
    num_dz = compute_dz_2nd(field, dz)
    
    err_dx = np.max(np.abs(num_dx[5:-5, 5:-5] - exact_dx[5:-5, 5:-5]))
    err_dz = np.max(np.abs(num_dz[5:-5, 5:-5] - exact_dz[5:-5, 5:-5]))
    
    print(f"Centered 2nd order: max error dx = {err_dx:.3e}, dz = {err_dz:.3e}")
    
    num_dx_stag = compute_dx_staggered_2nd(field, dx)
    num_dz_stag = compute_dz_staggered_2nd(field, dz)
    
    err_dx_stag = np.max(np.abs(num_dx_stag[5:-5, 5:-5] - exact_dx[5:-5, 5:-5]))
    err_dz_stag = np.max(np.abs(num_dz_stag[5:-5, 5:-5] - exact_dz[5:-5, 5:-5]))
    
    print(f"Staggered 2nd order: max error dx = {err_dx_stag:.3e}, dz = {err_dz_stag:.3e}")
    
    print("\nNote: Staggered derivative gives derivative at mid-point, so it should be compared with exact solution at mid-point.")
    print("For staggered derivative at x[i], it approximates df/dx at x[i+dx/2]")
    
    exact_dx_mid = k * np.cos(k * (X + dx/2)) * np.cos(k * Z)
    err_dx_stag_mid = np.max(np.abs(num_dx_stag[5:-5, 5:-5] - exact_dx_mid[5:-5, 5:-5]))
    print(f"Staggered dx compared to mid-point exact: max error = {err_dx_stag_mid:.3e}")

if __name__ == '__main__':
    test_2nd_order_derivative()
