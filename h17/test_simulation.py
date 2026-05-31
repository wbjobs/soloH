import sys
import numpy as np
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from config import SimulationConfig
from solver import ElasticSolver
from visualization import plot_wiggle, plot_snapshot, create_summary_figure

def progress_callback(current, total, elapsed):
    percent = 100 * current / total
    sys.stdout.write(f"\rProgress: {current}/{total} ({percent:.1f}%) | Elapsed: {elapsed:.1f}s")
    sys.stdout.flush()
    if current == total:
        print()

def run_small_simulation():
    print("=" * 70)
    print("Running Small Elastic Wave Simulation Test")
    print("=" * 70)
    
    config = SimulationConfig(
        nx=101,
        nz=101,
        dx=10.0,
        dz=10.0,
        dt=0.0005,
        nt=200,
        space_order=4,
        cpml_width=20,
        vp=3000.0,
        vs=1732.0,
        rho=2500.0,
        anisotropy_type='isotropic',
        source_type='explosive',
        source_x=75,
        source_z=75,
        source_f0=15.0,
        source_amplitude=1e9,
        source_time_delay=0.08,
        receiver_x_start=30,
        receiver_x_end=120,
        receiver_z=5,
        receiver_spacing=5,
        snapshot_interval=20,
        output_dir='test_simulation_output',
        dtype=np.float64
    )
    
    print(f"\nGrid size: {config.nx} x {config.nz}")
    print(f"Grid spacing: {config.dx} x {config.dz} m")
    print(f"Time steps: {config.nt}, dt: {config.dt*1000:.2f} ms")
    print(f"Total time: {config.nt*config.dt:.2f} s")
    print(f"Space order: {config.space_order}")
    print(f"Number of receivers: {config.receiver_x_end - config.receiver_x_start + 1}")
    cfl = config.vp * config.dt / config.dx
    print(f"CFL number: {cfl:.4f}")
    print(f"\nStarting simulation...")
    
    solver = ElasticSolver(config)
    
    particle_points = [(50, 50), (100, 50), (75, 100)]
    solver.set_particle_motion_points(particle_points)
    
    start_time = time.time()
    results = solver.solve(progress_callback=progress_callback)
    total_time = time.time() - start_time
    
    print(f"\nSimulation completed in {total_time:.2f} seconds")
    print(f"Average time per step: {total_time/config.nt*1000:.3f} ms")
    print(f"Performance: {config.nt/total_time:.1f} time steps/second")
    
    print("\nChecking results...")
    print(f"Number of snapshots: {len(results['snapshots'])}")
    print(f"Number of receivers: {len(results['receivers'].receiver_indices)}")
    print(f"Particle motion recorded: {'particle_motion' in results}")
    
    vx_max = np.max(np.abs(results['snapshots'][-1]['vx']))
    vz_max = np.max(np.abs(results['snapshots'][-1]['vz']))
    print(f"Final max vx: {vx_max:.4e} m/s")
    print(f"Final max vz: {vz_max:.4e} m/s")
    
    if vx_max < 1e-10 or vz_max < 1e-10:
        print("WARNING: Wavefield amplitudes are very small!")
    else:
        print("✓ Wavefield amplitudes are reasonable")
    
    print("\nGenerating summary figures...")
    create_summary_figure(results, config.output_dir)
    
    print("\n" + "=" * 70)
    print("Simulation test completed successfully! ✓")
    print(f"Results saved to: {config.output_dir}")
    print("=" * 70)
    
    return results

if __name__ == '__main__':
    try:
        results = run_small_simulation()
        print("\nTest PASSED!")
    except Exception as e:
        print(f"\nTest FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
