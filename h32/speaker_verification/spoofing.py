import numpy as np
import librosa
from scipy import signal
from typing import Tuple, Optional, Dict, Any
import warnings
warnings.filterwarnings('ignore')


class PSOLAPitchShifter:
    def __init__(self, sample_rate: int = 16000, frame_length: int = 2048,
                 hop_length: int = 512):
        self.sample_rate = sample_rate
        self.frame_length = frame_length
        self.hop_length = hop_length
        self.window = np.hanning(frame_length)

    def _find_pitch_period(self, frame: np.ndarray, fmin: float = 50,
                           fmax: float = 500) -> int:
        min_period = int(self.sample_rate / fmax)
        max_period = int(self.sample_rate / fmin)

        frame = frame - np.mean(frame)
        autocorr = np.correlate(frame, frame, mode='full')
        autocorr = autocorr[len(autocorr) // 2:]

        valid_range = autocorr[min_period:max_period]
        if len(valid_range) == 0 or np.max(valid_range) < 1e-8:
            return min_period

        period = np.argmax(valid_range) + min_period
        return period

    def shift_pitch(self, audio: np.ndarray, n_steps: float) -> np.ndarray:
        if n_steps == 0:
            return audio.copy()

        pitch_factor = 2 ** (n_steps / 12)
        output_length = int(len(audio) / pitch_factor)
        output = np.zeros(output_length)

        in_pos = 0
        out_pos = 0
        analysis_hop = self.hop_length
        synthesis_hop = int(analysis_hop / pitch_factor)

        while out_pos + self.frame_length < output_length:
            if in_pos + self.frame_length >= len(audio):
                break

            frame = audio[in_pos:in_pos + self.frame_length] * self.window
            period = self._find_pitch_period(frame)

            pulse_indices = []
            for i in range(0, len(frame), period):
                if i < len(frame):
                    pulse_indices.append(i)

            target_hop = int(period / pitch_factor)

            for idx, pulse_idx in enumerate(pulse_indices):
                start = pulse_idx - period // 2
                end = pulse_idx + period // 2
                if start < 0:
                    start = 0
                if end > len(frame):
                    end = len(frame)

                segment = frame[start:end].copy()
                if len(segment) > 0:
                    seg_window = np.hanning(len(segment))
                    segment = segment * seg_window

                    out_start = out_pos + idx * target_hop
                    out_end = out_start + len(segment)

                    if out_end <= output_length:
                        output[out_start:out_end] += segment

            in_pos += analysis_hop
            out_pos += synthesis_hop

        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val * np.max(np.abs(audio))

        return output


class ResampleTimeStretcher:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def stretch_time(self, audio: np.ndarray, rate: float) -> np.ndarray:
        if rate == 1.0:
            return audio.copy()

        new_length = int(len(audio) / rate)
        stretched = librosa.effects.time_stretch(audio, rate=rate)

        if len(stretched) > new_length:
            stretched = stretched[:new_length]
        elif len(stretched) < new_length:
            stretched = np.pad(stretched, (0, new_length - len(stretched)))

        return stretched


class PhaseVocoder:
    def __init__(self, sample_rate: int = 16000, n_fft: int = 2048,
                 hop_length: int = 512, transient_threshold: float = 0.6):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.window = np.hanning(n_fft)
        self.transient_threshold = transient_threshold

    def _detect_transients(self, mag: np.ndarray) -> np.ndarray:
        flux = np.zeros(mag.shape[1])
        for t in range(1, mag.shape[1]):
            diff = mag[:, t] - mag[:, t - 1]
            flux[t] = np.sum(np.maximum(0, diff))

        if np.max(flux) > 0:
            flux = flux / np.max(flux)

        transients = flux > self.transient_threshold

        transient_protection = np.zeros_like(transients, dtype=float)
        for i, is_transient in enumerate(transients):
            if is_transient:
                start = max(0, i - 2)
                end = min(len(transient_protection), i + 3)
                transient_protection[start:end] = np.maximum(
                    transient_protection[start:end],
                    np.linspace(0.5, 1.0, end - start) if (end - start) > 0 else 1.0
                )

        return transient_protection

    def _compute_phase_propagation(self, phase: np.ndarray,
                                   mag: np.ndarray) -> np.ndarray:
        n_bins, n_frames = phase.shape
        omega = 2 * np.pi * np.arange(n_bins) * self.hop_length / self.n_fft

        phase_unwrapped = np.unwrap(phase, axis=1)
        phase_derivative = np.diff(phase_unwrapped, axis=1)
        phase_derivative = np.pad(phase_derivative, ((0, 0), (1, 0)), mode='edge')

        true_frequency = omega[:, np.newaxis] + phase_derivative

        return true_frequency

    def _shift_pitch_with_transient_protection(
        self, mag: np.ndarray, phase: np.ndarray, n_steps: float,
        transient_protection: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        pitch_factor = 2 ** (n_steps / 12)
        n_bins, n_frames = mag.shape

        new_mag = np.zeros_like(mag)
        new_phase = np.zeros_like(phase)

        true_freq = self._compute_phase_propagation(phase, mag)

        bins_before = np.arange(n_bins)
        bins_after = bins_before * pitch_factor

        for j in range(n_frames):
            is_transient = transient_protection[j] > 0.3

            for i in range(n_bins):
                src_bin = bins_after[i]
                lower = int(np.floor(src_bin))
                upper = lower + 1
                frac = src_bin - lower

                if 0 <= lower < n_bins and 0 <= upper < n_bins:
                    new_mag[i, j] = mag[lower, j] * (1 - frac) + mag[upper, j] * frac

                    if is_transient:
                        orig_phase = phase[lower, j] * (1 - frac) + phase[upper, j] * frac
                        phase_offset = true_freq[lower, j] * (1 - frac) + true_freq[upper, j] * frac
                        phase_offset = phase_offset * (1 - transient_protection[j])
                        new_phase[i, j] = orig_phase * transient_protection[j] + phase_offset * (1 - transient_protection[j])
                    else:
                        phase_advance = true_freq[lower, j] * (1 - frac) + true_freq[upper, j] * frac
                        if j == 0:
                            new_phase[i, j] = phase[lower, j] * (1 - frac) + phase[upper, j] * frac
                        else:
                            expected_phase = new_phase[i, j - 1] + phase_advance * pitch_factor
                            new_phase[i, j] = expected_phase

        return new_mag, new_phase

    def _stretch_time_with_phase_lock(
        self, mag: np.ndarray, phase: np.ndarray,
        time_stretch: float, transient_protection: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, int]:
        n_bins, n_frames = mag.shape
        new_hop = int(self.hop_length / time_stretch)

        true_freq = self._compute_phase_propagation(phase, mag)

        time_steps = np.arange(0, n_frames, time_stretch)
        n_new_frames = len(time_steps)

        new_mag = np.zeros((n_bins, n_new_frames))
        new_phase = np.zeros((n_bins, n_new_frames))

        for i, t in enumerate(time_steps):
            lower = int(np.floor(t))
            upper = lower + 1
            frac = t - lower

            is_transient = False
            if lower < len(transient_protection) and transient_protection[lower] > 0.3:
                is_transient = True
            if upper < len(transient_protection) and transient_protection[upper] > 0.3:
                is_transient = True

            if upper < n_frames:
                new_mag[:, i] = mag[:, lower] * (1 - frac) + mag[:, upper] * frac

                if is_transient:
                    new_phase[:, i] = phase[:, lower] * (1 - frac) + phase[:, upper] * frac
                else:
                    phase_lower = phase[:, lower]
                    phase_upper = phase[:, upper]

                    phase_diff = phase_upper - phase_lower
                    phase_diff = np.mod(phase_diff + np.pi, 2 * np.pi) - np.pi

                    new_phase[:, i] = phase_lower + phase_diff * frac

                    if i > 0:
                        true_freq_interp = true_freq[:, lower] * (1 - frac) + true_freq[:, upper] * frac
                        expected_phase = new_phase[:, i - 1] + true_freq_interp * (self.hop_length / new_hop)

                        phase_err = new_phase[:, i] - expected_phase
                        phase_err = np.mod(phase_err + np.pi, 2 * np.pi) - np.pi

                        transient_weight = max(
                            transient_protection[lower] if lower < len(transient_protection) else 0,
                            transient_protection[upper] if upper < len(transient_protection) else 0
                        )

                        new_phase[:, i] = expected_phase + phase_err * transient_weight
            else:
                new_mag[:, i] = mag[:, lower]
                new_phase[:, i] = phase[:, lower]

        return new_mag, new_phase, new_hop

    def process(self, audio: np.ndarray, pitch_shift: float = 0,
                time_stretch: float = 1.0) -> np.ndarray:
        if pitch_shift == 0 and time_stretch == 1.0:
            return audio.copy()

        D = librosa.stft(audio, n_fft=self.n_fft, hop_length=self.hop_length,
                         window=self.window)

        mag = np.abs(D)
        phase = np.angle(D)

        transient_protection = self._detect_transients(mag)

        current_hop = self.hop_length

        if pitch_shift != 0:
            mag, phase = self._shift_pitch_with_transient_protection(
                mag, phase, pitch_shift, transient_protection
            )

        if time_stretch != 1.0:
            mag, phase, current_hop = self._stretch_time_with_phase_lock(
                mag, phase, time_stretch, transient_protection
            )

        D_reconstructed = mag * np.exp(1j * phase)
        output = librosa.istft(D_reconstructed, hop_length=current_hop,
                               window=self.window, length=len(audio))

        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val * np.max(np.abs(audio))

        return output


class ReplayAttackSimulator:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def apply_replay(self, audio: np.ndarray, quality: str = 'medium') -> np.ndarray:
        audio = audio.copy()

        if quality == 'low':
            noise_level = 0.05
            cutoff_freq = 3000
        elif quality == 'medium':
            noise_level = 0.02
            cutoff_freq = 5000
        else:
            noise_level = 0.005
            cutoff_freq = 7000

        b, a = signal.butter(4, cutoff_freq / (self.sample_rate / 2), 'low')
        audio = signal.filtfilt(b, a, audio)

        noise = np.random.normal(0, noise_level, len(audio))
        audio = audio + noise

        echo_delay = int(0.05 * self.sample_rate)
        echo_gain = 0.3
        if len(audio) > echo_delay:
            echo = np.zeros_like(audio)
            echo[echo_delay:] = audio[:-echo_delay] * echo_gain
            audio = audio + echo

        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.9

        return audio


class SplicingAttackSimulator:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def apply_splicing(self, audio1: np.ndarray, audio2: np.ndarray,
                       splice_point: Optional[float] = None) -> np.ndarray:
        if splice_point is None:
            splice_point = np.random.uniform(0.3, 0.7)

        splice_idx1 = int(len(audio1) * splice_point)
        splice_idx2 = int(len(audio2) * (1 - splice_point))

        crossfade_len = int(0.05 * self.sample_rate)
        if crossfade_len > splice_idx1 or crossfade_len > len(audio1) - splice_idx1:
            crossfade_len = min(splice_idx1, len(audio1) - splice_idx1)

        part1 = audio1[:splice_idx1].copy()
        part2 = audio2[splice_idx2:].copy()

        if crossfade_len > 0:
            fade_out = np.linspace(1, 0, crossfade_len)
            fade_in = np.linspace(0, 1, crossfade_len)

            part1[-crossfade_len:] = part1[-crossfade_len:] * fade_out
            part2[:crossfade_len] = part2[:crossfade_len] * fade_in

        return np.concatenate([part1, part2])


class SpoofingSimulator:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.psola = PSOLAPitchShifter(sample_rate)
        self.time_stretcher = ResampleTimeStretcher(sample_rate)
        self.phase_vocoder = PhaseVocoder(sample_rate)
        self.replay = ReplayAttackSimulator(sample_rate)
        self.splicing = SplicingAttackSimulator(sample_rate)

    def apply_pitch_shift_psola(self, audio: np.ndarray, n_steps: float) -> Tuple[np.ndarray, Dict[str, Any]]:
        shifted = self.psola.shift_pitch(audio, n_steps)
        return shifted, {'type': 'pitch_shift_psola', 'n_steps': n_steps, 'factor': 2 ** (n_steps / 12)}

    def apply_time_stretch_resample(self, audio: np.ndarray, rate: float) -> Tuple[np.ndarray, Dict[str, Any]]:
        stretched = self.time_stretcher.stretch_time(audio, rate)
        return stretched, {'type': 'time_stretch_resample', 'rate': rate}

    def apply_phase_vocoder(self, audio: np.ndarray, pitch_shift: float = 0,
                            time_stretch: float = 1.0) -> Tuple[np.ndarray, Dict[str, Any]]:
        processed = self.phase_vocoder.process(audio, pitch_shift, time_stretch)
        return processed, {
            'type': 'phase_vocoder',
            'pitch_shift': pitch_shift,
            'time_stretch': time_stretch,
            'pitch_factor': 2 ** (pitch_shift / 12) if pitch_shift != 0 else 1.0
        }

    def apply_replay_attack(self, audio: np.ndarray, quality: str = 'medium') -> Tuple[np.ndarray, Dict[str, Any]]:
        replayed = self.replay.apply_replay(audio, quality)
        return replayed, {'type': 'replay_attack', 'quality': quality}

    def apply_splicing_attack(self, audio1: np.ndarray, audio2: np.ndarray,
                              splice_point: Optional[float] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        spliced = self.splicing.apply_splicing(audio1, audio2, splice_point)
        return spliced, {'type': 'splicing_attack', 'splice_point': splice_point}

    def apply_random_spoofing(self, audio: np.ndarray,
                              audio2: Optional[np.ndarray] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        attack_types = ['pitch_shift_psola', 'time_stretch_resample',
                        'phase_vocoder', 'replay_attack']
        if audio2 is not None:
            attack_types.append('splicing_attack')

        attack = np.random.choice(attack_types)

        if attack == 'pitch_shift_psola':
            n_steps = np.random.uniform(-4, 4)
            return self.apply_pitch_shift_psola(audio, n_steps)
        elif attack == 'time_stretch_resample':
            rate = np.random.uniform(0.7, 1.3)
            return self.apply_time_stretch_resample(audio, rate)
        elif attack == 'phase_vocoder':
            pitch_shift = np.random.uniform(-3, 3)
            time_stretch = np.random.uniform(0.8, 1.2)
            return self.apply_phase_vocoder(audio, pitch_shift, time_stretch)
        elif attack == 'replay_attack':
            quality = np.random.choice(['low', 'medium', 'high'])
            return self.apply_replay_attack(audio, quality)
        elif attack == 'splicing_attack' and audio2 is not None:
            splice_point = np.random.uniform(0.3, 0.7)
            return self.apply_splicing_attack(audio, audio2, splice_point)
        else:
            return self.apply_replay_attack(audio, 'medium')
