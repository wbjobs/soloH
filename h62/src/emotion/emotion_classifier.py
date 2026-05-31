import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, List, Tuple, Optional, Union
import os


class EmotionClassifier(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        clf_config = config["classifier"]
        
        self.num_classes = clf_config["num_classes"]
        self.hidden_dim = clf_config["hidden_dim"]
        self.dropout = clf_config["dropout"]
        self.n_mel_channels = config["audio"]["n_mel_channels"]
        
        self.conv_layers = nn.Sequential(
            nn.Conv1d(self.n_mel_channels, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.MaxPool1d(2),
            
            nn.Conv1d(128, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.MaxPool1d(2),
            
            nn.Conv1d(128, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(2),
        )
        
        self.gru = nn.GRU(
            input_size=64,
            hidden_size=self.hidden_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=self.dropout,
        )
        
        self.attention = nn.Sequential(
            nn.Linear(self.hidden_dim * 2, self.hidden_dim),
            nn.Tanh(),
            nn.Linear(self.hidden_dim, 1),
        )
        
        self.classifier = nn.Sequential(
            nn.Linear(self.hidden_dim * 2, self.hidden_dim),
            nn.ReLU(),
            nn.Dropout(self.dropout),
            nn.Linear(self.hidden_dim, self.num_classes),
        )
        
        self.emotions = config["emotion"]["emotions"]
        self.emotion_to_idx = {e: i for i, e in enumerate(self.emotions)}
        self.idx_to_emotion = {i: e for i, e in enumerate(self.emotions)}

    def forward(self, mel_spectrogram: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_size = mel_spectrogram.size(0)
        
        x = self.conv_layers(mel_spectrogram)
        x = x.transpose(1, 2)
        
        self.gru.flatten_parameters()
        output, _ = self.gru(x)
        
        attn_weights = self.attention(output)
        attn_weights = F.softmax(attn_weights, dim=1)
        weighted_output = torch.sum(output * attn_weights, dim=1)
        
        logits = self.classifier(weighted_output)
        probs = F.softmax(logits, dim=-1)
        
        return logits, probs

    def predict(self, mel_spectrogram: torch.Tensor) -> Tuple[str, float]:
        with torch.no_grad():
            logits, probs = self.forward(mel_spectrogram.unsqueeze(0))
            pred_idx = torch.argmax(probs, dim=-1).item()
            pred_prob = probs[0, pred_idx].item()
            pred_emotion = self.idx_to_emotion[pred_idx]
        
        return pred_emotion, pred_prob

    def predict_proba(self, mel_spectrogram: torch.Tensor) -> Dict[str, float]:
        with torch.no_grad():
            _, probs = self.forward(mel_spectrogram.unsqueeze(0))
            probs = probs.squeeze(0).cpu().numpy()
        
        return {
            emotion: float(probs[i])
            for i, emotion in enumerate(self.emotions)
        }

    def evaluate(
        self,
        mel_spectrogram: torch.Tensor,
        target_emotion: str,
    ) -> Dict[str, Union[str, float, Dict[str, float]]]:
        pred_emotion, pred_confidence = self.predict(mel_spectrogram)
        all_probs = self.predict_proba(mel_spectrogram)
        
        target_idx = self.emotion_to_idx.get(target_emotion, -1)
        if target_idx >= 0:
            target_prob = all_probs.get(target_emotion, 0.0)
        else:
            target_prob = 0.0
        
        is_correct = pred_emotion == target_emotion
        
        return {
            "predicted_emotion": pred_emotion,
            "predicted_confidence": pred_confidence,
            "target_emotion": target_emotion,
            "target_probability": target_prob,
            "is_correct": is_correct,
            "all_probabilities": all_probs,
        }

    def validate_synthesis_quality(
        self,
        mel_spectrogram: torch.Tensor,
        target_emotion: str,
        target_intensity: float = 1.0,
    ) -> Dict[str, Union[float, bool, str]]:
        eval_result = self.evaluate(mel_spectrogram, target_emotion)
        
        target_prob = eval_result["target_probability"]
        pred_confidence = eval_result["predicted_confidence"]
        
        quality_score = target_prob * target_intensity
        is_acceptable = target_prob >= 0.5
        
        result = {
            "quality_score": float(quality_score),
            "target_emotion_match": eval_result["is_correct"],
            "target_probability": float(target_prob),
            "predicted_emotion": eval_result["predicted_emotion"],
            "predicted_confidence": float(pred_confidence),
            "is_acceptable": bool(is_acceptable),
            "threshold": 0.5,
        }
        
        return result


class EmotionQualityValidator:
    def __init__(self, config: dict, classifier: Optional[EmotionClassifier] = None):
        self.config = config
        self.classifier = classifier or EmotionClassifier(config)
        self.emotions = config["emotion"]["emotions"]
        self.audio_config = config["audio"]
        
        from ..utils.audio import AudioProcessor
        self.audio_processor = AudioProcessor(config)

    def validate_from_wav(
        self,
        wav_path: str,
        target_emotion: str,
        target_intensity: float = 1.0,
    ) -> Dict[str, Union[float, bool, str]]:
        wav = self.audio_processor.load_wav(wav_path)
        mel = self.audio_processor.wav_to_mel(wav)
        mel_tensor = torch.tensor(mel, dtype=torch.float32).unsqueeze(0)
        
        return self.classifier.validate_synthesis_quality(
            mel_tensor,
            target_emotion,
            target_intensity,
        )

    def validate_from_mel(
        self,
        mel_spectrogram: np.ndarray,
        target_emotion: str,
        target_intensity: float = 1.0,
    ) -> Dict[str, Union[float, bool, str]]:
        mel_tensor = torch.tensor(mel_spectrogram, dtype=torch.float32).unsqueeze(0)
        
        return self.classifier.validate_synthesis_quality(
            mel_tensor,
            target_emotion,
            target_intensity,
        )

    def batch_validate(
        self,
        mel_spectrograms: List[np.ndarray],
        target_emotions: List[str],
        target_intensities: Optional[List[float]] = None,
    ) -> List[Dict[str, Union[float, bool, str]]]:
        if target_intensities is None:
            target_intensities = [1.0] * len(mel_spectrograms)
        
        results = []
        for mel, emotion, intensity in zip(mel_spectrograms, target_emotions, target_intensities):
            result = self.validate_from_mel(mel, emotion, intensity)
            results.append(result)
        
        return results

    def compute_metrics(
        self,
        results: List[Dict[str, Union[float, bool, str]]],
    ) -> Dict[str, float]:
        if not results:
            return {}
        
        accuracy = sum(1 for r in results if r["target_emotion_match"]) / len(results)
        avg_quality = sum(r["quality_score"] for r in results) / len(results)
        avg_target_prob = sum(r["target_probability"] for r in results) / len(results)
        acceptance_rate = sum(1 for r in results if r["is_acceptable"]) / len(results)
        
        emotion_accuracies = {}
        for emotion in self.emotions:
            emotion_results = [r for r in results if r.get("target_emotion") == emotion]
            if emotion_results:
                emotion_accuracies[emotion] = sum(
                    1 for r in emotion_results if r["target_emotion_match"]
                ) / len(emotion_results)
            else:
                emotion_accuracies[emotion] = 0.0
        
        return {
            "overall_accuracy": accuracy,
            "average_quality_score": avg_quality,
            "average_target_probability": avg_target_prob,
            "acceptance_rate": acceptance_rate,
            "emotion_accuracies": emotion_accuracies,
            "total_samples": len(results),
        }

    def load_classifier_weights(self, weight_path: str) -> None:
        if os.path.exists(weight_path):
            checkpoint = torch.load(weight_path, map_location="cpu")
            self.classifier.load_state_dict(checkpoint["model_state_dict"])
            self.classifier.eval()
        else:
            raise FileNotFoundError(f"Classifier weights not found: {weight_path}")

    def save_classifier_weights(self, weight_path: str) -> None:
        os.makedirs(os.path.dirname(weight_path), exist_ok=True)
        torch.save({
            "model_state_dict": self.classifier.state_dict(),
            "emotions": self.emotions,
        }, weight_path)
