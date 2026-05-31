import os
import json
import random
import numpy as np
from scipy.io import wavfile
from scipy import signal
from typing import Optional, Tuple, List, Dict, Any


class AudioSynthesizer:
    """古琴音频合成服务，支持散音、按音、泛音三种技法的音频合成。"""

    def __init__(self, sample_rate: int = 44100, samples_dir: Optional[str] = None, style: str = "traditional"):
        """
        初始化音频合成器。

        Args:
            sample_rate: 采样率，默认44100Hz
            samples_dir: 采样音频文件目录，如无则使用合成音色
            style: 流派风格，默认为传统风格
        """
        self.sample_rate = sample_rate
        self.samples_dir = samples_dir
        self._samples_cache: Dict[str, np.ndarray] = {}
        self._dictionary = self._load_dictionary()
        self.current_style = style
        self._style_params = self._initialize_style_params()

    def _load_dictionary(self) -> dict:
        """加载映射表字典。"""
        dict_path = os.path.join(os.path.dirname(__file__), 'dictionary.json')
        with open(dict_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_sample(self, string_id: str, technique: str) -> Optional[np.ndarray]:
        """
        加载对应弦和技法的采样音频。

        Args:
            string_id: 弦标识（如"一"、"二"等）
            technique: 技法名称（如"sanyin"、"anyin"、"fanyin"）

        Returns:
            采样音频数组，如果没有采样文件返回None
        """
        if not self.samples_dir:
            return None

        cache_key = f"{string_id}_{technique}"
        if cache_key in self._samples_cache:
            return self._samples_cache[cache_key]

        sample_path = os.path.join(self.samples_dir, f"{string_id}_{technique}.wav")
        if not os.path.exists(sample_path):
            return None

        try:
            sr, audio = wavfile.read(sample_path)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if sr != self.sample_rate:
                audio = signal.resample(audio, int(len(audio) * self.sample_rate / sr))
            audio = audio.astype(np.float32) / 32767.0
            self._samples_cache[cache_key] = audio
            return audio
        except Exception as e:
            print(f"加载采样文件失败 {sample_path}: {e}")
            return None

    def apply_envelope(
        self,
        audio: np.ndarray,
        attack: float = 0.01,
        decay: float = 0.1,
        sustain: float = 0.7,
        release: float = 0.3
    ) -> np.ndarray:
        """
        应用ADSR包络到音频信号。

        Args:
            audio: 输入音频数组
            attack: 起音时间（秒）
            decay: 衰减时间（秒）
            sustain: 持续电平（0.0-1.0）
            release: 释放时间（秒）

        Returns:
            应用包络后的音频数组
        """
        total_samples = len(audio)
        envelope = np.ones(total_samples, dtype=np.float32)

        attack_samples = int(attack * self.sample_rate)
        decay_samples = int(decay * self.sample_rate)
        release_samples = int(release * self.sample_rate)

        if attack_samples > 0:
            envelope[:attack_samples] = np.linspace(0, 1, attack_samples, dtype=np.float32)

        if decay_samples > 0 and attack_samples + decay_samples < total_samples:
            decay_start = attack_samples
            decay_end = attack_samples + decay_samples
            envelope[decay_start:decay_end] = np.linspace(1, sustain, decay_samples, dtype=np.float32)

        if release_samples > 0:
            release_start = max(0, total_samples - release_samples)
            envelope[release_start:] = np.linspace(sustain, 0, release_samples, dtype=np.float32)

        if attack_samples + decay_samples < total_samples - release_samples:
            sustain_start = attack_samples + decay_samples
            sustain_end = total_samples - release_samples
            envelope[sustain_start:sustain_end] = sustain

        return audio * envelope

    def _midi_to_frequency(self, midi_number: int) -> float:
        """将MIDI编号转换为频率（Hz）。"""
        return 440.0 * (2.0 ** ((midi_number - 69) / 12.0))

    def _get_string_timbre_params(self, string_id: Optional[str]) -> Dict[str, Any]:
        """
        获取不同弦的音色参数，体现各弦的独特音色。
        
        古琴七弦特点：
        - 一弦（最粗）：低沉、浑厚、余韵悠长，谐波丰富
        - 二-三弦：中音区，音色饱满
        - 四-五弦：中高音区，音色明亮
        - 六-七弦（最细）：清脆、明亮、穿透力强，高频丰富
        
        Args:
            string_id: 弦标识（"一"到"七"）
            
        Returns:
            包含谐波权重、包络参数、亮度、衰减等参数的字典
        """
        string_params = {
            "一": {
                "description": "一弦（最粗）- 低沉浑厚",
                "brightness": 0.3,
                "decay": 0.8,
                "harmonic_weights": [1.0, 0.7, 0.5, 0.35, 0.2, 0.12, 0.08],
                "envelope_override": None,
                "low_boost": 3.0,
                "high_cut": 2000,
                "inharmonicity": 0.001
            },
            "二": {
                "description": "二弦 - 饱满深沉",
                "brightness": 0.4,
                "decay": 0.75,
                "harmonic_weights": [1.0, 0.65, 0.45, 0.3, 0.18, 0.1, 0.06],
                "envelope_override": None,
                "low_boost": 2.0,
                "high_cut": 3000,
                "inharmonicity": 0.0015
            },
            "三": {
                "description": "三弦 - 饱满温暖",
                "brightness": 0.5,
                "decay": 0.7,
                "harmonic_weights": [1.0, 0.6, 0.4, 0.28, 0.16, 0.09, 0.05],
                "envelope_override": None,
                "low_boost": 1.5,
                "high_cut": 4000,
                "inharmonicity": 0.002
            },
            "四": {
                "description": "四弦 - 温润明亮",
                "brightness": 0.6,
                "decay": 0.65,
                "harmonic_weights": [1.0, 0.55, 0.35, 0.25, 0.15, 0.08, 0.04],
                "envelope_override": None,
                "low_boost": 1.2,
                "high_cut": 5000,
                "inharmonicity": 0.0025
            },
            "五": {
                "description": "五弦 - 明亮通透",
                "brightness": 0.7,
                "decay": 0.6,
                "harmonic_weights": [1.0, 0.5, 0.3, 0.22, 0.14, 0.07, 0.035],
                "envelope_override": None,
                "low_boost": 1.0,
                "high_cut": 6000,
                "inharmonicity": 0.003
            },
            "六": {
                "description": "六弦 - 清脆亮丽",
                "brightness": 0.8,
                "decay": 0.55,
                "harmonic_weights": [1.0, 0.45, 0.28, 0.2, 0.13, 0.065, 0.03],
                "envelope_override": None,
                "low_boost": 0.8,
                "high_cut": 7000,
                "inharmonicity": 0.0035
            },
            "七": {
                "description": "七弦（最细）- 清脆尖锐",
                "brightness": 0.9,
                "decay": 0.5,
                "harmonic_weights": [1.0, 0.4, 0.25, 0.18, 0.12, 0.06, 0.025],
                "envelope_override": None,
                "low_boost": 0.5,
                "high_cut": 8000,
                "inharmonicity": 0.004
            }
        }
        
        if string_id and string_id in string_params:
            return string_params[string_id]
        
        return {
            "description": "默认弦参数",
            "brightness": 0.6,
            "decay": 0.65,
            "harmonic_weights": [1.0, 0.55, 0.35, 0.25, 0.15],
            "envelope_override": None,
            "low_boost": 1.0,
            "high_cut": 5000,
            "inharmonicity": 0.0025
        }

    def _get_technique_base_params(self, technique: str) -> Dict[str, Any]:
        """获取技法的基础参数"""
        params = {
            "sanyin": {
                "name": "散音",
                "base_harmonics": [1.0, 0.6, 0.3, 0.15, 0.08],
                "envelope": (0.005, 0.15, 0.4, 0.5),
                "vibrato": False,
                "noise_amount": 0.0
            },
            "anyin": {
                "name": "按音",
                "base_harmonics": [1.0, 0.5, 0.25, 0.1],
                "envelope": (0.008, 0.12, 0.5, 0.4),
                "vibrato": True,
                "vibrato_freq": 5.0,
                "vibrato_depth": 0.02,
                "noise_amount": 0.0
            },
            "fanyin": {
                "name": "泛音",
                "base_harmonics": [0.2, 0.8, 0.6, 0.3, 0.15],
                "envelope": (0.002, 0.08, 0.3, 0.6),
                "vibrato": False,
                "noise_amount": 0.01
            }
        }
        return params.get(technique, params["sanyin"])

    def _initialize_style_params(self) -> Dict[str, Any]:
        """初始化各流派的合成参数配置"""
        return {
            "traditional": {
                "name": "传统风格",
                "description": "经典传统演奏风格，中正平和",
                "tempo_modulation": 1.0,
                "vibrato_intensity": 1.0,
                "vibrato_rate": 1.0,
                "glissando_smoothness": 1.0,
                "harmonic_emphasis": 1.0,
                "attack_smoothness": 1.0,
                "decay_extension": 1.0,
                "reverb_amount": 0.3,
                "brightness_correction": 1.0,
                "note_gap": 0.05,
                "rubato": 0.0,
                "technique_params": {
                    "sanyin": {"attack_multiplier": 1.0, "decay_multiplier": 1.0},
                    "anyin": {"vibrato_multiplier": 1.0, "glissando_multiplier": 1.0},
                    "fanyin": {"purity_multiplier": 1.0, "attack_multiplier": 1.0}
                }
            },
            "guangling": {
                "name": "广陵派",
                "description": "江苏扬州流派，风格跌宕起伏、绮丽细腻",
                "tempo_modulation": 0.9,
                "vibrato_intensity": 1.3,
                "vibrato_rate": 0.9,
                "glissando_smoothness": 1.4,
                "harmonic_emphasis": 1.2,
                "attack_smoothness": 0.8,
                "decay_extension": 1.3,
                "reverb_amount": 0.45,
                "brightness_correction": 0.9,
                "note_gap": 0.08,
                "rubato": 0.2,
                "technique_params": {
                    "sanyin": {"attack_multiplier": 0.8, "decay_multiplier": 1.4},
                    "anyin": {"vibrato_multiplier": 1.4, "glissando_multiplier": 1.5},
                    "fanyin": {"purity_multiplier": 1.3, "attack_multiplier": 0.7}
                }
            },
            "yushan": {
                "name": "虞山派",
                "description": "江苏常熟流派，风格清微淡远、博大和平",
                "tempo_modulation": 1.05,
                "vibrato_intensity": 0.7,
                "vibrato_rate": 0.85,
                "glissando_smoothness": 0.8,
                "harmonic_emphasis": 0.9,
                "attack_smoothness": 1.2,
                "decay_extension": 0.9,
                "reverb_amount": 0.25,
                "brightness_correction": 1.05,
                "note_gap": 0.03,
                "rubato": 0.05,
                "technique_params": {
                    "sanyin": {"attack_multiplier": 1.1, "decay_multiplier": 0.9},
                    "anyin": {"vibrato_multiplier": 0.6, "glissando_multiplier": 0.7},
                    "fanyin": {"purity_multiplier": 1.1, "attack_multiplier": 1.1}
                }
            },
            "meian": {
                "name": "梅庵派",
                "description": "山东诸城流派，风格刚劲明快、气势雄浑",
                "tempo_modulation": 1.15,
                "vibrato_intensity": 1.1,
                "vibrato_rate": 1.15,
                "glissando_smoothness": 1.1,
                "harmonic_emphasis": 1.1,
                "attack_smoothness": 0.7,
                "decay_extension": 0.85,
                "reverb_amount": 0.35,
                "brightness_correction": 1.15,
                "note_gap": 0.02,
                "rubato": 0.1,
                "technique_params": {
                    "sanyin": {"attack_multiplier": 1.3, "decay_multiplier": 0.8},
                    "anyin": {"vibrato_multiplier": 1.2, "glissando_multiplier": 1.1},
                    "fanyin": {"purity_multiplier": 0.9, "attack_multiplier": 1.2}
                }
            },
            "zhucheng": {
                "name": "诸城派",
                "description": "山东诸城流派，风格清丽和雅、厚重朴实",
                "tempo_modulation": 1.0,
                "vibrato_intensity": 0.9,
                "vibrato_rate": 1.0,
                "glissando_smoothness": 0.9,
                "harmonic_emphasis": 1.0,
                "attack_smoothness": 1.0,
                "decay_extension": 1.0,
                "reverb_amount": 0.3,
                "brightness_correction": 1.0,
                "note_gap": 0.04,
                "rubato": 0.08,
                "technique_params": {
                    "sanyin": {"attack_multiplier": 1.0, "decay_multiplier": 1.0},
                    "anyin": {"vibrato_multiplier": 0.9, "glissando_multiplier": 0.95},
                    "fanyin": {"purity_multiplier": 1.0, "attack_multiplier": 1.0}
                }
            },
            "jiuyi": {
                "name": "九嶷派",
                "description": "湖南九嶷山流派，风格苍劲坚实、清丽秀雅",
                "tempo_modulation": 0.95,
                "vibrato_intensity": 1.2,
                "vibrato_rate": 1.05,
                "glissando_smoothness": 1.2,
                "harmonic_emphasis": 1.15,
                "attack_smoothness": 0.9,
                "decay_extension": 1.15,
                "reverb_amount": 0.4,
                "brightness_correction": 0.95,
                "note_gap": 0.06,
                "rubato": 0.15,
                "technique_params": {
                    "sanyin": {"attack_multiplier": 0.9, "decay_multiplier": 1.2},
                    "anyin": {"vibrato_multiplier": 1.3, "glissando_multiplier": 1.3},
                    "fanyin": {"purity_multiplier": 1.2, "attack_multiplier": 0.85}
                }
            },
            "shushan": {
                "name": "蜀山派",
                "description": "四川青城山流派，风格刚柔相济、飘逸洒脱",
                "tempo_modulation": 1.05,
                "vibrato_intensity": 1.0,
                "vibrato_rate": 1.1,
                "glissando_smoothness": 1.15,
                "harmonic_emphasis": 1.05,
                "attack_smoothness": 0.95,
                "decay_extension": 1.1,
                "reverb_amount": 0.38,
                "brightness_correction": 1.02,
                "note_gap": 0.05,
                "rubato": 0.12,
                "technique_params": {
                    "sanyin": {"attack_multiplier": 0.95, "decay_multiplier": 1.1},
                    "anyin": {"vibrato_multiplier": 1.1, "glissando_multiplier": 1.2},
                    "fanyin": {"purity_multiplier": 1.1, "attack_multiplier": 0.95}
                }
            }
        }

    def get_available_styles(self) -> List[Dict[str, Any]]:
        """获取所有可用的古琴流派风格"""
        return [
            {
                "id": style_id,
                "name": params["name"],
                "description": params["description"]
            }
            for style_id, params in self._style_params.items()
        ]

    def set_style(self, style_id: str) -> bool:
        """
        切换合成风格流派。

        Args:
            style_id: 流派ID（如"guangling"、"yushan"等）

        Returns:
            是否切换成功
        """
        if style_id in self._style_params:
            self.current_style = style_id
            return True
        return False

    def get_current_style(self) -> Dict[str, Any]:
        """获取当前使用的流派风格信息"""
        style = self._style_params.get(self.current_style, self._style_params["traditional"])
        return {
            "id": self.current_style,
            "name": style["name"],
            "description": style["description"],
            "params": style
        }

    def _apply_style_modulation(
        self,
        audio: np.ndarray,
        technique: str,
        frequency: float,
        duration: float,
        t: np.ndarray
    ) -> np.ndarray:
        """应用流派风格调制效果"""
        style = self._style_params.get(self.current_style, self._style_params["traditional"])
        tech_params = style["technique_params"].get(technique, {})
        
        result = audio.copy()
        
        vibrato_intensity = style["vibrato_intensity"] * tech_params.get("vibrato_multiplier", 1.0)
        vibrato_rate = style["vibrato_rate"] * 5.0
        
        if technique == "anyin" and vibrato_intensity > 0:
            vibrato_start = int(0.1 * len(t))
            if vibrato_start < len(t):
                vibrato_env = np.ones_like(t)
                vibrato_env[:vibrato_start] = np.linspace(0, 1, vibrato_start)
                vibrato = np.sin(2 * np.pi * vibrato_rate * t) * 0.02 * vibrato_intensity * vibrato_env
                freq_modulation = frequency * (1 + vibrato)
                phase = np.cumsum(2 * np.pi * freq_modulation / self.sample_rate)
                result = np.abs(result) * np.sin(phase)
        
        glissando_smoothness = style["glissando_smoothness"] * tech_params.get("glissando_multiplier", 1.0)
        if technique == "anyin" and glissando_smoothness > 1.0:
            window = np.hanning(int(0.1 * self.sample_rate))
            window = window / np.sum(window)
            result = np.convolve(result, window, mode='same')
        
        harmonic_emphasis = style["harmonic_emphasis"]
        if harmonic_emphasis != 1.0:
            from scipy.signal import butter, lfilter
            nyquist = self.sample_rate / 2
            cutoff = 2000 * harmonic_emphasis
            cutoff = min(cutoff, nyquist * 0.9)
            b, a = butter(2, cutoff / nyquist, btype='low')
            result = lfilter(b, a, result)
        
        attack_smoothness = style["attack_smoothness"] * tech_params.get("attack_multiplier", 1.0)
        if attack_smoothness != 1.0:
            attack_len = int(0.01 * self.sample_rate * attack_smoothness)
            if attack_len > 0 and attack_len < len(result):
                attack_env = np.linspace(0, 1, attack_len)
                result[:attack_len] *= attack_env
        
        decay_extension = style["decay_extension"] * tech_params.get("decay_multiplier", 1.0)
        if decay_extension != 1.0:
            decay_start = int(0.3 * len(t))
            if decay_start < len(t):
                decay_env = np.ones_like(t)
                decay_t = np.linspace(0, 1, len(t) - decay_start)
                decay_env[decay_start:] = np.exp(-decay_t * 3 / decay_extension)
                result *= decay_env
        
        brightness_correction = style["brightness_correction"]
        if brightness_correction != 1.0:
            from scipy.signal import butter, lfilter
            nyquist = self.sample_rate / 2
            if brightness_correction > 1.0:
                cutoff = 3000 / brightness_correction
                b, a = butter(2, cutoff / nyquist, btype='high')
            else:
                cutoff = 4000 * brightness_correction
                b, a = butter(2, cutoff / nyquist, btype='low')
            result = lfilter(b, a, result)
        
        return result

    def _apply_string_filter(self, audio: np.ndarray, string_params: Dict[str, Any]) -> np.ndarray:
        """应用弦特性滤波器，模拟不同弦的音色"""
        from scipy.signal import butter, lfilter
        
        nyquist = self.sample_rate / 2
        high_cut = min(string_params.get("high_cut", 8000), nyquist * 0.9)
        low_boost = string_params.get("low_boost", 1.0)
        
        if high_cut < nyquist:
            order = 4
            normal_cutoff = high_cut / nyquist
            b, a = butter(order, normal_cutoff, btype='low', analog=False)
            audio = lfilter(b, a, audio)
        
        if low_boost != 1.0:
            low_cutoff = 200 / nyquist
            b_low, a_low = butter(2, low_cutoff, btype='low', analog=False)
            low_component = lfilter(b_low, a_low, audio)
            audio = audio + (low_boost - 1.0) * low_component
        
        return audio

    def _generate_guqin_timbre(
        self,
        frequency: float,
        duration: float,
        technique: str,
        string_id: Optional[str] = None
    ) -> np.ndarray:
        """
        使用正弦波合成模拟古琴音色，结合弦特性和演奏技法。

        Args:
            frequency: 基频（Hz）
            duration: 持续时间（秒）
            technique: 技法类型
            string_id: 弦标识，用于调整音色

        Returns:
            合成的音频数组
        """
        t = np.linspace(0, duration, int(self.sample_rate * duration), dtype=np.float32)
        
        technique_params = self._get_technique_base_params(technique)
        string_params = self._get_string_timbre_params(string_id)
        
        base_harmonics = technique_params["base_harmonics"]
        string_harmonics = string_params["harmonic_weights"]
        
        max_harmonics = max(len(base_harmonics), len(string_harmonics))
        harmonic_weights = []
        for i in range(max_harmonics):
            base_w = base_harmonics[i] if i < len(base_harmonics) else 0.0
            string_w = string_harmonics[i] if i < len(string_harmonics) else 0.0
            brightness = string_params.get("brightness", 0.6)
            if i == 0:
                weight = base_w * string_w
            else:
                brightness_factor = brightness ** i
                weight = base_w * string_w * brightness_factor
            harmonic_weights.append(weight)
        
        total_weight = sum(harmonic_weights)
        if total_weight > 0:
            harmonic_weights = [w / total_weight * 2 for w in harmonic_weights]
        
        envelope_params = technique_params["envelope"]
        if string_params.get("envelope_override"):
            envelope_params = string_params["envelope_override"]
        
        string_decay = string_params.get("decay", 0.65)
        attack, decay, sustain, release = envelope_params
        decay = decay * (1.0 + (1.0 - string_decay) * 0.5)
        release = release * (1.0 + (1.0 - string_decay) * 0.3)
        
        inharmonicity = string_params.get("inharmonicity", 0.002)
        
        audio = np.zeros_like(t)
        for i, weight in enumerate(harmonic_weights):
            n = i + 1
            inharmonic_shift = 1.0 + inharmonicity * n * n
            harmonic_freq = frequency * n * inharmonic_shift
            phase = random.uniform(0, 2 * np.pi) if i > 0 else 0
            audio += weight * np.sin(2 * np.pi * harmonic_freq * t + phase)
        
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio))
        
        audio = self._apply_string_filter(audio, string_params)
        
        if technique_params.get("vibrato", False):
            vibrato_freq = technique_params.get("vibrato_freq", 5.0)
            vibrato_depth = technique_params.get("vibrato_depth", 0.02)
            string_vibrato_factor = 0.8 + string_params.get("brightness", 0.6) * 0.4
            vibrato = 1.0 + vibrato_depth * string_vibrato_factor * np.sin(2 * np.pi * vibrato_freq * t)
            audio = audio * vibrato
        
        noise_amount = technique_params.get("noise_amount", 0.0)
        if noise_amount > 0:
            noise = np.random.randn(len(t)) * noise_amount
            noise_envelope = np.exp(-t * 50)
            audio = audio + noise * noise_envelope
        
        audio = self._apply_style_modulation(audio, technique, frequency, duration, t)
        
        audio = self.apply_envelope(audio, attack, decay, sustain, release)
        
        return audio

    def synthesize_note(
        self,
        midi_number: int,
        technique: str,
        duration: float,
        string_id: Optional[str] = None
    ) -> np.ndarray:
        """
        合成单个音符，结合弦特性实现不同弦的音色差异。

        Args:
            midi_number: MIDI编号
            technique: 技法类型（sanyin/anyin/fanyin）
            duration: 持续时间（秒）
            string_id: 可选的弦标识，用于加载采样和调整音色

        Returns:
            合成的音频数组
        """
        string_params = self._get_string_timbre_params(string_id)
        technique_params = self._get_technique_base_params(technique)
        
        sample = None
        if string_id:
            sample = self.load_sample(string_id, technique)

        if sample is not None:
            frequency = self._midi_to_frequency(midi_number)
            original_freq = self._midi_to_frequency(60)
            pitch_shift = frequency / original_freq

            if abs(pitch_shift - 1.0) > 0.01:
                new_length = int(len(sample) / pitch_shift)
                audio = signal.resample(sample, new_length)
            else:
                audio = sample.copy()

            target_length = int(duration * self.sample_rate)
            if len(audio) > target_length:
                audio = audio[:target_length]
            else:
                audio = np.pad(audio, (0, target_length - len(audio)))
            
            audio = self._apply_string_filter(audio, string_params)
            
            attack, decay, sustain, release = technique_params["envelope"]
            string_decay = string_params.get("decay", 0.65)
            decay = decay * (1.0 + (1.0 - string_decay) * 0.5)
            release = release * (1.0 + (1.0 - string_decay) * 0.3)
            
            audio = self.apply_envelope(audio, attack, decay, sustain, release)
        else:
            frequency = self._midi_to_frequency(midi_number)
            audio = self._generate_guqin_timbre(frequency, duration, technique, string_id)

        return audio

    def synthesize_sequence(
        self,
        jianzi_list: List[dict],
        tempo: float = 60.0,
        style: Optional[str] = None
    ) -> np.ndarray:
        """
        合成完整的减字谱序列，支持流派风格参数。

        Args:
            jianzi_list: 减字谱对象列表，每个对象包含midi、technique、duration、string等字段
            tempo: 速度（拍/分钟）
            style: 可选流派风格ID，如不指定则使用当前设置的风格

        Returns:
            合成的完整音频数组
        """
        if not jianzi_list or len(jianzi_list) == 0:
            return np.zeros(int(0.5 * self.sample_rate), dtype=np.float32)
        
        if style:
            self.set_style(style)
        
        style_params = self._style_params.get(self.current_style, self._style_params["traditional"])
        tempo_modulation = style_params.get("tempo_modulation", 1.0)
        note_gap = style_params.get("note_gap", 0.05)
        rubato = style_params.get("rubato", 0.0)
        reverb_amount = style_params.get("reverb_amount", 0.3)
        
        adjusted_tempo = tempo * tempo_modulation
        beat_duration = 60.0 / adjusted_tempo
        audio_segments = []

        for i, jianzi in enumerate(jianzi_list):
            midi_number = jianzi.get('midi', 60)
            technique = jianzi.get('technique', 'sanyin')
            base_duration = jianzi.get('duration', 1.0) * beat_duration
            
            rubato_factor = 1.0
            if rubato > 0:
                rubato_factor = 1.0 + random.uniform(-rubato, rubato) * 0.3
            duration = base_duration * rubato_factor
            
            string_id = jianzi.get('string', None)
            rest_before = jianzi.get('rest_before', 0.0) * beat_duration

            if rest_before > 0:
                rest_samples = int(rest_before * self.sample_rate)
                audio_segments.append(np.zeros(rest_samples, dtype=np.float32))

            note_audio = self.synthesize_note(midi_number, technique, duration, string_id)
            audio_segments.append(note_audio)
            
            if note_gap > 0 and i < len(jianzi_list) - 1:
                gap_samples = int(note_gap * self.sample_rate)
                gap_samples = min(gap_samples, int(0.3 * len(note_audio)))
                if gap_samples > 0:
                    fade_env = np.ones(gap_samples, dtype=np.float32)
                    fade_env = np.linspace(1.0, 0.0, gap_samples)
                    audio_segments[-1][-gap_samples:] *= fade_env
                    audio_segments.append(np.zeros(gap_samples, dtype=np.float32))

        if not audio_segments:
            return np.array([], dtype=np.float32)

        full_audio = np.concatenate(audio_segments)
        
        if reverb_amount > 0:
            full_audio = self._apply_reverb(full_audio, reverb_amount)
        
        return full_audio

    def _apply_reverb(self, audio: np.ndarray, amount: float) -> np.ndarray:
        """应用简单的混响效果"""
        if amount <= 0:
            return audio
        
        delay = int(0.1 * self.sample_rate)
        decay = 0.3 * amount
        
        reverb = np.zeros_like(audio)
        for i in range(1, 4):
            delayed = np.zeros_like(audio)
            offset = delay * i
            if offset < len(audio):
                delayed[offset:] = audio[:-offset] * (decay ** i)
                reverb += delayed
        
        result = audio + reverb * amount
        max_val = np.max(np.abs(result))
        if max_val > 0:
            result = result / max_val * np.max(np.abs(audio))
        
        return result.astype(np.float32)

    def save_wav(self, audio: np.ndarray, output_path: str, normalize: bool = True) -> None:
        """
        保存音频为WAV文件。

        Args:
            audio: 音频数组
            output_path: 输出文件路径
            normalize: 是否归一化音频
        """
        if len(audio) == 0:
            audio = np.zeros(int(0.5 * self.sample_rate), dtype=np.float32)
        
        if normalize and len(audio) > 0:
            max_val = np.max(np.abs(audio))
            if max_val > 0:
                audio = audio / max_val * 0.9

        audio_int = (audio * 32767).astype(np.int16)
        wavfile.write(output_path, self.sample_rate, audio_int)

    def get_technique_params(self, technique: str, string_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取指定技法和弦的合成参数。

        Args:
            technique: 技法代码
            string_id: 可选的弦标识，用于获取弦特定的音色参数

        Returns:
            包含ADSR参数、谐波权重、弦参数的字典
        """
        technique_base = {
            "sanyin": {
                "name": "散音",
                "attack": 0.005, "decay": 0.15, "sustain": 0.4, "release": 0.5,
                "harmonics": [1.0, 0.6, 0.3, 0.15, 0.08]
            },
            "anyin": {
                "name": "按音",
                "attack": 0.008, "decay": 0.12, "sustain": 0.5, "release": 0.4,
                "harmonics": [1.0, 0.5, 0.25, 0.1]
            },
            "fanyin": {
                "name": "泛音",
                "attack": 0.002, "decay": 0.08, "sustain": 0.3, "release": 0.6,
                "harmonics": [0.2, 0.8, 0.6, 0.3, 0.15]
            }
        }
        
        params = technique_base.get(technique, technique_base["sanyin"]).copy()
        
        if string_id:
            string_params = self._get_string_timbre_params(string_id)
            params["string_params"] = string_params
            params["description"] = f"{technique_base.get(technique, technique_base['sanyin'])['name']} - {string_params.get('description', '默认弦')}"
            
            string_decay = string_params.get("decay", 0.65)
            params["decay"] = params["decay"] * (1.0 + (1.0 - string_decay) * 0.5)
            params["release"] = params["release"] * (1.0 + (1.0 - string_decay) * 0.3)
        
        return params
