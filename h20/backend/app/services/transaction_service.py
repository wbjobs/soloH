from typing import Optional, Dict, Any, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import csv
import aiohttp

from app.services.base import BaseService
from app.repositories import TransactionRepository
from app.models.blockchain import Transaction
from app.schemas.common import PaginationParams, PaginatedResponse


class TransactionService(BaseService[TransactionRepository]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, TransactionRepository)

    async def import_transactions_from_csv(self, file_path: str) -> int:
        count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            batch = []
            for row in reader:
                tx_data = self._parse_csv_row(row)
                batch.append(tx_data)
                if len(batch) >= 1000:
                    count += await self.repository.bulk_create(batch)
                    batch = []
            if batch:
                count += await self.repository.bulk_create(batch)
        return count

    def _parse_csv_row(self, row: Dict[str, str]) -> Dict[str, Any]:
        return {
            "txid": row.get("txid", ""),
            "block_height": int(row.get("block_height", 0)),
            "block_time": datetime.fromisoformat(row.get("block_time", "")).replace(tzinfo=None) if row.get("block_time") else None,
            "total_input": float(row.get("total_input", 0)),
            "total_output": float(row.get("total_output", 0)),
            "fee": float(row.get("fee", 0)),
            "input_count": int(row.get("input_count", 0)),
            "output_count": int(row.get("output_count", 0)),
            "is_coinbase": row.get("is_coinbase", "false").lower() == "true"
        }

    async def import_transactions_from_api(self, block_range: Tuple[int, int], api_source: str = "blockchain.info") -> int:
        start_block, end_block = block_range
        count = 0

        async with aiohttp.ClientSession() as session:
            for block_height in range(start_block, end_block + 1):
                block_data = await self._fetch_block(session, block_height, api_source)
                if block_data:
                    transactions = await self._parse_block_transactions(block_data)
                    for tx_data, inputs, outputs in transactions:
                        await self.repository.create_transaction_with_io(tx_data, inputs, outputs)
                        count += 1

        return count

    async def _fetch_block(self, session: aiohttp.ClientSession, block_height: int, api_source: str) -> Optional[Dict[str, Any]]:
        url = f"https://blockchain.info/block-height/{block_height}?format=json"
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
        except Exception:
            pass
        return None

    async def _parse_block_transactions(self, block_data: Dict[str, Any]) -> List[Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]]:
        transactions = []
        blocks = block_data.get("blocks", [])
        if blocks:
            block = blocks[0]
            block_time = datetime.fromtimestamp(block.get("time", 0))
            for tx in block.get("tx", []):
                tx_data = {
                    "txid": tx.get("hash", ""),
                    "block_height": block.get("height", 0),
                    "block_time": block_time,
                    "total_input": sum(inp.get("prev_out", {}).get("value", 0) for inp in tx.get("inputs", [])) / 1e8,
                    "total_output": sum(out.get("value", 0) for out in tx.get("out", [])) / 1e8,
                    "fee": tx.get("fee", 0) / 1e8,
                    "input_count": len(tx.get("inputs", [])),
                    "output_count": len(tx.get("out", [])),
                    "is_coinbase": any(inp.get("prev_out") is None for inp in tx.get("inputs", []))
                }

                inputs = []
                for inp in tx.get("inputs", []):
                    prev_out = inp.get("prev_out", {})
                    inputs.append({
                        "vout": inp.get("prev_out", {}).get("n", 0),
                        "prev_txid": prev_out.get("tx_index", ""),
                        "prev_vout": prev_out.get("n", 0),
                        "address": prev_out.get("addr", ""),
                        "value": prev_out.get("value", 0) / 1e8
                    })

                outputs = []
                for out in tx.get("out", []):
                    outputs.append({
                        "vout": out.get("n", 0),
                        "address": out.get("addr", ""),
                        "value": out.get("value", 0) / 1e8,
                        "script_type": out.get("type", ""),
                        "is_spent": out.get("spent", False)
                    })

                transactions.append((tx_data, inputs, outputs))

        return transactions

    async def get_transaction_list(self, params: PaginationParams, filters: Optional[Dict[str, Any]] = None) -> PaginatedResponse[Transaction]:
        items, total = await self.repository.list_transactions(params, filters)
        total_pages = (total + params.pageSize - 1) // params.pageSize
        return PaginatedResponse(
            items=items,
            total=total,
            page=params.page,
            pageSize=params.pageSize,
            totalPages=total_pages
        )

    async def get_transaction_detail(self, txid: str) -> Optional[Transaction]:
        return await self.repository.get_by_txid(txid)

    async def get_graph_data(self, min_value: float = 0, time_range: Optional[Tuple[datetime, datetime]] = None, limit: int = 1000):
        start_time = time_range[0] if time_range else None
        end_time = time_range[1] if time_range else None
        return await self.repository.get_transaction_graph(min_value, start_time, end_time, limit)
