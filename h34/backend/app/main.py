from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.schemas.common import HealthCheckResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    yield


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="农业病害预警系统API - 集成气象数据、孢子监测、病害预测模型和风险预警",
        version="1.0.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # 配置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 健康检查接口
    @app.get(
        "/health",
        response_model=HealthCheckResponse,
        summary="健康检查",
        tags=["系统"],
    )
    async def health_check() -> HealthCheckResponse:
        """服务健康检查接口"""
        return HealthCheckResponse()

    # 注册API路由
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
