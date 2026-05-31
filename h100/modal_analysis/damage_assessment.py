import numpy as np
from .damage_indicators import (
    modal_strain_energy,
    modal_strain_energy_change,
    mse_damage_index,
    flexibility_matrix,
    flexibility_based_damage_index,
    combined_damage_indicator,
    modal_energy_distribution,
)
from .env_correction import SimpleEnvCorrector


def locate_damage_elements(mse_di, flex_di, connectivity,
                           threshold_mse=0.1, threshold_flex=0.1,
                           use_combined=True, alpha=0.5):
    if use_combined:
        combined = combined_damage_indicator(mse_di, flex_di, alpha)
        di = combined
        threshold = threshold_mse
    else:
        di = mse_di
        threshold = threshold_mse
    n_elements = len(connectivity)
    damaged_elements = []
    for e in range(n_elements):
        if e < len(di) and di[e] > threshold:
            damaged_elements.append({
                'element_id': e,
                'node_i': connectivity[e][0],
                'node_j': connectivity[e][1],
                'damage_index': di[e],
                'mse_di': mse_di[e] if e < len(mse_di) else 0.0,
                'flex_di': flex_di[e] if e < len(flex_di) else 0.0,
                'severity': _classify_severity(di[e]),
            })
    damaged_elements.sort(key=lambda x: x['damage_index'], reverse=True)
    return damaged_elements, di


def locate_damage_nodes(damaged_elements, node_labels=None):
    if not damaged_elements:
        return [], {}
    node_damage = {}
    for elem in damaged_elements:
        for node in [elem['node_i'], elem['node_j']]:
            if node not in node_damage:
                node_damage[node] = {
                    'node_id': node,
                    'label': node_labels[node] if node_labels and node < len(node_labels) else f"Node_{node}",
                    'connected_elements': [],
                    'max_damage_index': 0.0,
                    'severity': 'none',
                }
            node_damage[node]['connected_elements'].append(elem['element_id'])
            if elem['damage_index'] > node_damage[node]['max_damage_index']:
                node_damage[node]['max_damage_index'] = elem['damage_index']
                node_damage[node]['severity'] = _classify_severity(elem['damage_index'])
    damaged_nodes = sorted(node_damage.values(), key=lambda x: x['max_damage_index'], reverse=True)
    return damaged_nodes, node_damage


def assess_stiffness_reduction(mode_shapes_baseline, mode_shapes_damaged,
                                natural_frequencies_baseline,
                                natural_frequencies_damaged,
                                connectivity, damaged_elements=None):
    n_elements = len(connectivity)
    n_modes = min(mode_shapes_baseline.shape[1], mode_shapes_damaged.shape[1])
    stiffness_reduction = np.zeros(n_elements)
    if n_modes == 0:
        return stiffness_reduction * 100, damaged_elements
    mse_baseline = modal_strain_energy(mode_shapes_baseline, connectivity)
    mse_damaged = modal_strain_energy(mode_shapes_damaged, connectivity)
    total_mse_baseline = np.sum(mse_baseline, axis=0)
    total_mse_damaged = np.sum(mse_damaged, axis=0)
    freq_ratio_sq = np.ones(n_modes)
    valid_modes = 0
    for m in range(n_modes):
        if natural_frequencies_baseline[m] > 1e-10 and natural_frequencies_damaged[m] > 0:
            ratio = (natural_frequencies_damaged[m] / natural_frequencies_baseline[m]) ** 2
            if 0.3 < ratio < 1.5:
                freq_ratio_sq[m] = ratio
                valid_modes += 1
    if valid_modes > 0:
        global_stiffness_change = 1.0 - np.mean(freq_ratio_sq[:valid_modes])
    else:
        global_stiffness_change = 0.15
    global_stiffness_change = max(0.01, min(global_stiffness_change, 0.8))
    mse_change = np.zeros(n_elements)
    for e in range(n_elements):
        if total_mse_baseline[e] > 1e-10:
            mse_change[e] = (total_mse_damaged[e] - total_mse_baseline[e]) / total_mse_baseline[e]
    positive_mse = np.maximum(mse_change, 0)
    if np.sum(positive_mse) > 1e-10:
        weights = positive_mse / np.sum(positive_mse)
    else:
        weights = np.ones(n_elements) / n_elements
    for e in range(n_elements):
        local_stiffness = global_stiffness_change * weights[e] * n_elements
        stiffness_reduction[e] = max(0.0, min(local_stiffness, 0.95))
    if damaged_elements is not None:
        for elem in damaged_elements:
            eid = elem['element_id']
            if eid < n_elements:
                elem['stiffness_reduction_pct'] = stiffness_reduction[eid] * 100
    return stiffness_reduction * 100, damaged_elements


def _classify_severity(damage_index):
    if damage_index < 0.05:
        return 'none'
    elif damage_index < 0.15:
        return 'mild'
    elif damage_index < 0.35:
        return 'moderate'
    elif damage_index < 0.60:
        return 'severe'
    else:
        return 'critical'


def assess_damage(mode_shapes_baseline, mode_shapes_damaged,
                   freqs_baseline, freqs_damaged,
                   damp_baseline, damp_damaged,
                   connectivity, node_labels=None,
                   threshold_mse=0.1, threshold_flex=0.1,
                   use_combined=True, alpha=0.5,
                   env_correction_config=None,
                   env_current=None, env_baseline=None):
    freqs_baseline_corrected = np.array(freqs_baseline)
    freqs_damaged_corrected = np.array(freqs_damaged)
    env_correction_applied = False
    env_correction_details = None
    if env_correction_config and env_correction_config.get('enable_correction', False):
        if env_current and env_baseline:
            method = env_correction_config.get('correction_method', 'simple')
            if method == 'simple':
                corrector = SimpleEnvCorrector(
                    temp_coeff=env_correction_config.get('temperature_coefficient', -0.004),
                    mc_coeff=env_correction_config.get('moisture_coefficient', -0.007)
                )
                freqs_baseline_corrected = corrector.correct_frequencies(
                    freqs_baseline,
                    env_baseline.get('temperature', 20.0),
                    env_baseline.get('moisture', 12.0),
                    env_correction_config.get('baseline_temperature', 20.0),
                    env_correction_config.get('baseline_moisture', 12.0)
                )
                freqs_damaged_corrected = corrector.correct_frequencies(
                    freqs_damaged,
                    env_current.get('temperature', 20.0),
                    env_current.get('moisture', 12.0),
                    env_correction_config.get('baseline_temperature', 20.0),
                    env_correction_config.get('baseline_moisture', 12.0)
                )
                env_correction_applied = True
                env_correction_details = {
                    'method': 'simple',
                    'baseline_temp': env_correction_config.get('baseline_temperature', 20.0),
                    'baseline_moisture': env_correction_config.get('baseline_moisture', 12.0),
                    'current_temp': env_current.get('temperature', 20.0),
                    'current_moisture': env_current.get('moisture', 12.0),
                    'freqs_before_baseline': np.array(freqs_baseline),
                    'freqs_after_baseline': freqs_baseline_corrected,
                    'freqs_before_current': np.array(freqs_damaged),
                    'freqs_after_current': freqs_damaged_corrected,
                }
    mse_baseline = modal_strain_energy(mode_shapes_baseline, connectivity)
    mse_damaged = modal_strain_energy(mode_shapes_damaged, connectivity)
    mse_di = mse_damage_index(mse_baseline, mse_damaged)
    F_baseline = flexibility_matrix(mode_shapes_baseline, freqs_baseline_corrected, damp_baseline)
    F_damaged = flexibility_matrix(mode_shapes_damaged, freqs_damaged_corrected, damp_damaged)
    flex_di, curvature_change = flexibility_based_damage_index(F_baseline, F_damaged)
    damaged_elements, di = locate_damage_elements(
        mse_di, flex_di, connectivity, threshold_mse, threshold_flex,
        use_combined, alpha
    )
    damaged_nodes, node_damage_dict = locate_damage_nodes(damaged_elements, node_labels)
    stiffness_reduction_pct, damaged_elements = assess_stiffness_reduction(
        mode_shapes_baseline, mode_shapes_damaged,
        freqs_baseline_corrected, freqs_damaged_corrected, connectivity, damaged_elements
    )
    energy_dist_baseline = modal_energy_distribution(mode_shapes_baseline, connectivity)
    energy_dist_damaged = modal_energy_distribution(mode_shapes_damaged, connectivity)
    return {
        'damaged_elements': damaged_elements,
        'damaged_nodes': damaged_nodes,
        'stiffness_reduction_pct': stiffness_reduction_pct,
        'mse_damage_index': mse_di,
        'flex_damage_index': flex_di,
        'combined_damage_index': di if use_combined else None,
        'curvature_change': curvature_change,
        'energy_distribution_baseline': energy_dist_baseline,
        'energy_distribution_damaged': energy_dist_damaged,
        'threshold_mse': threshold_mse,
        'threshold_flex': threshold_flex,
        'use_combined': use_combined,
        'alpha': alpha,
        'env_correction_applied': env_correction_applied,
        'env_correction_details': env_correction_details,
    }


def generate_damage_report(damage_assessment, modal_params_baseline,
                            modal_params_damaged, node_positions=None,
                            node_labels=None, output_dir=None):
    report = {
        'summary': {},
        'modal_comparison': [],
        'damage_elements': damage_assessment['damaged_elements'],
        'damage_nodes': damage_assessment['damaged_nodes'],
        'stiffness_reduction': damage_assessment['stiffness_reduction_pct'].tolist(),
        'env_correction': damage_assessment.get('env_correction_applied', False),
        'env_correction_details': damage_assessment.get('env_correction_details'),
    }
    n_damaged = len(damage_assessment['damaged_elements'])
    n_elements = len(damage_assessment['stiffness_reduction_pct'])
    report['summary'] = {
        'total_elements': n_elements,
        'damaged_elements_count': n_damaged,
        'damage_ratio': n_damaged / n_elements if n_elements > 0 else 0,
        'max_stiffness_reduction_pct': float(np.max(damage_assessment['stiffness_reduction_pct'])),
        'average_stiffness_reduction_pct': float(np.mean(damage_assessment['stiffness_reduction_pct'])),
        'env_correction_applied': damage_assessment.get('env_correction_applied', False),
    }
    n_modes = min(len(modal_params_baseline['natural_frequencies']),
                  len(modal_params_damaged['natural_frequencies']))
    for i in range(n_modes):
        report['modal_comparison'].append({
            'mode': i + 1,
            'baseline_freq_hz': modal_params_baseline['natural_frequencies'][i],
            'damaged_freq_hz': modal_params_damaged['natural_frequencies'][i],
            'freq_change_pct': 100 * (modal_params_damaged['natural_frequencies'][i] -
                                        modal_params_baseline['natural_frequencies'][i]) /
                               (modal_params_baseline['natural_frequencies'][i] + 1e-10),
            'baseline_damping': modal_params_baseline['damping_ratios'][i],
            'damaged_damping': modal_params_damaged['damping_ratios'][i],
        })
    return report

