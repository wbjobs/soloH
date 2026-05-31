from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class TrendRequest(BaseModel):
    lat: float = Field(..., description="Latitude in degrees (-90 to 90)", ge=-90, le=90)
    lon: float = Field(..., description="Longitude in degrees (-180 to 180)", ge=-180, le=180)
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    alpha: float = Field(0.05, description="Significance level for Mann-Kendall test", gt=0, lt=1)
    latitude_band: Optional[str] = Field(None, description="Filter by latitude band: global, tropics, mid_north, mid_south, arctic, antarctic")
    season: Optional[str] = Field(None, description="Filter by season: DJF, MAM, JJA, SON")


class GridTrendRequest(BaseModel):
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    alpha: float = Field(0.05, description="Significance level for Mann-Kendall test", gt=0, lt=1)
    value_field: str = Field("sen_slope", description="Field to return in GeoJSON: sen_slope, mk_slope, p_value, z_stat, tau")
    latitude_band: Optional[str] = Field(None, description="Filter by latitude band")
    season: Optional[str] = Field(None, description="Filter by season")
    lat_min: Optional[float] = Field(None, description="Minimum latitude", ge=-90, le=90)
    lat_max: Optional[float] = Field(None, description="Maximum latitude", ge=-90, le=90)
    lon_min: Optional[float] = Field(None, description="Minimum longitude", ge=-180, le=180)
    lon_max: Optional[float] = Field(None, description="Maximum longitude", ge=-180, le=180)


class STLRequest(BaseModel):
    lat: float = Field(..., description="Latitude in degrees (-90 to 90)", ge=-90, le=90)
    lon: float = Field(..., description="Longitude in degrees (-180 to 180)", ge=-180, le=180)
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    period: int = Field(12, description="Period for STL decomposition", ge=2)
    latitude_band: Optional[str] = Field(None, description="Filter by latitude band")
    season: Optional[str] = Field(None, description="Filter by season")


class SeasonalAmplitudeRequest(BaseModel):
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    period: int = Field(12, description="Period for STL decomposition", ge=2)
    value_field: str = Field("seasonal_amplitude", description="Field to return in GeoJSON")
    latitude_band: Optional[str] = Field(None, description="Filter by latitude band")
    season: Optional[str] = Field(None, description="Filter by season")


class OzoneHoleRequest(BaseModel):
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    threshold: float = Field(220.0, description="Ozone hole threshold in DU", gt=0)
    lat_min: float = Field(-90.0, description="Minimum latitude for hole detection", ge=-90, le=90)
    lat_max: float = Field(-50.0, description="Maximum latitude for hole detection", ge=-90, le=90)
    time_idx: Optional[int] = Field(None, description="Time index for hole mask GeoJSON (default: latest)")
    latitude_band: Optional[str] = Field(None, description="Filter by latitude band")
    season: Optional[str] = Field(None, description="Filter by season")


class PointDataRequest(BaseModel):
    lat: float = Field(..., description="Latitude in degrees (-90 to 90)", ge=-90, le=90)
    lon: float = Field(..., description="Longitude in degrees (-180 to 180)", ge=-180, le=180)
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    latitude_band: Optional[str] = Field(None, description="Filter by latitude band")
    season: Optional[str] = Field(None, description="Filter by season")


class CacheRequest(BaseModel):
    key: Optional[str] = Field(None, description="Specific cache key to clear (if not provided, clear all)")


class TrendResponse(BaseModel):
    lat: float
    lon: float
    sen_slope: float
    mk_slope: float
    intercept: float
    p_value: float
    z_stat: float
    tau: float
    significant: bool
    trend_direction: str
    unit: str
    alpha: float


class PointDataResponse(BaseModel):
    lat: float
    lon: float
    time: List[str]
    ozone: List[float]
    unit: str


class GridInfoResponse(BaseModel):
    time_range: List[str]
    lat_range: List[float]
    lon_range: List[float]
    time_steps: int
    lat_points: int
    lon_points: int
    grid_resolution: float


class CacheInfoResponse(BaseModel):
    cache_dir: str
    enabled: bool
    ttl_hours: int
    num_cache_entries: int
    total_size_bytes: int
    total_size_mb: float


class GEOSChemCompareRequest(BaseModel):
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    lat_min: Optional[float] = Field(None, description="Minimum latitude", ge=-90, le=90)
    lat_max: Optional[float] = Field(None, description="Maximum latitude", ge=-90, le=90)
    lon_min: Optional[float] = Field(None, description="Minimum longitude", ge=-180, le=180)
    lon_max: Optional[float] = Field(None, description="Maximum longitude", ge=-180, le=180)
    latitude_band: Optional[str] = Field(None, description="Filter by latitude band")
    season: Optional[str] = Field(None, description="Filter by season")
    geoschem_model_dir: Optional[str] = Field(None, description="Directory containing GEOS-Chem model output")
    var_name: str = Field("O3", description="Variable name in GEOS-Chem files")
    use_synthetic: bool = Field(True, description="Use synthetic model data if real GEOS-Chem data not available")


class GEOSChemHoleCompareRequest(BaseModel):
    threshold: float = Field(220.0, description="Ozone hole threshold in DU", gt=0)
    lat_min: float = Field(-90.0, description="Minimum latitude", ge=-90, le=90)
    lat_max: float = Field(-50.0, description="Maximum latitude", ge=-90, le=90)
    use_synthetic: bool = Field(True, description="Use synthetic model data if real GEOS-Chem data not available")


class VortexAnalysisRequest(BaseModel):
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    threshold: float = Field(220.0, description="Ozone hole threshold in DU", gt=0)
    lat_min: float = Field(-90.0, description="Minimum latitude", ge=-90, le=90)
    lat_max: float = Field(-50.0, description="Maximum latitude", ge=-90, le=90)
    season_filter: Optional[str] = Field(None, description="Filter by season: DJF, MAM, JJA, SON")
    latitude_band: Optional[str] = Field(None, description="Filter by latitude band")
    time_idx: Optional[int] = Field(None, description="Time index for vortex GeoJSON (default: latest)")


class PredictionRequest(BaseModel):
    lat: float = Field(..., description="Latitude in degrees (-90 to 90)", ge=-90, le=90)
    lon: float = Field(..., description="Longitude in degrees (-180 to 180)", ge=-180, le=180)
    years_ahead: int = Field(5, description="Number of years to predict", ge=1, le=20)
    confidence_level: float = Field(0.95, description="Confidence level", gt=0, lt=1)
    start_date: Optional[str] = Field(None, description="Start date for historical data")
    end_date: Optional[str] = Field(None, description="End date for historical data")
    latitude_band: Optional[str] = Field(None, description="Filter by latitude band")
    season: Optional[str] = Field(None, description="Filter by season")


class RegionPredictionRequest(BaseModel):
    years_ahead: int = Field(5, description="Number of years to predict", ge=1, le=20)
    confidence_level: float = Field(0.95, description="Confidence level", gt=0, lt=1)
    lat_min: Optional[float] = Field(None, description="Minimum latitude", ge=-90, le=90)
    lat_max: Optional[float] = Field(None, description="Maximum latitude", ge=-90, le=90)
    lon_min: Optional[float] = Field(None, description="Minimum longitude", ge=-180, le=180)
    lon_max: Optional[float] = Field(None, description="Maximum longitude", ge=-180, le=180)
    latitude_band: Optional[str] = Field(None, description="Filter by latitude band")
    value_field: str = Field("predicted_ozone", description="Field to return in GeoJSON")
    time_idx: Optional[int] = Field(None, description="Time index for prediction GeoJSON (default: latest)")


class HolePredictionRequest(BaseModel):
    years_ahead: int = Field(5, description="Number of years to predict", ge=1, le=20)
    confidence_level: float = Field(0.95, description="Confidence level", gt=0, lt=1)
    threshold: float = Field(220.0, description="Ozone hole threshold in DU", gt=0)
    lat_min: float = Field(-90.0, description="Minimum latitude", ge=-90, le=90)
    lat_max: float = Field(-50.0, description="Maximum latitude", ge=-90, le=90)
    latitude_band: Optional[str] = Field(None, description="Filter by latitude band")
