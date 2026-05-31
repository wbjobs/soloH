import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d


def detrend(data, method="linear"):
    if method == "linear":
        n = data.shape[0]
        x = np.arange(n)
        if data.ndim == 1:
            coeffs = np.polyfit(x, data, 1)
            return data - np.polyval(coeffs, x)
        else:
            result = np.zeros_like(data)
            for i in range(data.shape[1]):
                coeffs = np.polyfit(x, data[:, i], 1)
                result[:, i] = data[:, i] - np.polyval(coeffs, x)
            return result
    elif method == "constant":
        return data - np.mean(data, axis=0)
    else:
        raise ValueError(f"Unknown detrend method: {method}")


def bandpass_filter(data, fs, lowcut, highcut, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = signal.butter(order, [low, high], btype='band')
    if data.ndim == 1:
        return signal.filtfilt(b, a, data)
    else:
        result = np.zeros_like(data)
        for i in range(data.shape[1]):
            result[:, i] = signal.filtfilt(b, a, data[:, i])
        return result


def highpass_filter(data, fs, cutoff, order=4):
    nyq = 0.5 * fs
    high = cutoff / nyq
    b, a = signal.butter(order, high, btype='high')
    if data.ndim == 1:
        return signal.filtfilt(b, a, data)
    else:
        result = np.zeros_like(data)
        for i in range(data.shape[1]):
            result[:, i] = signal.filtfilt(b, a, data[:, i])
        return result


def lowpass_filter(data, fs, cutoff, order=4):
    nyq = 0.5 * fs
    low = cutoff / nyq
    b, a = signal.butter(order, low, btype='low')
    if data.ndim == 1:
        return signal.filtfilt(b, a, data)
    else:
        result = np.zeros_like(data)
        for i in range(data.shape[1]):
            result[:, i] = signal.filtfilt(b, a, data[:, i])
        return result


def moving_average(data, window_size=5):
    if data.ndim == 1:
        return uniform_filter1d(data, size=window_size)
    else:
        result = np.zeros_like(data)
        for i in range(data.shape[1]):
            result[:, i] = uniform_filter1d(data[:, i], size=window_size)
        return result


def estimate_snr(data, fs, signal_band=None):
    if signal_band is None:
        signal_band = (0.1, 20.0)
    freqs, psd = signal.welch(data, fs=fs, nperseg=min(1024, len(data)))
    signal_mask = (freqs >= signal_band[0]) & (freqs <= signal_band[1])
    noise_mask = ~signal_mask
    signal_power = np.sum(psd[signal_mask])
    noise_power = np.sum(psd[noise_mask])
    if noise_power == 0:
        return 100.0
    snr = 10 * np.log10(signal_power / noise_power)
    return snr


def preprocess(data, fs, detrend_method="linear",
               filter_type="bandpass", lowcut=0.1, highcut=20.0,
               filter_order=4, ma_window=None):
    result = detrend(data, method=detrend_method)
    if filter_type == "bandpass":
        result = bandpass_filter(result, fs, lowcut, highcut, filter_order)
    elif filter_type == "highpass":
        result = highpass_filter(result, fs, lowcut, filter_order)
    elif filter_type == "lowpass":
        result = lowpass_filter(result, fs, highcut, filter_order)
    if ma_window is not None and ma_window > 1:
        result = moving_average(result, ma_window)
    return result


def segment_data(data, fs, segment_duration, overlap=0.5):
    n_samples = data.shape[0]
    segment_length = int(segment_duration * fs)
    step = int(segment_length * (1 - overlap))
    segments = []
    start = 0
    while start + segment_length <= n_samples:
        segments.append(data[start:start + segment_length])
        start += step
    if len(segments) == 0:
        segments.append(data)
    return np.array(segments)
