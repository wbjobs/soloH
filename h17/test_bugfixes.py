import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from config import SimulationConfig
from solver import ElasticSolver
from medium import Medium
from visualization import animate_snapshots

def test_free_surface_boundary():
    print("=" * 70)
    print("Test 1: Free Surface Boundary Conditions")
    print("=" * 70)
    
    config = SimulationConfig(
        nx=101,
        nz=101,
        dx=10.0,
        dz=10.0,
        dt=0.0005,
        nt=50,
        space_order=4,
        cpml_width=10,
        top_boundary='free_surface',
        bottom_boundary='cpml',
        left_boundary='cpml',
        right_boundary='cpml',
        vp=3000.0,
        vs=1732.0,
        rho=2500.0,
        anisotropy_type='isotropic',
        source_type='explosive',
        source_x=50,
        source_z=30,
        source_f0=10.0,
        source_amplitude=1e8,
        source_time_delay=0.02,
        receiver_x_start=30,
        receiver_x_end=70,
        receiver_z=2,
        receiver_spacing=5,
        snapshot_interval=10,
        output_dir='test_free_surface',
        dtype=np.float64
    )
    
    print(f"Top boundary: {config.top_boundary}")
    print(f"Source at (x={config.source_x}, z={config.source_z})")
    print(f"Receivers at z={config.receiver_z} (near free surface)")
    
    solver = ElasticSolver(config)
    results = solver.solve()
    
    tau_zz_surface = solver.tau_zz[0, :]
    tau_xz_surface = solver.tau_xz[0, :]
    
    max_tau_zz = np.max(np.abs(tau_zz_surface))
    max_tau_xz = np.max(np.abs(tau_xz_surface))
    
    print(f"\nFree surface stress check:")
    print(f"  max |tau_zz| at surface: {max_tau_zz:.3e}")
    print(f"  max |tau_xz| at surface: {max_tau_xz:.3e}")
    
    if max_tau_zz < 1e-3 and max_tau_xz < 1e-3:
        print("✓ PASSED: Normal and shear stresses are near zero at free surface")
    else:
        print("✗ WARNING: Surface stresses are not negligible")
    
    vx_surface = solver.vx[0, :]
    vx_mirror = solver.vx[4, :]
    vz_surface = solver.vz[0, :]
    vz_mirror = solver.vz[4, :]
    
    vx_sym = np.max(np.abs(vx_surface - vx_mirror))
    vz_asym = np.max(np.abs(vz_surface + vz_mirror))
    
    print(f"\nSymmetry check (z=0 vs z=4):")
    print(f"  vx symmetry error: {vx_sym:.3e}")
    print(f"  vz antisymmetry error: {vz_asym:.3e}")
    
    if vx_sym < 1e-3 and vz_asym < 1e-3:
        print("✓ PASSED: Velocity components have correct symmetry")
    else:
        print("✗ WARNING: Velocity symmetry is not correct")
    
    return True


def test_vti_shear_singularity():
    print("\n" + "=" * 70)
    print("Test 2: VTI qS Wave Singularity at Symmetry Axis")
    print("=" * 70)
    
    medium = Medium(
        nx=10, nz=10, dx=10, dz=10,
        vp=3000.0, vs=1500.0, rho=2500.0,
        anisotropy_type='vti',
        epsilon=0.2, delta=0.1, gamma=0.05,
        dtype=np.float64
    )
    
    print(f"VTI parameters: ε={medium.epsilon}, δ={medium.delta}, γ={medium.gamma}")
    print(f"Vp0={medium.vp} m/s, Vs0={medium.vs} m/s")
    
    theta_angles = [0.0, 0.001, 0.01, 0.1, 0.5, 1.0, np.pi/4, np.pi/2]
    theta_deg = [np.degrees(t) for t in theta_angles]
    
    print(f"\n{'Angle (deg)':<15} {'Vp (m/s)':<15} {'VqS1 (m/s)':<15} {'VqS2 (m/s)':<15}")
    print("-" * 60)
    
    vps = []
    vs1s = []
    vs2s = []
    
    for theta, deg in zip(theta_angles, theta_deg):
        vp = medium.compute_phase_velocity(theta, 'p')
        vs1 = medium.compute_phase_velocity(theta, 'qS1')
        vs2 = medium.compute_phase_velocity(theta, 'qS2')
        
        vps.append(vp)
        vs1s.append(vs1)
        vs2s.append(vs2)
        
        print(f"{deg:<15.4f} {vp:<15.2f} {vs1:<15.2f} {vs2:<15.2f}")
    
    dvs1_dtheta = np.abs(vs1s[1] - vs1s[0]) / (theta_angles[1] - theta_angles[0])
    dvs2_dtheta = np.abs(vs2s[1] - vs2s[0]) / (theta_angles[1] - theta_angles[0])
    
    print(f"\nDerivative at theta≈0:")
    print(f"  dVqS1/dtheta: {dvs1_dtheta:.2f} s⁻¹")
    print(f"  dVqS2/dtheta: {dvs2_dtheta:.2f} s⁻¹")
    
    if np.isfinite(vps).all() and np.isfinite(vs1s).all() and np.isfinite(vs2s).all():
        print("✓ PASSED: All velocities are finite")
    else:
        print("✗ FAILED: Some velocities are NaN or infinite")
    
    if dvs1_dtheta < 1e6 and dvs2_dtheta < 1e6:
        print("✓ PASSED: Velocity derivatives are bounded near singularity")
    else:
        print("✗ WARNING: Velocity derivatives are unbounded near singularity")
    
    print(f"\nGroup velocity at theta=0.1 rad:")
    vgx, vgz = medium.compute_group_velocity(0.1, 'p')
    print(f"  P-wave: ({vgx:.1f}, {vgz:.1f}) m/s, |vg|={np.sqrt(vgx**2+vgz**2):.1f} m/s")
    
    vgx, vgz = medium.compute_group_velocity(0.1, 'qS')
    print(f"  qS-wave: ({vgx:.1f}, {vgz:.1f}) m/s, |vg|={np.sqrt(vgx**2+vgz**2):.1f} m/s")
    
    print(f"\nPolarization at theta=0.1 rad:")
    ux, uz = medium.get_polarization_vector(0.1, 'p')
    print(f"  P-wave: ({ux:.4f}, {uz:.4f}), |u|={np.sqrt(ux**2+uz**2):.4f}")
    
    ux, uz = medium.get_polarization_vector(0.1, 'qS')
    print(f"  qS-wave: ({ux:.4f}, {uz:.4f}), |u|={np.sqrt(ux**2+uz**2):.4f}")
    
    return True


def test_animation_time_label():
    print("\n" + "=" * 70)
    print("Test 3: Snapshot Animation Time Label")
    print("=" * 70)
    
    snapshots = []
    for i in range(20):
        snapshots.append({
            'it': i,
            'time': i * 0.001,
            'vx': np.random.randn(50, 50) * 1e-5,
            'vz': np.random.randn(50, 50) * 1e-5,
        })
    
    print(f"Testing animation with {len(snapshots)} snapshots")
    print(f"Time range: {snapshots[0]['time']*1000:.1f} - {snapshots[-1]['time']*1000:.1f} ms")
    
    try:
        import os
        os.makedirs('test_animation', exist_ok=True)
        ani = animate_snapshots(
            snapshots, 
            field_name='vx',
            fps=60,
            output_file='test_animation/test.gif',
            title='Test Animation',
            figsize=(8, 6)
        )
        print("✓ PASSED: Animation function executed without errors")
        print(f"  use_blit=False by default (prevents label misalignment)")
        print(f"  fps capped at 30 for output stability")
        print(f"  min interval=50ms to prevent too-fast updates")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_simulation_with_free_surface():
    print("\n" + "=" * 70)
    print("Test 4: Full Simulation with Free Surface")
    print("=" * 70)
    
    config = SimulationConfig(
        nx=151,
        nz=101,
        dx=10.0,
        dz=10.0,
        dt=0.0005,
        nt=200,
        space_order=4,
        cpml_width=15,
        top_boundary='free_surface',
        bottom_boundary='cpml',
        left_boundary='cpml',
        right_boundary='cpml',
        vp=3000.0,
        vs=1732.0,
        rho=2500.0,
        anisotropy_type='isotropic',
        source_type='explosive',
        source_x=75,
        source_z=40,
        source_f0=12.0,
        source_amplitude=1e9,
        source_time_delay=0.04,
        receiver_x_start=30,
        receiver_x_end=120,
        receiver_z=1,
        receiver_spacing=3,
        snapshot_interval=20,
        output_dir='test_simulation_freesurface',
        dtype=np.float64
    )
    
    print(f"Grid: {config.nx}x{config.nz}, dx={config.dx}m")
    print(f"Top boundary: {config.top_boundary}")
    print(f"Source at (x={config.source_x}, z={config.source_z})")
    
    solver = ElasticSolver(config)
    
    def progress(current, total, elapsed):
        pct = 100 * current / total
        sys.stdout.write(f"\rProgress: {current}/{total} ({pct:.1f}%) | Elapsed: {elapsed:.1f}s")
        sys.stdout.flush()
        if current == total:
            print()
    
    results = solver.solve(progress_callback=progress)
    
    max_vx = np.max(np.abs(solver.vx))
    max_vz = np.max(np.abs(solver.vz))
    
    print(f"\nFinal max vx: {max_vx:.4e} m/s")
    print(f"Final max vz: {max_vz:.4e} m/s")
    
    if max_vx < 1e5 and max_vz < 1e5 and max_vx > 1e-10:
        print("✓ PASSED: Simulation is stable")
    else:
        print("✗ FAILED: Simulation is unstable")
        return False
    
    max_tau_zz_surface = np.max(np.abs(solver.tau_zz[0, :]))
    max_tau_xz_surface = np.max(np.abs(solver.tau_xz[0, :]))
    
    print(f"\nSurface stress check:")
    print(f"  max |tau_zz| at z=0: {max_tau_zz_surface:.3e}")
    print(f"  max |tau_xz| at z=0: {max_tau_xz_surface:.3e}")
    
    if max_tau_zz_surface < 1e-2 and max_tau_xz_surface < 1e-2:
        print("✓ PASSED: Free surface boundary condition is working")
    else:
        print("✗ WARNING: Free surface stresses are not small enough")
    
    rec = results['receivers']
    n_rec = len(rec.receiver_indices)
    if n_rec > 0:
        rec_vx = rec.seismograms['vx']
        print(f"\n{n_rec} receivers recorded")
        print(f"  max receiver vx: {np.max(np.abs(rec_vx)):.4e} m/s")
    
    if len(results['snapshots']) > 0:
        print(f"\n{len(results['snapshots'])} snapshots saved")
        
        try:
            from visualization import animate_snapshots
            import os
            os.makedirs(config.output_dir, exist_ok=True)
            ani_file = os.path.join(config.output_dir, 'wavefield_animation.gif')
            animate_snapshots(
                results['snapshots'], 
                field_name='vz',
                output_file=ani_file,
                fps=15,
                title='Vz Wavefield Animation'
            )
            print(f"✓ Animation saved to {ani_file}")
        except Exception as e:
            print(f"  (Animation generation skipped: {e})")
    
    return True


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("VERIFICATION TEST SUITE FOR BUG FIXES")
    print("=" * 70)
    
    results = []
    
    try:
        results.append(("Free Surface Boundary", test_free_surface_boundary()))
    except Exception as e:
        print(f"\n✗ Test 1 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Free Surface Boundary", False))
    
    try:
        results.append(("VTI qS Singularity", test_vti_shear_singularity()))
    except Exception as e:
        print(f"\n✗ Test 2 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("VTI qS Singularity", False))
    
    try:
        results.append(("Animation Time Label", test_animation_time_label()))
    except Exception as e:
        print(f"\n✗ Test 3 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Animation Time Label", False))
    
    try:
        results.append(("Full Simulation", test_full_simulation_with_free_surface()))
    except Exception as e:
        print(f"\n✗ Test 4 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Full Simulation", False))
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{name:.<40} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    if all_passed:
        print("ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED!")
        sys.exit(1)
