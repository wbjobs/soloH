from typing import Optional, Tuple, Dict, Any, List
from app import db
from app.repositories.glyph_repository import GlyphRepository
from app.services.glyph_service import GlyphService
from app.models.glyph_character import GlyphCharacter


class GlyphController:
    def __init__(self):
        self.glyph_repository = GlyphRepository(db.session)
        self.glyph_service = GlyphService(self.glyph_repository)

    def _glyph_to_dict(self, glyph: GlyphCharacter) -> Dict[str, Any]:
        return {
            'id': glyph.id,
            'char': glyph.char,
            'radical': glyph.radical,
            'stroke_count': glyph.stroke_count,
            'pinyin': glyph.pinyin,
            'variants': glyph.variants,
            'structure': glyph.structure,
            'unicode': glyph.unicode,
            'kangxi_strokes': glyph.kangxi_strokes,
            'frequency': glyph.frequency
        }

    def search_glyphs(self, radical: Optional[str] = None, stroke_count: Optional[int] = None,
                      stroke_tolerance: int = 2, char: Optional[str] = None,
                      structure: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
        try:
            glyphs = self.glyph_service.search_glyphs(
                radical=radical,
                stroke_count=stroke_count,
                stroke_tolerance=stroke_tolerance,
                char=char,
                structure=structure
            )
            return {
                'items': [self._glyph_to_dict(g) for g in glyphs],
                'total': len(glyphs)
            }, 200
        except Exception as e:
            return {'error': str(e)}, 500

    def get_by_char(self, char: str) -> Tuple[Dict[str, Any], int]:
        try:
            glyph = self.glyph_service.get_by_char(char)
            if not glyph:
                return {'error': 'Glyph not found'}, 404
            return self._glyph_to_dict(glyph), 200
        except Exception as e:
            return {'error': str(e)}, 500

    def get_similar_chars(self, char: str, stroke_tolerance: int = 2) -> Tuple[Dict[str, Any], int]:
        try:
            variants = self.glyph_service.get_similar_variants(char)
            return {
                'char': char,
                'similar': variants
            }, 200
        except Exception as e:
            return {'error': str(e)}, 500

    def calculate_similarity(self, char1: str, char2: str) -> Tuple[Dict[str, Any], int]:
        try:
            similarity = self.glyph_service.calculate_shape_similarity(char1, char2)
            return {
                'char1': char1,
                'char2': char2,
                'similarity': similarity
            }, 200
        except Exception as e:
            return {'error': str(e)}, 500

    def initialize_glyphs(self) -> Tuple[Dict[str, Any], int]:
        try:
            count = self.glyph_service.initialize_builtin_glyphs()
            return {
                'initialized': count > 0,
                'count': count
            }, 200
        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 500
