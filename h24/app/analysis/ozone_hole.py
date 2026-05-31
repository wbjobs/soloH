import numpy as np
import xarray as xr
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import pandas as pd

from app.core.config import settings
from app.core.utils import sanitize_for_json
from app.cache.parquet_cache import get_cache, set_cache


def area_weighted_mean(
    data: xr.DataArray,
    area: xr.DataArray,
    mask: Optional[xr.DataArray] = None,
    dims: list = ['lat', 'lon'],
) -> xr.DataArray:
    if mask is not None:
        data = data.where(mask)
        area = area.where(mask)

    weighted_data = data * area
    total_weighted = weighted_data.sum(dim=dims)
    total_area = area.sum(dim=dims)

    return xr.where(total_area > 0, total_weighted / total_area, np.nan)


def detect_ozone_hole(
    ds: xr.Dataset,
    variable: str = 'ozone',
    threshold: Optional[float] = None,
    lat_range: Optional[Tuple[float, float]] = None,
) -> xr.Dataset:
    threshold = threshold or settings.OZONE_HOLE_THRESHOLD
    lat_range = lat_range or (-90, -50)

    data = ds[variable]
    antarctic_data = data.sel(lat=slice(lat_range[0], lat_range[1]))

    hole_mask = antarctic_data < threshold
    hole_mask = hole_mask.where(~np.isnan(antarctic_data))

    area_per_grid = calculate_grid_area(antarctic_data['lat'].values, antarctic_data['lon'].values)
    area_da = xr.DataArray(
        area_per_grid,
        dims=['lat', 'lon'],
        coords={'lat': antarctic_data['lat'].values, 'lon': antarctic_data['lon'].values}
    )

    hole_area_m2 = (hole_mask * area_da).sum(dim=['lat', 'lon'])
    hole_area = hole_area_m2 / 1e6

    mean_hole_ozone = area_weighted_mean(
        antarctic_data,
        area_da,
        mask=hole_mask,
        dims=['lat', 'lon']
    )

    min_hole_ozone = antarctic_data.where(hole_mask).min(dim=['lat', 'lon'])

    hole_grid_count = hole_mask.sum(dim=['lat', 'lon'])

    result_ds = xr.Dataset(
        {
            'hole_mask': hole_mask,
            'hole_area': hole_area,
            'mean_hole_ozone': mean_hole_ozone,
            'min_hole_ozone': min_hole_ozone,
            'hole_grid_count': hole_grid_count,
        },
        attrs={
            'threshold': threshold,
            'lat_range': lat_range,
            'unit_area': 'km²',
            'unit_ozone': 'DU',
        },
    )

    return result_ds


def calculate_grid_area(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    R_EARTH = 6371.0088

    n_lat = len(lats)
    n_lon = len(lons)

    lat_res = lats[1] - lats[0] if n_lat > 1 else 1.0
    lon_res = lons[1] - lons[0] if n_lon > 1 else 1.0

    lon_mesh, lat_mesh = np.meshgrid(lons, lats)

    lat_min_rad = np.radians(lat_mesh - lat_res / 2)
    lat_max_rad = np.radians(lat_mesh + lat_res / 2)
    lon_min_rad = np.radians(lon_mesh - lon_res / 2)
    lon_max_rad = np.radians(lon_mesh + lon_res / 2)

    sin_lat_diff = np.sin(lat_max_rad) - np.sin(lat_min_rad)
    lon_diff = lon_max_rad - lon_min_rad

    area_km2 = (R_EARTH ** 2) * np.abs(sin_lat_diff) * np.abs(lon_diff)

    area_m2 = area_km2 * 1e6

    return area_m2


def get_hole_area_timeseries(
    ds: xr.Dataset,
    variable: str = 'ozone',
    threshold: Optional[float] = None,
    lat_range: Optional[Tuple[float, float]] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    threshold = threshold or settings.OZONE_HOLE_THRESHOLD
    lat_range = lat_range or (-90, -50)

    cache_key = f"hole_ts_{variable}_{threshold}_{lat_range[0]}_{lat_range[1]}_{ds['time'].values[0]}_{ds['time'].values[-1]}"
    cache_key = cache_key.replace(':', '_').replace('-', '_').replace('.', '_')

    if use_cache:
        cached = get_cache(cache_key)
        if cached is not None:
            return cached

    hole_ds = detect_ozone_hole(ds, variable, threshold, lat_range)

    times = pd.to_datetime(ds['time'].values)
    areas = hole_ds['hole_area'].values
    mean_ozone = hole_ds['mean_hole_ozone'].values
    min_ozone = hole_ds['min_hole_ozone'].values
    grid_counts = hole_ds['hole_grid_count'].values

    annual_max_idx = []
    annual_means = []
    years = np.unique(times.year)

    for year in years:
        mask = times.year == year
        if np.any(mask):
            year_idx = np.where(mask)[0]
            max_idx = year_idx[np.nanargmax(areas[mask])]
            annual_max_idx.append(int(max_idx))
            annual_means.append(float(np.nanmean(areas[mask])))

    result = {
        'time': [str(t) for t in times],
        'hole_area_km2': areas.tolist(),
        'mean_hole_ozone_du': mean_ozone.tolist(),
        'min_hole_ozone_du': min_ozone.tolist(),
        'hole_grid_count': grid_counts.tolist(),
        'threshold': threshold,
        'lat_range': lat_range,
        'annual_max_area_km2': [float(areas[i]) for i in annual_max_idx],
        'annual_max_time': [str(times[i]) for i in annual_max_idx],
        'annual_mean_area_km2': annual_means,
        'years': years.tolist(),
        'unit_area': 'km²',
        'unit_ozone': 'DU',
        'stats': {
            'max_area_km2': float(np.nanmax(areas)),
            'mean_area_km2': float(np.nanmean(areas)),
            'min_area_km2': float(np.nanmin(areas)),
            'max_year': int(years[np.nanargmax([areas[i] for i in annual_max_idx])]) if annual_max_idx else None,
        },
    }

    if use_cache:
        set_cache(cache_key, result)

    return sanitize_for_json(result)


def hole_mask_to_geojson(
    ds: xr.Dataset,
    variable: str = 'ozone',
    time_idx: Optional[int] = None,
    threshold: Optional[float] = None,
    lat_range: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    threshold = threshold or settings.OZONE_HOLE_THRESHOLD
    lat_range = lat_range or (-90, -50)

    hole_ds = detect_ozone_hole(ds, variable, threshold, lat_range)

    if time_idx is None:
        time_idx = -1

    mask = hole_ds['hole_mask'][time_idx].values
    ozone_values = ds[variable].sel(lat=slice(lat_range[0], lat_range[1]))[time_idx].values

    lats = hole_ds['lat'].values
    lons = hole_ds['lon'].values
    resolution = (lats[1] - lats[0]) / 2 if len(lats) > 1 else 0.5

    features = []

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            is_hole = bool(mask[i, j]) if not np.isnan(mask[i, j]) else False
            ozone_val = float(ozone_values[i, j]) if not np.isnan(ozone_values[i, j]) else None

            if ozone_val is None:
                continue

            coords = [
                [lon - resolution, lat - resolution],
                [lon + resolution, lat - resolution],
                [lon + resolution, lat + resolution],
                [lon - resolution, lat + resolution],
                [lon - resolution, lat - resolution],
            ]

            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [coords],
                },
                'properties': {
                    'lat': float(lat),
                    'lon': float(lon),
                    'ozone_du': ozone_val,
                    'is_hole': is_hole,
                    'below_threshold': ozone_val < threshold,
                },
            }
            features.append(feature)

    result = {
        'type': 'FeatureCollection',
        'features': features,
        'properties': {
            'time': str(ds['time'].values[time_idx]),
            'threshold': threshold,
            'lat_range': lat_range,
            'hole_area_km2': float(hole_ds['hole_area'][time_idx].values),
            'mean_hole_ozone_du': float(hole_ds['mean_hole_ozone'][time_idx].values),
            'min_hole_ozone_du': float(hole_ds['min_hole_ozone'][time_idx].values),
        },
    }

    return sanitize_for_json(result)


def get_hole_climatology(
    ds: xr.Dataset,
    variable: str = 'ozone',
    threshold: Optional[float] = None,
    lat_range: Optional[Tuple[float, float]] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    threshold = threshold or settings.OZONE_HOLE_THRESHOLD
    lat_range = lat_range or (-90, -50)

    cache_key = f"hole_clim_{variable}_{threshold}_{lat_range[0]}_{lat_range[1]}"
    cache_key = cache_key.replace('.', '_').replace('-', '_')

    if use_cache:
        cached = get_cache(cache_key)
        if cached is not None:
            return cached

    hole_ds = detect_ozone_hole(ds, variable, threshold, lat_range)

    times = pd.to_datetime(ds['time'].values)

    monthly_mean = hole_ds['hole_area'].groupby('time.month').mean().to_pandas()
    monthly_std = hole_ds['hole_area'].groupby('time.month').std().to_pandas()
    monthly_min = hole_ds['hole_area'].groupby('time.month').min().to_pandas()
    monthly_max = hole_ds['hole_area'].groupby('time.month').max().to_pandas()

    result = {
        'monthly_mean_area_km2': monthly_mean.to_dict(),
        'monthly_std_area_km2': monthly_std.to_dict(),
        'monthly_min_area_km2': monthly_min.to_dict(),
        'monthly_max_area_km2': monthly_max.to_dict(),
        'threshold': threshold,
        'lat_range': lat_range,
        'peak_month': int(monthly_mean.idxmax()),
        'unit': 'km²',
    }

    if use_cache:
        set_cache(cache_key, result)

    return sanitize_for_json(result)
