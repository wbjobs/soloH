import torch
import numpy as np
import hashlib
import time
import uuid
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.models.db import ProteinSequence, PredictionTask, PredictionResult, TaskStatus
from app.utils import (
    parse_fasta,
    validate_sequence,
    generate_pssm,
    get_sequence_features,
    build_input_tensor,
    postprocess_predictions
)
from app.services.model_loader import get_model_loader

logger = logging.getLogger(__name__)


class PredictionService:
    def __init__(self, db: Session):
        self.db = db
        self.model_loader = get_model_loader()

    def _hash_sequence(self, sequence: str) -> str:
        return hashlib.sha256(sequence.encode()).hexdigest()

    def process_fasta(self, fasta_text: str) -> Tuple[ProteinSequence, str]:
        fasta_record = parse_fasta(fasta_text)

        is_valid, error_msg = validate_sequence(
            fasta_record.sequence,
            max_length=settings.MAX_SEQUENCE_LENGTH
        )
        if not is_valid:
            raise ValueError(f"Invalid sequence: {error_msg}")

        seq_hash = self._hash_sequence(fasta_record.sequence)

        existing = self.db.query(ProteinSequence).filter(
            ProteinSequence.sequence_hash == seq_hash
        ).first()

        if existing:
            logger.info(f"Found existing sequence with hash {seq_hash[:16]}...")
            return existing, seq_hash

        protein_seq = ProteinSequence(
            sequence_hash=seq_hash,
            sequence=fasta_record.sequence,
            header=fasta_record.header,
            description=fasta_record.description,
            length=len(fasta_record.sequence)
        )

        self.db.add(protein_seq)
        self.db.commit()
        self.db.refresh(protein_seq)

        logger.info(f"Created new sequence record: {protein_seq.id}")
        return protein_seq, seq_hash

    def create_prediction_task(
        self,
        protein_sequence: ProteinSequence,
        model_name: Optional[str] = None,
        priority: int = 0
    ) -> PredictionTask:
        if model_name is None:
            model_name = settings.DEFAULT_MODEL_NAME

        available_models = self.model_loader.get_available_models()
        if model_name not in available_models:
            raise ValueError(f"Model {model_name} not available. Available: {list(available_models.keys())}")

        existing_task = self.db.query(PredictionTask).filter(
            PredictionTask.protein_sequence_id == protein_sequence.id,
            PredictionTask.model_name == model_name,
            PredictionTask.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING])
        ).first()

        if existing_task:
            logger.info(f"Found existing pending task: {existing_task.task_id}")
            return existing_task

        completed_task = self.db.query(PredictionTask).filter(
            PredictionTask.protein_sequence_id == protein_sequence.id,
            PredictionTask.model_name == model_name,
            PredictionTask.status == TaskStatus.COMPLETED
        ).first()

        if completed_task:
            logger.info(f"Found existing completed task: {completed_task.task_id}")
            return completed_task

        task_id = str(uuid.uuid4())

        task = PredictionTask(
            task_id=task_id,
            protein_sequence_id=protein_sequence.id,
            model_name=model_name,
            status=TaskStatus.PENDING,
            priority=priority
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        logger.info(f"Created prediction task: {task_id}")
        return task

    def run_prediction(
        self,
        sequence: str,
        model_name: str,
        device: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info(f"Starting prediction for sequence length {len(sequence)} with model {model_name}")

        start_time = time.time()

        pssm = generate_pssm(sequence)
        logger.info(f"PSSM generated, shape: {pssm.shape}")

        features = get_sequence_features(sequence, pssm)
        logger.info(f"Features generated, shape: {features.shape}")

        input_tensor = build_input_tensor(features)
        logger.info(f"Input tensor built, shape: {input_tensor.shape}")

        contact_map = self.model_loader.predict(model_name, input_tensor, device)
        contact_map_np = contact_map.numpy()
        logger.info(f"Prediction completed, contact map shape: {contact_map_np.shape}")

        postprocessed = postprocess_predictions(
            contact_map_np,
            threshold_angstrom=settings.THRESHOLD_ANGSTROM
        )

        inference_time_ms = (time.time() - start_time) * 1000
        postprocessed["inference_time_ms"] = inference_time_ms

        logger.info(f"Prediction completed in {inference_time_ms:.2f}ms")
        return postprocessed

    def save_prediction_result(
        self,
        task: PredictionTask,
        prediction_data: Dict[str, Any]
    ) -> PredictionResult:
        result = PredictionResult(
            task_id=task.id,
            contact_list=prediction_data.get("contact_list"),
            precision_metrics=prediction_data.get("precision_metrics"),
            coordinates_3d=prediction_data.get("coordinates_3d"),
            sequence_length=prediction_data.get("sequence_length"),
            num_contacts=prediction_data.get("num_contacts"),
            threshold_angstrom=prediction_data.get("threshold_angstrom"),
            inference_time_ms=prediction_data.get("inference_time_ms")
        )

        self.db.add(result)

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(result)

        logger.info(f"Saved prediction result for task {task.task_id}")
        return result

    def update_task_status(
        self,
        task: PredictionTask,
        status: TaskStatus,
        error_message: Optional[str] = None,
        celery_task_id: Optional[str] = None
    ) -> None:
        task.status = status

        if status == TaskStatus.PROCESSING:
            task.started_at = datetime.utcnow()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            task.completed_at = datetime.utcnow()

        if error_message:
            task.error_message = error_message

        if celery_task_id:
            task.celery_task_id = celery_task_id

        self.db.commit()
        logger.info(f"Updated task {task.task_id} status to {status}")

    def get_task(self, task_id: str) -> Optional[PredictionTask]:
        return self.db.query(PredictionTask).filter(
            PredictionTask.task_id == task_id
        ).first()

    def get_task_result(self, task_id: str) -> Optional[PredictionResult]:
        task = self.get_task(task_id)
        if task is None:
            return None
        return task.result
