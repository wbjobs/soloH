import sys
import numpy as np
import time
import matplotlib
matplotlib.use('Agg')

from config import SimulationConfig
from solver import ElasticSolver

def progress_callback(current, total, elapsed):
    percent = 100 * current / total
    sys.stdout.write(f"\rProgress: {current}/{total} ({percent:.1f}%) | Elapsed: {elapsed:.1f}s")
    sys.stdout.flush()
    if current == total:
        print()

def test_stability():
    print("=" * 70)
    print("Stability Test for Elastic Wave Solver")
    print("=" * 70)
    
    vp = 3000.0
    dx = 10.0
    f0 = 10.0
    nx = 101
    nz = 101
    
    dt = 0.0005
    nt = 300
    
    print(f"\nGrid: {nx}x{nz}, dx={dx}m")
    print(f"Time: dt={dt*1000:.3f}ms, nt={nt}, total={dt*nt:.2f}s")
    print(f"Vp={vp}m/s, f0={f0}Hz")
    print(f"Points per wavelength: {vp/(f0*dx):.1f}")
    print(f"CFL: {vp*dt/dx:.4f}")
    print(f"Vp*dt/dx = {vp*dt/dx:.4f} (should be < 0.5 for stability)")
    
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
        output_dir='stability_test_output',
        dtype=np.float64
    )
    
    print(f"\nInitializing solver with {config.space_order}th order FD...")
    solver = ElasticSolver(config)
    
    print("\nStarting simulation...")
    start_time = time.time()
    
    vx_max_history = []
    vz_max_history = []
    times = []
    
    for it in range(nt):
        config = solver.config
        nx, nz, nt_steps = config.nx, config.nz, config.nt
        dt_step = config.dt
        dx_step, dz_step = config.dx, config.dz
        half_order = solver.half_order
        coeffs = solver.fd_coeffs
        
        c11 = solver.medium.c11
        c12 = solver.medium.c12
        c13 = solver.medium.c13
        c33 = solver.medium.c33
        c44 = solver.medium.c44
        c55 = solver.medium.c55
        c66 = solver.medium.c66
        rho_inv = solver.medium.rho_inv
        
        c11_x = solver.medium.stagger(c11, 'x')
        c13_x = solver.medium.stagger(c13, 'x')
        c55_x = solver.medium.stagger(c55, 'x')
        
        c33_z = solver.medium.stagger(c33, 'z')
        c13_z = solver.medium.stagger(c13, 'z')
        c55_z = solver.medium.stagger(c55, 'z')
        
        rho_inv_vx = solver.medium.stagger(rho_inv, 'x')
        rho_inv_vz = solver.medium.stagger(rho_inv, 'z')
        
        solver.dvx_dx.fill(0)
        solver.dvx_dz.fill(0)
        solver.dvz_dx.fill(0)
        solver.dvz_dz.fill(0)
        
        from solver import _compute_velocity_derivatives
        _compute_velocity_derivatives(
            solver.vx, solver.vz,
            solver.dvx_dx, solver.dvx_dz, solver.dvz_dx, solver.dvz_dz,
            coeffs, dx_step, dz_step, half_order
        )
        
        solver.cpml.apply_velocity_correction(
            solver.dvx_dx, solver.dvx_dz, solver.dvz_dx, solver.dvz_dz
        )
        
        from solver import _update_stress
        _update_stress(
            solver.tau_xx, solver.tau_zz, solver.tau_xz,
            solver.dvx_dx, solver.dvx_dz, solver.dvz_dx, solver.dvz_dz,
            c11, c12, c13, c33, c44, c55, c66,
            c11_x, c13_x, c55_x, c33_z, c13_z, c55_z,
            dt_step, half_order
        )
        
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
        
        from solver import _compute_stress_derivatives
        _compute_stress_derivatives(
            solver.tau_xx, solver.tau_zz, solver.tau_xz,
            solver.dtau_xx_dx, solver.dtau_xx_dz,
            solver.dtau_zz_dx, solver.dtau_zz_dz,
            solver.dtau_xz_dx, solver.dtau_xz_dz,
            coeffs, dx_step, dz_step, half_order
        )
        
        solver.cpml.apply_stress_correction(
            solver.dtau_xx_dx, solver.dtau_xx_dz,
            solver.dtau_zz_dx, solver.dtau_zz_dz,
            solver.dtau_xz_dx, solver.dtau_xz_dz
        )
        
        from solver import _update_velocity
        _update_velocity(
            solver.vx, solver.vz,
            solver.dtau_xx_dx, solver.dtau_zz_dx,
            solver.dtau_xx_dz, solver.dtau_zz_dz,
            solver.dtau_xz_dx, solver.dtau_xz_dz,
            rho_inv_vx, rho_inv_vz,
            dt_step, half_order
        )
        
        vx_max = np.max(np.abs(solver.vx))
        vz_max = np.max(np.abs(solver.vz))
        vx_max_history.append(vx_max)
        vz_max_history.append(vz_max)
        times.append(it * dt_step)
        
        if it % 10 == 0:
            elapsed = time.time() - start_time
            print(f"Step {it:4d}/{nt}: max_vx={vx_max:.3e}, max_vz={vz_max:.3e}, elapsed={elapsed:.1f}s")
        
        if vx_max > 1e10 or vz_max > 1e10:
            print(f"\nWARNING: Solution diverging at step {it}!")
            print(f"max_vx={vx_max:.3e}, max_vz={vz_max:.3e}")
            break
    
    total_time = time.time() - start_time
    print(f"\nSimulation completed in {total_time:.2f}s")
    
    vx_max = vx_max_history[-1]
    vz_max = vz_max_history[-1]
    
    print(f"\nFinal max vx: {vx_max:.4e}")
    print(f"Final max vz: {vz_max:.4e}")
    
    if vx_max < 1e-10 or vz_max < 1e-10:
        print("FAILED: Wavefield amplitudes are zero")
        return False
    elif vx_max > 1e5 or vz_max > 1e5:
        print(f"FAILED: Solution is diverging!")
        return False
    else:
        print("PASSED: Solution is stable")
        return True

if __name__ == '__main__':
    try:
        success = test_stability()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nTest crashed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
