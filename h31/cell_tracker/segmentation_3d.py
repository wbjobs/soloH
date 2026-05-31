import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import logging
import pandas as pd
from skimage.measure import label as ski_label
from scipy.ndimage import distance_transform_edt
from skimage.feature import peak_local_max

from .utils import normalize_image

logger = logging.getLogger(__name__)


class DoubleConv3D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, mid_channels: Optional[int] = None):
        super().__init__()
        if not mid_channels:
            mid_channels = out_channels
        self.double_conv = nn.Sequential(
            nn.Conv3d(in_channels, mid_channels, kernel_size=3, padding=1),
            nn.BatchNorm3d(mid_channels),
            nn.ReLU(inplace=True),
            nn.Conv3d(mid_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm3d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.double_conv(x)


class Down3D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.maxpool_conv = nn.Sequential(
            nn.MaxPool3d(2),
            DoubleConv3D(in_channels, out_channels)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.maxpool_conv(x)


class Up3D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, trilinear: bool = True):
        super().__init__()
        if trilinear:
            self.up = nn.Upsample(scale_factor=2, mode='trilinear', align_corners=True)
            self.conv = DoubleConv3D(in_channels, out_channels, in_channels // 2)
        else:
            self.up = nn.ConvTranspose3d(in_channels, in_channels // 2, kernel_size=2, stride=2)
            self.conv = DoubleConv3D(in_channels, out_channels)

    def forward(self, x1: torch.Tensor, x2: torch.Tensor) -> torch.Tensor:
        x1 = self.up(x1)
        
        diffZ = x2.size()[2] - x1.size()[2]
        diffY = x2.size()[3] - x1.size()[3]
        diffX = x2.size()[4] - x1.size()[4]
        
        x1 = F.pad(x1, [
            diffX // 2, diffX - diffX // 2,
            diffY // 2, diffY - diffY // 2,
            diffZ // 2, diffZ - diffZ // 2
        ])
        
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)


class OutConv3D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = nn.Conv3d(in_channels, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class UNet3D(nn.Module):
    def __init__(self, n_channels: int = 1, n_classes: int = 2, trilinear: bool = True):
        super().__init__()
        self.n_channels = n_channels
        self.n_classes = n_classes
        self.trilinear = trilinear

        self.inc = DoubleConv3D(n_channels, 32)
        self.down1 = Down3D(32, 64)
        self.down2 = Down3D(64, 128)
        self.down3 = Down3D(128, 256)
        factor = 2 if trilinear else 1
        self.down4 = Down3D(256, 512 // factor)
        self.up1 = Up3D(512, 256 // factor, trilinear)
        self.up2 = Up3D(256, 128 // factor, trilinear)
        self.up3 = Up3D(128, 64 // factor, trilinear)
        self.up4 = Up3D(64, 32, trilinear)
        self.outc = OutConv3D(32, n_classes)

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


def check_3d_data(image_stack: np.ndarray) -> Tuple[bool, int]:
    """
    Check if image data is 3D (volumetric) or 2D.
    
    Returns:
        is_3d: True if data is 3D (with Z dimension)
        z_slices: Number of Z slices
    """
    if image_stack.ndim == 5:
        return True, image_stack.shape[1]
    elif image_stack.ndim == 4:
        return True, image_stack.shape[1]
    elif image_stack.ndim == 3:
        return False, 1
    elif image_stack.ndim == 2:
        return False, 1
    else:
        raise ValueError(f"Unsupported data shape: {image_stack.shape}")


def reshape_3d_to_2d(image_stack: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int, int]]:
    """
    Reshape 3D volume for 2D processing (slice-by-slice).
    """
    if image_stack.ndim == 4:
        T, Z, H, W = image_stack.shape
        return image_stack.reshape(T * Z, H, W), (T, Z, H, W)
    elif image_stack.ndim == 5:
        T, C, Z, H, W = image_stack.shape
        return image_stack.reshape(T * Z, C, H, W), (T, C, Z, H, W)
    else:
        return image_stack, image_stack.shape


def reshape_2d_to_3d(masks_2d: np.ndarray, original_shape: Tuple) -> np.ndarray:
    """
    Reshape 2D processed masks back to 3D volume.
    """
    if len(original_shape) == 4:
        T, Z, H, W = original_shape
        return masks_2d.reshape(T, Z, H, W)
    elif len(original_shape) == 5:
        T, C, Z, H, W = original_shape
        return masks_2d.reshape(T, Z, H, W)
    else:
        return masks_2d


def z_axis_consistency_filter(masks_3d: np.ndarray,
                             z_connected_threshold: float = 0.5,
                             min_z_slices: int = 2) -> np.ndarray:
    """
    Filter segmentation based on Z-axis connectivity and consistency.
    """
    T, Z, H, W = masks_3d.shape
    filtered_masks = np.zeros_like(masks_3d)
    
    for t in range(T):
        volume = masks_3d[t]
        labels = np.unique(volume)
        labels = labels[labels != 0]
        
        new_volume = np.zeros_like(volume)
        new_label = 1
        
        for label in labels:
            label_mask = volume == label
            z_presence = np.any(label_mask, axis=(1, 2))
            z_count = np.sum(z_presence)
            
            if z_count < min_z_slices:
                continue
            
            z_connections = 0
            for z in range(Z - 1):
                overlap = np.logical_and(label_mask[z], label_mask[z + 1]).sum()
                area = label_mask[z].sum()
                if area > 0 and overlap / area > z_connected_threshold:
                    z_connections += 1
            
            if z_count > 1 and z_connections < z_count - 1:
                connected_components, n_components = ski_label(label_mask, return_num=True, connectivity=2)
                
                for comp in range(1, n_components + 1):
                    comp_mask = connected_components == comp
                    comp_z_presence = np.any(comp_mask, axis=(1, 2))
                    comp_z_count = np.sum(comp_z_presence)
                    
                    if comp_z_count >= min_z_slices:
                        new_volume[comp_mask] = new_label
                        new_label += 1
            else:
                new_volume[label_mask] = new_label
                new_label += 1
        
        filtered_masks[t] = new_volume
    
    return filtered_masks


def create_3d_instance_mask(prob_3d: np.ndarray,
                            threshold: float = 0.5,
                            z_weight: float = 0.5,
                            use_3d_watershed: bool = True) -> np.ndarray:
    """
    Create 3D instance segmentation mask from probability volume.
    """
    T, Z, H, W = prob_3d.shape
    instance_masks = np.zeros((T, Z, H, W), dtype=np.int32)
    
    for t in range(T):
        volume = prob_3d[t]
        binary = volume > threshold
        
        if binary.sum() == 0:
            continue
        
        if use_3d_watershed:
            instance_mask = _watershed_3d(volume, binary)
        else:
            instance_mask, _ = ski_label(binary, return_num=True, connectivity=2)
        
        instance_masks[t] = instance_mask
    
    return instance_masks


def _watershed_3d(prob_volume: np.ndarray, binary: np.ndarray) -> np.ndarray:
    """
    3D watershed segmentation for instance generation.
    """
    Z, H, W = prob_volume.shape
    
    distance = distance_transform_edt(binary)
    
    coords = peak_local_max(
        distance,
        footprint=np.ones((3, 3, 3)),
        labels=binary,
        min_distance=5
    )
    
    if len(coords) == 0:
        return ski_label(binary).astype(np.int32)
    
    markers = np.zeros(prob_volume.shape, dtype=np.int32)
    for i, (z, y, x) in enumerate(coords, 1):
        markers[z, y, x] = i
    
    try:
        from skimage.segmentation import watershed
        instance_mask = watershed(-prob_volume, markers, mask=binary)
    except:
        instance_mask = ski_label(binary).astype(np.int32)
    
    return instance_mask.astype(np.int32)


def extract_3d_features(mask_3d: np.ndarray, image_3d: Optional[np.ndarray] = None) -> Dict[int, dict]:
    """
    Extract 3D features for each cell in the volume.
    """
    from skimage.measure import regionprops
    
    features = {}
    Z, H, W = mask_3d.shape
    
    try:
        regions = regionprops(mask_3d)
    except:
        regions = []
    
    for region in regions:
        if region.label == 0:
            continue
        
        props = {
            'label': region.label,
            'volume': region.area,
            'centroid_3d': region.centroid,
            'bbox_3d': region.bbox,
            'extent': region.extent,
            'solidity': region.solidity,
            'z_min': region.bbox[0],
            'z_max': region.bbox[3],
            'z_extent': region.bbox[3] - region.bbox[0],
        }
        
        try:
            props['eccentricity'] = region.eccentricity
            props['aspect_ratio_xy'] = region.major_axis_length / max(region.minor_axis_length, 1)
        except NotImplementedError:
            bbox = region.bbox
            height = bbox[3] - bbox[0]
            width_y = bbox[4] - bbox[1]
            width_x = bbox[5] - bbox[2]
            max_dim = max(height, width_y, width_x)
            min_dim = min(height, width_y, width_x)
            props['eccentricity_3d'] = 1.0 - (min_dim / max(max_dim, 1))
            props['aspect_ratio_z_xy'] = height / max(min(width_y, width_x), 1)
        
        if image_3d is not None:
            cell_pixels = image_3d[mask_3d == region.label]
            if len(cell_pixels) > 0:
                props['mean_intensity_3d'] = float(np.mean(cell_pixels))
                props['max_intensity_3d'] = float(np.max(cell_pixels))
                props['std_intensity_3d'] = float(np.std(cell_pixels))
        
        features[region.label] = props
    
    return features


class Segmentation3D:
    """
    3D Segmentation handler that supports both 3D U-Net and 2D+Z processing.
    """
    
    def __init__(self,
                 weights_path_3d: Optional[str] = None,
                 weights_path_2d: Optional[str] = None,
                 device: str = 'auto',
                 threshold: float = 0.5,
                 use_3d_network: bool = True,
                 use_z_consistency: bool = True,
                 min_object_size: int = 500,
                 z_connected_threshold: float = 0.5):
        self.device = self._get_device(device)
        self.threshold = threshold
        self.use_3d_network = use_3d_network
        self.use_z_consistency = use_z_consistency
        self.min_object_size = min_object_size
        self.z_connected_threshold = z_connected_threshold
        
        self.model_3d = None
        self.model_2d = None
        
        if use_3d_network and weights_path_3d and Path(weights_path_3d).exists():
            self.model_3d = UNet3D(n_channels=1, n_classes=2, trilinear=True)
            self.model_3d.to(self.device)
            self._load_weights(self.model_3d, weights_path_3d)
            self.model_3d.eval()
            logger.info("3D U-Net model loaded")
        
        if weights_path_2d and Path(weights_path_2d).exists():
            from .segmentation import UNet
            self.model_2d = UNet(n_channels=1, n_classes=2)
            self.model_2d.to(self.device)
            self._load_weights(self.model_2d, weights_path_2d)
            self.model_2d.eval()
            logger.info("2D U-Net model loaded for fallback")
    
    def _get_device(self, device: str) -> torch.device:
        if device == 'auto':
            if torch.cuda.is_available():
                return torch.device('cuda')
            return torch.device('cpu')
        return torch.device(device)
    
    def _load_weights(self, model: nn.Module, weights_path: str) -> None:
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
        
        model.load_state_dict(new_state_dict, strict=False)
    
    def segment_3d(self, 
                   image_stack: np.ndarray,
                   channel: int = 0,
                   parallel: bool = False,
                   num_workers: int = 4) -> np.ndarray:
        """
        Segment 3D/4D/5D image data.
        
        Args:
            image_stack: Can be (T, Z, H, W), (T, C, Z, H, W), or (T, H, W) for 2D
            channel: Channel index if multi-channel
            parallel: Use parallel processing for 2D slices
            num_workers: Number of parallel workers
        
        Returns:
            Instance masks with same spatial dimensions as input
        """
        is_3d, z_slices = check_3d_data(image_stack)
        
        if not is_3d:
            from .segmentation import UNetSegmenter
            segmenter = UNetSegmenter(
                device=str(self.device),
                threshold=self.threshold,
                min_object_size=self.min_object_size
            )
            if self.model_2d is not None:
                segmenter.model = self.model_2d
            return segmenter.segment_stack(image_stack, parallel=parallel, num_workers=num_workers)
        
        if image_stack.ndim == 5:
            images = image_stack[:, channel, :, :, :]
        else:
            images = image_stack
        
        T, Z, H, W = images.shape
        logger.info(f"Processing 3D data: {T} timepoints, {Z} Z-slices, {H}x{W} pixels")
        
        if self.use_3d_network and self.model_3d is not None:
            instance_masks = self._segment_with_3d_unet(images)
        else:
            instance_masks = self._segment_with_2d_plus_z(images, parallel, num_workers)
        
        if self.use_z_consistency:
            instance_masks = z_axis_consistency_filter(
                instance_masks,
                z_connected_threshold=self.z_connected_threshold,
                min_z_slices=2
            )
        
        instance_masks = self._remove_small_objects_3d(instance_masks)
        
        return instance_masks
    
    def _segment_with_3d_unet(self, images: np.ndarray) -> np.ndarray:
        """
        Segment using 3D U-Net.
        """
        T, Z, H, W = images.shape
        instance_masks = np.zeros((T, Z, H, W), dtype=np.int32)
        prob_volumes = np.zeros((T, Z, H, W), dtype=np.float32)
        
        for t in range(T):
            logger.info(f"Segmenting volume {t+1}/{T} with 3D U-Net")
            
            volume = images[t]
            volume = normalize_image(volume)
            
            x = torch.from_numpy(volume).float().unsqueeze(0).unsqueeze(0)
            x = x.to(self.device)
            
            with torch.no_grad():
                logits = self.model_3d(x)
                logits = F.interpolate(
                    logits,
                    size=(Z, H, W),
                    mode='trilinear',
                    align_corners=True
                )
                probs = F.softmax(logits, dim=1)
                foreground_prob = probs[0, 1].cpu().numpy()
            
            prob_volumes[t] = foreground_prob
        
        instance_masks = create_3d_instance_mask(
            prob_volumes,
            threshold=self.threshold,
            use_3d_watershed=True
        )
        
        return instance_masks
    
    def _segment_with_2d_plus_z(self, 
                                  images: np.ndarray,
                                  parallel: bool,
                                  num_workers: int) -> np.ndarray:
        """
        Segment slice-by-slice using 2D network, then reconstruct 3D.
        """
        T, Z, H, W = images.shape
        original_shape = (T, Z, H, W)
        
        images_2d, _ = reshape_3d_to_2d(images)
        
        from .segmentation import UNetSegmenter
        segmenter = UNetSegmenter(
            device=str(self.device),
            threshold=self.threshold,
            min_object_size=self.min_object_size // Z
        )
        if self.model_2d is not None:
            segmenter.model = self.model_2d
        
        masks_2d = segmenter.segment_stack(
            images_2d,
            parallel=parallel,
            num_workers=num_workers
        )
        
        masks_3d = reshape_2d_to_3d(masks_2d, original_shape)
        
        return masks_3d
    
    def _remove_small_objects_3d(self, masks: np.ndarray) -> np.ndarray:
        """
        Remove small objects in 3D.
        """
        T, Z, H, W = masks.shape
        cleaned_masks = np.zeros_like(masks)
        
        for t in range(T):
            volume = masks[t]
            labels = np.unique(volume)
            labels = labels[labels != 0]
            
            new_volume = np.zeros_like(volume)
            new_label = 1
            
            for label in labels:
                vol = np.sum(volume == label)
                if vol >= self.min_object_size:
                    new_volume[volume == label] = new_label
                    new_label += 1
            
            cleaned_masks[t] = new_volume
        
        return cleaned_masks
    
    def extract_3d_track_features(self,
                                    masks_3d: np.ndarray,
                                    tracker: object,
                                    image_stack: Optional[np.ndarray] = None) -> pd.DataFrame:
        """
        Extract 3D features for each track.
        """
        from .utils import load_tiff_stack
        
        T = masks_3d.shape[0]
        features_3d = []
        
        for track_id, track in tracker.tracks.items():
            for i, frame in enumerate(track.frames):
                if frame >= T:
                    continue
                
                label = track.labels[i]
                mask_3d = masks_3d[frame]
                
                if np.any(mask_3d == label):
                    feats = extract_3d_features(
                        mask_3d,
                        image_stack[frame] if image_stack is not None else None
                    )
                    
                    if label in feats:
                        f = feats[label]
                        features_3d.append({
                            'track_id': track_id,
                            'frame': frame,
                            'volume': f['volume'],
                            'centroid_z': f['centroid_3d'][0],
                            'centroid_y': f['centroid_3d'][1],
                            'centroid_x': f['centroid_3d'][2],
                            'z_extent': f['z_extent'],
                            'extent_3d': f['extent'],
                            'solidity_3d': f['solidity'],
                        })
        
        return pd.DataFrame(features_3d)
