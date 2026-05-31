"""
Validation module for sea ice drift estimates.

Includes:
- Comparison with buoy observations
- Scatter plots
- Bias statistics
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
from scipy.spatial import cKDTree
from scipy.stats import linregress


class BuoyObservation:
    """
    Container for buoy observation data.
    
    Attributes:
        id: buoy identifier
        lats: array of latitudes
        lons: array of longitudes
        times: array of datetime objects
        u: eastward velocity (m/s)
        v: northward velocity (m/s)
    """
    
    def __init__(self, buoy_id, lats, lons, times, u=None, v=None):
        self.id = buoy_id
        self.lats = np.asarray(lats, dtype=np.float64)
        self.lons = np.asarray(lons, dtype=np.float64)
        self.times = np.asarray(times)
        self.u = np.asarray(u, dtype=np.float64) if u is not None else None
        self.v = np.asarray(v, dtype=np.float64) if v is not None else None
        
        if self.u is None or self.v is None:
            self._compute_velocities()
    
    def _compute_velocities(self):
        """Compute velocities from position differences."""
        from pyproj import Geod
        
        geod = Geod(ellps='WGS84')
        
        self.u = np.zeros(len(self.lats) - 1)
        self.v = np.zeros(len(self.lats) - 1)
        
        for i in range(len(self.lats) - 1):
            _, _, distance = geod.inv(
                self.lons[i], self.lats[i],
                self.lons[i+1], self.lats[i+1]
            )
            
            dt = (self.times[i+1] - self.times[i]).total_seconds()
            
            if dt > 0:
                self.u[i] = (distance * np.cos(np.radians(45))) / dt
                self.v[i] = (distance * np.sin(np.radians(45))) / dt
    
    def get_velocity_at_time(self, time):
        """Interpolate velocity at specific time."""
        if len(self.times) < 2:
            return None, None
        
        times_num = np.array([t.timestamp() for t in self.times])
        t_num = time.timestamp()
        
        if t_num < times_num[0] or t_num > times_num[-1]:
            return None, None
        
        u_interp = np.interp(t_num, times_num[:-1], self.u)
        v_interp = np.interp(t_num, times_num[:-1], self.v)
        
        return u_interp, v_interp
    
    def __repr__(self):
        return f'BuoyObservation(id={self.id}, n_points={len(self.lats)})'


def load_buoy_data(csv_file):
    """
    Load buoy observations from CSV file.
    
    Expected CSV columns:
    buoy_id, latitude, longitude, time [, u, v]
    
    Parameters
    ----------
    csv_file : str
        Path to CSV file
        
    Returns
    -------
    list
        List of BuoyObservation objects
    """
    df = pd.read_csv(csv_file)
    
    required_cols = ['buoy_id', 'latitude', 'longitude', 'time']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f'CSV missing required column: {col}')
    
    df['time'] = pd.to_datetime(df['time'])
    
    buoys = []
    for buoy_id, group in df.groupby('buoy_id'):
        group = group.sort_values('time')
        
        u = group['u'].values if 'u' in group.columns else None
        v = group['v'].values if 'v' in group.columns else None
        
        buoy = BuoyObservation(
            buoy_id=buoy_id,
            lats=group['latitude'].values,
            lons=group['longitude'].values,
            times=group['time'].values,
            u=u,
            v=v
        )
        buoys.append(buoy)
    
    return buoys


def create_sample_buoy_data(num_buoys=5, num_points=10, 
                            lat_range=(70, 85), lon_range=(-100, 0),
                            save_path='sample_buoys.csv'):
    """
    Create synthetic buoy data for testing.
    
    Parameters
    ----------
    num_buoys : int
        Number of buoys to create
    num_points : int
        Number of time points per buoy
    lat_range : tuple
        (min_lat, max_lat)
    lon_range : tuple
        (min_lon, max_lon)
    save_path : str
        Output CSV file path
    """
    data = []
    
    base_time = datetime(2023, 1, 1)
    
    for b in range(num_buoys):
        lat0 = np.random.uniform(*lat_range)
        lon0 = np.random.uniform(*lon_range)
        
        for i in range(num_points):
            lat = lat0 + i * np.random.uniform(-0.1, 0.1)
            lon = lon0 + i * np.random.uniform(-0.1, 0.1)
            time = base_time + pd.Timedelta(hours=12*i)
            
            data.append({
                'buoy_id': f'BUOY_{b:03d}',
                'latitude': lat,
                'longitude': lon,
                'time': time.isoformat()
            })
    
    df = pd.DataFrame(data)
    df.to_csv(save_path, index=False)
    print(f'Sample buoy data saved to: {save_path}')
    return save_path


def extract_model_velocity_at_points(motion_field, lats, lons, target_time,
                                  model_lats, model_lons,
                                  method='nearest'):
    """
    Extract model velocity at specific geographic points.
    
    Parameters
    ----------
    motion_field : MotionField
        Model motion field
    lats, lons : float or array
        Query latitudes/longitudes
    target_time : datetime
        Time of the motion field
    model_lats, model_lons : 2D array
        Model coordinate grids
    method : str
        'nearest' or 'bilinear'
        
    Returns
    -------
    tuple
        (u_model, v_model) velocities in m/s
    """
    lats = np.atleast_1d(lats)
    lons = np.atleast_1d(lons)
    
    rows, cols = model_lats.shape
    
    flat_lats = model_lats.ravel()
    flat_lons = model_lons.ravel()
    flat_u = motion_field.velocity_u.ravel()
    flat_v = motion_field.velocity_v.ravel()
    
    valid = ~(np.isnan(flat_u) | np.isnan(flat_v) | \
            np.isnan(flat_lats) | np.isnan(flat_lons))
    
    if not np.any(valid):
        return np.full_like(lats, np.nan), np.full_like(lons, np.nan)
    
    tree = cKDTree(np.column_stack([
        flat_lons[valid], flat_lats[valid]]))
    
    u_model = np.zeros(len(lats))
    v_model = np.zeros(len(lats))
    
    for i, (lat, lon) in enumerate(zip(lats, lons)):
        if method == 'nearest':
            dist, idx = tree.query([lon, lat], k=1)
            if dist < 1.0:
                u_model[i] = flat_u[valid][idx]
                v_model[i] = flat_v[valid][idx]
            else:
                u_model[i] = np.nan
                v_model[i] = np.nan
        
        elif method == 'bilinear':
            dists, idxs = tree.query([lon, lat], k=4)
            valid_dists = dists < 2.0
            
            if np.any(valid_dists):
                weights = 1.0 / (dists[valid_dists] + 1e-10)
                weights /= weights.sum()
                
                u_model[i] = np.sum(weights * flat_u[valid][idxs[valid_dists]])
                v_model[i] = np.sum(weights * flat_v[valid][idxs[valid_dists]])
            else:
                u_model[i] = np.nan
                v_model[i] = np.nan
        
        else:
            raise ValueError(f'Unknown interpolation method: {method}')
    
    return u_model, v_model


def compare_with_buoys(motion_fields, preprocessed_images,
                     buoys, output_dir='validation'):
    """
    Compare model drift estimates with buoy observations.
    
    Parameters
    ----------
    motion_fields : list
        List of MotionField objects
    preprocessed_images : list
        List of preprocessed image dicts
    buoys : list
        List of BuoyObservation objects
    output_dir : str
        Output directory for results
        
    Returns
    -------
    dict
        Comparison results including statistics and matched data
    """
    os.makedirs(output_dir, exist_ok=True)
    
    results = {
        'buoy_id': [],
        'time': [],
        'buoy_u': [],
        'buoy_v': [],
        'model_u': [],
        'model_v': [],
        'buoy_speed': [],
        'model_speed': [],
    }
    
    times = [img['timestamp'] for img in preprocessed_images]
    
    for i, mf in enumerate(motion_fields):
        t1 = times[i]
        t2 = times[i+1]
        mid_time = t1 + (t2 - t1) / 2
        
        model_lats = preprocessed_images[i]['lats']
        model_lons = preprocessed_images[i]['lons']
        
        for buoy in buoys:
            u_buoy, v_buoy = buoy.get_velocity_at_time(mid_time)
            
            if u_buoy is None:
                continue
            
            time_idx = np.argmin(np.abs([(t - mid_time).total_seconds() 
                                       for t in buoy.times[:-1]]))
            
            lat_buoy = buoy.lats[time_idx]
            lon_buoy = buoy.lons[time_idx]
            
            u_model, v_model = extract_model_velocity_at_points(
                mf, lat_buoy, lon_buoy, mid_time,
                model_lats, model_lons, method='bilinear'
            )
            
            if not (np.isnan(u_model) or np.isnan(v_model)):
                results['buoy_id'].append(buoy.id)
                results['time'].append(mid_time)
                results['buoy_u'].append(u_buoy)
                results['buoy_v'].append(v_buoy)
                results['model_u'].append(u_model[0])
                results['model_v'].append(v_model[0])
                results['buoy_speed'].append(np.sqrt(u_buoy**2 + v_buoy**2))
                results['model_speed'].append(np.sqrt(u_model[0]**2 + v_model[0]**2))
    
    for key in results:
        results[key] = np.array(results[key])
    
    if len(results['buoy_id']) > 0:
        stats = compute_bias_statistics(results)
        
        plot_scatter_comparison(results, output_dir)
        plot_time_series(results, output_dir)
        
        results['statistics'] = stats
        
        stats_df = pd.DataFrame({
            'Metric': ['Mean Bias (U)', 'Mean Bias (V)', 'Mean Bias (Speed)',
                       'RMSE (U)', 'RMSE (V)', 'RMSE (Speed)',
                       'Correlation (U)', 'Correlation (V)', 'Correlation (Speed)',
                       'MAE (U)', 'MAE (V)', 'MAE (Speed)',
                       'N Points'],
            'Value': [stats['mean_bias_u'], stats['mean_bias_v'], stats['mean_bias_speed'],
                      stats['rmse_u'], stats['rmse_v'], stats['rmse_speed'],
                      stats['corr_u'], stats['corr_v'], stats['corr_speed'],
                      stats['mae_u'], stats['mae_v'], stats['mae_speed'],
                      stats['n_points']]
        })
        stats_df.to_csv(os.path.join(output_dir, 'bias_statistics.csv'), index=False)
    
    return results


def compute_bias_statistics(results):
    """
    Compute bias statistics between model and observations.
    
    Parameters
    ----------
    results : dict
        Comparison results dictionary
        
    Returns
    -------
    dict
        Statistics dictionary
    """
    valid = ~(np.isnan(results['model_u']) | np.isnan(results['buoy_u']) |
            np.isnan(results['model_v']) | np.isnan(results['buoy_v']))
    
    if not np.any(valid):
        return {'n_points': 0}
    
    model_u = results['model_u'][valid]
    model_v = results['model_v'][valid]
    buoy_u = results['buoy_u'][valid]
    buoy_v = results['buoy_v'][valid]
    model_speed = results['model_speed'][valid]
    buoy_speed = results['buoy_speed'][valid]
    
    bias_u = model_u - buoy_u
    bias_v = model_v - buoy_v
    bias_speed = model_speed - buoy_speed
    
    stats = {
        'n_points': np.sum(valid),
        'mean_bias_u': np.mean(bias_u),
        'mean_bias_v': np.mean(bias_v),
        'mean_bias_speed': np.mean(bias_speed),
        'std_bias_u': np.std(bias_u),
        'std_bias_v': np.std(bias_v),
        'std_bias_speed': np.std(bias_speed),
        'rmse_u': np.sqrt(np.mean(bias_u**2)),
        'rmse_v': np.sqrt(np.mean(bias_v**2)),
        'rmse_speed': np.sqrt(np.mean(bias_speed**2)),
        'mae_u': np.mean(np.abs(bias_u)),
        'mae_v': np.mean(np.abs(bias_v)),
        'mae_speed': np.mean(np.abs(bias_speed)),
        'corr_u': np.corrcoef(model_u, buoy_u)[0, 1] if len(model_u) > 1 else np.nan,
        'corr_v': np.corrcoef(model_v, buoy_v)[0, 1] if len(model_v) > 1 else np.nan,
        'corr_speed': np.corrcoef(model_speed, buoy_speed)[0, 1] if len(model_speed) > 1 else np.nan,
    }
    
    if len(model_u) > 2:
        slope_u, intercept_u, r_u, _, _ = linregress(model_u, buoy_u)
        slope_v, intercept_v, r_v, _, _ = linregress(model_v, buoy_v)
        stats.update({
            'slope_u': slope_u,
            'intercept_u': intercept_u,
            'r_squared_u': r_u**2,
            'slope_v': slope_v,
            'intercept_v': intercept_v,
            'r_squared_v': r_v**2,
        })
    
    return stats


def plot_scatter_comparison(results, output_dir='validation'):
    """
    Create scatter plots comparing model and buoy observations.
    
    Parameters
    ----------
    results : dict
        Comparison results
    output_dir : str
        Output directory
    """
    os.makedirs(output_dir, exist_ok=True)
    
    valid = ~(np.isnan(results['model_u']) | np.isnan(results['buoy_u']) |
            np.isnan(results['model_v']) | np.isnan(results['buoy_v']))
    
    if not np.any(valid):
        return
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    for ax_idx, (model_key, buoy_key, title) in enumerate([
        ('model_u', 'buoy_u', 'Eastward Velocity (U)'),
        ('model_v', 'buoy_v', 'Northward Velocity (V)'),
        ('model_speed', 'buoy_speed', 'Drift Speed'),
    ]):
        ax = axes[ax_idx]
        
        model_data = results[model_key][valid]
        buoy_data = results[buoy_key][valid]
        
        if len(model_data) < 2:
            continue
        
        vmin = min(np.nanmin(model_data), np.nanmin(buoy_data))
        vmax = max(np.nanmax(model_data), np.nanmax(buoy_data))
        
        scatter = ax.scatter(buoy_data, model_data, alpha=0.6, edgecolors='k', s=50)
        
        ax.plot([vmin, vmax], [vmin, vmax], 'r--', label='1:1 Line')
        
        if len(model_data) > 2:
            slope, intercept, r, _, _ = linregress(buoy_data, model_data)
            x_line = np.linspace(vmin, vmax, 100)
            ax.plot(x_line, slope * x_line + intercept, 'b-', 
                   label=f'Regression (R²={r**2:.3f})')
        
        ax.set_xlabel(f'Buoy {title} (m/s)')
        ax.set_ylabel(f'Model {title} (m/s)')
        ax.set_title(f'{title} Comparison')
        ax.legend()
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'scatter_comparison.png'), dpi=150, bbox_inches='tight')
    plt.close()
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    bias_u = results['model_u'][valid] - results['buoy_u'][valid]
    bias_v = results['model_v'][valid] - results['buoy_v'][valid]
    
    ax.quiver(np.zeros_like(bias_u), np.zeros_like(bias_v),
              bias_u, bias_v, angles='xy', scale_units='xy', scale=1,
              alpha=0.6)
    
    circle = plt.Circle((0, 0), np.mean(np.sqrt(bias_u**2 + bias_v**2)), 
                        fill=False, color='r', linestyle='--', label='Mean Bias')
    ax.add_artist(circle)
    
    ax.set_xlabel('Bias in U (m/s)')
    ax.set_ylabel('Bias in V (m/s)')
    ax.set_title('Velocity Bias Vectors')
    ax.axhline(0, color='k', linestyle='--', alpha=0.5)
    ax.axvline(0, color='k', linestyle='--', alpha=0.5)
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'bias_vectors.png'), dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f'Scatter plots saved to: {output_dir}')


def plot_time_series(results, output_dir='validation'):
    """
    Create time series plots of model and buoy comparisons.
    
    Parameters
    ----------
    results : dict
        Comparison results
    output_dir : str
        Output directory
    """
    os.makedirs(output_dir, exist_ok=True)
    
    if len(results['time']) == 0:
        return
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    
    times = results['time']
    buoy_ids = np.unique(results['buoy_id'])
    
    colors = plt.cm.tab10(np.arange(len(buoy_ids)))
    
    for bid, color in zip(buoy_ids, colors):
        mask = results['buoy_id'] == bid
        
        if not np.any(mask):
            continue
        
        axes[0].plot(times[mask], results['model_u'][mask], 'o-', 
                    label=f'Model U ({bid})', color=color, alpha=0.7)
        axes[0].plot(times[mask], results['buoy_u'][mask], 's--', 
                    label=f'Buoy U ({bid})', color=color, alpha=0.7,
                    markerfacecolor='none')
        
        axes[1].plot(times[mask], results['model_v'][mask], 'o-',
                    label=f'Model V ({bid})', color=color, alpha=0.7)
        axes[1].plot(times[mask], results['buoy_v'][mask], 's--',
                    label=f'Buoy V ({bid})', color=color, alpha=0.7,
                    markerfacecolor='none')
    
    axes[0].set_ylabel('Eastward Velocity (m/s)')
    axes[0].set_title('Eastward Velocity Time Series')
    axes[0].legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    axes[0].grid(True, alpha=0.3)
    
    axes[1].set_ylabel('Northward Velocity (m/s)')
    axes[1].set_title('Northward Velocity Time Series')
    axes[1].set_xlabel('Time')
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'time_series.png'), dpi=150, bbox_inches='tight')
    plt.close()
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    for bid, color in zip(buoy_ids, colors):
        mask = results['buoy_id'] == bid
        
        if not np.any(mask):
            continue
        
        ax.plot(times[mask], results['model_speed'][mask], 'o-',
               label=f'Model ({bid})', color=color, alpha=0.7)
        ax.plot(times[mask], results['buoy_speed'][mask], 's--',
               label=f'Buoy ({bid})', color=color, alpha=0.7,
               markerfacecolor='none')
    
    ax.set_ylabel('Drift Speed (m/s)')
    ax.set_title('Drift Speed Time Series')
    ax.set_xlabel('Time')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'speed_time_series.png'), dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f'Time series plots saved to: {output_dir}')
