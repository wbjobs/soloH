import os
import json
import cv2
import numpy as np
from typing import Tuple, Dict, Optional, Union, List

BBox = Tuple[int, int, int, int]
ComponentImage = np.ndarray

class ImagePreprocessor:
    def __init__(self):
        self.default_options = {
            "rotate_angle": 0,
            "binarize_threshold": 127,
            "denoise_kernel_size": 3,
            "contrast_alpha": 1.0,
            "vertical_layout": True
        }

    def rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        if angle == 0:
            return image
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        rotated = cv2.warpAffine(image, M, (new_w, new_h),
                                 flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
        return rotated

    def binarize(self, image: np.ndarray, threshold: int = 127) -> np.ndarray:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return binary

    def denoise(self, image: np.ndarray, kernel_size: int = 3) -> np.ndarray:
        if len(image.shape) == 3:
            denoised = cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
        else:
            denoised = cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        denoised = cv2.morphologyEx(denoised, cv2.MORPH_OPEN, kernel)
        denoised = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel)
        return denoised

    def adjust_contrast(self, image: np.ndarray, alpha: float = 1.0) -> np.ndarray:
        if alpha == 1.0:
            return image
        new_image = cv2.convertScaleAbs(image, alpha=alpha, beta=0)
        return new_image

    def detect_skew_angle(self, image: np.ndarray) -> float:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100)
        if lines is None:
            return 0.0
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
            angles.append(angle)
        median_angle = np.median(angles)
        return median_angle

    def correct_vertical_skew(self, image: np.ndarray) -> np.ndarray:
        angle = self.detect_skew_angle(image)
        if abs(angle) < 0.5:
            return image
        return self.rotate_image(image, -angle)

    def preprocess_pipeline(
        self,
        image_path: Optional[str] = None,
        image: Optional[np.ndarray] = None,
        options: Optional[Dict] = None
    ) -> Dict[str, Union[np.ndarray, List[BBox]]]:
        opts = self.default_options.copy()
        if options:
            opts.update(options)
        if image is None and image_path is not None:
            image = cv2.imread(image_path, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"Cannot read image from path: {image_path}")
        if image is None:
            raise ValueError("Either image_path or image must be provided")
        processed = image.copy()
        if opts.get("auto_rotate", False):
            angle = self.detect_skew_angle(processed)
            processed = self.rotate_image(processed, opts["rotate_angle"] - angle)
        else:
            processed = self.rotate_image(processed, opts["rotate_angle"])
        if opts.get("vertical_layout", True):
            processed = self.correct_vertical_skew(processed)
        processed = self.denoise(processed, opts["denoise_kernel_size"])
        processed = self.adjust_contrast(processed, opts["contrast_alpha"])
        binary = self.binarize(processed, opts["binarize_threshold"])
        text_lines = self.detect_text_lines(binary, vertical=opts["vertical_layout"])
        return {
            "original": image,
            "processed": processed,
            "binary": binary,
            "text_lines": text_lines
        }

    def detect_text_lines(self, binary: np.ndarray, vertical: bool = True) -> List[BBox]:
        if vertical:
            projection = np.sum(binary, axis=0)
        else:
            projection = np.sum(binary, axis=1)
        threshold = np.mean(projection) * 0.3
        line_positions = []
        in_line = False
        line_start = 0
        for i, val in enumerate(projection):
            if val > threshold and not in_line:
                in_line = True
                line_start = i
            elif val <= threshold and in_line:
                in_line = False
                line_positions.append((line_start, i))
        if in_line:
            line_positions.append((line_start, len(projection)))
        bboxes = []
        h, w = binary.shape[:2]
        for start, end in line_positions:
            if vertical:
                x1, x2 = max(0, start - 5), min(w, end + 5)
                line_region = binary[:, x1:x2]
                row_proj = np.sum(line_region, axis=1)
                y_indices = np.where(row_proj > 0)[0]
                if len(y_indices) > 0:
                    y1, y2 = y_indices[0], y_indices[-1]
                    bboxes.append((x1, y1, x2, y2))
            else:
                y1, y2 = max(0, start - 5), min(h, end + 5)
                line_region = binary[y1:y2, :]
                col_proj = np.sum(line_region, axis=0)
                x_indices = np.where(col_proj > 0)[0]
                if len(x_indices) > 0:
                    x1, x2 = x_indices[0], x_indices[-1]
                    bboxes.append((x1, y1, x2, y2))
        return bboxes

    def save_image(self, image: np.ndarray, output_path: str) -> None:
        cv2.imwrite(output_path, image)

    def resize_image(self, image: np.ndarray, target_size: Tuple[int, int]) -> np.ndarray:
        return cv2.resize(image, target_size, interpolation=cv2.INTER_AREA)

    def normalize_image(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        normalized = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX)
        return normalized
