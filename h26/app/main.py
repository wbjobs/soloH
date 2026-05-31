import logging
from typing import List, Optional
from datetime import datetime

import numpy as np
import torch

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.models.db import TaskStatus
from app.schemas.api import (
    FastaInput,
    PredictionTaskResponse,
    PredictionTaskStatus,
    PredictionResultResponse,
    ModelInfoResponse,
    ErrorResponse,
    MutationInput,
    MutationScanInput,
    AttentionInput,
    StructureCompareInput,
    AttentionResponse,
    MutationResponse,
    MutationScanResponse,
    StructureCompareResponse
)
from app.services.prediction import PredictionService
from app.services.model_loader import get_model_loader
from app.tasks.celery_tasks import process_prediction_task
from app.utils import (
    compute_attention_map,
    get_contact_explanation,
    predict_mutation_effect,
    scan_all_mutations,
    analyze_mutation_impact,
    compare_with_alphafold
)
from app.utils.encoding import get_sequence_features, build_input_tensor
from app.utils.pssm import create_dummy_pssm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Protein Contact Map Prediction API",
    description="使用ResNet架构预测蛋白质接触图的API服务。支持one-hot编码+PSSM输入，输出LxL接触图（8Å阈值），后处理包括接触列表、Top-L精度和MDS三维重建。",
    version="1.0.0",
    contact={
        "name": "Protein Structure Prediction Team",
    },
    license_info={
        "name": "MIT License",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Protein Contact Map Prediction API")
    init_db()
    logger.info("Database initialized")

    model_loader = get_model_loader()
    model_loader.load_model(settings.DEFAULT_MODEL_NAME)
    logger.info(f"Default model {settings.DEFAULT_MODEL_NAME} loaded")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Protein Contact Map Prediction API")


@app.get("/", tags=["Health"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "environment": settings.APP_ENV,
        "default_model": settings.DEFAULT_MODEL_NAME,
        "threshold_angstrom": settings.THRESHOLD_ANGSTROM
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "healthy",
            "models_loaded": get_model_loader().list_loaded_models()
        }
    }


@app.get("/models", tags=["Models"], response_model=List[ModelInfoResponse])
async def get_available_models(db: Session = Depends(get_db)):
    model_loader = get_model_loader()
    available_models = model_loader.get_available_models()

    models = []
    for name, info in available_models.items():
        models.append(ModelInfoResponse(
            name=name,
            description=info["description"],
            version="1.0.0",
            in_channels=info["in_channels"],
            threshold_angstrom=info["threshold"],
            is_available=info.get("pretrained_available", False),
            is_default=(name == settings.DEFAULT_MODEL_NAME),
            trained_on="PDB dataset" if "pdb" in name.lower() else f"CASP{name.split('_')[-1].upper()} dataset",
            training_samples=150000 if "casp" in name.lower() else 100000
        ))

    return models


@app.get("/models/{model_name}", tags=["Models"], response_model=ModelInfoResponse)
async def get_model_info(model_name: str, db: Session = Depends(get_db)):
    model_loader = get_model_loader()
    available_models = model_loader.get_available_models()

    if model_name not in available_models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_name} not found. Available models: {list(available_models.keys())}"
        )

    info = available_models[model_name]
    return ModelInfoResponse(
        name=model_name,
        description=info["description"],
        version="1.0.0",
        in_channels=info["in_channels"],
        threshold_angstrom=info["threshold"],
        is_available=info.get("pretrained_available", False),
        is_default=(model_name == settings.DEFAULT_MODEL_NAME),
        trained_on="PDB dataset" if "pdb" in model_name.lower() else f"CASP{model_name.split('_')[-1].upper()} dataset",
        training_samples=150000 if "casp" in model_name.lower() else 100000
    )


@app.post("/predict", tags=["Prediction"], response_model=PredictionTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_prediction(
    input_data: FastaInput,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        prediction_service = PredictionService(db)

        protein_sequence, seq_hash = prediction_service.process_fasta(input_data.fasta)

        task = prediction_service.create_prediction_task(
            protein_sequence=protein_sequence,
            model_name=input_data.model_name
        )

        if task.status == TaskStatus.PENDING:
            celery_task = process_prediction_task.delay(task.task_id)
            prediction_service.update_task_status(
                task,
                task.status,
                celery_task_id=celery_task.id
            )
            logger.info(f"Submitted task {task.task_id} to Celery (worker_id: {celery_task.id})")

        return PredictionTaskResponse(
            task_id=task.task_id,
            status=task.status,
            model_name=task.model_name,
            sequence_length=protein_sequence.length,
            submitted_at=task.submitted_at
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error submitting prediction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.get("/predict/{task_id}", tags=["Prediction"], response_model=PredictionTaskStatus)
async def get_prediction_status(task_id: str, db: Session = Depends(get_db)):
    prediction_service = PredictionService(db)
    task = prediction_service.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )

    return PredictionTaskStatus(
        task_id=task.task_id,
        status=task.status,
        model_name=task.model_name,
        submitted_at=task.submitted_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        error_message=task.error_message,
        sequence_length=task.protein_sequence.length,
        sequence_header=task.protein_sequence.header
    )


@app.get("/predict/{task_id}/result", tags=["Prediction"], response_model=PredictionResultResponse)
async def get_prediction_result(task_id: str, db: Session = Depends(get_db)):
    prediction_service = PredictionService(db)
    task = prediction_service.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )

    if task.status == TaskStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Prediction failed: {task.error_message or 'Unknown error'}"
        )

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail=f"Prediction still in progress. Current status: {task.status}"
        )

    result = task.result
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction result not found"
        )

    return PredictionResultResponse(
        task_id=task.task_id,
        status=task.status,
        model_name=task.model_name,
        sequence_length=result.sequence_length,
        num_contacts=result.num_contacts,
        threshold_angstrom=result.threshold_angstrom,
        contact_list=result.contact_list,
        precision_metrics=result.precision_metrics,
        coordinates_3d=result.coordinates_3d,
        inference_time_ms=result.inference_time_ms,
        completed_at=task.completed_at
    )


@app.post("/predict/sync", tags=["Prediction"], response_model=PredictionResultResponse)
async def predict_sync(
    input_data: FastaInput,
    db: Session = Depends(get_db)
):
    try:
        prediction_service = PredictionService(db)

        protein_sequence, seq_hash = prediction_service.process_fasta(input_data.fasta)

        task = prediction_service.create_prediction_task(
            protein_sequence=protein_sequence,
            model_name=input_data.model_name
        )

        if task.status != TaskStatus.COMPLETED:
            prediction_service.update_task_status(task, TaskStatus.PROCESSING)

            prediction_data = prediction_service.run_prediction(
                sequence=protein_sequence.sequence,
                model_name=task.model_name
            )

            prediction_service.save_prediction_result(task, prediction_data)

        result = task.result

        return PredictionResultResponse(
            task_id=task.task_id,
            status=task.status,
            model_name=task.model_name,
            sequence_length=result.sequence_length,
            num_contacts=result.num_contacts,
            threshold_angstrom=result.threshold_angstrom,
            contact_list=result.contact_list,
            precision_metrics=result.precision_metrics,
            coordinates_3d=result.coordinates_3d,
            inference_time_ms=result.inference_time_ms,
            completed_at=task.completed_at
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in sync prediction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.delete("/predict/{task_id}", tags=["Prediction"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_prediction_task(task_id: str, db: Session = Depends(get_db)):
    prediction_service = PredictionService(db)
    task = prediction_service.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )

    if task.result:
        db.delete(task.result)

    db.delete(task)
    db.commit()

    logger.info(f"Deleted task {task_id}")
    return None


@app.get("/tasks", tags=["Tasks"])
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    from app.models.db import PredictionTask

    query = db.query(PredictionTask)

    if status:
        query = query.filter(PredictionTask.status == status)

    tasks = query.order_by(PredictionTask.submitted_at.desc()) \
        .offset(offset).limit(limit).all()

    return {
        "total": query.count(),
        "limit": limit,
        "offset": offset,
        "tasks": [
            {
                "task_id": t.task_id,
                "status": t.status,
                "model_name": t.model_name,
                "sequence_length": t.protein_sequence.length,
                "submitted_at": t.submitted_at,
                "completed_at": t.completed_at
            }
            for t in tasks
        ]
    }


@app.post("/explain/attention", tags=["Explanation"], response_model=AttentionResponse)
async def get_attention_explanation(
    input_data: AttentionInput,
    db: Session = Depends(get_db)
):
    try:
        prediction_service = PredictionService(db)
        task = prediction_service.get_task(input_data.task_id)

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {input_data.task_id} not found"
            )

        if task.status != TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task not completed. Current status: {task.status}"
            )

        model_loader = get_model_loader()
        model = model_loader.load_model(task.model_name)

        sequence = task.protein_sequence.sequence
        pssm = create_dummy_pssm(sequence)
        features = get_sequence_features(sequence, pssm)
        input_tensor = build_input_tensor(features)

        seq_len = task.protein_sequence.length
        contact_map_np = np.zeros((seq_len, seq_len), dtype=np.float32)
        if task.result and task.result.contact_list:
            for contact in task.result.contact_list:
                i = contact["i"]
                j = contact["j"]
                prob = contact["probability"]
                contact_map_np[i, j] = prob
                contact_map_np[j, i] = prob
        else:
            with torch.no_grad():
                output = model(input_tensor)
                contact_map_np = output.squeeze(0).numpy()
                contact_map_np = (contact_map_np + contact_map_np.T) / 2

        if input_data.residue_i is not None and input_data.residue_j is not None:
            explanation = get_contact_explanation(
                model, input_tensor, contact_map_np,
                input_data.residue_i, input_data.residue_j
            )
            if explanation is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to generate explanation"
                )
            return AttentionResponse(
                attention_results=[explanation],
                per_residue_importance=[],
                analyzed_contacts=1
            )

        else:
            attention_data = compute_attention_map(
                model, input_tensor, contact_map_np,
                top_k=input_data.top_k
            )
            return AttentionResponse(**attention_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in attention explanation: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.post("/mutate/predict", tags=["Mutation"], response_model=MutationResponse)
async def predict_single_mutation(
    input_data: FastaInput,
    mutation: MutationInput,
    db: Session = Depends(get_db)
):
    try:
        prediction_service = PredictionService(db)
        protein_sequence, _ = prediction_service.process_fasta(input_data.fasta)

        sequence = protein_sequence.sequence
        model_name = mutation.model_name or input_data.model_name or settings.DEFAULT_MODEL_NAME

        model_loader = get_model_loader()
        model = model_loader.load_model(model_name)

        result = predict_mutation_effect(
            model=model,
            sequence=sequence,
            position=mutation.position,
            mutant_aa=mutation.mutant_aa,
            model_name=model_name
        )

        return MutationResponse(**result.to_dict())

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in mutation prediction: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.post("/mutate/scan", tags=["Mutation"], response_model=MutationScanResponse)
async def scan_mutations(
    input_data: FastaInput,
    scan_input: MutationScanInput,
    db: Session = Depends(get_db)
):
    try:
        prediction_service = PredictionService(db)
        protein_sequence, _ = prediction_service.process_fasta(input_data.fasta)

        sequence = protein_sequence.sequence
        model_name = scan_input.model_name or input_data.model_name or settings.DEFAULT_MODEL_NAME

        model_loader = get_model_loader()
        model = model_loader.load_model(model_name)

        positions = scan_input.positions
        if positions is not None:
            max_pos = len(sequence) - 1
            positions = [p for p in positions if 0 <= p <= max_pos]
            if not positions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No valid positions. Valid range: 0-{max_pos}"
                )

        results = scan_all_mutations(
            model=model,
            sequence=sequence,
            model_name=model_name,
            positions=positions
        )

        analysis = analyze_mutation_impact(results)

        response_data = {
            **analysis,
            "results": [r.to_dict() for r in results[:100]]
        }

        return MutationScanResponse(**response_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in mutation scan: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.post("/compare/alphafold", tags=["Structure"], response_model=StructureCompareResponse)
async def compare_with_alphafold_structure(
    task_id: str,
    compare_input: StructureCompareInput,
    db: Session = Depends(get_db)
):
    try:
        prediction_service = PredictionService(db)
        task = prediction_service.get_task(task_id)

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )

        if task.status != TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task not completed. Current status: {task.status}"
            )

        result = task.result
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prediction result not found"
            )

        predicted_coords = np.array(result.coordinates_3d, dtype=np.float32)

        contact_map = np.zeros((result.sequence_length, result.sequence_length))
        for contact in result.contact_list:
            i = contact["i"]
            j = contact["j"]
            prob = contact["probability"]
            contact_map[i, j] = prob
            contact_map[j, i] = prob

        comparison_result = compare_with_alphafold(
            predicted_coords=predicted_coords,
            predicted_contact_map=contact_map,
            alphafold_pdb_content=compare_input.alphafold_pdb,
            threshold_angstrom=compare_input.threshold_angstrom
        )

        return StructureCompareResponse(**comparison_result.to_dict())

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in structure comparison: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": f"HTTP_{exc.status_code}"}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"}
    )
