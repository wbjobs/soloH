import numpy as np
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class UserBaseline:
    user_id: str
    facial_landmarks: np.ndarray = None
    voice_features: np.ndarray = None
    text_style: Dict[str, float] = field(default_factory=dict)
    emotion_baseline: Dict[str, float] = field(default_factory=lambda: {
        'anger': 0.05, 'joy': 0.1, 'sadness': 0.05,
        'surprise': 0.05, 'disgust': 0.02, 'fear': 0.03, 'neutral': 0.7
    })
    valence_baseline: float = 0.0
    arousal_baseline: float = 0.0
    calibration_samples: int = 0
    is_calibrated: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'user_id': self.user_id,
            'facial_landmarks': self.facial_landmarks.tolist() if self.facial_landmarks is not None else None,
            'voice_features': self.voice_features.tolist() if self.voice_features is not None else None,
            'text_style': self.text_style,
            'emotion_baseline': self.emotion_baseline,
            'valence_baseline': self.valence_baseline,
            'arousal_baseline': self.arousal_baseline,
            'calibration_samples': self.calibration_samples,
            'is_calibrated': self.is_calibrated,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat()
        }


class PersonalizationCalibrator:
    def __init__(self, min_calibration_samples: int = 5, max_baseline_age_days: int = 30):
        self.min_calibration_samples = min_calibration_samples
        self.max_baseline_age_days = max_baseline_age_days
        self.user_baselines: Dict[str, UserBaseline] = {}
        self.calibration_sessions: Dict[str, List[Dict]] = {}
        
        self.facial_alpha = 0.3
        self.voice_alpha = 0.3
        self.emotion_alpha = 0.4
        self.va_alpha = 0.35
        
        logger.info(f"PersonalizationCalibrator initialized with min_samples={min_calibration_samples}")

    def start_calibration_session(self, user_id: str) -> Dict:
        self.calibration_sessions[user_id] = []
        logger.info(f"Started calibration session for user {user_id}")
        return {
            'user_id': user_id,
            'session_started': datetime.now().isoformat(),
            'required_samples': self.min_calibration_samples,
            'current_samples': 0
        }

    def add_calibration_sample(
        self,
        user_id: str,
        facial_landmarks: Optional[np.ndarray] = None,
        voice_features: Optional[np.ndarray] = None,
        text_features: Optional[Dict] = None,
        emotion_probs: Optional[Dict[str, float]] = None,
        valence: Optional[float] = None,
        arousal: Optional[float] = None
    ) -> Dict:
        sample = {
            'timestamp': datetime.now(),
            'facial_landmarks': facial_landmarks.copy() if facial_landmarks is not None else None,
            'voice_features': voice_features.copy() if voice_features is not None else None,
            'text_features': text_features,
            'emotion_probs': emotion_probs,
            'valence': valence,
            'arousal': arousal
        }
        
        if user_id not in self.calibration_sessions:
            self.calibration_sessions[user_id] = []
        
        self.calibration_sessions[user_id].append(sample)
        current_count = len(self.calibration_sessions[user_id])
        
        logger.info(f"Added calibration sample {current_count} for user {user_id}")
        
        return {
            'user_id': user_id,
            'current_samples': current_count,
            'required_samples': self.min_calibration_samples,
            'can_complete': current_count >= self.min_calibration_samples
        }

    def complete_calibration(self, user_id: str) -> UserBaseline:
        if user_id not in self.calibration_sessions:
            raise ValueError(f"No calibration session found for user {user_id}")
        
        samples = self.calibration_sessions[user_id]
        if len(samples) < self.min_calibration_samples:
            raise ValueError(
                f"Insufficient calibration samples: {len(samples)}/{self.min_calibration_samples}"
            )
        
        baseline = UserBaseline(user_id=user_id)
        
        facial_samples = [s['facial_landmarks'] for s in samples if s['facial_landmarks'] is not None]
        if facial_samples:
            baseline.facial_landmarks = np.mean(facial_samples, axis=0)
        
        voice_samples = [s['voice_features'] for s in samples if s['voice_features'] is not None]
        if voice_samples:
            baseline.voice_features = np.mean(voice_samples, axis=0)
        
        text_samples = [s['text_features'] for s in samples if s['text_features'] is not None]
        if text_samples:
            keys = set().union(*[t.keys() for t in text_samples])
            baseline.text_style = {k: np.mean([t.get(k, 0) for t in text_samples]) for k in keys}
        
        emotion_samples = [s['emotion_probs'] for s in samples if s['emotion_probs'] is not None]
        if emotion_samples:
            emotions = ['anger', 'joy', 'sadness', 'surprise', 'disgust', 'fear', 'neutral']
            baseline.emotion_baseline = {e: np.mean([s.get(e, 0) for s in emotion_samples]) for e in emotions}
            total = sum(baseline.emotion_baseline.values())
            if total > 0:
                baseline.emotion_baseline = {k: v/total for k, v in baseline.emotion_baseline.items()}
        
        valence_samples = [s['valence'] for s in samples if s['valence'] is not None]
        if valence_samples:
            baseline.valence_baseline = float(np.mean(valence_samples))
        
        arousal_samples = [s['arousal'] for s in samples if s['arousal'] is not None]
        if arousal_samples:
            baseline.arousal_baseline = float(np.mean(arousal_samples))
        
        baseline.calibration_samples = len(samples)
        baseline.is_calibrated = True
        baseline.last_updated = datetime.now()
        
        self.user_baselines[user_id] = baseline
        del self.calibration_sessions[user_id]
        
        logger.info(f"Completed calibration for user {user_id} with {len(samples)} samples")
        
        return baseline

    def get_user_baseline(self, user_id: str) -> Optional[UserBaseline]:
        baseline = self.user_baselines.get(user_id)
        
        if baseline is not None:
            age_days = (datetime.now() - baseline.last_updated).days
            if age_days > self.max_baseline_age_days:
                logger.warning(f"Baseline for user {user_id} is {age_days} days old, recommending recalibration")
        
        return baseline

    def adjust_emotion(
        self,
        user_id: str,
        emotion_probs: Dict[str, float],
        valence: float,
        arousal: float
    ) -> Tuple[Dict[str, float], float, float]:
        baseline = self.get_user_baseline(user_id)
        if baseline is None or not baseline.is_calibrated:
            return emotion_probs, valence, arousal
        
        adjusted_probs = {}
        for emotion, prob in emotion_probs.items():
            baseline_prob = baseline.emotion_baseline.get(emotion, 0)
            deviation = prob - baseline_prob
            adjusted_probs[emotion] = baseline_prob + deviation * (1 + self.emotion_alpha)
        
        total = sum(adjusted_probs.values())
        if total > 0:
            adjusted_probs = {k: max(0, min(1, v/total)) for k, v in adjusted_probs.items()}
        
        adjusted_valence = valence + (valence - baseline.valence_baseline) * self.va_alpha
        adjusted_arousal = arousal + (arousal - baseline.arousal_baseline) * self.va_alpha
        
        adjusted_valence = max(-1.0, min(1.0, adjusted_valence))
        adjusted_arousal = max(-1.0, min(1.0, adjusted_arousal))
        
        return adjusted_probs, adjusted_valence, adjusted_arousal

    def adjust_facial_features(self, user_id: str, features: np.ndarray) -> np.ndarray:
        baseline = self.get_user_baseline(user_id)
        if baseline is None or baseline.facial_landmarks is None or not baseline.is_calibrated:
            return features
        
        deviation = features - baseline.facial_landmarks
        adjusted = baseline.facial_landmarks + deviation * (1 + self.facial_alpha)
        
        return adjusted

    def adjust_voice_features(self, user_id: str, features: np.ndarray) -> np.ndarray:
        baseline = self.get_user_baseline(user_id)
        if baseline is None or baseline.voice_features is None or not baseline.is_calibrated:
            return features
        
        deviation = features - baseline.voice_features
        adjusted = baseline.voice_features + deviation * (1 + self.voice_alpha)
        
        return adjusted

    def reset_calibration(self, user_id: str):
        if user_id in self.user_baselines:
            del self.user_baselines[user_id]
        if user_id in self.calibration_sessions:
            del self.calibration_sessions[user_id]
        logger.info(f"Reset calibration for user {user_id}")
