import numpy as np
from scipy import stats
from scipy.optimize import curve_fit


def frequency_temperature_model(frequencies, temperatures, order=1):
    n_modes = len(frequencies[0]) if hasattr(frequencies[0], '__len__') else 1
    models = []
    for m in range(n_modes):
        if n_modes > 1:
            f_mode = [f[m] for f in frequencies]
        else:
            f_mode = frequencies
        coeffs = np.polyfit(temperatures, f_mode, order)
        models.append({
            'mode': m,
            'coefficients': coeffs,
            'order': order,
            'r_squared': r_squared(f_mode, np.polyval(coeffs, temperatures))
        })
    return models


def frequency_moisture_model(frequencies, moisture_contents, order=1):
    n_modes = len(frequencies[0]) if hasattr(frequencies[0], '__len__') else 1
    models = []
    for m in range(n_modes):
        if n_modes > 1:
            f_mode = [f[m] for f in frequencies]
        else:
            f_mode = frequencies
        coeffs = np.polyfit(moisture_contents, f_mode, order)
        models.append({
            'mode': m,
            'coefficients': coeffs,
            'order': order,
            'r_squared': r_squared(f_mode, np.polyval(coeffs, moisture_contents))
        })
    return models


def frequency_combined_model(frequencies, temperatures, moisture_contents,
                              interaction_term=True):
    n_samples = len(frequencies)
    n_modes = len(frequencies[0]) if hasattr(frequencies[0], '__len__') else 1
    models = []
    for m in range(n_modes):
        if n_modes > 1:
            f_mode = np.array([f[m] for f in frequencies])
        else:
            f_mode = np.array(frequencies)
        if interaction_term:
            X = np.column_stack([
                np.ones(n_samples),
                temperatures,
                moisture_contents,
                np.array(temperatures) * np.array(moisture_contents)
            ])
        else:
            X = np.column_stack([
                np.ones(n_samples),
                temperatures,
                moisture_contents
            ])
        coeffs, _, _, _ = np.linalg.lstsq(X, f_mode, rcond=None)
        f_pred = X @ coeffs
        models.append({
            'mode': m,
            'coefficients': coeffs,
            'interaction_term': interaction_term,
            'r_squared': r_squared(f_mode, f_pred)
        })
    return models


def r_squared(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0


class EnvFrequencyCorrector:
    def __init__(self, n_modes=4, correction_method='combined'):
        self.n_modes = n_modes
        self.correction_method = correction_method
        self.models = None
        self.baseline_temperature = 20.0
        self.baseline_moisture = 12.0
        self.temperature_history = []
        self.moisture_history = []
        self.frequency_history = []
        self.is_trained = False

    def add_measurement(self, frequencies, temperature, moisture_content):
        self.frequency_history.append(np.array(frequencies))
        self.temperature_history.append(temperature)
        self.moisture_history.append(moisture_content)
        self.is_trained = False

    def train(self, method='combined', order=1):
        if len(self.frequency_history) < 5:
            raise ValueError("Need at least 5 measurements to train the model")
        self.correction_method = method
        if method == 'temperature_only':
            self.models = frequency_temperature_model(
                self.frequency_history,
                self.temperature_history,
                order
            )
        elif method == 'moisture_only':
            self.models = frequency_moisture_model(
                self.frequency_history,
                self.moisture_history,
                order
            )
        elif method == 'combined':
            self.models = frequency_combined_model(
                self.frequency_history,
                self.temperature_history,
                self.moisture_history
            )
        else:
            raise ValueError(f"Unknown method: {method}")
        self.is_trained = True
        return self.models

    def predict_frequencies(self, temperature, moisture_content):
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")
        predicted = []
        for m, model in enumerate(self.models):
            if self.correction_method in ['temperature_only', 'moisture_only']:
                if self.correction_method == 'temperature_only':
                    pred = np.polyval(model['coefficients'], temperature)
                else:
                    pred = np.polyval(model['coefficients'], moisture_content)
            else:
                coeffs = model['coefficients']
                if model['interaction_term']:
                    pred = (coeffs[0] + coeffs[1] * temperature +
                            coeffs[2] * moisture_content +
                            coeffs[3] * temperature * moisture_content)
                else:
                    pred = (coeffs[0] + coeffs[1] * temperature +
                            coeffs[2] * moisture_content)
            predicted.append(pred)
        return np.array(predicted)

    def correct_frequencies(self, measured_frequencies, current_temperature,
                             current_moisture, target_temperature=None,
                             target_moisture=None):
        if target_temperature is None:
            target_temperature = self.baseline_temperature
        if target_moisture is None:
            target_moisture = self.baseline_moisture
        f_current_env = self.predict_frequencies(current_temperature, current_moisture)
        f_target_env = self.predict_frequencies(target_temperature, target_moisture)
        correction_factors = f_target_env / f_current_env
        corrected = np.array(measured_frequencies) * correction_factors
        return {
            'corrected_frequencies': corrected,
            'correction_factors': correction_factors,
            'predicted_current': f_current_env,
            'predicted_target': f_target_env,
            'current_temperature': current_temperature,
            'current_moisture': current_moisture,
            'target_temperature': target_temperature,
            'target_moisture': target_moisture
        }

    def estimate_damage_threshold(self, confidence_level=0.95):
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")
        residuals = []
        for i in range(len(self.frequency_history)):
            f_pred = self.predict_frequencies(
                self.temperature_history[i],
                self.moisture_history[i]
            )
            res = (self.frequency_history[i] - f_pred) / f_pred * 100
            residuals.append(res)
        residuals = np.array(residuals)
        thresholds = []
        for m in range(self.n_modes):
            mean_res = np.mean(residuals[:, m])
            std_res = np.std(residuals[:, m])
            z_score = stats.norm.ppf((1 + confidence_level) / 2)
            threshold = {
                'mode': m,
                'mean_residual_pct': mean_res,
                'std_residual_pct': std_res,
                'lower_pct': mean_res - z_score * std_res,
                'upper_pct': mean_res + z_score * std_res,
                'confidence_level': confidence_level
            }
            thresholds.append(threshold)
        return thresholds

    def is_significant_change(self, measured_frequencies, temperature,
                               moisture_content, confidence_level=0.95):
        thresholds = self.estimate_damage_threshold(confidence_level)
        corrected = self.correct_frequencies(
            measured_frequencies, temperature, moisture_content
        )
        baseline_freqs = self.predict_frequencies(
            self.baseline_temperature, self.baseline_moisture
        )
        change_pct = (corrected['corrected_frequencies'] - baseline_freqs) / baseline_freqs * 100
        significant = []
        for m in range(min(self.n_modes, len(change_pct))):
            is_sig = (change_pct[m] < thresholds[m]['lower_pct'] or
                      change_pct[m] > thresholds[m]['upper_pct'])
            significant.append({
                'mode': m,
                'change_pct': change_pct[m],
                'threshold_low_pct': thresholds[m]['lower_pct'],
                'threshold_high_pct': thresholds[m]['upper_pct'],
                'is_significant': is_sig
            })
        any_significant = any(s['is_significant'] for s in significant)
        return {
            'any_significant': any_significant,
            'mode_details': significant,
            'corrected_frequencies': corrected['corrected_frequencies'],
            'baseline_frequencies': baseline_freqs
        }


class SimpleEnvCorrector:
    def __init__(self, temp_coeff=-0.004, mc_coeff=-0.007):
        self.temp_coeff = temp_coeff
        self.mc_coeff = mc_coeff

    def correct_frequency(self, measured_freq, current_temp=20.0,
                           current_mc=12.0, ref_temp=20.0, ref_mc=12.0):
        delta_T = current_temp - ref_temp
        delta_MC = current_mc - ref_mc
        k_T = 1.0 / (1.0 + self.temp_coeff * delta_T)
        k_MC = 1.0 / (1.0 + self.mc_coeff * delta_MC)
        corrected = measured_freq * k_T * k_MC
        return corrected

    def correct_frequencies(self, measured_freqs, current_temp=20.0,
                             current_mc=12.0, ref_temp=20.0, ref_mc=12.0):
        return np.array([
            self.correct_frequency(f, current_temp, current_mc, ref_temp, ref_mc)
            for f in measured_freqs
        ])


def calculate_expected_frequency_shift(temperature_change=0.0,
                                        moisture_change=0.0,
                                        base_frequency=1.0):
    temp_coeff = -0.004
    mc_coeff = -0.007
    factor = (1.0 + temp_coeff * temperature_change) * (1.0 + mc_coeff * moisture_change)
    return base_frequency * factor
