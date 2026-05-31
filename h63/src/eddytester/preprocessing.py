import numpy as np
import pywt
from typing import Union, Tuple, Optional
from scipy import signal
from scipy.signal import savgol_filter
from .data_io import EddyCurrentData
from .config import Config


class WaveletDenoiser:
    def __init__(self,
                 wavelet: str = Config.WAVELET_TYPE,
                 level: int = Config.WAVELET_LEVEL,
                 mode: str = 'symmetric'):
        self.wavelet = wavelet
        self.level = level
        self.mode = mode

    def _universal_threshold(self, coeffs: np.ndarray) -> float:
        sigma = np.median(np.abs(coeffs)) / 0.6745
        n = len(coeffs)
        return sigma * np.sqrt(2 * np.log(n))

    def _soft_threshold(self, x: np.ndarray, threshold: float) -> np.ndarray:
        return np.sign(x) * np.maximum(np.abs(x) - threshold, 0)

    def denoise_signal(self, signal_data: np.ndarray) -> np.ndarray:
        if signal_data.ndim == 1:
            return self._denoise_1d(signal_data)
        elif signal_data.ndim == 2:
            denoised = np.zeros_like(signal_data, dtype=complex if np.iscomplexobj(signal_data) else float)
            for i in range(signal_data.shape[1]):
                col = signal_data[:, i]
                if np.iscomplexobj(col):
                    real_denoised = self._denoise_1d(np.real(col))
                    imag_denoised = self._denoise_1d(np.imag(col))
                    denoised[:, i] = real_denoised + 1j * imag_denoised
                else:
                    denoised[:, i] = self._denoise_1d(col)
            return denoised
        else:
            raise ValueError(f"Unsupported signal dimension: {signal_data.ndim}")

    def _denoise_1d(self, signal_1d: np.ndarray) -> np.ndarray:
        coeffs = pywt.wavedec(signal_1d, self.wavelet, level=self.level, mode=self.mode)
        
        threshold = self._universal_threshold(coeffs[-1])
        
        coeffs_thresh = list(coeffs)
        for i in range(1, len(coeffs_thresh)):
            coeffs_thresh[i] = self._soft_threshold(coeffs_thresh[i], threshold)
        
        reconstructed = pywt.waverec(coeffs_thresh, self.wavelet, mode=self.mode)
        
        return reconstructed[:len(signal_1d)]


class SavGolDenoiser:
    def __init__(self, window_length: int = 51, polyorder: int = 3):
        self.window_length = window_length
        self.polyorder = polyorder

    def denoise_signal(self, signal_data: np.ndarray) -> np.ndarray:
        if signal_data.ndim == 1:
            return savgol_filter(signal_data, self.window_length, self.polyorder)
        elif signal_data.ndim == 2:
            denoised = np.zeros_like(signal_data, dtype=complex if np.iscomplexobj(signal_data) else float)
            for i in range(signal_data.shape[1]):
                col = signal_data[:, i]
                if np.iscomplexobj(col):
                    real_denoised = savgol_filter(np.real(col), self.window_length, self.polyorder)
                    imag_denoised = savgol_filter(np.imag(col), self.window_length, self.polyorder)
                    denoised[:, i] = real_denoised + 1j * imag_denoised
                else:
                    denoised[:, i] = savgol_filter(col, self.window_length, self.polyorder)
            return denoised
        else:
            raise ValueError(f"Unsupported signal dimension: {signal_data.ndim}")


class LiftOffCompensator:
    def __init__(self, method: str = 'pca'):
        self.method = method
        self.lift_off_direction = None
        self.mean_impedance = None

    def fit(self, impedance: np.ndarray) -> 'LiftOffCompensator':
        if self.method == 'pca':
            self._fit_pca(impedance)
        elif self.method == 'mean':
            self._fit_mean(impedance)
        elif self.method == 'reference':
            self._fit_reference(impedance)
        else:
            raise ValueError(f"Unknown method: {self.method}")
        return self

    def _fit_pca(self, impedance: np.ndarray) -> None:
        X = np.column_stack([np.real(impedance).flatten(), np.imag(impedance).flatten()])
        self.mean_impedance = np.mean(X, axis=0)
        X_centered = X - self.mean_impedance
        
        cov_matrix = np.cov(X_centered.T)
        eigenvalues, eigenvectors = np.linalg.eig(cov_matrix)
        
        idx = np.argsort(eigenvalues)[::-1]
        self.lift_off_direction = eigenvectors[:, idx[0]]
        
        if self.lift_off_direction[0] < 0:
            self.lift_off_direction = -self.lift_off_direction

    def _fit_mean(self, impedance: np.ndarray) -> None:
        real_flat = np.real(impedance).flatten()
        imag_flat = np.imag(impedance).flatten()
        self.mean_impedance = np.array([np.mean(real_flat), np.mean(imag_flat)])
        
        real = np.real(impedance)
        imag = np.imag(impedance)
        diff_real = np.mean(real[-1]) - np.mean(real[0])
        diff_imag = np.mean(imag[-1]) - np.mean(imag[0])
        direction = np.array([diff_real, diff_imag])
        norm = np.linalg.norm(direction)
        if norm > 0:
            self.lift_off_direction = direction / norm
        else:
            self.lift_off_direction = np.array([1.0, 0.0])

    def _fit_reference(self, impedance: np.ndarray, reference_idx: int = 0) -> None:
        ref_real = np.real(impedance[reference_idx]).mean()
        ref_imag = np.imag(impedance[reference_idx]).mean()
        self.mean_impedance = np.array([ref_real, ref_imag])
        
        real = np.real(impedance[0]).mean()
        imag = np.imag(impedance[0]).mean()
        direction = np.array([real - self.mean_impedance[0], imag - self.mean_impedance[1]])
        norm = np.linalg.norm(direction)
        if norm > 0:
            self.lift_off_direction = direction / norm
        else:
            self.lift_off_direction = np.array([1.0, 0.0])

    def transform(self, impedance: np.ndarray) -> np.ndarray:
        if self.lift_off_direction is None:
            raise ValueError("LiftOffCompensator not fitted. Call fit() first.")
        
        original_shape = impedance.shape
        real = np.real(impedance).flatten()
        imag = np.imag(impedance).flatten()
        
        X = np.column_stack([real, imag])
        X_centered = X - self.mean_impedance
        
        projection = np.dot(X_centered, self.lift_off_direction)
        lift_off_component = np.outer(projection, self.lift_off_direction)
        
        X_compensated = X_centered - lift_off_component
        X_compensated = X_compensated + self.mean_impedance
        
        compensated = X_compensated[:, 0] + 1j * X_compensated[:, 1]
        
        return compensated.reshape(original_shape)

    def fit_transform(self, impedance: np.ndarray) -> np.ndarray:
        return self.fit(impedance).transform(impedance)


class MaterialNormalizer:
    def __init__(self,
                 reference_conductivity: float = Config.REFERENCE_CONDUCTIVITY,
                 reference_permeability: float = Config.REFERENCE_PERMEABILITY):
        self.reference_conductivity = reference_conductivity
        self.reference_permeability = reference_permeability
        self.fitted = False
        self._normalization_factor = None

    def fit(self, data: EddyCurrentData) -> 'MaterialNormalizer':
        conductivity = data.conductivity or self.reference_conductivity
        permeability = data.permeability or self.reference_permeability
        
        sigma_ref = self.reference_conductivity
        mu_ref = self.reference_permeability
        
        self._normalization_factor = np.sqrt((sigma_ref * mu_ref) / (conductivity * permeability))
        self.fitted = True
        return self

    def transform(self, data: EddyCurrentData) -> EddyCurrentData:
        if not self.fitted:
            raise ValueError("MaterialNormalizer not fitted. Call fit() first.")
        
        n_freqs = len(data.frequencies) if data.frequencies else data.impedance.shape[1]
        freq_factors = np.ones(n_freqs)
        
        if data.frequencies:
            for i, f in enumerate(data.frequencies):
                if f > 0:
                    freq_factors[i] = self._normalization_factor / np.sqrt(f)
        
        normalized_impedance = data.impedance.copy()
        for i in range(n_freqs):
            normalized_impedance[:, i] *= freq_factors[i]
        
        new_data = EddyCurrentData(
            impedance=normalized_impedance,
            frequencies=data.frequencies,
            positions=data.positions,
            timestamps=data.timestamps,
            labels=data.labels,
            conductivity=self.reference_conductivity,
            permeability=self.reference_permeability,
            metadata={**data.metadata, 'material_normalized': True}
        )
        new_data._normalized = True
        return new_data

    def fit_transform(self, data: EddyCurrentData) -> EddyCurrentData:
        return self.fit(data).transform(data)


class SpatialResampler:
    def __init__(self,
                 target_spacing: Optional[float] = None,
                 n_points: Optional[int] = None,
                 method: str = 'cubic'):
        self.target_spacing = target_spacing
        self.n_points = n_points
        self.method = method
        self.fitted = False
        self._original_positions = None
        self._new_positions = None

    def fit(self, data: EddyCurrentData) -> 'SpatialResampler':
        if data.positions is None:
            if data.timestamps is not None:
                self._original_positions = self._estimate_positions_from_timestamps(data.timestamps)
            else:
                n = data.impedance.shape[0]
                self._original_positions = np.arange(n, dtype=float)
        else:
            positions = data.positions
            if positions.ndim > 1:
                self._original_positions = positions[:, 0].copy()
            else:
                self._original_positions = positions.copy()
        
        self._original_positions = self._original_positions.astype(float)
        
        if len(self._original_positions) < 2:
            raise ValueError("Need at least 2 points for resampling")
        
        if self.n_points is None and self.target_spacing is None:
            self.n_points = len(self._original_positions)
        
        if self.target_spacing is not None:
            pos_min = np.min(self._original_positions)
            pos_max = np.max(self._original_positions)
            total_length = pos_max - pos_min
            self.n_points = max(int(np.ceil(total_length / self.target_spacing)) + 1, 2)
        
        self._new_positions = np.linspace(
            np.min(self._original_positions),
            np.max(self._original_positions),
            self.n_points
        )
        
        self.fitted = True
        return self

    def transform(self, data: EddyCurrentData) -> EddyCurrentData:
        if not self.fitted:
            raise ValueError("SpatialResampler not fitted. Call fit() first.")
        
        from scipy.interpolate import interp1d
        
        n_samples, n_freqs = data.impedance.shape
        resampled_impedance = np.zeros((self.n_points, n_freqs), dtype=complex)
        
        for i in range(n_freqs):
            real_interp = interp1d(
                self._original_positions, np.real(data.impedance[:, i]),
                kind=self.method, fill_value='extrapolate'
            )
            imag_interp = interp1d(
                self._original_positions, np.imag(data.impedance[:, i]),
                kind=self.method, fill_value='extrapolate'
            )
            resampled_impedance[:, i] = real_interp(self._new_positions) + 1j * imag_interp(self._new_positions)
        
        resampled_labels = None
        if data.labels is not None:
            if data.labels.ndim == 1:
                label_interp = interp1d(
                    self._original_positions, data.labels,
                    kind='nearest', fill_value='extrapolate'
                )
                resampled_labels = label_interp(self._new_positions)
            else:
                resampled_labels = np.zeros((self.n_points, data.labels.shape[1]))
                for j in range(data.labels.shape[1]):
                    label_interp = interp1d(
                        self._original_positions, data.labels[:, j],
                        kind='nearest', fill_value='extrapolate'
                    )
                    resampled_labels[:, j] = label_interp(self._new_positions)
        
        new_data = EddyCurrentData(
            impedance=resampled_impedance,
            frequencies=data.frequencies,
            positions=self._new_positions.reshape(-1, 1),
            timestamps=None,
            labels=resampled_labels,
            conductivity=data.conductivity,
            permeability=data.permeability,
            metadata={**data.metadata, 'spatially_resampled': True}
        )
        new_data._resampled = True
        return new_data

    def fit_transform(self, data: EddyCurrentData) -> EddyCurrentData:
        return self.fit(data).transform(data)

    def _estimate_positions_from_timestamps(self, timestamps: np.ndarray) -> np.ndarray:
        if len(timestamps) < 2:
            return np.arange(len(timestamps), dtype=float)
        
        default_speed = 0.1
        dt = np.diff(timestamps)
        positions = np.zeros_like(timestamps, dtype=float)
        
        for i in range(1, len(timestamps)):
            positions[i] = positions[i-1] + default_speed * dt[i-1]
        
        return positions


class Preprocessor:
    def __init__(self,
                 denoiser: Optional[WaveletDenoiser] = None,
                 compensator: Optional[LiftOffCompensator] = None,
                 material_normalizer: Optional[MaterialNormalizer] = None,
                 spatial_resampler: Optional[SpatialResampler] = None,
                 normalize: bool = True):
        self.denoiser = denoiser or WaveletDenoiser()
        self.compensator = compensator or LiftOffCompensator(method='pca')
        self.material_normalizer = material_normalizer
        self.spatial_resampler = spatial_resampler
        self.normalize = normalize
        self.normalization_params = None

    def process(self, data: EddyCurrentData) -> EddyCurrentData:
        processed_data = data
        
        if self.spatial_resampler is not None:
            processed_data = self.spatial_resampler.fit_transform(processed_data)
        
        impedance = processed_data.impedance.copy()
        
        denoised_impedance = self.denoiser.denoise_signal(impedance)
        
        compensated_impedance = self.compensator.fit_transform(denoised_impedance)
        
        if self.normalize:
            compensated_impedance = self._normalize(compensated_impedance)
        
        if self.material_normalizer is not None:
            temp_data = EddyCurrentData(
                impedance=compensated_impedance,
                frequencies=processed_data.frequencies,
                positions=processed_data.positions,
                timestamps=processed_data.timestamps,
                labels=processed_data.labels,
                conductivity=processed_data.conductivity,
                permeability=processed_data.permeability,
                metadata=processed_data.metadata
            )
            temp_data = self.material_normalizer.fit_transform(temp_data)
            compensated_impedance = temp_data.impedance
            final_conductivity = temp_data.conductivity
            final_permeability = temp_data.permeability
        else:
            final_conductivity = processed_data.conductivity
            final_permeability = processed_data.permeability
        
        return EddyCurrentData(
            impedance=compensated_impedance,
            frequencies=processed_data.frequencies,
            positions=processed_data.positions,
            timestamps=processed_data.timestamps,
            labels=processed_data.labels,
            conductivity=final_conductivity,
            permeability=final_permeability,
            metadata={**processed_data.metadata, 'preprocessed': True}
        )._copy_flags_from(processed_data)

    def _normalize(self, impedance: np.ndarray) -> np.ndarray:
        real = np.real(impedance)
        imag = np.imag(impedance)
        
        if self.normalization_params is None:
            self.normalization_params = {
                'real_mean': np.mean(real),
                'real_std': np.std(real),
                'imag_mean': np.mean(imag),
                'imag_std': np.std(imag)
            }
        
        real_norm = (real - self.normalization_params['real_mean']) / self.normalization_params['real_std']
        imag_norm = (imag - self.normalization_params['imag_mean']) / self.normalization_params['imag_std']
        
        return real_norm + 1j * imag_norm

    def denoise(self, data: EddyCurrentData) -> EddyCurrentData:
        denoised = self.denoiser.denoise_signal(data.impedance)
        return EddyCurrentData(
            impedance=denoised,
            frequencies=data.frequencies,
            positions=data.positions,
            timestamps=data.timestamps,
            labels=data.labels,
            conductivity=data.conductivity,
            permeability=data.permeability,
            metadata={**data.metadata, 'denoised': True}
        )

    def compensate_lift_off(self, data: EddyCurrentData) -> EddyCurrentData:
        compensated = self.compensator.fit_transform(data.impedance)
        return EddyCurrentData(
            impedance=compensated,
            frequencies=data.frequencies,
            positions=data.positions,
            timestamps=data.timestamps,
            labels=data.labels,
            conductivity=data.conductivity,
            permeability=data.permeability,
            metadata={**data.metadata, 'lift_off_compensated': True}
        )
