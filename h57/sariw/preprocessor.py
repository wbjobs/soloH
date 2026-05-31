import numpy as np
import cv2
from scipy import ndimage
from scipy.signal import wiener
from skimage import exposure, restoration
from dataclasses import dataclass
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingParams:
    """Parameters for image preprocessing."""
    denoise_method: str = 'bilateral'
    denoise_strength: int = 5
    contrast_method: str = 'clahe'
    clahe_clip_limit: float = 2.0
    clahe_grid_size: Tuple[int, int] = (8, 8)
    gamma: float = 1.0
    remove_background: bool = True
    background_kernel_size: int = 51
    speckle_filter: bool = True
    speckle_sigma: float = 1.0


class Preprocessor:
    """Image preprocessing for SAR images."""

    def __init__(self, params: Optional[PreprocessingParams] = None):
        """
        Initialize preprocessor.

        Args:
            params: Preprocessing parameters
        """
        self.params = params or PreprocessingParams()

    def process(self, image: np.ndarray) -> np.ndarray:
        """
        Full preprocessing pipeline.

        Args:
            image: Input SAR image (2D numpy array)

        Returns:
            Preprocessed image
        """
        logger.info("Starting image preprocessing...")

        img = image.copy()

        valid_mask = ~np.isnan(img)
        img_filled = np.where(valid_mask, img, np.nanmean(img))

        img_min = np.nanmin(img_filled)
        img_max = np.nanmax(img_filled)
        if img_max > img_min:
            img_normalized = (img_filled - img_min) / (img_max - img_min)
        else:
            img_normalized = img_filled * 0

        if self.params.speckle_filter:
            logger.info("  Applying speckle filtering...")
            img_normalized = self._speckle_filter(img_normalized)

        if self.params.denoise_method != 'none':
            logger.info(f"  Applying {self.params.denoise_method} denoising...")
            img_normalized = self._denoise(img_normalized)

        if self.params.contrast_method != 'none':
            logger.info(f"  Applying {self.params.contrast_method} contrast enhancement...")
            img_normalized = self._enhance_contrast(img_normalized)

        if self.params.gamma != 1.0:
            logger.info(f"  Applying gamma correction (gamma={self.params.gamma})...")
            img_normalized = self._gamma_correction(img_normalized, self.params.gamma)

        if self.params.remove_background:
            logger.info("  Removing background...")
            img_normalized = self._remove_background(img_normalized)

        img_normalized = np.clip(img_normalized, 0, 1)

        logger.info("Preprocessing completed.")
        return img_normalized

    def _speckle_filter(self, image: np.ndarray) -> np.ndarray:
        """
        Apply speckle filtering (Lee filter or Frost filter).

        Args:
            image: Input image

        Returns:
            Filtered image
        """
        sigma = self.params.speckle_sigma
        image_8bit = (image * 255).astype(np.uint8)

        lee_filtered = cv2.fastNlMeansDenoising(image_8bit, h=sigma * 10,
                                                templateWindowSize=7,
                                                searchWindowSize=21)

        return lee_filtered.astype(np.float32) / 255.0

    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """
        Apply denoising.

        Args:
            image: Input image

        Returns:
            Denoised image
        """
        method = self.params.denoise_method.lower()
        strength = self.params.denoise_strength

        if method == 'bilateral':
            image_8bit = (image * 255).astype(np.uint8)
            denoised = cv2.bilateralFilter(image_8bit, d=strength * 2,
                                           sigmaColor=strength * 10,
                                           sigmaSpace=strength * 10)
            return denoised.astype(np.float32) / 255.0
        elif method == 'gaussian':
            return cv2.GaussianBlur(image, (strength * 2 + 1, strength * 2 + 1), 0)
        elif method == 'median':
            image_8bit = (image * 255).astype(np.uint8)
            denoised = cv2.medianBlur(image_8bit, strength * 2 + 1)
            return denoised.astype(np.float32) / 255.0
        elif method == 'wiener':
            return wiener(image, (strength * 2 + 1, strength * 2 + 1))
        elif method == 'tv':
            return restoration.denoise_tv_chambolle(image, weight=strength * 0.1)
        else:
            logger.warning(f"Unknown denoise method: {method}, skipping")
            return image

    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance image contrast.

        Args:
            image: Input image

        Returns:
            Contrast-enhanced image
        """
        method = self.params.contrast_method.lower()

        if method == 'clahe':
            image_8bit = (image * 255).astype(np.uint8)
            clahe = cv2.createCLAHE(clipLimit=self.params.clahe_clip_limit,
                                    tileGridSize=self.params.clahe_grid_size)
            enhanced = clahe.apply(image_8bit)
            return enhanced.astype(np.float32) / 255.0
        elif method == 'equalize':
            image_8bit = (image * 255).astype(np.uint8)
            enhanced = cv2.equalizeHist(image_8bit)
            return enhanced.astype(np.float32) / 255.0
        elif method == 'percentile':
            p2, p98 = np.percentile(image, (2, 98))
            return exposure.rescale_intensity(image, in_range=(p2, p98))
        elif method == 'adaptive':
            return exposure.equalize_adapthist(image, kernel_size=8)
        else:
            logger.warning(f"Unknown contrast method: {method}, skipping")
            return image

    def _gamma_correction(self, image: np.ndarray, gamma: float) -> np.ndarray:
        """
        Apply gamma correction.

        Args:
            image: Input image
            gamma: Gamma value

        Returns:
            Gamma-corrected image
        """
        return np.power(image, gamma)

    def _remove_background(self, image: np.ndarray) -> np.ndarray:
        """
        Remove slow-varying background using morphological operations.

        Args:
            image: Input image

        Returns:
            Background-removed image
        """
        kernel_size = self.params.background_kernel_size

        image_8bit = (image * 255).astype(np.uint8)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

        background = cv2.morphologyEx(image_8bit, cv2.MORPH_OPEN, kernel)
        background = cv2.GaussianBlur(background, (kernel_size, kernel_size), 0)

        result = image_8bit.astype(np.float32) - background.astype(np.float32)
        result = (result - np.min(result)) / (np.max(result) - np.min(result) + 1e-8)

        return result

    def detect_valid_regions(self, image: np.ndarray, threshold: float = 0.01) -> np.ndarray:
        """
        Detect valid (non-background) regions.

        Args:
            image: Input image
            threshold: Variance threshold

        Returns:
            Binary mask of valid regions
        """
        local_var = ndimage.generic_filter(image, np.var, size=15)
        return local_var > threshold

    def estimate_noise_level(self, image: np.ndarray) -> float:
        """
        Estimate noise level in the image.

        Args:
            image: Input image

        Returns:
            Estimated noise standard deviation
        """
        return restoration.estimate_sigma(image)

    def compute_image_statistics(self, image: np.ndarray) -> dict:
        """
        Compute image statistics.

        Args:
            image: Input image

        Returns:
            Dictionary of statistics
        """
        valid_data = image[~np.isnan(image)]
        return {
            'mean': float(np.mean(valid_data)),
            'std': float(np.std(valid_data)),
            'min': float(np.min(valid_data)),
            'max': float(np.max(valid_data)),
            'median': float(np.median(valid_data)),
            'snr': float(np.mean(valid_data) / (np.std(valid_data) + 1e-8))
        }
