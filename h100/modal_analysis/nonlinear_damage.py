import numpy as np
from scipy import signal
from scipy.fft import fft, fftfreq, ifft
from scipy.signal import welch, hilbert, stft
from scipy.stats import kurtosis, skew


def detect_higher_harmonics(signal, fs, fundamental_freq, n_harmonics=5):
    n = len(signal)
    fft_vals = np.abs(fft(signal))
    fft_freqs = fftfreq(n, 1 / fs)
    positive_idx = fft_freqs >= 0
    fft_vals = fft_vals[positive_idx]
    fft_freqs = fft_freqs[positive_idx]
    harmonics = []
    for h in range(1, n_harmonics + 1):
        target_freq = h * fundamental_freq
        closest_idx = np.argmin(np.abs(fft_freqs - target_freq))
        harmonic_amp = fft_vals[closest_idx]
        harmonics.append({
            'harmonic_order': h,
            'frequency': fft_freqs[closest_idx],
            'amplitude': harmonic_amp,
            'freq_error': abs(fft_freqs[closest_idx] - target_freq)
        })
    if harmonics[0]['amplitude'] > 0:
        for h in harmonics[1:]:
            h['relative_amplitude'] = h['amplitude'] / harmonics[0]['amplitude']
    else:
        for h in harmonics[1:]:
            h['relative_amplitude'] = 0.0
    hhi = np.sum([h['relative_amplitude'] for h in harmonics[1:]])
    return {
        'harmonics': harmonics,
        'higher_harmonic_index': hhi,
        'fundamental_amplitude': harmonics[0]['amplitude']
    }


def detect_frequency_response_distortion(signal, fs, fundamental_freq, bandwidth=0.5):
    f, t, Zxx = stft(signal, fs=fs, nperseg=256)
    mag = np.abs(Zxx)
    fund_idx = np.argmin(np.abs(f - fundamental_freq))
    window = int(bandwidth / (f[1] - f[0]))
    fund_mag = mag[max(0, fund_idx - window):fund_idx + window, :]
    mean_mag = np.mean(fund_mag, axis=0)
    cv = np.std(mean_mag) / (np.mean(mean_mag) + 1e-10)
    return {
        'time_varying_cv': cv,
        'stft_mean_amplitude': np.mean(mean_mag),
        'amplitude_modulation_depth': (np.max(mean_mag) - np.min(mean_mag)) / (np.mean(mean_mag) + 1e-10)
    }


def bispectrum_analysis(signal, fs, segment_length=256, overlap=0.5):
    n = len(signal)
    step = int(segment_length * (1 - overlap))
    n_segments = (n - segment_length) // step + 1
    bisp = np.zeros((segment_length // 2, segment_length // 2), dtype=complex)
    for i in range(n_segments):
        start = i * step
        end = start + segment_length
        seg = signal[start:end] * np.hanning(segment_length)
        fft_seg = fft(seg)
        for f1 in range(segment_length // 2):
            for f2 in range(segment_length // 2 - f1):
                bisp[f1, f2] += fft_seg[f1] * fft_seg[f2] * np.conj(fft_seg[f1 + f2])
    bisp /= n_segments
    bisp_mag = np.abs(bisp)
    bicoherence = bisp_mag / (np.mean(bisp_mag) + 1e-10)
    nonlinear_degree = np.mean(bicoherence[bicoherence > np.percentile(bicoherence, 95)])
    return {
        'bispectrum_magnitude': bisp_mag,
        'bicoherence': bicoherence,
        'nonlinear_degree': nonlinear_degree,
        'max_bicoherence': np.max(bicoherence)
    }


def detect_energy_transfer(signal, fs, fundamental_freq):
    f, Pxx = welch(signal, fs=fs, nperseg=1024)
    subharmonic_energy = 0.0
    for frac in [1/2, 1/3, 1/4]:
        target = fundamental_freq * frac
        idx = np.argmin(np.abs(f - target))
        subharmonic_energy += Pxx[idx]
    superharmonic_energy = 0.0
    for h in [2, 3, 4, 5]:
        target = fundamental_freq * h
        idx = np.argmin(np.abs(f - target))
        superharmonic_energy += Pxx[idx]
    fund_idx = np.argmin(np.abs(f - fundamental_freq))
    fund_energy = Pxx[fund_idx]
    total_energy = np.sum(Pxx)
    return {
        'subharmonic_energy_ratio': subharmonic_energy / (fund_energy + 1e-10),
        'superharmonic_energy_ratio': superharmonic_energy / (fund_energy + 1e-10),
        'energy_distortion_ratio': (subharmonic_energy + superharmonic_energy) / (total_energy + 1e-10)
    }


def detect_breathing_crack(signal, fs, threshold_level=0.1):
    analytic = hilbert(signal)
    envelope = np.abs(analytic)
    env_norm = (envelope - np.mean(envelope)) / (np.std(envelope) + 1e-10)
    crossings = np.where(np.diff(np.signbit(env_norm - threshold_level)))[0]
    crossing_rate = len(crossings) / len(signal) * fs
    envelope_cv = np.std(envelope) / (np.mean(envelope) + 1e-10)
    return {
        'envelope_cv': envelope_cv,
        'threshold_crossing_rate': crossing_rate,
        'envelope_kurtosis': kurtosis(envelope),
        'breathing_likelihood': min(1.0, envelope_cv * 0.5 + crossing_rate * 10)
    }


def phase_synchronization_analysis(signal1, signal2, fs):
    analytic1 = hilbert(signal1)
    analytic2 = hilbert(signal2)
    phase1 = np.angle(analytic1)
    phase2 = np.angle(analytic2)
    phase_diff = np.unwrap(phase1 - phase2)
    phase_cv = np.std(phase_diff) / (np.mean(np.abs(phase_diff)) + 1e-10)
    synch_index = np.abs(np.mean(np.exp(1j * phase_diff)))
    return {
        'phase_difference_std': np.std(phase_diff),
        'phase_cv': phase_cv,
        'synchronization_index': synch_index,
        'nonlinear_coupling': 1.0 - synch_index
    }


def nonlinear_feature_vector(signal, fs, fundamental_freq=None):
    if fundamental_freq is None:
        f, Pxx = welch(signal, fs=fs, nperseg=1024)
        fundamental_freq = f[np.argmax(Pxx)]
    features = {}
    hh = detect_higher_harmonics(signal, fs, fundamental_freq)
    features['higher_harmonic_index'] = hh['higher_harmonic_index']
    features['harmonic_2_rel_amp'] = hh['harmonics'][1]['relative_amplitude'] if len(hh['harmonics']) > 1 else 0
    features['harmonic_3_rel_amp'] = hh['harmonics'][2]['relative_amplitude'] if len(hh['harmonics']) > 2 else 0
    frd = detect_frequency_response_distortion(signal, fs, fundamental_freq)
    features['frd_cv'] = frd['time_varying_cv']
    features['am_depth'] = frd['amplitude_modulation_depth']
    et = detect_energy_transfer(signal, fs, fundamental_freq)
    features['subharmonic_ratio'] = et['subharmonic_energy_ratio']
    features['superharmonic_ratio'] = et['superharmonic_energy_ratio']
    features['energy_distortion'] = et['energy_distortion_ratio']
    bc = detect_breathing_crack(signal, fs)
    features['envelope_cv'] = bc['envelope_cv']
    features['breathing_likelihood'] = bc['breathing_likelihood']
    features['signal_kurtosis'] = kurtosis(signal)
    features['signal_skew'] = skew(signal)
    return features


class NonlinearDamageDetector:
    def __init__(self, threshold_quantile=0.95):
        self.threshold_quantile = threshold_quantile
        self.baseline_features = None
        self.baseline_thresholds = None
        self.feature_names = [
            'higher_harmonic_index',
            'harmonic_2_rel_amp',
            'harmonic_3_rel_amp',
            'frd_cv',
            'am_depth',
            'subharmonic_ratio',
            'superharmonic_ratio',
            'energy_distortion',
            'envelope_cv',
            'breathing_likelihood',
            'signal_kurtosis',
            'signal_skew'
        ]

    def fit_baseline(self, baseline_signals, fs, fundamental_freqs=None):
        n_signals = len(baseline_signals)
        self.baseline_features = np.zeros((n_signals, len(self.feature_names)))
        for i, sig in enumerate(baseline_signals):
            fund_freq = fundamental_freqs[i] if fundamental_freqs else None
            feat = nonlinear_feature_vector(sig, fs, fund_freq)
            for j, name in enumerate(self.feature_names):
                self.baseline_features[i, j] = feat[name]
        self.baseline_thresholds = np.percentile(
            self.baseline_features,
            self.threshold_quantile * 100,
            axis=0
        )
        return {
            'n_baseline_samples': n_signals,
            'thresholds': dict(zip(self.feature_names, self.baseline_thresholds))
        }

    def detect(self, signal, fs, fundamental_freq=None):
        feat = nonlinear_feature_vector(signal, fs, fundamental_freq)
        feature_values = np.array([feat[name] for name in self.feature_names])
        if self.baseline_thresholds is not None:
            threshold_exceed = feature_values > self.baseline_thresholds
            nonlinear_score = np.mean(threshold_exceed.astype(float))
        else:
            nonlinear_score = np.mean(feature_values / (np.max(feature_values) + 1e-10))
        crack_likelihood = min(1.0, nonlinear_score + feat['breathing_likelihood'] * 0.5)
        severity_level = 'none'
        if crack_likelihood > 0.8:
            severity_level = 'severe'
        elif crack_likelihood > 0.5:
            severity_level = 'moderate'
        elif crack_likelihood > 0.2:
            severity_level = 'mild'
        return {
            'features': feat,
            'nonlinear_score': nonlinear_score,
            'crack_likelihood': crack_likelihood,
            'severity': severity_level,
            'threshold_exceeded': dict(zip(self.feature_names, threshold_exceed)) if self.baseline_thresholds is not None else None
        }

    def detect_multichannel(self, data, fs, fundamental_freq=None):
        n_samples, n_channels = data.shape
        channel_results = []
        for ch in range(n_channels):
            res = self.detect(data[:, ch], fs, fundamental_freq)
            res['channel'] = ch
            channel_results.append(res)
        channel_results.sort(key=lambda x: x['crack_likelihood'], reverse=True)
        overall_score = np.mean([r['crack_likelihood'] for r in channel_results])
        overall_severity = 'none'
        if any(r['severity'] == 'severe' for r in channel_results):
            overall_severity = 'severe'
        elif any(r['severity'] == 'moderate' for r in channel_results):
            overall_severity = 'moderate'
        elif any(r['severity'] == 'mild' for r in channel_results):
            overall_severity = 'mild'
        return {
            'overall_crack_likelihood': overall_score,
            'overall_severity': overall_severity,
            'channel_results': channel_results,
            'most_likely_channel': channel_results[0]['channel'] if channel_results else None
        }


def generate_crack_simulation_signal(fs=100.0, duration=10.0, fundamental_freq=5.0,
                                       crack_severity=0.5, noise_level=0.05):
    t = np.arange(0, duration, 1/fs)
    stiffness_open = 1.0
    stiffness_closed = 1.0 + crack_severity * 0.5
    displacement = np.zeros_like(t)
    velocity = np.zeros_like(t)
    acceleration = np.zeros_like(t)
    omega0 = 2 * np.pi * fundamental_freq
    zeta = 0.02
    dt = 1 / fs
    for i in range(1, len(t)):
        if displacement[i-1] >= 0:
            omega = omega0 * np.sqrt(stiffness_closed)
        else:
            omega = omega0 * np.sqrt(stiffness_open)
        acceleration[i] = (-2 * zeta * omega * velocity[i-1]
                            - omega ** 2 * displacement[i-1]
                            + np.random.randn() * 0.01)
        velocity[i] = velocity[i-1] + acceleration[i] * dt
        displacement[i] = displacement[i-1] + velocity[i] * dt
    acceleration += noise_level * np.random.randn(len(t))
    return acceleration, t, displacement
