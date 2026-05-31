#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to verify all modules can be imported correctly.
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all modules import successfully."""
    logger.info("Testing module imports...")
    
    try:
        from cell_tracker import utils
        logger.info("✓ cell_tracker.utils imported")
    except Exception as e:
        logger.error(f"✗ cell_tracker.utils failed: {e}")
        return False
    
    try:
        from cell_tracker import segmentation
        logger.info("✓ cell_tracker.segmentation imported")
    except Exception as e:
        logger.error(f"✗ cell_tracker.segmentation failed: {e}")
        return False
    
    try:
        from cell_tracker import tracking
        logger.info("✓ cell_tracker.tracking imported")
    except Exception as e:
        logger.error(f"✗ cell_tracker.tracking failed: {e}")
        return False
    
    try:
        from cell_tracker import division_detection
        logger.info("✓ cell_tracker.division_detection imported")
    except Exception as e:
        logger.error(f"✗ cell_tracker.division_detection failed: {e}")
        return False
    
    try:
        from cell_tracker import features
        logger.info("✓ cell_tracker.features imported")
    except Exception as e:
        logger.error(f"✗ cell_tracker.features failed: {e}")
        return False
    
    try:
        from cell_tracker import evaluation
        logger.info("✓ cell_tracker.evaluation imported")
    except Exception as e:
        logger.error(f"✗ cell_tracker.evaluation failed: {e}")
        return False
    
    try:
        from cell_tracker import parallel
        logger.info("✓ cell_tracker.parallel imported")
    except Exception as e:
        logger.error(f"✗ cell_tracker.parallel failed: {e}")
        return False
    
    try:
        from cell_tracker import visualization
        logger.info("✓ cell_tracker.visualization imported")
    except Exception as e:
        logger.error(f"✗ cell_tracker.visualization failed: {e}")
        return False
    
    try:
        from cell_tracker import pipeline
        logger.info("✓ cell_tracker.pipeline imported")
    except Exception as e:
        logger.error(f"✗ cell_tracker.pipeline failed: {e}")
        return False
    
    try:
        from cell_tracker import cli
        logger.info("✓ cell_tracker.cli imported")
    except Exception as e:
        logger.error(f"✗ cell_tracker.cli failed: {e}")
        return False
    
    try:
        from cell_tracker import (
            UNetSegmenter,
            CellTracker,
            hungarian_assignment,
            DivisionDetector,
            FeatureExtractor,
            Evaluator,
            NapariVisualizer,
            ParallelProcessor,
        )
        logger.info("✓ All API classes imported successfully")
    except Exception as e:
        logger.error(f"✗ API classes import failed: {e}")
        return False
    
    logger.info("\nAll imports successful!")
    return True


def test_basic_functions():
    """Test basic functionality of key components."""
    logger.info("\nTesting basic functionality...")
    
    import numpy as np
    
    try:
        from cell_tracker.utils import normalize_image
        test_img = np.random.rand(100, 100)
        normalized = normalize_image(test_img)
        assert normalized.shape == test_img.shape
        assert normalized.min() >= 0
        assert normalized.max() <= 1
        logger.info("✓ normalize_image works")
    except Exception as e:
        logger.error(f"✗ normalize_image failed: {e}")
        return False
    
    try:
        from cell_tracker.tracking import hungarian_assignment
        cost = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=float)
        row_ind, col_ind = hungarian_assignment(cost)
        assert len(row_ind) == 3
        logger.info("✓ hungarian_assignment works")
    except Exception as e:
        logger.error(f"✗ hungarian_assignment failed: {e}")
        return False
    
    try:
        from cell_tracker.evaluation import compute_iou_binary
        mask1 = np.zeros((10, 10), dtype=bool)
        mask2 = np.zeros((10, 10), dtype=bool)
        mask1[2:7, 2:7] = True
        mask2[4:9, 4:9] = True
        iou = compute_iou_binary(mask1, mask2)
        assert 0 <= iou <= 1
        logger.info("✓ compute_iou_binary works")
    except Exception as e:
        logger.error(f"✗ compute_iou_binary failed: {e}")
        return False
    
    try:
        from cell_tracker.tracking import CellTracker
        tracker = CellTracker(max_distance=50.0, min_track_length=2)
        
        mask1 = np.zeros((100, 100), dtype=np.int32)
        mask1[20:40, 20:40] = 1
        mask1[60:80, 60:80] = 2
        
        tracker.update(0, mask1)
        
        mask2 = np.zeros((100, 100), dtype=np.int32)
        mask2[22:42, 22:42] = 1
        mask2[58:78, 58:78] = 2
        
        tracker.update(1, mask2)
        
        assert len(tracker.tracks) == 2
        logger.info("✓ CellTracker works")
    except Exception as e:
        logger.error(f"✗ CellTracker failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        from cell_tracker.segmentation import UNet, DoubleConv, Down, Up, OutConv
        import torch
        
        model = UNet(n_channels=1, n_classes=2)
        test_tensor = torch.randn(1, 1, 64, 64)
        output = model(test_tensor)
        assert output.shape == (1, 2, 64, 64)
        logger.info("✓ UNet model forward pass works")
    except Exception as e:
        logger.error(f"✗ UNet model failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        from cell_tracker.parallel import ParallelProcessor
        processor = ParallelProcessor(num_workers=2, use_threads=True, show_progress=False)
        
        def square(x):
            return x * x
        
        results = processor.map(square, [1, 2, 3, 4, 5])
        assert results == [1, 4, 9, 16, 25]
        logger.info("✓ ParallelProcessor works")
    except Exception as e:
        logger.error(f"✗ ParallelProcessor failed: {e}")
        return False
    
    logger.info("\nAll basic tests passed!")
    return True


def test_synthetic_data():
    """Test with synthetic data generation."""
    logger.info("\nTesting synthetic data generation...")
    
    try:
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_data.tiff"
            
            from cell_tracker.cli import generate_test_data
            from click.testing import CliRunner
            
            runner = CliRunner()
            result = runner.invoke(
                generate_test_data,
                [
                    '--output-path', str(output_path),
                    '--n-frames', '10',
                    '--n-cells', '3',
                    '--image-size', '64',
                ]
            )
            
            if result.exit_code != 0:
                logger.error(f"Command failed with output: {result.output}")
                logger.error(f"Exception: {result.exception}")
                return False
            
            assert output_path.exists()
            logger.info("✓ Synthetic data generation works")
            
            from cell_tracker.utils import load_tiff_stack
            images = load_tiff_stack(str(output_path))
            assert images.shape == (10, 64, 64)
            logger.info("✓ Synthetic data loads correctly")
            
    except Exception as e:
        logger.error(f"✗ Synthetic data test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("CELL TRACKER - TEST SUITE")
    logger.info("=" * 60)
    
    success = True
    
    if not test_imports():
        success = False
    
    if not test_basic_functions():
        success = False
    
    if not test_synthetic_data():
        success = False
    
    logger.info("\n" + "=" * 60)
    if success:
        logger.info("ALL TESTS PASSED! ✓")
    else:
        logger.error("SOME TESTS FAILED! ✗")
        sys.exit(1)
    logger.info("=" * 60)
    
    return success


if __name__ == '__main__':
    main()
