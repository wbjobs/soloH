import numpy as np
from config import Config
from sta_lta import compute_sta_lta
from polarization import compute_polarization_parameters


def detect_s_wave(data, sampling_rate, p_arrival_idx, p_arrival_time,
                  horizontal_data=None, polarization_params=None):
    if not Config.s_wave_detection:
        return None, None, {'method': 'disabled'}

    dt = 1.0 / sampling_rate
    npts = data.shape[0]

    if horizontal_data is None:
        if data.shape[1] >= 3:
            horizontal_data = np.sqrt(data[:, 1]**2 + data[:, 2]**2)
        else:
            horizontal_data = np.sqrt(np.sum(data**2, axis=1))

    start_idx = min(p_arrival_idx + int(Config.s_wave_min_interval / dt), npts - 1)

    if start_idx >= npts - 10:
        estimated_s = Config.estimate_s_arrival_time(p_arrival_time)
        return int(estimated_s / dt), estimated_s, {'method': 'estimated', 'reason': 'insufficient_data'}

    search_data = horizontal_data[start_idx:]

    sta, lta, sta_lta_ratio = compute_sta_lta(
        search_data,
        sampling_rate,
        sta_window=Config.s_wave_sta_window,
        lta_window=Config.s_wave_lta_window
    )

    if polarization_params is None:
        polarization_params = compute_polarization_parameters(data, sampling_rate)

    planarity = polarization_params['planarity'][start_idx:]
    rectilinearity = polarization_params['rectilinearity'][start_idx:]

    s_score = np.zeros(len(sta_lta_ratio))
    for i in range(len(sta_lta_ratio)):
        if sta_lta_ratio[i] >= Config.s_wave_threshold:
            s_score[i] += 0.5
        if planarity[i] >= 0.7:
            s_score[i] += 0.3
        if rectilinearity[i] <= 0.8:
            s_score[i] += 0.2

    max_score_idx = np.argmax(s_score)
    max_score = s_score[max_score_idx]

    if max_score >= 0.5:
        s_idx_local = max_score_idx
        s_idx_global = start_idx + s_idx_local
        s_time = p_arrival_time + (s_idx_global - p_arrival_idx) * dt

        ps_interval = s_time - p_arrival_time

        info = {
            'method': 'detected',
            'score': max_score,
            'sta_lta_ratio': sta_lta_ratio[max_score_idx],
            'planarity': planarity[max_score_idx],
            'rectilinearity': rectilinearity[max_score_idx],
            'ps_interval': ps_interval
        }
        return s_idx_global, s_time, info
    else:
        estimated_s = Config.estimate_s_arrival_time(p_arrival_time)
        estimated_idx = int((estimated_s - p_arrival_time) / dt) + p_arrival_idx
        info = {
            'method': 'estimated',
            'reason': 'low_score',
            'max_score': max_score
        }
        return estimated_idx, estimated_s, info


def apply_site_correction(pd, site_class=None, magnitude=None):
    correction_factor = Config.get_site_correction_factor(site_class)

    if magnitude is not None and magnitude >= 6.0:
        correction_factor = correction_factor ** 0.8

    corrected_pd = pd / correction_factor

    return corrected_pd, correction_factor


def correct_pd_for_s_wave(pd, p_idx, s_idx, dt, disp_horizontal, full_disp=None):
    if s_idx is None:
        return pd, {'method': 'no_s_detection'}

    ps_interval_samples = s_idx - p_idx
    ps_interval = ps_interval_samples * dt

    pd_window_samples = int(Config.pd_window / dt)

    if ps_interval < pd_window_samples * Config.s_wave_cut_to_pd_ratio:
        effective_end_idx = min(s_idx, p_idx + pd_window_samples)
        if full_disp is not None and len(full_disp) >= effective_end_idx - p_idx:
            disp_segment = full_disp[p_idx:effective_end_idx]
            if disp_segment.ndim > 1:
                disp_h = np.sqrt(disp_segment[:, 1]**2 + disp_segment[:, 2]**2)
            else:
                disp_h = np.abs(disp_segment)
            corrected_pd = np.max(disp_h) if len(disp_h) > 0 else pd
        else:
            cut_ratio = ps_interval / (pd_window_samples * dt)
            corrected_pd = pd * (1.0 - 0.3 * (1.0 - cut_ratio))

        info = {
            'method': 's_wave_corrected',
            'original_pd': pd,
            'ps_interval': ps_interval,
            'cut_ratio': cut_ratio if 'cut_ratio' in locals() else 1.0,
            'window_truncated': True
        }
        return corrected_pd, info
    else:
        info = {
            'method': 'no_correction_needed',
            'ps_interval': ps_interval,
            'pd_window': Config.pd_window
        }
        return pd, info


class EventCluster:
    def __init__(self, first_detection):
        self.detections = [first_detection]
        self.start_time = first_detection.get('arrival_time', 0)
        self.end_time = self.start_time
        self.max_magnitude = first_detection.get('magnitude', 0)
        self.is_mainshock_identified = False
        self.mainshock_index = 0

    def add_detection(self, detection):
        self.detections.append(detection)
        arr_time = detection.get('arrival_time', 0)
        self.end_time = max(self.end_time, arr_time)
        mag = detection.get('magnitude', 0)
        if mag > self.max_magnitude:
            self.max_magnitude = mag
            self.mainshock_index = len(self.detections) - 1

    def is_within_cluster(self, detection, max_time_gap=None):
        if max_time_gap is None:
            max_time_gap = Config.event_cluster_max_time
        arr_time = detection.get('arrival_time', 0)
        return arr_time - self.end_time <= max_time_gap

    def classify_events(self):
        if len(self.detections) < 2:
            for det in self.detections:
                det['event_type'] = 'single'
            return self.detections

        sorted_dets = sorted(self.detections, key=lambda x: x.get('magnitude', 0), reverse=True)
        mainshock = sorted_dets[0]
        mainshock['event_type'] = 'mainshock'
        mainshock_mag = mainshock.get('magnitude', 0)

        for det in self.detections:
            if det is mainshock:
                continue

            det_mag = det.get('magnitude', 0)
            det_time = det.get('arrival_time', 0)
            main_time = mainshock.get('arrival_time', 0)

            if det_time < main_time:
                if mainshock_mag - det_mag <= Config.aftershock_magnitude_drop_threshold:
                    det['event_type'] = 'foreshock'
                else:
                    det['event_type'] = 'separate_event'
            else:
                time_diff = det_time - main_time
                if time_diff <= Config.aftershock_time_window:
                    if mainshock_mag - det_mag >= 0.3:
                        det['event_type'] = 'aftershock'
                    elif mainshock_mag - det_mag <= Config.aftershock_magnitude_drop_threshold:
                        det['event_type'] = 'separate_event'
                    else:
                        det['event_type'] = 'possible_aftershock'
                else:
                    det['event_type'] = 'separate_event'

            det['cluster_id'] = id(self)
            det['time_since_mainshock'] = det_time - main_time
            det['magnitude_difference'] = det_mag - mainshock_mag

        return self.detections


def cluster_and_classify_events(detections):
    if not Config.aftershock_detection_enabled:
        for det in detections:
            det['event_type'] = 'single'
            det['cluster_id'] = None
        return detections

    if not detections:
        return []

    sorted_detections = sorted(detections, key=lambda x: x.get('arrival_time', 0))

    clusters = []
    current_cluster = EventCluster(sorted_detections[0])

    for det in sorted_detections[1:]:
        if current_cluster.is_within_cluster(det):
            current_cluster.add_detection(det)
        else:
            clusters.append(current_cluster)
            current_cluster = EventCluster(det)

    clusters.append(current_cluster)

    all_classified = []
    for i, cluster in enumerate(clusters):
        classified = cluster.classify_events()
        for det in classified:
            det['cluster_id'] = i
            det['cluster_size'] = len(cluster.detections)
        all_classified.extend(classified)

    return all_classified


def deduplicate_detections(detections, time_tolerance=0.5):
    if len(detections) < 2:
        return detections

    sorted_dets = sorted(detections, key=lambda x: x.get('arrival_time', 0))
    unique_dets = []
    last_time = -np.inf

    for det in sorted_dets:
        arr_time = det.get('arrival_time', 0)
        if arr_time - last_time >= time_tolerance:
            unique_dets.append(det)
            last_time = arr_time
        else:
            if unique_dets:
                prev = unique_dets[-1]
                if det.get('sta_lta_ratio', 0) > prev.get('sta_lta_ratio', 0):
                    det['merged_from'] = prev.get('arrival_time', 0)
                    unique_dets[-1] = det
                    last_time = arr_time

    return unique_dets
