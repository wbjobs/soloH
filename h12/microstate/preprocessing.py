import numpy as np
from scipy import signal


class Preprocessor:
    def __init__(self, low_freq=1.0, high_freq=40.0, sfreq=250.0):
        self.low_freq = low_freq
        self.high_freq = high_freq
        self.sfreq = sfreq

    def bandpass_filter(self, data):
        nyq = 0.5 * self.sfreq
        low = self.low_freq / nyq
        high = self.high_freq / nyq
        b, a = signal.butter(4, [low, high], btype='band')
        filtered_data = signal.filtfilt(b, a, data, axis=1)
        return filtered_data

    def set_sampling_rate(self, sfreq):
        self.sfreq = sfreq

    def rereference(self, data, reference_type='average'):
        if reference_type == 'average':
            ref = np.mean(data, axis=0, keepdims=True)
        elif reference_type == 'median':
            ref = np.median(data, axis=0, keepdims=True)
        elif isinstance(reference_type, int):
            ref = data[reference_type:reference_type+1, :]
        else:
            raise ValueError(f"不支持的参考类型: {reference_type}")
        
        rereferenced_data = data - ref
        return rereferenced_data

    def preprocess(self, data, reference_type='average'):
        filtered_data = self.bandpass_filter(data)
        rereferenced_data = self.rereference(filtered_data, reference_type)
        return rereferenced_data
