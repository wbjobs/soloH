import numpy as np
import librosa
from scipy import signal
from typing import Tuple, Dict, Any, Optional
from . import utils


class WaveletAnalyzer:
    def __init__(self, sample_rate: int = 16000, wavelet: str = 'morlet',
                 n_scales: int = 32, fmin: float = 50, fmax: float = 400):
        self.sample_rate = sample_rate
        self.wavelet = wavelet
        self.n_scales = n_scales
        self.fmin = fmin
        self.fmax = fmax

    def compute_cwt(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        frequencies = np.geomspace(self.fmin, self.fmax, self.n_scales)
        scales = self.sample_rate / (frequencies * 2 * np.pi)

        cwt_matrix = np.zeros((len(scales), len(audio)), dtype=np.complex128)

        for i, scale in enumerate(scales):
            wavelet = self._generate_wavelet(scale)
            cwt_matrix[i, :] = np.convolve(audio, wavelet, mode='same')

        return cwt_matrix, frequencies

    def _generate_wavelet(self, scale: float) -> np.ndarray:
        length = int(10 * scale)
        if length < 1:
            length = 1

        t = np.arange(-length // 2, length // 2 + 1) / self.sample_rate

        if self.wavelet == 'morlet':
            omega0 = 5.0
            wavelet = (np.pi ** -0.25) * np.exp(1j * omega0 * t / scale) * \
                      np.exp(-(t ** 2) / (2 * scale ** 2))
        elif self.wavelet == 'mexican_hat':
            wavelet = (2 / (np.sqrt(3 * scale) * np.pi ** 0.25)) * \
                      (1 - (t / scale) ** 2) * np.exp(-(t ** 2) / (2 * scale ** 2))
        else:
            wavelet = np.exp(-(t ** 2) / (2 * scale ** 2)) * np.cos(5 * t / scale)

        return wavelet / np.sqrt(np.sum(np.abs(wavelet) ** 2))

    def compute_inverse_cwt(self, cwt_matrix: np.ndarray,
                            frequencies: np.ndarray) -> np.ndarray:
        scales = self.sample_rate / (frequencies * 2 * np.pi)

        reconstructed = np.zeros(cwt_matrix.shape[1], dtype=np.float64)

        for i, scale in enumerate(scales):
            wavelet = self._generate_wavelet(scale)
            recon = np.convolve(cwt_matrix[i, :].real, wavelet.real, mode='same')
            reconstructed += recon / scale

        reconstructed = reconstructed / len(scales)

        max_val = np.max(np.abs(reconstructed))
        if max_val > 0:
            reconstructed = reconstructed / max_val * 0.9

        return reconstructed


class PitchRecovery:
    def __init__(self, sample_rate: int = 16000, wavelet: str = 'morlet',
                 n_scales: int = 32):
        self.sample_rate = sample_rate
        self.wavelet_analyzer = WaveletAnalyzer(
            sample_rate=sample_rate, wavelet=wavelet, n_scales=n_scales
        )

    def recover_pitch(self, audio: np.ndarray,
                      estimated_pitch_factor: float = 1.0) -> Tuple[np.ndarray, Dict[str, Any]]:
        if estimated_pitch_factor == 1.0:
            return audio.copy(), {
                'recovered': False,
                'applied_factor': 1.0,
                'method': 'none'
            }

        n_steps = -12 * np.log2(estimated_pitch_factor)

        recovered_audio = self._recover_with_cwt(audio, n_steps)

        info = {
            'recovered': True,
            'estimated_factor': float(estimated_pitch_factor),
            'applied_semitones': float(n_steps),
            'method': 'cwt_based'
        }

        return recovered_audio, info

    def _recover_with_cwt(self, audio: np.ndarray, n_steps: float) -> np.ndarray:
        cwt_matrix, frequencies = self.wavelet_analyzer.compute_cwt(audio)

        mag = np.abs(cwt_matrix)
        phase = np.angle(cwt_matrix)

        scale_factor = 2 ** (n_steps / 12)

        new_n_scales = mag.shape[0]
        new_mag = np.zeros_like(mag)
        new_phase = np.zeros_like(phase)

        for i in range(new_n_scales):
            orig_idx = i / scale_factor
            lower = int(np.floor(orig_idx))
            upper = lower + 1
            frac = orig_idx - lower

            if 0 <= lower < mag.shape[0] and 0 <= upper < mag.shape[0]:
                new_mag[i, :] = mag[lower, :] * (1 - frac) + mag[upper, :] * frac
                new_phase[i, :] = phase[lower, :] * (1 - frac) + phase[upper, :] * frac

        new_cwt = new_mag * np.exp(1j * new_phase)

        recovered = self.wavelet_analyzer.compute_inverse_cwt(new_cwt, frequencies)

        if len(recovered) < len(audio):
            recovered = np.pad(recovered, (0, len(audio) - len(recovered)))
        elif len(recovered) > len(audio):
            recovered = recovered[:len(audio)]

        return recovered

    def recover_pitch_iterative(self, audio: np.ndarray,
                                target_pitch_factor: Optional[float] = None,
                                max_iterations: int = 5) -> Tuple[np.ndarray, Dict[str, Any]]:
        current_audio = audio.copy()
        best_audio = audio.copy()
        best_confidence = 0.0
        best_factor = 1.0

        iterations = []

        for iteration in range(max_iterations):
            pitch = utils.estimate_pitch(
                current_audio, sample_rate=self.sample_rate
            )
            pitch = pitch[pitch > 0]

            if len(pitch) < 10:
                break

            current_pitch_mean = np.median(pitch)

            if target_pitch_factor is not None:
                factor = target_pitch_factor
            else:
                factor = current_pitch_mean / 120.0
                factor = np.clip(factor, 0.5, 2.0)

            if abs(factor - 1.0) < 0.02:
                break

            recovered_audio, info = self.recover_pitch(current_audio, factor)

            recovered_pitch = utils.estimate_pitch(
                recovered_audio, sample_rate=self.sample_rate
            )
            recovered_pitch = recovered_pitch[recovered_pitch > 0]

            confidence = 0.0
            if len(recovered_pitch) >= 10:
                recovered_mean = np.median(recovered_pitch)
                recovered_std = np.std(recovered_pitch) / (recovered_mean + 1e-8)
                confidence = max(0.0, 1.0 - recovered_std)

            iterations.append({
                'iteration': iteration + 1,
                'factor': float(factor),
                'confidence': float(confidence),
                'pitch_mean': float(current_pitch_mean)
            })

            if confidence > best_confidence:
                best_confidence = confidence
                best_audio = recovered_audio
                best_factor = factor

            current_audio = recovered_audio

        info = {
            'recovered': best_confidence > 0.3,
            'best_factor': float(best_factor),
            'best_confidence': float(best_confidence),
            'iterations': iterations,
            'method': 'iterative_cwt'
        }

        return best_audio, info


class SpectralRestoration:
    def __init__(self, sample_rate: int = 16000, n_fft: int = 512,
                 hop_length: int = 160):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length

    def restore_spectrum(self, audio: np.ndarray,
                         reference_audio: Optional[np.ndarray] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        mag, phase = utils.compute_stft(
            audio, n_fft=self.n_fft, hop_length=self.hop_length
        )

        restored_mag = self._denoise_spectrum(mag)

        if reference_audio is not None:
            ref_mag, _ = utils.compute_stft(
                reference_audio, n_fft=self.n_fft, hop_length=self.hop_length
            )
            restored_mag = self._match_spectral_shape(restored_mag, ref_mag)

        if restored_mag.shape != phase.shape:
            if restored_mag.shape[0] < phase.shape[0]:
                pad_height = phase.shape[0] - restored_mag.shape[0]
                restored_mag = np.pad(restored_mag, ((0, pad_height), (0, 0)), mode='edge')
            elif restored_mag.shape[0] > phase.shape[0]:
                restored_mag = restored_mag[:phase.shape[0], :]

            if restored_mag.shape[1] < phase.shape[1]:
                pad_width = phase.shape[1] - restored_mag.shape[1]
                restored_mag = np.pad(restored_mag, ((0, 0), (0, pad_width)), mode='edge')
            elif restored_mag.shape[1] > phase.shape[1]:
                restored_mag = restored_mag[:, :phase.shape[1]]

        restored_mag = self._enhance_harmonics(restored_mag)

        D = restored_mag * np.exp(1j * phase)
        restored_audio = librosa.istft(
            D, hop_length=self.hop_length, length=len(audio)
        )

        info = {
            'restored': True,
            'method': 'spectral_restoration',
            'noise_reduction_applied': True,
            'harmonic_enhancement_applied': True,
            'spectral_matching': reference_audio is not None
        }

        return restored_audio, info

    def _denoise_spectrum(self, mag: np.ndarray) -> np.ndarray:
        noise_floor = np.median(mag, axis=1, keepdims=True) * 0.5
        mag_denoised = np.maximum(mag - noise_floor, 0)

        kernel_size = 3
        kernel = np.ones((kernel_size, kernel_size)) / (kernel_size ** 2)
        mag_smoothed = signal.fftconvolve(mag_denoised, kernel, mode='same')

        alpha = 0.7
        mag_denoised = alpha * mag_denoised + (1 - alpha) * mag_smoothed

        return mag_denoised

    def _match_spectral_shape(self, mag: np.ndarray, ref_mag: np.ndarray) -> np.ndarray:
        if mag.shape[0] != ref_mag.shape[0]:
            min_bins = min(mag.shape[0], ref_mag.shape[0])
            mag = mag[:min_bins, :]
            ref_mag = ref_mag[:min_bins, :]

        ref_envelope = np.mean(ref_mag, axis=1, keepdims=True)
        mag_envelope = np.mean(mag, axis=1, keepdims=True)

        gain = ref_envelope / (mag_envelope + 1e-8)
        gain = np.clip(gain, 0.5, 2.0)

        return mag * gain

    def _enhance_harmonics(self, mag: np.ndarray) -> np.ndarray:
        enhanced = mag.copy()

        for t in range(mag.shape[1]):
            spectrum = mag[:, t]

            peak_idx = signal.find_peaks(spectrum, distance=5, height=np.max(spectrum) * 0.1)[0]

            if len(peak_idx) > 1:
                for i, idx in enumerate(peak_idx):
                    if idx > 0 and idx < len(spectrum) - 1:
                        window = slice(max(0, idx - 2), min(len(spectrum), idx + 3))
                        enhanced[window, t] *= 1.2

        return enhanced


class AudioRestoration:
    def __init__(self, sample_rate: int = 16000, wavelet: str = 'morlet',
                 n_scales: int = 32, n_fft: int = 512, hop_length: int = 160):
        self.sample_rate = sample_rate
        self.pitch_recovery = PitchRecovery(
            sample_rate=sample_rate, wavelet=wavelet, n_scales=n_scales
        )
        self.spectral_restoration = SpectralRestoration(
            sample_rate=sample_rate, n_fft=n_fft, hop_length=hop_length
        )

    def restore_audio(self, audio: np.ndarray,
                      estimated_pitch_factor: float = 1.0,
                      reference_audio: Optional[np.ndarray] = None,
                      use_iterative: bool = False) -> Tuple[np.ndarray, Dict[str, Any]]:
        recovery_info = {}
        spectral_info = {}
        recovered_audio = audio.copy()

        if estimated_pitch_factor != 1.0:
            if use_iterative:
                recovered_audio, recovery_info = self.pitch_recovery.recover_pitch_iterative(
                    audio, estimated_pitch_factor
                )
            else:
                recovered_audio, recovery_info = self.pitch_recovery.recover_pitch(
                    audio, estimated_pitch_factor
                )

        restored_audio, spectral_info = self.spectral_restoration.restore_spectrum(
            recovered_audio, reference_audio
        )

        info = {
            'pitch_recovery': recovery_info,
            'spectral_restoration': spectral_info,
            'final_snr_improvement': self._estimate_snr_improvement(audio, restored_audio)
        }

        return restored_audio, info

    def _estimate_snr_improvement(self, original: np.ndarray,
                                  restored: np.ndarray) -> float:
        noise_original = np.std(original)
        noise_restored = np.std(restored)

        if noise_original > 0:
            improvement = 20 * np.log10(noise_original / (noise_restored + 1e-8))
            return float(improvement)
        return 0.0
