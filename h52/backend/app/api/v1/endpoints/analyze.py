from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, Optional
import logging
import uuid
import os
import asyncio
from datetime import datetime

from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ResultResponse,
    EmotionResult,
    EmotionProbabilities,
)
from app.services import get_emotion_service, EmotionAnalysisService
from app.core.config import settings
from app.api.v1.endpoints.history import add_to_history

logger = logging.getLogger(__name__)

router = APIRouter()
task_router = APIRouter()
result_router = APIRouter()

UPLOAD_DIR = os.path.join(settings.DATA_DIR, "uploads")

tasks: Dict[str, Dict] = {}
results: Dict[str, EmotionResult] = {}


def get_video_path(video_id: str) -> Optional[str]:
    for filename in os.listdir(UPLOAD_DIR):
        if filename.startswith(video_id):
            return os.path.join(UPLOAD_DIR, filename)
    return None


async def process_analysis_task(
    task_id: str,
    video_id: str,
    request: AnalyzeRequest,
    service: EmotionAnalysisService
):
    try:
        tasks[task_id]['status'] = 'processing'
        tasks[task_id]['progress'] = 10.0
        
        video_path = get_video_path(video_id)
        if not video_path:
            raise ValueError(f"Video not found: {video_id}")
        
        tasks[task_id]['progress'] = 30.0
        
        result = await service.analyze_video(
            video_path,
            include_attention=request.includeAttention,
            time_step=request.timeStep
        )
        
        tasks[task_id]['progress'] = 90.0
        
        results[task_id] = result
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100.0
        tasks[task_id]['completed_at'] = datetime.now().isoformat()
        
        add_to_history(result)
        
        logger.info(f"Analysis task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error processing analysis task {task_id}: {e}", exc_info=True)
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
        tasks[task_id]['progress'] = 0.0


@router.post("/{video_id}", response_model=AnalyzeResponse)
async def start_analysis(
    video_id: str,
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    video_path = get_video_path(video_id)
    if not video_path:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
    
    task_id = str(uuid.uuid4())
    
    tasks[task_id] = {
        'task_id': task_id,
        'video_id': video_id,
        'status': 'queued',
        'progress': 0.0,
        'created_at': datetime.now().isoformat(),
        'request': request.model_dump()
    }
    
    background_tasks.add_task(process_analysis_task, task_id, video_id, request, service)
    
    logger.info(f"Analysis task {task_id} started for video {video_id}")
    
    return AnalyzeResponse(
        taskId=task_id,
        status='queued',
        progress=0.0
    )


@task_router.get("/{task_id}/status", response_model=AnalyzeResponse)
async def get_analysis_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    
    task = tasks[task_id]
    
    return AnalyzeResponse(
        taskId=task_id,
        status=task['status'],
        progress=task['progress']
    )


@result_router.get("/{task_id}", response_model=ResultResponse)
async def get_analysis_result(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    
    task = tasks[task_id]
    
    if task['status'] == 'failed':
        raise HTTPException(status_code=500, detail=task.get('error', 'Analysis failed'))
    
    if task['status'] != 'completed':
        raise HTTPException(
            status_code=202,
            detail=f"Analysis still in progress. Current progress: {task['progress']}%"
        )
    
    if task_id not in results:
        raise HTTPException(status_code=404, detail="Result not found")
    
    result = results[task_id]
    processing_time = 0.0
    
    if 'completed_at' in task and 'created_at' in task:
        try:
            completed = datetime.fromisoformat(task['completed_at'])
            created = datetime.fromisoformat(task['created_at'])
            processing_time = (completed - created).total_seconds()
        except Exception as e:
            logger.warning(f"Error calculating processing time: {e}")
    
    return ResultResponse(
        taskId=task_id,
        status='completed',
        result=result,
        processingTime=processing_time
    )


@result_router.get("/{task_id}/export")
async def export_result(
    task_id: str,
    format: str = 'json'
):
    if task_id not in results:
        raise HTTPException(status_code=404, detail=f"Result not found: {task_id}")
    
    result = results[task_id]
    
    if format == 'json':
        import json
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=json.loads(result.model_dump_json()),
            media_type='application/json',
            headers={
                'Content-Disposition': f'attachment; filename="emotion-analysis-{task_id}.json"'
            }
        )
    elif format == 'csv':
        import io
        import csv
        from fastapi.responses import StreamingResponse
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['Field', 'Value'])
        writer.writerow(['ID', result.id])
        writer.writerow(['Timestamp', result.timestamp])
        writer.writerow(['Primary Emotion', result.emotion['category']])
        writer.writerow(['Confidence', result.emotion['confidence']])
        writer.writerow(['Valence', result.valenceArousal.valence])
        writer.writerow(['Arousal', result.valenceArousal.arousal])
        writer.writerow([])
        
        writer.writerow(['Emotion Probabilities'])
        for emotion, prob in result.emotion['probabilities'].items():
            writer.writerow([emotion, prob])
        writer.writerow([])
        
        writer.writerow(['Modality Contributions'])
        for modality, data in result.modalities.items():
            writer.writerow([modality, data['contribution']])
        writer.writerow([])
        
        writer.writerow(['Transcript', result.transcript])
        writer.writerow([])
        
        writer.writerow(['Time Series'])
        writer.writerow(['Time', 'Emotion', 'Valence', 'Arousal'] + list(result.emotion['probabilities'].keys()))
        for point in result.timeSeries:
            row = [
                point.time,
                point.emotion,
                point.valence,
                point.arousal
            ] + [point.probabilities.model_dump()[e] for e in result.emotion['probabilities'].keys()]
            writer.writerow(row)
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="emotion-analysis-{task_id}.csv"'
            }
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
