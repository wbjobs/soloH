import numpy as np
from scipy import signal
from scipy.optimize import curve_fit


def peak_picking_identification(data, fs, freq_range=(0.1, 20.0),
                                 n_peaks_max=10, min_peak_distance=0.3,
                                 peak_height=0.002, min_channels=2,
                                 damping_bandwidth=0.707,
                                 nperseg=None, nfft=None):
    n_samples, n_channels = data.shape
    if nperseg is None:
        nperseg = min(4096, n_samples // 2)
    if nfft is None:
        nfft = max(nperseg * 2, 2048)
    freqs, psd = signal.welch(data, fs=fs, nperseg=nperseg, nfft=nfft,
                               axis=0, detrend='linear')
    avg_psd = np.mean(psd, axis=1)
    freq_mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    search_freqs = freqs[freq_mask]
    search_psd_all = psd[freq_mask, :]
    freq_res = freqs[1] - freqs[0]
    min_distance_samples = max(1, int(min_peak_distance / freq_res))
    kernel_width = max(5, int(0.5 / freq_res))
    kernel = np.ones(kernel_width) / kernel_width
    channel_peaks = np.zeros((len(search_freqs), n_channels), dtype=int)
    for ch in range(n_channels):
        ch_psd = search_psd_all[:, ch]
        smoothed = np.convolve(ch_psd, kernel, mode='same')
        residual = ch_psd - smoothed
        residual[residual < 0] = 0
        height_val = peak_height * np.max(ch_psd)
        peaks, _ = signal.find_peaks(
            residual,
            height=height_val,
            distance=min_distance_samples,
            width=1,
            rel_height=0.5,
        )
        for p in peaks:
            channel_peaks[p, ch] = 1
    peak_counts = np.sum(channel_peaks, axis=1)
    valid_peaks = np.where(peak_counts >= min_channels)[0]
    if len(valid_peaks) == 0:
        max_psd = np.max(psd, axis=1)
        search_max = max_psd[freq_mask]
        smoothed = np.convolve(search_max, kernel, mode='same')
        residual = search_max - smoothed
        residual[residual < 0] = 0
        height_val = peak_height * np.max(search_max)
        valid_peaks, _ = signal.find_peaks(
            residual,
            height=height_val,
            distance=min_distance_samples,
        )
    if len(valid_peaks) == 0:
        return {
            'natural_frequencies': np.array([]),
            'damping_ratios': np.array([]),
            'mode_shapes': np.zeros((n_channels, 0)),
            'psd': avg_psd,
            'freqs': freqs,
        }
    peak_freqs = search_freqs[valid_peaks]
    max_psd_at_peaks = np.max(search_psd_all[valid_peaks, :], axis=1)
    if len(valid_peaks) > n_peaks_max:
        top_idx = np.argsort(max_psd_at_peaks)[::-1][:n_peaks_max]
        valid_peaks = valid_peaks[top_idx]
        peak_freqs = peak_freqs[top_idx]
        max_psd_at_peaks = max_psd_at_peaks[top_idx]
    sort_idx = np.argsort(peak_freqs)
    peak_freqs = peak_freqs[sort_idx]
    valid_peaks = valid_peaks[sort_idx]
    natural_freqs = []
    damping_ratios = []
    mode_shapes_list = []
    fft_vals = np.fft.rfft(data, axis=0)
    fft_freqs = np.fft.rfftfreq(n_samples, 1.0 / fs)
    search_psd_avg = np.mean(search_psd_all, axis=1)
    for p_idx, peak in enumerate(valid_peaks):
        peak_freq = peak_freqs[p_idx]
        freq_idx = valid_peaks[p_idx]
        half_power = search_psd_avg[freq_idx] * damping_bandwidth
        left_idx = freq_idx
        while left_idx > 0 and search_psd_avg[left_idx] > half_power:
            left_idx -= 1
        right_idx = freq_idx
        while right_idx < len(search_psd_avg) - 1 and search_psd_avg[right_idx] > half_power:
            right_idx += 1
        if right_idx > left_idx + 1:
            bandwidth = search_freqs[right_idx] - search_freqs[left_idx]
            damping = bandwidth / (2 * peak_freq) if peak_freq > 0 else 0.02
            damping = max(0.001, min(damping, 0.2))
        else:
            damping = 0.02
        natural_freqs.append(peak_freq)
        damping_ratios.append(damping)
        closest_idx = np.argmin(np.abs(fft_freqs - peak_freq))
        if closest_idx < len(fft_vals):
            mode_shape = np.abs(fft_vals[closest_idx, :])
            max_val = np.max(np.abs(mode_shape))
            if max_val > 1e-10:
                mode_shape = mode_shape / max_val
            mode_shapes_list.append(mode_shape)
        else:
            mode_shapes_list.append(np.ones(n_channels) / np.sqrt(n_channels))
    mode_shapes = np.column_stack(mode_shapes_list) if mode_shapes_list else np.zeros((n_channels, 0))
    return {
        'natural_frequencies': np.array(natural_freqs),
        'damping_ratios': np.array(damping_ratios),
        'mode_shapes': mode_shapes,
        'psd': avg_psd,
        'freqs': freqs,
    }


def ssi_cov_identification(data, fs, block_rows=100, model_order=None,
                            freq_range=(0.01, 50.0)):
    n_samples, n_channels = data.shape
    max_lag = min(block_rows * 4, n_samples // 4)
    block_cols = max(1, n_samples - max_lag)
    H = np.zeros((n_channels * block_rows, n_channels * block_cols))
    for i in range(block_rows):
        for j in range(block_cols):
            row_start = i * n_channels
            row_end = row_start + n_channels
            H[row_start:row_end, j] = data[i + j, :] if (i + j) < n_samples else 0.0
    U, S, Vt = np.linalg.svd(H, full_matrices=False)
    if model_order is None:
        model_order = min(30, len(S) // 4)
    S_sqrt = np.sqrt(S[:model_order])
    S_inv_sqrt = np.diag(1.0 / S_sqrt)
    Obs = U[:, :model_order] * S_sqrt[np.newaxis, :]
    A_matrix = np.zeros((model_order, model_order))
    if model_order > 0 and n_channels * block_rows > n_channels:
        Obs_up = Obs[:-n_channels, :]
        Obs_down = Obs[n_channels:, :]
        A_matrix = np.linalg.lstsq(Obs_up, Obs_down, rcond=None)[0]
    eigenvalues, eigenvectors = np.linalg.eig(A_matrix)
    C_matrix = np.zeros((n_channels, model_order))
    if model_order > 0:
        C_matrix = Obs[:n_channels, :]
    natural_freqs = []
    damping_ratios = []
    mode_shapes_list = []
    for idx, ev in enumerate(eigenvalues):
        freq_hz = np.abs(np.log(ev + 1e-20)) * fs / (2.0 * np.pi)
        if freq_hz < freq_range[0] or freq_hz > freq_range[1]:
            continue
        real_part = np.real(np.log(ev + 1e-20))
        imag_part = np.imag(np.log(ev + 1e-20))
        damping = -real_part / np.sqrt(real_part ** 2 + imag_part ** 2) if np.abs(ev) > 0 else 0
        if 0.001 < damping < 0.3 and np.abs(ev) < 1.05:
            natural_freqs.append(freq_hz)
            damping_ratios.append(damping)
            if model_order > 0 and idx < eigenvectors.shape[1]:
                mode_shape = np.abs(C_matrix @ eigenvectors[:, idx])
                max_val = np.max(np.abs(mode_shape))
                if max_val > 1e-10:
                    mode_shape = mode_shape / max_val
                mode_shapes_list.append(mode_shape)
            else:
                mode_shapes_list.append(np.ones(n_channels) / np.sqrt(n_channels))
    mode_shapes = np.column_stack(mode_shapes_list) if mode_shapes_list else np.zeros((n_channels, 0))
    return {
        'natural_frequencies': np.array(natural_freqs),
        'damping_ratios': np.array(damping_ratios),
        'mode_shapes': mode_shapes,
        'singular_values': S,
        'observation_matrix': Obs,
    }


def identify_modal_parameters(data, fs, method='peak_picking', **kwargs):
    if method == 'peak_picking':
        return peak_picking_identification(data, fs, **kwargs)
    elif method == 'ssi_cov':
        return ssi_cov_identification(data, fs, **kwargs)
    else:
        return peak_picking_identification(data, fs, **kwargs)
