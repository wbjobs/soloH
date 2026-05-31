#!/usr/bin/env python
"""
Example script demonstrating the sea ice drift estimation pipeline.

This script:
1. Creates synthetic sample data
2. Runs the complete processing pipeline
3. Demonstrates all key features
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sea_ice_drift.io import create_sample_data, read_time_series
from sea_ice_drift.preprocess import preprocess_pipeline
from sea_ice_drift.motion import estimate_motion_sequence
from sea_ice_drift.mask import create_full_mask, apply_mask, apply_mask_to_motion
from sea_ice_drift.quality import quality_control_pipeline, compute_quality_metrics
from sea_ice_drift.output import save_to_netcdf, create_visualization_summary
from sea_ice_drift.validation import create_sample_buoy_data, load_buoy_data, compare_with_buoys


def main():
    print('=' * 70)
    print('Sea Ice Drift Estimation - Complete Example')
    print('=' * 70)
    
    output_dir = 'example_output'
    os.makedirs(output_dir, exist_ok=True)
    
    print('\n[Step 1] Creating synthetic sample data...')
    sample_dir = create_sample_data(
        shape=(150, 150),
        num_frames=3,
        save_dir=os.path.join(output_dir, 'sample_data')
    )
    
    buoy_path = create_sample_buoy_data(
        num_buoys=5,
        num_points=6,
        save_path=os.path.join(output_dir, 'sample_buoys.csv')
    )
    
    print(f'\n[Step 2] Reading time series data...')
    import glob
    input_files = sorted(glob.glob(os.path.join(sample_dir, '*.h5')))
    print(f'  Found {len(input_files)} files:')
    for f in input_files:
        print(f'    - {os.path.basename(f)}')
    
    images = read_time_series(input_files, sensor='SSMI', channel='19H')
    print(f'  Read {len(images)} frames')
    for i, img in enumerate(images):
        print(f'    Frame {i}: {img.timestamp}, shape={img.data.shape}')
    
    print(f'\n[Step 3] Preprocessing images...')
    preprocessed = []
    masks_list = []
    
    for i, img in enumerate(images):
        print(f'  Frame {i}: Reprojecting and denoising...')
        pre = preprocess_pipeline(
            img,
            denoise_method='gaussian',
            denoise_kwargs={'sigma': 1.5},
            target_resolution=12.5,
            hemisphere='north',
            do_normalize=False,
            do_enhance=False,
        )
        preprocessed.append(pre)
        
        print(f'    Creating masks...')
        masks = create_full_mask(
            pre['data'],
            pre['lats'],
            pre['lons'],
            do_low_brightness=True,
            do_coastline=True,
            do_land=True,
            hemisphere='north',
        )
        masks_list.append(masks)
        
        pre['data'] = apply_mask(pre['data'], masks['combined'])
        
        valid_pixels = np.sum(~np.isnan(pre['data']))
        total_pixels = pre['data'].size
        print(f'    Valid pixels after masking: {valid_pixels}/{total_pixels} '
              f'({100*valid_pixels/total_pixels:.1f}%)')
    
    print(f'\n[Step 4] Estimating motion using multiple methods...')
    methods = ['horn_schunck', 'lucas_kanade', 'farneback']
    
    for method in methods:
        print(f'\n  Method: {method}')
        method_output_dir = os.path.join(output_dir, f'{method}_results')
        os.makedirs(method_output_dir, exist_ok=True)
        
        try:
            motion_kwargs = {}
            if method == 'horn_schunck':
                motion_kwargs = {'alpha': 1.0, 'iterations': 50}
            elif method == 'lucas_kanade':
                motion_kwargs = {'window_size': 15, 'max_levels': 3}
            elif method == 'farneback':
                motion_kwargs = {'winsize': 15, 'iterations': 3}
            
            motion_fields = estimate_motion_sequence(
                preprocessed,
                method=method,
                **motion_kwargs
            )
            print(f'    Estimated {len(motion_fields)} motion fields')
            
            print(f'  Applying masks...')
            for i, mf in enumerate(motion_fields):
                motion_fields[i] = apply_mask_to_motion(mf, masks_list[i]['combined'])
            
            print(f'  Quality control...')
            final_motion = []
            for i, mf in enumerate(motion_fields):
                qc = quality_control_pipeline(
                    mf,
                    min_correlation=0.3,
                    outlier_method='iqr',
                    outlier_threshold=2.0,
                    interp_method='linear',
                    smooth_method='gaussian',
                    smooth_sigma=1.0,
                )
                final_motion.append(qc['smoothed'])
                
                metrics = compute_quality_metrics(qc['smoothed'])
                print(f'    Motion {i}: {metrics["percentage_valid"]:.1f}% valid, '
                      f'mean speed={metrics["mean_speed"]:.2f} px')
            
            print(f'  Saving to NetCDF...')
            nc_path = os.path.join(method_output_dir, 'sea_ice_drift.nc')
            save_to_netcdf(
                final_motion,
                preprocessed,
                nc_path,
                global_attrs={
                    'sensor': 'SSMI',
                    'channel': '19H',
                    'motion_estimation_method': method,
                }
            )
            
            print(f'  Creating visualizations...')
            create_visualization_summary(
                final_motion,
                preprocessed,
                output_dir=os.path.join(method_output_dir, 'plots'),
                stride=8,
                hemisphere='north',
            )
            
            print(f'  Validating with buoy data...')
            try:
                buoys = load_buoy_data(buoy_path)
                val_results = compare_with_buoys(
                    final_motion,
                    preprocessed,
                    buoys,
                    output_dir=os.path.join(method_output_dir, 'validation'),
                )
                
                if 'statistics' in val_results:
                    stats = val_results['statistics']
                    if stats.get('n_points', 0) > 0:
                        print(f'    Validation RMSE (U): {stats.get("rmse_u", 0):.4f} m/s')
                        print(f'    Validation RMSE (V): {stats.get("rmse_v", 0):.4f} m/s')
                        print(f'    Correlation (U): {stats.get("corr_u", 0):.4f}')
                        print(f'    Correlation (V): {stats.get("corr_v", 0):.4f}')
            except Exception as e:
                print(f'    Validation skipped: {e}')
            
            print(f'  ✓ {method} complete! Results in {method_output_dir}')
            
        except Exception as e:
            print(f'  ✗ {method} failed: {e}')
            import traceback
            traceback.print_exc()
    
    print('\n' + '=' * 70)
    print('Example complete!')
    print(f'All results saved to: {os.path.abspath(output_dir)}')
    print('=' * 70)
    
    print('\nSummary of output directories:')
    for method in methods:
        print(f'  - {method}_results/')
        print(f'    ├── sea_ice_drift.nc')
        print(f'    ├── plots/')
        print(f'    │   ├── quiver_*.png')
        print(f'    │   ├── speed_*.png')
        print(f'    │   └── correlation_*.png')
        print(f'    └── validation/')
        print(f'        ├── scatter_comparison.png')
        print(f'        ├── bias_statistics.csv')
        print(f'        └── time_series.png')
    
    print('\nTo run the command-line tool:')
    print(f'  python -m sea_ice_drift.main --input {sample_dir}/*.h5 '
          f'--output {output_dir}/cli_output --method horn_schunck')
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
