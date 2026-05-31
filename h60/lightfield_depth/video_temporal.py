"""
Temporal Consistency for Light Field Video Depth Estimation.

Implements temporal smoothing and consistency constraints for video
depth estimation, including:
- Optical flow estimation for temporal alignment
- Kalman filtering for per-pixel depth tracking
- Spatio-temporal joint filtering
- Temporal consistency check and outlier rejection
- Exponential moving average smoothing
"""

import numpy as np
from tqdm import tqdm
import cv2
from scipy.ndimage import gaussian_filter, median_filter, uniform_filter


class TemporalDepthSmoother:
    """
    Temporal smoothing for video depth estimation using Kalman filtering
    and optical flow-based motion compensation.
    
    Maintains per-pixel state (depth estimate + variance) across frames.
    """
    
    def __init__(self, alpha=0.3, process_noise=0.01, measurement_noise=0.1,
                 use_flow=True, flow_method='farneback'):
        """
        Initialize temporal smoother.
        
        Parameters:
            alpha: Smoothing factor for EMA (0-1, lower = more smoothing)
            process_noise: Process noise variance for Kalman filter
            measurement_noise: Measurement noise variance for Kalman filter
            use_flow: Use optical flow for motion compensation
            flow_method: 'farneback', 'dis', 'dense'
        """
        self.alpha = alpha
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.use_flow = use_flow
        self.flow_method = flow_method
        
        self.prev_depth = None
        self.prev_variance = None
        self.prev_frame = None
        self.prev_confidence = None
        
        self.history = []
        self.flow_history = []
        
        self.frame_count = 0
    
    def reset(self):
        """Reset the smoother state."""
        self.prev_depth = None
        self.prev_variance = None
        self.prev_frame = None
        self.prev_confidence = None
        self.history = []
        self.flow_history = []
        self.frame_count = 0
    
    def estimate_flow(self, frame1, frame2):
        """
        Estimate dense optical flow between two frames.
        
        Parameters:
            frame1: Previous frame (grayscale) [H, W]
            frame2: Current frame (grayscale) [H, W]
            
        Returns:
            flow: Optical flow field [H, W, 2] (x, y displacements)
        """
        if frame1.shape != frame2.shape:
            raise ValueError("Frames must have the same shape")
        
        if len(frame1.shape) == 3:
            frame1 = np.mean(frame1, axis=-1)
            frame2 = np.mean(frame2, axis=-1)
        
        frame1_8 = (frame1 * 255).astype(np.uint8) if frame1.max() <= 1.0 else frame1.astype(np.uint8)
        frame2_8 = (frame2 * 255).astype(np.uint8) if frame2.max() <= 1.0 else frame2.astype(np.uint8)
        
        try:
            if self.flow_method == 'farneback':
                flow = cv2.calcOpticalFlowFarneback(
                    frame1_8, frame2_8, None,
                    pyr_scale=0.5, levels=3, winsize=15,
                    iterations=3, poly_n=5, poly_sigma=1.2, flags=0
                )
            elif self.flow_method == 'dis':
                dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
                flow = dis.calc(frame1_8, frame2_8, None)
            else:
                flow = np.zeros((frame1.shape[0], frame1.shape[1], 2), dtype=np.float32)
                
        except:
            flow = np.zeros((frame1.shape[0], frame1.shape[1], 2), dtype=np.float32)
        
        return flow
    
    def warp_image(self, image, flow):
        """
        Warp image using optical flow.
        
        Parameters:
            image: Image to warp [H, W] or [H, W, C]
            flow: Optical flow field [H, W, 2]
            
        Returns:
            warped: Warped image
        """
        h, w = flow.shape[:2]
        
        y_coords, x_coords = np.mgrid[0:h, 0:w]
        
        map_x = x_coords + flow[:, :, 0]
        map_y = y_coords + flow[:, :, 1]
        
        map_x = map_x.astype(np.float32)
        map_y = map_y.astype(np.float32)
        
        try:
            if len(image.shape) == 2:
                warped = cv2.remap(image, map_x, map_y, cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_REFLECT)
            else:
                warped = np.zeros_like(image)
                for c in range(image.shape[2]):
                    warped[:, :, c] = cv2.remap(
                        image[:, :, c], map_x, map_y, cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REFLECT
                    )
        except:
            from scipy.ndimage import map_coordinates
            coords = np.stack([map_y.flatten(), map_x.flatten()], axis=0)
            
            if len(image.shape) == 2:
                warped = map_coordinates(image, coords, order=1, mode='reflect').reshape(h, w)
            else:
                warped = np.zeros_like(image)
                for c in range(image.shape[2]):
                    warped[:, :, c] = map_coordinates(
                        image[:, :, c], coords, order=1, mode='reflect'
                    ).reshape(h, w)
        
        return warped
    
    def kalman_predict(self, prev_depth, prev_var):
        """
        Kalman filter prediction step.
        
        Parameters:
            prev_depth: Previous depth estimate [H, W]
            prev_var: Previous depth variance [H, W]
            
        Returns:
            pred_depth: Predicted depth [H, W]
            pred_var: Predicted variance [H, W]
        """
        pred_depth = prev_depth.copy()
        pred_var = prev_var + self.process_noise
        
        return pred_depth, pred_var
    
    def kalman_update(self, pred_depth, pred_var, meas_depth, meas_var):
        """
        Kalman filter update step.
        
        Parameters:
            pred_depth: Predicted depth [H, W]
            pred_var: Predicted variance [H, W]
            meas_depth: Measured depth [H, W]
            meas_var: Measurement variance [H, W]
            
        Returns:
            new_depth: Updated depth estimate [H, W]
            new_var: Updated variance [H, W]
            kalman_gain: Kalman gain [H, W]
        """
        kalman_gain = pred_var / (pred_var + meas_var + 1e-8)
        
        new_depth = pred_depth + kalman_gain * (meas_depth - pred_depth)
        new_var = (1 - kalman_gain) * pred_var
        
        return new_depth, new_var, kalman_gain
    
    def check_temporal_consistency(self, current_depth, warped_depth, 
                                   threshold=2.0):
        """
        Check temporal consistency between current and warped previous depth.
        
        Parameters:
            current_depth: Current depth estimate [H, W]
            warped_depth: Warped previous depth [H, W]
            threshold: Consistency threshold (in depth units)
            
        Returns:
            consistent_mask: Boolean mask of consistent pixels
            error_map: Depth difference map [H, W]
        """
        error_map = np.abs(current_depth - warped_depth)
        
        consistent_mask = error_map < threshold
        
        return consistent_mask, error_map
    
    def process_frame(self, current_depth, current_frame, current_confidence=None,
                      measurement_variance=None):
        """
        Process a single frame with temporal smoothing.
        
        Parameters:
            current_depth: Current frame's depth estimate [H, W]
            current_frame: Current video frame (grayscale or RGB) [H, W] or [H, W, 3]
            current_confidence: Optional confidence map [H, W] (0-1)
            measurement_variance: Optional per-pixel measurement variance
            
        Returns:
            smoothed_depth: Temporally smoothed depth map [H, W]
            outlier_mask: Mask of detected temporal outliers
        """
        h, w = current_depth.shape
        
        if current_frame.ndim == 3 and current_frame.shape[2] == 3:
            current_gray = np.mean(current_frame, axis=-1)
        else:
            current_gray = current_frame
        
        if current_confidence is None:
            current_confidence = np.ones((h, w), dtype=np.float32)
        
        if measurement_variance is None:
            measurement_variance = self.measurement_noise * (1.0 - current_confidence + 0.1)
        
        if self.prev_depth is None:
            self.prev_depth = current_depth.copy()
            self.prev_variance = np.full((h, w), self.measurement_noise, dtype=np.float32)
            self.prev_frame = current_gray.copy()
            self.prev_confidence = current_confidence.copy()
            self.frame_count = 1
            
            self.history.append(current_depth.copy())
            
            return current_depth, np.zeros((h, w), dtype=bool)
        
        flow = None
        warped_depth = self.prev_depth.copy()
        warped_variance = self.prev_variance.copy()
        
        if self.use_flow:
            flow = self.estimate_flow(self.prev_frame, current_gray)
            warped_depth = self.warp_image(self.prev_depth, flow)
            warped_conf = self.warp_image(self.prev_confidence, flow)
            warped_variance = self.warp_image(self.prev_variance, flow)
            
            self.flow_history.append(flow)
        
        consistent_mask, error_map = self.check_temporal_consistency(
            current_depth, warped_depth, threshold=3.0
        )
        
        pred_depth, pred_var = self.kalman_predict(warped_depth, warped_variance)
        
        fused_depth, fused_var, k_gain = self.kalman_update(
            pred_depth, pred_var, current_depth, measurement_variance
        )
        
        outlier_mask = ~consistent_mask
        
        if np.any(outlier_mask):
            outlier_depth = pred_depth[outlier_mask]
            outlier_var = pred_var[outlier_mask] + self.process_noise * 2
            
            fused_depth[outlier_mask] = outlier_depth
            fused_var[outlier_mask] = outlier_var
        
        alpha_adaptive = self.alpha * current_confidence[:, :, np.newaxis] if False else self.alpha
        ema_depth = alpha_adaptive * current_depth + (1 - alpha_adaptive) * pred_depth
        
        final_depth = np.where(consistent_mask, fused_depth, ema_depth)
        
        self.prev_depth = final_depth.copy()
        self.prev_variance = fused_var.copy()
        self.prev_frame = current_gray.copy()
        self.prev_confidence = current_confidence.copy()
        self.frame_count += 1
        
        self.history.append(final_depth.copy())
        
        if len(self.history) > 30:
            self.history.pop(0)
        if len(self.flow_history) > 30:
            self.flow_history.pop(0)
        
        return final_depth, outlier_mask


class SpatioTemporalFilter:
    """
    Joint spatio-temporal filtering for video depth maps.
    
    Combines:
    - Temporal filtering (across frames)
    - Spatial filtering (within frame, edge-preserving)
    - Confidence-weighted fusion
    """
    
    def __init__(self, temporal_window=5, spatial_sigma=1.0, temporal_sigma=2.0,
                 edge_threshold=0.5):
        """
        Initialize spatio-temporal filter.
        
        Parameters:
            temporal_window: Number of frames to consider for temporal filtering
            spatial_sigma: Sigma for spatial Gaussian kernel
            temporal_sigma: Sigma for temporal Gaussian kernel
            edge_threshold: Threshold for edge-preserving filtering
        """
        self.temporal_window = temporal_window
        self.spatial_sigma = spatial_sigma
        self.temporal_sigma = temporal_sigma
        self.edge_threshold = edge_threshold
        
        self.depth_buffer = []
        self.conf_buffer = []
        self.frame_buffer = []
    
    def reset(self):
        """Reset filter buffers."""
        self.depth_buffer = []
        self.conf_buffer = []
        self.frame_buffer = []
    
    def add_frame(self, depth, confidence=None, frame=None):
        """Add a frame to the buffer."""
        self.depth_buffer.append(depth.copy())
        if confidence is None:
            confidence = np.ones_like(depth)
        self.conf_buffer.append(confidence.copy())
        if frame is not None:
            self.frame_buffer.append(frame.copy())
        
        if len(self.depth_buffer) > self.temporal_window:
            self.depth_buffer.pop(0)
            self.conf_buffer.pop(0)
            if self.frame_buffer:
                self.frame_buffer.pop(0)
    
    def apply(self, depth=None, confidence=None, frame=None):
        """
        Apply spatio-temporal filtering.
        
        Parameters:
            depth: Current depth map (if not added already)
            confidence: Current confidence map
            frame: Current frame (for edge detection)
            
        Returns:
            filtered_depth: Spatio-temporally filtered depth map
        """
        if depth is not None:
            self.add_frame(depth, confidence, frame)
        
        if len(self.depth_buffer) < 2:
            return self.depth_buffer[-1]
        
        stacked_depths = np.stack(self.depth_buffer, axis=0)
        stacked_confs = np.stack(self.conf_buffer, axis=0)
        
        num_frames = len(self.depth_buffer)
        temporal_weights = np.exp(-(np.arange(num_frames) - num_frames + 1) ** 2 / 
                                  (2 * self.temporal_sigma ** 2))
        temporal_weights = temporal_weights / temporal_weights.sum()
        
        conf_sum = np.sum(stacked_confs * temporal_weights[:, np.newaxis, np.newaxis], axis=0) + 1e-8
        weighted_depths = stacked_depths * stacked_confs * temporal_weights[:, np.newaxis, np.newaxis]
        temporal_avg = np.sum(weighted_depths, axis=0) / conf_sum
        
        if self.frame_buffer and len(self.frame_buffer) == num_frames:
            current_frame = self.frame_buffer[-1]
            if current_frame.ndim == 3:
                gray = np.mean(current_frame, axis=-1)
            else:
                gray = current_frame
            
            try:
                grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
                grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            except:
                from scipy.ndimage import sobel
                grad_x = sobel(gray, axis=1)
                grad_y = sobel(gray, axis=0)
            edge_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)
            edge_mag = (edge_mag - edge_mag.min()) / (edge_mag.max() + 1e-8)
            
            edge_mask = edge_mag < self.edge_threshold
            
            from scipy.ndimage import gaussian_filter
            spatial_smooth = gaussian_filter(temporal_avg, sigma=self.spatial_sigma)
            
            filtered = np.where(edge_mask, spatial_smooth, temporal_avg)
        else:
            from scipy.ndimage import gaussian_filter
            filtered = gaussian_filter(temporal_avg, sigma=self.spatial_sigma)
        
        return filtered


def estimate_optical_flow(frame1, frame2, method='farneback'):
    """
    Estimate dense optical flow between two frames.
    
    Parameters:
        frame1: First frame [H, W]
        frame2: Second frame [H, W]
        method: 'farneback' or 'dis'
        
    Returns:
        flow: Optical flow field [H, W, 2]
    """
    if len(frame1.shape) == 3:
        frame1 = np.mean(frame1, axis=-1)
    if len(frame2.shape) == 3:
        frame2 = np.mean(frame2, axis=-1)
    
    f1 = (frame1 * 255).astype(np.uint8) if frame1.max() <= 1.0 else frame1.astype(np.uint8)
    f2 = (frame2 * 255).astype(np.uint8) if frame2.max() <= 1.0 else frame2.astype(np.uint8)
    
    try:
        if method == 'farneback':
            flow = cv2.calcOpticalFlowFarneback(
                f1, f2, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
        elif method == 'dis':
            dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
            flow = dis.calc(f1, f2, None)
        else:
            flow = np.zeros((frame1.shape[0], frame1.shape[1], 2), dtype=np.float32)
    except:
        flow = np.zeros((frame1.shape[0], frame1.shape[1], 2), dtype=np.float32)
    
    return flow


def warp_depth(depth, flow):
    """Warp depth map using optical flow."""
    h, w = depth.shape
    
    y_coords, x_coords = np.mgrid[0:h, 0:w]
    map_x = (x_coords + flow[:, :, 0]).astype(np.float32)
    map_y = (y_coords + flow[:, :, 1]).astype(np.float32)
    
    try:
        warped = cv2.remap(depth.astype(np.float32), map_x, map_y,
                           cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    except:
        from scipy.ndimage import map_coordinates
        coords = np.stack([map_y.flatten(), map_x.flatten()], axis=0)
        warped = map_coordinates(depth, coords, order=1, mode='reflect').reshape(h, w)
    
    return warped


def smooth_temporal_kalman(depth_sequence, confidence_sequence=None, 
                           process_noise=0.01, measurement_noise=0.1):
    """
    Smooth a sequence of depth maps using Kalman filtering.
    
    Parameters:
        depth_sequence: List or array of depth maps [T, H, W]
        confidence_sequence: Optional list of confidence maps [T, H, W]
        process_noise: Kalman filter process noise
        measurement_noise: Kalman filter measurement noise
        
    Returns:
        smoothed_depths: Temporally smoothed depth sequence [T, H, W]
    """
    num_frames = len(depth_sequence)
    h, w = depth_sequence[0].shape
    
    smoothed = np.zeros((num_frames, h, w), dtype=np.float32)
    
    x_hat = depth_sequence[0].copy()
    P = np.full((h, w), measurement_noise, dtype=np.float32)
    
    Q = process_noise
    R = measurement_noise
    
    if confidence_sequence is None:
        confidence_sequence = [np.ones((h, w)) for _ in range(num_frames)]
    
    for t in tqdm(range(num_frames), desc="Temporal smoothing"):
        x_pred = x_hat.copy()
        P_pred = P + Q
        
        R_t = R * (1.0 - confidence_sequence[t] + 0.1)
        
        K = P_pred / (P_pred + R_t + 1e-8)
        
        x_hat = x_pred + K * (depth_sequence[t] - x_pred)
        P = (1 - K) * P_pred
        
        smoothed[t] = x_hat
    
    return smoothed


def smooth_temporal_ema(depth_sequence, alpha=0.3):
    """
    Smooth depth sequence using Exponential Moving Average (EMA).
    
    Parameters:
        depth_sequence: List or array of depth maps [T, H, W]
        alpha: Smoothing factor (0-1, lower = more smoothing)
        
    Returns:
        smoothed_depths: EMA smoothed depth sequence [T, H, W]
    """
    num_frames = len(depth_sequence)
    smoothed = np.zeros_like(depth_sequence)
    
    smoothed[0] = depth_sequence[0].copy()
    
    for t in range(1, num_frames):
        smoothed[t] = alpha * depth_sequence[t] + (1 - alpha) * smoothed[t-1]
    
    return smoothed


def smooth_temporal_bilateral(depth_sequence, flow_sequence=None,
                              spatial_sigma=3.0, temporal_sigma=1.0):
    """
    Temporal bilateral filtering that considers depth similarity.
    
    Parameters:
        depth_sequence: Depth map sequence [T, H, W]
        flow_sequence: Optional optical flow sequence for warping
        spatial_sigma: Spatial sigma for bilateral filter
        temporal_sigma: Temporal sigma for bilateral filter
        
    Returns:
        smoothed_depths: Filtered depth sequence [T, H, W]
    """
    from scipy.ndimage import gaussian_filter
    
    num_frames = len(depth_sequence)
    h, w = depth_sequence[0].shape
    smoothed = np.zeros_like(depth_sequence)
    
    half_t = 2
    
    for t in tqdm(range(num_frames), desc="Temporal bilateral smoothing"):
        weights = np.zeros((h, w), dtype=np.float32)
        values = np.zeros((h, w), dtype=np.float32)
        
        for dt in range(-half_t, half_t + 1):
            t_idx = np.clip(t + dt, 0, num_frames - 1)
            
            if flow_sequence is not None and dt != 0 and t_idx < len(flow_sequence):
                warped = warp_depth(depth_sequence[t_idx], flow_sequence[t_idx])
            else:
                warped = depth_sequence[t_idx]
            
            spatial_weight = gaussian_filter(np.ones((h, w)), sigma=spatial_sigma)
            temporal_weight = np.exp(-dt ** 2 / (2 * temporal_sigma ** 2))
            
            depth_diff = np.abs(warped - depth_sequence[t])
            depth_weight = np.exp(-depth_diff ** 2 / (2 * 0.5 ** 2))
            
            total_weight = spatial_weight * temporal_weight * depth_weight
            
            values += warped * total_weight
            weights += total_weight
        
        smoothed[t] = values / (weights + 1e-8)
    
    return smoothed


def temporal_consistency_check(depth_sequence, flow_sequence=None, threshold=2.0):
    """
    Check temporal consistency across depth sequence.
    
    Parameters:
        depth_sequence: Depth map sequence [T, H, W]
        flow_sequence: Optional optical flow sequence
        threshold: Consistency threshold
        
    Returns:
        consistency_scores: Per-frame consistency scores [T, H, W] (0-1, 1=consistent)
        outlier_masks: Per-frame outlier masks [T, H, W]
    """
    num_frames = len(depth_sequence)
    h, w = depth_sequence[0].shape
    
    consistency = np.zeros((num_frames, h, w), dtype=np.float32)
    outliers = np.zeros((num_frames, h, w), dtype=bool)
    
    for t in range(num_frames):
        if t > 0:
            if flow_sequence is not None and t-1 < len(flow_sequence):
                warped_prev = warp_depth(depth_sequence[t-1], flow_sequence[t-1])
            else:
                warped_prev = depth_sequence[t-1]
            
            error_prev = np.abs(depth_sequence[t] - warped_prev)
            consistent_prev = error_prev < threshold
        else:
            consistent_prev = np.ones((h, w), dtype=bool)
            error_prev = np.zeros((h, w))
        
        if t < num_frames - 1:
            if flow_sequence is not None and t < len(flow_sequence):
                flow_inv = -flow_sequence[t]
                warped_next = warp_depth(depth_sequence[t+1], flow_inv)
            else:
                warped_next = depth_sequence[t+1]
            
            error_next = np.abs(depth_sequence[t] - warped_next)
            consistent_next = error_next < threshold
        else:
            consistent_next = np.ones((h, w), dtype=bool)
            error_next = np.zeros((h, w))
        
        consistent = consistent_prev & consistent_next
        error = (error_prev + error_next) / 2.0
        
        consistency[t] = 1.0 - np.clip(error / threshold, 0, 1)
        outliers[t] = ~consistent
    
    return consistency, outliers


def process_video_frames(frames, num_views=9, num_v=None, num_u=None,
                         method='stereo', temporal_smoothing='kalman', **kwargs):
    """
    Process a video sequence of light field frames.
    
    Parameters:
        frames: List of light field images or video frames
        num_views: Number of views per dimension
        method: Depth estimation method ('dfd', 'stereo', 'epi', 'learning', 'all')
        temporal_smoothing: Temporal smoothing method ('kalman', 'ema', 'bilateral', None)
        **kwargs: Additional arguments for depth estimation
        
    Returns:
        depth_sequence: List of depth maps
        confidence_sequence: List of confidence maps
    """
    from .subaperture import extract_subapertures
    from . import depth_dfd, depth_stereo, depth_epi, depth_learning
    
    num_frames = len(frames)
    depth_sequence = []
    confidence_sequence = []
    
    smoother = None
    if temporal_smoothing == 'kalman':
        smoother = TemporalDepthSmoother(**kwargs)
    elif temporal_smoothing == 'stf':
        stf = SpatioTemporalFilter(**kwargs)
    
    for i, frame in enumerate(tqdm(frames, desc="Processing video")):
        subap = extract_subapertures(frame, num_u or num_views, num_v or num_views)
        
        if method == 'dfd':
            depth, conf = depth_dfd.estimate_depth_dfd_fast(subap)
        elif method == 'stereo':
            depth, conf, _ = depth_stereo.estimate_depth_stereo(subap)
        elif method == 'epi':
            depth, conf = depth_epi.estimate_depth_epi_fast(subap)
        elif method == 'learning':
            depth, conf = depth_learning.estimate_depth_learning(subap)
        else:
            depth_d, conf_d = depth_dfd.estimate_depth_dfd_fast(subap)
            depth_s, conf_s, _ = depth_stereo.estimate_depth_stereo(subap)
            depth_e, conf_e = depth_epi.estimate_depth_epi_fast(subap)
            
            conf_total = conf_d + conf_s + conf_e + 1e-8
            depth = (depth_d * conf_d + depth_s * conf_s + depth_e * conf_e) / conf_total
            conf = np.max([conf_d, conf_s, conf_e], axis=0)
        
        if temporal_smoothing == 'kalman' and smoother is not None:
            if frame.ndim >= 3:
                gray_frame = np.mean(frame, axis=-1) if frame.shape[-1] in [3, 4] else frame
            else:
                gray_frame = frame
            
            center_view = subap.get_center_view()
            if center_view.ndim == 3:
                center_view = np.mean(center_view, axis=-1)
            
            depth, outliers = smoother.process_frame(depth, center_view, conf)
        
        elif temporal_smoothing == 'stf' and stf is not None:
            center_view = subap.get_center_view()
            if center_view.ndim == 3:
                center_view = np.mean(center_view, axis=-1)
            depth = stf.apply(depth, conf, center_view)
        
        depth_sequence.append(depth)
        confidence_sequence.append(conf)
    
    if temporal_smoothing == 'ema':
        alpha = kwargs.get('alpha', 0.3)
        depth_sequence = list(smooth_temporal_ema(np.array(depth_sequence), alpha))
    elif temporal_smoothing == 'bilateral':
        depth_sequence = list(smooth_temporal_bilateral(np.array(depth_sequence)))
    elif temporal_smoothing == 'kalman_batch':
        depth_sequence = list(smooth_temporal_kalman(np.array(depth_sequence), 
                                                      np.array(confidence_sequence)))
    
    return depth_sequence, confidence_sequence
