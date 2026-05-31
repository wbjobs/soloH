from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, status
from pydantic import BaseModel

from app.api.dependencies import get_transaction_service, get_task_service
from app.services import TransactionService, TaskService
from app.schemas import (
    TransactionResponse,
    TransactionListResponse,
    PaginatedResponse,
    PaginationParams,
    GraphData,
    ImportCSVRequest,
    ImportAPIRequest,
    TaskResponse,
)

router = APIRouter()


class ImportCSVResponse(BaseModel):
    taskId: str
    message: str


class ImportAPIResponse(BaseModel):
    taskId: str
    message: str


@router.get("", response_model=PaginatedResponse[TransactionListResponse])
async def get_transactions(
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[TransactionService, Depends(get_transaction_service)],
    minBlockHeight: Optional[int] = Query(None, description="最小区块高度"),
    maxBlockHeight: Optional[int] = Query(None, description="最大区块高度"),
    minSuspiciousScore: Optional[float] = Query(None, ge=0, le=100, description="最小可疑分数"),
):
    """获取交易列表"""
    return await service.get_transactions(
        page=pagination.page,
        page_size=pagination.pageSize,
        min_block_height=minBlockHeight,
        max_block_height=maxBlockHeight,
        min_suspicious_score=minSuspiciousScore,
    )


@router.get("/{txid}", response_model=TransactionResponse)
async def get_transaction_detail(
    txid: str,
    service: Annotated[TransactionService, Depends(get_transaction_service)],
):
    """获取交易详情"""
    transaction = await service.get_transaction_by_txid(txid)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with txid {txid} not found",
        )
    return transaction


@router.get("/graph/data", response_model=GraphData)
async def get_transaction_graph(
    service: Annotated[TransactionService, Depends(get_transaction_service)],
    startBlock: Optional[int] = Query(None, description="起始区块高度"),
    endBlock: Optional[int] = Query(None, description="结束区块高度"),
    limit: int = Query(1000, ge=1, le=10000, description="最大交易数量"),
):
    """获取交易图数据"""
    return await service.get_graph_data(
        start_block=startBlock,
        end_block=endBlock,
        limit=limit,
    )


@router.post("/import/csv", response_model=ImportCSVResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_csv(
    params: Annotated[ImportCSVRequest, Depends()],
    transaction_service: Annotated[TransactionService, Depends(get_transaction_service)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
    file: UploadFile = File(..., description="CSV文件"),
):
    """导入CSV文件"""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are allowed",
        )

    task = await task_service.create_task(
        task_type="import_csv",
        name=f"Import CSV: {file.filename}",
        description="Import transactions from CSV file",
        parameters={
            "filePath": params.filePath,
            "type": params.type,
            "delimiter": params.delimiter,
            "hasHeader": params.hasHeader,
            "encoding": params.encoding,
            "mapping": params.mapping,
        },
    )

    try:
        from app.tasks.import_tasks import import_csv_task

        file_content = await file.read()
        import_csv_task.apply_async(
            task_id=task.id,
            kwargs={
                "file_content": file_content,
                "params": params.model_dump(),
            },
        )
    except Exception as e:
        await task_service.fail_task(task.id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start import task: {str(e)}",
        )

    return ImportCSVResponse(
        taskId=task.id,
        message="CSV import task started",
    )


@router.post("/import/api", response_model=ImportAPIResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_from_api(
    request: ImportAPIRequest,
    transaction_service: Annotated[TransactionService, Depends(get_transaction_service)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
):
    """通过API拉取数据"""
    task = await task_service.create_task(
        task_type="import_api",
        name=f"Import from API: {request.source}",
        description="Import transactions from blockchain API",
        parameters=request.model_dump(),
    )

    try:
        from app.tasks.import_tasks import import_api_task

        import_api_task.apply_async(
            task_id=task.id,
            kwargs={
                "block_start": request.startBlock,
                "block_end": request.endBlock,
                "api_source": request.source,
                "params": request.model_dump(),
            },
        )
    except Exception as e:
        await task_service.fail_task(task.id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start API import task: {str(e)}",
        )

    return ImportAPIResponse(
        taskId=task.id,
        message="API import task started",
    )
