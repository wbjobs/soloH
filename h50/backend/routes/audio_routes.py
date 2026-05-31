import os
import json
from flask import Blueprint, request, jsonify, current_app

from services import AudioSynthesizer, MidiGenerator

audio_bp = Blueprint('audio', __name__)


@audio_bp.route('/api/synthesize', methods=['POST'])
def synthesize_audio():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        jianzi_list = data.get('jianziList')
        if not jianzi_list or not isinstance(jianzi_list, list):
            return jsonify({'error': 'jianziList is required and must be an array'}), 400

        tempo = int(data.get('tempo', 60))
        technique = data.get('technique', 'sanyin')

        if technique not in ['sanyin', 'anyin', 'fanyin']:
            return jsonify({'error': 'Invalid technique. Must be sanyin, anyin, or fanyin'}), 400

        if tempo < 20 or tempo > 240:
            return jsonify({'error': 'Tempo must be between 20 and 240'}), 400

        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        sample_dir = current_app.config.get('SAMPLE_DIR', 'backend/data/samples')

        audio_synthesizer = AudioSynthesizer(temp_dir, sample_dir)
        midi_generator = MidiGenerator(temp_dir)

        audio_filename, audio_duration = audio_synthesizer.synthesize(
            jianzi_list=jianzi_list,
            tempo=tempo,
            technique=technique
        )

        midi_filename, midi_duration = midi_generator.generate(
            jianzi_list=jianzi_list,
            tempo=tempo,
            technique=technique
        )

        return jsonify({
            'audioUrl': f"/api/temp/{audio_filename}",
            'midiUrl': f"/api/temp/{midi_filename}",
            'duration': round(max(audio_duration, midi_duration), 2),
            'tempo': tempo,
            'technique': technique
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Synthesis failed: {str(e)}'}), 500
