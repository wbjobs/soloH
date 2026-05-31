from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService
from app.repositories import AddressRepository, GraphRepository, PatternRepository
from app.models.blockchain import Address
from app.schemas.common import PaginationParams, PaginatedResponse


class AddressService(BaseService[AddressRepository]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, AddressRepository)
        self.graph_repo = GraphRepository(db)
        self.pattern_repo = PatternRepository(db)

    async def get_address_detail(self, address: str) -> Optional[Address]:
        addr = await self.repository.get_by_address(address)
        if addr:
            stats = await self.repository.calculate_address_stats(address)
            addr.total_received = stats["total_received"]
            addr.total_sent = stats["total_sent"]
            addr.balance = stats["balance"]
            addr.tx_count = stats["tx_count"]
            addr.first_seen = stats["first_seen"]
            addr.last_seen = stats["last_seen"]
        return addr

    async def get_address_list(self, params: PaginationParams, filters: Optional[Dict[str, Any]] = None) -> PaginatedResponse[Address]:
        items, total = await self.repository.list_addresses(params, filters)
        total_pages = (total + params.pageSize - 1) // params.pageSize
        return PaginatedResponse(
            items=items,
            total=total,
            page=params.page,
            pageSize=params.pageSize,
            totalPages=total_pages
        )

    async def get_address_subgraph(self, address: str, depth: int = 2, min_value: float = 0):
        return await self.graph_repo.get_subgraph(address, depth, min_value)

    async def calculate_suspicious_score(self, address: str) -> Optional[Address]:
        patterns = await self.pattern_repo.get_address_patterns(address)
        stats = await self.repository.calculate_address_stats(address)

        score = 0.0
        risk_factors = {}
        risk_level = "low"

        pattern_weights = {
            "layering": 25,
            "mixing": 30,
            "structuring": 20,
            "cycle": 25,
            "peeling": 15,
            "funnel": 20,
            "dusting": 10,
        }

        for pattern in patterns:
            weight = pattern_weights.get(pattern.pattern_type, 10)
            contribution = weight * pattern.confidence
            score += contribution
            risk_factors[pattern.pattern_type] = {
                "confidence": pattern.confidence,
                "severity": pattern.severity,
                "description": pattern.description
            }

        if stats["tx_count"] > 1000:
            score += 10
            risk_factors["high_tx_count"] = stats["tx_count"]

        if stats["total_received"] > 1000:
            score += 5
            risk_factors["high_volume"] = stats["total_received"]

        score = min(score, 100)

        if score >= 70:
            risk_level = "high"
        elif score >= 40:
            risk_level = "medium"

        return await self.repository.update_suspicious_score(address, score, risk_factors, risk_level)

    async def get_top_addresses(self, limit: int = 100, sort_by: str = "balance") -> List[Address]:
        return await self.repository.get_top_addresses(limit, sort_by)
