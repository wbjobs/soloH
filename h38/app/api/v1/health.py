import os
from fastapi import APIRouter, Depends
from app.config import get_settings, Settings
from app.api.schemas import HealthResponse, CacheStatsResponse
from app.api.dependencies import get_predictor, get_genome_handler, get_cache
from app.models.crispr_model import CRISPRPredictor
from app.data_processing.genome_handler import GenomeHandler
from app.cache.redis_cache import RedisCache

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health_check(
    settings: Settings = Depends(get_settings),
    predictor: CRISPRPredictor = Depends(get_predictor),
    genome_handler: GenomeHandler = Depends(get_genome_handler),
    cache: RedisCache = Depends(get_cache),
):
    model_loaded = predictor is not None and predictor.model is not None

    genome_loaded = os.path.exists(settings.GENOME_REFERENCE_PATH)

    redis_connected = cache._connect() if cache._enabled else False

    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        genome_build=settings.GENOME_BUILD,
        model_loaded=model_loaded,
        redis_connected=redis_connected,
        genome_loaded=genome_loaded,
    )


@router.get("/stats", response_model=CacheStatsResponse)
async def cache_stats(
    cache: RedisCache = Depends(get_cache),
):
    return CacheStatsResponse(**cache.get_stats())


@router.get("/ready")
async def readiness_check(
    settings: Settings = Depends(get_settings),
    predictor: CRISPRPredictor = Depends(get_predictor),
    genome_handler: GenomeHandler = Depends(get_genome_handler),
    cache: RedisCache = Depends(get_cache),
):
    model_ok = predictor is not None and predictor.model is not None
    genome_ok = os.path.exists(settings.GENOME_REFERENCE_PATH)

    if not model_ok:
        return {"status": "not_ready", "reason": "model_not_loaded"}

    if not genome_ok:
        return {"status": "not_ready", "reason": "genome_not_found"}

    return {"status": "ready"}
