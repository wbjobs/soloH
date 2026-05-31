from flask import jsonify, request
from app.api import api_bp


@api_bp.route('/documents', methods=['GET'])
def list_documents():
    return jsonify({'documents': []})


@api_bp.route('/documents/<int:doc_id>', methods=['GET'])
def get_document(doc_id):
    return jsonify({'id': doc_id, 'name': 'example'})
