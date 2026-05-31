import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import cv2
import numpy as np

upload_bp = Blueprint('upload', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@upload_bp.route('/api/upload', methods=['POST'])
def upload_image():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400

        file = request.files['image']

        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400

        image_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()

        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        os.makedirs(temp_dir, exist_ok=True)

        save_filename = f"{image_id}.{ext}"
        save_path = os.path.join(temp_dir, save_filename)

        file.save(save_path)

        img = cv2.imdecode(np.fromfile(save_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            os.remove(save_path)
            return jsonify({'error': 'Invalid image file'}), 400

        height, width = img.shape[:2]

        png_path = os.path.join(temp_dir, f"{image_id}.png")
        cv2.imwrite(png_path, img)

        if save_path != png_path:
            os.remove(save_path)

        return jsonify({
            'imageId': image_id,
            'width': width,
            'height': height,
            'url': f"/api/temp/{image_id}.png"
        }), 200

    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500
