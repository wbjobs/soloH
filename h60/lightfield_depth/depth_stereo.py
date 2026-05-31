"""
Stereo Matching for Light Field Depth Estimation

Implements sub-pixel accurate disparity estimation using multi-view stereo.
Methods include:
- Sum of Absolute Differences (SAD)
- Sum of Squared Differences (SSD)
- Normalized Cross-Correlation (NCC)
- Census Transform
- Sub-pixel refinement using quadratic fitting
"""

import numpy as np
import cv2
from tqdm import tqdm
from scipy.ndimage import gaussian_filter, median_filter


def compute_cost_volume(img_left, img_right, min_disp, max_disp, window_size=7, cost_type='sad'):
    """
    Compute cost volume for stereo matching.
    
    Parameters:
        img_left: Left image (H, W) grayscale
        img_right: Right image (H, W) grayscale
        min_disp: Minimum disparity
        max_disp: Maximum disparity
        window_size: Matching window size
        cost_type: 'sad', 'ssd', 'ncc', 'census'
        
    Returns:
        cost_volume: [num_disp, H, W] cost volume
    """
    h, w = img_left.shape
    num_disp = max_disp - min_disp

    img_left = img_left.astype(np.float32)
    img_right = img_right.astype(np.float32)

    cost_volume = np.zeros((num_disp, h, w), dtype=np.float32)

    half_w = window_size // 2

    if cost_type == 'census':
        census_left = compute_census_transform(img_left, window_size)
        census_right = compute_census_transform(img_right, window_size)

    for d_idx in range(num_disp):
        disp = min_disp + d_idx

        if disp >= 0:
            shifted_right = np.zeros_like(img_right)
            shifted_right[:, disp:] = img_right[:, :-disp] if disp > 0 else img_right

            if cost_type == 'census':
                shifted_census = np.zeros_like(census_right)
                shifted_census[:, disp:] = census_right[:, :-disp] if disp > 0 else census_right
                cost = compute_hamming_distance(census_left, shifted_census)
            else:
                cost = compute_matching_cost(img_left, shifted_right, window_size, cost_type)
        else:
            disp_abs = abs(disp)
            shifted_right = np.zeros_like(img_right)
            shifted_right[:, :-disp_abs] = img_right[:, disp_abs:]

            if cost_type == 'census':
                shifted_census = np.zeros_like(census_right)
                shifted_census[:, :-disp_abs] = census_right[:, disp_abs:]
                cost = compute_hamming_distance(census_left, shifted_census)
            else:
                cost = compute_matching_cost(img_left, shifted_right, window_size, cost_type)

        cost_volume[d_idx] = cost

    return cost_volume


def compute_matching_cost(img1, img2, window_size=7, cost_type='sad'):
    """
    Compute pixel-wise matching cost between two images.
    
    Parameters:
        img1: First image
        img2: Second image
        window_size: Window size for aggregation
        cost_type: 'sad', 'ssd', 'ncc'
        
    Returns:
        cost_map: Cost map (lower is better)
    """
    h, w = img1.shape
    half_w = window_size // 2

    if cost_type == 'sad':
        diff = np.abs(img1 - img2)
        from scipy.ndimage import uniform_filter
        cost = uniform_filter(diff, size=window_size) * (window_size * window_size)

    elif cost_type == 'ssd':
        diff = (img1 - img2) ** 2
        from scipy.ndimage import uniform_filter
        cost = uniform_filter(diff, size=window_size) * (window_size * window_size)

    elif cost_type == 'ncc':
        from scipy.ndimage import uniform_filter
        mean1 = uniform_filter(img1, size=window_size)
        mean2 = uniform_filter(img2, size=window_size)

        diff1 = img1 - mean1
        diff2 = img2 - mean2

        numerator = uniform_filter(diff1 * diff2, size=window_size)
        denom1 = uniform_filter(diff1 ** 2, size=window_size)
        denom2 = uniform_filter(diff2 ** 2, size=window_size)

        denom = np.sqrt(np.maximum(denom1 * denom2, 1e-10))
        ncc = numerator / denom
        cost = 1 - ncc

    else:
        raise ValueError(f"Unknown cost type: {cost_type}")

    return cost


def compute_census_transform(img, window_size=7):
    """
    Compute Census Transform of an image.
    
    Parameters:
        img: Input grayscale image
        window_size: Census window size
        
    Returns:
        census: Census transformed image (each pixel is a bit string)
    """
    h, w = img.shape
    half_w = window_size // 2

    census = np.zeros((h, w), dtype=np.int64)

    center_val = img[half_w:h - half_w, half_w:w - half_w]

    bit_idx = 0
    for dy in range(window_size):
        for dx in range(window_size):
            if dy == half_w and dx == half_w:
                continue

            neighbor = img[dy:dy + h - 2 * half_w, dx:dx + w - 2 * half_w]
            mask = (neighbor <= center_val).astype(np.int64)
            census[half_w:h - half_w, half_w:w - half_w] |= (mask << bit_idx)
            bit_idx += 1

    return census


def compute_hamming_distance(census1, census2):
    """
    Compute Hamming distance between two census images.
    
    Parameters:
        census1: First census image
        census2: Second census image
        
    Returns:
        hamming: Hamming distance map
    """
    xor = np.bitwise_xor(census1.astype(np.int64), census2.astype(np.int64))

    hamming = np.zeros_like(xor, dtype=np.float32)
    while np.any(xor != 0):
        hamming += np.bitwise_and(xor, 1).astype(np.float32)
        xor = np.right_shift(xor, 1)

    return hamming


def winner_takes_all(cost_volume):
    """
    Winner-Takes-All (WTA) disparity selection.
    
    Parameters:
        cost_volume: [num_disp, H, W] cost volume (lower is better)
        
    Returns:
        disp_idx: Disparity index map
    """
    return np.argmin(cost_volume, axis=0)


def subpixel_refinement(cost_volume, disp_idx, min_disp):
    """
    Sub-pixel disparity refinement using quadratic fitting.
    
    Fits a quadratic curve to the three costs around the minimum
    to find the sub-pixel accurate disparity.
    
    Parameters:
        cost_volume: [num_disp, H, W] cost volume
        disp_idx: [H, W] integer disparity indices from WTA
        min_disp: Minimum disparity
        
    Returns:
        disp_subpixel: [H, W] sub-pixel accurate disparity map
    """
    num_disp, h, w = cost_volume.shape

    disp_subpixel = np.zeros((h, w), dtype=np.float32)

    disp_idx_int = disp_idx.astype(int)

    valid = (disp_idx_int > 0) & (disp_idx_int < num_disp - 1)

    d0 = disp_idx_int[valid]
    c0 = cost_volume[d0, valid]
    c_neg = cost_volume[d0 - 1, valid]
    c_pos = cost_volume[d0 + 1, valid]

    denom = 2 * (c_neg + c_pos - 2 * c0)

    subpix_offset = np.zeros_like(d0, dtype=np.float32)
    valid_denom = np.abs(denom) > 1e-8
    subpix_offset[valid_denom] = (c_neg[valid_denom] - c_pos[valid_denom]) / denom[valid_denom]

    disp_subpixel[valid] = min_disp + d0 + subpix_offset

    edge_left = disp_idx_int == 0
    disp_subpixel[edge_left] = min_disp

    edge_right = disp_idx_int == num_disp - 1
    disp_subpixel[edge_right] = min_disp + num_disp - 1

    return disp_subpixel


def left_right_consistency_check(disp_left, disp_right, max_diff=1.0):
    """
    Left-Right Consistency (LRC) check for occlusion detection.
    
    Parameters:
        disp_left: Disparity map from left view
        disp_right: Disparity map from right view
        max_diff: Maximum allowed difference for consistency
        
    Returns:
        valid_mask: Boolean mask of valid pixels
        occlusion_mask: Boolean mask of occluded pixels
    """
    h, w = disp_left.shape

    h_range = np.arange(h)[:, np.newaxis]
    w_range = np.arange(w)[np.newaxis, :]

    w_matched = (w_range - disp_left).astype(int)

    valid_w = (w_matched >= 0) & (w_matched < w)

    disp_reprojected = np.zeros_like(disp_left)
    for y in range(h):
        for x in range(w):
            if valid_w[y, x]:
                wm = w_matched[y, x]
                disp_reprojected[y, x] = disp_right[y, wm]

    diff = np.abs(disp_left - disp_reprojected)
    valid_mask = (diff <= max_diff) & valid_w
    occlusion_mask = ~valid_mask

    return valid_mask, occlusion_mask


def estimate_depth_stereo(subapertures, min_disp=-8, max_disp=8, 
                          window_size=7, cost_type='sad', 
                          use_subpixel=True, use_lrc=True):
    """
    Depth estimation using multi-view stereo matching.
    
    Uses multiple view pairs from the sub-aperture array and fuses
    the results for robust disparity estimation.
    
    Parameters:
        subapertures: SubApertureArray object
        min_disp: Minimum disparity
        max_disp: Maximum disparity
        window_size: Matching window size
        cost_type: Cost function ('sad', 'ssd', 'ncc', 'census')
        use_subpixel: Enable sub-pixel refinement
        use_lrc: Enable left-right consistency check
        
    Returns:
        disparity_map: Final disparity map
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

    img_center = imgs_gray[center_v, center_u]

    disp_accum = np.zeros((h, w), dtype=np.float32)
    weight_accum = np.zeros((h, w), dtype=np.float32)
    valid_mask_accum = np.zeros((h, w), dtype=bool)

    view_pairs = []

    for du in range(1, min(4, num_u - center_u)):
        u_left = center_u
        u_right = center_u + du
        view_pairs.append((center_v, u_left, center_v, u_right, du))
        u_left = center_u - du
        u_right = center_u
        view_pairs.append((center_v, u_left, center_v, u_right, du))

    for dv in range(1, min(4, num_v - center_v)):
        v_top = center_v - dv
        v_bot = center_v + dv
        view_pairs.append((v_top, center_u, v_bot, center_u, dv))

    for (v1, u1, v2, u2, baseline) in tqdm(view_pairs, desc="Stereo matching"):
        img1 = imgs_gray[v1, u1]
        img2 = imgs_gray[v2, u2]
        if img1.ndim == 3 and img1.shape[2] == 1:
            img1 = img1[:, :, 0]
            img2 = img2[:, :, 0]

        cost_vol = compute_cost_volume(img1, img2, min_disp, max_disp, window_size, cost_type)
        disp_idx = winner_takes_all(cost_vol)

        if use_subpixel:
            disp = subpixel_refinement(cost_vol, disp_idx, min_disp)
        else:
            disp = min_disp + disp_idx.astype(np.float32)

        disp = disp / baseline

        conf = compute_matching_confidence(cost_vol, disp_idx)

        if use_lrc:
            cost_vol_rl = compute_cost_volume(img2, img1, min_disp, max_disp, window_size, cost_type)
            disp_idx_rl = winner_takes_all(cost_vol_rl)
            if use_subpixel:
                disp_rl = subpixel_refinement(cost_vol_rl, disp_idx_rl, min_disp)
            else:
                disp_rl = min_disp + disp_idx_rl.astype(np.float32)
            disp_rl = disp_rl / baseline

            valid_mask, occl_mask = left_right_consistency_check(disp, disp_rl)
        else:
            valid_mask = np.ones((h, w), dtype=bool)
            occl_mask = np.zeros((h, w), dtype=bool)

        weight = conf * valid_mask.astype(np.float32)
        disp_accum += disp * weight
        weight_accum += weight
        valid_mask_accum |= valid_mask

    with np.errstate(divide='ignore', invalid='ignore'):
        disparity_map = np.where(weight_accum > 0, disp_accum / weight_accum, 0)

    confidence_map = weight_accum / (len(view_pairs) + 1e-8)
    occlusion_mask = ~valid_mask_accum

    disparity_map = median_filter(disparity_map, size=3)

    return disparity_map, confidence_map, occlusion_mask


def compute_matching_confidence(cost_volume, disp_idx):
    """
    Compute confidence map based on matching cost.
    
    Uses the ratio between the best and second-best matching cost
    as a confidence measure.
    
    Parameters:
        cost_volume: [num_disp, H, W] cost volume
        disp_idx: [H, W] best disparity indices
        
    Returns:
        confidence: [H, W] confidence values (0-1)
    """
    num_disp, h, w = cost_volume.shape

    best_cost = np.min(cost_volume, axis=0)

    second_best = np.zeros_like(best_cost)
    for y in range(h):
        for x in range(w):
            d = int(disp_idx[y, x])
            costs = list(cost_volume[:, y, x])
            costs.pop(d)
            second_best[y, x] = min(costs) if costs else best_cost[y, x]

    with np.errstate(divide='ignore', invalid='ignore'):
        confidence = np.where(best_cost > 0, 
                              np.minimum(second_best / (best_cost + 1e-8), 10), 
                              0)

    confidence = (confidence - confidence.min()) / (confidence.max() + 1e-8)

    return confidence
