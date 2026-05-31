import os
import uuid
from typing import Tuple, Dict, Any
from werkzeug.datastructures import FileStorage

from app import db
from app.services.file_service import FileService
from app.services.task_service import TaskService
from app.repositories.task_repository import TaskRepository


class FileController:
    def __init__(self):
        self.task_repo = TaskRepository(db.session)
        self.file_service = FileService(self.task_repo)
        self.task_service = TaskService(self.task_repo)

    def upload_file(self, file: FileStorage) -> Tuple[Dict[str, Any], int]:
        try:
            is_valid, error = self.file_service.validate_file(file)
            if not is_valid:
                return {'error': error}, 400

            task_id = str(uuid.uuid4())
            original_filename = file.filename
            file_type = self.file_service.get_file_type(original_filename)

            saved_path, saved_filename = self.file_service.save_file(file, task_id)

            image_paths, page_count = self.file_service.process_file(
                saved_path, task_id, file_type
            )

            task = self.task_service.create_task(
                file_name=original_filename,
                file_type=file_type,
                page_count=page_count
            )

            from tasks.processing_tasks import process_document_task
            process_document_task.delay(saved_path, task.id)

            from app.schemas.task_schema import TaskSchema
            return TaskSchema().dump(task), 201

        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 500
