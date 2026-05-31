import numpy as np
import os
from config import Config
from utils import preprocess_waveform

class WaveformData:
    def __init__(self, data, sampling_rate, start_time=0.0, station_name='STA'):
        self.data = np.array(data, dtype=np.float64)
        if self.data.ndim == 1:
            self.data = self.data.reshape(-1, 1)
        if self.data.shape[1] == 1:
            self.data = np.tile(self.data, (1, 3))
        self.sampling_rate = sampling_rate
        self.dt = 1.0 / sampling_rate
        self.npts = self.data.shape[0]
        self.start_time = start_time
        self.station_name = station_name
        self.times = start_time + np.arange(self.npts) * self.dt

    def get_component(self, comp):
        comp_map = {'Z': 0, 'N': 1, 'E': 2, '0': 0, '1': 1, '2': 2}
        return self.data[:, comp_map[str(comp).upper()]]

    def slice(self, start_idx, end_idx):
        sliced_data = self.data[start_idx:end_idx, :]
        sliced_times = self.times[start_idx:end_idx]
        return WaveformData(
            sliced_data,
            self.sampling_rate,
            start_time=sliced_times[0] if len(sliced_times) > 0 else self.start_time,
            station_name=self.station_name
        )


def load_from_npy(file_path, sampling_rate=None):
    data = np.load(file_path)
    if sampling_rate is None:
        sampling_rate = Config.sampling_rate
    return WaveformData(data, sampling_rate)


def load_from_txt(file_path, sampling_rate=None, delimiter=',', skiprows=0):
    data = np.loadtxt(file_path, delimiter=delimiter, skiprows=skiprows)
    if sampling_rate is None:
        sampling_rate = Config.sampling_rate
    return WaveformData(data, sampling_rate)


def load_from_csv(file_path, sampling_rate=None, skiprows=1):
    return load_from_txt(file_path, sampling_rate, delimiter=',', skiprows=skiprows)


def generate_synthetic_waveform(
    duration=120.0,
    sampling_rate=100.0,
    p_arrival=30.0,
    s_arrival=35.0,
    magnitude=5.0,
    noise_level=0.01,
    apply_preprocess=True
):
    npts = int(duration * sampling_rate)
    dt = 1.0 / sampling_rate
    times = np.arange(npts) * dt

    data = np.zeros((npts, 3))

    noise = noise_level * np.random.randn(npts, 3)
    data += noise

    p_idx = int(p_arrival / dt)
    s_idx = int(s_arrival / dt)

    p_amplitude = 10 ** (0.5 * magnitude) * 0.01
    p_duration = 2.0
    p_npts = int(p_duration / dt)
    p_t = np.arange(p_npts) * dt

    p_envelope = p_amplitude * (1 - np.exp(-p_t / 0.1)) * np.exp(-p_t / 0.5)

    p_angle_incident = np.radians(30)
    p_angle_azimuth = np.radians(45)

    p_z = p_envelope * np.cos(p_angle_incident)
    p_n = p_envelope * np.sin(p_angle_incident) * np.cos(p_angle_azimuth)
    p_e = p_envelope * np.sin(p_angle_incident) * np.sin(p_angle_azimuth)

    if p_idx + p_npts <= npts:
        data[p_idx:p_idx + p_npts, 0] += p_z
        data[p_idx:p_idx + p_npts, 1] += p_n
        data[p_idx:p_idx + p_npts, 2] += p_e

    s_amplitude = p_amplitude * 1.5
    s_duration = 4.0
    s_npts = int(s_duration / dt)
    s_t = np.arange(s_npts) * dt
    s_envelope = s_amplitude * (1 - np.exp(-s_t / 0.2)) * np.exp(-s_t / 1.0)

    if s_idx + s_npts <= npts:
        data[s_idx:s_idx + s_npts, 1] += s_envelope * 0.8
        data[s_idx:s_idx + s_npts, 2] += s_envelope * 0.6

    if apply_preprocess:
        data = preprocess_waveform(data, sampling_rate)

    return WaveformData(data, sampling_rate, start_time=0.0, station_name='SYN')


class RealTimeStreamSimulator:
    def __init__(self, waveform_data, chunk_size=1.0):
        self.waveform = waveform_data
        self.chunk_size = chunk_size
        self.chunk_npts = int(chunk_size * waveform_data.sampling_rate)
        self.current_idx = 0
        self.true_p_arrival = None

    def set_true_p_arrival(self, p_arrival_time):
        self.true_p_arrival = p_arrival_time

    def has_next(self):
        return self.current_idx < self.waveform.npts

    def next_chunk(self):
        if not self.has_next():
            return None
        end_idx = min(self.current_idx + self.chunk_npts, self.waveform.npts)
        chunk = self.waveform.slice(self.current_idx, end_idx)
        self.current_idx = end_idx
        return chunk

    def reset(self):
        self.current_idx = 0
