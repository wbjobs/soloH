from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from .connected_components import (
    BoundingBox, find_connected_components, merge_nearby_components,
    _dynamic_column_clustering, _simple_column_clustering
)


class Column:
    def __init__(self, components: List[Dict[str, Any]]):
        self.components = sorted(
            components,
            key=lambda c: c['bbox'].center_y
        )

    @property
    def bbox(self) -> BoundingBox:
        if not self.components:
            raise ValueError("Empty column has no bounding box")

        x1 = min(c['bbox'].x1 for c in self.components)
        y1 = min(c['bbox'].y1 for c in self.components)
        x2 = max(c['bbox'].x2 for c in self.components)
        y2 = max(c['bbox'].y2 for c in self.components)

        return BoundingBox(x1, y1, x2, y2)

    @property
    def center_x(self) -> float:
        return self.bbox.center_x

    @property
    def center_y(self) -> float:
        return self.bbox.center_y

    @property
    def text(self) -> str:
        return ''.join(c['text'] for c in self.components if c['text'])

    def add_component(self, component: Dict[str, Any]):
        self.components.append(component)
        self.components.sort(key=lambda c: c['bbox'].center_y)


def analyze_vertical_layout(
    components: List[Dict[str, Any]],
    column_width_threshold: float = 80.0,
    row_height_threshold: float = 60.0,
    column_overlap_threshold: float = 0.2
) -> List[Column]:
    if not components:
        return []

    columns = _cluster_columns(
        components,
        column_width_threshold,
        column_overlap_threshold
    )

    columns = merge_columns(columns, column_width_threshold)

    for column in columns:
        column.components = merge_lines(
            column.components,
            row_height_threshold
        )

    columns.sort(key=lambda col: col.center_x, reverse=True)

    return columns


def _cluster_columns(
    components: List[Dict[str, Any]],
    column_width_threshold: float,
    overlap_threshold: float
) -> List[Column]:
    if not components:
        return []

    centers = np.array([c['bbox'].center_x for c in components])
    widths = np.array([c['bbox'].width for c in components])
    avg_width = np.mean(widths) if len(widths) > 0 else column_width_threshold

    adaptive_threshold = max(column_width_threshold * 0.6, avg_width * 0.4)

    if len(components) >= 5:
        labels = _dynamic_column_clustering(centers, adaptive_threshold)
    else:
        labels = _simple_column_clustering(centers, adaptive_threshold)

    column_groups: Dict[int, List[Dict[str, Any]]] = {}
    for comp, label in zip(components, labels):
        if label not in column_groups:
            column_groups[label] = []
        column_groups[label].append(comp)

    columns = []
    for col_idx in sorted(column_groups.keys()):
        col_comps = column_groups[col_idx]
        columns.append(Column(col_comps))

    if len(columns) > 1:
        columns = _merge_overlapping_columns(columns, overlap_threshold)

    return columns


def _merge_overlapping_columns(
    columns: List[Column],
    overlap_threshold: float
) -> List[Column]:
    if len(columns) < 2:
        return columns

    columns_sorted = sorted(columns, key=lambda c: c.center_x)

    merged = []
    current_group = [columns_sorted[0]]

    for i in range(1, len(columns_sorted)):
        col = columns_sorted[i]
        last_col = current_group[-1]

        gap = col.bbox.x1 - last_col.bbox.x2
        overlap = _vertical_overlap_ratio(col.bbox, last_col.bbox)

        should_merge = False
        if gap <= 0 and overlap >= overlap_threshold * 0.3:
            should_merge = True
        elif gap < last_col.bbox.width * 0.3 and overlap >= overlap_threshold * 0.5:
            should_merge = True

        if should_merge:
            current_group.append(col)
        else:
            if len(current_group) > 1:
                merged.append(_merge_column_group(current_group))
            else:
                merged.append(current_group[0])
            current_group = [col]

    if len(current_group) > 1:
        merged.append(_merge_column_group(current_group))
    else:
        merged.append(current_group[0])

    return merged


def _vertical_overlap_ratio(bbox1: BoundingBox, bbox2: BoundingBox) -> float:
    overlap_top = max(bbox1.y1, bbox2.y1)
    overlap_bottom = min(bbox1.y2, bbox2.y2)

    if overlap_bottom <= overlap_top:
        return 0.0

    overlap_height = overlap_bottom - overlap_top
    min_height = min(bbox1.height, bbox2.height)

    return overlap_height / min_height if min_height > 0 else 0.0


def merge_columns(
    columns: List[Column],
    distance_threshold: float = 50.0
) -> List[Column]:
    if len(columns) < 2:
        return columns

    columns_sorted = sorted(columns, key=lambda col: col.center_x)

    merged = []
    current_group = [columns_sorted[0]]

    for i in range(1, len(columns_sorted)):
        col = columns_sorted[i]
        last_col = current_group[-1]

        gap = col.bbox.x1 - last_col.bbox.x2
        overlap = _vertical_overlap_ratio(col.bbox, last_col.bbox)

        if gap < distance_threshold and overlap > 0.1:
            should_merge = False
            for comp in col.components:
                for last_comp in last_col.components:
                    comp_gap = abs(comp['bbox'].center_x - last_comp['bbox'].center_x)
                    if comp_gap < distance_threshold * 0.8:
                        should_merge = True
                        break
                if should_merge:
                    break

            if should_merge:
                current_group.append(col)
                continue

        if len(current_group) > 1:
            merged_col = _merge_column_group(current_group)
            merged.append(merged_col)
        else:
            merged.append(current_group[0])
        current_group = [col]

    if len(current_group) > 1:
        merged_col = _merge_column_group(current_group)
        merged.append(merged_col)
    else:
        merged.append(current_group[0])

    return merged


def _merge_column_group(column_group: List[Column]) -> Column:
    all_components = []
    for col in column_group:
        all_components.extend(col.components)

    merged = Column(all_components)
    return merged


def merge_lines(
    components: List[Dict[str, Any]],
    distance_threshold: float = 30.0,
    overlap_threshold: float = 0.3
) -> List[Dict[str, Any]]:
    if len(components) < 2:
        return components

    return merge_nearby_components(
        components,
        direction='vertical',
        distance_threshold=distance_threshold,
        overlap_threshold=overlap_threshold
    )


def get_column_reading_order(columns: List[Column]) -> List[Column]:
    return sorted(columns, key=lambda col: col.center_x, reverse=True)


def get_text_from_columns(columns: List[Column], column_separator: str = '\n') -> str:
    ordered_columns = get_column_reading_order(columns)
    texts = []
    for col in ordered_columns:
        line_texts = [comp['text'] for comp in col.components if comp['text']]
        col_text = ''.join(line_texts)
        if col_text:
            texts.append(col_text)
    return column_separator.join(texts)
