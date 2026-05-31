from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository
from app.models.analysis import AddressCluster, ClusterMember
from app.models.blockchain import Address
from app.schemas.common import PaginationParams


class ClusterRepository(BaseRepository[AddressCluster]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, AddressCluster)

    async def create_cluster(self, cluster_data: Dict[str, Any]) -> AddressCluster:
        cluster = AddressCluster(**cluster_data)
        self.db.add(cluster)
        await self.db.commit()
        await self.db.refresh(cluster)
        return cluster

    async def add_member(self, cluster_id: str, address: str) -> Optional[ClusterMember]:
        member = ClusterMember(cluster_id=cluster_id, address=address)
        self.db.add(member)

        stmt = (
            update(Address)
            .where(Address.address == address)
            .values(cluster_id=cluster_id)
        )
        await self.db.execute(stmt)

        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def get_cluster(self, cluster_id: str) -> Optional[AddressCluster]:
        stmt = (
            select(AddressCluster)
            .where(AddressCluster.cluster_id == cluster_id)
            .options(
                selectinload(AddressCluster.members),
                selectinload(AddressCluster.addresses)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_clusters(
        self,
        pagination_params: PaginationParams
    ) -> Tuple[List[AddressCluster], int]:
        skip = (pagination_params.page - 1) * pagination_params.pageSize
        limit = pagination_params.pageSize

        stmt = (
            select(AddressCluster)
            .order_by(AddressCluster.size.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(AddressCluster)

        result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)

        return list(result.scalars().all()), count_result.scalar_one()

    async def get_address_cluster(self, address: str) -> Optional[AddressCluster]:
        stmt = (
            select(AddressCluster)
            .join(ClusterMember, AddressCluster.cluster_id == ClusterMember.cluster_id)
            .where(ClusterMember.address == address)
            .options(
                selectinload(AddressCluster.members),
                selectinload(AddressCluster.addresses)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def bulk_create_members(self, cluster_id: str, addresses: List[str]) -> int:
        members = [
            ClusterMember(cluster_id=cluster_id, address=addr)
            for addr in addresses
        ]
        self.db.add_all(members)

        for addr in addresses:
            stmt = (
                update(Address)
                .where(Address.address == addr)
                .values(cluster_id=cluster_id)
            )
            await self.db.execute(stmt)

        await self.db.commit()
        return len(members)
