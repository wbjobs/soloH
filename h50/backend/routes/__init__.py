from .upload_routes import upload_bp
from .detection_routes import detection_bp
from .recognition_routes import recognition_bp
from .audio_routes import audio_bp
from .export_routes import export_bp
from .advanced_routes import advanced_bp

__all__ = [
    'upload_bp',
    'detection_bp',
    'recognition_bp',
    'audio_bp',
    'export_bp',
    'advanced_bp'
]
