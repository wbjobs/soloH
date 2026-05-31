import numpy as np
from scipy import ndimage
from scipy.interpolate import interp2d
from typing import Optional, Tuple


def _align_images(
    img_ref: np.ndarray,
    img_test: np.ndarray,
    align_method: str = 'center_crop'
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Align images of different sizes for metric computation.
    
    Args:
        img_ref: Reference image
        img_test: Test image (may have different size)
        align_method: 'center_crop' or 'interpolate'
        
    Returns:
        Aligned reference and test images (same size)
    """
    img_ref = np.asarray(img_ref, dtype=np.float64)
    img_test = np.asarray(img_test, dtype=np.float64)
    
    if img_ref.shape == img_test.shape:
        return img_ref, img_test
    
    if align_method == 'center_crop':
        h_ref, w_ref = img_ref.shape
        h_test, w_test = img_test.shape
        
        h_new = min(h_ref, h_test)
        w_new = min(w_ref, w_test)
        
        r_start_ref = (h_ref - h_new) // 2
        c_start_ref = (w_ref - w_new) // 2
        r_start_test = (h_test - h_new) // 2
        c_start_test = (w_test - w_new) // 2
        
        img_ref_cropped = img_ref[r_start_ref:r_start_ref + h_new, c_start_ref:c_start_ref + w_new]
        img_test_cropped = img_test[r_start_test:r_start_test + h_new, c_start_test:c_start_test + w_new]
        
        return img_ref_cropped, img_test_cropped
    
    elif align_method == 'interpolate':
        h_ref, w_ref = img_ref.shape
        h_test, w_test = img_test.shape
        
        if h_test != h_ref or w_test != w_ref:
            x_old = np.arange(w_test)
            y_old = np.arange(h_test)
            x_new = np.linspace(0, w_test - 1, w_ref)
            y_new = np.linspace(0, h_test - 1, h_ref)
            
            f = interp2d(x_old, y_old, img_test, kind='bilinear')
            img_test = f(x_new, y_new)
        
        return img_ref, img_test
    
    else:
        raise ValueError(f"Unknown alignment method: {align_method}")


def psnr(
    img_ref: np.ndarray,
    img_test: np.ndarray,
    data_range: Optional[float] = None,
    align: bool = True,
    align_method: str = 'center_crop'
) -> float:
    """
    Compute Peak Signal-to-Noise Ratio (PSNR).
    
    Args:
        img_ref: Reference image
        img_test: Test image
        data_range: Dynamic range of the image (default: max - min)
        align: Auto-align images if sizes differ
        align_method: 'center_crop' or 'interpolate'
        
    Returns:
        PSNR in dB
    """
    img_ref = np.asarray(img_ref, dtype=np.float64)
    img_test = np.asarray(img_test, dtype=np.float64)
    
    if align:
        img_ref, img_test = _align_images(img_ref, img_test, align_method)
    
    if img_ref.shape != img_test.shape:
        raise ValueError("Input images must have the same shape after alignment")
    
    if data_range is None:
        data_range = img_ref.max() - img_ref.min()
        if data_range == 0:
            data_range = 1.0
    
    mse = np.mean((img_ref - img_test) ** 2)
    
    if mse == 0:
        return float('inf')
    
    return 10 * np.log10((data_range ** 2) / mse)


def _ssim_single_channel(
    img_ref: np.ndarray,
    img_test: np.ndarray,
    data_range: float,
    win_size: int = 11,
    K1: float = 0.01,
    K2: float = 0.03
) -> float:
    """Compute SSIM for single channel."""
    C1 = (K1 * data_range) ** 2
    C2 = (K2 * data_range) ** 2
    
    sigma = 1.5
    ux = ndimage.gaussian_filter(img_ref, sigma)
    uy = ndimage.gaussian_filter(img_test, sigma)
    
    uxx = ndimage.gaussian_filter(img_ref * img_ref, sigma)
    uyy = ndimage.gaussian_filter(img_test * img_test, sigma)
    uxy = ndimage.gaussian_filter(img_ref * img_test, sigma)
    
    vx = uxx - ux * ux
    vy = uyy - uy * uy
    vxy = uxy - ux * uy
    
    ssim_map = ((2 * ux * uy + C1) * (2 * vxy + C2)) / \
               ((ux * ux + uy * uy + C1) * (vx + vy + C2))
    
    return float(np.mean(ssim_map))


def ssim(
    img_ref: np.ndarray,
    img_test: np.ndarray,
    data_range: Optional[float] = None,
    win_size: int = 11,
    align: bool = True,
    align_method: str = 'center_crop'
) -> float:
    """
    Compute Structural Similarity Index (SSIM).
    
    Args:
        img_ref: Reference image
        img_test: Test image
        data_range: Dynamic range of the image
        win_size: Window size
        align: Auto-align images if sizes differ
        align_method: 'center_crop' or 'interpolate'
        
    Returns:
        SSIM value (0-1)
    """
    img_ref = np.asarray(img_ref, dtype=np.float64)
    img_test = np.asarray(img_test, dtype=np.float64)
    
    if align:
        img_ref, img_test = _align_images(img_ref, img_test, align_method)
    
    if img_ref.shape != img_test.shape:
        raise ValueError("Input images must have the same shape after alignment")
    
    if data_range is None:
        data_range = img_ref.max() - img_ref.min()
        if data_range == 0:
            data_range = 1.0
    
    return _ssim_single_channel(img_ref, img_test, data_range, win_size)


def normalized_mse(
    img_ref: np.ndarray,
    img_test: np.ndarray,
    align: bool = True,
    align_method: str = 'center_crop'
) -> float:
    """
    Compute Normalized Mean Squared Error (NMSE).
    
    Args:
        img_ref: Reference image
        img_test: Test image
        align: Auto-align images if sizes differ
        align_method: 'center_crop' or 'interpolate'
        
    Returns:
        NMSE value
    """
    img_ref = np.asarray(img_ref, dtype=np.float64)
    img_test = np.asarray(img_test, dtype=np.float64)
    
    if align:
        img_ref, img_test = _align_images(img_ref, img_test, align_method)
    
    mse = np.mean((img_ref - img_test) ** 2)
    norm = np.mean(img_ref ** 2)
    
    if norm == 0:
        return float('inf')
    
    return mse / norm


def compute_metrics(
    img_ref: np.ndarray,
    img_test: np.ndarray,
    data_range: Optional[float] = None,
    align: bool = True,
    align_method: str = 'center_crop'
) -> dict:
    """
    Compute all image quality metrics.
    
    Args:
        img_ref: Reference image
        img_test: Test image
        data_range: Dynamic range
        align: Auto-align images if sizes differ
        align_method: 'center_crop' or 'interpolate'
        
    Returns:
        Dictionary with PSNR, SSIM, and NMSE
    """
    return {
        'PSNR': psnr(img_ref, img_test, data_range, align, align_method),
        'SSIM': ssim(img_ref, img_test, data_range, align=align, align_method=align_method),
        'NMSE': normalized_mse(img_ref, img_test, align, align_method),
    }


def error_map(
    img_ref: np.ndarray,
    img_test: np.ndarray,
    normalize: bool = True,
    align: bool = True,
    align_method: str = 'center_crop'
) -> np.ndarray:
    """
    Compute error map between reference and test image.
    
    Args:
        img_ref: Reference image
        img_test: Test image
        normalize: Normalize to [0, 1]
        align: Auto-align images if sizes differ
        align_method: 'center_crop' or 'interpolate'
        
    Returns:
        Error map (absolute difference)
    """
    img_ref = np.asarray(img_ref, dtype=np.float64)
    img_test = np.asarray(img_test, dtype=np.float64)
    
    if align:
        img_ref, img_test = _align_images(img_ref, img_test, align_method)
    
    err = np.abs(img_ref - img_test)
    
    if normalize:
        err_max = err.max()
        if err_max > 0:
            err = err / err_max
    
    return err
