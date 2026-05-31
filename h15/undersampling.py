import numpy as np
from typing import Tuple


def cartesian_mask(
    size: int = 256,
    acceleration: float = 4.0,
    partial_fourier: float = 0.0,
    center_fraction: float = 0.08,
    seed: int = None,
    random_t: bool = False,
    num_frames: int = 1
) -> np.ndarray:
    """
    Generate Cartesian under-sampling mask.
    
    Args:
        size: Image size
        acceleration: Acceleration factor (R)
        partial_fourier: Partial Fourier fraction (0-1)
        center_fraction: Fraction of center k-space to fully sample
        seed: Random seed
        random_t: Use different random pattern per time frame
        num_frames: Number of time frames for dynamic imaging
        
    Returns:
        2D or 3D sampling mask (num_frames x size x size if random_t)
    """
    if seed is not None:
        np.random.seed(seed)
    
    if not random_t or num_frames == 1:
        mask = np.zeros((size, size), dtype=np.float64)
        
        num_center = int(size * center_fraction)
        center_start = size // 2 - num_center // 2
        center_end = center_start + num_center
        mask[:, center_start:center_end] = 1.0
        
        num_sampled = int(size / acceleration) - num_center
        if num_sampled > 0:
            outer_cols = np.concatenate([
                np.arange(0, center_start),
                np.arange(center_end, size)
            ])
            sampled_cols = np.random.choice(outer_cols, num_sampled, replace=False)
            mask[:, sampled_cols] = 1.0
        
        if partial_fourier > 0:
            cutoff = int(size * (1 - partial_fourier))
            mask[cutoff:, :] = 0
        
        return mask
    else:
        masks = np.zeros((num_frames, size, size), dtype=np.float64)
        
        for t in range(num_frames):
            if seed is not None:
                np.random.seed(seed + t)
            
            num_center = int(size * center_fraction)
            center_start = size // 2 - num_center // 2
            center_end = center_start + num_center
            masks[t, :, center_start:center_end] = 1.0
            
            num_sampled = int(size / acceleration) - num_center
            if num_sampled > 0:
                outer_cols = np.concatenate([
                    np.arange(0, center_start),
                    np.arange(center_end, size)
                ])
                sampled_cols = np.random.choice(outer_cols, num_sampled, replace=False)
                masks[t, :, sampled_cols] = 1.0
            
            if partial_fourier > 0:
                cutoff = int(size * (1 - partial_fourier))
                masks[t, cutoff:, :] = 0
        
        return masks


def radial_mask(
    size: int = 256,
    num_spokes: int = 64,
    golden_angle: bool = False
) -> np.ndarray:
    """
    Generate radial sampling mask.
    
    Args:
        size: Image size
        num_spokes: Number of radial spokes
        golden_angle: Use golden angle ordering
        
    Returns:
        2D sampling mask
    """
    mask = np.zeros((size, size), dtype=np.float64)
    center = size // 2
    
    if golden_angle:
        golden = np.pi * (3 - np.sqrt(5))
        angles = np.arange(num_spokes) * golden
    else:
        angles = np.linspace(0, np.pi, num_spokes, endpoint=False)
    
    max_r = size // 2
    r = np.arange(max_r)
    
    for theta in angles:
        x = (center + r * np.cos(theta)).astype(int)
        y = (center + r * np.sin(theta)).astype(int)
        valid = (x >= 0) & (x < size) & (y >= 0) & (y < size)
        mask[y[valid], x[valid]] = 1.0
        
        x = (center - r * np.cos(theta)).astype(int)
        y = (center - r * np.sin(theta)).astype(int)
        valid = (x >= 0) & (x < size) & (y >= 0) & (y < size)
        mask[y[valid], x[valid]] = 1.0
    
    mask[center, center] = 1.0
    return mask


def spiral_mask(
    size: int = 256,
    num_arms: int = 16,
    num_interleaves: int = 1,
    max_radius: float = None,
    use_density_compensation: bool = True
) -> np.ndarray:
    """
    Generate spiral sampling mask with optional density compensation.
    
    Args:
        size: Image size
        num_arms: Number of spiral arms
        num_interleaves: Number of interleaves
        max_radius: Maximum radius (default: size/2)
        use_density_compensation: Apply 1/r density weighting
        
    Returns:
        2D sampling mask (with density weights if enabled)
    """
    mask = np.zeros((size, size), dtype=np.float64)
    density_weights = np.zeros((size, size), dtype=np.float64)
    center = size // 2
    
    if max_radius is None:
        max_radius = size // 2
    
    total_arms = num_arms * num_interleaves
    
    for arm in range(total_arms):
        theta_offset = 2 * np.pi * arm / total_arms
        
        for t in np.linspace(0, 1, int(max_radius * 5)):
            r = t * max_radius
            theta = theta_offset + 8 * np.pi * t
            
            x = int(center + r * np.cos(theta))
            y = int(center + r * np.sin(theta))
            
            if 0 <= x < size and 0 <= y < size:
                if use_density_compensation:
                    r_eff = np.sqrt((x - center) ** 2 + (y - center) ** 2)
                    dcf = max(r_eff, 1.0) / max_radius
                    weight = np.clip(dcf, 0.1, 1.0)
                    mask[y, x] = max(mask[y, x], weight)
                    density_weights[y, x] = weight
                else:
                    mask[y, x] = 1.0
    
    if use_density_compensation:
        center_radius = max_radius * 0.08
        for dy in range(-int(center_radius), int(center_radius) + 1):
            for dx in range(-int(center_radius), int(center_radius) + 1):
                x = center + dx
                y = center + dy
                if 0 <= x < size and 0 <= y < size:
                    if mask[y, x] > 0:
                        r = np.sqrt(dx * dx + dy * dy)
                        if r <= center_radius:
                            mask[y, x] = 0.1 + 0.9 * (r / center_radius)
    
    if mask[center, center] == 0:
        mask[center, center] = 1.0
    
    return mask


def random_mask(
    size: int = 256,
    acceleration: float = 4.0,
    center_fraction: float = 0.08,
    pdf_exponent: float = 2.0,
    seed: int = None
) -> np.ndarray:
    """
    Generate random under-sampling mask with variable density.
    
    Args:
        size: Image size
        acceleration: Acceleration factor
        center_fraction: Fraction of center k-space to fully sample
        pdf_exponent: Exponent for radial probability density
        seed: Random seed
        
    Returns:
        2D sampling mask
    """
    if seed is not None:
        np.random.seed(seed)
    
    mask = np.zeros((size, size), dtype=np.float64)
    
    x = np.linspace(-1, 1, size)
    y = np.linspace(-1, 1, size)
    X, Y = np.meshgrid(x, y)
    R = np.sqrt(X ** 2 + Y ** 2)
    
    num_center = int(size * center_fraction)
    center_start = size // 2 - num_center // 2
    center_end = center_start + num_center
    mask[center_start:center_end, center_start:center_end] = 1.0
    
    pdf = 1.0 / (1.0 + R ** pdf_exponent)
    pdf[mask == 1.0] = 0
    
    total_samples = int(size * size / acceleration)
    center_samples = num_center * num_center
    outer_samples = total_samples - center_samples
    
    if outer_samples > 0:
        pdf_flat = pdf.flatten()
        pdf_flat = pdf_flat / pdf_flat.sum()
        
        indices = np.random.choice(
            size * size,
            outer_samples,
            replace=False,
            p=pdf_flat
        )
        
        mask_flat = mask.flatten()
        mask_flat[indices] = 1.0
        mask = mask_flat.reshape((size, size))
    
    return mask


def get_sampling_patterns() -> dict:
    """Get available sampling patterns with descriptions."""
    return {
        'cartesian': 'Cartesian under-sampling',
        'radial': 'Radial sampling',
        'spiral': 'Spiral sampling',
        'random': 'Random variable-density sampling',
    }


def generate_mask(
    pattern: str,
    size: int = 256,
    **kwargs
) -> np.ndarray:
    """
    Generate sampling mask of specified pattern.
    
    Args:
        pattern: Sampling pattern name
        size: Image size
        **kwargs: Pattern-specific parameters
        
    Returns:
        2D sampling mask
    """
    pattern = pattern.lower()
    
    if pattern == 'cartesian':
        return cartesian_mask(size, **kwargs)
    elif pattern == 'radial':
        return radial_mask(size, **kwargs)
    elif pattern == 'spiral':
        return spiral_mask(size, **kwargs)
    elif pattern == 'random':
        return random_mask(size, **kwargs)
    else:
        raise ValueError(f"Unknown sampling pattern: {pattern}")
