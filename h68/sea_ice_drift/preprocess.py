"""
Preprocessing module for brightness temperature images.

Includes:
- Reprojection to polar azimuthal equal-area grid
- Denoising algorithms (Gaussian, median, wavelet, bilateral)
- Image normalization and enhancement
"""

import numpy as np
import cv2
from scipy import ndimage
from scipy.interpolate import griddata, interp2d
from scipy.ndimage import map_coordinates
from pyproj import Proj, Transformer
from skimage.restoration import denoise_wavelet, estimate_sigma
from skimage.transform import resize


def detect_resolution(lats, lons):
    """
    Detect the spatial resolution of the input grid.
    
    Parameters
    ----------
    lats, lons : 2D array
        Coordinate grids
        
    Returns
    -------
    dict
        'resolution_km': approximate resolution in km,
        'resolution_m': resolution in meters,
        'is_high_res': boolean indicating if > 20km resolution
    """
    lats = np.asarray(lats)
    lons = np.asarray(lons)
    
    dy = np.abs(lats[1, 0] - lats[0, 0]) * 111.32
    dx = np.abs(lons[0, 1] - lons[0, 0]) * 111.32 * np.cos(np.radians(np.mean(lats)))
    
    resolution_km = np.mean([dx, dy])
    resolution_m = resolution_km * 1000
    
    return {
        'resolution_km': resolution_km,
        'resolution_m': resolution_m,
        'is_high_res': resolution_km <= 20.0,
        'resolution_class': 'high' if resolution_km <= 20.0 else 'low'
    }


def upsample_image(image, target_shape, method='bicubic'):
    """
    Upsample image to target shape with subpixel accuracy.
    
    Parameters
    ----------
    image : 2D array
        Input image
    target_shape : tuple
        Target (rows, cols)
    method : str
        'bicubic', 'bilinear', 'lanczos', or 'gaussian'
        
    Returns
    -------
    2D array
        Upsampled image
    """
    image = np.asarray(image, dtype=np.float64)
    nan_mask = np.isnan(image)
    
    if np.any(nan_mask):
        filled = image.copy()
        ind = ndimage.distance_transform_edt(nan_mask, return_distances=False,
                                             return_indices=True)
        filled[nan_mask] = image[tuple(ind[:, nan_mask])]
    else:
        filled = image
    
    order = {'bilinear': 1, 'bicubic': 3, 'lanczos': 4, 'gaussian': 1}[method]
    
    if method == 'gaussian':
        upsampled = resize(filled, target_shape, order=order, mode='reflect',
                          anti_aliasing=True, anti_aliasing_sigma=0.5)
    else:
        upsampled = resize(filled, target_shape, order=order, mode='reflect',
                          anti_aliasing=False)
    
    if np.any(nan_mask):
        nan_mask_upsampled = resize(nan_mask.astype(float), target_shape, 
                                   order=0, mode='nearest', anti_aliasing=False) > 0.5
        upsampled[nan_mask_upsampled] = np.nan
    
    return upsampled


def downsample_image(image, target_shape, method='gaussian'):
    """
    Downsample image to target shape with anti-aliasing.
    
    Parameters
    ----------
    image : 2D array
        Input image
    target_shape : tuple
        Target (rows, cols)
    method : str
        'gaussian', 'mean', or 'median'
        
    Returns
    -------
    2D array
        Downsampled image
    """
    image = np.asarray(image, dtype=np.float64)
    nan_mask = np.isnan(image)
    
    if np.any(nan_mask):
        filled = image.copy()
        ind = ndimage.distance_transform_edt(nan_mask, return_distances=False,
                                             return_indices=True)
        filled[nan_mask] = image[tuple(ind[:, nan_mask])]
    else:
        filled = image
    
    if method == 'gaussian':
        downsampled = resize(filled, target_shape, order=1, mode='reflect',
                            anti_aliasing=True, anti_aliasing_sigma=1.0)
    elif method == 'mean':
        downsampled = resize(filled, target_shape, order=1, mode='reflect',
                            anti_aliasing=False)
    elif method == 'median':
        rows, cols = image.shape
        trows, tcols = target_shape
        scale_y, scale_x = rows // trows, cols // tcols
        
        downsampled = np.zeros(target_shape)
        for i in range(trows):
            for j in range(tcols):
                patch = filled[i*scale_y:(i+1)*scale_y, j*scale_x:(j+1)*scale_x]
                downsampled[i, j] = np.median(patch)
    else:
        downsampled = resize(filled, target_shape, order=1, mode='reflect',
                            anti_aliasing=True)
    
    if np.any(nan_mask):
        nan_mask_down = resize(nan_mask.astype(float), target_shape,
                              order=0, mode='nearest', anti_aliasing=False) > 0.1
        downsampled[nan_mask_down] = np.nan
    
    return downsampled


def subpixel_refine_correlation(corr_map, upsample_factor=10):
    """
    Refine correlation peak to subpixel accuracy using quadratic fitting.
    
    Parameters
    ----------
    corr_map : 2D array
        Correlation map
    upsample_factor : int
        Upsampling factor for subpixel refinement
        
    Returns
    -------
    tuple
        (subpixel_y, subpixel_x, correlation_value)
    """
    if corr_map.size == 0:
        return 0.0, 0.0, 0.0
    
    max_pos = np.unravel_index(np.argmax(corr_map), corr_map.shape)
    py, px = max_pos
    
    if (py <= 0 or py >= corr_map.shape[0] - 1 or 
        px <= 0 or px >= corr_map.shape[1] - 1):
        return float(py), float(px), corr_map[py, px]
    
    try:
        c = corr_map[py, px]
        cy = (corr_map[py-1, px] - corr_map[py+1, px]) / (2 * corr_map[py-1, px] - 4 * c + 2 * corr_map[py+1, px] + 1e-10)
        cx = (corr_map[py, px-1] - corr_map[py, px+1]) / (2 * corr_map[py, px-1] - 4 * c + 2 * corr_map[py, px+1] + 1e-10)
        
        cy = np.clip(cy, -0.5, 0.5)
        cx = np.clip(cx, -0.5, 0.5)
        
        subpy = py + cy
        subpx = px + cx
        
        return subpy, subpx, c
    except:
        return float(py), float(px), corr_map[py, px]


def align_multiresolution_images(img1, img2, res1, res2, 
                                  target_resolution=12.5,
                                  upsample_method='bicubic'):
    """
    Align images from different resolutions to a common grid.
    
    Parameters
    ----------
    img1, img2 : 2D array
        Input images
    res1, res2 : dict
        Resolution info from detect_resolution
    target_resolution : float
        Target resolution in km
    upsample_method : str
        Method for upsampling
        
    Returns
    -------
    tuple
        (aligned_img1, aligned_img2, scale_factor_1, scale_factor_2)
    """
    img1 = np.asarray(img1, dtype=np.float64)
    img2 = np.asarray(img2, dtype=np.float64)
    
    target_shape = None
    scale1 = 1.0
    scale2 = 1.0
    
    if res1['resolution_km'] > target_resolution:
        scale1 = res1['resolution_km'] / target_resolution
        target_shape = (int(img1.shape[0] * scale1), int(img1.shape[1] * scale1))
        img1_aligned = upsample_image(img1, target_shape, method=upsample_method)
    elif res1['resolution_km'] < target_resolution:
        scale1 = target_resolution / res1['resolution_km']
        target_shape = (int(img1.shape[0] / scale1), int(img1.shape[1] / scale1))
        img1_aligned = downsample_image(img1, target_shape, method='gaussian')
    else:
        img1_aligned = img1.copy()
        target_shape = img1.shape
    
    if res2['resolution_km'] > target_resolution:
        scale2 = res2['resolution_km'] / target_resolution
        img2_aligned = upsample_image(img2, target_shape, method=upsample_method)
    elif res2['resolution_km'] < target_resolution:
        scale2 = target_resolution / res2['resolution_km']
        img2_shape = (int(img2.shape[0] / scale2), int(img2.shape[1] / scale2))
        if img2_shape != target_shape:
            img2_aligned = downsample_image(img2, target_shape, method='gaussian')
        else:
            img2_aligned = downsample_image(img2, img2_shape, method='gaussian')
            if img2_aligned.shape != target_shape:
                img2_aligned = resize(img2_aligned, target_shape, order=3, 
                                     mode='reflect', anti_aliasing=False)
    else:
        if img2.shape != target_shape:
            img2_aligned = resize(img2, target_shape, order=3, 
                                 mode='reflect', anti_aliasing=False)
        else:
            img2_aligned = img2.copy()
    
    return img1_aligned, img2_aligned, scale1, scale2


def reproject_to_polar_ae(data, src_lats, src_lons, target_resolution=12.5,
                          hemisphere='north', target_shape=None,
                          interpolation_method='linear'):
    """
    Reproject image to polar azimuthal equal-area (AE) projection.
    
    Parameters
    ----------
    data : 2D array
        Input image data
    src_lats : 2D array
        Source latitudes
    src_lons : 2D array
        Source longitudes
    target_resolution : float
        Target grid resolution in km
    hemisphere : str
        'north' or 'south'
    target_shape : tuple, optional
        Target (rows, cols). If None, calculated from resolution.
        
    Returns
    -------
    dict
        'data': reprojected data,
        'x': x coordinates in meters,
        'y': y coordinates in meters,
        'lats': reprojected latitudes,
        'lons': reprojected longitudes,
        'proj': projection string
    """
    src_lats = np.asarray(src_lats)
    src_lons = np.asarray(src_lons)
    data = np.asarray(data, dtype=np.float64)
    
    lat_0 = 90 if hemisphere == 'north' else -90
    lon_0 = 0
    
    target_proj_str = (f'+proj=laea +lat_0={lat_0} +lon_0={lon_0} '
                       f'+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs')
    
    target_proj = Proj(target_proj_str)
    latlon_proj = Proj('+proj=latlong +datum=WGS84')
    transformer_to_xy = Transformer.from_proj(latlon_proj, target_proj)
    transformer_to_latlon = Transformer.from_proj(target_proj, latlon_proj)
    
    src_x, src_y = transformer_to_xy.transform(src_lons, src_lats)
    
    if target_shape is None:
        extent_x = np.nanmax(src_x) - np.nanmin(src_x)
        extent_y = np.nanmax(src_y) - np.nanmin(src_y)
        res_m = target_resolution * 1000
        cols = int(np.ceil(extent_x / res_m))
        rows = int(np.ceil(extent_y / res_m))
        target_shape = (max(rows, 100), max(cols, 100))
    
    rows, cols = target_shape
    x_min, x_max = np.nanmin(src_x), np.nanmax(src_x)
    y_min, y_max = np.nanmin(src_y), np.nanmax(src_y)
    
    x = np.linspace(x_min, x_max, cols)
    y = np.linspace(y_min, y_max, rows)
    target_x, target_y = np.meshgrid(x, y)
    
    valid_mask = ~np.isnan(data) & ~np.isnan(src_lats) & ~np.isnan(src_lons)
    
    if np.any(valid_mask):
        src_points = np.column_stack([
            src_x[valid_mask].ravel(),
            src_y[valid_mask].ravel()
        ])
        src_values = data[valid_mask].ravel()
        
        target_points = np.column_stack([
            target_x.ravel(),
            target_y.ravel()
        ])
        
        reprojected = griddata(src_points, src_values, target_points,
                               method=interpolation_method, fill_value=np.nan)
        reprojected = reprojected.reshape(target_shape)
        
        nearest = griddata(src_points, src_values, target_points,
                           method='nearest')
        nearest = nearest.reshape(target_shape)
        nan_mask = np.isnan(reprojected)
        reprojected[nan_mask] = nearest[nan_mask]
    else:
        reprojected = np.full(target_shape, np.nan)
    
    target_lons, target_lats = transformer_to_latlon.transform(target_x, target_y)
    
    return {
        'data': reprojected,
        'x': target_x,
        'y': target_y,
        'lats': target_lats,
        'lons': target_lons,
        'proj': target_proj_str,
        'resolution': target_resolution
    }


def denoise_image(image, method='gaussian', **kwargs):
    """
    Denoise brightness temperature image.
    
    Parameters
    ----------
    image : 2D array
        Input image
    method : str
        'gaussian', 'median', 'wavelet', 'bilateral', 'anisotropic'
    **kwargs
        Additional parameters for the denoising method
        
    Returns
    -------
    2D array
        Denoised image
    """
    image = np.asarray(image, dtype=np.float64)
    nan_mask = np.isnan(image)
    
    if np.any(nan_mask):
        filled_image = _fill_nans(image)
    else:
        filled_image = image.copy()
    
    if method == 'gaussian':
        sigma = kwargs.get('sigma', 1.5)
        denoised = ndimage.gaussian_filter(filled_image, sigma=sigma)
    
    elif method == 'median':
        size = kwargs.get('size', 3)
        denoised = ndimage.median_filter(filled_image, size=size)
    
    elif method == 'wavelet':
        sigma = estimate_sigma(filled_image, average_sigmas=True)
        sigma = kwargs.get('sigma', sigma * 0.5)
        denoised = denoise_wavelet(
            filled_image,
            sigma=sigma,
            wavelet=kwargs.get('wavelet', 'db4'),
            mode=kwargs.get('mode', 'soft'),
            method=kwargs.get('method', 'BayesShrink')
        )
    
    elif method == 'bilateral':
        img_norm = cv2.normalize(filled_image, None, 0, 255, cv2.NORM_MINMAX)
        img_norm = img_norm.astype(np.uint8)
        d = kwargs.get('d', 9)
        sigma_color = kwargs.get('sigma_color', 75)
        sigma_space = kwargs.get('sigma_space', 75)
        denoised_norm = cv2.bilateralFilter(img_norm, d, sigma_color, sigma_space)
        denoised = cv2.normalize(denoised_norm.astype(np.float64), None,
                                 np.nanmin(filled_image), np.nanmax(filled_image),
                                 cv2.NORM_MINMAX)
    
    elif method == 'anisotropic':
        denoised = _anisotropic_diffusion(
            filled_image,
            niter=kwargs.get('niter', 10),
            kappa=kwargs.get('kappa', 50),
            gamma=kwargs.get('gamma', 0.25)
        )
    
    else:
        raise ValueError(f'Unknown denoising method: {method}')
    
    if np.any(nan_mask):
        denoised[nan_mask] = np.nan
    
    return denoised


def _fill_nans(image):
    """Fill NaN values using nearest neighbor interpolation."""
    mask = np.isnan(image)
    if not np.any(mask):
        return image
    
    filled = image.copy()
    
    ind = ndimage.distance_transform_edt(mask, return_distances=False,
                                         return_indices=True)
    filled[mask] = image[tuple(ind[:, mask])]
    
    return filled


def _anisotropic_diffusion(img, niter=10, kappa=50, gamma=0.25, option=1):
    """
    Perona-Malik anisotropic diffusion.
    
    Parameters
    ----------
    img : 2D array
        Input image
    niter : int
        Number of iterations
    kappa : float
        Conduction coefficient
    gamma : float
        Time step (0 <= gamma <= 0.25 for stability)
    option : int
        1 for exponential, 2 for quadratic
        
    Returns
    -------
    2D array
        Diffused image
    """
    img = img.astype(np.float64)
    rows, cols = img.shape
    
    for i in range(niter):
        imgN = np.zeros_like(img)
        imgS = np.zeros_like(img)
        imgE = np.zeros_like(img)
        imgW = np.zeros_like(img)
        
        imgN[1:, :] = img[:-1, :]
        imgS[:-1, :] = img[1:, :]
        imgE[:, 1:] = img[:, :-1]
        imgW[:, :-1] = img[:, 1:]
        
        deltaN = imgN - img
        deltaS = imgS - img
        deltaE = imgE - img
        deltaW = imgW - img
        
        if option == 1:
            cN = np.exp(-(np.abs(deltaN) / kappa) ** 2)
            cS = np.exp(-(np.abs(deltaS) / kappa) ** 2)
            cE = np.exp(-(np.abs(deltaE) / kappa) ** 2)
            cW = np.exp(-(np.abs(deltaW) / kappa) ** 2)
        else:
            cN = 1.0 / (1.0 + (np.abs(deltaN) / kappa) ** 2)
            cS = 1.0 / (1.0 + (np.abs(deltaS) / kappa) ** 2)
            cE = 1.0 / (1.0 + (np.abs(deltaE) / kappa) ** 2)
            cW = 1.0 / (1.0 + (np.abs(deltaW) / kappa) ** 2)
        
        img = img + gamma * (cN * deltaN + cS * deltaS + cE * deltaE + cW * deltaW)
    
    return img


def normalize_image(image, method='minmax'):
    """
    Normalize image intensity.
    
    Parameters
    ----------
    image : 2D array
        Input image
    method : str
        'minmax' or 'zscore'
        
    Returns
    -------
    2D array
        Normalized image
    """
    image = np.asarray(image, dtype=np.float64)
    valid_mask = ~np.isnan(image)
    
    if method == 'minmax':
        vmin = np.nanmin(image)
        vmax = np.nanmax(image)
        normalized = np.zeros_like(image)
        normalized[valid_mask] = (image[valid_mask] - vmin) / (vmax - vmin + 1e-10)
    
    elif method == 'zscore':
        mean = np.nanmean(image)
        std = np.nanstd(image)
        normalized = np.zeros_like(image)
        normalized[valid_mask] = (image[valid_mask] - mean) / (std + 1e-10)
    
    else:
        raise ValueError(f'Unknown normalization method: {method}')
    
    normalized[~valid_mask] = np.nan
    return normalized


def enhance_contrast(image, clip_limit=2.0, tile_grid_size=(8, 8)):
    """
    Enhance image contrast using CLAHE.
    
    Parameters
    ----------
    image : 2D array
        Input image
    clip_limit : float
        CLAHE clip limit
    tile_grid_size : tuple
        CLAHE tile grid size
        
    Returns
    -------
    2D array
        Contrast-enhanced image
    """
    image = np.asarray(image, dtype=np.float64)
    nan_mask = np.isnan(image)
    
    vmin, vmax = np.nanmin(image), np.nanmax(image)
    img_norm = np.uint8(255 * (image - vmin) / (vmax - vmin + 1e-10))
    img_norm[nan_mask] = 0
    
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    enhanced = clahe.apply(img_norm)
    
    result = vmin + (enhanced.astype(np.float64) / 255.0) * (vmax - vmin)
    result[nan_mask] = np.nan
    
    return result


def compute_brightness_gradient(image):
    """
    Compute brightness temperature gradient magnitude.
    
    Parameters
    ----------
    image : 2D array
        Input brightness temperature image
        
    Returns
    -------
    2D array
        Gradient magnitude
    """
    image = np.asarray(image, dtype=np.float64)
    nan_mask = np.isnan(image)
    
    if np.any(nan_mask):
        from scipy.ndimage import gaussian_filter
        filled = image.copy()
        filled[nan_mask] = np.nanmean(image)
    else:
        filled = image
    
    grad_x = cv2.Sobel(filled, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(filled, cv2.CV_64F, 0, 1, ksize=3)
    
    gradient = np.sqrt(grad_x**2 + grad_y**2)
    gradient[nan_mask] = np.nan
    
    return gradient


def preprocess_pipeline(tb_data, denoise_method='gaussian',
                        denoise_kwargs=None, target_resolution=12.5,
                        hemisphere='north', target_shape=None,
                        do_normalize=False, do_enhance=False,
                        interpolation_method='linear',
                        detect_res=True):
    """
    Complete preprocessing pipeline.
    
    Parameters
    ----------
    tb_data : BrightnessTemperatureData
        Input data object
    denoise_method : str
        Denoising method to use
    denoise_kwargs : dict
        Parameters for denoising
    target_resolution : float
        Target resolution in km
    hemisphere : str
        'north' or 'south'
    target_shape : tuple
        Target (rows, cols) for reprojection
    do_normalize : bool
        Whether to normalize the image
    do_enhance : bool
        Whether to enhance contrast
    interpolation_method : str
        Interpolation method for reprojection
    detect_res : bool
        Whether to detect and store original resolution
        
    Returns
    -------
    dict
        Preprocessing results including reprojected and denoised data
    """
    denoise_kwargs = denoise_kwargs or {}
    
    resolution_info = None
    if detect_res:
        resolution_info = detect_resolution(tb_data.lats, tb_data.lons)
        print(f'Detected resolution: {resolution_info["resolution_km"]:.1f} km '
              f'({resolution_info["resolution_class"]})')
    
    print('Reprojecting to polar azimuthal equal-area grid...')
    reproj_result = reproject_to_polar_ae(
        tb_data.data,
        tb_data.lats,
        tb_data.lons,
        target_resolution=target_resolution,
        hemisphere=hemisphere,
        target_shape=target_shape,
        interpolation_method=interpolation_method
    )
    
    print(f'Denoising using {denoise_method} method...')
    denoised = denoise_image(
        reproj_result['data'],
        method=denoise_method,
        **denoise_kwargs
    )
    
    if do_enhance:
        print('Enhancing contrast...')
        denoised = enhance_contrast(denoised)
    
    if do_normalize:
        print('Normalizing image...')
        denoised = normalize_image(denoised)
    
    gradient = compute_brightness_gradient(denoised)
    
    result = reproj_result.copy()
    result['data_raw'] = reproj_result['data']
    result['data'] = denoised
    result['gradient'] = gradient
    result['timestamp'] = tb_data.timestamp
    result['sensor'] = tb_data.sensor
    result['channel'] = tb_data.channel
    result['original_resolution'] = resolution_info
    
    return result
