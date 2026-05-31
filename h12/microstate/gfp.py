import numpy as np
from scipy.signal import find_peaks, savgol_filter


class GFPAnalyzer:
    def __init__(self, sfreq=250.0):
        self.sfreq = sfreq
        self.gfp = None
        self.gfp_smoothed = None
        self.peak_indices = None
        self.peak_times = None
        self.peak_data = None

    def compute_gfp(self, data):
        self.gfp = np.sqrt(np.mean(data ** 2, axis=0))
        return self.gfp

    def smooth_gfp(self, gfp=None, window_length_ms=20, polyorder=3):
        if gfp is None:
            gfp = self.gfp
        if gfp is None:
            raise ValueError("请先计算GFP或提供GFP数据")
        
        window_length = int(window_length_ms * self.sfreq / 1000)
        if window_length % 2 == 0:
            window_length += 1
        if window_length < polyorder + 1:
            window_length = polyorder + 2
            if window_length % 2 == 0:
                window_length += 1
        
        self.gfp_smoothed = savgol_filter(gfp, window_length=window_length, polyorder=polyorder)
        return self.gfp_smoothed

    def find_peaks(self, gfp=None, min_distance_ms=20, height_threshold='median', 
                   prominence_factor=0.5, smooth=True):
        if gfp is None:
            gfp = self.gfp
        if gfp is None:
            raise ValueError("请先计算GFP或提供GFP数据")
        
        if smooth:
            gfp_for_detection = self.smooth_gfp(gfp)
        else:
            gfp_for_detection = gfp

        min_distance_samples = int(min_distance_ms * self.sfreq / 1000)
        
        if isinstance(height_threshold, str):
            if height_threshold == 'median':
                height = np.median(gfp_for_detection)
            elif height_threshold == 'mean':
                height = np.mean(gfp_for_detection)
            elif height_threshold == 'percentile75':
                height = np.percentile(gfp_for_detection, 75)
            else:
                height = np.median(gfp_for_detection)
        else:
            height = height_threshold
        
        gfp_std = np.std(gfp_for_detection)
        prominence = prominence_factor * gfp_std
        
        self.peak_indices, peak_props = find_peaks(
            gfp_for_detection,
            distance=min_distance_samples,
            height=height,
            prominence=prominence
        )
        self.peak_times = self.peak_indices / self.sfreq
        
        return self.peak_indices, self.peak_times, peak_props

    def get_peak_data(self, data, peak_indices=None):
        if peak_indices is None:
            peak_indices = self.peak_indices
        if peak_indices is None:
            raise ValueError("请先提取GFP峰值")

        self.peak_data = data[:, peak_indices]
        return self.peak_data

    def set_sampling_rate(self, sfreq):
        self.sfreq = sfreq

    def analyze(self, data, min_distance_ms=20, height_threshold='median', 
                prominence_factor=0.5, smooth=True):
        gfp = self.compute_gfp(data)
        peak_indices, peak_times, peak_props = self.find_peaks(
            gfp, min_distance_ms, height_threshold, prominence_factor, smooth
        )
        peak_data = self.get_peak_data(data, peak_indices)
        return gfp, peak_indices, peak_times, peak_data, peak_props
