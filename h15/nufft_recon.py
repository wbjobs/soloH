import numpy as np
from typing import Tuple, Optional, List
import warnings

try:
    import finufft
    FINUFFT_AVAILABLE = True
except ImportError:
    FINUFFT_AVAILABLE = False
    warnings.warn("FINUFFT not available. Using numpy-based gridding as fallback.")


def generate_radial_trajectory(
    num_spokes: int = 64,
    num_samples: int = 256,
    fov: float = 1.0,
    golden_angle: bool = False
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate radial k-space trajectory coordinates.
    
    Args:
        num_spokes: Number of radial spokes
        num_samples: Number of samples per spoke
        fov: Field of view (normalized units)
        golden_angle: Use golden angle ordering
        
    Returns:
        kx, ky: k-space coordinates (normalized to [-pi, pi])
    """
    if golden_angle:
        golden = np.pi * (3 - np.sqrt(5))
        angles = np.arange(num_spokes) * golden
    else:
        angles = np.linspace(0, np.pi, num_spokes, endpoint=False)
    
    kx = np.zeros((num_spokes, num_samples))
    ky = np.zeros((num_spokes, num_samples))
    
    r = np.linspace(-1, 1, num_samples) * fov * np.pi
    
    for i, theta in enumerate(angles):
        kx[i] = r * np.cos(theta)
        ky[i] = r * np.sin(theta)
    
    return kx.flatten(), ky.flatten()


def generate_spiral_trajectory(
    num_arms: int = 16,
    num_samples: int = 512,
    fov: float = 1.0,
    max_theta: float = 8 * np.pi
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate spiral k-space trajectory coordinates.
    
    Args:
        num_arms: Number of spiral arms
        num_samples: Number of samples per arm
        fov: Field of view
        max_theta: Maximum rotation angle
        
    Returns:
        kx, ky: k-space coordinates (normalized to [-pi, pi])
    """
    kx = np.zeros((num_arms, num_samples))
    ky = np.zeros((num_arms, num_samples))
    
    for arm in range(num_arms):
        theta_offset = 2 * np.pi * arm / num_arms
        t = np.linspace(0, 1, num_samples)
        r = t * fov * np.pi
        theta = theta_offset + max_theta * t
        
        kx[arm] = r * np.cos(theta)
        ky[arm] = r * np.sin(theta)
    
    return kx.flatten(), ky.flatten()


def generate_random_trajectory(
    num_samples: int = 65536,
    fov: float = 1.0,
    pdf_exponent: float = 2.0,
    seed: int = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate random variable-density k-space trajectory.
    
    Args:
        num_samples: Total number of k-space samples
        fov: Field of view
        pdf_exponent: Radial probability density exponent
        seed: Random seed
        
    Returns:
        kx, ky: k-space coordinates (normalized to [-pi, pi])
    """
    if seed is not None:
        np.random.seed(seed)
    
    kx = np.zeros(num_samples)
    ky = np.zeros(num_samples)
    
    for i in range(num_samples):
        while True:
            x = np.random.uniform(-1, 1)
            y = np.random.uniform(-1, 1)
            r = np.sqrt(x ** 2 + y ** 2)
            if r <= 1:
                pdf = 1.0 / (1.0 + r ** pdf_exponent)
                if np.random.random() < pdf:
                    kx[i] = x * fov * np.pi
                    ky[i] = y * fov * np.pi
                    break
    
    return kx, ky


def kaiser_bessel_kernel(r: np.ndarray, width: float = 2.5, beta: float = 2.34) -> np.ndarray:
    """
    Kaiser-Bessel gridding kernel.
    
    Args:
        r: Normalized distance from grid point
        width: Kernel width in grid units
        beta: Shape parameter
        
    Returns:
        Kernel values
    """
    from scipy.special import iv
    
    r_abs = np.abs(r)
    mask = r_abs < width
    r_valid = r_abs[mask]
    
    arg = beta * np.sqrt(1 - (r_valid / width) ** 2)
    kernel = np.zeros_like(r)
    kernel[mask] = iv(0, arg) / iv(0, beta)
    
    return kernel


def compute_density_compensation(
    kx: np.ndarray,
    ky: np.ndarray,
    method: str = 'voronoi'
) -> np.ndarray:
    """
    Compute density compensation weights for non-Cartesian sampling.
    
    Args:
        kx, ky: k-space coordinates
        method: 'voronoi' or 'distance'
        
    Returns:
        Density compensation weights
    """
    num_samples = len(kx)
    
    if method == 'distance':
        weights = np.ones(num_samples)
        for i in range(num_samples):
            dists = np.sqrt((kx - kx[i]) ** 2 + (ky - ky[i]) ** 2)
            dists[dists == 0] = np.inf
            weights[i] = np.min(dists)
        weights = weights / weights.max()
    else:
        try:
            from scipy.spatial import Voronoi
            points = np.column_stack([kx, ky])
            vor = Voronoi(points)
            weights = np.zeros(num_samples)
            for i in range(num_samples):
                region = vor.regions[vor.point_region[i]]
                if -1 not in region and len(region) > 0:
                    vertices = vor.vertices[region]
                    weights[i] = np.abs(np.dot(
                        vertices[:, 0] - np.roll(vertices[:, 0], 1),
                        vertices[:, 1] + np.roll(vertices[:, 1], 1)
                    )) / 2
            weights = weights / weights.max()
        except:
            weights = compute_density_compensation(kx, ky, method='distance')
    
    weights[weights == 0] = weights[weights > 0].min()
    return weights


def grid_noncartesian(
    kx: np.ndarray,
    ky: np.ndarray,
    kspace_data: np.ndarray,
    grid_size: int = 256,
    kernel_width: float = 2.5
) -> np.ndarray:
    """
    Grid non-Cartesian k-space data onto Cartesian grid.
    
    Args:
        kx, ky: k-space coordinates
        kspace_data: k-space values (complex)
        grid_size: Size of output Cartesian grid
        kernel_width: Gridding kernel width
        
    Returns:
        Gridded k-space data (grid_size x grid_size)
    """
    grid = np.zeros((grid_size, grid_size), dtype=np.complex128)
    density = np.zeros((grid_size, grid_size), dtype=np.float64)
    
    kx_norm = (kx + np.pi) / (2 * np.pi) * grid_size
    ky_norm = (ky + np.pi) / (2 * np.pi) * grid_size
    
    kernel_half = int(np.ceil(kernel_width))
    
    for i in range(len(kx)):
        x = kx_norm[i]
        y = ky_norm[i]
        val = kspace_data[i]
        
        x_floor = int(np.floor(x))
        y_floor = int(np.floor(y))
        
        for dx in range(-kernel_half, kernel_half + 1):
            for dy in range(-kernel_half, kernel_half + 1):
                gx = x_floor + dx
                gy = y_floor + dy
                
                if 0 <= gx < grid_size and 0 <= gy < grid_size:
                    dist = np.sqrt((x - (gx + 0.5)) ** 2 + (y - (gy + 0.5)) ** 2)
                    if dist < kernel_width:
                        kernel = kaiser_bessel_kernel(dist, kernel_width)
                        grid[gy, gx] += val * kernel
                        density[gy, gx] += kernel
    
    density[density == 0] = 1
    grid = grid / density
    
    return grid


def nufft_forward(
    img: np.ndarray,
    kx: np.ndarray,
    ky: np.ndarray,
    use_finufft: bool = True
) -> np.ndarray:
    """
    Forward NUFFT: image -> non-Cartesian k-space.
    
    Args:
        img: Input image (2D)
        kx, ky: Target k-space coordinates
        use_finufft: Use FINUFFT if available
        
    Returns:
        k-space values at specified coordinates
    """
    if FINUFFT_AVAILABLE and use_finufft:
        kspace = finufft.nufft2d3(kx, ky, img.astype(np.complex128), isign=-1, eps=1e-6)
        return kspace
    else:
        grid_size = img.shape[0]
        kspace_full = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(img)))
        
        kx_idx = ((kx + np.pi) / (2 * np.pi) * grid_size).astype(int)
        ky_idx = ((ky + np.pi) / (2 * np.pi) * grid_size).astype(int)
        
        kx_idx = np.clip(kx_idx, 0, grid_size - 1)
        ky_idx = np.clip(ky_idx, 0, grid_size - 1)
        
        return kspace_full[ky_idx, kx_idx]


def nufft_adjoint(
    kspace_data: np.ndarray,
    kx: np.ndarray,
    ky: np.ndarray,
    grid_size: int = 256,
    density_comp: np.ndarray = None,
    use_finufft: bool = True
) -> np.ndarray:
    """
    Adjoint NUFFT: non-Cartesian k-space -> image.
    
    Args:
        kspace_data: k-space values
        kx, ky: k-space coordinates
        grid_size: Output image size
        density_comp: Density compensation weights
        use_finufft: Use FINUFFT if available
        
    Returns:
        Reconstructed image
    """
    if density_comp is not None:
        kspace_data = kspace_data * density_comp
    
    if FINUFFT_AVAILABLE and use_finufft:
        img = finufft.nufft2d3(kx, ky, kspace_data.astype(np.complex128), 
                              n_modes=(grid_size, grid_size), isign=1, eps=1e-6)
        return np.abs(img)
    else:
        grid = grid_noncartesian(kx, ky, kspace_data, grid_size)
        img = np.abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(grid))))
        return img


def gridding_reconstruction(
    kspace_data: np.ndarray,
    kx: np.ndarray,
    ky: np.ndarray,
    grid_size: int = 256,
    num_iter: int = 20,
    use_density_comp: bool = True,
    verbose: bool = False
) -> np.ndarray:
    """
    Iterative gridding reconstruction with conjugate gradient.
    
    Args:
        kspace_data: Non-Cartesian k-space data
        kx, ky: k-space coordinates
        grid_size: Output image size
        num_iter: Number of CG iterations
        use_density_comp: Use density compensation
        verbose: Print progress
        
    Returns:
        Reconstructed image
    """
    if use_density_comp:
        density_comp = compute_density_compensation(kx, ky)
    else:
        density_comp = None
    
    x = nufft_adjoint(kspace_data, kx, ky, grid_size, density_comp)
    
    r = kspace_data.copy()
    p = r.copy()
    rs_old = np.sum(np.abs(r) ** 2)
    
    for i in range(num_iter):
        Ap = nufft_forward(
            nufft_adjoint(p, kx, ky, grid_size, density_comp),
            kx, ky
        )
        
        if use_density_comp:
            Ap = Ap * density_comp
        
        pAp = np.sum(np.conj(p) * Ap)
        alpha = rs_old / pAp if np.abs(pAp) > 1e-10 else 0
        
        x = x + alpha * nufft_adjoint(p, kx, ky, grid_size, density_comp)
        r = r - alpha * Ap
        
        rs_new = np.sum(np.abs(r) ** 2)
        
        if verbose and i % 5 == 0:
            print(f"Gridding CG Iteration {i}, Residual: {np.sqrt(rs_new):.2e}")
        
        if np.sqrt(rs_new) < 1e-6:
            break
        
        beta = rs_new / rs_old if rs_old > 1e-10 else 0
        p = r + beta * p
        rs_old = rs_new
    
    return np.clip(np.abs(x), 0, None)


def get_available_trajectories() -> dict:
    """Get available non-Cartesian trajectories."""
    return {
        'radial': 'Radial trajectory',
        'spiral': 'Spiral trajectory',
        'random': 'Random variable-density',
    }
