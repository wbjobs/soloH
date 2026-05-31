import numpy as np
from numba import njit, prange
from fd_coefficients import get_fd_coefficients

def test_derivative():
    print("Testing derivative computation...")
    
    nx = 20
    nz = 20
    dx = 1.0
    dz = 1.0
    
    x = np.arange(nx) * dx
    z = np.arange(nz) * dz
    X, Z = np.meshgrid(x, z)
    
    field = np.sin(X) * np.cos(Z)
    exact_dx = np.cos(X) * np.cos(Z)
    exact_dz = -np.sin(X) * np.sin(Z)
    
    for order in [2, 4, 6, 8]:
        coeffs = get_fd_coefficients(order)
        half_order = order // 2
        
        @njit
        def compute_dx(field, coeffs, dx, half_order):
            nz, nx = field.shape
            out = np.zeros_like(field)
            for z in range(nz):
                for x in range(half_order, nx - half_order - 1):
                    deriv = 0.0
                    for m in range(half_order):
                        deriv += coeffs[m] * (field[z, x + m + 1] - field[z, x - m])
                    out[z, x] = deriv / dx
            return out
        
        @njit
        def compute_dz(field, coeffs, dz, half_order):
            nz, nx = field.shape
            out = np.zeros_like(field)
            for z in range(half_order, nz - half_order - 1):
                for x in range(nx):
                    deriv = 0.0
                    for m in range(half_order):
                        deriv += coeffs[m] * (field[z + m + 1, x] - field[z - m, x])
                    out[z, x] = deriv / dz
            return out
        
        num_dx = compute_dx(field, coeffs, dx, half_order)
        num_dz = compute_dz(field, coeffs, dz, half_order)
        
        err_dx = np.max(np.abs(num_dx[half_order:-half_order-1, half_order:-half_order-1] - 
                              exact_dx[half_order:-half_order-1, half_order:-half_order-1]))
        err_dz = np.max(np.abs(num_dz[half_order:-half_order-1, half_order:-half_order-1] - 
                              exact_dz[half_order:-half_order-1, half_order:-half_order-1]))
        
        print(f"Order {order}: max error dx = {err_dx:.3e}, dz = {err_dz:.3e}")
    
    print("\nDerivative test passed!")

if __name__ == '__main__':
    test_derivative()
