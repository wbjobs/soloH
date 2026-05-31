import numpy as np
from scipy.signal import find_peaks
from config import Config


class FocalMechanismEstimator:
    def __init__(self, sampling_rate=100.0, p_window=0.5):
        self.sampling_rate = sampling_rate
        self.dt = 1.0 / sampling_rate
        self.p_window = p_window

    def estimate_focal_mechanism(self, data, arrival_idx, polarization_params=None):
        npts = data.shape[0]
        window_npts = int(self.p_window * self.sampling_rate)
        start_idx = max(0, arrival_idx - 10)
        end_idx = min(npts, arrival_idx + window_npts)

        p_segment = data[start_idx:end_idx, :].copy()

        if polarization_params is None:
            from polarization import compute_polarization_parameters
            polarization_params = compute_polarization_parameters(data, self.sampling_rate)

        results = {}

        results['first_motion'] = self._analyze_first_motion(p_segment, arrival_idx - start_idx)
        results['polarity_pattern'] = self._extract_polarity_pattern(p_segment, arrival_idx - start_idx)
        results['amplitude_ratios'] = self._compute_amplitude_ratios(p_segment, arrival_idx - start_idx)
        results['spectral_features'] = self._extract_spectral_features(p_segment)

        results.update(self._estimate_fault_parameters(results, polarization_params, arrival_idx))

        results.update(self._compute_uncertainty(results))

        return results

    def _analyze_first_motion(self, segment, p_onset):
        onset = p_onset
        if onset >= len(segment):
            onset = len(segment) - 1

        n_before = min(10, onset)
        baseline = np.mean(segment[max(0, onset - n_before):onset, :], axis=0)

        segment_demean = segment - baseline

        polarity = {}
        for comp, name in enumerate(['Z', 'N', 'E']):
            after_onset = segment_demean[onset:min(onset + 20, len(segment_demean)), comp]
            if len(after_onset) > 0:
                first_peak_idx = np.argmax(np.abs(after_onset))
                first_value = after_onset[first_peak_idx]
                polarity[name] = 'up' if first_value > 0 else 'down'
                polarity[f'{name}_amp'] = first_value
            else:
                polarity[name] = 'unknown'
                polarity[f'{name}_amp'] = 0.0

        z_pol = 1 if polarity.get('Z') == 'up' else -1
        n_pol = 1 if polarity.get('N') == 'up' else -1
        e_pol = 1 if polarity.get('E') == 'up' else -1

        total_polarity = z_pol + n_pol + e_pol
        polarity['overall'] = 'compression' if total_polarity > 0 else 'dilation' if total_polarity < 0 else 'mixed'

        return polarity

    def _extract_polarity_pattern(self, segment, p_onset):
        pattern = {}
        onset = min(p_onset, len(segment) - 1)

        npts_after = min(50, len(segment) - onset - 1)
        if npts_after < 5:
            return {'error': 'Insufficient data'}

        z_after = segment[onset:onset + npts_after, 0]
        n_after = segment[onset:onset + npts_after, 1]
        e_after = segment[onset:onset + npts_after, 2]

        z_peaks, _ = find_peaks(z_after, height=0.1 * np.max(np.abs(z_after)))
        z_troughs, _ = find_peaks(-z_after, height=0.1 * np.max(np.abs(z_after)))

        pattern['z_num_peaks'] = len(z_peaks)
        pattern['z_num_troughs'] = len(z_troughs)

        if len(z_peaks) > 0 and len(z_troughs) > 0:
            pattern['z_first_extremum'] = 'peak' if z_peaks[0] < z_troughs[0] else 'trough'
        elif len(z_peaks) > 0:
            pattern['z_first_extremum'] = 'peak'
        elif len(z_troughs) > 0:
            pattern['z_first_extremum'] = 'trough'
        else:
            pattern['z_first_extremum'] = 'unknown'

        cross_corr_nz = np.correlate(z_after - np.mean(z_after),
                                     n_after - np.mean(n_after), mode='valid')[0]
        cross_corr_ez = np.correlate(z_after - np.mean(z_after),
                                     e_after - np.mean(e_after), mode='valid')[0]

        pattern['nz_correlation'] = cross_corr_nz / (np.std(z_after) * np.std(n_after) + 1e-10)
        pattern['ez_correlation'] = cross_corr_ez / (np.std(z_after) * np.std(e_after) + 1e-10)

        pattern['n_phase_shift'] = self._estimate_phase_shift(z_after, n_after)
        pattern['e_phase_shift'] = self._estimate_phase_shift(z_after, e_after)

        return pattern

    def _estimate_phase_shift(self, sig1, sig2):
        if len(sig1) != len(sig2) or len(sig1) < 10:
            return 0.0

        npts = len(sig1)
        max_shift = min(20, npts // 4)

        correlations = []
        for shift in range(-max_shift, max_shift + 1):
            if shift < 0:
                s1 = sig1[:shift]
                s2 = sig2[-shift:]
            elif shift > 0:
                s1 = sig1[shift:]
                s2 = sig2[:-shift]
            else:
                s1 = sig1
                s2 = sig2

            if len(s1) > 0:
                corr = np.correlate(s1 - np.mean(s1), s2 - np.mean(s2))[0]
                corr /= (np.std(s1) * np.std(s2) * len(s1) + 1e-10)
                correlations.append((shift, corr))

        if correlations:
            best_shift, best_corr = max(correlations, key=lambda x: x[1])
            return best_shift * self.dt

        return 0.0

    def _compute_amplitude_ratios(self, segment, p_onset):
        ratios = {}
        onset = min(p_onset, len(segment) - 1)

        npts_after = min(30, len(segment) - onset - 1)
        if npts_after < 5:
            return {'error': 'Insufficient data'}

        z_amp = np.max(np.abs(segment[onset:onset + npts_after, 0]))
        n_amp = np.max(np.abs(segment[onset:onset + npts_after, 1]))
        e_amp = np.max(np.abs(segment[onset:onset + npts_after, 2]))

        horizontal_amp = np.sqrt(n_amp**2 + e_amp**2)

        ratios['z_max_amp'] = z_amp
        ratios['n_max_amp'] = n_amp
        ratios['e_max_amp'] = e_amp
        ratios['horizontal_max_amp'] = horizontal_amp

        ratios['z_over_h'] = z_amp / (horizontal_amp + 1e-10)
        ratios['n_over_z'] = n_amp / (z_amp + 1e-10)
        ratios['e_over_z'] = e_amp / (z_amp + 1e-10)
        ratios['n_over_e'] = n_amp / (e_amp + 1e-10)

        z_rms = np.sqrt(np.mean(segment[onset:onset + npts_after, 0]**2))
        n_rms = np.sqrt(np.mean(segment[onset:onset + npts_after, 1]**2))
        e_rms = np.sqrt(np.mean(segment[onset:onset + npts_after, 2]**2))
        h_rms = np.sqrt(n_rms**2 + e_rms**2)

        ratios['z_rms'] = z_rms
        ratios['h_rms'] = h_rms
        ratios['z_rms_over_h'] = z_rms / (h_rms + 1e-10)

        return ratios

    def _extract_spectral_features(self, segment):
        features = {}

        npts = len(segment)
        if npts < 32:
            return {'error': 'Insufficient data for spectral analysis'}

        for comp, name in enumerate(['Z', 'N', 'E']):
            data_comp = segment[:, comp]
            data_comp = data_comp * np.hanning(npts)
            fft = np.fft.rfft(data_comp)
            freq = np.fft.rfftfreq(npts, d=self.dt)
            power = np.abs(fft)**2

            total_power = np.sum(power)
            if total_power > 0:
                cumulative = np.cumsum(power) / total_power

                features[f'{name}_peak_freq'] = freq[np.argmax(power)]
                features[f'{name}_freq_50'] = freq[np.searchsorted(cumulative, 0.5)]
                features[f'{name}_freq_95'] = freq[np.searchsorted(cumulative, 0.95)]
                features[f'{name}_spectral_centroid'] = np.sum(freq * power) / total_power
                features[f'{name}_spectral_width'] = np.sqrt(
                    np.sum((freq - features[f'{name}_spectral_centroid'])**2 * power) / total_power
                )

        if 'Z_peak_freq' in features:
            features['n_z_peak_ratio'] = features.get('N_peak_freq', 0) / (features['Z_peak_freq'] + 1e-10)
            features['e_z_peak_ratio'] = features.get('E_peak_freq', 0) / (features['Z_peak_freq'] + 1e-10)

        return features

    def _estimate_fault_parameters(self, features, polarization_params, arrival_idx):
        params = {}

        if arrival_idx < len(polarization_params.get('azimuth', [])):
            params['azimuth'] = polarization_params['azimuth'][arrival_idx]
            params['incidence_angle'] = polarization_params['incidence_angle'][arrival_idx]
        else:
            params['azimuth'] = 0.0
            params['incidence_angle'] = 0.0

        amp_ratios = features.get('amplitude_ratios', {})
        first_motion = features.get('first_motion', {})
        spectral = features.get('spectral_features', {})
        polarity = features.get('polarity_pattern', {})

        strike = params['azimuth']
        rake = self._estimate_rake(amp_ratios, first_motion, polarity)
        dip = self._estimate_dip(amp_ratios, params['incidence_angle'])

        params['strike'] = strike
        params['rake'] = rake
        params['dip'] = dip

        params['fault_type'] = self._classify_fault_type(strike, dip, rake)

        params['rupture_direction'] = self._estimate_rupture_direction(
            amp_ratios, spectral, polarity, strike
        )

        params['moment_magnitude_estimate'] = self._estimate_moment_magnitude(amp_ratios, spectral)

        return params

    def _estimate_rake(self, amp_ratios, first_motion, polarity):
        n_over_e = amp_ratios.get('n_over_e', 1.0)
        nz_corr = polarity.get('nz_correlation', 0.0)
        ez_corr = polarity.get('ez_correlation', 0.0)

        rake = np.arctan2(n_over_e * np.sign(nz_corr), np.sign(ez_corr))
        rake = np.degrees(rake)

        z_pol = first_motion.get('Z', 'up')
        if z_pol == 'down':
            if rake > 0:
                rake = 180 - rake
            else:
                rake = -180 - rake

        rake = np.clip(rake, -90, 90)

        return float(rake)

    def _estimate_dip(self, amp_ratios, incidence_angle):
        z_over_h = amp_ratios.get('z_over_h', 0.5)

        dip = np.degrees(np.arcsin(np.clip(z_over_h, 0, 1)))
        dip = np.clip(dip + incidence_angle * 0.3, 10, 80)

        return float(dip)

    def _classify_fault_type(self, strike, dip, rake):
        rake_abs = abs(rake)

        if rake_abs > 135 or rake_abs < 45:
            if dip < 45:
                return 'thrust'
            elif dip > 70:
                return 'normal'
            else:
                return 'strike_slip'
        elif 45 <= rake_abs <= 135:
            if rake > 0:
                return 'thrust'
            else:
                return 'normal'
        else:
            return 'unknown'

    def _estimate_rupture_direction(self, amp_ratios, spectral, polarity, strike):
        direction = {}

        n_phase = polarity.get('n_phase_shift', 0.0)
        e_phase = polarity.get('e_phase_shift', 0.0)

        n_z_ratio = amp_ratios.get('n_over_z', 0.0)
        e_z_ratio = amp_ratios.get('e_over_z', 0.0)

        direction_azimuth = np.degrees(np.arctan2(e_z_ratio, n_z_ratio))
        direction_azimuth = (direction_azimuth + 360) % 360

        direction['azimuth'] = float(direction_azimuth)
        direction['relative_to_strike'] = float((direction_azimuth - strike + 360) % 360)

        n_peak_freq = spectral.get('N_peak_freq', 1.0)
        e_peak_freq = spectral.get('E_peak_freq', 1.0)
        z_peak_freq = spectral.get('Z_peak_freq', 1.0)

        if z_peak_freq > 0:
            direction['doppler_effect_hint'] = (
                'rupture_towards' if max(n_peak_freq, e_peak_freq) > z_peak_freq * 1.1
                else 'rupture_away' if max(n_peak_freq, e_peak_freq) < z_peak_freq * 0.9
                else 'uncertain'
            )
        else:
            direction['doppler_effect_hint'] = 'uncertain'

        direction['direction_confidence'] = float(
            min(0.95, 0.5 + 0.5 * abs(n_phase - e_phase) / max(abs(n_phase) + abs(e_phase), 1e-6))
        )

        return direction

    def _estimate_moment_magnitude(self, amp_ratios, spectral):
        h_amp = amp_ratios.get('horizontal_max_amp', 0.0)
        z_amp = amp_ratios.get('z_max_amp', 0.0)
        z_rms = amp_ratios.get('z_rms', 0.0)

        spectral_centroid = np.mean([
            spectral.get('Z_spectral_centroid', 1.0),
            spectral.get('N_spectral_centroid', 1.0),
            spectral.get('E_spectral_centroid', 1.0)
        ])

        if spectral_centroid > 0:
            corner_freq_est = spectral_centroid * 0.7
            moment_est = h_amp / (corner_freq_est ** 2 + 1e-10)
            mw_est = 2.0 / 3.0 * (np.log10(moment_est * 1e7) - 10.7)
        else:
            mw_est = np.nan

        return float(mw_est) if not np.isnan(mw_est) else 0.0

    def _compute_uncertainty(self, results):
        uncertainty = {}

        n_peaks = results.get('polarity_pattern', {}).get('z_num_peaks', 0)
        n_troughs = results.get('polarity_pattern', {}).get('z_num_troughs', 0)
        data_quality = min(1.0, (n_peaks + n_troughs) / 5.0)

        z_over_h = results.get('amplitude_ratios', {}).get('z_over_h', 0.5)
        amplitude_consistency = 1.0 - abs(z_over_h - 0.5)

        nz_corr = abs(results.get('polarity_pattern', {}).get('nz_correlation', 0.0))
        ez_corr = abs(results.get('polarity_pattern', {}).get('ez_correlation', 0.0))
        correlation_quality = (nz_corr + ez_corr) / 2.0

        overall_quality = 0.4 * data_quality + 0.3 * amplitude_consistency + 0.3 * correlation_quality

        uncertainty['data_quality'] = float(data_quality)
        uncertainty['amplitude_consistency'] = float(amplitude_consistency)
        uncertainty['correlation_quality'] = float(correlation_quality)
        uncertainty['overall_quality'] = float(overall_quality)

        base_uncertainty = 15.0
        strike_uncertainty = base_uncertainty / (overall_quality + 0.2)
        dip_uncertainty = base_uncertainty * 0.8 / (overall_quality + 0.2)
        rake_uncertainty = base_uncertainty * 1.2 / (overall_quality + 0.2)

        uncertainty['strike_uncertainty'] = float(min(strike_uncertainty, 45.0))
        uncertainty['dip_uncertainty'] = float(min(dip_uncertainty, 30.0))
        uncertainty['rake_uncertainty'] = float(min(rake_uncertainty, 60.0))

        uncertainty['quality_level'] = (
            'excellent' if overall_quality > 0.8
            else 'good' if overall_quality > 0.6
            else 'fair' if overall_quality > 0.4
            else 'poor'
        )

        return uncertainty


def format_focal_mechanism(fm):
    lines = []

    lines.append("  震源机制解:")
    lines.append(f"    节面参数:")
    lines.append(f"      走向 (Strike): {fm.get('strike', 0):.1f}° ± {fm.get('strike_uncertainty', 15):.1f}°")
    lines.append(f"      倾角 (Dip): {fm.get('dip', 0):.1f}° ± {fm.get('dip_uncertainty', 10):.1f}°")
    lines.append(f"      滑动角 (Rake): {fm.get('rake', 0):.1f}° ± {fm.get('rake_uncertainty', 15):.1f}°")

    fault_types = {
        'strike_slip': '走滑断层',
        'thrust': '逆冲断层',
        'normal': '正断层',
        'unknown': '未知'
    }
    lines.append(f"    断层类型: {fault_types.get(fm.get('fault_type', 'unknown'), '未知')}")

    rupture_dir = fm.get('rupture_direction', {})
    lines.append(f"    破裂方向估计:")
    lines.append(f"      方位角: {rupture_dir.get('azimuth', 0):.1f}°")
    lines.append(f"      与走向夹角: {rupture_dir.get('relative_to_strike', 0):.1f}°")
    lines.append(f"      多普勒效应: {rupture_dir.get('doppler_effect_hint', 'N/A')}")
    lines.append(f"      方向置信度: {rupture_dir.get('direction_confidence', 0):.2f}")

    first_motion = fm.get('first_motion', {})
    lines.append(f"    初动极性:")
    lines.append(f"      Z分量: {first_motion.get('Z', 'N/A')} ({first_motion.get('Z_amp', 0):.3f})")
    lines.append(f"      N分量: {first_motion.get('N', 'N/A')} ({first_motion.get('N_amp', 0):.3f})")
    lines.append(f"      E分量: {first_motion.get('E', 'N/A')} ({first_motion.get('E_amp', 0):.3f})")
    lines.append(f"      整体: {first_motion.get('overall', 'N/A')}")

    quality = fm.get('overall_quality', 0)
    quality_level = fm.get('quality_level', 'poor')
    lines.append(f"    数据质量: {quality_level} ({quality:.2f})")

    mw_est = fm.get('moment_magnitude_estimate', 0)
    if mw_est > 0:
        lines.append(f"    矩震级估计: Mw{mw_est:.1f}")

    return lines
