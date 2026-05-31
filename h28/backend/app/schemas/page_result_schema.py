from app.extensions import ma
from marshmallow import fields
from app.schemas.text_line_schema import TextLineSchema


class PageResultSchema(ma.Schema):
    pageNumber = fields.Integer(required=True, data_key='pageNumber')
    width = fields.Integer(required=True)
    height = fields.Integer(required=True)
    imageUrl = fields.String(required=True, data_key='imageUrl')
    textLines = fields.List(fields.Nested(TextLineSchema), required=True, data_key='textLines')
    columns = fields.List(fields.List(fields.Nested(TextLineSchema)), required=True)
