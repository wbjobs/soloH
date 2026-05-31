import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from config import SideChannelProtectionConfig
from event_detection import KeyEvent
from feature_extraction import KeyFeatures
from utils import preemphasis, framing, compute_energy


@dataclass
class FakeKeyDetectionResult:
    is_fake: bool
    confidence: float
    reasons: List[str] = field(default_factory=list)
    energy_score: float = 0.0
    spectral_score: float = 0.0
    temporal_score: float = 0.0
    correlation_score: float = 0.0


@dataclass
class ProtectionStats:
    total_events: int = 0
    fake_events_detected: int = 0
    avg_confidence: float = 0.0
    detection_reasons: List[str] = field(default_factory=list)


class SideChannelProtector:
    def __init__(self, config: SideChannelProtectionConfig, sample_rate: int, 
                 num_channels: int):
        self.config = config
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        
        self.history: List[KeyEvent] = []
        self.history_features: List[KeyFeatures] = []
        self.max_history = 100
        
        self.stats = ProtectionStats()
    
    def analyze_event(self, event: KeyEvent, multi_channel_audio: np.ndarray,
                      features: Optional[KeyFeatures] = None) -> FakeKeyDetectionResult:
        if not self.config.enable_protection:
            return FakeKeyDetectionResult(
                is_fake=False,
                confidence=0.0,
                reasons=["Protection disabled"]
            )
        
        reasons = []
        scores = []
        
        energy_score = self._check_energy_consistency(event)
        scores.append(energy_score)
        if energy_score < 0.3:
            reasons.append(f"Abnormal energy distribution (score: {energy_score:.2f})")
        
        spectral_score = self._check_spectral_features(event, features)
        scores.append(spectral_score)
        if spectral_score < 0.3:
            reasons.append(f"Abnormal spectral features (score: {spectral_score:.2f})")
        
        temporal_score = self._check_temporal_consistency(event)
        scores.append(temporal_score)
        if temporal_score < 0.3:
            reasons.append(f"Abnormal temporal pattern (score: {temporal_score:.2f})")
        
        correlation_score = self._check_multichannel_correlation(event, multi_channel_audio)
        scores.append(correlation_score)
        if correlation_score < 0.3:
            reasons.append(f"Low multi-channel correlation (score: {correlation_score:.2f})")
        
        overall_score = float(np.mean(scores))
        is_fake = overall_score < self.config.fake_key_confidence_threshold
        
        if is_fake:
            self.stats.fake_events_detected += 1
        
        self.stats.total_events += 1
        self.stats.avg_confidence = (
            (self.stats.avg_confidence * (self.stats.total_events - 1) + overall_score) / 
            self.stats.total_events
        )
        
        if reasons:
            self.stats.detection_reasons.extend(reasons)
        
        self.history.append(event)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        if features is not None:
            self.history_features.append(features)
            if len(self.history_features) > self.max_history:
                self.history_features.pop(0)
        
        return FakeKeyDetectionResult(
            is_fake=is_fake,
            confidence=overall_score,
            reasons=reasons,
            energy_score=energy_score,
            spectral_score=spectral_score,
            temporal_score=temporal_score,
            correlation_score=correlation_score
        )
    
    def _check_energy_consistency(self, event: KeyEvent) -> float:
        audio = event.audio
        
        energy = np.abs(audio) ** 2
        energy_std = np.std(energy)
        energy_mean = np.mean(energy) + 1e-10
        energy_cv = energy_std / energy_mean
        
        frame_size = 256
        hop_size = 128
        audio_pre = preemphasis(audio)
        frames = framing(audio_pre, frame_size, hop_size)
        frame_energy = compute_energy(frames)
        
        frame_energy_std = np.std(frame_energy)
        frame_energy_mean = np.mean(frame_energy) + 1e-10
        frame_energy_cv = frame_energy_std / frame_energy_mean
        
        score = 1.0
        
        if energy_cv < self.config.min_energy_std or energy_cv > self.config.max_energy_std:
            score *= 0.5
        
        if frame_energy_cv < 0.1 or frame_energy_cv > 5.0:
            score *= 0.7
        
        peak_pos = np.argmax(np.abs(audio)) / len(audio)
        if peak_pos < 0.1 or peak_pos > 0.9:
            score *= 0.8
        
        return float(score)
    
    def _check_spectral_features(self, event: KeyEvent, 
                                  features: Optional[KeyFeatures]) -> float:
        score = 1.0
        
        if features is not None and hasattr(features, 'robust_features'):
            rf = features.robust_features
            
            if rf.spectral_centroid < self.config.min_spectral_centroid or \
               rf.spectral_centroid > self.config.max_spectral_centroid:
                score *= 0.6
            
            if rf.decay_rate < self.config.min_decay_rate or \
               rf.decay_rate > self.config.max_decay_rate:
                score *= 0.7
            
            if rf.attack_time < 0.0001 or rf.attack_time > 0.05:
                score *= 0.8
            
            if rf.zero_crossing_rate < 0.01 or rf.zero_crossing_rate > 0.5:
                score *= 0.8
        
        audio = event.audio
        n_fft = min(1024, len(audio))
        if n_fft >= 64:
            spec = np.abs(np.fft.rfft(audio, n=n_fft))
            freqs = np.fft.rfftfreq(n_fft, d=1.0/self.sample_rate)
            
            spec_sum = np.sum(spec) + 1e-10
            low_freq_ratio = np.sum(spec[freqs < 100]) / spec_sum
            high_freq_ratio = np.sum(spec[freqs > 15000]) / spec_sum
            
            if low_freq_ratio > 0.8:
                score *= 0.7
            
            if high_freq_ratio > 0.5:
                score *= 0.8
        
        return float(score)
    
    def _check_temporal_consistency(self, event: KeyEvent) -> float:
        score = 1.0
        
        if len(self.history) >= 3:
            recent_times = [e.start_time for e in self.history[-10:]]
            recent_times.append(event.start_time)
            intervals = np.diff(recent_times)
            
            if len(intervals) >= 2:
                interval_std = np.std(intervals)
                interval_mean = np.mean(intervals) + 1e-10
                interval_cv = interval_std / interval_mean
                
                if interval_cv < self.config.temporal_consistency_threshold:
                    score *= 0.6
                
                if interval_mean < 0.02:
                    score *= 0.7
        
        event_duration = event.end_time - event.start_time
        if event_duration < 0.005 or event_duration > 0.3:
            score *= 0.7
        
        if len(self.history) >= 2:
            prev_event = self.history[-1]
            gap = event.start_time - prev_event.end_time
            if gap < 0:
                score *= 0.5
        
        return float(score)
    
    def _check_multichannel_correlation(self, event: KeyEvent, 
                                        multi_channel_audio: np.ndarray) -> float:
        score = 1.0
        
        if self.num_channels < 2 or multi_channel_audio.shape[0] < 2:
            return float(score)
        
        start = event.start_sample
        end = event.end_sample
        
        if end <= start or start < 0 or end > multi_channel_audio.shape[1]:
            return float(score)
        
        event_audio = multi_channel_audio[:, start:end]
        min_len = min(event_audio.shape[1], len(event.audio))
        
        if min_len < 64:
            return float(score)
        
        correlations = []
        ref_channel = event.channel if event.channel < self.num_channels else 0
        ref_signal = event_audio[ref_channel, :min_len]
        
        for ch in range(self.num_channels):
            if ch == ref_channel:
                continue
            
            ch_signal = event_audio[ch, :min_len]
            
            if np.std(ref_signal) < 1e-10 or np.std(ch_signal) < 1e-10:
                correlations.append(0.0)
                continue
            
            corr = np.corrcoef(ref_signal, ch_signal)[0, 1]
            correlations.append(max(0.0, corr))
        
        if correlations:
            avg_corr = float(np.mean(correlations))
            
            if avg_corr < self.config.multi_channel_correlation_threshold:
                score *= 0.5
            
            if avg_corr > 0.99:
                score *= 0.8
        
        energy_per_channel = []
        for ch in range(self.num_channels):
            ch_energy = np.sum(np.abs(event_audio[ch, :min_len]) ** 2)
            energy_per_channel.append(ch_energy)
        
        energy_per_channel = np.array(energy_per_channel)
        if np.sum(energy_per_channel) > 0:
            energy_norm = energy_per_channel / np.sum(energy_per_channel)
            energy_spread = np.std(energy_norm)
            
            if energy_spread < 0.01:
                score *= 0.7
            
            if energy_spread > 0.4:
                score *= 0.8
        
        return float(score)
    
    def filter_events(self, events: List[KeyEvent], 
                       multi_channel_audio: np.ndarray,
                       features: Optional[List[KeyFeatures]] = None
                       ) -> Tuple[List[KeyEvent], List[FakeKeyDetectionResult]]:
        filtered_events = []
        results = []
        
        for i, event in enumerate(events):
            feat = features[i] if features and i < len(features) else None
            result = self.analyze_event(event, multi_channel_audio, feat)
            
            results.append(result)
            
            if not result.is_fake:
                filtered_events.append(event)
        
        return filtered_events, results
    
    def generate_fake_key_signal(self, sample_rate: int, duration: float = 0.05,
                                  fake_type: str = 'sine') -> np.ndarray:
        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples)
        
        if fake_type == 'sine':
            freq = np.random.uniform(50, 200)
            signal = np.sin(2 * np.pi * freq * t)
        elif fake_type == 'ultrasonic':
            freq = np.random.uniform(20000, 25000)
            signal = np.sin(2 * np.pi * freq * t) * np.exp(-t * 100)
        elif fake_type == 'em_interference':
            signal = np.random.randn(num_samples) * 0.1
            signal += np.sin(2 * np.pi * 60 * t) * 0.5
        elif fake_type == 'impulse':
            signal = np.zeros(num_samples)
            impulse_pos = int(num_samples * 0.5)
            signal[impulse_pos] = 1.0
        elif fake_type == 'noise':
            signal = np.random.randn(num_samples)
        else:
            signal = np.random.randn(num_samples)
        
        envelope = np.exp(-np.linspace(0, 3, num_samples))
        signal = signal * envelope
        signal = signal / (np.max(np.abs(signal)) + 1e-10)
        
        return signal
    
    def get_stats(self) -> ProtectionStats:
        return self.stats
    
    def reset_stats(self):
        self.stats = ProtectionStats()


def build_side_channel_protector(config: SideChannelProtectionConfig,
                                  sample_rate: int,
                                  num_channels: int) -> SideChannelProtector:
    return SideChannelProtector(config, sample_rate, num_channels)
