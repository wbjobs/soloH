import numpy as np
import xarray as xr
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import pandas as pd
from scipy import stats
from scipy.ndimage import gaussian_filter

from app.core.config import settings
from app.core.utils import sanitize_for_json
from app.analysis.ozone_hole import detect_ozone_hole, calculate_grid_area, area_weighted_mean
from app.cache.parquet_cache import get_cache, set_cache


def detect_vortex_boundary(
    ds: xr.Dataset,
    time_idx: int,
    threshold_method: str = 'gradient',
    gradient_threshold: float = 50.0,
    lat_range: Tuple[float, float] = (-90, -50),
) -> Dict[str, Any]:
    data_subset = ds.sel(lat=slice(*lat_range), time=ds['time'].values[time_idx])

    if 'geopotential_height' in ds.data_vars:
        z = data_subset['geopotential_height'].values
    elif 'ozone' in ds.data_vars:
        z = data_subset['ozone'].values
    else:
        raise ValueError("No suitable variable found for vortex detection")

    lats = data_subset['lat'].values
    lons = data_subset['lon'].values
    lat_res = lats[1] - lats[0] if len(lats) > 1 else 1.0
    lon_res = lons[1] - lons[0] if len(lons) > 1 else 1.0

    z_smooth = gaussian_filter(z, sigma=1)

    dlat, dlon = np.gradient(z_smooth, lat_res, lon_res)
    gradient_magnitude = np.sqrt(dlat ** 2 + dlon ** 2)

    if threshold_method == 'gradient':
        boundary_mask = gradient_magnitude >= gradient_threshold
    elif threshold_method == 'percentile':
        threshold = np.percentile(gradient_magnitude, 90)
        boundary_mask = gradient_magnitude >= threshold
    elif threshold_method == 'contour':
        contour_level = np.median(z_smooth) - np.std(z_smooth)
        boundary_mask = z_smooth <= contour_level
    else:
        raise ValueError(f"Unknown threshold method: {threshold_method}")

    inner_mask = np.zeros_like(z_smooth, dtype=bool)
    center_lat_idx = np.argmin(np.abs(lats + 75))
    for j in range(len(lons)):
        boundary_lat_idx = np.where(boundary_mask[:, j])[0]
        if len(boundary_lat_idx) > 0:
            northernmost_boundary = np.min(boundary_lat_idx)
            inner_mask[northernmost_boundary:, j] = True

    vortex_area_mask = inner_mask & ~boundary_mask

    grid_areas = calculate_grid_area(lats, lons)
    vortex_area = np.sum(vortex_area_mask * grid_areas) / 1e6

    if np.any(vortex_area_mask):
        mean_z_inside = np.mean(z_smooth[vortex_area_mask])
        mean_z_outside = np.mean(z_smooth[~vortex_area_mask & (lats[:, None] >= lat_range[0])])
        vortex_strength = mean_z_outside - mean_z_inside
    else:
        vortex_strength = np.nan

    boundary_latitudes = []
    for j in range(len(lons)):
        boundary_positions = np.where(boundary_mask[:, j])[0]
        if len(boundary_positions) > 0:
            boundary_latitudes.append(lats[np.min(boundary_positions)])
        else:
            boundary_latitudes.append(np.nan)

    mean_boundary_lat = np.nanmean(boundary_latitudes) if boundary_latitudes else np.nan

    return {
        'time': str(ds['time'].values[time_idx]),
        'vortex_area_km2': float(vortex_area),
        'vortex_strength_du': float(vortex_strength),
        'mean_boundary_latitude': float(mean_boundary_lat),
        'boundary_latitudes': boundary_latitudes,
        'boundary_mask': boundary_mask,
        'vortex_mask': vortex_area_mask,
        'gradient_magnitude': gradient_magnitude,
        'data_values': z_smooth,
        'lats': lats,
        'lons': lons,
    }


def compute_vortex_indices(
    ds: xr.Dataset,
    lat_range: Tuple[float, float] = (-90, -50),
    use_cache: bool = True,
) -> xr.Dataset:
    cache_key = f"vortex_indices_{lat_range[0]}_{lat_range[1]}_{ds['time'].values[0]}_{ds['time'].values[-1]}"
    cache_key = cache_key.replace(':', '_').replace('-', '_').replace('.', '_')

    if use_cache:
        cached = get_cache(cache_key)
        if cached is not None:
            return cached

    times = ds['time'].values
    n_times = len(times)

    vortex_areas = np.full(n_times, np.nan)
    vortex_strengths = np.full(n_times, np.nan)
    boundary_lats = np.full(n_times, np.nan)

    for t in range(n_times):
        try:
            result = detect_vortex_boundary(
                ds, t, lat_range=lat_range, threshold_method='contour'
            )
            vortex_areas[t] = result['vortex_area_km2']
            vortex_strengths[t] = result['vortex_strength_du']
            boundary_lats[t] = result['mean_boundary_latitude']
        except Exception as e:
            print(f"Warning: Failed to detect vortex at time {t}: {e}")

    result_ds = xr.Dataset(
        {
            'vortex_area': (['time'], vortex_areas),
            'vortex_strength': (['time'], vortex_strengths),
            'boundary_latitude': (['time'], boundary_lats),
        },
        coords={'time': times},
        attrs={
            'lat_range': lat_range,
            'detection_method': 'contour',
            'unit_area': 'km²',
            'unit_strength': 'DU',
        },
    )

    if use_cache:
        set_cache(cache_key, result_ds)

    return result_ds


def vortex_hole_correlation(
    ds: xr.Dataset,
    threshold: float = 220.0,
    lat_range: Tuple[float, float] = (-90, -50),
    season_filter: Optional[str] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    cache_key = f"vortex_hole_corr_{threshold}_{lat_range}_{season_filter}"
    cache_key = cache_key.replace(':', '_').replace('-', '_').replace('.', '_').replace('None', 'all')

    if use_cache:
        cached = get_cache(cache_key)
        if cached is not None:
            return cached

    ds_analysis = ds.copy()
    if season_filter:
        from app.data.loader import OzoneDataLoader
        loader = OzoneDataLoader()
        ds_analysis = loader.filter_by_season(ds_analysis, season_filter)

    vortex_ds = compute_vortex_indices(ds_analysis, lat_range=lat_range, use_cache=False)
    hole_ds = detect_ozone_hole(ds_analysis, threshold=threshold, lat_range=lat_range)

    times = pd.to_datetime(ds_analysis['time'].values)

    vortex_area = vortex_ds['vortex_area'].values
    vortex_strength = vortex_ds['vortex_strength'].values
    hole_area = hole_ds['hole_area'].values
    hole_mean_ozone = hole_ds['mean_hole_ozone'].values
    hole_min_ozone = hole_ds['min_hole_ozone'].values

    valid_mask = ~np.isnan(vortex_area) & ~np.isnan(hole_area)

    result = {
        'timeseries': {
            'time': [str(t) for t in times],
            'vortex_area_km2': vortex_area.tolist(),
            'vortex_strength_du': vortex_strength.tolist(),
            'hole_area_km2': hole_area.tolist(),
            'hole_mean_ozone_du': hole_mean_ozone.tolist(),
            'hole_min_ozone_du': hole_min_ozone.tolist(),
        },
    }

    if np.any(valid_mask):
        va = np.asarray(vortex_area)[valid_mask]
        vs = np.asarray(vortex_strength)[valid_mask]
        ha = np.asarray(hole_area)[valid_mask]
        hmo = np.asarray(hole_mean_ozone)[valid_mask]
        hmin = np.asarray(hole_min_ozone)[valid_mask]

        def compute_corr(x, y):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            fin = np.isfinite(x) & np.isfinite(y)
            x = x[fin]
            y = y[fin]
            if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
                return np.nan, np.nan
            r, p = stats.pearsonr(x, y)
            return r, p

        corr_va_ha, p_va_ha = compute_corr(va, ha)
        corr_va_hmo, p_va_hmo = compute_corr(va, hmo)
        corr_va_hmin, p_va_hmin = compute_corr(va, hmin)
        corr_vs_ha, p_vs_ha = compute_corr(vs, ha)
        corr_vs_hmo, p_vs_hmo = compute_corr(vs, hmo)
        corr_vs_hmin, p_vs_hmin = compute_corr(vs, hmin)

        def lagged_corr(x, y, max_lag: int = 12):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            correlations = []
            p_values = []
            for lag in range(-max_lag, max_lag + 1):
                if lag >= 0:
                    x_lagged = x[lag:]
                    y_aligned = y[:len(x_lagged)]
                else:
                    y_aligned = y[-lag:]
                    x_lagged = x[:len(y_aligned)]
                fin = np.isfinite(x_lagged) & np.isfinite(y_aligned)
                x_lagged = x_lagged[fin]
                y_aligned = y_aligned[fin]
                if len(x_lagged) >= 10 and np.std(x_lagged) > 0 and np.std(y_aligned) > 0:
                    r, p = stats.pearsonr(x_lagged, y_aligned)
                    correlations.append(r)
                    p_values.append(p)
                else:
                    correlations.append(np.nan)
                    p_values.append(np.nan)
            return correlations, p_values, list(range(-max_lag, max_lag + 1))

        lag_corr, lag_p, lags = lagged_corr(va, ha, max_lag=12)

        monthly_correlations = {}
        months = np.array([t.month for t in times])
        for month in range(1, 13):
            month_mask = months == month
            if np.any(month_mask & valid_mask):
                r, p = compute_corr(va[month_mask & valid_mask], ha[month_mask & valid_mask])
                monthly_correlations[month] = {
                    'correlation': float(r) if not np.isnan(r) else None,
                    'p_value': float(p) if not np.isnan(p) else None,
                    'n_samples': int(np.sum(month_mask & valid_mask)),
                }

        result['correlations'] = {
            'vortex_area_vs_hole_area': {
                'correlation': float(corr_va_ha) if not np.isnan(corr_va_ha) else None,
                'p_value': float(p_va_ha) if not np.isnan(p_va_ha) else None,
            },
            'vortex_area_vs_mean_ozone': {
                'correlation': float(corr_va_hmo) if not np.isnan(corr_va_hmo) else None,
                'p_value': float(p_va_hmo) if not np.isnan(p_va_hmo) else None,
            },
            'vortex_area_vs_min_ozone': {
                'correlation': float(corr_va_hmin) if not np.isnan(corr_va_hmin) else None,
                'p_value': float(p_va_hmin) if not np.isnan(p_va_hmin) else None,
            },
            'vortex_strength_vs_hole_area': {
                'correlation': float(corr_vs_ha) if not np.isnan(corr_vs_ha) else None,
                'p_value': float(p_vs_ha) if not np.isnan(p_vs_ha) else None,
            },
            'vortex_strength_vs_mean_ozone': {
                'correlation': float(corr_vs_hmo) if not np.isnan(corr_vs_hmo) else None,
                'p_value': float(p_vs_hmo) if not np.isnan(p_vs_hmo) else None,
            },
            'vortex_strength_vs_min_ozone': {
                'correlation': float(corr_vs_hmin) if not np.isnan(corr_vs_hmin) else None,
                'p_value': float(p_vs_hmin) if not np.isnan(p_vs_hmin) else None,
            },
            'lagged_correlation_vortex_hole_area': {
                'lags': lags,
                'correlations': [float(c) if not np.isnan(c) else None for c in lag_corr],
                'p_values': [float(p) if not np.isnan(p) else None for p in lag_p],
            },
            'monthly_correlations': monthly_correlations,
            'n_valid_samples': int(np.sum(valid_mask)),
        }

        annual_max = {}
        years = np.unique([t.year for t in times])
        for year in years:
            year_mask = np.array([t.year == year for t in times])
            if np.any(year_mask & valid_mask):
                year_idx = np.where(year_mask & valid_mask)[0]
                max_hole_idx = year_idx[np.argmax(ha[year_mask & valid_mask])]
                max_vortex_idx = year_idx[np.argmax(va[year_mask & valid_mask])]
                annual_max[int(year)] = {
                    'max_hole_area': float(ha[max_hole_idx]),
                    'max_hole_date': str(times[max_hole_idx]),
                    'max_vortex_area': float(va[max_vortex_idx]),
                    'max_vortex_date': str(times[max_vortex_idx]),
                    'vortex_at_hole_max': float(va[max_hole_idx]),
                }

        result['annual_maxima'] = annual_max

    result['metadata'] = {
        'threshold': threshold,
        'lat_range': lat_range,
        'season_filter': season_filter,
        'unit_area': 'km²',
        'unit_ozone': 'DU',
    }

    if use_cache:
        set_cache(cache_key, result)

    return sanitize_for_json(result)


def vortex_to_geojson(
    ds: xr.Dataset,
    time_idx: Optional[int] = None,
    lat_range: Tuple[float, float] = (-90, -50),
) -> Dict[str, Any]:
    if time_idx is None:
        time_idx = -1

    result = detect_vortex_boundary(ds, time_idx, lat_range=lat_range, threshold_method='contour')

    lats = result['lats']
    lons = result['lons']
    resolution = (lats[1] - lats[0]) / 2 if len(lats) > 1 else 0.5

    features = []

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            is_boundary = bool(result['boundary_mask'][i, j])
            is_inside = bool(result['vortex_mask'][i, j])
            data_value = float(result['data_values'][i, j])
            gradient = float(result['gradient_magnitude'][i, j])

            if np.isnan(data_value):
                continue

            coords = [
                [lon - resolution, lat - resolution],
                [lon + resolution, lat - resolution],
                [lon + resolution, lat + resolution],
                [lon - resolution, lat + resolution],
                [lon - resolution, lat - resolution],
            ]

            category = 'outside'
            if is_boundary:
                category = 'boundary'
            elif is_inside:
                category = 'inside'

            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [coords],
                },
                'properties': {
                    'lat': float(lat),
                    'lon': float(lon),
                    'ozone_du': data_value,
                    'gradient_magnitude': gradient,
                    'is_vortex_boundary': is_boundary,
                    'is_inside_vortex': is_inside,
                    'category': category,
                },
            }
            features.append(feature)

    geojson = {
        'type': 'FeatureCollection',
        'features': features,
        'properties': {
            'time': str(ds['time'].values[time_idx]),
            'vortex_area_km2': float(result['vortex_area_km2']),
            'vortex_strength_du': float(result['vortex_strength_du']),
            'mean_boundary_latitude': float(result['mean_boundary_latitude']),
            'lat_range': lat_range,
            'unit_area': 'km²',
            'unit_ozone': 'DU',
        },
    }

    return sanitize_for_json(geojson)
