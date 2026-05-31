import dask
from dask.distributed import Client, LocalCluster
from contextlib import contextmanager
from typing import Optional, Generator, Callable, Iterable, Any
from app.core.config import settings


_cluster: Optional[LocalCluster] = None
_client: Optional[Client] = None


def get_client() -> Optional[Client]:
    global _client, _cluster

    if _client is not None and not _client.status == "closed":
        return _client

    if settings.DASK_SCHEDULER == "distributed":
        if _cluster is None:
            _cluster = LocalCluster(
                n_workers=settings.DASK_WORKERS,
                threads_per_worker=2,
                memory_limit=settings.DASK_MEMORY_LIMIT,
                processes=True,
            )
        _client = Client(_cluster)
        return _client

    dask.config.set(scheduler=settings.DASK_SCHEDULER)
    return None


def close_client() -> None:
    global _client, _cluster
    if _client is not None:
        _client.close()
        _client = None
    if _cluster is not None:
        _cluster.close()
        _cluster = None


@contextmanager
def dask_client_context() -> Generator[Optional[Client], None, None]:
    client = get_client()
    try:
        yield client
    finally:
        pass


def parallel_map(func: Callable, iterable: Iterable, **kwargs) -> list:
    client = get_client()

    if client is not None:
        futures = client.map(func, iterable, **kwargs)
        return client.gather(futures)
    else:
        from dask import delayed
        import dask.bag as db

        bag = db.from_sequence(iterable, npartitions=settings.DASK_WORKERS * 4)
        results = bag.map(func, **kwargs).compute()
        return list(results)
