import pandas as pd
import numpy as np
import xarray as xr
from pathlib import Path
from typing import Any, Optional, Dict, Union
import hashlib
import json
import time
from datetime import datetime, timedelta

from app.core.config import settings


def _get_cache_dir() -> Path:
    cache_dir = Path(settings.CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_cache_path(key: str) -> Path:
    hashed_key = hashlib.md5(key.encode()).hexdigest()
    cache_dir = _get_cache_dir()
    return cache_dir / f"{hashed_key}.parquet"


def _get_metadata_path(key: str) -> Path:
    hashed_key = hashlib.md5(key.encode()).hexdigest()
    cache_dir = _get_cache_dir()
    return cache_dir / f"{hashed_key}_metadata.json"


def _save_metadata(key: str, metadata: Dict[str, Any]) -> None:
    metadata_path = _get_metadata_path(key)
    metadata['_created_at'] = datetime.now().isoformat()
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, default=str)


def _load_metadata(key: str) -> Optional[Dict[str, Any]]:
    metadata_path = _get_metadata_path(key)
    if not metadata_path.exists():
        return None
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def _is_cache_valid(key: str) -> bool:
    if not settings.ENABLE_CACHE:
        return False

    metadata = _load_metadata(key)
    if metadata is None:
        return False

    cache_path = _get_cache_path(key)
    if not cache_path.exists():
        return False

    created_at = metadata.get('_created_at')
    if created_at:
        try:
            created_time = datetime.fromisoformat(created_at)
            if datetime.now() - created_time > timedelta(hours=settings.CACHE_TTL_HOURS):
                return False
        except Exception:
            pass

    return True


def dataset_to_dataframe(ds: xr.Dataset) -> pd.DataFrame:
    df = ds.to_dataframe().reset_index()
    return df


def dataframe_to_dataset(df: pd.DataFrame, attrs: Optional[Dict[str, Any]] = None) -> xr.Dataset:
    ds = df.set_index(['lat', 'lon']).to_xarray()
    if attrs:
        ds.attrs.update(attrs)
    return ds


def set_cache(key: str, data: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
    if not settings.ENABLE_CACHE:
        return

    cache_path = _get_cache_path(key)
    metadata = metadata or {}

    try:
        if isinstance(data, xr.Dataset):
            df = dataset_to_dataframe(data)
            df.to_parquet(cache_path, engine='pyarrow', compression='snappy')
            metadata['_type'] = 'xarray.Dataset'
            metadata['_attrs'] = json.dumps(dict(data.attrs), default=str)
        elif isinstance(data, pd.DataFrame):
            data.to_parquet(cache_path, engine='pyarrow', compression='snappy')
            metadata['_type'] = 'pandas.DataFrame'
        elif isinstance(data, np.ndarray):
            df = pd.DataFrame(data)
            df.to_parquet(cache_path, engine='pyarrow', compression='snappy')
            metadata['_type'] = 'numpy.ndarray'
        else:
            metadata['_type'] = 'json'
            metadata['_data'] = json.dumps(data, default=str)

        _save_metadata(key, metadata)

    except Exception as e:
        print(f"Warning: Failed to save cache for key {key}: {e}")
        if cache_path.exists():
            try:
                cache_path.unlink()
            except Exception:
                pass


def get_cache(key: str) -> Optional[Any]:
    if not _is_cache_valid(key):
        return None

    cache_path = _get_cache_path(key)
    metadata = _load_metadata(key)

    try:
        data_type = metadata.get('_type', 'json')

        if data_type == 'xarray.Dataset':
            df = pd.read_parquet(cache_path, engine='pyarrow')
            attrs_str = metadata.get('_attrs', '{}')
            try:
                attrs = json.loads(attrs_str)
            except Exception:
                attrs = {}
            return dataframe_to_dataset(df, attrs)
        elif data_type == 'pandas.DataFrame':
            return pd.read_parquet(cache_path, engine='pyarrow')
        elif data_type == 'numpy.ndarray':
            df = pd.read_parquet(cache_path, engine='pyarrow')
            return df.values
        else:
            data_str = metadata.get('_data')
            if data_str:
                return json.loads(data_str)
            return None

    except Exception as e:
        print(f"Warning: Failed to load cache for key {key}: {e}")
        return None


def clear_cache(key: Optional[str] = None) -> int:
    cache_dir = _get_cache_dir()

    if key:
        cache_path = _get_cache_path(key)
        metadata_path = _get_metadata_path(key)
        count = 0
        if cache_path.exists():
            cache_path.unlink()
            count += 1
        if metadata_path.exists():
            metadata_path.unlink()
            count += 1
        return count

    count = 0
    for f in cache_dir.glob('*.parquet'):
        f.unlink()
        count += 1
    for f in cache_dir.glob('*_metadata.json'):
        f.unlink()
        count += 1
    return count


def get_cache_info() -> Dict[str, Any]:
    cache_dir = _get_cache_dir()
    parquet_files = list(cache_dir.glob('*.parquet'))
    metadata_files = list(cache_dir.glob('*_metadata.json'))

    total_size = 0
    for f in parquet_files:
        total_size += f.stat().st_size

    return {
        'cache_dir': str(cache_dir),
        'enabled': settings.ENABLE_CACHE,
        'ttl_hours': settings.CACHE_TTL_HOURS,
        'num_cache_entries': len(parquet_files),
        'total_size_bytes': total_size,
        'total_size_mb': total_size / (1024 * 1024),
    }


def list_cache_keys() -> list:
    cache_dir = _get_cache_dir()
    metadata_files = list(cache_dir.glob('*_metadata.json'))

    keys = []
    for f in metadata_files:
        try:
            with open(f, 'r') as fp:
                meta = json.load(fp)
                data_type = meta.get('_type', 'unknown')
                created_at = meta.get('_created_at', 'unknown')
                keys.append({
                    'file': f.name,
                    'type': data_type,
                    'created_at': created_at,
                })
        except Exception:
            pass

    return keys
