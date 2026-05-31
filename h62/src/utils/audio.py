import os
import numpy as np
import librosa
import soundfile as sf
import torch
from scipy.io.wavfile import write
from typing import Tuple, Optional
import warnings

warnings.filterwarnings("ignore")


class AudioProcessor:
    def __init__(self, config: dict):
        self.sampling_rate = config["audio"]["sampling_rate"]
        self.filter_length = config["audio"]["filter_length"]
        self.hop_length = config["audio"]["hop_length"]
        self.win_length = config["audio"]["win_length"]
        self.n_mel_channels = config["audio"]["n_mel_channels"]
        self.mel_fmin = config["audio"]["mel_fmin"]
        self.mel_fmax = config["audio"]["mel_fmax"]
        self.max_wav_value = config["audio"]["max_wav_value"]

    def load_wav(self, wav_path: str, sr: Optional[int] = None) -> np.ndarray:
        sr = sr or self.sampling_rate
        wav, _ = librosa.load(wav_path, sr=sr)
        return wav

    def save_wav(self, wav: np.ndarray, wav_path: str, sr: Optional[int] = None) -> None:
        sr = sr or self.sampling_rate
        os.makedirs(os.path.dirname(wav_path), exist_ok=True)
        wav = wav / np.max(np.abs(wav)) * 0.95
        write(wav_path, sr, (wav * self.max_wav_value).astype(np.int16))

    def save_wav_soundfile(self, wav: np.ndarray, wav_path: str, sr: Optional[int] = None) -> None:
        sr = sr or self.sampling_rate
        os.makedirs(os.path.dirname(wav_path), exist_ok=True)
        wav = wav / np.max(np.abs(wav)) * 0.95
        sf.write(wav_path, wav, sr)

    def wav_to_mel(self, wav: np.ndarray) -> np.ndarray:
        if np.max(np.abs(wav)) > 1.0:
            wav = wav / self.max_wav_value

        mel = librosa.feature.melspectrogram(
            y=wav,
            sr=self.sampling_rate,
            n_fft=self.filter_length,
            hop_length=self.hop_length,
            win_length=self.win_length,
            n_mels=self.n_mel_channels,
            fmin=self.mel_fmin,
            fmax=self.mel_fmax,
        )
        mel = np.log(np.clip(mel, a_min=1e-5, a_max=None))
        return mel.astype(np.float32)

    def mel_to_wav(self, mel: np.ndarray) -> np.ndarray:
        mel = np.exp(mel)
        wav = librosa.feature.inverse.mel_to_audio(
            mel,
            sr=self.sampling_rate,
            n_fft=self.filter_length,
            hop_length=self.hop_length,
            win_length=self.win_length,
            fmin=self.mel_fmin,
            fmax=self.mel_fmax,
        )
        return wav

    def dynamic_range_compression(self, x: np.ndarray, C: int = 1, clip_val: float = 1e-5) -> np.ndarray:
        return np.log(np.clip(x, a_min=clip_val, a_max=None) * C)

    def dynamic_range_decompression(self, x: np.ndarray, C: int = 1) -> np.ndarray:
        return np.exp(x) / C

    def get_mel_from_file(self, wav_path: str) -> np.ndarray:
        wav = self.load_wav(wav_path)
        return self.wav_to_mel(wav)

    def trim_silence(self, wav: np.ndarray, top_db: int = 45) -> np.ndarray:
        trimmed, _ = librosa.effects.trim(wav, top_db=top_db)
        return trimmed

    def normalize_volume(self, wav: np.ndarray, target_db: float = -20.0) -> np.ndarray:
        rms = np.sqrt(np.mean(wav ** 2))
        target_rms = 10 ** (target_db / 20)
        if rms > 0:
            wav = wav * (target_rms / rms)
        return wav

    def resample(self, wav: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        return librosa.resample(wav, orig_sr=orig_sr, target_sr=target_sr)

    def preemphasis(self, wav: np.ndarray, coef: float = 0.97) -> np.ndarray:
        return librosa.effects.preemphasis(wav, coef=coef)

    def inv_preemphasis(self, wav: np.ndarray, coef: float = 0.97) -> np.ndarray:
        return librosa.effects.deemphasis(wav, coef=coef)

    def get_f0(self, wav: np.ndarray) -> np.ndarray:
        f0, _, _ = librosa.pyin(
            wav,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=self.sampling_rate,
            hop_length=self.hop_length,
        )
        f0 = np.nan_to_num(f0)
        return f0

    def get_energy(self, wav: np.ndarray) -> np.ndarray:
        energy = librosa.feature.rms(y=wav, hop_length=self.hop_length)
        return energy.squeeze()

    def get_duration(self, wav_path: str) -> float:
        return librosa.get_duration(filename=wav_path)

    def mel_spectrogram_torch(self, y: torch.Tensor) -> torch.Tensor:
        if torch.max(torch.abs(y)) > 1.0:
            y = y / self.max_wav_value

        mel = torch.stft(
            y,
            n_fft=self.filter_length,
            hop_length=self.hop_length,
            win_length=self.win_length,
            window=torch.hann_window(self.win_length, device=y.device),
            return_complex=True,
        )
        mel = torch.abs(mel)

        mel_basis = torch.from_numpy(
            librosa.filters.mel(
                sr=self.sampling_rate,
                n_fft=self.filter_length,
                n_mels=self.n_mel_channels,
                fmin=self.mel_fmin,
                fmax=self.mel_fmax,
            )
        ).to(y.device)
        mel = torch.matmul(mel_basis, mel)
        mel = torch.log(torch.clamp(mel, min=1e-5))
        return mel
