from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from .connected_components import (
    BoundingBox,
    find_connected_components,
    merge_nearby_components
)
from .layout_analyzer import (
    Column,
    analyze_vertical_layout,
    get_column_reading_order,
    get_text_from_columns
)


class PageLayout:
    def __init__(self):
        self.columns: List[Column] = []
        self.page_bbox: Optional[BoundingBox] = None
        self.reading_order: List[int] = []
        self.metadata: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'columns': [
                {
                    'bbox': col.bbox.to_list(),
                    'center_x': col.center_x,
                    'center_y': col.center_y,
                    'text': col.text,
                    'components': [
                        {
                            'bbox': comp['bbox'].to_list(),
                            'text': comp['text'],
                            'confidence': comp['confidence'],
                            'merged': comp.get('merged', False)
                        }
                        for comp in col.components
                    ]
                }
                for col in self.columns
            ],
            'page_bbox': self.page_bbox.to_list() if self.page_bbox else None,
            'reading_order': self.reading_order,
            'metadata': self.metadata
        }


def reconstruct_page(
    bboxes: List[List[float]],
    labels: Optional[List[str]] = None,
    confidences: Optional[List[float]] = None,
    page_size: Optional[Tuple[float, float]] = None,
    is_vertical: bool = True
) -> PageLayout:
    if not bboxes:
        empty_layout = PageLayout()
        if page_size:
            empty_layout.page_bbox = BoundingBox(0, 0, page_size[0], page_size[1])
        return empty_layout

    components = find_connected_components(bboxes, labels, confidences)

    page_layout = PageLayout()

    if page_size:
        page_layout.page_bbox = BoundingBox(0, 0, page_size[0], page_size[1])
    else:
        all_x1 = min(comp['bbox'].x1 for comp in components)
        all_y1 = min(comp['bbox'].y1 for comp in components)
        all_x2 = max(comp['bbox'].x2 for comp in components)
        all_y2 = max(comp['bbox'].y2 for comp in components)
        page_layout.page_bbox = BoundingBox(all_x1, all_y1, all_x2, all_y2)

    if is_vertical:
        page_layout.columns = analyze_vertical_layout(components)
    else:
        page_layout.columns = _analyze_horizontal_layout(components)

    page_layout.reading_order = build_reading_order(
        page_layout.columns,
        is_vertical=is_vertical
    )

    page_layout.metadata = {
        'is_vertical': is_vertical,
        'total_columns': len(page_layout.columns),
        'total_components': sum(len(col.components) for col in page_layout.columns)
    }

    return page_layout


def _analyze_horizontal_layout(
    components: List[Dict[str, Any]],
    line_height_threshold: float = 40.0,
    distance_threshold: float = 20.0
) -> List[Column]:
    if not components:
        return []

    sorted_by_y = sorted(components, key=lambda c: c['bbox'].center_y)

    lines = []
    current_line = [sorted_by_y[0]]

    for i in range(1, len(sorted_by_y)):
        comp = sorted_by_y[i]
        last_comp = current_line[-1]

        vertical_distance = abs(comp['bbox'].center_y - last_comp['bbox'].center_y)

        if vertical_distance <= line_height_threshold:
            current_line.append(comp)
        else:
            lines.append(current_line)
            current_line = [comp]

    if current_line:
        lines.append(current_line)

    merged_lines = []
    for line in lines:
        line_sorted = sorted(line, key=lambda c: c['bbox'].center_x)
        merged = merge_nearby_components(
            line_sorted,
            direction='horizontal',
            distance_threshold=distance_threshold
        )
        merged_lines.append(merged)

    columns = []
    for line in merged_lines:
        column = Column(line)
        columns.append(column)

    return columns


def build_reading_order(
    columns: List[Column],
    is_vertical: bool = True
) -> List[int]:
    if not columns:
        return []

    if is_vertical:
        ordered_columns = get_column_reading_order(columns)
    else:
        ordered_columns = sorted(columns, key=lambda col: col.center_y)

    order_map = {id(col): idx for idx, col in enumerate(ordered_columns)}
    reading_order = [order_map[id(col)] for col in columns]

    return reading_order


def generate_formatted_text(
    page_layout: PageLayout,
    format_type: str = 'plain',
    column_separator: str = '\n',
    line_separator: str = '\n',
    include_bboxes: bool = False
) -> str:
    if not page_layout.columns:
        return ''

    is_vertical = page_layout.metadata.get('is_vertical', True)

    if format_type == 'plain':
        if is_vertical:
            return get_text_from_columns(
                page_layout.columns,
                column_separator=column_separator
            )
        else:
            ordered_columns = sorted(
                page_layout.columns,
                key=lambda col: col.center_y
            )
            texts = []
            for col in ordered_columns:
                line_texts = sorted(
                    col.components,
                    key=lambda c: c['bbox'].center_x
                )
                line_text = ''.join(
                    comp['text'] for comp in line_texts if comp['text']
                )
                if line_text:
                    texts.append(line_text)
            return line_separator.join(texts)

    elif format_type == 'structured':
        return _generate_structured_text(
            page_layout,
            is_vertical,
            column_separator,
            line_separator,
            include_bboxes
        )

    elif format_type == 'reading_order':
        return _generate_reading_order_text(
            page_layout,
            is_vertical,
            column_separator,
            line_separator
        )

    else:
        raise ValueError(f"Unknown format_type: {format_type}")


def _generate_structured_text(
    page_layout: PageLayout,
    is_vertical: bool,
    column_separator: str,
    line_separator: str,
    include_bboxes: bool
) -> str:
    output_lines = []

    output_lines.append(f"=== 页面版式信息 ===")
    if page_layout.page_bbox:
        output_lines.append(
            f"页面尺寸: {page_layout.page_bbox.width:.1f} x {page_layout.page_bbox.height:.1f}"
        )
    output_lines.append(f"排版方式: {'竖排(从右到左)' if is_vertical else '横排(从左到右)'}")
    output_lines.append(f"列数: {len(page_layout.columns)}")
    output_lines.append("")

    if is_vertical:
        ordered_columns = get_column_reading_order(page_layout.columns)
    else:
        ordered_columns = sorted(page_layout.columns, key=lambda col: col.center_y)

    for col_idx, col in enumerate(ordered_columns, 1):
        output_lines.append(f"--- 第{col_idx}列 ---")
        if include_bboxes:
            output_lines.append(
                f"位置: [{col.bbox.x1:.1f}, {col.bbox.y1:.1f}, "
                f"{col.bbox.x2:.1f}, {col.bbox.y2:.1f}]"
            )

        if is_vertical:
            for comp in col.components:
                comp_text = comp['text']
                if include_bboxes:
                    bbox_str = f"[{comp['bbox'].x1:.1f}, {comp['bbox'].y1:.1f}, " \
                               f"{comp['bbox'].x2:.1f}, {comp['bbox'].y2:.1f}]"
                    output_lines.append(f"  {bbox_str}: {comp_text}")
                else:
                    output_lines.append(comp_text)
        else:
            sorted_comps = sorted(col.components, key=lambda c: c['bbox'].center_x)
            line_text = ''.join(comp['text'] for comp in sorted_comps if comp['text'])
            if include_bboxes:
                for comp in sorted_comps:
                    bbox_str = f"[{comp['bbox'].x1:.1f}, {comp['bbox'].y1:.1f}, " \
                               f"{comp['bbox'].x2:.1f}, {comp['bbox'].y2:.1f}]"
                    output_lines.append(f"  {bbox_str}: {comp['text']}")
            else:
                output_lines.append(line_text)

        output_lines.append("")

    return '\n'.join(output_lines)


def _generate_reading_order_text(
    page_layout: PageLayout,
    is_vertical: bool,
    column_separator: str,
    line_separator: str
) -> str:
    if is_vertical:
        ordered_columns = get_column_reading_order(page_layout.columns)
    else:
        ordered_columns = sorted(page_layout.columns, key=lambda col: col.center_y)

    result = []
    for col_idx, col in enumerate(ordered_columns):
        col_header = f"【第{col_idx + 1}列】"
        if is_vertical:
            col_text = ''.join(comp['text'] for comp in col.components if comp['text'])
        else:
            sorted_comps = sorted(col.components, key=lambda c: c['bbox'].center_x)
            col_text = ''.join(comp['text'] for comp in sorted_comps if comp['text'])

        result.append(col_header + col_text)

    return column_separator.join(result)
