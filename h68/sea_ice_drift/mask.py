"""
Mask generation and application module.

Supports:
- Coastline masks (from shapefiles or synthetic)
- Low brightness temperature masks
- Land/sea masks
- Custom mask application
"""

import os
import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion, distance_transform_edt


def create_low_brightness_mask(image_data, threshold=None, percentile=5):
    """
    Create mask for low brightness temperature areas.
    
    Parameters
    ----------
    image_data : 2D array
        Brightness temperature image
    threshold : float, optional
        Absolute threshold in K. If None, uses percentile.
    percentile : float
        Percentile value for automatic threshold (0-100)
        
    Returns
    -------
    2D array (boolean)
        Mask where True indicates valid (not low-brightness) pixels
    """
    image_data = np.asarray(image_data, dtype=np.float64)
    valid_data = image_data[~np.isnan(image_data)]
    
    if threshold is None:
        threshold = np.percentile(valid_data, percentile)
    
    mask = image_data > threshold
    mask[np.isnan(image_data)] = False
    
    return mask


def compute_distance_to_coast(lats, lons, land_mask, resolution_km=12.5):
    """
    Compute distance from each pixel to the nearest coastline.
    
    Parameters
    ----------
    lats, lons : 2D array
        Coordinate grids
    land_mask : 2D array (boolean)
        Mask where True indicates land
    resolution_km : float
        Grid resolution in km
        
    Returns
    -------
    dict
        'distance': distance map in km,
        'signed_distance': signed distance (negative = land, positive = ocean),
        'nearest_land': indices of nearest land point
    """
    ocean_mask = ~land_mask
    ocean_mask[np.isnan(lats)] = False
    
    distance_ocean = distance_transform_edt(ocean_mask.astype(float),
                                            sampling=resolution_km)
    distance_land = distance_transform_edt(land_mask.astype(float),
                                           sampling=resolution_km)
    
    signed_distance = np.where(land_mask, -distance_land, distance_ocean)
    distance = np.abs(signed_distance)
    
    return {
        'distance': distance,
        'signed_distance': signed_distance,
        'distance_land': distance_land,
        'distance_ocean': distance_ocean,
    }


def create_gradient_constraint_mask(gradient_magnitude, coast_distance,
                                    max_gradient_ratio=3.0,
                                    min_coast_distance_km=25.0):
    """
    Create mask to exclude vectors near coastlines with high gradient
    (likely contaminated by land pixels).
    
    Parameters
    ----------
    gradient_magnitude : 2D array
        Brightness temperature gradient magnitude
    coast_distance : 2D array
        Distance to nearest coastline in km
    max_gradient_ratio : float
        Maximum allowed gradient relative to median
    min_coast_distance_km : float
        Minimum distance from coast for reliable vectors
        
    Returns
    -------
    2D array (boolean)
        Mask where True indicates valid pixels
    """
    valid_mask = np.ones_like(gradient_magnitude, dtype=bool)
    
    near_coast = coast_distance < min_coast_distance_km
    
    valid_gradient = gradient_magnitude[~near_coast & ~np.isnan(gradient_magnitude)]
    if len(valid_gradient) > 0:
        median_grad = np.median(valid_gradient)
        high_gradient = gradient_magnitude > max_gradient_ratio * median_grad
        
        invalid = near_coast & high_gradient
        valid_mask[invalid] = False
    
    valid_mask[np.isnan(gradient_magnitude)] = False
    
    return valid_mask


def create_coastline_mask(lats, lons, buffer_km=10.0, hemisphere='north',
                          gradient_magnitude=None, resolution_km=None,
                          exclude_near_coast=True, min_coast_distance_km=25.0):
    """
    Create coastline buffer mask with enhanced coastline handling.
    
    Uses distance from approximate coastline based on latitude threshold
    and synthetic continent outlines for the Arctic. Includes gradient-based
    filtering to exclude pixels potentially contaminated by land.
    
    Parameters
    ----------
    lats : 2D array
        Latitude grid
    lons : 2D array
        Longitude grid
    buffer_km : float
        Buffer distance from coastline in km
    hemisphere : str
        'north' or 'south'
    gradient_magnitude : 2D array, optional
        Brightness temperature gradient for enhanced masking
    resolution_km : float, optional
        Grid resolution in km (auto-detected if None)
    exclude_near_coast : bool
        Whether to apply gradient-based near-coast exclusion
    min_coast_distance_km : float
        Minimum distance from coast for reliable vectors
        
    Returns
    -------
    dict
        'mask': boolean mask where True indicates valid pixels,
        'land_mask': land mask,
        'coast_distance': distance to coast in km,
        'gradient_mask': gradient-based constraint mask
    """
    lats = np.asarray(lats, dtype=np.float64)
    lons = np.asarray(lons, dtype=np.float64)
    
    rows, cols = lats.shape
    
    if resolution_km is None:
        dy = np.abs(lats[1, 0] - lats[0, 0]) * 111.32
        dx = np.abs(lons[0, 1] - lons[0, 0]) * 111.32 * np.cos(np.radians(np.mean(lats)))
        resolution_km = np.mean([dx, dy])
    
    land_mask = np.zeros((rows, cols), dtype=bool)
    
    if hemisphere == 'north':
        north_america = (lats > 50) & (lats < 85) & (lons > -140) & (lons < -50)
        greenland = (lats > 60) & (lats < 85) & (lons > -75) & (lons < -15)
        europe = (lats > 50) & (lats < 75) & (lons > -10) & (lons < 40)
        asia = (lats > 50) & (lats < 80) & (lons > 40) & (lons < 180)
        svalbard = (lats > 75) & (lats < 82) & (lons > 10) & (lons < 35)
        novaya_zemlya = (lats > 70) & (lats < 76) & (lons > 50) & (lons < 70)
        franz_josef = (lats > 80) & (lats < 82) & (lons > 45) & (lons < 65)
        
        land_mask = (north_america | greenland | europe | asia | 
                     svalbard | novaya_zemlya | franz_josef)
        
    else:
        antarctica = lats < -60
        land_mask = antarctica
    
    land_mask[np.isnan(lats)] = True
    
    dist_info = compute_distance_to_coast(lats, lons, land_mask, resolution_km)
    coast_distance = dist_info['distance']
    
    buffer_pixels = int(np.ceil(buffer_km / resolution_km))
    if buffer_pixels > 0:
        coast_mask = binary_dilation(land_mask, iterations=buffer_pixels)
    else:
        coast_mask = land_mask
    
    valid_mask = ~coast_mask
    valid_mask[np.isnan(lats)] = False
    
    gradient_mask = np.ones_like(valid_mask, dtype=bool)
    if exclude_near_coast and gradient_magnitude is not None:
        gradient_mask = create_gradient_constraint_mask(
            gradient_magnitude, coast_distance,
            min_coast_distance_km=min_coast_distance_km
        )
        valid_mask = valid_mask & gradient_mask
    
    return {
        'mask': valid_mask,
        'land_mask': land_mask,
        'coast_mask': coast_mask,
        'coast_distance': coast_distance,
        'signed_distance': dist_info['signed_distance'],
        'gradient_mask': gradient_mask,
    }


def create_land_mask(lats, lons, hemisphere='north'):
    """
    Create land/sea mask based on approximate continent boundaries.
    
    Parameters
    ----------
    lats : 2D array
        Latitude grid
    lons : 2D array
        Longitude grid
    hemisphere : str
        'north' or 'south'
        
    Returns
    -------
    2D array (boolean)
        Mask where True indicates ocean (valid) pixels
    """
    lats = np.asarray(lats, dtype=np.float64)
    lons = np.asarray(lons, dtype=np.float64)
    
    if hemisphere == 'north':
        north_america = (lats > 50) & (lats < 85) & (lons > -140) & (lons < -50)
        greenland = (lats > 60) & (lats < 85) & (lons > -75) & (lons < -15)
        europe = (lats > 50) & (lats < 75) & (lons > -10) & (lons < 40)
        asia = (lats > 50) & (lats < 80) & (lons > 40) & (lons < 180)
        svalbard = (lats > 75) & (lats < 82) & (lons > 10) & (lons < 35)
        
        land_mask = north_america | greenland | europe | asia | svalbard
    else:
        antarctica = lats < -60
        land_mask = antarctica
    
    ocean_mask = ~land_mask
    ocean_mask[np.isnan(lats)] = False
    
    return ocean_mask


def load_shapefile_mask(shapefile_path, lats, lons):
    """
    Load mask from ESRI shapefile.
    
    Parameters
    ----------
    shapefile_path : str
        Path to shapefile (.shp)
    lats : 2D array
        Latitude grid
    lons : 2D array
        Longitude grid
        
    Returns
    -------
    2D array (boolean)
        Mask where True indicates pixels inside shapefile features
    """
    try:
        import shapefile
        from shapely.geometry import Point, shape
    except ImportError:
        raise ImportError('pyshp and shapely are required for shapefile support. '
                          'Install with: pip install pyshp shapely')
    
    sf = shapefile.Reader(shapefile_path)
    shapes = sf.shapes()
    
    rows, cols = lats.shape
    mask = np.zeros((rows, cols), dtype=bool)
    
    for shp in shapes:
        polygon = shape(shp)
        for i in range(rows):
            for j in range(cols):
                if not np.isnan(lats[i, j]) and not np.isnan(lons[i, j]):
                    point = Point(lons[i, j], lats[i, j])
                    if polygon.contains(point):
                        mask[i, j] = True
    
    return mask


def apply_mask(image_data, mask, fill_value=np.nan):
    """
    Apply mask to image data.
    
    Parameters
    ----------
    image_data : 2D array
        Input image
    mask : 2D array (boolean)
        Mask where True indicates valid pixels
    fill_value : float
        Value to use for invalid pixels
        
    Returns
    -------
    2D array
        Masked image
    """
    image_data = np.asarray(image_data, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    
    if image_data.shape != mask.shape:
        raise ValueError(f'Shape mismatch: image {image_data.shape}, mask {mask.shape}')
    
    result = image_data.copy()
    result[~mask] = fill_value
    
    return result


def apply_mask_to_motion(motion_field, mask):
    """
    Apply mask to motion field.
    
    Parameters
    ----------
    motion_field : MotionField
        Input motion field
    mask : 2D array (boolean)
        Mask where True indicates valid pixels
        
    Returns
    -------
    MotionField
        Masked motion field
    """
    from .motion import MotionField
    
    mask = np.asarray(mask, dtype=bool)
    
    if motion_field.u.shape != mask.shape:
        raise ValueError(f'Shape mismatch: motion {motion_field.u.shape}, mask {mask.shape}')
    
    u_masked = motion_field.u.copy()
    v_masked = motion_field.v.copy()
    corr_masked = motion_field.correlation.copy()
    
    u_masked[~mask] = np.nan
    v_masked[~mask] = np.nan
    corr_masked[~mask] = np.nan
    
    return MotionField(
        u_masked, v_masked, corr_masked,
        time_diff=motion_field.time_diff,
        resolution=motion_field.resolution
    )


def combine_masks(*masks, method='and'):
    """
    Combine multiple masks.
    
    Parameters
    ----------
    *masks : 2D arrays (boolean)
        Masks to combine
    method : str
        'and' (intersection) or 'or' (union)
        
    Returns
    -------
    2D array (boolean)
        Combined mask
    """
    if not masks:
        raise ValueError('No masks provided')
    
    shapes = [m.shape for m in masks]
    if len(set(shapes)) > 1:
        raise ValueError(f'Mask shapes do not match: {shapes}')
    
    masks = [np.asarray(m, dtype=bool) for m in masks]
    
    if method == 'and':
        combined = masks[0]
        for m in masks[1:]:
            combined = combined & m
    elif method == 'or':
        combined = masks[0]
        for m in masks[1:]:
            combined = combined | m
    else:
        raise ValueError(f'Unknown combination method: {method}')
    
    return combined


def smooth_mask(mask, iterations=1):
    """
    Smooth mask boundaries using morphological operations.
    
    Parameters
    ----------
    mask : 2D array (boolean)
        Input mask
    iterations : int
        Number of dilation/erosion iterations
        
    Returns
    -------
    2D array (boolean)
        Smoothed mask
    """
    mask = np.asarray(mask, dtype=bool)
    
    structure = np.ones((3, 3), dtype=bool)
    smoothed = binary_erosion(mask, structure, iterations=iterations)
    smoothed = binary_dilation(smoothed, structure, iterations=iterations)
    
    return smoothed


def create_full_mask(image_data, lats, lons, 
                     do_low_brightness=True, low_brightness_threshold=None,
                     do_coastline=True, coastline_buffer_km=10.0,
                     do_land=True, hemisphere='north',
                     gradient_magnitude=None,
                     exclude_near_coast=True,
                     min_coast_distance_km=25.0):
    """
    Create complete mask by combining all mask types.
    
    Parameters
    ----------
    image_data : 2D array
        Brightness temperature image
    lats, lons : 2D array
        Coordinate grids
    do_low_brightness : bool
        Include low brightness mask
    low_brightness_threshold : float, optional
        Threshold for low brightness mask
    do_coastline : bool
        Include coastline mask
    coastline_buffer_km : float
        Buffer for coastline mask
    do_land : bool
        Include land mask
    hemisphere : str
        'north' or 'south'
    gradient_magnitude : 2D array, optional
        Brightness temperature gradient for enhanced coastline masking
    exclude_near_coast : bool
        Whether to apply gradient-based near-coast exclusion
    min_coast_distance_km : float
        Minimum distance from coast for reliable vectors
        
    Returns
    -------
    dict
        'combined': combined mask,
        'low_brightness': low brightness mask,
        'coastline': coastline mask information dict,
        'land': land mask,
        'coast_distance': distance to coast in km
    """
    masks = {}
    result = {}
    
    if do_low_brightness:
        masks['low_brightness'] = create_low_brightness_mask(
            image_data, low_brightness_threshold
        )
        result['low_brightness'] = masks['low_brightness']
    
    if do_coastline:
        coastline_result = create_coastline_mask(
            lats, lons, coastline_buffer_km, hemisphere,
            gradient_magnitude=gradient_magnitude,
            exclude_near_coast=exclude_near_coast,
            min_coast_distance_km=min_coast_distance_km
        )
        masks['coastline'] = coastline_result['mask']
        result['coastline'] = coastline_result
        result['coast_distance'] = coastline_result['coast_distance']
    
    if do_land:
        masks['land'] = create_land_mask(lats, lons, hemisphere)
        result['land'] = masks['land']
    
    if masks:
        combined = combine_masks(*masks.values(), method='and')
    else:
        combined = np.ones_like(image_data, dtype=bool)
    
    result['combined'] = combined
    
    return result
