"""
Light Field Camera Depth Estimation Toolkit

This package provides tools for:
- Reading light field raw images (LFR format or white-image corrected)
- Extracting sub-aperture image arrays (UV plane)
- Depth estimation using DFD, stereo matching, EPI, and deep learning methods
- Point cloud generation (PLY format)
- Confidence mapping and occlusion detection
- Temporal consistency for video processing
- Interactive depth editing
"""

__version__ = "2.0.0"

from . import io, calibration, subaperture, depth_dfd, depth_stereo, depth_epi, postprocessing, pointcloud
from . import depth_learning, video_temporal, editor
