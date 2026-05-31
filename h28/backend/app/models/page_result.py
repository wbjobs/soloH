from app.extensions import db


class PageResult(db.Model):
    __tablename__ = 'page_results'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), db.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    page_number = db.Column(db.Integer, nullable=False)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    image_path = db.Column(db.String(500))

    task = db.relationship('Task', back_populates='page_results')
    text_lines = db.relationship('TextLine', back_populates='page_result', cascade='all, delete-orphan')
    annotations = db.relationship('Annotation', back_populates='page_result', cascade='all, delete-orphan')
