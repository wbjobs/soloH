import numpy as np
from config import Config
from utils import integrate_acceleration
from advanced_processing import (
    detect_s_wave,
    apply_site_correction,
    correct_pd_for_s_wave
)


def compute_pd(acceleration, dt, arrival_idx, window=None, s_arrival_idx=None,
               full_acceleration=None, polarization_params=None, site_class=None):
    if window is None:
        window = Config.pd_window

    dt = float(dt)
    window_npts = int(window / dt)
    end_idx = min(len(acceleration), arrival_idx + window_npts)

    if arrival_idx >= len(acceleration):
        return 0.0, np.array([]), np.array([]), np.array([]), {}

    acc_segment = acceleration[arrival_idx:end_idx]

    vel, disp = integrate_acceleration(acc_segment, dt)

    disp_horizontal = np.sqrt(disp[:, 1] ** 2 + disp[:, 2] ** 2) if disp.ndim > 1 else np.abs(disp)
    raw_pd = np.max(disp_horizontal)

    corrections = {}

    if Config.s_wave_detection and s_arrival_idx is None and full_acceleration is not None:
        p_arrival_time = arrival_idx * dt
        s_idx, s_time, s_info = detect_s_wave(
            full_acceleration,
            1.0 / dt,
            arrival_idx,
            p_arrival_time,
            polarization_params=polarization_params
        )
        s_arrival_idx = s_idx
        corrections['s_detection'] = s_info
        corrections['s_arrival_idx'] = s_idx
        corrections['s_arrival_time'] = s_time

    if s_arrival_idx is not None:
        corrected_pd, s_correction_info = correct_pd_for_s_wave(
            raw_pd, arrival_idx, s_arrival_idx, dt, disp_horizontal, disp
        )
        corrections['s_wave_correction'] = s_correction_info
    else:
        corrected_pd = raw_pd
        corrections['s_wave_correction'] = {'method': 'not_applied'}

    if Config.site_correction_enabled:
        magnitude_est = estimate_magnitude_from_pd(corrected_pd)
        site_corrected_pd, site_factor = apply_site_correction(
            corrected_pd, site_class, magnitude_est
        )
        corrections['site_correction'] = {
            'site_class': site_class or Config.site_class,
            'correction_factor': site_factor,
            'pd_before_correction': corrected_pd,
            'pd_after_correction': site_corrected_pd
        }
        final_pd = site_corrected_pd
    else:
        final_pd = corrected_pd
        corrections['site_correction'] = {'method': 'disabled'}

    corrections['raw_pd'] = raw_pd
    corrections['corrected_pd'] = corrected_pd
    corrections['final_pd'] = final_pd

    return final_pd, vel, disp, disp_horizontal, corrections


def compute_tau_c(acceleration, dt, arrival_idx, window=None):
    if window is None:
        window = Config.tau_c_window

    window_npts = int(window / dt)
    end_idx = min(len(acceleration), arrival_idx + window_npts)

    if arrival_idx >= len(acceleration):
        return 0.0

    acc_segment = acceleration[arrival_idx:end_idx]

    if acc_segment.ndim > 1:
        acc_combined = np.sqrt(np.sum(acc_segment ** 2, axis=1))
    else:
        acc_segment = acc_segment.reshape(-1, 1)
        acc_combined = np.sqrt(np.sum(acc_segment ** 2, axis=1))

    vel, _ = integrate_acceleration(acc_segment, dt)
    if vel.ndim > 1:
        vel_combined = np.sqrt(np.sum(vel ** 2, axis=1))
    else:
        vel_combined = vel

    n = len(acc_combined)
    if n < 2:
        return 0.0

    integral_v2 = np.sum(vel_combined ** 2) * dt
    integral_a2 = np.sum(acc_combined ** 2) * dt

    if integral_a2 < 1e-15 or integral_v2 < 1e-15:
        return 0.0

    tau_c = 2.0 * np.pi * np.sqrt(integral_v2 / integral_a2)

    return tau_c


def estimate_magnitude_from_pd(pd, a=None, b=None):
    if a is None:
        a = Config.magnitude_calibration_a
    if b is None:
        b = Config.magnitude_calibration_b

    if pd <= 0:
        return np.nan

    magnitude = a + b * np.log10(pd * 100)
    return magnitude


def estimate_magnitude_from_tau_c(tau_c, a=None, b=None):
    if tau_c <= 0:
        return np.nan

    if a is None:
        a = 3.5
    if b is None:
        b = 2.5

    magnitude = a + b * np.log10(tau_c)
    return magnitude


def estimate_magnitude(acceleration, dt, arrival_idx, method=None,
                       polarization_params=None, site_class=None):
    if method is None:
        method = Config.magnitude_method

    full_acceleration = acceleration

    if method == 'pd':
        pd, _, _, _, corrections = compute_pd(
            acceleration, dt, arrival_idx,
            full_acceleration=full_acceleration,
            polarization_params=polarization_params,
            site_class=site_class
        )
        magnitude = estimate_magnitude_from_pd(pd)
        return {
            'method': 'pd',
            'pd': pd,
            'magnitude': magnitude,
            'uncertainty': 0.3,
            'corrections': corrections
        }
    elif method == 'tau_c':
        tau_c = compute_tau_c(acceleration, dt, arrival_idx)
        magnitude = estimate_magnitude_from_tau_c(tau_c)
        return {
            'method': 'tau_c',
            'tau_c': tau_c,
            'magnitude': magnitude,
            'uncertainty': 0.4
        }
    elif method == 'combined':
        pd, _, _, _, corrections = compute_pd(
            acceleration, dt, arrival_idx,
            full_acceleration=full_acceleration,
            polarization_params=polarization_params,
            site_class=site_class
        )
        tau_c = compute_tau_c(acceleration, dt, arrival_idx)
        mag_pd = estimate_magnitude_from_pd(pd)
        mag_tau_c = estimate_magnitude_from_tau_c(tau_c)

        if np.isnan(mag_pd):
            magnitude = mag_tau_c
        elif np.isnan(mag_tau_c):
            magnitude = mag_pd
        else:
            magnitude = 0.6 * mag_pd + 0.4 * mag_tau_c

        return {
            'method': 'combined',
            'pd': pd,
            'tau_c': tau_c,
            'magnitude_pd': mag_pd,
            'magnitude_tau_c': mag_tau_c,
            'magnitude': magnitude,
            'uncertainty': 0.25,
            'corrections': corrections
        }
    else:
        raise ValueError(f"Unknown magnitude estimation method: {method}")


class MagnitudeEstimator:
    def __init__(self, sampling_rate):
        self.sampling_rate = sampling_rate
        self.dt = 1.0 / sampling_rate
        self.data_buffer = []
        self.max_buffer = int(10.0 / self.dt)

    def process_chunk(self, chunk_data, arrival_indices=None):
        self.data_buffer.extend(chunk_data.tolist())
        self.data_buffer = self.data_buffer[-self.max_buffer:]

        results = []
        if arrival_indices is not None:
            for arr_idx in arrival_indices:
                global_idx = len(self.data_buffer) - len(chunk_data) + arr_idx

                if global_idx >= 0 and global_idx < len(self.data_buffer):
                    data_array = np.array(self.data_buffer)
                    mag_result = estimate_magnitude(
                        data_array,
                        self.dt,
                        global_idx,
                        method='combined'
                    )
                    results.append(mag_result)

        return results

    def reset(self):
        self.data_buffer = []
