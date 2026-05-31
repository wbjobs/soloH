from flask import Blueprint, jsonify, request
from app.extensions import socketio

files_bp = Blueprint('files', __name__)

_file_controller = None


def get_file_controller():
    global _file_controller
    if _file_controller is None:
        from app.controllers.file_controller import FileController
        _file_controller = FileController()
    return _file_controller


@files_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file_controller = get_file_controller()
    file = request.files['file']
    result, status = file_controller.upload_file(file)

    if status == 201:
        socketio.emit('task_created', result)
        socketio.emit('file_uploaded', result)

    return jsonify(result), status
