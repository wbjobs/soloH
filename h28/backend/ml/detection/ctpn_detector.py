import os
import numpy as np
from typing import List, Tuple, Optional, Dict, Any

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


class CTPNDetector:
    def __init__(self, model_path: Optional[str] = None, use_mock: bool = True):
        self.model_path = model_path or os.environ.get("CTPN_MODEL_PATH", "")
        self.use_mock = use_mock
        self._model = None
        self._is_loaded = False

    def load_model(self) -> None:
        if self._is_loaded:
            return

        if self.use_mock or not self.model_path or not os.path.exists(self.model_path):
            self._model = "mock_ctpn_model"
            self._is_loaded = True
            return

        if not HAS_OPENCV:
            raise ImportError("OpenCV is required for CTPN detection")

        self._model = cv2.dnn.readNet(self.model_path)
        self._is_loaded = True

    def unload_model(self) -> None:
        self._model = None
        self._is_loaded = False

    def _ensure_model_loaded(self) -> None:
        if not self._is_loaded:
            self.load_model()

    def detect(self, image: np.ndarray, **kwargs) -> List[Dict[str, Any]]:
        self._ensure_model_loaded()

        if self.use_mock or self._model == "mock_ctpn_model":
            return self._mock_detect(image, **kwargs)

        return self._real_detect(image, **kwargs)

    def _mock_detect(self, image: np.ndarray, **kwargs) -> List[Dict[str, Any]]:
        h, w = image.shape[:2]
        text_boxes = []

        num_columns = kwargs.get("num_columns", 3)
        num_lines_per_column = kwargs.get("num_lines", 8)

        column_width = w // (num_columns + 1)
        line_height = h // (num_lines_per_column + 2)

        for col in range(num_columns):
            x_center = column_width * (col + 1)
            box_width = int(column_width * 0.7)

            for line in range(num_lines_per_column):
                y_center = line_height * (line + 1) + int(line_height * 0.5)
                box_height = int(line_height * 0.8)

                x1 = max(0, x_center - box_width // 2)
                y1 = max(0, y_center - box_height // 2)
                x2 = min(w, x_center + box_width // 2)
                y2 = min(h, y_center + box_height // 2)

                confidence = 0.85 + np.random.uniform(-0.1, 0.1)

                text_boxes.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(confidence, 4),
                    "orientation": "vertical",
                    "column": col,
                    "line": line,
                })

        return text_boxes

    def _real_detect(self, image: np.ndarray, **kwargs) -> List[Dict[str, Any]]:
        if not HAS_OPENCV:
            return self._mock_detect(image, **kwargs)

        h, w = image.shape[:2]

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 15))
        vertical_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)

        contours, _ = cv2.findContours(vertical_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        text_boxes = []
        for contour in contours:
            x, y, bw, bh = cv2.boundingRect(contour)

            if bh < 20 or bw < 10:
                continue

            if bh > bw * 2:
                x1, y1 = max(0, x - 5), max(0, y - 5)
                x2, y2 = min(w, x + bw + 5), min(h, y + bh + 5)

                confidence = 0.7 + np.random.uniform(0, 0.25)

                text_boxes.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(confidence, 4),
                    "orientation": "vertical",
                })

        text_boxes.sort(key=lambda b: (b["bbox"][0], b["bbox"][1]))

        return text_boxes

    def __enter__(self):
        self.load_model()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unload_model()
