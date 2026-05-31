from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, Dict, List
import logging
import numpy as np

from app.schemas import (
    CalibrationStartResponse,
    CalibrationSampleRequest,
    CalibrationSampleResponse,
    CalibrationCompleteResponse,
    SessionStartRequest,
    SessionStartResponse,
    AdversarialDetectionResponse,
)
from app.services import get_emotion_service, EmotionAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/calibration/start/{user_id}", response_model=CalibrationStartResponse)
async def start_calibration(
    user_id: str,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    result = service.personalization.start_calibration_session(user_id)
    return CalibrationStartResponse(
        userId=user_id,
        sessionStarted=result['session_started'],
        requiredSamples=result['required_samples'],
        currentSamples=result['current_samples']
    )


@router.post("/calibration/sample", response_model=CalibrationSampleResponse)
async def add_calibration_sample(
    request: CalibrationSampleRequest,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    facial_landmarks = None
    if request.facialLandmarks is not None:
        facial_landmarks = np.array(request.facialLandmarks)
    
    voice_features = None
    if request.voiceFeatures is not None:
        voice_features = np.array(request.voiceFeatures)
    
    result = service.personalization.add_calibration_sample(
        user_id=request.userId,
        facial_landmarks=facial_landmarks,
        voice_features=voice_features,
        text_features=request.textFeatures,
        emotion_probs=request.emotionProbabilities,
        valence=request.valence,
        arousal=request.arousal
    )
    
    return CalibrationSampleResponse(
        userId=request.userId,
        currentSamples=result['current_samples'],
        requiredSamples=result['required_samples'],
        canComplete=result['can_complete']
    )


@router.post("/calibration/complete/{user_id}", response_model=CalibrationCompleteResponse)
async def complete_calibration(
    user_id: str,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    try:
        baseline = service.personalization.complete_calibration(user_id)
        return CalibrationCompleteResponse(
            userId=user_id,
            isCalibrated=baseline.is_calibrated,
            calibrationSamples=baseline.calibration_samples,
            emotionBaseline=baseline.emotion_baseline,
            valenceBaseline=baseline.valence_baseline,
            arousalBaseline=baseline.arousal_baseline
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/calibration/{user_id}")
async def get_calibration_status(
    user_id: str,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    baseline = service.personalization.get_user_baseline(user_id)
    if baseline is None:
        return {
            "userId": user_id,
            "isCalibrated": False,
            "message": "User not calibrated"
        }
    return baseline.to_dict()


@router.delete("/calibration/{user_id}")
async def reset_calibration(
    user_id: str,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    service.personalization.reset_calibration(user_id)
    return {
        "success": True,
        "message": f"Calibration reset for user {user_id}"
    }


@router.post("/session/start", response_model=SessionStartResponse)
async def start_session(
    request: SessionStartRequest,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    result = service.context_tracker.start_session(
        session_id=request.sessionId,
        user_id=request.userId
    )
    return SessionStartResponse(
        sessionId=result['session_id'],
        userId=result['user_id'],
        createdAt=result['created_at'],
        maxHistory=result['max_history']
    )


@router.get("/session/{session_id}/history")
async def get_session_history(
    session_id: str,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    history = service.context_tracker.get_session_history(session_id)
    return {
        "sessionId": session_id,
        "history": [state.to_dict() for state in history]
    }


@router.get("/session/{session_id}/summary")
async def get_session_summary(
    session_id: str,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    summary = service.context_tracker.get_session_summary(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return summary


@router.post("/session/{session_id}/end")
async def end_session(
    session_id: str,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    summary = service.context_tracker.end_session(session_id)
    return {
        "success": True,
        "summary": summary
    }


@router.get("/session/transitions")
async def get_emotion_transitions(
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    transitions = service.context_tracker.get_transition_matrix()
    return {
        "transitions": transitions,
        "emotions": ['anger', 'joy', 'sadness', 'surprise', 'disgust', 'fear', 'neutral']
    }


@router.get("/user/{user_id}/profile")
async def get_user_emotion_profile(
    user_id: str,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    profile = service.context_tracker.get_user_profile(user_id)
    if not profile:
        return {
            "userId": user_id,
            "message": "No profile available for this user"
        }
    return profile


@router.post("/adversarial/check", response_model=AdversarialDetectionResponse)
async def check_adversarial(
    audio_features: Optional[List[float]] = None,
    video_features: Optional[List[float]] = None,
    text_features: Optional[List[float]] = None,
    audio_probs: Optional[Dict[str, float]] = None,
    video_probs: Optional[Dict[str, float]] = None,
    text_probs: Optional[Dict[str, float]] = None,
    fused_probs: Optional[Dict[str, float]] = None,
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    audio_feat = np.array(audio_features) if audio_features else None
    video_feat = np.array(video_features) if video_features else None
    text_feat = np.array(text_features) if text_features else None
    
    result = service.adversarial_detector.detect(
        audio_features=audio_feat,
        video_features=video_feat,
        text_features=text_feat,
        fused_probabilities=fused_probs,
        audio_probs=audio_probs,
        video_probs=video_probs,
        text_probs=text_probs,
        feature_history=service.feature_history
    )
    
    return AdversarialDetectionResponse(
        isAdversarial=result.is_adversarial,
        confidence=result.confidence,
        detectionMethod=result.detection_method,
        anomalyScores=result.anomaly_scores,
        reasons=result.reasons,
        timestamp=result.timestamp.isoformat()
    )


@router.get("/adversarial/stats")
async def get_adversarial_stats(
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    stats = service.adversarial_detector.get_detection_stats()
    return stats


@router.post("/analyze/{video_id}/enhanced")
async def start_enhanced_analysis(
    video_id: str,
    user_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    include_attention: bool = Query(True),
    time_step: int = Query(2),
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    from app.api.v1.endpoints.analyze import get_video_path, tasks, results, process_analysis_task
    from fastapi import BackgroundTasks
    from app.schemas import AnalyzeRequest
    from datetime import datetime
    import uuid
    
    video_path = get_video_path(video_id)
    if not video_path:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
    
    task_id = str(uuid.uuid4())
    
    request = AnalyzeRequest(
        includeAttention=include_attention,
        timeStep=time_step,
        userId=user_id,
        sessionId=session_id
    )
    
    tasks[task_id] = {
        'task_id': task_id,
        'video_id': video_id,
        'user_id': user_id,
        'session_id': session_id,
        'status': 'queued',
        'progress': 0.0,
        'created_at': datetime.now().isoformat(),
        'request': request.model_dump()
    }
    
    async def enhanced_process():
        from app.schemas import AnalyzeResponse, ResultResponse
        try:
            tasks[task_id]['status'] = 'processing'
            tasks[task_id]['progress'] = 10.0
            
            result = await service.analyze_video(
                video_path,
                include_attention=include_attention,
                time_step=time_step,
                user_id=user_id,
                session_id=session_id
            )
            
            tasks[task_id]['progress'] = 90.0
            
            results[task_id] = result
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100.0
            tasks[task_id]['completed_at'] = datetime.now().isoformat()
            
            from app.api.v1.endpoints.history import add_to_history
            add_to_history(result)
            
            logger.info(f"Enhanced analysis task {task_id} completed for video {video_id}")
            
        except Exception as e:
            logger.error(f"Error processing enhanced analysis task {task_id}: {e}", exc_info=True)
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)
            tasks[task_id]['progress'] = 0.0
    
    import asyncio
    asyncio.create_task(enhanced_process())
    
    from app.schemas import AnalyzeResponse
    return AnalyzeResponse(
        taskId=task_id,
        status='queued',
        progress=0.0
    )


@router.get("/sessions/cleanup")
async def cleanup_expired_sessions(
    service: EmotionAnalysisService = Depends(get_emotion_service)
):
    count = service.context_tracker.cleanup_expired_sessions()
    return {
        "success": True,
        "cleaned_sessions": count,
        "message": f"Cleaned up {count} expired sessions"
    }
