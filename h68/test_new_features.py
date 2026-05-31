"""Test script for new features."""

import os
import shutil
import tempfile
import numpy as np
from datetime import datetime, timedelta

from sea_ice_drift.io import create_sample_data
from sea_ice_drift.motion import MotionField
from sea_ice_drift.analysis import (
    kinematic_analysis, detect_eddies, classify_ice_age,
    create_sample_ice_age, fuse_ice_age_motion
)
from sea_ice_drift.output import (
    save_kinematic_to_netcdf, save_ice_age_to_netcdf,
    plot_vorticity_map, plot_divergence_map, plot_ice_age_map
)

def test_all_features():
    print('=== Creating sample data ===')
    sample_dir = create_sample_data(shape=(150, 150), num_frames=3)
    print(f'Sample data created at: {sample_dir}')

    print('\n=== Testing kinematic analysis ===')
    u = np.random.randn(150, 150) * 0.5
    v = np.random.randn(150, 150) * 0.5

    mf = MotionField(u, v, time_diff=86400, resolution=12500)

    kin = kinematic_analysis(
        mf.velocity_u, mf.velocity_v,
        resolution=12500, smooth_sigma=1.5
    )
    summary = kin.summary()
    print(f'Mean vorticity: {summary["vorticity"]["mean"]*1e6:.3e} s⁻¹')
    print(f'Mean divergence: {summary["divergence"]["mean"]*1e6:.3e} s⁻¹')
    print(f'Mean strain rate: {summary["total_strain"]["mean"]*1e6:.3e} s⁻¹')

    print('\n=== Testing eddy detection ===')
    eddies = detect_eddies(kin, resolution=12500, min_radius_km=30)
    print(f'Detected {len(eddies)} eddies')

    print('\n=== Testing ice age classification ===')
    ia_data = create_sample_ice_age((150, 150), fy_fraction=0.45, my_fraction=0.35)
    ia = classify_ice_age(ia_data)
    ia_summary = ia.summary()
    print(f'FY ice: {ia_summary["fy_percentage"]:.1f}%')
    print(f'MY ice: {ia_summary["my_percentage"]:.1f}%')

    print('\n=== Testing ice age-motion fusion ===')
    fusion = fuse_ice_age_motion(kin, ia)
    if fusion['differences']:
        print(f'Strain ratio (FY/MY): {fusion["differences"]["strain_ratio"]:.2f}')

    print('\n=== Testing NetCDF output ===')
    tmpdir = tempfile.mkdtemp()
    kin_nc = os.path.join(tmpdir, 'test_kinematic.nc')
    ia_nc = os.path.join(tmpdir, 'test_ice_age.nc')

    try:
        save_kinematic_to_netcdf([kin], kin_nc)
        save_ice_age_to_netcdf(ia, ia_nc)
        print('✓ NetCDF files created successfully')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print('\n=== Testing visualization ===')
    tmpdir = tempfile.mkdtemp()
    try:
        plot_vorticity_map(kin, output_path=os.path.join(tmpdir, 'vort.png'))
        plot_divergence_map(kin, output_path=os.path.join(tmpdir, 'div.png'))
        plot_ice_age_map(ia, output_path=os.path.join(tmpdir, 'ia.png'))
        print('✓ Visualizations created successfully')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    shutil.rmtree(sample_dir, ignore_errors=True)
    print('\n✅ All features tested successfully!')

if __name__ == '__main__':
    test_all_features()
