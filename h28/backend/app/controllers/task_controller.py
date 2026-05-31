from typing import Optional, Tuple, Dict, Any
from app import db
from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.repositories.result_repository import ResultRepository
from app.schemas.task_schema import TaskSchema
from app.schemas.task_result_schema import TaskResultSchema


class TaskController:
    def __init__(self):
        self.task_repository = TaskRepository(db.session)
        self.result_repository = ResultRepository(db.session)
        self.task_schema = TaskSchema()
        self.task_result_schema = TaskResultSchema()

    def create_task(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        try:
            task = Task(
                id=data.get('id'),
                file_name=data.get('fileName'),
                file_type=data.get('fileType'),
                status='pending',
                progress=0,
                page_count=data.get('pageCount', 0),
                current_page=0
            )
            self.task_repository.db.add(task)
            self.task_repository.db.commit()
            self.task_repository.db.refresh(task)
            return self.task_schema.dump(task), 201
        except Exception as e:
            self.task_repository.db.rollback()
            return {'error': str(e)}, 500

    def get_task_list(self, page: int = 1, per_page: int = 10, status: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
        try:
            tasks, total = self.task_repository.get_list_paginated(page, per_page, status)
            return {
                'items': self.task_schema.dump(tasks, many=True),
                'total': total,
                'page': page,
                'perPage': per_page
            }, 200
        except Exception as e:
            return {'error': str(e)}, 500

    def get_task_by_id(self, task_id: str) -> Tuple[Dict[str, Any], int]:
        try:
            task = self.task_repository.get_by_id(task_id)
            if not task:
                return {'error': 'Task not found'}, 404
            return self.task_schema.dump(task), 200
        except Exception as e:
            return {'error': str(e)}, 500

    def get_task_result(self, task_id: str) -> Tuple[Dict[str, Any], int]:
        try:
            task = self.task_repository.get_by_id(task_id)
            if not task:
                return {'error': 'Task not found'}, 404
            if task.status != 'completed':
                return {'error': 'Task not completed'}, 400
            page_results = self.result_repository.get_page_results_by_task_id(task_id)
            full_text = self.result_repository.get_full_text(task_id)
            return self.task_result_schema.dump({
                'taskId': task_id,
                'pages': page_results,
                'fullText': full_text
            }), 200
        except Exception as e:
            return {'error': str(e)}, 500

    def update_task_result(self, task_id: str, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        try:
            task = self.task_repository.get_by_id(task_id)
            if not task:
                return {'error': 'Task not found'}, 404

            if 'pages' in data:
                for page_data in data['pages']:
                    page_number = page_data.get('pageNumber')
                    for line_data in page_data.get('textLines', []):
                        line_id = line_data.get('id')
                        content = line_data.get('content')
                        if line_id and content is not None:
                            self.result_repository.update_text_line_content(line_id, content)
            elif 'lineId' in data and 'content' in data:
                line_id = data.get('lineId')
                content = data.get('content')
                self.result_repository.update_text_line_content(line_id, content)

            return {
                'success': True,
                'updated': True,
                'message': 'Result saved successfully'
            }, 200
        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 500

    def rerun_task(self, task_id: str) -> Tuple[Dict[str, Any], int]:
        try:
            task = self.task_repository.get_by_id(task_id)
            if not task:
                return {'error': 'Task not found'}, 404
            updated_task = self.task_repository.update_status(task_id, 'pending')
            updated_task = self.task_repository.update_progress(task_id, 0, 0)
            updated_task.error_message = None
            updated_task.completed_at = None
            self.task_repository.db.commit()
            self.task_repository.db.refresh(updated_task)
            return self.task_schema.dump(updated_task), 200
        except Exception as e:
            self.task_repository.db.rollback()
            return {'error': str(e)}, 500

    def delete_task(self, task_id: str) -> Tuple[Dict[str, Any], int]:
        try:
            task = self.task_repository.get_by_id(task_id)
            if not task:
                return {'error': 'Task not found'}, 404
            self.task_repository.delete(task_id)
            return {'message': 'Task deleted successfully'}, 200
        except Exception as e:
            self.task_repository.db.rollback()
            return {'error': str(e)}, 500
