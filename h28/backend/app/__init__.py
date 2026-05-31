import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from app.extensions import init_extensions, db, socketio


def create_app(config_class):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    _ensure_directories(app)
    _configure_logging(app)
    
    init_extensions(app)
    
    from app.api import api_bp, register_blueprints
    register_blueprints()
    app.register_blueprint(api_bp, url_prefix='/api')
    
    _register_socketio_events()
    
    with app.app_context():
        db.create_all()
    
    return app


def _ensure_directories(app):
    directories = [
        app.config['UPLOAD_FOLDER'],
        app.config['PROCESSED_FOLDER'],
        app.config.get('LOG_DIR', os.path.join(app.root_path, 'logs'))
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def _configure_logging(app):
    if not app.debug and not app.testing:
        log_dir = app.config.get('LOG_DIR', os.path.join(app.root_path, 'logs'))
        os.makedirs(log_dir, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'app.log'),
            maxBytes=10240000,
            backupCount=10,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(app.config.get('LOG_LEVEL', 'INFO'))
        
        app.logger.addHandler(file_handler)
        app.logger.setLevel(app.config.get('LOG_LEVEL', 'INFO'))
        app.logger.info('Application startup')


def _register_socketio_events():
    from app.core import socketio_events
    socketio_events.register_events(socketio)
