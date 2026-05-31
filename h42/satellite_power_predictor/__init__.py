"""
卫星太阳能电池板功率预测系统
Satellite Solar Array Power Prediction System
"""

__version__ = "1.0.0"
__author__ = "Satellite Power Prediction Team"

from .power.power_predictor import PowerPredictor
from .parallel.batch_processor import BatchProcessor

__all__ = ["PowerPredictor", "BatchProcessor"]
