import os
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict


class PostProcessor:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.min_box_confidence = self.config.get("min_box_confidence", 0.5)
        self.min_text_confidence = self.config.get("min_text_confidence", 0.6)
        self.iou_threshold = self.config.get("iou_threshold", 0.5)
        self._is_loaded = False

    def load_model(self) -> None:
        self._is_loaded = True

    def unload_model(self) -> None:
        self._is_loaded = False

    def _ensure_loaded(self) -> None:
        if not self._is_loaded:
            self.load_model()

    def process(
        self,
        detection_results: List[Dict[str, Any]],
        recognition_results: List[Dict[str, Any]],
        punctuation_results: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        self._ensure_loaded()

        filtered_boxes = self._filter_low_confidence_boxes(detection_results)
        sorted_boxes = self._sort_vertical_text_boxes(filtered_boxes)
        merged_boxes = self._merge_overlapping_boxes(sorted_boxes)

        aligned_results = self._align_detection_recognition(merged_boxes, recognition_results)

        if punctuation_results:
            aligned_results = self._apply_punctuation(aligned_results, punctuation_results)

        final_text = self._assemble_final_text(aligned_results)

        return {
            "boxes": merged_boxes,
            "recognition_results": aligned_results,
            "full_text": final_text,
            "processing_stats": {
                "total_boxes": len(detection_results),
                "filtered_boxes": len(filtered_boxes),
                "merged_boxes": len(merged_boxes),
                "avg_confidence": np.mean([r.get("confidence", 0) for r in aligned_results]) if aligned_results else 0,
            },
        }

    def _filter_low_confidence_boxes(self, boxes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            box for box in boxes
            if box.get("confidence", 1.0) >= self.min_box_confidence
        ]

    def _sort_vertical_text_boxes(self, boxes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not boxes:
            return []

        columns = defaultdict(list)
        for box in boxes:
            bbox = box.get("bbox", [0, 0, 0, 0])
            x_center = (bbox[0] + bbox[2]) / 2

            column_key = self._assign_column(x_center, boxes)
            columns[column_key].append(box)

        sorted_boxes = []
        for column_key in sorted(columns.keys()):
            column_boxes = sorted(
                columns[column_key],
                key=lambda b: (b["bbox"][1] + b["bbox"][3]) / 2
            )
            sorted_boxes.extend(column_boxes)

        return sorted_boxes

    def _assign_column(self, x_center: float, all_boxes: List[Dict[str, Any]]) -> int:
        if len(all_boxes) <= 1:
            return 0

        all_x_centers = sorted([
            (b["bbox"][0] + b["bbox"][2]) / 2 for b in all_boxes
        ])

        gaps = []
        for i in range(1, len(all_x_centers)):
            gaps.append(all_x_centers[i] - all_x_centers[i - 1])

        if not gaps:
            return 0

        mean_gap = np.mean(gaps)
        threshold = mean_gap * 1.5

        column_breaks = []
        for i, gap in enumerate(gaps):
            if gap > threshold:
                column_breaks.append(all_x_centers[i] + gap / 2)

        column = 0
        for break_point in column_breaks:
            if x_center > break_point:
                column += 1

        return column

    def _merge_overlapping_boxes(self, boxes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(boxes) <= 1:
            return boxes

        merged = []
        used = [False] * len(boxes)

        for i, box in enumerate(boxes):
            if used[i]:
                continue

            current_box = box.copy()
            used[i] = True

            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue

                other_box = boxes[j]
                iou = self._calculate_iou(current_box["bbox"], other_box["bbox"])

                if iou > self.iou_threshold:
                    current_box["bbox"] = self._merge_bboxes(current_box["bbox"], other_box["bbox"])
                    current_box["confidence"] = max(
                        current_box.get("confidence", 0),
                        other_box.get("confidence", 0)
                    )
                    used[j] = True

            merged.append(current_box)

        return merged

    def _calculate_iou(self, bbox1: List[int], bbox2: List[int]) -> float:
        x1, y1, x2, y2 = bbox1
        x3, y3, x4, y4 = bbox2

        xi1, yi1 = max(x1, x3), max(y1, y3)
        xi2, yi2 = min(x2, x4), min(y2, y4)

        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        area1 = (x2 - x1) * (y2 - y1)
        area2 = (x4 - x3) * (y4 - y3)
        union_area = area1 + area2 - inter_area

        return inter_area / union_area if union_area > 0 else 0

    def _merge_bboxes(self, bbox1: List[int], bbox2: List[int]) -> List[int]:
        return [
            min(bbox1[0], bbox2[0]),
            min(bbox1[1], bbox2[1]),
            max(bbox1[2], bbox2[2]),
            max(bbox1[3], bbox2[3]),
        ]

    def _align_detection_recognition(
        self,
        boxes: List[Dict[str, Any]],
        recognition_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        aligned = []
        min_len = min(len(boxes), len(recognition_results))

        for i in range(min_len):
            result = {
                **boxes[i],
                **recognition_results[i],
            }
            aligned.append(result)

        for i in range(min_len, len(boxes)):
            aligned.append({
                **boxes[i],
                "text": "",
                "confidence": 0.0,
                "char_confidences": [],
            })

        return aligned

    def _apply_punctuation(
        self,
        aligned_results: List[Dict[str, Any]],
        punctuation_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        for i, result in enumerate(aligned_results):
            if i < len(punctuation_results):
                punct_result = punctuation_results[i]
                result["punctuated_text"] = punct_result.get("punctuated_text", result.get("text", ""))
                result["punctuations"] = punct_result.get("punctuations", [])

        return aligned_results

    def _assemble_final_text(self, aligned_results: List[Dict[str, Any]]) -> str:
        if not aligned_results:
            return ""

        columns = defaultdict(list)
        for result in aligned_results:
            bbox = result.get("bbox", [0, 0, 0, 0])
            x_center = (bbox[0] + bbox[2]) / 2
            column_key = self._assign_column(x_center, aligned_results)
            columns[column_key].append(result)

        full_text_parts = []
        for column_key in sorted(columns.keys()):
            column_results = sorted(
                columns[column_key],
                key=lambda r: (r["bbox"][1] + r["bbox"][3]) / 2
            )

            column_text = "".join([
                r.get("punctuated_text", r.get("text", ""))
                for r in column_results
            ])
            full_text_parts.append(column_text)

        return "\n\n".join(full_text_parts)

    def __enter__(self):
        self.load_model()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unload_model()
