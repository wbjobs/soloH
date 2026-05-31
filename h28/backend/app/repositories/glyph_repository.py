from typing import List, Optional, Dict, Any
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from app.repositories.base_repository import BaseRepository
from app.models.glyph_character import GlyphCharacter


class GlyphRepository(BaseRepository[GlyphCharacter, Dict[str, Any], Dict[str, Any]]):
    def __init__(self, db: Session):
        super().__init__(db, GlyphCharacter)

    def search_by_radical_and_strokes(self, radical: Optional[str], min_strokes: Optional[int], max_strokes: Optional[int]) -> List[GlyphCharacter]:
        query = self.db.query(GlyphCharacter)
        if radical:
            query = query.filter(GlyphCharacter.radical == radical)
        if min_strokes is not None:
            query = query.filter(GlyphCharacter.stroke_count >= min_strokes)
        if max_strokes is not None:
            query = query.filter(GlyphCharacter.stroke_count <= max_strokes)
        return query.order_by(GlyphCharacter.frequency.desc()).all()

    def get_similar_chars(self, char: str, stroke_tolerance: int = 2) -> List[GlyphCharacter]:
        target = self.get_by_char(char)
        if not target:
            return []
        min_strokes = target.stroke_count - stroke_tolerance
        max_strokes = target.stroke_count + stroke_tolerance
        return self.db.query(GlyphCharacter).filter(
            and_(
                GlyphCharacter.char != char,
                GlyphCharacter.stroke_count >= min_strokes,
                GlyphCharacter.stroke_count <= max_strokes,
                or_(
                    GlyphCharacter.radical == target.radical,
                    GlyphCharacter.structure == target.structure
                )
            )
        ).order_by(GlyphCharacter.frequency.desc()).all()

    def get_by_char(self, char: str) -> Optional[GlyphCharacter]:
        return self.db.query(GlyphCharacter).filter(GlyphCharacter.char == char).first()

    def create_glyph(self, data: Dict[str, Any]) -> GlyphCharacter:
        return self.create(data)

    def list_all(self) -> List[GlyphCharacter]:
        return self.get_all()
