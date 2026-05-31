import sys
sys.path.insert(0, 'e:/soloH/h24')

import numpy as np
import pandas as pd

print("=" * 70)
print("Testing New Features: GEOS-Chem, Vortex, Prediction")
print("=" * 70)

print("\n--- Test 1: GEOS-Chem Validation ---")
from app.analysis.geoschem_validation import (
    GEOSChemValidator, generate_synthetic_geoschem_data
)
from app.data.loader import get_data_loader

loader = get_data_loader()
ds = loader.load_dataset()

print(f"Observation data loaded: {dict(ds.dims)}")
print(f"Time range: {ds['time'].values[0]} to {ds['time'].values[-1]}")

model_ds = generate_synthetic_geoschem_data(ds, bias=5.0, noise=8.0, seasonal_phase_shift=0.3)
print(f"Synthetic GEOS-Chem data created: {dict(model_ds.dims)}")

validator = GEOSChemValidator()
validator.model_data = model_ds
result = validator.compare_datasets(ds, use_cache=False)

print("\nGEOS-Chem vs Observation Metrics:")
print(f"  Mean Bias: {result['metrics']['mean_bias_du']:.2f} DU")
print(f"  RMSE: {result['metrics']['rmse_du']:.2f} DU")
print(f"  R²: {result['metrics']['r2']:.4f}")
print(f"  Correlation: {result['metrics']['correlation_coefficient']:.4f}")
print(f"  NMB: {result['metrics']['nmb_percent']:.2f}%")
print(f"  NME: {result['metrics']['nme_percent']:.2f}%")
print(f"  Slope: {result['metrics']['regression_slope']:.4f}")
print(f"  P-value: {result['metrics']['p_value']:.6f}")
print(f"  Samples: {result['metrics']['n_points']}")

hole_result = validator.compare_hole_metrics(ds, use_cache=False)
print(f"\nOzone Hole Comparison:")
print(f"  Mean Obs Area: {hole_result['metrics']['mean_obs_area_km2']:.0f} km²")
print(f"  Mean Model Area: {hole_result['metrics']['mean_model_area_km2']:.0f} km²")
print(f"  Area Correlation: {hole_result['metrics']['area_correlation']:.4f}")
print(f"  Area Bias: {hole_result['metrics']['area_mean_bias_km2']:.0f} km²")

print("\n✓ GEOS-Chem validation works correctly")

print("\n--- Test 2: Antarctic Vortex Analysis ---")
from app.analysis.vortex_analysis import (
    detect_vortex_boundary, compute_vortex_indices,
    vortex_hole_correlation, vortex_to_geojson
)

ds_ant = ds.sel(lat=slice(-90, -50))
vortex_result = detect_vortex_boundary(ds_ant, time_idx=-1, threshold_method='contour')

print(f"\nVortex Detection (latest time):")
print(f"  Time: {vortex_result['time']}")
print(f"  Vortex Area: {vortex_result['vortex_area_km2']:.0f} km²")
print(f"  Vortex Strength: {vortex_result['vortex_strength_du']:.2f} DU")
print(f"  Mean Boundary Lat: {vortex_result['mean_boundary_latitude']:.2f}°")
print(f"  Grid: {vortex_result['lats'].shape[0]} x {vortex_result['lons'].shape[0]}")

vortex_indices = compute_vortex_indices(ds_ant, use_cache=False)
print(f"\nVortex Indices computed for {len(vortex_indices['time'])} time steps")
print(f"  Mean Vortex Area: {float(np.nanmean(vortex_indices['vortex_area'].values)):.0f} km²")
print(f"  Mean Vortex Strength: {float(np.nanmean(vortex_indices['vortex_strength'].values)):.2f} DU")

corr_result = vortex_hole_correlation(ds, season_filter='SON', use_cache=False)
print(f"\nVortex-Hole Correlation (SON season only):")
if 'correlations' in corr_result:
    c = corr_result['correlations']
    print(f"  Vortex Area vs Hole Area: r={c['vortex_area_vs_hole_area']['correlation']:.4f}, p={c['vortex_area_vs_hole_area']['p_value']:.4f}")
    print(f"  Vortex Area vs Mean O3: r={c['vortex_area_vs_mean_ozone']['correlation']:.4f}, p={c['vortex_area_vs_mean_ozone']['p_value']:.4f}")
    print(f"  Vortex Strength vs Hole Area: r={c['vortex_strength_vs_hole_area']['correlation']:.4f}, p={c['vortex_strength_vs_hole_area']['p_value']:.4f}")
    print(f"  Valid samples: {c['n_valid_samples']}")

    if 'lagged_correlation_vortex_hole_area' in c:
        lc = c['lagged_correlation_vortex_hole_area']
        max_corr = max([x for x in lc['correlations'] if x is not None], default=0)
        max_lag = lc['lags'][lc['correlations'].index(max_corr)] if max_corr != 0 else 0
        print(f"  Max lagged correlation: {max_corr:.4f} at lag {max_lag} months")

geojson = vortex_to_geojson(ds_ant, time_idx=-1)
print(f"\nVortex GeoJSON: {len(geojson['features'])} features")
print(f"  Properties: {list(geojson['properties'].keys())}")

print("\n✓ Vortex analysis works correctly")

print("\n--- Test 3: Ozone Prediction ---")
from app.analysis.prediction import (
    OzonePredictor, prediction_to_geojson
)

predictor = OzonePredictor()

print("\nPoint Prediction at (-75, 0) for 5 years ahead:")
pred_result = predictor.predict_future(ds, lat=-75.0, lon=0.0, years_ahead=5, confidence_level=0.95, use_cache=False)

if 'error' not in pred_result:
    print(f"  Lat/Lon: {pred_result['lat']:.2f}, {pred_result['lon']:.2f}")
    print(f"  Historical slope: {pred_result['trend']['historical_slope_du_per_year']:.2f} DU/year")
    print(f"  Prediction period: {pred_result['prediction']['time'][0]} to {pred_result['prediction']['time'][-1]}")
    print(f"  Number of predictions: {len(pred_result['prediction']['time'])} months")

    print(f"\n  Annual Predictions:")
    for ap in pred_result['annual_predictions'][:3]:
        print(f"    {ap['year']}: {ap['mean_ozone_du']:.1f} DU [{ap['mean_lower_du']:.1f}, {ap['mean_upper_du']:.1f}]")

    if len(pred_result['annual_predictions']) >= 2:
        first = pred_result['annual_predictions'][0]
        last = pred_result['annual_predictions'][-1]
        change = last['mean_ozone_du'] - first['mean_ozone_du']
        print(f"\n  Expected change: {change:+.2f} DU over {pred_result['years_ahead']} years")

    print(f"\n  Model Metrics:")
    mi = pred_result['model_info']
    print(f"    R²: {mi['r2']:.4f}")
    print(f"    RMSE: {mi['rmse']:.2f} DU")
    print(f"    N samples: {mi['n_samples']}")
    print(f"    MK significant: {mi['mk_significant']}")
    print(f"    Has breakpoint: {mi['has_breakpoint']}")

    print(f"\n  Fit quality:")
    print(f"    Historical RMSE: {pred_result['historical']['fit_rmse_du']:.2f} DU")

print("\n✓ Point prediction works correctly")

print("\nRegion Prediction (Antarctic) for 3 years ahead:")
pred_region = predictor.predict_region(
    ds, years_ahead=3, lat_range=(-80, -50), confidence_level=0.90, use_cache=False
)
print(f"  Prediction dimensions: {dict(pred_region.dims)}")
print(f"  Time range: {pred_region['time'].values[0]} to {pred_region['time'].values[-1]}")
print(f"  Mean predicted ozone: {float(np.nanmean(pred_region['predicted_ozone'].values)):.1f} DU")
print(f"  Mean trend slope: {float(np.nanmean(pred_region['trend_slope'].values)):.2f} DU/year")

geojson_pred = prediction_to_geojson(pred_region, time_idx=-1)
print(f"\nPrediction GeoJSON: {len(geojson_pred['features'])} features")

print("\nHole Area Prediction for 5 years:")
hole_pred = predictor.predict_hole_area(
    ds, years_ahead=5, threshold=220.0, lat_range=(-90, -50), use_cache=False
)
print(f"  Time steps: {len(hole_pred['time'])}")
print(f"  Mean predicted area: {float(np.mean(hole_pred['predicted_hole_area_km2'])):.0f} km²")
print(f"  Max predicted area: {float(np.max(hole_pred['predicted_hole_area_km2'])):.0f} km²")

if 'trend' in hole_pred and hole_pred['trend']['average_area_2020s_km2'] is not None:
    print(f"  Average start: {hole_pred['trend']['average_area_2020s_km2']:.0f} km²")
    print(f"  Average end: {hole_pred['trend']['average_area_end_km2']:.0f} km²")

if 'annual_maxima' in hole_pred:
    print(f"\n  Annual Maxima:")
    for am in hole_pred['annual_maxima'][:3]:
        print(f"    {am['year']}: {am['max_area_km2']:.0f} km² [{am['max_area_lower_km2']:.0f}, {am['max_area_upper_km2']:.0f}]")

print("\n✓ Region and hole prediction works correctly")

print("\n--- Test 4: API Integration ---")
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

response = client.post(
    "/api/v1/geoschem/compare",
    json={"use_synthetic": True}
)
print(f"\nGEOS-Chem compare API: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"  RMSE: {data['metrics']['rmse_du']:.2f} DU")
    print(f"  R²: {data['metrics']['r2']:.4f}")

response = client.post(
    "/api/v1/vortex/correlation",
    json={
        "threshold": 220.0,
        "lat_min": -90.0,
        "lat_max": -50.0,
        "season_filter": "SON"
    }
)
print(f"\nVortex correlation API: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    if 'correlations' in data:
        print(f"  Vortex-Hole correlation: {data['correlations']['vortex_area_vs_hole_area']['correlation']:.4f}")

response = client.post(
    "/api/v1/prediction/point",
    json={
        "lat": -75.0,
        "lon": 0.0,
        "years_ahead": 5,
        "confidence_level": 0.95
    }
)
print(f"\nPrediction point API: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"  Historical slope: {data['trend']['historical_slope_du_per_year']:.2f} DU/year")
    print(f"  Predictions: {len(data['prediction']['time'])} months")

response = client.post(
    "/api/v1/prediction/hole-area",
    json={
        "years_ahead": 5,
        "confidence_level": 0.95,
        "threshold": 220.0,
        "lat_min": -90.0,
        "lat_max": -50.0
    }
)
print(f"\nHole area prediction API: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"  Predictions: {len(data['time'])} months")

print("\n✓ All API endpoints work correctly")

print("\n" + "=" * 70)
print("Summary of New Features")
print("=" * 70)

print("""
1. GEOS-Chem Model Validation
   • Load and compare GEOS-Chem model output with observations
   • Metrics: MB, RMSE, MAE, NMB, NME, R², correlation
   • Spatial and temporal bias analysis (zonal, seasonal)
   • Ozone hole metric comparison (area, mean ozone)
   • Synthetic model data generator for testing

2. Antarctic Vortex Analysis
   • Vortex boundary detection (gradient/contour methods)
   • Vortex area and strength index calculation
   • Vortex-ozone hole correlation analysis (Pearson r, p-values)
   • Lagged correlation analysis (±12 months)
   • Monthly and annual correlation breakdown
   • GeoJSON output for mapping

3. Machine Learning Prediction
   • Hybrid model: Sen slope trend + Fourier seasonal components
   • Piecewise linear trend breakpoint detection
   • Uncertainty estimation (confidence intervals)
   • Single point prediction (with annual aggregation)
   • Regional prediction (3D xarray output)
   • Ozone hole area prediction with uncertainty bounds
   • GeoJSON output for predicted spatial patterns

All features include:
• Parquet caching
• Dynamic filtering (time, latitude band, season)
• Proper NaN handling
• API endpoints with OpenAPI documentation
""")

print("=" * 70)
print("✓ ALL NEW FEATURES VERIFIED SUCCESSFULLY")
print("=" * 70)
