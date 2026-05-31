import os
import yaml
import numpy as np
import librosa
import soundfile as sf
import torch
from typing import Tuple, Optional, Dict, Any


def load_config(config_path: str = 'config.yaml') -> Dict[str, Any]:
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_audio(file_path: str, sample_rate: int = 16000, mono: bool = True) -> Tuple[np.ndarray, int]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"音频文件不存在: {file_path}")
    
    audio, sr = librosa.load(file_path, sr=sample_rate, mono=mono)
    
    if len(audio.shape) > 1 and mono:
        audio = np.mean(audio, axis=0)
    
    return audio, sr


def save_audio(file_path: str, audio: np.ndarray, sample_rate: int) -> None:
    dirname = os.path.dirname(file_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    sf.write(file_path, audio, sample_rate)


def normalize_audio(audio: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    rms = np.sqrt(np.mean(audio ** 2))
    target_rms = 10 ** (target_db / 20)
    gain = target_rms / (rms + 1e-8)
    return audio * gain


def pad_or_trim(audio: np.ndarray, target_length: int) -> np.ndarray:
    if len(audio) > target_length:
        start = (len(audio) - target_length) // 2
        return audio[start:start + target_length]
    elif len(audio) < target_length:
        pad_start = (target_length - len(audio)) // 2
        pad_end = target_length - len(audio) - pad_start
        return np.pad(audio, (pad_start, pad_end), mode='constant')
    return audio


def compute_stft(audio: np.ndarray, n_fft: int = 512, 
                 hop_length: int = 160, win_length: int = 400) -> Tuple[np.ndarray, np.ndarray]:
    stft = librosa.stft(audio, n_fft=n_fft, hop_length=hop_length, 
                        win_length=win_length, window='hann')
    mag = np.abs(stft)
    phase = np.angle(stft)
    return mag, phase


def compute_mel_spectrogram(audio: np.ndarray, sample_rate: int = 16000,
                            n_fft: int = 512, hop_length: int = 160,
                            n_mels: int = 80, f_min: float = 0,
                            f_max: float = 8000) -> np.ndarray:
    mel_spec = librosa.feature.melspectrogram(
        y=audio, sr=sample_rate, n_fft=n_fft, hop_length=hop_length,
        n_mels=n_mels, fmin=f_min, fmax=f_max
    )
    return librosa.power_to_db(mel_spec, ref=np.max)


def compute_mfcc(audio: np.ndarray, sample_rate: int = 16000,
                 n_mfcc: int = 20, **kwargs) -> np.ndarray:
    return librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=n_mfcc, **kwargs)


def to_tensor(audio: np.ndarray, device: str = 'cpu') -> torch.Tensor:
    return torch.tensor(audio, dtype=torch.float32, device=device)


def to_numpy(tensor: torch.Tensor) -> np.ndarray:
    return tensor.detach().cpu().numpy()


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    vec1 = vec1 / (np.linalg.norm(vec1) + 1e-8)
    vec2 = vec2 / (np.linalg.norm(vec2) + 1e-8)
    return float(np.dot(vec1, vec2))


def l2_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
    return float(np.linalg.norm(vec1 - vec2))


def apply_vad(audio: np.ndarray, sample_rate: int = 16000,
              top_db: float = 20) -> np.ndarray:
    intervals = librosa.effects.split(audio, top_db=top_db)
    if len(intervals) == 0:
        return audio
    segments = []
    for start, end in intervals:
        segments.append(audio[start:end])
    return np.concatenate(segments) if segments else audio


def estimate_pitch(audio: np.ndarray, sample_rate: int = 16000,
                   fmin: float = 50, fmax: float = 400) -> np.ndarray:
    pitches, magnitudes = librosa.piptrack(
        y=audio, sr=sample_rate, fmin=fmin, fmax=fmax
    )
    pitch = []
    for i in range(pitches.shape[1]):
        index = magnitudes[:, i].argmax()
        p = pitches[index, i]
        pitch.append(p if p > 0 else 0)
    return np.array(pitch)


def compute_snr(clean_audio: np.ndarray, noisy_audio: np.ndarray) -> float:
    if len(clean_audio) != len(noisy_audio):
        min_len = min(len(clean_audio), len(noisy_audio))
        clean_audio = clean_audio[:min_len]
        noisy_audio = noisy_audio[:min_len]

    noise = noisy_audio - clean_audio

    signal_power = np.mean(clean_audio ** 2)
    noise_power = np.mean(noise ** 2)

    if noise_power < 1e-10:
        return 100.0

    snr = 10 * np.log10(signal_power / noise_power)
    return float(snr)
