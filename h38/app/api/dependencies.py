from typing import Optional
from functools import lru_cache
from fastapi import Depends
from app.config import get_settings, Settings
from app.models.model_utils import load_model
from app.models.crispr_model import CRISPRPredictor
from app.data_processing.genome_handler import GenomeHandler
from app.cache.redis_cache import RedisCache, get_cache
from app.offtarget_search.offtarget_finder import OffTargetFinder


@lru_cache
def get_predictor(settings: Settings = Depends(get_settings)) -> CRISPRPredictor:
    try:
        predictor = load_model(
            model_path=settings.MODEL_PATH,
            device=settings.MODEL_DEVICE,
        )
        return predictor
    except Exception as e:
        print(f"Warning: Could not load model: {e}")
        from app.models.crispr_model import CRISPRModel, CRISPRPredictor
        model = CRISPRModel()
        return CRISPRPredictor(model=model, device=settings.MODEL_DEVICE)


@lru_cache
def get_genome_handler() -> GenomeHandler:
    return GenomeHandler()


def get_offtarget_finder(
    predictor: CRISPRPredictor = Depends(get_predictor),
    genome_handler: GenomeHandler = Depends(get_genome_handler),
    settings: Settings = Depends(get_settings),
) -> OffTargetFinder:
    return OffTargetFinder(
        genome_handler=genome_handler,
        predictor=predictor,
        max_mismatches=settings.MAX_MISMATCHES,
        max_indel=settings.MAX_INDEL,
        batch_size=settings.BATCH_SIZE,
    )
