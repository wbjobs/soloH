import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
from config import Config, EventDetectionConfig
from utils import compute_energy, framing, preemphasis


@dataclass
class KeyEvent:
    start_sample: int
    end_sample: int
    start_time: float
    end_time: float
    duration: float
    audio: np.ndarray
    peak_energy: float
    peak_sample: int
    channel: int = 0
    is_long_press: bool = False
    press_count: int = 1
    is_collision: bool = False
    collision_order: int = 0


class EventDetector:
    def __init__(self, config: EventDetectionConfig, sample_rate: int):
        self.config = config
        self.sample_rate = sample_rate
        self.min_samples = int(config.min_duration * sample_rate)
        self.max_samples = int(config.max_duration * sample_rate)
        self.pre_trigger_samples = int(config.pre_trigger * sample_rate)
        self.post_trigger_samples = int(config.post_trigger * sample_rate)
        self.long_press_min_samples = int(config.long_press_min_duration * sample_rate)
        self.long_press_max_gap_samples = int(config.long_press_max_gap * sample_rate)
        self.collision_min_separation_samples = int(config.collision_min_separation * sample_rate)

    def detect(self, audio: np.ndarray) -> List[KeyEvent]:
        if len(audio.shape) == 1:
            audio = audio.reshape(1, -1)
        
        num_channels = audio.shape[0]
        
        all_channel_events = []
        for ch in range(num_channels):
            channel_audio = audio[ch]
            events = self._detect_single_channel(channel_audio, ch)
            all_channel_events.extend(events)
        
        events = self._merge_cross_channel_events(all_channel_events, num_channels)
        
        events = self._filter_low_energy_events(events)
        
        events = self._detect_and_mark_collisions(events)
        
        events = self._merge_long_presses(events)
        
        events = self._resolve_timing_order(events, audio)
        
        events.sort(key=lambda x: x.peak_sample)
        
        return events
    
    def _filter_low_energy_events(self, events: List[KeyEvent]) -> List[KeyEvent]:
        if not events:
            return []
        
        energies = [e.peak_energy for e in events]
        median_energy = np.median(energies)
        threshold = median_energy * 0.1
        
        return [e for e in events if e.peak_energy > threshold]

    def _detect_single_channel(self, audio: np.ndarray, channel: int) -> List[KeyEvent]:
        audio_pre = preemphasis(audio)
        
        frames = framing(audio_pre, self.config.window_size, self.config.hop_size)
        energy = compute_energy(frames)
        
        threshold = self.config.energy_threshold
        if threshold is None:
            threshold = np.median(energy) * 5
        
        peak_frames = self._detect_peaks(energy, threshold)
        
        events = []
        for peak_frame in peak_frames:
            peak_sample = peak_frame * self.config.hop_size + self.config.window_size // 2
            
            start_frame = peak_frame
            while start_frame > 0 and energy[start_frame] > threshold * 0.3 and (peak_frame - start_frame) < self.config.peak_detection_window * 2:
                start_frame -= 1
            start_sample = max(0, start_frame * self.config.hop_size - self.pre_trigger_samples)
            
            end_frame = peak_frame
            while end_frame < len(energy) - 1 and energy[end_frame] > threshold * 0.3 and (end_frame - peak_frame) < self.config.peak_detection_window * 2:
                end_frame += 1
            end_sample = min(len(audio), end_frame * self.config.hop_size + self.config.window_size + self.post_trigger_samples)
            
            duration = end_sample - start_sample
            
            if self.min_samples <= duration <= self.max_samples:
                event_audio = audio[start_sample:end_sample].copy()
                peak_energy = energy[peak_frame]
                
                events.append(KeyEvent(
                    start_sample=start_sample,
                    end_sample=end_sample,
                    start_time=start_sample / self.sample_rate,
                    end_time=end_sample / self.sample_rate,
                    duration=duration / self.sample_rate,
                    audio=event_audio,
                    peak_energy=peak_energy,
                    peak_sample=peak_sample,
                    channel=channel
                ))
        
        return events

    def _detect_peaks(self, energy: np.ndarray, threshold: float = None) -> List[int]:
        peaks = []
        window = self.config.peak_detection_window
        
        if threshold is None:
            threshold = self.config.energy_threshold
        
        for i in range(window, len(energy) - window):
            if energy[i] > threshold:
                is_peak = True
                for j in range(1, window + 1):
                    if energy[i] <= energy[i - j] or energy[i] <= energy[i + j]:
                        is_peak = False
                        break
                if is_peak:
                    peaks.append(i)
        
        return peaks

    def _merge_cross_channel_events(self, events: List[KeyEvent], 
                                     num_channels: int) -> List[KeyEvent]:
        if not events:
            return []
        
        events.sort(key=lambda x: x.peak_sample)
        
        merged = []
        i = 0
        max_time_diff = int(self.sample_rate * 0.003)
        
        while i < len(events):
            current = events[i]
            group = [current]
            j = i + 1
            
            while j < len(events):
                other = events[j]
                time_diff = abs(other.peak_sample - current.peak_sample)
                
                if time_diff < max_time_diff and other.channel != current.channel:
                    group.append(other)
                    j += 1
                else:
                    break
            
            if len(group) > 1:
                best_event = max(group, key=lambda e: e.peak_energy)
                
                min_peak = min(e.peak_sample for e in group)
                max_peak = max(e.peak_sample for e in group)
                best_event.peak_sample = (min_peak + max_peak) // 2
                
                merged.append(best_event)
            else:
                merged.append(current)
            
            i = j
        
        return merged

    def _detect_and_mark_collisions(self, events: List[KeyEvent]) -> List[KeyEvent]:
        if not events or len(events) < 2:
            return events
        
        events.sort(key=lambda x: x.peak_sample)
        
        i = 0
        while i < len(events) - 1:
            j = i + 1
            collision_group = [events[i]]
            
            while j < len(events):
                time_diff = events[j].peak_sample - collision_group[-1].peak_sample
                
                if time_diff < self.collision_min_separation_samples:
                    collision_group.append(events[j])
                    j += 1
                else:
                    break
            
            if len(collision_group) >= 2:
                for k, event in enumerate(collision_group):
                    event.is_collision = True
                    event.collision_order = k
            
            i = j
        
        return events

    def _compute_multichannel_offsets(self, audio: np.ndarray, peak_sample: int) -> np.ndarray:
        num_channels = audio.shape[0]
        offsets = np.zeros(num_channels)
        
        window = self.config.tdoa_window_size if hasattr(self.config, 'tdoa_window_size') else 512
        start = max(0, peak_sample - window // 2)
        end = min(audio.shape[1], peak_sample + window // 2)
        
        ref_ch = 0
        ref_signal = audio[ref_ch, start:end]
        
        for ch in range(num_channels):
            if ch == ref_ch:
                offsets[ch] = 0
                continue
            
            ch_signal = audio[ch, start:end]
            
            corr = np.correlate(ref_signal, ch_signal, mode='same')
            peak_idx = np.argmax(corr)
            offsets[ch] = peak_idx - len(corr) // 2
        
        return offsets

    def _merge_long_presses(self, events: List[KeyEvent]) -> List[KeyEvent]:
        if not events:
            return []
        
        events.sort(key=lambda x: x.peak_sample)
        
        merged = []
        i = 0
        
        while i < len(events):
            current = events[i]
            group = [current]
            j = i + 1
            
            while j < len(events):
                next_event = events[j]
                peak_gap = next_event.peak_sample - group[-1].peak_sample
                
                if peak_gap < self.long_press_max_gap_samples:
                    group.append(next_event)
                    j += 1
                else:
                    break
            
            if len(group) >= 3:
                total_duration = group[-1].end_sample - group[0].start_sample
                if total_duration >= self.long_press_min_samples:
                    merged_event = self._merge_long_press_group(group)
                    merged.append(merged_event)
                    i = j
                    continue
            
            for e in group:
                merged.append(e)
            
            i = j
        
        return merged

    def _merge_long_press_group(self, group: List[KeyEvent]) -> KeyEvent:
        if len(group) == 1:
            return group[0]
        
        total_duration = group[-1].end_sample - group[0].start_sample
        is_long_press = total_duration >= self.long_press_min_samples
        
        start_sample = group[0].start_sample
        end_sample = group[-1].end_sample
        peak_energy = max(e.peak_energy for e in group)
        best_channel = max(group, key=lambda e: e.peak_energy).channel
        
        max_audio_len = max(len(e.audio) for e in group)
        audio_data = np.zeros(end_sample - start_sample)
        
        for e in group:
            rel_start = e.start_sample - start_sample
            rel_end = rel_start + len(e.audio)
            if rel_start < len(audio_data):
                copy_len = min(rel_end, len(audio_data)) - rel_start
                audio_data[rel_start:rel_start + copy_len] = e.audio[:copy_len]
        
        first_peak = min(e.peak_sample for e in group)
        
        return KeyEvent(
            start_sample=start_sample,
            end_sample=end_sample,
            start_time=start_sample / self.sample_rate,
            end_time=end_sample / self.sample_rate,
            duration=(end_sample - start_sample) / self.sample_rate,
            audio=audio_data,
            peak_energy=peak_energy,
            peak_sample=first_peak,
            channel=best_channel,
            is_long_press=is_long_press,
            press_count=len(group)
        )



    def _resolve_timing_order(self, events: List[KeyEvent], audio: np.ndarray) -> List[KeyEvent]:
        if len(events) < 2 or audio.shape[0] < 2:
            return events
        
        num_channels = audio.shape[0]
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                e1 = events[i]
                e2 = events[j]
                
                if abs(e1.peak_sample - e2.peak_sample) < self.collision_min_separation_samples:
                    cross_corr_lags = []
                    
                    for ch in range(num_channels):
                        for ch2 in range(ch + 1, num_channels):
                            lag = self._compute_cross_correlation_lag(
                                audio[ch, e1.start_sample:e1.end_sample],
                                audio[ch2, e2.start_sample:e2.end_sample]
                            )
                            cross_corr_lags.append(lag)
                    
                    if cross_corr_lags:
                        avg_lag = np.mean(cross_corr_lags)
                        if avg_lag > 0:
                            e1.peak_sample += int(avg_lag / 2)
                            e2.peak_sample -= int(avg_lag / 2)
                        elif avg_lag < 0:
                            e1.peak_sample -= int(abs(avg_lag) / 2)
                            e2.peak_sample += int(abs(avg_lag) / 2)
        
        return events

    def _compute_cross_correlation_lag(self, sig1: np.ndarray, sig2: np.ndarray) -> int:
        min_len = min(len(sig1), len(sig2))
        if min_len < 10:
            return 0
        
        max_lag = min(100, min_len // 4)
        sig1 = sig1[:min_len]
        sig2 = sig2[:min_len]
        
        corr = np.correlate(sig1, sig2, mode='full')
        center = len(corr) // 2
        region_start = center - max_lag
        region_end = center + max_lag
        corr_region = corr[region_start:region_end]
        
        peak_idx = np.argmax(np.abs(corr_region))
        lag = peak_idx - max_lag
        
        return lag

    def adaptive_threshold(self, audio: np.ndarray) -> float:
        audio_pre = preemphasis(audio)
        frames = framing(audio_pre, self.config.window_size, self.config.hop_size)
        energy = compute_energy(frames)
        
        noise_floor = np.percentile(energy, 10)
        signal_level = np.percentile(energy, 90)
        
        threshold = noise_floor + (signal_level - noise_floor) * 0.2
        
        return max(threshold, self.config.energy_threshold)

    def set_threshold_from_noise(self, noise_audio: np.ndarray) -> None:
        audio_pre = preemphasis(noise_audio)
        frames = framing(audio_pre, self.config.window_size, self.config.hop_size)
        energy = compute_energy(frames)
        
        noise_mean = np.mean(energy)
        noise_std = np.std(energy)
        
        self.config.energy_threshold = noise_mean + 3 * noise_std


def detect_events(audio: np.ndarray, sample_rate: int, 
                  threshold: float = None) -> List[KeyEvent]:
    config = EventDetectionConfig()
    if threshold is not None:
        config.energy_threshold = threshold
    
    detector = EventDetector(config, sample_rate)
    return detector.detect(audio)
