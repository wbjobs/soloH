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

FILE_TYPES = ['image', 'pdf']


class TaskSchema(ma.Schema):
    id = fields.String()
    fileName = fields.String(required=True, data_key='fileName')
    fileType = fields.String(
        required=True,
        validate=validate.OneOf(FILE_TYPES),
        data_key='fileType'
    )
    status = fields.String(
        required=True,
        validate=validate.OneOf(TASK_STATUSES)
    )
    progress = fields.Integer(required=True)
    createdAt = fields.DateTime(data_key='createdAt')
    completedAt = fields.DateTime(data_key='completedAt')
    pageCount = fields.Integer(required=True, data_key='pageCount')
    currentPage = fields.Integer(required=True, data_key='currentPage')
    errorMessage = fields.String(data_key='errorMessage')
