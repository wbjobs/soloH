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

def test_anisotropy():
    print("=" * 70)
    print("Testing Anisotropic Media (VTI and TTI)")
    print("=" * 70)
    
    vp = 3000.0
    dx = 10.0
    f0 = 10.0
    nx = 101
    nz = 101
    
    dt = 0.0005
    nt = 200
    
    test_cases = [
        ('isotropic', None, None),
        ('vti', 0.2, 0.1),
        ('tti', 0.2, 0.1),
    ]
    
    for aniso_type, epsilon, delta in test_cases:
        print(f"\n{'='*70}")
        if aniso_type == 'isotropic':
            print(f"Testing: {aniso_type}")
        else:
            print(f"Testing: {aniso_type.upper()} (ε={epsilon}, δ={delta})")
        print(f"{'='*70}")
        
        kwargs = {
            'nx': nx,
            'nz': nz,
            'dx': dx,
            'dz': dx,
            'dt': dt,
            'nt': nt,
            'space_order': 4,
            'cpml_width': 10,
            'vp': vp,
            'vs': vp/np.sqrt(3),
            'rho': 2500.0,
            'anisotropy_type': aniso_type,
            'source_type': 'explosive',
            'source_x': 50,
            'source_z': 50,
            'source_f0': f0,
            'source_amplitude': 1e8,
            'source_time_delay': 0.05,
            'receiver_x_start': 20,
            'receiver_x_end': 80,
            'receiver_z': 5,
            'receiver_spacing': 5,
            'snapshot_interval': 50,
            'output_dir': f'test_{aniso_type}',
            'dtype': np.float64
        }
        
        if aniso_type in ['vti', 'tti']:
            kwargs['epsilon'] = epsilon
            kwargs['delta'] = delta
            kwargs['gamma'] = 0.05
            
        if aniso_type == 'tti':
            kwargs['theta'] = 30.0
            kwargs['phi'] = 0.0
        
        config = SimulationConfig(**kwargs)
        
        print(f"\nInitializing solver...")
        try:
            solver = ElasticSolver(config)
            
            print(f"  Medium type: {solver.medium.anisotropy_type}")
            print(f"  c11 shape: {solver.medium.c11.shape}")
            print(f"  c33 shape: {solver.medium.c33.shape}")
            
            c11_val = solver.medium.c11[50, 50]
            c33_val = solver.medium.c33[50, 50]
            c55_val = solver.medium.c55[50, 50]
            
            print(f"  Stiffness at center:")
            print(f"    c11 = {c11_val:.3e}")
            print(f"    c33 = {c33_val:.3e}")
            print(f"    c55 = {c55_val:.3e}")
            
            if aniso_type == 'isotropic':
                expected_c11 = 2500 * vp**2
                expected_c33 = expected_c11
                expected_c55 = 2500 * (vp/np.sqrt(3))**2
                
                print(f"  Expected for isotropic:")
                print(f"    c11,c33 = ρVp² = {expected_c11:.3e}")
                print(f"    c55 = ρVs² = {expected_c55:.3e}")
            
            print("\nStarting simulation...")
            start_time = time.time()
            
            results = solver.solve(progress_callback=progress_callback)
            
            total_time = time.time() - start_time
            print(f"\nSimulation completed in {total_time:.2f}s")
            
            vx_max = np.max(np.abs(solver.vx))
            vz_max = np.max(np.abs(solver.vz))
            
            print(f"Final max vx: {vx_max:.4e}")
            print(f"Final max vz: {vz_max:.4e}")
            
            if vx_max < 1e-10 or vz_max < 1e-10:
                print(f"{aniso_type.upper()} FAILED: Wavefield amplitudes are too small")
            elif vx_max > 1e5 or vz_max > 1e5:
                print(f"{aniso_type.upper()} FAILED: Solution is diverging!")
            else:
                print(f"{aniso_type.upper()} PASSED: Solution is stable")
                
                n_rec = len(results['receivers'].receiver_indices)
                if n_rec > 0:
                    rec_vx_max = np.max(np.abs(results['receivers'].seismograms['vx']))
                    print(f"  {n_rec} receivers, vx max: {rec_vx_max:.4e}")
                    
        except Exception as e:
            print(f"\n{aniso_type.upper()} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'='*70}")
    print("All anisotropy tests completed")
    print(f"{'='*70}")

if __name__ == '__main__':
    try:
        test_anisotropy()
    except Exception as e:
        print(f"\nTest crashed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
