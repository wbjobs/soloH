from app.extensions import ma

from app.schemas.task_schema import TaskSchema
from app.schemas.text_box_schema import TextBoxSchema
from app.schemas.text_line_schema import TextLineSchema
from app.schemas.page_result_schema import PageResultSchema
from app.schemas.task_result_schema import TaskResultSchema
from app.schemas.progress_message_schema import ProgressMessageSchema

__all__ = [
    'TaskSchema',
    'TextBoxSchema',
    'TextLineSchema',
    'PageResultSchema',
    'TaskResultSchema',
    'ProgressMessageSchema',
]
