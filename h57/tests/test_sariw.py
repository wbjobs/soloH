#!/usr/bin/env python
"""
Test script for SARIW - SAR Internal Wave Detection and Analysis Tool.
"""

import os
import sys
import tempfile
import numpy as np
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPreprocessor(unittest.TestCase):
    """Test image preprocessing module."""

    def setUp(self):
        from sariw.preprocessor import Preprocessor, PreprocessingParams
        params = PreprocessingParams(
            denoise_method='gaussian',
            contrast_method='none',
            remove_background=False
        )
        self.preprocessor = Preprocessor(params)
        self.test_image = np.random.rand(100, 100).astype(np.float32)

    def test_preprocess_basic(self):
        """Test basic preprocessing pipeline."""
        result = self.preprocessor.process(self.test_image)
        self.assertEqual(result.shape, self.test_image.shape)
        self.assertTrue(np.all(result >= 0) and np.all(result <= 1))

    def test_image_statistics(self):
        """Test image statistics computation."""
        stats = self.preprocessor.compute_image_statistics(self.test_image)
        self.assertIn('mean', stats)
        self.assertIn('std', stats)
        self.assertIn('snr', stats)
        self.assertTrue(stats['snr'] > 0)

    def test_different_denoise_methods(self):
        """Test different denoising methods."""
        from sariw.preprocessor import PreprocessingParams

        for method in ['bilateral', 'gaussian', 'median', 'none']:
            params = PreprocessingParams(
                denoise_method=method,
                contrast_method='none',
                remove_background=False
            )
            preproc = Preprocessor(params)
            result = preproc.process(self.test_image)
            self.assertEqual(result.shape, self.test_image.shape)


class TestWaveDetector(unittest.TestCase):
    """Test wave detection module."""

    def setUp(self):
        from sariw.wave_detector import WaveDetector, WaveDetectionParams
        params = WaveDetectionParams(
            gabor_frequencies=[0.1]
        )
        self.detector = WaveDetector(params)

    def test_detect_synthetic_waves(self):
        """Test detection with synthetic wave pattern."""
        size = 128
        image = np.random.rand(size, size) * 0.1

        y, x = np.mgrid[0:size, 0:size]
        wavelength = 20
        direction = np.deg2rad(45)
        perp_dir = direction + np.pi / 2
        dist = (x - size/2) * np.cos(perp_dir) + (y - size/2) * np.sin(perp_dir)
        along_dist = (x - size/2) * np.cos(direction) + (y - size/2) * np.sin(direction)
        envelope = np.exp(-(along_dist / 40)**2)
        wave = 0.3 * envelope * np.cos(2 * np.pi * dist / wavelength)
        image += wave + 0.5
        image = np.clip(image, 0, 1)

        result = self.detector.detect(image.astype(np.float32), (1.0, 1.0))
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.radon_image)
        self.assertTrue(0 <= result.dominant_direction < 180)


class TestWavefrontExtractor(unittest.TestCase):
    """Test wavefront extraction module."""

    def setUp(self):
        from sariw.wavefront_extractor import WavefrontExtractor, WavefrontParams
        params = WavefrontParams(
            min_edge_length=10
        )
        self.extractor = WavefrontExtractor(params)

    def test_edge_detection(self):
        """Test Canny edge detection."""
        image = np.zeros((100, 100), dtype=np.float32)
        image[40:60, 40:60] = 1.0
        image = cv2.GaussianBlur(image, (5, 5), 0)

        result = self.extractor.extract(image)
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.edge_image)


class TestAmplitudeInverter(unittest.TestCase):
    """Test amplitude inversion module."""

    def setUp(self):
        from sariw.amplitude_inverter import AmplitudeInverter, InversionParams
        params = InversionParams(
            water_depth=100.0,
            upper_layer_thickness=20.0,
            wind_speed=5.0
        )
        self.inverter = AmplitudeInverter(params)

    def test_reduced_gravity(self):
        """Test reduced gravity computation."""
        g_prime = self.inverter._compute_reduced_gravity()
        self.assertTrue(0 < g_prime < 1.0)

    def test_buoyancy_frequency(self):
        """Test buoyancy frequency computation."""
        N = self.inverter._compute_buoyancy_frequency()
        self.assertTrue(N > 0)

    def test_kdv_coefficients(self):
        """Test KdV coefficient computation."""
        g_prime = self.inverter._compute_reduced_gravity()
        alpha, beta = self.inverter._compute_kdv_coefficients(100.0, g_prime)
        self.assertIsInstance(alpha, float)
        self.assertIsInstance(beta, float)


class TestKMLExporter(unittest.TestCase):
    """Test KML export module."""

    def setUp(self):
        from sariw.kml_exporter import KMLExporter, KMLExportParams
        self.exporter = KMLExporter(KMLExportParams())

    def test_color_by_confidence(self):
        """Test confidence color mapping."""
        import simplekml
        self.assertEqual(self.exporter._get_color_by_confidence(0.8), simplekml.Color.green)
        self.assertEqual(self.exporter._get_color_by_confidence(0.5), simplekml.Color.yellow)
        self.assertEqual(self.exporter._get_color_by_confidence(0.3), simplekml.Color.orange)
        self.assertEqual(self.exporter._get_color_by_confidence(0.1), simplekml.Color.red)


class TestWaveTracker(unittest.TestCase):
    """Test wave tracking module."""

    def setUp(self):
        from sariw.wave_tracker import WaveTracker, TrackParams
        self.tracker = WaveTracker(TrackParams())

    def test_cost_matrix(self):
        """Test cost matrix computation."""
        from sariw.wave_tracker import TrackedWave

        track = TrackedWave(track_id=0)
        mock_wave = Mock()
        mock_wave.wave_id = 0
        mock_wave.direction = 45.0
        mock_wave.wavelength = 50.0
        mock_wave.center_geo = Mock(return_value=(-118.0, 34.0))

        mock_geotiff = Mock()
        mock_geotiff.pixel_to_wgs84 = Mock(return_value=(-118.0, 34.0))

        track.add_observation(0, mock_wave, None, 0.0, mock_geotiff)

        cost_matrix = self.tracker._compute_cost_matrix(
            [track], [mock_wave], mock_geotiff, 1, 3600.0
        )

        self.assertEqual(cost_matrix.shape, (1, 1))


class TestCLI(unittest.TestCase):
    """Test CLI module."""

    def test_cli_import(self):
        """Test that CLI module can be imported."""
        try:
            from sariw import cli
            self.assertIsNotNone(cli)
        except ImportError as e:
            self.fail(f"Failed to import CLI module: {e}")


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestPreprocessor))
    suite.addTests(loader.loadTestsFromTestCase(TestWaveDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestWavefrontExtractor))
    suite.addTests(loader.loadTestsFromTestCase(TestAmplitudeInverter))
    suite.addTests(loader.loadTestsFromTestCase(TestKMLExporter))
    suite.addTests(loader.loadTestsFromTestCase(TestWaveTracker))
    suite.addTests(loader.loadTestsFromTestCase(TestCLI))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    import cv2
    print("Running SARIW unit tests...\n")
    success = run_tests()
    sys.exit(0 if success else 1)
