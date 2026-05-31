import os
import sys
from pathlib import Path
import numpy as np
import click
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .data_io import DataLoader, EddyCurrentData, DataVisualizer
from .preprocessing import Preprocessor, WaveletDenoiser, LiftOffCompensator
from .features import FeatureExtractor
from .simulation import EddyCurrentSimulator, CrackParams, generate_standard_dataset
from .identification import CrackIdentifier, SVMClassifier, SVMRegressor
from .annotation import AnnotationTool
from .reporting import ReportGenerator
from .config import Config
from .array_probe import (
    ArrayProbeConfig,
    ArraySimulator,
    ArrayDataFusion,
    CScanImaging,
    ArrayDataLoader,
    ArrayPreprocessor
)
from .streaming import (
    StreamConfig,
    SimulatedDataSource,
    FileDataSource,
    StreamProcessor,
    ConsoleAlarmHandler,
    FileAlarmHandler,
    RealTimeMonitor
)
from . import PINN_AVAILABLE

if PINN_AVAILABLE:
    from .pinn_inversion import PINNConfig, PINNInverter


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Eddy Current Testing Signal Analysis Tool.
    
    A comprehensive tool for eddy current testing signal processing,
    crack detection, and characterization.
    """
    pass


@cli.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True),
              help='Input data file (.csv, .npy, .mat)')
@click.option('--output', '-o', type=click.Path(),
              help='Output directory for processed data')
@click.option('--denoise/--no-denoise', default=True,
              help='Apply wavelet denoising')
@click.option('--compensate/--no-compensate', default=True,
              help='Apply lift-off compensation')
@click.option('--normalize/--no-normalize', default=True,
              help='Normalize the data')
def preprocess(input, output, denoise, compensate, normalize):
    """Preprocess eddy current data: denoise, compensate lift-off, normalize."""
    click.echo(f"Loading data from {input}...")
    data = DataLoader.load(input)
    click.echo(f"Loaded data: {data}")
    
    preprocessor = Preprocessor(
        denoiser=WaveletDenoiser() if denoise else None,
        compensator=LiftOffCompensator() if compensate else None,
        normalize=normalize
    )
    
    click.echo("Processing data...")
    processed = preprocessor.process(data)
    click.echo(f"Processing complete. Output shape: {processed.impedance.shape}")
    
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        DataLoader.save(processed, str(out_path))
        click.echo(f"Processed data saved to {output}")
    else:
        click.echo("Use --output to save processed data.")


@cli.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True),
              help='Input data file')
@click.option('--freq', '-f', type=int, default=0,
              help='Frequency index to plot')
@click.option('--output', '-o', type=click.Path(),
              help='Output file for the plot')
@click.option('--plot-type', type=click.Choice(['impedance', 'amplitude', 'both']),
              default='both', help='Type of plot to generate')
def visualize(input, freq, output, plot_type):
    """Visualize eddy current data: impedance plane, amplitude, phase."""
    import matplotlib.pyplot as plt
    
    click.echo(f"Loading data from {input}...")
    data = DataLoader.load(input)
    
    if plot_type in ['impedance', 'both']:
        click.echo("Plotting impedance plane...")
        fig, ax = plt.subplots(figsize=(8, 6))
        DataVisualizer.plot_impedance(data, freq_idx=freq, ax=ax)
        
        if output:
            out_path = Path(output)
            base = out_path.stem
            fig.savefig(f"{out_path.parent}/{base}_impedance.png", dpi=150)
            click.echo(f"Impedance plot saved to {out_path.parent}/{base}_impedance.png")
        else:
            plt.show()
    
    if plot_type in ['amplitude', 'both']:
        click.echo("Plotting amplitude and phase...")
        fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        DataVisualizer.plot_amplitude_phase(data, freq_idx=freq, axes=axes)
        
        if output:
            out_path = Path(output)
            base = out_path.stem
            fig.savefig(f"{out_path.parent}/{base}_amplitude_phase.png", dpi=150)
            click.echo(f"Amplitude/phase plot saved to {out_path.parent}/{base}_amplitude_phase.png")
        else:
            plt.show()


@cli.command()
@click.option('--n-samples', '-n', type=int, default=100,
              help='Number of samples to generate')
@click.option('--n-points', '-p', type=int, default=500,
              help='Number of sampling points per scan')
@click.option('--output', '-o', type=click.Path(), required=True,
              help='Output directory for generated data')
@click.option('--seed', type=int, default=Config.RANDOM_SEED,
              help='Random seed for reproducibility')
@click.option('--material', type=click.Choice(['aluminum', 'steel', 'copper', 'brass']),
              default='aluminum', help='Material type for simulation')
def simulate(n_samples, n_points, output, seed, material):
    """Generate simulated eddy current data with cracks."""
    click.echo(f"Generating {n_samples} simulated samples...")
    
    from .simulation import MaterialParams, ProbeParams
    
    materials = {
        'aluminum': MaterialParams(conductivity=37.7e6),
        'steel': MaterialParams(conductivity=10e6, permeability=100 * Config.PERMEABILITY),
        'copper': MaterialParams(conductivity=59.6e6),
        'brass': MaterialParams(conductivity=15.9e6),
    }
    
    simulator = EddyCurrentSimulator(
        material=materials[material],
        probe=ProbeParams(),
        random_seed=seed
    )
    
    datasets = simulator.generate_dataset(
        n_samples=n_samples,
        n_points=n_points,
        no_crack_ratio=0.3,
        seed=seed
    )
    
    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    click.echo("Saving generated data...")
    for i, data in enumerate(datasets):
        filename = f"sample_{i:05d}.npy"
        DataLoader.save(data, str(out_dir / filename))
    
    click.echo(f"Generated {len(datasets)} samples saved to {output}")
    click.echo(f"  - With cracks: {sum(1 for d in datasets if d.labels is not None and np.max(d.labels[:, 0]) > 0)}")
    click.echo(f"  - Without cracks: {sum(1 for d in datasets if d.labels is None or np.max(d.labels[:, 0]) == 0)}")


@cli.command()
@click.option('--data-dir', '-d', required=True, type=click.Path(exists=True),
              help='Directory containing training data')
@click.option('--model-dir', '-m', required=True, type=click.Path(),
              help='Directory to save trained models')
@click.option('--use-cnn', is_flag=True,
              help='Use CNN model instead of SVM (requires PyTorch)')
@click.option('--epochs', type=int, default=Config.CNN_EPOCHS,
              help='Number of epochs for CNN training')
def train(data_dir, model_dir, use_cnn, epochs):
    """Train crack detection models on labeled data."""
    click.echo(f"Loading training data from {data_dir}...")
    datasets = DataLoader.load_directory(data_dir)
    click.echo(f"Loaded {len(datasets)} training samples")
    
    if len(datasets) < 10:
        click.echo("Warning: Small dataset. Consider generating more data with 'simulate' command.")
    
    click.echo("Initializing crack identifier...")
    identifier = CrackIdentifier(use_cnn=use_cnn)
    
    click.echo(f"Training {'CNN' if use_cnn else 'SVM'} model...")
    identifier.fit(datasets, use_cnn=use_cnn)
    
    click.echo("Training complete! Saving models...")
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    identifier.save_models(model_dir)
    click.echo(f"Models saved to {model_dir}")


@cli.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True),
              help='Input data file to analyze')
@click.option('--model-dir', '-m', required=True, type=click.Path(exists=True),
              help='Directory containing trained models')
@click.option('--output', '-o', type=click.Path(),
              help='Output directory for reports')
@click.option('--use-cnn', is_flag=True,
              help='Use CNN model for detection')
@click.option('--report-format', type=click.Choice(['txt', 'json', 'html', 'all']),
              default='all', help='Report output format')
def detect(input, model_dir, output, use_cnn, report_format):
    """Detect cracks in eddy current data and generate reports."""
    click.echo(f"Loading data from {input}...")
    data = DataLoader.load(input)
    
    click.echo("Loading trained models...")
    identifier = CrackIdentifier(use_cnn=use_cnn)
    identifier.load_models(model_dir)
    
    click.echo("Analyzing data for cracks...")
    result = identifier.identify(data, use_cnn=use_cnn)
    
    click.echo("\n=== Detection Results ===")
    click.echo(f"Crack detected: {'YES' if result['has_crack'] else 'NO'}")
    click.echo(f"Confidence: {result['confidence']:.1%}")
    if result['has_crack']:
        click.echo(f"Estimated depth: {result['depth']*1000:.2f} mm")
        click.echo(f"Estimated length: {result['length']*1000:.2f} mm")
        if 'position_mm' in result:
            click.echo(f"Position: {result['position_mm']:.2f} mm")
    
    if output:
        click.echo("\nGenerating reports...")
        reporter = ReportGenerator(output_dir=output)
        report = reporter.generate_report(data, result)
        
        click.echo(f"Report generated: {report['report_path']}")
        click.echo("  Files:")
        for name, path in report.get('figures', {}).items():
            click.echo(f"    - {name}: {os.path.basename(path)}")


@cli.command()
@click.option('--data-dir', '-d', required=True, type=click.Path(exists=True),
              help='Directory containing data to annotate')
@click.option('--output-dir', '-o', type=click.Path(), default='annotations',
              help='Directory to save annotations')
@click.option('--auto', is_flag=True,
              help='Use model for auto-annotation')
@click.option('--model-dir', type=click.Path(exists=True),
              help='Model directory for auto-annotation')
@click.option('--threshold', type=float, default=0.8,
              help='Confidence threshold for auto-annotation')
@click.option('--max-samples', type=int,
              help='Maximum number of samples to annotate')
def annotate(data_dir, output_dir, auto, model_dir, threshold, max_samples):
    """Manually or automatically annotate eddy current data."""
    click.echo("Initializing annotation tool...")
    tool = AnnotationTool(output_dir=output_dir)
    
    click.echo(f"Loading data from {data_dir}...")
    datasets = DataLoader.load_directory(data_dir)
    click.echo(f"Loaded {len(datasets)} samples")
    
    tool.add_unlabeled_data(datasets)
    
    if auto:
        if not model_dir:
            click.echo("Error: --model-dir is required for auto-annotation", err=True)
            return
        
        click.echo("Loading model for auto-annotation...")
        identifier = CrackIdentifier()
        identifier.load_models(model_dir)
        
        click.echo(f"Auto-annotating with confidence threshold {threshold:.1%}...")
        n_annotated = tool.auto_annotate(identifier, confidence_threshold=threshold)
        click.echo(f"Auto-annotated {n_annotated} samples")
    else:
        click.echo("Starting interactive annotation...")
        tool.annotate_interactive(max_samples=max_samples)
    
    click.echo("Saving annotations...")
    tool.save_annotations()
    tool.print_statistics()


@cli.command()
@click.option('--annotations', '-a', type=click.Path(exists=True),
              help='Annotations file path')
def stats(annotations):
    """Show statistics about annotations."""
    tool = AnnotationTool()
    
    if annotations:
        tool.load_annotations(os.path.basename(annotations))
    
    tool.print_statistics()


@cli.command()
@click.option('--data-dir', '-d', required=True, type=click.Path(exists=True),
              help='Directory containing test data')
@click.option('--model-dir', '-m', required=True, type=click.Path(exists=True),
              help='Directory containing trained models')
@click.option('--output', '-o', type=click.Path(), default='reports',
              help='Output directory for batch report')
@click.option('--use-cnn', is_flag=True,
              help='Use CNN model for detection')
def batch(data_dir, model_dir, output, use_cnn):
    """Process multiple files and generate batch report."""
    click.echo(f"Loading data from {data_dir}...")
    datasets = DataLoader.load_directory(data_dir)
    click.echo(f"Loaded {len(datasets)} samples")
    
    click.echo("Loading models...")
    identifier = CrackIdentifier(use_cnn=use_cnn)
    identifier.load_models(model_dir)
    
    click.echo("Processing samples...")
    results = []
    for i, data in enumerate(datasets):
        click.echo(f"  Processing {i+1}/{len(datasets)}...")
        result = identifier.identify(data, use_cnn=use_cnn)
        results.append((data, result))
    
    click.echo("Generating batch report...")
    reporter = ReportGenerator(output_dir=output)
    summary = reporter.generate_batch_report(results)
    
    click.echo("\n=== Batch Summary ===")
    click.echo(f"Total samples: {summary['total_samples']}")
    click.echo(f"Cracks detected: {summary['cracks_detected']}")
    click.echo(f"No crack: {summary['no_crack_count']}")
    click.echo(f"Detection rate: {summary['detection_rate']:.1%}")
    click.echo(f"Average confidence: {summary['average_confidence']:.1%}")


@cli.command()
@click.option('--output', '-o', type=click.Path(), required=True,
              help='Output path for standard dataset')
@click.option('--n-train', type=int, default=200,
              help='Number of training samples')
@click.option('--n-test', type=int, default=50,
              help='Number of test samples')
def generate_dataset(output, n_train, n_test):
    """Generate standard train/test dataset for model training."""
    click.echo(f"Generating standard dataset: {n_train} train + {n_test} test samples...")
    
    dataset = generate_standard_dataset(
        save_path=output,
        n_train=n_train,
        n_test=n_test
    )
    
    X_train, y_train = dataset['train']
    X_test, y_test = dataset['test']
    
    click.echo("\n=== Dataset Summary ===")
    click.echo(f"Training set: {X_train.shape}")
    click.echo(f"  - Crack samples: {int(np.sum(y_train[:, 0]))}")
    click.echo(f"  - No crack samples: {int(len(y_train) - np.sum(y_train[:, 0]))}")
    click.echo(f"Test set: {X_test.shape}")
    click.echo(f"  - Crack samples: {int(np.sum(y_test[:, 0]))}")
    click.echo(f"  - No crack samples: {int(len(y_test) - np.sum(y_test[:, 0]))}")
    click.echo(f"\nDataset saved to {output}")


@cli.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True),
              help='Input data file')
def info(input):
    """Display information about an eddy current data file."""
    data = DataLoader.load(input)
    
    click.echo("\n=== Data Information ===")
    click.echo(f"File: {input}")
    click.echo(f"Shape: {data.impedance.shape}")
    click.echo(f"Data type: {data.impedance.dtype}")
    click.echo(f"Frequencies: {data.frequencies}")
    
    if data.positions is not None:
        click.echo(f"Position range: [{data.positions.min():.4f}, {data.positions.max():.4f}]")
    
    if data.labels is not None:
        click.echo(f"Labels shape: {data.labels.shape}")
        if data.labels.ndim >= 2:
            has_crack = np.max(data.labels[:, 0]) > 0.5
            click.echo(f"Has crack: {'YES' if has_crack else 'NO'}")
            if has_crack:
                click.echo(f"Crack depth: {np.max(data.labels[:, 1])*1000:.2f} mm")
                click.echo(f"Crack length: {np.max(data.labels[:, 2])*1000:.2f} mm")
    
    click.echo(f"\nAmplitude stats:")
    amp = np.abs(data.impedance)
    click.echo(f"  Mean: {amp.mean():.4f}")
    click.echo(f"  Std:  {amp.std():.4f}")
    click.echo(f"  Min:  {amp.min():.4f}")
    click.echo(f"  Max:  {amp.max():.4f}")
    
    if data.metadata:
        click.echo(f"\nMetadata: {data.metadata}")


@cli.group()
def array():
    """Array probe operations: C-scan imaging, multi-channel data fusion."""
    pass


@array.command()
@click.option('--n-elements', '-n', type=int, default=Config.ARRAY_N_ELEMENTS,
              help='Number of probe elements')
@click.option('--element-spacing', '-s', type=float, default=Config.ARRAY_SPACING,
              help='Spacing between elements (m)')
@click.option('--n-positions', '-p', type=int, default=200,
              help='Number of scan positions')
@click.option('--scan-length', '-l', type=float, default=0.2,
              help='Total scan length (m)')
@click.option('--output', '-o', type=click.Path(), required=True,
              help='Output path for simulated array data')
@click.option('--crack', is_flag=True,
              help='Include simulated cracks')
def simulate_array(n_elements, element_spacing, n_positions, scan_length, output, crack):
    """Simulate array probe scan data with optional cracks."""
    click.echo(f"Simulating array probe data ({n_elements} elements)...")
    
    probe_config = ArrayProbeConfig(
        n_elements=n_elements,
        element_spacing=element_spacing
    )
    
    simulator = ArraySimulator(probe_config=probe_config)
    
    crack_params = None
    if crack:
        crack_params = [{
            'center': scan_length * 0.5,
            'length': 0.02,
            'depth': 0.005,
            'y': 0.0
        }]
    
    array_data = simulator.simulate_array_scan(
        n_positions=n_positions,
        scan_length=scan_length,
        crack_params=crack_params
    )
    
    ArrayDataLoader.save_numpy(array_data, output)
    click.echo(f"Array data saved to {output}")
    click.echo(f"  Shape: {array_data.shape}")
    click.echo(f"  Elements: {array_data.n_elements}")
    click.echo(f"  Positions: {array_data.n_positions}")


@array.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True),
              help='Input array data file (.npz)')
@click.option('--output', '-o', type=click.Path(),
              help='Output directory for C-scan images')
@click.option('--quantity', '-q', type=click.Choice(['amplitude', 'phase', 'real', 'imag']),
              default='amplitude', help='Quantity to image')
@click.option('--freq-idx', '-f', type=int, default=0,
              help='Frequency index')
@click.option('--pixel-size', type=float, default=Config.C_SCAN_PIXEL_SIZE,
              help='C-scan pixel size (m)')
@click.option('--detect/--no-detect', default=True,
              help='Detect cracks in C-scan image')
def cscan(input, output, quantity, freq_idx, pixel_size, detect):
    """Generate C-scan image from array probe data."""
    click.echo(f"Loading array data from {input}...")
    array_data = ArrayDataLoader.load_numpy(input)
    click.echo(f"Loaded data: {array_data.shape}")
    
    click.echo(f"Generating C-scan (quantity: {quantity})...")
    cscan_imager = CScanImaging(pixel_size=pixel_size)
    
    cscan_result = cscan_imager.generate_cscan(
        array_data,
        quantity=quantity,
        freq_idx=freq_idx
    )
    
    click.echo(f"C-scan generated: {cscan_result['cscan'].shape}")
    
    if detect:
        click.echo("Detecting cracks in C-scan...")
        cracks = cscan_imager.detect_cracks_in_cscan(cscan_result)
        click.echo(f"Detected {len(cracks)} crack(s):")
        for crack in cracks:
            click.echo(f"  Crack {crack['crack_id']}: "
                       f"confidence={crack['confidence']:.2f}, "
                       f"area={crack['area_pixels']} px, "
                       f"x=[{crack['bbox_x'][0]*1000:.2f}, {crack['bbox_x'][1]*1000:.2f}] mm")
    
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        click.echo("Saving C-scan image...")
        cscan_imager.plot_cscan(
            cscan_result,
            show=False,
            save_path=str(out_path)
        )
        click.echo(f"C-scan image saved to {output}")
        
        if detect and cracks:
            import json
            with open(out_path.parent / 'cracks.json', 'w') as f:
                json.dump(cracks, f, indent=2)
            click.echo("Crack detection results saved to cracks.json")
    else:
        cscan_imager.plot_cscan(cscan_result)


@array.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True),
              help='Input array data file')
@click.option('--output', '-o', type=click.Path(),
              help='Output path for fused data')
@click.option('--method', '-m', type=click.Choice(['static', 'dynamic']),
              default='dynamic', help='Fusion method')
def fuse(input, output, method):
    """Fuse multi-channel array data into single channel."""
    click.echo(f"Loading array data from {input}...")
    array_data = ArrayDataLoader.load_numpy(input)
    
    click.echo(f"Fusing {array_data.n_elements} channels ({method} weighting)...")
    fusion = ArrayDataFusion(array_data.probe_config)
    
    if method == 'static':
        fused = fusion.fit_transform(array_data)
    else:
        fused = fusion.dynamic_fusion(array_data)
    
    click.echo(f"Fused data shape: {fused.shape}")
    
    if output:
        np.save(output, fused)
        click.echo(f"Fused data saved to {output}")


@cli.group()
def pinn():
    """Physics-Informed Neural Network (PINN) operations."""
    pass


@pinn.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True),
              help='Input data file')
@click.option('--freq-idx', '-f', type=int, multiple=True, default=[0],
              help='Frequency indices (can specify multiple)')
@click.option('--multi-freq/--single-freq', default=True,
              help='Use multi-frequency fusion')
@click.option('--epochs', '-e', type=int, default=100,
              help='Number of training epochs')
@click.option('--pde-weight', type=float, default=Config.PINN_PDE_WEIGHT,
              help='PDE loss weight')
@click.option('--output', '-o', type=click.Path(),
              help='Output directory for inversion results')
def invert(input, freq_idx, multi_freq, epochs, pde_weight, output):
    """Invert eddy current data using PINN to reconstruct crack profile."""
    if not PINN_AVAILABLE:
        click.echo("Error: PyTorch is required for PINN inversion. Install with: pip install torch", err=True)
        return
    
    click.echo(f"Loading data from {input}...")
    data = DataLoader.load(input)
    
    click.echo("Initializing PINN inverter...")
    pinn_config = PINNConfig(
        epochs=epochs,
        pde_weight=pde_weight
    )
    inverter = PINNInverter(pinn_config)
    
    freq_indices = list(freq_idx)
    click.echo(f"Inverting using frequencies: {[data.frequencies[i] for i in freq_indices]}")
    
    result = inverter.invert(
        data,
        freq_indices=freq_indices,
        use_multi_freq=multi_freq,
        verbose=True
    )
    
    if 'fused' in result:
        cracks = result['fused']['cracks']
    else:
        cracks = result['reconstruction']['cracks']
    
    click.echo(f"\n=== Inversion Results ===")
    click.echo(f"Cracks detected: {len(cracks)}")
    for crack in cracks:
        click.echo(f"\nCrack {crack['crack_id']}:")
        click.echo(f"  Center: ({crack['center'][0]*1000:.2f}, {crack['center'][1]*1000:.2f}) mm")
        click.echo(f"  Length X: {crack['length_x']*1000:.2f} mm")
        click.echo(f"  Length Y: {crack['length_y']*1000:.2f} mm")
        click.echo(f"  Estimated depth: {crack['estimated_depth']*1000:.2f} mm")
        click.echo(f"  Confidence: {crack['confidence']:.2f}")
    
    if output:
        import json
        out_path = Path(output)
        out_path.mkdir(parents=True, exist_ok=True)
        
        click.echo("\nSaving inversion results...")
        
        save_result = {
            'multi_freq': result.get('multi_freq', False),
            'cracks': cracks,
        }
        
        if 'fused' in result:
            save_result['fused'] = {
                'reconstructed_amplitude': result['fused']['reconstructed_amplitude'].tolist(),
                'grid_x': result['fused']['grid_x'].tolist(),
                'grid_y': result['fused']['grid_y'].tolist(),
                'baseline': result['fused']['baseline'],
                'threshold': result['fused']['threshold']
            }
        else:
            save_result['reconstruction'] = {
                'reconstructed_amplitude': result['reconstruction']['reconstructed_amplitude'].tolist(),
                'grid_x': result['reconstruction']['grid_x'].tolist(),
                'grid_y': result['reconstruction']['grid_y'].tolist(),
                'baseline': result['reconstruction']['baseline'],
                'threshold': result['reconstruction']['threshold']
            }
        
        with open(out_path / 'inversion_result.json', 'w') as f:
            json.dump(save_result, f, indent=2, default=lambda x: float(x) if isinstance(x, np.floating) else int(x) if isinstance(x, np.integer) else x)
        
        click.echo(f"Results saved to {out_path}")


@cli.group()
def stream():
    """Real-time streaming operations for online detection."""
    pass


@stream.command()
@click.option('--n-chunks', '-n', type=int, default=20,
              help='Number of chunks to process')
@click.option('--chunk-size', '-s', type=int, default=256,
              help='Samples per chunk')
@click.option('--alarm-threshold', type=float, default=Config.ALARM_THRESHOLD,
              help='Alarm confidence threshold')
@click.option('--alarm-log', type=click.Path(),
              help='Path for alarm log file')
@click.option('--model-dir', '-m', type=click.Path(exists=True),
              help='Trained model directory (optional)')
def simulate_stream(n_chunks, chunk_size, alarm_threshold, alarm_log, model_dir):
    """Simulate real-time streaming detection."""
    click.echo("Initializing simulated streaming...")
    
    stream_config = StreamConfig(
        buffer_size=1024,
        overlap=256,
        alarm_threshold=alarm_threshold
    )
    
    data_source = SimulatedDataSource(
        n_chunks=n_chunks,
        chunk_size=chunk_size,
        n_frequencies=len(Config.DEFAULT_FREQUENCIES),
        crack_probability=0.2
    )
    
    alarm_handlers = [ConsoleAlarmHandler()]
    if alarm_log:
        alarm_handlers.append(FileAlarmHandler(alarm_log))
    
    processor = StreamProcessor(
        config=stream_config,
        alarm_handlers=alarm_handlers
    )
    
    if model_dir:
        click.echo(f"Loading models from {model_dir}...")
        processor.crack_identifier.load_models(model_dir)
    
    click.echo(f"\nStarting simulated stream ({n_chunks} chunks)...")
    click.echo("=" * 60)
    
    results = processor.process_stream(
        data_source,
        verbose=True
    )
    
    click.echo("\n" + "=" * 60)
    click.echo("Stream processing complete!")
    
    stats = processor.get_statistics()
    click.echo(f"\n=== Statistics ===")
    click.echo(f"Total chunks: {stats['total_chunks']}")
    click.echo(f"Alarms triggered: {stats['alarm_count']}")
    click.echo(f"Alarm rate: {stats['alarm_rate']*100:.1f}%")
    click.echo(f"Max crack probability: {stats['max_crack_probability']:.3f}")
    
    if alarm_log:
        click.echo(f"\nAlarm log saved to {alarm_log}")


@stream.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True),
              help='Input data file to stream')
@click.option('--chunk-size', '-s', type=int, default=256,
              help='Samples per chunk')
@click.option('--overlap', '-o', type=int, default=128,
              help='Overlap between chunks')
@click.option('--alarm-threshold', type=float, default=Config.ALARM_THRESHOLD,
              help='Alarm confidence threshold')
@click.option('--alarm-log', type=click.Path(),
              help='Path for alarm log file')
@click.option('--model-dir', '-m', type=click.Path(exists=True),
              help='Trained model directory')
@click.option('--real-time', is_flag=True,
              help='Simulate real-time processing with delays')
def file_stream(input, chunk_size, overlap, alarm_threshold, alarm_log, model_dir, real_time):
    """Stream data from a file with chunk processing."""
    click.echo(f"Loading data from {input}...")
    data = DataLoader.load(input)
    click.echo(f"Data shape: {data.impedance.shape}")
    
    stream_config = StreamConfig(
        buffer_size=1024,
        overlap=overlap,
        alarm_threshold=alarm_threshold
    )
    
    data_source = FileDataSource(
        data=data,
        chunk_size=chunk_size,
        overlap=overlap
    )
    
    alarm_handlers = [ConsoleAlarmHandler()]
    if alarm_log:
        alarm_handlers.append(FileAlarmHandler(alarm_log))
    
    processor = StreamProcessor(
        config=stream_config,
        alarm_handlers=alarm_handlers
    )
    
    click.echo(f"Loading models from {model_dir}...")
    processor.crack_identifier.load_models(model_dir)
    
    click.echo(f"\nStarting file stream processing...")
    click.echo("=" * 60)
    
    results = processor.process_stream(
        data_source,
        verbose=True,
        real_time=real_time
    )
    
    click.echo("\n" + "=" * 60)
    click.echo("Processing complete!")
    
    stats = processor.get_statistics()
    click.echo(f"\n=== Statistics ===")
    click.echo(f"Total chunks: {stats['total_chunks']}")
    click.echo(f"Alarms triggered: {stats['alarm_count']}")
    click.echo(f"Alarm rate: {stats['alarm_rate']*100:.1f}%")
    click.echo(f"Max crack probability: {stats['max_crack_probability']:.3f}")


@stream.command()
@click.option('--n-chunks', '-n', type=int, default=100,
              help='Number of chunks')
@click.option('--chunk-size', '-s', type=int, default=256,
              help='Samples per chunk')
@click.option('--alarm-threshold', type=float, default=Config.ALARM_THRESHOLD,
              help='Alarm confidence threshold')
@click.option('--model-dir', '-m', type=click.Path(exists=True),
              help='Trained model directory (optional)')
def monitor(n_chunks, chunk_size, alarm_threshold, model_dir):
    """Real-time monitoring with live display."""
    click.echo("Initializing real-time monitor...")
    
    stream_config = StreamConfig(
        buffer_size=1024,
        overlap=256,
        alarm_threshold=alarm_threshold
    )
    
    data_source = SimulatedDataSource(
        n_chunks=n_chunks,
        chunk_size=chunk_size,
        n_frequencies=len(Config.DEFAULT_FREQUENCIES),
        crack_probability=0.2
    )
    
    processor = StreamProcessor(
        config=stream_config,
        alarm_handlers=[ConsoleAlarmHandler()]
    )
    
    if model_dir:
        processor.crack_identifier.load_models(model_dir)
    
    monitor = RealTimeMonitor(processor, update_interval=1.0)
    
    click.echo("Starting real-time monitoring. Press Ctrl+C to stop...")
    try:
        monitor.start(data_source)
        import time
        while processor.is_running:
            time.sleep(1.0)
    except KeyboardInterrupt:
        click.echo("\nStopping...")
    finally:
        monitor.stop()
    
    stats = processor.get_statistics()
    click.echo(f"\nFinal Stats: Alarms={stats['alarm_count']}, "
               f"Chunks={stats['total_chunks']}")


if __name__ == '__main__':
    cli()
