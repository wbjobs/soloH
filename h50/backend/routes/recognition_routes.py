import os
import json
from flask import Blueprint, request, jsonify, current_app

from services import ComponentRecognizer

recognition_bp = Blueprint('recognition', __name__)

jianzi_storage = {}


@recognition_bp.route('/api/recognize', methods=['POST'])
def recognize_jianzi():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        image_id = data.get('imageId')
        jianzi_id = data.get('jianziId')
        jianzi_data = data.get('jianzi')

        if not image_id:
            return jsonify({'error': 'imageId is required'}), 400
        if not jianzi_id:
            return jsonify({'error': 'jianziId is required'}), 400
        if not jianzi_data:
            return jsonify({'error': 'jianzi data is required'}), 400

        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        dict_path = current_app.config.get('DICT_PATH', 'backend/data/dictionary.json')

        recognizer = ComponentRecognizer(temp_dir, dict_path)

        result = recognizer.recognize(
            image_id=image_id,
            jianzi_id=jianzi_id,
            jianzi_data=jianzi_data
        )

        jianzi_storage[jianzi_id] = result

        return jsonify(result), 200

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'Recognition failed: {str(e)}'}), 500


@recognition_bp.route('/api/jianzi/<id>', methods=['PUT'])
def update_jianzi(id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        existing = jianzi_storage.get(id, {
            'id': id,
            'bbox': [0, 0, 100, 100],
            'components': [],
            'gongche': '',
            'description': '',
            'confidence': 0.0
        })

        if 'bbox' in data:
            existing['bbox'] = data['bbox']
        if 'components' in data:
            existing['components'] = data['components']
        if 'gongche' in data:
            existing['gongche'] = data['gongche']
        if 'description' in data:
            existing['description'] = data['description']
        if 'confidence' in data:
            existing['confidence'] = data['confidence']

        jianzi_storage[id] = existing

        return jsonify(existing), 200

    except Exception as e:
        return jsonify({'error': f'Update failed: {str(e)}'}), 500
