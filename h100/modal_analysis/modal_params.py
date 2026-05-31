import numpy as np


def mac(phi1, phi2):
    if len(phi1) != len(phi2):
        return 0.0
    numerator = abs(np.dot(phi1.conj(), phi2)) ** 2
    denominator = np.dot(phi1.conj(), phi1) * np.dot(phi2.conj(), phi2)
    if denominator == 0:
        return 0.0
    return np.real(numerator / denominator)


def mac_matrix(modes1, modes2):
    n_modes1 = modes1.shape[1]
    n_modes2 = modes2.shape[1]
    mac_mat = np.zeros((n_modes1, n_modes2))
    for i in range(n_modes1):
        for j in range(n_modes2):
            mac_mat[i, j] = mac(modes1[:, i], modes2[:, j])
    return mac_mat


def match_modes(modes_healthy, modes_damaged, freq_healthy, freq_damaged,
                freq_tolerance=0.05, mac_threshold=0.7):
    n_healthy = modes_healthy.shape[1]
    n_damaged = modes_damaged.shape[1]
    matched_pairs = []
    used_damaged = set()
    for i in range(n_healthy):
        best_j = -1
        best_score = 0
        for j in range(n_damaged):
            if j in used_damaged:
                continue
            freq_diff = abs(freq_healthy[i] - freq_damaged[j]) / (freq_healthy[i] + 1e-10)
            if freq_diff > freq_tolerance:
                continue
            mac_val = mac(modes_healthy[:, i], modes_damaged[:, j])
            if mac_val < mac_threshold:
                continue
            score = mac_val * (1 - freq_diff)
            if score > best_score:
                best_score = score
                best_j = j
        if best_j >= 0:
            used_damaged.add(best_j)
            matched_pairs.append((i, best_j))
    return matched_pairs


def normalize_mode_shapes(mode_shapes, reference_dof=0):
    n_channels, n_modes = mode_shapes.shape
    normalized = np.zeros_like(mode_shapes)
    for i in range(n_modes):
        mode = mode_shapes[:, i]
        sign = np.sign(mode[reference_dof]) if mode[reference_dof] != 0 else 1.0
        max_val = np.max(np.abs(mode))
        if max_val > 0:
            normalized[:, i] = sign * mode / max_val
        else:
            normalized[:, i] = mode
    return normalized


def modal_assurance_criterion_report(modes_baseline, modes_current,
                                     freqs_baseline, freqs_current):
    mac_mat = mac_matrix(modes_baseline, modes_current)
    pairs = match_modes(modes_baseline, modes_current, freqs_baseline, freqs_current)
    report = {
        'mac_matrix': mac_mat,
        'matched_pairs': pairs,
        'n_baseline_modes': modes_baseline.shape[1],
        'n_current_modes': modes_current.shape[1],
    }
    return report


def compute_modal_damping(impulse_responses, fs, natural_freqs, mode_shapes,
                          max_cycles=10):
    n_channels = impulse_responses.shape[0]
    n_modes = len(natural_freqs)
    damping_estimates = []
    for mode_idx in range(n_modes):
        freq = natural_freqs[mode_idx]
        mode = mode_shapes[:, mode_idx]
        n_decay_points = int(max_cycles / (freq / fs)) if freq > 0 else len(impulse_responses[0])
        n_decay_points = min(n_decay_points, impulse_responses.shape[1])
        envelope = np.zeros(n_decay_points)
        for t in range(n_decay_points):
            ir_vec = impulse_responses[:, t]
            envelope[t] = abs(np.dot(mode, ir_vec))
        envelope = envelope - np.min(envelope)
        envelope = envelope / (np.max(envelope) + 1e-10)
        peaks = []
        for i in range(1, len(envelope) - 1):
            if envelope[i] > envelope[i-1] and envelope[i] > envelope[i+1]:
                peaks.append((i, envelope[i]))
        if len(peaks) >= 2:
            log_decrements = []
            for i in range(len(peaks) - 1):
                if peaks[i+1][1] > 0 and peaks[i][1] > 0:
                    ld = np.log(peaks[i][1] / peaks[i+1][1])
                    log_decrements.append(ld)
            if len(log_decrements) > 0:
                avg_ld = np.mean(log_decrements)
                damping = avg_ld / (2 * np.pi)
                damping = min(damping, 1.0)
                damping_estimates.append({
                    'mode': mode_idx,
                    'frequency': freq,
                    'damping_from_envelope': damping,
                })
    return damping_estimates


def modal_parameters_summary(natural_frequencies, damping_ratios,
                              mode_shapes, fs=None):
    summary = []
    for i in range(len(natural_frequencies)):
        summary.append({
            'mode_index': i + 1,
            'natural_frequency_hz': natural_frequencies[i],
            'natural_period_s': 1.0 / natural_frequencies[i] if natural_frequencies[i] > 0 else float('inf'),
            'damping_ratio': damping_ratios[i],
            'mode_shape_normalized': mode_shapes[:, i] / (np.max(np.abs(mode_shapes[:, i])) + 1e-10),
        })
    return summary
