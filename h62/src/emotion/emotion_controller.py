import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, List, Tuple, Optional, Union
import os


class EmotionEmbedding(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        emotion_config = config["emotion"]
        
        self.emotions = emotion_config["emotions"]
        self.num_emotions = len(self.emotions)
        self.emotion_embedding_dim = emotion_config["emotion_embedding_dim"]
        self.min_intensity = emotion_config["min_intensity"]
        self.max_intensity = emotion_config["max_intensity"]
        
        self.emotion_embeddings = nn.Embedding(
            self.num_emotions,
            self.emotion_embedding_dim,
        )
        
        nn.init.normal_(self.emotion_embeddings.weight, mean=0, std=0.02)
        
        self.emotion_to_idx = {emotion: idx for idx, emotion in enumerate(self.emotions)}
        self.idx_to_emotion = {idx: emotion for idx, emotion in enumerate(self.emotions)}

    def forward(
        self,
        emotion_indices: torch.Tensor,
        intensity: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        embeddings = self.emotion_embeddings(emotion_indices)
        
        if intensity is not None:
            intensity = intensity.unsqueeze(-1)
            embeddings = embeddings * intensity
        
        return embeddings

    def get_emotion_embedding(
        self,
        emotion: str,
        intensity: float = 1.0,
    ) -> torch.Tensor:
        if emotion not in self.emotion_to_idx:
            raise ValueError(f"Unknown emotion: {emotion}. Available emotions: {self.emotions}")
        
        idx = self.emotion_to_idx[emotion]
        intensity = max(self.min_intensity, min(self.max_intensity, intensity))
        
        idx_tensor = torch.tensor([idx], dtype=torch.long)
        intensity_tensor = torch.tensor([intensity], dtype=torch.float32)
        
        return self.forward(idx_tensor, intensity_tensor).squeeze(0)

    def mix_emotions(
        self,
        emotion_weights: Dict[str, float],
    ) -> torch.Tensor:
        total_weight = sum(emotion_weights.values())
        if abs(total_weight - 1.0) > 1e-6:
            emotion_weights = {k: v / total_weight for k, v in emotion_weights.items()}
        
        mixed_embedding = torch.zeros(self.emotion_embedding_dim, dtype=torch.float32)
        
        for emotion, weight in emotion_weights.items():
            if emotion not in self.emotion_to_idx:
                raise ValueError(f"Unknown emotion: {emotion}")
            emb = self.get_emotion_embedding(emotion, 1.0)
            mixed_embedding += weight * emb
        
        return mixed_embedding


class ProsodyRegulator(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        emotion_config = config["emotion"]
        
        self.prosody_dim = emotion_config["prosody_dim"]
        self.emotion_embedding_dim = emotion_config["emotion_embedding_dim"]
        self.hidden_dim = 128
        
        self.prosody_predictor = nn.Sequential(
            nn.Linear(self.emotion_embedding_dim, self.hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(self.hidden_dim, self.hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(self.hidden_dim, self.prosody_dim),
        )
        
        self.register_buffer(
            "emotion_prosody_means",
            torch.tensor([
                [0.0, 1.0, 1.0],
                [1.2, 1.3, 0.9],
                [-1.0, 0.7, 1.3],
                [1.8, 1.5, 0.7],
                [1.5, 1.2, 0.85],
            ], dtype=torch.float32)
        )
        
        self.register_buffer(
            "emotion_prosody_ranges",
            torch.tensor([
                [0.5, 0.2, 0.1],
                [0.8, 0.3, 0.15],
                [0.5, 0.2, 0.2],
                [1.0, 0.4, 0.15],
                [0.8, 0.25, 0.1],
            ], dtype=torch.float32)
        )

    def forward(
        self,
        emotion_embedding: torch.Tensor,
        emotion_idx: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        prosody_params = self.prosody_predictor(emotion_embedding)
        
        if emotion_idx is not None:
            base_prosody = self.emotion_prosody_means[emotion_idx]
            prosody_params = prosody_params + base_prosody
        
        return prosody_params

    def predict_prosody_from_emotion(
        self,
        emotion_embedding: torch.Tensor,
        intensity: float = 1.0,
        emotion_idx: Optional[int] = None,
    ) -> torch.Tensor:
        emotion_idx_tensor = None
        if emotion_idx is not None:
            emotion_idx_tensor = torch.tensor([emotion_idx], dtype=torch.long)
        
        prosody = self.forward(
            emotion_embedding.unsqueeze(0), 
            emotion_idx_tensor
        ).squeeze(0)
        
        saturated_intensity = self._saturate_intensity(intensity)
        
        if emotion_idx is not None:
            prosody_means = self.emotion_prosody_means[emotion_idx]
            deviation = prosody - prosody_means
            deviation = deviation * saturated_intensity
            prosody = prosody_means + deviation
            
            prosody_ranges = self.emotion_prosody_ranges[emotion_idx]
            min_vals = prosody_means - prosody_ranges
            max_vals = prosody_means + prosody_ranges
            prosody = torch.clamp(prosody, min_vals, max_vals)
        else:
            prosody = prosody * saturated_intensity
        
        return prosody
    
    def _saturate_intensity(self, intensity: float) -> float:
        alpha = 3.0
        scaled = intensity * alpha
        saturated = 2.0 / (1.0 + np.exp(-scaled)) - 1.0
        return max(0.0, min(1.5, saturated))
    
    def _smooth_pitch(self, mel_spectrogram: torch.Tensor, 
                      emotion_idx: Optional[int] = None) -> torch.Tensor:
        if mel_spectrogram.dim() == 2:
            mel = mel_spectrogram.unsqueeze(0)
        else:
            mel = mel_spectrogram
        
        batch_size, n_mels, n_frames = mel.shape
        
        kernel_size = 7
        sigma = 2.0
        
        if emotion_idx == 2:
            kernel_size = 15
            sigma = 4.0
        
        kernel = self._gaussian_kernel(kernel_size, sigma)
        kernel = kernel.repeat(n_mels, 1, 1)
        
        padding = kernel_size // 2
        
        mel_np = mel.cpu().numpy()
        padded_np = np.pad(
            mel_np,
            ((0, 0), (0, 0), (padding, padding)),
            mode='reflect',
        )
        padded = torch.tensor(padded_np, dtype=mel.dtype, device=mel.device)
        
        smoothed = F.conv1d(
            padded,
            kernel,
            groups=n_mels,
        )
        
        if mel_spectrogram.dim() == 2:
            smoothed = smoothed.squeeze(0)
        
        return smoothed
    
    def _gaussian_kernel(self, kernel_size: int, sigma: float) -> torch.Tensor:
        x = torch.arange(kernel_size, dtype=torch.float32)
        x = x - (kernel_size - 1) / 2.0
        kernel = torch.exp(-x**2 / (2 * sigma**2))
        kernel = kernel / kernel.sum()
        return kernel.view(1, 1, -1)

    def adjust_prosody(
        self,
        mel_spectrogram: torch.Tensor,
        pitch_shift: float = 0.0,
        energy_scale: float = 1.0,
        duration_scale: float = 1.0,
        emotion_idx: Optional[int] = None,
        apply_smoothing: bool = True,
    ) -> torch.Tensor:
        adjusted_mel = mel_spectrogram.clone()
        
        if pitch_shift != 0:
            adjusted_mel = adjusted_mel + pitch_shift
        
        if apply_smoothing:
            adjusted_mel = self._smooth_pitch(adjusted_mel, emotion_idx)
        
        if energy_scale != 1.0:
            adjusted_mel = adjusted_mel * energy_scale
        
        if duration_scale != 1.0:
            original_length = adjusted_mel.size(-1)
            new_length = int(original_length * duration_scale)
            new_length = max(new_length, 1)
            adjusted_mel = F.interpolate(
                adjusted_mel.unsqueeze(0),
                size=new_length,
                mode='linear',
                align_corners=False,
            ).squeeze(0)
        
        return adjusted_mel


class EmotionController(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.emotion_embedding = EmotionEmbedding(config)
        self.prosody_regulator = ProsodyRegulator(config)
        
        self.emotions = config["emotion"]["emotions"]
        self.emotion_to_idx = self.emotion_embedding.emotion_to_idx
        self.idx_to_emotion = self.emotion_embedding.idx_to_emotion
        self.num_emotions = len(self.emotions)
        
        self.min_intensity = config["emotion"]["min_intensity"]
        self.max_intensity = config["emotion"]["max_intensity"]

    def get_emotion_embedding(
        self,
        emotion: Union[str, Dict[str, float]],
        intensity: float = 1.0,
    ) -> torch.Tensor:
        if isinstance(emotion, dict):
            return self.emotion_embedding.mix_emotions(emotion)
        else:
            return self.emotion_embedding.get_emotion_embedding(emotion, intensity)

    def get_prosody_features(
        self,
        emotion_embedding: torch.Tensor,
        intensity: float = 1.0,
        emotion_idx: Optional[int] = None,
    ) -> torch.Tensor:
        return self.prosody_regulator.predict_prosody_from_emotion(
            emotion_embedding,
            intensity,
            emotion_idx,
        )

    def process_emotion_input(
        self,
        emotion: Union[str, Dict[str, float]],
        intensity: float = 1.0,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        emotion_emb = self.get_emotion_embedding(emotion, intensity)
        
        emotion_idx = self.get_emotion_idx_from_input(emotion)
        prosody_features = self.get_prosody_features(emotion_emb, intensity, emotion_idx)
        return emotion_emb, prosody_features
    
    def get_emotion_idx_from_input(
        self,
        emotion: Union[str, Dict[str, float]],
    ) -> Optional[int]:
        if isinstance(emotion, str) and emotion in self.emotion_to_idx:
            return self.emotion_to_idx[emotion]
        elif isinstance(emotion, dict):
            if len(emotion) == 1:
                single_emotion = list(emotion.keys())[0]
                if single_emotion in self.emotion_to_idx:
                    return self.emotion_to_idx[single_emotion]
            else:
                weights = list(emotion.values())
                emotions = list(emotion.keys())
                max_idx = weights.index(max(weights))
                dominant_emotion = emotions[max_idx]
                if dominant_emotion in self.emotion_to_idx:
                    return self.emotion_to_idx[dominant_emotion]
        return None

    def parse_emotion_string(
        self,
        emotion_str: str,
    ) -> Tuple[Union[str, Dict[str, float]], float]:
        if "+" in emotion_str:
            parts = emotion_str.split("+")
            emotion_dict = {}
            total_weight = 0.0
            
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                if ":" in part:
                    e, w = part.rsplit(":", 1)
                    emotion_dict[e.strip()] = float(w)
                    total_weight += float(w)
                else:
                    emotion_dict[part] = 1.0
                    total_weight += 1.0
            
            if total_weight > 0 and abs(total_weight - 1.0) > 1e-6:
                emotion_dict = {k: v / total_weight for k, v in emotion_dict.items()}
            
            return emotion_dict, 1.0
        elif ":" in emotion_str:
            parts = emotion_str.rsplit(":", 1)
            emotion = parts[0]
            intensity = float(parts[1])
        else:
            emotion = emotion_str
            intensity = 1.0
        
        return emotion, intensity

    def validate_emotion(self, emotion: str) -> bool:
        if isinstance(emotion, dict):
            return all(e in self.emotions for e in emotion.keys())
        return emotion in self.emotions

    def get_available_emotions(self) -> List[str]:
        return self.emotions

    def get_emotion_idx(self, emotion: str) -> int:
        return self.emotion_to_idx.get(emotion, -1)

    def adjust_intensity(self, intensity: float) -> float:
        return max(self.min_intensity, min(self.max_intensity, intensity))

    def create_mixed_emotion_embedding(
        self,
        emotions: List[str],
        weights: List[float],
        intensities: Optional[List[float]] = None,
    ) -> torch.Tensor:
        if intensities is None:
            intensities = [1.0] * len(emotions)
        
        if len(emotions) != len(weights) or len(emotions) != len(intensities):
            raise ValueError("emotions, weights, and intensities must have the same length")
        
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        mixed_embedding = torch.zeros(
            self.emotion_embedding.emotion_embedding_dim,
            dtype=torch.float32,
        )
        
        for emotion, weight, intensity in zip(emotions, weights, intensities):
            emb = self.get_emotion_embedding(emotion, intensity)
            mixed_embedding += weight * emb
        
        return mixed_embedding

    def get_style_embedding_from_reference(
        self,
        reference_mel: torch.Tensor,
        reference_encoder: nn.Module,
    ) -> torch.Tensor:
        with torch.no_grad():
            style_embedding = reference_encoder(reference_mel.unsqueeze(0))
        return style_embedding.squeeze(0)

    def combine_style_and_emotion(
        self,
        style_embedding: torch.Tensor,
        emotion_embedding: torch.Tensor,
        style_weight: float = 0.5,
    ) -> torch.Tensor:
        combined = style_weight * style_embedding + (1 - style_weight) * emotion_embedding
        return combined

    def save_emotion_embeddings(self, save_path: str) -> None:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        torch.save({
            "emotion_embeddings": self.emotion_embedding.emotion_embeddings.weight.data,
            "emotion_to_idx": self.emotion_to_idx,
            "idx_to_emotion": self.idx_to_emotion,
        }, save_path)

    def load_emotion_embeddings(self, load_path: str) -> None:
        checkpoint = torch.load(load_path, map_location="cpu")
        self.emotion_embedding.emotion_embeddings.weight.data.copy_(
            checkpoint["emotion_embeddings"]
        )
