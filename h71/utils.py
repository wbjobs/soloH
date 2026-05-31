import numpy as np
from scipy.signal import butter, filtfilt
from config import Config

def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    y = filtfilt(b, a, data, axis=0)
    return y

def integrate_acceleration(acc, dt):
    acc = np.array(acc)
    if acc.ndim == 1:
        acc = acc.reshape(-1, 1)
    
    n, ncomp = acc.shape
    vel = np.zeros_like(acc)
    disp = np.zeros_like(acc)
    
    vel[0] = 0.0
    disp[0] = 0.0
    
    for i in range(1, n):
        vel[i] = vel[i-1] + acc[i] * dt
        disp[i] = disp[i-1] + vel[i] * dt
    
    return vel, disp

def detrend(data):
    return data - np.mean(data, axis=0)

def preprocess_waveform(data, fs):
    data_detrended = detrend(data)
    data_filtered = butter_bandpass_filter(
        data_detrended,
        Config.filter_lowcut,
        Config.filter_highcut,
        fs,
        Config.filter_order
    )
    return data_filtered

def compute_horizontal_amplitude(n, e):
    return np.sqrt(n**2 + e**2)

def compute_combined_amplitude(data):
    return np.sqrt(np.sum(data**2, axis=1))
