#!/usr/bin/env python3
"""End-to-end test script for halo analysis pipeline."""

import os
import sys
import subprocess
import json
import tempfile
import shutil

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, 'python'))


def run_command(cmd, cwd=None):
    print(f"\n$ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    return result.returncode


def test_imports():
    print("="*60)
    print("TEST 1: Python imports")
    print("="*60)

    try:
        import halo_analysis as ha
        print(f"  [OK] halo_analysis imported successfully")
        print(f"  [OK] C++ extension available: {ha.CPP_AVAILABLE}")
        print(f"  [OK] Numba available: {ha.core.NUMBA_AVAILABLE}")
        print(f"  [OK] Graphviz available: {ha.visualization.GRAPHVIZ_AVAILABLE}")

        from halo_analysis import GadgetReader, FoFFinder, MergerTreeBuilder
        print("  [OK] Core classes imported")

        from halo_analysis.analysis import (
            compute_mass_function, filter_halos_by_mass, save_halo_catalog
        )
        print("  [OK] Analysis functions imported")

        from halo_analysis.visualization import (
            save_merger_tree_graphviz, plot_mass_function
        )
        print("  [OK] Visualization functions imported")

        return True
    except Exception as e:
        print(f"  [FAIL] Import failed: {e}")
        return False


def test_core_functions():
    print("\n" + "="*60)
    print("TEST 2: Core functions")
    print("="*60)

    try:
        import numpy as np
        import halo_analysis as ha
        from halo_analysis.core import Snapshot, Halo

        spacing = ha.compute_mean_interparticle_spacing(100.0, 1000)
        assert spacing > 0, "Mean spacing should be positive"
        print(f"  [OK] compute_mean_interparticle_spacing: {spacing:.2f}")

        dist = ha.periodic_distance((0, 0, 0), (90, 0, 0), 100.0)
        assert abs(dist - 10.0) < 1e-10, "Periodic distance calculation incorrect"
        print(f"  [OK] periodic_distance: {dist:.2f}")

        return True
    except Exception as e:
        print(f"  [FAIL] Core function test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_pipeline(tmpdir):
    print("\n" + "="*60)
    print("TEST 3: Full analysis pipeline")
    print("="*60)

    test_data_dir = os.path.join(tmpdir, "test_snapshots")
    results_dir = os.path.join(tmpdir, "results")

    try:
        gen_script = os.path.join(os.path.dirname(__file__), "generate_test_data.py")
        ret = run_command(
            f"python {gen_script} --output-dir {test_data_dir} "
            f"--n-snapshots 4 --n-halos 3 --n-particles 50 --seed 42"
        )
        assert ret == 0, "Test data generation failed"
        print("  [OK] Test data generated")

        snapshot_files = sorted([f for f in os.listdir(test_data_dir) if f.endswith('.dat')])
        assert len(snapshot_files) == 4, f"Expected 4 snapshots, got {len(snapshot_files)}"
        print(f"  [OK] Found {len(snapshot_files)} snapshot files")

        import numpy as np
        import halo_analysis as ha
        from halo_analysis.core import Snapshot
        from halo_analysis.analysis import (
            get_merger_history, save_halo_catalog, filter_halos_by_mass
        )
        from halo_analysis.visualization import save_merger_tree_graphviz

        reader = ha.GadgetReader()
        snapshots = []
        for i, fname in enumerate(snapshot_files):
            snap = Snapshot()
            filepath = os.path.join(test_data_dir, fname)
            success = reader.read(filepath, snap, i)
            assert success, f"Failed to read {fname}"
            snapshots.append(snap)
            print(f"  [OK] Read snapshot {i}: z={snap.redshift:.2f}, "
                  f"{snap.particles.size()} particles")

        fof = ha.FoFFinder(link_length_ratio=0.2, min_particles=20)
        for i, snap in enumerate(snapshots):
            fof.find_halos(snap)
            print(f"  [OK] FoF on snapshot {i}: found {len(snap.halos)} halos")

        builder = ha.MergerTreeBuilder(particle_share_threshold=0.3)
        builder.build_trees(snapshots)
        print(f"  [OK] Merger tree built with {len(builder.get_nodes())} nodes")

        builder.compute_formation_redshifts(snapshots)
        print("  [OK] Formation redshifts computed")

        builder.identify_subhalos(snapshots)
        print("  [OK] Subhalos identified")

        all_halos = [h for s in snapshots for h in s.halos]
        if all_halos:
            target_halo = all_halos[-1]
            history = get_merger_history(target_halo.halo_id, builder, snapshots)
            print(f"  [OK] Merger history for halo {target_halo.halo_id}: "
                  f"{len(history['progenitor_chain'])} progenitors, "
                  f"{len(history['merger_events'])} mergers")

        os.makedirs(results_dir, exist_ok=True)
        catalog_file = os.path.join(results_dir, "catalog.json")
        save_halo_catalog(snapshots, builder, catalog_file)
        assert os.path.exists(catalog_file), "Catalog not saved"
        with open(catalog_file, 'r') as f:
            catalog = json.load(f)
        print(f"  [OK] Catalog saved: {len(catalog['halos'])} halos")

        filtered = filter_halos_by_mass(all_halos, 1e11, 1e13)
        print(f"  [OK] Mass filtering: {len(filtered)}/{len(all_halos)} halos in range")

        tree_file = os.path.join(results_dir, "merger_tree")
        if ha.visualization.GRAPHVIZ_AVAILABLE:
            success = save_merger_tree_graphviz(builder, tree_file, format='png')
            if success:
                expected = tree_file + '.png'
                if os.path.exists(expected):
                    print(f"  [OK] Merger tree visualization saved")
                else:
                    print(f"  [WARN] Merger tree file not found at {expected}")
            else:
                print(f"  [WARN] Merger tree rendering failed (Graphviz may not be installed)")
        else:
            print(f"  [WARN] Skipping visualization (graphviz not available)")

        for snap in snapshots:
            for halo in snap.halos:
                assert halo.mass > 0, "Halo mass should be positive"
                assert halo.spin_parameter >= 0, "Spin parameter should be non-negative"
                assert halo.formation_redshift >= 0, "Formation redshift should be non-negative"
        print("  [OK] All halo properties valid")

        return True

    except Exception as e:
        print(f"  [FAIL] Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cli(tmpdir):
    print("\n" + "="*60)
    print("TEST 4: Command-line interface")
    print("="*60)

    test_data_dir = os.path.join(tmpdir, "cli_snapshots")
    results_dir = os.path.join(tmpdir, "cli_results")

    try:
        gen_script = os.path.join(os.path.dirname(__file__), "generate_test_data.py")
        ret = run_command(
            f"python {gen_script} --output-dir {test_data_dir} "
            f"--n-snapshots 3 --n-halos 2 --n-particles 60 --seed 123"
        )
        assert ret == 0, "Test data generation failed"

        cli_script = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "python", "halo_analysis", "cli.py"
        )

        ret = run_command(
            f"python {cli_script} info"
        )
        assert ret == 0, "CLI info command failed"
        print("  [OK] CLI info command works")

        input_pattern = os.path.join(test_data_dir, "*.dat")
        ret = run_command(
            f"python {cli_script} run --input \"{input_pattern}\" "
            f"--output {results_dir} --print-stats --min-particles 10 "
            f"--share-threshold 0.3 --verbose"
        )
        assert ret == 0, "CLI run command failed"
        print("  [OK] CLI run command works")

        catalog_file = os.path.join(results_dir, "halo_catalog.json")
        assert os.path.exists(catalog_file), "Catalog not generated by CLI"
        print("  [OK] CLI generated catalog")

        with open(catalog_file, 'r') as f:
            catalog = json.load(f)
        assert len(catalog['halos']) > 0, "No halos in catalog"
        print(f"  [OK] CLI found {len(catalog['halos'])} halos")

        return True

    except Exception as e:
        print(f"  [FAIL] CLI test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "#"*60)
    print("# HALO ANALYSIS PIPELINE - END-TO-END TEST")
    print("#"*60)

    tmpdir = tempfile.mkdtemp(prefix="halo_test_")
    print(f"\nWorking in temporary directory: {tmpdir}")

    try:
        all_passed = True

        all_passed &= test_imports()
        all_passed &= test_core_functions()
        all_passed &= test_full_pipeline(tmpdir)
        all_passed &= test_cli(tmpdir)

        print("\n" + "="*60)
        if all_passed:
            print("[OK] ALL TESTS PASSED")
        else:
            print("[FAIL] SOME TESTS FAILED")
        print("="*60)

        return 0 if all_passed else 1

    finally:
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)


if __name__ == '__main__':
    sys.exit(main())
