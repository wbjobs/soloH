from typing import Any, Dict
from celery import Task
from datetime import datetime

from app.core.database import async_session_factory
from app.repositories import TaskRepository
from app.services import TaskService


class BaseTask(Task):
    abstract = True

    def __call__(self, *args, **kwargs):
        self.task_id = self.request.id
        return super().__call__(*args, **kwargs)

    def on_success(self, retval, task_id, args, kwargs):
        pass

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        import asyncio

        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self._handle_failure(task_id, exc))
        else:
            asyncio.run(self._handle_failure(task_id, exc))

    async def _handle_failure(self, task_id: str, error: Exception):
        async with async_session_factory() as db:
            task_repo = TaskRepository(db)
            task_service = TaskService(task_repo)
            await task_service.handle_task_error(task_id, error)


def update_progress(task_id: str, progress: int, message: str = "") -> None:
    import asyncio

    async def _update():
        async with async_session_factory() as db:
            task_repo = TaskRepository(db)
            task_service = TaskService(task_repo)
            await task_service.update_task_progress(task_id, progress, message)

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"http://localhost:8000/api/v1/tasks/{task_id}/progress",
                    json={"progress": progress, "message": message},
                )
        except Exception:
            pass

    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(_update())
    else:
        asyncio.run(_update())


def handle_task_error(task_id: str, error: Exception) -> None:
    import asyncio

    async def _handle():
        async with async_session_factory() as db:
            task_repo = TaskRepository(db)
            task_service = TaskService(task_repo)
            await task_service.handle_task_error(task_id, error)

    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(_handle())
    else:
        asyncio.run(_handle())


async def add_task_log(task_id: str, level: str, message: str, metadata: Dict[str, Any] = None) -> None:
    async with async_session_factory() as db:
        task_repo = TaskRepository(db)
        task_service = TaskService(task_repo)
        await task_service.add_task_log(task_id, level, message, metadata)
