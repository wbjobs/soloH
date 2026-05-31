from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Multimodal Emotion Analysis API"
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    APP_ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    DATABASE_URL: str = "sqlite:///./data/emotion_analysis.db"

    MODELS_DIR: str = "./models"
    MODEL_CACHE_DIR: str = "./models"
    DATA_DIR: str = "./data"

    MOCK_MODE: bool = True
    DEVICE: str = "cpu"
    USE_CUDA: bool = False

    WHISPER_MODEL_SIZE: str = "base"
    MEDIAPIPE_STATIC_IMAGE_MODE: bool = False
    MEDIAPIPE_MIN_DETECTION_CONFIDENCE: float = 0.5
    MEDIAPIPE_MIN_TRACKING_CONFIDENCE: float = 0.5

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
