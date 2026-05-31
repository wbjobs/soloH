"""
Depth Map Post-Processing Module

Provides:
- Confidence map computation and refinement
- Occlusion region detection and marking
- Disparity map filtering and smoothing
- Multi-algorithm result fusion
"""

import numpy as np
import cv2
from scipy.ndimage import (
    median_filter, gaussian_filter, binary_dilation, binary_erosion,
    maximum_filter, minimum_filter, label
)
from tqdm import tqdm


def compute_confidence_map(disparity_map, subapertures, method='variance', window_size=7):
    """
    Compute confidence map for disparity estimation.
    
    Parameters:
        disparity_map: Estimated disparity map
        subapertures: SubApertureArray object
        method: Confidence computation method
            'variance': Variance of matching costs
            'gradient': Edge-aware confidence
            'consistency': Left-right consistency
        window_size: Window size for local computation
        
    Returns:
        confidence_map: Confidence values (0-1)
    """
    h, w = disparity_map.shape

    if method == 'gradient':
        try:
            grad_x = np.abs(cv2.Sobel(disparity_map, cv2.CV_32F, 1, 0, ksize=3))
            grad_y = np.abs(cv2.Sobel(disparity_map, cv2.CV_32F, 0, 1, ksize=3))
        except:
            from scipy.ndimage import sobel
            grad_x = np.abs(sobel(disparity_map, axis=1))
            grad_y = np.abs(sobel(disparity_map, axis=0))
        grad_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)

        grad_inv = 1.0 / (grad_mag + 1.0)
        confidence = (grad_inv - grad_inv.min()) / (grad_inv.max() - grad_inv.min() + 1e-8)

    elif method == 'variance':
        from scipy.ndimage import uniform_filter
        mean_disp = uniform_filter(disparity_map, size=window_size)
        mean_disp_sq = uniform_filter(disparity_map ** 2, size=window_size)
        variance = mean_disp_sq - mean_disp ** 2
        variance = np.maximum(variance, 0)

        var_inv = 1.0 / (variance + 1.0)
        confidence = (var_inv - var_inv.min()) / (var_inv.max() - var_inv.min() + 1e-8)

    else:
        confidence = np.ones((h, w), dtype=np.float32) * 0.5

    return confidence


def detect_occlusions(disparity_map, subapertures=None, method='lrc', threshold=1.0):
    """
    Detect occluded regions in disparity map.
    
    Parameters:
        disparity_map: Disparity map from left view
        subapertures: Optional SubApertureArray object for view-based detection
        method: Occlusion detection method
            'lrc': Left-right consistency check
            'gradient': Discontinuity-based detection
            'combination': Combined multiple methods
        threshold: Threshold for consistency check
        
    Returns:
        occlusion_mask: Boolean mask where True indicates occluded region
    """
    h, w = disparity_map.shape

    if method == 'gradient':
        try:
            grad_x = cv2.Sobel(disparity_map, cv2.CV_32F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(disparity_map, cv2.CV_32F, 0, 1, ksize=3)
        except:
            from scipy.ndimage import sobel
            grad_x = sobel(disparity_map, axis=1)
            grad_y = sobel(disparity_map, axis=0)
        grad_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)

        occlusion_mask = grad_mag > threshold * np.median(grad_mag)

    elif method == 'lrc' and subapertures is not None:
        num_v, num_u = subapertures.num_v, subapertures.num_u
        center_v, center_u = num_v // 2, num_u // 2

        imgs = subapertures.images
        if subapertures.channels > 1:
            imgs_gray = np.mean(imgs, axis=-1)
        else:
            imgs_gray = imgs[..., 0]

        if center_u + 1 < num_u and center_u - 1 >= 0:
            img_left = imgs_gray[center_v, center_u - 1]
            img_right = imgs_gray[center_v, center_u + 1]

            from .depth_stereo import compute_cost_volume, winner_takes_all, subpixel_refinement

            cost_lr = compute_cost_volume(img_left, img_right, -8, 8, 7, 'sad')
            disp_idx_lr = winner_takes_all(cost_lr)
            disp_lr = subpixel_refinement(cost_lr, disp_idx_lr, -8)

            cost_rl = compute_cost_volume(img_right, img_left, -8, 8, 7, 'sad')
            disp_idx_rl = winner_takes_all(cost_rl)
            disp_rl = subpixel_refinement(cost_rl, disp_idx_rl, -8)

            from .depth_stereo import left_right_consistency_check
            valid_mask, occlusion_mask = left_right_consistency_check(disp_lr, disp_rl, threshold)
        else:
            occlusion_mask = np.zeros((h, w), dtype=bool)

    elif method == 'combination':
        try:
            grad_x = np.abs(cv2.Sobel(disparity_map, cv2.CV_32F, 1, 0, ksize=3))
            grad_y = np.abs(cv2.Sobel(disparity_map, cv2.CV_32F, 0, 1, ksize=3))
        except:
            from scipy.ndimage import sobel
            grad_x = np.abs(sobel(disparity_map, axis=1))
            grad_y = np.abs(sobel(disparity_map, axis=0))
        grad_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)

        from scipy.ndimage import uniform_filter
        mean_disp = uniform_filter(disparity_map, size=5)
        mean_disp_sq = uniform_filter(disparity_map ** 2, size=5)
        variance = mean_disp_sq - mean_disp ** 2
        variance = np.maximum(variance, 0)

        occlusion_mask = (grad_mag > 2 * np.median(grad_mag)) | (variance > 5 * np.median(variance))

    else:
        grad_x = np.abs(cv2.Sobel(disparity_map, cv2.CV_32F, 1, 0, ksize=3))
        occlusion_mask = grad_x > 5 * np.median(grad_x)

    return occlusion_mask


def fill_occlusions(disparity_map, occlusion_mask, method='ordered_inpaint'):
    """
    Fill occluded regions in disparity map with depth-order-aware algorithms.
    
    Implements layered filling for foreground-background occlusions:
    1. Classify occlusions by depth order (foreground vs background)
    2. Fill background occlusions first using background depth values
    3. Use edge-preserving interpolation to ensure depth continuity
    4. Apply smooth transition at occlusion boundaries
    
    Parameters:
        disparity_map: Disparity map with occlusions
        occlusion_mask: Boolean mask of occluded regions
        method: Filling method
            'ordered_inpaint': Depth-ordered inpainting (recommended)
            'layered_bilateral': Layered bilateral interpolation
            'region_growing': Depth-aware region growing
            'inpaint': Standard OpenCV inpainting
            'bilateral': Bilateral interpolation
            'median': Median filtering from neighbors
            
    Returns:
        filled_disparity: Disparity map with occlusions filled
    """
    h, w = disparity_map.shape
    filled = disparity_map.copy()
    valid = ~occlusion_mask

    if not np.any(occlusion_mask):
        return filled

    if method == 'ordered_inpaint':
        filled = _ordered_inpainting(disparity_map, occlusion_mask)

    elif method == 'layered_bilateral':
        filled = _layered_bilateral_fill(disparity_map, occlusion_mask)

    elif method == 'region_growing':
        filled = _depth_aware_region_growing(disparity_map, occlusion_mask)

    elif method == 'inpaint':
        mask_8bit = (occlusion_mask.astype(np.uint8) * 255)

        disp_norm = (disparity_map - disparity_map.min()) / (disparity_map.max() - disparity_map.min() + 1e-8)
        disp_8bit = (disp_norm * 255).astype(np.uint8)

        disp_3ch = np.stack([disp_8bit, disp_8bit, disp_8bit], axis=-1)

        try:
            inpainted_3ch = cv2.inpaint(disp_3ch, mask_8bit, 3, cv2.INPAINT_TELEA)
            inpainted = inpainted_3ch[:, :, 0]
        except:
            from scipy.ndimage import median_filter, gaussian_filter
            inpainted = median_filter(disparity_map, size=5)
            inpainted = gaussian_filter(inpainted, sigma=1.0)
            inpainted = ((inpainted - inpainted.min()) / (inpainted.max() - inpainted.min() + 1e-8) * 255).astype(np.uint8)

        filled = inpainted.astype(np.float32) / 255.0
        filled = filled * (disparity_map.max() - disparity_map.min()) + disparity_map.min()
        filled[~occlusion_mask] = disparity_map[~occlusion_mask]

    elif method == 'bilateral':
        for y in range(h):
            for x in range(w):
                if occlusion_mask[y, x]:
                    window = 5
                    neighbors = []
                    for dy in range(-window, window + 1):
                        for dx in range(-window, window + 1):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w and valid[ny, nx]:
                                dist = np.sqrt(dy ** 2 + dx ** 2)
                                weight = 1.0 / (dist + 1.0)
                                neighbors.append((weight, disparity_map[ny, nx]))

                    if neighbors:
                        total_weight = sum(w for w, _ in neighbors)
                        filled[y, x] = sum(w * v for w, v in neighbors) / total_weight

    elif method == 'median':
        med_filtered = median_filter(disparity_map, size=5)
        filled[occlusion_mask] = med_filtered[occlusion_mask]

    else:
        filled = _ordered_inpainting(disparity_map, occlusion_mask)

    return filled


def _classify_occlusion_type(disparity_map, occlusion_mask):
    """
    Classify occlusions into background-occluded and foreground-occluded regions.
    
    Background-occluded: Low disparity (far) pixels occluded by high disparity (near) objects
    Foreground-occluded: High disparity (near) pixels at object boundaries
    
    Parameters:
        disparity_map: Input disparity map
        occlusion_mask: Boolean occlusion mask
        
    Returns:
        bg_occlusion: Mask of background-occluded regions
        fg_occlusion: Mask of foreground-occluded regions
    """
    h, w = disparity_map.shape
    valid = ~occlusion_mask
    
    try:
        grad_x = cv2.Sobel(disparity_map, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(disparity_map, cv2.CV_32F, 0, 1, ksize=3)
    except:
        from scipy.ndimage import sobel
        grad_x = sobel(disparity_map, axis=1)
        grad_y = sobel(disparity_map, axis=0)
    
    grad_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)
    
    mean_disp = np.mean(disparity_map[valid])
    median_disp = np.median(disparity_map[valid])
    
    bg_occlusion = np.zeros_like(occlusion_mask)
    fg_occlusion = np.zeros_like(occlusion_mask)
    
    labeled, num_regions = label(occlusion_mask)
    
    for region_id in range(1, num_regions + 1):
        region_mask = labeled == region_id
        
        dilated = binary_dilation(region_mask, iterations=2)
        border = dilated & ~region_mask & valid
        
        if np.sum(border) > 0:
            border_disp = disparity_map[border]
            region_grad = grad_mag[border]
            
            if np.mean(border_disp) > median_disp and np.mean(region_grad) > np.median(grad_mag):
                fg_occlusion |= region_mask
            else:
                bg_occlusion |= region_mask
        else:
            bg_occlusion |= region_mask
    
    return bg_occlusion, fg_occlusion


def _ordered_inpainting(disparity_map, occlusion_mask):
    """
    Depth-ordered inpainting for occlusion filling.
    
    Fills background occlusions first using background depth values,
    then foreground occlusions. Uses anisotropic diffusion to ensure
    depth continuity across occlusion boundaries.
    
    Parameters:
        disparity_map: Input disparity map
        occlusion_mask: Boolean occlusion mask
        
    Returns:
        filled: Filled disparity map
    """
    h, w = disparity_map.shape
    filled = disparity_map.copy()
    
    bg_occlusion, fg_occlusion = _classify_occlusion_type(disparity_map, occlusion_mask)
    
    valid = ~occlusion_mask
    
    bg_mask = bg_occlusion & ~valid
    fg_mask = fg_occlusion & ~valid
    
    all_occlusion = bg_mask | fg_mask
    
    mask_8bit = (all_occlusion.astype(np.uint8) * 255)
    
    disp_min, disp_max = disparity_map[valid].min(), disparity_map[valid].max()
    disp_norm = (disparity_map - disp_min) / (disp_max - disp_min + 1e-8)
    disp_8bit = (disp_norm * 255).astype(np.uint8)
    
    disp_3ch = np.stack([disp_8bit, disp_8bit, disp_8bit], axis=-1)
    
    try:
        if np.any(bg_mask):
            bg_mask_8bit = (bg_mask.astype(np.uint8) * 255)
            inpainted_bg_3ch = cv2.inpaint(disp_3ch, bg_mask_8bit, 5, cv2.INPAINT_TELEA)
            inpainted_bg = inpainted_bg_3ch[:, :, 0]
            
            filled_bg = inpainted_bg.astype(np.float32) / 255.0
            filled_bg = filled_bg * (disp_max - disp_min) + disp_min
            
            filled[bg_mask] = filled_bg[bg_mask]
            disp_8bit[bg_mask] = inpainted_bg[bg_mask]
            disp_3ch = np.stack([disp_8bit, disp_8bit, disp_8bit], axis=-1)
        
        if np.any(fg_mask):
            fg_mask_8bit = (fg_mask.astype(np.uint8) * 255)
            inpainted_fg_3ch = cv2.inpaint(disp_3ch, fg_mask_8bit, 3, cv2.INPAINT_TELEA)
            inpainted_fg = inpainted_fg_3ch[:, :, 0]
            
            filled_fg = inpainted_fg.astype(np.float32) / 255.0
            filled_fg = filled_fg * (disp_max - disp_min) + disp_min
            
            filled[fg_mask] = filled_fg[fg_mask]
            
    except:
        filled = _anisotropic_diffusion_fill(disparity_map, occlusion_mask)
    
    filled[~all_occlusion] = disparity_map[~all_occlusion]
    
    filled = _smooth_occlusion_boundaries(filled, occlusion_mask, disparity_map)
    
    return filled


def _anisotropic_diffusion_fill(disparity_map, occlusion_mask, num_iter=5):
    """
    Fill occlusions using anisotropic diffusion for depth continuity.
    
    Parameters:
        disparity_map: Input disparity map
        occlusion_mask: Boolean occlusion mask
        num_iter: Number of diffusion iterations
        
    Returns:
        filled: Filled disparity map
    """
    h, w = disparity_map.shape
    filled = disparity_map.copy()
    valid = ~occlusion_mask
    
    lambda_coeff = 0.25
    kappa = 0.05 * (disparity_map[valid].max() - disparity_map[valid].min() + 1e-8)
    
    for iteration in range(num_iter):
        new_filled = filled.copy()
        
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if not occlusion_mask[y, x]:
                    continue
                
                dN = filled[y - 1, x] - filled[y, x]
                dS = filled[y + 1, x] - filled[y, x]
                dE = filled[y, x + 1] - filled[y, x]
                dW = filled[y, x - 1] - filled[y, x]
                
                cN = np.exp(-(np.abs(dN) / kappa) ** 2)
                cS = np.exp(-(np.abs(dS) / kappa) ** 2)
                cE = np.exp(-(np.abs(dE) / kappa) ** 2)
                cW = np.exp(-(np.abs(dW) / kappa) ** 2)
                
                if not valid[y - 1, x]: cN = 0.1
                if not valid[y + 1, x]: cS = 0.1
                if not valid[y, x + 1]: cE = 0.1
                if not valid[y, x - 1]: cW = 0.1
                
                new_filled[y, x] = filled[y, x] + lambda_coeff * (
                    cN * dN + cS * dS + cE * dE + cW * dW
                )
        
        filled = new_filled
    
    return filled


def _layered_bilateral_fill(disparity_map, occlusion_mask):
    """
    Layered bilateral interpolation that respects depth order.
    
    Separates background and foreground layers, fills each layer
    independently, and combines with smooth transitions.
    
    Parameters:
        disparity_map: Input disparity map
        occlusion_mask: Boolean occlusion mask
        
    Returns:
        filled: Filled disparity map
    """
    h, w = disparity_map.shape
    filled = disparity_map.copy()
    valid = ~occlusion_mask
    
    bg_occlusion, fg_occlusion = _classify_occlusion_type(disparity_map, occlusion_mask)
    
    median_disp = np.median(disparity_map[valid])
    
    bg_pixels = valid & (disparity_map <= median_disp)
    fg_pixels = valid & (disparity_map > median_disp)
    
    bg_disp = np.where(bg_pixels, disparity_map, np.nan)
    fg_disp = np.where(fg_pixels, disparity_map, np.nan)
    
    from scipy.interpolate import griddata
    y_coords, x_coords = np.mgrid[0:h, 0:w]
    
    if np.any(bg_pixels):
        bg_points = np.column_stack([y_coords[bg_pixels], x_coords[bg_pixels]])
        bg_values = disparity_map[bg_pixels]
        bg_interp = griddata(bg_points, bg_values, (y_coords, x_coords), method='linear', fill_value=np.nanmean(bg_values))
    else:
        bg_interp = np.full((h, w), median_disp)
    
    if np.any(fg_pixels):
        fg_points = np.column_stack([y_coords[fg_pixels], x_coords[fg_pixels]])
        fg_values = disparity_map[fg_pixels]
        fg_interp = griddata(fg_points, fg_values, (y_coords, x_coords), method='linear', fill_value=np.nanmean(fg_values))
    else:
        fg_interp = np.full((h, w), median_disp)
    
    try:
        grad_x = cv2.Sobel(disparity_map, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(disparity_map, cv2.CV_32F, 0, 1, ksize=3)
    except:
        from scipy.ndimage import sobel
        grad_x = sobel(disparity_map, axis=1)
        grad_y = sobel(disparity_map, axis=0)
    edge_strength = np.sqrt(grad_x ** 2 + grad_y ** 2)
    edge_strength = (edge_strength - edge_strength.min()) / (edge_strength.max() + 1e-8)
    
    alpha = 1.0 / (1.0 + np.exp(-10 * (edge_strength - 0.3)))
    
    bg_weight = np.where(fg_occlusion, 0.3, 1.0 - alpha)
    fg_weight = np.where(fg_occlusion, 0.7, alpha)
    
    combined = bg_weight * bg_interp + fg_weight * fg_interp
    
    filled[occlusion_mask] = combined[occlusion_mask]
    filled[~occlusion_mask] = disparity_map[~occlusion_mask]
    
    return filled


def _depth_aware_region_growing(disparity_map, occlusion_mask):
    """
    Fill occlusions using depth-aware region growing.
    
    Starts from occlusion boundaries and grows inward, preferring
    to fill with similar depth values from neighbors. Fills from
    low gradient regions first, then high gradient boundaries.
    
    Parameters:
        disparity_map: Input disparity map
        occlusion_mask: Boolean occlusion mask
        
    Returns:
        filled: Filled disparity map
    """
    h, w = disparity_map.shape
    filled = disparity_map.copy()
    valid = ~occlusion_mask
    
    from scipy.ndimage import distance_transform_edt
    
    dist_transform = distance_transform_edt(occlusion_mask)
    
    frontier = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if occlusion_mask[y, x]:
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ny, nx = y + dy, x + dx
                    if valid[ny, nx]:
                        frontier.append((dist_transform[y, x], y, x, disparity_map[ny, nx]))
                        break
    
    frontier.sort(key=lambda x: x[0])
    
    for dist, y, x, seed_disp in frontier:
        if not occlusion_mask[y, x]:
            continue
        
        window = 3
        neighbors = []
        weights = []
        
        for dy in range(-window, window + 1):
            for dx in range(-window, window + 1):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and valid[ny, nx]:
                    spatial_dist = np.sqrt(dy ** 2 + dx ** 2)
                    depth_diff = np.abs(disparity_map[ny, nx] - seed_disp)
                    
                    weight = np.exp(-spatial_dist / 2.0) * np.exp(-depth_diff / 1.0)
                    neighbors.append(disparity_map[ny, nx])
                    weights.append(weight)
        
        if neighbors and sum(weights) > 0:
            filled[y, x] = np.average(neighbors, weights=weights)
            valid[y, x] = True
            occlusion_mask[y, x] = False
    
    remaining = np.where(occlusion_mask)
    for y, x in zip(*remaining):
        window = 5
        neighbors = []
        for dy in range(-window, window + 1):
            for dx in range(-window, window + 1):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and valid[ny, nx]:
                    neighbors.append(filled[ny, nx])
        if neighbors:
            filled[y, x] = np.median(neighbors)
    
    return filled


def _smooth_occlusion_boundaries(filled, occlusion_mask, original_disparity, window=3):
    """
    Apply smooth transition at occlusion boundaries to reduce artifacts.
    
    Parameters:
        filled: Filled disparity map
        occlusion_mask: Original occlusion mask
        original_disparity: Original disparity map
        window: Size of transition window
        
    Returns:
        smoothed: Smoothed disparity map
    """
    h, w = filled.shape
    smoothed = filled.copy()
    
    dilated = binary_dilation(occlusion_mask, iterations=window)
    boundary = dilated & ~occlusion_mask
    
    try:
        dist_to_occlusion = distance_transform_edt(~occlusion_mask)
    except:
        from scipy.ndimage import distance_transform_edt
        dist_to_occlusion = distance_transform_edt(~occlusion_mask)
    
    alpha = np.clip(dist_to_occlusion / window, 0, 1)
    
    smoothed = alpha * original_disparity + (1 - alpha) * filled
    
    return smoothed


def smooth_disparity(disparity_map, confidence_map=None, method='bilateral', sigma_color=25, sigma_space=5):
    """
    Smooth disparity map while preserving edges.
    
    Parameters:
        disparity_map: Input disparity map
        confidence_map: Optional confidence map for weighted smoothing
        method: Smoothing method
            'bilateral': Bilateral filter
            'gaussian': Gaussian filter
            'median': Median filter
            'wls': Weighted least squares (edge-preserving)
        sigma_color: Color sigma for bilateral filter
        sigma_space: Spatial sigma for filters
        
    Returns:
        smoothed_disparity: Smoothed disparity map
    """
    if method == 'bilateral':
        disp_norm = (disparity_map - disparity_map.min()) / (disparity_map.max() - disparity_map.min() + 1e-8)
        disp_8bit = (disp_norm * 255).astype(np.uint8)

        disp_3ch = np.stack([disp_8bit, disp_8bit, disp_8bit], axis=-1)

        try:
            smoothed_3ch = cv2.bilateralFilter(disp_3ch, 9, sigma_color, sigma_space)
            smoothed_8bit = smoothed_3ch[:, :, 0]
        except:
            from scipy.ndimage import gaussian_filter
            smoothed_8bit = gaussian_filter(disp_8bit.astype(np.float32), sigma=1.0).astype(np.uint8)

        smoothed = smoothed_8bit.astype(np.float32) / 255.0
        smoothed = smoothed * (disparity_map.max() - disparity_map.min()) + disparity_map.min()

    elif method == 'gaussian':
        if confidence_map is not None:
            weight = confidence_map[:, :, np.newaxis] if len(confidence_map.shape) == 2 else confidence_map
            smoothed = gaussian_filter(disparity_map * confidence_map, sigma=sigma_space)
            weight_sum = gaussian_filter(confidence_map, sigma=sigma_space)
            smoothed = smoothed / (weight_sum + 1e-8)
        else:
            smoothed = gaussian_filter(disparity_map, sigma=sigma_space)

    elif method == 'median':
        smoothed = median_filter(disparity_map, size=int(sigma_space * 2) + 1)

    elif method == 'wls':
        smoothed = wls_smooth(disparity_map, confidence_map, sigma_space, 0.1)

    else:
        smoothed = disparity_map

    return smoothed


def wls_smooth(disparity, confidence=None, lambda_=0.1, alpha=1.2):
    """
    Weighted Least Squares (WLS) edge-preserving smoothing.
    
    Parameters:
        disparity: Input disparity map
        confidence: Optional confidence map
        lambda_: Regularization strength
        alpha: Edge sensitivity
        
    Returns:
        smoothed: Smoothed disparity map
    """
    h, w = disparity.shape

    try:
        grad_x = np.abs(cv2.Sobel(disparity, cv2.CV_32F, 1, 0, ksize=3))
        grad_y = np.abs(cv2.Sobel(disparity, cv2.CV_32F, 0, 1, ksize=3))
    except:
        from scipy.ndimage import sobel
        grad_x = np.abs(sobel(disparity, axis=1))
        grad_y = np.abs(sobel(disparity, axis=0))
    grad_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)

    weights_x = 1.0 / (grad_x ** alpha + lambda_)
    weights_y = 1.0 / (grad_y ** alpha + lambda_)

    if confidence is not None:
        conf = confidence
    else:
        conf = np.ones_like(disparity)

    smoothed = disparity.copy()

    for _ in range(5):
        new_smooth = smoothed.copy()

        for y in range(h):
            for x in range(w):
                if x > 0:
                    wx = weights_x[y, x - 1]
                    new_smooth[y, x] += wx * smoothed[y, x - 1]
                    conf[y, x] += wx
                if x < w - 1:
                    wx = weights_x[y, x]
                    new_smooth[y, x] += wx * smoothed[y, x + 1]
                    conf[y, x] += wx
                if y > 0:
                    wy = weights_y[y - 1, x]
                    new_smooth[y, x] += wy * smoothed[y - 1, x]
                    conf[y, x] += wy
                if y < h - 1:
                    wy = weights_y[y, x]
                    new_smooth[y, x] += wy * smoothed[y + 1, x]
                    conf[y, x] += wy

        smoothed = new_smooth / (conf + 1e-8)

    return smoothed


def fuse_disparity_maps(disparity_maps, confidence_maps=None, method='weighted_mean'):
    """
    Fuse multiple disparity maps from different algorithms.
    
    Parameters:
        disparity_maps: List of disparity maps
        confidence_maps: Optional list of confidence maps
        method: Fusion method
            'mean': Simple average
            'weighted_mean': Weighted by confidence
            'median': Median fusion
            'select_best': Select pixel-wise best based on confidence
            
    Returns:
        fused_map: Fused disparity map
        fused_confidence: Fused confidence map
    """
    if len(disparity_maps) == 0:
        raise ValueError("No disparity maps to fuse")

    h, w = disparity_maps[0].shape
    num_maps = len(disparity_maps)

    stacked = np.stack(disparity_maps, axis=0)

    if method == 'mean':
        fused = np.mean(stacked, axis=0)
        fused_conf = np.ones((h, w), dtype=np.float32) / num_maps

    elif method == 'median':
        fused = np.median(stacked, axis=0)
        fused_conf = np.ones((h, w), dtype=np.float32) / num_maps

    elif method == 'weighted_mean' and confidence_maps is not None:
        conf_stack = np.stack(confidence_maps, axis=0)
        conf_sum = np.sum(conf_stack, axis=0) + 1e-8
        fused = np.sum(stacked * conf_stack, axis=0) / conf_sum
        fused_conf = np.max(conf_stack, axis=0)

    elif method == 'select_best' and confidence_maps is not None:
        conf_stack = np.stack(confidence_maps, axis=0)
        best_idx = np.argmax(conf_stack, axis=0)

        fused = np.zeros((h, w), dtype=np.float32)
        for y in range(h):
            for x in range(w):
                fused[y, x] = stacked[best_idx[y, x], y, x]

        fused_conf = np.max(conf_stack, axis=0)

    else:
        fused = np.mean(stacked, axis=0)
        fused_conf = np.ones((h, w), dtype=np.float32) / num_maps

    return fused, fused_conf


def remove_outliers(disparity_map, confidence_map=None, threshold=3.0):
    """
    Remove outliers from disparity map.
    
    Parameters:
        disparity_map: Input disparity map
        confidence_map: Optional confidence map
        threshold: Outlier threshold in standard deviations
        
    Returns:
        cleaned_map: Disparity map with outliers removed
        outlier_mask: Boolean mask of removed outliers
    """
    h, w = disparity_map.shape

    median = np.median(disparity_map)
    mad = np.median(np.abs(disparity_map - median))
    std = 1.4826 * mad

    z_scores = np.abs(disparity_map - median) / (std + 1e-8)
    outlier_mask = z_scores > threshold

    local_median = median_filter(disparity_map, size=5)
    cleaned_map = disparity_map.copy()
    cleaned_map[outlier_mask] = local_median[outlier_mask]

    if confidence_map is not None:
        outlier_mask |= confidence_map < 0.2

    return cleaned_map, outlier_mask


def postprocess_pipeline(disparity_map, confidence_map=None, occlusion_mask=None, subapertures=None, occlusion_fill_method='ordered_inpaint'):
    """
    Complete post-processing pipeline.
    
    Parameters:
        disparity_map: Raw disparity map
        confidence_map: Optional initial confidence map
        occlusion_mask: Optional initial occlusion mask
        subapertures: Optional SubApertureArray object
        occlusion_fill_method: Method for occlusion filling:
                              'ordered_inpaint', 'anisotropic', 'layered_bilateral',
                              'region_growing', 'telea', 'none'
        
    Returns:
        processed_disparity: Final processed disparity map
        confidence: Final confidence map
        occlusion: Final occlusion mask
    """
    if confidence_map is None:
        confidence = compute_confidence_map(disparity_map, subapertures, method='variance')
    else:
        confidence = confidence_map

    if occlusion_mask is None:
        occlusion = detect_occlusions(disparity_map, subapertures, method='combination')
    else:
        occlusion = occlusion_mask

    cleaned, outlier_mask = remove_outliers(disparity_map, confidence)

    combined_occlusion = occlusion | outlier_mask

    if occlusion_fill_method and occlusion_fill_method != 'none':
        filled = fill_occlusions(cleaned, combined_occlusion, method=occlusion_fill_method)
    else:
        filled = cleaned
        combined_occlusion = np.zeros_like(combined_occlusion, dtype=bool)

    smoothed = smooth_disparity(filled, confidence, method='bilateral')

    return smoothed, confidence, combined_occlusion
