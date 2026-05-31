__all__ = ["RedisCache", "get_cache", "cache_key"]


def __getattr__(name):
    from . import redis_cache
    if hasattr(redis_cache, name):
        return getattr(redis_cache, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
