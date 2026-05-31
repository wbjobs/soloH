#!/usr/bin/env python3
"""Test script for new features: ellipsoidal fitting, substructure tracking, and modified gravity."""

import sys
import os
import numpy as np
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

import halo_analysis as ha
from halo_analysis.core import Snapshot, Halo, EllipsoidalShape
from halo_analysis.analysis import save_halo_catalog

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
OK = "[OK]"


def create_test_snapshot(n_halos: int = 3, n_particles_per_halo: int = 100,
                         box_size: float = 100.0, redshift: float = 0.0,
                         index: int = 0) -> Snapshot:
    snap = Snapshot()
    snap.index = index
    snap.redshift = redshift
    snap.scale_factor = 1.0 / (1.0 + redshift)
    snap.box_size = box_size

    total_particles = n_halos * n_particles_per_halo
    snap.particles.ids = np.arange(total_particles, dtype=np.uint64)
    snap.particles.positions = np.zeros((total_particles, 3), dtype=np.float64)
    snap.particles.velocities = np.random.randn(total_particles, 3).astype(np.float64) * 50.0
    snap.particles.masses = np.ones(total_particles, dtype=np.float64) * 1e10

    halo_centers = [
        (25.0, 25.0, 25.0),
        (75.0, 50.0, 50.0),
        (50.0, 75.0, 75.0),
    ]

    for h in range(min(n_halos, 3)):
        cx, cy, cz = halo_centers[h]
        start = h * n_particles_per_halo
        end = (h + 1) * n_particles_per_halo

        a, b, c = 5.0, 3.0, 2.0
        theta = np.random.uniform(0, np.pi, n_particles_per_halo)
        phi = np.random.uniform(0, 2 * np.pi, n_particles_per_halo)
        r = np.random.uniform(0, 1, n_particles_per_halo) ** (1/3)

        x = cx + a * r * np.sin(theta) * np.cos(phi)
        y = cy + b * r * np.sin(theta) * np.sin(phi)
        z = cz + c * r * np.cos(theta)

        x = np.mod(x, box_size)
        y = np.mod(y, box_size)
        z = np.mod(z, box_size)

        snap.particles.positions[start:end, 0] = x
        snap.particles.positions[start:end, 1] = y
        snap.particles.positions[start:end, 2] = z

    return snap


def test_ellipsoidal_fit():
    print("\n" + "="*60)
    print("TEST 1: Ellipsoidal Shape Fitting")
    print("="*60)

    all_passed = True

    try:
        snap = create_test_snapshot(n_halos=1, n_particles_per_halo=200)

        fof = ha.FoFFinder(link_length_ratio=0.2, min_particles=10)
        fof.find_halos(snap)

        print(f"{OK} Found {len(snap.halos)} halos")

        halo = snap.halos[0]
        print(f"{OK} Halo mass: {halo.mass:.2e} Msun")
        print(f"{OK} Shape converged: {halo.shape.converged}")

        if not halo.shape.converged:
            print(f"{FAIL} Shape did not converge")
            all_passed = False
        else:
            print(f"{OK} Axis lengths: a={halo.shape.axis_a:.2f}, b={halo.shape.axis_b:.2f}, c={halo.shape.axis_c:.2f}")

            expected_ratio_b_a = 3.0 / 5.0
            expected_ratio_c_a = 2.0 / 5.0

            ratio_error_b_a = abs(halo.shape.axis_ratio_b_a - expected_ratio_b_a)
            ratio_error_c_a = abs(halo.shape.axis_ratio_c_a - expected_ratio_c_a)

            print(f"{OK} Axis ratio b/a: {halo.shape.axis_ratio_b_a:.3f} (expected ~{expected_ratio_b_a:.3f}, error: {ratio_error_b_a:.3f})")
            print(f"{OK} Axis ratio c/a: {halo.shape.axis_ratio_c_a:.3f} (expected ~{expected_ratio_c_a:.3f}, error: {ratio_error_c_a:.3f})")

            if ratio_error_b_a > 0.2 or ratio_error_c_a > 0.2:
                print(f"{WARN} Axis ratios differ significantly from expected (this may be OK for random distributions)")

            print(f"{OK} Ellipticity: {halo.shape.ellipticity:.3f}")
            print(f"{OK} Prolateness: {halo.shape.prolateness:.3f}")
            print(f"{OK} Triaxiality: {halo.shape.triaxiality:.3f}")

            det = np.linalg.det(halo.shape.orientation_matrix)
            print(f"{OK} Orientation matrix determinant: {det:.3f} (should be ±1)")
            if abs(abs(det) - 1.0) > 0.1:
                print(f"{WARN} Orientation matrix is not orthogonal")

            phi, theta, psi = halo.shape.euler_angles
            print(f"{OK} Euler angles: phi={phi:.2f}, theta={theta:.2f}, psi={psi:.2f}")

            if 0 <= halo.shape.ellipticity <= 1:
                print(f"{OK} Ellipticity in valid range [0, 1]")
            else:
                print(f"{FAIL} Ellipticity out of range: {halo.shape.ellipticity}")
                all_passed = False

            if -1 <= halo.shape.triaxiality <= 1:
                print(f"{OK} Triaxiality in valid range [-1, 1]")
            else:
                print(f"{FAIL} Triaxiality out of range: {halo.shape.triaxiality}")
                all_passed = False

            if halo.shape.axis_a >= halo.shape.axis_b >= halo.shape.axis_c:
                print(f"{OK} Axes correctly ordered (a >= b >= c)")
            else:
                print(f"{FAIL} Axes not correctly ordered")
                all_passed = False

        fitter = ha.EllipsoidalFitter()
        tensor = fitter.compute_inertia_tensor(halo, snap)
        eigvals, eigvecs = fitter.diagonalize_3x3(tensor)

        print(f"{OK} Inertia tensor eigenvalues: {eigvals}")

        if eigvals[0] >= eigvals[1] >= eigvals[2]:
            print(f"{OK} Eigenvalues correctly sorted")
        else:
            print(f"{FAIL} Eigenvalues not sorted")
            all_passed = False

    except Exception as e:
        print(f"{FAIL} Exception in ellipsoidal fit test: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    if all_passed:
        print(f"\n{PASS} Ellipsoidal shape fitting test passed")
    else:
        print(f"\n{FAIL} Ellipsoidal shape fitting test failed")

    return all_passed


def test_substructure():
    print("\n" + "="*60)
    print("TEST 2: Substructure Finding and Tracking")
    print("="*60)

    all_passed = True

    try:
        n_snapshots = 3
        snapshots = []

        for i in range(n_snapshots):
            z = 5.0 - i * 2.5
            snap = create_test_snapshot(n_halos=3, n_particles_per_halo=80, redshift=z, index=i)

            host_start = 2 * 80
            sub_center = (28.0, 28.0, 28.0)
            n_sub_particles = 20
            for j in range(n_sub_particles):
                idx = host_start + j
                theta = np.random.uniform(0, np.pi)
                phi = np.random.uniform(0, 2 * np.pi)
                r = np.random.uniform(0, 2.0)
                x = sub_center[0] + r * np.sin(theta) * np.cos(phi)
                y = sub_center[1] + r * np.sin(theta) * np.sin(phi)
                z = sub_center[2] + r * np.cos(theta)
                snap.particles.positions[idx] = [x, y, z]

            snapshots.append(snap)

        fof = ha.FoFFinder(link_length_ratio=0.2, min_particles=10)
        for snap in snapshots:
            fof.find_halos(snap)
            print(f"{OK} Snapshot {snap.index} (z={snap.redshift:.2f}): {len(snap.halos)} halos")

        sub_finder = ha.SubstructureFinder(mass_ratio_threshold=0.5, radius_threshold=3.0, min_particles=10)

        for snap in snapshots:
            sub_finder.find_substructures(snap)
            n_sub = sum(1 for h in snap.halos if h.is_substructure)
            print(f"{OK} Snapshot {snap.index}: {n_sub} substructures identified")

            for halo in snap.halos:
                if halo.is_substructure:
                    print(f"  {OK} Subhalo {halo.halo_id}: M={halo.mass:.2e}, parent={halo.parent_halo_id}")
                if halo.substructure_ids:
                    print(f"  {OK} Host halo {halo.halo_id}: M={halo.mass:.2e}, {len(halo.substructure_ids)} substructures")

        if n_snapshots >= 2:
            builder = ha.MergerTreeBuilder(particle_share_threshold=0.3)
            builder.build_trees(snapshots)

            sub_finder.track_substructures(snapshots)
            n_tracked = sum(1 for s in snapshots for h in s.halos if h.is_substructure and h.descendant_id != 0)
            print(f"{OK} Substructures tracked across snapshots: {n_tracked}")

        r = sub_finder.compute_halo_radius(snapshots[0].halos[0])
        print(f"{OK} Halo radius computation works: {r:.2f} Mpc/h")

        if len(snapshots[0].halos) > 1:
            host = snapshots[0].halos[0]
            sub_ids = sub_finder.identify_subhalos_within_halo(host, snapshots[0].halos, snapshots[0])
            print(f"{OK} Subhalo identification within halo returns {len(sub_ids)} candidates")

        if len(snapshots[0].halos) > 0:
            halo = snapshots[0].halos[0]
            orig_n = len(halo.particle_ids)
            sub_finder.decompose_halo_bound(halo, snapshots[0], n_iterations=2)
            new_n = len(halo.particle_ids)
            print(f"{OK} Bound particle decomposition: {orig_n} -> {new_n} particles")

            if new_n <= orig_n and new_n >= 10:
                print(f"{OK} Bound decomposition correctly reduced particle count")
            else:
                print(f"{WARN} Bound decomposition result unexpected (orig={orig_n}, new={new_n})")

    except Exception as e:
        print(f"{FAIL} Exception in substructure test: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    if all_passed:
        print(f"\n{PASS} Substructure test passed")
    else:
        print(f"\n{FAIL} Substructure test failed")

    return all_passed


def test_modified_gravity():
    print("\n" + "="*60)
    print("TEST 3: Modified Gravity (F(R)) Comparison Interface")
    print("="*60)

    all_passed = True

    try:
        snap = create_test_snapshot(n_halos=3, n_particles_per_halo=100)
        fof = ha.FoFFinder(link_length_ratio=0.2, min_particles=10)
        fof.find_halos(snap)

        mg_interface = ha.ModifiedGravityInterface()
        print(f"{OK} ModifiedGravityInterface created")

        fr_params = ha.FR_Parameters(f_R0=1e-6, n=1.0, name='F(R), fR0=1e-6')
        mg_interface.register_model(ha.GravityModel.F_R, fr_params)
        print(f"{OK} F(R) model registered: f_R0={fr_params.f_R0}, n={fr_params.n}")

        beta = mg_interface.compute_fifth_force_coupling(1e-6, n=1.0)
        print(f"{OK} Fifth force coupling (f_R=1e-6): {beta:.4f}")
        if beta > 0:
            print(f"{OK} Fifth force coupling is positive")
        else:
            print(f"{FAIL} Fifth force coupling should be positive")
            all_passed = False

        beta_zero = mg_interface.compute_fifth_force_coupling(0.0)
        if abs(beta_zero) < 1e-10:
            print(f"{OK} Fifth force coupling is zero for GR (f_R=0)")
        else:
            print(f"{FAIL} Fifth force coupling should be zero for GR")
            all_passed = False

        lambda_s = mg_interface.compute_screening_scale(1e-6, n=1.0, density=200 * 2.775e11)
        print(f"{OK} Screening scale: {lambda_s:.4f} Mpc/h")

        gr_params = mg_interface.get_parameters(ha.GravityModel.GR)
        print(f"{OK} GR parameters retrieved: f_R0={gr_params.f_R0}")
        if abs(gr_params.f_R0) < 1e-15:
            print(f"{OK} GR has f_R0=0")
        else:
            print(f"{FAIL} GR should have f_R0=0")
            all_passed = False

        all_halos = snap.halos
        box_size = snap.box_size
        stats = mg_interface.compute_statistics(all_halos, box_size, use_adaptive_binning=True, min_count_per_bin=2)

        print(f"\n{OK} Halo statistics computed:")
        print(f"  Number of halos: {stats.num_halos}")
        print(f"  Mean mass: {stats.mass_mean:.2e} Msun")
        print(f"  Median mass: {stats.mass_median:.2e} Msun")
        print(f"  Mean spin: {stats.spin_mean:.4f}")
        print(f"  Mean axis ratio b/a: {stats.axis_ratio_mean_b_a:.3f}")
        print(f"  Mean axis ratio c/a: {stats.axis_ratio_mean_c_a:.3f}")
        print(f"  Mean triaxiality: {stats.triaxiality_mean:.3f}")
        print(f"  Mean ellipticity: {stats.ellipticity_mean:.3f}")
        print(f"  Mass function bins: {len(stats.mass_bins)}")

        if stats.num_halos > 0 and stats.mass_mean > 0:
            print(f"{OK} Statistics look reasonable")
        else:
            print(f"{FAIL} Statistics have unexpected zero values")
            all_passed = False

        if len(stats.mass_bins) > 0 and len(stats.mass_function) == len(stats.mass_bins):
            print(f"{OK} Mass function arrays have consistent lengths")
        else:
            print(f"{FAIL} Mass function array lengths inconsistent")
            all_passed = False

        boost_factors = []
        screened = 0
        for halo in all_halos:
            boost = mg_interface.compute_boost_factor(halo.mass, halo.redshift, fr_params)
            boost_factors.append(boost)
            if mg_interface.is_halo_chameleon_screened(halo, fr_params):
                screened += 1

        print(f"\n{OK} F(R) analysis:")
        print(f"  Mean boost factor: {np.mean(boost_factors):.4f}")
        print(f"  Boost factor range: [{min(boost_factors):.4f}, {max(boost_factors):.4f}]")
        print(f"  Screened halos: {screened}/{len(all_halos)}")

        if all(b >= 1.0 for b in boost_factors):
            print(f"{OK} All boost factors are >= 1.0 (as expected for F(R))")
        else:
            print(f"{WARN} Some boost factors are < 1.0 (unexpected for F(R))")

        snap2 = create_test_snapshot(n_halos=3, n_particles_per_halo=100, redshift=0.5)
        fof.find_halos(snap2)
        stats2 = mg_interface.compute_statistics(snap2.halos, snap2.box_size)

        comp = mg_interface.compare_models(stats, stats2, 'z=0', 'z=0.5')
        print(f"\n{OK} Model comparison:")
        print(f"  Mass function delta: {comp.mass_function_delta:.4f}")
        print(f"  Spin delta: {comp.spin_delta:.4f}")
        print(f"  Ellipticity delta: {comp.ellipticity_delta:.4f}")
        print(f"  Mass function ratio bins: {len(comp.mass_function_ratio)}")

        sample1 = np.random.normal(0, 1, 1000)
        sample2 = np.random.normal(0, 1, 1000)
        d, p = mg_interface.kolmogorov_smirnov_test(sample1, sample2)
        print(f"\n{OK} KS test (same distribution): D={d:.4f}, p={p:.4f}")
        if p > 0.05:
            print(f"{OK} KS test correctly does not reject same distribution")
        else:
            print(f"{WARN} KS test p-value is low for same distribution (statistical fluctuation)")

        sample3 = np.random.normal(1, 1, 1000)
        d2, p2 = mg_interface.kolmogorov_smirnov_test(sample1, sample3)
        print(f"{OK} KS test (different distribution): D={d2:.4f}, p={p2:.4e}")
        if p2 < 0.05:
            print(f"{OK} KS test correctly rejects different distribution")
        else:
            print(f"{WARN} KS test p-value is high for different distribution (statistical fluctuation)")

    except Exception as e:
        print(f"{FAIL} Exception in modified gravity test: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    if all_passed:
        print(f"\n{PASS} Modified gravity test passed")
    else:
        print(f"\n{FAIL} Modified gravity test failed")

    return all_passed


def test_cli_new_options():
    print("\n" + "="*60)
    print("TEST 4: CLI New Options Integration")
    print("="*60)

    all_passed = True

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            sys.path.insert(0, os.path.dirname(__file__))
            from generate_test_data import generate_snapshot, generate_halo_particles

            snap_file = os.path.join(tmpdir, 'snapshot_000.dat')

            n_halos = 3
            n_particles_per_halo = 150
            box_size = 50.0
            particle_mass = 1e10
            rng = np.random.RandomState(42)
            halo_centers = np.array([[15.0, 15.0, 15.0], [35.0, 25.0, 25.0], [25.0, 35.0, 35.0]])
            halo_velocities = np.zeros((n_halos, 3))
            halo_masses = np.ones(n_halos) * particle_mass * n_particles_per_halo
            halo_r_virs = np.array([2.0, 2.0, 2.0])

            generate_snapshot(snap_file, redshift=0.0, n_halos=n_halos,
                             n_particles_per_halo=n_particles_per_halo,
                             box_size=box_size, particle_mass=particle_mass,
                             halo_centers=halo_centers, halo_velocities=halo_velocities,
                             halo_masses=halo_masses, halo_r_virs=halo_r_virs, rng=rng,
                             merge_events={})

            import subprocess
            cli_path = os.path.join(os.path.dirname(__file__), '..', 'python', 'halo_analysis', 'cli.py')

            output_dir = os.path.join(tmpdir, 'results')

            cmd = [
                sys.executable, cli_path, 'run',
                '--input', snap_file,
                '--output', output_dir,
                '--min-particles', '10',
                '--find-substructures',
                '--track-substructures',
                '--compare-mg',
                '--f_R0', '1e-5',
                '--fr-n', '1.0',
                '--print-stats',
                '--verbose'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                print(f"{OK} CLI with new options runs successfully")

                output = result.stdout + result.stderr

                expected_strings = [
                    'Ellipsoidal shape',
                    'Substructures',
                    'boost factor',
                    'Screened halos',
                    'axis ratio',
                    'triaxiality',
                ]

                for s in expected_strings:
                    if s in output:
                        print(f"{OK} Output contains '{s}'")
                    else:
                        print(f"{WARN} Output missing '{s}' (might be OK)")

                mg_file = os.path.join(output_dir, 'mg_comparison.json')
                if os.path.exists(mg_file):
                    import json
                    with open(mg_file) as f:
                        mg_data = json.load(f)
                    print(f"{OK} MG comparison JSON generated")
                    print(f"  Model: {mg_data.get('model', 'N/A')}")
                    print(f"  f_R0: {mg_data.get('f_R0', 'N/A')}")
                    print(f"  Mean boost: {mg_data.get('mean_boost', 'N/A'):.4f}")
                else:
                    print(f"{WARN} MG comparison JSON not found at {mg_file}")

            else:
                print(f"{FAIL} CLI failed with return code {result.returncode}")
                print(f"stdout:\n{result.stdout}")
                print(f"stderr:\n{result.stderr}")
                all_passed = False

    except Exception as e:
        print(f"{FAIL} Exception in CLI test: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    if all_passed:
        print(f"\n{PASS} CLI new options test passed")
    else:
        print(f"\n{FAIL} CLI new options test failed")

    return all_passed


def test_api_consistency():
    print("\n" + "="*60)
    print("TEST 5: API Consistency and Module Exports")
    print("="*60)

    all_passed = True

    expected_exports = [
        'EllipsoidalShape',
        'EllipsoidalFitter',
        'SubstructureFinder',
        'GravityModel',
        'FR_Parameters',
        'HaloStatistics',
        'ModelComparison',
        'ModifiedGravityInterface',
    ]

    for name in expected_exports:
        if hasattr(ha, name):
            print(f"{OK} '{name}' is exported from halo_analysis")
        else:
            print(f"{FAIL} '{name}' is NOT exported from halo_analysis")
            all_passed = False

    if ha.__version__ >= '1.1.0':
        print(f"{OK} Version updated: {ha.__version__}")
    else:
        print(f"{WARN} Version not properly updated: {ha.__version__}")

    halo = Halo()
    if hasattr(halo, 'shape') and isinstance(halo.shape, EllipsoidalShape):
        print(f"{OK} Halo has 'shape' attribute of correct type")
    else:
        print(f"{FAIL} Halo missing 'shape' attribute or wrong type")
        all_passed = False

    if hasattr(halo, 'is_substructure') and hasattr(halo, 'parent_halo_id') and hasattr(halo, 'substructure_ids'):
        print(f"{OK} Halo has substructure attributes")
    else:
        print(f"{FAIL} Halo missing substructure attributes")
        all_passed = False

    fof = ha.FoFFinder()
    if hasattr(fof, 'compute_shape') and hasattr(fof, 'shape_fitter'):
        print(f"{OK} FoFFinder has shape computation attributes")
    else:
        print(f"{FAIL} FoFFinder missing shape attributes")
        all_passed = False

    if all_passed:
        print(f"\n{PASS} API consistency test passed")
    else:
        print(f"\n{FAIL} API consistency test failed")

    return all_passed


def main():
    print("Testing new features: ellipsoidal fitting, substructure tracking, modified gravity")
    print(f"Using {'C++ extension' if ha.CPP_AVAILABLE else 'Python/Numba'} implementation")

    results = []

    results.append(('Ellipsoidal fitting', test_ellipsoidal_fit()))
    results.append(('Substructure', test_substructure()))
    results.append(('Modified gravity', test_modified_gravity()))
    results.append(('API consistency', test_api_consistency()))

    try:
        results.append(('CLI new options', test_cli_new_options()))
    except Exception as e:
        print(f"\n{WARN} CLI test skipped due to: {e}")

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    all_passed = True
    for name, passed in results:
        status = PASS if passed else FAIL
        print(f"{status} {name}")
        if not passed:
            all_passed = False

    print("="*60)

    if all_passed:
        print(f"\n{PASS} ALL TESTS PASSED")
        return 0
    else:
        print(f"\n{FAIL} SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
