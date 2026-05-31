from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.repositories.base import BaseRepository
from app.models.blockchain import Transaction, TxInput, TxOutput, GraphEdge
from app.schemas.common import PaginationParams


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Transaction)

    async def get_by_txid(self, txid: str) -> Optional[Transaction]:
        stmt = (
            select(Transaction)
            .where(Transaction.txid == txid)
            .options(
                selectinload(Transaction.inputs),
                selectinload(Transaction.outputs)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_transactions(
        self,
        pagination_params: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Transaction], int]:
        skip = (pagination_params.page - 1) * pagination_params.pageSize
        limit = pagination_params.pageSize

        stmt = select(Transaction)
        count_stmt = select(func.count()).select_from(Transaction)

        conditions = []
        if filters:
            if "min_block_height" in filters and filters["min_block_height"] is not None:
                conditions.append(Transaction.block_height >= filters["min_block_height"])
            if "max_block_height" in filters and filters["max_block_height"] is not None:
                conditions.append(Transaction.block_height <= filters["max_block_height"])
            if "start_time" in filters and filters["start_time"] is not None:
                conditions.append(Transaction.block_time >= filters["start_time"])
            if "end_time" in filters and filters["end_time"] is not None:
                conditions.append(Transaction.block_time <= filters["end_time"])
            if "min_value" in filters and filters["min_value"] is not None:
                conditions.append(Transaction.total_output >= filters["min_value"])
            if "is_coinbase" in filters and filters["is_coinbase"] is not None:
                conditions.append(Transaction.is_coinbase == filters["is_coinbase"])
            if "address" in filters and filters["address"] is not None:
                addr = filters["address"]
                subq_input = select(TxInput.txid).where(TxInput.address == addr)
                subq_output = select(TxOutput.txid).where(TxOutput.address == addr)
                conditions.append(or_(
                    Transaction.txid.in_(subq_input),
                    Transaction.txid.in_(subq_output)
                ))

        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))

        stmt = stmt.order_by(Transaction.block_time.desc()).offset(skip).limit(limit)

        result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)

        return list(result.scalars().all()), count_result.scalar_one()

    async def get_transaction_graph(
        self,
        min_value: float = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[GraphEdge]:
        stmt = select(GraphEdge)
        conditions = [GraphEdge.value >= min_value]

        if start_time:
            conditions.append(GraphEdge.block_time >= start_time)
        if end_time:
            conditions.append(GraphEdge.block_time <= end_time)

        stmt = stmt.where(and_(*conditions)).order_by(GraphEdge.value.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_transaction_with_io(
        self,
        transaction_data: Dict[str, Any],
        inputs: List[Dict[str, Any]],
        outputs: List[Dict[str, Any]]
    ) -> Transaction:
        transaction = Transaction(**transaction_data)
        self.db.add(transaction)
        await self.db.flush()

        for input_data in inputs:
            tx_input = TxInput(txid=transaction.txid, **input_data)
            self.db.add(tx_input)

        for output_data in outputs:
            tx_output = TxOutput(txid=transaction.txid, **output_data)
            self.db.add(tx_output)

        await self.db.commit()
        await self.db.refresh(transaction)
        return transaction

    async def bulk_create(self, transactions: List[Dict[str, Any]]) -> int:
        db_objs = [Transaction(**tx) for tx in transactions]
        self.db.add_all(db_objs)
        await self.db.commit()
        return len(db_objs)
