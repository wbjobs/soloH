from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/spectrum_auction"
    DATABASE_URL_SQLITE: str = "sqlite:///./spectrum_auction.db"
    USE_SQLITE: bool = True

    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Spectrum Auction Simulation Platform"
    VERSION: str = "1.0.0"

    UPLOAD_DIR: str = "uploaded_strategies"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024

    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DEFAULT_AUCTION_PARAMS: dict = {
        "min_price": 10.0,
        "max_price": 1000.0,
        "bid_increment": 5.0,
        "max_rounds": 100,
        "activity_rule": True,
        "smr": {
            "bid_increment": 5.0,
            "activity_weight": 0.8,
        },
        "cca": {
            "clock_increment": 5.0,
            "supplementary_rounds": 3,
            "core_selecting": True,
        }
    }


settings = Settings()
