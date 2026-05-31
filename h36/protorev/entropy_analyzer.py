"""Entropy analysis for protocol reverse engineering."""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import math
from collections import Counter
import numpy as np


@dataclass
class EntropyResult:
    """Result of entropy analysis."""
    offset: int
    entropy: float
    byte_counts: Dict[int, int] = field(default_factory=dict)
    unique_bytes: int = 0


@dataclass
class SlidingWindowEntropy:
    """Sliding window entropy analysis result."""
    window_size: int
    positions: List[int] = field(default_factory=list)
    entropies: List[float] = field(default_factory=list)
    low_entropy_regions: List[Tuple[int, int]] = field(default_factory=list)
    high_entropy_regions: List[Tuple[int, int]] = field(default_factory=list)


class EntropyAnalyzer:
    """Analyzes byte entropy to identify protocol structure."""

    def __init__(self, window_size: int = 4, step: int = 1):
        self.window_size = window_size
        self.step = step

    def shannon_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of byte sequence."""
        if not data:
            return 0.0

        length = len(data)
        counts = Counter(data)
        entropy = 0.0

        for count in counts.values():
            p = count / length
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy

    def byte_frequency(self, data: bytes) -> Dict[int, int]:
        """Count frequency of each byte value."""
        return dict(Counter(data))

    def analyze_offset(self, messages: List[bytes], offset: int) -> EntropyResult:
        """Analyze entropy at a specific offset across all messages."""
        bytes_at_offset = []
        for msg in messages:
            if offset < len(msg):
                bytes_at_offset.append(msg[offset])

        if not bytes_at_offset:
            return EntropyResult(offset=offset, entropy=0.0, byte_counts={}, unique_bytes=0)

        counts = Counter(bytes_at_offset)
        entropy = 0.0
        total = len(bytes_at_offset)

        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        return EntropyResult(
            offset=offset,
            entropy=entropy,
            byte_counts=dict(counts),
            unique_bytes=len(counts)
        )

    def analyze_all_offsets(self, messages: List[bytes]) -> List[EntropyResult]:
        """Analyze entropy at each offset position."""
        max_len = max(len(msg) for msg in messages) if messages else 0
        results = []

        for offset in range(max_len):
            results.append(self.analyze_offset(messages, offset))

        return results

    def sliding_window(self, data: bytes) -> SlidingWindowEntropy:
        """Perform sliding window entropy analysis on a single message."""
        if len(data) < self.window_size:
            return SlidingWindowEntropy(window_size=self.window_size)

        positions = []
        entropies = []

        for i in range(0, len(data) - self.window_size + 1, self.step):
            window = data[i:i + self.window_size]
            entropy = self.shannon_entropy(window)
            positions.append(i)
            entropies.append(entropy)

        low_threshold = 2.0
        high_threshold = 6.0

        low_regions = self._find_regions(positions, entropies, low_threshold, 'low')
        high_regions = self._find_regions(positions, entropies, high_threshold, 'high')

        return SlidingWindowEntropy(
            window_size=self.window_size,
            positions=positions,
            entropies=entropies,
            low_entropy_regions=low_regions,
            high_entropy_regions=high_regions
        )

    def _find_regions(self, positions: List[int], entropies: List[float],
                      threshold: float, mode: str) -> List[Tuple[int, int]]:
        """Find contiguous regions above/below threshold."""
        regions = []
        in_region = False
        region_start = 0

        for i, entropy in enumerate(entropies):
            condition = (entropy <= threshold) if mode == 'low' else (entropy >= threshold)

            if condition and not in_region:
                in_region = True
                region_start = positions[i]
            elif not condition and in_region:
                in_region = False
                regions.append((region_start, positions[i - 1] + self.window_size))

        if in_region:
            regions.append((region_start, positions[-1] + self.window_size))

        return regions

    def analyze_messages(self, messages: List[bytes]) -> Dict:
        """Comprehensive entropy analysis of all messages."""
        offset_results = self.analyze_all_offsets(messages)

        entropies = [r.entropy for r in offset_results]
        avg_entropy = np.mean(entropies) if entropies else 0.0
        std_entropy = np.std(entropies) if entropies else 0.0

        low_entropy_offsets = [r.offset for r in offset_results if r.entropy < 2.0]
        high_entropy_offsets = [r.offset for r in offset_results if r.entropy > 6.0]

        overall_entropy = self.shannon_entropy(b''.join(messages))

        single_msg_analysis = []
        for i, msg in enumerate(messages[:10]):
            sw = self.sliding_window(msg)
            single_msg_analysis.append({
                'message_index': i,
                'length': len(msg),
                'overall_entropy': self.shannon_entropy(msg),
                'low_regions': sw.low_entropy_regions,
                'high_regions': sw.high_entropy_regions
            })

        return {
            'offset_entropy': [
                {'offset': r.offset, 'entropy': r.entropy, 'unique_bytes': r.unique_bytes}
                for r in offset_results
            ],
            'average_entropy': avg_entropy,
            'std_entropy': std_entropy,
            'overall_entropy': overall_entropy,
            'low_entropy_offsets': low_entropy_offsets,
            'high_entropy_offsets': high_entropy_offsets,
            'message_analysis': single_msg_analysis
        }

    def classify_region(self, entropy: float) -> str:
        """Classify entropy value into region type."""
        if entropy < 2.0:
            return 'low'
        elif entropy < 4.0:
            return 'medium'
        elif entropy < 6.0:
            return 'high'
        else:
            return 'very_high'

    def get_entropy_heatmap(self, messages: List[bytes], max_messages: int = 50) -> Dict:
        """Generate entropy heatmap data for visualization."""
        if not messages:
            return {}

        max_len = max(len(msg) for msg in messages)
        num_msgs = min(len(messages), max_messages)

        heatmap = np.zeros((num_msgs, max_len))

        for i in range(num_msgs):
            msg = messages[i]
            for j in range(len(msg)):
                if j < max_len:
                    heatmap[i][j] = self.shannon_entropy(bytes([msg[j]]))

            for j in range(len(msg), max_len):
                heatmap[i][j] = float('nan')

        return {
            'heatmap': heatmap.tolist(),
            'max_length': max_len,
            'num_messages': num_msgs
        }
