from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
import os
import uuid
import tempfile
from typing import Optional
import logging

from app.schemas import UploadResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = os.path.join(settings.DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_video_duration(file_path: str) -> float:
    try:
        import moviepy.editor as mp
        video = mp.VideoFileClip(file_path)
        duration = video.duration
        video.close()
        return duration
    except Exception as e:
        logger.warning(f"Failed to get video duration with moviepy: {e}")
        try:
            import cv2
            cap = cv2.VideoCapture(file_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps if fps > 0 else 0
            cap.release()
            return duration
        except Exception as e2:
            logger.error(f"Failed to get video duration: {e2}")
            return 60.0


@router.post("", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail="Only video files are allowed"
        )
    
    try:
        video_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1] if file.filename else ".mp4"
        file_path = os.path.join(UPLOAD_DIR, f"{video_id}{file_extension}")
        
        file_size = 0
        with open(file_path, "wb") as f:
            while chunk := await file.read(8192):
                f.write(chunk)
                file_size += len(chunk)
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        duration = get_video_duration(file_path)
        
        response = UploadResponse(
            videoId=video_id,
            filename=file.filename or f"{video_id}{file_extension}",
            size=file_size,
            duration=duration
        )
        
        logger.info(f"Video uploaded successfully: {video_id}, size: {file_size}, duration: {duration}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading video: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {str(e)}")


@router.get("/{video_id}")
async def get_upload_info(video_id: str):
    for filename in os.listdir(UPLOAD_DIR):
        if filename.startswith(video_id):
            file_path = os.path.join(UPLOAD_DIR, filename)
            file_size = os.path.getsize(file_path)
            duration = get_video_duration(file_path)
            return {
                "videoId": video_id,
                "filename": filename,
                "size": file_size,
                "duration": duration,
                "exists": True
            }
    
    return {"videoId": video_id, "exists": False}
