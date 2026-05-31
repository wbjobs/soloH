import asyncio
from typing import Dict, Any, List
from celery import shared_task

from app.tasks.base_task import update_progress, handle_task_error, add_task_log
from app.core.database import async_session_factory
from app.repositories import TaskRepository, TransactionRepository
from app.services import TaskService, TransactionService


@shared_task(bind=True, name="import_csv_task")
def import_csv_task(self, file_content: bytes, params: Dict[str, Any]) -> Dict[str, Any]:
    task_id = self.request.id

    async def _process():
        try:
            update_progress(task_id, 5, "Initializing CSV import...")
            await add_task_log(task_id, "info", "Starting CSV import task")

            async with async_session_factory() as db:
                task_repo = TaskRepository(db)
                task_service = TaskService(task_repo)
                tx_repo = TransactionRepository(db)
                tx_service = TransactionService(tx_repo)

                update_progress(task_id, 10, "Parsing CSV file...")
                await add_task_log(task_id, "info", f"Parsing CSV with params: {params}")

                result = await tx_service.import_csv(file_content, params)

                update_progress(task_id, 90, f"Imported {result['imported']} records...")
                await add_task_log(task_id, "info", f"Imported {result['imported']} records successfully")

                if result["errors"]:
                    await add_task_log(
                        task_id,
                        "warning",
                        f"Encountered {len(result['errors'])} errors during import",
                        {"errors": result["errors"][:10]},
                    )

                update_progress(task_id, 100, "CSV import completed")
                await task_service.complete_task(task_id, result=result)

                return result

        except Exception as e:
            handle_task_error(task_id, e)
            raise

    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(_process())
    return loop.run_until_complete(_process())


@shared_task(bind=True, name="import_api_task")
def import_api_task(
    self,
    block_start: int = None,
    block_end: int = None,
    api_source: str = "blockstream",
    params: Dict[str, Any] = None,
) -> Dict[str, Any]:
    task_id = self.request.id
    params = params or {}

    async def _process():
        try:
            update_progress(task_id, 5, f"Initializing API import from {api_source}...")
            await add_task_log(task_id, "info", f"Starting API import task from {api_source}")
            await add_task_log(task_id, "info", f"Block range: {block_start} - {block_end}")

            async with async_session_factory() as db:
                task_repo = TaskRepository(db)
                task_service = TaskService(task_repo)
                tx_repo = TransactionRepository(db)
                tx_service = TransactionService(tx_repo)

                update_progress(task_id, 10, "Fetching data from API...")

                api_params = {
                    **params,
                    "startBlock": block_start,
                    "endBlock": block_end,
                    "source": api_source,
                }

                result = await tx_service.import_from_api(api_params)

                update_progress(task_id, 90, f"Imported {result['imported']} records from API...")
                await add_task_log(task_id, "info", f"Successfully imported {result['imported']} transactions from {api_source}")

                if result["errors"]:
                    await add_task_log(
                        task_id,
                        "warning",
                        f"Encountered {len(result['errors'])} errors during API import",
                        {"errors": result["errors"][:10]},
                    )

                update_progress(task_id, 100, "API import completed")
                await task_service.complete_task(task_id, result=result)

                return result

        except Exception as e:
            handle_task_error(task_id, e)
            raise

    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(_process())
    return loop.run_until_complete(_process())


@shared_task(bind=True, name="process_transaction_batch")
def process_transaction_batch(self, batch_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    task_id = self.request.id

    async def _process():
        try:
            update_progress(task_id, 10, f"Processing batch of {len(batch_data)} transactions...")
            await add_task_log(task_id, "info", f"Starting batch processing of {len(batch_data)} transactions")

            async with async_session_factory() as db:
                task_repo = TaskRepository(db)
                task_service = TaskService(task_repo)
                tx_repo = TransactionRepository(db)
                tx_service = TransactionService(tx_repo)

                total = len(batch_data)
                processed = 0
                batch_size = 100

                for i in range(0, total, batch_size):
                    batch = batch_data[i : i + batch_size]
                    partial_result = await tx_service.process_batch(batch)
                    processed += len(batch)

                    progress = 10 + int(80 * processed / total)
                    update_progress(task_id, progress, f"Processed {processed}/{total} transactions...")
                    await add_task_log(
                        task_id,
                        "info",
                        f"Processed batch {i // batch_size + 1}: {partial_result['imported']} imported",
                    )

                result = {
                    "total": total,
                    "processed": processed,
                    "batch_count": (total + batch_size - 1) // batch_size,
                }

                update_progress(task_id, 100, "Batch processing completed")
                await task_service.complete_task(task_id, result=result)

                return result

        except Exception as e:
            handle_task_error(task_id, e)
            raise

    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(_process())
    return loop.run_until_complete(_process())
