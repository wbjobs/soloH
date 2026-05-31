import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available. CNN detector will use NumPy fallback.")


@dataclass
class CNNDetectionParams:
    """Parameters for CNN-based internal wave detection."""
    use_cnn: bool = True
    model_architecture: str = 'unet'
    pretrained_weights: Optional[str] = None
    input_channels: int = 1
    num_classes: int = 2
    confidence_threshold: float = 0.5
    nms_threshold: float = 0.3
    min_box_size: int = 16
    stride: int = 16
    use_gpu: bool = True
    batch_size: int = 1
    use_numpy_fallback: bool = True


@dataclass
class CNNDetection:
    """Data class for a CNN-detected internal wave."""
    wave_id: int
    bbox: Tuple[int, int, int, int]
    center_row: int
    center_col: int
    confidence: float
    direction: float = 0.0
    wavelength: float = 0.0
    mask: Optional[np.ndarray] = None
    class_id: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CNNDetectionResult:
    """Result of CNN-based wave detection."""
    detections: List[CNNDetection] = field(default_factory=list)
    detection_map: Optional[np.ndarray] = None
    feature_maps: Optional[np.ndarray] = None
    inference_time: float = 0.0
    model_used: str = ''
    numpy_fallback_used: bool = False


class DoubleConvBlock:
    """Double convolution block: Conv2d -> BN -> ReLU -> Conv2d -> BN -> ReLU."""

    def __init__(self, in_channels: int, out_channels: int):
        self.in_channels = in_channels
        self.out_channels = out_channels
        kernels = [3, 3]
        self.weights1 = self._init_weights(in_channels, out_channels, kernels[0])
        self.bias1 = np.zeros(out_channels)
        self.weights2 = self._init_weights(out_channels, out_channels, kernels[1])
        self.bias2 = np.zeros(out_channels)
        self.gamma1 = np.ones(out_channels)
        self.beta1 = np.zeros(out_channels)
        self.gamma2 = np.ones(out_channels)
        self.beta2 = np.zeros(out_channels)

    def _init_weights(self, in_c: int, out_c: int, k: int) -> np.ndarray:
        std = np.sqrt(2.0 / (in_c * k * k))
        return np.random.randn(out_c, in_c, k, k) * std

    def _conv2d(self, x: np.ndarray, weights: np.ndarray, bias: np.ndarray,
                stride: int = 1, padding: int = 1) -> np.ndarray:
        N, C, H, W = x.shape
        F, _, KH, KW = weights.shape
        OH = (H + 2 * padding - KH) // stride + 1
        OW = (W + 2 * padding - KW) // stride + 1

        if padding > 0:
            x_pad = np.pad(x, ((0, 0), (0, 0), (padding, padding), (padding, padding)), mode='reflect')
        else:
            x_pad = x

        out = np.zeros((N, F, OH, OW))
        for i in range(OH):
            for j in range(OW):
                h_start = i * stride
                h_end = h_start + KH
                w_start = j * stride
                w_end = w_start + KW
                x_slice = x_pad[:, :, h_start:h_end, w_start:w_end]
                for f in range(F):
                    out[:, f, i, j] = np.sum(x_slice * weights[f], axis=(1, 2, 3)) + bias[f]
        return out

    def _batchnorm(self, x: np.ndarray, gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
        mean = np.mean(x, axis=(0, 2, 3), keepdims=True)
        var = np.var(x, axis=(0, 2, 3), keepdims=True)
        x_norm = (x - mean) / np.sqrt(var + 1e-5)
        return gamma.reshape(1, -1, 1, 1) * x_norm + beta.reshape(1, -1, 1, 1)

    def _relu(self, x: np.ndarray) -> np.ndarray:
        return np.maximum(0, x)

    def forward(self, x: np.ndarray) -> np.ndarray:
        x1 = self._conv2d(x, self.weights1, self.bias1)
        x1 = self._batchnorm(x1, self.gamma1, self.beta1)
        x1 = self._relu(x1)
        x2 = self._conv2d(x1, self.weights2, self.bias2)
        x2 = self._batchnorm(x2, self.gamma2, self.beta2)
        x2 = self._relu(x2)
        return x2


class WaveUNetNumpy:
    """NumPy implementation of U-Net for internal wave detection."""

    def __init__(self, in_channels: int = 1, n_classes: int = 2):
        self.in_channels = in_channels
        self.n_classes = n_classes

        self.down1 = DoubleConvBlock(in_channels, 16)
        self.down2 = DoubleConvBlock(16, 32)
        self.down3 = DoubleConvBlock(32, 64)
        self.down4 = DoubleConvBlock(64, 128)

        self.bottleneck = DoubleConvBlock(128, 256)

        self.up1 = DoubleConvBlock(256 + 128, 128)
        self.up2 = DoubleConvBlock(128 + 64, 64)
        self.up3 = DoubleConvBlock(64 + 32, 32)
        self.up4 = DoubleConvBlock(32 + 16, 16)

        self.final_conv_weights = np.random.randn(n_classes, 16, 1, 1) * np.sqrt(2.0 / 16)
        self.final_conv_bias = np.zeros(n_classes)

    def _maxpool(self, x: np.ndarray, ksize: int = 2) -> np.ndarray:
        N, C, H, W = x.shape
        OH, OW = H // ksize, W // ksize
        out = np.zeros((N, C, OH, OW))
        for i in range(OH):
            for j in range(OW):
                h_start = i * ksize
                w_start = j * ksize
                out[:, :, i, j] = np.max(
                    x[:, :, h_start:h_start+ksize, w_start:w_start+ksize], axis=(2, 3)
                )
        return out

    def _upsample(self, x: np.ndarray, scale: int = 2) -> np.ndarray:
        N, C, H, W = x.shape
        out = np.zeros((N, C, H * scale, W * scale))
        for i in range(H * scale):
            for j in range(W * scale):
                ii = min(i // scale, H - 1)
                jj = min(j // scale, W - 1)
                out[:, :, i, j] = x[:, :, ii, jj]
        return out

    def _sigmoid(self, x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -100, 100)))

    def forward(self, x: np.ndarray) -> Tuple[np.ndarray, List[np.ndarray]]:
        x1 = self.down1.forward(x)
        x2 = self._maxpool(x1)
        x2 = self.down2.forward(x2)
        x3 = self._maxpool(x2)
        x3 = self.down3.forward(x3)
        x4 = self._maxpool(x3)
        x4 = self.down4.forward(x4)

        x5 = self._maxpool(x4)
        x5 = self.bottleneck.forward(x5)

        x6 = self._upsample(x5)
        x6 = np.concatenate([x6, x4], axis=1)
        x6 = self.up1.forward(x6)

        x7 = self._upsample(x6)
        x7 = np.concatenate([x7, x3], axis=1)
        x7 = self.up2.forward(x7)

        x8 = self._upsample(x7)
        x8 = np.concatenate([x8, x2], axis=1)
        x8 = self.up3.forward(x8)

        x9 = self._upsample(x8)
        x9 = np.concatenate([x9, x1], axis=1)
        x9 = self.up4.forward(x9)

        out = np.zeros((x.shape[0], self.n_classes, x.shape[2], x.shape[3]))
        for f in range(self.n_classes):
            kernel = self.final_conv_weights[f]
            for c in range(16):
                out[:, f] += kernel[c, 0, 0] * x9[:, c]
            out[:, f] += self.final_conv_bias[f]

        out = self._sigmoid(out)

        return out, [x1, x2, x3, x4, x5]


if TORCH_AVAILABLE:
    class WaveUNetTorch(nn.Module):
        """PyTorch implementation of U-Net for internal wave detection."""

        def __init__(self, in_channels: int = 1, n_classes: int = 2):
            super().__init__()
            self.in_channels = in_channels
            self.n_classes = n_classes

            def double_conv(in_c, out_c):
                return nn.Sequential(
                    nn.Conv2d(in_c, out_c, kernel_size=3, padding=1),
                    nn.BatchNorm2d(out_c),
                    nn.ReLU(inplace=True),
                    nn.Conv2d(out_c, out_c, kernel_size=3, padding=1),
                    nn.BatchNorm2d(out_c),
                    nn.ReLU(inplace=True)
                )

            self.down1 = double_conv(in_channels, 16)
            self.down2 = double_conv(16, 32)
            self.down3 = double_conv(32, 64)
            self.down4 = double_conv(64, 128)

            self.bottleneck = double_conv(128, 256)

            self.up1 = double_conv(256 + 128, 128)
            self.up2 = double_conv(128 + 64, 64)
            self.up3 = double_conv(64 + 32, 32)
            self.up4 = double_conv(32 + 16, 16)

            self.final_conv = nn.Conv2d(16, n_classes, kernel_size=1)
            self.maxpool = nn.MaxPool2d(2)
            self.upsample = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)

        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, List[torch.Tensor]]:
            x1 = self.down1(x)
            x2 = self.down2(self.maxpool(x1))
            x3 = self.down3(self.maxpool(x2))
            x4 = self.down4(self.maxpool(x3))

            x5 = self.bottleneck(self.maxpool(x4))

            x6 = self.up1(torch.cat([self.upsample(x5), x4], dim=1))
            x7 = self.up2(torch.cat([self.upsample(x6), x3], dim=1))
            x8 = self.up3(torch.cat([self.upsample(x7), x2], dim=1))
            x9 = self.up4(torch.cat([self.upsample(x8), x1], dim=1))

            out = torch.sigmoid(self.final_conv(x9))

            return out, [x1, x2, x3, x4, x5]


class CNNWaveDetector:
    """
    CNN-based end-to-end internal wave detector.

    Uses a U-Net architecture to directly detect internal wave features
    from SAR images, skipping hand-crafted feature engineering.

    Supports both PyTorch (preferred) and NumPy (fallback) implementations.
    """

    def __init__(self, params: Optional[CNNDetectionParams] = None):
        self.params = params or CNNDetectionParams()

        if TORCH_AVAILABLE and self.params.use_gpu:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device('cpu') if TORCH_AVAILABLE else 'numpy'

        self.model = None
        self._build_model()

    def _build_model(self):
        """Build the detection model."""
        if TORCH_AVAILABLE and self.params.use_cnn:
            logger.info(f"Building PyTorch WaveUNet on {self.device}...")
            self.model = WaveUNetTorch(
                in_channels=self.params.input_channels,
                n_classes=self.params.num_classes
            ).to(self.device)
            self.model.eval()

            if self.params.pretrained_weights and os.path.exists(self.params.pretrained_weights):
                logger.info(f"Loading pretrained weights from {self.params.pretrained_weights}...")
                state_dict = torch.load(self.params.pretrained_weights, map_location=self.device)
                self.model.load_state_dict(state_dict)
            else:
                logger.info("Using randomly initialized WaveUNet weights")
                self._initialize_pseudo_weights()
        elif self.params.use_numpy_fallback:
            logger.info("Building NumPy WaveUNet (fallback)...")
            self.model = WaveUNetNumpy(
                in_channels=self.params.input_channels,
                n_classes=self.params.num_classes
            )
        else:
            logger.warning("No CNN model available. CNN detection disabled.")

    def _initialize_pseudo_weights(self):
        """Initialize weights with wave-like patterns for demo purposes."""
        if not TORCH_AVAILABLE:
            return

        model_type = type(self.model).__name__
        if model_type != 'WaveUNetTorch':
            return

        with torch.no_grad():
            for m in self.model.modules():
                if type(m).__name__ == 'Conv2d':
                    if m.in_channels == 1 and m.out_channels == 16:
                        for i in range(16):
                            angle = np.deg2rad(i * 11.25)
                            freq = 0.05 + 0.01 * (i % 4)
                            for y in range(3):
                                for x in range(3):
                                    dy = y - 1
                                    dx = x - 1
                                    wave_pattern = np.sin(2 * np.pi * freq * (dx * np.cos(angle) + dy * np.sin(angle)))
                                    m.weight[i, 0, y, x] = wave_pattern

    def detect(self, image: np.ndarray) -> CNNDetectionResult:
        """
        Detect internal waves using CNN.

        Args:
            image: Input SAR image (2D numpy array)

        Returns:
            CNNDetectionResult containing detections
        """
        import time
        start_time = time.time()

        result = CNNDetectionResult()
        result.model_used = self.params.model_architecture

        if self.model is None:
            logger.warning("CNN model not available, returning empty result")
            return result

        if image.ndim == 2:
            input_tensor = image[np.newaxis, np.newaxis, :, :].astype(np.float32)
        else:
            input_tensor = image.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)

        logger.info(f"Running CNN detection on {image.shape} image...")

        try:
            if TORCH_AVAILABLE and isinstance(self.model, WaveUNetTorch):
                detections, features = self._detect_torch(input_tensor)
                result.numpy_fallback_used = False
            else:
                detections, features = self._detect_numpy(input_tensor)
                result.numpy_fallback_used = True

            result.detection_map = detections[0, 1] if detections.shape[1] > 1 else detections[0, 0]
            result.feature_maps = features[0] if features else None

            detections_list = self._postprocess_detections(
                result.detection_map, image.shape
            )
            result.detections = detections_list

        except Exception as e:
            logger.error(f"CNN detection failed: {e}")
            if self.params.use_numpy_fallback and not result.numpy_fallback_used:
                logger.info("Falling back to NumPy implementation...")
                detections, features = self._detect_numpy(input_tensor)
                result.numpy_fallback_used = True
                result.detection_map = detections[0, 1] if detections.shape[1] > 1 else detections[0, 0]
                result.feature_maps = features[0] if features else None
                result.detections = self._postprocess_detections(result.detection_map, image.shape)

        result.inference_time = time.time() - start_time
        logger.info(f"CNN detection completed: {len(result.detections)} waves in {result.inference_time:.3f}s")

        return result

    def _detect_torch(self, input_tensor: np.ndarray) -> Tuple[np.ndarray, List[np.ndarray]]:
        """Run detection with PyTorch model."""
        x = torch.from_numpy(input_tensor).to(self.device)

        with torch.no_grad():
            out, features = self.model(x)

        out_np = out.cpu().numpy()
        features_np = [f.cpu().numpy() for f in features]

        return out_np, features_np

    def _detect_numpy(self, input_tensor: np.ndarray) -> Tuple[np.ndarray, List[np.ndarray]]:
        """Run detection with NumPy model."""
        return self.model.forward(input_tensor)

    def _postprocess_detections(self, detection_map: np.ndarray,
                                 image_shape: Tuple[int, int]) -> List[CNNDetection]:
        """
        Post-process CNN output to extract individual wave detections.

        Args:
            detection_map: Class probability map [H, W]
            image_shape: Original image shape

        Returns:
            List of CNNDetection objects
        """
        from scipy import ndimage

        binary_mask = detection_map > self.params.confidence_threshold

        labeled, num_regions = ndimage.label(binary_mask)

        detections = []
        wave_id = 0

        for region_id in range(1, num_regions + 1):
            region_mask = labeled == region_id

            if np.sum(region_mask) < self.params.min_box_size:
                continue

            rows, cols = np.where(region_mask)

            min_row, max_row = np.min(rows), np.max(rows)
            min_col, max_col = np.min(cols), np.max(cols)

            height = max_row - min_row
            width = max_col - min_col

            if height < self.params.min_box_size or width < self.params.min_box_size:
                continue

            center_row = int((min_row + max_row) // 2)
            center_col = int((min_col + max_col) // 2)

            region_probs = detection_map[region_mask]
            confidence = float(np.mean(region_probs))

            direction = self._estimate_direction_from_mask(region_mask, center_row, center_col)
            wavelength = self._estimate_wavelength_from_mask(region_mask, detection_map)

            detection = CNNDetection(
                wave_id=wave_id,
                bbox=(min_row, min_col, max_row, max_col),
                center_row=center_row,
                center_col=center_col,
                confidence=confidence,
                direction=direction,
                wavelength=wavelength,
                mask=region_mask.astype(np.uint8),
                class_id=1,
                metadata={
                    'area': int(np.sum(region_mask)),
                    'bbox_height': height,
                    'bbox_width': width,
                    'max_probability': float(np.max(region_probs))
                }
            )
            detections.append(detection)
            wave_id += 1

        detections = self._apply_nms(detections)

        return detections

    def _estimate_direction_from_mask(self, mask: np.ndarray,
                                       center_row: int, center_col: int) -> float:
        """Estimate wave direction from binary mask using image moments."""
        from scipy import ndimage

        y_indices, x_indices = np.where(mask)

        if len(y_indices) < 10:
            return 0.0

        x_mean = np.mean(x_indices)
        y_mean = np.mean(y_indices)

        dx = x_indices - x_mean
        dy = y_indices - y_mean

        cov_xx = np.mean(dx * dx)
        cov_yy = np.mean(dy * dy)
        cov_xy = np.mean(dx * dy)

        eigenvalues, eigenvectors = np.linalg.eig([[cov_xx, cov_xy], [cov_xy, cov_yy]])

        if eigenvalues[0] > eigenvalues[1]:
            main_vec = eigenvectors[:, 0]
        else:
            main_vec = eigenvectors[:, 1]

        angle_rad = np.arctan2(main_vec[1], main_vec[0])
        angle_deg = np.rad2deg(angle_rad) % 180

        return float(angle_deg)

    def _estimate_wavelength_from_mask(self, mask: np.ndarray,
                                        detection_map: np.ndarray) -> float:
        """Estimate wavelength from detection map using autocorrelation."""
        from scipy import signal

        if np.sum(mask) < 20:
            return 50.0

        region = detection_map.copy()
        region[~mask] = 0

        center = np.array(region.shape) // 2
        profile = region[int(center[0]), :]

        if np.sum(profile) < 0.1:
            profile = region[:, int(center[1])]

        try:
            autocorr = np.correlate(profile - np.mean(profile),
                                    profile - np.mean(profile), mode='full')
            autocorr = autocorr[len(autocorr) // 2:]

            peaks, _ = signal.find_peaks(autocorr, distance=5, prominence=0.1)
            if len(peaks) >= 2:
                wavelength_pixels = np.mean(np.diff(peaks))
                return float(wavelength_pixels * 10.0)
        except Exception:
            pass

        return 50.0

    def _apply_nms(self, detections: List[CNNDetection]) -> List[CNNDetection]:
        """Apply Non-Maximum Suppression to remove overlapping detections."""
        if len(detections) <= 1:
            return detections

        detections.sort(key=lambda d: d.confidence, reverse=True)

        keep = []
        while detections:
            best = detections.pop(0)
            keep.append(best)

            remaining = []
            for det in detections:
                iou = self._compute_iou(best.bbox, det.bbox)
                if iou < self.params.nms_threshold:
                    remaining.append(det)
            detections = remaining

        return keep

    def _compute_iou(self, bbox1: Tuple[int, int, int, int],
                     bbox2: Tuple[int, int, int, int]) -> float:
        """Compute Intersection over Union between two bounding boxes."""
        min_r1, min_c1, max_r1, max_c1 = bbox1
        min_r2, min_c2, max_r2, max_c2 = bbox2

        inter_min_r = max(min_r1, min_r2)
        inter_min_c = max(min_c1, min_c2)
        inter_max_r = min(max_r1, max_r2)
        inter_max_c = min(max_c1, max_c2)

        if inter_min_r >= inter_max_r or inter_min_c >= inter_max_c:
            return 0.0

        inter_area = (inter_max_r - inter_min_r) * (inter_max_c - inter_min_c)
        area1 = (max_r1 - min_r1) * (max_c1 - min_c1)
        area2 = (max_r2 - min_r2) * (max_c2 - min_c2)

        return inter_area / max(area1 + area2 - inter_area, 1e-8)

    def visualize_detection(self, result: CNNDetectionResult,
                            original_image: np.ndarray) -> np.ndarray:
        """
        Create visualization of CNN detection results.

        Args:
            result: CNN detection result
            original_image: Original SAR image

        Returns:
            Visualization image (BGR for OpenCV)
        """
        import cv2

        if len(original_image.shape) == 2:
            display = cv2.cvtColor((original_image * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        else:
            display = (original_image * 255).astype(np.uint8).copy()

        if result.detection_map is not None:
            heatmap = (result.detection_map * 255).astype(np.uint8)
            heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
            display = cv2.addWeighted(display, 0.6, heatmap_color, 0.4, 0)

        for det in result.detections:
            color = self._get_confidence_color(det.confidence)
            min_r, min_c, max_r, max_c = det.bbox

            cv2.rectangle(display, (min_c, min_r), (max_c, max_r), color, 2)

            label = f"IW {det.wave_id} ({det.confidence:.2f})"
            cv2.putText(display, label, (min_c, max(0, min_r - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            center = (det.center_col, det.center_row)
            dir_rad = np.deg2rad(det.direction)
            end_point = (
                int(center[0] + 30 * np.cos(dir_rad)),
                int(center[1] + 30 * np.sin(dir_rad))
            )
            cv2.arrowedLine(display, center, end_point, (0, 255, 255), 2, tipLength=0.3)

        return display

    def _get_confidence_color(self, confidence: float) -> Tuple[int, int, int]:
        """Get BGR color based on confidence level."""
        if confidence >= 0.8:
            return (0, 255, 0)
        elif confidence >= 0.6:
            return (0, 255, 255)
        elif confidence >= 0.4:
            return (0, 165, 255)
        else:
            return (0, 0, 255)
