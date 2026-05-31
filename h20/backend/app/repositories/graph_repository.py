from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime

from app.repositories.base import BaseRepository
from app.models.blockchain import GraphEdge, Transaction, TxInput, TxOutput


class GraphRepository(BaseRepository[GraphEdge]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, GraphEdge)

    async def get_subgraph(
        self,
        center_address: str,
        depth: int = 2,
        min_value: float = 0,
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> List[GraphEdge]:
        visited = set()
        all_edges = []
        current_level = {center_address}

        for _ in range(depth):
            if not current_level:
                break

            next_level = set()
            for addr in current_level:
                if addr in visited:
                    continue
                visited.add(addr)

                stmt = select(GraphEdge).where(
                    and_(
                        or_(
                            GraphEdge.from_address == addr,
                            GraphEdge.to_address == addr
                        ),
                        GraphEdge.value >= min_value
                    )
                )

                if time_range:
                    start_time, end_time = time_range
                    stmt = stmt.where(
                        and_(
                            GraphEdge.block_time >= start_time,
                            GraphEdge.block_time <= end_time
                        )
                    )

                result = await self.db.execute(stmt)
                edges = list(result.scalars().all())
                all_edges.extend(edges)

                for edge in edges:
                    if edge.from_address not in visited:
                        next_level.add(edge.from_address)
                    if edge.to_address not in visited:
                        next_level.add(edge.to_address)

            current_level = next_level

        return all_edges

    async def build_graph_edges(self, transactions: List[Transaction]) -> List[GraphEdge]:
        edges = []
        for tx in transactions:
            if tx.is_coinbase:
                continue

            input_addresses = [inp.address for inp in tx.inputs]
            input_total = sum(inp.value for inp in tx.inputs)

            for out in tx.outputs:
                if out.value <= 0:
                    continue

                for in_addr in input_addresses:
                    value_share = (out.value / input_total) * out.value if input_total > 0 else out.value
                    edge = GraphEdge(
                        from_address=in_addr,
                        to_address=out.address,
                        txid=tx.txid,
                        value=value_share,
                        block_time=tx.block_time
                    )
                    edges.append(edge)
                    self.db.add(edge)

        if edges:
            await self.db.commit()

        return edges

    async def get_outgoing_edges(
        self,
        address: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[GraphEdge]:
        stmt = select(GraphEdge).where(GraphEdge.from_address == address)

        if filters:
            if "min_value" in filters and filters["min_value"] is not None:
                stmt = stmt.where(GraphEdge.value >= filters["min_value"])
            if "start_time" in filters and filters["start_time"] is not None:
                stmt = stmt.where(GraphEdge.block_time >= filters["start_time"])
            if "end_time" in filters and filters["end_time"] is not None:
                stmt = stmt.where(GraphEdge.block_time <= filters["end_time"])
            if "limit" in filters and filters["limit"] is not None:
                stmt = stmt.limit(filters["limit"])

        stmt = stmt.order_by(GraphEdge.block_time.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_incoming_edges(
        self,
        address: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[GraphEdge]:
        stmt = select(GraphEdge).where(GraphEdge.to_address == address)

        if filters:
            if "min_value" in filters and filters["min_value"] is not None:
                stmt = stmt.where(GraphEdge.value >= filters["min_value"])
            if "start_time" in filters and filters["start_time"] is not None:
                stmt = stmt.where(GraphEdge.block_time >= filters["start_time"])
            if "end_time" in filters and filters["end_time"] is not None:
                stmt = stmt.where(GraphEdge.block_time <= filters["end_time"])
            if "limit" in filters and filters["limit"] is not None:
                stmt = stmt.limit(filters["limit"])

        stmt = stmt.order_by(GraphEdge.block_time.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
