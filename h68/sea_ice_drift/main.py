"""
Main command-line interface for sea ice drift estimation.

This script provides a complete pipeline for estimating sea ice drift
from time series of SSM/I or AMSR-E brightness temperature images.
"""

import os
import sys
import argparse
import glob
import numpy as np
from datetime import datetime

from .io import (
    read_hdf_file,
    read_time_series,
    create_sample_data,
)
from .preprocess import (
    preprocess_pipeline,
    denoise_image,
    reproject_to_polar_ae,
)
from .motion import (
    estimate_motion_sequence,
    estimate_motion,
)
from .mask import (
    create_full_mask,
    apply_mask_to_motion,
    apply_mask,
)
from .quality import (
    quality_control_pipeline,
    compute_quality_metrics,
    filter_by_temporal_consistency,
)
from .output import (
    save_to_netcdf,
    create_visualization_summary,
    plot_quiver,
    save_kinematic_to_netcdf,
    save_ice_age_to_netcdf,
    create_kinematic_summary,
    plot_ice_age_map,
)
from .validation import (
    load_buoy_data,
    compare_with_buoys,
    create_sample_buoy_data,
)
from .analysis import (
    kinematic_analysis,
    detect_eddies,
    classify_ice_age,
    fuse_ice_age_motion,
    read_ice_age_netcdf,
    create_sample_ice_age,
)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Sea Ice Drift Estimation from SSM/I or AMSR-E Brightness Temperature Images',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create sample data
  sea-ice-drift --create-sample-data
  
  # Process sample data with default settings
  sea-ice-drift --input sample_data/*.h5 --output output
  
  # Process with specific motion estimation method
  sea-ice-drift --input data/*.h5 --output output --method lucas_kanade
  
  # Include validation with buoy data
  sea-ice-drift --input data/*.h5 --buoys buoys.csv --output output
        """
    )
    
    input_group = parser.add_argument_group('Input Options')
    input_group.add_argument('--input', '-i', nargs='+', 
                           help='Input HDF5 file(s) or glob pattern')
    input_group.add_argument('--sensor', default='SSMI',
                           choices=['SSMI', 'AMSR2'],
                           help='Sensor type (default: SSMI)')
    input_group.add_argument('--channel', default='19H',
                           help='Frequency channel (default: 19H)')
    
    preprocess_group = parser.add_argument_group('Preprocessing Options')
    preprocess_group.add_argument('--target-resolution', type=float, default=12.5,
                                 help='Target grid resolution in km (default: 12.5)')
    preprocess_group.add_argument('--hemisphere', default='north',
                                 choices=['north', 'south'],
                                 help='Hemisphere for projection (default: north)')
    preprocess_group.add_argument('--denoise-method', default='gaussian',
                                 choices=['gaussian', 'median', 'wavelet', 
                                          'bilateral', 'anisotropic', 'none'],
                                 help='Denoising method (default: gaussian)')
    preprocess_group.add_argument('--denoise-sigma', type=float, default=1.5,
                                 help='Denoising sigma parameter (default: 1.5)')
    preprocess_group.add_argument('--target-shape', type=int, nargs=2,
                                 help='Target shape (rows cols) for reprojection')
    preprocess_group.add_argument('--no-enhance', action='store_true',
                                 help='Disable contrast enhancement')
    preprocess_group.add_argument('--normalize', action='store_true',
                                 help='Enable image normalization')
    
    motion_group = parser.add_argument_group('Motion Estimation Options')
    motion_group.add_argument('--method', default='horn_schunck',
                             choices=['cross_correlation', 'horn_schunck', 
                                      'lucas_kanade', 'farneback', 'flow_net'],
                             help='Motion estimation method (default: horn_schunck)')
    motion_group.add_argument('--window-size', type=int, default=32,
                             help='Window size for cross-correlation (default: 32)')
    motion_group.add_argument('--search-range', type=int, default=16,
                             help='Search range for cross-correlation (default: 16)')
    motion_group.add_argument('--step', type=int, default=4,
                             help='Step size for cross-correlation (default: 4)')
    motion_group.add_argument('--alpha', type=float, default=1.0,
                             help='Smoothness parameter for Horn-Schunck (default: 1.0)')
    motion_group.add_argument('--iterations', type=int, default=100,
                             help='Max iterations for Horn-Schunck (default: 100)')
    
    mask_group = parser.add_argument_group('Mask Options')
    mask_group.add_argument('--no-mask', action='store_true',
                           help='Disable masking')
    mask_group.add_argument('--no-land-mask', action='store_true',
                           help='Disable land mask')
    mask_group.add_argument('--no-coastline-mask', action='store_true',
                           help='Disable coastline mask')
    mask_group.add_argument('--no-low-brightness-mask', action='store_true',
                           help='Disable low brightness temperature mask')
    mask_group.add_argument('--coastline-buffer', type=float, default=10.0,
                           help='Coastline buffer in km (default: 10.0)')
    mask_group.add_argument('--brightness-threshold', type=float,
                           help='Low brightness temperature threshold in K')
    
    qc_group = parser.add_argument_group('Quality Control Options')
    qc_group.add_argument('--min-correlation', type=float, default=0.5,
                         help='Minimum correlation coefficient (default: 0.5)')
    qc_group.add_argument('--outlier-method', default='iqr',
                         choices=['iqr', 'zscore', 'isolation_forest'],
                         help='Outlier detection method (default: iqr)')
    qc_group.add_argument('--outlier-threshold', type=float, default=3.0,
                         help='Outlier detection threshold (default: 3.0)')
    qc_group.add_argument('--interp-method', default='linear',
                         choices=['linear', 'nearest', 'cubic', 'rbf', 'gaussian'],
                         help='Interpolation method (default: linear)')
    qc_group.add_argument('--smooth-method', default='gaussian',
                         choices=['gaussian', 'median'],
                         help='Smoothing method (default: gaussian)')
    qc_group.add_argument('--smooth-sigma', type=float, default=1.0,
                         help='Smoothing sigma (default: 1.0)')
    qc_group.add_argument('--do-tb-filter', action='store_true',
                         help='Filter by brightness temperature change (melt pond detection)')
    qc_group.add_argument('--max-tb-change', type=float, default=20.0,
                         help='Maximum allowed TB change for valid vectors (K, default: 20.0)')
    qc_group.add_argument('--high-tb-threshold', type=float, default=272.0,
                         help='High TB threshold for melt pond detection (K, default: 272.0)')
    qc_group.add_argument('--do-temporal-check', action='store_true',
                         help='Enable temporal consistency check between motion fields')
    qc_group.add_argument('--max-rotation-change', type=float, default=30.0,
                         help='Maximum allowed direction change (degrees, default: 30.0)')
    qc_group.add_argument('--max-speed-change', type=float, default=0.3,
                         help='Maximum allowed relative speed change (fraction, default: 0.3)')
    
    multires_group = parser.add_argument_group('Multi-Resolution Alignment Options')
    multires_group.add_argument('--no-multires-align', action='store_true',
                               help='Disable multi-resolution image alignment')
    multires_group.add_argument('--upsample-method', default='bicubic',
                               choices=['bilinear', 'bicubic', 'lanczos', 'gaussian'],
                               help='Upsampling method for low-res images (default: bicubic)')
    multires_group.add_argument('--no-subpixel-refine', action='store_true',
                               help='Disable subpixel refinement')
    multires_group.add_argument('--interpolation-method', default='linear',
                               choices=['linear', 'nearest', 'cubic'],
                               help='Interpolation method for reprojection (default: linear)')
    
    coast_group = parser.add_argument_group('Coastline Enhancement Options')
    coast_group.add_argument('--no-gradient-coast-constraint', action='store_true',
                            help='Disable gradient-based coastline constraint')
    coast_group.add_argument('--min-coast-distance', type=float, default=25.0,
                            help='Minimum distance from coast for reliable vectors (km, default: 25.0)')
    coast_group.add_argument('--max-gradient-ratio', type=float, default=3.0,
                            help='Maximum allowed gradient ratio near coast (default: 3.0)')
    coast_group.add_argument('--coastline-resolution', type=float,
                            help='Coastline grid resolution in km (auto-detected if not set)')
    
    dl_group = parser.add_argument_group('Deep Learning Options (FlowNet)')
    dl_group.add_argument('--flownet-model-type', default='small',
                         choices=['small', 'full', 'custom'],
                         help='FlowNet model type (default: small)')
    dl_group.add_argument('--flownet-model-path',
                         help='Path to custom FlowNet model weights')
    dl_group.add_argument('--flownet-device',
                         help='Device for FlowNet inference (cpu/cuda)')
    dl_group.add_argument('--no-flownet-pretrained', action='store_true',
                         help='Do not load pre-trained weights')
    
    kinematic_group = parser.add_argument_group('Kinematic Analysis Options')
    kinematic_group.add_argument('--do-kinematic-analysis', action='store_true',
                                help='Enable kinematic analysis (vorticity, divergence, strain)')
    kinematic_group.add_argument('--kinematic-smooth-sigma', type=float, default=1.5,
                                help='Smoothing sigma for kinematic derivatives (default: 1.5)')
    kinematic_group.add_argument('--detect-eddies', action='store_true',
                                help='Detect eddies using Okubo-Weiss parameter')
    kinematic_group.add_argument('--min-eddy-radius-km', type=float, default=25.0,
                                help='Minimum eddy radius in km (default: 25.0)')
    kinematic_group.add_argument('--ow-threshold', type=float, default=-1e-10,
                                help='Okubo-Weiss threshold for eddy detection (default: -1e-10)')
    
    ice_age_group = parser.add_argument_group('Ice Age Fusion Options')
    ice_age_group.add_argument('--ice-age-file',
                              help='NetCDF file containing ice age data')
    ice_age_group.add_argument('--ice-age-var', default='ice_age',
                              help='Variable name for ice age in NetCDF (default: ice_age)')
    ice_age_group.add_argument('--fy-threshold', type=float, default=2.0,
                              help='Upper threshold for first-year ice in years (default: 2.0)')
    ice_age_group.add_argument('--my-threshold', type=float, default=4.0,
                              help='Lower threshold for multi-year ice in years (default: 4.0)')
    ice_age_group.add_argument('--create-sample-ice-age', action='store_true',
                              help='Create synthetic ice age data for testing')
    
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument('--output', '-o', default='output',
                             help='Output directory (default: output)')
    output_group.add_argument('--save-netcdf', action='store_true', default=True,
                             help='Save results to NetCDF (default: True)')
    output_group.add_argument('--no-netcdf', action='store_true',
                             help='Disable NetCDF output')
    output_group.add_argument('--visualize', action='store_true', default=True,
                             help='Create visualizations (default: True)')
    output_group.add_argument('--no-visualize', action='store_true',
                             help='Disable visualization')
    output_group.add_argument('--stride', type=int, default=10,
                             help='Stride for quiver plots (default: 10)')
    
    validation_group = parser.add_argument_group('Validation Options')
    validation_group.add_argument('--buoys', 
                                 help='CSV file with buoy observations')
    
    sample_group = parser.add_argument_group('Sample Data')
    sample_group.add_argument('--create-sample-data', action='store_true',
                             help='Create synthetic sample data for testing')
    sample_group.add_argument('--sample-shape', type=int, nargs=2, default=[200, 200],
                             metavar=('ROWS', 'COLS'),
                             help='Sample data shape (default: 200 200)')
    sample_group.add_argument('--sample-frames', type=int, default=3,
                             help='Number of sample frames (default: 3)')
    
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    
    return parser.parse_args()


def expand_input_files(input_patterns):
    """Expand glob patterns and verify files exist."""
    all_files = []
    for pattern in input_patterns:
        matches = glob.glob(pattern)
        if not matches:
            print(f'Warning: No files found matching {pattern}')
        else:
            all_files.extend(matches)
    
    all_files = sorted(list(set(all_files)))
    
    if not all_files:
        raise FileNotFoundError('No input files found')
    
    if len(all_files) < 2:
        raise ValueError('At least 2 input files are required for motion estimation')
    
    return all_files


def main():
    """Main entry point for the sea ice drift estimation pipeline."""
    args = parse_arguments()
    
    if args.create_sample_data:
        print('Creating sample data...')
        sample_dir = create_sample_data(
            shape=tuple(args.sample_shape),
            num_frames=args.sample_frames
        )
        create_sample_buoy_data(
            num_buoys=5,
            num_points=args.sample_frames * 2,
            save_path='sample_buoys.csv'
        )
        print(f'\nSample data created in: {sample_dir}')
        print(f'Sample buoy data: sample_buoys.csv')
        print(f'\nTo process sample data, run:')
        print(f'  sea-ice-drift --input {sample_dir}/*.h5 --output output --buoys sample_buoys.csv')
        return 0
    
    if not args.input:
        print('Error: --input is required (or use --create-sample-data)')
        return 1
    
    print('=' * 60)
    print('Sea Ice Drift Estimation Toolkit')
    print('=' * 60)
    
    try:
        print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Expanding input files...')
        input_files = expand_input_files(args.input)
        print(f'  Found {len(input_files)} input files')
        
        if args.verbose:
            for i, f in enumerate(input_files):
                print(f'    {i+1}. {f}')
        
        print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Reading time series...')
        images = read_time_series(input_files, args.sensor, args.channel)
        print(f'  Read {len(images)} frames')
        for i, img in enumerate(images):
            print(f'    Frame {i}: {img.timestamp}, shape={img.data.shape}')
        
        print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Preprocessing...')
        denoise_kwargs = {'sigma': args.denoise_sigma} if args.denoise_method != 'none' else {}
        denoise_method = args.denoise_method if args.denoise_method != 'none' else None
        
        preprocessed = []
        masks_list = []
        
        for i, img in enumerate(images):
            print(f'  Processing frame {i}...')
            
            if denoise_method is not None:
                pre = preprocess_pipeline(
                    img,
                    denoise_method=denoise_method,
                    denoise_kwargs=denoise_kwargs,
                    target_resolution=args.target_resolution,
                    hemisphere=args.hemisphere,
                    target_shape=tuple(args.target_shape) if args.target_shape else None,
                    do_normalize=args.normalize,
                    do_enhance=not args.no_enhance,
                    interpolation_method=args.interpolation_method,
                )
            else:
                reproj = reproject_to_polar_ae(
                    img.data, img.lats, img.lons,
                    target_resolution=args.target_resolution,
                    hemisphere=args.hemisphere,
                    target_shape=tuple(args.target_shape) if args.target_shape else None,
                    interpolation_method=args.interpolation_method,
                )
                pre = reproj
                pre['data_raw'] = pre['data']
                pre['timestamp'] = img.timestamp
                pre['sensor'] = img.sensor
                pre['channel'] = img.channel
                pre['gradient'] = None
            
            preprocessed.append(pre)
            
            if not args.no_mask:
                print(f'    Creating masks...')
                gradient = pre.get('gradient')
                masks = create_full_mask(
                    pre['data'],
                    pre['lats'],
                    pre['lons'],
                    do_low_brightness=not args.no_low_brightness_mask,
                    low_brightness_threshold=args.brightness_threshold,
                    do_coastline=not args.no_coastline_mask,
                    coastline_buffer_km=args.coastline_buffer,
                    do_land=not args.no_land_mask,
                    hemisphere=args.hemisphere,
                    gradient_magnitude=gradient,
                    exclude_near_coast=not args.no_gradient_coast_constraint,
                    min_coast_distance_km=args.min_coast_distance,
                )
                masks_list.append(masks)
                
                pre['data'] = apply_mask(pre['data'], masks['combined'])
        
        print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Estimating motion...')
        motion_kwargs = {}
        
        if args.method == 'cross_correlation':
            motion_kwargs = {
                'window_size': args.window_size,
                'search_range': args.search_range,
                'step': args.step,
            }
        elif args.method == 'horn_schunck':
            motion_kwargs = {
                'alpha': args.alpha,
                'iterations': args.iterations,
            }
        elif args.method == 'lucas_kanade':
            motion_kwargs = {
                'window_size': args.window_size,
                'max_levels': 3,
            }
        elif args.method == 'farneback':
            motion_kwargs = {
                'winsize': args.window_size,
                'iterations': args.iterations,
            }
        elif args.method == 'flow_net':
            motion_kwargs = {
                'model_type': args.flownet_model_type,
                'device': args.flownet_device,
                'model_path': args.flownet_model_path,
            }
        
        motion_fields = estimate_motion_sequence(
            preprocessed,
            method=args.method,
            do_multires_align=not args.no_multires_align,
            target_resolution=args.target_resolution,
            upsample_method=args.upsample_method,
            do_subpixel_refine=not args.no_subpixel_refine,
            **motion_kwargs
        )
        print(f'  Estimated {len(motion_fields)} motion fields')
        
        if masks_list and not args.no_mask:
            print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Applying masks...')
            for i, mf in enumerate(motion_fields):
                mask = masks_list[i]['combined']
                motion_fields[i] = apply_mask_to_motion(mf, mask)
        
        if args.do_temporal_check and len(motion_fields) > 1:
            print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Temporal consistency check...')
            motion_fields = filter_by_temporal_consistency(
                motion_fields,
                max_rotation_change=args.max_rotation_change,
                max_speed_change=args.max_speed_change
            )
        
        print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Quality control...')
        qc_results_list = []
        final_motion_fields = []
        
        for i, mf in enumerate(motion_fields):
            print(f'  QC for motion field {i}...')
            
            img1 = preprocessed[i]['data']
            img2 = preprocessed[i + 1]['data']
            
            qc_results = quality_control_pipeline(
                mf,
                min_correlation=args.min_correlation,
                outlier_method=args.outlier_method,
                outlier_threshold=args.outlier_threshold,
                interp_method=args.interp_method,
                smooth_method=args.smooth_method,
                smooth_sigma=args.smooth_sigma,
                img1=img1,
                img2=img2,
                do_tb_filter=args.do_tb_filter,
                max_tb_change=args.max_tb_change,
                high_tb_threshold=args.high_tb_threshold,
            )
            qc_results_list.append(qc_results)
            final_motion_fields.append(qc_results['smoothed'])
            
            metrics = compute_quality_metrics(qc_results['smoothed'])
            print(f'    {metrics["percentage_valid"]:.1f}% valid, '
                  f'mean speed={metrics["mean_speed"]:.2f} px')
        
        kinematic_list = []
        eddies_list = []
        if args.do_kinematic_analysis:
            print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Performing kinematic analysis...')
            for i, mf in enumerate(final_motion_fields):
                print(f'  Analyzing motion field {i}...')
                resolution = mf.resolution
                kin = kinematic_analysis(
                    mf.velocity_u,
                    mf.velocity_v,
                    resolution=resolution,
                    smooth_sigma=args.kinematic_smooth_sigma,
                    lats=preprocessed[i]['lats'],
                    lons=preprocessed[i]['lons']
                )
                kinematic_list.append(kin)
                
                summary = kin.summary()
                print(f'    Mean vorticity: {summary["vorticity"]["mean"]*1e6:.3e} s⁻¹')
                print(f'    Mean divergence: {summary["divergence"]["mean"]*1e6:.3e} s⁻¹')
                print(f'    Mean strain rate: {summary["total_strain"]["mean"]*1e6:.3e} s⁻¹')
                
                if args.detect_eddies:
                    eddies = detect_eddies(
                        kin,
                        resolution=resolution,
                        min_radius_km=args.min_eddy_radius_km,
                        ow_threshold=args.ow_threshold
                    )
                    eddies_list.append(eddies)
                    print(f'    Detected {len(eddies)} eddies')
        
        ice_age_result = None
        if args.ice_age_file or args.create_sample_ice_age:
            print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Processing ice age data...')
            if args.create_sample_ice_age:
                shape = preprocessed[0]['data'].shape
                ice_age_data = create_sample_ice_age(shape)
                print(f'  Created synthetic ice age data, shape={shape}')
            else:
                print(f'  Loading ice age data from: {args.ice_age_file}')
                ia_data = read_ice_age_netcdf(args.ice_age_file, variable_name=args.ice_age_var)
                ice_age_data = ia_data['ice_age']
            
            ice_age_result = classify_ice_age(
                ice_age_data,
                fy_threshold=args.fy_threshold,
                my_threshold=args.my_threshold
            )
            
            ia_summary = ice_age_result.summary()
            print(f'  First-year ice: {ia_summary["fy_percentage"]:.1f}%')
            print(f'  Multi-year ice: {ia_summary["my_percentage"]:.1f}%')
            
            if kinematic_list:
                print(f'\n  Fusing ice age with motion data...')
                for i, kin in enumerate(kinematic_list):
                    fusion_stats = fuse_ice_age_motion(kin, ice_age_result)
                    if fusion_stats.get('differences'):
                        diff = fusion_stats['differences']
                        print(f'  Pair {i}:')
                        print(f'    Strain rate ratio (FY/MY): {diff["strain_ratio"]:.2f}')
                        print(f'    Vorticity difference: {diff["vorticity_diff"]*1e6:.3e} s⁻¹')
        
        os.makedirs(args.output, exist_ok=True)
        
        if not args.no_netcdf:
            print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Saving to NetCDF...')
            nc_path = os.path.join(args.output, 'sea_ice_drift.nc')
            save_to_netcdf(
                final_motion_fields,
                preprocessed,
                nc_path,
                global_attrs={
                    'sensor': args.sensor,
                    'channel': args.channel,
                    'motion_estimation_method': args.method,
                }
            )
            
            if kinematic_list:
                kin_nc_path = os.path.join(args.output, 'kinematic_analysis.nc')
                save_kinematic_to_netcdf(
                    kinematic_list,
                    kin_nc_path,
                    preprocessed_images=preprocessed,
                    global_attrs={
                        'sensor': args.sensor,
                        'channel': args.channel,
                        'smooth_sigma': args.kinematic_smooth_sigma,
                    }
                )
                print(f'  Kinematic analysis saved to: {kin_nc_path}')
            
            if ice_age_result is not None:
                ia_nc_path = os.path.join(args.output, 'ice_age_classification.nc')
                save_ice_age_to_netcdf(
                    ice_age_result,
                    ia_nc_path,
                    lats=preprocessed[0]['lats'],
                    lons=preprocessed[0]['lons'],
                    global_attrs={
                        'fy_threshold_years': args.fy_threshold,
                        'my_threshold_years': args.my_threshold,
                    }
                )
                print(f'  Ice age data saved to: {ia_nc_path}')
        
        if not args.no_visualize:
            print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Creating visualizations...')
            create_visualization_summary(
                final_motion_fields,
                preprocessed,
                output_dir=os.path.join(args.output, 'plots'),
                stride=args.stride,
                hemisphere=args.hemisphere,
            )
            
            if kinematic_list:
                create_kinematic_summary(
                    kinematic_list,
                    eddies_list=eddies_list if args.detect_eddies else None,
                    preprocessed_images=preprocessed,
                    output_dir=os.path.join(args.output, 'plots', 'kinematic'),
                    hemisphere=args.hemisphere,
                )
            
            if ice_age_result is not None:
                ia_plot_path = os.path.join(args.output, 'plots', 'ice_age_classification.png')
                plot_ice_age_map(
                    ice_age_result,
                    output_path=ia_plot_path,
                    title='Ice Age Classification'
                )
        
        if args.buoys:
            print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Validating with buoy data...')
            try:
                buoys = load_buoy_data(args.buoys)
                print(f'  Loaded {len(buoys)} buoy datasets')
                
                val_results = compare_with_buoys(
                    final_motion_fields,
                    preprocessed,
                    buoys,
                    output_dir=os.path.join(args.output, 'validation'),
                )
                
                if 'statistics' in val_results:
                    stats = val_results['statistics']
                    print(f'\n  Validation Statistics:')
                    print(f'    N points: {stats.get("n_points", 0)}')
                    if stats.get("n_points", 0) > 0:
                        print(f'    Mean Bias (U): {stats.get("mean_bias_u", 0):.4f} m/s')
                        print(f'    Mean Bias (V): {stats.get("mean_bias_v", 0):.4f} m/s')
                        print(f'    RMSE (U): {stats.get("rmse_u", 0):.4f} m/s')
                        print(f'    RMSE (V): {stats.get("rmse_v", 0):.4f} m/s')
                        print(f'    Correlation (U): {stats.get("corr_u", 0):.4f}')
                        print(f'    Correlation (V): {stats.get("corr_v", 0):.4f}')
            except Exception as e:
                print(f'  Warning: Validation failed: {e}')
        
        print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Processing complete!')
        print(f'  Output directory: {args.output}')
        print(f'\n  Summary:')
        print(f'    Input frames: {len(images)}')
        print(f'    Motion fields: {len(motion_fields)}')
        print(f'    Method: {args.method}')
        print(f'    Output: {args.output}')
        
        return 0
        
    except Exception as e:
        print(f'\nError: {e}')
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
