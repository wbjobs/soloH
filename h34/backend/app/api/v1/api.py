from fastapi import APIRouter

from app.api.v1.endpoints import auth, weather, spore, risk, forecast, alert, config, stats
from app.api.v1.endpoints import attribution, drone, pesticide

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(weather.router, prefix="/weather", tags=["气象数据"])
api_router.include_router(spore.router, prefix="/spore", tags=["孢子数据"])
api_router.include_router(risk.router, prefix="/risk", tags=["风险地图"])
api_router.include_router(forecast.router, prefix="/forecast", tags=["预报数据"])
api_router.include_router(alert.router, prefix="/alert", tags=["预警"])
api_router.include_router(config.router, prefix="/config", tags=["用户配置"])
api_router.include_router(stats.router, prefix="/stats", tags=["统计数据"])
api_router.include_router(attribution.router, prefix="/attribution", tags=["风险归因"])
api_router.include_router(drone.router, prefix="/drone", tags=["无人机影像"])
api_router.include_router(pesticide.router, prefix="/pesticide", tags=["农药喷洒"])
