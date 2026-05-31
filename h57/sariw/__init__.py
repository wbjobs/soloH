"""
SARIW - SAR Image Internal Wave Detection and Analysis Tool.
"""

__version__ = '2.0.0'
__author__ = 'SAR Internal Wave Team'

from .geotiff_reader import GeoTIFFReader
from .preprocessor import Preprocessor
from .wave_detector import WaveDetector
from .wavefront_extractor import WavefrontExtractor
from .amplitude_inverter import AmplitudeInverter
from .wave_tracker import WaveTracker
from .kml_exporter import KMLExporter
from .cnn_detector import CNNWaveDetector, CNNDetectionParams, CNNDetection, CNNDetectionResult
from .ts_inverter import TSInverter, TSInversionParams, TSProfile, TSInversionResult
from .wave_breaking import WaveBreakingModel, BreakingParams, BreakingRegion, BreakingSimulationResult

__all__ = [
    'GeoTIFFReader',
    'Preprocessor',
    'WaveDetector',
    'WavefrontExtractor',
    'AmplitudeInverter',
    'WaveTracker',
    'KMLExporter',
    'CNNWaveDetector',
    'CNNDetectionParams',
    'CNNDetection',
    'CNNDetectionResult',
    'TSInverter',
    'TSInversionParams',
    'TSProfile',
    'TSInversionResult',
    'WaveBreakingModel',
    'BreakingParams',
    'BreakingRegion',
    'BreakingSimulationResult',
]
