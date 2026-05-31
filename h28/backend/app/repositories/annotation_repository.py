from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.annotation import Annotation


class AnnotationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_annotation(self, page_result_id: int, data: Dict[str, Any]) -> Annotation:
        annotation = Annotation(
            page_result_id=page_result_id,
            content=data.get('content'),
            confidence=data.get('confidence'),
            x1=data['x1'],
            y1=data['y1'],
            x2=data['x2'],
            y2=data['y2'],
            x3=data['x3'],
            y3=data['y3'],
            x4=data['x4'],
            y4=data['y4'],
            annotation_type=data.get('annotation_type', 'handwritten'),
            is_merged=data.get('is_merged', False)
        )
        self.db.add(annotation)
        self.db.commit()
        self.db.refresh(annotation)
        return annotation

    def batch_create_annotations(self, page_result_id: int, annotations_data: List[Dict[str, Any]]) -> List[Annotation]:
        annotations = []
        for data in annotations_data:
            annotation = Annotation(
                page_result_id=page_result_id,
                content=data.get('content'),
                confidence=data.get('confidence'),
                x1=data['x1'],
                y1=data['y1'],
                x2=data['x2'],
                y2=data['y2'],
                x3=data['x3'],
                y3=data['y3'],
                x4=data['x4'],
                y4=data['y4'],
                annotation_type=data.get('annotation_type', 'handwritten'),
                is_merged=data.get('is_merged', False)
            )
            annotations.append(annotation)
            self.db.add(annotation)
        self.db.commit()
        for annotation in annotations:
            self.db.refresh(annotation)
        return annotations

    def get_annotation_by_id(self, annotation_id: int) -> Optional[Annotation]:
        return self.db.query(Annotation).filter(Annotation.id == annotation_id).first()

    def get_annotations_by_page_result_id(self, page_result_id: int) -> List[Annotation]:
        return self.db.query(Annotation).filter(Annotation.page_result_id == page_result_id).all()

    def get_annotations_by_task_id(self, task_id: str) -> List[Annotation]:
        from app.models.page_result import PageResult
        return self.db.query(Annotation).join(PageResult).filter(PageResult.task_id == task_id).all()

    def update_annotation(self, annotation_id: int, data: Dict[str, Any]) -> Optional[Annotation]:
        annotation = self.get_annotation_by_id(annotation_id)
        if not annotation:
            return None
        for field, value in data.items():
            if hasattr(annotation, field):
                setattr(annotation, field, value)
        self.db.commit()
        self.db.refresh(annotation)
        return annotation

    def delete_annotation(self, annotation_id: int) -> Optional[Annotation]:
        annotation = self.get_annotation_by_id(annotation_id)
        if annotation:
            self.db.delete(annotation)
            self.db.commit()
        return annotation
