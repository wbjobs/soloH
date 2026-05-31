"""
Depth from EPI (Epipolar Plane Image) for Light Fields

Implements depth estimation based on slope detection in epipolar plane images.
Methods include:
- EPI construction from sub-aperture array
- Slope detection using gradient analysis
- Hough/Radon transform for line detection
- Sub-pixel slope refinement
"""

import numpy as np
import cv2
from tqdm import tqdm
from scipy.ndimage import gaussian_filter, sobel, median_filter
from scipy.signal import find_peaks


def construct_epi(subapertures, axis='horizontal', line_idx=None):
    """
    Construct Epipolar Plane Image (EPI) from sub-aperture array.
    
    Horizontal EPI (u, t): Fix v (view row), vary u (view column) and t (spatial row)
    Vertical EPI (v, s): Fix u (view column), vary v (view row) and s (spatial column)
    
    Parameters:
        subapertures: SubApertureArray object
        axis: 'horizontal' or 'vertical'
        line_idx: Index of the fixed line (if None, return all)
        
    Returns:
        epi: EPI volume [num_fixed, num_views, num_spatial, num_channels]
    """
    num_v, num_u = subapertures.num_v, subapertures.num_u
    h, w = subapertures.height, subapertures.width
    channels = subapertures.channels

    imgs = subapertures.images

    if channels > 1:
        imgs_gray = np.mean(imgs, axis=-1)
    else:
        imgs_gray = imgs[..., 0]

    if axis == 'horizontal':
        if line_idx is not None:
            epi = imgs_gray[:, line_idx, :, :]
        else:
            epi = np.zeros((num_v, num_u, w), dtype=np.float32)
            for v in range(num_v):
                epi[v] = imgs_gray[:, v, :, :]
    else:
        if line_idx is not None:
            epi = imgs_gray[:, :, :, line_idx]
        else:
            epi = np.zeros((num_u, num_v, h), dtype=np.float32)
            for u in range(num_u):
                epi[u] = imgs_gray[:, :, :, u]

    return epi


def detect_slope_gradient(epi_line, min_slope=-10, max_slope=10, num_slopes=201):
    """
    Detect slope in EPI line using gradient analysis.
    
    Parameters:
        epi_line: EPI for a single spatial location [num_views, num_spatial]
        min_slope: Minimum slope to consider
        max_slope: Maximum slope to consider
        num_slopes: Number of slope candidates
        
    Returns:
        best_slope: Estimated slope
        confidence: Confidence measure
        response_curve: Slope response curve
    """
    num_views, num_spatial = epi_line.shape
    center_view = num_views // 2

    slopes = np.linspace(min_slope, max_slope, num_slopes)

    grad_u = np.gradient(epi_line, axis=0)
    grad_s = np.gradient(epi_line, axis=1)

    responses = np.zeros(num_slopes, dtype=np.float32)

    for i, slope in enumerate(slopes):
        aligned_stack = np.zeros((num_views, num_spatial), dtype=np.float32)

        for v in range(num_views):
            shift = (v - center_view) * slope

            M = np.float32([[1, 0, shift], [0, 1, 0]])
            aligned_stack[v] = cv2.warpAffine(
                epi_line, M, (num_spatial, num_views),
                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
            )[v]

        response = np.var(aligned_stack, axis=0).mean()
        responses[i] = response

    best_idx = np.argmax(responses)
    best_slope = slopes[best_idx]

    confidence = compute_slope_confidence(responses, best_idx, slopes)

    return best_slope, confidence, responses


def detect_slope_radon(epi_line, min_slope=-10, max_slope=10, num_slopes=201):
    """
    Detect slope using Radon transform approach.
    
    Measures alignment quality by integrating along lines of different slopes.
    
    Parameters:
        epi_line: EPI for a single spatial location [num_views, num_spatial]
        min_slope: Minimum slope
        max_slope: Maximum slope
        num_slopes: Number of slope candidates
        
    Returns:
        best_slope: Estimated slope
        confidence: Confidence measure
        response_curve: Slope response curve
    """
    num_views, num_spatial = epi_line.shape
    center_view = num_views // 2

    slopes = np.linspace(min_slope, max_slope, num_slopes)
    responses = np.zeros(num_slopes, dtype=np.float32)

    epi_norm = (epi_line - epi_line.min()) / (epi_line.max() - epi_line.min() + 1e-8)

    for i, slope in enumerate(slopes):
        integral = 0.0
        count = 0

        for s in range(num_spatial):
            for v in range(num_views):
                s_aligned = int(s + (v - center_view) * slope)
                if 0 <= s_aligned < num_spatial:
                    integral += epi_norm[v, s_aligned]
                    count += 1

        responses[i] = integral / max(count, 1)

    best_idx = np.argmax(responses)
    best_slope = slopes[best_idx]

    confidence = compute_slope_confidence(responses, best_idx, slopes)

    return best_slope, confidence, responses


def detect_slope_fourier(epi_line, min_slope=-10, max_slope=10):
    """
    Detect slope using Fourier domain analysis.
    
    The orientation of energy in the 2D Fourier transform of an EPI
    corresponds to the slope of lines in the spatial domain.
    
    Parameters:
        epi_line: EPI for a single spatial location [num_views, num_spatial]
        
    Returns:
        best_slope: Estimated slope
        confidence: Confidence measure
    """
    num_views, num_spatial = epi_line.shape

    fft = np.fft.fft2(epi_line - epi_line.mean())
    fft_mag = np.abs(np.fft.fftshift(fft))

    cy, cx = num_views // 2, num_spatial // 2

    angles = np.linspace(-np.pi / 2, np.pi / 2, 181)
    responses = np.zeros_like(angles)

    for i, angle in enumerate(angles):
        r = min(num_views, num_spatial) // 2
        for k in range(-r, r + 1):
            ky = int(cy + k * np.sin(angle))
            kx = int(cx + k * np.cos(angle))
            if 0 <= ky < num_views and 0 <= kx < num_spatial:
                responses[i] += fft_mag[ky, kx]

    best_idx = np.argmax(responses)
    best_angle = angles[best_idx]

    slope = np.tan(best_angle + np.pi / 2) if np.cos(best_angle) != 0 else np.sign(np.sin(best_angle)) * 100
    slope = np.clip(slope, min_slope, max_slope)

    second_best = np.partition(responses, -2)[-2]
    confidence = (responses[best_idx] - second_best) / (responses[best_idx] + 1e-8)

    return slope, confidence, responses


def compute_slope_confidence(response_curve, best_idx, slopes):
    """
    Compute confidence for slope detection based on peak sharpness.
    
    Parameters:
        response_curve: Response values for each slope
        best_idx: Index of best slope
        slopes: Array of slope values
        
    Returns:
        confidence: Confidence value (0-1)
    """
    num_slopes = len(slopes)

    peak_val = response_curve[best_idx]

    if best_idx > 0 and best_idx < num_slopes - 1:
        left = response_curve[best_idx - 1]
        right = response_curve[best_idx + 1]
        avg_side = (left + right) / 2

        if peak_val > avg_side:
            sharpness = (peak_val - avg_side) / (peak_val + 1e-8)
        else:
            sharpness = 0.1
    else:
        sharpness = 0.3

    overall_max = response_curve.max()
    overall_min = response_curve.min()
    if overall_max > overall_min:
        normalized = (peak_val - overall_min) / (overall_max - overall_min)
    else:
        normalized = 0.5

    confidence = 0.5 * sharpness + 0.5 * normalized
    confidence = np.clip(confidence, 0, 1)

    return confidence


def subpixel_slope_refinement(response_curve, best_idx, slopes):
    """
    Sub-pixel slope refinement using quadratic fitting.
    
    Parameters:
        response_curve: Response values
        best_idx: Index of best integer slope
        slopes: Array of slope values
        
    Returns:
        refined_slope: Sub-pixel accurate slope
    """
    num_slopes = len(slopes)

    if best_idx <= 0 or best_idx >= num_slopes - 1:
        return slopes[best_idx]

    d0 = best_idx
    c0 = response_curve[d0]
    c_neg = response_curve[d0 - 1]
    c_pos = response_curve[d0 + 1]

    denom = 2 * (c_neg + c_pos - 2 * c0)

    if abs(denom) < 1e-8:
        return slopes[best_idx]

    offset = (c_neg - c_pos) / denom
    slope_step = slopes[1] - slopes[0]

    refined = slopes[best_idx] + offset * slope_step

    return refined


def estimate_depth_epi(subapertures, method='gradient', min_slope=-8, max_slope=8, 
                       num_slopes=161, subpixel_refine=True):
    """
    Depth estimation from EPI slope analysis.
    
    Parameters:
        subapertures: SubApertureArray object
        method: 'gradient', 'radon', or 'fourier'
        min_slope: Minimum slope to consider
        max_slope: Maximum slope to consider
        num_slopes: Number of slope candidates
        subpixel_refine: Enable sub-pixel refinement
        
    Returns:
        disparity_map: Estimated disparity map (disparity = slope)
        confidence_map: Confidence map
        occlusion_mask: Occlusion mask
    """
    num_v, num_u = subapertures.num_v, subapertures.num_u
    h, w = subapertures.height, subapertures.width

    imgs = subapertures.images
    if subapertures.channels > 1:
        imgs_gray = np.mean(imgs, axis=-1)
    else:
        imgs_gray = imgs[..., 0]

    disparity_h = np.zeros((h, w), dtype=np.float32)
    confidence_h = np.zeros((h, w), dtype=np.float32)

    for t in tqdm(range(h), desc="Horizontal EPI analysis"):
        epi_line = imgs_gray[:, :, t, :]

        for s in range(w):
            epi_patch = epi_line[:, max(0, s - 5):min(w, s + 6)]

            if epi_patch.shape[1] < 3:
                continue

            if method == 'gradient':
                slope, conf, responses = detect_slope_gradient(
                    epi_patch, min_slope, max_slope, num_slopes
                )
            elif method == 'radon':
                slope, conf, responses = detect_slope_radon(
                    epi_patch, min_slope, max_slope, num_slopes
                )
            elif method == 'fourier':
                slope, conf, responses = detect_slope_fourier(
                    epi_patch, min_slope, max_slope
                )
            else:
                raise ValueError(f"Unknown method: {method}")

            if subpixel_refine and method != 'fourier':
                best_idx = np.argmax(responses)
                slope = subpixel_slope_refinement(responses, best_idx, 
                                                  np.linspace(min_slope, max_slope, num_slopes))

            disparity_h[t, s] = slope
            confidence_h[t, s] = conf

    disparity_v = np.zeros((h, w), dtype=np.float32)
    confidence_v = np.zeros((h, w), dtype=np.float32)

    center_v = num_v // 2
    for s in tqdm(range(w), desc="Vertical EPI analysis"):
        epi_line = imgs_gray[:, :, :, s]

        for t in range(h):
            epi_patch = epi_line[:, max(0, t - 5):min(h, t + 6)]

            if epi_patch.shape[1] < 3:
                continue

            if method == 'gradient':
                slope, conf, responses = detect_slope_gradient(
                    epi_patch, min_slope, max_slope, num_slopes
                )
            elif method == 'radon':
                slope, conf, responses = detect_slope_radon(
                    epi_patch, min_slope, max_slope, num_slopes
                )
            elif method == 'fourier':
                slope, conf, responses = detect_slope_fourier(
                    epi_patch, min_slope, max_slope
                )

            if subpixel_refine and method != 'fourier':
                best_idx = np.argmax(responses)
                slope = subpixel_slope_refinement(responses, best_idx,
                                                  np.linspace(min_slope, max_slope, num_slopes))

            disparity_v[t, s] = slope
            confidence_v[t, s] = conf

    weight_h = confidence_h / (confidence_h + confidence_v + 1e-8)
    weight_v = confidence_v / (confidence_h + confidence_v + 1e-8)

    disparity_map = weight_h * disparity_h + weight_v * disparity_v
    confidence_map = np.maximum(confidence_h, confidence_v)

    diff = np.abs(disparity_h - disparity_v)
    occlusion_mask = diff > 2.0

    disparity_map = median_filter(disparity_map, size=3)
    confidence_map = gaussian_filter(confidence_map, sigma=1.0)

    return disparity_map, confidence_map, occlusion_mask


def estimate_depth_epi_fast(subapertures, min_slope=-8, max_slope=8, num_slopes=81):
    """
    Fast EPI-based depth estimation using vectorized operations.
    
    Uses pre-shifted stacks and variance computation for efficiency.
    
    Parameters:
        subapertures: SubApertureArray object
        min_slope: Minimum slope
        max_slope: Maximum slope
        num_slopes: Number of slope candidates
        
    Returns:
        disparity_map: Estimated disparity map
        confidence_map: Confidence map
        occlusion_mask: Occlusion mask
    """
    num_v, num_u = subapertures.num_v, subapertures.num_u
    h, w = subapertures.height, subapertures.width
    center_v, center_u = num_v // 2, num_u // 2

    imgs = subapertures.images
    if subapertures.channels > 1:
        imgs_gray = np.mean(imgs, axis=-1)
    else:
        imgs_gray = imgs[..., 0]

    slopes = np.linspace(min_slope, max_slope, num_slopes)

    focus_volume_h = np.zeros((num_slopes, h, w), dtype=np.float32)
    focus_volume_v = np.zeros((num_slopes, h, w), dtype=np.float32)

    for d_idx, slope in enumerate(tqdm(slopes, desc="Fast EPI slope sweep")):
        shifted_stack_h = np.zeros((num_u, h, w), dtype=np.float32)

        for u in range(num_u):
            shift = (u - center_u) * slope
            M = np.float32([[1, 0, shift], [0, 1, 0]])
            shifted_stack_h[u] = cv2.warpAffine(
                imgs_gray[center_v, u], M, (w, h),
                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
            )

        focus_volume_h[d_idx] = np.var(shifted_stack_h, axis=0)

        shifted_stack_v = np.zeros((num_v, h, w), dtype=np.float32)
        for v in range(num_v):
            shift = (v - center_v) * slope
            M = np.float32([[1, 0, 0], [0, 1, shift]])
            shifted_stack_v[v] = cv2.warpAffine(
                imgs_gray[v, center_u], M, (w, h),
                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
            )

        focus_volume_v[d_idx] = np.var(shifted_stack_v, axis=0)

    best_idx_h = np.argmax(focus_volume_h, axis=0)
    best_idx_v = np.argmax(focus_volume_v, axis=0)

    disparity_h = slopes[best_idx_h]
    disparity_v = slopes[best_idx_v]

    conf_h = np.zeros((h, w), dtype=np.float32)
    conf_v = np.zeros((h, w), dtype=np.float32)
    for y in range(h):
        for x in range(w):
            conf_h[y, x] = compute_slope_confidence(
                focus_volume_h[:, y, x], best_idx_h[y, x], slopes
            )
            conf_v[y, x] = compute_slope_confidence(
                focus_volume_v[:, y, x], best_idx_v[y, x], slopes
            )

    disparity_h = refine_disparity_subpixel(focus_volume_h, best_idx_h, slopes)
    disparity_v = refine_disparity_subpixel(focus_volume_v, best_idx_v, slopes)

    weight_h = conf_h / (conf_h + conf_v + 1e-8)
    weight_v = conf_v / (conf_h + conf_v + 1e-8)

    disparity_map = weight_h * disparity_h + weight_v * disparity_v
    confidence_map = np.maximum(conf_h, conf_v)

    diff = np.abs(disparity_h - disparity_v)
    occlusion_mask = diff > 1.5

    disparity_map = median_filter(disparity_map, size=3)

    return disparity_map, confidence_map, occlusion_mask


def refine_disparity_subpixel(focus_volume, best_idx, slopes):
    """
    Vectorized sub-pixel refinement for disparity map.
    
    Parameters:
        focus_volume: [num_slopes, H, W] focus measure volume
        best_idx: [H, W] best slope indices
        slopes: Array of slope values
        
    Returns:
        refined_disparity: Sub-pixel refined disparity map
    """
    num_slopes = len(slopes)
    h, w = best_idx.shape

    refined = np.zeros((h, w), dtype=np.float32)

    for y in range(h):
        for x in range(w):
            idx = int(best_idx[y, x])

            if idx <= 0 or idx >= num_slopes - 1:
                refined[y, x] = slopes[idx]
                continue

            c0 = focus_volume[idx, y, x]
            c_neg = focus_volume[idx - 1, y, x]
            c_pos = focus_volume[idx + 1, y, x]

            denom = 2 * (c_neg + c_pos - 2 * c0)

            if abs(denom) < 1e-8:
                refined[y, x] = slopes[idx]
            else:
                offset = (c_neg - c_pos) / denom
                slope_step = slopes[1] - slopes[0]
                refined[y, x] = slopes[idx] + offset * slope_step

    return refined
