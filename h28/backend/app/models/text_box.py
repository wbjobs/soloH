from app.extensions import db


class TextBox(db.Model):
    __tablename__ = 'text_boxes'

    id = db.Column(db.Integer, primary_key=True)
    text_line_id = db.Column(db.Integer, db.ForeignKey('text_lines.id', ondelete='CASCADE'), nullable=False)
    x1 = db.Column(db.Float, nullable=False)
    y1 = db.Column(db.Float, nullable=False)
    x2 = db.Column(db.Float, nullable=False)
    y2 = db.Column(db.Float, nullable=False)
    x3 = db.Column(db.Float, nullable=False)
    y3 = db.Column(db.Float, nullable=False)
    x4 = db.Column(db.Float, nullable=False)
    y4 = db.Column(db.Float, nullable=False)
    confidence = db.Column(db.Float)

    text_line = db.relationship('TextLine', back_populates='text_boxes')
