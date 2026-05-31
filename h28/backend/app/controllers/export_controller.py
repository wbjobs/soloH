import os
import json
from typing import Tuple, Dict, Any
from flask import current_app
from app import db
from app.services.export_service import ExportService
from app.repositories.task_repository import TaskRepository
from app.repositories.result_repository import ResultRepository


class ExportController:
    ALLOWED_FORMATS = ['markdown', 'tei', 'txt', 'json']

    def __init__(self):
        self.task_repository = TaskRepository(db.session)
        self.result_repository = ResultRepository(db.session)
        self.export_service = ExportService(self.result_repository, self.task_repository)
        self._export_dir = None

    @property
    def export_dir(self):
        if self._export_dir is None:
            self._export_dir = current_app.config.get('EXPORT_FOLDER', os.path.join('storage', 'exports'))
            os.makedirs(self._export_dir, exist_ok=True)
        return self._export_dir

    def export_task_result(
        self, 
        task_id: str, 
        format: str = 'markdown',
        include_confidence: bool = True,
        include_coordinates: bool = False
    ) -> Tuple[Dict[str, Any], int]:
        try:
            task = self.task_repository.get_by_id(task_id)
            if not task:
                return {'error': 'Task not found'}, 404
            if task.status != 'completed':
                return {'error': 'Task not completed'}, 400
            if format not in self.ALLOWED_FORMATS:
                return {'error': f'Unsupported format. Allowed formats: {self.ALLOWED_FORMATS}'}, 400

            export_options = {
                'include_confidence': include_confidence,
                'include_coordinates': include_coordinates
            }

            if format == 'markdown':
                content = self.export_service.export_markdown(task_id, **export_options)
                filename = f"{task_id}.md"
            elif format == 'tei':
                content = self.export_service.export_tei_xml(task_id, **export_options)
                filename = f"{task_id}_tei.xml"
            elif format == 'txt':
                content = self.export_service.export_txt(task_id, **export_options)
                filename = f"{task_id}.txt"
            elif format == 'json':
                content = json.dumps(self._get_json_result(task_id, **export_options), ensure_ascii=False, indent=2)
                filename = f"{task_id}.json"

            file_path = os.path.join(self.export_dir, filename)
            self.export_service.export_to_file(content, file_path)

            return {
                'filePath': file_path,
                'filename': filename,
                'format': format,
                'content': content
            }, 200
        except Exception as e:
            return {'error': str(e)}, 500

    def _get_json_result(
        self, 
        task_id: str,
        include_confidence: bool = True,
        include_coordinates: bool = False
    ) -> Dict[str, Any]:
        page_results = self.result_repository.get_page_results_by_task_id(task_id)
        full_text = self.result_repository.get_full_text(task_id)
        
        pages = []
        for pr in page_results:
            page_data = {
                'pageNumber': pr.page_number,
                'width': pr.width,
                'height': pr.height,
                'imagePath': pr.image_path,
                'textLines': []
            }
            
            for tl in pr.text_lines:
                line_data = {
                    'id': tl.id,
                    'content': tl.content,
                    'columnIndex': tl.column_index,
                    'lineIndex': tl.line_index,
                }
                
                if include_confidence:
                    line_data['confidence'] = tl.confidence
                
                if include_coordinates:
                    line_data['textBoxes'] = [
                        {
                            'x1': tb.x1, 'y1': tb.y1,
                            'x2': tb.x2, 'y2': tb.y2,
                            'x3': tb.x3, 'y3': tb.y3,
                            'x4': tb.x4, 'y4': tb.y4,
                            'confidence': tb.confidence if include_confidence else None
                        }
                        for tb in tl.text_boxes
                    ]
                
                page_data['textLines'].append(line_data)
            
            pages.append(page_data)
        
        return {
            'taskId': task_id,
            'fullText': full_text,
            'pages': pages
        }
