from app.extensions import ma
from marshmallow import fields
from app.schemas.page_result_schema import PageResultSchema


class TaskResultSchema(ma.Schema):
    taskId = fields.String(required=True, data_key='taskId')
    pages = fields.List(fields.Nested(PageResultSchema), required=True)
    fullText = fields.String(required=True, data_key='fullText')
