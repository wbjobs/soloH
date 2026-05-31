from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update, desc
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository
from app.models.blockchain import Address, TxInput, TxOutput, Transaction
from app.schemas.common import PaginationParams


class AddressRepository(BaseRepository[Address]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Address)

    async def get_by_address(self, address: str) -> Optional[Address]:
        stmt = select(Address).where(Address.address == address)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_addresses(
        self,
        pagination_params: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Address], int]:
        skip = (pagination_params.page - 1) * pagination_params.pageSize
        limit = pagination_params.pageSize

        stmt = select(Address)
        count_stmt = select(func.count()).select_from(Address)

        conditions = []
        if filters:
            if "min_balance" in filters and filters["min_balance"] is not None:
                conditions.append(Address.balance >= filters["min_balance"])
            if "max_balance" in filters and filters["max_balance"] is not None:
                conditions.append(Address.balance <= filters["max_balance"])
            if "min_tx_count" in filters and filters["min_tx_count"] is not None:
                conditions.append(Address.tx_count >= filters["min_tx_count"])
            if "risk_level" in filters and filters["risk_level"] is not None:
                conditions.append(Address.risk_level == filters["risk_level"])
            if "min_suspicious_score" in filters and filters["min_suspicious_score"] is not None:
                conditions.append(Address.suspicious_score >= filters["min_suspicious_score"])
            if "cluster_id" in filters and filters["cluster_id"] is not None:
                conditions.append(Address.cluster_id == filters["cluster_id"])

        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))

        stmt = stmt.order_by(Address.balance.desc()).offset(skip).limit(limit)

        result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)

        return list(result.scalars().all()), count_result.scalar_one()

    async def get_top_addresses(self, limit: int = 100, sort_by: str = "balance") -> List[Address]:
        stmt = select(Address)
        if sort_by == "balance":
            stmt = stmt.order_by(desc(Address.balance))
        elif sort_by == "tx_count":
            stmt = stmt.order_by(desc(Address.tx_count))
        elif sort_by == "suspicious_score":
            stmt = stmt.order_by(desc(Address.suspicious_score).nullslast())
        elif sort_by == "total_received":
            stmt = stmt.order_by(desc(Address.total_received))
        else:
            stmt = stmt.order_by(desc(Address.balance))
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def upsert_address(self, address_data: Dict[str, Any]) -> Address:
        address = address_data.get("address")
        existing = await self.get_by_address(address)

        if existing:
            stmt = (
                update(Address)
                .where(Address.address == address)
                .values(**address_data)
                .returning(Address)
            )
            result = await self.db.execute(stmt)
            await self.db.commit()
            return result.scalar_one()
        else:
            db_obj = Address(**address_data)
            self.db.add(db_obj)
            await self.db.commit()
            await self.db.refresh(db_obj)
            return db_obj

    async def get_address_transactions(
        self,
        address: str,
        pagination_params: PaginationParams
    ) -> Tuple[List[Transaction], int]:
        skip = (pagination_params.page - 1) * pagination_params.pageSize
        limit = pagination_params.pageSize

        subq_input = select(TxInput.txid).where(TxInput.address == address)
        subq_output = select(TxOutput.txid).where(TxOutput.address == address)

        stmt = (
            select(Transaction)
            .where(
                or_(
                    Transaction.txid.in_(subq_input),
                    Transaction.txid.in_(subq_output)
                )
            )
            .order_by(Transaction.block_time.desc())
            .offset(skip)
            .limit(limit)
        )

        count_stmt = (
            select(func.count())
            .select_from(Transaction)
            .where(
                or_(
                    Transaction.txid.in_(subq_input),
                    Transaction.txid.in_(subq_output)
                )
            )
        )

        result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)

        return list(result.scalars().all()), count_result.scalar_one()

    async def calculate_address_stats(self, address: str) -> Dict[str, Any]:
        received_stmt = (
            select(func.coalesce(func.sum(TxOutput.value), 0))
            .where(TxOutput.address == address)
        )
        sent_stmt = (
            select(func.coalesce(func.sum(TxInput.value), 0))
            .where(TxInput.address == address)
        )
        tx_in_stmt = (
            select(func.count(TxInput.id))
            .where(TxInput.address == address)
        )
        tx_out_stmt = (
            select(func.count(TxOutput.id))
            .where(TxOutput.address == address)
        )
        first_seen_stmt = (
            select(func.min(Transaction.block_time))
            .select_from(Transaction)
            .join(TxInput, Transaction.txid == TxInput.txid)
            .where(TxInput.address == address)
        )
        last_seen_stmt = (
            select(func.max(Transaction.block_time))
            .select_from(Transaction)
            .join(TxOutput, Transaction.txid == TxOutput.txid)
            .where(TxOutput.address == address)
        )

        received = await self.db.execute(received_stmt)
        sent = await self.db.execute(sent_stmt)
        tx_in = await self.db.execute(tx_in_stmt)
        tx_out = await self.db.execute(tx_out_stmt)
        first_seen = await self.db.execute(first_seen_stmt)
        last_seen = await self.db.execute(last_seen_stmt)

        total_received = received.scalar_one()
        total_sent = sent.scalar_one()
        tx_count = tx_in.scalar_one() + tx_out.scalar_one()
        balance = total_received - total_sent
        first_seen_time = first_seen.scalar_one_or_none()
        last_seen_time = last_seen.scalar_one_or_none()

        return {
            "total_received": total_received,
            "total_sent": total_sent,
            "balance": balance,
            "tx_count": tx_count,
            "first_seen": first_seen_time,
            "last_seen": last_seen_time
        }

    async def update_suspicious_score(
        self,
        address: str,
        score: float,
        risk_factors: Optional[Dict[str, Any]] = None,
        risk_level: Optional[str] = None
    ) -> Optional[Address]:
        update_data = {
            "suspicious_score": score,
            "risk_factors": risk_factors,
            "risk_level": risk_level
        }
        stmt = (
            update(Address)
            .where(Address.address == address)
            .values(**update_data)
            .returning(Address)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.scalar_one_or_none()
