from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.repositories.base_repository import BaseRepository
from app.models.task import Task


class TaskRepository(BaseRepository[Task, Dict[str, Any], Dict[str, Any]]):
    def __init__(self, db: Session):
        super().__init__(db, Task)

    def get_by_status(self, status: str) -> List[Task]:
        return self.db.query(Task).filter(Task.status == status).all()

    def update_progress(self, task_id: str, progress: int, current_page: Optional[int] = None) -> Optional[Task]:
        task = self.get_by_id(task_id)
        if not task:
            return None
        task.progress = progress
        if current_page is not None:
            task.current_page = current_page
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_status(self, task_id: str, status: str, error_message: Optional[str] = None) -> Optional[Task]:
        task = self.get_by_id(task_id)
        if not task:
            return None
        task.status = status
        if status == 'completed' or status == 'failed':
            task.completed_at = datetime.utcnow()
        if error_message:
            task.error_message = error_message
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_list_paginated(self, page: int = 1, per_page: int = 10, status: Optional[str] = None) -> Tuple[List[Task], int]:
        query = self.db.query(Task)
        if status:
            query = query.filter(Task.status == status)
        total = query.count()
        tasks = query.order_by(Task.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return tasks, total
