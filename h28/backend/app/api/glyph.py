from flask import Blueprint, jsonify, request

glyph_bp = Blueprint('glyphs', __name__)

_glyph_controller = None


def get_glyph_controller():
    global _glyph_controller
    if _glyph_controller is None:
        from app.controllers.glyph_controller import GlyphController
        _glyph_controller = GlyphController()
    return _glyph_controller


@glyph_bp.route('', methods=['GET'])
def search_glyphs():
    glyph_controller = get_glyph_controller()
    radical = request.args.get('radical', type=str)
    stroke_count = request.args.get('stroke_count', type=int)
    stroke_tolerance = request.args.get('stroke_tolerance', 2, type=int)
    char = request.args.get('char', type=str)
    structure = request.args.get('structure', type=str)
    
    result, status = glyph_controller.search_glyphs(
        radical=radical,
        stroke_count=stroke_count,
        stroke_tolerance=stroke_tolerance,
        char=char,
        structure=structure
    )
    return jsonify(result), status


@glyph_bp.route('/<char>', methods=['GET'])
def get_glyph(char: str):
    glyph_controller = get_glyph_controller()
    result, status = glyph_controller.get_by_char(char)
    return jsonify(result), status


@glyph_bp.route('/<char>/similar', methods=['GET'])
def get_similar_glyphs(char: str):
    glyph_controller = get_glyph_controller()
    stroke_tolerance = request.args.get('stroke_tolerance', 2, type=int)
    result, status = glyph_controller.get_similar_chars(char, stroke_tolerance)
    return jsonify(result), status


@glyph_bp.route('/similarity', methods=['GET'])
def calculate_similarity():
    glyph_controller = get_glyph_controller()
    char1 = request.args.get('char1', type=str)
    char2 = request.args.get('char2', type=str)
    if not char1 or not char2:
        return jsonify({'error': 'Both char1 and char2 are required'}), 400
    result, status = glyph_controller.calculate_similarity(char1, char2)
    return jsonify(result), status


@glyph_bp.route('/initialize', methods=['POST'])
def initialize_glyphs():
    glyph_controller = get_glyph_controller()
    result, status = glyph_controller.initialize_glyphs()
    return jsonify(result), status
