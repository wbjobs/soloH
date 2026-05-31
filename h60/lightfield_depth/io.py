"""
Light Field Image I/O Module

Supports reading:
- LFR (Lytro Light Field Raw) format
- White-image corrected light field images
- Standard image formats for pre-processed data
"""

import os
import struct
import numpy as np
from PIL import Image
import cv2


class LightFieldImage:
    def __init__(self):
        self.raw_image = None
        self.white_image = None
        self.corrected_image = None
        self.metadata = {}
        self.mla_params = {}  # Micro-lens array parameters

    def get_image(self):
        if self.corrected_image is not None:
            return self.corrected_image
        return self.raw_image

    def get_shape(self):
        img = self.get_image()
        if img is not None:
            return img.shape
        return None


def read_lfr(file_path):
    """
    Read Lytro Light Field Raw (LFR) format.
    
    LFR is a TIFF-based format with metadata stored in TIFF tags.
    This implementation provides basic LFR parsing.
    
    Parameters:
        file_path: Path to .lfr file
        
    Returns:
        LightFieldImage object
    """
    lf = LightFieldImage()
    
    try:
        img = Image.open(file_path)
        lf.raw_image = np.array(img)
        
        try:
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    lf.metadata[str(tag_id)] = str(value)
        except:
            pass
            
        if hasattr(img, 'info'):
            for key, value in img.info.items():
                if key not in lf.metadata:
                    lf.metadata[key] = str(value)
                    
        if lf.raw_image is not None:
            h, w = lf.raw_image.shape[:2]
            lf.mla_params['image_width'] = w
            lf.mla_params['image_height'] = h
            
    except Exception as e:
        raise IOError(f"Failed to read LFR file: {e}")
        
    return lf


def read_corrected_image(file_path):
    """
    Read a white-image corrected light field image.
    
    Parameters:
        file_path: Path to corrected image file
        
    Returns:
        LightFieldImage object
    """
    lf = LightFieldImage()
    
    try:
        img = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            img = np.array(Image.open(file_path))
            
        if len(img.shape) == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
        lf.corrected_image = img
        lf.raw_image = img
        
        h, w = img.shape[:2]
        lf.mla_params['image_width'] = w
        lf.mla_params['image_height'] = h
        
    except Exception as e:
        raise IOError(f"Failed to read corrected image: {e}")
        
    return lf


def read_white_image(file_path):
    """
    Read white reference image for calibration.
    
    Parameters:
        file_path: Path to white image
        
    Returns:
        White image as numpy array
    """
    try:
        img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            img = np.array(Image.open(file_path).convert('L'))
        return img.astype(np.float32)
    except Exception as e:
        raise IOError(f"Failed to read white image: {e}")


def read_light_field(file_path, white_image_path=None):
    """
    Main entry point for reading light field images.
    
    Automatically detects format based on file extension.
    
    Parameters:
        file_path: Path to light field image
        white_image_path: Optional path to white reference image
        
    Returns:
        LightFieldImage object
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.lfr':
        lf = read_lfr(file_path)
    elif ext in ['.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp']:
        lf = read_corrected_image(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")
    
    if white_image_path is not None:
        white_img = read_white_image(white_image_path)
        lf.white_image = white_img
        lf = apply_white_correction(lf, white_img)
        
    return lf


def apply_white_correction(lf, white_image):
    """
    Apply white image correction to raw light field.
    
    Parameters:
        lf: LightFieldImage object
        white_image: White reference image
        
    Returns:
        Corrected LightFieldImage object
    """
    if lf.raw_image is None:
        raise ValueError("No raw image to correct")
    
    raw = lf.raw_image.astype(np.float32)
    
    if len(raw.shape) == 3:
        white_norm = white_image / (white_image.max() + 1e-8)
        for c in range(raw.shape[2]):
            raw[:, :, c] = raw[:, :, c] / (white_norm + 1e-8)
    else:
        white_norm = white_image / (white_image.max() + 1e-8)
        raw = raw / (white_norm + 1e-8)
    
    raw = np.clip(raw, 0, 255).astype(np.uint8)
    lf.corrected_image = raw
    
    return lf


def save_image(image, file_path, normalize=False):
    """
    Save an image (depth map, confidence map, etc.)
    
    Parameters:
        image: Image as numpy array
        file_path: Output path
        normalize: If True, normalize to 0-255 range
    """
    if normalize and image.dtype != np.uint8:
        img_norm = (image - image.min()) / (image.max() - image.min() + 1e-8)
        img_save = (img_norm * 255).astype(np.uint8)
    else:
        img_save = image.astype(np.uint8) if image.dtype != np.uint8 else image
    
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    
    if len(img_save.shape) == 2:
        Image.fromarray(img_save, mode='L').save(file_path)
    elif len(img_save.shape) == 3 and img_save.shape[2] == 3:
        Image.fromarray(img_save, mode='RGB').save(file_path)
    else:
        cv2.imwrite(file_path, img_save)


def save_disparity_map(disparity, file_path, colormap=True):
    """
    Save disparity map with optional colormap for visualization.
    
    Parameters:
        disparity: Disparity map as numpy array
        file_path: Output path
        colormap: If True, apply jet colormap
    """
    disp_norm = (disparity - disparity.min()) / (disparity.max() - disparity.min() + 1e-8)
    disp_8bit = (disp_norm * 255).astype(np.uint8)
    
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    
    if colormap:
        disp_color = cv2.applyColorMap(disp_8bit, cv2.COLORMAP_JET)
        cv2.imwrite(file_path, disp_color)
    else:
        Image.fromarray(disp_8bit, mode='L').save(file_path)
