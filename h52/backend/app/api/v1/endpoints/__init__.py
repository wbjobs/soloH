from fastapi import APIRouter
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.upload import router as upload_router
from app.api.v1.endpoints.analyze import (
    router as analyze_router,
    task_router,
    result_router
)
from app.api.v1.endpoints.history import router as history_router
from app.api.v1.endpoints.stream import router as stream_router
from app.api.v1.endpoints.enhanced import router as enhanced_router

router = APIRouter()

router.include_router(health_router, prefix="", tags=["health"])
router.include_router(upload_router, prefix="/upload", tags=["upload"])
router.include_router(analyze_router, prefix="/analyze", tags=["analyze"])
router.include_router(task_router, prefix="/task", tags=["task"])
router.include_router(result_router, prefix="/result", tags=["result"])
router.include_router(history_router, prefix="/history", tags=["history"])
router.include_router(stream_router, prefix="/stream", tags=["stream"])
router.include_router(enhanced_router, prefix="", tags=["enhanced"])
