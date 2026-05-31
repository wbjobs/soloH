from app.extensions import db


class TextLine(db.Model):
    __tablename__ = 'text_lines'

    id = db.Column(db.Integer, primary_key=True)
    page_result_id = db.Column(db.Integer, db.ForeignKey('page_results.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.Float)
    candidates = db.Column(db.JSON)
    column_index = db.Column(db.Integer)
    line_index = db.Column(db.Integer)
    is_edited = db.Column(db.Boolean, default=False, nullable=False)

    page_result = db.relationship('PageResult', back_populates='text_lines')
    text_boxes = db.relationship('TextBox', back_populates='text_line', cascade='all, delete-orphan')
