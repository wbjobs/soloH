from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import numpy as np
import xarray as xr

from app.api.models import (
    TrendRequest, GridTrendRequest, STLRequest, SeasonalAmplitudeRequest,
    OzoneHoleRequest, PointDataRequest, CacheRequest,
    TrendResponse, PointDataResponse, GridInfoResponse, CacheInfoResponse,
    GEOSChemCompareRequest, GEOSChemHoleCompareRequest,
    VortexAnalysisRequest, PredictionRequest, RegionPredictionRequest, HolePredictionRequest
)
from app.data.loader import get_data_loader, OzoneDataLoader
from app.analysis.trend import compute_grid_trends, get_point_trend, trend_to_geojson
from app.analysis.stl import decompose_point, compute_seasonal_amplitude, stl_to_geojson
from app.analysis.ozone_hole import (
    get_hole_area_timeseries, hole_mask_to_geojson, get_hole_climatology
)
from app.analysis.geoschem_validation import GEOSChemValidator, generate_synthetic_geoschem_data
from app.analysis.vortex_analysis import (
    vortex_hole_correlation, vortex_to_geojson, compute_vortex_indices
)
from app.analysis.prediction import (
    OzonePredictor, prediction_to_geojson
)
from app.cache.parquet_cache import get_cache_info, clear_cache, list_cache_keys

router = APIRouter()


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if date_str is None:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def _apply_filters(
    ds: xr.Dataset,
    loader: OzoneDataLoader,
    latitude_band: Optional[str] = None,
    season: Optional[str] = None,
) -> xr.Dataset:
    if latitude_band:
        try:
            ds = loader.filter_by_latitude_band(ds, latitude_band)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if season:
        try:
            ds = loader.filter_by_season(ds, season)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return ds


def _get_filtered_dataset(
    loader: OzoneDataLoader,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    lat_min: Optional[float] = None,
    lat_max: Optional[float] = None,
    lon_min: Optional[float] = None,
    lon_max: Optional[float] = None,
    latitude_band: Optional[str] = None,
    season: Optional[str] = None,
) -> xr.Dataset:
    time_range = None
    if start_date or end_date:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        time_range = (start, end)

    lat_range = None
    if lat_min is not None or lat_max is not None:
        lat_range = (lat_min if lat_min is not None else -90, lat_max if lat_max is not None else 90)

    lon_range = None
    if lon_min is not None or lon_max is not None:
        lon_range = (lon_min if lon_min is not None else -180, lon_max if lon_max is not None else 180)

    ds = loader.load_dataset(
        time_range=time_range,
        lat_range=lat_range,
        lon_range=lon_range,
    )

    ds = _apply_filters(ds, loader, latitude_band, season)

    return ds


@router.get("/grid/info", response_model=GridInfoResponse)
async def get_grid_info(loader: OzoneDataLoader = Depends(get_data_loader)):
    try:
        info = loader.get_global_grid_info()
        return GridInfoResponse(
            time_range=[str(info['time_range'][0]), str(info['time_range'][1])],
            lat_range=info['lat_range'],
            lon_range=info['lon_range'],
            time_steps=info['time_steps'],
            lat_points=info['lat_points'],
            lon_points=info['lon_points'],
            grid_resolution=info['grid_resolution'],
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading grid info: {str(e)}")


@router.post("/trend/point", response_model=TrendResponse)
async def get_trend_at_point(
    request: TrendRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            latitude_band=request.latitude_band,
            season=request.season,
        )

        result = get_point_trend(ds, request.lat, request.lon, alpha=request.alpha)

        return TrendResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing trend: {str(e)}")


@router.post("/trend/grid")
async def get_trend_grid(
    request: GridTrendRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            lat_min=request.lat_min,
            lat_max=request.lat_max,
            lon_min=request.lon_min,
            lon_max=request.lon_max,
            latitude_band=request.latitude_band,
            season=request.season,
        )

        trend_ds = compute_grid_trends(ds, alpha=request.alpha)
        geojson = trend_to_geojson(trend_ds, value_field=request.value_field)

        return geojson
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing grid trends: {str(e)}")


@router.post("/stl/point")
async def get_stl_at_point(
    request: STLRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            latitude_band=request.latitude_band,
            season=request.season,
        )

        result = decompose_point(ds, request.lat, request.lon, period=request.period)

        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing STL decomposition: {str(e)}")


@router.post("/stl/grid")
async def get_stl_grid(
    request: SeasonalAmplitudeRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            latitude_band=request.latitude_band,
            season=request.season,
        )

        stl_ds = compute_seasonal_amplitude(ds, period=request.period)
        geojson = stl_to_geojson(stl_ds, value_field=request.value_field)

        return geojson
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing seasonal amplitude: {str(e)}")


@router.post("/ozone-hole/timeseries")
async def get_hole_timeseries(
    request: OzoneHoleRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            latitude_band=request.latitude_band,
            season=request.season,
        )

        result = get_hole_area_timeseries(
            ds,
            threshold=request.threshold,
            lat_range=(request.lat_min, request.lat_max),
        )

        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing ozone hole timeseries: {str(e)}")


@router.post("/ozone-hole/geojson")
async def get_hole_geojson(
    request: OzoneHoleRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            latitude_band=request.latitude_band,
            season=request.season,
        )

        geojson = hole_mask_to_geojson(
            ds,
            time_idx=request.time_idx,
            threshold=request.threshold,
            lat_range=(request.lat_min, request.lat_max),
        )

        return geojson
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing ozone hole GeoJSON: {str(e)}")


@router.get("/ozone-hole/climatology")
async def get_hole_climatology_endpoint(
    threshold: float = Query(220.0, description="Ozone hole threshold in DU"),
    lat_min: float = Query(-90.0, description="Minimum latitude"),
    lat_max: float = Query(-50.0, description="Maximum latitude"),
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = loader.load_dataset()

        result = get_hole_climatology(
            ds,
            threshold=threshold,
            lat_range=(lat_min, lat_max),
        )

        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing ozone hole climatology: {str(e)}")


@router.post("/data/point", response_model=PointDataResponse)
async def get_data_at_point(
    request: PointDataRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            latitude_band=request.latitude_band,
            season=request.season,
        )

        point_data = ds['ozone'].sel(lat=request.lat, lon=request.lon, method='nearest')
        times = [str(t) for t in point_data['time'].values]
        ozone_values = point_data.values.tolist()

        return PointDataResponse(
            lat=float(point_data['lat'].values),
            lon=float(point_data['lon'].values),
            time=times,
            ozone=ozone_values,
            unit='DU'
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading point data: {str(e)}")


@router.get("/cache/info", response_model=CacheInfoResponse)
async def get_cache_info_endpoint():
    try:
        info = get_cache_info()
        return CacheInfoResponse(**info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cache info: {str(e)}")


@router.get("/cache/keys")
async def get_cache_keys():
    try:
        keys = list_cache_keys()
        return {"keys": keys}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing cache keys: {str(e)}")


@router.post("/cache/clear")
async def clear_cache_endpoint(request: CacheRequest):
    try:
        count = clear_cache(request.key)
        return {"message": f"Cleared {count} cache entries", "entries_cleared": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")


@router.get("/latitude-bands")
async def get_latitude_bands():
    return {
        "bands": {
            "global": "(-90, 90)",
            "tropics": "(-23.5, 23.5)",
            "mid_north": "(23.5, 66.5)",
            "mid_south": "(-66.5, -23.5)",
            "arctic": "(66.5, 90)",
            "antarctic": "(-90, -66.5)",
            "southern_hemisphere": "(-90, 0)",
            "northern_hemisphere": "(0, 90)",
        }
    }


@router.get("/seasons")
async def get_seasons():
    return {
        "seasons": {
            "DJF": "December, January, February (Southern Hemisphere summer)",
            "MAM": "March, April, May (Southern Hemisphere autumn)",
            "JJA": "June, July, August (Southern Hemisphere winter)",
            "SON": "September, October, November (Southern Hemisphere spring)",
        }
    }


@router.post("/geoschem/compare")
async def geoschem_compare(
    request: GEOSChemCompareRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            lat_min=request.lat_min,
            lat_max=request.lat_max,
            lon_min=request.lon_min,
            lon_max=request.lon_max,
            latitude_band=request.latitude_band,
            season=request.season,
        )

        validator = GEOSChemValidator(model_dir=request.geoschem_model_dir)

        try:
            validator.load_model_data(
                var_name=request.var_name,
                time_range=_parse_date_range(request.start_date, request.end_date),
                lat_range=(request.lat_min, request.lat_max) if request.lat_min else None,
                lon_range=(request.lon_min, request.lon_max) if request.lon_min else None,
            )
        except Exception as e:
            if request.use_synthetic:
                print(f"Using synthetic GEOS-Chem data: {e}")
                model_ds = generate_synthetic_geoschem_data(ds)
                validator.model_data = model_ds
            else:
                raise HTTPException(status_code=404, detail=f"Could not load GEOS-Chem data: {e}")

        result = validator.compare_datasets(ds, use_cache=False)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in GEOS-Chem comparison: {str(e)}")


@router.post("/geoschem/hole-compare")
async def geoschem_hole_compare(
    request: GEOSChemHoleCompareRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            lat_min=request.lat_min,
            lat_max=request.lat_max,
        )

        validator = GEOSChemValidator()

        try:
            validator.load_model_data(
                lat_range=(request.lat_min, request.lat_max),
            )
        except Exception as e:
            if request.use_synthetic:
                print(f"Using synthetic GEOS-Chem data: {e}")
                model_ds = generate_synthetic_geoschem_data(ds)
                validator.model_data = model_ds
            else:
                raise HTTPException(status_code=404, detail=f"Could not load GEOS-Chem data: {e}")

        result = validator.compare_hole_metrics(
            ds,
            threshold=request.threshold,
            lat_range=(request.lat_min, request.lat_max),
            use_cache=False,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in GEOS-Chem hole comparison: {str(e)}")


@router.post("/vortex/correlation")
async def vortex_hole_correlation_endpoint(
    request: VortexAnalysisRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            lat_min=request.lat_min,
            lat_max=request.lat_max,
            latitude_band=request.latitude_band,
        )

        result = vortex_hole_correlation(
            ds,
            threshold=request.threshold,
            lat_range=(request.lat_min, request.lat_max),
            season_filter=request.season_filter,
            use_cache=False,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in vortex-hole correlation: {str(e)}")


@router.post("/vortex/geojson")
async def vortex_geojson(
    request: VortexAnalysisRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            lat_min=request.lat_min,
            lat_max=request.lat_max,
            latitude_band=request.latitude_band,
        )

        geojson = vortex_to_geojson(
            ds,
            time_idx=request.time_idx,
            lat_range=(request.lat_min, request.lat_max),
        )
        return geojson
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating vortex GeoJSON: {str(e)}")


@router.post("/vortex/indices")
async def get_vortex_indices(
    request: VortexAnalysisRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            lat_min=request.lat_min,
            lat_max=request.lat_max,
            latitude_band=request.latitude_band,
        )

        vortex_ds = compute_vortex_indices(
            ds,
            lat_range=(request.lat_min, request.lat_max),
            use_cache=False,
        )

        return {
            "time": [str(t) for t in vortex_ds['time'].values],
            "vortex_area_km2": vortex_ds['vortex_area'].values.tolist(),
            "vortex_strength_du": vortex_ds['vortex_strength'].values.tolist(),
            "boundary_latitude": vortex_ds['boundary_latitude'].values.tolist(),
            "lat_range": [request.lat_min, request.lat_max],
            "unit_area": "km²",
            "unit_strength": "DU",
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing vortex indices: {str(e)}")


@router.post("/prediction/point")
async def predict_point(
    request: PredictionRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            start_date=request.start_date,
            end_date=request.end_date,
            latitude_band=request.latitude_band,
            season=request.season,
        )

        predictor = OzonePredictor()
        result = predictor.predict_future(
            ds,
            lat=request.lat,
            lon=request.lon,
            years_ahead=request.years_ahead,
            confidence_level=request.confidence_level,
            use_cache=False,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in point prediction: {str(e)}")


@router.post("/prediction/region")
async def predict_region(
    request: RegionPredictionRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            lat_min=request.lat_min,
            lat_max=request.lat_max,
            lon_min=request.lon_min,
            lon_max=request.lon_max,
            latitude_band=request.latitude_band,
        )

        predictor = OzonePredictor()
        pred_ds = predictor.predict_region(
            ds,
            years_ahead=request.years_ahead,
            lat_range=(request.lat_min, request.lat_max) if request.lat_min else None,
            lon_range=(request.lon_min, request.lon_max) if request.lon_min else None,
            confidence_level=request.confidence_level,
            use_cache=False,
        )

        geojson = prediction_to_geojson(
            pred_ds,
            time_idx=request.time_idx,
            value_field=request.value_field,
        )
        return geojson
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in region prediction: {str(e)}")


@router.post("/prediction/hole-area")
async def predict_hole_area(
    request: HolePredictionRequest,
    loader: OzoneDataLoader = Depends(get_data_loader)
):
    try:
        ds = _get_filtered_dataset(
            loader,
            lat_min=request.lat_min,
            lat_max=request.lat_max,
            latitude_band=request.latitude_band,
        )

        predictor = OzonePredictor()
        result = predictor.predict_hole_area(
            ds,
            years_ahead=request.years_ahead,
            threshold=request.threshold,
            lat_range=(request.lat_min, request.lat_max),
            confidence_level=request.confidence_level,
            use_cache=False,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in hole area prediction: {str(e)}")


def _parse_date_range(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[Tuple[datetime, datetime]]:
    if start_date or end_date:
        return (_parse_date(start_date), _parse_date(end_date))
    return None
