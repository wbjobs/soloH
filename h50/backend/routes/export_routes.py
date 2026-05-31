import os
import json
from flask import Blueprint, request, jsonify, send_file, current_app

from services import GongcheConverter

export_bp = Blueprint('export', __name__)


@export_bp.route('/api/download/<type>/<id>', methods=['GET'])
def download_file(type, id):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')

        if type == 'midi':
            filename = f"{id}.mid"
            mimetype = 'audio/midi'
        elif type == 'audio':
            filename = f"{id}.wav"
            mimetype = 'audio/wav'
        elif type == 'text':
            filename = f"{id}.txt"
            mimetype = 'text/plain'
        else:
            return jsonify({'error': 'Invalid type. Must be midi, audio, or text'}), 400

        file_path = os.path.join(temp_dir, filename)

        if not os.path.exists(file_path):
            return jsonify({'error': f'File not found: {filename}'}), 404

        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500


@export_bp.route('/api/gongche', methods=['GET'])
def get_gongche():
    try:
        jianzi_id = request.args.get('jianziId')
        dict_path = current_app.config.get('DICT_PATH', 'backend/data/dictionary.json')
        converter = GongcheConverter(dict_path)

        if jianzi_id:
            from routes.recognition_routes import jianzi_storage
            jianzi = jianzi_storage.get(jianzi_id)

            if not jianzi:
                return jsonify({'error': f'Jianzi not found: {jianzi_id}'}), 404

            result = converter.convert(jianzi)
            return jsonify(result), 200
        else:
            jianzi_list_str = request.args.get('jianziList')
            if jianzi_list_str:
                try:
                    jianzi_list = json.loads(jianzi_list_str)
                    results = converter.convert_batch(jianzi_list)
                    return jsonify({'gongcheList': results}), 200
                except json.JSONDecodeError:
                    return jsonify({'error': 'Invalid jianziList JSON'}), 400

            table = converter.get_gongche_table()
            return jsonify(table), 200

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'Gongche conversion failed: {str(e)}'}), 500
