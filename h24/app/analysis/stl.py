import numpy as np
import xarray as xr
from typing import Dict, Any, Optional, Tuple
from statsmodels.tsa.seasonal import STL
import pandas as pd

from app.core.utils import sanitize_for_json
from app.cache.parquet_cache import get_cache, set_cache


def stl_decompose(
    y: np.ndarray,
    time_index: Optional[np.ndarray] = None,
    period: int = 12,
    seasonal: int = 7,
    trend: Optional[int] = None,
    low_pass: Optional[int] = None,
    robust: bool = True,
    interpolation_method: str = 'time',
) -> Dict[str, np.ndarray]:
    valid_mask = ~np.isnan(y)
    n_valid = valid_mask.sum()
    n = len(y)

    if n_valid < period * 2:
        return {
            'trend': np.full_like(y, np.nan),
            'seasonal': np.full_like(y, np.nan),
            'residual': np.full_like(y, np.nan),
        }

    y_interp = y.copy()

    if np.any(~valid_mask):
        if time_index is not None and len(time_index) == n:
            try:
                times = pd.to_datetime(time_index)
                s = pd.Series(y, index=times)
                s_valid = s[valid_mask]

                if s_valid.index.is_monotonic_increasing:
                    s_interp = s_valid.resample('MS').mean()
                    full_idx = pd.date_range(times.min(), times.max(), freq='MS')
                    s_interp = s_interp.reindex(full_idx)

                    methods = ['time', 'linear', 'spline', 'polynomial']
                    if interpolation_method not in methods:
                        interpolation_method = 'time'

                    if interpolation_method in ['spline', 'polynomial']:
                        s_interp = s_interp.interpolate(
                            method=interpolation_method,
                            order=3,
                            limit_direction='both'
                        )
                    else:
                        s_interp = s_interp.interpolate(
                            method=interpolation_method,
                            limit_direction='both'
                        )

                    s_interp = s_interp.reindex(times)
                    y_interp = s_interp.values
                else:
                    raise ValueError("Time index not monotonic")
            except Exception as e:
                print(f"Time-aware interpolation failed ({e}), falling back to linear interpolation")
                indices = np.arange(n)
                valid_indices = indices[valid_mask]
                valid_values = y[valid_mask]
                sorted_order = np.argsort(valid_indices)
                y_interp = np.interp(
                    indices,
                    valid_indices[sorted_order],
                    valid_values[sorted_order]
                )
        else:
            indices = np.arange(n)
            valid_indices = indices[valid_mask]
            valid_values = y[valid_mask]
            sorted_order = np.argsort(valid_indices)
            y_interp = np.interp(
                indices,
                valid_indices[sorted_order],
                valid_values[sorted_order]
            )

    try:
        stl = STL(
            y_interp,
            period=period,
            seasonal=seasonal,
            trend=trend,
            low_pass=low_pass,
            robust=robust,
        )
        result = stl.fit()

        trend_comp = result.trend.astype(float)
        seasonal_comp = result.seasonal.astype(float)
        residual_comp = result.resid.astype(float)

        trend_comp[~valid_mask] = np.nan
        seasonal_comp[~valid_mask] = np.nan
        residual_comp[~valid_mask] = np.nan

        return {
            'trend': trend_comp,
            'seasonal': seasonal_comp,
            'residual': residual_comp,
        }
    except Exception as e:
        print(f"Error in STL decomposition: {e}")
        return {
            'trend': np.full_like(y, np.nan),
            'seasonal': np.full_like(y, np.nan),
            'residual': np.full_like(y, np.nan),
        }


def decompose_point(
    ds: xr.Dataset,
    lat: float,
    lon: float,
    variable: str = 'ozone',
    period: int = 12,
    use_cache: bool = True,
) -> Dict[str, Any]:
    cache_key = f"stl_{variable}_{lat}_{lon}_{period}"
    cache_key = cache_key.replace('.', '_').replace('-', '_')

    if use_cache:
        cached = get_cache(cache_key)
        if cached is not None:
            return cached

    point_data = ds[variable].sel(lat=lat, lon=lon, method='nearest')
    times = pd.to_datetime(ds['time'].values)
    time_values = ds['time'].values

    decomposition = stl_decompose(
        point_data.values,
        time_index=time_values,
        period=period
    )

    result = {
        'lat': float(point_data['lat'].values),
        'lon': float(point_data['lon'].values),
        'time': [str(t) for t in times],
        'original': point_data.values.tolist(),
        'trend': decomposition['trend'].tolist(),
        'seasonal': decomposition['seasonal'].tolist(),
        'residual': decomposition['residual'].tolist(),
        'period': period,
        'unit': 'DU',
    }

    if use_cache:
        set_cache(cache_key, result)

    return sanitize_for_json(result)


def compute_seasonal_amplitude(
    ds: xr.Dataset,
    variable: str = 'ozone',
    period: int = 12,
    use_cache: bool = True,
) -> xr.Dataset:
    cache_key = f"seasonal_amp_{variable}_{period}_{ds['time'].values[0]}_{ds['time'].values[-1]}"
    cache_key = cache_key.replace(':', '_').replace('-', '_').replace('.', '_')

    if use_cache:
        cached = get_cache(cache_key)
        if cached is not None:
            return cached

    data = ds[variable]
    lats = ds['lat'].values
    lons = ds['lon'].values
    times = ds['time'].values

    seasonal_amp = np.full((len(lats), len(lons)), np.nan)
    seasonal_peak = np.full((len(lats), len(lons)), np.nan)
    trend_mean = np.full((len(lats), len(lons)), np.nan)

    time_values = ds['time'].values
    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            point_data = data[:, i, j].values
            decomp = stl_decompose(
                point_data,
                time_index=time_values,
                period=period
            )

            if not np.all(np.isnan(decomp['seasonal'])):
                seasonal_amp[i, j] = np.nanmax(decomp['seasonal']) - np.nanmin(decomp['seasonal'])
                peak_idx = np.nanargmax(decomp['seasonal'])
                seasonal_peak[i, j] = peak_idx % period

            if not np.all(np.isnan(decomp['trend'])):
                trend_mean[i, j] = np.nanmean(decomp['trend'])

    result_ds = xr.Dataset(
        {
            'seasonal_amplitude': (['lat', 'lon'], seasonal_amp),
            'seasonal_peak_month': (['lat', 'lon'], seasonal_peak),
            'trend_mean': (['lat', 'lon'], trend_mean),
        },
        coords={'lat': lats, 'lon': lons},
        attrs={
            'variable': variable,
            'period': period,
            'time_start': str(times[0]),
            'time_end': str(times[-1]),
        },
    )

    if use_cache:
        set_cache(cache_key, result_ds)

    return result_ds


def stl_to_geojson(stl_ds: xr.Dataset, value_field: str = 'seasonal_amplitude') -> Dict[str, Any]:
    features = []

    lats = stl_ds['lat'].values
    lons = stl_ds['lon'].values
    resolution = (lats[1] - lats[0]) / 2 if len(lats) > 1 else 0.5

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            value = float(stl_ds[value_field][i, j].values)
            if np.isnan(value):
                continue

            coords = [
                [lon - resolution, lat - resolution],
                [lon + resolution, lat - resolution],
                [lon + resolution, lat + resolution],
                [lon - resolution, lat + resolution],
                [lon - resolution, lat - resolution],
            ]

            properties = {
                'lat': float(lat),
                'lon': float(lon),
                value_field: value,
            }

            if 'seasonal_peak_month' in stl_ds:
                properties['seasonal_peak_month'] = float(stl_ds['seasonal_peak_month'][i, j].values)
            if 'trend_mean' in stl_ds:
                properties['trend_mean'] = float(stl_ds['trend_mean'][i, j].values)

            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [coords],
                },
                'properties': properties,
            }
            features.append(feature)

    result = {
        'type': 'FeatureCollection',
        'features': features,
        'properties': {
            'value_field': value_field,
            'time_start': stl_ds.attrs.get('time_start', ''),
            'time_end': stl_ds.attrs.get('time_end', ''),
        },
    }

    return sanitize_for_json(result)
