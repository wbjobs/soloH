import json
import hashlib
from typing import Optional, Any, List, Dict
from redis import Redis
from redis.exceptions import RedisError
from app.config import get_settings
from app.offtarget_search.offtarget_finder import OffTargetSite


def cache_key(sgrna: str, **kwargs) -> str:
    sgrna_clean = sgrna.upper().strip()
    key_parts = [f"sgrna={sgrna_clean}"]
    for k, v in sorted(kwargs.items()):
        if v is not None:
            if isinstance(v, list):
                v_str = ",".join(sorted(str(x) for x in v))
            else:
                v_str = str(v)
            key_parts.append(f"{k}={v_str}")

    key_string = "|".join(key_parts)
    md5_digest = hashlib.md5(key_string.encode()).hexdigest()
    sha1_digest = hashlib.sha1(key_string.encode()).hexdigest()[:16]
    return f"crispr:offtarget:{md5_digest}:{sha1_digest}"


class RedisCache:
    _instance: Optional["RedisCache"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        settings = get_settings()
        self.host = settings.REDIS_HOST
        self.port = settings.REDIS_PORT
        self.db = settings.REDIS_DB
        self.password = settings.REDIS_PASSWORD
        self.default_ttl = settings.REDIS_CACHE_TTL
        self._client: Optional[Redis] = None
        self._initialized = True
        self._enabled = True

    def _connect(self) -> bool:
        if self._client is not None:
            return True

        try:
            self._client = Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            self._client.ping()
            return True
        except RedisError as e:
            print(f"Warning: Could not connect to Redis: {e}")
            self._client = None
            self._enabled = False
            return False

    def get(self, key: str) -> Optional[Any]:
        if not self._enabled or not self._connect():
            return None

        try:
            value = self._client.get(key)
            if value is not None:
                return json.loads(value)
        except RedisError as e:
            print(f"Warning: Redis get error: {e}")

        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not self._enabled or not self._connect():
            return False

        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value, default=str)
            self._client.setex(key, ttl, serialized)
            return True
        except (RedisError, TypeError) as e:
            print(f"Warning: Redis set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        if not self._enabled or not self._connect():
            return False

        try:
            self._client.delete(key)
            return True
        except RedisError as e:
            print(f"Warning: Redis delete error: {e}")
            return False

    def exists(self, key: str) -> bool:
        if not self._enabled or not self._connect():
            return False

        try:
            return bool(self._client.exists(key))
        except RedisError as e:
            print(f"Warning: Redis exists error: {e}")
            return False

    def cache_offtarget_results(
        self,
        sgrna: str,
        results: List[OffTargetSite],
        params: Optional[Dict] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        key = cache_key(sgrna, **(params or {}))
        results_dict = [r.to_dict() for r in results]
        cache_data = {
            "sgrna": sgrna,
            "params": params,
            "results": results_dict,
            "count": len(results_dict),
        }
        return self.set(key, cache_data, ttl)

    def get_offtarget_results(
        self, sgrna: str, params: Optional[Dict] = None
    ) -> Optional[List[Dict]]:
        sgrna_clean = sgrna.upper().strip()
        key = cache_key(sgrna, **(params or {}))
        cached = self.get(key)
        if cached and isinstance(cached, dict):
            cached_sgrna = cached.get("sgrna", "")
            cached_sgrna_clean = cached_sgrna.upper().strip()
            if cached_sgrna_clean == sgrna_clean:
                return cached.get("results")
            else:
                print(
                    f"Warning: Cache key collision detected! "
                    f"Expected sgrna: {sgrna_clean}, "
                    f"Found sgrna in cache: {cached_sgrna_clean}. "
                    f"Deleting invalid cache entry."
                )
                self.delete(key)
        return None

    def clear_pattern(self, pattern: str = "crispr:offtarget:*") -> int:
        if not self._enabled or not self._connect():
            return 0

        try:
            keys = list(self._client.scan_iter(match=pattern))
            if keys:
                return self._client.delete(*keys)
            return 0
        except RedisError as e:
            print(f"Warning: Redis clear error: {e}")
            return 0

    def get_stats(self) -> Dict:
        if not self._enabled or not self._connect():
            return {"enabled": False}

        try:
            info = self._client.info()
            return {
                "enabled": True,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }
        except RedisError as e:
            return {"enabled": False, "error": str(e)}

    def batch_get(self, keys: List[str]) -> Dict[str, Any]:
        if not self._enabled or not self._connect():
            return {}

        try:
            values = self._client.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = json.loads(value)
            return result
        except RedisError as e:
            print(f"Warning: Redis batch get error: {e}")
            return {}

    def batch_set(self, items: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        if not self._enabled or not self._connect():
            return False

        try:
            ttl = ttl or self.default_ttl
            pipe = self._client.pipeline()
            for key, value in items.items():
                serialized = json.dumps(value, default=str)
                pipe.setex(key, ttl, serialized)
            pipe.execute()
            return True
        except (RedisError, TypeError) as e:
            print(f"Warning: Redis batch set error: {e}")
            return False


def get_cache() -> RedisCache:
    return RedisCache()
