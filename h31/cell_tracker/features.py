import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import logging

from .utils import extract_mask_properties

logger = logging.getLogger(__name__)


class FeatureExtractor:
    def __init__(self,
                 use_parallel: bool = True,
                 num_workers: int = 4,
                 perform_photobleach_correction: bool = True,
                 bleaching_correction_method: str = 'exponential',
                 background_correction: bool = True,
                 use_global_bleach: bool = True,
                 bleach_fit_window: Optional[int] = None):
        self.use_parallel = use_parallel
        self.num_workers = num_workers
        self.perform_photobleach_correction = perform_photobleach_correction
        self.bleaching_correction_method = bleaching_correction_method
        self.background_correction = background_correction
        self.use_global_bleach = use_global_bleach
        self.bleach_fit_window = bleach_fit_window
        
        self.fluorescence_data: Dict[int, Dict[int, float]] = defaultdict(dict)
        self.corrected_fluorescence_data: Dict[int, Dict[int, float]] = defaultdict(dict)
        self.features_data: Dict[int, Dict[int, dict]] = defaultdict(dict)
        self.bleach_correction_params: Optional[dict] = None
        self.background_levels: Optional[np.ndarray] = None
    
    def extract_fluorescence(self,
                              image_stack: np.ndarray,
                              masks: np.ndarray,
                              channel: int = 0) -> Dict[int, Dict[int, float]]:
        logger.info("Extracting fluorescence intensities")
        
        if image_stack.ndim == 4:
            images = image_stack[:, channel, :, :]
        elif image_stack.ndim == 3:
            images = image_stack
        else:
            raise ValueError(f"Unsupported image stack shape: {image_stack.shape}")
        
        n_frames = images.shape[0]
        
        for frame in range(n_frames):
            if frame % 10 == 0:
                logger.info(f"Processing frame {frame}/{n_frames}")
            
            image = images[frame]
            mask = masks[frame]
            
            labels = np.unique(mask)
            labels = labels[labels != 0]
            
            for label in labels:
                cell_pixels = image[mask == label]
                
                if len(cell_pixels) > 0:
                    mean_intensity = np.mean(cell_pixels)
                    median_intensity = np.median(cell_pixels)
                    max_intensity = np.max(cell_pixels)
                    min_intensity = np.min(cell_pixels)
                    std_intensity = np.std(cell_pixels)
                    sum_intensity = np.sum(cell_pixels)
                    
                    self.fluorescence_data[frame][label] = {
                        'mean': mean_intensity,
                        'median': median_intensity,
                        'max': max_intensity,
                        'min': min_intensity,
                        'std': std_intensity,
                        'sum': sum_intensity,
                        'n_pixels': len(cell_pixels),
                    }
        
        logger.info("Fluorescence extraction complete")
        
        if self.perform_photobleach_correction:
            self.correct_photobleaching(image_stack, masks, channel)
        
        return self.fluorescence_data
    
    def estimate_background(self, 
                             image_stack: np.ndarray,
                             masks: np.ndarray,
                             channel: int = 0) -> np.ndarray:
        logger.info("Estimating background levels...")
        
        if image_stack.ndim == 4:
            images = image_stack[:, channel, :, :]
        elif image_stack.ndim == 3:
            images = image_stack
        else:
            raise ValueError(f"Unsupported image stack shape: {image_stack.shape}")
        
        n_frames = images.shape[0]
        background_levels = np.zeros(n_frames)
        
        for frame in range(n_frames):
            image = images[frame]
            mask = masks[frame]
            
            background_pixels = image[mask == 0]
            
            if len(background_pixels) > 0:
                background_levels[frame] = np.percentile(background_pixels, 10)
            else:
                background_levels[frame] = np.percentile(image, 10)
        
        self.background_levels = background_levels
        logger.info(f"Background estimation complete. Mean background: {np.mean(background_levels):.2f}")
        return background_levels
    
    def fit_exponential_decay(self, 
                                time_points: np.ndarray,
                                intensity_values: np.ndarray) -> Tuple[float, float, float]:
        logger.info("Fitting exponential decay model...")
        
        valid_mask = np.isfinite(intensity_values) & (intensity_values > 0)
        
        if not np.any(valid_mask):
            return 1.0, 0.0, 0.0
        
        t = time_points[valid_mask]
        y = intensity_values[valid_mask]
        
        if len(t) < 3:
            return 1.0, 0.0, 0.0
        
        try:
            from scipy.optimize import curve_fit
            
            def exponential_decay(t, I0, tau, offset):
                return I0 * np.exp(-t / max(tau, 1e-6)) + offset
            
            I0_init = y[0] if len(y) > 0 else 1.0
            tau_init = len(t) / 2.0
            offset_init = np.min(y) if len(y) > 0 else 0.0
            
            bounds = (
                [0, 1e-6, -np.inf],
                [np.inf, np.inf, np.inf]
            )
            
            params, _ = curve_fit(
                exponential_decay,
                t, y,
                p0=[I0_init, tau_init, offset_init],
                bounds=bounds,
                maxfev=10000
            )
            
            I0, tau, offset = params
            logger.info(f"Exponential decay fit: I0={I0:.2f}, tau={tau:.2f}, offset={offset:.2f}")
            
            return I0, tau, offset
            
        except Exception as e:
            logger.warning(f"Exponential fit failed, using linear approximation: {e}")
            
            slope, intercept = np.polyfit(t, np.log(y + 1e-8), 1)
            I0 = np.exp(intercept)
            tau = -1.0 / max(slope, -1e-6) if slope < 0 else len(t)
            offset = 0.0
            
            return I0, tau, offset
    
    def compute_global_bleach_curve(self, 
                                     time_points: np.ndarray,
                                     masks: np.ndarray) -> Tuple[np.ndarray, dict]:
        logger.info("Computing global photobleaching curve...")
        
        all_means = []
        all_medians = []
        
        for frame in range(len(time_points)):
            frame_fluo = self.fluorescence_data.get(frame, {})
            
            if len(frame_fluo) > 0:
                means = [fluo['mean'] for fluo in frame_fluo.values()]
                all_means.append(np.mean(means))
                all_medians.append(np.median(means))
            else:
                all_means.append(np.nan)
                all_medians.append(np.nan)
        
        all_means = np.array(all_means)
        all_medians = np.array(all_medians)
        
        if self.background_correction and self.background_levels is not None:
            bg = self.background_levels[:len(time_points)]
            all_means = all_means - bg
            all_medians = all_medians - bg
        
        valid_mask = np.isfinite(all_means)
        
        if not np.any(valid_mask):
            return np.ones_like(time_points), {'I0': 1.0, 'tau': np.inf, 'offset': 0.0}
        
        I0, tau, offset = self.fit_exponential_decay(
            time_points[valid_mask],
            all_medians[valid_mask]
        )
        
        def decay_curve(t):
            return I0 * np.exp(-t / max(tau, 1e-6)) + offset
        
        correction_factors = np.ones_like(time_points, dtype=float)
        
        for i, t in enumerate(time_points):
            expected = decay_curve(t)
            if expected > 0:
                correction_factors[i] = I0 / expected
            else:
                correction_factors[i] = 1.0
        
        params = {
            'I0': I0,
            'tau': tau,
            'offset': offset,
            'half_life': tau * np.log(2) if tau > 0 and np.isfinite(tau) else np.inf,
            'decay_function': 'exponential',
        }
        
        logger.info(f"Global bleach correction computed. Half-life: {params['half_life']:.2f} frames")
        
        return correction_factors, params
    
    def correct_photobleaching(self,
                                 image_stack: np.ndarray,
                                 masks: np.ndarray,
                                 channel: int = 0) -> Dict[int, Dict[int, dict]]:
        logger.info("Performing photobleaching correction...")
        
        n_frames = masks.shape[0]
        time_points = np.arange(n_frames)
        
        if self.background_correction:
            self.estimate_background(image_stack, masks, channel)
        
        if self.bleach_fit_window is not None:
            fit_window = min(self.bleach_fit_window, n_frames)
            fit_time_points = time_points[:fit_window]
        else:
            fit_time_points = time_points
        
        if self.use_global_bleach:
            correction_factors, params = self.compute_global_bleach_curve(fit_time_points, masks)
            self.bleach_correction_params = params
            
            if len(correction_factors) < n_frames:
                full_correction = np.ones(n_frames)
                full_correction[:len(correction_factors)] = correction_factors
                if len(correction_factors) > 1:
                    last_factor = correction_factors[-1]
                    for i in range(len(correction_factors), n_frames):
                        full_correction[i] = last_factor
                correction_factors = full_correction
            
            for frame in range(n_frames):
                factor = correction_factors[frame]
                bg = self.background_levels[frame] if self.background_levels is not None else 0
                
                for label, fluo in self.fluorescence_data.get(frame, {}).items():
                    corrected_fluo = {}
                    
                    for key in ['mean', 'median', 'max', 'min', 'sum']:
                        val = fluo[key]
                        
                        if self.background_correction:
                            if key == 'sum':
                                corrected = (val - bg * fluo['n_pixels']) * factor
                            else:
                                corrected = (val - bg) * factor
                        else:
                            corrected = val * factor
                        
                        corrected_fluo[key] = corrected
                    
                    corrected_fluo['std'] = fluo['std'] * factor
                    corrected_fluo['n_pixels'] = fluo['n_pixels']
                    corrected_fluo['correction_factor'] = factor
                    corrected_fluo['background'] = bg
                    
                    self.corrected_fluorescence_data[frame][label] = corrected_fluo
            
            logger.info("Global photobleaching correction complete")
            
        else:
            for track_id in self._get_track_ids(masks):
                track_data = self._get_track_fluorescence(track_id, masks)
                
                if len(track_data) < 3:
                    continue
                
                track_frames = np.array([d['frame'] for d in track_data])
                track_means = np.array([d['mean'] for d in track_data])
                
                if self.background_correction and self.background_levels is not None:
                    bg = self.background_levels[track_frames]
                    track_means = track_means - bg
                
                I0, tau, offset = self.fit_exponential_decay(track_frames, track_means)
                
                for d in track_data:
                    frame = d['frame']
                    label = d['label']
                    
                    expected = I0 * np.exp(-frame / max(tau, 1e-6)) + offset
                    factor = I0 / max(expected, 1e-8)
                    
                    bg = self.background_levels[frame] if self.background_levels is not None else 0
                    
                    fluo = self.fluorescence_data[frame][label]
                    corrected_fluo = {}
                    
                    for key in ['mean', 'median', 'max', 'min', 'sum']:
                        val = fluo[key]
                        if self.background_correction:
                            if key == 'sum':
                                corrected = (val - bg * fluo['n_pixels']) * factor
                            else:
                                corrected = (val - bg) * factor
                        else:
                            corrected = val * factor
                        
                        corrected_fluo[key] = corrected
                    
                    corrected_fluo['std'] = fluo['std'] * factor
                    corrected_fluo['n_pixels'] = fluo['n_pixels']
                    corrected_fluo['correction_factor'] = factor
                    corrected_fluo['background'] = bg
                    
                    self.corrected_fluorescence_data[frame][label] = corrected_fluo
            
            logger.info("Track-level photobleaching correction complete")
        
        return self.corrected_fluorescence_data
    
    def _get_track_ids(self, masks: np.ndarray) -> List[int]:
        all_labels = set()
        for frame in range(masks.shape[0]):
            labels = np.unique(masks[frame])
            all_labels.update(labels[labels != 0])
        return list(all_labels)
    
    def _get_track_fluorescence(self, track_id: int, masks: np.ndarray) -> List[dict]:
        track_data = []
        for frame in range(masks.shape[0]):
            if track_id in self.fluorescence_data.get(frame, {}):
                track_data.append({
                    'frame': frame,
                    'label': track_id,
                    **self.fluorescence_data[frame][track_id]
                })
        return track_data
    
    def extract_all_features(self,
                              image_stack: np.ndarray,
                              masks: np.ndarray,
                              channel: int = 0) -> Dict[int, Dict[int, dict]]:
        logger.info("Extracting all features")
        
        if image_stack.ndim == 4:
            images = image_stack[:, channel, :, :]
        elif image_stack.ndim == 3:
            images = image_stack
        else:
            raise ValueError(f"Unsupported image stack shape: {image_stack.shape}")
        
        n_frames = images.shape[0]
        
        for frame in range(n_frames):
            if frame % 10 == 0:
                logger.info(f"Processing frame {frame}/{n_frames}")
            
            image = images[frame]
            mask = masks[frame]
            
            morph_props = extract_mask_properties(mask)
            
            labels = np.unique(mask)
            labels = labels[labels != 0]
            
            for label in labels:
                cell_mask = mask == label
                cell_pixels = image[cell_mask]
                
                if len(cell_pixels) == 0:
                    continue
                
                features = {}
                
                if label in morph_props:
                    mp = morph_props[label]
                    features['morphology'] = {
                        'area': mp.get('area', 0),
                        'centroid': mp.get('centroid', (0, 0)),
                        'eccentricity': mp.get('eccentricity', 0),
                        'solidity': mp.get('solidity', 0),
                        'extent': mp.get('extent', 0),
                        'orientation': mp.get('orientation', 0),
                        'major_axis_length': mp.get('major_axis_length', 0),
                        'minor_axis_length': mp.get('minor_axis_length', 0),
                        'perimeter': mp.get('perimeter', 0),
                        'aspect_ratio': mp.get('major_axis_length', 1) / max(mp.get('minor_axis_length', 1), 1),
                        'circularity': (4 * np.pi * mp.get('area', 0)) / max(mp.get('perimeter', 1) ** 2, 1),
                        'compactness': mp.get('perimeter', 0) / np.sqrt(max(mp.get('area', 1), 1)),
                    }
                
                features['fluorescence'] = {
                    'mean': np.mean(cell_pixels),
                    'median': np.median(cell_pixels),
                    'max': np.max(cell_pixels),
                    'min': np.min(cell_pixels),
                    'std': np.std(cell_pixels),
                    'sum': np.sum(cell_pixels),
                    'n_pixels': len(cell_pixels),
                    'q25': np.percentile(cell_pixels, 25),
                    'q75': np.percentile(cell_pixels, 75),
                    'skewness': self._skewness(cell_pixels),
                    'kurtosis': self._kurtosis(cell_pixels),
                }
                
                features['texture'] = self._extract_texture_features(image, cell_mask)
                
                self.features_data[frame][label] = features
        
        logger.info("Feature extraction complete")
        return self.features_data
    
    def _skewness(self, data: np.ndarray) -> float:
        if len(data) == 0 or np.std(data) == 0:
            return 0.0
        
        mean = np.mean(data)
        std = np.std(data)
        return np.mean(((data - mean) / std) ** 3)
    
    def _kurtosis(self, data: np.ndarray) -> float:
        if len(data) == 0 or np.std(data) == 0:
            return 0.0
        
        mean = np.mean(data)
        std = np.std(data)
        return np.mean(((data - mean) / std) ** 4) - 3
    
    def _extract_texture_features(self, 
                                   image: np.ndarray, 
                                   cell_mask: np.ndarray) -> dict:
        from skimage.feature import graycomatrix, graycoprops
        
        cell_bbox = self._get_mask_bbox(cell_mask)
        if cell_bbox is None:
            return {
                'contrast': 0, 'dissimilarity': 0, 'homogeneity': 0,
                'energy': 0, 'correlation': 0, 'ASM': 0
            }
        
        y_min, y_max, x_min, x_max = cell_bbox
        cell_patch = image[y_min:y_max+1, x_min:x_max+1]
        cell_patch_mask = cell_mask[y_min:y_max+1, x_min:x_max+1]
        
        if cell_patch.size == 0 or cell_patch_mask.sum() == 0:
            return {
                'contrast': 0, 'dissimilarity': 0, 'homogeneity': 0,
                'energy': 0, 'correlation': 0, 'ASM': 0
            }
        
        cell_patch_uint8 = self._normalize_to_uint8(cell_patch)
        
        try:
            glcm = graycomatrix(
                cell_patch_uint8,
                distances=[1],
                angles=[0, np.pi/4, np.pi/2, 3*np.pi/4],
                levels=256,
                symmetric=True,
                normed=True
            )
            
            texture = {
                'contrast': float(np.mean(graycoprops(glcm, 'contrast'))),
                'dissimilarity': float(np.mean(graycoprops(glcm, 'dissimilarity'))),
                'homogeneity': float(np.mean(graycoprops(glcm, 'homogeneity'))),
                'energy': float(np.mean(graycoprops(glcm, 'energy'))),
                'correlation': float(np.mean(graycoprops(glcm, 'correlation'))),
                'ASM': float(np.mean(graycoprops(glcm, 'ASM'))),
            }
        except Exception as e:
            logger.debug(f"GLCM calculation failed: {e}")
            texture = {
                'contrast': 0, 'dissimilarity': 0, 'homogeneity': 0,
                'energy': 0, 'correlation': 0, 'ASM': 0
            }
        
        return texture
    
    def _get_mask_bbox(self, mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        
        if not np.any(rows) or not np.any(cols):
            return None
        
        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]
        
        return y_min, y_max, x_min, x_max
    
    def _normalize_to_uint8(self, image: np.ndarray) -> np.ndarray:
        if image.dtype == np.uint8:
            return image
        
        img_normalized = (image - image.min()) / (image.max() - image.min() + 1e-8)
        return (img_normalized * 255).astype(np.uint8)
    
    def get_fluorescence_for_tracker(self, tracker: object, use_corrected: bool = None) -> Dict[int, Dict[int, float]]:
        if use_corrected is None:
            use_corrected = self.perform_photobleach_correction and len(self.corrected_fluorescence_data) > 0
        
        track_fluorescence = defaultdict(dict)
        
        fluo_source = self.corrected_fluorescence_data if use_corrected else self.fluorescence_data
        
        for track_id, track in tracker.tracks.items():
            for frame, label in zip(track.frames, track.labels):
                if frame in fluo_source and label in fluo_source[frame]:
                    mean_intensity = fluo_source[frame][label]['mean']
                    track_fluorescence[track_id][frame] = mean_intensity
                    
                    idx = track.frames.index(frame)
                    if idx < len(track.fluorescence):
                        track.fluorescence[idx] = mean_intensity
        
        return track_fluorescence
    
    def get_fluorescence_timeseries(self, tracker: object, use_corrected: bool = None) -> pd.DataFrame:
        if use_corrected is None:
            use_corrected = self.perform_photobleach_correction and len(self.corrected_fluorescence_data) > 0
        
        data = []
        
        fluo_source = self.corrected_fluorescence_data if use_corrected else self.fluorescence_data
        
        for track_id, track in tracker.tracks.items():
            for i, frame in enumerate(track.frames):
                label = track.labels[i]
                
                fluo_dict = None
                if frame in fluo_source and label in fluo_source[frame]:
                    fluo_dict = fluo_source[frame][label]
                
                raw_fluo_dict = None
                if frame in self.fluorescence_data and label in self.fluorescence_data[frame]:
                    raw_fluo_dict = self.fluorescence_data[frame][label]
                
                features_dict = None
                if frame in self.features_data and label in self.features_data[frame]:
                    features_dict = self.features_data[frame][label]
                
                row = {
                    'track_id': track_id,
                    'frame': frame,
                    'label': label,
                    'y': track.centroids[i][0],
                    'x': track.centroids[i][1],
                    'area': track.areas[i],
                }
                
                if fluo_dict is not None:
                    row.update({
                        'fluo_mean': fluo_dict['mean'],
                        'fluo_median': fluo_dict['median'],
                        'fluo_max': fluo_dict['max'],
                        'fluo_min': fluo_dict['min'],
                        'fluo_std': fluo_dict['std'],
                        'fluo_sum': fluo_dict['sum'],
                        'n_pixels': fluo_dict['n_pixels'],
                    })
                    
                    if 'correction_factor' in fluo_dict:
                        row['correction_factor'] = fluo_dict['correction_factor']
                        row['background'] = fluo_dict['background']
                    
                    if raw_fluo_dict is not None and use_corrected:
                        row.update({
                            'raw_fluo_mean': raw_fluo_dict['mean'],
                            'raw_fluo_median': raw_fluo_dict['median'],
                        })
                
                if features_dict is not None and 'morphology' in features_dict:
                    morph = features_dict['morphology']
                    row.update({
                        'eccentricity': morph['eccentricity'],
                        'solidity': morph['solidity'],
                        'aspect_ratio': morph['aspect_ratio'],
                        'circularity': morph['circularity'],
                        'perimeter': morph['perimeter'],
                    })
                
                if features_dict is not None and 'texture' in features_dict:
                    texture = features_dict['texture']
                    row.update({
                        'contrast': texture['contrast'],
                        'homogeneity': texture['homogeneity'],
                        'correlation': texture['correlation'],
                    })
                
                data.append(row)
        
        return pd.DataFrame(data)
    
    def get_summary_statistics(self, tracker: object) -> pd.DataFrame:
        df = self.get_fluorescence_timeseries(tracker)
        
        if df.empty:
            return pd.DataFrame()
        
        summary = df.groupby('track_id').agg({
            'frame': ['min', 'max', 'count'],
            'fluo_mean': ['mean', 'std', 'min', 'max', 'median'],
            'area': ['mean', 'std', 'min', 'max'],
            'circularity': ['mean', 'std'],
            'eccentricity': ['mean', 'std'],
        })
        
        summary.columns = ['_'.join(col).strip() for col in summary.columns.values]
        summary = summary.reset_index()
        
        summary['track_length'] = summary['frame_max'] - summary['frame_min'] + 1
        
        return summary
