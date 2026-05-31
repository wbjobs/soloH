import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-dev-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///gwas.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'data', 'uploads'))
    RESULTS_FOLDER = os.getenv('RESULTS_FOLDER', os.path.join(BASE_DIR, 'data', 'results'))
    REFERENCE_FOLDER = os.getenv('REFERENCE_FOLDER', os.path.join(BASE_DIR, 'data', 'reference'))
    
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 500 * 1024 * 1024))
    
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')
    
    ALLOWED_VCF_EXTENSIONS = {'.vcf', '.vcf.gz'}
    ALLOWED_CSV_EXTENSIONS = {'.csv', '.txt'}
    
    SIGNIFICANCE_THRESHOLD_DEFAULT = 5e-8
    
    @staticmethod
    def ensure_directories():
        for folder in [Config.UPLOAD_FOLDER, Config.RESULTS_FOLDER, Config.REFERENCE_FOLDER]:
            os.makedirs(folder, exist_ok=True)
            os.makedirs(os.path.join(folder, 'maize'), exist_ok=True)
