#!/usr/bin/env python3
"""Command-line interface for halo analysis pipeline."""

import argparse
import os
import sys
import glob
import json
from typing import List, Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import halo_analysis as ha
from halo_analysis.core import Snapshot
from halo_analysis.analysis import (
    save_halo_catalog,
    get_merger_history,
    save_merger_history,
    filter_halos_by_mass,
    filter_halos_by_redshift,
    compute_mass_function,
    compute_subhalo_mass_function,
)
from halo_analysis.visualization import (
    save_merger_tree_graphviz,
    create_summary_plots,
    plot_mass_function,
    plot_spin_distribution,
    plot_formation_redshift_distribution,
)


def find_snapshot_files(pattern: str) -> List[str]:
    files = sorted(glob.glob(pattern))
    return files


def read_snapshots(file_pattern: str, verbose: bool = False) -> List[Snapshot]:
    files = find_snapshot_files(file_pattern)
    if not files:
        print(f"Error: No files found matching pattern: {file_pattern}")
        return []

    if verbose:
        print(f"Found {len(files)} snapshot files")

    reader = ha.GadgetReader()
    snapshots = []

    for i, filename in enumerate(files):
        if verbose:
            print(f"Reading snapshot {i+1}/{len(files)}: {os.path.basename(filename)}")

        snap = Snapshot()
        success = reader.read(filename, snap, i)

        if success:
            snapshots.append(snap)
            if verbose:
                print(f"  Loaded {snap.particles.size()} particles, z={snap.redshift:.3f}")
        else:
            print(f"  Warning: Failed to read {filename}")

    return snapshots


def run_analysis(args):
    if args.verbose:
        print(f"Using {'C++ extension' if ha.CPP_AVAILABLE else 'Python/Numba'} implementation")

    snapshots = read_snapshots(args.input, args.verbose)
    if not snapshots:
        return 1

    if args.verbose:
        print(f"\nRunning Friends-of-Friends halo finder...")

    fof = ha.FoFFinder(
        link_length_ratio=args.link_length,
        min_particles=args.min_particles,
        compute_shape=not args.no_ellipsoidal_fit
    )

    for i, snap in enumerate(snapshots):
        if args.verbose:
            mean_spacing = ha.compute_mean_interparticle_spacing(snap.box_size, snap.particles.size())
            link_len = args.link_length * mean_spacing
            print(f"  Snapshot {i}: z={snap.redshift:.3f}, {snap.particles.size()} particles")
            print(f"    Mean spacing: {mean_spacing:.2f}, Link length: {link_len:.2f}")

        fof.find_halos(snap)

        if args.verbose:
            print(f"    Found {len(snap.halos)} halos")

    if args.verbose:
        print(f"\nBuilding merger trees...")

    builder = ha.MergerTreeBuilder(
        particle_share_threshold=args.share_threshold,
        subhalo_mass_ratio_threshold=args.subhalo_threshold
    )
    builder.build_trees(snapshots)

    if args.verbose:
        print(f"  Found {len(builder.get_nodes())} halos in merger tree")

    if args.verbose:
        print(f"Computing formation redshifts...")
    builder.compute_formation_redshifts(snapshots)

    if args.verbose:
        print(f"Identifying subhalos...")
    builder.identify_subhalos(snapshots)

    if args.find_substructures:
        if args.verbose:
            print(f"Finding substructures...")
        sub_finder = ha.SubstructureFinder(
            mass_ratio_threshold=args.substructure_mass_ratio,
            radius_threshold=args.substructure_radius_threshold
        )
        for snap in snapshots:
            sub_finder.find_substructures(snap)
            if args.bound_decomposition:
                for halo in snap.halos:
                    if halo.is_substructure:
                        sub_finder.decompose_halo_bound(halo, snap)
        if args.track_substructures:
            sub_finder.track_substructures(snapshots)
        if args.verbose:
            total_sub = sum(1 for s in snapshots for h in s.halos if h.is_substructure)
            print(f"  Found {total_sub} substructures")

    mass_range = None
    if args.min_mass is not None or args.max_mass is not None:
        mass_range = (
            args.min_mass if args.min_mass is not None else 0.0,
            args.max_mass if args.max_mass is not None else float('inf')
        )

    redshift_range = None
    if args.min_redshift is not None or args.max_redshift is not None:
        redshift_range = (
            args.min_redshift if args.min_redshift is not None else 0.0,
            args.max_redshift if args.max_redshift is not None else float('inf')
        )

    os.makedirs(args.output, exist_ok=True)

    if args.verbose:
        print(f"\nSaving halo catalog...")

    catalog_file = os.path.join(args.output, 'halo_catalog.json')
    save_halo_catalog(snapshots, builder, catalog_file, mass_range, redshift_range)
    if args.verbose:
        print(f"  Saved to {catalog_file}")

    if args.halo_id is not None:
        if args.verbose:
            print(f"\nAnalyzing merger history for halo {args.halo_id}...")

        history = get_merger_history(args.halo_id, builder, snapshots)
        history_file = os.path.join(args.output, f'merger_history_{args.halo_id}.json')
        save_merger_history(history, history_file)

        if args.verbose:
            print(f"  Formation redshift: {history.get('formation_redshift', 'N/A')}")
            print(f"  Spin parameter: {history.get('spin_parameter', 'N/A'):.4f}")
            print(f"  Current mass: {history.get('current_mass', 'N/A'):.2e}")
            print(f"  Number of mergers: {len(history.get('merger_events', []))}")
            print(f"  Saved to {history_file}")

    if args.compare_mg:
        if args.verbose:
            print(f"\nRunning modified gravity comparison...")
        mg_interface = ha.ModifiedGravityInterface()
        if args.f_R0 is not None:
            fr_params = ha.FR_Parameters(f_R0=args.f_R0, n=args.fr_n, name=f'F(R), fR0={args.f_R0}')
            mg_interface.register_model(ha.GravityModel.F_R, fr_params)

        all_halos = [h for s in snapshots for h in s.halos]
        box_size = snapshots[0].box_size
        stats_gr = mg_interface.compute_statistics(all_halos, box_size,
                                                    use_adaptive_binning=not args.fixed_binning,
                                                    min_count_per_bin=args.min_count_per_bin)

        fr_boost = []
        screened_count = 0
        for halo in all_halos:
            boost = mg_interface.compute_boost_factor(halo.mass, halo.redshift, fr_params)
            fr_boost.append(boost)
            if mg_interface.is_halo_chameleon_screened(halo, fr_params):
                screened_count += 1

        if args.verbose:
            print(f"  Mean boost factor: {sum(fr_boost)/len(fr_boost):.4f}")
            print(f"  Screened halos: {screened_count}/{len(all_halos)} ({100*screened_count/len(all_halos):.1f}%)")
            print(f"  Mean axis ratio (b/a): {stats_gr.axis_ratio_mean_b_a:.3f}")
            print(f"  Mean axis ratio (c/a): {stats_gr.axis_ratio_mean_c_a:.3f}")
            print(f"  Mean triaxiality: {stats_gr.triaxiality_mean:.3f}")

        mg_file = os.path.join(args.output, 'mg_comparison.json')
        with open(mg_file, 'w') as f:
            json.dump({
                'model': fr_params.name,
                'f_R0': fr_params.f_R0,
                'n': fr_params.n,
                'mean_boost': sum(fr_boost)/len(fr_boost),
                'screened_fraction': screened_count/len(all_halos),
                'stats_gr': {
                    'num_halos': stats_gr.num_halos,
                    'mass_mean': stats_gr.mass_mean,
                    'spin_mean': stats_gr.spin_mean,
                    'axis_ratio_mean_b_a': stats_gr.axis_ratio_mean_b_a,
                    'axis_ratio_mean_c_a': stats_gr.axis_ratio_mean_c_a,
                    'triaxiality_mean': stats_gr.triaxiality_mean,
                    'ellipticity_mean': stats_gr.ellipticity_mean,
                    'mass_bins': stats_gr.mass_bins.tolist(),
                    'mass_function': stats_gr.mass_function.tolist(),
                    'mass_function_errors': stats_gr.mass_function_errors.tolist(),
                },
                'boost_factors': fr_boost,
            }, f, indent=2, default=float)
        if args.verbose:
            print(f"  MG comparison saved to {mg_file}")

    if args.verbose:
        print(f"\nGenerating visualization...")

    if args.plot_merger_tree:
        tree_file = os.path.join(args.output, 'merger_tree')
        if args.halo_id is not None:
            tree_file = os.path.join(args.output, f'merger_tree_{args.halo_id}')

        success = save_merger_tree_graphviz(
            builder, tree_file,
            halo_id=args.halo_id,
            mass_range=mass_range,
            redshift_range=redshift_range,
            format=args.tree_format,
            show_subhalos=not args.no_subhalos
        )
        if success and args.verbose:
            print(f"  Merger tree saved to {tree_file}.{args.tree_format}")

    if args.plot_summary:
        if args.verbose:
            print("  Generating summary plots...")
        plot_dir = os.path.join(args.output, 'plots')
        plot_files = create_summary_plots(
            snapshots, plot_dir,
            mass_range=mass_range,
            redshift_range=redshift_range,
            use_adaptive_binning=not args.fixed_binning,
            apply_smoothing=args.smooth_mass_function
        )
        for name, fname in plot_files.items():
            if args.verbose:
                print(f"    {name}: {fname}")

    if args.print_stats:
        print_statistics(snapshots, builder, mass_range, redshift_range)

    if args.verbose:
        print(f"\nAnalysis complete. Results saved to {args.output}/")

    return 0


def print_statistics(snapshots: List[Snapshot], builder,
                     mass_range: Optional[Tuple[float, float]],
                     redshift_range: Optional[Tuple[float, float]]):
    print("\n" + "="*60)
    print("HALO STATISTICS")
    print("="*60)

    all_halos = []
    for snap in snapshots:
        halos = snap.halos
        if mass_range:
            halos = filter_halos_by_mass(halos, mass_range[0], mass_range[1])
        if redshift_range:
            halos = filter_halos_by_redshift(halos, redshift_range[0], redshift_range[1])
        all_halos.extend(halos)

    if not all_halos:
        print("No halos match filter criteria")
        return

    masses = [h.mass for h in all_halos]
    spins = [h.spin_parameter for h in all_halos if h.spin_parameter > 0]
    z_forms = [h.formation_redshift for h in all_halos]
    n_subhalos = sum(len(h.subhalo_ids) for h in all_halos)

    shapes = [h.shape for h in all_halos if h.shape.converged]
    substructures = [h for h in all_halos if h.is_substructure]

    print(f"Total halos: {len(all_halos)}")
    print(f"Mass range: {min(masses):.2e} - {max(masses):.2e} Msun")
    print(f"Mean mass: {sum(masses)/len(masses):.2e} Msun")
    print(f"Median mass: {sorted(masses)[len(masses)//2]:.2e} Msun")
    print()
    print(f"Spin parameter:")
    if spins:
        print(f"  Mean: {sum(spins)/len(spins):.4f}")
        print(f"  Median: {sorted(spins)[len(spins)//2]:.4f}")
    print()
    print(f"Formation redshift:")
    print(f"  Mean: {sum(z_forms)/len(z_forms):.2f}")
    print(f"  Median: {sorted(z_forms)[len(z_forms)//2]:.2f}")
    print(f"  Range: {min(z_forms):.2f} - {max(z_forms):.2f}")
    print()
    print(f"Subhalos: {n_subhalos} total")
    if substructures:
        print(f"Substructures: {len(substructures)} identified")
    print()
    if shapes:
        axis_b_a = [s.axis_ratio_b_a for s in shapes]
        axis_c_a = [s.axis_ratio_c_a for s in shapes]
        triax = [s.triaxiality for s in shapes]
        ellip = [s.ellipticity for s in shapes]
        print(f"Ellipsoidal shape ({len(shapes)} halos converged):")
        print(f"  Mean axis ratio b/a: {sum(axis_b_a)/len(axis_b_a):.3f}")
        print(f"  Mean axis ratio c/a: {sum(axis_c_a)/len(axis_c_a):.3f}")
        print(f"  Mean ellipticity: {sum(ellip)/len(ellip):.3f}")
        print(f"  Mean triaxiality: {sum(triax)/len(triax):.3f}")
        print()

    box_size = snapshots[0].box_size
    bin_centers, mass_func, counts, errors = compute_mass_function(all_halos, box_size)
    print("Mass function (dN/dlogM):")
    for i in range(min(5, len(bin_centers))):
        print(f"  logM={bin_centers[i]:.2e}: {mass_func[i]:.2e} ± {errors[i]:.2e} h^3/Mpc^3")

    print("\nSnapshots:")
    for snap in snapshots:
        print(f"  z={snap.redshift:.3f}: {len(snap.halos)} halos, {snap.particles.size()} particles")

    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Halo analysis pipeline for Gadget-2 simulations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic analysis of all snapshots
  python cli.py run --input "snapshots/snapshot_*.dat" --output results/

  # With filtering
  python cli.py run --input "snapshots/*" --output results/ \\
      --min-mass 1e12 --max-mass 1e15 --min-redshift 0 --max-redshift 5

  # Analyze specific halo and plot merger tree
  python cli.py run --input "snapshots/*" --output results/ \\
      --halo-id 12345 --plot-merger-tree --print-stats

  # Change FoF parameters
  python cli.py run --input "snapshots/*" --output results/ \\
      --link-length 0.2 --min-particles 30
        """
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    run_parser = subparsers.add_parser('run', help='Run full analysis pipeline')
    run_parser.add_argument('--input', '-i', required=True,
                           help='Glob pattern for Gadget-2 snapshot files')
    run_parser.add_argument('--output', '-o', default='halo_results',
                           help='Output directory for results')

    run_parser.add_argument('--link-length', type=float, default=0.2,
                           help='FoF link length as fraction of mean spacing (default: 0.2)')
    run_parser.add_argument('--min-particles', type=int, default=20,
                           help='Minimum particles per halo (default: 20)')
    run_parser.add_argument('--share-threshold', type=float, default=0.5,
                           help='Minimum particle share for merger linking (default: 0.5)')
    run_parser.add_argument('--subhalo-threshold', type=float, default=0.1,
                           help='Max mass ratio for subhalo identification (default: 0.1)')

    run_parser.add_argument('--min-mass', type=float, default=None,
                           help='Minimum halo mass for filtering (Msun)')
    run_parser.add_argument('--max-mass', type=float, default=None,
                           help='Maximum halo mass for filtering (Msun)')
    run_parser.add_argument('--min-redshift', type=float, default=None,
                           help='Minimum redshift for filtering')
    run_parser.add_argument('--max-redshift', type=float, default=None,
                           help='Maximum redshift for filtering')

    run_parser.add_argument('--halo-id', type=int, default=None,
                           help='Specific halo ID for detailed analysis')
    run_parser.add_argument('--plot-merger-tree', action='store_true',
                           help='Generate merger tree visualization')
    run_parser.add_argument('--tree-format', default='png',
                           choices=['png', 'pdf', 'svg', 'dot'],
                           help='Output format for merger tree (default: png)')
    run_parser.add_argument('--plot-summary', action='store_true',
                           help='Generate summary plots (mass function, etc.)')
    run_parser.add_argument('--no-subhalos', action='store_true',
                           help='Hide subhalo links in merger tree')
    run_parser.add_argument('--print-stats', action='store_true',
                           help='Print detailed statistics')
    run_parser.add_argument('--verbose', '-v', action='store_true',
                           help='Verbose output')
    run_parser.add_argument('--fixed-binning', action='store_true',
                           help='Use fixed-width binning for mass function (default: adaptive)')
    run_parser.add_argument('--smooth-mass-function', action='store_true',
                           help='Apply Gaussian smoothing to mass function')
    run_parser.add_argument('--min-count-per-bin', type=int, default=10,
                           help='Minimum halos per bin for adaptive binning (default: 10)')
    run_parser.add_argument('--consistent-ids', action='store_true', default=True,
                           help='Assign consistent halo IDs across snapshots (default: True)')
    run_parser.add_argument('--no-ellipsoidal-fit', action='store_true',
                           help='Disable ellipsoidal shape fitting (default: enabled)')
    run_parser.add_argument('--find-substructures', action='store_true',
                           help='Find substructures within halos')
    run_parser.add_argument('--track-substructures', action='store_true',
                           help='Track substructures across snapshots')
    run_parser.add_argument('--bound-decomposition', action='store_true',
                           help='Apply gravitational bound decomposition to substructures')
    run_parser.add_argument('--substructure-mass-ratio', type=float, default=0.1,
                           help='Max mass ratio for substructure identification (default: 0.1)')
    run_parser.add_argument('--substructure-radius-threshold', type=float, default=2.0,
                           help='Radius threshold in R_vir for substructure identification (default: 2.0)')
    run_parser.add_argument('--compare-mg', action='store_true',
                           help='Compare with modified gravity (F(R)) model predictions')
    run_parser.add_argument('--f_R0', type=float, default=1e-6,
                           help='Amplitude of f(R) modification at z=0 (default: 1e-6)')
    run_parser.add_argument('--fr-n', type=float, default=1.0,
                           help='Index of f(R) model (default: 1.0)')

    info_parser = subparsers.add_parser('info', help='Show information about the tool')

    args = parser.parse_args()

    if args.command == 'run':
        sys.exit(run_analysis(args))
    elif args.command == 'info':
        print("Halo Analysis Tool - C++ + Python Hybrid")
        print("="*50)
        print(f"C++ extension available: {ha.CPP_AVAILABLE}")
        print(f"Numba available: {ha.core.NUMBA_AVAILABLE}")
        print(f"Graphviz available: {ha.visualization.GRAPHVIZ_AVAILABLE}")
        print()
        print("Features:")
        print("  - Gadget-2 snapshot reader")
        print("  - Friends-of-Friends halo finder (link length = 0.2 * mean spacing)")
        print("  - Ellipsoidal shape fitting (inertia tensor, axis ratios, orientation)")
        print("  - Substructure finding and tracking")
        print("  - Gravitational bound particle decomposition")
        print("  - Merger tree building via particle sharing")
        print("  - Subhalo identification")
        print("  - Spin parameter calculation")
        print("  - Formation redshift tracking")
        print("  - Mass function computation (adaptive binning with Poisson errors)")
        print("  - Modified gravity (F(R)) comparison interface")
        print("  - Chameleon screening detection")
        print("  - Graphviz merger tree visualization")
        print("  - Mass and redshift range filtering")
        return 0

    return 0


if __name__ == '__main__':
    main()
