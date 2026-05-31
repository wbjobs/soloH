import numpy as np
from tifffile import imread, imwrite
from pathlib import Path
from typing import Tuple, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_tiff_stack(filepath: str) -> np.ndarray:
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    logger.info(f"Loading TIFF stack from {filepath}")
    stack = imread(str(filepath))
    
    if stack.ndim == 2:
        stack = stack[np.newaxis, ...]
    
    logger.info(f"Loaded stack shape: {stack.shape}, dtype: {stack.dtype}")
    return stack


def save_tiff_stack(images: np.ndarray, filepath: str) -> None:
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving TIFF stack to {filepath}")
    imwrite(str(filepath), images)


def normalize_image(image: np.ndarray, 
                    lower_percentile: float = 0.5,
                    upper_percentile: float = 99.5) -> np.ndarray:
    lower = np.percentile(image, lower_percentile)
    upper = np.percentile(image, upper_percentile)
    
    if upper == lower:
        return np.zeros_like(image, dtype=np.float32)
    
    normalized = np.clip(image, lower, upper)
    normalized = (normalized - lower) / (upper - lower)
    
    return normalized.astype(np.float32)


def normalize_stack(stack: np.ndarray, 
                    lower_percentile: float = 0.5,
                    upper_percentile: float = 99.5,
                    by_frame: bool = True) -> np.ndarray:
    if by_frame:
        normalized = np.zeros_like(stack, dtype=np.float32)
        for i in range(stack.shape[0]):
            normalized[i] = normalize_image(stack[i], lower_percentile, upper_percentile)
    else:
        normalized = normalize_image(stack, lower_percentile, upper_percentile)
    
    return normalized


def instance_mask_to_centroids(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    labels = np.unique(mask)
    labels = labels[labels != 0]
    
    centroids = []
    areas = []
    
    for label in labels:
        y, x = np.where(mask == label)
        if len(y) > 0:
            centroids.append([np.mean(y), np.mean(x)])
            areas.append(len(y))
    
    return np.array(centroids), np.array(areas)


def instance_mask_to_bboxes(mask: np.ndarray) -> np.ndarray:
    labels = np.unique(mask)
    labels = labels[labels != 0]
    
    bboxes = []
    for label in labels:
        y, x = np.where(mask == label)
        if len(y) > 0:
            bboxes.append([y.min(), x.min(), y.max(), x.max()])
    
    return np.array(bboxes)


def extract_mask_properties(mask: np.ndarray) -> dict:
    from skimage.measure import regionprops
    
    properties = {}
    regions = regionprops(mask)
    
    for region in regions:
        props = {
            'area': region.area,
            'centroid': region.centroid,
            'bbox': region.bbox,
            'eccentricity': region.eccentricity,
            'solidity': region.solidity,
            'extent': region.extent,
            'orientation': region.orientation,
            'major_axis_length': region.major_axis_length,
            'minor_axis_length': region.minor_axis_length,
            'perimeter': region.perimeter,
            'label': region.label,
        }
        properties[region.label] = props
    
    return properties
