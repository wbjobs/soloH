#!/usr/bin/env python
"""
Basic usage example for SARIW library.

This example demonstrates how to use the SARIW library programmatically
to detect and analyze internal waves in a SAR image.
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sariw.geotiff_reader import GeoTIFFReader
from sariw.preprocessor import Preprocessor, PreprocessingParams
from sariw.wave_detector import WaveDetector, WaveDetectionParams
from sariw.wavefront_extractor import WavefrontExtractor, WavefrontParams
from sariw.amplitude_inverter import AmplitudeInverter, InversionParams
from sariw.kml_exporter import KMLExporter, KMLExportParams


def analyze_single_image(input_path: str, output_dir: str):
    """
    Analyze a single SAR image for internal waves.

    Args:
        input_path: Path to input GeoTIFF
        output_dir: Output directory
    """
    os.makedirs(output_dir, exist_ok=True)
    basename = os.path.splitext(os.path.basename(input_path))[0]

    logger.info(f"Reading GeoTIFF: {input_path}")
    with GeoTIFFReader(input_path) as reader:
        geotiff_data = reader.read(band=1)

    pixel_res = geotiff_data.get_pixel_resolution()
    logger.info(f"Pixel resolution: {pixel_res[0]:.2f} x {pixel_res[1]:.2f} m")

    logger.info("Preprocessing image...")
    preproc_params = PreprocessingParams(
        denoise_method='bilateral',
        denoise_strength=5,
        contrast_method='clahe',
        clahe_clip_limit=2.0,
        remove_background=True,
        speckle_filter=True
    )
    preprocessor = Preprocessor(preproc_params)
    preprocessed = preprocessor.process(geotiff_data.data)

    img_stats = preprocessor.compute_image_statistics(preprocessed)
    logger.info(f"Image SNR: {img_stats['snr']:.2f}")

    logger.info("Detecting internal waves...")
    detect_params = WaveDetectionParams()
    detector = WaveDetector(detect_params)
    detection_result = detector.detect(preprocessed, pixel_res)

    logger.info(f"Found {len(detection_result.waves)} wave packets")
    logger.info(f"Dominant direction: {detection_result.dominant_direction:.1f}°")
    logger.info(f"Dominant spacing: {detection_result.dominant_spacing:.1f}m")

    logger.info("Extracting wavefronts...")
    wavefront_params = WavefrontParams()
    extractor = WavefrontExtractor(wavefront_params)
    wavefront_result = extractor.extract(preprocessed, detection_result)

    logger.info(f"Extracted {len(wavefront_result.wavefronts)} wavefronts")

    logger.info("Inverting wave amplitudes...")
    invert_params = InversionParams(
        wind_speed=5.0,
        water_depth=100.0,
        upper_layer_thickness=20.0,
        upper_layer_density=1024.0,
        lower_layer_density=1027.0
    )
    inverter = AmplitudeInverter(invert_params)
    inversion_result = inverter.invert(detection_result, wavefront_result)

    inverter.print_inversion_summary(inversion_result)

    logger.info("Exporting results...")
    kml_params = KMLExportParams()
    exporter = KMLExporter(kml_params)

    kml_path = os.path.join(output_dir, f"{basename}_output.kml")
    exporter.export(geotiff_data, detection_result, inversion_result, wavefront_result, kml_path)
    logger.info(f"KML saved: {kml_path}")

    geojson_path = os.path.join(output_dir, f"{basename}_output.geojson")
    exporter.export_geojson(geotiff_data, detection_result, inversion_result, wavefront_result, geojson_path)
    logger.info(f"GeoJSON saved: {geojson_path}")

    logger.info("Analysis complete!")

    return {
        'geotiff': geotiff_data,
        'preprocessed': preprocessed,
        'detection': detection_result,
        'wavefront': wavefront_result,
        'inversion': inversion_result
    }


def track_multiple_frames(input_paths: list, output_dir: str, time_intervals: list):
    """
    Track waves across multiple frames.

    Args:
        input_paths: List of input GeoTIFF paths (ordered by time)
        output_dir: Output directory
        time_intervals: Time intervals between frames in seconds
    """
    from sariw.wave_tracker import WaveTracker, TrackParams

    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Tracking waves across {len(input_paths)} frames")

    frame_results = []
    for i, input_path in enumerate(input_paths):
        logger.info(f"Processing frame {i + 1}/{len(input_paths)}")
        results = analyze_single_image(input_path, output_dir)
        frame_results.append(results)

    logger.info("Performing tracking...")
    track_params = TrackParams(
        max_distance=50.0,
        direction_tolerance=30.0
    )
    tracker = WaveTracker(track_params)
    tracking_result = tracker.track(frame_results, time_intervals)

    tracker.print_tracking_summary(tracking_result)

    tracks_kml = os.path.join(output_dir, 'tracks.kml')
    tracker.export_tracks_kml(tracking_result, tracks_kml)
    logger.info(f"Tracks KML saved: {tracks_kml}")

    tracks_geojson = os.path.join(output_dir, 'tracks.geojson')
    tracker.export_tracks_geojson(tracking_result, tracks_geojson)
    logger.info(f"Tracks GeoJSON saved: {tracks_geojson}")

    return tracking_result


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='SARIW Library Usage Example')
    parser.add_argument('--mode', choices=['analyze', 'track'], default='analyze',
                        help='Operation mode')
    parser.add_argument('--inputs', nargs='+', required=True,
                        help='Input GeoTIFF files')
    parser.add_argument('--output', default='example_output',
                        help='Output directory')
    parser.add_argument('--time-intervals', nargs='*', type=float, default=[3600],
                        help='Time intervals between frames (seconds)')

    args = parser.parse_args()

    if args.mode == 'analyze':
        if len(args.inputs) < 1:
            logger.error("At least one input file required for analyze mode")
            sys.exit(1)
        analyze_single_image(args.inputs[0], args.output)
    else:
        if len(args.inputs) < 2:
            logger.error("At least two input files required for track mode")
            sys.exit(1)
        track_multiple_frames(args.inputs, args.output, args.time_intervals)
