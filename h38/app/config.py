from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    APP_NAME: str = "CRISPR Off-Target Predictor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_CACHE_TTL: int = 86400

    GENOME_REFERENCE_PATH: str = "./data/hg38.fa"
    GENOME_BUILD: str = "hg38"

    MODEL_PATH: str = "./models/crispr_model.pt"
    MODEL_DEVICE: str = "cpu"
    MAX_MISMATCHES: int = 6
    MAX_INDEL: int = 2
    BATCH_SIZE: int = 32

    IGV_BASE_URL: str = "http://localhost:60151"
    IGV_GENOME: str = "hg38"

    ATAC_PEAK_PATH: Optional[str] = None
    DEFAULT_CELL_TYPE: str = "default"
    ENABLE_CHROMATIN_CORRECTION: bool = True
    ENABLE_EFFICIENCY_PREDICTION: bool = True
    ENABLE_REPAIR_PREDICTION: bool = True
    CHROMATIN_CORRECTION_WEIGHT: float = 0.3

    RATE_LIMIT: int = 100
    RATE_LIMIT_WINDOW: int = 60


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
