from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, Set
from collections import deque
import logging
import json
import numpy as np
import base64
import io
from datetime import datetime

from app.schemas import StreamFrame, StreamResult, EmotionProbabilities
from app.services import get_emotion_service, EmotionAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter()

active_connections: Set[WebSocket] = set()

MAX_BUFFER_SIZE = 300
MAX_FRAME_COUNT = 10000


class StreamManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.stream_buffers: Dict[str, Dict] = {}
        self.result_history: Dict[str, deque] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.stream_buffers[client_id] = {
            'audio_buffer': deque(maxlen=MAX_BUFFER_SIZE),
            'transcript_buffer': deque(maxlen=MAX_BUFFER_SIZE),
            'frame_count': 0
        }
        self.result_history[client_id] = deque(maxlen=MAX_BUFFER_SIZE)
        logger.info(f"Client {client_id} connected with max buffer size: {MAX_BUFFER_SIZE}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.stream_buffers:
            del self.stream_buffers[client_id]
        if client_id in self.result_history:
            del self.result_history[client_id]
        logger.info(f"Client {client_id} disconnected, buffers cleaned up")

    async def send_message(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, message: dict):
        for client_id in list(self.active_connections.keys()):
            await self.send_message(client_id, message)

    def process_audio_chunk(self, client_id: str, audio_base64: str) -> np.ndarray:
        try:
            audio_bytes = base64.b64decode(audio_base64)
            audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
            return audio_array
        except Exception as e:
            logger.error(f"Error decoding audio chunk: {e}")
            return np.array([])


manager = StreamManager()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    await manager.connect(websocket, client_id)
    
    try:
        await manager.send_message(client_id, {
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        })

        while True:
            try:
                data = await websocket.receive_text()
                
                try:
                    frame_data = json.loads(data)
                except json.JSONDecodeError:
                    await manager.send_message(client_id, {
                        "type": "error",
                        "message": "Invalid JSON format"
                    })
                    continue

                if frame_data.get("type") == "ping":
                    await manager.send_message(client_id, {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                if frame_data.get("type") == "frame":
                    try:
                        stream_frame = StreamFrame(**frame_data)
                    except Exception as e:
                        await manager.send_message(client_id, {
                            "type": "error",
                            "message": f"Invalid frame format: {str(e)}"
                        })
                        continue

                    audio_chunk = None
                    if stream_frame.audio:
                        audio_chunk = manager.process_audio_chunk(client_id, stream_frame.audio)
                        if len(audio_chunk) == 0:
                            audio_chunk = None

                    transcript = frame_data.get("transcript")
                    
                    try:
                        result = service.process_stream_frame(
                            stream_frame.frame,
                            audio_chunk=audio_chunk,
                            transcript_text=transcript
                        )
                        
                        response = {
                            "type": "result",
                            "data": result.model_dump(),
                            "frame_index": manager.stream_buffers[client_id]['frame_count']
                        }
                        
                        await manager.send_message(client_id, response)
                        
                        manager.stream_buffers[client_id]['frame_count'] += 1
                        
                        if manager.stream_buffers[client_id]['frame_count'] >= MAX_FRAME_COUNT:
                            manager.stream_buffers[client_id]['frame_count'] = 0
                            service.reset_stream_filter()
                            logger.info(f"Frame count reset for client {client_id} after reaching {MAX_FRAME_COUNT}")
                        
                        if client_id in manager.result_history:
                            manager.result_history[client_id].append({
                                'timestamp': result.timestamp,
                                'emotion': result.emotion
                            })

                    except Exception as e:
                        logger.error(f"Error processing frame: {e}", exc_info=True)
                        await manager.send_message(client_id, {
                            "type": "error",
                            "message": f"Frame processing failed: {str(e)}"
                        })

                elif frame_data.get("type") == "control":
                    action = frame_data.get("action")
                    
                    if action == "start":
                        manager.stream_buffers[client_id] = {
                            'audio_buffer': deque(maxlen=MAX_BUFFER_SIZE),
                            'transcript_buffer': deque(maxlen=MAX_BUFFER_SIZE),
                            'frame_count': 0
                        }
                        manager.result_history[client_id] = deque(maxlen=MAX_BUFFER_SIZE)
                        service.reset_stream_filter()
                        await manager.send_message(client_id, {
                            "type": "control",
                            "action": "started",
                            "timestamp": datetime.now().isoformat(),
                            "maxBufferSize": MAX_BUFFER_SIZE
                        })
                    
                    elif action == "stop":
                        frame_count = manager.stream_buffers[client_id]['frame_count']
                        await manager.send_message(client_id, {
                            "type": "control",
                            "action": "stopped",
                            "frames_processed": frame_count,
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    elif action == "clear":
                        manager.stream_buffers[client_id] = {
                            'audio_buffer': deque(maxlen=MAX_BUFFER_SIZE),
                            'transcript_buffer': deque(maxlen=MAX_BUFFER_SIZE),
                            'frame_count': 0
                        }
                        manager.result_history[client_id] = deque(maxlen=MAX_BUFFER_SIZE)
                        service.reset_stream_filter()
                        await manager.send_message(client_id, {
                            "type": "control",
                            "action": "cleared",
                            "timestamp": datetime.now().isoformat()
                        })

                else:
                    await manager.send_message(client_id, {
                        "type": "error",
                        "message": f"Unknown message type: {frame_data.get('type')}"
                    })

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}", exc_info=True)
                await manager.send_message(client_id, {
                    "type": "error",
                    "message": f"Server error: {str(e)}"
                })

    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}", exc_info=True)
    finally:
        manager.disconnect(client_id)


@router.get("/status")
async def get_stream_status():
    return {
        "active_connections": len(manager.active_connections),
        "clients": list(manager.active_connections.keys())
    }
