import numpy as np
import xarray as xr
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import pandas as pd
from scipy import stats

from app.core.config import settings
from app.core.utils import sanitize_for_json
from app.analysis.ozone_hole import area_weighted_mean, calculate_grid_area
from app.cache.parquet_cache import get_cache, set_cache


class GEOSChemValidator:
    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir or (settings.DATA_DIR + "/geoschem")
        self.obs_data = None
        self.model_data = None

    def load_model_data(
        self,
        pattern: str = "*.nc",
        var_name: str = "O3",
        time_range: Optional[Tuple[datetime, datetime]] = None,
        lat_range: Optional[Tuple[float, float]] = None,
        lon_range: Optional[Tuple[float, float]] = None,
    ) -> xr.Dataset:
        import glob
        from pathlib import Path

        model_path = Path(self.model_dir)
        files = sorted(glob.glob(str(model_path / pattern)))

        if not files:
            raise FileNotFoundError(f"No GEOS-Chem files found in {model_path} matching {pattern}")

        datasets = []
        for f in files:
            try:
                ds = xr.open_dataset(f)
                if var_name in ds.data_vars:
                    ds = ds.rename({var_name: 'ozone_model'})
                    if 'time' not in ds.dims:
                        ds = ds.expand_dims(time=[datetime(int(f[-7:-3]), 1, 1)])
                    datasets.append(ds[['ozone_model']])
            except Exception as e:
                print(f"Warning: Could not load {f}: {e}")

        if not datasets:
            raise ValueError("No GEOS-Chem datasets could be loaded")

        model_ds = xr.concat(datasets, dim='time')
        model_ds = model_ds.sortby('time')

        if time_range:
            model_ds = model_ds.sel(time=slice(*time_range))
        if lat_range:
            model_ds = model_ds.sel(lat=slice(*lat_range))
        if lon_range:
            model_ds = model_ds.sel(lon=slice(*lon_range))

        self.model_data = model_ds
        return model_ds

    def load_observation_data(
        self,
        obs_ds: xr.Dataset,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        lat_range: Optional[Tuple[float, float]] = None,
        lon_range: Optional[Tuple[float, float]] = None,
    ) -> xr.Dataset:
        obs = obs_ds.copy()
        if 'ozone' in obs.data_vars:
            obs = obs.rename({'ozone': 'ozone_obs'})

        if time_range:
            obs = obs.sel(time=slice(*time_range))
        if lat_range:
            obs = obs.sel(lat=slice(*lat_range))
        if lon_range:
            obs = obs.sel(lon=slice(*lon_range))

        self.obs_data = obs
        return obs

    def regrid_model(self, target_ds: xr.Dataset) -> xr.Dataset:
        if self.model_data is None:
            raise ValueError("Model data not loaded")

        model_regrid = self.model_data.interp(
            lat=target_ds['lat'].values,
            lon=target_ds['lon'].values,
            method='linear'
        )

        model_regrid = model_regrid.reindex(time=target_ds['time'].values, method='nearest')

        return model_regrid

    def compare_datasets(
        self,
        obs_ds: xr.Dataset,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        lat_range: Optional[Tuple[float, float]] = None,
        lon_range: Optional[Tuple[float, float]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        cache_key = f"geoschem_compare_{time_range}_{lat_range}_{lon_range}"
        cache_key = cache_key.replace(':', '_').replace('-', '_').replace('.', '_').replace(' ', '_')

        if use_cache:
            cached = get_cache(cache_key)
            if cached is not None:
                return cached

        if self.obs_data is None:
            self.load_observation_data(obs_ds, time_range, lat_range, lon_range)
        if self.model_data is None:
            self.load_model_data(time_range=time_range, lat_range=lat_range, lon_range=lon_range)

        model_regrid = self.regrid_model(self.obs_data)

        obs = self.obs_data['ozone_obs'].values
        model = model_regrid['ozone_model'].values

        valid_mask = ~np.isnan(obs) & ~np.isnan(model)
        obs_valid = obs[valid_mask]
        model_valid = model[valid_mask]

        if len(obs_valid) < 10:
            return {"error": "Insufficient overlapping data points"}

        bias = model_valid - obs_valid
        mean_bias = np.mean(bias)
        mean_abs_bias = np.mean(np.abs(bias))
        rmse = np.sqrt(np.mean(bias ** 2))
        mae = np.mean(np.abs(bias))
        nmb = mean_bias / np.mean(obs_valid) * 100
        nme = mean_abs_bias / np.mean(obs_valid) * 100

        slope, intercept, r_value, p_value, std_err = stats.linregress(obs_valid, model_valid)
        r2 = r_value ** 2

        bias_da = xr.DataArray(
            model - obs,
            dims=['time', 'lat', 'lon'],
            coords={
                'time': self.obs_data['time'].values,
                'lat': self.obs_data['lat'].values,
                'lon': self.obs_data['lon'].values,
            }
        )

        zonal_mean_bias = bias_da.mean(dim=['lon', 'time'])
        seasonal_bias = bias_da.groupby('time.month').mean(dim=['time', 'lat', 'lon'])

        result = {
            'metrics': {
                'mean_bias_du': float(mean_bias),
                'mean_abs_bias_du': float(mean_abs_bias),
                'rmse_du': float(rmse),
                'mae_du': float(mae),
                'nmb_percent': float(nmb),
                'nme_percent': float(nme),
                'r2': float(r2),
                'correlation_coefficient': float(r_value),
                'p_value': float(p_value),
                'regression_slope': float(slope),
                'regression_intercept': float(intercept),
                'n_points': int(len(obs_valid)),
            },
            'scatter_data': {
                'observations': obs_valid[::max(1, len(obs_valid) // 1000)].tolist(),
                'model': model_valid[::max(1, len(model_valid) // 1000)].tolist(),
            },
            'zonal_mean_bias': {
                'latitudes': zonal_mean_bias['lat'].values.tolist(),
                'bias': zonal_mean_bias.values.tolist(),
            },
            'seasonal_bias': {
                'months': list(range(1, 13)),
                'bias': seasonal_bias.values.tolist(),
            },
            'time_range': [str(self.obs_data['time'].values[0]), str(self.obs_data['time'].values[-1])],
            'lat_range': [float(self.obs_data['lat'].min()), float(self.obs_data['lat'].max())],
            'lon_range': [float(self.obs_data['lon'].min()), float(self.obs_data['lon'].max())],
        }

        if use_cache:
            set_cache(cache_key, result)

        return sanitize_for_json(result)

    def compare_hole_metrics(
        self,
        obs_ds: xr.Dataset,
        threshold: float = 220.0,
        lat_range: Tuple[float, float] = (-90, -50),
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        from app.analysis.ozone_hole import detect_ozone_hole

        cache_key = f"geoschem_hole_compare_{threshold}_{lat_range}"
        cache_key = cache_key.replace(':', '_').replace('-', '_').replace('.', '_').replace(' ', '_')

        if use_cache:
            cached = get_cache(cache_key)
            if cached is not None:
                return cached

        if self.obs_data is None:
            self.load_observation_data(obs_ds, lat_range=lat_range)
        if self.model_data is None:
            self.load_model_data(lat_range=lat_range)

        model_regrid = self.regrid_model(self.obs_data)

        obs_hole = detect_ozone_hole(
            self.obs_data.rename({'ozone_obs': 'ozone'}),
            threshold=threshold,
            lat_range=lat_range,
        )
        model_hole = detect_ozone_hole(
            model_regrid.rename({'ozone_model': 'ozone'}),
            threshold=threshold,
            lat_range=lat_range,
        )

        obs_area = obs_hole['hole_area'].values
        model_area = model_hole['hole_area'].values
        obs_mean = obs_hole['mean_hole_ozone'].values
        model_mean = model_hole['mean_hole_ozone'].values

        valid_mask = ~np.isnan(obs_area) & ~np.isnan(model_area)
        if np.any(valid_mask):
            area_corr = np.corrcoef(obs_area[valid_mask], model_area[valid_mask])[0, 1]
            area_bias = np.mean(model_area[valid_mask] - obs_area[valid_mask])
            area_rmse = np.sqrt(np.mean((model_area[valid_mask] - obs_area[valid_mask]) ** 2))
        else:
            area_corr = np.nan
            area_bias = np.nan
            area_rmse = np.nan

        times = pd.to_datetime(self.obs_data['time'].values)

        result = {
            'hole_area_comparison': {
                'time': [str(t) for t in times],
                'observation_area_km2': obs_area.tolist(),
                'model_area_km2': model_area.tolist(),
                'observation_mean_ozone_du': obs_mean.tolist(),
                'model_mean_ozone_du': model_mean.tolist(),
            },
            'metrics': {
                'area_correlation': float(area_corr) if not np.isnan(area_corr) else None,
                'area_mean_bias_km2': float(area_bias) if not np.isnan(area_bias) else None,
                'area_rmse_km2': float(area_rmse) if not np.isnan(area_rmse) else None,
                'max_obs_area_km2': float(np.nanmax(obs_area)),
                'max_model_area_km2': float(np.nanmax(model_area)),
                'mean_obs_area_km2': float(np.nanmean(obs_area)),
                'mean_model_area_km2': float(np.nanmean(model_area)),
            },
            'threshold': threshold,
            'lat_range': lat_range,
            'unit_area': 'km²',
            'unit_ozone': 'DU',
        }

        if use_cache:
            set_cache(cache_key, result)

        return sanitize_for_json(result)


def generate_synthetic_geoschem_data(
    obs_ds: xr.Dataset,
    bias: float = 5.0,
    noise: float = 10.0,
    seasonal_phase_shift: float = 0.5,
) -> xr.Dataset:
    ozone_obs = obs_ds['ozone'].values
    times = obs_ds['time'].values
    lats = obs_ds['lat'].values
    lons = obs_ds['lon'].values

    lat_factor = np.cos(np.radians(lats))
    lat_factor = np.expand_dims(lat_factor, axis=(0, 2))

    time_idx = np.arange(len(times))
    seasonal_bias = 10 * lat_factor * np.sin(2 * np.pi * np.expand_dims(time_idx, axis=(1, 2)) / 12 + seasonal_phase_shift)

    random_noise = np.random.normal(0, noise, ozone_obs.shape)

    ozone_model = ozone_obs + bias + seasonal_bias + random_noise

    model_ds = xr.Dataset(
        {
            'ozone_model': (['time', 'lat', 'lon'], ozone_model),
        },
        coords={
            'time': times,
            'lat': lats,
            'lon': lons,
        },
        attrs={
            'title': 'Synthetic GEOS-Chem Ozone Data',
            'source': 'Synthetic data for validation testing',
            'model_bias': bias,
            'model_noise': noise,
            'seasonal_phase_shift': seasonal_phase_shift,
        },
    )

    return model_ds
