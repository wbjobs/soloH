from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.repositories.base_repository import BaseRepository
from app.models.collation import Collation


class CollationRepository(BaseRepository[Collation, Dict[str, Any], Dict[str, Any]]):
    def __init__(self, db: Session):
        super().__init__(db, Collation)

    def list_by_task_id(self, task_id: str) -> List[Collation]:
        return self.db.query(Collation).filter(
            (Collation.base_task_id == task_id) | (Collation.compared_task_id == task_id)
        ).order_by(Collation.created_at.desc()).all()

    def update_status(self, collation_id: str, status: str, error_message: Optional[str] = None) -> Optional[Collation]:
        collation = self.get_by_id(collation_id)
        if not collation:
            return None
        collation.status = status
        if status in ['completed', 'failed']:
            collation.completed_at = datetime.utcnow()
        if error_message:
            if collation.diff_result is None:
                collation.diff_result = {}
            collation.diff_result['error_message'] = error_message
        self.db.commit()
        self.db.refresh(collation)
        return collation
