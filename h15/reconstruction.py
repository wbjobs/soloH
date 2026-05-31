import numpy as np
from typing import Optional, Callable, Tuple, List
from kspace import fft2c, ifft2c
from wavelet import (
    wavelet_decompose,
    wavelet_reconstruct,
    wavelet_threshold,
    soft_threshold,
    cycle_spinning_threshold,
    translation_invariant_denoise,
)


def _gradient(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute gradient of image."""
    grad_x = np.zeros_like(img)
    grad_y = np.zeros_like(img)
    
    grad_x[:, :-1] = img[:, 1:] - img[:, :-1]
    grad_y[:-1, :] = img[1:, :] - img[:-1, :]
    
    return grad_x, grad_y


def _divergence(grad_x: np.ndarray, grad_y: np.ndarray) -> np.ndarray:
    """Compute divergence of gradient field."""
    div = np.zeros_like(grad_x)
    
    div[:, 1:-1] = grad_x[:, 1:-1] - grad_x[:, :-2]
    div[:, 0] = grad_x[:, 0]
    div[:, -1] = -grad_x[:, -2]
    
    div[1:-1, :] += grad_y[1:-1, :] - grad_y[:-2, :]
    div[0, :] += grad_y[0, :]
    div[-1, :] += -grad_y[-2, :]
    
    return div


def tv_denoise(
    img: np.ndarray,
    lambda_tv: float = 0.1,
    num_iter: int = 100,
    tau: float = 0.125,
    tol: float = 1e-4,
    verbose: bool = False
) -> np.ndarray:
    """
    Total Variation (TV) denoising using Chambolle-Pock algorithm.
    
    Args:
        img: Input image (potentially noisy)
        lambda_tv: Regularization parameter
        num_iter: Maximum number of iterations
        tau: Step size
        tol: Convergence tolerance
        verbose: Print progress
        
    Returns:
        Denoised image
    """
    img = np.asarray(img, dtype=np.float64)
    x = img.copy()
    
    p_x = np.zeros_like(x)
    p_y = np.zeros_like(x)
    
    sigma = 1.0 / (8.0 * tau)
    theta = 1.0
    
    x_bar = x.copy()
    
    for i in range(num_iter):
        x_old = x.copy()
        
        grad_x, grad_y = _gradient(x_bar)
        p_x = p_x + sigma * grad_x
        p_y = p_y + sigma * grad_y
        
        norm_p = np.sqrt(p_x ** 2 + p_y ** 2)
        norm_p = np.maximum(norm_p, lambda_tv)
        p_x = p_x / norm_p * lambda_tv
        p_y = p_y / norm_p * lambda_tv
        
        div_p = _divergence(p_x, p_y)
        x = x + tau * div_p
        x = (x + tau * img) / (1 + tau)
        
        theta = 1.0 / np.sqrt(1 + 2 * tau * lambda_tv)
        tau = tau * theta
        sigma = sigma / theta
        
        x_bar = x + theta * (x - x_old)
        
        rel_change = np.linalg.norm(x - x_old) / (np.linalg.norm(x) + 1e-10)
        
        if verbose and i % 10 == 0:
            print(f"TV Iteration {i}, Relative Change: {rel_change:.2e}")
        
        if rel_change < tol and i > 10:
            break
    
    return x


def tv_regularized_reconstruction(
    kspace_und: np.ndarray,
    mask: np.ndarray,
    lambda_tv: float = 0.05,
    num_iter: int = 50,
    verbose: bool = False
) -> np.ndarray:
    """
    TV-regularized MRI reconstruction.
    
    Args:
        kspace_und: Under-sampled k-space data
        mask: Sampling mask
        lambda_tv: TV regularization parameter
        num_iter: Number of iterations
        verbose: Print progress
        
    Returns:
        Reconstructed image
    """
    x = ifft2c(kspace_und)
    
    for i in range(num_iter):
        kspace_current = fft2c(x)
        kspace_data_consistency = kspace_current * (1 - mask) + kspace_und * mask
        x = ifft2c(kspace_data_consistency)
        
        x_mag = np.abs(x)
        x_phase = np.angle(x)
        
        x_denoised = tv_denoise(x_mag, lambda_tv=lambda_tv, num_iter=20)
        x = x_denoised * np.exp(1j * x_phase)
        
        if verbose and i % 5 == 0:
            print(f"TV Recon Iteration {i}")
    
    return np.abs(x)


def sense_reconstruction(
    kspace_und: np.ndarray,
    sense_maps: np.ndarray,
    mask: np.ndarray,
    num_iter: int = 20,
    lambda_reg: float = 0.01,
    verbose: bool = False
) -> np.ndarray:
    """
    SENSE (Sensitivity Encoding) reconstruction.
    
    Args:
        kspace_und: Under-sampled multi-coil k-space (num_channels, N, N)
        sense_maps: Coil sensitivity maps (num_channels, N, N)
        mask: Sampling mask
        num_iter: Number of iterations
        lambda_reg: Regularization parameter
        verbose: Print progress
        
    Returns:
        Reconstructed image
    """
    num_channels = kspace_und.shape[0]
    img_size = kspace_und.shape[1]
    
    x = np.zeros((img_size, img_size), dtype=np.complex128)
    
    for ch in range(num_channels):
        coil_img = ifft2c(kspace_und[ch])
        x += coil_img * np.conj(sense_maps[ch])
    
    norm = np.sum(np.abs(sense_maps) ** 2, axis=0)
    norm[norm == 0] = 1
    x = x / norm
    
    for i in range(num_iter):
        e = np.zeros_like(kspace_und)
        
        for ch in range(num_channels):
            coil_img = x * sense_maps[ch]
            coil_kspace = fft2c(coil_img)
            coil_kspace = coil_kspace * (1 - mask) + kspace_und[ch] * mask
            e[ch] = coil_kspace - fft2c(x * sense_maps[ch])
        
        g = np.zeros_like(x)
        for ch in range(num_channels):
            g += np.conj(sense_maps[ch]) * ifft2c(e[ch])
        
        x = x + g - lambda_reg * x
        
        if verbose and i % 5 == 0:
            print(f"SENSE Iteration {i}, Residual: {np.linalg.norm(g):.2e}")
    
    return np.abs(x)


def _wavelet_soft_threshold_detail(
    coeffs: List,
    threshold: float
) -> List:
    """Apply soft thresholding only to detail coefficients, keep approximation."""
    new_coeffs = [coeffs[0].copy()]
    
    for detail_coeffs in coeffs[1:]:
        new_details = tuple(
            soft_threshold(c, threshold) for c in detail_coeffs
        )
        new_coeffs.append(new_details)
    
    return new_coeffs


def _wavelet_thresh_real(
    img: np.ndarray,
    threshold: float,
    wavelet: str = 'db4',
    level: int = 3,
    use_cycle_spinning: bool = True,
    num_shifts: int = 2
) -> np.ndarray:
    """Apply wavelet soft thresholding to real-valued image with cycle spinning."""
    if use_cycle_spinning:
        return cycle_spinning_threshold(img, threshold, wavelet, level, num_shifts, mode='soft')
    else:
        coeffs = wavelet_decompose(img, wavelet, level)
        coeffs_thresh = _wavelet_soft_threshold_detail(coeffs, threshold)
        img_rec = wavelet_reconstruct(coeffs_thresh, wavelet)
        return np.clip(img_rec, 0, None)


def cs_mri_ist(
    kspace_und: np.ndarray,
    mask: np.ndarray,
    wavelet: str = 'db4',
    wavelet_level: int = 3,
    lambda_csmri: float = 0.01,
    num_iter: int = 100,
    step_size: float = 0.1,
    tol: float = 1e-5,
    use_cycle_spinning: bool = True,
    num_cycle_shifts: int = 2,
    use_density_compensation: bool = True,
    verbose: bool = False
) -> np.ndarray:
    """
    Compressed Sensing MRI using Iterative Soft Thresholding (ISTA).
    
    Args:
        kspace_und: Under-sampled k-space data
        mask: Sampling mask (can include density compensation weights)
        wavelet: Wavelet name
        wavelet_level: Wavelet decomposition level
        lambda_csmri: Regularization parameter
        num_iter: Maximum number of iterations
        step_size: Gradient step size
        tol: Convergence tolerance
        use_cycle_spinning: Use cycle spinning to reduce blocking artifacts
        num_cycle_shifts: Number of shifts for cycle spinning
        use_density_compensation: Apply density compensation to gradient
        verbose: Print progress
        
    Returns:
        Reconstructed image (magnitude)
    """
    if kspace_und.ndim == 3:
        kspace_und = np.sqrt(np.sum(np.abs(kspace_und) ** 2, axis=0))
    
    mask_binary = (np.abs(mask) > 0).astype(np.float64)
    
    if use_density_compensation and np.any(mask != mask_binary):
        density_weights = np.abs(mask)
        density_weights[density_weights == 0] = 1.0
    else:
        density_weights = np.ones_like(mask_binary)
    
    x = np.abs(ifft2c(kspace_und))
    x_old = x.copy()
    
    for i in range(num_iter):
        kspace_current = fft2c(x)
        kspace_residual = (kspace_und - kspace_current) * mask_binary
        kspace_residual_weighted = kspace_residual * density_weights
        gradient = np.real(ifft2c(kspace_residual_weighted))
        
        x_grad = x + step_size * gradient
        x_new = _wavelet_thresh_real(
            x_grad, lambda_csmri * step_size, wavelet, wavelet_level,
            use_cycle_spinning, num_cycle_shifts
        )
        
        rel_change = np.linalg.norm(x_new - x_old) / (np.linalg.norm(x_new) + 1e-10)
        
        x_old = x.copy()
        x = x_new
        
        if verbose and i % 10 == 0:
            print(f"CS-MRI ISTA Iteration {i}, Rel Change: {rel_change:.2e}")
        
        if rel_change < tol and i > 20:
            break
    
    return x


def cs_mri_fista(
    kspace_und: np.ndarray,
    mask: np.ndarray,
    wavelet: str = 'db4',
    wavelet_level: int = 3,
    lambda_csmri: float = 0.01,
    num_iter: int = 100,
    step_size: float = 0.1,
    tol: float = 1e-5,
    use_cycle_spinning: bool = True,
    num_cycle_shifts: int = 2,
    use_density_compensation: bool = True,
    verbose: bool = False
) -> np.ndarray:
    """
    Compressed Sensing MRI using Fast ISTA (FISTA) with adaptive restart.
    
    Args:
        kspace_und: Under-sampled k-space data
        mask: Sampling mask (can include density compensation weights)
        wavelet: Wavelet name
        wavelet_level: Wavelet decomposition level
        lambda_csmri: Regularization parameter
        num_iter: Maximum number of iterations
        step_size: Gradient step size
        tol: Convergence tolerance
        use_cycle_spinning: Use cycle spinning to reduce blocking artifacts
        num_cycle_shifts: Number of shifts for cycle spinning
        use_density_compensation: Apply density compensation to gradient
        verbose: Print progress
        
    Returns:
        Reconstructed image (magnitude)
    """
    if kspace_und.ndim == 3:
        kspace_und = np.sqrt(np.sum(np.abs(kspace_und) ** 2, axis=0))
    
    mask_binary = (np.abs(mask) > 0).astype(np.float64)
    
    if use_density_compensation and np.any(mask != mask_binary):
        density_weights = np.abs(mask)
        density_weights[density_weights == 0] = 1.0
    else:
        density_weights = np.ones_like(mask_binary)
    
    x = np.abs(ifft2c(kspace_und))
    
    t = 1.0
    y = x.copy()
    x_old = x.copy()
    best_x = x.copy()
    
    def _objective(x_img):
        k = fft2c(x_img)
        residual = (kspace_und - k) * mask_binary * density_weights
        data_fid = 0.5 * np.sum(np.abs(residual) ** 2)
        coeffs = wavelet_decompose(x_img, wavelet, wavelet_level)
        l1_norm = 0
        for dc in coeffs[1:]:
            for c in dc:
                l1_norm += np.sum(np.abs(c))
        return data_fid + lambda_csmri * l1_norm
    
    best_obj = _objective(x)
    restarts = 0
    
    for i in range(num_iter):
        kspace_current = fft2c(y)
        kspace_residual = (kspace_und - kspace_current) * mask_binary
        kspace_residual_weighted = kspace_residual * density_weights
        gradient = np.real(ifft2c(kspace_residual_weighted))
        
        x_grad = y + step_size * gradient
        x_new = _wavelet_thresh_real(
            x_grad, lambda_csmri * step_size, wavelet, wavelet_level,
            use_cycle_spinning, num_cycle_shifts
        )
        
        current_obj = _objective(x_new)
        
        if current_obj > best_obj and i > 5:
            t = 1.0
            y = best_x.copy()
            restarts += 1
            if restarts > 3:
                return cs_mri_ist(
                    kspace_und, mask, wavelet, wavelet_level,
                    lambda_csmri, num_iter - i, step_size, tol,
                    use_cycle_spinning, num_cycle_shifts,
                    use_density_compensation, verbose
                )
            continue
        
        if current_obj < best_obj:
            best_obj = current_obj
            best_x = x_new.copy()
        
        t_new = min(0.5 * (1 + np.sqrt(1 + 4 * t * t)), 5.0)
        momentum = max(0.0, min(0.9, (t - 1) / t_new))
        y = x_new + momentum * (x_new - x_old)
        y = np.clip(y, 0, None)
        
        t = t_new
        x_old = x.copy()
        x = x_new
        
        rel_change = np.linalg.norm(x - x_old) / (np.linalg.norm(x) + 1e-10)
        
        if verbose and i % 10 == 0:
            print(f"CS-MRI FISTA Iteration {i}, Rel Change: {rel_change:.2e}, Restarts: {restarts}")
        
        if rel_change < tol and i > 20:
            break
    
    return x


def zero_filled_reconstruction(kspace_und: np.ndarray) -> np.ndarray:
    """
    Simple zero-filled reconstruction (inverse FFT of under-sampled k-space).
    
    Args:
        kspace_und: Under-sampled k-space data
        
    Returns:
        Zero-filled reconstruction
    """
    return np.abs(ifft2c(kspace_und))


def reconstruct(
    method: str,
    kspace_und: np.ndarray,
    mask: np.ndarray,
    **kwargs
) -> np.ndarray:
    """
    Reconstruct image using specified method.
    
    Args:
        method: Reconstruction method name
        kspace_und: Under-sampled k-space
        mask: Sampling mask
        **kwargs: Method-specific parameters
        
    Returns:
        Reconstructed image
    """
    method = method.lower()
    
    if method == 'zero_filled' or method == 'zf':
        return zero_filled_reconstruction(kspace_und)
    elif method == 'tv':
        return tv_regularized_reconstruction(kspace_und, mask, **kwargs)
    elif method == 'sense':
        return sense_reconstruction(kspace_und, mask=mask, **kwargs)
    elif method == 'cs_mri_ist' or method == 'ist':
        return cs_mri_ist(kspace_und, mask, **kwargs)
    elif method == 'cs_mri_fista' or method == 'fista':
        return cs_mri_fista(kspace_und, mask, **kwargs)
    elif method == 'pnp_dncnn' or method == 'pnp':
        from dncnn import pnp_admm_reconstruction, create_denoiser
        denoiser_type = kwargs.pop('denoiser_type', 'auto')
        denoiser = create_denoiser(denoiser_type)
        return pnp_admm_reconstruction(kspace_und, mask, denoiser, **kwargs)
    elif method == 'gridding' or method == 'nufft':
        from nufft_recon import gridding_reconstruction
        kx = kwargs.pop('kx', None)
        ky = kwargs.pop('ky', None)
        grid_size = kwargs.pop('grid_size', kspace_und.shape[-1])
        if kx is None or ky is None:
            return np.abs(ifft2c(kspace_und))
        return gridding_reconstruction(kspace_und, kx, ky, grid_size, **kwargs)
    elif method == 'kt_slr' or method == 'slr':
        from kt_slr import kt_slr_reconstruction
        return kt_slr_reconstruction(kspace_und, mask, **kwargs)
    elif method == 'kt_focuss':
        from kt_slr import kt_focuss_reconstruction
        return kt_focuss_reconstruction(kspace_und, mask, **kwargs)
    elif method == 'temporal_low_rank' or method == 'tlr':
        from kt_slr import temporal_low_rank_reconstruction
        return temporal_low_rank_reconstruction(kspace_und, mask, **kwargs)
    else:
        raise ValueError(f"Unknown reconstruction method: {method}")


def get_reconstruction_methods() -> dict:
    """Get available reconstruction methods."""
    methods = {
        'zero_filled': 'Zero-filled',
        'tv': 'TV Regularization',
        'sense': 'SENSE',
        'cs_mri_ist': 'CS-MRI (IST)',
        'cs_mri_fista': 'CS-MRI (FISTA)',
        'pnp_dncnn': 'PnP-DnCNN (Plug-and-Play)',
        'gridding': 'NUFFT Gridding',
        'kt_slr': 'k-t SLR (Dynamic)',
        'kt_focuss': 'k-t FOCUSS (Dynamic)',
        'temporal_low_rank': 'Temporal Low-Rank (Dynamic)',
    }
    return methods
