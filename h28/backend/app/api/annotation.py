from flask import Blueprint, jsonify, request
from app.core.socketio_events import socketio
from app.repositories.annotation_repository import AnnotationRepository
from app.repositories.result_repository import ResultRepository
from app.services.annotation_service import AnnotationService
from app.extensions import db


annotations_bp = Blueprint('annotations', __name__)

_annotation_service = None


def get_annotation_service():
    global _annotation_service
    if _annotation_service is None:
        annotation_repo = AnnotationRepository(db.session)
        result_repo = ResultRepository(db.session)
        _annotation_service = AnnotationService(annotation_repo, result_repo)
    return _annotation_service


@annotations_bp.route('/tasks/<task_id>/pages/<int:page_number>/annotations', methods=['GET'])
def get_annotations(task_id, page_number):
    annotation_service = get_annotation_service()
    result_repo = ResultRepository(db.session)

    page_results = result_repo.get_page_results_by_task_id(task_id)
    page_result = None
    for pr in page_results:
        if pr.page_number == page_number:
            page_result = pr
            break

    if not page_result:
        return jsonify({'error': 'Page not found'}), 404

    annotations = annotation_service.get_annotations_by_page(page_result.id)
    return jsonify({
        'task_id': task_id,
        'page_number': page_number,
        'page_result_id': page_result.id,
        'annotations': annotations
    }), 200


@annotations_bp.route('/annotations/<int:annotation_id>', methods=['GET'])
def get_annotation(annotation_id):
    annotation_service = get_annotation_service()
    annotation = annotation_service.get_annotation(annotation_id)
    if not annotation:
        return jsonify({'error': 'Annotation not found'}), 404
    return jsonify(annotation), 200


@annotations_bp.route('/annotations/<int:annotation_id>', methods=['PUT'])
def update_annotation(annotation_id):
    annotation_service = get_annotation_service()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    annotation = annotation_service.update_annotation(annotation_id, data)
    if not annotation:
        return jsonify({'error': 'Annotation not found'}), 404

    socketio.emit('annotation_updated', {'annotationId': annotation_id, **data})
    return jsonify(annotation), 200


@annotations_bp.route('/annotations/<int:annotation_id>', methods=['DELETE'])
def delete_annotation(annotation_id):
    annotation_service = get_annotation_service()
    success = annotation_service.delete_annotation(annotation_id)
    if not success:
        return jsonify({'error': 'Annotation not found'}), 404

    socketio.emit('annotation_deleted', {'annotationId': annotation_id})
    return jsonify({'message': 'Annotation deleted successfully'}), 200


@annotations_bp.route('/tasks/<task_id>/annotations', methods=['GET'])
def get_task_annotations(task_id):
    annotation_service = get_annotation_service()
    annotations = annotation_service.get_annotations_by_task(task_id)
    return jsonify({
        'task_id': task_id,
        'annotations': annotations
    }), 200
