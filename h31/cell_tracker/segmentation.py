import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from typing import Optional, Tuple, List
import logging
from skimage.measure import label as ski_label
from skimage.segmentation import watershed
from skimage.feature import peak_local_max
from scipy.ndimage import distance_transform_edt

from .utils import normalize_image, normalize_stack

logger = logging.getLogger(__name__)


class DoubleConv(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, mid_channels: Optional[int] = None):
        super().__init__()
        if not mid_channels:
            mid_channels = out_channels
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(mid_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.double_conv(x)


class Down(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.maxpool_conv = nn.Sequential(
            nn.MaxPool2d(2),
            DoubleConv(in_channels, out_channels)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.maxpool_conv(x)


class Up(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, bilinear: bool = True):
        super().__init__()
        if bilinear:
            self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
            self.conv = DoubleConv(in_channels, out_channels, in_channels // 2)
        else:
            self.up = nn.ConvTranspose2d(in_channels, in_channels // 2, kernel_size=2, stride=2)
            self.conv = DoubleConv(in_channels, out_channels)

    def forward(self, x1: torch.Tensor, x2: torch.Tensor) -> torch.Tensor:
        x1 = self.up(x1)
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3]
        x1 = F.pad(x1, [diffX // 2, diffX - diffX // 2, diffY // 2, diffY - diffY // 2])
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)


class OutConv(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class UNet(nn.Module):
    def __init__(self, n_channels: int = 1, n_classes: int = 2, bilinear: bool = True):
        super().__init__()
        self.n_channels = n_channels
        self.n_classes = n_classes
        self.bilinear = bilinear

        self.inc = DoubleConv(n_channels, 64)
        self.down1 = Down(64, 128)
        self.down2 = Down(128, 256)
        self.down3 = Down(256, 512)
        factor = 2 if bilinear else 1
        self.down4 = Down(512, 1024 // factor)
        self.up1 = Up(1024, 512 // factor, bilinear)
        self.up2 = Up(512, 256 // factor, bilinear)
        self.up3 = Up(256, 128 // factor, bilinear)
        self.up4 = Up(128, 64, bilinear)
        self.outc = OutConv(64, n_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.down4(x4)
        x = self.up1(x5, x4)
        x = self.up2(x, x3)
        x = self.up3(x, x2)
        x = self.up4(x, x1)
        logits = self.outc(x)
        return logits


class UNetSegmenter:
    def __init__(self, 
                 weights_path: Optional[str] = None,
                 device: str = 'auto',
                 threshold: float = 0.5,
                 use_watershed: bool = True,
                 min_object_size: int = 100):
        self.device = self._get_device(device)
        self.threshold = threshold
        self.use_watershed = use_watershed
        self.min_object_size = min_object_size
        
        self.model = UNet(n_channels=1, n_classes=2, bilinear=True)
        self.model.to(self.device)
        
        if weights_path and Path(weights_path).exists():
            self.load_weights(weights_path)
        else:
            logger.warning("No pre-trained weights loaded. Using random initialization.")
        
        self.model.eval()
    
    def _get_device(self, device: str) -> torch.device:
        if device == 'auto':
            if torch.cuda.is_available():
                return torch.device('cuda')
            return torch.device('cpu')
        return torch.device(device)
    
    def load_weights(self, weights_path: str) -> None:
        logger.info(f"Loading pre-trained weights from {weights_path}")
        checkpoint = torch.load(weights_path, map_location=self.device)
        
        if 'model_state_dict' in checkpoint:
            state_dict = checkpoint['model_state_dict']
        elif 'state_dict' in checkpoint:
            state_dict = checkpoint['state_dict']
        else:
            state_dict = checkpoint
        
        new_state_dict = {}
        for k, v in state_dict.items():
            if k.startswith('module.'):
                k = k[7:]
            new_state_dict[k] = v
        
        self.model.load_state_dict(new_state_dict, strict=False)
        logger.info("Weights loaded successfully")
    
    def _preprocess(self, image: np.ndarray) -> torch.Tensor:
        if image.ndim == 2:
            image = image[np.newaxis, ...]
        
        normalized = normalize_image(image)
        tensor = torch.from_numpy(normalized).float().unsqueeze(0)
        return tensor.to(self.device)
    
    def _postprocess(self, 
                    logits: torch.Tensor, 
                    original_shape: Tuple[int, int]) -> np.ndarray:
        probs = F.softmax(logits, dim=1)
        foreground_prob = probs[0, 1].cpu().numpy()
        
        binary_mask = foreground_prob > self.threshold
        
        if binary_mask.sum() == 0:
            return np.zeros(original_shape, dtype=np.int32)
        
        if self.use_watershed:
            instance_mask = self._watershed_segmentation(foreground_prob, binary_mask)
        else:
            instance_mask = ski_label(binary_mask)
        
        instance_mask = self._remove_small_objects(instance_mask)
        
        return instance_mask.astype(np.int32)
    
    def _watershed_segmentation(self, 
                                 foreground_prob: np.ndarray, 
                                 binary_mask: np.ndarray) -> np.ndarray:
        distance = distance_transform_edt(binary_mask)
        
        coords = peak_local_max(
            distance, 
            footprint=np.ones((3, 3)),
            labels=binary_mask,
            min_distance=5
        )
        
        if len(coords) == 0:
            return ski_label(binary_mask)
        
        markers = np.zeros(foreground_prob.shape, dtype=np.int32)
        for i, (y, x) in enumerate(coords, 1):
            markers[y, x] = i
        
        instance_mask = watershed(
            -foreground_prob, 
            markers, 
            mask=binary_mask
        )
        
        return instance_mask
    
    def _remove_small_objects(self, mask: np.ndarray) -> np.ndarray:
        labels = np.unique(mask)
        labels = labels[labels != 0]
        
        for label in labels:
            if np.sum(mask == label) < self.min_object_size:
                mask[mask == label] = 0
        
        labels = np.unique(mask)
        labels = labels[labels != 0]
        
        new_mask = np.zeros_like(mask)
        for i, label in enumerate(labels, 1):
            new_mask[mask == label] = i
        
        return new_mask
    
    def segment_image(self, image: np.ndarray) -> np.ndarray:
        original_shape = image.shape[-2:]
        
        with torch.no_grad():
            x = self._preprocess(image)
            logits = self.model(x)
            logits = F.interpolate(
                logits, 
                size=original_shape, 
                mode='bilinear', 
                align_corners=True
            )
            instance_mask = self._postprocess(logits, original_shape)
        
        return instance_mask
    
    def segment_stack(self, 
                      stack: np.ndarray, 
                      parallel: bool = False,
                      num_workers: int = 4) -> np.ndarray:
        logger.info(f"Segmenting stack of {stack.shape[0]} frames")
        
        if parallel and num_workers > 1 and torch.cuda.device_count() <= 1:
            from joblib import Parallel, delayed
            
            masks = Parallel(n_jobs=num_workers, verbose=1)(
                delayed(self.segment_image)(stack[i])
                for i in range(stack.shape[0])
            )
            instance_masks = np.stack(masks, axis=0)
        else:
            instance_masks = np.zeros(
                (stack.shape[0], stack.shape[-2], stack.shape[-1]), 
                dtype=np.int32
            )
            
            for i in range(stack.shape[0]):
                logger.info(f"Segmenting frame {i+1}/{stack.shape[0]}")
                instance_masks[i] = self.segment_image(stack[i])
        
        logger.info(f"Segmentation complete. Output shape: {instance_masks.shape}")
        return instance_masks
    
    def predict_probability(self, image: np.ndarray) -> np.ndarray:
        original_shape = image.shape[-2:]
        
        with torch.no_grad():
            x = self._preprocess(image)
            logits = self.model(x)
            logits = F.interpolate(
                logits, 
                size=original_shape, 
                mode='bilinear', 
                align_corners=True
            )
            probs = F.softmax(logits, dim=1)
            foreground_prob = probs[0, 1].cpu().numpy()
        
        return foreground_prob
