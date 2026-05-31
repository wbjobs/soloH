from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.routers import (
    auction_routes, strategy_routes, visualization_routes,
    market_power_routes, secondary_market_routes, realtime_routes
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
    Spectrum Auction Simulation Platform API.

    ## Features

    - **Auction Formats**: SMR (Simultaneous Multi-Round) and CCA (Combinatorial Clock Auction)
    - **Bidder Models**: Random valuation generation with complementary values
    - **Bidding Strategies**: Multiple built-in strategies + custom strategy upload
    - **Strategy Competitions**: Run tournaments between different strategies
    - **Visualization**: Price paths, allocation, efficiency metrics
    - **Analytics**: Revenue, efficiency, social welfare calculations

    ## Quick Start

    1. Create an auction with `POST /auctions`
    2. Run it with `POST /auctions/{id}/run`
    3. View results and visualization in the response
    """,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auction_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(strategy_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(visualization_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(market_power_routes.router)
app.include_router(secondary_market_routes.router)
app.include_router(realtime_routes.router)


@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "api_prefix": settings.API_V1_PREFIX,
        "endpoints": {
            "auctions": f"{settings.API_V1_PREFIX}/auctions",
            "strategies": f"{settings.API_V1_PREFIX}/strategies",
            "competitions": f"{settings.API_V1_PREFIX}/competitions",
            "market_power_analysis": "/api/market-power",
            "secondary_market": "/api/secondary-market",
            "realtime_websocket": "/api/realtime/ws/auction/{auction_id}",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
