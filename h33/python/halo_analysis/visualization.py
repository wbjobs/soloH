import numpy as np
import os
from typing import List, Tuple, Dict, Optional, Set
from collections import defaultdict

try:
    import graphviz
    GRAPHVIZ_AVAILABLE = True
except ImportError:
    GRAPHVIZ_AVAILABLE = False

try:
    import pydot
    PYDOT_AVAILABLE = True
except ImportError:
    PYDOT_AVAILABLE = False

from .core import Halo, Snapshot, MergerTreeBuilder, MergerTreeNode
from .analysis import (
    compute_mass_function,
    compute_spin_parameter_distribution,
    compute_formation_redshift_distribution,
    compute_subhalo_mass_function,
)

def save_merger_tree_graphviz(builder: MergerTreeBuilder, output_file: str,
                               halo_id: Optional[int] = None,
                               mass_range: Optional[Tuple[float, float]] = None,
                               redshift_range: Optional[Tuple[float, float]] = None,
                               format: str = 'pdf',
                               show_subhalos: bool = True):
    if not GRAPHVIZ_AVAILABLE:
        print("Warning: graphviz not available. Install with 'pip install graphviz'")
        return False

    nodes = builder.get_nodes()
    halo_to_node = builder.get_halo_to_node()

    if halo_id is not None:
        relevant_ids = set()
        if halo_id in halo_to_node:
            progenitor_chain = builder.get_progenitor_chain(halo_id)
            descendant_chain = builder.get_descendant_chain(halo_id)
            relevant_ids.update(progenitor_chain)
            relevant_ids.update(descendant_chain)
        filtered_nodes = [n for n in nodes if n.halo_id in relevant_ids]
    else:
        filtered_nodes = nodes
        if mass_range:
            filtered_nodes = [n for n in filtered_nodes
                             if mass_range[0] <= n.mass <= mass_range[1]]
        if redshift_range:
            filtered_nodes = [n for n in filtered_nodes
                             if redshift_range[0] <= n.redshift <= redshift_range[1]]

    if not filtered_nodes:
        print("No halos match the filter criteria")
        return False

    dot = graphviz.Digraph(comment='Halo Merger Tree', format=format)
    dot.attr(rankdir='LR', size='16,10')
    dot.attr('node', shape='box', style='filled', fontsize='10')

    max_mass = max(n.mass for n in filtered_nodes) if filtered_nodes else 1.0

    snap_groups = defaultdict(list)
    for node in filtered_nodes:
        snap_groups[node.snapshot_index].append(node)

    node_ids = {n.halo_id for n in filtered_nodes}

    for snap_idx in sorted(snap_groups.keys()):
        with dot.subgraph(name=f'cluster_{snap_idx}') as sub:
            sub.attr(style='dashed', color='gray')
            sub.attr(label=f'Snapshot {snap_idx} (z={snap_groups[snap_idx][0].redshift:.2f})')
            for node in snap_groups[snap_idx]:
                mass_ratio = node.mass / max_mass
                intensity = int(255 * (1.0 - mass_ratio * 0.7))
                color = f'#{intensity:02x}{intensity:02x}ff'
                width = 0.5 + mass_ratio * 2.0

                label = (
                    f'ID: {node.halo_id}\n'
                    f'M: {node.mass:.2e}\n'
                    f'z: {node.redshift:.2f}\n'
                    f'N_p: {node.num_particles}\n'
                    f'λ: {node.spin_parameter:.3f}\n'
                    f'z_form: {node.formation_redshift:.2f}'
                )

                sub.node(
                    str(node.halo_id),
                    label=label,
                    fillcolor=color,
                    width=str(width),
                    height=str(width * 0.6),
                )

    for node in filtered_nodes:
        if node.descendant_id != 0 and node.descendant_id in node_ids:
            dot.edge(
                str(node.halo_id),
                str(node.descendant_id),
                color='#3366cc',
                penwidth='2',
                arrowhead='vee',
            )

    if show_subhalos:
        for node in filtered_nodes:
            for sub_id in node.subhalo_ids:
                if sub_id in node_ids:
                    dot.edge(
                        str(sub_id),
                        str(node.halo_id),
                        style='dashed',
                        color='#ff6633',
                        penwidth='1.5',
                        arrowhead='dot',
                    )

    try:
        base, ext = os.path.splitext(output_file)
        if ext:
            output_file = base
        dot.render(output_file, cleanup=True)
        return True
    except Exception as e:
        print(f"Error rendering merger tree: {e}")
        return False

def plot_mass_function(halos: List[Halo], box_size: float,
                        output_file: Optional[str] = None,
                        n_bins: int = 20,
                        log_mass_range: Optional[Tuple[float, float]] = None,
                        use_adaptive_binning: bool = True,
                        show_errors: bool = True,
                        apply_smoothing: bool = False):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("Warning: matplotlib not available. Install with 'pip install matplotlib'")
        return None

    result = compute_mass_function(halos, box_size, n_bins, log_mass_range,
                                   use_adaptive_binning=use_adaptive_binning,
                                   apply_smoothing=apply_smoothing)
    bin_centers, mass_func, counts, errors = result

    if len(bin_centers) == 0:
        return None

    fig, ax = plt.subplots(figsize=(10, 7))

    if show_errors and len(errors) == len(bin_centers):
        ax.errorbar(bin_centers, mass_func, yerr=errors,
                    fmt='bo-', markersize=6, linewidth=2,
                    capsize=4, elinewidth=1.5, alpha=0.8)
    else:
        ax.loglog(bin_centers, mass_func, 'bo-', markersize=6, linewidth=2)

    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel(r'Halo Mass $M_\odot$', fontsize=14)
    ax.set_ylabel(r'dN/dlogM $h^3$ Mpc$^{-3}$', fontsize=14)

    title = 'Halo Mass Function'
    if use_adaptive_binning:
        title += ' (Adaptive Binning)'
    if apply_smoothing:
        title += ' (Smoothed)'
    ax.set_title(title, fontsize=16)

    ax.grid(True, alpha=0.3, which='both')
    ax.tick_params(axis='both', labelsize=12)

    bin_widths = np.diff(np.log10(bin_centers))
    min_width = np.min(bin_widths) if len(bin_widths) > 0 else 0
    if min_width > 0 and use_adaptive_binning:
        ax.text(0.02, 0.98, f'Min bin width: {min_width:.2f} dex',
                transform=ax.transAxes, va='top', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        return output_file
    else:
        return fig

def plot_spin_distribution(halos: List[Halo],
                            output_file: Optional[str] = None,
                            n_bins: int = 20):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("Warning: matplotlib not available. Install with 'pip install matplotlib'")
        return None

    bin_centers, counts, spins = compute_spin_parameter_distribution(halos, n_bins)

    if len(spins) == 0:
        return None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    ax1.hist(spins, bins=30, density=True, alpha=0.7, color='green', edgecolor='black')
    ax1.set_xlabel('Spin Parameter λ', fontsize=12)
    ax1.set_ylabel('Probability Density', fontsize=12)
    ax1.set_title('Spin Parameter Distribution', fontsize=14)
    ax1.axvline(np.mean(spins), color='red', linestyle='--', linewidth=2,
                label=f'Mean = {np.mean(spins):.3f}')
    ax1.axvline(np.median(spins), color='blue', linestyle='--', linewidth=2,
                label=f'Median = {np.median(spins):.3f}')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.loglog(bin_centers, counts, 'rs-', markersize=6)
    ax2.set_xlabel('Spin Parameter λ', fontsize=12)
    ax2.set_ylabel('Count', fontsize=12)
    ax2.set_title('Binned Spin Distribution', fontsize=14)
    ax2.grid(True, alpha=0.3, which='both')

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        return output_file
    else:
        return fig

def plot_formation_redshift_distribution(halos: List[Halo],
                                          output_file: Optional[str] = None,
                                          n_bins: int = 20):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("Warning: matplotlib not available. Install with 'pip install matplotlib'")
        return None

    bin_centers, counts = compute_formation_redshift_distribution(halos, n_bins)

    if len(bin_centers) == 0:
        return None

    redshifts = np.array([h.formation_redshift for h in halos])

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.hist(redshifts, bins=n_bins, alpha=0.7, color='purple', edgecolor='black')
    ax.set_xlabel('Formation Redshift z_form', fontsize=14)
    ax.set_ylabel('Number of Halos', fontsize=14)
    ax.set_title('Halo Formation Redshift Distribution', fontsize=16)
    ax.axvline(np.mean(redshifts), color='red', linestyle='--', linewidth=2,
               label=f'Mean = {np.mean(redshifts):.2f}')
    ax.axvline(np.median(redshifts), color='blue', linestyle='--', linewidth=2,
               label=f'Median = {np.median(redshifts):.2f}')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='both', labelsize=12)

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        return output_file
    else:
        return fig

def plot_merger_tree(halo_id: int, builder: MergerTreeBuilder,
                      snapshots: List[Snapshot],
                      output_file: Optional[str] = None,
                      format: str = 'png',
                      show_subhalos: bool = True):
    return save_merger_tree_graphviz(builder, output_file, halo_id=halo_id,
                                     format=format, show_subhalos=show_subhalos)

def create_summary_plots(snapshots: List[Snapshot], output_dir: str,
                          mass_range: Optional[Tuple[float, float]] = None,
                          redshift_range: Optional[Tuple[float, float]] = None,
                          use_adaptive_binning: bool = True,
                          apply_smoothing: bool = False):
    os.makedirs(output_dir, exist_ok=True)

    all_halos = []
    for snap in snapshots:
        halos = snap.halos
        if mass_range:
            halos = [h for h in halos if mass_range[0] <= h.mass <= mass_range[1]]
        if redshift_range:
            halos = [h for h in halos if redshift_range[0] <= h.redshift <= redshift_range[1]]
        all_halos.extend(halos)

    if not all_halos:
        print("No halos match the filter criteria")
        return {}

    box_size = snapshots[0].box_size

    output_files = {}

    mf_file = os.path.join(output_dir, 'mass_function.png')
    result = plot_mass_function(all_halos, box_size, mf_file,
                                use_adaptive_binning=use_adaptive_binning,
                                apply_smoothing=apply_smoothing)
    if result:
        output_files['mass_function'] = mf_file

    spin_file = os.path.join(output_dir, 'spin_distribution.png')
    result = plot_spin_distribution(all_halos, spin_file)
    if result:
        output_files['spin_distribution'] = spin_file

    zform_file = os.path.join(output_dir, 'formation_redshift.png')
    result = plot_formation_redshift_distribution(all_halos, zform_file)
    if result:
        output_files['formation_redshift'] = zform_file

    return output_files
