import uuid
from datetime import datetime
from app.extensions import db


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending')
    progress = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    page_count = db.Column(db.Integer)
    current_page = db.Column(db.Integer)
    error_message = db.Column(db.Text)

    page_results = db.relationship('PageResult', back_populates='task', cascade='all, delete-orphan')
