import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch
import os
from datetime import datetime
from typing import List, Dict, Optional, Union, Tuple
from pathlib import Path
import json
import pandas as pd

from .data_io import EddyCurrentData, DataVisualizer
from .preprocessing import Preprocessor


class ReportGenerator:
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def generate_report(self,
                       data: EddyCurrentData,
                       detection_result: Dict,
                       filename: Optional[str] = None) -> Dict:
        if filename is None:
            filename = f"report_{self.timestamp}"
        
        report_dir = self.output_dir / filename
        report_dir.mkdir(exist_ok=True)
        
        figs = self._create_visualizations(data, detection_result, report_dir)
        
        report_data = self._generate_report_data(data, detection_result)
        report_data['figures'] = figs
        
        self._save_text_report(report_data, report_dir / "report.txt")
        self._save_json_report(report_data, report_dir / "report.json")
        self._save_html_report(report_data, report_dir / "report.html")
        
        report_data['report_path'] = str(report_dir)
        
        print(f"Report generated: {report_dir}")
        return report_data

    def _create_visualizations(self,
                              data: EddyCurrentData,
                              detection_result: Dict,
                              report_dir: Path) -> Dict[str, str]:
        figs = {}
        
        preprocessor = Preprocessor()
        processed_data = preprocessor.process(data)
        
        n_freqs = len(data.frequencies) if data.frequencies else data.impedance.shape[1]
        
        for freq_idx in range(min(n_freqs, 2)):
            fig_path = report_dir / f"impedance_plane_freq{freq_idx}.png"
            self._plot_impedance_plane(data, processed_data, detection_result, freq_idx, fig_path)
            figs[f'impedance_plane_{freq_idx}'] = str(fig_path)
        
        fig_path = report_dir / f"amplitude_phase.png"
        self._plot_amplitude_phase(data, processed_data, detection_result, fig_path)
        figs['amplitude_phase'] = str(fig_path)
        
        fig_path = report_dir / f"crack_location.png"
        self._plot_crack_location(data, detection_result, fig_path)
        figs['crack_location'] = str(fig_path)
        
        fig_path = report_dir / f"confidence_map.png"
        self._plot_confidence_map(data, detection_result, fig_path)
        figs['confidence_map'] = str(fig_path)
        
        if n_freqs > 1:
            fig_path = report_dir / f"multi_freq_comparison.png"
            self._plot_multi_frequency(data, detection_result, fig_path)
            figs['multi_frequency'] = str(fig_path)
        
        plt.close('all')
        return figs

    def _plot_impedance_plane(self,
                             raw_data: EddyCurrentData,
                             processed_data: EddyCurrentData,
                             result: Dict,
                             freq_idx: int,
                             save_path: Path) -> None:
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        DataVisualizer.plot_impedance(raw_data, freq_idx, axes[0])
        axes[0].set_title('Raw Data - Impedance Plane')
        
        DataVisualizer.plot_impedance(processed_data, freq_idx, axes[1])
        axes[1].set_title('Processed Data - Impedance Plane')
        
        if result.get('has_crack', False):
            crack_idx = result.get('crack_index', None)
            if crack_idx is not None:
                for ax in axes:
                    crack_real = processed_data.real[crack_idx, freq_idx]
                    crack_imag = processed_data.imag[crack_idx, freq_idx]
                    ax.plot(crack_real, crack_imag, 'r*', markersize=15, 
                            label=f'Detected Crack (pos={result.get("position_mm", 0):.2f}mm)')
                    ax.legend()
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _plot_amplitude_phase(self,
                             raw_data: EddyCurrentData,
                             processed_data: EddyCurrentData,
                             result: Dict,
                             save_path: Path) -> None:
        n_freqs = len(raw_data.frequencies) if raw_data.frequencies else raw_data.impedance.shape[1]
        fig, axes = plt.subplots(2 * n_freqs, 1, figsize=(12, 4 * n_freqs), sharex=True)
        
        if n_freqs == 1:
            axes = axes.reshape(-1, 1)
        
        for freq_idx in range(n_freqs):
            ax_amp = axes[2 * freq_idx]
            ax_phase = axes[2 * freq_idx + 1]
            
            DataVisualizer.plot_amplitude_phase(processed_data, freq_idx, [ax_amp, ax_phase])
            
            if result.get('has_crack', False):
                pos_mm = result.get('position_mm', 0)
                ax_amp.axvline(x=pos_mm, color='r', linestyle='--', label=f'Crack ({pos_mm:.2f}mm)')
                ax_phase.axvline(x=pos_mm, color='r', linestyle='--')
                ax_amp.legend()
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _plot_crack_location(self,
                            data: EddyCurrentData,
                            result: Dict,
                            save_path: Path) -> None:
        fig, ax = plt.subplots(figsize=(12, 4))
        
        x = data.positions[:, 0] if data.positions is not None else np.arange(data.impedance.shape[0])
        amp = np.mean(np.abs(data.impedance), axis=1)
        
        ax.plot(x, amp, 'b-', linewidth=2, label='Mean Amplitude')
        ax.fill_between(x, amp.min(), amp, alpha=0.3)
        
        if result.get('has_crack', False):
            pos = result.get('position_mm', x.mean())
            depth = result.get('depth', 0) * 1000
            length = result.get('length', 0) * 1000
            confidence = result.get('confidence', 0)
            
            half_len = length / 2000
            crack_rect = Rectangle(
                (pos - half_len, amp.min()),
                length / 1000, amp.max() - amp.min(),
                facecolor='red', alpha=0.3, edgecolor='red', linewidth=2,
                label=f'Detected Crack'
            )
            ax.add_patch(crack_rect)
            
            arrow_props = dict(facecolor='red', shrink=0.05, width=2, headwidth=8)
            ax.annotate(
                f'Depth: {depth:.2f} mm\nLength: {length:.2f} mm\nConfidence: {confidence:.1%}',
                xy=(pos, amp.max() * 0.9),
                xytext=(pos + (x.max() - x.min()) * 0.1, amp.max() * 0.8),
                arrowprops=arrow_props,
                fontsize=11,
                bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='red')
            )
        
        ax.set_xlabel('Position (mm)' if data.positions is not None else 'Sample Index')
        ax.set_ylabel('Mean Amplitude (Ohm)')
        ax.set_title('Crack Location Map')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _plot_confidence_map(self,
                            data: EddyCurrentData,
                            result: Dict,
                            save_path: Path) -> None:
        fig, ax = plt.subplots(figsize=(12, 5))
        
        n_samples = data.impedance.shape[0]
        n_freqs = data.impedance.shape[1]
        
        amp_data = np.abs(data.impedance).T
        
        im = ax.imshow(amp_data, aspect='auto', cmap='viridis',
                      extent=[0, n_samples, 0, n_freqs],
                      origin='lower')
        
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Amplitude (Ohm)')
        
        if result.get('has_crack', False):
            pos = result.get('crack_index', n_samples // 2)
            depth = result.get('depth', 0) * 1000
            confidence = result.get('confidence', 0)
            
            ax.axvline(x=pos, color='white', linewidth=2, linestyle='--',
                      label=f'Crack (conf={confidence:.1%})')
            
            ax.text(pos + 2, n_freqs / 2,
                   f'Confidence: {confidence:.1%}\nDepth: {depth:.2f}mm',
                   color='white', fontsize=11,
                   bbox=dict(facecolor='black', alpha=0.7, pad=5))
        
        ax.set_xlabel('Sample Index')
        ax.set_ylabel('Frequency Channel')
        ax.set_title('Signal Amplitude Map with Detection Confidence')
        ax.legend()
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _plot_multi_frequency(self,
                             data: EddyCurrentData,
                             result: Dict,
                             save_path: Path) -> None:
        n_freqs = data.impedance.shape[1]
        fig, axes = plt.subplots(n_freqs, 1, figsize=(12, 3 * n_freqs), sharex=True)
        
        if n_freqs == 1:
            axes = [axes]
        
        x = data.positions[:, 0] if data.positions is not None else np.arange(data.impedance.shape[0])
        
        for i, ax in enumerate(axes):
            real = np.real(data.impedance[:, i])
            imag = np.imag(data.impedance[:, i])
            
            freq_label = f"{data.frequencies[i]/1000:.0f} kHz" if data.frequencies else f"Freq {i}"
            
            ax.plot(x, real, 'b-', label='Real', linewidth=1.5)
            ax.plot(x, imag, 'r-', label='Imaginary', linewidth=1.5)
            
            if result.get('has_crack', False):
                pos = result.get('position_mm', x.mean())
                ax.axvline(x=pos, color='k', linestyle='--', linewidth=2, alpha=0.7)
            
            ax.set_ylabel('Impedance (Ohm)')
            ax.set_title(f'{freq_label}')
            ax.legend(loc='upper right')
            ax.grid(True, alpha=0.3)
        
        axes[-1].set_xlabel('Position (mm)' if data.positions is not None else 'Sample Index')
        plt.suptitle('Multi-Frequency Eddy Current Signals', y=1.02)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _generate_report_data(self, data: EddyCurrentData, result: Dict) -> Dict:
        report = {
            'report_id': f"REP_{self.timestamp}",
            'generated_at': datetime.now().isoformat(),
            'input_data': {
                'shape': list(data.impedance.shape),
                'frequencies': data.frequencies,
                'has_positions': data.positions is not None,
                'position_range': [float(data.positions.min()), float(data.positions.max())] if data.positions is not None else None,
                'metadata': data.metadata,
            },
            'detection_result': {
                'has_crack': bool(result.get('has_crack', False)),
                'confidence': float(result.get('confidence', 0.0)),
                'depth_mm': float(result.get('depth', 0.0)) * 1000,
                'length_mm': float(result.get('length', 0.0)) * 1000,
                'position': float(result.get('position', 0.0)),
                'position_mm': float(result.get('position_mm', 0.0)),
                'crack_index': int(result.get('crack_index', -1)) if 'crack_index' in result else None,
            },
            'signal_statistics': {
                'amplitude': {
                    'mean': float(np.mean(np.abs(data.impedance))),
                    'std': float(np.std(np.abs(data.impedance))),
                    'min': float(np.min(np.abs(data.impedance))),
                    'max': float(np.max(np.abs(data.impedance))),
                },
                'phase': {
                    'mean': float(np.mean(np.angle(data.impedance))),
                    'std': float(np.std(np.angle(data.impedance))),
                    'min': float(np.min(np.angle(data.impedance))),
                    'max': float(np.max(np.angle(data.impedance))),
                }
            },
            'recommendation': self._generate_recommendation(result),
        }
        
        return report

    def _generate_recommendation(self, result: Dict) -> str:
        has_crack = result.get('has_crack', False)
        confidence = result.get('confidence', 0)
        
        if not has_crack:
            return "No crack detected. The inspected area appears to be defect-free."
        else:
            depth = result.get('depth', 0) * 1000
            length = result.get('length', 0) * 1000
            
            severity = "LOW"
            if depth > 0.5:
                severity = "MEDIUM"
            if depth > 1.0 or length > 10:
                severity = "HIGH"
            
            return (f"CRACK DETECTED (Severity: {severity}). "
                   f"Confidence: {confidence:.1%}. "
                   f"Estimated depth: {depth:.2f} mm, length: {length:.2f} mm. "
                   f"Recommended: Further inspection and evaluation required.")

    def _save_text_report(self, report_data: Dict, filepath: Path) -> None:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("           EDDY CURRENT CRACK DETECTION REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Report ID: {report_data['report_id']}\n")
            f.write(f"Generated: {report_data['generated_at']}\n\n")
            
            f.write("-" * 40 + "\n")
            f.write("INPUT DATA INFORMATION\n")
            f.write("-" * 40 + "\n")
            input_data = report_data['input_data']
            f.write(f"Data shape: {input_data['shape']}\n")
            f.write(f"Frequencies: {input_data['frequencies']}\n")
            if input_data['position_range']:
                f.write(f"Position range: [{input_data['position_range'][0]:.4f}, {input_data['position_range'][1]:.4f}] mm\n")
            if input_data['metadata']:
                f.write(f"Metadata: {input_data['metadata']}\n")
            f.write("\n")
            
            f.write("-" * 40 + "\n")
            f.write("DETECTION RESULTS\n")
            f.write("-" * 40 + "\n")
            det = report_data['detection_result']
            f.write(f"Crack detected: {'YES' if det['has_crack'] else 'NO'}\n")
            f.write(f"Detection confidence: {det['confidence']:.1%}\n")
            if det['has_crack']:
                f.write(f"Estimated crack depth: {det['depth_mm']:.2f} mm\n")
                f.write(f"Estimated crack length: {det['length_mm']:.2f} mm\n")
                f.write(f"Crack position: {det['position_mm']:.2f} mm\n")
            f.write("\n")
            
            f.write("-" * 40 + "\n")
            f.write("SIGNAL STATISTICS\n")
            f.write("-" * 40 + "\n")
            stats = report_data['signal_statistics']
            f.write("Amplitude:\n")
            f.write(f"  Mean: {stats['amplitude']['mean']:.4f} Ohm\n")
            f.write(f"  Std:  {stats['amplitude']['std']:.4f} Ohm\n")
            f.write(f"  Min:  {stats['amplitude']['min']:.4f} Ohm\n")
            f.write(f"  Max:  {stats['amplitude']['max']:.4f} Ohm\n")
            f.write("Phase (radians):\n")
            f.write(f"  Mean: {stats['phase']['mean']:.4f}\n")
            f.write(f"  Std:  {stats['phase']['std']:.4f}\n")
            f.write("\n")
            
            f.write("-" * 40 + "\n")
            f.write("RECOMMENDATION\n")
            f.write("-" * 40 + "\n")
            f.write(f"{report_data['recommendation']}\n\n")
            
            f.write("-" * 40 + "\n")
            f.write("GENERATED FIGURES\n")
            f.write("-" * 40 + "\n")
            for name, path in report_data.get('figures', {}).items():
                f.write(f"  - {name}: {path}\n")
            
            f.write("\n" + "=" * 60 + "\n")
            f.write("                    END OF REPORT\n")
            f.write("=" * 60 + "\n")

    def _save_json_report(self, report_data: Dict, filepath: Path) -> None:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, default=str)

    def _save_html_report(self, report_data: Dict, filepath: Path) -> None:
        det = report_data['detection_result']
        status_color = '#e74c3c' if det['has_crack'] else '#27ae60'
        status_text = 'CRACK DETECTED' if det['has_crack'] else 'NO CRACK'
        
        figures_html = ""
        for name, path in report_data.get('figures', {}).items():
            rel_path = os.path.basename(path)
            figures_html += f'''
            <div class="figure-container">
                <h3>{name.replace('_', ' ').title()}</h3>
                <img src="{rel_path}" alt="{name}" class="report-figure">
            </div>
            '''
        
        html_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Eddy Current Detection Report - {report_data['report_id']}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #2c3e50, #34495e);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 10px 20px;
            background-color: {status_color};
            color: white;
            font-weight: bold;
            border-radius: 5px;
            font-size: 1.2em;
            margin: 10px 0;
        }}
        .section {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}
        .data-table td, .data-table th {{
            padding: 10px;
            border: 1px solid #ddd;
        }}
        .data-table th {{
            background-color: #3498db;
            color: white;
        }}
        .confidence-bar {{
            height: 30px;
            background-color: #ecf0f1;
            border-radius: 15px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .confidence-fill {{
            height: 100%;
            background: linear-gradient(90deg, #f39c12, #e74c3c);
            width: {det['confidence'] * 100}%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }}
        .figure-container {{
            margin: 20px 0;
            text-align: center;
        }}
        .report-figure {{
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        .recommendation {{
            padding: 15px;
            background-color: #fff3cd;
            border-left: 5px solid #ffc107;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Eddy Current Crack Detection Report</h1>
        <p>Report ID: {report_data['report_id']} | Generated: {report_data['generated_at']}</p>
    </div>
    
    <div class="status-badge">{status_text}</div>
    
    <div class="section">
        <h2>Detection Results</h2>
        <table class="data-table">
            <tr><th>Parameter</th><th>Value</th></tr>
            <tr><td>Crack Detected</td><td>{'Yes' if det['has_crack'] else 'No'}</td></tr>
            <tr><td>Confidence</td><td>{det['confidence']:.1%}</td></tr>
            {"<tr><td>Estimated Depth</td><td>" + f"{det['depth_mm']:.2f} mm" + "</td></tr>" if det['has_crack'] else ""}
            {"<tr><td>Estimated Length</td><td>" + f"{det['length_mm']:.2f} mm" + "</td></tr>" if det['has_crack'] else ""}
            {"<tr><td>Position</td><td>" + f"{det['position_mm']:.2f} mm" + "</td></tr>" if det['has_crack'] else ""}
        </table>
        <h3>Detection Confidence</h3>
        <div class="confidence-bar">
            <div class="confidence-fill">{det['confidence']:.1%}</div>
        </div>
    </div>
    
    <div class="section">
        <h2>Recommendation</h2>
        <div class="recommendation">
            {report_data['recommendation']}
        </div>
    </div>
    
    <div class="section">
        <h2>Signal Visualization</h2>
        {figures_html}
    </div>
    
    <div class="section">
        <h2>Input Data Information</h2>
        <table class="data-table">
            <tr><th>Parameter</th><th>Value</th></tr>
            <tr><td>Data Shape</td><td>{report_data['input_data']['shape']}</td></tr>
            <tr><td>Frequencies</td><td>{report_data['input_data']['frequencies']}</td></tr>
        </table>
    </div>
</body>
</html>
        '''
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def generate_batch_report(self,
                              results: List[Tuple[EddyCurrentData, Dict]],
                              filename: Optional[str] = None) -> Dict:
        if filename is None:
            filename = f"batch_report_{self.timestamp}"
        
        report_dir = self.output_dir / filename
        report_dir.mkdir(exist_ok=True)
        
        summary = self._generate_batch_summary(results)
        summary['reports'] = []
        
        for i, (data, result) in enumerate(results):
            sub_report = self.generate_report(
                data, result,
                filename=f"sample_{i:03d}"
            )
            summary['reports'].append(sub_report)
        
        self._save_batch_summary(summary, report_dir)
        
        return summary

    def _generate_batch_summary(self, results: List[Tuple[EddyCurrentData, Dict]]) -> Dict:
        total = len(results)
        cracks_detected = sum(1 for _, r in results if r.get('has_crack', False))
        avg_confidence = np.mean([r.get('confidence', 0) for _, r in results])
        
        return {
            'report_id': f"BATCH_{self.timestamp}",
            'generated_at': datetime.now().isoformat(),
            'total_samples': total,
            'cracks_detected': cracks_detected,
            'no_crack_count': total - cracks_detected,
            'detection_rate': cracks_detected / total if total > 0 else 0,
            'average_confidence': float(avg_confidence),
        }

    def _save_batch_summary(self, summary: Dict, report_dir: Path) -> None:
        with open(report_dir / "summary.json", 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, default=str)
        
        with open(report_dir / "summary.txt", 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("       BATCH EDDY CURRENT DETECTION SUMMARY\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Report ID: {summary['report_id']}\n")
            f.write(f"Generated: {summary['generated_at']}\n\n")
            f.write(f"Total samples processed: {summary['total_samples']}\n")
            f.write(f"Cracks detected: {summary['cracks_detected']}\n")
            f.write(f"No crack samples: {summary['no_crack_count']}\n")
            f.write(f"Detection rate: {summary['detection_rate']:.1%}\n")
            f.write(f"Average confidence: {summary['average_confidence']:.1%}\n\n")
            
            f.write("Detailed reports:\n")
            for i, rep in enumerate(summary.get('reports', [])):
                status = "CRACK" if rep['detection_result']['has_crack'] else "OK"
                conf = rep['detection_result']['confidence']
                f.write(f"  {i:03d}: [{status}] conf={conf:.1%} - {rep.get('report_path', '')}\n")
