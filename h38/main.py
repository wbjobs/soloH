import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import get_settings
from app.api.v1 import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.api.dependencies import get_predictor, get_genome_handler, get_cache

    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")

    print("Initializing model predictor...")
    predictor = get_predictor()
    print(f"Model loaded on device: {predictor.device}")

    print("Initializing genome handler...")
    genome_handler = get_genome_handler()

    print("Initializing cache...")
    cache = get_cache()
    cache_stats = cache.get_stats()
    print(f"Redis cache status: {'Connected' if cache_stats.get('enabled') else 'Not available'}")

    print("Service started successfully!")
    yield

    print("Shutting down service...")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
        CRISPR Off-Target Predictor API

        基于深度学习的CRISPR sgRNA脱靶位点预测服务。
        支持：
        - 单条和批量sgRNA脱靶预测
        - 错配和插入缺失检测
        - 评分排序和多维度过滤
        - IGV可视化链接生成
        - Redis结果缓存
        """,
        lifespan=lifespan,
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

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs")

    @app.get("/api/v1", include_in_schema=False)
    async def api_root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "endpoints": {
                "health": "/api/v1/health",
                "offtarget_predict": "/api/v1/offtarget/predict",
                "offtarget_batch": "/api/v1/offtarget/batch",
                "offtarget_validate": "/api/v1/offtarget/validate",
                "offtarget_igv_link": "/api/v1/offtarget/igv-link",
            },
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1,
    )
