import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from matplotlib.collections import LineCollection
import json
import os
from datetime import datetime


def plot_mode_shapes(mode_shapes, natural_frequencies, node_positions=None,
                     node_labels=None, title="Mode Shapes", save_path=None,
                     show_legend=True):
    n_modes = mode_shapes.shape[1]
    if n_modes == 0:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, 'No modes identified', ha='center', va='center',
                transform=ax.transAxes, fontsize=14)
        ax.set_title(title)
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
            return save_path
        return fig
    n_dofs = mode_shapes.shape[0]
    if node_positions is None:
        node_positions = np.arange(n_dofs)
    if node_labels is None:
        node_labels = [f"DOF {i+1}" for i in range(n_dofs)]
    n_cols = min(3, n_modes)
    n_rows = (n_modes + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 5 * n_rows))
    if n_modes == 1:
        axes = np.array([axes])
    axes = axes.flatten()
    for m in range(n_modes):
        ax = axes[m]
        mode = mode_shapes[:, m]
        max_val = np.max(np.abs(mode))
        if max_val > 0:
            mode_norm = mode / max_val
        else:
            mode_norm = mode
        if isinstance(node_positions, dict) and len(node_positions) >= n_dofs:
            x_vals = np.array([node_positions.get(i, (i, 0))[0] for i in range(n_dofs)])
        elif isinstance(node_positions, (list, np.ndarray)) and len(node_positions) >= n_dofs:
            x_vals = np.array([node_positions[i][0] if isinstance(node_positions[i], (list, tuple)) else node_positions[i]
                              for i in range(n_dofs)])
        else:
            x_vals = np.arange(n_dofs)
        ax.plot(x_vals, mode_norm, 'o-', linewidth=2, markersize=8,
                label=f'Mode {m+1}')
        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax.fill_between(x_vals, mode_norm, alpha=0.3)
        ax.set_title(f"Mode {m+1}: {natural_frequencies[m]:.3f} Hz")
        ax.set_xlabel("Position")
        ax.set_ylabel("Normalized Mode Shape")
        ax.grid(True, alpha=0.3)
        if node_labels is not None and len(node_labels) <= 20:
            ax.set_xticks(x_vals)
            ax.set_xticklabels(node_labels, rotation=45, ha='right', fontsize=7)
        elif node_labels is not None:
            step = max(1, len(node_labels) // 20)
            ax.set_xticks(x_vals[::step])
            ax.set_xticklabels([node_labels[i] for i in range(0, len(node_labels), step)],
                             rotation=45, ha='right', fontsize=7)
    for m in range(n_modes, len(axes)):
        axes[m].set_visible(False)
    plt.suptitle(title, fontsize=16, fontweight='bold')
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        return save_path
    else:
        return fig


def plot_damage_elements(damage_assessment, connectivity, node_positions=None,
                          node_labels=None, title="Damage Location Map",
                          save_path=None, threshold=0.1):
    n_elements = len(connectivity)
    if node_positions is None:
        node_positions = {}
        n_nodes = max(max(conn) for conn in connectivity) + 1
        for i in range(n_nodes):
            angle = 2 * np.pi * i / n_nodes
            node_positions[i] = (np.cos(angle), np.sin(angle))
    fig, ax = plt.subplots(figsize=(12, 10))
    for i, pos in node_positions.items():
        label = node_labels[i] if node_labels and i < len(node_labels) else f"N{i}"
        ax.plot(pos[0], pos[1], 'ko', markersize=10)
        ax.annotate(label, (pos[0], pos[1]),
                   textcoords="offset points", xytext=(10, 5), fontsize=9)
    stiffness = damage_assessment['stiffness_reduction_pct']
    max_stiff = np.max(stiffness) if len(stiffness) > 0 else 1
    cmap = plt.cm.RdYlGn_r
    for e, (i, j) in enumerate(connectivity):
        if e >= len(stiffness):
            continue
        pos_i = node_positions.get(i, (0, 0))
        pos_j = node_positions.get(j, (0, 0))
        norm_val = stiffness[e] / max(max_stiff, 1e-10)
        color = cmap(norm_val)
        linewidth = 1.5 + 3 * norm_val
        ax.plot([pos_i[0], pos_j[0]], [pos_i[1], pos_j[1]],
                color=color, linewidth=linewidth, alpha=0.8)
        mid_x = (pos_i[0] + pos_j[0]) / 2
        mid_y = (pos_i[1] + pos_j[1]) / 2
        ax.annotate(f"{stiffness[e]:.1f}%", (mid_x, mid_y),
                   fontsize=8, ha='center', va='center',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))
    damaged = damage_assessment.get('damaged_elements', [])
    for elem in damaged:
        i, j = elem['node_i'], elem['node_j']
        pos_i = node_positions.get(i, (0, 0))
        pos_j = node_positions.get(j, (0, 0))
        ax.plot([pos_i[0], pos_j[0]], [pos_i[1], pos_j[1]],
                'r--', linewidth=2.5, alpha=0.8)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, max(max_stiff, 1e-10)))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.6)
    cbar.set_label('Stiffness Reduction (%)', fontsize=11)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        return save_path
    else:
        return fig


def plot_damage_indices(damage_assessment, connectivity, node_labels=None,
                         title="Damage Indices Comparison", save_path=None):
    n_elements = len(connectivity)
    mse_di = damage_assessment.get('mse_damage_index', np.zeros(n_elements))
    flex_di = damage_assessment.get('flex_damage_index', np.zeros(n_elements))
    element_labels = []
    for e, (i, j) in enumerate(connectivity):
        label_i = node_labels[i] if node_labels and i < len(node_labels) else f"N{i}"
        label_j = node_labels[j] if node_labels and j < len(node_labels) else f"N{j}"
        element_labels.append(f"{label_i}-{label_j}")
    fig, axes = plt.subplots(2, 1, figsize=(max(10, n_elements * 0.4), 10))
    x = np.arange(n_elements)
    width = 0.35
    axes[0].bar(x - width/2, mse_di[:n_elements], width, label='MSE Damage Index',
                color='steelblue', alpha=0.8)
    axes[0].axhline(y=damage_assessment.get('threshold_mse', 0.1),
                   color='red', linestyle='--', label='Threshold')
    axes[0].set_title("Modal Strain Energy (MSE) Damage Index")
    axes[0].set_ylabel("MSE Change Ratio")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3, axis='y')
    axes[1].bar(x - width/2, flex_di[:n_elements], width, label='Flexibility Damage Index',
                color='coral', alpha=0.8)
    axes[1].axhline(y=damage_assessment.get('threshold_flex', 0.1),
                   color='red', linestyle='--', label='Threshold')
    axes[1].set_title("Flexibility Curvature Damage Index")
    axes[1].set_ylabel("Curvature Change Ratio")
    axes[1].set_xlabel("Element")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3, axis='y')
    for ax in axes:
        if n_elements <= 30:
            ax.set_xticks(x)
            ax.set_xticklabels(element_labels, rotation=45, ha='right', fontsize=7)
        else:
            step = max(1, n_elements // 30)
            ax.set_xticks(x[::step])
            ax.set_xticklabels([element_labels[i] for i in range(0, n_elements, step)],
                             rotation=45, ha='right', fontsize=7)
    plt.suptitle(title, fontsize=14, fontweight='bold')
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        return save_path
    else:
        return fig


def plot_stiffness_reduction(damage_assessment, connectivity, node_labels=None,
                              title="Stiffness Reduction by Element", save_path=None):
    n_elements = len(connectivity)
    stiffness = damage_assessment['stiffness_reduction_pct']
    element_labels = []
    for e, (i, j) in enumerate(connectivity):
        label_i = node_labels[i] if node_labels and i < len(node_labels) else f"N{i}"
        label_j = node_labels[j] if node_labels and j < len(node_labels) else f"N{j}"
        element_labels.append(f"{label_i}-{label_j}")
    fig, ax = plt.subplots(figsize=(max(12, n_elements * 0.4), 6))
    colors = []
    for s in stiffness:
        if s >= 60:
            colors.append('#d32f2f')
        elif s >= 35:
            colors.append('#f57c00')
        elif s >= 15:
            colors.append('#fbc02d')
        else:
            colors.append('#388e3c')
    x = np.arange(n_elements)
    bars = ax.bar(x, stiffness[:n_elements], color=colors, alpha=0.85, edgecolor='white')
    ax.axhline(y=15, color='#fbc02d', linestyle='--', alpha=0.7, label='Mild (15%)')
    ax.axhline(y=35, color='#f57c00', linestyle='--', alpha=0.7, label='Moderate (35%)')
    ax.axhline(y=60, color='#d32f2f', linestyle='--', alpha=0.7, label='Severe (60%)')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel("Element")
    ax.set_ylabel("Stiffness Reduction (%)")
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3, axis='y')
    if n_elements <= 30:
        ax.set_xticks(x)
        ax.set_xticklabels(element_labels, rotation=45, ha='right', fontsize=7)
    else:
        step = max(1, n_elements // 30)
        ax.set_xticks(x[::step])
        ax.set_xticklabels([element_labels[i] for i in range(0, n_elements, step)],
                         rotation=45, ha='right', fontsize=7)
    for bar, val in zip(bars, stiffness[:n_elements]):
        if val > 5:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                   f'{val:.1f}%', ha='center', va='bottom', fontsize=8, fontweight='bold')
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        return save_path
    else:
        return fig


def plot_frequency_comparison(freqs_baseline, freqs_damaged, damp_baseline=None,
                               damp_damaged=None, title="Modal Parameter Comparison",
                               save_path=None):
    n_modes = min(len(freqs_baseline), len(freqs_damaged))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    x = np.arange(n_modes)
    width = 0.35
    ax1.bar(x - width/2, freqs_baseline[:n_modes], width, label='Baseline', color='steelblue')
    ax1.bar(x + width/2, freqs_damaged[:n_modes], width, label='Damaged', color='coral')
    ax1.set_xlabel("Mode")
    ax1.set_ylabel("Frequency (Hz)")
    ax1.set_title("Natural Frequency Comparison")
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"M{i+1}" for i in range(n_modes)])
    for i in range(n_modes):
        change = 100 * (freqs_damaged[i] - freqs_baseline[i]) / (freqs_baseline[i] + 1e-10)
        ax1.annotate(f'{change:+.1f}%', (x[i] + width/2, freqs_damaged[i]),
                    textcoords="offset points", xytext=(0, 10), ha='center', fontsize=8)
    if damp_baseline is not None and damp_damaged is not None:
        ax2.bar(x - width/2, damp_baseline[:n_modes] * 100, width, label='Baseline', color='steelblue')
        ax2.bar(x + width/2, damp_damaged[:n_modes] * 100, width, label='Damaged', color='coral')
        ax2.set_xlabel("Mode")
        ax2.set_ylabel("Damping Ratio (%)")
        ax2.set_title("Damping Ratio Comparison")
        ax2.legend()
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_xticks(x)
        ax2.set_xticklabels([f"M{i+1}" for i in range(n_modes)])
    else:
        ax2.set_visible(False)
    plt.suptitle(title, fontsize=14, fontweight='bold')
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        return save_path
    else:
        return fig


def plot_stabilization_diagram(stable_poles, all_poles, orders,
                                title="Stabilization Diagram", save_path=None):
    fig, ax = plt.subplots(figsize=(10, 8))
    order_vals = [p['order'] for p in all_poles]
    freq_vals = [p['frequency'] for p in all_poles]
    ax.scatter(order_vals, freq_vals, s=2, alpha=0.3, color='gray', label='All Poles')
    if stable_poles:
        stable_orders = [p['order'] for p in stable_poles]
        stable_freqs = [p['frequency'] for p in stable_poles]
        ax.scatter(stable_orders, stable_freqs, s=30, alpha=0.8,
                  color='red', marker='s', label='Stable Poles')
    ax.set_xlabel("Model Order")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        return save_path
    else:
        return fig


def plot_impulse_response(impulse_responses, channel_idx=0, lags=None, fs=1.0,
                          title="Impulse Response Functions", save_path=None):
    n_channels = impulse_responses.shape[0]
    fig, axes = plt.subplots(min(4, n_channels), 1, figsize=(12, 3 * min(4, n_channels)),
                              sharex=True)
    if n_channels == 1:
        axes = [axes]
    if lags is None:
        lags = np.arange(impulse_responses.shape[1])
    for i in range(min(4, n_channels)):
        axes[i].plot(lags / fs, impulse_responses[i, :], linewidth=0.8)
        axes[i].set_ylabel(f"Ch {i+1}")
        axes[i].grid(True, alpha=0.3)
    axes[-1].set_xlabel("Time (s)")
    plt.suptitle(title, fontsize=14)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        return save_path
    else:
        return fig


def generate_report_figures(damage_assessment, modal_baseline, modal_damaged,
                             connectivity, node_positions=None, node_labels=None,
                             output_dir=None, prefix=""):
    if output_dir is None:
        output_dir = "."
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    paths['mode_shapes_baseline'] = plot_mode_shapes(
        modal_baseline['mode_shapes'],
        modal_baseline['natural_frequencies'],
        node_positions, node_labels,
        title="Baseline Mode Shapes",
        save_path=os.path.join(output_dir, f"{prefix}mode_shapes_baseline.png")
    )
    paths['mode_shapes_damaged'] = plot_mode_shapes(
        modal_damaged['mode_shapes'],
        modal_damaged['natural_frequencies'],
        node_positions, node_labels,
        title="Damaged Mode Shapes",
        save_path=os.path.join(output_dir, f"{prefix}mode_shapes_damaged.png")
    )
    paths['damage_map'] = plot_damage_elements(
        damage_assessment, connectivity,
        node_positions, node_labels,
        save_path=os.path.join(output_dir, f"{prefix}damage_location_map.png")
    )
    paths['damage_indices'] = plot_damage_indices(
        damage_assessment, connectivity, node_labels,
        save_path=os.path.join(output_dir, f"{prefix}damage_indices.png")
    )
    paths['stiffness_reduction'] = plot_stiffness_reduction(
        damage_assessment, connectivity, node_labels,
        save_path=os.path.join(output_dir, f"{prefix}stiffness_reduction.png")
    )
    paths['frequency_comparison'] = plot_frequency_comparison(
        modal_baseline['natural_frequencies'],
        modal_damaged['natural_frequencies'],
        modal_baseline['damping_ratios'],
        modal_damaged['damping_ratios'],
        save_path=os.path.join(output_dir, f"{prefix}frequency_comparison.png")
    )
    return paths


def generate_html_report(damage_assessment, damage_report, modal_baseline,
                          modal_damaged, figure_paths, output_dir,
                          config=None):
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "damage_report.html")
    summary = damage_report['summary']
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Structural Damage Detection Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }}
        h2 {{ color: #283593; margin-top: 30px; }}
        h3 {{ color: #3949ab; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .summary-card {{ background: #e8eaf6; padding: 20px; border-radius: 8px; text-align: center; }}
        .summary-card .value {{ font-size: 2em; font-weight: bold; color: #1a237e; }}
        .summary-card .label {{ color: #5c6bc0; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #3949ab; color: white; }}
        tr:hover {{ background: #f5f5f5; }}
        .severity-critical {{ color: #d32f2f; font-weight: bold; }}
        .severity-severe {{ color: #f57c00; font-weight: bold; }}
        .severity-moderate {{ color: #f9a825; font-weight: bold; }}
        .severity-mild {{ color: #558b2f; font-weight: bold; }}
        .figure-container {{ margin: 20px 0; text-align: center; }}
        .figure-container img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .figure-container .caption {{ font-size: 0.9em; color: #666; margin-top: 5px; font-style: italic; }}
        .alert {{ padding: 15px; border-radius: 5px; margin: 10px 0; }}
        .alert-danger {{ background: #ffebee; border-left: 4px solid #d32f2f; }}
        .alert-warning {{ background: #fff3e0; border-left: 4px solid #f57c00; }}
        .alert-info {{ background: #e3f2fd; border-left: 4px solid #1976d2; }}
        .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
    </style>
</head>
<body>
<div class="container">
    <h1>Structural Damage Detection Report</h1>
    <p class="meta">Generated: {timestamp} | Analysis Method: NExT-ERA</p>

    <h2>Executive Summary</h2>
    <div class="summary-grid">
        <div class="summary-card">
            <div class="value">{summary['total_elements']}</div>
            <div class="label">Total Elements</div>
        </div>
        <div class="summary-card">
            <div class="value">{summary['damaged_elements_count']}</div>
            <div class="label">Damaged Elements</div>
        </div>
        <div class="summary-card">
            <div class="value">{summary['damage_ratio']*100:.1f}%</div>
            <div class="label">Damage Ratio</div>
        </div>
        <div class="summary-card">
            <div class="value">{summary['max_stiffness_reduction_pct']:.1f}%</div>
            <div class="label">Max Stiffness Reduction</div>
        </div>
    </div>
"""
    if summary['damage_ratio'] > 0.3:
        html += """    <div class="alert alert-danger">
        <strong>Critical:</strong> Significant structural damage detected. Immediate inspection recommended.
    </div>
"""
    elif summary['damage_ratio'] > 0.1:
        html += """    <div class="alert alert-warning">
        <strong>Warning:</strong> Moderate structural damage detected. Further evaluation recommended.
    </div>
"""
    else:
        html += """    <div class="alert alert-info">
        <strong>Info:</strong> Minor or no significant damage detected. Routine monitoring is sufficient.
    </div>
"""
    html += """
    <h2>Modal Parameter Comparison</h2>
    <table>
        <tr><th>Mode</th><th>Baseline Freq (Hz)</th><th>Damaged Freq (Hz)</th><th>Freq Change (%)</th>
            <th>Baseline Damping (%)</th><th>Damaged Damping (%)</th></tr>
"""
    for comp in damage_report['modal_comparison']:
        html += f"""        <tr>
            <td>Mode {comp['mode']}</td>
            <td>{comp['baseline_freq_hz']:.4f}</td>
            <td>{comp['damaged_freq_hz']:.4f}</td>
            <td>{comp['freq_change_pct']:.2f}%</td>
            <td>{comp['baseline_damping']*100:.3f}</td>
            <td>{comp['damaged_damping']*100:.3f}</td>
        </tr>
"""
    html += """    </table>

    <h2>Damage Assessment</h2>
    <h3>Damaged Elements</h3>
    <table>
        <tr><th>Element</th><th>Node I</th><th>Node J</th><th>MSE DI</th>
            <th>Flex DI</th><th>Stiffness Reduction (%)</th><th>Severity</th></tr>
"""
    for elem in damage_assessment['damaged_elements'][:20]:
        sev_class = f"severity-{elem.get('severity', 'mild')}"
        html += f"""        <tr>
            <td>{elem['element_id']}</td>
            <td>{elem.get('label_i', elem['node_i'])}</td>
            <td>{elem.get('label_j', elem['node_j'])}</td>
            <td>{elem['mse_di']:.4f}</td>
            <td>{elem['flex_di']:.4f}</td>
            <td>{elem.get('stiffness_reduction_pct', 0):.2f}</td>
            <td class="{sev_class}">{elem.get('severity', 'unknown').upper()}</td>
        </tr>
"""
    if len(damage_assessment['damaged_elements']) > 20:
        html += f"        <tr><td colspan='7'>... and {len(damage_assessment['damaged_elements']) - 20} more damaged elements</td></tr>\n"
    html += """    </table>

    <h2>Visualizations</h2>
"""
    if 'mode_shapes_baseline' in figure_paths:
        html += f"""    <div class="figure-container">
        <img src="{figure_paths['mode_shapes_baseline']}" alt="Baseline Mode Shapes">
        <div class="caption">Figure 1: Baseline Mode Shapes</div>
    </div>
"""
    if 'damage_map' in figure_paths:
        html += f"""    <div class="figure-container">
        <img src="{figure_paths['damage_map']}" alt="Damage Location Map">
        <div class="caption">Figure 2: Damage Location Map with Stiffness Reduction</div>
    </div>
"""
    if 'damage_indices' in figure_paths:
        html += f"""    <div class="figure-container">
        <img src="{figure_paths['damage_indices']}" alt="Damage Indices">
        <div class="caption">Figure 3: Damage Indices Comparison (MSE and Flexibility)</div>
    </div>
"""
    if 'stiffness_reduction' in figure_paths:
        html += f"""    <div class="figure-container">
        <img src="{figure_paths['stiffness_reduction']}" alt="Stiffness Reduction">
        <div class="caption">Figure 4: Stiffness Reduction by Element</div>
    </div>
"""
    if 'frequency_comparison' in figure_paths:
        html += f"""    <div class="figure-container">
        <img src="{figure_paths['frequency_comparison']}" alt="Frequency Comparison">
        <div class="caption">Figure 5: Modal Frequency and Damping Comparison</div>
    </div>
"""
    html += """
    <h2>Methodology</h2>
    <div class="alert alert-info">
        <strong>Analysis Method:</strong> NExT-ERA (Natural Excitation Technique combined with Eigensystem Realization Algorithm)
        <br><strong>Damage Indicators:</strong> Modal Strain Energy (MSE) Change, Flexibility Curvature Method
        <br><strong>Stiffness Reduction:</strong> Estimated from mode shape and frequency changes
    </div>

    <footer style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; text-align: center; color: #666;">
        <p>Structural Health Monitoring System | Report generated by NExT-ERA Analysis Tool</p>
    </footer>
</div>
</body>
</html>
"""
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    json_path = os.path.join(output_dir, "damage_report.json")
    json_report = {
        'timestamp': timestamp,
        'method': 'NExT-ERA',
        'summary': summary,
        'modal_comparison': damage_report['modal_comparison'],
        'damaged_elements': damage_assessment['damaged_elements'],
        'stiffness_reduction_pct': damage_assessment['stiffness_reduction_pct'].tolist(),
        'mse_damage_index': damage_assessment['mse_damage_index'].tolist() if hasattr(damage_assessment['mse_damage_index'], 'tolist') else list(damage_assessment['mse_damage_index']),
        'flex_damage_index': damage_assessment['flex_damage_index'].tolist() if hasattr(damage_assessment['flex_damage_index'], 'tolist') else list(damage_assessment['flex_damage_index']),
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_report, f, indent=2, default=str)
    return report_path, json_path
