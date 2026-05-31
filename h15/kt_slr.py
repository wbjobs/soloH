import numpy as np
from typing import Tuple, Optional, List
from kspace import fft2c, ifft2c
from wavelet import wavelet_decompose, wavelet_reconstruct, soft_threshold


def generate_dynamic_phantom(
    size: int = 128,
    num_frames: int = 20,
    motion_type: str = 'rotation'
) -> np.ndarray:
    """
    Generate a dynamic MRI phantom with motion.
    
    Args:
        size: Spatial size
        num_frames: Number of time frames
        motion_type: Type of motion ('rotation', 'translation', 'expansion')
        
    Returns:
        Dynamic image series (num_frames x size x size)
    """
    from phantom import shepp_logan_phantom
    from scipy import ndimage
    
    static = shepp_logan_phantom(size)
    dynamic = np.zeros((num_frames, size, size))
    
    center = (size - 1) / 2
    
    for t in range(num_frames):
        phase = 2 * np.pi * t / num_frames
        
        if motion_type == 'rotation':
            angle = 15 * np.sin(phase)
            rotated = ndimage.rotate(static, angle, reshape=False, order=3)
            dynamic[t] = rotated
            
        elif motion_type == 'translation':
            tx = 5 * np.sin(phase)
            ty = 3 * np.cos(phase)
            translated = ndimage.shift(static, [ty, tx], order=3)
            dynamic[t] = translated
            
        elif motion_type == 'expansion':
            scale = 1 + 0.1 * np.sin(phase)
            zoomed = ndimage.zoom(static, scale, order=3)
            if zoomed.shape[0] >= size:
                start = (zoomed.shape[0] - size) // 2
                dynamic[t] = zoomed[start:start+size, start:start+size]
            else:
                pad = (size - zoomed.shape[0]) // 2
                dynamic[t, pad:pad+zoomed.shape[0], pad:pad+zoomed.shape[0]] = zoomed
    
    dynamic = dynamic / dynamic.max()
    return dynamic


def generate_dynamic_kspace(
    dynamic_img: np.ndarray,
    mask: np.ndarray = None,
    snr_db: float = 30.0
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate dynamic k-space data with under-sampling.
    
    Args:
        dynamic_img: Dynamic image series (num_frames x size x size)
        mask: Under-sampling mask (size x size or num_frames x size x size)
        snr_db: Signal-to-noise ratio in dB
        
    Returns:
        kspace_data: Under-sampled k-space
        mask: Sampling mask used
    """
    num_frames, size, _ = dynamic_img.shape
    
    if mask is None:
        from undersampling import generate_mask
        mask = generate_mask('cartesian', size, acceleration=4, random_t=True, 
                            num_frames=num_frames)
    
    if mask.ndim == 2:
        mask = np.repeat(mask[np.newaxis, :, :], num_frames, axis=0)
    
    kspace_full = np.zeros_like(dynamic_img, dtype=np.complex128)
    for t in range(num_frames):
        kspace_full[t] = fft2c(dynamic_img[t])
    
    from phantom import add_noise
    kspace_noisy = add_noise(kspace_full, snr_db)
    
    kspace_und = kspace_noisy * mask
    
    return kspace_und, mask


def svt(matrix: np.ndarray, threshold: float) -> np.ndarray:
    """
    Singular Value Thresholding (SVT) for low-rank approximation.
    
    Args:
        matrix: Input matrix (2D)
        threshold: Singular value threshold
        
    Returns:
        Thresholded matrix
    """
    U, S, Vt = np.linalg.svd(matrix, full_matrices=False)
    S_thresholded = np.maximum(S - threshold, 0)
    return U @ np.diag(S_thresholded) @ Vt


def soft_threshold(x: np.ndarray, threshold: float) -> np.ndarray:
    """
    Soft thresholding operator.
    
    Args:
        x: Input array
        threshold: Threshold value
        
    Returns:
        Thresholded array
    """
    return np.sign(x) * np.maximum(np.abs(x) - threshold, 0)


def rearrange_to_matrix(dynamic_img: np.ndarray) -> np.ndarray:
    """
    Rearrange dynamic 3D data (time x rows x cols) into 2D matrix (rows*cols x time).
    Each column is a vectorized time frame.
    
    Args:
        dynamic_img: Dynamic image (num_frames x size x size)
        
    Returns:
        Matrix (size*size x num_frames)
    """
    num_frames, size, _ = dynamic_img.shape
    return dynamic_img.reshape(num_frames, -1).T


def rearrange_to_dynamic(matrix: np.ndarray, size: int) -> np.ndarray:
    """
    Rearrange 2D matrix back to 3D dynamic data.
    
    Args:
        matrix: Matrix (size*size x num_frames)
        size: Spatial size
        
    Returns:
        Dynamic image (num_frames x size x size)
    """
    num_frames = matrix.shape[1]
    return matrix.T.reshape(num_frames, size, size)


def kt_slr_reconstruction(
    kspace_und: np.ndarray,
    mask: np.ndarray,
    lambda_lr: float = 0.1,
    lambda_sp: float = 0.01,
    num_iter: int = 50,
    wavelet: str = 'db4',
    wavelet_level: int = 3,
    step_size: float = 0.1,
    verbose: bool = False
) -> np.ndarray:
    """
    k-t SLR (Spatial-Temporal Sparsity and Low-Rank) reconstruction.
    
    Solves: min ||F X - Y||^2 + lambda_lr * ||X||_* + lambda_sp * ||W X||_1
    
    Reference: Lingala et al., "k-t SLR: A Dynamic Cardiac MR Imaging Method
    Using Exploitation of Low-Rank and Sparsity Constraints", IEEE TMI 2011.
    
    Args:
        kspace_und: Under-sampled k-space (num_frames x size x size)
        mask: Sampling mask (num_frames x size x size)
        lambda_lr: Low-rank regularization parameter (nuclear norm)
        lambda_sp: Sparsity regularization parameter (L1 norm)
        num_iter: Maximum number of iterations
        wavelet: Wavelet type for sparse coding
        wavelet_level: Wavelet decomposition level
        step_size: Gradient step size
        verbose: Print progress
        
    Returns:
        Reconstructed dynamic image (num_frames x size x size)
    """
    num_frames, size, _ = kspace_und.shape
    
    X = np.zeros((num_frames, size, size), dtype=np.float64)
    for t in range(num_frames):
        X[t] = np.abs(ifft2c(kspace_und[t]))
    
    L = X.copy()
    S = np.zeros_like(X)
    
    for i in range(num_iter):
        X_prev = X.copy()
        
        for t in range(num_frames):
            kspace_current = fft2c(X[t])
            kspace_residual = (kspace_und[t] - kspace_current) * mask[t]
            grad = np.real(ifft2c(kspace_residual))
            X[t] = X[t] + step_size * grad
        
        X_matrix = rearrange_to_matrix(X)
        L_matrix = rearrange_to_matrix(L)
        S_matrix = rearrange_to_matrix(S)
        
        Y_matrix = X_matrix + L_matrix - S_matrix
        L_matrix_new = svt(Y_matrix, lambda_lr)
        
        X_wavelet = np.zeros((num_frames, size, size), dtype=np.float64)
        for t in range(num_frames):
            coeffs = wavelet_decompose(X[t] + L[t] - S[t], wavelet, wavelet_level)
            coeffs_thresh = list(coeffs)
            for j in range(1, len(coeffs_thresh)):
                coeffs_thresh[j] = tuple(soft_threshold(c, lambda_sp) for c in coeffs_thresh[j])
            X_wavelet[t] = wavelet_reconstruct(tuple(coeffs_thresh), wavelet)
        
        S_matrix_new = rearrange_to_matrix(X_wavelet)
        
        L = rearrange_to_dynamic(L_matrix_new, size)
        S = rearrange_to_dynamic(S_matrix_new, size)
        
        X = X + L - S
        
        rel_change = np.linalg.norm(X - X_prev) / (np.linalg.norm(X) + 1e-10)
        
        if verbose and i % 10 == 0:
            print(f"k-t SLR Iteration {i}, Rel Change: {rel_change:.2e}")
        
        if rel_change < 1e-5 and i > 10:
            break
    
    return np.clip(X, 0, None)


def kt_focuss_reconstruction(
    kspace_und: np.ndarray,
    mask: np.ndarray,
    lambda_reg: float = 0.01,
    num_iter: int = 50,
    wavelet: str = 'db4',
    wavelet_level: int = 3,
    p: float = 0.5,
    verbose: bool = False
) -> np.ndarray:
    """
    k-t FOCUSS reconstruction (FOCal Underdetermined System Solver).
    
    Reference: Jung et al., "k-t FOCUSS: A General Compressed Sensing Framework
    for High Resolution Dynamic MRI", IEEE TMI 2010.
    
    Args:
        kspace_und: Under-sampled k-space (num_frames x size x size)
        mask: Sampling mask
        lambda_reg: Regularization parameter
        num_iter: Maximum iterations
        wavelet: Wavelet type
        wavelet_level: Wavelet level
        p: Lp norm parameter (0 < p <= 1)
        verbose: Print progress
        
    Returns:
        Reconstructed dynamic image
    """
    num_frames, size, _ = kspace_und.shape
    
    X = np.zeros((num_frames, size, size), dtype=np.float64)
    for t in range(num_frames):
        X[t] = np.abs(ifft2c(kspace_und[t]))
    
    W = np.ones((num_frames, size, size))
    
    for i in range(num_iter):
        X_prev = X.copy()
        
        for t in range(num_frames):
            alpha = wavelet_decompose(X[t], wavelet, wavelet_level)
            weights = np.ones_like(X[t])
            for level_detail in alpha[1:]:
                for detail in level_detail:
                    weights += np.abs(detail) ** (p - 2)
            W[t] = weights / weights.max()
        
        for t in range(num_frames):
            kspace_current = fft2c(X[t])
            kspace_residual = (kspace_und[t] - kspace_current) * mask[t]
            grad = np.real(ifft2c(kspace_residual))
            
            threshold = lambda_reg * W[t]
            X_grad = X[t] + grad
            coeffs = wavelet_decompose(X_grad, wavelet, wavelet_level)
            
            coeffs_thresh = list(coeffs)
            for j in range(1, len(coeffs_thresh)):
                coeffs_thresh[j] = tuple(
                    c * np.maximum(1 - threshold.mean() / (np.abs(c) + 1e-10), 0)
                    for c in coeffs_thresh[j]
                )
            X[t] = wavelet_reconstruct(tuple(coeffs_thresh), wavelet)
        
        rel_change = np.linalg.norm(X - X_prev) / (np.linalg.norm(X) + 1e-10)
        
        if verbose and i % 10 == 0:
            print(f"k-t FOCUSS Iteration {i}, Rel Change: {rel_change:.2e}")
        
        if rel_change < 1e-5 and i > 10:
            break
    
    return np.clip(X, 0, None)


def temporal_low_rank_reconstruction(
    kspace_und: np.ndarray,
    mask: np.ndarray,
    lambda_lr: float = 0.1,
    num_iter: int = 50,
    step_size: float = 0.1,
    verbose: bool = False
) -> np.ndarray:
    """
    Simple temporal low-rank reconstruction (nuclear norm minimization).
    
    Args:
        kspace_und: Under-sampled k-space
        mask: Sampling mask
        lambda_lr: Nuclear norm parameter
        num_iter: Maximum iterations
        step_size: Gradient step
        verbose: Print progress
        
    Returns:
        Reconstructed dynamic image
    """
    num_frames, size, _ = kspace_und.shape
    
    X = np.zeros((num_frames, size, size), dtype=np.float64)
    for t in range(num_frames):
        X[t] = np.abs(ifft2c(kspace_und[t]))
    
    for i in range(num_iter):
        X_prev = X.copy()
        
        for t in range(num_frames):
            kspace_current = fft2c(X[t])
            kspace_residual = (kspace_und[t] - kspace_current) * mask[t]
            grad = np.real(ifft2c(kspace_residual))
            X[t] = X[t] + step_size * grad
        
        X_matrix = rearrange_to_matrix(X)
        X_matrix_svt = svt(X_matrix, lambda_lr)
        X = rearrange_to_dynamic(X_matrix_svt, size)
        
        rel_change = np.linalg.norm(X - X_prev) / (np.linalg.norm(X) + 1e-10)
        
        if verbose and i % 10 == 0:
            print(f"Temporal Low-Rank Iteration {i}, Rel Change: {rel_change:.2e}")
        
        if rel_change < 1e-5 and i > 10:
            break
    
    return np.clip(X, 0, None)


def compute_dynamic_metrics(
    reference: np.ndarray,
    reconstruction: np.ndarray
) -> dict:
    """
    Compute metrics for dynamic MRI reconstruction.
    
    Args:
        reference: Reference dynamic image (num_frames x size x size)
        reconstruction: Reconstructed dynamic image
        
    Returns:
        Dictionary with per-frame and average metrics
    """
    from metrics import compute_metrics
    
    num_frames = reference.shape[0]
    per_frame = []
    
    for t in range(num_frames):
        m = compute_metrics(reference[t], reconstruction[t])
        per_frame.append(m)
    
    avg_psnr = np.mean([m['PSNR'] for m in per_frame])
    avg_ssim = np.mean([m['SSIM'] for m in per_frame])
    avg_nmse = np.mean([m['NMSE'] for m in per_frame])
    
    return {
        'per_frame': per_frame,
        'avg_PSNR': avg_psnr,
        'avg_SSIM': avg_ssim,
        'avg_NMSE': avg_nmse,
    }
