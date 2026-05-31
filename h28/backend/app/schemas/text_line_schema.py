from app.extensions import ma
from marshmallow import fields
from app.schemas.text_box_schema import TextBoxSchema


class TextLineSchema(ma.Schema):
    id = fields.String()
    textBox = fields.Nested(TextBoxSchema, required=True, data_key='textBox')
    content = fields.String(required=True)
    confidence = fields.Float(required=True)
    candidates = fields.List(fields.String(), required=True)
    columnIndex = fields.Integer(required=True, data_key='columnIndex')
    lineIndex = fields.Integer(required=True, data_key='lineIndex')
