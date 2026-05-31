from app.extensions import ma
from marshmallow import fields


class TextBoxSchema(ma.Schema):
    id = fields.String()
    x1 = fields.Float(required=True)
    y1 = fields.Float(required=True)
    x2 = fields.Float(required=True)
    y2 = fields.Float(required=True)
    x3 = fields.Float(required=True)
    y3 = fields.Float(required=True)
    x4 = fields.Float(required=True)
    y4 = fields.Float(required=True)
    confidence = fields.Float(required=True)
