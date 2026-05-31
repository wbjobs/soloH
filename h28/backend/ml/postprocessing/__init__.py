from typing import List, Dict, Any, Optional, Tuple

from .connected_components import (
    BoundingBox,
    find_connected_components,
    merge_nearby_components
)
from .layout_analyzer import (
    Column,
    analyze_vertical_layout,
    merge_columns,
    merge_lines,
    get_column_reading_order,
    get_text_from_columns
)
from .page_reconstructor import (
    PageLayout,
    reconstruct_page,
    build_reading_order,
    generate_formatted_text
)
from .annotation_separator import AnnotationSeparator


class PostProcessor:
    def __init__(
        self,
        is_vertical: bool = True,
        column_width_threshold: float = 80.0,
        row_height_threshold: float = 60.0,
        merge_distance_threshold: float = 15.0,
        overlap_threshold: float = 0.3
    ):
        self.is_vertical = is_vertical
        self.column_width_threshold = column_width_threshold
        self.row_height_threshold = row_height_threshold
        self.merge_distance_threshold = merge_distance_threshold
        self.overlap_threshold = overlap_threshold

    def process(
        self,
        bboxes: List[List[float]],
        labels: Optional[List[str]] = None,
        confidences: Optional[List[float]] = None,
        page_size: Optional[Tuple[float, float]] = None
    ) -> PageLayout:
        page_layout = reconstruct_page(
            bboxes=bboxes,
            labels=labels,
            confidences=confidences,
            page_size=page_size,
            is_vertical=self.is_vertical
        )
        return page_layout

    def get_text(
        self,
        page_layout: PageLayout,
        format_type: str = 'plain',
        column_separator: str = '\n',
        line_separator: str = '\n',
        include_bboxes: bool = False
    ) -> str:
        return generate_formatted_text(
            page_layout=page_layout,
            format_type=format_type,
            column_separator=column_separator,
            line_separator=line_separator,
            include_bboxes=include_bboxes
        )

    def find_components(
        self,
        bboxes: List[List[float]],
        labels: Optional[List[str]] = None,
        confidences: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        return find_connected_components(
            bboxes=bboxes,
            labels=labels,
            confidences=confidences,
            horizontal_threshold=self.column_width_threshold,
            vertical_threshold=self.row_height_threshold
        )

    def merge_components(
        self,
        components: List[Dict[str, Any]],
        direction: str = 'vertical'
    ) -> List[Dict[str, Any]]:
        return merge_nearby_components(
            components=components,
            direction=direction,
            distance_threshold=self.merge_distance_threshold,
            overlap_threshold=self.overlap_threshold
        )

    def analyze_layout(
        self,
        components: List[Dict[str, Any]]
    ) -> List[Column]:
        if self.is_vertical:
            return analyze_vertical_layout(
                components=components,
                column_width_threshold=self.column_width_threshold,
                row_height_threshold=self.row_height_threshold
            )
        else:
            from .page_reconstructor import _analyze_horizontal_layout
            return _analyze_horizontal_layout(
                components=components,
                line_height_threshold=self.row_height_threshold,
                distance_threshold=self.merge_distance_threshold
            )


__all__ = [
    'BoundingBox',
    'Column',
    'PageLayout',
    'PostProcessor',
    'AnnotationSeparator',
    'find_connected_components',
    'merge_nearby_components',
    'analyze_vertical_layout',
    'merge_columns',
    'merge_lines',
    'get_column_reading_order',
    'get_text_from_columns',
    'reconstruct_page',
    'build_reading_order',
    'generate_formatted_text'
]
