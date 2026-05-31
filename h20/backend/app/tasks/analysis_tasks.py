import asyncio
from typing import Dict, Any, Optional, List
from celery import shared_task

from app.tasks.base_task import update_progress, handle_task_error, add_task_log
from app.core.database import async_session_factory
from app.repositories import (
    TaskRepository,
    ClusterRepository,
    TransactionRepository,
    PatternRepository,
    AddressRepository,
    GraphRepository,
)
from app.services import (
    TaskService,
    ClusteringService,
    PatternService,
    GraphService,
    AddressService,
)


@shared_task(bind=True, name="run_clustering_task")
def run_clustering_task(
    self,
    heuristic_type: str = "multi_input",
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    task_id = self.request.id
    params = params or {}

    async def _process():
        try:
            update_progress(task_id, 5, f"Initializing {heuristic_type} clustering...")
            await add_task_log(task_id, "info", f"Starting clustering task with heuristic: {heuristic_type}")
            await add_task_log(task_id, "info", f"Parameters: {params}")

            async with async_session_factory() as db:
                task_repo = TaskRepository(db)
                task_service = TaskService(task_repo)
                cluster_repo = ClusterRepository(db)
                tx_repo = TransactionRepository(db)
                clustering_service = ClusteringService(cluster_repo, tx_repo)

                update_progress(task_id, 20, "Running clustering algorithm...")
                await add_task_log(task_id, "info", "Executing clustering analysis...")

                result = await clustering_service.run_clustering(
                    heuristic_type=heuristic_type,
                    params=params,
                )

                update_progress(task_id, 80, "Processing clustering results...")
                await add_task_log(
                    task_id,
                    "info",
                    f"Clustering completed: {result.clusterCount} clusters, {result.addressCount} addresses",
                )

                update_progress(task_id, 100, "Clustering task completed")
                await task_service.complete_task(
                    task_id,
                    result={
                        "clusterCount": result.clusterCount,
                        "addressCount": result.addressCount,
                        "algorithm": result.algorithm,
                        "clusters": [c.model_dump() for c in result.clusters],
                    },
                )

                return {
                    "clusterCount": result.clusterCount,
                    "addressCount": result.addressCount,
                    "algorithm": result.algorithm,
                }

        except Exception as e:
            handle_task_error(task_id, e)
            raise

    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(_process())
    return loop.run_until_complete(_process())


@shared_task(bind=True, name="detect_patterns_task")
def detect_patterns_task(
    self,
    address: Optional[str] = None,
    pattern_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    task_id = self.request.id

    async def _process():
        try:
            update_progress(task_id, 5, "Initializing pattern detection...")
            await add_task_log(task_id, "info", "Starting pattern detection task")
            if address:
                await add_task_log(task_id, "info", f"Target address: {address}")
            if pattern_types:
                await add_task_log(task_id, "info", f"Pattern types: {pattern_types}")

            async with async_session_factory() as db:
                task_repo = TaskRepository(db)
                task_service = TaskService(task_repo)
                pattern_repo = PatternRepository(db)
                addr_repo = AddressRepository(db)
                pattern_service = PatternService(pattern_repo, addr_repo)

                update_progress(task_id, 20, "Detecting patterns...")
                await add_task_log(task_id, "info", "Executing pattern detection...")

                result = await pattern_service.detect_patterns_batch(
                    address=address,
                    pattern_types=pattern_types,
                )

                update_progress(task_id, 80, "Processing detection results...")
                await add_task_log(
                    task_id,
                    "info",
                    f"Pattern detection completed: {result['processed']} processed, {result['detected']} patterns detected",
                )

                update_progress(task_id, 100, "Pattern detection completed")
                await task_service.complete_task(task_id, result=result)

                return result

        except Exception as e:
            handle_task_error(task_id, e)
            raise

    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(_process())
    return loop.run_until_complete(_process())


@shared_task(bind=True, name="build_graph_task")
def build_graph_task(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    task_id = self.request.id
    params = params or {}

    async def _process():
        try:
            update_progress(task_id, 5, "Initializing graph building...")
            await add_task_log(task_id, "info", "Starting graph building task")
            await add_task_log(task_id, "info", f"Parameters: {params}")

            async with async_session_factory() as db:
                task_repo = TaskRepository(db)
                task_service = TaskService(task_repo)
                graph_repo = GraphRepository(db)
                graph_service = GraphService(graph_repo)

                update_progress(task_id, 30, "Querying transaction data...")
                await add_task_log(task_id, "info", "Fetching transaction data for graph...")

                result = await graph_service.build_graph_from_params(params)

                update_progress(task_id, 80, "Building graph structure...")
                await add_task_log(
                    task_id,
                    "info",
                    f"Graph built: {result.statistics['nodeCount']} nodes, {result.statistics['edgeCount']} edges",
                )

                update_progress(task_id, 100, "Graph building completed")
                await task_service.complete_task(
                    task_id,
                    result={
                        "nodeCount": result.statistics["nodeCount"],
                        "edgeCount": result.statistics["edgeCount"],
                        "transactionCount": result.statistics.get("transactionCount", 0),
                        "addressCount": result.statistics.get("addressCount", 0),
                    },
                )

                return {
                    "nodeCount": result.statistics["nodeCount"],
                    "edgeCount": result.statistics["edgeCount"],
                }

        except Exception as e:
            handle_task_error(task_id, e)
            raise

    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(_process())
    return loop.run_until_complete(_process())


@shared_task(bind=True, name="calculate_suspicious_scores_task")
def calculate_suspicious_scores_task(
    self,
    addresses: Optional[List[str]] = None,
) -> Dict[str, Any]:
    task_id = self.request.id

    async def _process():
        try:
            update_progress(task_id, 5, "Initializing suspicious score calculation...")
            await add_task_log(task_id, "info", "Starting suspicious score calculation task")
            if addresses:
                await add_task_log(task_id, "info", f"Target addresses count: {len(addresses)}")

            async with async_session_factory() as db:
                task_repo = TaskRepository(db)
                task_service = TaskService(task_repo)
                addr_repo = AddressRepository(db)
                tx_repo = TransactionRepository(db)
                address_service = AddressService(addr_repo, tx_repo)

                update_progress(task_id, 20, "Calculating scores...")
                await add_task_log(task_id, "info", "Computing suspicious scores...")

                result = await address_service.calculate_suspicious_scores(
                    addresses=addresses,
                )

                update_progress(task_id, 80, "Updating address records...")
                await add_task_log(
                    task_id,
                    "info",
                    f"Score calculation completed: {result['processed']} processed, {result['updated']} updated",
                )

                if result["failed"] > 0:
                    await add_task_log(
                        task_id,
                        "warning",
                        f"Failed to update {result['failed']} addresses",
                    )

                update_progress(task_id, 100, "Suspicious score calculation completed")
                await task_service.complete_task(task_id, result=result)

                return result

        except Exception as e:
            handle_task_error(task_id, e)
            raise

    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(_process())
    return loop.run_until_complete(_process())
