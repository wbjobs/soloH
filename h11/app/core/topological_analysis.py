import numpy as np
from scipy.sparse import csr_matrix
from scipy.linalg import eig, sqrtm, logm
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TopologicalResult:
    zak_phases: np.ndarray
    wilson_loop_eigenvalues: np.ndarray
    topological_invariants: np.ndarray
    band_topology: List[str]
    chern_numbers: Optional[np.ndarray] = None


def compute_zak_phase(eigenvectors: np.ndarray, k_points: np.ndarray,
                       boundary_info: Dict, unit_cell_size: Tuple[float, float],
                       band_index: int) -> float:
    n_k = len(k_points)
    n_dof = eigenvectors[0].shape[0] if eigenvectors[0] is not None else 0

    if n_dof == 0:
        return 0.0

    lx, ly = unit_cell_size

    u_k = np.zeros((n_k, n_dof), dtype=complex)
    for i, evec in enumerate(eigenvectors):
        if evec is not None and evec.shape[1] > band_index:
            u_k[i, :] = evec[:, band_index] / np.linalg.norm(evec[:, band_index])

    U = 1.0 + 0.0j
    for i in range(n_k - 1):
        overlap = np.conj(u_k[i, :]) @ u_k[i + 1, :]
        if np.abs(overlap) > 1e-10:
            U *= overlap / np.abs(overlap)

    final_overlap = np.conj(u_k[-1, :]) @ u_k[0, :]
    if np.abs(final_overlap) > 1e-10:
        U *= final_overlap / np.abs(final_overlap)

    gamma = np.imag(np.log(U))

    if gamma > np.pi:
        gamma -= 2 * np.pi
    elif gamma < -np.pi:
        gamma += 2 * np.pi

    return float(gamma)


def compute_zak_phases_for_bands(band_structure: Dict, boundary_info: Dict,
                                  unit_cell_size: Tuple[float, float],
                                  n_bands: Optional[int] = None) -> np.ndarray:
    eigenvectors = band_structure['eigenvectors']
    k_points = band_structure['k_points']
    frequencies = band_structure['frequencies']

    if n_bands is None:
        n_bands = frequencies.shape[1]

    zak_phases = np.zeros(n_bands)

    for band in range(n_bands):
        valid_evecs = []
        for evec in eigenvectors:
            if evec is not None and evec.shape[1] > band:
                valid_evecs.append(evec)
            else:
                valid_evecs.append(None)

        if sum(1 for e in valid_evecs if e is not None) > len(k_points) // 2:
            zak_phases[band] = compute_zak_phase(
                valid_evecs, k_points, boundary_info, unit_cell_size, band
            )
        else:
            zak_phases[band] = np.nan

    return zak_phases


def construct_wilson_loop_operator(eigenvectors: List[np.ndarray],
                                    k_loop: np.ndarray,
                                    band_indices: List[int]) -> np.ndarray:
    n_bands = len(band_indices)
    n_k = len(k_loop)

    overlaps = []

    for i in range(n_k - 1):
        evec_i = eigenvectors[i]
        evec_j = eigenvectors[i + 1]

        if evec_i is None or evec_j is None:
            overlaps.append(np.eye(n_bands, dtype=complex))
            continue

        U_i = evec_i[:, band_indices]
        U_j = evec_j[:, band_indices]

        overlap = U_i.conj().T @ U_j

        q, r = np.linalg.qr(overlap)
        overlap = q @ np.diag(np.sign(np.diag(r)))

        overlaps.append(overlap)

    evec_last = eigenvectors[-1]
    evec_first = eigenvectors[0]

    if evec_last is not None and evec_first is not None:
        U_last = evec_last[:, band_indices]
        U_first = evec_first[:, band_indices]
        overlap_last = U_last.conj().T @ U_first
        q, r = np.linalg.qr(overlap_last)
        overlap_last = q @ np.diag(np.sign(np.diag(r)))
        overlaps.append(overlap_last)
    else:
        overlaps.append(np.eye(n_bands, dtype=complex))

    W = np.eye(n_bands, dtype=complex)
    for overlap in overlaps:
        W = W @ overlap

    return W


def compute_wilson_loop_spectrum(band_structure: Dict, brillouin_zone: Dict,
                                  band_subset: List[int],
                                  n_phi: int = 20) -> Dict:
    eigenvectors = band_structure['eigenvectors']
    k_points_all = band_structure['k_points']

    n_bands_subset = len(band_subset)
    phi_values = np.linspace(0, 2 * np.pi, n_phi, endpoint=False)

    wilson_eigenvalues = np.zeros((n_phi, n_bands_subset), dtype=complex)

    high_sym = brillouin_zone['high_symmetry_points']
    Gamma = high_sym.get('Gamma', np.array([0, 0]))
    X = high_sym.get('X', np.array([np.pi, 0]))
    M = high_sym.get('M', np.array([np.pi, np.pi]))

    base_k = np.linspace(Gamma, X, len(eigenvectors) // 3, endpoint=True)

    for ip, phi in enumerate(phi_values):
        k_loop = []
        for k in base_k:
            k_rotated = np.array([
                k[0] * np.cos(phi) - k[1] * np.sin(phi),
                k[0] * np.sin(phi) + k[1] * np.cos(phi)
            ])
            k_loop.append(k_rotated)
        k_loop = np.array(k_loop)

        evecs_subset = []
        for k in k_loop:
            min_dist = 1e10
            min_idx = 0
            for i, kk in enumerate(k_points_all):
                dist = np.linalg.norm(k - kk)
                if dist < min_dist:
                    min_dist = dist
                    min_idx = i
            evecs_subset.append(eigenvectors[min_idx] if min_idx < len(eigenvectors) else None)

        try:
            W = construct_wilson_loop_operator(evecs_subset, k_loop, band_subset)
            eigvals = np.linalg.eigvals(W)
            eigvals = eigvals / np.abs(eigvals)
            wilson_eigenvalues[ip, :] = np.sort(eigvals)
        except Exception as e:
            wilson_eigenvalues[ip, :] = np.nan

    return {
        'phi_values': phi_values,
        'wilson_eigenvalues': wilson_eigenvalues,
        'band_subset': band_subset,
        'wilson_phases': np.angle(wilson_eigenvalues)
    }


def extract_topological_invariants(zak_phases: np.ndarray,
                                     wilson_spectrum: Optional[Dict] = None,
                                     threshold: float = np.pi / 2) -> Dict:
    n_bands = len(zak_phases)

    band_topology = []
    for gamma in zak_phases:
        if np.isnan(gamma):
            band_topology.append('unknown')
        elif abs(abs(gamma) - np.pi) < threshold:
            band_topology.append('topological')
        elif abs(gamma) < threshold:
            band_topology.append('trivial')
        else:
            band_topology.append('hybrid')

    edge_state_predictions = []
    for i in range(n_bands - 1):
        if not np.isnan(zak_phases[i]) and not np.isnan(zak_phases[i + 1]):
            phase_diff = abs(zak_phases[i + 1] - zak_phases[i])
            if abs(phase_diff - np.pi) < threshold:
                edge_state_predictions.append({
                    'gap_index': i,
                    'prediction': 'gapless_edge_states',
                    'zak_phase_jump': float(phase_diff)
                })

    wilson_winding = None
    if wilson_spectrum is not None and 'wilson_phases' in wilson_spectrum:
        phases = wilson_spectrum['wilson_phases']
        if len(phases) > 0:
            unwrapped = np.unwrap(phases, axis=0)
            if unwrapped.shape[1] > 0:
                total_change = unwrapped[-1, :] - unwrapped[0, :]
                wilson_winding = total_change / (2 * np.pi)

    chern_numbers = None
    if wilson_winding is not None:
        chern_numbers = np.round(np.real(wilson_winding)).astype(int)

    return {
        'zak_phases': zak_phases.tolist(),
        'band_topology': band_topology,
        'edge_state_predictions': edge_state_predictions,
        'wilson_winding_numbers': wilson_winding.tolist() if wilson_winding is not None else None,
        'chern_numbers': chern_numbers.tolist() if chern_numbers is not None else None
    }


def compute_full_topological_analysis(band_structure: Dict,
                                       boundary_info: Dict,
                                       unit_cell_size: Tuple[float, float],
                                       brillouin_zone: Dict,
                                       compute_wilson: bool = True,
                                       n_phi: int = 15,
                                       max_bands: int = 10) -> Dict:
    frequencies = band_structure['frequencies']
    n_bands = min(frequencies.shape[1], max_bands)

    zak_phases = compute_zak_phases_for_bands(
        band_structure, boundary_info, unit_cell_size, n_bands
    )

    wilson_spectrum = None
    if compute_wilson and n_bands >= 2:
        band_subset = list(range(min(4, n_bands)))
        try:
            wilson_spectrum = compute_wilson_loop_spectrum(
                band_structure, brillouin_zone, band_subset, n_phi
            )
        except Exception as e:
            print(f"Wilson loop computation failed: {e}")

    topo_invariants = extract_topological_invariants(zak_phases, wilson_spectrum)

    result = {
        'zak_phases': zak_phases,
        'band_topology': topo_invariants['band_topology'],
        'edge_state_predictions': topo_invariants['edge_state_predictions'],
        'topological_gap_indices': [
            p['gap_index'] for p in topo_invariants['edge_state_predictions']
        ]
    }

    if wilson_spectrum is not None:
        result['wilson_loop'] = {
            'phi_values': wilson_spectrum['phi_values'].tolist(),
            'eigenvalues': wilson_spectrum['wilson_eigenvalues'].tolist(),
            'phases': wilson_spectrum['wilson_phases'].tolist(),
            'band_subset': wilson_spectrum['band_subset']
        }
        result['wilson_winding_numbers'] = topo_invariants['wilson_winding_numbers']
        result['chern_numbers'] = topo_invariants['chern_numbers']

    return result


def compute_bott_index(eigenvectors: List[np.ndarray],
                       kx_line: np.ndarray, ky_value: float,
                       band_indices: List[int]) -> float:
    n_k = len(kx_line)
    n_bands = len(band_indices)

    evecs_at_ky = []
    for kx in kx_line:
        # In real usage, interpolate or find nearest k-point
        # Here we assume eigenvectors are pre-computed at these k-points
        evecs_at_ky.append(eigenvectors[0] if len(eigenvectors) > 0 else None)

    W = construct_wilson_loop_operator(evecs_at_ky, kx_line, band_indices)

    eigvals = np.linalg.eigvals(W)
    eigvals = eigvals / np.abs(eigvals)
    phases = np.angle(eigvals)

    bott_index = np.sum(phases) / (2 * np.pi)

    return float(np.real(bott_index))
