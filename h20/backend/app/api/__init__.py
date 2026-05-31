from fastapi import APIRouter
from app.api.transactions import router as transactions_router
from app.api.addresses import router as addresses_router
from app.api.analysis import router as analysis_router
from app.api.tasks import router as tasks_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(transactions_router, prefix="/transactions", tags=["Transactions"])
api_router.include_router(addresses_router, prefix="/addresses", tags=["Addresses"])
api_router.include_router(analysis_router, tags=["Analysis"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])

__all__ = ["api_router"]
