import sys
import numpy as np
import time
import matplotlib
matplotlib.use('Agg')

from config import SimulationConfig
from solver_central import CentralElasticSolver

def progress_callback(current, total, elapsed):
    percent = 100 * current / total
    sys.stdout.write(f"\rProgress: {current}/{total} ({percent:.1f}%) | Elapsed: {elapsed:.1f}s")
    sys.stdout.flush()
    if current == total:
        print()

def test_central_solver():
    print("=" * 70)
    print("Testing Central Difference Elastic Wave Solver")
    print("=" * 70)
    
    vp = 3000.0
    dx = 10.0
    f0 = 10.0
    nx = 101
    nz = 101
    
    dt = 0.0005
    nt = 200
    
    print(f"\nGrid: {nx}x{nz}, dx={dx}m")
    print(f"Time: dt={dt*1000:.3f}ms, nt={nt}, total={dt*nt:.2f}s")
    print(f"Vp={vp}m/s, f0={f0}Hz")
    print(f"Points per wavelength: {vp/(f0*dx):.1f}")
    print(f"CFL: {vp*dt/dx:.4f}")
    
    config = SimulationConfig(
        nx=nx,
        nz=nz,
        dx=dx,
        dz=dx,
        dt=dt,
        nt=nt,
        space_order=4,
        cpml_width=15,
        vp=vp,
        vs=vp/np.sqrt(3),
        rho=2500.0,
        anisotropy_type='isotropic',
        source_type='explosive',
        source_x=50,
        source_z=50,
        source_f0=f0,
        source_amplitude=1e8,
        source_time_delay=0.1,
        receiver_x_start=20,
        receiver_x_end=80,
        receiver_z=5,
        receiver_spacing=5,
        snapshot_interval=10,
        output_dir='central_solver_output',
        dtype=np.float64
    )
    
    print(f"\nInitializing solver with {config.space_order}th order FD...")
    solver = CentralElasticSolver(config)
    
    print("\nStarting simulation...")
    start_time = time.time()
    
    for it in range(nt):
        config = solver.config
        nx, nz, nt_steps = config.nx, config.nz, config.nt
        dt_step = config.dt
        dx_step, dz_step = config.dx, config.dz
        half_order = solver.half_order
        coeffs = solver.fd_coeffs
        
        c11 = solver.medium.c11
        c13 = solver.medium.c13
        c33 = solver.medium.c33
        c55 = solver.medium.c55
        rho_inv = solver.medium.rho_inv
        
        solver.dvx_dx.fill(0)
        solver.dvx_dz.fill(0)
        solver.dvz_dx.fill(0)
        solver.dvz_dz.fill(0)
        
        from solver_central import _compute_derivatives_central
        _compute_derivatives_central(solver.vx, dx_step, dz_step, solver.dvx_dx, solver.dvx_dz, coeffs, half_order)
        _compute_derivatives_central(solver.vz, dx_step, dz_step, solver.dvz_dx, solver.dvz_dz, coeffs, half_order)
        
        solver.cpml.apply_velocity_correction(
            solver.dvx_dx, solver.dvx_dz, solver.dvz_dx, solver.dvz_dz
        )
        
        for z in range(half_order, nz - half_order):
            for x in range(half_order, nx - half_order):
                sxx = c11[z, x] * solver.dvx_dx[z, x] + c13[z, x] * solver.dvz_dz[z, x]
                solver.tau_xx[z, x] += dt_step * sxx
                szz = c13[z, x] * solver.dvx_dx[z, x] + c33[z, x] * solver.dvz_dz[z, x]
                solver.tau_zz[z, x] += dt_step * szz
                sxz = c55[z, x] * (solver.dvx_dz[z, x] + solver.dvz_dx[z, x])
                solver.tau_xz[z, x] += dt_step * sxz
        
        solver.source.add_source(
            solver.tau_xx, solver.tau_zz, solver.tau_xz,
            solver.vx, solver.vz, it
        )
        
        solver.dtau_xx_dx.fill(0)
        solver.dtau_xx_dz.fill(0)
        solver.dtau_zz_dx.fill(0)
        solver.dtau_zz_dz.fill(0)
        solver.dtau_xz_dx.fill(0)
        solver.dtau_xz_dz.fill(0)
        
        _compute_derivatives_central(solver.tau_xx, dx_step, dz_step, solver.dtau_xx_dx, solver.dtau_xx_dz, coeffs, half_order)
        _compute_derivatives_central(solver.tau_zz, dx_step, dz_step, solver.dtau_zz_dx, solver.dtau_zz_dz, coeffs, half_order)
        _compute_derivatives_central(solver.tau_xz, dx_step, dz_step, solver.dtau_xz_dx, solver.dtau_xz_dz, coeffs, half_order)
        
        solver.cpml.apply_stress_correction(
            solver.dtau_xx_dx, solver.dtau_xx_dz,
            solver.dtau_zz_dx, solver.dtau_zz_dz,
            solver.dtau_xz_dx, solver.dtau_xz_dz
        )
        
        for z in range(half_order, nz - half_order):
            for x in range(half_order, nx - half_order):
                dvx = (solver.dtau_xx_dx[z, x] + solver.dtau_xz_dz[z, x]) * rho_inv[z, x]
                solver.vx[z, x] += dt_step * dvx
                dvz = (solver.dtau_zz_dz[z, x] + solver.dtau_xz_dx[z, x]) * rho_inv[z, x]
                solver.vz[z, x] += dt_step * dvz
        
        if it % 10 == 0:
            vx_max = np.max(np.abs(solver.vx))
            vz_max = np.max(np.abs(solver.vz))
            elapsed = time.time() - start_time
            print(f"Step {it:4d}/{nt}: max_vx={vx_max:.3e}, max_vz={vz_max:.3e}, elapsed={elapsed:.1f}s")
        
        if np.max(np.abs(solver.vx)) > 1e10 or np.max(np.abs(solver.vz)) > 1e10:
            print(f"\nFAILED: Solution diverging at step {it}!")
            return False
    
    total_time = time.time() - start_time
    print(f"\nSimulation completed in {total_time:.2f}s")
    
    vx_max = np.max(np.abs(solver.vx))
    vz_max = np.max(np.abs(solver.vz))
    
    print(f"\nFinal max vx: {vx_max:.4e}")
    print(f"Final max vz: {vz_max:.4e}")
    
    if vx_max < 1e-3 or vz_max < 1e-3:
        print("FAILED: Wavefield amplitudes are too small")
        return False
    elif vx_max > 1e5 or vz_max > 1e5:
        print(f"FAILED: Solution is diverging!")
        return False
    else:
        print("PASSED: Solution is stable")
        return True

if __name__ == '__main__':
    try:
        success = test_central_solver()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nTest crashed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
