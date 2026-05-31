from typing import List, Dict, Any, Tuple
import numpy as np
from sklearn.cluster import DBSCAN


class AnnotationSeparator:
    def __init__(
        self,
        sidebar_ratio: float = 0.15,
        size_ratio_threshold: float = 0.6,
        margin_ratio: float = 0.1
    ):
        self.sidebar_ratio = sidebar_ratio
        self.size_ratio_threshold = size_ratio_threshold
        self.margin_ratio = margin_ratio

    def separate_annotations(
        self,
        text_boxes: List[Dict[str, Any]],
        image_shape: Tuple[int, int]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not text_boxes:
            return [], []

        height, width = image_shape
        main_text_boxes = []
        annotation_boxes = []

        avg_box_height = self._calculate_avg_height(text_boxes)

        for box in text_boxes:
            if self._is_annotation(box, image_shape, avg_box_height):
                annotation_boxes.append(box)
            else:
                main_text_boxes.append(box)

        if annotation_boxes:
            annotation_boxes = self.cluster_annotations(annotation_boxes)

        return main_text_boxes, annotation_boxes

    def _is_annotation(
        self,
        text_box: Dict[str, Any],
        image_shape: Tuple[int, int],
        avg_box_height: float
    ) -> bool:
        height, width = image_shape

        x_coords = [text_box.get(f'x{i}', 0) for i in range(1, 5)]
        y_coords = [text_box.get(f'y{i}', 0) for i in range(1, 5)]

        center_x = np.mean(x_coords)
        center_y = np.mean(y_coords)
        box_height = max(y_coords) - min(y_coords)
        box_width = max(x_coords) - min(x_coords)

        margin_w = width * self.margin_ratio
        margin_h = height * self.margin_ratio

        is_in_margin = (
            center_x < margin_w or
            center_x > width - margin_w or
            center_y < margin_h or
            center_y > height - margin_h
        )

        is_in_sidebar = (
            center_x < width * self.sidebar_ratio or
            center_x > width * (1 - self.sidebar_ratio)
        )

        is_small = box_height > 0 and avg_box_height > 0 and (box_height / avg_box_height) < self.size_ratio_threshold

        is_between_columns = self._is_between_columns(center_x, width)

        return is_in_margin or is_in_sidebar or is_small or is_between_columns

    def _is_between_columns(self, center_x: float, width: float) -> bool:
        column_positions = [i * width / 5 for i in range(1, 5)]
        for pos in column_positions:
            if abs(center_x - pos) < width * 0.03:
                return True
        return False

    def _calculate_avg_height(self, text_boxes: List[Dict[str, Any]]) -> float:
        if not text_boxes:
            return 0.0
        heights = []
        for box in text_boxes:
            y_coords = [box.get(f'y{i}', 0) for i in range(1, 5)]
            box_height = max(y_coords) - min(y_coords)
            if box_height > 0:
                heights.append(box_height)
        return np.mean(heights) if heights else 0.0

    def cluster_annotations(
        self,
        text_boxes: List[Dict[str, Any]],
        eps: float = 50.0,
        min_samples: int = 1
    ) -> List[Dict[str, Any]]:
        if len(text_boxes) < 2:
            return text_boxes

        centers = []
        for box in text_boxes:
            x_coords = [box.get(f'x{i}', 0) for i in range(1, 5)]
            y_coords = [box.get(f'y{i}', 0) for i in range(1, 5)]
            centers.append([np.mean(x_coords), np.mean(y_coords)])

        X = np.array(centers)
        clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(X)

        clustered_boxes: Dict[int, List[Dict[str, Any]]] = {}
        for box, label in zip(text_boxes, clustering.labels_):
            if label not in clustered_boxes:
                clustered_boxes[label] = []
            clustered_boxes[label].append(box)

        result = []
        for label, boxes in clustered_boxes.items():
            if len(boxes) == 1:
                result.append(boxes[0])
            else:
                merged_box = self._merge_boxes(boxes)
                merged_box['is_merged'] = True
                result.append(merged_box)

        return result

    def _merge_boxes(self, boxes: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_x = []
        all_y = []
        confidences = []

        for box in boxes:
            for i in range(1, 5):
                all_x.append(box.get(f'x{i}', 0))
                all_y.append(box.get(f'y{i}', 0))
            if 'confidence' in box and box['confidence'] is not None:
                confidences.append(box['confidence'])

        merged = {
            'x1': min(all_x),
            'y1': min(all_y),
            'x2': max(all_x),
            'y2': min(all_y),
            'x3': max(all_x),
            'y3': max(all_y),
            'x4': min(all_x),
            'y4': max(all_y),
            'confidence': np.mean(confidences) if confidences else None,
            'is_merged': True,
            'merged_count': len(boxes)
        }

        return merged
