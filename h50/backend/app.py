import os
import json
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from dotenv import load_dotenv

from routes import upload_bp, detection_bp, recognition_bp, audio_bp, export_bp, advanced_bp

load_dotenv()

app = Flask(__name__)

CORS(app, resources={r"/api/*": {"origins": "*"}})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['TEMP_DIR'] = os.path.join(BASE_DIR, 'data', 'temp')
app.config['DICT_PATH'] = os.path.join(BASE_DIR, 'data', 'dictionary.json')
app.config['SAMPLE_DIR'] = os.path.join(BASE_DIR, 'data', 'samples')

os.makedirs(app.config['TEMP_DIR'], exist_ok=True)
os.makedirs(app.config['SAMPLE_DIR'], exist_ok=True)

DATA_DIR = os.path.join(BASE_DIR, 'data')
with open(os.path.join(DATA_DIR, 'dictionary.json'), 'r', encoding='utf-8') as f:
    DICTIONARY = json.load(f)

app.register_blueprint(upload_bp)
app.register_blueprint(detection_bp)
app.register_blueprint(recognition_bp)
app.register_blueprint(audio_bp)
app.register_blueprint(export_bp)
app.register_blueprint(advanced_bp)

@app.route('/api/temp/<filename>')
def serve_temp_file(filename):
    temp_dir = app.config.get('TEMP_DIR', 'backend/data/temp')
    return send_from_directory(temp_dir, filename)

@app.route('/api/dictionary', methods=['GET'])
def get_dictionary():
    return jsonify(DICTIONARY)

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'service': 'guqin-jianzi-api'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
