import xarray as xr
import dask.array as da
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Union
from datetime import datetime
import glob
import re

from app.core.config import settings


class OzoneDataLoader:
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or settings.DATA_DIR)
        self._dataset: Optional[xr.Dataset] = None

    def discover_files(self) -> list:
        pattern = str(self.data_dir / settings.NETCDF_PATTERN)
        return sorted(glob.glob(pattern))

    def _parse_date_from_filename(self, filename: str) -> Optional[datetime]:
        match = re.search(r'(\d{4})', filename)
        if match:
            year = int(match.group(1))
            return datetime(year, 1, 1)
        return None

    def load_single_file(self, filepath: str, chunks: Optional[dict] = None) -> xr.Dataset:
        default_chunks = {'time': 1, 'lat': 90, 'lon': 180}
        chunks = chunks or default_chunks

        ds = xr.open_dataset(filepath, chunks=chunks)

        if 'time' not in ds.dims:
            date = self._parse_date_from_filename(filepath)
            if date:
                ds = ds.expand_dims(time=[date])

        if 'ozone' not in ds.data_vars:
            possible_names = ['O3', 'o3', 'ozone', 'toz', 'TOZ', 'total_ozone']
            for name in possible_names:
                if name in ds.data_vars:
                    ds = ds.rename({name: 'ozone'})
                    break

        return ds

    def load_dataset(
        self,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        lat_range: Optional[Tuple[float, float]] = None,
        lon_range: Optional[Tuple[float, float]] = None,
        force_reload: bool = False,
    ) -> xr.Dataset:
        if self._dataset is not None and not force_reload:
            ds = self._dataset
        else:
            files = self.discover_files()
            if not files:
                raise FileNotFoundError(
                    f"No NetCDF files found in {self.data_dir} matching {settings.NETCDF_PATTERN}"
                )

            datasets = []
            for f in files:
                try:
                    ds_single = self.load_single_file(f)
                    datasets.append(ds_single)
                except Exception as e:
                    print(f"Warning: Could not load {f}: {e}")

            if not datasets:
                raise ValueError("No datasets could be loaded")

            ds = xr.concat(datasets, dim='time')
            ds = ds.sortby('time')

            if 'lat' in ds.coords:
                if ds['lat'].values[0] > ds['lat'].values[-1]:
                    ds = ds.sortby('lat')

            self._dataset = ds

        if time_range is not None:
            start, end = time_range
            ds = ds.sel(time=slice(start, end))

        if lat_range is not None:
            lat_min, lat_max = lat_range
            ds = ds.sel(lat=slice(lat_min, lat_max))

        if lon_range is not None:
            lon_min, lon_max = lon_range
            ds = ds.sel(lon=slice(lon_min, lon_max))

        return ds

    def get_point_data(
        self,
        lat: float,
        lon: float,
        time_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> xr.DataArray:
        ds = self.load_dataset(time_range=time_range)
        return ds['ozone'].sel(lat=lat, lon=lon, method='nearest')

    def get_global_grid_info(self) -> dict:
        ds = self.load_dataset()
        return {
            'time_range': [ds['time'].values[0], ds['time'].values[-1]],
            'lat_range': [float(ds['lat'].values.min()), float(ds['lat'].values.max())],
            'lon_range': [float(ds['lon'].values.min()), float(ds['lon'].values.max())],
            'time_steps': len(ds['time']),
            'lat_points': len(ds['lat']),
            'lon_points': len(ds['lon']),
            'grid_resolution': settings.GRID_RESOLUTION,
        }

    def filter_by_latitude_band(
        self,
        ds: xr.Dataset,
        band: str,
    ) -> xr.Dataset:
        bands = {
            'global': (-90, 90),
            'tropics': (-23.5, 23.5),
            'mid_north': (23.5, 66.5),
            'mid_south': (-66.5, -23.5),
            'arctic': (66.5, 90),
            'antarctic': (-90, -66.5),
            'southern_hemisphere': (-90, 0),
            'northern_hemisphere': (0, 90),
        }
        if band not in bands:
            raise ValueError(f"Unknown latitude band: {band}. Available: {list(bands.keys())}")

        lat_min, lat_max = bands[band]
        return ds.sel(lat=slice(lat_min, lat_max))

    def filter_by_season(
        self,
        ds: xr.Dataset,
        season: str,
    ) -> xr.Dataset:
        seasons = {
            'DJF': [12, 1, 2],
            'MAM': [3, 4, 5],
            'JJA': [6, 7, 8],
            'SON': [9, 10, 11],
        }
        if season not in seasons:
            raise ValueError(f"Unknown season: {season}. Available: {list(seasons.keys())}")

        return ds.sel(time=ds['time.month'].isin(seasons[season]))

    def close(self):
        if self._dataset is not None:
            self._dataset.close()
            self._dataset = None


def get_data_loader() -> OzoneDataLoader:
    return OzoneDataLoader()
