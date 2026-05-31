from app.extensions import db


class GlyphCharacter(db.Model):
    __tablename__ = 'glyph_characters'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    char = db.Column(db.String(1), nullable=False, unique=True, index=True)
    radical = db.Column(db.String(1), nullable=False)
    stroke_count = db.Column(db.Integer, nullable=False)
    pinyin = db.Column(db.String(50))
    variants = db.Column(db.JSON)
    structure = db.Column(db.String(20))
    unicode = db.Column(db.String(10))
    kangxi_strokes = db.Column(db.Integer)
    frequency = db.Column(db.Float, default=0.0)
