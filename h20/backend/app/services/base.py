from typing import Generic, TypeVar, Type, Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository

RepoType = TypeVar("RepoType", bound=BaseRepository)


class BaseService(Generic[RepoType]):
    def __init__(self, db: AsyncSession, repository_class: Type[RepoType]):
        self.db = db
        self.repository = repository_class(db)

    async def get_by_id(self, id: Any) -> Optional[Any]:
        return await self.repository.get_by_id(id)

    async def create(self, obj_in: Dict[str, Any]) -> Any:
        return await self.repository.create(obj_in)

    async def update(self, id: Any, obj_in: Dict[str, Any]) -> Optional[Any]:
        return await self.repository.update(id, obj_in)

    async def delete(self, id: Any) -> bool:
        return await self.repository.delete(id)

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[Any] = None
    ) -> list:
        return await self.repository.list(
            skip=skip,
            limit=limit,
            filters=filters,
            order_by=order_by
        )

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        return await self.repository.count(filters)
