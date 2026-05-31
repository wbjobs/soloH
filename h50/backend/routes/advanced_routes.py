import os
import json
import numpy as np
import cv2
from flask import Blueprint, request, jsonify, send_file, current_app
from typing import List, Dict, Any

from services import ScoreSerializer, DifficultyEvaluator, AudioSynthesizer

advanced_bp = Blueprint('advanced', __name__)


@advanced_bp.route('/api/score/create', methods=['POST'])
def create_score():
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        serializer = ScoreSerializer(temp_dir)
        
        title = request.form.get('title', '未命名曲目')
        metadata_str = request.form.get('metadata', '{}')
        metadata = json.loads(metadata_str)
        
        page_images = []
        page_jianzi_list = []
        
        files = request.files.getlist('pages')
        for i, file in enumerate(files):
            file_bytes = np.frombuffer(file.read(), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is not None:
                page_images.append(img)
        
        jianzi_data_str = request.form.get('jianzi_data', '[]')
        jianzi_data = json.loads(jianzi_data_str)
        
        if isinstance(jianzi_data, list) and len(jianzi_data) == len(page_images):
            page_jianzi_list = jianzi_data
        else:
            for _ in page_images:
                page_jianzi_list.append([])
        
        genre = metadata.get('genre', 'classical')
        score = serializer.create_serialized_score(
            title=title,
            page_images=page_images,
            page_jianzi_list=page_jianzi_list,
            metadata=metadata,
            genre=genre
        )
        
        return jsonify({
            'success': True,
            'score_id': score.id,
            'metadata': {
                'title': score.metadata.title,
                'composer': score.metadata.composer,
                'total_pages': score.metadata.total_pages,
                'total_jianzi': score.metadata.total_jianzi
            },
            'jianzi_count': len(score.jianzi_sequence)
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'创建曲目失败: {str(e)}'}), 500


@advanced_bp.route('/api/score/list', methods=['GET'])
def list_scores():
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        serializer = ScoreSerializer(temp_dir)
        
        scores = serializer.list_scores()
        return jsonify({
            'success': True,
            'scores': scores
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取曲目列表失败: {str(e)}'}), 500


@advanced_bp.route('/api/score/<score_id>', methods=['GET'])
def get_score(score_id):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        serializer = ScoreSerializer(temp_dir)
        
        score = serializer.load_score(score_id)
        if not score:
            return jsonify({'success': False, 'error': '曲目不存在'}), 404
        
        return jsonify({
            'success': True,
            'score': {
                'id': score.id,
                'metadata': {
                    'title': score.metadata.title,
                    'composer': score.metadata.composer,
                    'dynasty': score.metadata.dynasty,
                    'genre': score.metadata.genre,
                    'difficulty': score.metadata.difficulty,
                    'description': score.metadata.description,
                    'total_pages': score.metadata.total_pages,
                    'total_jianzi': score.metadata.total_jianzi,
                    'created_at': score.metadata.created_at,
                    'updated_at': score.metadata.updated_at
                },
                'pages': [{
                    'page_number': p.page_number,
                    'width': p.width,
                    'height': p.height,
                    'jianzi_count': p.jianzi_count
                } for p in score.pages],
                'jianzi_sequence': score.jianzi_sequence,
                'gongche_sequence': score.gongche_sequence,
                'audio_synthesis_params': score.audio_synthesis_params
            }
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取曲目失败: {str(e)}'}), 500


@advanced_bp.route('/api/score/<score_id>/update', methods=['POST'])
def update_score(score_id):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        serializer = ScoreSerializer(temp_dir)
        
        data = request.json or {}
        jianzi_updates = data.get('jianzi_updates', [])
        audio_params = data.get('audio_synthesis_params')
        
        success = serializer.update_jianzi_sequence(score_id, jianzi_updates)
        
        if success and audio_params:
            score = serializer.load_score(score_id)
            if score:
                score.audio_synthesis_params.update(audio_params)
                from dataclasses import asdict
                from datetime import datetime
                score.metadata.updated_at = datetime.now().isoformat()
                
                score_dir = os.path.join(serializer.scores_dir, score_id)
                score_dict = {
                    "id": score.id,
                    "metadata": asdict(score.metadata),
                    "pages": [asdict(p) for p in score.pages],
                    "jianzi_sequence": score.jianzi_sequence,
                    "gongche_sequence": score.gongche_sequence,
                    "audio_synthesis_params": score.audio_synthesis_params
                }
                
                with open(os.path.join(score_dir, 'score.json'), 'w', encoding='utf-8') as f:
                    json.dump(score_dict, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': success,
            'message': '更新成功' if success else '更新失败'
        }), 200 if success else 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'更新曲目失败: {str(e)}'}), 500


@advanced_bp.route('/api/score/<score_id>/delete', methods=['DELETE'])
def delete_score(score_id):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        serializer = ScoreSerializer(temp_dir)
        
        success = serializer.delete_score(score_id)
        return jsonify({
            'success': success,
            'message': '删除成功' if success else '删除失败'
        }), 200 if success else 404
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'删除曲目失败: {str(e)}'}), 500


@advanced_bp.route('/api/score/<score_id>/stitched', methods=['GET'])
def get_stitched_image(score_id):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        scores_dir = os.path.join(temp_dir, 'scores')
        img_path = os.path.join(scores_dir, score_id, 'stitched.png')
        
        if not os.path.exists(img_path):
            return jsonify({'success': False, 'error': '拼接图像不存在'}), 404
        
        return send_file(img_path, mimetype='image/png')
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取拼接图像失败: {str(e)}'}), 500


@advanced_bp.route('/api/score/<score_id>/page/<int:page_num>', methods=['GET'])
def get_page_image(score_id, page_num):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        scores_dir = os.path.join(temp_dir, 'scores')
        img_path = os.path.join(scores_dir, score_id, 'pages', f'page_{page_num}.png')
        
        if not os.path.exists(img_path):
            return jsonify({'success': False, 'error': '页面图像不存在'}), 404
        
        return send_file(img_path, mimetype='image/png')
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取页面图像失败: {str(e)}'}), 500


@advanced_bp.route('/api/score/<score_id>/export/midi', methods=['GET'])
def export_score_midi(score_id):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        serializer = ScoreSerializer(temp_dir)
        
        output_path = os.path.join(temp_dir, f'{score_id}.mid')
        success = serializer.export_score_to_midi(score_id, output_path)
        
        if not success:
            return jsonify({'success': False, 'error': '导出MIDI失败'}), 500
        
        return send_file(output_path, mimetype='audio/midi', as_attachment=True,
                        download_name=f'{score_id}.mid')
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'导出MIDI失败: {str(e)}'}), 500


@advanced_bp.route('/api/difficulty/evaluate/<score_id>', methods=['GET'])
def evaluate_difficulty(score_id):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        evaluator = DifficultyEvaluator()
        
        difficulty = evaluator.evaluate_from_score(score_id, temp_dir)
        if not difficulty:
            return jsonify({'success': False, 'error': '评估失败，曲目不存在或无法加载'}), 404
        
        report = evaluator.generate_difficulty_report(difficulty)
        
        viz_path = os.path.join(temp_dir, f'{score_id}_difficulty.png')
        evaluator.visualize_difficulty(difficulty, viz_path)
        
        return jsonify({
            'success': True,
            'score_id': score_id,
            'report': report,
            'visualization': f'/api/difficulty/visualization/{score_id}'
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'难度评估失败: {str(e)}'}), 500


@advanced_bp.route('/api/difficulty/visualization/<score_id>', methods=['GET'])
def get_difficulty_visualization(score_id):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        viz_path = os.path.join(temp_dir, f'{score_id}_difficulty.png')
        
        if not os.path.exists(viz_path):
            return jsonify({'success': False, 'error': '可视化图像不存在'}), 404
        
        return send_file(viz_path, mimetype='image/png')
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取可视化图像失败: {str(e)}'}), 500


@advanced_bp.route('/api/difficulty/analyze', methods=['POST'])
def analyze_audio_difficulty():
    try:
        import tempfile
        from scipy.io import wavfile
        
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        evaluator = DifficultyEvaluator()
        
        audio_file = request.files.get('audio')
        if not audio_file:
            return jsonify({'success': False, 'error': '未提供音频文件'}), 400
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            audio_file.save(f.name)
            temp_path = f.name
        
        try:
            sr, audio = wavfile.read(temp_path)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            audio = audio.astype(np.float32) / 32767.0
            
            if sr != evaluator.sample_rate:
                from scipy import signal
                audio = signal.resample(audio, int(len(audio) * evaluator.sample_rate / sr))
            
            jianzi_info = request.form.get('jianzi_info', '{}')
            jianzi_info = json.loads(jianzi_info)
            
            features = evaluator.extract_technique_features(audio, jianzi_info.get('technique', 'sanyin'))
            
            note_diff = evaluator.evaluate_note_difficulty(audio, jianzi_info, 0)
            
            return jsonify({
                'success': True,
                'features': {
                    'vibrato_rate': features.vibrato_rate,
                    'vibrato_depth': features.vibrato_depth,
                    'glissando_speed': features.glissando_speed,
                    'harmonic_purity': features.harmonic_purity,
                    'attack_sharpness': features.attack_sharpness,
                    'sustain_decay': features.sustain_decay,
                    'noise_level': features.noise_level,
                    'spectral_centroid': features.spectral_centroid
                },
                'difficulty': {
                    'score': note_diff.difficulty_score,
                    'technique_complexity': note_diff.technique_complexity,
                    'physical_difficulty': note_diff.physical_difficulty,
                    'explanations': note_diff.explanations
                }
            }), 200
            
        finally:
            os.unlink(temp_path)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'音频分析失败: {str(e)}'}), 500


@advanced_bp.route('/api/styles', methods=['GET'])
def get_available_styles():
    try:
        synthesizer = AudioSynthesizer()
        styles = synthesizer.get_available_styles()
        
        return jsonify({
            'success': True,
            'styles': styles
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取风格列表失败: {str(e)}'}), 500


@advanced_bp.route('/api/styles/<style_id>', methods=['GET'])
def get_style_detail(style_id):
    try:
        synthesizer = AudioSynthesizer()
        if not synthesizer.set_style(style_id):
            return jsonify({'success': False, 'error': '风格不存在'}), 404
        
        style_info = synthesizer.get_current_style()
        
        return jsonify({
            'success': True,
            'style': style_info
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取风格详情失败: {str(e)}'}), 500


@advanced_bp.route('/api/styles/compare', methods=['POST'])
def compare_styles():
    try:
        data = request.json or {}
        jianzi_list = data.get('jianzi_list', [])
        style_ids = data.get('style_ids', ['traditional', 'guangling', 'yushan'])
        tempo = data.get('tempo', 60.0)
        
        if not jianzi_list:
            return jsonify({'success': False, 'error': '未提供减字谱数据'}), 400
        
        results = []
        for style_id in style_ids:
            synthesizer = AudioSynthesizer(style=style_id)
            
            audio = synthesizer.synthesize_sequence(jianzi_list, tempo)
            
            import tempfile
            temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            output_path = os.path.join(temp_dir, f'compare_{style_id}.wav')
            synthesizer.save_wav(audio, output_path)
            
            style_info = synthesizer.get_current_style()
            
            evaluator = DifficultyEvaluator()
            audio_segments = []
            for jz in jianzi_list:
                midi = jz.get('midi', 60)
                technique = jz.get('technique', 'sanyin')
                duration = jz.get('duration', 1.0)
                string_id = jz.get('string', None)
                seg_audio = synthesizer.synthesize_note(midi, technique, duration, string_id)
                audio_segments.append(seg_audio)
            
            difficulty = evaluator.evaluate_sequence(audio_segments, jianzi_list)
            
            results.append({
                'style_id': style_id,
                'style_name': style_info['name'],
                'description': style_info['description'],
                'audio_url': f'/api/styles/compare/audio/{style_id}',
                'overall_difficulty': difficulty.overall_score,
                'level': difficulty.level
            })
        
        return jsonify({
            'success': True,
            'results': results
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'风格对比失败: {str(e)}'}), 500


@advanced_bp.route('/api/styles/compare/audio/<style_id>', methods=['GET'])
def get_style_compare_audio(style_id):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        audio_path = os.path.join(temp_dir, f'compare_{style_id}.wav')
        
        if not os.path.exists(audio_path):
            return jsonify({'success': False, 'error': '音频不存在'}), 404
        
        return send_file(audio_path, mimetype='audio/wav')
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取对比音频失败: {str(e)}'}), 500


@advanced_bp.route('/api/score/<score_id>/synthesize', methods=['POST'])
def synthesize_score(score_id):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        serializer = ScoreSerializer(temp_dir)
        score = serializer.load_score(score_id)
        
        if not score:
            return jsonify({'success': False, 'error': '曲目不存在'}), 404
        
        data = request.json or {}
        style = data.get('style')
        tempo = data.get('tempo', score.audio_synthesis_params.get('tempo', 60.0))
        
        synthesizer = AudioSynthesizer()
        if style:
            synthesizer.set_style(style)
        
        audio = synthesizer.synthesize_sequence(score.jianzi_sequence, tempo, style)
        
        output_path = os.path.join(temp_dir, f'{score_id}_audio.wav')
        synthesizer.save_wav(audio, output_path)
        
        return jsonify({
            'success': True,
            'audio_url': f'/api/score/{score_id}/audio',
            'style': synthesizer.get_current_style()['name'],
            'tempo': tempo,
            'duration': len(audio) / synthesizer.sample_rate
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'合成音频失败: {str(e)}'}), 500


@advanced_bp.route('/api/score/<score_id>/audio', methods=['GET'])
def get_score_audio(score_id):
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        audio_path = os.path.join(temp_dir, f'{score_id}_audio.wav')
        
        if not os.path.exists(audio_path):
            return jsonify({'success': False, 'error': '音频不存在'}), 404
        
        return send_file(audio_path, mimetype='audio/wav')
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取音频失败: {str(e)}'}), 500


@advanced_bp.route('/api/score/stitch', methods=['POST'])
def stitch_pages():
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        serializer = ScoreSerializer(temp_dir)
        
        files = request.files.getlist('pages')
        page_order_str = request.form.get('page_order')
        
        if page_order_str:
            page_order = json.loads(page_order_str)
        else:
            page_order = list(range(len(files)))
        
        images = []
        for file in files:
            file_bytes = np.frombuffer(file.read(), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is not None:
                images.append(img)
        
        if not images:
            return jsonify({'success': False, 'error': '未提供有效图像'}), 400
        
        stitched, bounds = serializer.stitch_multipage_scores(images, page_order)
        
        output_path = os.path.join(temp_dir, 'stitched_preview.png')
        cv2.imwrite(output_path, stitched)
        
        columns = serializer.detect_columns(stitched)
        
        return jsonify({
            'success': True,
            'stitched_url': '/api/score/stitch/preview',
            'page_bounds': bounds,
            'columns': columns,
            'column_count': len(columns)
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'拼接图像失败: {str(e)}'}), 500


@advanced_bp.route('/api/score/stitch/preview', methods=['GET'])
def get_stitch_preview():
    try:
        temp_dir = current_app.config.get('TEMP_DIR', 'backend/data/temp')
        preview_path = os.path.join(temp_dir, 'stitched_preview.png')
        
        if not os.path.exists(preview_path):
            return jsonify({'success': False, 'error': '预览图像不存在'}), 404
        
        return send_file(preview_path, mimetype='image/png')
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取预览图像失败: {str(e)}'}), 500
