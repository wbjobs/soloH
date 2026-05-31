from typing import Optional, List, Tuple, Dict, Any
from uuid import uuid4
from app.repositories.task_repository import TaskRepository
from app.models.task import Task


class TaskService:
    def __init__(self, task_repository: TaskRepository):
        self.task_repository = task_repository

    def get_by_id(self, task_id: str) -> Optional[Task]:
        return self.task_repository.get_by_id(task_id)

    def get_all(self) -> List[Task]:
        return self.task_repository.get_all()

    def create_task(self, file_name: str, file_type: str, page_count: int = 0) -> Task:
        task_data = {
            'id': str(uuid4()),
            'file_name': file_name,
            'file_type': file_type,
            'status': 'pending',
            'progress': 0,
            'page_count': page_count,
            'current_page': 0,
        }
        return self.task_repository.create(task_data)

    def update_task(self, task_id: str, task_data: Dict[str, Any]) -> Optional[Task]:
        task = self.task_repository.get_by_id(task_id)
        if not task:
            return None
        return self.task_repository.update(task, task_data)

    def delete_task(self, task_id: str) -> Optional[Task]:
        task = self.task_repository.get_by_id(task_id)
        if not task:
            return None
        return self.task_repository.delete(task_id)

    def update_status(self, task_id: str, status: str, error_message: Optional[str] = None) -> Optional[Task]:
        return self.task_repository.update_status(task_id, status, error_message)

    def update_progress(self, task_id: str, progress: int, current_page: Optional[int] = None) -> Optional[Task]:
        return self.task_repository.update_progress(task_id, progress, current_page)

    def get_by_status(self, status: str) -> List[Task]:
        return self.task_repository.get_by_status(status)

    def get_list_paginated(self, page: int = 1, per_page: int = 10, status: Optional[str] = None) -> Tuple[List[Task], int]:
        return self.task_repository.get_list_paginated(page, per_page, status)
