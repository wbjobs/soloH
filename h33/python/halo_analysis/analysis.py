import numpy as np
import json
import os
from typing import List, Tuple, Dict, Optional, Any
from collections import defaultdict

from .core import Halo, Snapshot, MergerTreeBuilder, MergerTreeNode

def compute_mass_function_adaptive(halos: List[Halo], box_size: float,
                                    min_count_per_bin: int = 10,
                                    log_mass_range: Optional[Tuple[float, float]] = None,
                                    min_bin_width_dex: float = 0.05,
                                    max_bin_width_dex: float = 0.5) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if not halos:
        return np.array([]), np.array([]), np.array([]), np.array([])

    masses = np.array([h.mass for h in halos if h.mass > 0])
    if len(masses) == 0:
        return np.array([]), np.array([]), np.array([]), np.array([])

    masses_sorted = np.sort(masses)
    log_masses_sorted = np.log10(masses_sorted)

    if log_mass_range is None:
        log_min = np.floor(log_masses_sorted.min())
        log_max = np.ceil(log_masses_sorted.max())
    else:
        log_min, log_max = log_mass_range

    mask = (log_masses_sorted >= log_min) & (log_masses_sorted <= log_max)
    masses_sorted = masses_sorted[mask]
    log_masses_sorted = log_masses_sorted[mask]

    if len(masses_sorted) < min_count_per_bin:
        return np.array([]), np.array([]), np.array([]), np.array([])

    bin_edges = [log_min]
    bin_counts = []
    current_idx = 0

    while current_idx < len(log_masses_sorted):
        target_idx = current_idx + min_count_per_bin
        if target_idx >= len(log_masses_sorted):
            next_edge = log_max
        else:
            next_edge = log_masses_sorted[target_idx]

        current_edge = bin_edges[-1]
        width = next_edge - current_edge

        if width < min_bin_width_dex:
            next_edge = current_edge + min_bin_width_dex
        elif width > max_bin_width_dex:
            next_edge = current_edge + max_bin_width_dex

        if next_edge > log_max:
            next_edge = log_max

        count = np.sum((log_masses_sorted >= current_edge) & (log_masses_sorted < next_edge))
        if count == 0 and next_edge < log_max:
            next_edge = min(current_edge + max_bin_width_dex, log_max)
            count = np.sum((log_masses_sorted >= current_edge) & (log_masses_sorted < next_edge))

        bin_edges.append(next_edge)
        bin_counts.append(count)

        while current_idx < len(log_masses_sorted) and log_masses_sorted[current_idx] < next_edge:
            current_idx += 1

        if next_edge >= log_max:
            break

    bin_edges = np.array(bin_edges)
    bin_counts = np.array(bin_counts)

    if bin_counts[-1] < min_count_per_bin and len(bin_counts) > 1:
        bin_counts[-2] += bin_counts[-1]
        bin_counts = bin_counts[:-1]
        bin_edges = bin_edges[:-1]

    bin_edges_lin = 10 ** bin_edges
    bin_centers = np.sqrt(bin_edges_lin[:-1] * bin_edges_lin[1:])

    volume = box_size ** 3
    dlogM = np.diff(bin_edges)
    mass_function = bin_counts / (volume * dlogM)

    poisson_error = np.sqrt(bin_counts) / (volume * dlogM)

    return bin_centers, mass_function, bin_counts, poisson_error


def compute_mass_function(halos: List[Halo], box_size: float,
                          n_bins: int = 20, log_mass_range: Optional[Tuple[float, float]] = None,
                          use_adaptive_binning: bool = True,
                          min_count_per_bin: int = 10,
                          apply_smoothing: bool = False,
                          smooth_sigma: float = 1.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if not halos:
        return np.array([]), np.array([]), np.array([]), np.array([])

    if use_adaptive_binning:
        bin_centers, mass_func, counts, errors = compute_mass_function_adaptive(
            halos, box_size, min_count_per_bin, log_mass_range
        )
    else:
        masses = np.array([h.mass for h in halos if h.mass > 0])
        if len(masses) == 0:
            return np.array([]), np.array([]), np.array([]), np.array([])

        log_masses = np.log10(masses)
        if log_mass_range is None:
            log_min = np.floor(log_masses.min())
            log_max = np.ceil(log_masses.max())
        else:
            log_min, log_max = log_mass_range

        bins = np.logspace(log_min, log_max, n_bins + 1)
        bin_centers = np.sqrt(bins[:-1] * bins[1:])
        counts, _ = np.histogram(masses, bins=bins)

        volume = box_size ** 3
        dlogM = np.diff(np.log10(bins))
        mass_func = counts / (volume * dlogM)
        errors = np.sqrt(counts) / (volume * dlogM)

    if apply_smoothing and len(mass_func) >= 3:
        log_centers = np.log10(bin_centers)
        smoothed = np.zeros_like(mass_func)

        for i in range(len(mass_func)):
            distances = (log_centers - log_centers[i]) ** 2
            weights = np.exp(-distances / (2 * smooth_sigma ** 2))
            weights /= weights.sum()
            smoothed[i] = np.sum(weights * mass_func)

        mass_func = smoothed

    return bin_centers, mass_func, counts, errors

def compute_subhalo_mass_function(halos: List[Halo], all_halos: List[Halo],
                                   n_bins: int = 15,
                                   use_adaptive_binning: bool = True,
                                   min_count_per_bin: int = 5) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    subhalo_masses = []
    id_to_halo = {h.halo_id: h for h in all_halos}

    for halo in halos:
        for sub_id in halo.subhalo_ids:
            if sub_id in id_to_halo:
                subhalo_masses.append(id_to_halo[sub_id].mass)

    if not subhalo_masses:
        return np.array([]), np.array([]), np.array([])

    masses = np.array(subhalo_masses)

    if use_adaptive_binning and len(masses) >= min_count_per_bin:
        masses_sorted = np.sort(masses)
        log_masses_sorted = np.log10(masses_sorted)
        log_min = np.floor(log_masses_sorted.min())
        log_max = np.ceil(log_masses_sorted.max())

        bin_edges = [log_min]
        bin_counts = []
        current_idx = 0

        while current_idx < len(log_masses_sorted):
            target_idx = current_idx + min_count_per_bin
            if target_idx >= len(log_masses_sorted):
                next_edge = log_max
            else:
                next_edge = log_masses_sorted[target_idx]

            current_edge = bin_edges[-1]
            width = next_edge - current_edge

            if width < 0.05:
                next_edge = current_edge + 0.05
            elif width > 0.5:
                next_edge = current_edge + 0.5

            if next_edge > log_max:
                next_edge = log_max

            count = np.sum((log_masses_sorted >= current_edge) & (log_masses_sorted < next_edge))
            bin_edges.append(next_edge)
            bin_counts.append(count)

            while current_idx < len(log_masses_sorted) and log_masses_sorted[current_idx] < next_edge:
                current_idx += 1

            if next_edge >= log_max:
                break

        bin_edges = np.array(bin_edges)
        bin_counts = np.array(bin_counts)

        if bin_counts[-1] < min_count_per_bin and len(bin_counts) > 1:
            bin_counts[-2] += bin_counts[-1]
            bin_counts = bin_counts[:-1]
            bin_edges = bin_edges[:-1]

        bin_edges_lin = 10 ** bin_edges
        bin_centers = np.sqrt(bin_edges_lin[:-1] * bin_edges_lin[1:])
        errors = np.sqrt(bin_counts)
    else:
        log_masses = np.log10(masses)
        log_min = np.floor(log_masses.min())
        log_max = np.ceil(log_masses.max())

        bins = np.logspace(log_min, log_max, n_bins + 1)
        bin_centers = np.sqrt(bins[:-1] * bins[1:])
        bin_counts, _ = np.histogram(masses, bins=bins)
        errors = np.sqrt(bin_counts)

    return bin_centers, bin_counts, errors

def compute_spin_parameter_distribution(halos: List[Halo],
                                         n_bins: int = 20) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    spins = np.array([h.spin_parameter for h in halos if h.spin_parameter > 0])
    if len(spins) == 0:
        return np.array([]), np.array([]), np.array([])

    log_spins = np.log10(spins)
    bins = np.logspace(log_spins.min(), log_spins.max(), n_bins + 1)
    bin_centers = np.sqrt(bins[:-1] * bins[1:])
    counts, _ = np.histogram(spins, bins=bins)

    return bin_centers, counts, spins

def compute_formation_redshift_distribution(halos: List[Halo],
                                             n_bins: int = 20) -> Tuple[np.ndarray, np.ndarray]:
    redshifts = np.array([h.formation_redshift for h in halos])
    if len(redshifts) == 0:
        return np.array([]), np.array([])

    bins = np.linspace(redshifts.min(), redshifts.max(), n_bins + 1)
    bin_centers = 0.5 * (bins[:-1] + bins[1:])
    counts, _ = np.histogram(redshifts, bins=bins)

    return bin_centers, counts

def filter_halos_by_mass(halos: List[Halo], min_mass: float, max_mass: float) -> List[Halo]:
    return [h for h in halos if min_mass <= h.mass <= max_mass]

def filter_halos_by_redshift(halos: List[Halo], min_z: float, max_z: float) -> List[Halo]:
    return [h for h in halos if min_z <= h.redshift <= max_z]

def get_merger_history(halo_id: int, builder: MergerTreeBuilder,
                        snapshots: List[Snapshot]) -> Dict[str, Any]:
    halo_map = {}
    for snap in snapshots:
        for halo in snap.halos:
            halo_map[halo.halo_id] = halo

    if halo_id not in halo_map and halo_id not in builder.get_halo_to_node():
        id_mapping = builder.get_halo_id_mapping()
        for old_id, new_id in id_mapping.items():
            if new_id == halo_id:
                halo_id = new_id
                break

    progenitor_chain = builder.get_progenitor_chain(halo_id)
    descendant_chain = builder.get_descendant_chain(halo_id)

    history = {
        'halo_id': halo_id,
        'progenitor_chain': [],
        'descendant_chain': [],
        'merger_events': [],
    }

    for hid in progenitor_chain:
        if hid in halo_map:
            h = halo_map[hid]
            history['progenitor_chain'].append({
                'halo_id': h.halo_id,
                'snapshot': h.snapshot_index,
                'redshift': h.redshift,
                'mass': h.mass,
                'num_progenitors': len(h.progenitor_ids),
            })

    for hid in descendant_chain:
        if hid in halo_map:
            h = halo_map[hid]
            history['descendant_chain'].append({
                'halo_id': h.halo_id,
                'snapshot': h.snapshot_index,
                'redshift': h.redshift,
                'mass': h.mass,
            })

    for hid in progenitor_chain:
        if hid in halo_map:
            h = halo_map[hid]
            if len(h.progenitor_ids) > 1:
                history['merger_events'].append({
                    'snapshot': h.snapshot_index,
                    'redshift': h.redshift,
                    'descendant_mass': h.mass,
                    'progenitor_masses': [halo_map[pid].mass for pid in h.progenitor_ids if pid in halo_map],
                    'progenitor_ids': h.progenitor_ids,
                })

    if halo_id in halo_map:
        h = halo_map[halo_id]
        history['formation_redshift'] = h.formation_redshift
        history['spin_parameter'] = h.spin_parameter
        history['current_mass'] = h.mass
        history['subhalos'] = h.subhalo_ids

    return history

def save_halo_catalog(snapshots: List[Snapshot], builder: Optional[MergerTreeBuilder],
                       output_file: str, mass_range: Optional[Tuple[float, float]] = None,
                       redshift_range: Optional[Tuple[float, float]] = None):
    all_halos = []
    for snap in snapshots:
        halos = snap.halos
        if mass_range:
            halos = filter_halos_by_mass(halos, mass_range[0], mass_range[1])
        if redshift_range:
            halos = filter_halos_by_redshift(halos, redshift_range[0], redshift_range[1])

        for halo in halos:
            halo_data = {
                'halo_id': halo.halo_id,
                'snapshot_index': halo.snapshot_index,
                'redshift': halo.redshift,
                'mass': halo.mass,
                'num_particles': len(halo.particle_ids),
                'center_of_mass': list(halo.center_of_mass),
                'mean_velocity': list(halo.mean_velocity),
                'velocity_dispersion': list(halo.velocity_dispersion),
                'spin_parameter': halo.spin_parameter,
                'formation_redshift': halo.formation_redshift,
                'descendant_id': halo.descendant_id,
                'progenitor_ids': halo.progenitor_ids,
                'subhalo_ids': halo.subhalo_ids,
            }
            all_halos.append(halo_data)

    output_data = {
        'metadata': {
            'num_snapshots': len(snapshots),
            'num_halos': len(all_halos),
            'mass_range': mass_range,
            'redshift_range': redshift_range,
        },
        'snapshots': [
            {
                'index': s.index,
                'redshift': s.redshift,
                'scale_factor': s.scale_factor,
                'box_size': s.box_size,
                'num_particles': s.particles.size(),
            }
            for s in snapshots
        ],
        'halos': all_halos,
    }

    if builder is not None:
        output_data['merger_tree'] = {
            'num_nodes': len(builder.get_nodes()),
            'particle_share_threshold': builder.get_particle_share_threshold(),
        }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

def load_halo_catalog(input_file: str) -> Dict[str, Any]:
    with open(input_file, 'r') as f:
        return json.load(f)

def save_merger_history(history: Dict[str, Any], output_file: str):
    with open(output_file, 'w') as f:
        json.dump(history, f, indent=2)
