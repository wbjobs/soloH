import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class AudioConfig:
    sample_rate: int = 48000
    num_channels: int = 4
    dtype: np.dtype = np.float32
    bit_depth: int = 16

@dataclass
class EventDetectionConfig:
    energy_threshold: float = 0.01
    min_duration: float = 0.01
    max_duration: float = 0.1
    long_press_min_duration: float = 0.3
    long_press_max_gap: float = 0.25
    pre_trigger: float = 0.005
    post_trigger: float = 0.01
    window_size: int = 256
    hop_size: int = 128
    collision_min_separation: float = 0.05
    collision_energy_ratio: float = 0.3
    use_multichannel_separation: bool = True
    peak_detection_window: int = 5

@dataclass
class FeatureExtractionConfig:
    n_mels: int = 128
    n_fft: int = 2048
    hop_length: int = 512
    fmin: float = 20.0
    fmax: float = 20000.0
    tdoa_max_delay_bins: int = 128
    tdoa_window_size: int = 1024
    extract_robust_features: bool = True
    spectral_centroid: bool = True
    spectral_bandwidth: bool = True
    spectral_rolloff: bool = True
    spectral_centroid_order: int = 2
    mfcc_coeffs: int = 20
    decay_rate: bool = True
    attack_time: bool = True
    zero_crossing_rate: bool = True
    use_whitening: bool = True
    whitening_epsilon: float = 1e-6

@dataclass
class ClassifierConfig:
    num_classes: int = 104
    cnn_channels: List[int] = field(default_factory=lambda: [32, 64, 128, 256])
    transformer_heads: int = 8
    transformer_layers: int = 4
    transformer_dim: int = 512
    dropout: float = 0.1
    learning_rate: float = 0.0001

@dataclass
class LocalizationConfig:
    sound_speed: float = 343.0
    mic_positions: np.ndarray = field(default_factory=lambda: np.array([
        [0.0, 0.0, 0.0],
        [0.1, 0.0, 0.0],
        [0.1, 0.1, 0.0],
        [0.0, 0.1, 0.0]
    ]))
    keyboard_size: Tuple[float, float] = (0.45, 0.15)
    keyboard_position: Tuple[float, float, float] = (0.2, 0.3, 0.0)

@dataclass
class CalibrationConfig:
    calibration_sequence: str = "the quick brown fox jumps over the lazy dog 0123456789"
    num_calibration_iterations: int = 100
    optimization_method: str = "gradient_descent"

@dataclass
class LanguageModelConfig:
    use_keyboard_layout: bool = True
    keyboard_distance_weight: float = 0.3
    use_ngram: bool = True
    ngram_order: int = 2
    language_model_weight: float = 0.4
    acoustic_model_weight: float = 0.6
    viterbi_beam_width: int = 10
    unknown_key_penalty: float = -10.0

@dataclass
class SideChannelProtectionConfig:
    enable_protection: bool = True
    min_energy_std: float = 0.1
    max_energy_std: float = 2.0
    min_spectral_centroid: float = 100.0
    max_spectral_centroid: float = 10000.0
    min_decay_rate: float = 5.0
    max_decay_rate: float = 200.0
    temporal_consistency_threshold: float = 0.3
    multi_channel_correlation_threshold: float = 0.5
    fake_key_confidence_threshold: float = 0.8

@dataclass
class StreamingConfig:
    enable_streaming: bool = False
    window_size: float = 2.0
    window_overlap: float = 1.5
    buffer_size: float = 0.5
    min_event_gap: float = 0.1
    emit_partial_results: bool = True

@dataclass
class Config:
    audio: AudioConfig = field(default_factory=AudioConfig)
    event_detection: EventDetectionConfig = field(default_factory=EventDetectionConfig)
    feature_extraction: FeatureExtractionConfig = field(default_factory=FeatureExtractionConfig)
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)
    localization: LocalizationConfig = field(default_factory=LocalizationConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    language_model: LanguageModelConfig = field(default_factory=LanguageModelConfig)
    side_channel_protection: SideChannelProtectionConfig = field(default_factory=SideChannelProtectionConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)

KEYBOARD_KEYS = [
    '`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', 'Backspace',
    'Tab', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', '\\',
    'Caps', 'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', "'", 'Enter',
    'Shift', 'z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/', 'Shift',
    'Ctrl', 'Win', 'Alt', 'Space', 'Alt', 'Win', 'Menu', 'Ctrl',
    'Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
    'PrtSc', 'ScrLk', 'Pause',
    'Insert', 'Home', 'PgUp',
    'Delete', 'End', 'PgDn',
    'Up', 'Left', 'Down', 'Right',
    'NumLk', 'Num/', 'Num*', 'Num-',
    'Num7', 'Num8', 'Num9', 'Num+',
    'Num4', 'Num5', 'Num6',
    'Num1', 'Num2', 'Num3', 'NumEnter',
    'Num0', 'Num.'
]

KEY_POSITIONS = {
    '`': (0.02, 0.02), '1': (0.06, 0.02), '2': (0.10, 0.02), '3': (0.14, 0.02),
    '4': (0.18, 0.02), '5': (0.22, 0.02), '6': (0.26, 0.02), '7': (0.30, 0.02),
    '8': (0.34, 0.02), '9': (0.38, 0.02), '0': (0.42, 0.02), '-': (0.46, 0.02),
    '=': (0.50, 0.02), 'Backspace': (0.56, 0.02),
    'Tab': (0.03, 0.06), 'q': (0.08, 0.06), 'w': (0.12, 0.06), 'e': (0.16, 0.06),
    'r': (0.20, 0.06), 't': (0.24, 0.06), 'y': (0.28, 0.06), 'u': (0.32, 0.06),
    'i': (0.36, 0.06), 'o': (0.40, 0.06), 'p': (0.44, 0.06), '[': (0.48, 0.06),
    ']': (0.52, 0.06), '\\': (0.57, 0.06),
    'Caps': (0.04, 0.10), 'a': (0.09, 0.10), 's': (0.13, 0.10), 'd': (0.17, 0.10),
    'f': (0.21, 0.10), 'g': (0.25, 0.10), 'h': (0.29, 0.10), 'j': (0.33, 0.10),
    'k': (0.37, 0.10), 'l': (0.41, 0.10), ';': (0.45, 0.10), "'": (0.49, 0.10),
    'Enter': (0.56, 0.10),
    'Shift': (0.06, 0.14), 'z': (0.11, 0.14), 'x': (0.15, 0.14), 'c': (0.19, 0.14),
    'v': (0.23, 0.14), 'b': (0.27, 0.14), 'n': (0.31, 0.14), 'm': (0.35, 0.14),
    ',': (0.39, 0.14), '.': (0.43, 0.14), '/': (0.47, 0.14),
    'Ctrl': (0.03, 0.18), 'Win': (0.08, 0.18), 'Alt': (0.13, 0.18),
    'Space': (0.30, 0.18), 'Alt': (0.48, 0.18), 'Win': (0.53, 0.18),
    'Menu': (0.58, 0.18), 'Ctrl': (0.63, 0.18)
}

CHAR_TO_KEY = {
    '`': '`', '~': '`',
    '1': '1', '!': '1',
    '2': '2', '@': '2',
    '3': '3', '#': '3',
    '4': '4', '$': '4',
    '5': '5', '%': '5',
    '6': '6', '^': '6',
    '7': '7', '&': '7',
    '8': '8', '*': '8',
    '9': '9', '(': '9',
    '0': '0', ')': '0',
    '-': '-', '_': '-',
    '=': '=', '+': '=',
    'q': 'q', 'Q': 'q',
    'w': 'w', 'W': 'w',
    'e': 'e', 'E': 'e',
    'r': 'r', 'R': 'r',
    't': 't', 'T': 't',
    'y': 'y', 'Y': 'y',
    'u': 'u', 'U': 'u',
    'i': 'i', 'I': 'i',
    'o': 'o', 'O': 'o',
    'p': 'p', 'P': 'p',
    '[': '[', '{': '[',
    ']': ']', '}': ']',
    '\\': '\\', '|': '\\',
    'a': 'a', 'A': 'a',
    's': 's', 'S': 's',
    'd': 'd', 'D': 'd',
    'f': 'f', 'F': 'f',
    'g': 'g', 'G': 'g',
    'h': 'h', 'H': 'h',
    'j': 'j', 'J': 'j',
    'k': 'k', 'K': 'k',
    'l': 'l', 'L': 'l',
    ';': ';', ':': ';',
    "'": "'", '"': "'",
    'z': 'z', 'Z': 'z',
    'x': 'x', 'X': 'x',
    'c': 'c', 'C': 'c',
    'v': 'v', 'V': 'v',
    'b': 'b', 'B': 'b',
    'n': 'n', 'N': 'n',
    'm': 'm', 'M': 'm',
    ',': ',', '<': ',',
    '.': '.', '>': '.',
    '/': '/', '?': '/',
    ' ': 'Space'
}
