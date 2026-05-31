"""
Depth from Defocus (DFD) for Light Fields

Implements depth estimation based on multi-view standard deviation.
The focus measure (variance/std) across views is used to estimate depth:
- In-focus regions have high variance across views
- Out-of-focus regions have low variance across views
"""

import numpy as np
import cv2
from tqdm import tqdm
from scipy.ndimage import gaussian_filter, maximum_filter, minimum_filter


def compute_focus_stack(subapertures, refocus_depths=None, sigma=1.0):
    """
    Compute focus stack for different depth layers.
    
    Parameters:
        subapertures: SubApertureArray object
        refocus_depths: List of disparity values to refocus at
        sigma: Gaussian sigma for variance computation
        
    Returns:
        focus_stack: [num_depths, H, W] focus measure volume
        depths: The depth values used
    """
    if refocus_depths is None:
        refocus_depths = np.linspace(-5, 5, 21)

    num_v, num_u = subapertures.num_v, subapertures.num_u
    h, w = subapertures.height, subapertures.width

    center_v, center_u = num_v // 2, num_u // 2

    imgs = subapertures.images
    if subapertures.channels > 1:
        imgs_gray = np.mean(imgs, axis=-1)
    else:
        imgs_gray = imgs[..., 0]

    focus_stack = np.zeros((len(refocus_depths), h, w), dtype=np.float32)

    for d_idx, disparity in enumerate(tqdm(refocus_depths, desc="Computing focus stack")):
        refocused_views = np.zeros((num_v, num_u, h, w), dtype=np.float32)

        for v in range(num_v):
            for u in range(num_u):
                shift_v = (v - center_v) * disparity
                shift_u = (u - center_u) * disparity

                M = np.float32([[1, 0, shift_u], [0, 1, shift_v]])
                refocused_views[v, u] = cv2.warpAffine(
                    imgs_gray[v, u], M, (w, h),
                    flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
                )

        focus_measure = np.std(refocused_views, axis=(0, 1))
        focus_measure = gaussian_filter(focus_measure, sigma=sigma)

        focus_stack[d_idx] = focus_measure

    return focus_stack, refocus_depths


def estimate_depth_dfd(subapertures, window_size=7, refocus_depths=None, 
                        use_subpixel=True, anti_alias=True):
    """
    Depth estimation using Depth from Defocus (DFD) method.
    
    Uses the standard deviation across sub-aperture views as a focus measure.
    The depth with maximum focus measure is selected for each pixel.
    
    Includes sub-pixel refinement and anti-aliasing to reduce depth aliasing.
    
    Parameters:
        subapertures: SubApertureArray object
        window_size: Window size for focus measure computation
        refocus_depths: List of disparity values to evaluate
        use_subpixel: Enable sub-pixel depth refinement via quadratic fitting
        anti_alias: Apply anti-aliasing along depth axis
        
    Returns:
        disparity_map: Estimated disparity map
        confidence_map: Confidence map (peak sharpness)
    """
    num_v, num_u = subapertures.num_v, subapertures.num_u
    h, w = subapertures.height, subapertures.width

    imgs = subapertures.images
    if subapertures.channels > 1:
        imgs_gray = np.mean(imgs, axis=-1)
    else:
        imgs_gray = imgs[..., 0]

    if refocus_depths is None:
        refocus_depths = np.linspace(-8, 8, 33)

    center_v, center_u = num_v // 2, num_u // 2

    half_w = window_size // 2

    focus_volume = np.zeros((len(refocus_depths), h, w), dtype=np.float32)

    for d_idx, disparity in enumerate(tqdm(refocus_depths, desc="DFD depth estimation")):
        shifted_stack = np.zeros((num_v, num_u, h, w), dtype=np.float32)

        for v in range(num_v):
            for u in range(num_u):
                shift_v = (v - center_v) * disparity
                shift_u = (u - center_u) * disparity

                M = np.float32([[1, 0, shift_u], [0, 1, shift_v]])
                shifted_stack[v, u] = cv2.warpAffine(
                    imgs_gray[v, u], M, (w, h),
                    flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
                )

        std_map = np.std(shifted_stack, axis=(0, 1))

        from scipy.ndimage import uniform_filter
        local_std = uniform_filter(std_map, size=window_size)

        focus_volume[d_idx] = local_std
    
    if anti_alias:
        focus_volume = anti_alias_focus_volume(focus_volume, sigma=0.5)

    best_depth_idx = np.argmax(focus_volume, axis=0)
    
    if use_subpixel:
        disparity_map = subpixel_refocus(focus_volume, best_depth_idx, refocus_depths)
    else:
        disparity_map = refocus_depths[best_depth_idx]

    confidence_map = compute_confidence(focus_volume, best_depth_idx, refocus_depths, 
                                        refined_depths=disparity_map if use_subpixel else None)

    return disparity_map, confidence_map


def subpixel_refocus(focus_volume, best_idx, depths):
    """
    Sub-pixel depth refinement using quadratic fitting around focus peak.
    
    For each pixel, fits a parabola to the 3 focus values around the peak
    to find the true peak location with sub-disparity precision.
    
    Parameters:
        focus_volume: [D, H, W] focus measure volume
        best_idx: [H, W] index of best depth (integer)
        depths: List of depth/disparity values
        
    Returns:
        refined_depth: [H, W] sub-pixel refined depth map
    """
    num_depths = len(depths)
    h, w = focus_volume.shape[1], focus_volume.shape[2]
    
    refined = np.zeros((h, w), dtype=np.float32)
    
    best_idx = best_idx.astype(int)
    idx_prev = np.clip(best_idx - 1, 0, num_depths - 1)
    idx_next = np.clip(best_idx + 1, 0, num_depths - 1)
    
    y_idx, x_idx = np.ogrid[0:h, 0:w]
    
    f0 = focus_volume[best_idx, y_idx, x_idx]
    f_prev = focus_volume[idx_prev, y_idx, x_idx]
    f_next = focus_volume[idx_next, y_idx, x_idx]
    
    d_prev = depths[idx_prev]
    d0 = depths[best_idx]
    d_next = depths[idx_next]
    
    valid_edge = (best_idx > 0) & (best_idx < num_depths - 1)
    
    denom = 2 * (f_prev - 2 * f0 + f_next)
    valid_peak = valid_edge & (np.abs(denom) > 1e-10)
    
    delta = np.where(
        valid_peak,
        (f_prev - f_next) * (d_next - d0) / denom,
        0.0
    )
    
    refined = np.where(valid_peak, d0 + delta, d0)
    
    refined = np.clip(refined, depths.min(), depths.max())
    
    return refined


def compute_confidence(focus_volume, best_idx, depths, refined_depths=None):
    """
    Compute confidence map based on focus volume peak sharpness.
    
    Includes sub-pixel peak analysis and anti-aliasing measures.
    
    Parameters:
        focus_volume: [D, H, W] focus measure volume
        best_idx: [H, W] index of best depth
        depths: List of depth values
        refined_depths: Optional sub-pixel refined depth map
        
    Returns:
        confidence_map: [H, W] confidence values (0-1)
    """
    num_depths = len(depths)
    h, w = focus_volume.shape[1], focus_volume.shape[2]

    best_idx = best_idx.astype(int)
    y_idx, x_idx = np.ogrid[0:h, 0:w]
    
    idx_prev = np.clip(best_idx - 1, 0, num_depths - 1)
    idx_next = np.clip(best_idx + 1, 0, num_depths - 1)
    
    f0 = focus_volume[best_idx, y_idx, x_idx]
    f_prev = focus_volume[idx_prev, y_idx, x_idx]
    f_next = focus_volume[idx_next, y_idx, x_idx]
    
    avg_side = (f_prev + f_next) / 2
    
    peak_sharpness = np.where(
        f0 > avg_side,
        (f0 - avg_side) / (f0 + 1e-8),
        0.0
    )
    
    valid_edge = (best_idx > 0) & (best_idx < num_depths - 1)
    
    if refined_depths is not None:
        d0 = depths[best_idx]
        delta = np.abs(refined_depths - d0)
        max_delta = (depths[1] - depths[0]) / 2
        interpolation_confidence = 1.0 - np.clip(delta / max_delta, 0, 1)
    else:
        interpolation_confidence = np.ones((h, w), dtype=np.float32)
    
    all_focus = focus_volume.reshape(num_depths, -1)
    sorted_focus = np.sort(all_focus, axis=0)[::-1]
    if sorted_focus.shape[0] >= 2:
        ratio = sorted_focus[1] / (sorted_focus[0] + 1e-8)
        ratio = ratio.reshape(h, w)
        uniqueness = 1.0 - np.clip(ratio, 0, 1)
    else:
        uniqueness = np.ones((h, w), dtype=np.float32)
    
    confidence = peak_sharpness * interpolation_confidence * uniqueness
    
    edge_confidence = np.where(valid_edge, 1.0, 0.5)
    confidence = confidence * edge_confidence
    
    confidence = (confidence - confidence.min()) / (confidence.max() + 1e-8)

    return confidence


def anti_alias_focus_volume(focus_volume, sigma=0.5):
    """
    Apply anti-aliasing filtering to focus volume.
    
    Uses Gaussian smoothing along the depth axis to reduce aliasing
    caused by discrete depth sampling.
    
    Parameters:
        focus_volume: [D, H, W] focus measure volume
        sigma: Gaussian sigma for depth-axis smoothing
        
    Returns:
        aa_volume: Anti-aliased focus volume
    """
    from scipy.ndimage import gaussian_filter1d
    
    aa_volume = gaussian_filter1d(focus_volume, sigma=sigma, axis=0)
    
    return aa_volume


def fit_parabola_1d(f_vals, x_vals):
    """
    Fit parabola to 3 points and find peak position.
    
    Parameters:
        f_vals: [3] function values at x_vals
        x_vals: [3] x coordinates
        
    Returns:
        x_peak: Peak x coordinate
        f_peak: Peak function value
    """
    f0, f1, f2 = f_vals
    x0, x1, x2 = x_vals
    
    denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
    if abs(denom) < 1e-10:
        return x1, f1
    
    A = (x2 * (f1 - f0) + x1 * (f0 - f2) + x0 * (f2 - f1)) / denom
    B = (x2*x2 * (f0 - f1) + x1*x1 * (f2 - f0) + x0*x0 * (f1 - f2)) / denom
    
    if abs(A) < 1e-10:
        return x1, f1
    
    x_peak = -B / (2 * A)
    f_peak = f0 + A * x_peak * x_peak + B * x_peak
    
    return x_peak, f_peak


def estimate_depth_dfd_fast(subapertures, use_all_views=True, 
                            use_subpixel=True, anti_alias=True, num_depths=32):
    """
    Fast DFD depth estimation using direct variance computation.
    
    Computes variance across views at multiple scales without explicit refocusing.
    
    Includes sub-pixel refinement and anti-aliasing to reduce depth aliasing.
    
    Parameters:
        subapertures: SubApertureArray object
        use_all_views: If True, use all views; if False, use center row/column
        use_subpixel: Enable sub-pixel depth refinement via quadratic fitting
        anti_alias: Apply anti-aliasing along depth axis
        num_depths: Number of depth planes for sampling (default: 32)
        
    Returns:
        disparity_map: Estimated disparity map
        confidence_map: Confidence map
    """
    num_v, num_u = subapertures.num_v, subapertures.num_u
    h, w = subapertures.height, subapertures.width

    imgs = subapertures.images
    if subapertures.channels > 1:
        imgs_gray = np.mean(imgs, axis=-1)
    else:
        imgs_gray = imgs[..., 0]

    center_v, center_u = num_v // 2, num_u // 2

    disparities = np.linspace(-6, 6, 25)
    focus_responses = np.zeros((len(disparities), h, w), dtype=np.float32)

    if use_all_views:
        view_indices = [(v, u) for v in range(num_v) for u in range(num_u)]
    else:
        view_indices = [(center_v, u) for u in range(num_u)] + \
                       [(v, center_u) for v in range(num_v) if v != center_v]

    for d_idx, disp in enumerate(tqdm(disparities, desc="Fast DFD")):
        variance_accum = np.zeros((h, w), dtype=np.float32)
        mean_accum = np.zeros((h, w), dtype=np.float32)
        count = 0

        for v, u in view_indices:
            shift_v = (v - center_v) * disp
            shift_u = (u - center_u) * disp

            M = np.float32([[1, 0, shift_u], [0, 1, shift_v]])
            shifted = cv2.warpAffine(
                imgs_gray[v, u], M, (w, h),
                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
            )

            mean_accum += shifted
            variance_accum += shifted * shifted
            count += 1

        mean = mean_accum / count
        variance = (variance_accum / count) - mean * mean
        focus_responses[d_idx] = np.sqrt(np.maximum(variance, 0))
    
    if anti_alias:
        focus_responses = anti_alias_focus_volume(focus_responses, sigma=0.5)

    best_idx = np.argmax(focus_responses, axis=0)
    
    if use_subpixel:
        disparity_map = subpixel_refocus(focus_responses, best_idx, disparities)
    else:
        disparity_map = disparities[best_idx]

    confidence = compute_confidence(focus_responses, best_idx, disparities,
                                    refined_depths=disparity_map if use_subpixel else None)

    return disparity_map, confidence
