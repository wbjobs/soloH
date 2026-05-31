from fastapi import APIRouter
from .routes import router as off_target_router
from .health import router as health_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(off_target_router, prefix="/offtarget", tags=["offtarget"])
api_router.include_router(health_router, prefix="/health", tags=["health"])

__all__ = ["api_router"]
