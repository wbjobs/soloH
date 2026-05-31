import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
from config import CalibrationConfig, LocalizationConfig, KEY_POSITIONS, CHAR_TO_KEY
from event_detection import EventDetector, KeyEvent
from feature_extraction import FeatureExtractor
from source_localization import SourceLocalizer, SourceLocation


@dataclass
class CalibrationResult:
    mic_positions: np.ndarray
    key_positions_3d: dict
    reconstruction_error: float
    converged: bool
    iterations: int


class MicrophoneCalibrator:
    def __init__(self, config: CalibrationConfig, sample_rate: int, num_channels: int):
        self.config = config
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.sound_speed = 343.0

    def get_expected_key_positions(self, sequence: str) -> List[Tuple[str, np.ndarray]]:
        key_positions = []
        
        for char in sequence:
            key = CHAR_TO_KEY.get(char)
            if key is not None and key in KEY_POSITIONS:
                key_2d = np.array(KEY_POSITIONS[key])
                key_3d = np.array([key_2d[0], key_2d[1], 0.0])
                key_positions.append((key, key_3d))
        
        return key_positions

    def extract_tdoa_measurements(self, events: List[KeyEvent], 
                                   multi_channel_audio: np.ndarray) -> List[np.ndarray]:
        tdoa_measurements = []
        
        for event in events:
            start = event.start_sample
            end = event.end_sample
            event_audio = multi_channel_audio[:, start:end]
            
            tdoa_matrix = self._compute_tdoa_matrix(event_audio)
            tdoa_measurements.append(tdoa_matrix)
        
        return tdoa_measurements

    def _compute_tdoa_matrix(self, multi_channel_audio: np.ndarray) -> np.ndarray:
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
        max_shift = int(self.sample_rate * 0.02)
        start = center - max_shift
        end = center + max_shift
        correlation_roi = correlation[start:end]
        
        peak_idx = np.argmax(np.abs(correlation_roi))
        delay_samples = peak_idx - max_shift
        delay_seconds = delay_samples / self.sample_rate
        
        return delay_seconds

    def calibrate(self, multi_channel_audio: np.ndarray, 
                  calibration_sequence: Optional[str] = None,
                  initial_mic_positions: Optional[np.ndarray] = None) -> CalibrationResult:
        if calibration_sequence is None:
            calibration_sequence = self.config.calibration_sequence
        
        if initial_mic_positions is None:
            initial_mic_positions = np.array([
                [0.0, 0.0, 0.0],
                [0.1, 0.0, 0.0],
                [0.1, 0.1, 0.0],
                [0.0, 0.1, 0.0]
            ])
        
        expected_keys = self.get_expected_key_positions(calibration_sequence)
        
        from event_detection import EventDetectionConfig
        ed_config = EventDetectionConfig()
        detector = EventDetector(ed_config, self.sample_rate)
        events = detector.detect(multi_channel_audio)
        
        if len(events) < len(expected_keys):
            print(f"Warning: Detected {len(events)} events, expected {len(expected_keys)} keys")
        
        tdoa_measurements = self.extract_tdoa_measurements(
            events[:len(expected_keys)], multi_channel_audio
        )
        
        mic_positions, key_positions, error, converged, iterations = self._optimize_positions(
            tdoa_measurements, expected_keys, initial_mic_positions
        )
        
        key_positions_3d = {}
        for i, (key_name, _) in enumerate(expected_keys):
            if i < len(key_positions):
                key_positions_3d[key_name] = key_positions[i]
        
        return CalibrationResult(
            mic_positions=mic_positions,
            key_positions_3d=key_positions_3d,
            reconstruction_error=error,
            converged=converged,
            iterations=iterations
        )

    def _optimize_positions(self, tdoa_measurements: List[np.ndarray],
                            expected_keys: List[Tuple[str, np.ndarray]],
                            initial_mic_positions: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float, bool, int]:
        num_mics = self.num_channels
        num_events = min(len(tdoa_measurements), len(expected_keys))
        
        mic_positions = initial_mic_positions.copy().astype(np.float64)
        key_positions = np.array([pos for _, pos in expected_keys[:num_events]]).astype(np.float64)
        
        learning_rate = 0.001
        max_iterations = self.config.num_calibration_iterations
        tolerance = 1e-8
        
        reference_idx = 0
        prev_error = float('inf')
        converged = False
        
        for iteration in range(max_iterations):
            total_error = 0.0
            grad_mic = np.zeros_like(mic_positions)
            grad_key = np.zeros_like(key_positions)
            
            for event_idx in range(num_events):
                tdoa_matrix = tdoa_measurements[event_idx]
                key_pos = key_positions[event_idx]
                
                distances = np.linalg.norm(mic_positions - key_pos, axis=1)
                
                for mic_i in range(num_mics):
                    for mic_j in range(mic_i + 1, num_mics):
                        predicted_tdoa = (distances[mic_i] - distances[mic_j]) / self.sound_speed
                        measured_tdoa = tdoa_matrix[mic_i, mic_j]
                        
                        error = predicted_tdoa - measured_tdoa
                        total_error += error ** 2
                        
                        direction_i = (key_pos - mic_positions[mic_i]) / (distances[mic_i] + 1e-10)
                        direction_j = (key_pos - mic_positions[mic_j]) / (distances[mic_j] + 1e-10)
                        
                        grad_mic[mic_i] += 2 * error * (-direction_i) / self.sound_speed
                        grad_mic[mic_j] += 2 * error * (direction_j) / self.sound_speed
                        grad_key[event_idx] += 2 * error * (direction_i - direction_j) / self.sound_speed
            
            rmse = np.sqrt(total_error / (num_events * num_mics * (num_mics - 1) / 2))
            
            if abs(prev_error - rmse) < tolerance:
                converged = True
                break
            
            prev_error = rmse
            
            mic_positions -= learning_rate * grad_mic
            key_positions -= learning_rate * grad_key
            
            mic_positions[reference_idx] = np.zeros(3)
            if num_mics > 1:
                mic_positions[1, 1] = 0
                mic_positions[1, 2] = 0
            
            if iteration % 10 == 0:
                print(f"Iteration {iteration}, RMSE: {rmse:.6f} seconds")
        
        return mic_positions, key_positions, prev_error, converged, iteration + 1

    def mds_calibration(self, tdoa_measurements: List[np.ndarray]) -> np.ndarray:
        num_mics = self.num_channels
        num_events = len(tdoa_measurements)
        
        distance_matrix = np.zeros((num_mics + num_events, num_mics + num_events))
        
        for event_idx, tdoa_matrix in enumerate(tdoa_measurements):
            event_distances = np.abs(tdoa_matrix[0, :]) * self.sound_speed
            for mic_idx in range(num_mics):
                d = event_distances[mic_idx]
                distance_matrix[mic_idx, num_mics + event_idx] = d
                distance_matrix[num_mics + event_idx, mic_idx] = d
        
        for i in range(num_mics):
            for j in range(i + 1, num_mics):
                d = 0.1
                distance_matrix[i, j] = d
                distance_matrix[j, i] = d
        
        J = np.eye(num_mics + num_events) - 1.0 / (num_mics + num_events) * np.ones((num_mics + num_events, num_mics + num_events))
        
        D_squared = distance_matrix ** 2
        B = -0.5 * J @ D_squared @ J
        
        eigenvalues, eigenvectors = np.linalg.eigh(B)
        
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        positive_eigenvalues = eigenvalues[eigenvalues > 1e-6]
        num_dimensions = min(3, len(positive_eigenvalues))
        
        V = eigenvectors[:, :num_dimensions]
        L = np.diag(np.sqrt(positive_eigenvalues[:num_dimensions]))
        
        positions = V @ L
        
        mic_positions = positions[:num_mics]
        
        return mic_positions


class KeyLocalizationCalibrator:
    def __init__(self, sample_rate: int, num_channels: int, 
                 mic_positions: Optional[np.ndarray] = None):
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.mic_positions = mic_positions
        self.sound_speed = 343.0
        self.calibrated_key_positions = {}

    def calibrate_key_locations(self, multi_channel_audio: np.ndarray,
                                known_sequence: str,
                                events: List[KeyEvent]) -> dict:
        from source_localization import SourceLocalizer, LocalizationConfig
        
        if self.mic_positions is None:
            loc_config = LocalizationConfig()
            self.mic_positions = loc_config.mic_positions
        
        loc_config = LocalizationConfig(mic_positions=self.mic_positions)
        localizer = SourceLocalizer(loc_config, self.sample_rate, self.num_channels)
        
        expected_keys = [CHAR_TO_KEY.get(c) for c in known_sequence if c in CHAR_TO_KEY]
        
        key_locations = {}
        
        for i, event in enumerate(events):
            if i >= len(expected_keys):
                break
            
            key_name = expected_keys[i]
            if key_name is None:
                continue
            
            start = event.start_sample
            end = event.end_sample
            event_audio = multi_channel_audio[:, start:end]
            
            location = localizer.localize(event_audio, method='taylor')
            key_locations[key_name] = np.array([location.x, location.y, location.z])
        
        self.calibrated_key_positions = key_locations
        return key_locations

    def refine_classifier_with_location(self, classification_probs: np.ndarray,
                                         event_audio: np.ndarray) -> np.ndarray:
        from source_localization import SourceLocalizer, LocalizationConfig
        
        loc_config = LocalizationConfig(mic_positions=self.mic_positions)
        localizer = SourceLocalizer(loc_config, self.sample_rate, self.num_channels)
        
        location = localizer.localize(event_audio, method='taylor')
        
        refined_probs = localizer.combine_predictions(classification_probs, location, alpha=0.3)
        
        return refined_probs
