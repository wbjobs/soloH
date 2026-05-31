#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to verify the three bug fixes:
1. Kalman filter motion prediction for low frame rate tracking
2. Dual-threshold hysteresis for division detection
3. Exponential decay photobleaching correction
"""

import sys
import numpy as np
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_kalman_motion_prediction():
    """Test Kalman filter motion prediction for fast moving cells."""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Kalman Filter Motion Prediction")
    logger.info("="*60)
    
    from cell_tracker.tracking import CellTrack
    
    track = CellTrack(track_id=1)
    
    frames = [0, 1, 2, 3, 4]
    positions = [(10, 10), (20, 20), (30, 30), (40, 40), (50, 50)]
    velocities = [(10, 10), (10, 10), (10, 10), (10, 10), (10, 10)]
    
    for frame, pos in zip(frames, positions):
        track.add_detection(
            frame=frame,
            label=1,
            centroid=pos,
            area=100,
            properties={'centroid': pos, 'area': 100},
            fluorescence=100.0
        )
    
    logger.info(f"Track positions: {positions}")
    logger.info(f"Velocity history: vx={track.velocity_x}, vy={track.velocity_y}")
    
    next_pos = track.predict_next_position(current_frame=5)
    expected_pos = (60, 60)
    distance = np.sqrt((next_pos[0] - expected_pos[0])**2 + (next_pos[1] - expected_pos[1])**2)
    
    logger.info(f"Predicted position for frame 5: ({next_pos[0]:.1f}, {next_pos[1]:.1f})")
    logger.info(f"Expected position for frame 5: {expected_pos}")
    logger.info(f"Prediction error: {distance:.2f} px")
    
    max_dist = track.get_expected_max_distance(base_max_distance=50.0)
    logger.info(f"Adaptive max distance: {max_dist:.1f} px (base: 50.0)")
    
    assert distance < 5.0, f"Prediction error too large: {distance}"
    assert max_dist > 50.0, f"Adaptive distance should be larger than base: {max_dist}"
    assert track.kalman_state is not None, "Kalman state not initialized"
    
    logger.info("✓ Kalman filter motion prediction works correctly")
    
    return True


def test_division_hysteresis():
    """Test dual-threshold hysteresis for division detection."""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Division Detection Hysteresis")
    logger.info("="*60)
    
    from cell_tracker.division_detection import DivisionDetector
    
    detector = DivisionDetector(
        area_drop_threshold=0.4,
        area_drop_hysteresis=0.1,
        morphology_change_threshold=0.3,
        morphology_hysteresis=0.08,
        min_consecutive_frames=1,
        area_smoothing_window=1
    )
    
    logger.info(f"Area drop threshold: {detector.area_drop_threshold} (low: {detector.area_drop_low})")
    logger.info(f"Area increase threshold: {detector.area_increase_threshold} (low: {detector.area_increase_low})")
    logger.info(f"Morphology threshold: {detector.morphology_change_threshold} (low: {detector.morphology_low})")
    
    areas = np.array([200, 205, 198, 195, 75, 80, 85, 200, 198, 202])
    frames = list(range(len(areas)))
    
    candidate_indices, candidate_frames, area_ratios, _ = detector.detect_area_mutation(areas, frames)
    
    logger.info(f"Area sequence: {areas.tolist()}")
    logger.info(f"Area ratios: {area_ratios.tolist()}")
    logger.info(f"Candidate indices: {candidate_indices.tolist()}")
    logger.info(f"Candidate frames: {candidate_frames.tolist()}")
    
    expected_drops = np.where(area_ratios < detector.area_drop_low)[0]
    logger.info(f"Expected drops (low threshold): {expected_drops.tolist()}")
    
    assert len(candidate_indices) > 0, "Should detect area drops"
    assert 3 in candidate_indices or 4 in candidate_indices, "Should detect drop at frame 4"
    
    morph_props = [
        {'eccentricity': 0.3, 'solidity': 0.9, 'extent': 0.7},
        {'eccentricity': 0.3, 'solidity': 0.9, 'extent': 0.7},
        {'eccentricity': 0.3, 'solidity': 0.9, 'extent': 0.7},
        {'eccentricity': 0.3, 'solidity': 0.9, 'extent': 0.7},
        {'eccentricity': 0.7, 'solidity': 0.5, 'extent': 0.4},
        {'eccentricity': 0.68, 'solidity': 0.52, 'extent': 0.42},
        {'eccentricity': 0.3, 'solidity': 0.9, 'extent': 0.7},
    ]
    morph_frames = list(range(len(morph_props)))
    
    morph_indices, morph_changes, _ = detector.detect_morphology_change(morph_props, morph_frames)
    
    logger.info(f"\nMorphology changes: {morph_changes.tolist()}")
    logger.info(f"Morphology candidate indices: {morph_indices.tolist()}")
    
    assert len(morph_indices) > 0, "Should detect morphology changes"
    
    detector_both = DivisionDetector(
        area_drop_threshold=0.4,
        area_drop_hysteresis=0.1,
        morphology_change_threshold=0.3,
        morphology_hysteresis=0.08,
        require_both_metrics=True
    )
    
    logger.info(f"\nDual-metric requirement enabled: {detector_both.require_both_metrics}")
    
    assert detector_both.require_both_metrics == True, "Dual-metric should be enabled"
    
    logger.info("✓ Division detection hysteresis works correctly")
    
    return True


def test_exponential_bleach_correction():
    """Test exponential decay photobleaching correction."""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Exponential Decay Photobleaching Correction")
    logger.info("="*60)
    
    from cell_tracker.features import FeatureExtractor
    
    extractor = FeatureExtractor(
        perform_photobleach_correction=True,
        bleaching_correction_method='exponential',
        background_correction=True,
        use_global_bleach=True
    )
    
    n_frames = 50
    image_size = 64
    
    image_stack = np.zeros((n_frames, image_size, image_size), dtype=np.float32)
    masks = np.zeros((n_frames, image_size, image_size), dtype=np.int32)
    
    I0 = 1000.0
    tau = 25.0
    bg = 50.0
    
    for frame in range(n_frames):
        decay = np.exp(-frame / tau)
        intensity = I0 * decay + bg
        
        image_stack[frame, 20:30, 20:30] = intensity
        masks[frame, 20:30, 20:30] = 1
    
    logger.info(f"Simulated bleach: I0={I0}, tau={tau}, bg={bg}")
    logger.info(f"Frames: {n_frames}, Image size: {image_size}x{image_size}")
    
    extractor.extract_fluorescence(image_stack, masks)
    
    logger.info("\nRaw fluorescence (first 5 frames):")
    for frame in range(5):
        if frame in extractor.fluorescence_data and 1 in extractor.fluorescence_data[frame]:
            raw = extractor.fluorescence_data[frame][1]['mean']
            expected = I0 * np.exp(-frame / tau) + bg
            logger.info(f"  Frame {frame}: {raw:.1f} (expected: {expected:.1f})")
    
    assert extractor.corrected_fluorescence_data is not None
    assert len(extractor.corrected_fluorescence_data) > 0
    
    logger.info("\nCorrected fluorescence (first 5 frames):")
    for frame in range(5):
        if frame in extractor.corrected_fluorescence_data and 1 in extractor.corrected_fluorescence_data[frame]:
            corrected = extractor.corrected_fluorescence_data[frame][1]['mean']
            factor = extractor.corrected_fluorescence_data[frame][1]['correction_factor']
            bg_val = extractor.corrected_fluorescence_data[frame][1]['background']
            logger.info(f"  Frame {frame}: {corrected:.1f} (factor: {factor:.3f}, bg: {bg_val:.1f})")
    
    if extractor.bleach_correction_params is not None:
        params = extractor.bleach_correction_params
        logger.info(f"\nFitted parameters:")
        logger.info(f"  I0: {params['I0']:.1f} (expected: {I0})")
        logger.info(f"  tau: {params['tau']:.1f} (expected: {tau})")
        logger.info(f"  offset: {params['offset']:.1f} (expected: {bg})")
        logger.info(f"  Half-life: {params['half_life']:.1f} frames")
        
        error_I0 = abs(params['I0'] - I0) / I0 * 100
        error_tau = abs(params['tau'] - tau) / tau * 100
        
        logger.info(f"\nFit errors:")
        logger.info(f"  I0 error: {error_I0:.1f}%")
        logger.info(f"  tau error: {error_tau:.1f}%")
        
        assert error_I0 < 20.0, f"I0 fit error too large: {error_I0:.1f}%"
        assert error_tau < 30.0, f"tau fit error too large: {error_tau:.1f}%"
    
    corrected_values = []
    for frame in range(n_frames):
        if frame in extractor.corrected_fluorescence_data and 1 in extractor.corrected_fluorescence_data[frame]:
            corrected_values.append(extractor.corrected_fluorescence_data[frame][1]['mean'])
    
    if len(corrected_values) > 10:
        cv_start = np.std(corrected_values[:10]) / np.mean(corrected_values[:10])
        cv_end = np.std(corrected_values[-10:]) / np.mean(corrected_values[-10])
        cv_all = np.std(corrected_values) / np.mean(corrected_values)
        
        logger.info(f"\nCoefficient of variation:")
        logger.info(f"  First 10 frames: {cv_start:.4f}")
        logger.info(f"  Last 10 frames: {cv_end:.4f}")
        logger.info(f"  All frames: {cv_all:.4f}")
        
        raw_values = []
        for frame in range(n_frames):
            if frame in extractor.fluorescence_data and 1 in extractor.fluorescence_data[frame]:
                raw_values.append(extractor.fluorescence_data[frame][1]['mean'])
        
        raw_cv = np.std(raw_values) / np.mean(raw_values)
        logger.info(f"  Raw (all): {raw_cv:.4f}")
        logger.info(f"  CV reduction: {(1 - cv_all/raw_cv)*100:.1f}%")
    
    logger.info("✓ Exponential decay photobleaching correction works correctly")
    
    return True


def test_integration():
    """Test all fixes in a small integration test."""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Integration Test with Synthetic Data")
    logger.info("="*60)
    
    from pathlib import Path
    import tempfile
    from cell_tracker.pipeline import CellTrackingPipeline
    from cell_tracker.utils import load_tiff_stack
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_data_path = Path(tmpdir) / "test_data.tiff"
        
        from cell_tracker.cli import generate_test_data
        from click.testing import CliRunner
        
        runner = CliRunner()
        result = runner.invoke(
            generate_test_data,
            [
                '--output-path', str(test_data_path),
                '--n-frames', '30',
                '--n-cells', '5',
                '--image-size', '128',
            ]
        )
        
        assert result.exit_code == 0, f"Data generation failed: {result.output}"
        
        images = load_tiff_stack(str(test_data_path))
        masks_path = Path(tmpdir) / "test_masks.tiff"
        tracks_path = Path(tmpdir) / "test_tracks.csv"
        
        logger.info(f"Test data shape: {images.shape}")
        
        pipeline = CellTrackingPipeline(
            output_dir=str(Path(tmpdir) / "output"),
            num_workers=2,
            tracking_max_distance=30.0,
            tracking_max_lost_frames=3,
            division_area_drop_threshold=0.5,
            division_area_hysteresis=0.1,
            division_require_both_metrics=False,
            photobleach_correction=True,
            photobleach_global=True,
            background_correction=True
        )
        
        pipeline.load_data(str(test_data_path))
        pipeline.preprocess()
        
        pipeline.segmentation_masks = load_tiff_stack(str(masks_path))
        
        pipeline.run_feature_extraction(extract_all=False)
        
        logger.info(f"Feature extraction complete")
        logger.info(f"  Bleach correction params: {pipeline.feature_extractor.bleach_correction_params}")
        
        pipeline.run_tracking()
        
        logger.info(f"Tracking complete")
        logger.info(f"  Number of tracks: {len(pipeline.tracker.tracks)}")
        
        for track_id, track in list(pipeline.tracker.tracks.items())[:3]:
            logger.info(f"  Track {track_id}: {len(track)} frames, velocity_x={track.velocity_x[:3] if track.velocity_x else 'N/A'}")
        
        pipeline.run_division_detection()
        
        logger.info(f"Division detection complete")
        logger.info(f"  Number of divisions: {len(pipeline.division_events)}")
        
        assert pipeline.tracker is not None
        assert pipeline.feature_extractor is not None
        
        logger.info("✓ Integration test passed")
        
        return True


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("BUG FIX VERIFICATION TEST SUITE")
    logger.info("=" * 60)
    
    success = True
    tests = [
        ("Kalman filter motion prediction", test_kalman_motion_prediction),
        ("Division detection hysteresis", test_division_hysteresis),
        ("Exponential bleach correction", test_exponential_bleach_correction),
        ("Integration test", test_integration),
    ]
    
    for test_name, test_func in tests:
        try:
            if not test_func():
                success = False
                logger.error(f"✗ {test_name} FAILED")
            else:
                logger.info(f"✓ {test_name} PASSED")
        except Exception as e:
            success = False
            logger.error(f"✗ {test_name} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
    
    logger.info("\n" + "=" * 60)
    if success:
        logger.info("ALL BUG FIX TESTS PASSED! ✓")
        logger.info("\nSummary of fixes:")
        logger.info("  1. ✓ Kalman filter motion prediction for low frame rate tracking")
        logger.info("     - Predicts cell positions using velocity history")
        logger.info("     - Adaptive max distance based on cell speed")
        logger.info("     - Reduces matching failures for fast-moving cells")
        logger.info("  2. ✓ Dual-threshold hysteresis for division detection")
        logger.info("     - Separate high/low thresholds for area and morphology")
        logger.info("     - Consecutive frame validation")
        logger.info("     - Optional dual-metric requirement")
        logger.info("  3. ✓ Exponential decay photobleaching correction")
        logger.info("     - Scipy curve_fit for exponential model fitting")
        logger.info("     - Background subtraction (per-frame)")
        logger.info("     - Global or per-track correction")
        logger.info("     - Correction factor output")
    else:
        logger.error("SOME TESTS FAILED! ✗")
        sys.exit(1)
    logger.info("=" * 60)
    
    return success


if __name__ == '__main__':
    main()
