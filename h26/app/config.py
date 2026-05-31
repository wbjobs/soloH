import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    APP_NAME: str = "ProteinContactPrediction"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/protein_contact"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    MODEL_CACHE_DIR: str = "./data/models"
    DEFAULT_MODEL_NAME: str = "resnet50_pdb"

    THRESHOLD_ANGSTROM: float = 8.0
    MAX_SEQUENCE_LENGTH: int = 1000

    BLAST_DB_PATH: Optional[str] = None
    BLASTP_PATH: Optional[str] = None
    PSIBLAST_PATH: Optional[str] = None

    @property
    def MODEL_CACHE_PATH(self) -> Path:
        path = Path(self.MODEL_CACHE_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def IS_DEVELOPMENT(self) -> bool:
        return self.APP_ENV.lower() == "development"


settings = Settings()
