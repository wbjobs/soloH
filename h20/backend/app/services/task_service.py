from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime

from app.services.base import BaseService
from app.repositories import TaskRepository
from app.models.task import Task
from app.schemas.common import PaginationParams, PaginatedResponse


class TaskService(BaseService[TaskRepository]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, TaskRepository)

    async def create_task(self, task_type: str, params: Optional[Dict[str, Any]] = None) -> Task:
        task_id = str(uuid.uuid4())
        task_data = {
            "task_id": task_id,
            "task_type": task_type,
            "status": "pending",
            "progress": 0.0,
            "params": params or {}
        }
        task = await self.repository.create_task(task_data)
        await self.repository.add_task_log(task_id, "info", f"任务已创建，类型: {task_type}")
        return task

    async def get_task_status(self, task_id: str) -> Optional[Task]:
        return await self.repository.get_task(task_id)

    async def list_tasks(self, params: PaginationParams, filters: Optional[Dict[str, Any]] = None) -> PaginatedResponse[Task]:
        items, total = await self.repository.list_tasks(params, filters)
        total_pages = (total + params.pageSize - 1) // params.pageSize
        return PaginatedResponse(
            items=items,
            total=total,
            page=params.page,
            pageSize=params.pageSize,
            totalPages=total_pages
        )

    async def cancel_task(self, task_id: str) -> Optional[Task]:
        task = await self.repository.get_task(task_id)
        if not task:
            return None

        if task.status in ["pending", "running"]:
            await self.repository.add_task_log(task_id, "warning", "任务被用户取消")
            return await self.repository.update_task_status(task_id, "cancelled", task.progress)

        return task

    async def retry_task(self, task_id: str) -> Optional[Task]:
        task = await self.repository.get_task(task_id)
        if not task:
            return None

        if task.status in ["failed", "cancelled"]:
            new_task = await self.create_task(task.task_type, task.params)
            await self.repository.add_task_log(
                new_task.task_id,
                "info",
                f"重试任务，原任务ID: {task_id}"
            )
            return new_task

        return None

    async def start_task(self, task_id: str) -> Optional[Task]:
        await self.repository.add_task_log(task_id, "info", "任务开始执行")
        return await self.repository.update_task_status(task_id, "running", 0.0)

    async def update_progress(self, task_id: str, progress: float, message: Optional[str] = None) -> Optional[Task]:
        if message:
            await self.repository.add_task_log(task_id, "info", f"进度更新: {progress:.1f}% - {message}")
        return await self.repository.update_task_status(task_id, "running", progress)

    async def complete_task(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> Optional[Task]:
        await self.repository.add_task_log(task_id, "info", "任务执行完成")
        return await self.repository.update_task_status(task_id, "completed", 100.0, result)

    async def fail_task(self, task_id: str, error_message: str) -> Optional[Task]:
        await self.repository.add_task_log(task_id, "error", f"任务执行失败: {error_message}")
        return await self.repository.update_task_status(
            task_id,
            "failed",
            None,
            {"error": error_message}
        )

    async def add_log(self, task_id: str, log_level: str, message: str) -> None:
        await self.repository.add_task_log(task_id, log_level, message)
