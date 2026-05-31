from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from app.core.config import settings
from app.api.v1.api import api_router
from app.db.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Multimodal Emotion Analysis API",
    description="Real-time multi-modal emotion analysis with audio, video, and text",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.DATA_DIR, "uploads"), exist_ok=True)
    os.makedirs(os.path.join(settings.DATA_DIR, "results"), exist_ok=True)
    
    init_db()
    
    logger.info("Application started")
    logger.info(f"Data directory: {settings.DATA_DIR}")


@app.get("/")
async def root():
    return {
        "name": "Multimodal Emotion Analysis API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0"
    }
