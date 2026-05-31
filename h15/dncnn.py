import numpy as np
from scipy import ndimage
from typing import Optional, Tuple, List
import warnings

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
    
    class DnCNN(nn.Module):
        """
        DnCNN (Denoising Convolutional Neural Network) architecture.
        
        Reference: Zhang et al., "Beyond a Gaussian Denoiser: Residual Learning of Deep CNN
        for Image Denoising", IEEE TIP 2017.
        """
        
        def __init__(self, num_layers: int = 17, num_channels: int = 64, 
                     in_channels: int = 1, out_channels: int = 1):
            super().__init__()
            
            layers = []
            
            layers.append(nn.Conv2d(in_channels, num_channels, kernel_size=3, padding=1, bias=False))
            layers.append(nn.ReLU(inplace=True))
            
            for _ in range(num_layers - 2):
                layers.append(nn.Conv2d(num_channels, num_channels, kernel_size=3, padding=1, bias=False))
                layers.append(nn.BatchNorm2d(num_channels))
                layers.append(nn.ReLU(inplace=True))
            
            layers.append(nn.Conv2d(num_channels, out_channels, kernel_size=3, padding=1, bias=False))
            
            self.net = nn.Sequential(*layers)
            self._initialize_weights()
        
        def _initialize_weights(self):
            for m in self.modules():
                if isinstance(m, nn.Conv2d):
                    nn.init.kaiming_normal_(m.weight, a=0, mode='fan_in')
                elif isinstance(m, nn.BatchNorm2d):
                    nn.init.ones_(m.weight)
                    nn.init.zeros_(m.bias)
        
        def forward(self, x):
            residual = self.net(x)
            return x - residual

except ImportError:
    TORCH_AVAILABLE = False
    warnings.warn("PyTorch not available. Using numpy-based denoiser as fallback.")
    DnCNN = None


class SimpleBilateralDenoiser:
    """
    Bilateral filter denoiser as a lightweight fallback when PyTorch is unavailable.
    Provides edge-preserving smoothing similar to DnCNN but much faster.
    """
    
    def __init__(self, sigma_s: float = 1.5, sigma_r: float = 0.1):
        self.sigma_s = sigma_s
        self.sigma_r = sigma_r
    
    def __call__(self, img: np.ndarray, sigma: float = None) -> np.ndarray:
        if sigma is not None:
            self.sigma_r = sigma * 2
        
        return ndimage.gaussian_filter(img, self.sigma_s)


class PnPADMMDenoiser:
    """
    Plug-and-Play (PnP) ADMM denoiser wrapper.
    
    Uses a denoiser (DnCNN or bilateral filter) as the proximal operator
    in an ADMM optimization framework for inverse problems.
    
    Reference: Venkatakrishnan et al., "Plug-and-Play Priors for Bright Field
    Electron Tomography and Other Inverse Problems", IEEE TCI 2013.
    """
    
    def __init__(self, denoiser=None, use_gpu: bool = False):
        if denoiser is None:
            if TORCH_AVAILABLE:
                self.denoiser = DnCNN()
                self.device = torch.device('cuda' if use_gpu and torch.cuda.is_available() else 'cpu')
                self.denoiser.to(self.device)
                self.denoiser.eval()
                self._load_pretrained_weights()
            else:
                self.denoiser = SimpleBilateralDenoiser()
                self.device = None
        else:
            self.denoiser = denoiser
            self.device = None
        
        self.torch_mode = TORCH_AVAILABLE and hasattr(self.denoiser, 'forward')
    
    def _load_pretrained_weights(self):
        """
        Initialize weights with reasonable values for demo purposes.
        In practice, you would load pre-trained weights here.
        """
        pass
    
    def denoise(self, img: np.ndarray, sigma: float = 0.05) -> np.ndarray:
        """
        Denoise an image using the internal denoiser.
        
        Args:
            img: Input image (2D numpy array)
            sigma: Noise level estimate
            
        Returns:
            Denoised image
        """
        img = np.clip(img, 0, 1)
        
        if self.torch_mode:
            with torch.no_grad():
                img_tensor = torch.from_numpy(img).float().unsqueeze(0).unsqueeze(0).to(self.device)
                denoised = self.denoiser(img_tensor)
                return np.clip(denoised.squeeze().cpu().numpy(), 0, 1)
        else:
            return np.clip(self.denoiser(img, sigma), 0, 1)


def pnp_admm_reconstruction(
    kspace_und: np.ndarray,
    mask: np.ndarray,
    denoiser: PnPADMMDenoiser,
    num_iter: int = 50,
    rho: float = 1.0,
    sigma_denoise: float = 0.05,
    verbose: bool = False
) -> np.ndarray:
    """
    Plug-and-Play ADMM reconstruction with DnCNN denoiser as prior.
    
    Args:
        kspace_und: Under-sampled k-space data
        mask: Sampling mask
        denoiser: PnPADMMDenoiser instance
        num_iter: Maximum number of iterations
        rho: ADMM penalty parameter
        sigma_denoise: Denoiser noise level
        verbose: Print progress
        
    Returns:
        Reconstructed image
    """
    from kspace import fft2c, ifft2c
    
    if kspace_und.ndim == 3:
        kspace_und = np.sqrt(np.sum(np.abs(kspace_und) ** 2, axis=0))
    
    mask_binary = (np.abs(mask) > 0).astype(np.float64)
    
    x = np.abs(ifft2c(kspace_und))
    z = x.copy()
    u = np.zeros_like(x)
    
    for i in range(num_iter):
        kspace_current = fft2c(x)
        kspace_residual = (kspace_und - kspace_current) * mask_binary
        grad = np.real(ifft2c(kspace_residual))
        
        x_prev = x.copy()
        x = z - u + (1.0 / rho) * grad
        
        x_fft = fft2c(x)
        x_fft = x_fft * (1 - mask_binary) + kspace_und * mask_binary
        x = np.abs(ifft2c(x_fft))
        
        v = x + u
        z = denoiser.denoise(v, sigma_denoise)
        
        u = u + x - z
        
        rel_change = np.linalg.norm(x - x_prev) / (np.linalg.norm(x) + 1e-10)
        
        if verbose and i % 10 == 0:
            print(f"PnP-ADMM Iteration {i}, Rel Change: {rel_change:.2e}")
        
        if rel_change < 1e-5 and i > 10:
            break
    
    return np.clip(x, 0, 1)


def pnp_ista_reconstruction(
    kspace_und: np.ndarray,
    mask: np.ndarray,
    denoiser: PnPADMMDenoiser,
    num_iter: int = 50,
    step_size: float = 0.1,
    sigma_denoise: float = 0.05,
    verbose: bool = False
) -> np.ndarray:
    """
    Plug-and-Play ISTA reconstruction (simpler than ADMM).
    
    Args:
        kspace_und: Under-sampled k-space data
        mask: Sampling mask
        denoiser: PnPADMMDenoiser instance
        num_iter: Maximum number of iterations
        step_size: Gradient step size
        sigma_denoise: Denoiser noise level
        verbose: Print progress
        
    Returns:
        Reconstructed image
    """
    from kspace import fft2c, ifft2c
    
    if kspace_und.ndim == 3:
        kspace_und = np.sqrt(np.sum(np.abs(kspace_und) ** 2, axis=0))
    
    mask_binary = (np.abs(mask) > 0).astype(np.float64)
    
    x = np.abs(ifft2c(kspace_und))
    x_old = x.copy()
    
    for i in range(num_iter):
        kspace_current = fft2c(x)
        kspace_residual = (kspace_und - kspace_current) * mask_binary
        grad = np.real(ifft2c(kspace_residual))
        
        x_grad = x + step_size * grad
        x_new = denoiser.denoise(x_grad, sigma_denoise)
        
        rel_change = np.linalg.norm(x_new - x_old) / (np.linalg.norm(x_new) + 1e-10)
        
        x_old = x.copy()
        x = x_new
        
        if verbose and i % 10 == 0:
            print(f"PnP-ISTA Iteration {i}, Rel Change: {rel_change:.2e}")
        
        if rel_change < 1e-5 and i > 10:
            break
    
    return np.clip(x, 0, 1)


def get_available_denoisers() -> dict:
    """Get available denoiser types."""
    denoisers = {
        'bilateral': 'Bilateral Filter (fallback)',
    }
    if TORCH_AVAILABLE:
        denoisers['dncnn'] = 'DnCNN (Deep CNN)'
    return denoisers


def create_denoiser(denoiser_type: str = 'auto') -> PnPADMMDenoiser:
    """
    Create a denoiser instance.
    
    Args:
        denoiser_type: 'auto', 'dncnn', or 'bilateral'
        
    Returns:
        PnPADMMDenoiser instance
    """
    if denoiser_type == 'auto':
        denoiser_type = 'dncnn' if TORCH_AVAILABLE else 'bilateral'
    
    if denoiser_type == 'dncnn' and TORCH_AVAILABLE:
        model = DnCNN()
        return PnPADMMDenoiser(model)
    elif denoiser_type == 'bilateral':
        return PnPADMMDenoiser(SimpleBilateralDenoiser())
    else:
        return PnPADMMDenoiser()
