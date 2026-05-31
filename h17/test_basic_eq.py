import numpy as np
from numba import njit, prange
import time

def test_basic_equations():
    print("Testing basic elastic wave equations with 2nd order FD...")
    
    nx = 51
    nz = 51
    dx = 10.0
    dz = 10.0
    dt = 0.0005
    nt = 100
    
    vp = 3000.0
    vs = 1732.0
    rho = 2500.0
    
    c11 = rho * vp**2
    c33 = rho * vp**2
    c13 = c11 - 2 * rho * vs**2
    c55 = rho * vs**2
    
    print(f"c11={c11:.3e}, c13={c13:.3e}, c33={c33:.3e}, c55={c55:.3e}")
    print(f"CFL={vp*dt/dx:.4f}")
    
    vx = np.zeros((nz, nx))
    vz = np.zeros((nz, nx))
    tau_xx = np.zeros((nz, nx))
    tau_zz = np.zeros((nz, nx))
    tau_xz = np.zeros((nz, nx))
    
    sx = nx // 2
    sz = nz // 2
    f0 = 10.0
    t0 = 0.05
    
    @njit
    def step(vx, vz, tau_xx, tau_zz, tau_xz, dt, dx, dz, c11, c13, c33, c55, rho, it, f0, t0, sx, sz):
        nz, nx = vx.shape
        
        for z in range(1, nz-1):
            for x in range(1, nx-1):
                dvx_dx = (vx[z, x+1] - vx[z, x-1]) / (2*dx)
                dvz_dz = (vz[z+1, x] - vz[z-1, x]) / (2*dz)
                dvx_dz = (vx[z+1, x] - vx[z-1, x]) / (2*dz)
                dvz_dx = (vz[z, x+1] - vz[z, x-1]) / (2*dx)
                
                tau_xx[z, x] += dt * (c11 * dvx_dx + c13 * dvz_dz)
                tau_zz[z, x] += dt * (c13 * dvx_dx + c33 * dvz_dz)
                tau_xz[z, x] += dt * c55 * (dvx_dz + dvz_dx)
        
        t = it * dt
        tau = 0.0
        if t > 0:
            tau = np.pi * f0 * (t - t0)
            w = (1 - 2*tau**2) * np.exp(-tau**2)
        tau_xx[sz, sx] += dt * 1e8 * w
        tau_zz[sz, sx] += dt * 1e8 * w
        
        for z in range(1, nz-1):
            for x in range(1, nx-1):
                dtau_xx_dx = (tau_xx[z, x+1] - tau_xx[z, x-1]) / (2*dx)
                dtau_zz_dz = (tau_zz[z+1, x] - tau_zz[z-1, x]) / (2*dz)
                dtau_xz_dx = (tau_xz[z, x+1] - tau_xz[z, x-1]) / (2*dx)
                dtau_xz_dz = (tau_xz[z+1, x] - tau_xz[z-1, x]) / (2*dz)
                
                vx[z, x] += dt * (dtau_xx_dx + dtau_xz_dz) / rho
                vz[z, x] += dt * (dtau_zz_dz + dtau_xz_dx) / rho
    
    start = time.time()
    for it in range(nt):
        step(vx, vz, tau_xx, tau_zz, tau_xz, dt, dx, dz, c11, c13, c33, c55, rho, it, f0, t0, sx, sz)
        if it % 10 == 0:
            vx_max = np.max(np.abs(vx))
            vz_max = np.max(np.abs(vz))
            print(f"Step {it:3d}: max_vx={vx_max:.3e}, max_vz={vz_max:.3e}")
        
        if np.max(np.abs(vx)) > 1e10:
            print(f"Diverged at step {it}!")
            return False
    
    elapsed = time.time() - start
    print(f"\nCompleted in {elapsed:.2f}s")
    print(f"Final max_vx={np.max(np.abs(vx)):.3e}, max_vz={np.max(np.abs(vz)):.3e}")
    
    if np.max(np.abs(vx)) < 1e-3:
        print("FAILED: Amplitude too small")
        return False
    elif np.max(np.abs(vx)) > 1e5:
        print("FAILED: Diverging")
        return False
    else:
        print("PASSED: Stable")
        return True

if __name__ == '__main__':
    success = test_basic_equations()
    import sys
    sys.exit(0 if success else 1)
