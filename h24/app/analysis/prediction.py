import numpy as np
import xarray as xr
from typing import Dict, Any, Optional, Tuple, List, Union
from datetime import datetime, timedelta
import pandas as pd
from scipy import stats
from scipy.optimize import curve_fit

from app.core.config import settings
from app.core.utils import sanitize_for_json
from app.analysis.trend import sen_slope, mann_kendall_test
from app.cache.parquet_cache import get_cache, set_cache


class OzonePredictor:
    def __init__(self, model_type: str = 'hybrid'):
        self.model_type = model_type
        self.models = {}
        self.feature_columns = []
        self.is_fitted = False

    def _prepare_features(self, times: np.ndarray, include_trend: bool = True) -> pd.DataFrame:
        dt_times = pd.to_datetime(times)
        df = pd.DataFrame(index=dt_times)

        df['year'] = df.index.year
        df['month'] = df.index.month
        df['day_of_year'] = df.index.dayofyear

        df['sin_month'] = np.sin(2 * np.pi * df['month'] / 12)
        df['cos_month'] = np.cos(2 * np.pi * df['month'] / 12)
        df['sin_doy'] = np.sin(2 * np.pi * df['day_of_year'] / 365.25)
        df['cos_doy'] = np.cos(2 * np.pi * df['day_of_year'] / 365.25)

        df['time_index'] = np.arange(len(df))

        if include_trend:
            df['trend'] = df['time_index']
            df['trend_squared'] = df['time_index'] ** 2

        for m in range(1, 13):
            df[f'month_{m}'] = (df['month'] == m).astype(int)

        return df

    def _piecewise_linear(self, x, a, b, c, d):
        return np.piecewise(
            x,
            [x < c, x >= c],
            [lambda x: a + b * x, lambda x: a + b * x + d * (x - c)]
        )

    def fit_point(
        self,
        times: np.ndarray,
        values: np.ndarray,
        lat: float,
        lon: float,
    ) -> Dict[str, Any]:
        valid_mask = ~np.isnan(values)
        if valid_mask.sum() < 24:
            return {"error": "Insufficient data for prediction (need at least 24 months)"}

        t_valid = times[valid_mask]
        y_valid = values[valid_mask]

        features = self._prepare_features(t_valid)
        X = features[['time_index', 'sin_month', 'cos_month', 'sin_doy', 'cos_doy']].values
        y = y_valid

        t_idx = np.arange(len(y_valid))

        sen_slope_val, sen_intercept = self._fit_sen_slope(t_idx, y_valid)

        season_features = features[['sin_month', 'cos_month', 'sin_doy', 'cos_doy']].values
        season_coeffs, season_intercept = self._fit_seasonal_model(season_features, y_valid - (sen_intercept + sen_slope_val * t_idx))

        breakpoint, piecewise_params = self._fit_piecewise_trend(t_idx, y_valid)

        mk_result = mann_kendall_test(y_valid)

        model_key = f"point_{lat}_{lon}"
        self.models[model_key] = {
            'sen_slope': sen_slope_val,
            'sen_intercept': sen_intercept,
            'season_coeffs': season_coeffs,
            'season_intercept': season_intercept,
            'breakpoint': breakpoint,
            'piecewise_params': piecewise_params,
            'mk_result': mk_result,
            'lat': lat,
            'lon': lon,
            'time_span': [float(t_idx.min()), float(t_idx.max())],
        }

        y_fit = self._predict_point_internal(
            t_idx,
            sen_slope_val,
            sen_intercept,
            season_coeffs,
            season_intercept,
            features.loc[valid_mask]
        )

        residuals = y_valid - y_fit
        rmse = np.sqrt(np.mean(residuals ** 2))
        mae = np.mean(np.abs(residuals))
        r2 = 1 - np.sum(residuals ** 2) / np.sum((y_valid - np.mean(y_valid)) ** 2)

        self.is_fitted = True

        return {
            'lat': lat,
            'lon': lon,
            'sen_slope': float(sen_slope_val),
            'sen_intercept': float(sen_intercept),
            'breakpoint_index': int(breakpoint) if breakpoint is not None else None,
            'mk_p_value': float(mk_result['p']),
            'mk_significant': bool(mk_result['h']),
            'fit_metrics': {
                'rmse': float(rmse),
                'mae': float(mae),
                'r2': float(r2),
                'n_samples': int(len(y_valid)),
            },
            'residual_std': float(np.std(residuals)),
        }

    def _fit_sen_slope(self, x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        slope = sen_slope(y, x=x)
        intercept = np.median(y - slope * x)
        return slope, intercept

    def _fit_seasonal_model(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, float]:
        X_bias = np.column_stack([X, np.ones(len(X))])
        coeffs, _, _, _ = np.linalg.lstsq(X_bias, y, rcond=None)
        return coeffs[:-1], coeffs[-1]

    def _fit_piecewise_trend(self, x: np.ndarray, y: np.ndarray) -> Tuple[Optional[int], Optional[np.ndarray]]:
        if len(x) < 60:
            return None, None

        try:
            best_break = None
            best_rss = np.inf
            best_params = None

            for break_candidate in range(20, len(x) - 20):
                try:
                    p0 = [np.mean(y), 0, break_candidate, 0]
                    params, _ = curve_fit(
                        self._piecewise_linear,
                        x, y,
                        p0=p0,
                        maxfev=10000
                    )
                    y_pred = self._piecewise_linear(x, *params)
                    rss = np.sum((y - y_pred) ** 2)
                    if rss < best_rss:
                        best_rss = rss
                        best_break = int(params[2])
                        best_params = params
                except Exception:
                    continue

            return best_break, best_params
        except Exception:
            return None, None

    def _predict_point_internal(
        self,
        t_idx: np.ndarray,
        sen_slope: float,
        sen_intercept: float,
        season_coeffs: np.ndarray,
        season_intercept: float,
        features: pd.DataFrame,
    ) -> np.ndarray:
        trend_pred = sen_intercept + sen_slope * t_idx

        season_features = features[['sin_month', 'cos_month', 'sin_doy', 'cos_doy']].values
        season_pred = season_intercept + season_features @ season_coeffs

        return trend_pred + season_pred

    def predict_point(
        self,
        times: np.ndarray,
        lat: float,
        lon: float,
        confidence_level: float = 0.95,
    ) -> Dict[str, Any]:
        model_key = f"point_{lat}_{lon}"
        if model_key not in self.models:
            return {"error": "Model not fitted. Call fit_point first."}

        model = self.models[model_key]
        features = self._prepare_features(times)

        original_span = model['time_span']
        future_mask = features['time_index'].values > original_span[1]

        t_idx = features['time_index'].values
        y_pred = self._predict_point_internal(
            t_idx,
            model['sen_slope'],
            model['sen_intercept'],
            model['season_coeffs'],
            model['season_intercept'],
            features,
        )

        z_score = stats.norm.ppf((1 + confidence_level) / 2)
        residual_std = model.get('residual_std', 10.0)

        n_historical = int(original_span[1] - original_span[0] + 1)
        n_future = np.sum(future_mask) if np.any(future_mask) else 0
        uncertainty_scale = np.sqrt(1 + (n_future / max(n_historical, 1)) * 0.2)
        margin_of_error = z_score * residual_std * uncertainty_scale

        lower_bound = y_pred - margin_of_error
        upper_bound = y_pred + margin_of_error

        dt_times = pd.to_datetime(times)

        result = {
            'lat': lat,
            'lon': lon,
            'time': [str(t) for t in dt_times],
            'predicted_ozone_du': y_pred.tolist(),
            'lower_bound_du': lower_bound.tolist(),
            'upper_bound_du': upper_bound.tolist(),
            'confidence_level': confidence_level,
            'margin_of_error_du': float(margin_of_error),
            'is_future': future_mask.tolist(),
            'model_type': self.model_type,
            'trend_slope_du_per_year': float(model['sen_slope'] * 12),
            'has_breakpoint': model['breakpoint'] is not None,
            'breakpoint_index': model['breakpoint'],
        }

        return sanitize_for_json(result)

    def predict_future(
        self,
        ds: xr.Dataset,
        lat: float,
        lon: float,
        years_ahead: int = 5,
        confidence_level: float = 0.95,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        cache_key = f"prediction_{lat}_{lon}_{years_ahead}_{confidence_level}"
        cache_key = cache_key.replace('.', '_').replace('-', '_')

        if use_cache:
            cached = get_cache(cache_key)
            if cached is not None:
                return cached

        point_data = ds['ozone'].sel(lat=lat, lon=lon, method='nearest')
        historical_times = ds['time'].values
        historical_values = point_data.values

        fit_result = self.fit_point(historical_times, historical_values, lat, lon)
        if 'error' in fit_result:
            return fit_result

        last_date = pd.to_datetime(historical_times[-1])
        future_dates = pd.date_range(
            start=last_date + pd.DateOffset(months=1),
            periods=years_ahead * 12,
            freq='MS'
        )

        all_times = np.concatenate([historical_times, future_dates.values])

        prediction = self.predict_point(all_times, lat, lon, confidence_level)

        historical_mask = ~np.array(prediction['is_future'])
        future_mask = np.array(prediction['is_future'])

        y_hist = np.array(prediction['predicted_ozone_du'])[historical_mask]
        y_true = historical_values[~np.isnan(historical_values)]
        valid_hist = ~np.isnan(historical_values)
        if len(y_true) > 0 and len(y_hist) == len(valid_hist):
            hist_rmse = np.sqrt(np.mean((y_hist[valid_hist] - y_true) ** 2))
        else:
            hist_rmse = None

        future_pred = np.array(prediction['predicted_ozone_du'])[future_mask]
        future_lower = np.array(prediction['lower_bound_du'])[future_mask]
        future_upper = np.array(prediction['upper_bound_du'])[future_mask]
        future_times = np.array(prediction['time'])[future_mask]

        annual_means = []
        years = np.unique([pd.to_datetime(t).year for t in future_times])
        for year in years:
            year_mask = np.array([pd.to_datetime(t).year == year for t in future_times])
            if np.any(year_mask):
                annual_means.append({
                    'year': int(year),
                    'mean_ozone_du': float(np.mean(future_pred[year_mask])),
                    'min_ozone_du': float(np.min(future_pred[year_mask])),
                    'max_ozone_du': float(np.max(future_pred[year_mask])),
                    'mean_lower_du': float(np.mean(future_lower[year_mask])),
                    'mean_upper_du': float(np.mean(future_upper[year_mask])),
                })

        result = {
            'lat': float(point_data['lat'].values),
            'lon': float(point_data['lon'].values),
            'years_ahead': years_ahead,
            'confidence_level': confidence_level,
            'historical': {
                'time': [str(t) for t in historical_times],
                'observed_ozone_du': historical_values.tolist(),
                'fitted_ozone_du': y_hist.tolist(),
                'fit_rmse_du': float(hist_rmse) if hist_rmse is not None else None,
            },
            'prediction': {
                'time': future_times.tolist(),
                'predicted_ozone_du': future_pred.tolist(),
                'lower_bound_du': future_lower.tolist(),
                'upper_bound_du': future_upper.tolist(),
            },
            'annual_predictions': annual_means,
            'trend': {
                'historical_slope_du_per_year': float(fit_result['sen_slope'] * 12),
                'predicted_mean_2020s': float(np.mean(future_pred[:12])) if len(future_pred) >= 12 else None,
                'predicted_mean_end': float(np.mean(future_pred[-12:])) if len(future_pred) >= 12 else None,
                'expected_change_du': float(np.mean(future_pred[-12:]) - np.mean(future_pred[:12])) if len(future_pred) >= 24 else None,
            },
            'model_info': {
                'type': self.model_type,
                'n_samples': fit_result['fit_metrics']['n_samples'],
                'r2': fit_result['fit_metrics']['r2'],
                'rmse': fit_result['fit_metrics']['rmse'],
                'mk_significant': fit_result['mk_significant'],
                'has_breakpoint': fit_result['breakpoint_index'] is not None,
            },
        }

        if use_cache:
            set_cache(cache_key, result)

        return sanitize_for_json(result)

    def predict_region(
        self,
        ds: xr.Dataset,
        years_ahead: int = 5,
        lat_range: Optional[Tuple[float, float]] = None,
        lon_range: Optional[Tuple[float, float]] = None,
        confidence_level: float = 0.95,
        use_cache: bool = True,
    ) -> xr.Dataset:
        cache_key = f"region_prediction_{years_ahead}_{lat_range}_{lon_range}_{confidence_level}"
        cache_key = cache_key.replace(':', '_').replace('-', '_').replace('.', '_').replace(' ', '_').replace('(', '_').replace(')', '_')

        if use_cache:
            cached = get_cache(cache_key)
            if cached is not None:
                return cached

        if lat_range:
            ds = ds.sel(lat=slice(*lat_range))
        if lon_range:
            ds = ds.sel(lon=slice(*lon_range))

        lats = ds['lat'].values
        lons = ds['lon'].values

        last_date = pd.to_datetime(ds['time'].values[-1])
        future_dates = pd.date_range(
            start=last_date + pd.DateOffset(months=1),
            periods=years_ahead * 12,
            freq='MS'
        )

        prediction_mean = np.zeros((len(future_dates), len(lats), len(lons)))
        prediction_lower = np.zeros_like(prediction_mean)
        prediction_upper = np.zeros_like(prediction_mean)
        trend_slopes = np.zeros((len(lats), len(lons)))

        for i, lat in enumerate(lats):
            for j, lon in enumerate(lons):
                try:
                    point_result = self.predict_future(
                        ds, lat, lon, years_ahead, confidence_level, use_cache=False
                    )
                    if 'error' not in point_result:
                        prediction_mean[:, i, j] = point_result['prediction']['predicted_ozone_du']
                        prediction_lower[:, i, j] = point_result['prediction']['lower_bound_du']
                        prediction_upper[:, i, j] = point_result['prediction']['upper_bound_du']
                        trend_slopes[i, j] = point_result['trend']['historical_slope_du_per_year']
                    else:
                        prediction_mean[:, i, j] = np.nan
                        prediction_lower[:, i, j] = np.nan
                        prediction_upper[:, i, j] = np.nan
                        trend_slopes[i, j] = np.nan
                except Exception as e:
                    print(f"Warning: Failed to predict at ({lat}, {lon}): {e}")
                    prediction_mean[:, i, j] = np.nan
                    prediction_lower[:, i, j] = np.nan
                    prediction_upper[:, i, j] = np.nan
                    trend_slopes[i, j] = np.nan

        result_ds = xr.Dataset(
            {
                'predicted_ozone': (['time', 'lat', 'lon'], prediction_mean),
                'lower_bound': (['time', 'lat', 'lon'], prediction_lower),
                'upper_bound': (['time', 'lat', 'lon'], prediction_upper),
                'trend_slope': (['lat', 'lon'], trend_slopes),
            },
            coords={
                'time': future_dates.values,
                'lat': lats,
                'lon': lons,
            },
            attrs={
                'years_ahead': years_ahead,
                'confidence_level': confidence_level,
                'model_type': self.model_type,
                'unit': 'DU',
            },
        )

        if use_cache:
            set_cache(cache_key, result_ds)

        return result_ds

    def predict_hole_area(
        self,
        ds: xr.Dataset,
        years_ahead: int = 5,
        threshold: float = 220.0,
        lat_range: Tuple[float, float] = (-90, -50),
        confidence_level: float = 0.95,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        from app.analysis.ozone_hole import detect_ozone_hole, calculate_grid_area

        cache_key = f"hole_prediction_{years_ahead}_{threshold}_{lat_range}_{confidence_level}"
        cache_key = cache_key.replace('.', '_').replace('-', '_').replace(' ', '_')

        if use_cache:
            cached = get_cache(cache_key)
            if cached is not None:
                return cached

        pred_ds = self.predict_region(
            ds, years_ahead, lat_range=lat_range, confidence_level=confidence_level, use_cache=False
        )

        grid_areas = calculate_grid_area(pred_ds['lat'].values, pred_ds['lon'].values)
        area_da = xr.DataArray(grid_areas, dims=['lat', 'lon'], coords={'lat': pred_ds['lat'].values, 'lon': pred_ds['lon'].values})

        def compute_hole_area(ozone_da):
            mask = ozone_da < threshold
            hole_area_m2 = (mask * area_da).sum(dim=['lat', 'lon'])
            return hole_area_m2 / 1e6

        mean_area = compute_hole_area(pred_ds['predicted_ozone'])
        lower_area = compute_hole_area(pred_ds['upper_bound'])
        upper_area = compute_hole_area(pred_ds['lower_bound'])

        times = pd.to_datetime(pred_ds['time'].values)

        annual_max = []
        years = np.unique([t.year for t in times])
        for year in years:
            year_mask = np.array([t.year == year for t in times])
            if np.any(year_mask):
                max_idx = np.nanargmax(mean_area.values[year_mask])
                max_time_idx = np.where(year_mask)[0][max_idx]
                annual_max.append({
                    'year': int(year),
                    'max_area_km2': float(mean_area.values[max_time_idx]),
                    'max_area_lower_km2': float(lower_area.values[max_time_idx]),
                    'max_area_upper_km2': float(upper_area.values[max_time_idx]),
                    'max_date': str(times[max_time_idx]),
                })

        result = {
            'time': [str(t) for t in times],
            'predicted_hole_area_km2': mean_area.values.tolist(),
            'lower_bound_km2': lower_area.values.tolist(),
            'upper_bound_km2': upper_area.values.tolist(),
            'annual_maxima': annual_max,
            'threshold': threshold,
            'lat_range': lat_range,
            'confidence_level': confidence_level,
            'years_ahead': years_ahead,
            'unit': 'km²',
            'trend': {
                'average_area_2020s_km2': float(np.mean(mean_area.values[:12])) if len(mean_area.values) >= 12 else None,
                'average_area_end_km2': float(np.mean(mean_area.values[-12:])) if len(mean_area.values) >= 12 else None,
            },
        }

        if use_cache:
            set_cache(cache_key, result)

        return sanitize_for_json(result)


def prediction_to_geojson(
    pred_ds: xr.Dataset,
    time_idx: Optional[int] = None,
    value_field: str = 'predicted_ozone',
) -> Dict[str, Any]:
    if time_idx is None:
        time_idx = -1

    lats = pred_ds['lat'].values
    lons = pred_ds['lon'].values
    resolution = (lats[1] - lats[0]) / 2 if len(lats) > 1 else 0.5

    features = []

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            value = float(pred_ds[value_field][time_idx, i, j].values)
            if np.isnan(value):
                continue

            lower = float(pred_ds['lower_bound'][time_idx, i, j].values) if 'lower_bound' in pred_ds else None
            upper = float(pred_ds['upper_bound'][time_idx, i, j].values) if 'upper_bound' in pred_ds else None
            trend = float(pred_ds['trend_slope'][i, j].values) if 'trend_slope' in pred_ds else None

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
                    'lower_bound_du': lower,
                    'upper_bound_du': upper,
                    'trend_slope_du_per_year': trend,
                    'uncertainty_range_du': upper - lower if lower is not None and upper is not None else None,
                },
            }
            features.append(feature)

    return sanitize_for_json({
        'type': 'FeatureCollection',
        'features': features,
        'properties': {
            'time': str(pred_ds['time'].values[time_idx]),
            'value_field': value_field,
            'years_ahead': pred_ds.attrs.get('years_ahead', None),
            'confidence_level': pred_ds.attrs.get('confidence_level', None),
            'unit': 'DU',
        },
    })
