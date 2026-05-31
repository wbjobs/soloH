import numpy as np
import wave
import struct
from typing import Tuple, Optional
from config import Config, KEYBOARD_KEYS, CHAR_TO_KEY


def read_wav_file(file_path: str) -> Tuple[np.ndarray, int]:
    with wave.open(file_path, 'rb') as wf:
        num_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        num_frames = wf.getnframes()
        
        raw_data = wf.readframes(num_frames)
        
        if sample_width == 2:
            dtype = np.int16
        elif sample_width == 4:
            dtype = np.int32
        else:
            raise ValueError(f"Unsupported sample width: {sample_width}")
        
        samples = np.frombuffer(raw_data, dtype=dtype)
        samples = samples.reshape(-1, num_channels).T
        samples = samples.astype(np.float32) / np.iinfo(dtype).max
        
        return samples, sample_rate


def write_wav_file(file_path: str, audio: np.ndarray, sample_rate: int) -> None:
    num_channels = audio.shape[0]
    audio_int = (audio * np.iinfo(np.int16).max).astype(np.int16)
    
    with wave.open(file_path, 'wb') as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        
        audio_int = audio_int.T.flatten()
        raw_data = audio_int.tobytes()
        wf.writeframes(raw_data)


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        return audio / max_val
    return audio


def preemphasis(audio: np.ndarray, coeff: float = 0.97) -> np.ndarray:
    return np.append(audio[0], audio[1:] - coeff * audio[:-1])


def framing(audio: np.ndarray, frame_size: int, hop_size: int) -> np.ndarray:
    if len(audio) < frame_size:
        pad = np.zeros(frame_size - len(audio))
        audio = np.concatenate([audio, pad])
    
    num_frames = 1 + max(0, (len(audio) - frame_size) // hop_size)
    if num_frames < 1:
        num_frames = 1
    
    frames = np.zeros((num_frames, frame_size))
    for i in range(num_frames):
        start = i * hop_size
        end = min(start + frame_size, len(audio))
        frames[i, :end - start] = audio[start:end]
    return frames


def windowing(frames: np.ndarray, window_type: str = 'hamming') -> np.ndarray:
    if window_type == 'hamming':
        window = np.hamming(frames.shape[1])
    elif window_type == 'hann':
        window = np.hanning(frames.shape[1])
    else:
        window = np.ones(frames.shape[1])
    return frames * window


def compute_energy(audio: np.ndarray) -> np.ndarray:
    return np.sum(audio ** 2, axis=-1)


def compute_rms(audio: np.ndarray) -> np.ndarray:
    return np.sqrt(np.mean(audio ** 2, axis=-1))


def compute_snr(signal: np.ndarray, noise: np.ndarray) -> float:
    signal_power = np.mean(signal ** 2)
    noise_power = np.mean(noise ** 2)
    return 10 * np.log10(signal_power / (noise_power + 1e-10))


def char_to_key(char: str) -> str:
    return CHAR_TO_KEY.get(char, char)


def sequence_to_keys(sequence: str) -> list:
    return [char_to_key(c) for c in sequence if c in CHAR_TO_KEY]


def keys_to_text(keys: list) -> str:
    key_to_char = {v: k for k, v in CHAR_TO_KEY.items()}
    text = []
    for key in keys:
        if key == 'Space':
            text.append(' ')
        elif key in key_to_char:
            text.append(key_to_char[key])
        elif key in ('Backspace', 'Enter', 'Tab'):
            text.append(f'[{key}]')
    return ''.join(text)


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    x_max = np.max(x, axis=axis, keepdims=True)
    e_x = np.exp(x - x_max)
    return e_x / np.sum(e_x, axis=axis, keepdims=True)


def pad_sequence(events: list, max_len: int, pad_value: float = 0.0) -> np.ndarray:
    if len(events) == 0:
        return np.zeros((max_len,))
    
    dim = events[0].shape[-1] if len(events[0].shape) > 0 else 1
    padded = np.full((len(events), max_len, dim), pad_value)
    
    for i, event in enumerate(events):
        length = min(event.shape[0], max_len)
        padded[i, :length] = event[:length]
    
    return padded


def one_hot_encode(labels: list, num_classes: int) -> np.ndarray:
    encoded = np.zeros((len(labels), num_classes))
    for i, label in enumerate(labels):
        if 0 <= label < num_classes:
            encoded[i, label] = 1
    return encoded


def get_key_index(key: str) -> Optional[int]:
    if key in KEYBOARD_KEYS:
        return KEYBOARD_KEYS.index(key)
    return None


def get_key_name(index: int) -> Optional[str]:
    if 0 <= index < len(KEYBOARD_KEYS):
        return KEYBOARD_KEYS[index]
    return None
