import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    environment: str = "development"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
        logger.info(f"Client connected to task: {task_id}")

    def disconnect(self, task_id: str, websocket: WebSocket):
        if task_id in self.active_connections:
            self.active_connections[task_id].remove(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
            logger.info(f"Client disconnected from task: {task_id}")

    async def send_progress(self, task_id: str, message: dict):
        if task_id in self.active_connections:
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send message: {e}")

    async def broadcast(self, message: dict):
        for connections in self.active_connections.values():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast message: {e}")


manager = ConnectionManager()


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Bitcoin Transaction Graph Analysis Backend")
    logger.info(f"Environment: {settings.environment}")
    yield
    logger.info("Shutting down backend")


app = FastAPI(
    title="Bitcoin Transaction Graph Analysis API",
    description="API for analyzing Bitcoin transaction networks and identifying suspicious trading patterns",
    version="0.1.0",
    lifespan=lifespan,
)

origins = [origin.strip() for origin in settings.cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.environment,
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Bitcoin Transaction Graph Analysis API",
        "docs": "/docs",
        "health": "/health",
    }


@app.websocket("/ws/task/{task_id}")
async def websocket_task_progress(websocket: WebSocket, task_id: str):
    await manager.connect(task_id, websocket)
    try:
        await manager.send_progress(
            task_id,
            {
                "type": "connected",
                "task_id": task_id,
                "message": "Connected to task progress channel",
            },
        )

        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_progress(
                        task_id,
                        {"type": "pong", "task_id": task_id, "timestamp": message.get("timestamp")},
                    )
            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON from task {task_id}")
    except WebSocketDisconnect:
        manager.disconnect(task_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
        manager.disconnect(task_id, websocket)


@app.post("/api/v1/tasks/{task_id}/progress", tags=["Tasks"])
async def send_task_progress(task_id: str, progress: dict):
    await manager.send_progress(task_id, {"task_id": task_id, **progress})
    return {"status": "sent", "task_id": task_id}


def register_routers():
    from app.api import api_router

    app.include_router(api_router)


register_routers()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development",
    )
