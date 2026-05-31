"""
Motion estimation module for sea ice drift.

Provides multiple algorithms:
- Cross-correlation (template matching)
- Horn-Schunck optical flow
- Lucas-Kanade optical flow
- Farneback optical flow
- FlowNet deep learning
"""

import numpy as np
import cv2
from scipy.signal import correlate2d
from scipy.ndimage import convolve, gaussian_filter
from skimage.registration import phase_cross_correlation


TORCH_AVAILABLE = False
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    pass


class MotionField:
    """
    Container for motion vector field.
    
    Attributes:
        u: x-component of displacement (pixels or meters)
        v: y-component of displacement (pixels or meters)
        correlation: correlation coefficient map
        time_diff: time difference between frames (seconds)
        resolution: grid resolution (meters per pixel)
    """
    
    def __init__(self, u, v, correlation=None, time_diff=1.0, resolution=1.0):
        self.u = np.asarray(u, dtype=np.float64)
        self.v = np.asarray(v, dtype=np.float64)
        self.correlation = np.asarray(correlation) if correlation is not None else None
        self.time_diff = time_diff
        self.resolution = resolution
        
        if self.correlation is None:
            self.correlation = np.ones_like(self.u)
        
    @property
    def speed(self):
        """Calculate speed (magnitude of velocity)."""
        return np.sqrt(self.u**2 + self.v**2)
    
    @property
    def direction(self):
        """Calculate direction (angle from x-axis, radians)."""
        return np.arctan2(self.v, self.u)
    
    @property
    def velocity_u(self):
        """Velocity in x-direction (meters per second)."""
        return self.u * self.resolution / self.time_diff
    
    @property
    def velocity_v(self):
        """Velocity in y-direction (meters per second)."""
        return self.v * self.resolution / self.time_diff
    
    def __repr__(self):
        return (f'MotionField(shape={self.u.shape}, '
                f'mean_speed={np.nanmean(self.speed):.2f} px)')


def cross_correlation_motion(img1, img2, window_size=32, search_range=16,
                             step=4, method='normalized'):
    """
    Estimate motion using cross-correlation template matching.
    
    Parameters
    ----------
    img1 : 2D array
        First image (reference)
    img2 : 2D array
        Second image (target)
    window_size : int
        Size of the template window
    search_range : int
        Maximum search distance in pixels
    step : int
        Step size between windows
    method : str
        'normalized' (NCC), 'phase' (phase correlation), or 'ssd'
        
    Returns
    -------
    MotionField
        Estimated motion field
    """
    img1 = np.asarray(img1, dtype=np.float64)
    img2 = np.asarray(img2, dtype=np.float64)
    
    rows, cols = img1.shape
    
    out_rows = max(1, (rows - window_size) // step + 1)
    out_cols = max(1, (cols - window_size) // step + 1)
    
    u = np.zeros((out_rows, out_cols))
    v = np.zeros((out_rows, out_cols))
    correlation = np.zeros((out_rows, out_cols))
    
    half_w = window_size // 2
    
    for i in range(out_rows):
        for j in range(out_cols):
            y = i * step + half_w
            x = j * step + half_w
            
            y_min = max(0, y - half_w)
            y_max = min(rows, y + half_w + 1)
            x_min = max(0, x - half_w)
            x_max = min(cols, x + half_w + 1)
            
            template = img1[y_min:y_max, x_min:x_max]
            
            if template.size < window_size * window_size // 2:
                u[i, j] = np.nan
                v[i, j] = np.nan
                correlation[i, j] = 0
                continue
            
            sy_min = max(0, y - search_range - half_w)
            sy_max = min(rows, y + search_range + half_w + 1)
            sx_min = max(0, x - search_range - half_w)
            sx_max = min(cols, x + search_range + half_w + 1)
            
            search_region = img2[sy_min:sy_max, sx_min:sx_max]
            
            if method == 'normalized':
                dx, dy, corr = _ncc_match(template, search_region)
            elif method == 'phase':
                dx, dy, corr = _phase_correlation_match(template, search_region)
            elif method == 'ssd':
                dx, dy, corr = _ssd_match(template, search_region)
            else:
                raise ValueError(f'Unknown correlation method: {method}')
            
            orig_dy = y - (sy_min + half_w)
            orig_dx = x - (sx_min + half_w)
            
            v[i, j] = dy - orig_dy
            u[i, j] = dx - orig_dx
            correlation[i, j] = corr
    
    u_full = np.zeros((rows, cols))
    v_full = np.zeros((rows, cols))
    corr_full = np.zeros((rows, cols))
    
    for i in range(out_rows):
        for j in range(out_cols):
            y = i * step
            x = j * step
            y_end = min(y + step, rows)
            x_end = min(x + step, cols)
            u_full[y:y_end, x:x_end] = u[i, j]
            v_full[y:y_end, x:x_end] = v[i, j]
            corr_full[y:y_end, x:x_end] = correlation[i, j]
    
    return MotionField(u_full, v_full, corr_full)


def _ncc_match(template, search_region):
    """Normalized cross-correlation matching."""
    template = template - np.mean(template)
    search_region = search_region - np.mean(search_region)
    
    if np.std(template) == 0 or np.std(search_region) == 0:
        return search_region.shape[1] // 2, search_region.shape[0] // 2, 0
    
    corr = correlate2d(search_region, template, mode='valid')
    
    norm = np.sqrt((template**2).sum() * 
                   np.array([[np.sum(search_region[i:i+template.shape[0], 
                                            j:j+template.shape[1]]**2)
                              for j in range(search_region.shape[1] - template.shape[1] + 1)]
                             for i in range(search_region.shape[0] - template.shape[0] + 1)]))
    
    norm[norm == 0] = 1
    ncc = corr / norm
    
    max_pos = np.unravel_index(np.argmax(ncc), ncc.shape)
    dy, dx = max_pos
    
    return dx + template.shape[1] // 2, dy + template.shape[0] // 2, ncc[dy, dx]


def _phase_correlation_match(template, search_region):
    """Phase correlation matching."""
    try:
        shift, error, diffphase = phase_cross_correlation(
            template, search_region, upsample_factor=10
        )
        dy, dx = shift
        corr = 1.0 - error
    except:
        h, w = search_region.shape
        th, tw = template.shape
        dy = (h - th) // 2
        dx = (w - tw) // 2
        corr = 0
    
    return dx + tw // 2, dy + th // 2, corr


def _ssd_match(template, search_region):
    """Sum of squared differences matching."""
    th, tw = template.shape
    sh, sw = search_region.shape
    
    if th > sh or tw > sw:
        return sw // 2, sh // 2, 0
    
    ssd = np.zeros((sh - th + 1, sw - tw + 1))
    
    for i in range(sh - th + 1):
        for j in range(sw - tw + 1):
            diff = search_region[i:i+th, j:j+tw] - template
            ssd[i, j] = np.sum(diff**2)
    
    if np.max(ssd) == 0:
        return tw // 2, th // 2, 1
    
    corr = 1.0 - ssd / np.max(ssd)
    min_pos = np.unravel_index(np.argmin(ssd), ssd.shape)
    dy, dx = min_pos
    
    return dx + tw // 2, dy + th // 2, corr[dy, dx]


def horn_schunck(img1, img2, alpha=1.0, iterations=100,
                 omega=1.0, eps=1e-5):
    """
    Horn-Schunck optical flow estimation.
    
    Parameters
    ----------
    img1 : 2D array
        First image
    img2 : 2D array
        Second image
    alpha : float
        Regularization parameter (smoothness)
    iterations : int
        Maximum number of iterations
    omega : float
        Relaxation parameter for SOR
    eps : float
        Convergence threshold
        
    Returns
    -------
    MotionField
        Estimated motion field
    """
    img1 = np.asarray(img1, dtype=np.float64)
    img2 = np.asarray(img2, dtype=np.float64)
    
    valid_mask = ~(np.isnan(img1) | np.isnan(img2))
    if np.any(~valid_mask):
        from .preprocess import _fill_nans
        img1_filled = _fill_nans(img1)
        img2_filled = _fill_nans(img2)
    else:
        img1_filled = img1
        img2_filled = img2
    
    fx = np.array([[-1, 1], [-1, 1]]) * 0.25
    fy = np.array([[-1, -1], [1, 1]]) * 0.25
    ft = np.ones((2, 2)) * 0.25
    
    Ix = convolve(img1_filled, fx) + convolve(img2_filled, fx)
    Iy = convolve(img1_filled, fy) + convolve(img2_filled, fy)
    It = convolve(img2_filled, ft) - convolve(img1_filled, ft)
    
    u = np.zeros_like(img1_filled)
    v = np.zeros_like(img1_filled)
    
    avg_kernel = np.array([[0, 1/4, 0],
                           [1/4, 0, 1/4],
                           [0, 1/4, 0]])
    
    for it in range(iterations):
        u_avg = convolve(u, avg_kernel)
        v_avg = convolve(v, avg_kernel)
        
        denominator = alpha**2 + Ix**2 + Iy**2
        numerator = Ix * u_avg + Iy * v_avg + It
        
        u_new = u_avg - Ix * numerator / denominator
        v_new = v_avg - Iy * numerator / denominator
        
        u_new = omega * u_new + (1 - omega) * u
        v_new = omega * v_new + (1 - omega) * v
        
        diff_u = np.mean(np.abs(u_new - u))
        diff_v = np.mean(np.abs(v_new - v))
        u, v = u_new, v_new
        
        if diff_u < eps and diff_v < eps:
            print(f'Horn-Schunck converged after {it+1} iterations')
            break
    
    correlation = _compute_correlation_map(img1_filled, img2_filled, u, v)
    
    u[~valid_mask] = np.nan
    v[~valid_mask] = np.nan
    correlation[~valid_mask] = np.nan
    
    return MotionField(u, v, correlation)


def lucas_kanade(img1, img2, window_size=15, max_levels=3):
    """
    Lucas-Kanade optical flow using pyramidal implementation.
    
    Parameters
    ----------
    img1 : 2D array
        First image
    img2 : 2D array
        Second image
    window_size : int
        Size of integration window (odd)
    max_levels : int
        Number of pyramid levels
        
    Returns
    -------
    MotionField
        Estimated motion field
    """
    img1 = np.asarray(img1, dtype=np.float64)
    img2 = np.asarray(img2, dtype=np.float64)
    
    valid_mask = ~(np.isnan(img1) | np.isnan(img2))
    if np.any(~valid_mask):
        from .preprocess import _fill_nans
        img1_filled = _fill_nans(img1)
        img2_filled = _fill_nans(img2)
    else:
        img1_filled = img1
        img2_filled = img2
    
    img1_norm = cv2.normalize(img1_filled, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    img2_norm = cv2.normalize(img2_filled, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    
    p1 = []
    for y in range(0, img1.shape[0], 2):
        for x in range(0, img1.shape[1], 2):
            p1.append([[x, y]])
    p1 = np.array(p1, dtype=np.float32)
    
    lk_params = dict(
        winSize=(window_size, window_size),
        maxLevel=max_levels,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
    )
    
    p2, st, err = cv2.calcOpticalFlowPyrLK(img1_norm, img2_norm, p1, None, **lk_params)
    
    u = np.zeros(img1.shape, dtype=np.float64)
    v = np.zeros(img1.shape, dtype=np.float64)
    correlation = np.zeros(img1.shape, dtype=np.float64)
    
    u_counts = np.zeros(img1.shape, dtype=np.int32)
    v_counts = np.zeros(img1.shape, dtype=np.int32)
    
    for i, (old_pt, new_pt, status) in enumerate(zip(p1, p2, st)):
        if status[0] == 1:
            x_old, y_old = old_pt[0]
            x_new, y_new = new_pt[0]
            
            dx = x_new - x_old
            dy = y_new - y_old
            
            xi, yi = int(x_old), int(y_old)
            if 0 <= yi < img1.shape[0] and 0 <= xi < img1.shape[1]:
                u[yi, xi] += dx
                v[yi, xi] += dy
                u_counts[yi, xi] += 1
                v_counts[yi, xi] += 1
                
                corr = max(0, 1.0 - err[i, 0] / 100.0) if err[i, 0] < 100 else 0
                correlation[yi, xi] += corr
    
    valid_u = u_counts > 0
    valid_v = v_counts > 0
    u[valid_u] /= u_counts[valid_u]
    v[valid_v] /= v_counts[valid_v]
    
    from scipy.interpolate import griddata
    
    points_u = np.argwhere(u_counts > 0)
    values_u = u[points_u[:, 0], points_u[:, 1]]
    values_v = v[points_u[:, 0], points_u[:, 1]]
    values_corr = correlation[points_u[:, 0], points_u[:, 1]]
    
    if len(points_u) > 10:
        grid_y, grid_x = np.mgrid[0:img1.shape[0], 0:img1.shape[1]]
        grid_points = np.column_stack([grid_x.ravel(), grid_y.ravel()])
        
        u_full = griddata(points_u[:, ::-1], values_u, grid_points, method='linear')
        v_full = griddata(points_u[:, ::-1], values_v, grid_points, method='linear')
        corr_full = griddata(points_u[:, ::-1], values_corr, grid_points, method='linear')
        
        u = u_full.reshape(img1.shape)
        v = v_full.reshape(img1.shape)
        correlation = corr_full.reshape(img1.shape)
        
        u = np.where(np.isnan(u), 0, u)
        v = np.where(np.isnan(v), 0, v)
        correlation = np.where(np.isnan(correlation), 0, correlation)
    
    u_smooth = gaussian_filter(u, sigma=1.0)
    v_smooth = gaussian_filter(v, sigma=1.0)
    corr_smooth = gaussian_filter(correlation, sigma=1.0)
    
    u_smooth[~valid_mask] = np.nan
    v_smooth[~valid_mask] = np.nan
    corr_smooth[~valid_mask] = np.nan
    
    return MotionField(u_smooth, v_smooth, corr_smooth)


def farneback_optical_flow(img1, img2, pyr_scale=0.5, levels=3,
                           winsize=15, iterations=3, poly_n=5,
                           poly_sigma=1.2):
    """
    Farneback dense optical flow (OpenCV implementation).
    
    Parameters
    ----------
    img1, img2 : 2D array
        Input images
    pyr_scale : float
        Image scale between pyramid levels
    levels : int
        Number of pyramid levels
    winsize : int
        Averaging window size
    iterations : int
        Iterations per level
    poly_n : int
        Size of pixel neighborhood for polynomial expansion
    poly_sigma : float
        Standard deviation of Gaussian for polynomial expansion
        
    Returns
    -------
    MotionField
        Estimated motion field
    """
    img1 = np.asarray(img1, dtype=np.float64)
    img2 = np.asarray(img2, dtype=np.float64)
    
    valid_mask = ~(np.isnan(img1) | np.isnan(img2))
    if np.any(~valid_mask):
        from .preprocess import _fill_nans
        img1_filled = _fill_nans(img1)
        img2_filled = _fill_nans(img2)
    else:
        img1_filled = img1
        img2_filled = img2
    
    img1_norm = cv2.normalize(img1_filled, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    img2_norm = cv2.normalize(img2_filled, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    
    flow = cv2.calcOpticalFlowFarneback(
        img1_norm, img2_norm, None,
        pyr_scale, levels, winsize, iterations, poly_n, poly_sigma,
        cv2.OPTFLOW_FARNEBACK_GAUSSIAN
    )
    
    u = flow[..., 0]
    v = flow[..., 1]
    
    correlation = _compute_correlation_map(img1_filled, img2_filled, u, v)
    
    u[~valid_mask] = np.nan
    v[~valid_mask] = np.nan
    correlation[~valid_mask] = np.nan
    
    return MotionField(u, v, correlation)


def _compute_correlation_map(img1, img2, u, v):
    """Compute local correlation map for motion field quality."""
    rows, cols = img1.shape
    correlation = np.zeros((rows, cols))
    
    half_win = 4
    
    for y in range(half_win, rows - half_win):
        for x in range(half_win, cols - half_win):
            dx = int(round(u[y, x]))
            dy = int(round(v[y, x]))
            
            y1_min = y - half_win
            y1_max = y + half_win + 1
            x1_min = x - half_win
            x1_max = x + half_win + 1
            
            y2_min = max(0, y + dy - half_win)
            y2_max = min(rows, y + dy + half_win + 1)
            x2_min = max(0, x + dx - half_win)
            x2_max = min(cols, x + dx + half_win + 1)
            
            patch1 = img1[y1_min:y1_max, x1_min:x1_max]
            patch2 = img2[y2_min:y2_max, x2_min:x2_max]
            
            if patch1.shape == patch2.shape and patch1.size > 0:
                std1 = np.std(patch1)
                std2 = np.std(patch2)
                if std1 > 1e-6 and std2 > 1e-6:
                    corr = np.corrcoef(patch1.ravel(), patch2.ravel())[0, 1]
                    correlation[y, x] = np.clip(corr, -1, 1)
                else:
                    correlation[y, x] = 0
            else:
                correlation[y, x] = 0
    
    return correlation


def estimate_motion(img1, img2, method='horn_schunck', **kwargs):
    """
    Estimate motion between two images using specified method.
    
    Parameters
    ----------
    img1, img2 : 2D array
        Input images (img1 is reference, img2 is target)
    method : str
        'cross_correlation', 'horn_schunck', 'lucas_kanade', 'farneback'
    **kwargs
        Additional parameters for the method
        
    Returns
    -------
    MotionField
        Estimated motion field
    """
    if method == 'cross_correlation':
        return cross_correlation_motion(img1, img2, **kwargs)
    elif method == 'horn_schunck':
        return horn_schunck(img1, img2, **kwargs)
    elif method == 'lucas_kanade':
        return lucas_kanade(img1, img2, **kwargs)
    elif method == 'farneback':
        return farneback_optical_flow(img1, img2, **kwargs)
    elif method == 'flow_net':
        from .deep_learning import estimate_flow_net
        return estimate_flow_net(img1, img2, **kwargs)
    else:
        raise ValueError(f'Unknown motion estimation method: {method}')


def estimate_motion_sequence(preprocessed_images, method='horn_schunck',
                             do_multires_align=True, target_resolution=12.5,
                             upsample_method='bicubic',
                             do_subpixel_refine=True,
                             **kwargs):
    """
    Estimate motion for a sequence of preprocessed images.
    
    Includes multi-resolution alignment for images from different sensors
    (e.g., 25km SSM/I and 12.5km AMSR-E) and subpixel refinement.
    
    Parameters
    ----------
    preprocessed_images : list
        List of preprocessed image dicts
    method : str
        Motion estimation method
    do_multires_align : bool
        Whether to align images from different resolutions
    target_resolution : float
        Target resolution for alignment in km
    upsample_method : str
        Method for upsampling low-res images
    do_subpixel_refine : bool
        Whether to apply subpixel refinement
    **kwargs
        Additional parameters for motion estimation
        
    Returns
    -------
    list
        List of MotionField objects
    """
    from .preprocess import (
        detect_resolution, 
        align_multiresolution_images,
        subpixel_refine_correlation
    )
    
    motion_fields = []
    
    for i in range(len(preprocessed_images) - 1):
        img1 = preprocessed_images[i]['data']
        img2 = preprocessed_images[i + 1]['data']
        
        t1 = preprocessed_images[i]['timestamp']
        t2 = preprocessed_images[i + 1]['timestamp']
        time_diff = (t2 - t1).total_seconds()
        
        resolution = preprocessed_images[i].get('resolution', 12.5) * 1000
        
        res1 = preprocessed_images[i].get('original_resolution')
        res2 = preprocessed_images[i + 1].get('original_resolution')
        
        if res1 is None:
            res1 = detect_resolution(
                preprocessed_images[i]['lats'],
                preprocessed_images[i]['lons']
            )
        if res2 is None:
            res2 = detect_resolution(
                preprocessed_images[i + 1]['lats'],
                preprocessed_images[i + 1]['lons']
            )
        
        if do_multires_align and res1['resolution_km'] != res2['resolution_km']:
            print(f'  Aligning multi-resolution images: '
                  f'{res1["resolution_km"]:.1f}km -> {res2["resolution_km"]:.1f}km')
            
            img1_aligned, img2_aligned, scale1, scale2 = align_multiresolution_images(
                img1, img2, res1, res2,
                target_resolution=target_resolution,
                upsample_method=upsample_method
            )
            
            if img1_aligned.shape != img2_aligned.shape:
                from skimage.transform import resize
                img2_aligned = resize(img2_aligned, img1_aligned.shape,
                                     order=3, mode='reflect', anti_aliasing=False)
                img1_aligned = resize(img1_aligned, img1_aligned.shape,
                                     order=3, mode='reflect', anti_aliasing=False)
            
            img1_proc = img1_aligned
            img2_proc = img2_aligned
            
            scale_factor = min(scale1, scale2)
        else:
            img1_proc = img1
            img2_proc = img2
            scale_factor = 1.0
        
        print(f'Estimating motion between frame {i} and {i+1} ({method})...')
        motion = estimate_motion(img1_proc, img2_proc, method=method, **kwargs)
        
        if do_subpixel_refine and method == 'cross_correlation':
            print('  Applying subpixel refinement...')
            motion = _apply_subpixel_refinement(motion, img1_proc, img2_proc)
        
        motion.u = motion.u / scale_factor
        motion.v = motion.v / scale_factor
        motion.time_diff = time_diff
        motion.resolution = resolution
        
        motion_fields.append(motion)
    
    return motion_fields


def _apply_subpixel_refinement(motion_field, img1, img2, window_size=7):
    """
    Apply subpixel refinement to motion vectors using quadratic fitting.
    
    Parameters
    ----------
    motion_field : MotionField
        Initial motion field
    img1, img2 : 2D array
        Original images
    window_size : int
        Window size for local correlation
        
    Returns
    -------
    MotionField
        Refined motion field
    """
    from .preprocess import subpixel_refine_correlation
    
    rows, cols = motion_field.u.shape
    u_refined = motion_field.u.copy()
    v_refined = motion_field.v.copy()
    corr_refined = motion_field.correlation.copy()
    
    half_w = window_size // 2
    
    for y in range(half_w, rows - half_w, 2):
        for x in range(half_w, cols - half_w, 2):
            if np.isnan(motion_field.u[y, x]) or np.isnan(motion_field.v[y, x]):
                continue
            
            dx = int(round(motion_field.u[y, x]))
            dy = int(round(motion_field.v[y, x]))
            
            y1_min = y - half_w
            y1_max = y + half_w + 1
            x1_min = x - half_w
            x1_max = x + half_w + 1
            
            y2_min = max(0, y + dy - half_w)
            y2_max = min(rows, y + dy + half_w + 1)
            x2_min = max(0, x + dx - half_w)
            x2_max = min(cols, x + dx + half_w + 1)
            
            patch1 = img1[y1_min:y1_max, x1_min:x1_max]
            patch2 = img2[y2_min:y2_max, x2_min:x2_max]
            
            if patch1.shape != patch2.shape or patch1.size == 0:
                continue
            
            from scipy.signal import correlate2d
            try:
                corr_map = correlate2d(patch2, patch1 - np.mean(patch1), mode='valid')
                if corr_map.size > 0:
                    subpy, subpx, corr_val = subpixel_refine_correlation(corr_map)
                    
                    center_y = corr_map.shape[0] // 2
                    center_x = corr_map.shape[1] // 2
                    
                    u_refined[y, x] = dx + (subpx - center_x)
                    v_refined[y, x] = dy + (subpy - center_y)
                    corr_refined[y, x] = corr_val
            except:
                continue
    
    from scipy.ndimage import gaussian_filter
    u_refined = gaussian_filter(u_refined, sigma=1.0)
    v_refined = gaussian_filter(v_refined, sigma=1.0)
    
    nan_mask = np.isnan(motion_field.u)
    u_refined[nan_mask] = np.nan
    v_refined[nan_mask] = np.nan
    
    from .motion import MotionField
    return MotionField(
        u_refined, v_refined, corr_refined,
        time_diff=motion_field.time_diff,
        resolution=motion_field.resolution
    )
