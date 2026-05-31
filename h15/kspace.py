import numpy as np
from typing import Tuple


def fft2c(img: np.ndarray) -> np.ndarray:
    """
    Centered 2D FFT.
    
    Args:
        img: Input image (2D or 3D for multi-coil)
        
    Returns:
        k-space data
    """
    axes = (-2, -1)
    return np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(img, axes=axes), axes=axes), axes=axes)


def ifft2c(kspace: np.ndarray) -> np.ndarray:
    """
    Centered 2D inverse FFT.
    
    Args:
        kspace: Input k-space data
        
    Returns:
        Image space data
    """
    axes = (-2, -1)
    return np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kspace, axes=axes), axes=axes), axes=axes)


def compute_kspace(img: np.ndarray) -> np.ndarray:
    """
    Compute full k-space from image.
    
    Args:
        img: Input image (2D or 3D for multi-coil)
        
    Returns:
        Full sampled k-space
    """
    return fft2c(img)


def apply_mask(kspace: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Apply sampling mask to k-space.
    
    Args:
        kspace: Full k-space data
        mask: Sampling mask (1 for sampled, 0 for not sampled)
        
    Returns:
        Under-sampled k-space
    """
    if kspace.ndim == 3:
        mask = mask[np.newaxis, :, :]
    return kspace * mask
