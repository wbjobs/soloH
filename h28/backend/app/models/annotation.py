from datetime import datetime
from app.extensions import db


class Annotation(db.Model):
    __tablename__ = 'annotations'

    id = db.Column(db.Integer, primary_key=True)
    page_result_id = db.Column(db.Integer, db.ForeignKey('page_results.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text)
    confidence = db.Column(db.Float)
    x1 = db.Column(db.Float, nullable=False)
    y1 = db.Column(db.Float, nullable=False)
    x2 = db.Column(db.Float, nullable=False)
    y2 = db.Column(db.Float, nullable=False)
    x3 = db.Column(db.Float, nullable=False)
    y3 = db.Column(db.Float, nullable=False)
    x4 = db.Column(db.Float, nullable=False)
    y4 = db.Column(db.Float, nullable=False)
    annotation_type = db.Column(db.String(20), nullable=False, default='handwritten')
    is_merged = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    page_result = db.relationship('PageResult', back_populates='annotations')
