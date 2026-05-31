import os
import time
import random
import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from PIL import Image
from celery import shared_task
from app import db
from app.repositories.task_repository import TaskRepository
from app.repositories.result_repository import ResultRepository
from app.core.socketio_events import emit_progress, emit_completed, emit_failed

from ml import CTPNDetector, CRNNRecognizer, BERTPunctuator, PostProcessor

logger = logging.getLogger(__name__)

USE_MOCK = True

_detector = None
_recognizer = None
_punctuator = None
_post_processor = None


def _get_detector():
    global _detector
    if _detector is None:
        _detector = CTPNDetector(use_mock=USE_MOCK)
    return _detector


def _get_recognizer():
    global _recognizer
    if _recognizer is None:
        _recognizer = CRNNRecognizer(use_mock=USE_MOCK)
    return _recognizer


def _get_punctuator():
    global _punctuator
    if _punctuator is None:
        _punctuator = BERTPunctuator(use_mock=USE_MOCK)
    return _punctuator


def _get_post_processor():
    global _post_processor
    if _post_processor is None:
        _post_processor = PostProcessor()
    return _post_processor


def _preprocess_image(image_path: str) -> np.ndarray:
    img = Image.open(image_path).convert('RGB')
    return np.array(img)


def _preprocess_file(file_path: str) -> Dict[str, Any]:
    time.sleep(0.5)
    return {
        'page_count': random.randint(1, 5),
        'pages': [
            {
                'page_number': i + 1,
                'width': random.randint(800, 1200),
                'height': random.randint(1000, 1600),
                'image_path': f'/storage/processed/{os.path.basename(file_path)}_page_{i + 1}.png'
            }
            for i in range(random.randint(1, 5))
        ]
    }


def _detect_text_boxes(image: np.ndarray) -> List[Dict[str, Any]]:
    detector = _get_detector()
    return detector.detect(image)


def _recognize_text(
    image: np.ndarray,
    text_boxes: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    recognizer = _get_recognizer()
    box_images = []
    for box in text_boxes:
        bbox = box.get('bbox', [0, 0, image.shape[1], image.shape[0]])
        x1, y1, x2, y2 = [int(coord) for coord in bbox]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(image.shape[1], x2)
        y2 = min(image.shape[0], y2)
        if x2 > x1 and y2 > y1:
            box_img = image[y1:y2, x1:x2]
        else:
            box_img = image
        box_images.append(box_img)
    return recognizer.recognize_batch(box_images, return_candidates=True, top_k=5)


def _punctuate_texts(texts: List[str]) -> List[Dict[str, Any]]:
    punctuator = _get_punctuator()
    return punctuator.punctuate_batch(texts)


def _postprocess_results(
    detection_results: List[Dict[str, Any]],
    recognition_results: List[Dict[str, Any]],
    punctuation_results: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    post_processor = _get_post_processor()
    return post_processor.process(
        detection_results=detection_results,
        recognition_results=recognition_results,
        punctuation_results=punctuation_results
    )


def _bbox_to_four_points(bbox: List[float]) -> Dict[str, float]:
    x1, y1, x2, y2 = bbox
    return {
        'x1': float(x1),
        'y1': float(y1),
        'x2': float(x2),
        'y2': float(y1),
        'x3': float(x2),
        'y3': float(y2),
        'x4': float(x1),
        'y4': float(y2),
    }


def _convert_ml_to_db_format(
    ml_result: Dict[str, Any],
    page_width: int,
    page_height: int
) -> List[Dict[str, Any]]:
    recognition_results = ml_result.get('recognition_results', [])
    text_lines = []

    columns = {}
    for idx, result in enumerate(recognition_results):
        bbox = result.get('bbox', [0, 0, 0, 0])
        column_idx = result.get('column', 0)
        line_idx = result.get('line', idx)

        if column_idx not in columns:
            columns[column_idx] = []
        columns[column_idx].append((line_idx, result))

    line_global_idx = 0
    for column_idx in sorted(columns.keys()):
        sorted_lines = sorted(columns[column_idx], key=lambda x: x[0])
        for local_line_idx, result in sorted_lines:
            bbox = result.get('bbox', [0, 0, 0, 0])
            four_points = _bbox_to_four_points(bbox)
            confidence = result.get('confidence', 0.0)
            candidates = result.get('candidates', [])
            content = result.get('punctuated_text', result.get('text', ''))

            text_line = {
                'content': content,
                'confidence': confidence,
                'candidates': candidates,
                'column_index': column_idx,
                'line_index': line_global_idx,
                'text_boxes': [{
                    **four_points,
                    'confidence': result.get('confidence', confidence)
                }]
            }
            text_lines.append(text_line)
            line_global_idx += 1

    return text_lines


@shared_task(bind=True, name='tasks.process_document_task')
def process_document_task(self, file_path: str, task_id: str):
    task_repo = TaskRepository(db.session)
    result_repo = ResultRepository(db.session)

    try:
        task_repo.update_status(task_id, 'preprocessing')
        emit_progress(task_id, 'preprocessing', 5, '开始预处理文档...')

        preprocess_result = _preprocess_file(file_path)
        page_count = len(preprocess_result['pages'])

        task_repo.update_progress(task_id, 10, current_page=1)
        emit_progress(task_id, 'preprocessing', 10, f'文档预处理完成，共 {page_count} 页', total_pages=page_count)

        overall_progress_start = 10
        overall_progress_end = 90
        per_page_progress = (overall_progress_end - overall_progress_start) / page_count

        for page_idx, page_data in enumerate(preprocess_result['pages']):
            current_page = page_idx + 1

            task_repo.update_status(task_id, 'detecting')
            progress = int(overall_progress_start + page_idx * per_page_progress)
            emit_progress(task_id, 'detecting', progress, f'第 {current_page}/{page_count} 页：CTPN文本检测中...', current_page=current_page, total_pages=page_count)

            image = _preprocess_image(page_data['image_path'])
            detection_results = _detect_text_boxes(image)

            task_repo.update_status(task_id, 'recognizing')
            progress = int(overall_progress_start + page_idx * per_page_progress + per_page_progress * 0.25)
            emit_progress(task_id, 'recognizing', progress, f'第 {current_page}/{page_count} 页：CRNN文本识别中...', current_page=current_page, total_pages=page_count)

            recognition_results = _recognize_text(image, detection_results)

            task_repo.update_status(task_id, 'punctuating')
            progress = int(overall_progress_start + page_idx * per_page_progress + per_page_progress * 0.5)
            emit_progress(task_id, 'punctuating', progress, f'第 {current_page}/{page_count} 页：BERT标点恢复中...', current_page=current_page, total_pages=page_count)

            texts_to_punctuate = [r.get('text', '') for r in recognition_results]
            punctuation_results = _punctuate_texts(texts_to_punctuate)

            task_repo.update_status(task_id, 'postprocessing')
            progress = int(overall_progress_start + page_idx * per_page_progress + per_page_progress * 0.75)
            emit_progress(task_id, 'postprocessing', progress, f'第 {current_page}/{page_count} 页：后处理中...', current_page=current_page, total_pages=page_count)

            ml_result = _postprocess_results(detection_results, recognition_results, punctuation_results)
            text_lines = _convert_ml_to_db_format(ml_result, page_data['width'], page_data['height'])

            page_result_data = {
                'width': page_data['width'],
                'height': page_data['height'],
                'image_path': page_data['image_path'],
                'text_lines': text_lines
            }
            result_repo.save_page_result(task_id, current_page, page_result_data)

            progress = int(overall_progress_start + (page_idx + 1) * per_page_progress)
            task_repo.update_progress(task_id, progress, current_page=current_page)
            emit_progress(task_id, 'postprocessing', progress, f'第 {current_page}/{page_count} 页处理完成', current_page=current_page, total_pages=page_count)

        task_repo.update_status(task_id, 'completed')
        task_repo.update_progress(task_id, 100, current_page=page_count)
        emit_progress(task_id, 'completed', 100, '文档处理完成！', current_page=page_count, total_pages=page_count)

        full_text = result_repo.get_full_text(task_id)
        result = {
            'task_id': task_id,
            'status': 'completed',
            'page_count': page_count,
            'full_text': full_text
        }
        emit_completed(task_id, result)

        return result

    except Exception as e:
        error_message = str(e)
        logger.exception(f"Task {task_id} failed: {error_message}")
        task_repo.update_status(task_id, 'failed', error_message=error_message)
        emit_failed(task_id, error_message)
        raise


@shared_task(bind=True, name='tasks.text_detection')
def text_detection(self, image_path):
    self.update_state(state='PROGRESS', meta={'status': 'Detecting text regions'})
    try:
        image = _preprocess_image(image_path)
        detection_results = _detect_text_boxes(image)
        return {'bboxes': [r.get('bbox', []) for r in detection_results]}
    except Exception as e:
            logger.exception(f"Text detection failed: {str(e)}")
            return {'bboxes': []}


@shared_task(bind=True, name='tasks.text_recognition')
def text_recognition(self, image_path, bboxes):
    self.update_state(state='PROGRESS', meta={'status': 'Recognizing text'})
    try:
        image = _preprocess_image(image_path)
        detection_results = [{'bbox': bbox} for bbox in bboxes]
        recognition_results = _recognize_text(image, detection_results)
        texts = [r.get('text', '') for r in recognition_results]
        return {'text': '\n'.join(texts)}
    except Exception as e:
            logger.exception(f"Text recognition failed: {str(e)}")
            return {'text': ''}
