from typing import Optional, Dict, Any, List, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from collections import defaultdict

from app.services.base import BaseService
from app.repositories import ClusterRepository, TransactionRepository
from app.models.analysis import AddressCluster
from app.models.blockchain import Transaction, TxInput, TxOutput
from app.schemas.common import PaginationParams, PaginatedResponse


class ClusteringService(BaseService[ClusterRepository]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, ClusterRepository)
        self.tx_repo = TransactionRepository(db)

    async def run_common_input_clustering(self, transactions: List[Transaction]) -> Dict[str, Any]:
        address_to_cluster: Dict[str, str] = {}
        cluster_to_addresses: Dict[str, Set[str]] = defaultdict(set)

        for tx in transactions:
            if tx.is_coinbase or len(tx.inputs) <= 1:
                continue

            input_addresses = [inp.address for inp in tx.inputs if inp.address]
            if not input_addresses:
                continue

            existing_clusters = set()
            for addr in input_addresses:
                if addr in address_to_cluster:
                    existing_clusters.add(address_to_cluster[addr])

            if existing_clusters:
                merged_cluster = min(existing_clusters)
                for cluster_id in existing_clusters:
                    for addr in cluster_to_addresses[cluster_id]:
                        address_to_cluster[addr] = merged_cluster
                        cluster_to_addresses[merged_cluster].add(addr)
                    if cluster_id != merged_cluster:
                        del cluster_to_addresses[cluster_id]

                for addr in input_addresses:
                    address_to_cluster[addr] = merged_cluster
                    cluster_to_addresses[merged_cluster].add(addr)
            else:
                new_cluster = str(uuid.uuid4())
                for addr in input_addresses:
                    address_to_cluster[addr] = new_cluster
                    cluster_to_addresses[new_cluster].add(addr)

        clusters_created = 0
        for cluster_id, addresses in cluster_to_addresses.items():
            if len(addresses) >= 2:
                total_value = 0.0
                for addr in addresses:
                    addr_stats = await self._get_address_value(addr)
                    total_value += addr_stats

                cluster = await self.repository.create_cluster({
                    "cluster_id": cluster_id,
                    "heuristic": "common_input",
                    "confidence": 0.85,
                    "size": len(addresses),
                    "total_value": total_value
                })

                await self.repository.bulk_create_members(cluster_id, list(addresses))
                clusters_created += 1

        return {
            "heuristic": "common_input",
            "clusters_created": clusters_created,
            "total_addresses_clustered": len(address_to_cluster)
        }

    async def run_change_address_clustering(self, transactions: List[Transaction]) -> Dict[str, Any]:
        address_to_cluster: Dict[str, str] = {}
        cluster_to_addresses: Dict[str, Set[str]] = defaultdict(set)
        address_usage_count: Dict[str, int] = defaultdict(int)
        change_address_clusters: Dict[str, Set[str]] = defaultdict(set)

        for tx in transactions:
            if tx.is_coinbase or len(tx.inputs) == 0 or len(tx.outputs) != 2:
                continue

            input_addresses = {inp.address for inp in tx.inputs if inp.address}
            output_addresses = [out.address for out in tx.outputs if out.address]

            if len(output_addresses) != 2:
                continue

            change_candidate = None
            change_value = 0.0
            payment_value = 0.0
            for out in tx.outputs:
                if out.address and out.address not in input_addresses:
                    change_candidate = out.address
                    change_value = out.value
                else:
                    payment_value = out.value if out.value else 0.0

            if change_candidate and input_addresses:
                address_usage_count[change_candidate] += 1

                if change_candidate in address_to_cluster:
                    change_cluster = address_to_cluster[change_candidate]
                    change_address_clusters[change_candidate].add(change_cluster)

                if address_usage_count[change_candidate] > 3:
                    continue

                if change_value > payment_value and payment_value > 0:
                    continue

                input_cluster = None
                for addr in input_addresses:
                    if addr in address_to_cluster:
                        input_cluster = address_to_cluster[addr]
                        break

                if change_candidate in address_to_cluster:
                    change_cluster = address_to_cluster[change_candidate]
                    if input_cluster and input_cluster != change_cluster:
                        change_inputs = {
                            inp.address for tx2 in transactions
                            for inp in tx2.inputs
                            if inp.address and any(
                                out.address == change_candidate for out in tx2.outputs
                            )
                        }
                        if not change_inputs & input_addresses:
                            continue

                if input_cluster:
                    address_to_cluster[change_candidate] = input_cluster
                    cluster_to_addresses[input_cluster].add(change_candidate)
                    for addr in input_addresses:
                        address_to_cluster[addr] = input_cluster
                        cluster_to_addresses[input_cluster].add(addr)
                else:
                    new_cluster = str(uuid.uuid4())
                    for addr in input_addresses:
                        address_to_cluster[addr] = new_cluster
                        cluster_to_addresses[new_cluster].add(addr)
                    address_to_cluster[change_candidate] = new_cluster
                    cluster_to_addresses[new_cluster].add(change_candidate)

        clusters_created = 0
        for cluster_id, addresses in cluster_to_addresses.items():
            if len(addresses) >= 2:
                total_value = 0.0
                for addr in addresses:
                    addr_stats = await self._get_address_value(addr)
                    total_value += addr_stats

                cluster = await self.repository.create_cluster({
                    "cluster_id": cluster_id,
                    "heuristic": "change_address",
                    "confidence": 0.7,
                    "size": len(addresses),
                    "total_value": total_value
                })

                await self.repository.bulk_create_members(cluster_id, list(addresses))
                clusters_created += 1

        return {
            "heuristic": "change_address",
            "clusters_created": clusters_created,
            "total_addresses_clustered": len(address_to_cluster)
        }

    async def run_combined_clustering(self) -> Dict[str, Any]:
        params = PaginationParams(page=1, pageSize=10000)
        all_transactions = []

        while True:
            transactions, total = await self.tx_repo.list_transactions(params)
            all_transactions.extend(transactions)
            if len(all_transactions) >= total:
                break
            params.page += 1

        ci_result = await self.run_common_input_clustering(all_transactions)
        ca_result = await self.run_change_address_clustering(all_transactions)

        return {
            "common_input": ci_result,
            "change_address": ca_result,
            "total_transactions_processed": len(all_transactions)
        }

    async def get_clustering_results(self, params: PaginationParams) -> PaginatedResponse[AddressCluster]:
        items, total = await self.repository.list_clusters(params)
        total_pages = (total + params.pageSize - 1) // params.pageSize
        return PaginatedResponse(
            items=items,
            total=total,
            page=params.page,
            pageSize=params.pageSize,
            totalPages=total_pages
        )

    async def _get_address_value(self, address: str) -> float:
        stmt = """
            SELECT COALESCE(SUM(value), 0) as total_value
            FROM tx_outputs
            WHERE address = :address
        """
        from sqlalchemy import text
        result = await self.db.execute(text(stmt), {"address": address})
        row = result.fetchone()
        return float(row[0]) if row else 0.0
