from flask import Blueprint

api_bp = Blueprint('api', __name__)


def register_blueprints():
    from app.api.health import health_bp
    from app.api.tasks import tasks_bp
    from app.api.files import files_bp
    from app.api.collation import collations_bp
    from app.api.annotation import annotations_bp
    from app.api.glyph import glyph_bp

    api_bp.register_blueprint(health_bp)
    api_bp.register_blueprint(tasks_bp, url_prefix='/tasks')
    api_bp.register_blueprint(files_bp, url_prefix='/files')
    api_bp.register_blueprint(collations_bp, url_prefix='/collations')
    api_bp.register_blueprint(annotations_bp)
    api_bp.register_blueprint(glyph_bp, url_prefix='/glyphs')
