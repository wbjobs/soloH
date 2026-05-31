import numpy as np
import pywt
from typing import List, Tuple, Optional


def get_available_wavelets() -> List[str]:
    """Get available wavelet families."""
    daubechies = [f'db{n}' for n in range(1, 11)]
    symlets = [f'sym{n}' for n in range(2, 11)]
    return daubechies + symlets


def get_wavelet_families() -> dict:
    """Get wavelet families with descriptions."""
    return {
        'Daubechies': [f'db{n}' for n in range(1, 11)],
        'Symlet': [f'sym{n}' for n in range(2, 11)],
    }


def wavelet_decompose(
    img: np.ndarray,
    wavelet: str = 'db4',
    level: int = 3
) -> List:
    """
    Multilevel wavelet decomposition.
    
    Args:
        img: Input image (2D)
        wavelet: Wavelet name
        level: Decomposition level
        
    Returns:
        List of wavelet coefficients [cA_n, (cH_n, cV_n, cD_n), ...]
    """
    coeffs = pywt.wavedec2(img, wavelet, level=level)
    return coeffs


def wavelet_reconstruct(
    coeffs: List,
    wavelet: str = 'db4'
) -> np.ndarray:
    """
    Multilevel wavelet reconstruction.
    
    Args:
        coeffs: Wavelet coefficients
        wavelet: Wavelet name
        
    Returns:
        Reconstructed image
    """
    return pywt.waverec2(coeffs, wavelet)


def soft_threshold(
    x: np.ndarray,
    threshold: float
) -> np.ndarray:
    """
    Soft thresholding operator.
    
    Args:
        x: Input array
        threshold: Threshold value
        
    Returns:
        Thresholded array
    """
    return np.sign(x) * np.maximum(np.abs(x) - threshold, 0)


def hard_threshold(
    x: np.ndarray,
    threshold: float
) -> np.ndarray:
    """
    Hard thresholding operator.
    
    Args:
        x: Input array
        threshold: Threshold value
        
    Returns:
        Thresholded array
    """
    return x * (np.abs(x) > threshold)


def wavelet_threshold(
    coeffs: List,
    threshold: float,
    mode: str = 'soft'
) -> List:
    """
    Apply thresholding to wavelet coefficients.
    
    Args:
        coeffs: Wavelet coefficients
        threshold: Threshold value
        mode: 'soft' or 'hard'
        
    Returns:
        Thresholded coefficients
    """
    threshold_func = soft_threshold if mode == 'soft' else hard_threshold
    
    new_coeffs = [coeffs[0].copy()]
    
    for detail_coeffs in coeffs[1:]:
        new_details = tuple(
            threshold_func(c, threshold) for c in detail_coeffs
        )
        new_coeffs.append(new_details)
    
    return new_coeffs


def coeffs_to_array(coeffs: List) -> np.ndarray:
    """
    Convert wavelet coefficients to a single array.
    
    Args:
        coeffs: Wavelet coefficients
        
    Returns:
        Flattened array of coefficients
    """
    arr, _ = pywt.coeffs_to_array(coeffs)
    return arr


def array_to_coeffs(
    arr: np.ndarray,
    original_coeffs: List,
    wavelet: str = 'db4'
) -> List:
    """
    Convert array back to wavelet coefficients structure.
    
    Args:
        arr: Array of coefficients
        original_coeffs: Original coefficients for structure reference
        wavelet: Wavelet name
        
    Returns:
        Wavelet coefficients structure
    """
    _, slices = pywt.coeffs_to_array(original_coeffs)
    return pywt.array_to_coeffs(arr, slices, output_format='wavedec2')


def cycle_spinning_threshold(
    img: np.ndarray,
    threshold: float,
    wavelet: str = 'db4',
    level: int = 3,
    num_shifts: int = 4,
    mode: str = 'soft'
) -> np.ndarray:
    """
    Cycle spinning for wavelet thresholding to reduce blocking artifacts.
    
    Args:
        img: Input image
        threshold: Threshold value
        wavelet: Wavelet name
        level: Decomposition level
        num_shifts: Number of circular shifts (must be power of 2 for optimal results)
        mode: Threshold mode ('soft' or 'hard')
        
    Returns:
        Denoised image with reduced blocking artifacts
    """
    img_shape = img.shape
    result = np.zeros_like(img, dtype=np.float64)
    
    threshold_func = soft_threshold if mode == 'soft' else hard_threshold
    
    shift_step = max(1, 2 ** (level - 1))
    
    shifts = []
    for i in range(num_shifts):
        for j in range(num_shifts):
            shifts.append((i * shift_step, j * shift_step))
    
    total_weights = 0
    
    for (sy, sx) in shifts:
        img_shifted = np.roll(np.roll(img, sy, axis=0), sx, axis=1)
        
        coeffs = pywt.wavedec2(img_shifted, wavelet, level=level)
        
        new_coeffs = [coeffs[0].copy()]
        for detail_coeffs in coeffs[1:]:
            new_details = tuple(
                threshold_func(c, threshold) for c in detail_coeffs
            )
            new_coeffs.append(new_details)
        
        img_rec = pywt.waverec2(new_coeffs, wavelet)
        
        if img_rec.shape != img_shape:
            img_rec = img_rec[:img_shape[0], :img_shape[1]]
        
        img_back = np.roll(np.roll(img_rec, -sy, axis=0), -sx, axis=1)
        
        weight = 1.0
        if sy == 0 and sx == 0:
            weight = 2.0
        
        result += weight * img_back
        total_weights += weight
    
    result = result / total_weights
    
    return np.clip(result, 0, None)


def translation_invariant_denoise(
    img: np.ndarray,
    threshold: float,
    wavelet: str = 'db4',
    level: int = 3,
    mode: str = 'soft'
) -> np.ndarray:
    """
    Translation-invariant wavelet denoising using undecimated wavelet transform.
    
    Args:
        img: Input image
        threshold: Threshold value
        wavelet: Wavelet name
        level: Decomposition level
        mode: Threshold mode
        
    Returns:
        Denoised image
    """
    coeffs = pywt.swt2(img, wavelet, level=level, norm=True)
    
    new_coeffs = []
    threshold_func = soft_threshold if mode == 'soft' else hard_threshold
    
    for (cA, (cH, cV, cD)) in coeffs:
        new_cH = threshold_func(cH, threshold)
        new_cV = threshold_func(cV, threshold)
        new_cD = threshold_func(cD, threshold)
        new_coeffs.append((cA, (new_cH, new_cV, new_cD)))
    
    img_rec = pywt.iswt2(new_coeffs, wavelet, norm=True)
    
    return np.clip(img_rec, 0, None)
