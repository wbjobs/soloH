import numpy as np
from config import Config


def compute_sta_lta(data, sampling_rate, sta_window=None, lta_window=None):
    if sta_window is None:
        sta_window = Config.sta_window
    if lta_window is None:
        lta_window = Config.lta_window

    dt = 1.0 / sampling_rate
    npts = len(data)

    sta_npts = int(sta_window / dt)
    lta_npts = int(lta_window / dt)

    if sta_npts < 1:
        sta_npts = 1
    if lta_npts < sta_npts:
        lta_npts = sta_npts * 2

    data_sq = data ** 2

    sta = np.zeros(npts)
    lta = np.zeros(npts)

    cumsum = np.cumsum(data_sq)

    for i in range(npts):
        if i >= sta_npts:
            sta[i] = (cumsum[i] - cumsum[i - sta_npts]) / sta_npts
        else:
            sta[i] = cumsum[i] / (i + 1) if i > 0 else data_sq[0]

        if i >= lta_npts:
            lta[i] = (cumsum[i] - cumsum[i - lta_npts]) / lta_npts
        else:
            lta[i] = cumsum[i] / (i + 1) if i > 0 else data_sq[0]

    sta = np.sqrt(sta)
    lta = np.sqrt(lta)

    with np.errstate(divide='ignore', invalid='ignore'):
        sta_lta_ratio = np.where(lta > 1e-15, sta / lta, 0.0)

    return sta, lta, sta_lta_ratio


def detect_p_arrival(sta_lta_ratio, times, threshold=None, dead_time=None):
    if threshold is None:
        threshold = Config.sta_lta_threshold
    if dead_time is None:
        dead_time = Config.detection_dead_time

    detections = []
    npts = len(sta_lta_ratio)

    i = 0
    while i < npts:
        if sta_lta_ratio[i] >= threshold:
            peak_idx = i
            peak_val = sta_lta_ratio[i]

            j = i
            while j < npts and sta_lta_ratio[j] >= threshold * 0.5:
                if sta_lta_ratio[j] > peak_val:
                    peak_idx = j
                    peak_val = sta_lta_ratio[j]
                j += 1

            onset_idx = i
            for k in range(i, max(0, i - 100), -1):
                if sta_lta_ratio[k] < threshold * 0.3:
                    onset_idx = k + 1
                    break
                onset_idx = k

            detections.append({
                'arrival_time': times[onset_idx],
                'peak_time': times[peak_idx],
                'arrival_idx': onset_idx,
                'peak_idx': peak_idx,
                'sta_lta_ratio': peak_val,
                'confidence': min(1.0, (peak_val - threshold) / (threshold * 3))
            })

            dt = times[1] - times[0] if len(times) > 1 else 0.01
            dead_samples = int(dead_time / dt)
            i = peak_idx + dead_samples
        else:
            i += 1

    return detections


class STALTADetector:
    def __init__(self, sampling_rate):
        self.sampling_rate = sampling_rate
        self.dt = 1.0 / sampling_rate
        self.sta_buffer = []
        self.lta_buffer = []
        self.sta_window_npts = int(Config.sta_window / self.dt)
        self.lta_window_npts = int(Config.lta_window / self.dt)
        self.data_buffer = []
        self.last_detection_idx = -1
        self.detection_dead_npts = int(Config.detection_dead_time / self.dt)

    def process_chunk(self, chunk_data, chunk_times):
        chunk_npts = len(chunk_data)
        combined_amp = np.sqrt(np.sum(chunk_data ** 2, axis=1))

        self.data_buffer.extend(combined_amp.tolist())
        self.data_buffer = self.data_buffer[-self.lta_window_npts - chunk_npts:]

        data_array = np.array(self.data_buffer)
        npts = len(data_array)

        sta = np.zeros(npts)
        lta = np.zeros(npts)
        data_sq = data_array ** 2
        cumsum = np.cumsum(data_sq)

        for i in range(npts):
            sta[i] = cumsum[i] / (i + 1) if i < self.sta_window_npts else \
                     (cumsum[i] - cumsum[i - self.sta_window_npts]) / self.sta_window_npts
            lta[i] = cumsum[i] / (i + 1) if i < self.lta_window_npts else \
                     (cumsum[i] - cumsum[i - self.lta_window_npts]) / self.lta_window_npts

        sta = np.sqrt(sta)
        lta = np.sqrt(lta)

        with np.errstate(divide='ignore', invalid='ignore'):
            sta_lta_ratio = np.where(lta > 1e-15, sta / lta, 0.0)

        chunk_start_idx = npts - chunk_npts
        chunk_sta_lta = sta_lta_ratio[chunk_start_idx:]
        chunk_sta = sta[chunk_start_idx:]
        chunk_lta = lta[chunk_start_idx:]

        detections = []
        for i in range(chunk_npts):
            global_idx = chunk_start_idx + i
            if global_idx <= self.last_detection_idx + self.detection_dead_npts:
                continue

            if chunk_sta_lta[i] >= Config.sta_lta_threshold:
                self.last_detection_idx = global_idx
                detections.append({
                    'arrival_time': chunk_times[i],
                    'arrival_idx': i,
                    'sta_lta_ratio': chunk_sta_lta[i],
                    'confidence': min(1.0, (chunk_sta_lta[i] - Config.sta_lta_threshold) / (Config.sta_lta_threshold * 3)),
                    'sta': chunk_sta[i],
                    'lta': chunk_lta[i]
                })
                break

        return {
            'sta': chunk_sta,
            'lta': chunk_lta,
            'sta_lta_ratio': chunk_sta_lta,
            'detections': detections
        }

    def reset(self):
        self.sta_buffer = []
        self.lta_buffer = []
        self.data_buffer = []
        self.last_detection_idx = -1
