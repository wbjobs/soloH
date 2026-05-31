from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime
import logging
import math

from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import AnalysisRecord

from app.schemas import (
    EmotionResult,
    HistoryItem,
    EmotionCategory,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def add_to_history(result: EmotionResult, db: Optional[Session] = None):
    try:
        if db is None:
            from app.db.session import SessionLocal
            db = SessionLocal()
            should_close = True
        else:
            should_close = False
        
        modality_contributions = {
            k: v.get('contribution', 0.0)
            for k, v in result.modalities.items()
        }
        
        record = AnalysisRecord(
            id=result.id,
            timestamp=datetime.fromtimestamp(result.timestamp / 1000) if isinstance(result.timestamp, (int, float)) else datetime.fromisoformat(result.timestamp),
            video_id=getattr(result, 'videoId', None) or result.id,
            video_path=getattr(result, 'videoPath', None),
            video_duration=getattr(result, 'duration', 0.0),
            primary_emotion=result.emotion['category'],
            confidence=result.emotion['confidence'],
            valence=result.valenceArousal.valence,
            arousal=result.valenceArousal.arousal,
            emotion_probabilities=result.emotion['probabilities'],
            modality_contributions=modality_contributions,
            transcript=result.transcript,
            time_series=[p.model_dump() for p in result.timeSeries],
            attention_matrix=result.attentionWeights.model_dump() if result.attentionWeights else None,
            processing_time=getattr(result, 'processingTime', 0.0),
            status='completed'
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        
        logger.info(f"Saved analysis record {result.id} to database")
        
        if should_close:
            db.close()
            
    except Exception as e:
        logger.error(f"Error saving to history: {e}", exc_info=True)


def record_to_history_item(record: AnalysisRecord) -> HistoryItem:
    return HistoryItem(
        id=record.id,
        timestamp=record.timestamp.isoformat(),
        duration=record.video_duration or 0.0,
        primaryEmotion=record.primary_emotion,
        confidence=record.confidence,
        valence=record.valence,
        arousal=record.arousal,
        transcript=record.transcript or "",
        modalityContributions=record.modality_contributions or {}
    )


@router.get("", response_model=dict)
async def get_history(
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    emotion: Optional[EmotionCategory] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(AnalysisRecord)
    
    if emotion:
        query = query.filter(AnalysisRecord.primary_emotion == emotion)
    
    if search:
        query = query.filter(
            AnalysisRecord.transcript.ilike(f"%{search}%")
        )
    
    total = query.count()
    
    offset = (page - 1) * pageSize
    records = query.order_by(AnalysisRecord.created_at.desc()).offset(offset).limit(pageSize).all()
    
    items = [record_to_history_item(r) for r in records]
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "totalPages": math.ceil(total / pageSize)
    }


@router.get("/{id}")
async def get_history_item(
    id: str,
    db: Session = Depends(get_db)
):
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == id).first()
    
    if not record:
        raise HTTPException(status_code=404, detail=f"Record not found: {id}")
    
    emotion_probabilities = record.emotion_probabilities or {}
    modalities = {
        k: {"contribution": v, "confidence": 0.8}
        for k, v in (record.modality_contributions or {}).items()
    }
    
    time_series = record.time_series or []
    from app.schemas import EmotionProbabilities, TimeSeriesPoint
    
    processed_time_series = []
    for p in time_series:
        probs = p.get('probabilities', {}) if isinstance(p, dict) else {}
        if isinstance(probs, dict):
            emo_probs = EmotionProbabilities(**{
                'anger': float(probs.get('anger', 0)),
                'disgust': float(probs.get('disgust', 0)),
                'fear': float(probs.get('fear', 0)),
                'happiness': float(probs.get('happiness', 0)),
                'sadness': float(probs.get('sadness', 0)),
                'surprise': float(probs.get('surprise', 0)),
                'neutral': float(probs.get('neutral', 0)),
            })
        else:
            emo_probs = probs
        
        point = TimeSeriesPoint(
            time=float(p.get('time', 0) if isinstance(p, dict) else 0),
            emotion=p.get('emotion', 'neutral') if isinstance(p, dict) else 'neutral',
            valence=float(p.get('valence', 0) if isinstance(p, dict) else 0),
            arousal=float(p.get('arousal', 0) if isinstance(p, dict) else 0),
            probabilities=emo_probs
        )
        processed_time_series.append(point)
    
    result = EmotionResult(
        id=record.id,
        timestamp=record.timestamp.isoformat(),
        duration=record.video_duration or 0.0,
        emotion={
            'category': record.primary_emotion,
            'confidence': record.confidence,
            'probabilities': emotion_probabilities
        },
        valenceArousal=type('obj', (), {
            'valence': record.valence,
            'arousal': record.arousal
        }),
        modalities=modalities,
        transcript=record.transcript or "",
        timeSeries=processed_time_series,
        attentionWeights=record.attention_matrix
    )
    
    return result


@router.delete("/{id}")
async def delete_history_item(
    id: str,
    db: Session = Depends(get_db)
):
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == id).first()
    
    if not record:
        raise HTTPException(status_code=404, detail=f"Record not found: {id}")
    
    db.delete(record)
    db.commit()
    
    return {"success": True, "message": f"Record {id} deleted"}


@router.delete("")
async def clear_history(
    db: Session = Depends(get_db)
):
    try:
        db.query(AnalysisRecord).delete()
        db.commit()
        return {"success": True, "message": "All history cleared"}
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
