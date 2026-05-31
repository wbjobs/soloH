import os
from typing import List, Tuple, Optional
from werkzeug.datastructures import FileStorage
from PIL import Image
import fitz
from flask import current_app
from app.repositories.task_repository import TaskRepository


class FileService:
    def __init__(self, task_repository: TaskRepository):
        self.task_repository = task_repository
        self.allowed_extensions = {'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'pdf'}

    def _get_extension(self, filename: str) -> str:
        return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    def validate_file(self, file: FileStorage) -> Tuple[bool, Optional[str]]:
        if not file or not file.filename:
            return False, '未选择文件'
        
        filename = file.filename
        extension = self._get_extension(filename)
        
        if extension not in self.allowed_extensions:
            return False, f'不支持的文件格式: {extension}'
        
        return True, None

    def _get_unique_filename(self, task_id: str, original_filename: str) -> str:
        extension = self._get_extension(original_filename)
        return f"{task_id}.{extension}"

    def save_file(self, file: FileStorage, task_id: str) -> Tuple[str, str]:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        filename = self._get_unique_filename(task_id, file.filename)
        file_path = os.path.join(upload_folder, filename)
        
        file.save(file_path)
        
        return file_path, filename

    def get_file_type(self, filename: str) -> str:
        extension = self._get_extension(filename)
        return 'pdf' if extension == 'pdf' else 'image'

    def pdf_to_images(self, pdf_path: str, task_id: str) -> Tuple[List[str], int]:
        processed_folder = current_app.config['PROCESSED_FOLDER']
        task_folder = os.path.join(processed_folder, task_id)
        os.makedirs(task_folder, exist_ok=True)
        
        image_paths = []
        
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        
        for page_num in range(page_count):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            image_path = os.path.join(task_folder, f"page_{page_num + 1}.png")
            pix.save(image_path)
            image_paths.append(image_path)
        
        doc.close()
        
        return image_paths, page_count

    def prepare_image(self, image_path: str, task_id: str) -> Tuple[List[str], int]:
        processed_folder = current_app.config['PROCESSED_FOLDER']
        task_folder = os.path.join(processed_folder, task_id)
        os.makedirs(task_folder, exist_ok=True)
        
        img = Image.open(image_path)
        image_path = os.path.join(task_folder, "page_1.png")
        img.save(image_path, 'PNG')
        
        return [image_path], 1

    def process_file(self, file_path: str, task_id: str, file_type: str) -> Tuple[List[str], int]:
        if file_type == 'pdf':
            return self.pdf_to_images(file_path, task_id)
        else:
            return self.prepare_image(file_path, task_id)

    def get_task_folder(self, task_id: str) -> str:
        processed_folder = current_app.config['PROCESSED_FOLDER']
        return os.path.join(processed_folder, task_id)
