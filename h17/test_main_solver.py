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

def test_main_solver():
    print("=" * 70)
    print("Testing Main ElasticSolver with Central Differences")
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
    
    for order in [2, 4]:
        print(f"\n{'='*70}")
        print(f"Testing with {order}th order FD...")
        print(f"{'='*70}")
        
        config = SimulationConfig(
            nx=nx,
            nz=nz,
            dx=dx,
            dz=dx,
            dt=dt,
            nt=nt,
            space_order=order,
            cpml_width=10,
            vp=vp,
            vs=vp/np.sqrt(3),
            rho=2500.0,
            anisotropy_type='isotropic',
            source_type='explosive',
            source_x=50,
            source_z=50,
            source_f0=f0,
            source_amplitude=1e8,
            source_time_delay=0.05,
            receiver_x_start=20,
            receiver_x_end=80,
            receiver_z=5,
            receiver_spacing=5,
            snapshot_interval=50,
            output_dir=f'test_output_order{order}',
            dtype=np.float64
        )
        
        print(f"\nInitializing solver...")
        solver = ElasticSolver(config)
        
        print("\nStarting simulation...")
        start_time = time.time()
        
        try:
            results = solver.solve(progress_callback=progress_callback)
            
            total_time = time.time() - start_time
            print(f"\nSimulation completed in {total_time:.2f}s")
            
            vx_max = np.max(np.abs(solver.vx))
            vz_max = np.max(np.abs(solver.vz))
            
            print(f"Final max vx: {vx_max:.4e}")
            print(f"Final max vz: {vz_max:.4e}")
            
            if vx_max < 1e-6 or vz_max < 1e-6:
                print(f"ORDER {order} FAILED: Wavefield amplitudes are too small")
            elif vx_max > 1e5 or vz_max > 1e5:
                print(f"ORDER {order} FAILED: Solution is diverging!")
            else:
                print(f"ORDER {order} PASSED: Solution is stable")
                
                n_rec = len(results['receivers'].receiver_indices)
                if n_rec > 0:
                    rec_vx_max = np.max(np.abs(results['receivers'].seismograms['vx']))
                    print(f"  {n_rec} receivers, vx max: {rec_vx_max:.4e}")
                    
                if len(results['snapshots']) > 0:
                    print(f"  Saved {len(results['snapshots'])} snapshots")
                    
        except Exception as e:
            print(f"\nORDER {order} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'='*70}")
    print("All tests completed")
    print(f"{'='*70}")

if __name__ == '__main__':
    try:
        test_main_solver()
    except Exception as e:
        print(f"\nTest crashed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
