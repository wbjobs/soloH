import numpy as np

class Config:
    sampling_rate = 100.0
    dt = 1.0 / sampling_rate

    sta_window = 1.0
    lta_window = 20.0
    sta_lta_threshold = 4.0
    detection_dead_time = 2.0

    polarization_window = 1.0
    polarization_threshold = 0.7
    rectilinearity_threshold = 0.6

    pd_window = 3.0
    tau_c_window = 3.0

    magnitude_calibration_a = 2.0
    magnitude_calibration_b = 1.2
    magnitude_method = 'combined'

    s_wave_detection = True
    s_wave_sta_window = 0.5
    s_wave_lta_window = 5.0
    s_wave_threshold = 3.5
    s_wave_min_interval = 1.0
    s_wave_cut_to_pd_ratio = 0.8

    site_class = 'C'
    site_amplification_factors = {
        'A': 0.8,
        'B': 0.9,
        'C': 1.0,
        'D': 1.3,
        'E': 1.8,
        'F': 2.5
    }
    site_correction_enabled = True

    aftershock_detection_enabled = True
    aftershock_time_window = 30.0
    aftershock_magnitude_drop_threshold = 1.0
    aftershock_location_tolerance = 2.0
    event_cluster_max_time = 5.0

    alert_levels = {
        'info': {'sta_lta': 2.5, 'magnitude': 3.0},
        'warning': {'sta_lta': 4.0, 'magnitude': 4.0},
        'alarm': {'sta_lta': 6.0, 'magnitude': 5.0},
        'critical': {'sta_lta': 9.0, 'magnitude': 6.0}
    }

    online_window_size = 60.0
    online_overlap = 55.0

    filter_lowcut = 0.1
    filter_highcut = 20.0
    filter_order = 4

    dl_detector_enabled = True
    dl_window_size = 200
    dl_threshold = 0.5
    dl_batch_size = 32
    dl_hybrid_detection = True

    focal_mechanism_enabled = True
    focal_mechanism_window = 0.5
    focal_mechanism_min_snr = 2.0

    warning_zone_enabled = True
    warning_p_wave_velocity = 6.0
    warning_s_wave_velocity = 3.5
    warning_default_depth = 10.0
    warning_lead_time_threshold = 3.0

    @staticmethod
    def get_alert_level(sta_lta_ratio, magnitude):
        if np.isnan(magnitude):
            magnitude = 0
        for level in ['critical', 'alarm', 'warning', 'info']:
            thresholds = Config.alert_levels[level]
            if sta_lta_ratio >= thresholds['sta_lta'] and magnitude >= thresholds['magnitude']:
                return level
        return 'normal'

    @staticmethod
    def get_site_correction_factor(site_class=None):
        if site_class is None:
            site_class = Config.site_class
        if not Config.site_correction_enabled:
            return 1.0
        return Config.site_amplification_factors.get(site_class, 1.0)

    @staticmethod
    def estimate_s_arrival_time(p_arrival_time, epicentral_distance_km=None, p_velocity=6.0, s_velocity=3.5):
        if epicentral_distance_km is None:
            return p_arrival_time + 3.0
        t_p = epicentral_distance_km / p_velocity
        t_s = epicentral_distance_km / s_velocity
        return p_arrival_time + (t_s - t_p)
