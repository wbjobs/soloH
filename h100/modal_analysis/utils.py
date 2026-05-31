import numpy as np
import json
import csv
import os
from pathlib import Path


def load_acceleration_data(filepath):
    ext = Path(filepath).suffix.lower()
    if ext in ('.csv', '.txt'):
        return _load_csv(filepath)
    elif ext in ('.npy',):
        return np.load(filepath)
    elif ext in ('.json',):
        return _load_json(filepath)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def _load_csv(filepath, delimiter=','):
    data = []
    with open(filepath, 'r') as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader, None)
        for row in reader:
            try:
                data.append([float(x) for x in row])
            except (ValueError, IndexError):
                continue
    if not data:
        raise ValueError(f"No valid data in file: {filepath}")
    return np.array(data)


def _load_json(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
    if isinstance(data, dict) and 'data' in data:
        return np.array(data['data'])
    elif isinstance(data, list):
        return np.array(data)
    else:
        raise ValueError(f"Unsupported JSON format in: {filepath}")


def load_config(filepath):
    ext = Path(filepath).suffix.lower()
    with open(filepath, 'r') as f:
        if ext in ('.yaml', '.yml'):
            import yaml
            return yaml.safe_load(f)
        elif ext == '.json':
            return json.load(f)
        else:
            raise ValueError(f"Unsupported config format: {ext}")


def parse_connectivity(connectivity_config):
    if isinstance(connectivity_config, list):
        if all(isinstance(item, (list, tuple)) and len(item) == 2 for item in connectivity_config):
            return [(int(i), int(j)) for i, j in connectivity_config]
        else:
            raise ValueError("Connectivity must be list of [node_i, node_j] pairs")
    elif isinstance(connectivity_config, str):
        pairs = connectivity_config.split(';')
        result = []
        for pair in pairs:
            if '-' in pair:
                i, j = pair.split('-')
                result.append((int(i.strip()), int(j.strip())))
        return result
    raise ValueError(f"Unsupported connectivity format: {type(connectivity_config)}")


def parse_node_positions(positions_config):
    if positions_config is None:
        return None
    if isinstance(positions_config, dict):
        return {int(k): tuple(v) for k, v in positions_config.items()}
    elif isinstance(positions_config, list):
        return {i: tuple(pos) for i, pos in enumerate(positions_config)}
    return None


def parse_node_labels(labels_config):
    if labels_config is None:
        return None
    if isinstance(labels_config, list):
        return [str(l) for l in labels_config]
    return None


def get_default_config():
    return {
        'data': {
            'sampling_rate': 100.0,
            'segment_duration': 20.0,
            'overlap': 0.5,
        },
        'preprocessing': {
            'detrend_method': 'linear',
            'filter_type': 'bandpass',
            'lowcut': 0.1,
            'highcut': 20.0,
            'filter_order': 4,
            'ma_window': None,
        },
        'modal': {
            'model_order_min': 4,
            'model_order_max': 50,
            'block_rows': 20,
            'block_cols': 20,
            'freq_tolerance': 0.01,
            'damping_tolerance': 0.05,
            'mac_threshold': 0.90,
        },
        'damage': {
            'threshold_mse': 0.1,
            'threshold_flex': 0.1,
            'use_combined': True,
            'alpha': 0.5,
        },
        'transfer_learning': {
            'enable': False,
            'source_domains': [],
            'method': 'ensemble',
            'domain_adaptation': True,
            'fine_tune_samples': 5,
            'confidence_threshold': 0.95,
        },
        'nonlinear_damage': {
            'enable': True,
            'threshold_quantile': 0.95,
            'fundamental_freq': 'auto',
            'higher_harmonic_weight': 0.4,
            'breathing_crack_weight': 0.3,
            'energy_transfer_weight': 0.3,
        },
        'sensor_optimization': {
            'n_sensors': 8,
            'criterion': 'd_optimal',
            'method': 'sequential_forward',
            'measurement_noise_var': 0.01,
            'coverage_weight': 0.2,
            'redundancy_threshold': 0.9,
        },
        'timber': {
            'material': {
                'E_parallel': 12000e6,
                'E_perpendicular': 600e6,
                'G_parallel': 650e6,
                'density': 450.0,
                'poisson_ratio': 0.35,
            },
            'member': {
                'height': 0.2,
                'width': 0.1,
                'node_spacing': 1.0,
            },
            'joints': {
                'type': 'semi-rigid',
                'rotational_stiffness': 5e6,
                'translational_stiffness': 1e9,
            },
        },
        'environmental': {
            'enable_correction': True,
            'correction_method': 'simple',
            'baseline_temperature': 20.0,
            'baseline_moisture': 12.0,
            'temperature_coefficient': -0.004,
            'moisture_coefficient': -0.007,
            'confidence_level': 0.95,
        },
        'output': {
            'directory': './output',
            'format': 'png',
            'dpi': 150,
        },
        'structure': {
            'connectivity': [],
            'node_positions': None,
            'node_labels': None,
        },
    }


def merge_config(defaults, user_config):
    merged = defaults.copy()
    for key, value in user_config.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def generate_synthetic_data(n_channels=8, n_samples=10000, fs=100.0,
                             natural_freqs=None, damping_ratios=None,
                             mode_shapes=None, noise_level=0.05,
                             damage_scenario=None,
                             temperature_celsius=20.0,
                             moisture_content_pct=12.0,
                             temp_coeff=-0.004,
                             mc_coeff=-0.007):
    if natural_freqs is None:
        natural_freqs = [1.5, 3.2, 5.8, 8.1]
    if damping_ratios is None:
        damping_ratios = [0.02, 0.03, 0.025, 0.04]
    n_modes = len(natural_freqs)
    if mode_shapes is None:
        mode_shapes = np.zeros((n_channels, n_modes))
        for m in range(n_modes):
            for i in range(n_channels):
                mode_shapes[i, m] = np.sin((m + 1) * np.pi * (i + 1) / (n_channels + 1))
        for m in range(n_modes):
            max_val = np.max(np.abs(mode_shapes[:, m]))
            if max_val > 0:
                mode_shapes[:, m] /= max_val
    delta_T = temperature_celsius - 20.0
    delta_MC = moisture_content_pct - 12.0
    k_T = 1.0 + temp_coeff * delta_T
    k_MC = 1.0 + mc_coeff * delta_MC
    freq_scale = k_T * k_MC
    natural_freqs_env = [f * freq_scale for f in natural_freqs]
    if damage_scenario is not None:
        damaged_element = damage_scenario.get('element', None)
        severity = damage_scenario.get('severity', 0.3)
        if damaged_element is not None and damaged_element < n_channels - 1:
            for m in range(n_modes):
                mode_shapes[damaged_element, m] *= (1 - severity)
                if damaged_element + 1 < n_channels:
                    mode_shapes[damaged_element + 1, m] *= (1 - severity * 0.5)
        damage_freq_scale = damage_scenario.get('freq_scale', 1.0)
        natural_freqs_env = [f * damage_freq_scale for f in natural_freqs_env]
        natural_freqs = [f * damage_freq_scale for f in natural_freqs]
    t = np.arange(n_samples) / fs
    data = np.zeros((n_samples, n_channels))
    for m in range(n_modes):
        omega_n = 2 * np.pi * natural_freqs_env[m]
        omega_d = omega_n * np.sqrt(1 - damping_ratios[m] ** 2)
        zeta = damping_ratios[m]
        decay = np.exp(-zeta * omega_n * t)
        phase = 2 * np.pi * np.random.rand()
        amplitude = 1.0
        for i in range(n_channels):
            data[:, i] += mode_shapes[i, m] * amplitude * decay * np.sin(omega_d * t + phase)
    data += noise_level * np.random.randn(n_samples, n_channels)
    return data, {
        'natural_frequencies': natural_freqs_env,
        'natural_frequencies_reference': natural_freqs,
        'damping_ratios': damping_ratios,
        'mode_shapes': mode_shapes,
        'temperature': temperature_celsius,
        'moisture_content': moisture_content_pct,
        'frequency_scale_env': freq_scale,
    }
