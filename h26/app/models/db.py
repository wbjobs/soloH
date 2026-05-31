from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProteinSequence(Base):
    __tablename__ = "protein_sequences"

    id = Column(Integer, primary_key=True, index=True)
    sequence_hash = Column(String(64), unique=True, index=True, nullable=False)
    sequence = Column(Text, nullable=False)
    header = Column(String(255))
    description = Column(Text)
    length = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    prediction_tasks = relationship("PredictionTask", back_populates="protein_sequence")

    def __repr__(self):
        return f"<ProteinSequence(id={self.id}, length={self.length}, hash={self.sequence_hash[:16]}...)>"


class PredictionTask(Base):
    __tablename__ = "prediction_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(36), unique=True, index=True, nullable=False)
    protein_sequence_id = Column(Integer, ForeignKey("protein_sequences.id"), nullable=False)
    model_name = Column(String(64), nullable=False)
    status = Column(String(20), default=TaskStatus.PENDING, nullable=False)
    priority = Column(Integer, default=0)

    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)

    celery_task_id = Column(String(64))

    protein_sequence = relationship("ProteinSequence", back_populates="prediction_tasks")
    result = relationship("PredictionResult", back_populates="task", uselist=False)

    def __repr__(self):
        return f"<PredictionTask(id={self.id}, task_id={self.task_id}, status={self.status})>"


class PredictionResult(Base):
    __tablename__ = "prediction_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("prediction_tasks.id"), unique=True, nullable=False)

    contact_map_path = Column(String(512))
    contact_list = Column(JSON)
    precision_metrics = Column(JSON)
    coordinates_3d = Column(JSON)

    sequence_length = Column(Integer)
    num_contacts = Column(Integer)
    threshold_angstrom = Column(Float)
    inference_time_ms = Column(Float)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("PredictionTask", back_populates="result")

    def __repr__(self):
        return f"<PredictionResult(id={self.id}, task_id={self.task_id}, num_contacts={self.num_contacts})>"


class ModelInfo(Base):
    __tablename__ = "model_info"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, index=True, nullable=False)
    description = Column(Text)
    version = Column(String(20))
    in_channels = Column(Integer, default=80)
    threshold_angstrom = Column(Float, default=8.0)
    file_path = Column(String(512))
    is_available = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    trained_on = Column(String(255))
    training_samples = Column(Integer)
    last_updated = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ModelInfo(id={self.id}, name={self.name}, available={self.is_available})>"
