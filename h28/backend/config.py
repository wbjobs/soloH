import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'True') == 'True'
    
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(BASE_DIR, "app.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    UPLOAD_FOLDER = os.getenv(
        'UPLOAD_FOLDER',
        os.path.join(PROJECT_ROOT, 'storage', 'uploads')
    )
    PROCESSED_FOLDER = os.getenv(
        'PROCESSED_FOLDER',
        os.path.join(PROJECT_ROOT, 'storage', 'processed')
    )
    EXPORT_FOLDER = os.getenv(
        'EXPORT_FOLDER',
        os.path.join(PROJECT_ROOT, 'storage', 'exports')
    )
    
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'pdf'}
    
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = os.getenv('CELERY_TIMEZONE', 'Asia/Shanghai')
    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_TIME_LIMIT = 30 * 60
    
    SOCKETIO_CORS_ALLOWED_ORIGINS = os.getenv('SOCKETIO_CORS_ORIGINS', '*')
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')
    
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    RATE_LIMITS = {
        'upload': '10 per minute',
        'api': '100 per minute'
    }
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_DIR = os.path.join(BASE_DIR, 'logs')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'storage', 'test_uploads')
    PROCESSED_FOLDER = os.path.join(PROJECT_ROOT, 'storage', 'test_processed')
    EXPORT_FOLDER = os.path.join(PROJECT_ROOT, 'storage', 'test_exports')


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
