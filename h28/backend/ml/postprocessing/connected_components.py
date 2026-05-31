from typing import List, Tuple, Dict, Any, Optional
import numpy as np


class BoundingBox:
    def __init__(self, x1: float, y1: float, x2: float, y2: float):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def area(self) -> float:
        return self.width * self.height

    def to_list(self) -> List[float]:
        return [self.x1, self.y1, self.x2, self.y2]

    def iou(self, other: 'BoundingBox') -> float:
        inter_x1 = max(self.x1, other.x1)
        inter_y1 = max(self.y1, other.y1)
        inter_x2 = min(self.x2, other.x2)
        inter_y2 = min(self.y2, other.y2)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0

        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        union_area = self.area + other.area - inter_area

        return inter_area / union_area if union_area > 0 else 0.0

    def horizontal_overlap(self, other: 'BoundingBox') -> float:
        inter_x1 = max(self.x1, other.x1)
        inter_x2 = min(self.x2, other.x2)
        if inter_x2 <= inter_x1:
            return 0.0
        overlap = inter_x2 - inter_x1
        min_width = min(self.width, other.width)
        return overlap / min_width if min_width > 0 else 0.0

    def horizontal_offset_ratio(self, other: 'BoundingBox') -> float:
        offset = abs(self.center_x - other.center_x)
        avg_width = (self.width + other.width) / 2
        return offset / avg_width if avg_width > 0 else 1.0


def find_connected_components(
    bboxes: List[List[float]],
    labels: Optional[List[str]] = None,
    confidences: Optional[List[float]] = None,
    horizontal_threshold: float = 10.0,
    vertical_threshold: float = 5.0
) -> List[Dict[str, Any]]:
    if not bboxes:
        return []

    labels = labels or [''] * len(bboxes)
    confidences = confidences or [1.0] * len(bboxes)

    components = []
    for i, (bbox, label, conf) in enumerate(zip(bboxes, labels, confidences)):
        x1, y1, x2, y2 = bbox[:4]
        components.append({
            'id': i,
            'bbox': BoundingBox(x1, y1, x2, y2),
            'text': label,
            'confidence': conf,
            'merged': False
        })

    return components


def merge_nearby_components(
    components: List[Dict[str, Any]],
    direction: str = 'vertical',
    distance_threshold: float = 15.0,
    overlap_threshold: float = 0.3,
    enable_post_refinement: bool = True
) -> List[Dict[str, Any]]:
    if len(components) < 2:
        return components

    merged = []
    used = set()

    components_sorted = sorted(
        components,
        key=lambda c: (c['bbox'].center_y, c['bbox'].center_x)
    )

    for i, comp in enumerate(components_sorted):
        if comp['id'] in used:
            continue

        current_group = [comp]
        used.add(comp['id'])

        for j in range(i + 1, len(components_sorted)):
            other = components_sorted[j]
            if other['id'] in used:
                continue

            if _should_merge(
                current_group[-1]['bbox'],
                other['bbox'],
                direction,
                distance_threshold,
                overlap_threshold
            ):
                current_group.append(other)
                used.add(other['id'])
            else:
                if direction == 'vertical':
                    if other['bbox'].y1 > current_group[-1]['bbox'].y2 + distance_threshold:
                        break

        if len(current_group) > 1:
            merged_comp = _merge_component_group(current_group)
            merged.append(merged_comp)
        else:
            merged.append(current_group[0])

    if enable_post_refinement and len(merged) >= 2:
        merged = _refine_merged_components(
            merged, direction, distance_threshold, overlap_threshold
        )

    return merged


def _refine_merged_components(
    components: List[Dict[str, Any]],
    direction: str,
    distance_threshold: float,
    overlap_threshold: float
) -> List[Dict[str, Any]]:
    if len(components) < 2:
        return components

    if direction == 'vertical':
        centers = np.array([c['bbox'].center_x for c in components])
        avg_width = np.mean([c['bbox'].width for c in components])
        threshold = avg_width * 0.5

        if len(centers) >= 3:
            labels = _dynamic_column_clustering(centers, threshold)
        else:
            labels = _simple_column_clustering(centers, threshold)

        column_groups: Dict[int, List[Dict[str, Any]]] = {}
        for comp, label in zip(components, labels):
            if label not in column_groups:
                column_groups[label] = []
            column_groups[label].append(comp)

        refined = []
        for col_comps in column_groups.values():
            col_comps_sorted = sorted(col_comps, key=lambda c: c['bbox'].center_y)

            i = 0
            while i < len(col_comps_sorted):
                current = col_comps_sorted[i]
                if i + 1 < len(col_comps_sorted):
                    next_comp = col_comps_sorted[i + 1]
                    if _should_merge(
                        current['bbox'],
                        next_comp['bbox'],
                        'vertical',
                        distance_threshold * 1.2,
                        overlap_threshold * 0.5,
                        tolerate_misalignment=True
                    ):
                        merged = _merge_component_group([current, next_comp])
                        refined.append(merged)
                        i += 2
                        continue
                refined.append(current)
                i += 1

        return refined

    return components


def _simple_column_clustering(centers: np.ndarray, threshold: float) -> List[int]:
    if len(centers) == 0:
        return []
    if len(centers) == 1:
        return [0]

    sorted_indices = np.argsort(centers)
    sorted_centers = centers[sorted_indices]

    labels = np.zeros(len(centers), dtype=int)
    current_label = 0

    for i in range(1, len(sorted_centers)):
        if sorted_centers[i] - sorted_centers[i - 1] > threshold:
            current_label += 1
        labels[sorted_indices[i]] = current_label

    return labels.tolist()


def _dynamic_column_clustering(centers: np.ndarray, threshold: float) -> List[int]:
    if len(centers) < 3:
        return _simple_column_clustering(centers, threshold)

    n = len(centers)
    sorted_indices = np.argsort(centers)
    sorted_centers = centers[sorted_indices]

    gaps = np.diff(sorted_centers)
    median_gap = np.median(gaps) if len(gaps) > 0 else threshold
    adaptive_threshold = max(threshold, median_gap * 0.8)

    dp = np.zeros(n + 1)
    split_points = np.zeros(n + 1, dtype=int)

    for i in range(1, n + 1):
        min_cost = float('inf')
        best_j = 0
        for j in range(i):
            width = sorted_centers[i - 1] - sorted_centers[j]
            cost = dp[j] + (width > adaptive_threshold * 1.5) * 100 + 1
            if cost < min_cost:
                min_cost = cost
                best_j = j
        dp[i] = min_cost
        split_points[i] = best_j

    labels = np.zeros(n, dtype=int)
    current_label = 0
    i = n
    while i > 0:
        j = split_points[i]
        labels[sorted_indices[j:i]] = current_label
        current_label += 1
        i = j

    max_label = labels.max()
    labels = max_label - labels

    return labels.tolist()


def _should_merge(
    bbox1: BoundingBox,
    bbox2: BoundingBox,
    direction: str,
    distance_threshold: float,
    overlap_threshold: float,
    tolerate_misalignment: bool = True
) -> bool:
    if direction == 'vertical':
        vertical_gap = bbox2.y1 - bbox1.y2
        if vertical_gap < -distance_threshold * 0.3 or vertical_gap > distance_threshold:
            return False

        horizontal_overlap = bbox1.horizontal_overlap(bbox2)
        horizontal_offset = bbox1.horizontal_offset_ratio(bbox2)

        if horizontal_overlap >= overlap_threshold:
            return True

        if tolerate_misalignment:
            if vertical_gap <= distance_threshold * 0.7:
                if horizontal_overlap >= overlap_threshold * 0.5:
                    return True
                if horizontal_offset <= 0.8 and horizontal_overlap > 0:
                    avg_height = (bbox1.height + bbox2.height) / 2
                    if vertical_gap < avg_height * 0.3:
                        return True

            if horizontal_offset <= 0.5 and vertical_gap <= distance_threshold * 0.5:
                return True

        return False

    else:
        horizontal_gap = bbox2.x1 - bbox1.x2
        if horizontal_gap < -distance_threshold * 0.3 or horizontal_gap > distance_threshold:
            return False

        overlap_height = min(bbox1.y2, bbox2.y2) - max(bbox1.y1, bbox2.y1)
        min_height = min(bbox1.height, bbox2.height)
        overlap_ratio = overlap_height / min_height if min_height > 0 else 0

        if overlap_ratio >= overlap_threshold:
            return True

        if tolerate_misalignment:
            vertical_offset = abs(bbox1.center_y - bbox2.center_y) / ((bbox1.height + bbox2.height) / 2)
            if horizontal_gap <= distance_threshold * 0.7:
                if overlap_ratio >= overlap_threshold * 0.5:
                    return True
                if vertical_offset <= 0.8 and overlap_ratio > 0:
                    avg_width = (bbox1.width + bbox2.width) / 2
                    if horizontal_gap < avg_width * 0.3:
                        return True

        return False


def _merge_component_group(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not group:
        raise ValueError("Cannot merge empty component group")

    bboxes = [comp['bbox'] for comp in group]
    texts = [comp['text'] for comp in group if comp['text']]
    confidences = [comp['confidence'] for comp in group]

    merged_x1 = min(bbox.x1 for bbox in bboxes)
    merged_y1 = min(bbox.y1 for bbox in bboxes)
    merged_x2 = max(bbox.x2 for bbox in bboxes)
    merged_y2 = max(bbox.y2 for bbox in bboxes)

    avg_confidence = sum(confidences) / len(confidences)
    merged_text = ''.join(texts)

    return {
        'id': group[0]['id'],
        'bbox': BoundingBox(merged_x1, merged_y1, merged_x2, merged_y2),
        'text': merged_text,
        'confidence': avg_confidence,
        'merged': True,
        'merged_ids': [comp['id'] for comp in group]
    }
