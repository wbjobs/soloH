#!/usr/bin/env python3
"""
Structural Damage Detection Tool - NExT-ERA
============================================
基于环境振动响应的结构模态分析与损伤检测命令行工具

Usage:
    python main.py analyze --baseline <file> --current <file> --config <config.yaml>
    python main.py identify --data <file> --config <config.yaml>
    python main.py demo --scenario <damage_scenario>
    python main.py report --data-dir <dir>

Features:
    - 模态参数识别 (NExT-ERA): 频率、阻尼比、振型
    - 损伤指标计算: 模态应变能变化 (MSE), 柔度曲率
    - 损伤定位: 梁/柱节点
    - 损伤程度评估: 刚度折减百分比
    - 损伤报告: 可视化标注损伤位置
    - 支持风激励、微震激励等环境振动
    - 低信噪比数据处理
"""

import argparse
import sys
import os
import json
import numpy as np
from pathlib import Path
from datetime import datetime

from modal_analysis.preprocessing import preprocess, estimate_snr
from modal_analysis.next import (
    next_cross_correlation,
    next_segmented,
    next_extract_impulse_response,
    next_hankel_matrix,
)
from modal_analysis.era import (
    era_system_realization,
    era_modal_params,
    era_stabilization_diagram,
)
from modal_analysis.modal_params import (
    normalize_mode_shapes,
    mac_matrix,
    match_modes,
)
from modal_analysis.damage_assessment import (
    assess_damage,
    generate_damage_report,
)
from modal_analysis.visualization import (
    generate_report_figures,
    generate_html_report,
    plot_mode_shapes,
    plot_damage_elements,
    plot_damage_indices,
    plot_stiffness_reduction,
    plot_frequency_comparison,
    plot_stabilization_diagram,
    plot_impulse_response,
)
from modal_analysis.utils import (
    load_acceleration_data,
    load_config,
    parse_connectivity,
    parse_node_positions,
    parse_node_labels,
    get_default_config,
    merge_config,
    generate_synthetic_data,
)
from modal_analysis.peak_picking import (
    identify_modal_parameters,
    peak_picking_identification,
    ssi_cov_identification,
)
from modal_analysis.sensor_optimization import SensorOptimizer
from modal_analysis.nonlinear_damage import NonlinearDamageDetector, nonlinear_feature_vector
from modal_analysis.transfer_learning import (
    TransferDamageClassifier,
    CrossStructureKnowledgeBase,
    extract_damage_feature_vector,
)


def cmd_analyze(args):
    print("=" * 60)
    print("Structural Damage Detection - NExT-ERA Analysis")
    print("=" * 60)
    config = get_default_config()
    if args.config:
        user_config = load_config(args.config)
        config = merge_config(config, user_config)
    print(f"\n[1/6] Loading data...")
    baseline_data = load_acceleration_data(args.baseline)
    current_data = load_acceleration_data(args.current)
    fs = config['data']['sampling_rate']
    n_samples_base, n_channels_base = baseline_data.shape
    n_samples_curr, n_channels_curr = current_data.shape
    print(f"  Baseline: {n_samples_base} samples x {n_channels_base} channels")
    print(f"  Current:  {n_samples_curr} samples x {n_channels_curr} channels")
    print(f"  Sampling rate: {fs} Hz")
    snr_base = estimate_snr(baseline_data[:, 0], fs)
    snr_curr = estimate_snr(current_data[:, 0], fs)
    print(f"  SNR (Baseline, Ch1): {snr_base:.1f} dB")
    print(f"  SNR (Current, Ch1):  {snr_curr:.1f} dB")
    print(f"\n[2/6] Preprocessing...")
    pre_cfg = config['preprocessing']
    baseline_processed = preprocess(
        baseline_data, fs,
        detrend_method=pre_cfg['detrend_method'],
        filter_type=pre_cfg['filter_type'],
        lowcut=pre_cfg['lowcut'],
        highcut=pre_cfg['highcut'],
        filter_order=pre_cfg['filter_order'],
        ma_window=pre_cfg['ma_window'],
    )
    current_processed = preprocess(
        current_data, fs,
        detrend_method=pre_cfg['detrend_method'],
        filter_type=pre_cfg['filter_type'],
        lowcut=pre_cfg['lowcut'],
        highcut=pre_cfg['highcut'],
        filter_order=pre_cfg['filter_order'],
        ma_window=pre_cfg['ma_window'],
    )
    print(f"  Detrend: {pre_cfg['detrend_method']}")
    print(f"  Filter:  {pre_cfg['filter_type']} [{pre_cfg['lowcut']}-{pre_cfg['highcut']} Hz]")
    print(f"\n[3/6] Modal parameter identification (Peak-Picking)...")
    modal_cfg = config['modal']
    method = modal_cfg.get('method', 'peak_picking')
    modal_baseline = identify_modal_parameters(
        baseline_processed, fs, method=method,
        freq_range=(pre_cfg['lowcut'] * 0.5, pre_cfg['highcut'] * 1.5),
        n_peaks_max=modal_cfg.get('n_peaks_max', 10),
    )
    modal_current = identify_modal_parameters(
        current_processed, fs, method=method,
        freq_range=(pre_cfg['lowcut'] * 0.5, pre_cfg['highcut'] * 1.5),
        n_peaks_max=modal_cfg.get('n_peaks_max', 10),
    )
    freqs_base = modal_baseline['natural_frequencies']
    freqs_curr = modal_current['natural_frequencies']
    damp_base = modal_baseline['damping_ratios']
    damp_curr = modal_current['damping_ratios']
    modes_base = normalize_mode_shapes(modal_baseline['mode_shapes'])
    modes_curr = normalize_mode_shapes(modal_current['mode_shapes'])
    print(f"  Baseline identified modes: {len(freqs_base)}")
    for i, f in enumerate(freqs_base):
        print(f"    Mode {i+1}: {f:.4f} Hz, damping: {damp_base[i]:.4f}")
    print(f"  Current identified modes: {len(freqs_curr)}")
    for i, f in enumerate(freqs_curr):
        print(f"    Mode {i+1}: {f:.4f} Hz, damping: {damp_curr[i]:.4f}")
    print(f"\n[4/6] Damage assessment...")
    struct_cfg = config['structure']
    connectivity = parse_connectivity(struct_cfg['connectivity'])
    node_positions = parse_node_positions(struct_cfg.get('node_positions'))
    node_labels = parse_node_labels(struct_cfg.get('node_labels'))
    if not connectivity:
        n_nodes = baseline_processed.shape[1]
        connectivity = [(i, i+1) for i in range(n_nodes - 1)]
        print(f"  Using default connectivity: chain of {n_nodes} nodes")
    damage_cfg = config['damage']
    damage_assessment = assess_damage(
        modes_base, modes_curr,
        freqs_base, freqs_curr,
        damp_base, damp_curr,
        connectivity, node_labels,
        threshold_mse=damage_cfg['threshold_mse'],
        threshold_flex=damage_cfg['threshold_flex'],
        use_combined=damage_cfg['use_combined'],
        alpha=damage_cfg['alpha'],
    )
    damage_report = generate_damage_report(
        damage_assessment, modal_baseline, modal_current,
        node_positions, node_labels,
    )
    n_damaged = len(damage_assessment['damaged_elements'])
    max_stiff = np.max(damage_assessment['stiffness_reduction_pct'])
    print(f"  Damaged elements: {n_damaged}/{len(connectivity)}")
    print(f"  Max stiffness reduction: {max_stiff:.1f}%")
    if damage_assessment['damaged_elements']:
        print(f"  Top damaged elements:")
        for elem in damage_assessment['damaged_elements'][:5]:
            print(f"    Element {elem['element_id']}: "
                  f"DI={elem['damage_index']:.3f}, "
                  f"stiffness_reduction={elem.get('stiffness_reduction_pct', 0):.1f}%, "
                  f"severity={elem['severity']}")
    print(f"\n[5/6] Generating figures...")
    output_dir = config['output']['directory']
    os.makedirs(output_dir, exist_ok=True)
    figure_paths = generate_report_figures(
        damage_assessment, modal_baseline, modal_current,
        connectivity, node_positions, node_labels,
        output_dir,
    )
    for name, path in figure_paths.items():
        print(f"  {name}: {path}")
    print(f"\n[6/6] Generating report...")
    report_path, json_path = generate_html_report(
        damage_assessment, damage_report,
        modal_baseline, modal_current,
        figure_paths, output_dir, config,
    )
    print(f"\n{'=' * 60}")
    print(f"Analysis Complete!")
    print(f"  HTML Report: {report_path}")
    print(f"  JSON Data:   {json_path}")
    print(f"  Figures:     {output_dir}")
    print(f"{'=' * 60}")
    return {
        'damage_assessment': damage_assessment,
        'damage_report': damage_report,
        'modal_baseline': modal_baseline,
        'modal_current': modal_current,
        'report_path': report_path,
        'json_path': json_path,
    }


def cmd_identify(args):
    print("=" * 60)
    print("Modal Parameter Identification - NExT-ERA")
    print("=" * 60)
    config = get_default_config()
    if args.config:
        user_config = load_config(args.config)
        config = merge_config(config, user_config)
    print(f"\n[1/4] Loading data...")
    data = load_acceleration_data(args.data)
    fs = config['data']['sampling_rate']
    n_samples, n_channels = data.shape
    print(f"  Data: {n_samples} samples x {n_channels} channels")
    print(f"  Sampling rate: {fs} Hz")
    snr = estimate_snr(data[:, 0], fs)
    print(f"  SNR (Ch1): {snr:.1f} dB")
    print(f"\n[2/4] Preprocessing...")
    pre_cfg = config['preprocessing']
    processed = preprocess(
        data, fs,
        detrend_method=pre_cfg['detrend_method'],
        filter_type=pre_cfg['filter_type'],
        lowcut=pre_cfg['lowcut'],
        highcut=pre_cfg['highcut'],
        filter_order=pre_cfg['filter_order'],
        ma_window=pre_cfg['ma_window'],
    )
    print(f"\n[3/4] Running modal identification (Peak-Picking)...")
    modal_cfg = config['modal']
    method = modal_cfg.get('method', 'peak_picking')
    modal_params = identify_modal_parameters(
        processed, fs, method=method,
        freq_range=(pre_cfg['lowcut'] * 0.5, pre_cfg['highcut'] * 1.5),
        n_peaks_max=modal_cfg.get('n_peaks_max', 10),
    )
    freqs = modal_params['natural_frequencies']
    damp = modal_params['damping_ratios']
    modes = normalize_mode_shapes(modal_params['mode_shapes'])
    print(f"\n[4/4] Results:")
    print(f"  Method: {method}")
    print(f"  Identified modes: {len(freqs)}")
    print(f"  {'Mode':<8} {'Frequency (Hz)':<18} {'Damping':<12} {'Period (s)':<12}")
    print(f"  {'-'*50}")
    for i in range(len(freqs)):
        period = 1.0 / freqs[i] if freqs[i] > 0 else float('inf')
        print(f"  {i+1:<8} {freqs[i]:<18.4f} {damp[i]:<12.4f} {period:<12.4f}")
    if args.output:
        output_dir = args.output
        os.makedirs(output_dir, exist_ok=True)
        np.save(os.path.join(output_dir, 'natural_frequencies.npy'), freqs)
        np.save(os.path.join(output_dir, 'damping_ratios.npy'), damp)
        np.save(os.path.join(output_dir, 'mode_shapes.npy'), modes)
        fig = plot_mode_shapes(modes, freqs, title="Identified Mode Shapes",
                               save_path=os.path.join(output_dir, 'mode_shapes.png'))
        print(f"\n  Results saved to: {output_dir}")
    return {
        'natural_frequencies': freqs,
        'damping_ratios': damp,
        'mode_shapes': modes,
        'method': method,
    }


def cmd_demo(args):
    print("=" * 60)
    print("Structural Damage Detection - Demo Mode")
    print("=" * 60)
    n_channels = 12
    n_samples = 20000
    fs = 100.0
    natural_freqs = [1.2, 2.8, 5.0, 7.5]
    damping_ratios = [0.02, 0.025, 0.03, 0.035]
    mode_shapes_true = np.zeros((n_channels, len(natural_freqs)))
    for m in range(len(natural_freqs)):
        for i in range(n_channels):
            mode_shapes_true[i, m] = np.sin((m + 1) * np.pi * (i + 0.5) / n_channels)
        max_val = np.max(np.abs(mode_shapes_true[:, m]))
        if max_val > 0:
            mode_shapes_true[:, m] /= max_val
    baseline_temp = getattr(args, 'baseline_temp', 20.0)
    baseline_mc = getattr(args, 'baseline_mc', 12.0)
    current_temp = getattr(args, 'current_temp', 20.0)
    current_mc = getattr(args, 'current_mc', 12.0)
    enable_env_correction = not getattr(args, 'no_env_correction', False)
    print(f"\n[1/5] Generating synthetic baseline data...")
    print(f"  Baseline conditions: {baseline_temp}°C, {baseline_mc}% MC")
    baseline_data, baseline_true = generate_synthetic_data(
        n_channels=n_channels, n_samples=n_samples, fs=fs,
        natural_freqs=natural_freqs, damping_ratios=damping_ratios,
        mode_shapes=mode_shapes_true.copy(), noise_level=0.05,
        temperature_celsius=baseline_temp,
        moisture_content_pct=baseline_mc,
    )
    print(f"  Generated: {n_samples} samples x {n_channels} channels")
    print(f"  Noise level: 5%")
    print(f"  True frequencies: {natural_freqs}")
    print(f"  Environment-shifted frequencies: {[f'{f:.3f}' for f in baseline_true['natural_frequencies']]}")
    scenario = args.scenario
    if scenario == 'mild':
        damage_info = {'element': 4, 'severity': 0.15, 'freq_scale': 0.97}
        print(f"\n  Damage scenario: MILD (element 4, 15% stiffness reduction)")
    elif scenario == 'moderate':
        damage_info = {'element': 6, 'severity': 0.30, 'freq_scale': 0.92}
        print(f"\n  Damage scenario: MODERATE (element 6, 30% stiffness reduction)")
    elif scenario == 'severe':
        damage_info = {'element': 8, 'severity': 0.50, 'freq_scale': 0.85}
        print(f"\n  Damage scenario: SEVERE (element 8, 50% stiffness reduction)")
    else:
        damage_info = {'element': 5, 'severity': 0.25, 'freq_scale': 0.95}
        print(f"\n  Damage scenario: DEFAULT (element 5, 25% stiffness reduction)")
    print(f"\n[2/5] Generating synthetic damaged data...")
    print(f"  Current conditions: {current_temp}°C, {current_mc}% MC")
    current_data, current_true = generate_synthetic_data(
        n_channels=n_channels, n_samples=n_samples, fs=fs,
        natural_freqs=natural_freqs, damping_ratios=damping_ratios,
        mode_shapes=mode_shapes_true.copy(), noise_level=0.05,
        damage_scenario=damage_info,
        temperature_celsius=current_temp,
        moisture_content_pct=current_mc,
    )
    print(f"  True damaged frequencies (raw): {[f'{f:.3f}' for f in current_true['natural_frequencies_reference']]}")
    print(f"  Environment-shifted damaged frequencies: {[f'{f:.3f}' for f in current_true['natural_frequencies']]}")
    env_shift_pct = (current_true.get('frequency_scale_env', 1.0) - 1.0) * 100
    if abs(env_shift_pct) > 0.01:
        print(f"  Environmental frequency shift: {env_shift_pct:+.2f}%")
    print(f"\n[3/5] Running modal identification (Peak-Picking)...")
    baseline_pp = preprocess(baseline_data, fs, lowcut=0.1, highcut=15.0)
    current_pp = preprocess(current_data, fs, lowcut=0.1, highcut=15.0)
    modal_base = peak_picking_identification(
        baseline_pp, fs, freq_range=(0.5, 15.0), n_peaks_max=8,
        peak_height=0.002, min_peak_distance=0.3, min_channels=2,
    )
    modal_curr = peak_picking_identification(
        current_pp, fs, freq_range=(0.5, 15.0), n_peaks_max=8,
        peak_height=0.002, min_peak_distance=0.3, min_channels=2,
    )
    freqs_base_all = modal_base['natural_frequencies']
    freqs_curr_all = modal_curr['natural_frequencies']
    damp_base_all = modal_base['damping_ratios']
    damp_curr_all = modal_curr['damping_ratios']
    modes_base_all = normalize_mode_shapes(modal_base['mode_shapes'])
    modes_curr_all = normalize_mode_shapes(modal_curr['mode_shapes'])
    matched = match_modes(modes_base_all, modes_curr_all,
                           freqs_base_all, freqs_curr_all,
                           freq_tolerance=0.20, mac_threshold=0.3)
    if matched:
        base_idx = [p[0] for p in matched]
        curr_idx = [p[1] for p in matched]
        freqs_base = freqs_base_all[base_idx]
        freqs_curr = freqs_curr_all[curr_idx]
        damp_base = damp_base_all[base_idx]
        damp_curr = damp_curr_all[curr_idx]
        modes_base = modes_base_all[:, base_idx]
        modes_curr = modes_curr_all[:, curr_idx]
    else:
        freqs_base = freqs_base_all
        freqs_curr = freqs_curr_all
        damp_base = damp_base_all
        damp_curr = damp_curr_all
        modes_base = modes_base_all
        modes_curr = modes_curr_all
    print(f"  Baseline identified modes: {len(freqs_base_all)} (matched: {len(freqs_base)})")
    for i in range(min(len(freqs_base_all), 6)):
        print(f"    Mode {i+1}: {freqs_base_all[i]:.4f} Hz, damping: {damp_base_all[i]:.4f}")
    print(f"  Current identified modes: {len(freqs_curr_all)} (matched: {len(freqs_curr)})")
    for i in range(min(len(freqs_curr_all), 6)):
        print(f"    Mode {i+1}: {freqs_curr_all[i]:.4f} Hz, damping: {damp_curr_all[i]:.4f}")
    if matched:
        print(f"  Matched mode pairs: {len(matched)}")
        for i, (b, c) in enumerate(matched):
            print(f"    Base {b+1} ({freqs_base_all[b]:.2f} Hz) <-> Curr {c+1} ({freqs_curr_all[c]:.2f} Hz)")
    print(f"\n[4/5] Damage assessment...")
    if enable_env_correction:
        print(f"  Environmental correction: ENABLED")
        print(f"    Baseline: {baseline_temp}°C, {baseline_mc}% MC")
        print(f"    Current:  {current_temp}°C, {current_mc}% MC")
    else:
        print(f"  Environmental correction: DISABLED")
    connectivity = [(i, i+1) for i in range(n_channels - 1)]
    node_positions = {i: (float(i), 0.0) for i in range(n_channels)}
    node_labels = [f"N{i+1}" for i in range(n_channels)]
    env_correction_config = {
        'enable_correction': enable_env_correction,
        'correction_method': 'simple',
        'baseline_temperature': 20.0,
        'baseline_moisture': 12.0,
        'temperature_coefficient': -0.004,
        'moisture_coefficient': -0.007,
    }
    env_baseline = {
        'temperature': baseline_temp,
        'moisture': baseline_mc,
    }
    env_current = {
        'temperature': current_temp,
        'moisture': current_mc,
    }
    damage_assessment = assess_damage(
        modes_base, modes_curr,
        freqs_base, freqs_curr,
        damp_base, damp_curr,
        connectivity, node_labels,
        threshold_mse=0.1, threshold_flex=0.1,
        use_combined=True, alpha=0.5,
        env_correction_config=env_correction_config,
        env_baseline=env_baseline,
        env_current=env_current,
    )
    if damage_assessment.get('env_correction_applied'):
        details = damage_assessment['env_correction_details']
        print(f"  Frequency correction applied:")
        for i in range(min(4, len(details['freqs_before_current']))):
            before = details['freqs_before_current'][i]
            after = details['freqs_after_current'][i]
            print(f"    Mode {i+1}: {before:.3f} -> {after:.3f} Hz ({(after-before)/before*100:+.2f}%)")
    damage_report = generate_damage_report(
        damage_assessment, modal_base, modal_curr,
        node_positions, node_labels,
    )
    n_damaged = len(damage_assessment['damaged_elements'])
    max_stiff = np.max(damage_assessment['stiffness_reduction_pct'])
    true_damage_element = damage_info['element']
    detected = False
    for elem in damage_assessment['damaged_elements']:
        if elem['element_id'] == true_damage_element or \
           elem['element_id'] == true_damage_element - 1:
            detected = True
            break
    print(f"  True damaged element: {true_damage_element}")
    print(f"  Damaged elements found: {n_damaged}/{len(connectivity)}")
    print(f"  Max stiffness reduction: {max_stiff:.1f}%")
    print(f"  True damage correctly identified: {'YES' if detected else 'NO'}")
    if damage_assessment['damaged_elements']:
        print(f"  Top damaged elements:")
        for elem in damage_assessment['damaged_elements'][:5]:
            marker = " <-- TRUE" if (elem['element_id'] == true_damage_element or
                                       elem['element_id'] == true_damage_element - 1) else ""
            print(f"    Element {elem['element_id']}: "
                  f"DI={elem['damage_index']:.3f}, "
                  f"stiffness_reduction={elem.get('stiffness_reduction_pct', 0):.1f}%, "
                  f"severity={elem['severity']}{marker}")
    print(f"\n[5/5] Generating report...")
    output_dir = args.output or "./demo_output"
    os.makedirs(output_dir, exist_ok=True)
    figure_paths = generate_report_figures(
        damage_assessment, modal_base, modal_curr,
        connectivity, node_positions, node_labels,
        output_dir,
    )
    report_path, json_path = generate_html_report(
        damage_assessment, damage_report,
        modal_base, modal_curr,
        figure_paths, output_dir,
    )
    print(f"\n{'=' * 60}")
    print(f"Demo Complete!")
    print(f"  HTML Report: {report_path}")
    print(f"  JSON Data:   {json_path}")
    print(f"  Figures:     {output_dir}")
    print(f"{'=' * 60}")
    return {
        'damage_assessment': damage_assessment,
        'damage_report': damage_report,
        'report_path': report_path,
        'json_path': json_path,
    }


def cmd_optimize_sensors(args):
    print("=" * 60)
    print("Sensor Optimization - Information Entropy Criterion")
    print("=" * 60)
    config = get_default_config()
    if args.config:
        user_config = load_config(args.config)
        config = merge_config(config, user_config)
    print(f"\n[1/4] Generating mode shapes...")
    n_total_sensors = args.n_total or 12
    n_modes = args.n_modes or 4
    mode_shapes = np.zeros((n_total_sensors, n_modes))
    for m in range(n_modes):
        for i in range(n_total_sensors):
            mode_shapes[i, m] = np.sin((m + 1) * np.pi * (i + 0.5) / n_total_sensors)
        max_val = np.max(np.abs(mode_shapes[:, m]))
        if max_val > 0:
            mode_shapes[:, m] /= max_val
    print(f"  Total candidate positions: {n_total_sensors}")
    print(f"  Number of modes: {n_modes}")
    n_sensors = args.n_sensors or config['sensor_optimization']['n_sensors']
    criterion = args.criterion or config['sensor_optimization']['criterion']
    method = args.method or config['sensor_optimization']['method']
    print(f"\n[2/4] Running optimization...")
    print(f"  Target sensor count: {n_sensors}")
    print(f"  Criterion: {criterion}")
    print(f"  Method: {method}")
    optimizer = SensorOptimizer(
        mode_shapes,
        measurement_noise_var=config['sensor_optimization']['measurement_noise_var']
    )
    if method == 'sequential_forward':
        result = optimizer.sequential_forward_selection(n_sensors, criterion)
    elif method == 'sequential_backward':
        result = optimizer.sequential_backward_selection(n_sensors, criterion)
    elif method == 'effective_independence':
        result = optimizer.effective_independence_method(n_sensors)
    elif method == 'brute_force':
        result = optimizer.brute_force(min(n_sensors, 8), criterion)
    else:
        result = optimizer.sequential_forward_selection(n_sensors, criterion)
    print(f"\n[3/4] Optimization Results:")
    print(f"  Selected sensors: {result['selected_sensors']}")
    print(f"  Objective value: {result['objective_value']:.4f}")
    eval_result = optimizer.evaluate_configuration(result['selected_sensors'])
    print(f"  D-optimal: {eval_result['d_optimal']:.4f}")
    print(f"  Shannon entropy: {eval_result['shannon_entropy']:.4f}")
    print(f"  Condition number: {eval_result['condition_number']:.2f}")
    print(f"\n[4/4] Generating configuration report...")
    output_dir = args.output or "./sensor_optimization"
    os.makedirs(output_dir, exist_ok=True)
    import json
    report = {
        'n_total_candidates': int(n_total_sensors),
        'n_selected': int(n_sensors),
        'criterion': criterion,
        'method': method,
        'selected_sensors': [int(s) for s in result['selected_sensors']],
        'objective_value': float(result['objective_value']),
        'evaluation': {
            'd_optimal': float(eval_result['d_optimal']),
            'a_optimal': float(eval_result['a_optimal']),
            'e_optimal': float(eval_result['e_optimal']),
            'shannon_entropy': float(eval_result['shannon_entropy']),
            'condition_number': float(eval_result['condition_number']),
        }
    }
    report_path = os.path.join(output_dir, 'sensor_config.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"  Configuration saved to: {report_path}")
    print(f"\n{'=' * 60}")
    print(f"Sensor Optimization Complete!")
    print(f"{'=' * 60}")
    return report


def cmd_detect_nonlinear(args):
    print("=" * 60)
    print("Nonlinear Damage Detection - Breathing Crack Analysis")
    print("=" * 60)
    config = get_default_config()
    if args.config:
        user_config = load_config(args.config)
        config = merge_config(config, user_config)
    print(f"\n[1/4] Loading data...")
    data = load_acceleration_data(args.data)
    fs = config['data']['sampling_rate']
    n_samples, n_channels = data.shape
    print(f"  Data: {n_samples} samples x {n_channels} channels")
    print(f"  Sampling rate: {fs} Hz")
    print(f"\n[2/4] Running nonlinear feature extraction...")
    detector = NonlinearDamageDetector(
        threshold_quantile=config['nonlinear_damage']['threshold_quantile']
    )
    if args.baseline:
        print(f"  Fitting baseline from: {args.baseline}")
        baseline_data = load_acceleration_data(args.baseline)
        baseline_signals = [baseline_data[:, ch] for ch in range(n_channels)]
        detector.fit_baseline(baseline_signals, fs)
        print(f"  Baseline thresholds computed")
    print(f"\n[3/4] Detecting nonlinear damage...")
    result = detector.detect_multichannel(data, fs)
    print(f"\n[4/4] Analysis Results:")
    print(f"  Overall crack likelihood: {result['overall_crack_likelihood']:.3f}")
    print(f"  Overall severity: {result['overall_severity'].upper()}")
    print(f"  Most likely channel: {result['most_likely_channel']}")
    print(f"\n  Top 3 channels by likelihood:")
    for r in result['channel_results'][:3]:
        print(f"    Ch{r['channel']}: likelihood={r['crack_likelihood']:.3f}, "
              f"HHI={r['features']['higher_harmonic_index']:.3f}, "
              f"severity={r['severity']}")
    print(f"\n{'=' * 60}")
    print(f"Nonlinear Detection Complete!")
    print(f"{'=' * 60}")
    return result


def cmd_transfer_learn(args):
    print("=" * 60)
    print("Transfer Learning - Cross-Structure Damage Detection")
    print("=" * 60)
    config = get_default_config()
    if args.config:
        user_config = load_config(args.config)
        config = merge_config(config, user_config)
    fs = config['data']['sampling_rate']
    print(f"\n[1/5] Creating source domain knowledge base...")
    n_source_structures = args.n_sources or 3
    n_samples_per_struct = args.n_samples or 20
    kb = CrossStructureKnowledgeBase()
    for struct_id in range(n_source_structures):
        print(f"  Structure S{struct_id+1}: generating {n_samples_per_struct} samples...")
        features_list = []
        labels_list = []
        for sample_id in range(n_samples_per_struct):
            is_damaged = sample_id >= n_samples_per_struct // 2
            damage_severity = 0.3 if is_damaged else 0.0
            freq_scale = 0.92 if is_damaged else 1.0
            struct_data, _ = generate_synthetic_data(
                n_channels=8, n_samples=5000, fs=fs,
                natural_freqs=[1.2 + struct_id * 0.2, 2.8 + struct_id * 0.3, 5.0],
                noise_level=0.05,
                damage_scenario={'element': 3, 'severity': damage_severity, 'freq_scale': freq_scale} if is_damaged else None
            )
            from scipy.signal import welch
            modal_params = {
                'natural_frequencies': [1.2 + struct_id * 0.2, 2.8 + struct_id * 0.3, 5.0],
                'damping_ratios': [0.02, 0.025, 0.03],
                'mode_shapes': np.zeros((8, 3))
            }
            features, _, _ = extract_damage_feature_vector(struct_data, fs, modal_params)
            feature_values = np.array(list(features.values()))
            features_list.append(feature_values)
            labels_list.append(1 if is_damaged else 0)
        kb.add_structure(f'S{struct_id+1}', features_list, labels_list,
                          metadata={'n_modes': 3, 'n_channels': 8})
    print(f"\n[2/5] Knowledge base created: {n_source_structures} structures")
    print(f"\n[3/5] Generating target structure data...")
    target_scaling = 1.15
    target_damage = args.target_damage
    target_data, _ = generate_synthetic_data(
        n_channels=8, n_samples=10000, fs=fs,
        natural_freqs=[1.2 * target_scaling, 2.8 * target_scaling, 5.0 * target_scaling],
        noise_level=0.06,
        damage_scenario={'element': 4, 'severity': target_damage, 'freq_scale': 1.0 - target_damage * 0.25} if target_damage > 0 else None
    )
    print(f"  Target structure: frequencies scaled by {target_scaling}")
    print(f"  Target damage severity: {target_damage}")
    print(f"\n[4/5] Running ensemble prediction...")
    target_modal = {
        'natural_frequencies': [1.2 * target_scaling, 2.8 * target_scaling, 5.0 * target_scaling],
        'damping_ratios': [0.02, 0.025, 0.03],
        'mode_shapes': np.zeros((8, 3))
    }
    target_features, _, _ = extract_damage_feature_vector(target_data, fs, target_modal)
    target_values = np.array(list(target_features.values()))
    prediction = kb.ensemble_predict(target_values.reshape(1, -1), target_sample=target_values)
    print(f"\n[5/5] Prediction Results:")
    print(f"  Ensemble damage index: {prediction['ensemble_damage_index'][0]:.4f}")
    print(f"  Ensemble damage detected: {'YES' if prediction['ensemble_is_damaged'][0] else 'NO'}")
    print(f"  Ensemble severity: {prediction['ensemble_severity'][0]:.3f}")
    print(f"\n  Individual structure predictions:")
    for pred in prediction['individual_predictions']:
        print(f"    {pred['structure_id']}: DI={pred['damage_index'][0]:.4f}, "
              f"damaged={'Y' if pred['is_damaged'][0] else 'N'}")
    print(f"\n{'=' * 60}")
    print(f"Transfer Learning Complete!")
    print(f"{'=' * 60}")
    return prediction


def main():
    parser = argparse.ArgumentParser(
        description="Structural Damage Detection Tool - NExT-ERA Method",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze damage by comparing baseline and current data
  python main.py analyze --baseline baseline.csv --current damaged.csv --config config.yaml

  # Identify modal parameters from a single dataset
  python main.py identify --data acceleration.csv --config config.yaml

  # Run demo with synthetic data
  python main.py demo --scenario moderate

  # Optimize sensor placement using information entropy
  python main.py optimize-sensors --n-sensors 8 --criterion d_optimal

  # Detect nonlinear damage (breathing cracks)
  python main.py detect-nonlinear --data damaged.csv --baseline baseline.csv

  # Cross-structure transfer learning damage detection
  python main.py transfer-learn --n-sources 3 --target-damage 0.3
        """,
    )
    subparsers = parser.add_subparsers(dest='command', help='Command')
    parser_analyze = subparsers.add_parser('analyze', help='Analyze damage by comparing datasets')
    parser_analyze.add_argument('--baseline', '-b', required=True,
                                 help='Path to baseline (healthy) acceleration data file')
    parser_analyze.add_argument('--current', '-c', required=True,
                                 help='Path to current (potentially damaged) data file')
    parser_analyze.add_argument('--config', '-cfg', default=None,
                                 help='Path to configuration file (YAML/JSON)')
    parser_analyze.add_argument('--output', '-o', default=None,
                                 help='Output directory for reports')
    parser_identify = subparsers.add_parser('identify', help='Identify modal parameters')
    parser_identify.add_argument('--data', '-d', required=True,
                                  help='Path to acceleration data file')
    parser_identify.add_argument('--config', '-cfg', default=None,
                                  help='Path to configuration file')
    parser_identify.add_argument('--output', '-o', default=None,
                                  help='Output directory for results')
    parser_demo = subparsers.add_parser('demo', help='Run demo with synthetic data')
    parser_demo.add_argument('--scenario', '-s', default='moderate',
                              choices=['mild', 'moderate', 'severe'],
                              help='Damage scenario: mild, moderate, severe')
    parser_demo.add_argument('--output', '-o', default=None,
                              help='Output directory')
    parser_demo.add_argument('--baseline-temp', type=float, default=20.0,
                              help='Baseline temperature (°C), default: 20.0')
    parser_demo.add_argument('--baseline-mc', type=float, default=12.0,
                              help='Baseline moisture content (%%), default: 12.0')
    parser_demo.add_argument('--current-temp', type=float, default=20.0,
                              help='Current temperature (°C), default: 20.0')
    parser_demo.add_argument('--current-mc', type=float, default=12.0,
                              help='Current moisture content (%%), default: 12.0')
    parser_demo.add_argument('--no-env-correction', action='store_true',
                              help='Disable environmental frequency correction')
    parser_optimize = subparsers.add_parser('optimize-sensors', help='Optimize sensor placement using information entropy')
    parser_optimize.add_argument('--n-sensors', '-n', type=int, default=None,
                                  help='Number of sensors to place')
    parser_optimize.add_argument('--n-total', '-t', type=int, default=None,
                                  help='Total candidate sensor positions')
    parser_optimize.add_argument('--n-modes', '-m', type=int, default=None,
                                  help='Number of modes to consider')
    parser_optimize.add_argument('--criterion', '-c', type=str, default=None,
                                  choices=['d_optimal', 'a_optimal', 'e_optimal', 'shannon_entropy', 'modmac'],
                                  help='Optimization criterion')
    parser_optimize.add_argument('--method', type=str, default=None,
                                  choices=['sequential_forward', 'sequential_backward', 'effective_independence', 'brute_force'],
                                  help='Optimization algorithm')
    parser_optimize.add_argument('--config', '-cfg', default=None,
                                  help='Path to configuration file')
    parser_optimize.add_argument('--output', '-o', default=None,
                                  help='Output directory')
    parser_nonlinear = subparsers.add_parser('detect-nonlinear', help='Detect nonlinear damage (breathing cracks)')
    parser_nonlinear.add_argument('--data', '-d', required=True,
                                   help='Path to acceleration data file')
    parser_nonlinear.add_argument('--baseline', '-b', default=None,
                                   help='Path to baseline data file for threshold calibration')
    parser_nonlinear.add_argument('--config', '-cfg', default=None,
                                   help='Path to configuration file')
    parser_transfer = subparsers.add_parser('transfer-learn', help='Cross-structure transfer learning damage detection')
    parser_transfer.add_argument('--n-sources', type=int, default=3,
                                  help='Number of source structures in knowledge base')
    parser_transfer.add_argument('--n-samples', type=int, default=20,
                                  help='Number of samples per source structure')
    parser_transfer.add_argument('--target-damage', type=float, default=0.3,
                                  help='Target structure damage severity (0-1)')
    parser_transfer.add_argument('--config', '-cfg', default=None,
                                  help='Path to configuration file')
    args = parser.parse_args()
    if args.command == 'analyze':
        cmd_analyze(args)
    elif args.command == 'identify':
        cmd_identify(args)
    elif args.command == 'demo':
        cmd_demo(args)
    elif args.command == 'optimize-sensors':
        cmd_optimize_sensors(args)
    elif args.command == 'detect-nonlinear':
        cmd_detect_nonlinear(args)
    elif args.command == 'transfer-learn':
        cmd_transfer_learn(args)
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
