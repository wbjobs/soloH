"""
Advanced analysis module for sea ice drift fields.

Provides:
- Vorticity (curl) calculation for eddy detection
- Divergence calculation for convergence/divergence analysis
- Strain rate calculation (shear and normal components)
- Ice age data fusion (first-year vs multi-year ice)
- Kinematic feature detection (eddies, shear zones)
"""

import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter, label, find_objects
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, List
import warnings


@dataclass
class KinematicAnalysis:
    """Container for kinematic analysis results."""
    vorticity: np.ndarray
    divergence: np.ndarray
    shear_strain: np.ndarray
    normal_strain: np.ndarray
    total_strain: np.ndarray
    okubo_weiss: np.ndarray
    lats: np.ndarray = None
    lons: np.ndarray = None
    
    def summary(self):
        """Generate summary statistics."""
        return {
            'vorticity': {
                'mean': np.nanmean(self.vorticity),
                'std': np.nanstd(self.vorticity),
                'min': np.nanmin(self.vorticity),
                'max': np.nanmax(self.vorticity),
            },
            'divergence': {
                'mean': np.nanmean(self.divergence),
                'std': np.nanstd(self.divergence),
                'min': np.nanmin(self.divergence),
                'max': np.nanmax(self.divergence),
            },
            'total_strain': {
                'mean': np.nanmean(self.total_strain),
                'std': np.nanstd(self.total_strain),
            }
        }


@dataclass
class IceAgeData:
    """Container for ice age classification results."""
    ice_age: np.ndarray
    ice_type: np.ndarray
    fy_mask: np.ndarray
    my_mask: np.ndarray
    first_year_mask: np.ndarray = field(init=False)
    multi_year_mask: np.ndarray = field(init=False)
    
    def __post_init__(self):
        self.first_year_mask = self.fy_mask
        self.multi_year_mask = self.my_mask
    
    def summary(self):
        """Generate summary statistics."""
        total = np.sum(~np.isnan(self.ice_age))
        fy_count = np.sum(self.fy_mask)
        my_count = np.sum(self.my_mask)
        return {
            'total_valid_pixels': total,
            'first_year_ice': fy_count,
            'multi_year_ice': my_count,
            'fy_percentage': 100.0 * fy_count / total if total > 0 else 0,
            'my_percentage': 100.0 * my_count / total if total > 0 else 0,
        }


@dataclass
class Eddy:
    """Container for detected eddy features."""
    center: Tuple[int, int]
    center_geo: Optional[Tuple[float, float]]
    radius: float
    orientation: float
    vorticity: float
    okubo_weiss: float
    area_pixels: int
    area_km2: Optional[float]
    rotation_direction: str
    confidence: float


def compute_vorticity(u: np.ndarray, v: np.ndarray, resolution: float = 1.0,
                     smooth_sigma: float = 1.5) -> np.ndarray:
    """
    Compute vorticity (curl) of the velocity field.
    
    Vorticity = dv/dx - du/dy
    
    Positive values: counter-clockwise (cyclonic in NH)
    Negative values: clockwise (anticyclonic in NH)
    
    Parameters
    ----------
    u, v : 2D array
        Velocity components in x (east) and y (north) directions
    resolution : float
        Grid resolution in meters per pixel
    smooth_sigma : float
        Gaussian smoothing sigma applied to velocity before differentiation
        
    Returns
    -------
    2D array
        Vorticity in s^-1
    """
    u_s = gaussian_filter(u, sigma=smooth_sigma)
    v_s = gaussian_filter(v, sigma=smooth_sigma)
    
    dv_dx, _ = np.gradient(v_s)
    _, du_dy = np.gradient(u_s)
    
    vorticity = (dv_dx - du_dy) / resolution
    
    return vorticity


def compute_divergence(u: np.ndarray, v: np.ndarray, resolution: float = 1.0,
                       smooth_sigma: float = 1.5) -> np.ndarray:
    """
    Compute divergence of the velocity field.
    
    Divergence = du/dx + dv/dy
    
    Positive values: divergence (ice opening, new ice formation)
    Negative values: convergence (ice compaction, ridging)
    
    Parameters
    ----------
    u, v : 2D array
        Velocity components in x (east) and y (north) directions
    resolution : float
        Grid resolution in meters per pixel
    smooth_sigma : float
        Gaussian smoothing sigma applied to velocity before differentiation
        
    Returns
    -------
    2D array
        Divergence in s^-1
    """
    u_s = gaussian_filter(u, sigma=smooth_sigma)
    v_s = gaussian_filter(v, sigma=smooth_sigma)
    
    _, du_dx = np.gradient(u_s)
    dv_dy, _ = np.gradient(v_s)
    
    divergence = (du_dx + dv_dy) / resolution
    
    return divergence


def compute_strain_rates(u: np.ndarray, v: np.ndarray, resolution: float = 1.0,
                         smooth_sigma: float = 1.5) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute strain rate tensor components.
    
    Strain rate tensor:
    | du/dx   0.5*(du/dy + dv/dx) |
    | 0.5*(du/dy + dv/dx)   dv/dy |
    
    Parameters
    ----------
    u, v : 2D array
        Velocity components in x (east) and y (north) directions
    resolution : float
        Grid resolution in meters per pixel
    smooth_sigma : float
        Gaussian smoothing sigma
        
    Returns
    -------
    tuple
        (shear_strain, normal_strain, total_strain) in s^-1
    """
    u_s = gaussian_filter(u, sigma=smooth_sigma)
    v_s = gaussian_filter(v, sigma=smooth_sigma)
    
    du_dy, du_dx = np.gradient(u_s)
    dv_dy, dv_dx = np.gradient(v_s)
    
    du_dx /= resolution
    du_dy /= resolution
    dv_dx /= resolution
    dv_dy /= resolution
    
    normal_strain = du_dx + dv_dy
    shear_strain = np.sqrt((du_dx - dv_dy)**2 + (du_dy + dv_dx)**2)
    total_strain = np.sqrt(normal_strain**2 + shear_strain**2)
    
    return shear_strain, normal_strain, total_strain


def compute_okubo_weiss(u: np.ndarray, v: np.ndarray, resolution: float = 1.0,
                        smooth_sigma: float = 1.5) -> np.ndarray:
    """
    Compute Okubo-Weiss parameter for eddy detection.
    
    W = (du/dx - dv/dy)^2 + (du/dy + dv/dx)^2 - (dv/dx - du/dy)^2
    
    W > 0: strain-dominated regions
    W < 0: vorticity-dominated regions (eddies)
    
    Reference: Okubo (1970), Weiss (1991)
    
    Parameters
    ----------
    u, v : 2D array
        Velocity components
    resolution : float
        Grid resolution in meters per pixel
    smooth_sigma : float
        Gaussian smoothing sigma
        
    Returns
    -------
    2D array
        Okubo-Weiss parameter in s^-2
    """
    u_s = gaussian_filter(u, sigma=smooth_sigma)
    v_s = gaussian_filter(v, sigma=smooth_sigma)
    
    du_dy, du_dx = np.gradient(u_s)
    dv_dy, dv_dx = np.gradient(v_s)
    
    du_dx /= resolution
    du_dy /= resolution
    dv_dx /= resolution
    dv_dy /= resolution
    
    strain_term = (du_dx - dv_dy)**2 + (du_dy + dv_dx)**2
    vorticity = dv_dx - du_dy
    vorticity_term = vorticity**2
    
    ow = strain_term - vorticity_term
    
    return ow


def kinematic_analysis(u: np.ndarray, v: np.ndarray, resolution: float = 1.0,
                       smooth_sigma: float = 1.5, lats: np.ndarray = None,
                       lons: np.ndarray = None) -> KinematicAnalysis:
    """
    Complete kinematic analysis of a motion field.
    
    Parameters
    ----------
    u, v : 2D array
        Velocity components (m/s or pixel displacement)
    resolution : float
        Grid resolution in meters per pixel
    smooth_sigma : float
        Gaussian smoothing sigma for differentiation
    lats, lons : 2D array, optional
        Geographic coordinates
        
    Returns
    -------
    KinematicAnalysis
        Analysis results container
    """
    vorticity = compute_vorticity(u, v, resolution, smooth_sigma)
    divergence = compute_divergence(u, v, resolution, smooth_sigma)
    shear, normal, total = compute_strain_rates(u, v, resolution, smooth_sigma)
    ow = compute_okubo_weiss(u, v, resolution, smooth_sigma)
    
    return KinematicAnalysis(
        vorticity=vorticity,
        divergence=divergence,
        shear_strain=shear,
        normal_strain=normal,
        total_strain=total,
        okubo_weiss=ow,
        lats=lats,
        lons=lons
    )


def detect_eddies(kinematic: KinematicAnalysis, resolution: float = 12500.0,
                  min_radius_km: float = 25.0,
                  ow_threshold: float = -1e-10,
                  min_vorticity: float = 1e-6) -> List[Eddy]:
    """
    Detect coherent eddy structures using the Okubo-Weiss parameter.
    
    Parameters
    ----------
    kinematic : KinematicAnalysis
        Kinematic analysis results
    resolution : float
        Grid resolution in meters per pixel
    min_radius_km : float
        Minimum eddy radius in kilometers
    ow_threshold : float
        Okubo-Weiss threshold (negative = vorticity-dominated)
    min_vorticity : float
        Minimum absolute vorticity
        
    Returns
    -------
    list
        List of detected Eddy objects
    """
    ow = kinematic.okubo_weiss
    vort = kinematic.vorticity
    lats = kinematic.lats
    lons = kinematic.lons
    
    if ow is None or vort is None:
        return []
    
    resolution_km = resolution / 1000.0
    min_radius_pix = min_radius_km / resolution_km
    
    eddy_mask = (ow < ow_threshold) & (np.abs(vort) > min_vorticity)
    eddy_mask = np.nan_to_num(eddy_mask, nan=0).astype(int)
    
    labeled, n_labels = label(eddy_mask)
    
    eddies = []
    slices = find_objects(labeled)
    
    for i, sl in enumerate(slices):
        region_mask = labeled[sl] == (i + 1)
        
        area_pixels = np.sum(region_mask)
        radius_pix = np.sqrt(area_pixels / np.pi)
        
        if radius_pix < min_radius_pix:
            continue
        
        y_indices, x_indices = np.meshgrid(
            np.arange(sl[0].start, sl[0].stop),
            np.arange(sl[1].start, sl[1].stop),
            indexing='ij'
        )
        
        y_center = np.mean(y_indices[region_mask])
        x_center = np.mean(x_indices[region_mask])
        center = (int(y_center), int(x_center))
        
        center_geo = None
        if lats is not None and lons is not None:
            if 0 <= center[0] < lats.shape[0] and 0 <= center[1] < lats.shape[1]:
                center_geo = (lats[center[0], center[1]], lons[center[0], center[1]])
        
        region_vort = vort[sl][region_mask]
        region_ow = ow[sl][region_mask]
        
        mean_vort = np.mean(region_vort)
        mean_ow = np.mean(region_ow)
        
        rotation = 'cyclonic' if mean_vort > 0 else 'anticyclonic'
        
        area_km2 = area_pixels * resolution_km**2
        radius_km = radius_pix * resolution_km
        
        confidence = min(1.0, np.abs(mean_ow) / np.abs(ow_threshold))
        
        u_region = np.zeros_like(region_mask, dtype=float)
        v_region = np.zeros_like(region_mask, dtype=float)
        
        orientation = 0.0
        if area_pixels > 3:
            xs = x_indices[region_mask] - x_center
            ys = y_indices[region_mask] - y_center
            angles = np.arctan2(ys, xs)
            orientation = np.mean(angles)
        
        eddies.append(Eddy(
            center=center,
            center_geo=center_geo,
            radius=radius_km,
            orientation=orientation,
            vorticity=mean_vort,
            okubo_weiss=mean_ow,
            area_pixels=area_pixels,
            area_km2=area_km2,
            rotation_direction=rotation,
            confidence=confidence
        ))
    
    return eddies


def detect_convergence_zones(kinematic: KinematicAnalysis,
                             threshold: float = -1e-6,
                             min_size_km2: float = 500.0,
                             resolution: float = 12500.0) -> list:
    """
    Detect significant convergence zones.
    
    Parameters
    ----------
    kinematic : KinematicAnalysis
        Kinematic analysis results
    threshold : float
        Divergence threshold (negative = convergence)
    min_size_km2 : float
        Minimum zone area in km²
    resolution : float
        Grid resolution in meters
        
    Returns
    -------
    list
        List of convergence zone dictionaries
    """
    div = kinematic.divergence
    if div is None:
        return []
    
    resolution_km = resolution / 1000.0
    pix_area = resolution_km**2
    min_size_pix = min_size_km2 / pix_area
    
    conv_mask = (div < threshold)
    conv_mask = np.nan_to_num(conv_mask, nan=0).astype(int)
    
    labeled, n_labels = label(conv_mask)
    slices = find_objects(labeled)
    
    zones = []
    for i, sl in enumerate(slices):
        region_mask = labeled[sl] == (i + 1)
        area_pixels = np.sum(region_mask)
        
        if area_pixels < min_size_pix:
            continue
        
        y, x = np.where(region_mask)
        cy = sl[0].start + int(np.mean(y))
        cx = sl[1].start + int(np.mean(x))
        
        center_geo = None
        if kinematic.lats is not None and kinematic.lons is not None:
            center_geo = (kinematic.lats[cy, cx], kinematic.lons[cy, cx])
        
        mean_div = np.mean(div[sl][region_mask])
        area_km2 = area_pixels * pix_area
        
        zones.append({
            'center': (cy, cx),
            'center_geo': center_geo,
            'area_pixels': area_pixels,
            'area_km2': area_km2,
            'mean_divergence': mean_div,
            'strength': -mean_div
        })
    
    return zones


def classify_ice_age(ice_age_data: np.ndarray,
                     fy_threshold: float = 2.0,
                     my_threshold: float = 4.0,
                     nan_fill: float = np.nan) -> IceAgeData:
    """
    Classify ice into first-year (FY) and multi-year (MY) categories.
    
    Typical ice age values:
    - Open water / young ice: 0-0.5 years
    - First-year ice: 0.5-2 years
    - Second-year ice: 2-4 years
    - Multi-year ice: >4 years
    
    Parameters
    ----------
    ice_age_data : 2D array
        Ice age in years
    fy_threshold : float
        Upper threshold for first-year ice in years
    my_threshold : float
        Lower threshold for multi-year ice in years
    nan_fill : float
        Value to use for invalid/missing data
        
    Returns
    -------
    IceAgeData
        Ice age classification results
    """
    ice_age = np.where(np.isnan(ice_age_data), nan_fill, ice_age_data)
    
    fy_mask = (ice_age >= 0.5) & (ice_age < fy_threshold)
    my_mask = ice_age >= my_threshold
    
    ice_type = np.full(ice_age.shape, np.nan)
    ice_type[fy_mask] = 1
    ice_type[my_mask] = 2
    
    return IceAgeData(
        ice_age=ice_age,
        ice_type=ice_type,
        fy_mask=fy_mask,
        my_mask=my_mask
    )


def fuse_ice_age_motion(kinematic: KinematicAnalysis, ice_age: IceAgeData) -> Dict:
    """
    Analyze motion differences between first-year and multi-year ice.
    
    Parameters
    ----------
    kinematic : KinematicAnalysis
        Motion field kinematic analysis
    ice_age : IceAgeData
        Ice age classification
        
    Returns
    -------
    dict
        Comparison statistics between FY and MY ice
    """
    stats = {}
    
    for ice_type, mask in [('first_year', ice_age.fy_mask),
                           ('multi_year', ice_age.my_mask)]:
        if np.sum(mask) == 0:
            stats[ice_type] = None
            continue
        
        stats[ice_type] = {
            'count': int(np.sum(mask)),
            'mean_vorticity': float(np.nanmean(kinematic.vorticity[mask])),
            'std_vorticity': float(np.nanstd(kinematic.vorticity[mask])),
            'mean_divergence': float(np.nanmean(kinematic.divergence[mask])),
            'std_divergence': float(np.nanstd(kinematic.divergence[mask])),
            'mean_shear_strain': float(np.nanmean(kinematic.shear_strain[mask])),
            'mean_normal_strain': float(np.nanmean(kinematic.normal_strain[mask])),
            'mean_total_strain': float(np.nanmean(kinematic.total_strain[mask])),
        }
    
    if stats['first_year'] and stats['multi_year']:
        stats['differences'] = {
            'vorticity_diff': stats['first_year']['mean_vorticity'] - stats['multi_year']['mean_vorticity'],
            'divergence_diff': stats['first_year']['mean_divergence'] - stats['multi_year']['mean_divergence'],
            'shear_diff': stats['first_year']['mean_shear_strain'] - stats['multi_year']['mean_shear_strain'],
            'strain_ratio': stats['first_year']['mean_total_strain'] / (stats['multi_year']['mean_total_strain'] + 1e-15)
        }
    
    return stats


def read_ice_age_netcdf(file_path: str, variable_name: str = 'ice_age',
                        lat_name: str = 'latitude', lon_name: str = 'longitude') -> Dict:
    """
    Read ice age data from NetCDF file.
    
    Parameters
    ----------
    file_path : str
        Path to NetCDF file
    variable_name : str
        Name of ice age variable
    lat_name : str
        Name of latitude variable
    lon_name : str
        Name of longitude variable
        
    Returns
    -------
    dict
        Dictionary containing ice_age, latitudes, longitudes
    """
    try:
        from netCDF4 import Dataset
    except ImportError:
        raise ImportError('netCDF4 is required for reading ice age data')
    
    with Dataset(file_path, 'r') as ds:
        ice_age = ds.variables[variable_name][:]
        lats = ds.variables[lat_name][:]
        lons = ds.variables[lon_name][:]
        
        if hasattr(ice_age, 'mask'):
            ice_age = np.ma.filled(ice_age, np.nan)
    
    return {
        'ice_age': np.asarray(ice_age),
        'latitude': np.asarray(lats),
        'longitude': np.asarray(lons)
    }


def create_sample_ice_age(shape: Tuple[int, int], fy_fraction: float = 0.4,
                          my_fraction: float = 0.3) -> np.ndarray:
    """
    Create synthetic ice age data for testing.
    
    Parameters
    ----------
    shape : tuple
        (height, width) of output array
    fy_fraction : float
        Fraction of first-year ice pixels
    my_fraction : float
        Fraction of multi-year ice pixels
        
    Returns
    -------
    2D array
        Synthetic ice age data in years
    """
    rng = np.random.default_rng(42)
    
    ice_age = np.full(shape, np.nan)
    
    non_water = rng.random(shape) < (fy_fraction + my_fraction)
    
    fy_mask = non_water & (rng.random(shape) < (fy_fraction / (fy_fraction + my_fraction)))
    my_mask = non_water & ~fy_mask
    
    ice_age[fy_mask] = rng.uniform(0.5, 2.0, np.sum(fy_mask))
    ice_age[my_mask] = rng.uniform(4.0, 10.0, np.sum(my_mask))
    
    return ice_age


def compute_deformation_energy(kinematic: KinematicAnalysis,
                              ice_concentration: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Compute deformation energy of the ice pack.
    
    E = (1/2) * (shear_strain^2 + normal_strain^2) * ice_concentration
    
    Parameters
    ----------
    kinematic : KinematicAnalysis
        Kinematic analysis results
    ice_concentration : 2D array, optional
        Ice concentration (0-1)
        
    Returns
    -------
    2D array
        Deformation energy field
    """
    energy = 0.5 * (kinematic.shear_strain**2 + kinematic.normal_strain**2)
    
    if ice_concentration is not None:
        energy = energy * ice_concentration
    
    return energy
