import torch
import torch.nn as nn
import numpy as np
import librosa
from transformers import Wav2Vec2Model, Wav2Vec2Processor
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class AudioFeatureExtractor(nn.Module):
    def __init__(
        self,
        model_name: str = "facebook/wav2vec2-base-960h",
        output_dim: int = 768,
        emotion_dim: int = 7,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        super().__init__()
        self.device = device
        self.output_dim = output_dim
        
        try:
            self.processor = Wav2Vec2Processor.from_pretrained(model_name)
            self.model = Wav2Vec2Model.from_pretrained(model_name)
            self.model = self.model.to(self.device)
            self.model.eval()
            logger.info(f"Wav2Vec2 model loaded successfully on {self.device}")
        except Exception as e:
            logger.warning(f"Failed to load Wav2Vec2 model: {e}. Using mock mode.")
            self.processor = None
            self.model = None
        
        self.emotion_head = nn.Sequential(
            nn.Linear(output_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, emotion_dim)
        ).to(self.device)
        
        self.valence_arousal_head = nn.Sequential(
            nn.Linear(output_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 2),
            nn.Tanh()
        ).to(self.device)

    def preprocess_audio(
        self,
        audio_path: str,
        target_sr: int = 16000,
        max_duration: int = 60
    ) -> np.ndarray:
        audio, sr = librosa.load(audio_path, sr=target_sr, duration=max_duration)
        if len(audio) > target_sr * max_duration:
            audio = audio[:target_sr * max_duration]
        return audio

    @torch.no_grad()
    def extract_features(
        self,
        audio: np.ndarray,
        sampling_rate: int = 16000,
        return_sequence: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if self.model is None:
            batch_size = 1
            seq_len = min(len(audio) // 320, 500) if return_sequence else 1
            features = torch.randn(batch_size, seq_len, self.output_dim, device=self.device) * 0.1
            emotion_logits = torch.randn(batch_size, 7, device=self.device) * 0.1
            va = torch.randn(batch_size, 2, device=self.device) * 0.5
            return features, emotion_logits, va
        
        inputs = self.processor(
            audio,
            sampling_rate=sampling_rate,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            hidden_states = outputs.last_hidden_state
            
            if return_sequence:
                features = hidden_states
            else:
                features = torch.mean(hidden_states, dim=1)
            
            pooled_features = torch.mean(hidden_states, dim=1)
            emotion_logits = self.emotion_head(pooled_features)
            va = self.valence_arousal_head(pooled_features)
        
        return features, emotion_logits, va

    def get_emotion_probabilities(self, logits: torch.Tensor) -> dict:
        probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
        emotions = ['anger', 'joy', 'sadness', 'surprise', 'disgust', 'fear', 'neutral']
        return {emotions[i]: float(probs[i]) for i in range(7)}

    def __call__(self, audio_path: str, return_sequence: bool = False):
        audio = self.preprocess_audio(audio_path)
        features, emotion_logits, va = self.extract_features(
            audio, return_sequence=return_sequence
        )
        emotion_probs = self.get_emotion_probabilities(emotion_logits)
        va_values = va.cpu().numpy()[0]
        
        return {
            'features': features.cpu().numpy(),
            'emotion_probabilities': emotion_probs,
            'valence': float(va_values[0]),
            'arousal': float(va_values[1])
        }


class AudioStreamProcessor:
    def __init__(self, extractor: AudioFeatureExtractor, chunk_size: int = 16000):
        self.extractor = extractor
        self.chunk_size = chunk_size
        self.buffer = []

    def process_chunk(self, audio_chunk: np.ndarray) -> dict:
        self.buffer.extend(audio_chunk.tolist())
        
        if len(self.buffer) >= self.chunk_size:
            audio = np.array(self.buffer[:self.chunk_size], dtype=np.float32)
            self.buffer = self.buffer[self.chunk_size // 2:]
            
            features, emotion_logits, va = self.extractor.extract_features(
                audio, return_sequence=False
            )
            emotion_probs = self.extractor.get_emotion_probabilities(emotion_logits)
            va_values = va.cpu().numpy()[0]
            
            return {
                'features': features.cpu().numpy()[0],
                'emotion_probabilities': emotion_probs,
                'valence': float(va_values[0]),
                'arousal': float(va_values[1])
            }
        
        return None
