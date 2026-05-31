from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    API_TITLE: str = "Satellite Ozone Data Analysis API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "FastAPI + Xarray + Dask based satellite ozone (TOMS/OMI) data analysis service. Provides trend analysis, seasonal decomposition, and ozone hole detection."

    DATA_DIR: str = "e:/soloH/h24/data"
    CACHE_DIR: str = "e:/soloH/h24/cache"
    NETCDF_PATTERN: str = "*.nc"

    DASK_SCHEDULER: str = "threads"
    DASK_WORKERS: int = 4
    DASK_MEMORY_LIMIT: str = "8GB"

    OZONE_HOLE_THRESHOLD: float = 220.0
    GRID_RESOLUTION: float = 1.0

    CACHE_TTL_HOURS: int = 24
    ENABLE_CACHE: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
