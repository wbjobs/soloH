from flask import Blueprint, jsonify, request

collations_bp = Blueprint('collations', __name__)

_collation_controller = None


def get_collation_controller():
    global _collation_controller
    if _collation_controller is None:
        from app.controllers.collation_controller import CollationController
        _collation_controller = CollationController()
    return _collation_controller


@collations_bp.route('', methods=['POST'])
def create_collation():
    collation_controller = get_collation_controller()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    result, status = collation_controller.create_collation(data)
    return jsonify(result), status


@collations_bp.route('/<collation_id>', methods=['GET'])
def get_collation(collation_id):
    collation_controller = get_collation_controller()
    result, status = collation_controller.get_collation(collation_id)
    return jsonify(result), status


@collations_bp.route('/task/<task_id>', methods=['GET'])
def list_task_collations(task_id):
    collation_controller = get_collation_controller()
    result, status = collation_controller.list_collations(task_id)
    return jsonify(result), status
