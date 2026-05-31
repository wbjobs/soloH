import numpy as np
import xarray as xr
import dask.array as da
from typing import Tuple, Optional, Dict, Any
from scipy import stats
import pymannkendall as pmk

from app.core.dask_client import parallel_map
from app.core.utils import sanitize_for_json
from app.cache.parquet_cache import get_cache, set_cache


def sen_slope(y: np.ndarray, x: Optional[np.ndarray] = None) -> float:
    n = len(y)
    if x is None:
        x = np.arange(n)

    valid_mask = ~np.isnan(y)
    x_valid = x[valid_mask]
    y_valid = y[valid_mask]
    n_valid = len(y_valid)

    if n_valid < 2:
        return np.nan

    slopes = []
    for i in range(n_valid):
        for j in range(i + 1, n_valid):
            if x_valid[j] != x_valid[i]:
                slopes.append((y_valid[j] - y_valid[i]) / (x_valid[j] - x_valid[i]))

    if len(slopes) == 0:
        return np.nan

    return np.median(slopes)


def sen_slope_intercept(y: np.ndarray, x: Optional[np.ndarray] = None) -> Tuple[float, float]:
    slope = sen_slope(y, x)
    if np.isnan(slope):
        return np.nan, np.nan

    if x is None:
        x = np.arange(len(y))

    valid_mask = ~np.isnan(y)
    x_valid = x[valid_mask]
    y_valid = y[valid_mask]

    intercept = np.median(y_valid - slope * x_valid)
    return slope, intercept


def mann_kendall_test(y: np.ndarray, alpha: float = 0.05) -> Dict[str, Any]:
    valid_mask = ~np.isnan(y)
    y_valid = y[valid_mask]
    n = len(y_valid)

    if n < 3:
        return {
            'trend': 'insufficient_data',
            'h': False,
            'p': np.nan,
            'z': np.nan,
            'Tau': np.nan,
            's': np.nan,
            'var_s': np.nan,
            'slope': np.nan,
            'intercept': np.nan,
        }

    try:
        s = 0
        for i in range(n - 1):
            for j in range(i + 1, n):
                diff = y_valid[j] - y_valid[i]
                if diff > 0:
                    s += 1
                elif diff < 0:
                    s -= 1

        unique_values, counts = np.unique(y_valid, return_counts=True)
        tie_groups = counts[counts > 1]

        var_s_nominal = n * (n - 1) * (2 * n + 5) / 18

        tie_correction = 0
        for t in tie_groups:
            tie_correction += t * (t - 1) * (2 * t + 5)

        var_s = var_s_nominal - tie_correction / 18

        if var_s <= 0:
            var_s = 1e-10

        if s > 0:
            z = (s - 1) / np.sqrt(var_s)
        elif s < 0:
            z = (s + 1) / np.sqrt(var_s)
        else:
            z = 0

        p = 2 * (1 - stats.norm.cdf(abs(z)))

        h = p < alpha

        if h:
            if z > 0:
                trend = 'increasing'
            else:
                trend = 'decreasing'
        else:
            trend = 'no trend'

        n_pairs = n * (n - 1) / 2
        tau = s / n_pairs if n_pairs > 0 else 0

        sen_slope_val, intercept_val = sen_slope_intercept(y_valid)

        return {
            'trend': trend,
            'h': bool(h),
            'p': float(p),
            'z': float(z),
            'Tau': float(tau),
            's': float(s),
            'var_s': float(var_s),
            'var_s_nominal': float(var_s_nominal),
            'tie_correction': float(tie_correction / 18) if len(tie_groups) > 0 else 0.0,
            'slope': float(sen_slope_val),
            'intercept': float(intercept_val),
        }
    except Exception as e:
        print(f"Error in Mann-Kendall test: {e}")
        return {
            'trend': 'error',
            'h': False,
            'p': np.nan,
            'z': np.nan,
            'Tau': np.nan,
            's': np.nan,
            'var_s': np.nan,
            'slope': np.nan,
            'intercept': np.nan,
        }


def _analyze_point(args: Tuple[np.ndarray, np.ndarray, float]) -> Dict[str, Any]:
    data, time_values, alpha = args
    mk_result = mann_kendall_test(data, alpha=alpha)
    sen = sen_slope(data, x=time_values)
    return {
        'sen_slope': sen,
        'mk_slope': mk_result['slope'],
        'intercept': mk_result['intercept'],
        'p_value': mk_result['p'],
        'z_stat': mk_result['z'],
        'tau': mk_result['Tau'],
        'significant': mk_result['h'],
        'trend_direction': mk_result['trend'],
    }


def compute_grid_trends(
    ds: xr.Dataset,
    variable: str = 'ozone',
    alpha: float = 0.05,
    use_cache: bool = True,
) -> xr.Dataset:
    cache_key = f"trends_{variable}_{alpha}_{ds['time'].values[0]}_{ds['time'].values[-1]}"
    cache_key = cache_key.replace(':', '_').replace('-', '_')

    if use_cache:
        cached = get_cache(cache_key)
        if cached is not None:
            return cached

    data = ds[variable]
    time_values = np.arange(len(ds['time']))

    latitudes = ds['lat'].values
    longitudes = ds['lon'].values

    nlat = len(latitudes)
    nlon = len(longitudes)

    analysis_args = []
    grid_points = []

    for i, lat in enumerate(latitudes):
        for j, lon in enumerate(longitudes):
            point_data = data[:, i, j].values
            analysis_args.append((point_data, time_values, alpha))
            grid_points.append((lat, lon, i, j))

    results = parallel_map(_analyze_point, analysis_args)

    sen_slope_grid = np.full((nlat, nlon), np.nan)
    mk_slope_grid = np.full((nlat, nlon), np.nan)
    intercept_grid = np.full((nlat, nlon), np.nan)
    p_value_grid = np.full((nlat, nlon), np.nan)
    z_stat_grid = np.full((nlat, nlon), np.nan)
    tau_grid = np.full((nlat, nlon), np.nan)
    significant_grid = np.full((nlat, nlon), False, dtype=bool)
    trend_dir_grid = np.full((nlat, nlon), '', dtype=object)

    for k, result in enumerate(results):
        lat, lon, i, j = grid_points[k]
        sen_slope_grid[i, j] = result['sen_slope']
        mk_slope_grid[i, j] = result['mk_slope']
        intercept_grid[i, j] = result['intercept']
        p_value_grid[i, j] = result['p_value']
        z_stat_grid[i, j] = result['z_stat']
        tau_grid[i, j] = result['tau']
        significant_grid[i, j] = result['significant']
        trend_dir_grid[i, j] = result['trend_direction']

    trend_ds = xr.Dataset(
        {
            'sen_slope': (['lat', 'lon'], sen_slope_grid),
            'mk_slope': (['lat', 'lon'], mk_slope_grid),
            'intercept': (['lat', 'lon'], intercept_grid),
            'p_value': (['lat', 'lon'], p_value_grid),
            'z_stat': (['lat', 'lon'], z_stat_grid),
            'tau': (['lat', 'lon'], tau_grid),
            'significant': (['lat', 'lon'], significant_grid),
            'trend_direction': (['lat', 'lon'], trend_dir_grid.astype(str)),
        },
        coords={'lat': latitudes, 'lon': longitudes},
        attrs={
            'variable': variable,
            'alpha': alpha,
            'time_start': str(ds['time'].values[0]),
            'time_end': str(ds['time'].values[-1]),
            'n_time_steps': len(ds['time']),
        },
    )

    if use_cache:
        set_cache(cache_key, trend_ds)

    return trend_ds


def get_point_trend(
    ds: xr.Dataset,
    lat: float,
    lon: float,
    variable: str = 'ozone',
    alpha: float = 0.05,
) -> Dict[str, Any]:
    point_data = ds[variable].sel(lat=lat, lon=lon, method='nearest')
    time_values = np.arange(len(ds['time']))

    result = _analyze_point((point_data.values, time_values, alpha))

    return {
        'lat': float(point_data['lat'].values),
        'lon': float(point_data['lon'].values),
        **result,
        'unit': 'DU/year',
        'alpha': alpha,
    }


def trend_to_geojson(trend_ds: xr.Dataset, value_field: str = 'sen_slope') -> Dict[str, Any]:
    features = []

    lats = trend_ds['lat'].values
    lons = trend_ds['lon'].values
    resolution = (lats[1] - lats[0]) / 2 if len(lats) > 1 else 0.5

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            value = float(trend_ds[value_field][i, j].values)
            if np.isnan(value):
                continue

            significant = bool(trend_ds['significant'][i, j].values)
            p_value = float(trend_ds['p_value'][i, j].values)

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
                    value_field: value,
                    'significant': significant,
                    'p_value': p_value,
                    'trend_direction': str(trend_ds['trend_direction'][i, j].values),
                },
            }
            features.append(feature)

    result = {
        'type': 'FeatureCollection',
        'features': features,
        'properties': {
            'value_field': value_field,
            'time_start': trend_ds.attrs.get('time_start', ''),
            'time_end': trend_ds.attrs.get('time_end', ''),
            'alpha': trend_ds.attrs.get('alpha', 0.05),
        },
    }

    return sanitize_for_json(result)
