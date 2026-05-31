import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import cv2

import click
from tqdm import tqdm

from .geotiff_reader import GeoTIFFReader
from .preprocessor import Preprocessor, PreprocessingParams
from .wave_detector import WaveDetector, WaveDetectionParams
from .wavefront_extractor import WavefrontExtractor, WavefrontParams
from .amplitude_inverter import AmplitudeInverter, InversionParams
from .wave_tracker import WaveTracker, TrackParams
from .kml_exporter import KMLExporter, KMLExportParams
from .cnn_detector import CNNWaveDetector, CNNDetectionParams
from .ts_inverter import TSInverter, TSInversionParams
from .wave_breaking import WaveBreakingModel, BreakingParams

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sariw.cli')


def setup_output_dir(output_path: str) -> str:
    """Create output directory if it doesn't exist."""
    output_dir = os.path.dirname(output_path) if output_path else '.'
    if not output_dir:
        output_dir = '.'
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def save_image(image: np.ndarray, output_path: str) -> None:
    """Save image to file."""
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    cv2.imwrite(output_path, image)
    logger.info(f"Saved image: {output_path}")


def save_results_json(results: dict, output_path: str) -> None:
    """Save results to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Saved results JSON: {output_path}")


def process_single_image(input_path: str, output_dir: str,
                         preproc_params: PreprocessingParams,
                         detect_params: WaveDetectionParams,
                         wavefront_params: WavefrontParams,
                         invert_params: InversionParams,
                         kml_params: KMLExportParams,
                         save_visuals: bool = True,
                         cnn_params: Optional[CNNDetectionParams] = None,
                         ts_params: Optional[TSInversionParams] = None,
                         breaking_params: Optional[BreakingParams] = None,
                         observations: Optional[List[Dict[str, Any]]] = None) -> dict:
    """
    Process a single SAR image with all advanced features.

    Args:
        input_path: Path to input GeoTIFF
        output_dir: Output directory
        preproc_params: Preprocessing parameters
        detect_params: Detection parameters
        wavefront_params: Wavefront parameters
        invert_params: Inversion parameters
        kml_params: KML export parameters
        save_visuals: Whether to save visualization images
        cnn_params: Optional CNN detection parameters
        ts_params: Optional T-S inversion parameters
        breaking_params: Optional wave breaking simulation parameters
        observations: Optional in-situ observations for assimilation

    Returns:
        Dictionary of results
    """
    basename = os.path.splitext(os.path.basename(input_path))[0]
    logger.info(f"Processing: {input_path}")

    with GeoTIFFReader(input_path) as reader:
        geotiff_data = reader.read(band=1)

    pixel_res = geotiff_data.get_pixel_resolution()
    logger.info(f"Pixel resolution: {pixel_res[0]:.2f} x {pixel_res[1]:.2f} m")

    preprocessor = Preprocessor(preproc_params)
    preprocessed = preprocessor.process(geotiff_data.data)

    img_stats = preprocessor.compute_image_statistics(preprocessed)
    logger.info(f"Image stats: mean={img_stats['mean']:.3f}, std={img_stats['std']:.3f}, SNR={img_stats['snr']:.2f}")

    cnn_result = None
    if cnn_params is not None:
        logger.info("\n=== CNN-based End-to-End Detection ===")
        cnn_detector = CNNWaveDetector(cnn_params)
        cnn_result = cnn_detector.detect(preprocessed)
        logger.info(f"CNN detected {len(cnn_result.detections)} waves in {cnn_result.inference_time:.3f}s")
        logger.info(f"  Model: {cnn_result.model_used}, NumPy fallback: {cnn_result.numpy_fallback_used}")

        if save_visuals:
            cnn_viz = cnn_detector.visualize_detection(cnn_result, preprocessed)
            save_image(cnn_viz, os.path.join(output_dir, f"{basename}_cnn_detection.png"))

    detector = WaveDetector(detect_params)
    detection_result = detector.detect(preprocessed, pixel_res)

    extractor = WavefrontExtractor(wavefront_params)
    wavefront_result = extractor.extract(preprocessed, detection_result)

    inverter = AmplitudeInverter(invert_params)
    inversion_result = inverter.invert(detection_result, wavefront_result)

    inverter.print_inversion_summary(inversion_result)

    ts_result = None
    if ts_params is not None:
        logger.info("\n=== Joint T-S Profile Inversion ===")
        ts_inverter = TSInverter(ts_params)

        wave_amplitudes = [w.amplitude for w in inversion_result.inverted_waves]
        wave_wavelengths = [w.wavelength for w in inversion_result.inverted_waves]
        phase_speeds = [w.phase_speed for w in inversion_result.inverted_waves]
        g_prime = inversion_result.density_ratio * invert_params.gravity

        ts_result = ts_inverter.invert(
            wave_amplitudes=wave_amplitudes,
            wave_wavelengths=wave_wavelengths,
            phase_speeds=phase_speeds,
            g_prime=g_prime,
            observations=observations
        )
        ts_inverter.print_inversion_summary(ts_result)

        if save_visuals:
            ts_plot_path = os.path.join(output_dir, f"{basename}_ts_profiles.png")
            ts_inverter.visualize_profiles(ts_result, save_path=ts_plot_path)

    breaking_result = None
    if breaking_params is not None:
        logger.info("\n=== Wave Breaking & Roughness Simulation ===")
        breaking_model = WaveBreakingModel(breaking_params)

        wave_amplitudes = [w.amplitude for w in inversion_result.inverted_waves]
        wave_wavelengths = [w.wavelength for w in inversion_result.inverted_waves]
        wave_directions = [w.direction for w in detection_result.waves]
        wave_centers = [(w.center_row, w.center_col) for w in detection_result.waves]

        ts_profile = ts_result.background_profile if ts_result else None

        breaking_result = breaking_model.simulate(
            image=preprocessed,
            wave_amplitudes=wave_amplitudes,
            wave_wavelengths=wave_wavelengths,
            wave_directions=wave_directions,
            wave_centers=wave_centers,
            wind_speed=invert_params.wind_speed,
            ts_profile=ts_profile,
            pixel_resolution=pixel_res
        )
        breaking_model.print_simulation_summary(breaking_result)

        if save_visuals:
            breaking_plot_path = os.path.join(output_dir, f"{basename}_breaking_simulation.png")
            breaking_model.visualize_simulation(breaking_result, preprocessed, save_path=breaking_plot_path)

    results = {
        'input_file': input_path,
        'image_statistics': img_stats,
        'pixel_resolution': pixel_res,
        'dominant_direction': detection_result.dominant_direction,
        'dominant_spacing': detection_result.dominant_spacing,
        'direction_confidence': detection_result.direction_confidence,
        'num_waves_detected': len(detection_result.waves),
        'num_wavefronts': len(wavefront_result.wavefronts),
        'inversion': {
            'reduced_gravity': inversion_result.density_ratio * invert_params.gravity,
            'buoyancy_frequency': inversion_result.buoyancy_frequency,
            'waves': []
        },
        'advanced_features': {
            'cnn_detection': cnn_result is not None,
            'ts_inversion': ts_result is not None,
            'breaking_simulation': breaking_result is not None
        }
    }

    for wave, inv in zip(detection_result.waves, inversion_result.inverted_waves):
        lon, lat = wave.center_geo(geotiff_data)
        wave_data = {
            'wave_id': wave.wave_id,
            'center': {'lon': lon, 'lat': lat, 'row': wave.center_row, 'col': wave.center_col},
            'direction': wave.direction,
            'wavelength': wave.wavelength,
            'spacing': wave.spacing,
            'contrast': wave.contrast,
            'detection_confidence': wave.confidence,
            'amplitude': inv.amplitude,
            'half_width': inv.half_width,
            'phase_speed': inv.phase_speed,
            'wave_energy': inv.wave_energy,
            'inversion_confidence': inv.confidence,
            'inverse_method': inv.inverse_method
        }
        results['inversion']['waves'].append(wave_data)

    if cnn_result is not None:
        results['cnn_detection'] = {
            'num_detections': len(cnn_result.detections),
            'inference_time': cnn_result.inference_time,
            'model_used': cnn_result.model_used,
            'numpy_fallback': cnn_result.numpy_fallback_used,
            'detections': [
                {
                    'wave_id': d.wave_id,
                    'bbox': d.bbox,
                    'center_row': d.center_row,
                    'center_col': d.center_col,
                    'confidence': d.confidence,
                    'direction': d.direction,
                    'wavelength': d.wavelength
                }
                for d in cnn_result.detections
            ]
        }

    if ts_result is not None and ts_result.background_profile is not None:
        prof = ts_result.background_profile
        results['ts_inversion'] = {
            'mixed_layer_depth': ts_result.mixed_layer_depth,
            'pycnocline_depth': ts_result.pycnocline_depth,
            'stratification_strength': ts_result.stratification_strength,
            'max_buoyancy_frequency': float(np.max(prof.buoyancy_frequency)),
            'inversion_uncertainty': ts_result.inversion_uncertainty,
            'energy_conversion_rate': ts_result.energy_conversion_rate,
            'key_depth_levels': {},
            'profile': {
                'depth': prof.depth.tolist(),
                'temperature': prof.temperature.tolist(),
                'salinity': prof.salinity.tolist(),
                'density': prof.density.tolist(),
                'buoyancy_frequency': prof.buoyancy_frequency.tolist()
            }
        }
        if prof.sound_speed is not None:
            results['ts_inversion']['profile']['sound_speed'] = prof.sound_speed.tolist()

        key_depths = [0, 10, 25, 50, 100, 150, 200]
        for z in key_depths:
            if z <= prof.depth[-1]:
                results['ts_inversion']['key_depth_levels'][f'{z}m'] = {
                    'temperature': float(prof.get_value_at_depth(z, 'temperature')),
                    'salinity': float(prof.get_value_at_depth(z, 'salinity')),
                    'density': float(prof.get_value_at_depth(z, 'density')),
                    'buoyancy_frequency': float(prof.get_value_at_depth(z, 'buoyancy_frequency'))
                }

    if breaking_result is not None:
        results['breaking_simulation'] = {
            'num_breaking_regions': len(breaking_result.breaking_regions),
            'total_breaking_area': breaking_result.total_breaking_area,
            'total_energy_dissipation': breaking_result.total_energy_dissipation,
            'mean_breaking_probability': breaking_result.mean_breaking_probability,
            'breaking_type_distribution': breaking_result.breaking_type_distribution,
            'simulation_time': breaking_result.simulation_time,
            'regions': [
                {
                    'region_id': r.region_id,
                    'center_row': r.center_row,
                    'center_col': r.center_col,
                    'area': r.area,
                    'probability': r.probability,
                    'breaking_type': r.breaking_type,
                    'richardson_number': r.richardson_number,
                    'amplitude_depth_ratio': r.amplitude_depth_ratio,
                    'wave_steepness': r.wave_steepness,
                    'energy_dissipation': r.energy_dissipation,
                    'turbulence_intensity': r.turbulence_intensity,
                    'surface_roughness': r.surface_roughness,
                    'radar_backscatter': r.radar_backscatter
                }
                for r in breaking_result.breaking_regions
            ]
        }

    if save_visuals:
        detection_viz = detector.visualize_detection(detection_result, preprocessed)
        save_image(detection_viz, os.path.join(output_dir, f"{basename}_detection.png"))

        wavefront_viz = extractor.visualize(wavefront_result, preprocessed)
        save_image(wavefront_viz, os.path.join(output_dir, f"{basename}_wavefronts.png"))

        if wavefront_result.edge_image is not None:
            edges = wavefront_result.edge_image
            edges_color = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            save_image(edges_color, os.path.join(output_dir, f"{basename}_edges.png"))

        radon_viz = detector.visualize_radon(detection_result)
        save_image(radon_viz, os.path.join(output_dir, f"{basename}_radon.png"))

    exporter = KMLExporter(kml_params)
    kml_path = os.path.join(output_dir, f"{basename}_output.kml")
    exporter.export(geotiff_data, detection_result, inversion_result, wavefront_result, kml_path)

    geojson_path = os.path.join(output_dir, f"{basename}_output.geojson")
    exporter.export_geojson(geotiff_data, detection_result, inversion_result, wavefront_result, geojson_path)

    json_path = os.path.join(output_dir, f"{basename}_results.json")
    save_results_json(results, json_path)

    return {
        'geotiff': geotiff_data,
        'detection': detection_result,
        'wavefront': wavefront_result,
        'inversion': inversion_result,
        'cnn_detection': cnn_result,
        'ts_inversion': ts_result,
        'breaking_simulation': breaking_result,
        'results_dict': results
    }


@click.group()
@click.version_option(version='2.0.0')
def main():
    """
    SARIW v2.0 - SAR Image Internal Wave Detection and Analysis Tool.

    Advanced features:
    \b
    --use-cnn        CNN-based end-to-end wave detection
    --invert-ts      Joint temperature-salinity profile inversion
    --simulate-breaking  Wave breaking and roughness simulation

    Basic features:
    - Wave packet separation with interference correction
    - KdV/eKdV amplitude inversion
    - Multi-frame wave tracking
    - KML/GeoJSON export
    """
    pass


@main.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), default='output',
              help='Output directory')
@click.option('--wind-speed', type=float, default=5.0,
              help='Surface wind speed in m/s')
@click.option('--water-depth', type=float, default=100.0,
              help='Water depth in meters')
@click.option('--upper-layer-thickness', type=float, default=20.0,
              help='Upper mixed layer thickness in meters')
@click.option('--density-difference', type=float, default=3.0,
              help='Density difference between layers in kg/m³')
@click.option('--denoise-method', type=click.Choice(
    ['none', 'bilateral', 'gaussian', 'median', 'wiener', 'tv']),
    default='bilateral', help='Denoising method')
@click.option('--contrast-method', type=click.Choice(
    ['none', 'clahe', 'equalize', 'percentile', 'adaptive']),
    default='clahe', help='Contrast enhancement method')
@click.option('--enable-wavepacket-separation/--disable-wavepacket-separation',
              default=True, help='Enable/disable wave packet separation')
@click.option('--interference-correction/--no-interference-correction',
              default=True, help='Enable/disable interference correction')
@click.option('--max-waves-per-packet', type=int, default=5,
              help='Maximum number of waves to separate per packet')
@click.option('--use-ekdv/--no-ekdv', default=True,
              help='Enable/disable eKdV equation for shallow water')
@click.option('--ekdv-threshold', type=float, default=0.3,
              help='h1/h2 threshold for eKdV activation')
@click.option('--low-wind-mode/--no-low-wind-mode', default=False,
              help='Enable low-wind signal enhancement (for wind < 3 m/s)')
@click.option('--low-wind-enhancement', type=float, default=2.0,
              help='Low-wind signal enhancement factor')
@click.option('--use-cnn/--no-cnn', default=False,
              help='Enable CNN-based end-to-end wave detection')
@click.option('--cnn-confidence', type=float, default=0.5,
              help='CNN detection confidence threshold')
@click.option('--invert-ts/--no-invert-ts', default=False,
              help='Enable joint temperature-salinity profile inversion')
@click.option('--surface-temperature', type=float, default=25.0,
              help='Sea surface temperature (°C) for T-S inversion')
@click.option('--surface-salinity', type=float, default=35.0,
              help='Sea surface salinity (PSU) for T-S inversion')
@click.option('--bottom-temperature', type=float, default=5.0,
              help='Deep water temperature (°C) for T-S inversion')
@click.option('--bottom-salinity', type=float, default=34.5,
              help='Deep water salinity (PSU) for T-S inversion')
@click.option('--thermocline-depth', type=float, default=50.0,
              help='Thermocline depth (m) for T-S inversion')
@click.option('--assimilate-obs', type=str, default=None,
              help='JSON file with in-situ observations for assimilation')
@click.option('--simulate-breaking/--no-simulate-breaking', default=False,
              help='Enable wave breaking and surface roughness simulation')
@click.option('--save-visuals/--no-visuals', default=True,
              help='Save visualization images')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def analyze(input_path, output, wind_speed, water_depth, upper_layer_thickness,
            density_difference, denoise_method, contrast_method,
            enable_wavepacket_separation, interference_correction,
            max_waves_per_packet, use_ekdv, ekdv_threshold,
            low_wind_mode, low_wind_enhancement,
            use_cnn, cnn_confidence,
            invert_ts, surface_temperature, surface_salinity,
            bottom_temperature, bottom_salinity,
            thermocline_depth, assimilate_obs,
            simulate_breaking,
            save_visuals, verbose):
    """
    Analyze a single SAR image for internal waves.

    INPUT_PATH: Path to the input SAR GeoTIFF file

    Advanced Features:
    --use-cnn: CNN-based end-to-end detection (skips hand-crafted features)
    --invert-ts: Joint temperature-salinity profile inversion from wave dynamics
    --simulate-breaking: Wave breaking probability and surface roughness simulation

    Basic Features:
    - Wave packet separation: Detects multiple individual waves within a packet
    - Interference correction: Corrects contrast for wave-wave interference
    - eKdV equation: Automatically uses extended KdV for shallow water (h1/h2 > threshold)
    - Low-wind enhancement: Improves detection in low wind conditions (< 3 m/s)
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    output_dir = setup_output_dir(output)
    logger.info(f"Output directory: {output_dir}")

    if low_wind_mode and wind_speed > 3.0:
        logger.warning(f"Low-wind mode enabled but wind speed ({wind_speed:.1f} m/s) > 3 m/s. "
                      f"Consider disabling --low-wind-mode for better performance.")

    preproc_params = PreprocessingParams(
        denoise_method=denoise_method,
        contrast_method=contrast_method
    )

    detect_params = WaveDetectionParams(
        enable_wavepacket_separation=enable_wavepacket_separation,
        interference_correction=interference_correction,
        max_waves_per_packet=max_waves_per_packet,
        low_wind_mode=low_wind_mode,
        low_wind_enhancement=low_wind_enhancement
    )

    wavefront_params = WavefrontParams()

    invert_params = InversionParams(
        wind_speed=wind_speed,
        water_depth=water_depth,
        upper_layer_thickness=upper_layer_thickness,
        lower_layer_density=1024.0 + density_difference,
        upper_layer_density=1024.0,
        use_ekdv=use_ekdv,
        ekdv_threshold_ratio=ekdv_threshold
    )

    kml_params = KMLExportParams()

    cnn_params = None
    if use_cnn:
        cnn_params = CNNDetectionParams(
            confidence_threshold=cnn_confidence,
            use_gpu=False
        )

    ts_params = None
    if invert_ts:
        ts_params = TSInversionParams(
            surface_temperature=surface_temperature,
            surface_salinity=surface_salinity,
            bottom_temperature=bottom_temperature,
            bottom_salinity=bottom_salinity,
            thermocline_depth=thermocline_depth,
            max_depth=water_depth
        )

    breaking_params = None
    if simulate_breaking:
        breaking_params = BreakingParams()

    observations = None
    if assimilate_obs and os.path.exists(assimilate_obs):
        import json
        with open(assimilate_obs, 'r') as f:
            observations = json.load(f)
        logger.info(f"Loaded {len(observations)} observations for assimilation")

    try:
        process_single_image(
            input_path, output_dir,
            preproc_params, detect_params, wavefront_params, invert_params, kml_params,
            save_visuals,
            cnn_params=cnn_params,
            ts_params=ts_params,
            breaking_params=breaking_params,
            observations=observations
        )
        click.echo(f"\n✓ Analysis completed successfully!")
        click.echo(f"  Output files in: {output_dir}")
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        click.echo(f"\n✗ Analysis failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument('input_paths', nargs=-1, type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), default='track_output',
              help='Output directory')
@click.option('--time-interval', type=float, default=3600.0,
              help='Time interval between frames in seconds')
@click.option('--time-intervals', type=str, default=None,
              help='Comma-separated list of time intervals for each frame pair')
@click.option('--wind-speed', type=float, default=5.0,
              help='Surface wind speed in m/s')
@click.option('--water-depth', type=float, default=100.0,
              help='Water depth in meters')
@click.option('--upper-layer-thickness', type=float, default=20.0,
              help='Upper mixed layer thickness in meters')
@click.option('--enable-wavepacket-separation/--disable-wavepacket-separation',
              default=True, help='Enable/disable wave packet separation')
@click.option('--interference-correction/--no-interference-correction',
              default=True, help='Enable/disable interference correction')
@click.option('--use-ekdv/--no-ekdv', default=True,
              help='Enable/disable eKdV equation for shallow water')
@click.option('--ekdv-threshold', type=float, default=0.3,
              help='h1/h2 threshold for eKdV activation')
@click.option('--low-wind-mode/--no-low-wind-mode', default=False,
              help='Enable low-wind signal enhancement')
@click.option('--max-track-distance', type=float, default=50.0,
              help='Maximum distance for wave association in meters')
@click.option('--save-visuals/--no-visuals', default=True,
              help='Save visualization images')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def track(input_paths, output, time_interval, time_intervals, wind_speed,
          water_depth, upper_layer_thickness, enable_wavepacket_separation,
          interference_correction, use_ekdv, ekdv_threshold, low_wind_mode,
          max_track_distance, save_visuals, verbose):
    """
    Track internal waves across multiple SAR image frames.

    INPUT_PATHS: Paths to input SAR GeoTIFF files (ordered by time)
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if len(input_paths) < 2:
        click.echo("✗ At least 2 input files are required for tracking", err=True)
        sys.exit(1)

    output_dir = setup_output_dir(output)
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Processing {len(input_paths)} frames for tracking...")

    if time_intervals:
        time_intervals_list = [float(x) for x in time_intervals.split(',')]
        if len(time_intervals_list) != len(input_paths) - 1:
            click.echo(
                f"✗ Expected {len(input_paths) - 1} time intervals, got {len(time_intervals_list)}",
                err=True
            )
            sys.exit(1)
    else:
        time_intervals_list = [time_interval] * (len(input_paths) - 1)

    preproc_params = PreprocessingParams()
    detect_params = WaveDetectionParams(
        enable_wavepacket_separation=enable_wavepacket_separation,
        interference_correction=interference_correction,
        low_wind_mode=low_wind_mode
    )
    wavefront_params = WavefrontParams()
    invert_params = InversionParams(
        wind_speed=wind_speed,
        water_depth=water_depth,
        upper_layer_thickness=upper_layer_thickness,
        use_ekdv=use_ekdv,
        ekdv_threshold_ratio=ekdv_threshold
    )
    kml_params = KMLExportParams()
    track_params = TrackParams(max_distance=max_track_distance)

    frame_results = []
    for i, input_path in enumerate(tqdm(input_paths, desc="Processing frames")):
        try:
            result = process_single_image(
                input_path, output_dir,
                preproc_params, detect_params, wavefront_params, invert_params, kml_params,
                save_visuals
            )
            frame_results.append(result)
        except Exception as e:
            logger.error(f"Failed to process frame {i} ({input_path}): {e}")
            click.echo(f"✗ Frame {i} processing failed: {e}", err=True)

    if len(frame_results) < 2:
        click.echo("✗ Need at least 2 successfully processed frames for tracking", err=True)
        sys.exit(1)

    tracker = WaveTracker(track_params)
    tracking_result = tracker.track(frame_results, time_intervals_list)
    tracker.print_tracking_summary(tracking_result)

    tracks_kml_path = os.path.join(output_dir, 'tracks.kml')
    tracker.export_tracks_kml(tracking_result, tracks_kml_path)

    tracks_geojson_path = os.path.join(output_dir, 'tracks.geojson')
    tracker.export_tracks_geojson(tracking_result, tracks_geojson_path)

    tracks_json = {
        'num_frames': tracking_result.num_frames,
        'total_waves': tracking_result.total_waves,
        'num_tracks': len(tracking_result.tracks),
        'time_intervals': time_intervals_list,
        'tracks': []
    }

    for track in tracking_result.tracks:
        tracks_json['tracks'].append({
            'track_id': track.track_id,
            'wave_ids': track.wave_ids,
            'frames': track.frames,
            'positions': track.positions,
            'timestamps': track.timestamps,
            'directions': track.directions,
            'wavelengths': track.wavelengths,
            'amplitudes': track.amplitudes,
            'mean_velocity': track.mean_velocity,
            'attenuation_rate': track.attenuation_rate,
            'lifetime': track.lifetime
        })

    json_path = os.path.join(output_dir, 'tracking_results.json')
    save_results_json(tracks_json, json_path)

    click.echo(f"\n✓ Tracking completed successfully!")
    click.echo(f"  Found {len(tracking_result.tracks)} valid tracks")
    click.echo(f"  Output files in: {output_dir}")


@main.command()
@click.option('--output', '-o', type=click.Path(), default='.',
              help='Output directory for sample data')
@click.option('--size', type=int, default=256,
              help='Image size (pixels)')
@click.option('--num-waves', type=int, default=3,
              help='Number of synthetic waves')
def generate_sample(output, size, num_waves):
    """
    Generate sample synthetic SAR image with internal waves for testing.
    """
    output_dir = setup_output_dir(output)
    output_path = os.path.join(output_dir, 'sample_sar_image.tif')

    logger.info(f"Generating sample SAR image: {output_path}")

    try:
        import rasterio
        from rasterio.transform import from_origin

        image = np.random.normal(0.5, 0.1, (size, size)).astype(np.float32)

        for i in range(num_waves):
            x0 = np.random.uniform(size * 0.2, size * 0.8)
            y0 = np.random.uniform(size * 0.2, size * 0.8)
            direction = np.random.uniform(0, 180)
            wavelength = np.random.uniform(20, 80)
            amplitude = np.random.uniform(0.1, 0.3)
            width = np.random.uniform(30, 100)

            y, x = np.mgrid[0:size, 0:size]

            dir_rad = np.deg2rad(direction)
            perp_dir = dir_rad + np.pi / 2
            dist = (x - x0) * np.cos(perp_dir) + (y - y0) * np.sin(perp_dir)
            along_dist = (x - x0) * np.cos(dir_rad) + (y - y0) * np.sin(dir_rad)

            envelope = np.exp(-(along_dist / width)**2)
            wave_pattern = amplitude * envelope * np.cos(2 * np.pi * dist / wavelength)

            image += wave_pattern

        image = np.clip(image, 0, 1)

        transform = from_origin(-118.0, 34.0, 0.0001, 0.0001)

        with rasterio.open(
            output_path, 'w',
            driver='GTiff',
            height=size,
            width=size,
            count=1,
            dtype=image.dtype,
            crs='EPSG:4326',
            transform=transform,
        ) as dst:
            dst.write(image, 1)

        click.echo(f"✓ Sample image generated: {output_path}")
        click.echo(f"  Size: {size}x{size} pixels")
        click.echo(f"  Synthetic waves: {num_waves}")
        click.echo(f"  Coordinates: ~34°N, 118°W")
    except ImportError:
        click.echo("✗ rasterio not available, cannot generate GeoTIFF. Install rasterio first.", err=True)
        sys.exit(1)


@main.command()
def info():
    """Show information about SARIW tool."""
    from . import __version__
    click.echo("""
╔══════════════════════════════════════════════════════════════╗
║   SARIW - SAR Internal Wave Detection and Analysis Tool    ║
║                     Version """ + __version__ + """                           ║
╠══════════════════════════════════════════════════════════════╣
║  Features:                                                 ║
║    • GeoTIFF reading with coordinate transformation        ║
║    • SAR image preprocessing (denoising, contrast)        ║
║    • Radon transform for wave direction estimation        ║
║    • Canny edge detection for wavefront extraction        ║
║    • KdV equation based amplitude inversion               ║
║    • Multi-frame wave tracking and attenuation analysis   ║
║    • KML/GeoJSON export for Google Earth visualization    ║
╠══════════════════════════════════════════════════════════════╣
║  Usage:                                                    ║
║    sariw analyze <input.tif> [options]                    ║
║    sariw track <frame1.tif> <frame2.tif> ... [options]    ║
║    sariw generate-sample [options]                         ║
║                                                            ║
║  For detailed help:                                        ║
║    sariw analyze --help                                    ║
║    sariw track --help                                      ║
╚══════════════════════════════════════════════════════════════╝
    """)


if __name__ == '__main__':
    main()
