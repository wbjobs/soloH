from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import get_task_service
from app.services import TaskService
from app.schemas import (
    TaskResponse,
    TaskListResponse,
    TaskLogResponse,
    PaginatedResponse,
    PaginationParams,
)

router = APIRouter()


class RetryTaskResponse(BaseModel):
    taskId: str
    message: str


class CancelTaskResponse(BaseModel):
    taskId: str
    message: str


@router.get("", response_model=PaginatedResponse[TaskListResponse])
async def get_tasks(
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[TaskService, Depends(get_task_service)],
    taskType: Optional[str] = Query(None, description="任务类型"),
    status: Optional[str] = Query(None, description="任务状态"),
):
    """获取任务列表"""
    return await service.get_tasks(
        page=pagination.page,
        page_size=pagination.pageSize,
        task_type=taskType,
        status=status,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_detail(
    task_id: str,
    service: Annotated[TaskService, Depends(get_task_service)],
):
    """获取任务详情"""
    task = await service.get_task_detail(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found",
        )
    return task


@router.post("/{task_id}/retry", response_model=RetryTaskResponse)
async def retry_task(
    task_id: str,
    service: Annotated[TaskService, Depends(get_task_service)],
):
    """重试失败任务"""
    task = await service.get_task_detail(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found",
        )

    if task.status not in ["failed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry task with status '{task.status}'. Only failed or cancelled tasks can be retried.",
        )

    retried_task = await service.retry_task(task_id)
    if not retried_task:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry task",
        )

    return RetryTaskResponse(
        taskId=task_id,
        message="Task retry initiated",
    )


@router.delete("/{task_id}", response_model=CancelTaskResponse)
async def cancel_task(
    task_id: str,
    service: Annotated[TaskService, Depends(get_task_service)],
):
    """取消任务"""
    task = await service.get_task_detail(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found",
        )

    if task.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel task with status '{task.status}'",
        )

    cancelled_task = await service.cancel_task(task_id)
    if not cancelled_task:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel task",
        )

    return CancelTaskResponse(
        taskId=task_id,
        message="Task cancelled",
    )


@router.get("/{task_id}/logs", response_model=PaginatedResponse[TaskLogResponse])
async def get_task_logs(
    task_id: str,
    pagination: Annotated[PaginationParams, Depends()],
    service: Annotated[TaskService, Depends(get_task_service)],
    level: Optional[str] = Query(None, description="日志级别"),
):
    """获取任务日志"""
    task = await service.get_task_detail(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found",
        )

    return await service.get_task_logs(
        task_id=task_id,
        page=pagination.page,
        page_size=pagination.pageSize,
        level=level,
    )
