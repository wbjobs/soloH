import numpy as np
import xarray as xr
import pandas as pd
from pathlib import Path
from datetime import datetime
import argparse


def generate_ozone_data(
    start_year: int = 1980,
    end_year: int = 2024,
    lat_res: float = 1.0,
    lon_res: float = 1.0,
    output_dir: str = "e:/soloH/h24/data",
    annual: bool = False,
):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    lats = np.arange(-90, 90 + lat_res, lat_res)
    lons = np.arange(-180, 180, lon_res)

    if annual:
        years = range(start_year, end_year + 1)
        times = [datetime(year, 1, 1) for year in years]
    else:
        times = pd.date_range(start=f"{start_year}-01-01", end=f"{end_year}-12-31", freq='MS')

    nlat = len(lats)
    nlon = len(lons)
    ntime = len(times)

    print(f"Generating data: {ntime} time steps, {nlat}x{nlon} grid...")

    lat2d, lon2d = np.meshgrid(lats, lons, indexing='ij')
    time_idx = np.arange(ntime)

    base_ozone = 300 + 50 * np.sin(np.radians(lat2d))
    base_ozone = np.expand_dims(base_ozone, axis=0)

    lat_factor = np.ones_like(lat2d)
    southern_mask = lat2d < -50
    lat_factor[southern_mask] = 0.7 + 0.3 * np.sin(2 * np.pi * (lat2d[southern_mask] + 90) / 40)
    lat_factor = np.expand_dims(lat_factor, axis=0)

    annual_cycle = 40 * np.sin(2 * np.pi * np.expand_dims(time_idx, axis=(1, 2)) / 12 + np.radians(lon2d) / np.pi)
    annual_cycle = annual_cycle * lat_factor

    trend = np.zeros_like(base_ozone)
    trend_mag = -0.5 * lat_factor
    for t in range(ntime):
        decay = min(1.0, t / (ntime * 0.3))
        trend = np.concatenate([trend, trend_mag * t * decay * np.ones_like(base_ozone)], axis=0)
    trend = trend[1:]

    antarctic_hole = np.zeros((ntime, nlat, nlon))
    for t in range(ntime):
        month = (t % 12) + 1
        if 8 <= month <= 11:
            intensity = 1.0 if 9 <= month <= 10 else 0.6
            year_factor = min(1.0, t / (ntime * 0.5))
            depth = 150 * intensity * year_factor * southern_mask.astype(float)
            antarctic_hole[t] = depth

    noise = np.random.normal(0, 8, (ntime, nlat, nlon))

    ozone_data = base_ozone + annual_cycle + trend + antarctic_hole + noise
    ozone_data = np.clip(ozone_data, 100, 500)

    if annual:
        for i, year in enumerate(years):
            ds = xr.Dataset(
                {
                    'ozone': (['time', 'lat', 'lon'], ozone_data[i:i+1, :, :]),
                },
                coords={
                    'time': [times[i]],
                    'lat': lats,
                    'lon': lons,
                },
                attrs={
                    'title': 'Synthetic TOMS/OMI Total Column Ozone Data',
                    'institution': 'Sample Data Generator',
                    'source': 'Synthetic data for testing',
                    'units': 'Dobson Units (DU)',
                    'year': year,
                    'resolution': f'{lat_res}x{lon_res} degrees',
                },
            )

            filename = output_path / f'ozone_{year}.nc'
            ds.to_netcdf(filename)
            print(f'Saved: {filename}')
    else:
        ds = xr.Dataset(
            {
                'ozone': (['time', 'lat', 'lon'], ozone_data),
            },
            coords={
                'time': times,
                'lat': lats,
                'lon': lons,
            },
            attrs={
                'title': 'Synthetic TOMS/OMI Total Column Ozone Data',
                'institution': 'Sample Data Generator',
                'source': 'Synthetic data for testing',
                'units': 'Dobson Units (DU)',
                'time_range': f'{start_year}-{end_year}',
                'resolution': f'{lat_res}x{lon_res} degrees',
            },
        )

        filename = output_path / f'ozone_{start_year}_{end_year}.nc'
        ds.to_netcdf(filename)
        print(f'Saved: {filename}')

    print(f"Data generation complete. Output directory: {output_path}")
    print(f"Grid: {nlat} x {nlon} points, {ntime} time steps")
    print(f"Data range: {ozone_data.min():.1f} to {ozone_data.max():.1f} DU")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate synthetic ozone data for testing')
    parser.add_argument('--start-year', type=int, default=1980, help='Start year (default: 1980)')
    parser.add_argument('--end-year', type=int, default=2024, help='End year (default: 2024)')
    parser.add_argument('--lat-res', type=float, default=1.0, help='Latitude resolution (default: 1.0)')
    parser.add_argument('--lon-res', type=float, default=1.0, help='Longitude resolution (default: 1.0)')
    parser.add_argument('--output-dir', type=str, default='e:/soloH/h24/data', help='Output directory')
    parser.add_argument('--annual', action='store_true', help='Save annual files instead of single file')

    args = parser.parse_args()

    generate_ozone_data(
        start_year=args.start_year,
        end_year=args.end_year,
        lat_res=args.lat_res,
        lon_res=args.lon_res,
        output_dir=args.output_dir,
        annual=args.annual,
    )
