import numpy as np


def _extract_positive_ir(impulse_responses):
    if impulse_responses.ndim == 3:
        n_lags = impulse_responses.shape[2]
        max_lag = (n_lags - 1) // 2
        return impulse_responses[:, :, max_lag:]
    else:
        n_lags = impulse_responses.shape[1]
        max_lag = (n_lags - 1) // 2
        return impulse_responses[:, max_lag:]


def era_hankel_matrix(impulse_responses, block_rows, block_cols):
    positive_ir = _extract_positive_ir(impulse_responses)
    ndim = positive_ir.ndim
    if ndim == 3:
        n_channels = positive_ir.shape[0]
        n_positive = positive_ir.shape[2]
    else:
        n_channels = positive_ir.shape[0]
        n_positive = positive_ir.shape[1]

    if block_rows + block_cols > n_positive:
        block_rows = n_positive // 2
        block_cols = n_positive - block_rows
    block_rows = max(1, min(block_rows, n_positive - 1))
    block_cols = max(1, min(block_cols, n_positive - block_rows))

    if ndim == 3:
        H = np.zeros((n_channels * block_rows, n_channels * block_cols))
        H_shifted = np.zeros((n_channels * block_rows, n_channels * block_cols))
        for i in range(block_rows):
            for j in range(block_cols):
                k = i + j
                H[i * n_channels:(i + 1) * n_channels,
                  j * n_channels:(j + 1) * n_channels] = positive_ir[:, :, k]
                if k + 1 < n_positive:
                    H_shifted[i * n_channels:(i + 1) * n_channels,
                               j * n_channels:(j + 1) * n_channels] = positive_ir[:, :, k + 1]
    else:
        H = np.zeros((n_channels * block_rows, block_cols))
        H_shifted = np.zeros((n_channels * block_rows, block_cols))
        for i in range(block_rows):
            for j in range(block_cols):
                k = i + j
                H[i * n_channels:(i + 1) * n_channels, j] = positive_ir[:, k]
                if k + 1 < n_positive:
                    H_shifted[i * n_channels:(i + 1) * n_channels, j] = positive_ir[:, k + 1]

    return H, H_shifted


def era_svd(H, model_order=None, tolerance=1e-6):
    U, S, Vh = np.linalg.svd(H, full_matrices=False)
    if model_order is None:
        cumulative = np.cumsum(S) / np.sum(S)
        model_order = np.searchsorted(cumulative, 1 - tolerance) + 1
        model_order = min(model_order, len(S))
    model_order = max(2, min(model_order, len(S)))
    model_order = model_order // 2 * 2
    S_diag = np.diag(np.sqrt(S[:model_order]))
    Ob = U[:, :model_order] @ S_diag
    Cb = S_diag @ Vh[:model_order, :]
    return Ob, Cb, S, model_order


def era_system_realization(impulse_responses, block_rows, block_cols,
                           model_order=None, tolerance=1e-6):
    n_channels = impulse_responses.shape[0]
    H, H_shifted = era_hankel_matrix(impulse_responses, block_rows, block_cols)
    Ob, Cb, S, model_order = era_svd(H, model_order, tolerance)
    S_inv_sqrt = np.diag(1.0 / np.sqrt(S[:model_order]))
    A = S_inv_sqrt @ (Ob.T @ H_shifted @ Cb.T) @ S_inv_sqrt
    C = Ob[:n_channels, :]
    if Cb.shape[1] >= n_channels:
        B = Cb[:, :n_channels]
    else:
        B = Cb[:, :min(n_channels, Cb.shape[1])]
    return A, B, C, S, model_order


def era_modal_params(A, B, C, fs, freq_range=(0.01, 50.0)):
    eigenvalues, eigenvectors = np.linalg.eig(A)
    dt = 1.0 / fs
    s = np.log(eigenvalues) / dt
    natural_freq = np.abs(s) / (2 * np.pi)
    damping_ratio = -np.real(s) / (np.abs(s) + 1e-10)
    complex_mode_shapes = C @ eigenvectors
    mode_shapes = np.real(complex_mode_shapes)

    valid_mask = (
        (natural_freq >= freq_range[0]) &
        (natural_freq <= freq_range[1]) &
        (damping_ratio >= 0) &
        (damping_ratio <= 0.5) &
        (np.abs(eigenvalues) <= 1.0 + 1e-6)
    )
    valid_indices = np.where(valid_mask)[0]
    if len(valid_indices) == 0:
        n_dofs = mode_shapes.shape[0]
        return {
            'natural_frequencies': np.array([]),
            'damping_ratios': np.array([]),
            'mode_shapes': np.zeros((n_dofs, 0)),
            'complex_mode_shapes': np.zeros((n_dofs, 0)),
            'continuous_eigenvalues': np.array([]),
            'discrete_eigenvalues': np.array([]),
        }

    natural_freq = natural_freq[valid_indices]
    damping_ratio = damping_ratio[valid_indices]
    s_valid = s[valid_indices]
    eigenvectors_valid = eigenvectors[:, valid_indices]
    mode_shapes_valid = mode_shapes[:, valid_indices]
    complex_mode_shapes_valid = complex_mode_shapes[:, valid_indices]
    eigenvalues_valid = eigenvalues[valid_indices]

    unique_modes = []
    used = set()
    for i in range(len(natural_freq)):
        if i in used:
            continue
        for j in range(i + 1, len(natural_freq)):
            if j in used:
                continue
            freq_diff = abs(natural_freq[i] - natural_freq[j]) / (natural_freq[i] + 1e-10)
            if freq_diff < 0.01:
                ms1 = mode_shapes_valid[:, i]
                ms2 = mode_shapes_valid[:, j]
                norm1 = np.linalg.norm(ms1)
                norm2 = np.linalg.norm(ms2)
                if norm1 > 1e-10 and norm2 > 1e-10:
                    dot = np.dot(ms1, ms2) / (norm1 * norm2)
                    if abs(dot) > 0.8:
                        used.add(i)
                        used.add(j)
                        if abs(damping_ratio[i]) <= abs(damping_ratio[j]):
                            unique_modes.append(i)
                        else:
                            unique_modes.append(j)
                        break
        if i not in used:
            used.add(i)
            unique_modes.append(i)

    natural_freq = natural_freq[unique_modes]
    damping_ratio = damping_ratio[unique_modes]
    mode_shapes_valid = mode_shapes_valid[:, unique_modes]
    complex_mode_shapes_valid = complex_mode_shapes_valid[:, unique_modes]
    s_valid = s_valid[unique_modes]
    eigenvalues_valid = eigenvalues_valid[unique_modes]

    idx = np.argsort(natural_freq)
    natural_freq = natural_freq[idx]
    damping_ratio = damping_ratio[idx]
    mode_shapes_valid = mode_shapes_valid[:, idx]
    complex_mode_shapes_valid = complex_mode_shapes_valid[:, idx]
    s_valid = s_valid[idx]
    eigenvalues_valid = eigenvalues_valid[idx]

    return {
        'natural_frequencies': natural_freq,
        'damping_ratios': damping_ratio,
        'mode_shapes': mode_shapes_valid,
        'complex_mode_shapes': complex_mode_shapes_valid,
        'continuous_eigenvalues': s_valid,
        'discrete_eigenvalues': eigenvalues_valid,
    }


def era_stabilization_diagram(impulse_responses, fs, model_order_min=4,
                              model_order_max=50, order_step=2,
                              freq_tolerance=0.01, damping_tolerance=0.05,
                              mac_threshold=0.90):
    n_channels = impulse_responses.shape[0]
    block_rows = max(20, model_order_max // 2)
    block_cols = max(20, model_order_max // 2)
    all_poles = []
    orders = list(range(model_order_min, model_order_max + 1, order_step))
    for order in orders:
        try:
            A, B, C, S, eff_order = era_system_realization(
                impulse_responses, block_rows, block_cols,
                model_order=order
            )
            params = era_modal_params(A, B, C, fs)
            freqs = params['natural_frequencies']
            dampings = params['damping_ratios']
            modes = params['mode_shapes']
            for i in range(len(freqs)):
                all_poles.append({
                    'order': order,
                    'frequency': freqs[i],
                    'damping': dampings[i],
                    'mode_shape': modes[:, i] if modes.shape[1] > i else None,
                })
        except Exception:
            continue
    stable_poles = []
    for i, pole in enumerate(all_poles):
        if pole['mode_shape'] is None:
            continue
        is_stable = False
        for other in all_poles:
            if other['order'] == pole['order']:
                continue
            if other['mode_shape'] is None:
                continue
            freq_diff = abs(pole['frequency'] - other['frequency']) / (pole['frequency'] + 1e-10)
            damp_diff = abs(pole['damping'] - other['damping'])
            if pole['frequency'] > 0:
                mac_val = _mac(pole['mode_shape'], other['mode_shape'])
                if freq_diff < freq_tolerance and damp_diff < damping_tolerance and mac_val > mac_threshold:
                    is_stable = True
                    break
        if is_stable:
            stable_poles.append(pole)
    return stable_poles, all_poles, orders


def _mac(phi1, phi2):
    if len(phi1) != len(phi2):
        return 0.0
    denom = (np.dot(phi1, phi1) * np.dot(phi2, phi2))
    if denom == 0:
        return 0.0
    return abs(np.dot(phi1, phi2)) ** 2 / denom
