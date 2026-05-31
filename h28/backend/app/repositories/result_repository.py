from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.page_result import PageResult
from app.models.text_line import TextLine
from app.models.text_box import TextBox


class ResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_page_result(self, task_id: str, page_number: int, data: Dict[str, Any]) -> PageResult:
        page_result = PageResult(
            task_id=task_id,
            page_number=page_number,
            width=data.get('width'),
            height=data.get('height'),
            image_path=data.get('image_path')
        )
        self.db.add(page_result)
        self.db.flush()

        for line_data in data.get('text_lines', []):
            text_line = TextLine(
                page_result_id=page_result.id,
                content=line_data.get('content', '')
            )
            self.db.add(text_line)
            self.db.flush()

            for box_data in line_data.get('text_boxes', []):
                text_box = TextBox(
                    text_line_id=text_line.id,
                    x1=box_data['x1'],
                    y1=box_data['y1'],
                    x2=box_data['x2'],
                    y2=box_data['y2'],
                    x3=box_data['x3'],
                    y3=box_data['y3'],
                    x4=box_data['x4'],
                    y4=box_data['y4'],
                    confidence=box_data['confidence']
                )
                self.db.add(text_box)

        self.db.commit()
        self.db.refresh(page_result)
        return page_result

    def get_page_results_by_task_id(self, task_id: str) -> List[PageResult]:
        return self.db.query(PageResult).filter(PageResult.task_id == task_id).order_by(PageResult.page_number).all()

    def update_text_line_content(self, text_line_id: int, content: str) -> Optional[TextLine]:
        text_line = self.db.query(TextLine).filter(TextLine.id == text_line_id).first()
        if not text_line:
            return None
        text_line.content = content
        self.db.commit()
        self.db.refresh(text_line)
        return text_line

    def get_page_by_task_and_page(self, task_id: str, page_number: int) -> Optional[PageResult]:
        return self.db.query(PageResult).filter(
            PageResult.task_id == task_id,
            PageResult.page_number == page_number
        ).first()

    def get_full_text(self, task_id: str) -> str:
        page_results = self.get_page_results_by_task_id(task_id)
        full_text_parts = []
        for page_result in page_results:
            for text_line in page_result.text_lines:
                if text_line.content:
                    full_text_parts.append(text_line.content)
        return '\n'.join(full_text_parts)
