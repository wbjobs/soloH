from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from PIL import Image
from app.repositories.annotation_repository import AnnotationRepository
from app.repositories.result_repository import ResultRepository
from ml.postprocessing.annotation_separator import AnnotationSeparator


class AnnotationService:
    def __init__(
        self,
        annotation_repository: AnnotationRepository,
        result_repository: ResultRepository
    ):
        self.annotation_repository = annotation_repository
        self.result_repository = result_repository
        self.separator = AnnotationSeparator()

    def separate_and_recognize(
        self,
        page_result_id: int,
        image: np.ndarray,
        text_lines: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not text_lines:
            return [], []

        all_text_boxes = []
        for line in text_lines:
            for box in line.get('text_boxes', []):
                all_text_boxes.append(box)

        image_shape = image.shape[:2]

        main_boxes, annotation_boxes = self.separator.separate_annotations(
            all_text_boxes,
            image_shape
        )

        annotations_data = []
        for box in annotation_boxes:
            annotation_type = self._determine_annotation_type(box, image)
            content = self._recognize_annotation_content(box, image)
            annotations_data.append({
                **box,
                'content': content,
                'annotation_type': annotation_type,
                'is_merged': box.get('is_merged', False)
            })

        if annotations_data:
            self.annotation_repository.batch_create_annotations(
                page_result_id,
                annotations_data
            )

        main_text_lines = self._reconstruct_main_text_lines(main_boxes, text_lines)
        return main_text_lines, annotations_data

    def _determine_annotation_type(self, box: Dict[str, Any], image: np.ndarray) -> str:
        x_coords = [box.get(f'x{i}', 0) for i in range(1, 5)]
        y_coords = [box.get(f'y{i}', 0) for i in range(1, 5)]

        x1, y1 = int(min(x_coords)), int(min(y_coords))
        x2, y2 = int(max(x_coords)), int(max(y_coords))

        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(image.shape[1], x2)
        y2 = min(image.shape[0], y2)

        if x2 <= x1 or y2 <= y1:
            return 'handwritten'

        roi = image[y1:y2, x1:x2]
        if roi.size == 0:
            return 'handwritten'

        if len(roi.shape) == 3:
            gray = np.mean(roi, axis=2)
        else:
            gray = roi

        mean_intensity = np.mean(gray)
        std_intensity = np.std(gray)

        if std_intensity < 20:
            return 'seal'
        if mean_intensity < 60:
            return 'comment'
        return 'handwritten'

    def _recognize_annotation_content(self, box: Dict[str, Any], image: np.ndarray) -> str:
        return ''

    def _reconstruct_main_text_lines(
        self,
        main_boxes: List[Dict[str, Any]],
        original_lines: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        main_box_set = set()
        for box in main_boxes:
            key = self._box_key(box)
            main_box_set.add(key)

        result_lines = []
        for line in original_lines:
            filtered_boxes = []
            for box in line.get('text_boxes', []):
                if self._box_key(box) in main_box_set:
                    filtered_boxes.append(box)
            if filtered_boxes:
                result_lines.append({
                    **line,
                    'text_boxes': filtered_boxes
                })

        return result_lines

    def _box_key(self, box: Dict[str, Any]) -> Tuple[float, ...]:
        return tuple(box.get(f'x{i}', 0) for i in range(1, 5)) + tuple(box.get(f'y{i}', 0) for i in range(1, 5))

    def get_annotations_by_page(self, page_result_id: int) -> List[Dict[str, Any]]:
        annotations = self.annotation_repository.get_annotations_by_page_result_id(page_result_id)
        return [self._annotation_to_dict(a) for a in annotations]

    def get_annotations_by_task(self, task_id: str) -> List[Dict[str, Any]]:
        annotations = self.annotation_repository.get_annotations_by_task_id(task_id)
        return [self._annotation_to_dict(a) for a in annotations]

    def get_annotation(self, annotation_id: int) -> Optional[Dict[str, Any]]:
        annotation = self.annotation_repository.get_annotation_by_id(annotation_id)
        return self._annotation_to_dict(annotation) if annotation else None

    def update_annotation(self, annotation_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        annotation = self.annotation_repository.update_annotation(annotation_id, data)
        return self._annotation_to_dict(annotation) if annotation else None

    def delete_annotation(self, annotation_id: int) -> bool:
        annotation = self.annotation_repository.delete_annotation(annotation_id)
        return annotation is not None

    def _annotation_to_dict(self, annotation) -> Dict[str, Any]:
        return {
            'id': annotation.id,
            'page_result_id': annotation.page_result_id,
            'content': annotation.content,
            'confidence': annotation.confidence,
            'x1': annotation.x1,
            'y1': annotation.y1,
            'x2': annotation.x2,
            'y2': annotation.y2,
            'x3': annotation.x3,
            'y3': annotation.y3,
            'x4': annotation.x4,
            'y4': annotation.y4,
            'annotation_type': annotation.annotation_type,
            'is_merged': annotation.is_merged,
            'created_at': annotation.created_at.isoformat() if annotation.created_at else None
        }
