from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.dask_client import get_client, close_client
from app.api.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        client = get_client()
        print(f"Dask client started: {client}")
    except Exception as e:
        print(f"Warning: Could not start Dask client: {e}")

    yield

    try:
        close_client()
        print("Dask client closed")
    except Exception as e:
        print(f"Warning: Error closing Dask client: {e}")


app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "description": settings.API_DESCRIPTION,
        "docs": "/docs",
        "api_prefix": "/api/v1",
        "endpoints": {
            "grid_info": "GET /api/v1/grid/info",
            "trend_point": "POST /api/v1/trend/point",
            "trend_grid": "POST /api/v1/trend/grid",
            "stl_point": "POST /api/v1/stl/point",
            "stl_grid": "POST /api/v1/stl/grid",
            "ozone_hole_timeseries": "POST /api/v1/ozone-hole/timeseries",
            "ozone_hole_geojson": "POST /api/v1/ozone-hole/geojson",
            "ozone_hole_climatology": "GET /api/v1/ozone-hole/climatology",
            "data_point": "POST /api/v1/data/point",
            "geoschem_compare": "POST /api/v1/geoschem/compare",
            "geoschem_hole_compare": "POST /api/v1/geoschem/hole-compare",
            "vortex_correlation": "POST /api/v1/vortex/correlation",
            "vortex_geojson": "POST /api/v1/vortex/geojson",
            "vortex_indices": "POST /api/v1/vortex/indices",
            "prediction_point": "POST /api/v1/prediction/point",
            "prediction_region": "POST /api/v1/prediction/region",
            "prediction_hole_area": "POST /api/v1/prediction/hole-area",
            "cache_info": "GET /api/v1/cache/info",
            "cache_keys": "GET /api/v1/cache/keys",
            "cache_clear": "POST /api/v1/cache/clear",
            "latitude_bands": "GET /api/v1/latitude-bands",
            "seasons": "GET /api/v1/seasons",
        },
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
