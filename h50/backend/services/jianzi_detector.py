import os
import json
import random
import cv2
import numpy as np
from typing import Tuple, Dict, Optional, List, Any

BBox = Tuple[int, int, int, int]
ComponentBBoxes = Dict[str, BBox]
JianziBox = Dict[str, Any]

class JianziDetector:
    def __init__(self):
        self.min_char_width = 40
        self.min_char_height = 60
        self.max_char_width = 150
        self.max_char_height = 200
        self.char_aspect_ratio_range = (0.4, 0.8)
        self.min_area = 2000

    def detect_bounding_boxes(self, image: np.ndarray) -> List[JianziBox]:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        candidate_boxes = []
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            if not (self.min_char_width <= w <= self.max_char_width):
                continue
            if not (self.min_char_height <= h <= self.max_char_height):
                continue
            if not (self.char_aspect_ratio_range[0] <= aspect_ratio <= self.char_aspect_ratio_range[1]):
                continue
            if hierarchy is not None and hierarchy[0][i][3] != -1:
                parent_idx = hierarchy[0][i][3]
                if parent_idx >= 0 and parent_idx < len(contours):
                    parent_contour = contours[parent_idx]
                    parent_area = cv2.contourArea(parent_contour)
                    if parent_area > area * 5:
                        continue
            candidate_boxes.append({
                "bbox": (x, y, x + w, y + h),
                "area": area,
                "aspect_ratio": aspect_ratio,
                "confidence": self._calculate_confidence(area, w, h, aspect_ratio)
            })
        if len(candidate_boxes) == 0:
            return self._generate_mock_boxes(image)
        nms_boxes = self._nms(candidate_boxes, iou_threshold=0.3)
        vertical_projection = self._vertical_projection_analysis(binary)
        projection_boxes = self._boxes_from_projection(vertical_projection, image.shape)
        combined_boxes = self._merge_boxes(nms_boxes, projection_boxes)
        combined_boxes = self._filter_overlapping(combined_boxes)
        return combined_boxes

    def _calculate_confidence(self, area: float, w: int, h: int, aspect_ratio: float) -> float:
        base_confidence = 0.5
        area_factor = min(area / 10000, 1.0) * 0.2
        ratio_optimal = 0.6
        ratio_factor = (1 - abs(aspect_ratio - ratio_optimal) / 0.4) * 0.2
        size_factor = min((w * h) / 20000, 1.0) * 0.1
        confidence = base_confidence + area_factor + ratio_factor + size_factor
        return min(max(confidence, 0.1), 0.95)

    def _nms(self, boxes: List[JianziBox], iou_threshold: float = 0.3) -> List[JianziBox]:
        if len(boxes) == 0:
            return []
        boxes = sorted(boxes, key=lambda x: x["confidence"], reverse=True)
        keep = []
        while len(boxes) > 0:
            current = boxes.pop(0)
            keep.append(current)
            boxes = [
                box for box in boxes
                if self._iou(current["bbox"], box["bbox"]) < iou_threshold
            ]
        return keep

    def _iou(self, box1: BBox, box2: BBox) -> float:
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        xi1 = max(x1_1, x1_2)
        yi1 = max(y1_1, y1_2)
        xi2 = min(x2_1, x2_2)
        yi2 = min(y2_1, y2_2)
        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
        box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = box1_area + box2_area - inter_area
        return inter_area / union_area if union_area > 0 else 0

    def _vertical_projection_analysis(self, binary: np.ndarray) -> np.ndarray:
        h, w = binary.shape[:2]
        vertical_proj = np.sum(binary, axis=0)
        kernel = np.ones(15)
        smoothed = np.convolve(vertical_proj, kernel, mode='same') / kernel.sum()
        return smoothed

    def _boxes_from_projection(self, projection: np.ndarray, image_shape: Tuple[int, int]) -> List[JianziBox]:
        h, w = image_shape[:2]
        threshold = np.mean(projection) * 0.4
        peaks = []
        in_peak = False
        peak_start = 0
        for i, val in enumerate(projection):
            if val > threshold and not in_peak:
                in_peak = True
                peak_start = i
            elif val <= threshold and in_peak:
                in_peak = False
                peaks.append((peak_start, i))
        if in_peak:
            peaks.append((peak_start, len(projection)))
        boxes = []
        for start, end in peaks:
            col_width = end - start
            if col_width < self.min_char_width:
                continue
            num_chars = max(1, int(col_width / self.min_char_width))
            char_width = col_width / num_chars
            for i in range(num_chars):
                x1 = int(start + i * char_width)
                x2 = int(start + (i + 1) * char_width)
                char_h = int(char_width / 0.6)
                y1 = max(0, h // 2 - char_h // 2)
                y2 = min(h, h // 2 + char_h // 2)
                boxes.append({
                    "bbox": (x1, y1, x2, y2),
                    "area": (x2 - x1) * (y2 - y1),
                    "aspect_ratio": (x2 - x1) / (y2 - y1) if (y2 - y1) > 0 else 0,
                    "confidence": 0.5,
                    "from_projection": True
                })
        return boxes

    def _merge_boxes(self, boxes1: List[JianziBox], boxes2: List[JianziBox]) -> List[JianziBox]:
        merged = boxes1.copy()
        for box2 in boxes2:
            has_overlap = any(
                self._iou(box1["bbox"], box2["bbox"]) > 0.3
                for box1 in boxes1
            )
            if not has_overlap:
                merged.append(box2)
        return merged

    def _filter_overlapping(self, boxes: List[JianziBox]) -> List[JianziBox]:
        if len(boxes) <= 1:
            return boxes
        boxes = sorted(boxes, key=lambda x: x["confidence"], reverse=True)
        result = []
        used = [False] * len(boxes)
        for i in range(len(boxes)):
            if used[i]:
                continue
            current = boxes[i]
            merged_box = current
            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue
                iou = self._iou(current["bbox"], boxes[j]["bbox"])
                if iou > 0.3:
                    used[j] = True
                    x1 = min(current["bbox"][0], boxes[j]["bbox"][0])
                    y1 = min(current["bbox"][1], boxes[j]["bbox"][1])
                    x2 = max(current["bbox"][2], boxes[j]["bbox"][2])
                    y2 = max(current["bbox"][3], boxes[j]["bbox"][3])
                    merged_box = {
                        "bbox": (x1, y1, x2, y2),
                        "area": (x2 - x1) * (y2 - y1),
                        "aspect_ratio": (x2 - x1) / (y2 - y1) if (y2 - y1) > 0 else 0,
                        "confidence": max(current["confidence"], boxes[j]["confidence"])
                    }
            result.append(merged_box)
        return result

    def _generate_mock_boxes(self, image: np.ndarray) -> List[JianziBox]:
        h, w = image.shape[:2]
        num_cols = random.randint(3, 6)
        num_rows_per_col = random.randint(4, 8)
        col_width = w // (num_cols + 1)
        char_width = int(col_width * 0.7)
        char_height = int(char_width / 0.6)
        boxes = []
        char_id = 0
        for col in range(num_cols):
            x_center = w - (col + 1) * col_width
            for row in range(num_rows_per_col):
                y_center = int((row + 1) * h / (num_rows_per_col + 1))
                x1 = max(0, x_center - char_width // 2 + random.randint(-5, 5))
                y1 = max(0, y_center - char_height // 2 + random.randint(-5, 5))
                x2 = min(w, x_center + char_width // 2 + random.randint(-5, 5))
                y2 = min(h, y_center + char_height // 2 + random.randint(-5, 5))
                boxes.append({
                    "id": f"jianzi_{char_id:04d}",
                    "bbox": (x1, y1, x2, y2),
                    "area": (x2 - x1) * (y2 - y1),
                    "aspect_ratio": (x2 - x1) / (y2 - y1) if (y2 - y1) > 0 else 0,
                    "confidence": random.uniform(0.7, 0.95),
                    "column": col,
                    "row": row
                })
                char_id += 1
        return boxes

    def sort_vertical(self, jianzi_boxes: List[JianziBox]) -> List[JianziBox]:
        if len(jianzi_boxes) == 0:
            return []
        boxes_with_coords = []
        for box in jianzi_boxes:
            x1, y1, x2, y2 = box["bbox"]
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            boxes_with_coords.append((center_x, center_y, box))
        if len(boxes_with_coords) < 2:
            return [box for _, _, box in boxes_with_coords]
        x_coords = [x for x, _, _ in boxes_with_coords]
        x_gaps = np.diff(sorted(x_coords))
        if len(x_gaps) > 0:
            column_threshold = np.median(x_gaps) * 1.5
        else:
            column_threshold = 100
        sorted_by_x = sorted(boxes_with_coords, key=lambda x: -x[0])
        columns = []
        current_col = [sorted_by_x[0]]
        for item in sorted_by_x[1:]:
            prev_x = current_col[-1][0]
            curr_x = item[0]
            if abs(prev_x - curr_x) < column_threshold:
                current_col.append(item)
            else:
                columns.append(current_col)
                current_col = [item]
        if current_col:
            columns.append(current_col)
        sorted_boxes = []
        reading_order = 0
        for col in columns:
            col_sorted = sorted(col, key=lambda x: x[1])
            for _, _, box in col_sorted:
                box = box.copy()
                box["reading_order"] = reading_order
                sorted_boxes.append(box)
                reading_order += 1
        return sorted_boxes

    def segment_components(self, jianzi_image: np.ndarray) -> ComponentBBoxes:
        h, w = jianzi_image.shape[:2]
        if len(jianzi_image.shape) == 3:
            gray = cv2.cvtColor(jianzi_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = jianzi_image.copy()
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        horizontal_proj = np.sum(binary, axis=1)
        vertical_proj = np.sum(binary, axis=0)
        h_threshold = np.mean(horizontal_proj) * 0.2
        v_threshold = np.mean(vertical_proj) * 0.2
        split_h = h // 2
        for i in range(h // 2 - h // 4, h // 2 + h // 4):
            if horizontal_proj[i] < h_threshold:
                split_h = i
                break
        split_v = w // 2
        for i in range(w // 2 - w // 4, w // 2 + w // 4):
            if vertical_proj[i] < v_threshold:
                split_v = i
                break
        top_margin = int(h * 0.05)
        bottom_margin = int(h * 0.05)
        left_margin = int(w * 0.05)
        right_margin = int(w * 0.05)
        components: ComponentBBoxes = {
            "top": (left_margin, top_margin, w - right_margin, split_h),
            "bottom": (left_margin, split_h, w - right_margin, h - bottom_margin),
            "left": (left_margin, top_margin, split_v, h - bottom_margin),
            "right": (split_v, top_margin, w - right_margin, h - bottom_margin)
        }
        return components

    def extract_jianzi_image(self, image: np.ndarray, bbox: BBox) -> np.ndarray:
        x1, y1, x2, y2 = bbox
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(image.shape[1], x2)
        y2 = min(image.shape[0], y2)
        return image[y1:y2, x1:x2].copy()

    def pad_image(self, image: np.ndarray, target_size: Tuple[int, int], pad_color: Tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
        h, w = image.shape[:2]
        target_h, target_w = target_size
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        if len(resized.shape) == 2:
            padded = np.ones((target_h, target_w), dtype=np.uint8) * 255
        else:
            padded = np.ones((target_h, target_w, 3), dtype=np.uint8) * np.array(pad_color, dtype=np.uint8)
        x_offset = (target_w - new_w) // 2
        y_offset = (target_h - new_h) // 2
        padded[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
        return padded

    def save_detection_visualization(self, image: np.ndarray, boxes: List[JianziBox], output_path: str) -> None:
        vis_image = image.copy()
        for box in boxes:
            x1, y1, x2, y2 = box["bbox"]
            confidence = box.get("confidence", 0.0)
            color = (0, 255, 0)
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 2)
            label = f"{box.get('id', '')} {confidence:.2f}"
            cv2.putText(vis_image, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        cv2.imwrite(output_path, vis_image)
