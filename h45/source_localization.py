import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
from config import LocalizationConfig, KEY_POSITIONS
from feature_extraction import TDOAExtractor, KeyFeatures


@dataclass
class SourceLocation:
    x: float
    y: float
    z: float
    confidence: float
    estimated_key: Optional[str]
    distance_errors: np.ndarray


class SourceLocalizer:
    def __init__(self, config: LocalizationConfig, sample_rate: int, num_channels: int):
        self.config = config
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.mic_positions = config.mic_positions
        self.sound_speed = config.sound_speed

    def compute_tdoa_matrix(self, multi_channel_audio: np.ndarray) -> np.ndarray:
        if len(multi_channel_audio.shape) == 1:
            return np.zeros((self.num_channels, self.num_channels))
        
        num_channels = multi_channel_audio.shape[0]
        tdoa_matrix = np.zeros((num_channels, num_channels))
        
        for i in range(num_channels):
            for j in range(i + 1, num_channels):
                tdoa = self._compute_pair_tdoa(
                    multi_channel_audio[i], 
                    multi_channel_audio[j]
                )
                tdoa_matrix[i, j] = tdoa
                tdoa_matrix[j, i] = -tdoa
        
        return tdoa_matrix

    def _compute_pair_tdoa(self, sig1: np.ndarray, sig2: np.ndarray) -> float:
        max_len = max(len(sig1), len(sig2))
        pad_len = 1
        while pad_len < 2 * max_len - 1:
            pad_len *= 2
        
        sig1_pad = np.zeros(pad_len)
        sig2_pad = np.zeros(pad_len)
        sig1_pad[:len(sig1)] = sig1
        sig2_pad[:len(sig2)] = sig2
        
        X1 = np.fft.fft(sig1_pad)
        X2 = np.fft.fft(sig2_pad)
        
        X = X1 * np.conj(X2)
        denom = np.abs(X) + 1e-10
        X = X / denom
        
        correlation = np.fft.ifft(X)
        correlation = np.real(correlation)
        correlation = np.fft.fftshift(correlation)
        
        center = len(correlation) // 2
        max_shift = int(self.sample_rate * 0.01)
        start = center - max_shift
        end = center + max_shift
        correlation_roi = correlation[start:end]
        
        peak_idx = np.argmax(np.abs(correlation_roi))
        delay_samples = peak_idx - max_shift
        delay_seconds = delay_samples / self.sample_rate
        
        return delay_seconds

    def taylor_series_localization(self, tdoa_matrix: np.ndarray, 
                                   initial_guess: Optional[np.ndarray] = None) -> SourceLocation:
        num_mics = self.num_channels
        
        if initial_guess is None:
            center = np.mean(self.mic_positions, axis=0)
            initial_guess = center + np.array([0.2, 0.3, 0.0])
        
        source_pos = initial_guess.copy()
        max_iterations = 50
        tolerance = 1e-6
        
        reference_idx = 0
        
        for iteration in range(max_iterations):
            distances = np.linalg.norm(self.mic_positions - source_pos, axis=1)
            
            predicted_tdoa = np.zeros(num_mics)
            for i in range(num_mics):
                predicted_tdoa[i] = (distances[i] - distances[reference_idx]) / self.sound_speed
            
            measured_tdoa = tdoa_matrix[reference_idx, :]
            
            residual = measured_tdoa - predicted_tdoa
            
            jacobian = np.zeros((num_mics, 3))
            for i in range(num_mics):
                if i == reference_idx:
                    continue
                direction = (source_pos - self.mic_positions[i]) / (distances[i] + 1e-10)
                direction_ref = (source_pos - self.mic_positions[reference_idx]) / (distances[reference_idx] + 1e-10)
                jacobian[i] = (direction - direction_ref) / self.sound_speed
            
            valid_indices = [i for i in range(num_mics) if i != reference_idx]
            jacobian = jacobian[valid_indices]
            residual = residual[valid_indices]
            
            try:
                jtj = jacobian.T @ jacobian
                jtr = jacobian.T @ residual
                delta = np.linalg.solve(jtj + 1e-6 * np.eye(3), jtr)
            except np.linalg.LinAlgError:
                delta = np.linalg.lstsq(jacobian, residual, rcond=None)[0]
            
            source_pos += delta
            
            if np.linalg.norm(delta) < tolerance:
                break
        
        final_distances = np.linalg.norm(self.mic_positions - source_pos, axis=1)
        final_predicted_tdoa = np.zeros(num_mics)
        for i in range(num_mics):
            final_predicted_tdoa[i] = (final_distances[i] - final_distances[reference_idx]) / self.sound_speed
        
        final_residual = measured_tdoa - final_predicted_tdoa
        rmse = np.sqrt(np.mean(final_residual ** 2))
        confidence = np.exp(-rmse / 0.001)
        
        estimated_key = self._find_closest_key(source_pos)
        
        return SourceLocation(
            x=source_pos[0],
            y=source_pos[1],
            z=source_pos[2],
            confidence=confidence,
            estimated_key=estimated_key,
            distance_errors=final_residual
        )

    def grid_search_localization(self, tdoa_matrix: np.ndarray) -> SourceLocation:
        kb_pos = np.array(self.config.keyboard_position)
        kb_size = self.config.keyboard_size
        
        x_min = kb_pos[0] - kb_size[0] / 2
        x_max = kb_pos[0] + kb_size[0] / 2
        y_min = kb_pos[1] - kb_size[1] / 2
        y_max = kb_pos[1] + kb_size[1] / 2
        z_pos = kb_pos[2]
        
        grid_step = 0.01
        x_grid = np.arange(x_min, x_max, grid_step)
        y_grid = np.arange(y_min, y_max, grid_step)
        
        min_error = float('inf')
        best_pos = None
        reference_idx = 0
        
        for x in x_grid:
            for y in y_grid:
                source_pos = np.array([x, y, z_pos])
                distances = np.linalg.norm(self.mic_positions - source_pos, axis=1)
                
                predicted_tdoa = np.zeros(self.num_channels)
                for i in range(self.num_channels):
                    predicted_tdoa[i] = (distances[i] - distances[reference_idx]) / self.sound_speed
                
                measured_tdoa = tdoa_matrix[reference_idx, :]
                error = np.mean((measured_tdoa - predicted_tdoa) ** 2)
                
                if error < min_error:
                    min_error = error
                    best_pos = source_pos.copy()
        
        if best_pos is None:
            best_pos = np.array(kb_pos)
        
        confidence = np.exp(-np.sqrt(min_error) / 0.001)
        estimated_key = self._find_closest_key(best_pos)
        
        final_distances = np.linalg.norm(self.mic_positions - best_pos, axis=1)
        final_predicted_tdoa = np.zeros(self.num_channels)
        for i in range(self.num_channels):
            final_predicted_tdoa[i] = (final_distances[i] - final_distances[reference_idx]) / self.sound_speed
        measured_tdoa = tdoa_matrix[reference_idx, :]
        final_residual = measured_tdoa - final_predicted_tdoa
        
        return SourceLocation(
            x=best_pos[0],
            y=best_pos[1],
            z=best_pos[2],
            confidence=confidence,
            estimated_key=estimated_key,
            distance_errors=final_residual
        )

    def _find_closest_key(self, position: np.ndarray) -> Optional[str]:
        kb_pos = np.array(self.config.keyboard_position)
        kb_size = self.config.keyboard_size
        
        rel_x = position[0] - (kb_pos[0] - kb_size[0] / 2)
        rel_y = position[1] - (kb_pos[1] - kb_size[1] / 2)
        
        if rel_x < 0 or rel_x > kb_size[0] or rel_y < 0 or rel_y > kb_size[1]:
            return None
        
        min_distance = float('inf')
        closest_key = None
        
        for key, (key_x, key_y) in KEY_POSITIONS.items():
            distance = np.sqrt((rel_x - key_x) ** 2 + (rel_y - key_y) ** 2)
            if distance < min_distance:
                min_distance = distance
                closest_key = key
        
        if min_distance < 0.05:
            return closest_key
        return None

    def localize(self, multi_channel_audio: np.ndarray, 
                 method: str = 'taylor') -> SourceLocation:
        tdoa_matrix = self.compute_tdoa_matrix(multi_channel_audio)
        
        if method == 'taylor':
            return self.taylor_series_localization(tdoa_matrix)
        elif method == 'grid':
            return self.grid_search_localization(tdoa_matrix)
        else:
            raise ValueError(f"Unknown localization method: {method}")

    def get_key_region_prior(self, location: SourceLocation) -> np.ndarray:
        from config import KEYBOARD_KEYS
        
        kb_pos = np.array(self.config.keyboard_position)
        kb_size = self.config.keyboard_size
        
        rel_x = location.x - (kb_pos[0] - kb_size[0] / 2)
        rel_y = location.y - (kb_pos[1] - kb_size[1] / 2)
        
        prior = np.zeros(len(KEYBOARD_KEYS))
        
        for i, key in enumerate(KEYBOARD_KEYS):
            if key in KEY_POSITIONS:
                key_x, key_y = KEY_POSITIONS[key]
                distance = np.sqrt((rel_x - key_x) ** 2 + (rel_y - key_y) ** 2)
                sigma = 0.03
                prior[i] = np.exp(-distance ** 2 / (2 * sigma ** 2))
        
        if np.sum(prior) > 0:
            prior = prior / np.sum(prior)
        
        return prior

    def combine_predictions(self, classification_probs: np.ndarray, 
                            location: SourceLocation, 
                            alpha: float = 0.5) -> np.ndarray:
        prior = self.get_key_region_prior(location)
        
        combined = (1 - alpha) * classification_probs + alpha * prior
        combined = combined / (np.sum(combined) + 1e-10)
        
        return combined


def extract_tdoa_features_from_event(event_audio: np.ndarray, sample_rate: int,
                                     num_channels: int) -> np.ndarray:
    from config import FeatureExtractionConfig
    config = FeatureExtractionConfig()
    extractor = TDOAExtractor(config, sample_rate, num_channels)
    return extractor.extract_peak_tdoa(event_audio)
