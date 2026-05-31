import os
from flask import Blueprint, request, jsonify, current_app

from services import ImagePreprocessor, JianziDetector

detection_bp = Blueprint('detection', __name__)


@detection_bp.route('/api/preprocess', methods=['POST'])
def preprocess_image():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        image_id = data.get('imageId')
        if not image_id:
            return jsonify({'error': 'imageId is required'}), 400

        rotation = float(data.get('rotation', 0))
        threshold = int(data.get('threshold', 127))

        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        preprocessor = ImagePreprocessor(temp_dir)

        processed_filename, width, height = preprocessor.preprocess(
            image_id=image_id,
            rotation=rotation,
            threshold=threshold
        )

        return jsonify({
            'imageId': image_id,
            'processedUrl': f"/api/temp/{processed_filename}",
            'width': width,
            'height': height
        }), 200

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Preprocessing failed: {str(e)}'}), 500


@detection_bp.route('/api/detect', methods=['POST'])
def detect_jianzi():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        image_id = data.get('imageId')
        if not image_id:
            return jsonify({'error': 'imageId is required'}), 400

        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        detector = JianziDetector(temp_dir)

        result = detector.detect(image_id=image_id)

        return jsonify(result), 200

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'Detection failed: {str(e)}'}), 500
