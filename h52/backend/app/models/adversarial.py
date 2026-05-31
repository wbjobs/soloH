import numpy as np
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class AdversarialDetectionResult:
    is_adversarial: bool
    confidence: float
    detection_method: str
    anomaly_scores: Dict[str, float]
    reasons: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'is_adversarial': self.is_adversarial,
            'confidence': self.confidence,
            'detection_method': self.detection_method,
            'anomaly_scores': self.anomaly_scores,
            'reasons': self.reasons,
            'timestamp': self.timestamp.isoformat()
        }


class AdversarialSampleDetector:
    def __init__(
        self,
        threshold: float = 0.75,
        max_history: int = 1000,
        enable_ensemble: bool = True
    ):
        self.threshold = threshold
        self.max_history = max_history
        self.enable_ensemble = enable_ensemble
        
        self.normal_feature_stats: Dict[str, Dict[str, float]] = {}
        self.adversarial_history: deque = deque(maxlen=max_history)
        
        self.detection_weights = {
            'feature_statistics': 0.25,
            'frequency_analysis': 0.20,
            'temporal_consistency': 0.25,
            'prediction_entropy': 0.15,
            'modal_consistency': 0.15
        }
        
        self.epsilon = 1e-10
        
        logger.info(f"AdversarialSampleDetector initialized with threshold={threshold}")

    def _compute_feature_statistics(
        self,
        features: np.ndarray,
        modality: str
    ) -> Tuple[float, List[str]]:
        score = 0.0
        reasons = []
        
        if features.size == 0:
            return 1.0, ['Empty feature vector']
        
        mean_val = np.mean(features)
        std_val = np.std(features)
        max_val = np.max(features)
        min_val = np.min(features)
        median_val = np.median(features)
        skewness = np.mean(((features - mean_val) / (std_val + self.epsilon)) ** 3) if std_val > 0 else 0
        kurtosis = np.mean(((features - mean_val) / (std_val + self.epsilon)) ** 4) - 3 if std_val > 0 else 0
        
        feature_key = modality
        if feature_key not in self.normal_feature_stats:
            self.normal_feature_stats[feature_key] = {
                'mean': mean_val, 'std': std_val,
                'max': max_val, 'min': min_val,
                'count': 1
            }
            return 0.0, reasons
        
        stats = self.normal_feature_stats[feature_key]
        
        mean_deviation = abs(mean_val - stats['mean']) / (stats['std'] + self.epsilon)
        if mean_deviation > 3.0:
            score += 0.3
            reasons.append(f"Mean deviation: {mean_deviation:.2f}σ")
        
        std_ratio = std_val / (stats['std'] + self.epsilon)
        if std_ratio < 0.1 or std_ratio > 10.0:
            score += 0.2
            reasons.append(f"Std ratio abnormal: {std_ratio:.2f}")
        
        range_val = max_val - min_val
        expected_range = stats['max'] - stats['min']
        range_ratio = range_val / (expected_range + self.epsilon)
        if range_ratio < 0.1:
            score += 0.15
            reasons.append(f"Feature range too small: {range_ratio:.2f}")
        
        if abs(skewness) > 2.0:
            score += 0.15
            reasons.append(f"High skewness: {skewness:.2f}")
        
        if abs(kurtosis) > 4.0:
            score += 0.2
            reasons.append(f"High kurtosis: {kurtosis:.2f}")
        
        zero_ratio = np.sum(np.abs(features) < 1e-6) / features.size
        if zero_ratio > 0.5:
            score += 0.25
            reasons.append(f"High zero ratio: {zero_ratio:.2%}")
        
        nan_count = np.sum(np.isnan(features))
        inf_count = np.sum(np.isinf(features))
        if nan_count > 0 or inf_count > 0:
            score += 0.5
            reasons.append(f"Invalid values: NaN={nan_count}, Inf={inf_count}")
        
        score = min(1.0, score)
        
        return score, reasons

    def _compute_frequency_analysis(self, features: np.ndarray) -> Tuple[float, List[str]]:
        score = 0.0
        reasons = []
        
        if features.ndim < 2 or features.shape[0] < 4:
            return 0.0, reasons
        
        try:
            if features.ndim == 2:
                fft_data = np.fft.fft(features, axis=0)
                power_spectrum = np.abs(fft_data) ** 2
                
                total_power = np.sum(power_spectrum)
                if total_power > 0:
                    low_freq_ratio = np.sum(power_spectrum[:len(power_spectrum)//4]) / total_power
                    high_freq_ratio = np.sum(power_spectrum[3*len(power_spectrum)//4:]) / total_power
                    
                    if high_freq_ratio > 0.6:
                        score += 0.3
                        reasons.append(f"High frequency content: {high_freq_ratio:.2%}")
                    
                    if low_freq_ratio < 0.1:
                        score += 0.2
                        reasons.append(f"Low frequency content missing: {low_freq_ratio:.2%}")
                    
                    spectral_entropy = -np.sum((power_spectrum / total_power) * np.log2(power_spectrum / total_power + self.epsilon))
                    max_entropy = np.log2(len(power_spectrum))
                    normalized_entropy = spectral_entropy / max_entropy
                    
                    if normalized_entropy < 0.3:
                        score += 0.25
                        reasons.append(f"Low spectral entropy: {normalized_entropy:.3f}")
        except Exception as e:
            logger.warning(f"Frequency analysis failed: {e}")
            return 0.0, reasons
        
        score = min(1.0, score)
        
        return score, reasons

    def _compute_temporal_consistency(
        self,
        current_features: np.ndarray,
        history_features: List[np.ndarray]
    ) -> Tuple[float, List[str]]:
        score = 0.0
        reasons = []
        
        if len(history_features) < 3:
            return 0.0, reasons
        
        try:
            recent_features = history_features[-5:]
            
            diffs = []
            for i in range(1, len(recent_features)):
                diff = np.mean(np.abs(recent_features[i] - recent_features[i-1]))
                diffs.append(diff)
            
            if diffs:
                avg_diff = np.mean(diffs)
                current_diff = np.mean(np.abs(current_features - recent_features[-1]))
                
                diff_ratio = current_diff / (avg_diff + self.epsilon)
                if diff_ratio > 5.0:
                    score += 0.4
                    reasons.append(f"Sudden feature change: {diff_ratio:.2f}x")
                
                std_diff = np.std(diffs) if len(diffs) > 1 else 0
                if std_diff < 1e-6 and avg_diff < 1e-6:
                    score += 0.3
                    reasons.append("Static features (no variation)")
                
                if len(diffs) >= 3:
                    trend = np.polyfit(range(len(diffs)), diffs, 1)[0]
                    if abs(trend) > avg_diff * 0.5:
                        score += 0.2
                        reasons.append(f"Abnormal trend in feature changes")
        except Exception as e:
            logger.warning(f"Temporal consistency check failed: {e}")
            return 0.0, reasons
        
        score = min(1.0, score)
        
        return score, reasons

    def _compute_prediction_entropy(self, probabilities: Dict[str, float]) -> Tuple[float, List[str]]:
        score = 0.0
        reasons = []
        
        if not probabilities:
            return 1.0, ['Empty probabilities']
        
        probs = np.array(list(probabilities.values()))
        probs = probs / (np.sum(probs) + self.epsilon)
        
        entropy = -np.sum(probs * np.log2(probs + self.epsilon))
        max_entropy = np.log2(len(probs))
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        
        max_prob = np.max(probs)
        
        if max_prob > 0.99:
            score += 0.3
            reasons.append(f"Overconfident prediction: {max_prob:.4f}")
        
        if normalized_entropy < 0.1:
            score += 0.25
            reasons.append(f"Very low entropy: {normalized_entropy:.3f}")
        
        if normalized_entropy > 0.95 and max_prob < 0.2:
            score += 0.2
            reasons.append(f"Uncertain predictions (high entropy): {normalized_entropy:.3f}")
        
        sorted_probs = np.sort(probs)[::-1]
        margin = sorted_probs[0] - sorted_probs[1] if len(sorted_probs) > 1 else 0
        if margin > 0.9:
            score += 0.25
            reasons.append(f"Extreme prediction margin: {margin:.3f}")
        
        score = min(1.0, score)
        
        return score, reasons

    def _compute_modal_consistency(
        self,
        audio_probs: Optional[Dict[str, float]],
        video_probs: Optional[Dict[str, float]],
        text_probs: Optional[Dict[str, float]]
    ) -> Tuple[float, List[str]]:
        score = 0.0
        reasons = []
        
        available_probs = []
        if audio_probs:
            available_probs.append(audio_probs)
        if video_probs:
            available_probs.append(video_probs)
        if text_probs:
            available_probs.append(text_probs)
        
        if len(available_probs) < 2:
            return 0.0, reasons
        
        emotions = list(available_probs[0].keys())
        
        predictions = []
        for probs in available_probs:
            pred = max(probs, key=probs.get)
            predictions.append(pred)
        
        if len(set(predictions)) > 1:
            score += 0.2
            reasons.append(f"Modal disagreement: {predictions}")
        
        for i in range(len(available_probs)):
            for j in range(i + 1, len(available_probs)):
                vec_i = np.array([available_probs[i].get(e, 0) for e in emotions])
                vec_j = np.array([available_probs[j].get(e, 0) for e in emotions])
                
                vec_i = vec_i / (np.linalg.norm(vec_i) + self.epsilon)
                vec_j = vec_j / (np.linalg.norm(vec_j) + self.epsilon)
                
                similarity = np.dot(vec_i, vec_j)
                
                if similarity < 0.3:
                    score += 0.15
                    reasons.append(f"Low modal similarity {i}-{j}: {similarity:.3f}")
        
        score = min(1.0, score)
        
        return score, reasons

    def detect(
        self,
        audio_features: Optional[np.ndarray] = None,
        video_features: Optional[np.ndarray] = None,
        text_features: Optional[np.ndarray] = None,
        fused_probabilities: Optional[Dict[str, float]] = None,
        audio_probs: Optional[Dict[str, float]] = None,
        video_probs: Optional[Dict[str, float]] = None,
        text_probs: Optional[Dict[str, float]] = None,
        feature_history: Optional[Dict[str, List[np.ndarray]]] = None
    ) -> AdversarialDetectionResult:
        all_scores: Dict[str, float] = {}
        all_reasons: List[str] = []
        
        if audio_features is not None:
            score, reasons = self._compute_feature_statistics(audio_features, 'audio')
            all_scores['audio_feature_stats'] = score
            all_reasons.extend([f"[Audio] {r}" for r in reasons])
        
        if video_features is not None:
            score, reasons = self._compute_feature_statistics(video_features, 'video')
            all_scores['video_feature_stats'] = score
            all_reasons.extend([f"[Video] {r}" for r in reasons])
        
        if text_features is not None:
            score, reasons = self._compute_feature_statistics(text_features, 'text')
            all_scores['text_feature_stats'] = score
            all_reasons.extend([f"[Text] {r}" for r in reasons])
        
        if video_features is not None and video_features.ndim >= 2:
            score, reasons = self._compute_frequency_analysis(video_features)
            all_scores['frequency_analysis'] = score
            all_reasons.extend([f"[Freq] {r}" for r in reasons])
        
        if feature_history and 'video' in feature_history and video_features is not None:
            score, reasons = self._compute_temporal_consistency(video_features, feature_history['video'])
            all_scores['temporal_consistency'] = score
            all_reasons.extend([f"[Temp] {r}" for r in reasons])
        
        if fused_probabilities is not None:
            score, reasons = self._compute_prediction_entropy(fused_probabilities)
            all_scores['prediction_entropy'] = score
            all_reasons.extend([f"[Pred] {r}" for r in reasons])
        
        if any([audio_probs, video_probs, text_probs]):
            score, reasons = self._compute_modal_consistency(audio_probs, video_probs, text_probs)
            all_scores['modal_consistency'] = score
            all_reasons.extend([f"[Modal] {r}" for r in reasons])
        
        if not all_scores:
            return AdversarialDetectionResult(
                is_adversarial=False,
                confidence=0.0,
                detection_method='none',
                anomaly_scores={},
                reasons=['No features available for analysis']
            )
        
        weighted_score = 0.0
        total_weight = 0.0
        for method, score in all_scores.items():
            for key, weight in self.detection_weights.items():
                if key in method:
                    weighted_score += score * weight
                    total_weight += weight
                    break
        
        if total_weight > 0:
            final_score = weighted_score / total_weight
        else:
            final_score = np.mean(list(all_scores.values()))
        
        is_adversarial = final_score >= self.threshold
        
        if is_adversarial:
            self.adversarial_history.append({
                'score': final_score,
                'timestamp': datetime.now(),
                'reasons': all_reasons
            })
        
        return AdversarialDetectionResult(
            is_adversarial=is_adversarial,
            confidence=final_score,
            detection_method='ensemble' if self.enable_ensemble else 'weighted',
            anomaly_scores=all_scores,
            reasons=all_reasons
        )

    def get_detection_stats(self) -> Dict:
        return {
            'total_adversarial_detected': len(self.adversarial_history),
            'threshold': self.threshold,
            'detection_weights': self.detection_weights,
            'recent_detections': [
                {
                    'score': h['score'],
                    'timestamp': h['timestamp'].isoformat(),
                    'reasons_count': len(h['reasons'])
                }
                for h in list(self.adversarial_history)[-10:]
            ]
        }

    def update_normal_stats(
        self,
        features: np.ndarray,
        modality: str,
        alpha: float = 0.01
    ):
        if modality not in self.normal_feature_stats:
            self.normal_feature_stats[modality] = {
                'mean': np.mean(features),
                'std': np.std(features),
                'max': np.max(features),
                'min': np.min(features),
                'count': 1
            }
            return
        
        stats = self.normal_feature_stats[modality]
        stats['mean'] = (1 - alpha) * stats['mean'] + alpha * np.mean(features)
        stats['std'] = (1 - alpha) * stats['std'] + alpha * np.std(features)
        stats['max'] = max(stats['max'], np.max(features))
        stats['min'] = min(stats['min'], np.min(features))
        stats['count'] += 1
