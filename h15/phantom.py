import numpy as np
from typing import Tuple


def shepp_logan_phantom(size: int = 256) -> np.ndarray:
    """
    Generate modified Shepp-Logan phantom.
    
    Args:
        size: Image size (size x size)
        
    Returns:
        2D numpy array of the phantom
    """
    n = size
    p = np.zeros((n, n), dtype=np.float64)
    
    x = np.linspace(-1, 1, n)
    y = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(x, y)
    
    ellipses = [
        (1.0,  0.6900, 0.9200,  0.0000,  0.0000,  0.0000),
        (-0.80, 0.6624, 0.8740,  0.0000, -0.0184,  0.0000),
        (-0.20, 0.1100, 0.3100,  0.2200,  0.0000, -18.0000),
        (-0.20, 0.1600, 0.4100, -0.2200,  0.0000,  18.0000),
        (0.10,  0.2100, 0.2500,  0.0000,  0.3500,  0.0000),
        (0.10,  0.0460, 0.0460,  0.0000,  0.1000,  0.0000),
        (0.10,  0.0460, 0.0460,  0.0000, -0.1000,  0.0000),
        (0.10,  0.0460, 0.0230, -0.0800, -0.6050,  0.0000),
        (0.10,  0.0230, 0.0230,  0.0000, -0.6060,  0.0000),
        (0.10,  0.0460, 0.0230,  0.0600, -0.6050,  0.0000),
    ]
    
    for rho, a, b, x0, y0, phi in ellipses:
        phi = np.radians(phi)
        cos_phi = np.cos(phi)
        sin_phi = np.sin(phi)
        
        X_rot = (X - x0) * cos_phi + (Y - y0) * sin_phi
        Y_rot = -(X - x0) * sin_phi + (Y - y0) * cos_phi
        
        mask = (X_rot / a) ** 2 + (Y_rot / b) ** 2 <= 1
        p[mask] += rho
    
    p = np.clip(p, 0, None)
    return p / p.max()


def generate_sensitivity_maps(
    size: int = 256,
    num_channels: int = 8
) -> np.ndarray:
    """
    Generate simulated coil sensitivity maps.
    
    Args:
        size: Image size
        num_channels: Number of coil channels
        
    Returns:
        (num_channels, size, size) complex array of sensitivity maps
    """
    x = np.linspace(-1, 1, size)
    y = np.linspace(-1, 1, size)
    X, Y = np.meshgrid(x, y)
    r = np.sqrt(X ** 2 + Y ** 2)
    theta = np.arctan2(Y, X)
    
    sense_maps = np.zeros((num_channels, size, size), dtype=np.complex128)
    
    for ch in range(num_channels):
        angle = 2 * np.pi * ch / num_channels
        x_c = 0.6 * np.cos(angle)
        y_c = 0.6 * np.sin(angle)
        
        dist = np.sqrt((X - x_c) ** 2 + (Y - y_c) ** 2)
        amp = np.exp(-dist ** 2 / 0.5)
        phase = np.exp(1j * (X * np.cos(angle) + Y * np.sin(angle)))
        
        ramp = np.clip(1 - r, 0, 1) ** 2
        sense_maps[ch] = amp * phase * ramp
    
    norm = np.sqrt(np.sum(np.abs(sense_maps) ** 2, axis=0))
    norm[norm == 0] = 1
    sense_maps = sense_maps / norm[np.newaxis, :, :]
    
    return sense_maps


def add_noise(
    kspace: np.ndarray,
    snr_db: float = 30.0
) -> np.ndarray:
    """
    Add complex Gaussian noise to k-space data.
    
    Args:
        kspace: Input k-space data
        snr_db: Desired SNR in dB
        
    Returns:
        Noisy k-space data
    """
    if kspace.size == 0:
        return kspace
    
    signal_power = np.mean(np.abs(kspace) ** 2)
    noise_power = signal_power / (10 ** (snr_db / 10))
    
    noise_real = np.random.normal(0, np.sqrt(noise_power / 2), kspace.shape)
    noise_imag = np.random.normal(0, np.sqrt(noise_power / 2), kspace.shape)
    
    return kspace + noise_real + 1j * noise_imag
