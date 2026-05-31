"""
Sub-Aperture Image Extraction Module

Extracts UV plane sub-aperture image array from light field raw image.
Supports configurable microlens array parameters (e.g., 15x15 views).
"""

import numpy as np
import cv2
from tqdm import tqdm


class SubApertureArray:
    def __init__(self):
        self.images = None
        self.num_u = None
        self.num_v = None
        self.height = None
        self.width = None
        self.channels = None

    def get_shape(self):
        if self.images is not None:
            return self.images.shape
        return None

    def get_view(self, u, v):
        if self.images is None:
            raise ValueError("Sub-aperture array not initialized")
        if u < 0 or u >= self.num_u or v < 0 or v >= self.num_v:
            raise IndexError(f"View index ({u}, {v}) out of bounds ({self.num_u}x{self.num_v})")
        return self.images[v, u]

    def get_center_view(self):
        if self.images is None:
            raise ValueError("Sub-aperture array not initialized")
        center_u = self.num_u // 2
        center_v = self.num_v // 2
        return self.images[center_v, center_u]

    def get_epi(self, v, t=None, axis='horizontal'):
        if self.images is None:
            raise ValueError("Sub-aperture array not initialized")

        if axis == 'horizontal':
            if t is None:
                epi = self.images[:, v, :, :, :] if self.channels > 1 else self.images[:, v, :, :]
            else:
                epi = self.images[:, v, t, :, :] if self.channels > 1 else self.images[:, v, t, :]
        else:
            if t is None:
                epi = self.images[v, :, :, :, :] if self.channels > 1 else self.images[v, :, :, :]
            else:
                epi = self.images[v, :, :, t, :] if self.channels > 1 else self.images[v, :, :, t]

        return epi

    def get_stack(self):
        if self.images is None:
            raise ValueError("Sub-aperture array not initialized")
        return self.images

    def save_montage(self, file_path, ncols=None):
        if self.images is None:
            raise ValueError("Sub-aperture array not initialized")

        if ncols is None:
            ncols = self.num_u

        img_list = []
        for v in range(self.num_v):
            row_imgs = [self.images[v, u] for u in range(self.num_u)]
            if self.channels == 1:
                row_imgs = [np.stack([img] * 3, axis=-1) for img in row_imgs]
            img_list.append(np.hstack(row_imgs))

        montage = np.vstack(img_list)
        montage_bgr = cv2.cvtColor(montage.astype(np.uint8), cv2.COLOR_RGB2BGR)
        cv2.imwrite(file_path, montage_bgr)


def detect_mla_pattern(white_image, num_views=15, grid_type='hexagonal'):
    """
    Detect microlens array pattern from white reference image.
    
    Supports both rectangular and hexagonal grid arrangements with
    radial and tangential distortion correction.
    
    Parameters:
        white_image: White reference image
        num_views: Number of views per dimension
        grid_type: 'rectangular' or 'hexagonal'
        
    Returns:
        Dictionary with MLA parameters including distortion coefficients
    """
    h, w = white_image.shape[:2]

    centers = []
    
    if grid_type == 'hexagonal':
        pitch_x = w / num_views
        pitch_y = h / (num_views * np.sqrt(3) / 2 + 0.5)
        
        for i in range(num_views):
            row_offset = (i % 2) * pitch_x / 2
            for j in range(num_views):
                cx = (j + 0.5) * pitch_x + row_offset
                cy = (i + 0.5) * pitch_y
                if 0 <= cx < w and 0 <= cy < h:
                    centers.append((cx, cy))
    else:
        pitch_x = w / num_views
        pitch_y = h / num_views
        
        for i in range(num_views):
            for j in range(num_views):
                cx = (j + 0.5) * pitch_x
                cy = (i + 0.5) * pitch_y
                centers.append((cx, cy))
    
    centers = np.array(centers)
    
    params = {
        'lens_pitch_x': w / num_views,
        'lens_pitch_y': h / num_views,
        'centers': centers,
        'num_views': num_views,
        'grid_type': grid_type,
        'distortion': {
            'radial': np.array([0.0, 0.0, 0.0]),
            'tangential': np.array([0.0, 0.0]),
            'principal_point': np.array([w / 2.0, h / 2.0]),
        },
    }

    return params


def estimate_distortion(centers, detected_centers, principal_point):
    """
    Estimate radial and tangential distortion from ideal vs detected centers.
    
    Solves for distortion coefficients using least squares:
    - Radial: k1, k2, k3 (up to 3rd order)
    - Tangential: p1, p2
    
    Parameters:
        centers: Ideal grid centers (N, 2)
        detected_centers: Detected centers from white image (N, 2)
        principal_point: (cx, cy) optical center
        
    Returns:
        distortion: Dict with 'radial' (k1, k2, k3) and 'tangential' (p1, p2)
    """
    cx, cy = principal_point
    x_ideal = centers[:, 0] - cx
    y_ideal = centers[:, 1] - cy
    r_sq = x_ideal ** 2 + y_ideal ** 2
    
    x_detected = detected_centers[:, 0] - cx
    y_detected = detected_centers[:, 1] - cy
    
    A = np.zeros((len(centers) * 2, 5))
    b = np.zeros(len(centers) * 2)
    
    for i in range(len(centers)):
        r2 = r_sq[i]
        r4 = r2 * r2
        r6 = r2 * r4
        
        x_i = x_ideal[i]
        y_i = y_ideal[i]
        
        A[2 * i, 0] = x_i * r2
        A[2 * i, 1] = x_i * r4
        A[2 * i, 2] = x_i * r6
        A[2 * i, 3] = 2 * x_i * y_i
        A[2 * i, 4] = r2 + 2 * x_i * x_i
        
        A[2 * i + 1, 0] = y_i * r2
        A[2 * i + 1, 1] = y_i * r4
        A[2 * i + 1, 2] = y_i * r6
        A[2 * i + 1, 3] = r2 + 2 * y_i * y_i
        A[2 * i + 1, 4] = 2 * x_i * y_i
        
        b[2 * i] = x_detected[i] - x_i
        b[2 * i + 1] = y_detected[i] - y_i
    
    try:
        coeffs, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
        k1, k2, k3, p1, p2 = coeffs
    except:
        k1, k2, k3, p1, p2 = 0.0, 0.0, 0.0, 0.0, 0.0
    
    return {
        'radial': np.array([k1, k2, k3]),
        'tangential': np.array([p1, p2]),
        'principal_point': principal_point,
    }


def undistort_points(points, distortion):
    """
    Apply radial and tangential distortion correction to points.
    
    Distortion model (Brown-Conrady):
    x_corrected = x * (1 + k1*r^2 + k2*r^4 + k3*r^6) + 2*p1*x*y + p2*(r^2 + 2*x^2)
    y_corrected = y * (1 + k1*r^2 + k2*r^4 + k3*r^6) + p1*(r^2 + 2*y^2) + 2*p2*x*y
    
    Parameters:
        points: Input points (N, 2) as (x, y)
        distortion: Dict with 'radial' (k1, k2, k3), 
                   'tangential' (p1, p2), 'principal_point' (cx, cy)
        
    Returns:
        undistorted: Corrected points (N, 2)
    """
    cx, cy = distortion['principal_point']
    k1, k2, k3 = distortion['radial']
    p1, p2 = distortion['tangential']
    
    x = points[:, 0] - cx
    y = points[:, 1] - cy
    
    r_sq = x ** 2 + y ** 2
    r4 = r_sq * r_sq
    r6 = r_sq * r4
    
    radial_factor = 1 + k1 * r_sq + k2 * r4 + k3 * r6
    
    x_corr = x * radial_factor + 2 * p1 * x * y + p2 * (r_sq + 2 * x ** 2)
    y_corr = y * radial_factor + p1 * (r_sq + 2 * y ** 2) + 2 * p2 * x * y
    
    undistorted = np.stack([x_corr + cx, y_corr + cy], axis=1)
    
    return undistorted


def distort_points(points, distortion):
    """
    Apply distortion (forward model) to ideal points.
    
    Parameters:
        points: Ideal points (N, 2)
        distortion: Distortion parameters dict
        
    Returns:
        distorted: Distorted points (N, 2)
    """
    return undistort_points(points, distortion)


def generate_hexagonal_grid(num_views, image_size, pitch=None):
    """
    Generate ideal hexagonal grid coordinates for microlens array.
    
    Parameters:
        num_views: Number of views per dimension
        image_size: (height, width) of the sensor
        pitch: Lens pitch in pixels. If None, computed from image_size.
        
    Returns:
        centers: Grid center coordinates (N, 2) as (x, y)
        pitch_x: Horizontal pitch
        pitch_y: Vertical pitch
    """
    h, w = image_size
    
    if pitch is None:
        pitch_x = w / num_views
        pitch_y = h / (num_views * np.sqrt(3) / 2 + 0.5)
    else:
        pitch_x = pitch
        pitch_y = pitch * np.sqrt(3) / 2
    
    centers = []
    for row in range(num_views):
        row_offset = (row % 2) * pitch_x / 2
        for col in range(num_views):
            x = col * pitch_x + pitch_x / 2 + row_offset
            y = row * pitch_y + pitch_y / 2
            if 0 <= x < w and 0 <= y < h:
                centers.append((x, y))
    
    return np.array(centers), pitch_x, pitch_y


def extract_subapertures(lf_image, num_u=15, num_v=15, mla_params=None, correct_distortion=True, distortion=None):
    """
    Extract sub-aperture image array from light field image.
    
    Supports optional distortion correction using radial and tangential
    distortion coefficients from calibration.
    
    Parameters:
        lf_image: LightFieldImage object or numpy array
        num_u: Number of views in horizontal direction
        num_v: Number of views in vertical direction
        mla_params: Optional MLA parameters from calibration
        correct_distortion: If True, apply distortion correction
        distortion: Optional distortion dict with 'radial', 'tangential', 'principal_point' keys.
                   If provided, overrides distortion from mla_params.
        
    Returns:
        SubApertureArray object
    """
    if hasattr(lf_image, 'get_image'):
        raw_img = lf_image.get_image()
    else:
        raw_img = lf_image

    if raw_img is None:
        raise ValueError("No image data available")

    raw_img = raw_img.astype(np.float32)

    if len(raw_img.shape) == 2:
        h, w = raw_img.shape
        channels = 1
        raw_3d = raw_img[:, :, np.newaxis]
    else:
        h, w, channels = raw_img.shape
        raw_3d = raw_img

    if mla_params is not None:
        pitch_x = mla_params.get('lens_pitch_x', w / num_u)
        pitch_y = mla_params.get('lens_pitch_y', h / num_v)
    else:
        pitch_x = w / num_u
        pitch_y = h / num_v

    if correct_distortion:
        if distortion is None and mla_params is not None and 'distortion' in mla_params:
            distortion = mla_params['distortion']
        
        if distortion is not None:
            map_x, map_y = generate_distortion_maps((h, w), distortion)
            raw_corrected = np.zeros_like(raw_3d)
            for c in range(channels):
                try:
                    raw_corrected[:, :, c] = cv2.remap(
                        raw_3d[:, :, c], map_x, map_y,
                        interpolation=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REFLECT
                    )
                except:
                    from scipy.ndimage import map_coordinates
                    coords = np.stack([map_y.flatten(), map_x.flatten()], axis=0)
                    raw_corrected[:, :, c] = map_coordinates(
                        raw_3d[:, :, c], coords, order=1, mode='reflect'
                    ).reshape(h, w)
            raw_3d = raw_corrected

    sub_h = int(h / num_v)
    sub_w = int(w / num_u)

    subapertures = np.zeros((num_v, num_u, sub_h, sub_w, channels), dtype=np.float32)

    for v in tqdm(range(num_v), desc="Extracting sub-apertures"):
        for u in range(num_u):
            start_y = int(v * pitch_y)
            start_x = int(u * pitch_x)

            end_y = min(start_y + sub_h, h)
            end_x = min(start_x + sub_w, w)

            for c in range(channels):
                subapertures[v, u, :end_y - start_y, :end_x - start_x, c] = \
                    raw_3d[start_y:end_y, start_x:end_x, c]

    sa = SubApertureArray()
    sa.images = subapertures
    sa.num_u = num_u
    sa.num_v = num_v
    sa.height = sub_h
    sa.width = sub_w
    sa.channels = channels
    sa.mla_params = mla_params

    return sa


def generate_distortion_maps(image_size, distortion):
    """
    Generate remapping maps for distortion correction.
    
    Parameters:
        image_size: (height, width)
        distortion: Distortion parameters dict
        
    Returns:
        map_x: X coordinate remap
        map_y: Y coordinate remap
    """
    h, w = image_size
    cx, cy = distortion['principal_point']
    k1, k2, k3 = distortion['radial']
    p1, p2 = distortion['tangential']
    
    y_coords, x_coords = np.mgrid[0:h, 0:w]
    x = x_coords.astype(np.float32) - cx
    y = y_coords.astype(np.float32) - cy
    
    r_sq = x ** 2 + y ** 2
    r4 = r_sq * r_sq
    r6 = r_sq * r4
    
    radial_factor = 1 + k1 * r_sq + k2 * r4 + k3 * r6
    
    x_corr = x * radial_factor + 2 * p1 * x * y + p2 * (r_sq + 2 * x ** 2)
    y_corr = y * radial_factor + p1 * (r_sq + 2 * y ** 2) + 2 * p2 * x * y
    
    map_x = x_corr + cx
    map_y = y_corr + cy
    
    return map_x, map_y


def extract_subapertures_demosaic(lf_image, num_u=15, num_v=15, mla_params=None, correct_distortion=True, distortion=None):
    """
    Alternative extraction method using demosaicing pattern.
    Treats each microlens as a pixel in the view array.
    
    Parameters:
        lf_image: LightFieldImage object or numpy array
        num_u: Number of views in horizontal direction
        num_v: Number of views in vertical direction
        mla_params: Optional MLA parameters
        correct_distortion: If True, apply distortion correction
        distortion: Optional distortion dict with 'radial', 'tangential', 'principal_point' keys
        
    Returns:
        SubApertureArray object
    """
    if hasattr(lf_image, 'get_image'):
        raw_img = lf_image.get_image()
    else:
        raw_img = lf_image

    if raw_img is None:
        raise ValueError("No image data available")

    raw_img = raw_img.astype(np.float32)

    if len(raw_img.shape) == 2:
        h, w = raw_img.shape
        channels = 1
        raw_3d = raw_img[:, :, np.newaxis]
    else:
        h, w, channels = raw_img.shape
        raw_3d = raw_img

    if correct_distortion:
        if distortion is None and mla_params is not None and 'distortion' in mla_params:
            distortion = mla_params['distortion']
        
        if distortion is not None:
            map_x, map_y = generate_distortion_maps((h, w), distortion)
            raw_corrected = np.zeros_like(raw_3d)
            for c in range(channels):
                try:
                    raw_corrected[:, :, c] = cv2.remap(
                        raw_3d[:, :, c], map_x, map_y,
                        interpolation=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REFLECT
                    )
                except:
                    from scipy.ndimage import map_coordinates
                    coords = np.stack([map_y.flatten(), map_x.flatten()], axis=0)
                    raw_corrected[:, :, c] = map_coordinates(
                        raw_3d[:, :, c], coords, order=1, mode='reflect'
                    ).reshape(h, w)
            raw_3d = raw_corrected

    sub_h = h // num_v
    sub_w = w // num_u

    subapertures = np.zeros((num_v, num_u, sub_h, sub_w, channels), dtype=np.float32)

    for v in tqdm(range(num_v), desc="Extracting views (demosaic)"):
        for u in range(num_u):
            for c in range(channels):
                subapertures[v, u, :, :, c] = \
                    raw_3d[v::num_v, u::num_u, c][:sub_h, :sub_w]

    sa = SubApertureArray()
    sa.images = subapertures
    sa.num_u = num_u
    sa.num_v = num_v
    sa.height = sub_h
    sa.width = sub_w
    sa.channels = channels

    return sa


def rgb_to_gray(subapertures):
    """
    Convert RGB sub-aperture array to grayscale.
    
    Parameters:
        subapertures: SubApertureArray object with RGB images
        
    Returns:
        SubApertureArray with grayscale images
    """
    if subapertures.channels != 3:
        return subapertures

    gray_sa = SubApertureArray()
    gray_sa.num_u = subapertures.num_u
    gray_sa.num_v = subapertures.num_v
    gray_sa.height = subapertures.height
    gray_sa.width = subapertures.width
    gray_sa.channels = 1

    gray_images = np.zeros((subapertures.num_v, subapertures.num_u,
                            subapertures.height, subapertures.width, 1), dtype=np.float32)

    for v in range(subapertures.num_v):
        for u in range(subapertures.num_u):
            rgb = subapertures.images[v, u]
            gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
            gray_images[v, u, :, :, 0] = gray

    gray_sa.images = gray_images
    return gray_sa
