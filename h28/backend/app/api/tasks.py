from flask import Blueprint, jsonify, request, send_file, make_response
from app.core.socketio_events import socketio
import os

tasks_bp = Blueprint('tasks', __name__)

_task_controller = None
_export_controller = None


def get_task_controller():
    global _task_controller
    if _task_controller is None:
        from app.controllers.task_controller import TaskController
        _task_controller = TaskController()
    return _task_controller


def get_export_controller():
    global _export_controller
    if _export_controller is None:
        from app.controllers.export_controller import ExportController
        _export_controller = ExportController()
    return _export_controller


@tasks_bp.route('', methods=['POST'])
def create_task():
    task_controller = get_task_controller()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    result, status = task_controller.create_task(data)
    if status == 201:
        socketio.emit('task_created', result)
    return jsonify(result), status


@tasks_bp.route('', methods=['GET'])
def get_tasks():
    task_controller = get_task_controller()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('perPage', 10, type=int)
    status = request.args.get('status', type=str)
    result, status_code = task_controller.get_task_list(page, per_page, status)
    return jsonify(result), status_code


@tasks_bp.route('/<task_id>', methods=['GET'])
def get_task(task_id):
    task_controller = get_task_controller()
    result, status = task_controller.get_task_by_id(task_id)
    return jsonify(result), status


@tasks_bp.route('/<task_id>/result', methods=['GET'])
def get_task_result(task_id):
    task_controller = get_task_controller()
    result, status = task_controller.get_task_result(task_id)
    return jsonify(result), status


@tasks_bp.route('/<task_id>/result', methods=['PUT'])
def update_task_result(task_id):
    task_controller = get_task_controller()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    result, status = task_controller.update_task_result(task_id, data)
    if status == 200:
        socketio.emit('result_updated', {'taskId': task_id, **data})
    return jsonify(result), status


@tasks_bp.route('/<task_id>/rerun', methods=['POST'])
def rerun_task(task_id):
    task_controller = get_task_controller()
    result, status = task_controller.rerun_task(task_id)
    if status == 200:
        socketio.emit('task_rerun', result)
    return jsonify(result), status


@tasks_bp.route('/<task_id>/export', methods=['GET'])
def export_task_result(task_id):
    export_controller = get_export_controller()
    format = request.args.get('format', 'markdown', type=str)
    include_confidence = request.args.get('include_confidence', 'true', type=str).lower() == 'true'
    include_coordinates = request.args.get('include_coordinates', 'false', type=str).lower() == 'true'
    download = request.args.get('download', 'true', type=str).lower() == 'true'
    
    allowed_formats = ['markdown', 'tei', 'txt', 'json']
    if format not in allowed_formats:
        return jsonify({'error': f'Unsupported format. Allowed formats: {allowed_formats}'}), 400
    
    result, status = export_controller.export_task_result(
        task_id, 
        format, 
        include_confidence=include_confidence,
        include_coordinates=include_coordinates
    )
    
    if status != 200:
        return jsonify(result), status
    
    filename = result['filename']
    content = result['content']
    file_path = result['filePath']
    
    if download:
        mime_types = {
            'markdown': 'text/markdown; charset=utf-8',
            'tei': 'application/xml; charset=utf-8',
            'txt': 'text/plain; charset=utf-8',
            'json': 'application/json; charset=utf-8'
        }
        
        if os.path.exists(file_path):
            response = make_response(send_file(
                file_path,
                mimetype=mime_types.get(format, 'application/octet-stream'),
                as_attachment=True,
                download_name=filename
            ))
        else:
            response = make_response(content)
            response.headers['Content-Type'] = mime_types.get(format, 'application/octet-stream')
        
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{filename}"
        return response
    
    return jsonify(result), status


@tasks_bp.route('/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    task_controller = get_task_controller()
    result, status = task_controller.delete_task(task_id)
    if status == 200:
        socketio.emit('task_deleted', {'taskId': task_id})
    return jsonify(result), status
