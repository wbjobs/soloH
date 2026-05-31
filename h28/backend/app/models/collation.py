import uuid
from datetime import datetime
from app.extensions import db


class Collation(db.Model):
    __tablename__ = 'collations'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    base_task_id = db.Column(db.String(36), db.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    compared_task_id = db.Column(db.String(36), db.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    base_page_number = db.Column(db.Integer, nullable=False)
    compared_page_number = db.Column(db.Integer, nullable=False)
    alignment_score = db.Column(db.Float)
    diff_result = db.Column(db.JSON)
    status = db.Column(db.String(50), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    base_task = db.relationship('Task', foreign_keys=[base_task_id])
    compared_task = db.relationship('Task', foreign_keys=[compared_task_id])
