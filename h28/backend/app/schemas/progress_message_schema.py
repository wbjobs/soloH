from app.extensions import ma
from marshmallow import fields, validate


TASK_STATUSES = [
    'pending',
    'preprocessing',
    'detecting',
    'recognizing',
    'postprocessing',
    'punctuating',
    'completed',
    'failed'
]


class ProgressMessageSchema(ma.Schema):
    taskId = fields.String(required=True, data_key='taskId')
    status = fields.String(
        required=True,
        validate=validate.OneOf(TASK_STATUSES)
    )
    progress = fields.Integer(required=True)
    message = fields.String(required=True)
    currentPage = fields.Integer(data_key='currentPage')
    totalPages = fields.Integer(data_key='totalPages')
