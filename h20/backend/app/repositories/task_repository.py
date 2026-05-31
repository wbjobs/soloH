from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.repositories.base import BaseRepository
from app.models.task import Task, TaskLog
from app.schemas.common import PaginationParams


class TaskRepository(BaseRepository[Task]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Task)

    async def create_task(self, task_data: Dict[str, Any]) -> Task:
        task = Task(**task_data)
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        stmt = (
            select(Task)
            .where(Task.task_id == task_id)
            .options(selectinload(Task.logs))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: Optional[float] = None,
        result: Optional[Dict[str, Any]] = None
    ) -> Optional[Task]:
        update_data: Dict[str, Any] = {"status": status}

        if progress is not None:
            update_data["progress"] = progress
        if result is not None:
            update_data["result"] = result

        if status == "running" and progress is not None and progress == 0:
            update_data["started_at"] = datetime.now()
        if status in ["completed", "failed", "cancelled"]:
            update_data["completed_at"] = datetime.now()

        stmt = (
            update(Task)
            .where(Task.task_id == task_id)
            .values(**update_data)
            .returning(Task)
        )
        result_obj = await self.db.execute(stmt)
        await self.db.commit()
        return result_obj.scalar_one_or_none()

    async def add_task_log(
        self,
        task_id: str,
        log_level: str,
        message: str
    ) -> TaskLog:
        log = TaskLog(
            task_id=task_id,
            log_level=log_level,
            message=message
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def list_tasks(
        self,
        pagination_params: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Task], int]:
        skip = (pagination_params.page - 1) * pagination_params.pageSize
        limit = pagination_params.pageSize

        stmt = select(Task)
        count_stmt = select(func.count()).select_from(Task)

        conditions = []
        if filters:
            if "task_type" in filters and filters["task_type"] is not None:
                conditions.append(Task.task_type == filters["task_type"])
            if "status" in filters and filters["status"] is not None:
                conditions.append(Task.status == filters["status"])
            if "start_time" in filters and filters["start_time"] is not None:
                conditions.append(Task.created_at >= filters["start_time"])
            if "end_time" in filters and filters["end_time"] is not None:
                conditions.append(Task.created_at <= filters["end_time"])

        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))

        stmt = stmt.order_by(Task.created_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)

        return list(result.scalars().all()), count_result.scalar_one()
