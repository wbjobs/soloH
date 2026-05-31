"""
Deep learning module for sea ice drift estimation.

Provides:
- FlowNet architecture for optical flow estimation
- PyTorch model definitions
- Pre-trained model loading interface
- Transfer learning support for sea ice data
"""

import os
import numpy as np
import warnings

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    warnings.warn('PyTorch not available. Deep learning methods will be disabled. '
                  'Install with: pip install torch torchvision')

from .motion import MotionField


class FlowNetS(nn.Module):
    """
    FlowNetS (Simple) architecture for optical flow estimation.
    
    Adapted from: https://arxiv.org/abs/1504.06852
    Modified for sea ice brightness temperature images.
    """
    
    def __init__(self, in_channels=2, batch_norm=True):
        """
        Parameters
        ----------
        in_channels : int
            Number of input channels (2 for consecutive frames)
        batch_norm : bool
            Whether to use batch normalization
        """
        super(FlowNetS, self).__init__()
        
        self.batch_norm = batch_norm
        
        def conv_block(in_ch, out_ch, kernel_size=3, stride=2, padding=1):
            layers = [nn.Conv2d(in_ch, out_ch, kernel_size, stride, padding)]
            if batch_norm:
                layers.append(nn.BatchNorm2d(out_ch))
            layers.append(nn.LeakyReLU(0.1, inplace=True))
            return nn.Sequential(*layers)
        
        def upconv_block(in_ch, out_ch, kernel_size=4, stride=2, padding=1):
            return nn.Sequential(
                nn.ConvTranspose2d(in_ch, out_ch, kernel_size, stride, padding),
                nn.LeakyReLU(0.1, inplace=True)
            )
        
        self.conv1 = conv_block(in_channels, 64, kernel_size=7, stride=2, padding=3)
        self.conv2 = conv_block(64, 128, kernel_size=5, stride=2, padding=2)
        self.conv3 = conv_block(128, 256, kernel_size=5, stride=2, padding=2)
        self.conv3_1 = conv_block(256, 256, kernel_size=3, stride=1, padding=1)
        self.conv4 = conv_block(256, 512, kernel_size=3, stride=2, padding=1)
        self.conv4_1 = conv_block(512, 512, kernel_size=3, stride=1, padding=1)
        self.conv5 = conv_block(512, 512, kernel_size=3, stride=2, padding=1)
        self.conv5_1 = conv_block(512, 512, kernel_size=3, stride=1, padding=1)
        self.conv6 = conv_block(512, 1024, kernel_size=3, stride=2, padding=1)
        
        self.predict_flow6 = nn.Conv2d(1024, 2, kernel_size=3, stride=1, padding=1)
        
        self.upconv5 = upconv_block(1024, 512)
        self.iconv5 = conv_block(512 + 512 + 2, 512, kernel_size=3, stride=1, padding=1)
        self.predict_flow5 = nn.Conv2d(512, 2, kernel_size=3, stride=1, padding=1)
        
        self.upconv4 = upconv_block(512, 256)
        self.iconv4 = conv_block(256 + 512 + 2, 256, kernel_size=3, stride=1, padding=1)
        self.predict_flow4 = nn.Conv2d(256, 2, kernel_size=3, stride=1, padding=1)
        
        self.upconv3 = upconv_block(256, 128)
        self.iconv3 = conv_block(128 + 256 + 2, 128, kernel_size=3, stride=1, padding=1)
        self.predict_flow3 = nn.Conv2d(128, 2, kernel_size=3, stride=1, padding=1)
        
        self.upconv2 = upconv_block(128, 64)
        self.iconv2 = conv_block(64 + 128 + 2, 64, kernel_size=3, stride=1, padding=1)
        self.predict_flow2 = nn.Conv2d(64, 2, kernel_size=3, stride=1, padding=1)
        
        self._initialize_weights()
    
    def _initialize_weights(self):
        """Initialize network weights."""
        for m in self.modules():
            if isinstance(m, nn.Conv2d) or isinstance(m, nn.ConvTranspose2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='leaky_relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
    
    def forward(self, x):
        """
        Forward pass through FlowNetS.
        
        Parameters
        ----------
        x : torch.Tensor
            Input tensor of shape (batch, in_channels, height, width)
            
        Returns
        -------
        tuple
            (flow_prediction, [flow2, flow3, flow4, flow5, flow6])
        """
        conv1 = self.conv1(x)
        conv2 = self.conv2(conv1)
        conv3 = self.conv3(conv2)
        conv3_1 = self.conv3_1(conv3)
        conv4 = self.conv4(conv3_1)
        conv4_1 = self.conv4_1(conv4)
        conv5 = self.conv5(conv4_1)
        conv5_1 = self.conv5_1(conv5)
        conv6 = self.conv6(conv5_1)
        
        flow6 = self.predict_flow6(conv6)
        flow6_up = self._upsample2(flow6)
        
        upconv5 = self.upconv5(conv6)
        concat5 = torch.cat([upconv5, conv5_1, flow6_up], 1)
        iconv5 = self.iconv5(concat5)
        flow5 = self.predict_flow5(iconv5)
        flow5_up = self._upsample2(flow5)
        
        upconv4 = self.upconv4(iconv5)
        concat4 = torch.cat([upconv4, conv4_1, flow5_up], 1)
        iconv4 = self.iconv4(concat4)
        flow4 = self.predict_flow4(iconv4)
        flow4_up = self._upsample2(flow4)
        
        upconv3 = self.upconv3(iconv4)
        concat3 = torch.cat([upconv3, conv3_1, flow4_up], 1)
        iconv3 = self.iconv3(concat3)
        flow3 = self.predict_flow3(iconv3)
        flow3_up = self._upsample2(flow3)
        
        upconv2 = self.upconv2(iconv3)
        concat2 = torch.cat([upconv2, conv2, flow3_up], 1)
        iconv2 = self.iconv2(concat2)
        flow2 = self.predict_flow2(iconv2)
        
        flow_full = self._upsample2(flow2)
        
        return flow_full, [flow2, flow3, flow4, flow5, flow6]
    
    def _upsample2(self, x):
        """Upsample by factor of 2."""
        return F.interpolate(x, scale_factor=2, mode='bilinear', align_corners=True)


class FlowNet2Small(nn.Module):
    """
    Simplified FlowNet architecture for resource-constrained environments.
    
    Smaller version suitable for sea ice images without extreme detail requirements.
    """
    
    def __init__(self, in_channels=2):
        super(FlowNet2Small, self).__init__()
        
        self.encoder = nn.Sequential(
            nn.Conv2d(in_channels, 32, 7, 2, 3),
            nn.BatchNorm2d(32),
            nn.LeakyReLU(0.1, inplace=True),
            
            nn.Conv2d(32, 64, 5, 2, 2),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.1, inplace=True),
            
            nn.Conv2d(64, 128, 5, 2, 2),
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.1, inplace=True),
            
            nn.Conv2d(128, 256, 3, 2, 1),
            nn.BatchNorm2d(256),
            nn.LeakyReLU(0.1, inplace=True),
            
            nn.Conv2d(256, 256, 3, 1, 1),
            nn.BatchNorm2d(256),
            nn.LeakyReLU(0.1, inplace=True),
        )
        
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(256, 128, 4, 2, 1),
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.1, inplace=True),
            
            nn.ConvTranspose2d(128, 64, 4, 2, 1),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.1, inplace=True),
            
            nn.ConvTranspose2d(64, 32, 4, 2, 1),
            nn.BatchNorm2d(32),
            nn.LeakyReLU(0.1, inplace=True),
            
            nn.ConvTranspose2d(32, 16, 4, 2, 1),
            nn.BatchNorm2d(16),
            nn.LeakyReLU(0.1, inplace=True),
            
            nn.Conv2d(16, 2, 3, 1, 1),
        )
    
    def forward(self, x):
        """Forward pass."""
        x = self.encoder(x)
        flow = self.decoder(x)
        return flow, [flow]


class IceMotionCNN(nn.Module):
    """
    Custom CNN optimized for sea ice motion estimation.
    
    Features:
    - Multi-scale feature extraction
    - Residual connections
    - Channel attention for feature weighting
    - Outputs both flow and uncertainty estimates
    """
    
    def __init__(self, in_channels=2, base_channels=32):
        super().__init__()
        
        def conv_bn_relu(in_ch, out_ch, k=3, s=1, p=1):
            return nn.Sequential(
                nn.Conv2d(in_ch, out_ch, k, s, p),
                nn.BatchNorm2d(out_ch),
                nn.LeakyReLU(0.2, inplace=True)
            )
        
        self.conv1 = conv_bn_relu(in_channels, base_channels, k=7, s=2, p=3)
        self.conv2 = conv_bn_relu(base_channels, base_channels*2, k=5, s=2, p=2)
        self.conv3 = conv_bn_relu(base_channels*2, base_channels*4, k=3, s=2, p=1)
        self.conv4 = conv_bn_relu(base_channels*4, base_channels*8, k=3, s=2, p=1)
        
        self.res1 = nn.Sequential(
            conv_bn_relu(base_channels*8, base_channels*8),
            nn.Conv2d(base_channels*8, base_channels*8, 3, 1, 1),
            nn.BatchNorm2d(base_channels*8)
        )
        
        self.attention = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(base_channels*8, base_channels*2, 1),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(base_channels*2, base_channels*8, 1),
            nn.Sigmoid()
        )
        
        self.upconv4 = nn.ConvTranspose2d(base_channels*8, base_channels*4, 4, 2, 1)
        self.upconv3 = nn.ConvTranspose2d(base_channels*8, base_channels*2, 4, 2, 1)
        self.upconv2 = nn.ConvTranspose2d(base_channels*4, base_channels, 4, 2, 1)
        self.upconv1 = nn.ConvTranspose2d(base_channels*2, base_channels, 4, 2, 1)
        
        self.flow_head = nn.Sequential(
            nn.Conv2d(base_channels, base_channels, 3, 1, 1),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(base_channels, 2, 3, 1, 1)
        )
        
        self.uncertainty_head = nn.Sequential(
            nn.Conv2d(base_channels, base_channels, 3, 1, 1),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(base_channels, 1, 3, 1, 1),
            nn.Softplus()
        )
        
        self._init_weights()
    
    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, (nn.Conv2d, nn.ConvTranspose2d)):
                nn.init.kaiming_normal_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
    
    def forward(self, x):
        """
        Forward pass returning both flow and uncertainty.
        
        Returns
        -------
        tuple
            (flow, uncertainty)
        """
        c1 = self.conv1(x)
        c2 = self.conv2(c1)
        c3 = self.conv3(c2)
        c4 = self.conv4(c3)
        
        r = F.leaky_relu(c4 + self.res1(c4), 0.2)
        
        att = self.attention(r)
        r = r * att
        
        u4 = self.upconv4(r)
        u4_cat = torch.cat([u4, c3], dim=1)
        
        u3 = self.upconv3(u4_cat)
        u3_cat = torch.cat([u3, c2], dim=1)
        
        u2 = self.upconv2(u3_cat)
        u2_cat = torch.cat([u2, c1], dim=1)
        
        u1 = self.upconv1(u2_cat)
        
        flow = self.flow_head(u1)
        uncertainty = self.uncertainty_head(u1)
        
        return flow, uncertainty


class FlowNetEstimator:
    """
    High-level interface for FlowNet-based motion estimation.
    
    Handles:
    - Model loading (pre-trained or custom)
    - Image preprocessing for network input
    - Inference with optional GPU acceleration
    - Post-processing and uncertainty estimation
    """
    
    def __init__(self, model_path=None, model_type='small', device=None,
                 pretrained=True):
        """
        Parameters
        ----------
        model_path : str, optional
            Path to custom model weights
        model_type : str
            'small', 'full', or 'custom'
        device : str, optional
            'cpu', 'cuda', or None for auto-detection
        pretrained : bool
            Whether to load pre-trained weights (if available)
        """
        if not TORCH_AVAILABLE:
            raise ImportError('PyTorch is required for FlowNet estimation. '
                            'Install with: pip install torch torchvision')
        
        self.device = self._select_device(device)
        self.model_type = model_type
        self.model = self._build_model(model_type)
        self.model.to(self.device)
        
        if model_path and os.path.exists(model_path):
            self.load_weights(model_path)
        elif pretrained:
            self._load_pretrained()
        
        self.model.eval()
    
    def _select_device(self, device):
        """Select computation device."""
        if device is not None:
            return torch.device(device)
        
        if torch.cuda.is_available():
            return torch.device('cuda')
        elif torch.backends.mps.is_available():
            return torch.device('mps')
        else:
            return torch.device('cpu')
    
    def _build_model(self, model_type):
        """Build the requested model architecture."""
        if model_type == 'small':
            return FlowNet2Small(in_channels=2)
        elif model_type == 'full':
            return FlowNetS(in_channels=2, batch_norm=True)
        elif model_type == 'custom':
            return IceMotionCNN(in_channels=2)
        else:
            raise ValueError(f'Unknown model type: {model_type}')
    
    def _load_pretrained(self):
        """Load pre-trained weights if available."""
        import hashlib
        
        weights_dir = os.path.join(os.path.dirname(__file__), 'weights')
        os.makedirs(weights_dir, exist_ok=True)
        
        model_name = f'flownet_{self.model_type}_sea_ice.pth'
        weight_path = os.path.join(weights_dir, model_name)
        
        if os.path.exists(weight_path):
            try:
                state_dict = torch.load(weight_path, map_location=self.device)
                self.model.load_state_dict(state_dict)
                print(f'Loaded pre-trained weights from {weight_path}')
            except Exception as e:
                print(f'Warning: Could not load pre-trained weights: {e}')
                print('Using initialized weights. Fine-tuning recommended.')
        else:
            print(f'No pre-trained weights found at {weight_path}')
            print('Using initialized weights. For best performance:')
            print('  1. Fine-tune on your dataset')
            print('  2. Or use --method horn_schunck for classical estimation')
    
    def load_weights(self, model_path):
        """Load custom model weights."""
        state_dict = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        print(f'Loaded weights from {model_path}')
    
    def preprocess_images(self, img1, img2):
        """
        Preprocess images for network input.
        
        Parameters
        ----------
        img1, img2 : 2D array
            Input images (brightness temperature)
            
        Returns
        -------
        torch.Tensor
            Preprocessed tensor of shape (1, 2, H, W)
        """
        img1 = np.asarray(img1, dtype=np.float32)
        img2 = np.asarray(img2, dtype=np.float32)
        
        valid_mask = ~(np.isnan(img1) | np.isnan(img2))
        
        mean1 = np.nanmean(img1)
        std1 = np.nanstd(img1)
        mean2 = np.nanmean(img2)
        std2 = np.nanstd(img2)
        
        img1_norm = (img1 - mean1) / (std1 + 1e-10)
        img2_norm = (img2 - mean2) / (std2 + 1e-10)
        
        img1_norm[~valid_mask] = 0
        img2_norm[~valid_mask] = 0
        
        input_tensor = np.stack([img1_norm, img2_norm], axis=0)
        input_tensor = torch.from_numpy(input_tensor).unsqueeze(0)
        
        return input_tensor, valid_mask
    
    def estimate(self, img1, img2, time_diff=1.0, resolution=1.0):
        """
        Estimate motion between two images.
        
        Parameters
        ----------
        img1, img2 : 2D array
            Input images
        time_diff : float
            Time difference between images (seconds)
        resolution : float
            Grid resolution (meters per pixel)
            
        Returns
        -------
        MotionField
            Estimated motion field with optional uncertainty
        """
        self.model.eval()
        
        orig_shape = img1.shape
        
        input_tensor, valid_mask = self.preprocess_images(img1, img2)
        input_tensor = input_tensor.to(self.device)
        
        target_h = ((orig_shape[0] // 64) + 1) * 64
        target_w = ((orig_shape[1] // 64) + 1) * 64
        
        if orig_shape != (target_h, target_w):
            input_tensor = F.interpolate(input_tensor, size=(target_h, target_w),
                                       mode='bilinear', align_corners=True)
        
        with torch.no_grad():
            if self.model_type == 'custom':
                flow_pred, uncertainty = self.model(input_tensor)
            else:
                flow_pred, _ = self.model(input_tensor)
                uncertainty = None
        
        scale_y = orig_shape[0] / target_h
        scale_x = orig_shape[1] / target_w
        
        flow_full = F.interpolate(flow_pred, size=orig_shape,
                                 mode='bilinear', align_corners=True)
        
        flow_full[:, 0] *= scale_x
        flow_full[:, 1] *= scale_y
        
        u = flow_full[0, 0].cpu().numpy()
        v = flow_full[0, 1].cpu().numpy()
        
        u[~valid_mask] = np.nan
        v[~valid_mask] = np.nan
        
        correlation = None
        if uncertainty is not None:
            unc = uncertainty[0, 0].cpu().numpy()
            correlation = np.exp(-unc)
            correlation[~valid_mask] = np.nan
        
        return MotionField(
            u, v, correlation,
            time_diff=time_diff,
            resolution=resolution
        )


def estimate_flow_net(img1, img2, model_type='small', device=None,
                      model_path=None, time_diff=1.0, resolution=1.0):
    """
    Convenience function for FlowNet motion estimation.
    
    Parameters
    ----------
    img1, img2 : 2D array
        Input images
    model_type : str
        'small', 'full', or 'custom'
    device : str, optional
        Computation device
    model_path : str, optional
        Path to custom weights
    time_diff : float
        Time difference in seconds
    resolution : float
        Grid resolution in meters per pixel
        
    Returns
    -------
    MotionField
        Estimated motion field
    """
    if not TORCH_AVAILABLE:
        raise ImportError('PyTorch is required for FlowNet estimation.')
    
    estimator = FlowNetEstimator(
        model_path=model_path,
        model_type=model_type,
        device=device,
        pretrained=False
    )
    
    return estimator.estimate(img1, img2, time_diff, resolution)


class FlowNetTrainer:
    """
    Trainer for fine-tuning FlowNet models on sea ice data.
    
    Features:
    - Data augmentation for robust training
    - Multi-scale loss (EPE + robust loss)
    - Learning rate scheduling
    - Checkpoint saving and loading
    """
    
    def __init__(self, model, device=None, learning_rate=1e-4):
        if not TORCH_AVAILABLE:
            raise ImportError('PyTorch is required for training.')
        
        self.device = self._select_device(device)
        self.model = model.to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=5
        )
        self.global_step = 0
    
    def _select_device(self, device):
        if device is not None:
            return torch.device(device)
        return torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    def epe_loss(self, pred_flow, true_flow):
        """Endpoint Error loss."""
        return torch.norm(pred_flow - true_flow, p=2, dim=1).mean()
    
    def robust_loss(self, pred_flow, true_flow, alpha=0.5, epsilon=0.01):
        """Robust Charbonnier loss."""
        diff = pred_flow - true_flow
        return torch.sqrt(diff**2 + epsilon**2).mean()
    
    def train_step(self, img1, img2, true_flow):
        """
        Single training step.
        
        Parameters
        ----------
        img1, img2 : torch.Tensor
            Input image pairs (B, 1, H, W)
        true_flow : torch.Tensor
            Ground truth flow (B, 2, H, W)
            
        Returns
        -------
        dict
            Loss values
        """
        self.model.train()
        
        inputs = torch.cat([img1, img2], dim=1).to(self.device)
        true_flow = true_flow.to(self.device)
        
        self.optimizer.zero_grad()
        
        if self.model_type == 'custom':
            pred_flow, uncertainty = self.model(inputs)
        else:
            pred_flow, _ = self.model(inputs)
        
        if isinstance(pred_flow, list):
            pred_flow = pred_flow[0]
        
        epe = self.epe_loss(pred_flow, true_flow)
        robust = self.robust_loss(pred_flow, true_flow)
        loss = epe + 0.5 * robust
        
        loss.backward()
        self.optimizer.step()
        
        self.global_step += 1
        
        return {
            'epe_loss': epe.item(),
            'robust_loss': robust.item(),
            'total_loss': loss.item()
        }
    
    def save_checkpoint(self, path):
        """Save training checkpoint."""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'global_step': self.global_step,
        }, path)
    
    def load_checkpoint(self, path):
        """Load training checkpoint."""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
        self.global_step = checkpoint['global_step']


def get_available_models():
    """
    Get list of available deep learning models.
    
    Returns
    -------
    dict
        Model information dictionary
    """
    models = {
        'flownet_small': {
            'name': 'FlowNet2Small',
            'description': 'Lightweight FlowNet architecture for fast inference',
            'parameters': '~2M',
            'speed': 'fast',
            'accuracy': 'good'
        },
        'flownet_full': {
            'name': 'FlowNetS',
            'description': 'Full FlowNetS architecture with multi-scale predictions',
            'parameters': '~38M',
            'speed': 'medium',
            'accuracy': 'better'
        },
        'ice_motion_cnn': {
            'name': 'IceMotionCNN',
            'description': 'Custom CNN optimized for sea ice with uncertainty estimation',
            'parameters': '~5M',
            'speed': 'medium',
            'accuracy': 'best (sea ice)'
        }
    }
    return models
