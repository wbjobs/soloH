"""
Sea Ice Drift Estimation Toolkit

This package provides tools for estimating sea ice drift from time series
of SSM/I or AMSR-E brightness temperature images.

Modules:
    io: Data input/output for HDF files
    preprocess: Image preprocessing (reprojection, denoising)
    motion: Motion estimation algorithms
    quality: Quality assessment and filtering
    mask: Mask generation and application
    output: Output generation (NetCDF, visualization)
    validation: Validation against buoy observations
    deep_learning: FlowNet-based deep learning motion estimation
    analysis: Kinematic analysis (vorticity, divergence, strain, ice age fusion)
"""

__version__ = '2.0.0'
__all__ = [
    'io',
    'preprocess',
    'motion',
    'quality',
    'mask',
    'output',
    'validation',
    'deep_learning',
    'analysis',
]
