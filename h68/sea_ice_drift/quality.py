"""
Quality assessment and filtering module.

Includes:
- Correlation coefficient filtering
- Missing value interpolation
- Outlier detection and removal
"""

import numpy as np
from scipy.ndimage import gaussian_filter, median_filter, binary_dilation
from scipy.interpolate import griddata, RBFInterpolator
from sklearn.ensemble import IsolationForest


def detect_melt_ponds(img1, img2, threshold_tb=270.0, threshold_delta=15.0,
                      min_area_pixels=9):
    """
    Detect melt pond areas based on brightness temperature characteristics.
    
    Melt ponds have high brightness temperature (around 273K for water) 
    and may show rapid changes unrelated to motion.
    
    Parameters
    ----------
    img1, img2 : 2D array
        Brightness temperature images at two times
    threshold_tb : float
        Minimum brightness temperature for melt pond detection (K)
    threshold_delta : float
        Maximum allowed TB change for valid ice motion (K)
    min_area_pixels : int
        Minimum area for melt pond region (pixels)
        
    Returns
    -------
    2D array (boolean)
        Mask where True indicates melt pond or spurious TB change
    """
    img1 = np.asarray(img1, dtype=np.float64)
    img2 = np.asarray(img2, dtype=np.float64)
    
    delta_tb = np.abs(img2 - img1)
    
    high_tb = (img1 > threshold_tb) | (img2 > threshold_tb)
    
    rapid_change = delta_tb > threshold_delta
    
    melt_mask = high_tb | rapid_change
    
    melt_mask = melt_mask & ~(np.isnan(img1) | np.isnan(img2))
    
    if min_area_pixels > 0:
        from scipy.ndimage import label
        labeled, num_features = label(melt_mask)
        for i in range(1, num_features + 1):
            area = np.sum(labeled == i)
            if area < min_area_pixels:
                melt_mask[labeled == i] = False
    
    melt_mask = binary_dilation(melt_mask, iterations=2)
    
    return melt_mask


def temporal_consistency_check(motion_field_current, motion_field_previous,
                              max_rotation_change=30.0, max_speed_change=0.3):
    """
    Check temporal consistency between consecutive motion estimates.
    
    Parameters
    ----------
    motion_field_current : MotionField
        Current motion field
    motion_field_previous : MotionField
        Previous motion field
    max_rotation_change : float
        Maximum allowed direction change (degrees)
    max_speed_change : float
        Maximum allowed relative speed change (fraction)
        
    Returns
    -------
    2D array (boolean)
        Mask where True indicates consistent vectors
    """
    if motion_field_previous is None:
        return np.ones_like(motion_field_current.u, dtype=bool)
    
    valid_current = ~(np.isnan(motion_field_current.u) | np.isnan(motion_field_current.v))
    valid_prev = ~(np.isnan(motion_field_previous.u) | np.isnan(motion_field_previous.v))
    valid = valid_current & valid_prev
    
    consistent = np.ones_like(motion_field_current.u, dtype=bool)
    
    if not np.any(valid):
        return consistent
    
    dir_current = motion_field_current.direction
    dir_prev = motion_field_previous.direction
    
    dir_diff = np.abs(dir_current - dir_prev)
    dir_diff = np.minimum(dir_diff, 2 * np.pi - dir_diff)
    dir_diff_deg = np.degrees(dir_diff)
    
    speed_current = motion_field_current.speed
    speed_prev = motion_field_previous.speed
    
    with np.errstate(divide='ignore', invalid='ignore'):
        speed_change = np.abs(speed_current - speed_prev) / (speed_prev + 1e-10)
    
    inconsistent = (dir_diff_deg > max_rotation_change) | (speed_change > max_speed_change)
    consistent[valid & inconsistent] = False
    
    return consistent


def filter_by_temporal_consistency(motion_fields, max_rotation_change=30.0,
                                   max_speed_change=0.3):
    """
    Filter a sequence of motion fields for temporal consistency.
    
    Parameters
    ----------
    motion_fields : list
        List of MotionField objects
    max_rotation_change : float
        Maximum allowed direction change (degrees)
    max_speed_change : float
        Maximum allowed relative speed change
        
    Returns
    -------
    list
        List of filtered MotionField objects
    """
    from .motion import MotionField
    
    filtered_fields = []
    
    for i, mf in enumerate(motion_fields):
        if i == 0:
            filtered_fields.append(mf)
            continue
        
        prev_mf = motion_fields[i-1]
        
        consistent = temporal_consistency_check(
            mf, prev_mf, max_rotation_change, max_speed_change
        )
        
        u_filtered = mf.u.copy()
        v_filtered = mf.v.copy()
        corr_filtered = mf.correlation.copy() if mf.correlation is not None else None
        
        u_filtered[~consistent] = np.nan
        v_filtered[~consistent] = np.nan
        if corr_filtered is not None:
            corr_filtered[~consistent] = np.nan
        
        filtered = MotionField(
            u_filtered, v_filtered, corr_filtered,
            time_diff=mf.time_diff,
            resolution=mf.resolution
        )
        filtered_fields.append(filtered)
        
        removed = np.sum(~consistent)
        if removed > 0:
            print(f'  Temporal consistency check: removed {removed} inconsistent vectors '
                  f'({100*removed/mf.u.size:.1f}%)')
    
    return filtered_fields


def filter_by_tb_change(motion_field, img1, img2, max_tb_change=20.0,
                        high_tb_threshold=272.0):
    """
    Filter vectors where brightness temperature change is too high
    (indicating melt ponds or surface changes rather than motion).
    
    Parameters
    ----------
    motion_field : MotionField
        Input motion field
    img1, img2 : 2D array
        Brightness temperature images
    max_tb_change : float
        Maximum allowed TB change for valid vectors (K)
    high_tb_threshold : float
        Threshold for high TB (potential open water/melt ponds)
        
    Returns
    -------
    MotionField
        Filtered motion field
    """
    from .motion import MotionField
    
    img1 = np.asarray(img1, dtype=np.float64)
    img2 = np.asarray(img2, dtype=np.float64)
    
    delta_tb = np.abs(img2 - img1)
    high_tb = (img1 > high_tb_threshold) | (img2 > high_tb_threshold)
    
    invalid = (delta_tb > max_tb_change) | high_tb
    invalid = invalid & ~(np.isnan(img1) | np.isnan(img2))
    
    if motion_field.u.shape != invalid.shape:
        from skimage.transform import resize
        invalid = resize(invalid.astype(float), motion_field.u.shape, 
                        order=0, mode='nearest', anti_aliasing=False) > 0.5
    
    u_filtered = motion_field.u.copy()
    v_filtered = motion_field.v.copy()
    corr_filtered = motion_field.correlation.copy() if motion_field.correlation is not None else None
    
    u_filtered[invalid] = np.nan
    v_filtered[invalid] = np.nan
    if corr_filtered is not None:
        corr_filtered[invalid] = np.nan
    
    removed = np.sum(invalid)
    if removed > 0:
        print(f'  TB change filter: removed {removed} vectors '
              f'({100*removed/motion_field.u.size:.1f}%)')
    
    return MotionField(
        u_filtered, v_filtered, corr_filtered,
        time_diff=motion_field.time_diff,
        resolution=motion_field.resolution
    )


def multichannel_difference_mask(channels_data, max_diff=10.0):
    """
    Create mask based on multi-channel brightness temperature differences.
    
    Melt ponds and open water have characteristic spectral signatures:
    - Large difference between 19H and 37H channels
    - Low polarization difference at 19 GHz
    
    Parameters
    ----------
    channels_data : dict
        Dictionary of {channel_name: 2D array}
    max_diff : float
        Maximum allowed channel difference for valid ice
        
    Returns
    -------
    2D array (boolean)
        Mask where True indicates valid ice pixels
    """
    if len(channels_data) < 2:
        return np.ones_like(list(channels_data.values())[0], dtype=bool)
    
    reference_channel = list(channels_data.keys())[0]
    reference_img = np.asarray(channels_data[reference_channel], dtype=np.float64)
    valid_mask = np.ones_like(reference_img, dtype=bool)
    
    for ch, img in channels_data.items():
        if ch == reference_channel:
            continue
        
        img = np.asarray(img, dtype=np.float64)
        diff = np.abs(img - reference_img)
        invalid = diff > max_diff
        valid_mask = valid_mask & ~invalid
    
    valid_mask = valid_mask & ~np.isnan(reference_img)
    
    return valid_mask


def filter_by_correlation(motion_field, min_correlation=0.5):
    """
    Filter motion vectors by correlation coefficient.
    
    Parameters
    ----------
    motion_field : MotionField
        Input motion field
    min_correlation : float
        Minimum correlation coefficient threshold (-1 to 1)
        
    Returns
    -------
    MotionField
        Filtered motion field
    """
    from .motion import MotionField
    
    if motion_field.correlation is None:
        return motion_field
    
    mask = motion_field.correlation >= min_correlation
    
    u_filtered = motion_field.u.copy()
    v_filtered = motion_field.v.copy()
    corr_filtered = motion_field.correlation.copy()
    
    u_filtered[~mask] = np.nan
    v_filtered[~mask] = np.nan
    corr_filtered[~mask] = np.nan
    
    return MotionField(
        u_filtered, v_filtered, corr_filtered,
        time_diff=motion_field.time_diff,
        resolution=motion_field.resolution
    )


def detect_outliers(motion_field, method='iqr', threshold=3.0):
    """
    Detect outlier motion vectors.
    
    Parameters
    ----------
    motion_field : MotionField
        Input motion field
    method : str
        'iqr' (Interquartile Range), 'zscore', or 'isolation_forest'
    threshold : float
        Threshold for outlier detection
        
    Returns
    -------
    2D array (boolean)
        Mask where True indicates outliers
    """
    u = motion_field.u
    v = motion_field.v
    speed = motion_field.speed
    
    valid_mask = ~(np.isnan(u) | np.isnan(v))
    
    if method == 'iqr':
        q1_speed = np.percentile(speed[valid_mask], 25)
        q3_speed = np.percentile(speed[valid_mask], 75)
        iqr_speed = q3_speed - q1_speed
        
        q1_u = np.percentile(u[valid_mask], 25)
        q3_u = np.percentile(u[valid_mask], 75)
        iqr_u = q3_u - q1_u
        
        q1_v = np.percentile(v[valid_mask], 25)
        q3_v = np.percentile(v[valid_mask], 75)
        iqr_v = q3_v - q1_v
        
        speed_outliers = (speed < q1_speed - threshold * iqr_speed) | \
                         (speed > q3_speed + threshold * iqr_speed)
        u_outliers = (u < q1_u - threshold * iqr_u) | \
                     (u > q3_u + threshold * iqr_u)
        v_outliers = (v < q1_v - threshold * iqr_v) | \
                     (v > q3_v + threshold * iqr_v)
        
        outliers = speed_outliers | u_outliers | v_outliers
    
    elif method == 'zscore':
        from scipy.stats import zscore
        
        u_z = np.abs(zscore(u[valid_mask]))
        v_z = np.abs(zscore(v[valid_mask]))
        speed_z = np.abs(zscore(speed[valid_mask]))
        
        u_outliers = np.zeros_like(u, dtype=bool)
        v_outliers = np.zeros_like(v, dtype=bool)
        speed_outliers = np.zeros_like(speed, dtype=bool)
        
        u_outliers[valid_mask] = u_z > threshold
        v_outliers[valid_mask] = v_z > threshold
        speed_outliers[valid_mask] = speed_z > threshold
        
        outliers = speed_outliers | u_outliers | v_outliers
    
    elif method == 'isolation_forest':
        features = np.column_stack([
            u[valid_mask].ravel(),
            v[valid_mask].ravel(),
            speed[valid_mask].ravel()
        ])
        
        if len(features) < 10:
            return np.zeros_like(u, dtype=bool)
        
        clf = IsolationForest(contamination=0.1, random_state=42)
        pred = clf.fit_predict(features)
        
        outliers = np.zeros_like(u, dtype=bool)
        outliers[valid_mask] = pred == -1
    
    else:
        raise ValueError(f'Unknown outlier detection method: {method}')
    
    outliers[~valid_mask] = False
    
    return outliers


def remove_outliers(motion_field, method='iqr', threshold=3.0):
    """
    Remove outlier motion vectors (set to NaN).
    
    Parameters
    ----------
    motion_field : MotionField
        Input motion field
    method : str
        Outlier detection method
    threshold : float
        Threshold for outlier detection
        
    Returns
    -------
    MotionField
        Motion field with outliers removed
    """
    from .motion import MotionField
    
    outlier_mask = detect_outliers(motion_field, method, threshold)
    
    u_clean = motion_field.u.copy()
    v_clean = motion_field.v.copy()
    corr_clean = motion_field.correlation.copy() if motion_field.correlation is not None else None
    
    u_clean[outlier_mask] = np.nan
    v_clean[outlier_mask] = np.nan
    if corr_clean is not None:
        corr_clean[outlier_mask] = np.nan
    
    return MotionField(
        u_clean, v_clean, corr_clean,
        time_diff=motion_field.time_diff,
        resolution=motion_field.resolution
    )


def interpolate_missing(motion_field, method='linear', max_distance=None):
    """
    Interpolate missing (NaN) values in motion field.
    
    Parameters
    ----------
    motion_field : MotionField
        Input motion field with missing values
    method : str
        'linear', 'nearest', 'cubic', 'rbf', or 'gaussian'
    max_distance : float, optional
        Maximum interpolation distance in pixels
        
    Returns
    -------
    MotionField
        Interpolated motion field
    """
    from .motion import MotionField
    
    rows, cols = motion_field.u.shape
    
    valid_mask = ~(np.isnan(motion_field.u) | np.isnan(motion_field.v))
    
    if np.all(valid_mask):
        return motion_field
    
    if not np.any(valid_mask):
        raise ValueError('No valid data points for interpolation')
    
    grid_y, grid_x = np.mgrid[0:rows, 0:cols]
    grid_points = np.column_stack([grid_x.ravel(), grid_y.ravel()])
    
    valid_indices = np.argwhere(valid_mask)
    valid_points = valid_indices[:, ::-1]
    valid_u = motion_field.u[valid_mask]
    valid_v = motion_field.v[valid_mask]
    
    if method in ['linear', 'nearest', 'cubic']:
        u_interp = griddata(valid_points, valid_u, grid_points, method=method)
        v_interp = griddata(valid_points, valid_v, grid_points, method=method)
        
        u_interp = u_interp.reshape(rows, cols)
        v_interp = v_interp.reshape(rows, cols)
        
        if method == 'linear' or method == 'cubic':
            nan_mask = np.isnan(u_interp) | np.isnan(v_interp)
            if np.any(nan_mask):
                u_nearest = griddata(valid_points, valid_u, grid_points, method='nearest')
                v_nearest = griddata(valid_points, valid_v, grid_points, method='nearest')
                u_nearest = u_nearest.reshape(rows, cols)
                v_nearest = v_nearest.reshape(rows, cols)
                u_interp[nan_mask] = u_nearest[nan_mask]
                v_interp[nan_mask] = v_nearest[nan_mask]
    
    elif method == 'rbf':
        rbf_u = RBFInterpolator(valid_points, valid_u, kernel='thin_plate_spline', smoothing=1.0)
        rbf_v = RBFInterpolator(valid_points, valid_v, kernel='thin_plate_spline', smoothing=1.0)
        
        u_interp = rbf_u(grid_points).reshape(rows, cols)
        v_interp = rbf_v(grid_points).reshape(rows, cols)
    
    elif method == 'gaussian':
        if max_distance is None:
            max_distance = 10.0
        
        u_interp = np.zeros((rows, cols))
        v_interp = np.zeros((rows, cols))
        weights_sum = np.zeros((rows, cols))
        
        for (py, px), u_val, v_val in zip(valid_indices, valid_u, valid_v):
            dist = np.sqrt((grid_x - px)**2 + (grid_y - py)**2)
            weights = np.exp(-dist**2 / (2 * max_distance**2))
            
            u_interp += u_val * weights
            v_interp += v_val * weights
            weights_sum += weights
        
        valid_weights = weights_sum > 1e-10
        u_interp[valid_weights] /= weights_sum[valid_weights]
        v_interp[valid_weights] /= weights_sum[valid_weights]
        
        u_interp[~valid_weights] = np.nan
        v_interp[~valid_weights] = np.nan
    
    else:
        raise ValueError(f'Unknown interpolation method: {method}')
    
    if max_distance is not None and method != 'gaussian':
        from scipy.ndimage import distance_transform_edt
        distance = distance_transform_edt(~valid_mask)
        too_far = distance > max_distance
        u_interp[too_far] = np.nan
        v_interp[too_far] = np.nan
    
    corr_interp = None
    if motion_field.correlation is not None:
        valid_corr = motion_field.correlation[valid_mask]
        if method in ['linear', 'nearest', 'cubic']:
            corr_interp = griddata(valid_points, valid_corr, grid_points, method='nearest')
            corr_interp = corr_interp.reshape(rows, cols)
        else:
            corr_interp = np.zeros_like(motion_field.correlation)
            corr_interp[valid_mask] = valid_corr
    
    return MotionField(
        u_interp, v_interp, corr_interp,
        time_diff=motion_field.time_diff,
        resolution=motion_field.resolution
    )


def smooth_motion_field(motion_field, method='gaussian', sigma=1.5, **kwargs):
    """
    Smooth motion field.
    
    Parameters
    ----------
    motion_field : MotionField
        Input motion field
    method : str
        'gaussian' or 'median'
    sigma : float
        Sigma for Gaussian filter (or size for median)
    **kwargs
        Additional parameters for the filter
        
    Returns
    -------
    MotionField
        Smoothed motion field
    """
    from .motion import MotionField
    
    valid_mask = ~(np.isnan(motion_field.u) | np.isnan(motion_field.v))
    
    u_filled = motion_field.u.copy()
    v_filled = motion_field.v.copy()
    
    u_filled[~valid_mask] = 0
    v_filled[~valid_mask] = 0
    
    if method == 'gaussian':
        u_smooth = gaussian_filter(u_filled, sigma=sigma, **kwargs)
        v_smooth = gaussian_filter(v_filled, sigma=sigma, **kwargs)
    elif method == 'median':
        size = int(sigma)
        u_smooth = median_filter(u_filled, size=size, **kwargs)
        v_smooth = median_filter(v_filled, size=size, **kwargs)
    else:
        raise ValueError(f'Unknown smoothing method: {method}')
    
    weight = np.ones_like(valid_mask, dtype=float)
    weight[~valid_mask] = 0
    weight_smooth = gaussian_filter(weight, sigma=sigma) if method == 'gaussian' else weight
    
    valid_weight = weight_smooth > 1e-10
    u_smooth[valid_weight] /= weight_smooth[valid_weight]
    v_smooth[valid_weight] /= weight_smooth[valid_weight]
    
    u_smooth[~valid_weight] = np.nan
    v_smooth[~valid_weight] = np.nan
    
    corr_smooth = None
    if motion_field.correlation is not None:
        corr_filled = motion_field.correlation.copy()
        corr_filled[~valid_mask] = 0
        if method == 'gaussian':
            corr_smooth = gaussian_filter(corr_filled, sigma=sigma, **kwargs)
        else:
            corr_smooth = median_filter(corr_filled, size=size, **kwargs)
        corr_smooth[valid_weight] /= weight_smooth[valid_weight]
        corr_smooth[~valid_weight] = np.nan
    
    return MotionField(
        u_smooth, v_smooth, corr_smooth,
        time_diff=motion_field.time_diff,
        resolution=motion_field.resolution
    )


def quality_control_pipeline(motion_field, 
                             min_correlation=0.5,
                             outlier_method='iqr',
                             outlier_threshold=3.0,
                             interp_method='linear',
                             smooth_method='gaussian',
                             smooth_sigma=1.0,
                             img1=None,
                             img2=None,
                             do_tb_filter=False,
                             max_tb_change=20.0,
                             high_tb_threshold=272.0):
    """
    Complete quality control pipeline.
    
    Parameters
    ----------
    motion_field : MotionField
        Input motion field
    min_correlation : float
        Minimum correlation coefficient threshold
    outlier_method : str
        Outlier detection method
    outlier_threshold : float
        Outlier detection threshold
    interp_method : str
        Interpolation method for missing values
    smooth_method : str
        Smoothing method
    smooth_sigma : float
        Smoothing parameter
    img1, img2 : 2D array, optional
        Brightness temperature images for TB change filtering
    do_tb_filter : bool
        Whether to filter by TB change (melt pond detection)
    max_tb_change : float
        Maximum allowed TB change for valid vectors
    high_tb_threshold : float
        Threshold for high TB detection
        
    Returns
    -------
    dict
        'filtered': motion field after correlation filtering,
        'tb_filtered': motion field after TB change filtering,
        'outliers_removed': motion field after outlier removal,
        'interpolated': motion field after interpolation,
        'smoothed': motion field after smoothing,
        'qc_metrics': quality control metrics
    """
    results = {}
    
    original_valid = np.sum(~(np.isnan(motion_field.u) | np.isnan(motion_field.v)))
    total_pixels = motion_field.u.size
    
    print('Filtering by correlation...')
    results['filtered'] = filter_by_correlation(motion_field, min_correlation)
    
    corr_valid = np.sum(~(np.isnan(results['filtered'].u) | np.isnan(results['filtered'].v)))
    
    if do_tb_filter and img1 is not None and img2 is not None:
        print('Filtering by brightness temperature change...')
        results['tb_filtered'] = filter_by_tb_change(
            results['filtered'], img1, img2, max_tb_change, high_tb_threshold
        )
        next_mf = results['tb_filtered']
    else:
        results['tb_filtered'] = results['filtered']
        next_mf = results['filtered']
    
    tb_valid = np.sum(~(np.isnan(next_mf.u) | np.isnan(next_mf.v)))
    
    print('Removing outliers...')
    results['outliers_removed'] = remove_outliers(
        next_mf, outlier_method, outlier_threshold
    )
    
    outlier_valid = np.sum(~(np.isnan(results['outliers_removed'].u) | 
                             np.isnan(results['outliers_removed'].v)))
    
    print('Interpolating missing values...')
    results['interpolated'] = interpolate_missing(
        results['outliers_removed'], interp_method
    )
    
    interp_valid = np.sum(~(np.isnan(results['interpolated'].u) | 
                            np.isnan(results['interpolated'].v)))
    
    print('Smoothing motion field...')
    results['smoothed'] = smooth_motion_field(
        results['interpolated'], smooth_method, smooth_sigma
    )
    
    final_valid = np.sum(~(np.isnan(results['smoothed'].u) | 
                           np.isnan(results['smoothed'].v)))
    
    results['qc_metrics'] = {
        'total_pixels': total_pixels,
        'original_valid': original_valid,
        'after_correlation_filter': corr_valid,
        'after_tb_filter': tb_valid,
        'after_outlier_removal': outlier_valid,
        'after_interpolation': interp_valid,
        'final_valid': final_valid,
        'percentage_valid': (final_valid / total_pixels) * 100,
        'mean_speed': np.nanmean(results['smoothed'].speed),
        'std_speed': np.nanstd(results['smoothed'].speed),
        'mean_correlation': np.nanmean(results['smoothed'].correlation) if 
                            results['smoothed'].correlation is not None else None,
    }
    
    print(f'QC Complete: {results["qc_metrics"]["percentage_valid"]:.1f}% valid pixels')
    print(f'  Mean speed: {results["qc_metrics"]["mean_speed"]:.2f} px')
    
    return results


def compute_quality_metrics(motion_field):
    """
    Compute quality metrics for a motion field.
    
    Parameters
    ----------
    motion_field : MotionField
        Input motion field
        
    Returns
    -------
    dict
        Quality metrics
    """
    valid_mask = ~(np.isnan(motion_field.u) | np.isnan(motion_field.v))
    
    metrics = {
        'total_pixels': motion_field.u.size,
        'valid_pixels': np.sum(valid_mask),
        'percentage_valid': (np.sum(valid_mask) / motion_field.u.size) * 100,
        'mean_u': np.nanmean(motion_field.u),
        'mean_v': np.nanmean(motion_field.v),
        'mean_speed': np.nanmean(motion_field.speed),
        'std_u': np.nanstd(motion_field.u),
        'std_v': np.nanstd(motion_field.v),
        'std_speed': np.nanstd(motion_field.speed),
        'max_speed': np.nanmax(motion_field.speed),
        'min_speed': np.nanmin(motion_field.speed),
    }
    
    if motion_field.correlation is not None:
        metrics['mean_correlation'] = np.nanmean(motion_field.correlation)
        metrics['std_correlation'] = np.nanstd(motion_field.correlation)
        metrics['min_correlation'] = np.nanmin(motion_field.correlation)
    
    if motion_field.time_diff > 0:
        metrics['mean_velocity'] = np.nanmean(motion_field.speed) * motion_field.resolution / motion_field.time_diff
    
    return metrics
