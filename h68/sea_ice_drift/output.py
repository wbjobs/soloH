"""
Output generation module.

Supports:
- NetCDF output for motion fields
- Visualization (quiver plots, magnitude maps)
- Kinematic analysis output (vorticity, divergence, strain)
- Ice age data visualization
"""

import os
import numpy as np
import xarray as xr
from netCDF4 import Dataset
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, SymLogNorm
from datetime import datetime

try:
    from .analysis import KinematicAnalysis, IceAgeData, Eddy
    ANALYSIS_AVAILABLE = True
except ImportError:
    ANALYSIS_AVAILABLE = False


def save_to_netcdf(motion_fields, preprocessed_images, output_path, 
                   extra_vars=None, global_attrs=None):
    """
    Save motion fields to NetCDF file.
    
    Parameters
    ----------
    motion_fields : list
        List of MotionField objects
    preprocessed_images : list
        List of preprocessed image dicts
    output_path : str
        Output NetCDF file path
    extra_vars : dict, optional
        Additional variables to save
    global_attrs : dict, optional
        Global attributes for the NetCDF file
    """
    if len(motion_fields) != len(preprocessed_images) - 1:
        raise ValueError('Number of motion fields must be one less than number of images')
    
    ref_img = preprocessed_images[0]
    rows, cols = ref_img['data'].shape
    x_coords = ref_img['x'][0, :] if 'x' in ref_img else np.arange(cols)
    y_coords = ref_img['y'][:, 0] if 'y' in ref_img else np.arange(rows)
    lats = ref_img['lats']
    lons = ref_img['lons']
    
    times = [img['timestamp'] for img in preprocessed_images]
    time_intervals = [(times[i+1] - times[i]).total_seconds() for i in range(len(times)-1)]
    
    ds = Dataset(output_path, 'w', format='NETCDF4')
    
    ds.createDimension('time', len(motion_fields))
    ds.createDimension('y', rows)
    ds.createDimension('x', cols)
    
    time_var = ds.createVariable('time', 'f8', ('time',))
    time_var.units = 'seconds since 1970-01-01 00:00:00'
    time_var.standard_name = 'time'
    time_var.long_name = 'Time of motion estimate (mid-point)'
    for i, (t1, t2) in enumerate(zip(times[:-1], times[1:])):
        mid_time = t1 + (t2 - t1) / 2
        time_var[i] = (mid_time - datetime(1970, 1, 1)).total_seconds()
    
    x_var = ds.createVariable('x', 'f8', ('y', 'x'))
    x_var.units = 'meters'
    x_var.standard_name = 'projection_x_coordinate'
    x_var[:] = ref_img['x'] if 'x' in ref_img else np.arange(cols)
    
    y_var = ds.createVariable('y', 'f8', ('y', 'x'))
    y_var.units = 'meters'
    y_var.standard_name = 'projection_y_coordinate'
    y_var[:] = ref_img['y'] if 'y' in ref_img else np.arange(rows)
    
    lat_var = ds.createVariable('latitude', 'f8', ('y', 'x'))
    lat_var.units = 'degrees_north'
    lat_var.standard_name = 'latitude'
    lat_var[:] = lats
    
    lon_var = ds.createVariable('longitude', 'f8', ('y', 'x'))
    lon_var.units = 'degrees_east'
    lon_var.standard_name = 'longitude'
    lon_var[:] = lons
    
    resolution = ref_img.get('resolution', 12.5)
    u_var = ds.createVariable('eastward_displacement', 'f4', ('time', 'y', 'x'),
                              fill_value=np.nan)
    u_var.units = 'meters'
    u_var.standard_name = 'eastward_sea_ice_displacement'
    u_var.long_name = 'Eastward sea ice displacement'
    for i, mf in enumerate(motion_fields):
        u_var[i, :, :] = mf.u * resolution * 1000
    
    v_var = ds.createVariable('northward_displacement', 'f4', ('time', 'y', 'x'),
                              fill_value=np.nan)
    v_var.units = 'meters'
    v_var.standard_name = 'northward_sea_ice_displacement'
    v_var.long_name = 'Northward sea ice displacement'
    for i, mf in enumerate(motion_fields):
        v_var[i, :, :] = mf.v * resolution * 1000
    
    u_vel_var = ds.createVariable('eastward_velocity', 'f4', ('time', 'y', 'x'),
                                  fill_value=np.nan)
    u_vel_var.units = 'm s-1'
    u_vel_var.standard_name = 'eastward_sea_ice_velocity'
    u_vel_var.long_name = 'Eastward sea ice velocity'
    for i, mf in enumerate(motion_fields):
        u_vel_var[i, :, :] = mf.velocity_u
    
    v_vel_var = ds.createVariable('northward_velocity', 'f4', ('time', 'y', 'x'),
                                  fill_value=np.nan)
    v_vel_var.units = 'm s-1'
    v_vel_var.standard_name = 'northward_sea_ice_velocity'
    v_vel_var.long_name = 'Northward sea ice velocity'
    for i, mf in enumerate(motion_fields):
        v_vel_var[i, :, :] = mf.velocity_v
    
    speed_var = ds.createVariable('speed', 'f4', ('time', 'y', 'x'),
                                  fill_value=np.nan)
    speed_var.units = 'm s-1'
    speed_var.standard_name = 'sea_ice_speed'
    speed_var.long_name = 'Sea ice drift speed'
    for i, mf in enumerate(motion_fields):
        speed_var[i, :, :] = np.sqrt(mf.velocity_u**2 + mf.velocity_v**2)
    
    if motion_fields[0].correlation is not None:
        corr_var = ds.createVariable('correlation', 'f4', ('time', 'y', 'x'),
                                     fill_value=np.nan)
        corr_var.units = '1'
        corr_var.standard_name = 'pattern_correlation'
        corr_var.long_name = 'Pattern correlation coefficient'
        for i, mf in enumerate(motion_fields):
            corr_var[i, :, :] = mf.correlation
    
    dt_var = ds.createVariable('time_interval', 'f8', ('time',))
    dt_var.units = 'seconds'
    dt_var.long_name = 'Time interval between images'
    dt_var[:] = time_intervals
    
    tb_var = ds.createVariable('brightness_temperature', 'f4', ('time', 'y', 'x'),
                               fill_value=np.nan)
    tb_var.units = 'K'
    tb_var.standard_name = 'brightness_temperature'
    tb_var.long_name = 'Brightness temperature'
    for i, img in enumerate(preprocessed_images):
        tb_var[i, :, :] = img['data']
    
    if extra_vars:
        for name, data in extra_vars.items():
            if isinstance(data, tuple) and len(data) == 3:
                values, dims, attrs = data
                var = ds.createVariable(name, values.dtype, dims, fill_value=np.nan)
                var[:] = values
                for k, v in attrs.items():
                    setattr(var, k, v)
    
    if global_attrs:
        for k, v in global_attrs.items():
            setattr(ds, k, v)
    
    ds.title = 'Sea Ice Drift Estimation'
    ds.institution = 'Sea Ice Drift Toolkit'
    ds.source = f'Sea Ice Drift v1.0.0'
    ds.history = f'Created on {datetime.now().isoformat()}'
    ds.references = 'https://github.com/sea-ice-drift/toolkit'
    ds.Conventions = 'CF-1.8'
    
    ds.close()
    print(f'NetCDF file saved to: {output_path}')


def load_from_netcdf(filepath):
    """
    Load motion fields from NetCDF file.
    
    Parameters
    ----------
    filepath : str
        Path to NetCDF file
        
    Returns
    -------
    xarray.Dataset
        Dataset containing all variables
    """
    ds = xr.open_dataset(filepath)
    return ds


def plot_quiver(motion_field, background=None, lats=None, lons=None,
                output_path='quiver_plot.png', stride=10, scale=20,
                title='Sea Ice Drift', show_colorbar=True, cmap='viridis'):
    """
    Create quiver plot of motion vectors.
    
    Parameters
    ----------
    motion_field : MotionField
        Motion field to plot
    background : 2D array, optional
        Background image (e.g., brightness temperature)
    lats, lons : 2D array, optional
        Coordinate arrays for geographic projection
    output_path : str
        Output file path
    stride : int
        Stride for plotting arrows (every Nth pixel)
    scale : float
        Scale factor for arrow length
    title : str
        Plot title
    show_colorbar : bool
        Whether to show colorbar for speed
    cmap : str
        Colormap for speed coloring
    """
    rows, cols = motion_field.u.shape
    
    y_idx = np.arange(0, rows, stride)
    x_idx = np.arange(0, cols, stride)
    X, Y = np.meshgrid(x_idx, y_idx)
    
    U = motion_field.u[y_idx[:, None], x_idx[None, :]]
    V = motion_field.v[y_idx[:, None], x_idx[None, :]]
    speed = np.sqrt(U**2 + V**2)
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    if background is not None:
        vmin = np.nanmin(background)
        vmax = np.nanmax(background)
        im = ax.imshow(background, cmap='gray', vmin=vmin, vmax=vmax, alpha=0.7)
    
    valid = ~(np.isnan(U) | np.isnan(V) | np.isnan(speed))
    
    if np.any(valid):
        speed_valid = speed[valid]
        vmin_speed = np.nanmin(speed_valid)
        vmax_speed = np.nanmax(speed_valid)
        norm = Normalize(vmin=vmin_speed, vmax=vmax_speed)
        
        colors = plt.get_cmap(cmap)(norm(speed))
        colors[~valid] = [0, 0, 0, 0]
        
        q = ax.quiver(X, Y, U, V, speed,
                      scale=scale, scale_units='xy',
                      cmap=cmap, norm=norm,
                      width=0.002, headwidth=3, headlength=4)
        
        if show_colorbar:
            cbar = plt.colorbar(q, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label('Drift Speed (pixels)')
    
    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    ax.set_title(title)
    ax.set_aspect('equal')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Quiver plot saved to: {output_path}')


def plot_speed_map(motion_field, output_path='speed_map.png',
                   title='Sea Ice Drift Speed', cmap='jet',
                   units='pixels'):
    """
    Create speed magnitude map.
    
    Parameters
    ----------
    motion_field : MotionField
        Motion field to plot
    output_path : str
        Output file path
    title : str
        Plot title
    cmap : str
        Colormap
    units : str
        Units for colorbar label
    """
    speed = motion_field.speed
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    vmin = np.nanmin(speed)
    vmax = np.nanmax(speed)
    
    im = ax.imshow(speed, cmap=cmap, vmin=vmin, vmax=vmax)
    
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(f'Speed ({units})')
    
    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    ax.set_title(title)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Speed map saved to: {output_path}')


def plot_correlation_map(motion_field, output_path='correlation_map.png',
                         title='Pattern Correlation', cmap='RdYlBu'):
    """
    Create correlation coefficient map.
    
    Parameters
    ----------
    motion_field : MotionField
        Motion field with correlation data
    output_path : str
        Output file path
    title : str
        Plot title
    cmap : str
        Colormap
    """
    if motion_field.correlation is None:
        raise ValueError('Motion field does not have correlation data')
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    im = ax.imshow(motion_field.correlation, cmap=cmap, vmin=0, vmax=1)
    
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Correlation Coefficient')
    
    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    ax.set_title(title)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Correlation map saved to: {output_path}')


def plot_motion_vectors_geographic(motion_field, lats, lons,
                                   output_path='geographic_quiver.png',
                                   stride=10, title='Sea Ice Drift (Geographic)',
                                   hemisphere='north'):
    """
    Create quiver plot on geographic projection.
    
    Parameters
    ----------
    motion_field : MotionField
        Motion field to plot
    lats, lons : 2D array
        Geographic coordinates
    output_path : str
        Output file path
    stride : int
        Stride for plotting arrows
    title : str
        Plot title
    hemisphere : str
        'north' or 'south' for polar projection
    """
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
    except ImportError:
        raise ImportError('cartopy is required for geographic plots. '
                          'Install with: pip install cartopy')
    
    rows, cols = motion_field.u.shape
    
    y_idx = np.arange(0, rows, stride)
    x_idx = np.arange(0, cols, stride)
    
    U = motion_field.u[y_idx[:, None], x_idx[None, :]]
    V = motion_field.v[y_idx[:, None], x_idx[None, :]]
    speed = np.sqrt(U**2 + V**2)
    
    lat_plot = lats[y_idx[:, None], x_idx[None, :]]
    lon_plot = lons[y_idx[:, None], x_idx[None, :]]
    
    if hemisphere == 'north':
        projection = ccrs.NorthPolarStereo()
    else:
        projection = ccrs.SouthPolarStereo()
    
    fig, ax = plt.subplots(figsize=(12, 10),
                           subplot_kw={'projection': projection})
    
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.gridlines()
    
    valid = ~(np.isnan(U) | np.isnan(V) | np.isnan(lat_plot) | np.isnan(lon_plot))
    
    if np.any(valid):
        U_valid = U[valid]
        V_valid = V[valid]
        lat_valid = lat_plot[valid]
        lon_valid = lon_plot[valid]
        speed_valid = speed[valid]
        
        vmin = np.nanmin(speed_valid)
        vmax = np.nanmax(speed_valid)
        norm = Normalize(vmin=vmin, vmax=vmax)
        
        q = ax.quiver(lon_valid, lat_valid, U_valid, V_valid, speed_valid,
                      transform=ccrs.PlateCarree(),
                      scale=20, cmap='viridis', norm=norm,
                      width=0.002)
        
        cbar = plt.colorbar(q, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Drift Speed (pixels)')
    
    ax.set_title(title)
    ax.set_extent([-180, 180, 50 if hemisphere == 'north' else -90, 
                   90 if hemisphere == 'north' else -50],
                  crs=ccrs.PlateCarree())
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Geographic quiver plot saved to: {output_path}')


def create_visualization_summary(motion_fields, preprocessed_images,
                                 output_dir='output', stride=10,
                                 hemisphere='north'):
    """
    Create complete visualization summary for all motion fields.
    
    Parameters
    ----------
    motion_fields : list
        List of MotionField objects
    preprocessed_images : list
        List of preprocessed image dicts
    output_dir : str
        Output directory
    stride : int
        Stride for quiver plots
    hemisphere : str
        'north' or 'south'
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for i, mf in enumerate(motion_fields):
        t1 = preprocessed_images[i]['timestamp']
        t2 = preprocessed_images[i+1]['timestamp']
        time_str = f'{t1.strftime("%Y%m%d_%H%M")}_to_{t2.strftime("%Y%m%d_%H%M")}'
        
        bg = preprocessed_images[i]['data']
        lats = preprocessed_images[i]['lats']
        lons = preprocessed_images[i]['lons']
        
        quiver_path = os.path.join(output_dir, f'quiver_{i:03d}_{time_str}.png')
        plot_quiver(mf, background=bg, stride=stride,
                    title=f'Sea Ice Drift {t1} to {t2}',
                    output_path=quiver_path)
        
        speed_path = os.path.join(output_dir, f'speed_{i:03d}_{time_str}.png')
        plot_speed_map(mf, output_path=speed_path,
                       title=f'Drift Speed {t1} to {t2}',
                       units='pixels')
        
        if mf.correlation is not None:
            corr_path = os.path.join(output_dir, f'correlation_{i:03d}_{time_str}.png')
            plot_correlation_map(mf, output_path=corr_path,
                                 title=f'Pattern Correlation {t1} to {t2}')
        
        try:
            geo_path = os.path.join(output_dir, f'geo_quiver_{i:03d}_{time_str}.png')
            plot_motion_vectors_geographic(mf, lats, lons,
                                           output_path=geo_path,
                                           stride=stride,
                                           hemisphere=hemisphere,
                                           title=f'Geographic Drift {t1} to {t2}')
        except ImportError:
            print('cartopy not available, skipping geographic plots')
    
    print(f'Visualizations saved to: {output_dir}')


def save_kinematic_to_netcdf(kinematic_list, output_path,
                              preprocessed_images=None,
                              extra_vars=None, global_attrs=None):
    """
    Save kinematic analysis results to NetCDF file.
    
    Parameters
    ----------
    kinematic_list : list
        List of KinematicAnalysis objects
    output_path : str
        Output file path
    preprocessed_images : list, optional
        Preprocessed image dicts for coordinate info
    extra_vars : dict, optional
        Additional variables to save
    global_attrs : dict, optional
        Global attributes
    """
    if not ANALYSIS_AVAILABLE:
        raise ImportError('Analysis module not available')
    
    n_time = len(kinematic_list)
    ref = kinematic_list[0]
    rows, cols = ref.vorticity.shape
    
    ds = Dataset(output_path, 'w', format='NETCDF4')
    
    ds.createDimension('time', n_time)
    ds.createDimension('y', rows)
    ds.createDimension('x', cols)
    
    def create_2d_var(name, long_name, units, data_list):
        var = ds.createVariable(name, 'f4', ('time', 'y', 'x'), fill_value=np.nan)
        var.long_name = long_name
        var.units = units
        for i, data in enumerate(data_list):
            var[i, :, :] = data
        return var
    
    create_2d_var('vorticity', 'Relative vorticity', 's-1',
                  [k.vorticity for k in kinematic_list])
    create_2d_var('divergence', 'Horizontal divergence', 's-1',
                  [k.divergence for k in kinematic_list])
    create_2d_var('shear_strain', 'Shear strain rate', 's-1',
                  [k.shear_strain for k in kinematic_list])
    create_2d_var('normal_strain', 'Normal strain rate', 's-1',
                  [k.normal_strain for k in kinematic_list])
    create_2d_var('total_strain', 'Total strain rate', 's-1',
                  [k.total_strain for k in kinematic_list])
    create_2d_var('okubo_weiss', 'Okubo-Weiss parameter', 's-2',
                  [k.okubo_weiss for k in kinematic_list])
    
    if preprocessed_images is not None and 'lats' in preprocessed_images[0]:
        lat_var = ds.createVariable('latitude', 'f8', ('y', 'x'))
        lat_var.units = 'degrees_north'
        lat_var[:] = preprocessed_images[0]['lats']
        
        lon_var = ds.createVariable('longitude', 'f8', ('y', 'x'))
        lon_var.units = 'degrees_east'
        lon_var[:] = preprocessed_images[0]['lons']
    
    if extra_vars:
        for name, (values, dims, attrs) in extra_vars.items():
            var = ds.createVariable(name, values.dtype, dims, fill_value=np.nan)
            var[:] = values
            for k, v in attrs.items():
                setattr(var, k, v)
    
    ds.title = 'Sea Ice Drift Kinematic Analysis'
    ds.history = f'Created on {datetime.now().isoformat()}'
    ds.Conventions = 'CF-1.8'
    
    if global_attrs:
        for k, v in global_attrs.items():
            setattr(ds, k, v)
    
    ds.close()
    print(f'Kinematic analysis saved to: {output_path}')


def save_ice_age_to_netcdf(ice_age_data, output_path,
                           lats=None, lons=None,
                           global_attrs=None):
    """
    Save ice age data and classification to NetCDF.
    
    Parameters
    ----------
    ice_age_data : IceAgeData
        Ice age classification results
    output_path : str
        Output file path
    lats, lons : 2D array, optional
        Coordinate arrays
    global_attrs : dict, optional
        Global attributes
    """
    if not ANALYSIS_AVAILABLE:
        raise ImportError('Analysis module not available')
    
    rows, cols = ice_age_data.ice_age.shape
    
    ds = Dataset(output_path, 'w', format='NETCDF4')
    
    ds.createDimension('y', rows)
    ds.createDimension('x', cols)
    
    age_var = ds.createVariable('ice_age', 'f4', ('y', 'x'), fill_value=np.nan)
    age_var.long_name = 'Ice age'
    age_var.units = 'years'
    age_var[:] = ice_age_data.ice_age
    
    type_var = ds.createVariable('ice_type', 'i1', ('y', 'x'), fill_value=0)
    type_var.long_name = 'Ice type classification'
    type_var.flag_values = [0, 1, 2]
    type_var.flag_meanings = 'water first_year_ice multi_year_ice'
    type_var[:] = np.nan_to_num(ice_age_data.ice_type, nan=0).astype(np.int8)
    
    fy_var = ds.createVariable('first_year_ice_mask', 'i1', ('y', 'x'), fill_value=0)
    fy_var.long_name = 'First-year ice mask'
    fy_var.units = '1'
    fy_var[:] = ice_age_data.fy_mask.astype(np.int8)
    
    my_var = ds.createVariable('multi_year_ice_mask', 'i1', ('y', 'x'), fill_value=0)
    my_var.long_name = 'Multi-year ice mask'
    my_var.units = '1'
    my_var[:] = ice_age_data.my_mask.astype(np.int8)
    
    if lats is not None:
        lat_var = ds.createVariable('latitude', 'f8', ('y', 'x'))
        lat_var.units = 'degrees_north'
        lat_var[:] = lats
        
        lon_var = ds.createVariable('longitude', 'f8', ('y', 'x'))
        lon_var.units = 'degrees_east'
        lon_var[:] = lons
    
    ds.title = 'Sea Ice Age Classification'
    ds.history = f'Created on {datetime.now().isoformat()}'
    ds.Conventions = 'CF-1.8'
    
    if global_attrs:
        for k, v in global_attrs.items():
            setattr(ds, k, v)
    
    ds.close()
    print(f'Ice age data saved to: {output_path}')


def plot_vorticity_map(kinematic, output_path='vorticity_map.png',
                       title='Vorticity', cmap='RdBu_r',
                       symlog_scale=True, linthresh=1e-7):
    """
    Plot vorticity map.
    
    Parameters
    ----------
    kinematic : KinematicAnalysis
        Kinematic analysis results
    output_path : str
        Output file path
    title : str
        Plot title
    cmap : str
        Colormap (diverging recommended)
    symlog_scale : bool
        Whether to use symmetric log scale
    linthresh : float
        Linear threshold for symlog scale
    """
    if not ANALYSIS_AVAILABLE:
        raise ImportError('Analysis module not available')
    
    vort = kinematic.vorticity * 1e6
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    if symlog_scale:
        vmax = np.nanmax(np.abs(vort))
        norm = SymLogNorm(linthresh=linthresh*1e6, vmin=-vmax, vmax=vmax, base=10)
    else:
        vmax = np.nanmax(np.abs(vort))
        norm = Normalize(vmin=-vmax, vmax=vmax)
    
    im = ax.imshow(vort, cmap=cmap, norm=norm)
    
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Vorticity (×10⁻⁶ s⁻¹)')
    
    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    ax.set_title(title)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Vorticity map saved to: {output_path}')


def plot_divergence_map(kinematic, output_path='divergence_map.png',
                        title='Divergence', cmap='RdBu_r',
                        symlog_scale=True, linthresh=1e-7):
    """
    Plot divergence map.
    
    Positive = divergence (ice opening)
    Negative = convergence (ice compaction)
    """
    if not ANALYSIS_AVAILABLE:
        raise ImportError('Analysis module not available')
    
    div = kinematic.divergence * 1e6
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    if symlog_scale:
        vmax = np.nanmax(np.abs(div))
        norm = SymLogNorm(linthresh=linthresh*1e6, vmin=-vmax, vmax=vmax, base=10)
    else:
        vmax = np.nanmax(np.abs(div))
        norm = Normalize(vmin=-vmax, vmax=vmax)
    
    im = ax.imshow(div, cmap=cmap, norm=norm)
    
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Divergence (×10⁻⁶ s⁻¹)')
    
    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    ax.set_title(title)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Divergence map saved to: {output_path}')


def plot_strain_rate_map(kinematic, output_path='strain_map.png',
                         title='Total Strain Rate', cmap='hot_r'):
    """
    Plot total strain rate map.
    """
    if not ANALYSIS_AVAILABLE:
        raise ImportError('Analysis module not available')
    
    strain = kinematic.total_strain * 1e6
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    vmax = np.nanpercentile(strain, 99)
    im = ax.imshow(strain, cmap=cmap, vmin=0, vmax=vmax)
    
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Total Strain Rate (×10⁻⁶ s⁻¹)')
    
    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    ax.set_title(title)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Strain rate map saved to: {output_path}')


def plot_ice_age_map(ice_age_data, output_path='ice_age_map.png',
                     title='Ice Age Distribution', cmap='viridis'):
    """
    Plot ice age classification map.
    """
    if not ANALYSIS_AVAILABLE:
        raise ImportError('Analysis module not available')
    
    from matplotlib.colors import ListedColormap, BoundaryNorm
    
    ice_type = ice_age_data.ice_type
    
    colors = ['lightblue', 'skyblue', 'darkblue']
    cmap_custom = ListedColormap(colors)
    bounds = [0, 0.5, 1.5, 2.5]
    norm = BoundaryNorm(bounds, cmap_custom.N)
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    im = ax.imshow(ice_type, cmap=cmap_custom, norm=norm,
                   interpolation='nearest')
    
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, ticks=[0.3, 1, 1.7])
    cbar.ax.set_yticklabels(['Water/Young', 'First-Year', 'Multi-Year'])
    
    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    ax.set_title(title)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Ice age map saved to: {output_path}')


def plot_eddies_overlay(kinematic, eddies, output_path='eddies_overlay.png',
                        title='Detected Eddies', background=None):
    """
    Plot detected eddies overlaid on vorticity map.
    
    Parameters
    ----------
    kinematic : KinematicAnalysis
        Kinematic analysis results
    eddies : list
        List of Eddy objects
    output_path : str
        Output file path
    title : str
        Plot title
    background : 2D array, optional
        Background image
    """
    if not ANALYSIS_AVAILABLE:
        raise ImportError('Analysis module not available')
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    if background is not None:
        ax.imshow(background, cmap='gray', alpha=0.5)
    
    vort = kinematic.vorticity * 1e6
    vmax = np.nanmax(np.abs(vort))
    ax.imshow(vort, cmap='RdBu_r', vmin=-vmax, vmax=vmax, alpha=0.7)
    
    for eddy in eddies:
        cy, cx = eddy.center
        radius_pix = eddy.radius / (kinematic.lats.shape[0] / 1000) if kinematic.lats is not None else eddy.radius
        
        color = 'red' if eddy.rotation_direction == 'cyclonic' else 'blue'
        circle = plt.Circle((cx, cy), radius_pix, color=color, fill=False,
                           linewidth=2, alpha=0.8)
        ax.add_patch(circle)
        
        rot_label = 'CCW' if eddy.rotation_direction == 'cyclonic' else 'CW'
        ax.text(cx, cy, f'{rot_label}\n{eddy.radius:.0f}km',
               ha='center', va='center', fontsize=8,
               color='white', fontweight='bold')
    
    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    ax.set_title(title)
    
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='none', edgecolor='red', label='Cyclonic (CCW)'),
        Patch(facecolor='none', edgecolor='blue', label='Anticyclonic (CW)')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Eddies overlay saved to: {output_path}')


def create_kinematic_summary(kinematic_list, eddies_list=None,
                             preprocessed_images=None, output_dir='output',
                             hemisphere='north'):
    """
    Create complete kinematic analysis visualization summary.
    
    Parameters
    ----------
    kinematic_list : list
        List of KinematicAnalysis objects
    eddies_list : list, optional
        List of eddy detection results (one per kinematic)
    preprocessed_images : list, optional
        Preprocessed images for backgrounds
    output_dir : str
        Output directory
    hemisphere : str
        'north' or 'south'
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for i, kin in enumerate(kinematic_list):
        t1 = preprocessed_images[i]['timestamp'] if preprocessed_images else None
        t2 = preprocessed_images[i+1]['timestamp'] if preprocessed_images else None
        time_str = f'{t1.strftime("%Y%m%d_%H%M")}_to_{t2.strftime("%Y%m%d_%H%M")}' if t1 else f'{i:03d}'
        
        bg = preprocessed_images[i]['data'] if preprocessed_images else None
        
        vort_path = os.path.join(output_dir, f'vorticity_{i:03d}_{time_str}.png')
        plot_vorticity_map(kin, output_path=vort_path,
                          title=f'Vorticity {time_str}')
        
        div_path = os.path.join(output_dir, f'divergence_{i:03d}_{time_str}.png')
        plot_divergence_map(kin, output_path=div_path,
                           title=f'Divergence {time_str}')
        
        strain_path = os.path.join(output_dir, f'strain_{i:03d}_{time_str}.png')
        plot_strain_rate_map(kin, output_path=strain_path,
                            title=f'Total Strain Rate {time_str}')
        
        if eddies_list and i < len(eddies_list):
            eddy_path = os.path.join(output_dir, f'eddies_{i:03d}_{time_str}.png')
            plot_eddies_overlay(kin, eddies_list[i], output_path=eddy_path,
                               title=f'Detected Eddies {time_str}',
                               background=bg)
    
    print(f'Kinematic visualizations saved to: {output_dir}')
