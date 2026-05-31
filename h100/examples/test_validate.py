#!/usr/bin/env python3
"""
Validation test script for NExT-ERA structural damage detection tool.
Tests the complete pipeline with synthetic data.
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modal_analysis.utils import generate_synthetic_data
from modal_analysis.preprocessing import preprocess, estimate_snr
from modal_analysis.next import next_extract_impulse_response
from modal_analysis.era import era_system_realization, era_modal_params
from modal_analysis.modal_params import normalize_mode_shapes, mac
from modal_analysis.peak_picking import peak_picking_identification
from modal_analysis.damage_assessment import assess_damage, generate_damage_report
from modal_analysis.visualization import generate_report_figures, generate_html_report


def test_complete_pipeline():
    print("=" * 60)
    print("VALIDATION TEST: Complete NExT-ERA Pipeline")
    print("=" * 60)

    n_channels = 8
    n_samples = 15000
    fs = 100.0

    true_freqs = [1.0, 2.5, 4.5]
    true_damps = [0.02, 0.03, 0.025]

    print("\n[1] Generating synthetic data...")
    baseline_data, baseline_true = generate_synthetic_data(
        n_channels=n_channels, n_samples=n_samples, fs=fs,
        natural_freqs=true_freqs, damping_ratios=true_damps,
        noise_level=0.05,
    )
    damage_info = {'element': 3, 'severity': 0.30, 'freq_scale': 0.92}
    damaged_data, damaged_true = generate_synthetic_data(
        n_channels=n_channels, n_samples=n_samples, fs=fs,
        natural_freqs=true_freqs, damping_ratios=true_damps,
        noise_level=0.05,
        damage_scenario=damage_info,
    )
    print(f"  Baseline: {baseline_data.shape}")
    print(f"  Damaged:  {damaged_data.shape}")
    print(f"  True frequencies: {true_freqs}")
    print(f"  True damage: element 3, 30% stiffness reduction")

    print("\n[2] Preprocessing...")
    baseline_proc = preprocess(baseline_data, fs, lowcut=0.1, highcut=15.0)
    damaged_proc = preprocess(damaged_data, fs, lowcut=0.1, highcut=15.0)

    snr_base = estimate_snr(baseline_proc[:, 0], fs)
    snr_dam = estimate_snr(damaged_proc[:, 0], fs)
    print(f"  SNR baseline: {snr_base:.1f} dB")
    print(f"  SNR damaged:  {snr_dam:.1f} dB")

    print("\n[3] Peak-Picking modal identification...")
    modal_base = peak_picking_identification(baseline_proc, fs, freq_range=(0.05, 20.0), n_peaks_max=10)
    modal_dam = peak_picking_identification(damaged_proc, fs, freq_range=(0.05, 20.0), n_peaks_max=10)

    freqs_base = modal_base['natural_frequencies']
    freqs_dam = modal_dam['natural_frequencies']
    damp_base = modal_base['damping_ratios']
    damp_dam = modal_dam['damping_ratios']
    modes_base = normalize_mode_shapes(modal_base['mode_shapes'])
    modes_dam = normalize_mode_shapes(modal_dam['mode_shapes'])

    print(f"  Baseline modes ({len(freqs_base)}):")
    for i in range(min(len(freqs_base), 6)):
        print(f"    Mode {i+1}: {freqs_base[i]:.4f} Hz, damping: {damp_base[i]:.4f}")

    print(f"  Damaged modes ({len(freqs_dam)}):")
    for i in range(min(len(freqs_dam), 6)):
        print(f"    Mode {i+1}: {freqs_dam[i]:.4f} Hz, damping: {damp_dam[i]:.4f}")

    freq_errors = []
    for tf in true_freqs:
        errors = [abs(f - tf) / tf * 100 for f in freqs_base]
        freq_errors.append(min(errors))
    print(f"\n  Frequency identification errors (%):")
    for i, err in enumerate(freq_errors):
        print(f"    True {true_freqs[i]:.1f} Hz: {err:.2f}% error")

    print("\n[4] Damage assessment...")
    connectivity = [(i, i+1) for i in range(n_channels - 1)]
    node_positions = {i: (float(i), 0.0) for i in range(n_channels)}
    node_labels = [f"N{i+1}" for i in range(n_channels)]

    damage_assessment = assess_damage(
        modes_base, modes_dam,
        freqs_base, freqs_dam,
        damp_base, damp_dam,
        connectivity, node_labels,
        threshold_mse=0.1, threshold_flex=0.1,
        use_combined=True, alpha=0.5,
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

    print(f"  Damaged elements: {n_damaged}/{len(connectivity)}")
    print(f"  Max stiffness reduction: {max_stiff:.1f}%")
    print(f"  True damage element {true_damage_element} detected: {'YES' if detected else 'NO'}")

    if damage_assessment['damaged_elements']:
        print(f"  Top 3 damaged elements:")
        for elem in damage_assessment['damaged_elements'][:3]:
            marker = " <-- TRUE" if (elem['element_id'] == true_damage_element or
                                       elem['element_id'] == true_damage_element - 1) else ""
            print(f"    Element {elem['element_id']}: DI={elem['damage_index']:.3f}, "
                  f"stiffness={elem.get('stiffness_reduction_pct', 0):.1f}%{marker}")

    print("\n[5] Generating test output...")
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")
    os.makedirs(output_dir, exist_ok=True)

    figure_paths = generate_report_figures(
        damage_assessment, modal_base, modal_dam,
        connectivity, node_positions, node_labels,
        output_dir,
    )
    damage_report = generate_damage_report(
        damage_assessment, modal_base, modal_dam,
        node_positions, node_labels,
    )
    report_path, json_path = generate_html_report(
        damage_assessment, damage_report,
        modal_base, modal_dam,
        figure_paths, output_dir,
    )

    print(f"\n{'=' * 60}")
    print("VALIDATION TEST COMPLETE")
    print(f"  Report: {report_path}")
    print(f"  JSON:   {json_path}")

    if detected and max_stiff > 10:
        print("\n  RESULT: PASS - Damage correctly identified")
    elif detected:
        print("\n  RESULT: PARTIAL - Damage detected but severity underestimated")
    else:
        print("\n  RESULT: FAIL - Damage not detected at expected location")
    print(f"{'=' * 60}")

    return detected


if __name__ == '__main__':
    success = test_complete_pipeline()
    sys.exit(0 if success else 1)
