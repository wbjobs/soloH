from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository
from app.models.analysis import SuspiciousPattern
from app.schemas.common import PaginationParams


class PatternRepository(BaseRepository[SuspiciousPattern]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, SuspiciousPattern)

    async def create_pattern(self, pattern_data: Dict[str, Any]) -> SuspiciousPattern:
        pattern = SuspiciousPattern(**pattern_data)
        self.db.add(pattern)
        await self.db.commit()
        await self.db.refresh(pattern)
        return pattern

    async def get_address_patterns(self, address: str) -> List[SuspiciousPattern]:
        stmt = (
            select(SuspiciousPattern)
            .where(SuspiciousPattern.address == address)
            .order_by(SuspiciousPattern.detected_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_patterns(
        self,
        pagination_params: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[SuspiciousPattern], int]:
        skip = (pagination_params.page - 1) * pagination_params.pageSize
        limit = pagination_params.pageSize

        stmt = select(SuspiciousPattern)
        count_stmt = select(func.count()).select_from(SuspiciousPattern)

        conditions = []
        if filters:
            if "pattern_type" in filters and filters["pattern_type"] is not None:
                conditions.append(SuspiciousPattern.pattern_type == filters["pattern_type"])
            if "severity" in filters and filters["severity"] is not None:
                conditions.append(SuspiciousPattern.severity == filters["severity"])
            if "min_confidence" in filters and filters["min_confidence"] is not None:
                conditions.append(SuspiciousPattern.confidence >= filters["min_confidence"])
            if "address" in filters and filters["address"] is not None:
                conditions.append(SuspiciousPattern.address == filters["address"])
            if "txid" in filters and filters["txid"] is not None:
                conditions.append(SuspiciousPattern.txid == filters["txid"])
            if "start_time" in filters and filters["start_time"] is not None:
                conditions.append(SuspiciousPattern.detected_at >= filters["start_time"])
            if "end_time" in filters and filters["end_time"] is not None:
                conditions.append(SuspiciousPattern.detected_at <= filters["end_time"])

        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))

        stmt = stmt.order_by(SuspiciousPattern.detected_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)

        return list(result.scalars().all()), count_result.scalar_one()

    async def bulk_create_patterns(self, patterns: List[Dict[str, Any]]) -> int:
        db_objs = [SuspiciousPattern(**pattern) for pattern in patterns]
        self.db.add_all(db_objs)
        await self.db.commit()
        return len(db_objs)
