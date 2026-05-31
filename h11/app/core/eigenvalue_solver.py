import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import eigs
from typing import Dict, List, Tuple, Optional
import warnings


def solve_generalized_eigenproblem(K: csr_matrix, M: csr_matrix,
                                    n_eigenvalues: int = 20,
                                    sigma: Optional[complex] = None,
                                    handle_complex: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    n = K.shape[0]
    n_eigenvalues = min(n_eigenvalues, n - 2)

    if n_eigenvalues < 1:
        return np.array([]), np.array([])

    is_complex = np.iscomplexobj(K.data) or np.iscomplexobj(M.data) or handle_complex

    if sigma is None:
        sigma = 0.0 + 0.0j if is_complex else 0.0

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            eigenvalues, eigenvectors = eigs(
                K, M=M, k=n_eigenvalues, sigma=sigma,
                which='LM', maxiter=5000, tol=1e-6
            )
    except Exception as e:
        try:
            eigenvalues, eigenvectors = eigs(
                K, M=M, k=n_eigenvalues, which='SM',
                maxiter=5000, tol=1e-6
            )
        except Exception as e2:
            try:
                K_dense = K.todense()
                M_dense = M.todense()
                from scipy.linalg import eig as dense_eig
                eigenvalues, eigenvectors = dense_eig(
                    K_dense, M_dense, left=False, right=True
                )
                sort_idx = np.argsort(np.abs(eigenvalues))
                eigenvalues = eigenvalues[sort_idx[:n_eigenvalues]]
                eigenvectors = eigenvectors[:, sort_idx[:n_eigenvalues]]
            except Exception as e3:
                print(f"Eigenvalue solver failed: {e}, {e2}, {e3}")
                return np.array([]), np.array([])

    if is_complex:
        sort_idx = np.argsort(np.real(eigenvalues))
        eigenvalues = eigenvalues[sort_idx]
        eigenvectors = eigenvectors[:, sort_idx]

        omega_squared = eigenvalues
        omega = np.sqrt(omega_squared)
        frequencies = omega / (2 * np.pi)
    else:
        eigenvalues = np.real(eigenvalues)
        sort_idx = np.argsort(eigenvalues)
        eigenvalues = eigenvalues[sort_idx]
        eigenvectors = eigenvectors[:, sort_idx]

        eigenvalues = np.maximum(eigenvalues, 0)
        frequencies = np.sqrt(eigenvalues) / (2 * np.pi)

    return frequencies, eigenvectors


def solve_complex_eigenproblem(K: csr_matrix, M: csr_matrix,
                                n_eigenvalues: int = 20,
                                sigma: complex = 0.0) -> Tuple[np.ndarray, np.ndarray, Dict]:
    frequencies, eigenvectors = solve_generalized_eigenproblem(
        K, M, n_eigenvalues=n_eigenvalues, sigma=sigma, handle_complex=True
    )

    if len(frequencies) == 0:
        return np.array([]), np.array([])

    attenuation = -np.imag(frequencies) * 8.686  # Convert Np/m to dB/m
    phase_velocity = 2 * np.pi * np.real(frequencies)

    analysis = {
        'complex_frequencies': frequencies.tolist(),
        'real_frequencies': np.real(frequencies).tolist(),
        'imaginary_frequencies': np.imag(frequencies).tolist(),
        'attenuation_db_per_m': attenuation.tolist(),
        'phase_velocity': phase_velocity.tolist(),
        'quality_factors': np.abs(np.real(frequencies) / (2 * np.imag(frequencies))).tolist() if np.any(np.imag(frequencies) != 0) else None
    }

    return frequencies, eigenvectors, analysis


def solve_band_structure(K: csr_matrix, M: csr_matrix,
                          k_points: np.ndarray,
                          boundary_info: Dict,
                          unit_cell_size: Tuple[float, float],
                          wave_type: str = 'sh',
                          n_bands: int = 20,
                          has_loss: bool = False) -> Dict:
    from .fem_assembly import apply_bloch_boundary_conditions
    import warnings

    n_k = len(k_points)

    is_complex = has_loss or np.iscomplexobj(K.data) or np.iscomplexobj(M.data)

    if is_complex:
        frequencies = np.zeros((n_k, n_bands), dtype=complex)
    else:
        frequencies = np.zeros((n_k, n_bands))

    eigenvectors_list = []
    loss_analysis_list = []
    bloch_is_complex = False

    for i, k in enumerate(k_points):
        kx, ky = k[0], k[1]

        K_bloch, M_bloch, dof_mapping, node_map = apply_bloch_boundary_conditions(
            K, M, kx, ky, boundary_info, unit_cell_size, wave_type
        )

        if not bloch_is_complex and (np.iscomplexobj(K_bloch.data) or np.iscomplexobj(M_bloch.data)):
            bloch_is_complex = True
            if not is_complex:
                is_complex = True
                frequencies = frequencies.astype(complex)

        if K_bloch.shape[0] < 3:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                if is_complex:
                    frequencies[i, :] = complex(np.nan, np.nan)
                else:
                    frequencies[i, :] = np.nan
            eigenvectors_list.append(None)
            loss_analysis_list.append(None)
            continue

        if is_complex:
            freqs, evecs, analysis = solve_complex_eigenproblem(
                K_bloch, M_bloch, n_eigenvalues=n_bands
            )
            loss_analysis_list.append(analysis)
        else:
            freqs, evecs = solve_generalized_eigenproblem(
                K_bloch, M_bloch, n_eigenvalues=n_bands
            )
            loss_analysis_list.append(None)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if len(freqs) < n_bands:
                frequencies[i, :len(freqs)] = freqs
                if is_complex:
                    frequencies[i, len(freqs):] = complex(np.nan, np.nan)
                else:
                    frequencies[i, len(freqs):] = np.nan
            else:
                frequencies[i, :] = freqs[:n_bands]

        eigenvectors_list.append(evecs)

    result = {
        'k_points': k_points,
        'frequencies': frequencies,
        'eigenvectors': eigenvectors_list,
        'n_bands': n_bands,
        'wave_type': wave_type,
        'has_loss': is_complex
    }

    if is_complex:
        result['loss_analysis'] = loss_analysis_list
        result['real_frequencies'] = np.real(frequencies)
        result['attenuation'] = -np.imag(frequencies) * 8.686  # dB/m

    return result


def compute_group_velocity(band_structure: Dict,
                            brillouin_zone: Dict,
                            band_index: Optional[int] = None) -> np.ndarray:
    k_points = band_structure['k_points']
    frequencies = band_structure['frequencies']
    cumulative_dist = brillouin_zone['cumulative_dist']

    if np.iscomplexobj(frequencies):
        frequencies = np.real(frequencies)

    n_k, n_bands = frequencies.shape

    if band_index is not None:
        bands = [band_index]
    else:
        bands = range(n_bands)

    group_velocities = np.zeros((n_k, len(bands)))

    for j, band in enumerate(bands):
        freq_band = frequencies[:, band]

        valid = ~np.isnan(freq_band)
        if np.sum(valid) < 3:
            group_velocities[:, j] = np.nan
            continue

        v_g = np.gradient(freq_band, cumulative_dist) * 2 * np.pi

        group_velocities[:, j] = np.real(v_g)

    return group_velocities


def compute_dos(frequencies: np.ndarray,
                 frequency_range: Optional[Tuple[float, float]] = None,
                 n_bins: int = 100,
                 broadening: float = 0.01) -> Dict:
    all_freqs = frequencies.flatten()

    if np.iscomplexobj(all_freqs):
        all_freqs = np.real(all_freqs)

    all_freqs = all_freqs[~np.isnan(all_freqs)]

    if frequency_range is None:
        f_min = np.min(all_freqs) * 0.9 if len(all_freqs) > 0 else 0
        f_max = np.max(all_freqs) * 1.1 if len(all_freqs) > 0 else 1000
    else:
        f_min, f_max = frequency_range

    freq_axis = np.linspace(f_min, f_max, n_bins)
    dos = np.zeros(n_bins)

    if len(all_freqs) == 0:
        return {'frequencies': freq_axis, 'dos': dos}

    sigma = broadening * (f_max - f_min) if broadening < 1 else broadening

    for i, f in enumerate(freq_axis):
        dos[i] = np.sum(np.exp(-(all_freqs - f) ** 2 / (2 * sigma ** 2))) / (sigma * np.sqrt(2 * np.pi))

    dos /= len(all_freqs) / (f_max - f_min)

    return {
        'frequencies': freq_axis,
        'dos': dos,
        'n_states': len(all_freqs),
        'broadening': sigma
    }


def find_band_gaps(frequencies: np.ndarray,
                    threshold: float = 0.05) -> List[Tuple[float, float]]:
    if np.iscomplexobj(frequencies):
        frequencies = np.real(frequencies)

    n_k, n_bands = frequencies.shape

    band_gaps = []

    for i in range(n_bands - 1):
        max_lower = np.nanmax(frequencies[:, i])
        min_upper = np.nanmin(frequencies[:, i + 1])

        if not np.isnan(max_lower) and not np.isnan(min_upper):
            gap_size = min_upper - max_lower
            if gap_size > threshold * max_lower:
                band_gaps.append((float(max_lower), float(min_upper)))

    return band_gaps
