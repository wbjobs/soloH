import logging
import traceback
from typing import Optional

from app.tasks.celery_config import make_celery
from app.database import SessionLocal
from app.models.db import PredictionTask, TaskStatus
from app.services.prediction import PredictionService
from app.services.model_loader import get_model_loader

celery_app = make_celery()
logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="process_prediction", max_retries=3)
def process_prediction_task(self, task_id: str, device: Optional[str] = None):
    logger.info(f"Starting prediction task: {task_id}")

    db = SessionLocal()
    try:
        prediction_service = PredictionService(db)

        task = prediction_service.get_task(task_id)
        if task is None:
            logger.error(f"Task {task_id} not found")
            return {"status": "error", "message": f"Task {task_id} not found"}

        if task.status == TaskStatus.COMPLETED:
            logger.info(f"Task {task_id} already completed")
            return {"status": "completed", "task_id": task_id}

        prediction_service.update_task_status(
            task,
            TaskStatus.PROCESSING,
            celery_task_id=self.request.id
        )

        sequence = task.protein_sequence.sequence
        model_name = task.model_name

        logger.info(f"Running prediction for sequence length {len(sequence)} with model {model_name}")

        prediction_data = prediction_service.run_prediction(
            sequence=sequence,
            model_name=model_name,
            device=device
        )

        prediction_service.save_prediction_result(task, prediction_data)

        logger.info(f"Task {task_id} completed successfully")

        return {
            "status": "success",
            "task_id": task_id,
            "num_contacts": prediction_data.get("num_contacts"),
            "inference_time_ms": prediction_data.get("inference_time_ms")
        }

    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        logger.error(traceback.format_exc())

        try:
            task = db.query(PredictionTask).filter(
                PredictionTask.task_id == task_id
            ).first()
            if task:
                prediction_service = PredictionService(db)
                prediction_service.update_task_status(
                    task,
                    TaskStatus.FAILED,
                    error_message=str(e)
                )
        except Exception as inner_e:
            logger.error(f"Error updating task status for {task_id}: {str(inner_e)}")

        self.retry(exc=e, countdown=60, max_retries=3)

        return {"status": "error", "task_id": task_id, "error": str(e)}

    finally:
        db.close()


@celery_app.task(name="cleanup_old_tasks")
def cleanup_old_tasks(days: int = 30):
    logger.info(f"Starting cleanup of tasks older than {days} days")

    db = SessionLocal()
    try:
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        deleted_count = db.query(PredictionTask).filter(
            PredictionTask.completed_at < cutoff_date
        ).delete()

        db.commit()
        logger.info(f"Cleaned up {deleted_count} old tasks")

        return {"status": "success", "deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"Error cleaning up old tasks: {str(e)}")
        db.rollback()
        return {"status": "error", "error": str(e)}

    finally:
        db.close()


@celery_app.task(name="reload_model")
def reload_model(model_name: str, force_reload: bool = True):
    logger.info(f"Reloading model: {model_name}")

    try:
        model_loader = get_model_loader()
        model = model_loader.load_model(model_name, force_reload=force_reload)
        model_hash = model_loader.get_model_hash(model_name)

        logger.info(f"Model {model_name} reloaded successfully, hash: {model_hash[:16]}...")

        return {
            "status": "success",
            "model_name": model_name,
            "hash": model_hash,
            "loaded_models": model_loader.list_loaded_models()
        }

    except Exception as e:
        logger.error(f"Error reloading model {model_name}: {str(e)}")
        return {"status": "error", "model_name": model_name, "error": str(e)}


@celery_app.task(name="list_loaded_models")
def list_loaded_models():
    try:
        model_loader = get_model_loader()
        loaded_models = model_loader.list_loaded_models()
        available_models = model_loader.get_available_models()

        return {
            "status": "success",
            "loaded_models": loaded_models,
            "available_models": available_models
        }

    except Exception as e:
        logger.error(f"Error listing models: {str(e)}")
        return {"status": "error", "error": str(e)}
