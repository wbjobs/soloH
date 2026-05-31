import numpy as np
from numba import njit, prange
from typing import Optional, Tuple, Callable, List
from scipy.interpolate import interp1d, interp2d, RectBivariateSpline


def generate_topography(nx: int, dx: float,
                        topography_type: str = 'flat',
                        amplitude: float = 0.0,
                        wavelength: Optional[float] = None,
                        seed: Optional[int] = None,
                        **kwargs) -> np.ndarray:
    x = np.arange(nx) * dx
    
    if wavelength is None:
        wavelength = nx * dx / 4.0
    
    if topography_type == 'flat':
        elevation = np.zeros(nx)
    
    elif topography_type == 'hill':
        center_x = nx * dx / 2.0
        sigma = wavelength / 3.0
        elevation = amplitude * np.exp(-(x - center_x)**2 / (2 * sigma**2))
    
    elif topography_type == 'valley':
        center_x = nx * dx / 2.0
        sigma = wavelength / 3.0
        elevation = -amplitude * np.exp(-(x - center_x)**2 / (2 * sigma**2))
    
    elif topography_type == 'sine':
        k = 2 * np.pi / wavelength
        elevation = amplitude * np.sin(k * x)
    
    elif topography_type == 'cosine':
        k = 2 * np.pi / wavelength
        elevation = amplitude * np.cos(k * x)
    
    elif topography_type == 'random':
        if seed is not None:
            rng = np.random.RandomState(seed)
        else:
            rng = np.random
        
        elevation = np.zeros(nx)
        n_components = 5
        for i in range(n_components):
            freq = rng.uniform(0.5, 2.0) / wavelength
            phase = rng.uniform(0, 2 * np.pi)
            amp = amplitude * rng.uniform(0.3, 1.0)
            elevation += amp * np.sin(2 * np.pi * freq * x + phase)
    
    elif topography_type == 'step':
        step_x = nx * dx / 2.0
        elevation = np.where(x < step_x, 0.0, amplitude)
    
    elif topography_type == 'sag_and_bump':
        center1 = nx * dx / 3.0
        center2 = 2 * nx * dx / 3.0
        sigma = wavelength / 4.0
        elevation = (-amplitude * np.exp(-(x - center1)**2 / (2 * sigma**2)) +
                     amplitude * np.exp(-(x - center2)**2 / (2 * sigma**2)))
    
    elif topography_type == 'custom':
        if 'elevation' in kwargs:
            elevation = np.asarray(kwargs['elevation'])
            if len(elevation) != nx:
                raise ValueError(f"Custom elevation length {len(elevation)} != nx {nx}")
        else:
            raise ValueError("Custom topography requires 'elevation' keyword argument")
    
    else:
        raise ValueError(f"Unknown topography type: {topography_type}")
    
    return elevation


@njit(parallel=True)
def compute_curved_metrics_numba(X: np.ndarray, Z: np.ndarray,
                                dx: float, dz: float) -> Tuple[np.ndarray, ...]:
    nz, nx = X.shape
    
    xi_x = np.zeros((nz, nx), dtype=np.float64)
    xi_z = np.zeros((nz, nx), dtype=np.float64)
    zeta_x = np.zeros((nz, nx), dtype=np.float64)
    zeta_z = np.zeros((nz, nx), dtype=np.float64)
    J = np.ones((nz, nx), dtype=np.float64)
    
    for z in prange(1, nz - 1):
        for x in prange(1, nx - 1):
            dX_dxi = (X[z, x + 1] - X[z, x - 1]) / (2 * dx)
            dX_dzeta = (X[z + 1, x] - X[z - 1, x]) / (2 * dz)
            dZ_dxi = (Z[z, x + 1] - Z[z, x - 1]) / (2 * dx)
            dZ_dzeta = (Z[z + 1, x] - Z[z - 1, x]) / (2 * dz)
            
            det_J = dX_dxi * dZ_dzeta - dX_dzeta * dZ_dxi
            
            if abs(det_J) > 1e-10:
                xi_x[z, x] = dZ_dzeta / det_J
                xi_z[z, x] = -dX_dzeta / det_J
                zeta_x[z, x] = -dZ_dxi / det_J
                zeta_z[z, x] = dX_dxi / det_J
                J[z, x] = abs(det_J)
    
    for x in prange(nx):
        xi_x[0, x] = xi_x[1, x]
        xi_z[0, x] = xi_z[1, x]
        zeta_x[0, x] = zeta_x[1, x]
        zeta_z[0, x] = zeta_z[1, x]
        J[0, x] = J[1, x]
        
        xi_x[-1, x] = xi_x[-2, x]
        xi_z[-1, x] = xi_z[-2, x]
        zeta_x[-1, x] = zeta_x[-2, x]
        zeta_z[-1, x] = zeta_z[-2, x]
        J[-1, x] = J[-2, x]
    
    for z in prange(nz):
        xi_x[z, 0] = xi_x[z, 1]
        xi_z[z, 0] = xi_z[z, 1]
        zeta_x[z, 0] = zeta_x[z, 1]
        zeta_z[z, 0] = zeta_z[z, 1]
        J[z, 0] = J[z, 1]
        
        xi_x[z, -1] = xi_x[z, -2]
        xi_z[z, -1] = xi_z[z, -2]
        zeta_x[z, -1] = zeta_x[z, -2]
        zeta_z[z, -1] = zeta_z[z, -2]
        J[z, -1] = J[z, -2]
    
    return xi_x, xi_z, zeta_x, zeta_z, J


class CurvilinearGrid:
    def __init__(self, nx: int, nz: int, dx: float, dz: float,
                 topography: Optional[np.ndarray] = None,
                 topography_type: str = 'flat',
                 amplitude: float = 0.0,
                 stretching: str = 'linear',
                 stretch_factor: float = 1.0,
                 **topo_kwargs):
        self.nx = nx
        self.nz = nz
        self.dx = dx
        self.dz = dz
        self.topography_type = topography_type
        self.amplitude = amplitude
        self.stretching = stretching
        self.stretch_factor = stretch_factor
        
        if topography is None:
            self.topography = generate_topography(
                nx, dx, topography_type, amplitude, **topo_kwargs
            )
        else:
            self.topography = np.asarray(topography)
            if len(self.topography) != nx:
                raise ValueError(f"Topography length {len(self.topography)} != nx {nx}")
        
        self._generate_grid()
        self._compute_metrics()
    
    def _generate_grid(self):
        xi = np.arange(self.nx) * self.dx
        zeta = np.arange(self.nz) * self.dz
        max_depth = self.nz * self.dz
        
        if self.stretching == 'linear':
            zeta_stretch = zeta
        elif self.stretching == 'exponential':
            zeta_stretch = (np.exp(self.stretch_factor * zeta / max_depth) - 1) / \
                          (np.exp(self.stretch_factor) - 1) * max_depth
            zeta_stretch[0] = 0.0
            zeta_stretch[-1] = max_depth
        elif self.stretching == 'hyperbolic':
            z0 = max_depth * 0.1
            zeta_stretch = z0 * (np.exp(zeta / z0) - 1) / (np.exp(max_depth / z0) - 1) * max_depth
            zeta_stretch[0] = 0.0
            zeta_stretch[-1] = max_depth
        elif self.stretching == 'sigmoid':
            center = max_depth * 0.5
            width = max_depth * 0.2
            zeta_stretch = max_depth * (1 + np.tanh((zeta - center) / width)) / 2
            zeta_stretch[0] = 0.0
            zeta_stretch[-1] = max_depth
        else:
            raise ValueError(f"Unknown stretching type: {self.stretching}")
        
        dzeta = np.diff(zeta_stretch)
        if np.any(dzeta <= 0):
            zeta_stretch = np.linspace(0, max_depth, self.nz)
        
        XI, ZETA = np.meshgrid(xi, zeta_stretch)
        self.X = XI.copy()
        self.Z = ZETA.copy()
        
        max_topo = np.max(np.abs(self.topography))
        blend_width = max_depth * 0.15
        
        for i in range(self.nx):
            surface_elevation = self.topography[i]
            for j in range(self.nz):
                zeta_j = zeta_stretch[j]
                if zeta_j < blend_width:
                    blend = 1.0 - zeta_j / blend_width
                else:
                    blend = 0.0
                self.Z[j, i] = zeta_j + surface_elevation * blend
        
        self.physical_coords = (self.X, self.Z)
        self.computational_coords = (XI, ZETA)
    
    def _compute_metrics(self):
        (self.xi_x, self.xi_z, self.zeta_x, self.zeta_z, 
         self.J) = compute_curved_metrics_numba(self.X, self.Z, self.dx, self.dz)
        
        self.g_11 = self.xi_x**2 + self.xi_z**2
        self.g_12 = self.xi_x * self.zeta_x + self.xi_z * self.zeta_z
        self.g_22 = self.zeta_x**2 + self.zeta_z**2
    
    def get_surface_indices(self) -> np.ndarray:
        surface_indices = np.zeros(self.nx, dtype=np.int32)
        for i in range(self.nx):
            surface_indices[i] = np.argmin(np.abs(self.Z[:, i] - self.topography[i]))
        return surface_indices
    
    def interpolate_to_cartesian(self, field: np.ndarray,
                                x_cart: Optional[np.ndarray] = None,
                                z_cart: Optional[np.ndarray] = None,
                                method: str = 'linear') -> np.ndarray:
        if x_cart is None:
            x_cart = np.arange(self.nx) * self.dx
        if z_cart is None:
            z_cart = np.arange(self.nz) * self.dz
        
        if method == 'linear':
            interp = RectBivariateSpline(self.Z[:, 0], self.X[0, :], field, kx=1, ky=1)
            return interp(z_cart, x_cart)
        elif method == 'nearest':
            result = np.zeros((len(z_cart), len(x_cart)), dtype=field.dtype)
            for i, x in enumerate(x_cart):
                for j, z in enumerate(z_cart):
                    idx = np.argmin(np.abs(self.X - x) + np.abs(self.Z - z))
                    result[j, i] = field.flat[idx]
            return result
        else:
            raise ValueError(f"Unknown interpolation method: {method}")
    
    def interpolate_from_cartesian(self, field_cart: np.ndarray,
                                   x_cart: Optional[np.ndarray] = None,
                                   z_cart: Optional[np.ndarray] = None,
                                   method: str = 'linear') -> np.ndarray:
        if x_cart is None:
            x_cart = np.arange(self.nx) * self.dx
        if z_cart is None:
            z_cart = np.arange(self.nz) * self.dz
        
        if method == 'linear':
            interp = RectBivariateSpline(z_cart, x_cart, field_cart, kx=1, ky=1)
            return interp(self.Z[:, 0], self.X[0, :])
        else:
            raise ValueError(f"Unknown interpolation method: {method}")
    
    def get_cell_area(self) -> np.ndarray:
        return self.J * self.dx * self.dz
    
    def get_minimum_spacing(self) -> Tuple[float, float]:
        dx_phys = np.min(np.sqrt(np.diff(self.X, axis=1)**2 + np.diff(self.Z, axis=1)**2))
        dz_phys = np.min(np.sqrt(np.diff(self.X, axis=0)**2 + np.diff(self.Z, axis=0)**2))
        return dx_phys, dz_phys
    
    def export_to_vtk(self, filename: str,
                      fields: Optional[dict] = None) -> None:
        n_points = self.nx * self.nz
        n_cells = (self.nx - 1) * (self.nz - 1)
        
        with open(filename, 'w') as f:
            f.write("# vtk DataFile Version 3.0\n")
            f.write("Curvilinear Grid Data\n")
            f.write("ASCII\n")
            f.write("DATASET UNSTRUCTURED_GRID\n")
            f.write(f"POINTS {n_points} float\n")
            
            for j in range(self.nz):
                for i in range(self.nx):
                    f.write(f"{self.X[j, i]} {self.Z[j, i]} 0.0\n")
            
            f.write(f"\nCELLS {n_cells} {5 * n_cells}\n")
            for j in range(self.nz - 1):
                for i in range(self.nx - 1):
                    idx = j * self.nx + i
                    f.write(f"4 {idx} {idx+1} {idx+self.nx+1} {idx+self.nx}\n")
            
            f.write(f"\nCELL_TYPES {n_cells}\n")
            for _ in range(n_cells):
                f.write("9\n")
            
            if fields is not None:
                f.write(f"\nPOINT_DATA {n_points}\n")
                for name, field in fields.items():
                    f.write(f"SCALARS {name} float 1\n")
                    f.write("LOOKUP_TABLE default\n")
                    for j in range(self.nz):
                        for i in range(self.nx):
                            f.write(f"{field[j, i]}\n")
    
    def plot_grid(self, ax=None, show_elevation: bool = True,
                  interval: int = 5, **kwargs):
        import matplotlib.pyplot as plt
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        
        for i in range(0, self.nx, interval):
            ax.plot(self.X[:, i], self.Z[:, i], 'k-', linewidth=0.5, **kwargs)
        
        for j in range(0, self.nz, interval):
            ax.plot(self.X[j, :], self.Z[j, :], 'k-', linewidth=0.5, **kwargs)
        
        if show_elevation:
            ax.plot(self.X[0, :], self.topography, 'r-', linewidth=2, label='Topography')
            ax.legend()
        
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Z (m)')
        ax.set_aspect('equal')
        ax.set_title(f'Curvilinear Grid ({self.topography_type}, amp={self.amplitude}m)')
        
        return ax


@njit(parallel=True)
def transform_derivatives_curved(df_dxi: np.ndarray, df_dzeta: np.ndarray,
                                 xi_x: np.ndarray, xi_z: np.ndarray,
                                 zeta_x: np.ndarray, zeta_z: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    df_dx = df_dxi * xi_x + df_dzeta * zeta_x
    df_dz = df_dxi * xi_z + df_dzeta * zeta_z
    return df_dx, df_dz


class CurvilinearElasticSolver:
    def __init__(self, grid: CurvilinearGrid, config):
        self.grid = grid
        self.config = config
        self.nx = grid.nx
        self.nz = grid.nz
        self.dx = config.dx
        self.dz = config.dz
        
        self.half_order = config.space_order // 2
        self.dtype = config.dtype
        
        self._init_wavefields()
    
    def _init_wavefields(self):
        nx, nz = self.nx, self.nz
        dtype = self.dtype
        
        self.vx = np.zeros((nz, nx), dtype=dtype)
        self.vz = np.zeros((nz, nx), dtype=dtype)
        self.tau_xx = np.zeros((nz, nx), dtype=dtype)
        self.tau_zz = np.zeros((nz, nx), dtype=dtype)
        self.tau_xz = np.zeros((nz, nx), dtype=dtype)
        
        self.dvx_dxi = np.zeros((nz, nx), dtype=dtype)
        self.dvx_dzeta = np.zeros((nz, nx), dtype=dtype)
        self.dvz_dxi = np.zeros((nz, nx), dtype=dtype)
        self.dvz_dzeta = np.zeros((nz, nx), dtype=dtype)
        
        self.dtau_xx_dxi = np.zeros((nz, nx), dtype=dtype)
        self.dtau_xx_dzeta = np.zeros((nz, nx), dtype=dtype)
        self.dtau_zz_dxi = np.zeros((nz, nx), dtype=dtype)
        self.dtau_zz_dzeta = np.zeros((nz, nx), dtype=dtype)
        self.dtau_xz_dxi = np.zeros((nz, nx), dtype=dtype)
        self.dtau_xz_dzeta = np.zeros((nz, nx), dtype=dtype)
    
    def apply_topography_boundary_condition(self) -> None:
        surface_indices = self.grid.get_surface_indices()
        for i in range(self.nx):
            j_surface = surface_indices[i]
            if j_surface > 0 and j_surface < self.nz - 1:
                self.tau_zz[j_surface, i] = 0.0
                self.tau_xz[j_surface, i] = 0.0
                
                if j_surface > 0:
                    self.tau_zz[j_surface - 1, i] = -self.tau_zz[j_surface + 1, i]
                    self.tau_xz[j_surface - 1, i] = -self.tau_xz[j_surface + 1, i]
                    self.tau_xx[j_surface - 1, i] = self.tau_xx[j_surface + 1, i]
                    self.vx[j_surface - 1, i] = self.vx[j_surface + 1, i]
                    self.vz[j_surface - 1, i] = -self.vz[j_surface + 1, i]
    
    def get_physical_derivatives(self, dvar_dxi: np.ndarray, 
                                 dvar_dzeta: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        return transform_derivatives_curved(
            dvar_dxi, dvar_dzeta,
            self.grid.xi_x, self.grid.xi_z,
            self.grid.zeta_x, self.grid.zeta_z
        )
