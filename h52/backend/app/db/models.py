from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class AnalysisRecord(Base):
    __tablename__ = "analysis_records"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    video_id = Column(String, index=True)
    video_path = Column(String)
    video_duration = Column(Float)
    
    primary_emotion = Column(String)
    confidence = Column(Float)
    valence = Column(Float)
    arousal = Column(Float)
    
    emotion_probabilities = Column(JSON)
    modality_contributions = Column(JSON)
    transcript = Column(Text)
    
    time_series = Column(JSON)
    attention_matrix = Column(JSON, nullable=True)
    
    processing_time = Column(Float, default=0.0)
    status = Column(String, default="completed")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
