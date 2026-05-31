import numpy as np
from scipy import signal


def next_cross_correlation(data, fs, max_lag=None):
    n_samples, n_channels = data.shape
    if max_lag is None:
        max_lag = n_samples // 4
    max_lag = min(max_lag, n_samples - 1)
    n_lags = 2 * max_lag + 1
    impulse_responses = np.zeros((n_channels, n_channels, n_lags))
    lags = np.arange(-max_lag, max_lag + 1)
    for i in range(n_channels):
        for j in range(n_channels):
            x = data[:, i] - np.mean(data[:, i])
            y = data[:, j] - np.mean(data[:, j])
            corr = signal.correlate(x, y, mode='full')
            center = len(corr) // 2
            ir = corr[center - max_lag:center + max_lag + 1]
            ir = ir / (n_samples * np.std(x) * np.std(y))
            impulse_responses[i, j, :] = ir
    return impulse_responses, lags, fs


def next_segmented(data, fs, segment_duration=20.0, overlap=0.5, max_lag=None):
    n_samples, n_channels = data.shape
    segment_length = int(segment_duration * fs)
    step = int(segment_length * (1 - overlap))
    if max_lag is None:
        max_lag = segment_length // 4
    max_lag = min(max_lag, segment_length - 1)
    n_lags = 2 * max_lag + 1
    ir_sum = np.zeros((n_channels, n_channels, n_lags))
    n_segments = 0
    start = 0
    while start + segment_length <= n_samples:
        seg = data[start:start + segment_length, :]
        ir, _, _ = next_cross_correlation(seg, fs, max_lag)
        ir_sum += ir
        n_segments += 1
        start += step
    if n_segments == 0:
        ir, lags, fs_out = next_cross_correlation(data, fs, max_lag)
        return ir, lags, fs_out
    ir_avg = ir_sum / n_segments
    lags = np.arange(-max_lag, max_lag + 1)
    return ir_avg, lags, fs


def next_hankel_matrix(impulse_responses, block_rows, block_cols):
    n_channels = impulse_responses.shape[0]
    n_lags = impulse_responses.shape[2]
    max_lag = (n_lags - 1) // 2
    positive_ir = impulse_responses[:, :, max_lag:]
    n_positive = positive_ir.shape[2]
    if block_rows + block_cols > n_positive:
        block_rows = n_positive // 2
        block_cols = n_positive - block_rows
    H = np.zeros((n_channels * block_rows, n_channels * block_cols))
    for i in range(block_rows):
        for j in range(block_cols):
            H[i * n_channels:(i + 1) * n_channels,
              j * n_channels:(j + 1) * n_channels] = positive_ir[:, :, i + j]
    return H


def next_extract_impulse_response(data, fs, ref_channel=0, max_lag=None):
    n_samples, n_channels = data.shape
    if max_lag is None:
        max_lag = n_samples // 4
    max_lag = min(max_lag, n_samples - 1)
    n_lags = 2 * max_lag + 1
    impulse_responses = np.zeros((n_channels, n_lags))
    lags = np.arange(-max_lag, max_lag + 1)
    ref = data[:, ref_channel] - np.mean(data[:, ref_channel])
    for i in range(n_channels):
        x = data[:, i] - np.mean(data[:, i])
        corr = signal.correlate(x, ref, mode='full')
        center = len(corr) // 2
        ir = corr[center - max_lag:center + max_lag + 1]
        ir = ir / (n_samples * np.std(x) * np.std(ref) + 1e-10)
        impulse_responses[i, :] = ir
    return impulse_responses, lags, fs
