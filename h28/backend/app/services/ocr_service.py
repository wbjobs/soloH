from typing import List, Dict, Any, Callable, Optional
from PIL import Image
import numpy as np
from app.repositories.task_repository import TaskRepository
from app.repositories.result_repository import ResultRepository
from app.repositories.annotation_repository import AnnotationRepository
from app.services.annotation_service import AnnotationService


PIPELINE_STAGES = [
    ('preprocessing', '预处理中', 10),
    ('detecting', '检测文字区域中', 25),
    ('recognizing', '识别文字中', 60),
    ('postprocessing', '后处理中', 75),
    ('separating_annotations', '分离批注中', 85),
    ('punctuating', '添加标点中', 95),
]


class OCRService:
    def __init__(
        self,
        task_repository: TaskRepository,
        result_repository: ResultRepository,
        annotation_repository: AnnotationRepository,
        progress_callback: Optional[Callable[[str, str, int, Optional[int], int], None]] = None
    ):
        self.task_repository = task_repository
        self.result_repository = result_repository
        self.annotation_repository = annotation_repository
        self.annotation_service = AnnotationService(annotation_repository, result_repository)
        self.progress_callback = progress_callback

    def _report_progress(
        self,
        task_id: str,
        status: str,
        progress: int,
        current_page: Optional[int],
        total_pages: int,
        message: str
    ) -> None:
        self.task_repository.update_status(task_id, status)
        self.task_repository.update_progress(task_id, progress, current_page)
        
        if self.progress_callback:
            self.progress_callback(task_id, status, progress, current_page, total_pages, message)

    def _preprocess(self, image_path: str) -> np.ndarray:
        img = Image.open(image_path).convert('L')
        return np.array(img)

    def _detect(self, image: np.ndarray) -> List[Dict[str, Any]]:
        height, width = image.shape
        return [{
            'x1': 50, 'y1': 50, 'x2': width - 50, 'y2': 50,
            'x3': width - 50, 'y3': 100, 'x4': 50, 'y4': 100,
            'confidence': 0.95
        }]

    def _recognize(self, image: np.ndarray, text_boxes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{
            'content': '这是示例识别文本',
            'text_boxes': text_boxes
        }]

    def _postprocess(self, text_lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return text_lines

    def _punctuate(self, text_lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for line in text_lines:
            content = line.get('content', '')
            if content and not content.endswith('。'):
                line['content'] = content + '。'
        return text_lines

    def _process_single_page(
        self,
        task_id: str,
        image_path: str,
        page_number: int,
        total_pages: int
    ) -> Dict[str, Any]:
        img = Image.open(image_path)
        width, height = img.size
        
        image = self._preprocess(image_path)
        self._report_progress(
            task_id, 'preprocessing',
            10 + (page_number - 1) * (90 / max(total_pages, 1)),
            page_number, total_pages, f'第 {page_number}/{total_pages} 页预处理完成'
        )
        
        text_boxes = self._detect(image)
        self._report_progress(
            task_id, 'detecting',
            25 + (page_number - 1) * (90 / max(total_pages, 1)),
            page_number, total_pages, f'第 {page_number}/{total_pages} 页检测完成，发现 {len(text_boxes)} 个文字区域'
        )
        
        text_lines = self._recognize(image, text_boxes)
        self._report_progress(
            task_id, 'recognizing',
            60 + (page_number - 1) * (90 / max(total_pages, 1)),
            page_number, total_pages, f'第 {page_number}/{total_pages} 页识别完成'
        )
        
        text_lines = self._postprocess(text_lines)
        self._report_progress(
            task_id, 'postprocessing',
            75 + (page_number - 1) * (90 / max(total_pages, 1)),
            page_number, total_pages, f'第 {page_number}/{total_pages} 页后处理完成'
        )
        
        return {
            'width': width,
            'height': height,
            'image_path': image_path,
            'text_lines': text_lines,
            'image': image
        }

    def process_task(self, task_id: str, image_paths: List[str]) -> None:
        total_pages = len(image_paths)
        
        self._report_progress(task_id, 'preprocessing', 5, 0, total_pages, '开始处理')
        
        for idx, image_path in enumerate(image_paths, 1):
            page_data = self._process_single_page(task_id, image_path, idx, total_pages)
            image = page_data.pop('image')
            
            page_result = self.result_repository.save_page_result(task_id, idx, page_data)
            
            main_text_lines, annotations = self.annotation_service.separate_and_recognize(
                page_result.id,
                image,
                page_data['text_lines']
            )
            self._report_progress(
                task_id, 'separating_annotations',
                85 + (idx - 1) * (90 / max(total_pages, 1)),
                idx, total_pages, f'第 {idx}/{total_pages} 页批注分离完成，发现 {len(annotations)} 个批注'
            )
            
            for text_line in page_result.text_lines:
                for main_line in main_text_lines:
                    if text_line.content == main_line.get('content'):
                        filtered_boxes = []
                        for box in main_line.get('text_boxes', []):
                            for tb in text_line.text_boxes:
                                if (abs(tb.x1 - box['x1']) < 1 and
                                    abs(tb.y1 - box['y1']) < 1 and
                                    abs(tb.x2 - box['x2']) < 1 and
                                    abs(tb.y2 - box['y2']) < 1):
                                    filtered_boxes.append(tb)
                                    break
                        text_line.text_boxes = filtered_boxes
                        break
            
            punctuated_lines = self._punctuate(main_text_lines)
            for text_line, punctuated in zip(page_result.text_lines, punctuated_lines):
                text_line.content = punctuated.get('content', text_line.content)
            
            self._report_progress(
                task_id, 'punctuating',
                95 + (idx - 1) * (90 / max(total_pages, 1)),
                idx, total_pages, f'第 {idx}/{total_pages} 页标点添加完成'
            )
        
        self._report_progress(task_id, 'completed', 100, total_pages, total_pages, '处理完成')
        self.task_repository.update_status(task_id, 'completed')
        self.task_repository.update_progress(task_id, 100, total_pages)
