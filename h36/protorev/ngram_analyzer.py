"""n-gram analysis for field boundary detection."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import math


@dataclass
class NGramResult:
    """Result of n-gram analysis."""
    n: int
    frequencies: Dict[bytes, int] = field(default_factory=dict)
    boundary_scores: List[float] = field(default_factory=list)
    probable_boundaries: List[int] = field(default_factory=list)
    total_ngrams: int = 0


@dataclass
class FieldBoundary:
    """Represents a detected field boundary."""
    offset: int
    confidence: float
    supporting_ngrams: List[bytes] = field(default_factory=list)


class NGramAnalyzer:
    """Analyzes byte sequences using n-grams to detect field boundaries."""

    def __init__(self, n_values: Optional[List[int]] = None):
        self.n_values = n_values or [1, 2, 3, 4, 8]

    def extract_ngrams(self, data: bytes, n: int) -> List[bytes]:
        """Extract all n-grams from a byte sequence."""
        if len(data) < n:
            return []
        return [data[i:i + n] for i in range(len(data) - n + 1)]

    def count_ngrams(self, messages: List[bytes], n: int) -> Dict[bytes, int]:
        """Count n-gram frequencies across all messages."""
        counter = Counter()
        for msg in messages:
            ngrams = self.extract_ngrams(msg, n)
            counter.update(ngrams)
        return dict(counter)

    def count_ngrams_by_offset(self, messages: List[bytes], n: int) -> Dict[int, Dict[bytes, int]]:
        """Count n-gram frequencies grouped by their offset position."""
        offset_counts: Dict[int, Counter] = defaultdict(Counter)

        for msg in messages:
            for i in range(len(msg) - n + 1):
                ngram = msg[i:i + n]
                offset_counts[i][ngram] += 1

        return {offset: dict(counts) for offset, counts in offset_counts.items()}

    def calculate_entropy(self, counts: Dict[bytes, int]) -> float:
        """Calculate Shannon entropy of n-gram distribution."""
        total = sum(counts.values())
        if total == 0:
            return 0.0
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    def calculate_boundary_score(self, offset_counts: Dict[int, Dict[bytes, int]], n: int, num_messages: int) -> List[float]:
        """Calculate boundary score for each position.

        High score = likely boundary (low n-gram stability across messages).
        Low score = likely fixed field (high n-gram stability).
        """
        max_offset = max(offset_counts.keys()) if offset_counts else 0
        scores = [0.0] * (max_offset + n)

        for offset in range(max_offset + 1):
            counts = offset_counts.get(offset, {})
            if not counts:
                continue

            total = sum(counts.values())
            if total == 0:
                continue

            max_freq = max(counts.values())
            dominance = max_freq / total
            entropy = self.calculate_entropy(counts)

            normalized_entropy = entropy / math.log2(min(total, 256 ** n)) if total > 1 else 0
            scores[offset] = normalized_entropy * (1 - dominance)

        return scores

    def detect_boundaries(self, messages: List[bytes], threshold: float = 0.3,
                          min_distance: int = 2) -> List[FieldBoundary]:
        """Detect probable field boundaries using multi-scale n-gram analysis."""
        all_scores: Dict[int, List[float]] = {}
        all_offset_counts: Dict[int, Dict[int, Dict[bytes, int]]] = {}

        for n in self.n_values:
            offset_counts = self.count_ngrams_by_offset(messages, n)
            scores = self.calculate_boundary_score(offset_counts, n, len(messages))
            all_scores[n] = scores
            all_offset_counts[n] = offset_counts

        max_len = max(len(scores) for scores in all_scores.values()) if all_scores else 0
        combined_scores = [0.0] * max_len

        for n, scores in all_scores.items():
            weight = 1.0 / n
            for i, score in enumerate(scores):
                if i < max_len:
                    combined_scores[i] += score * weight

        total_weight = sum(1.0 / n for n in self.n_values)
        combined_scores = [s / total_weight for s in combined_scores]

        boundaries = []
        i = 0
        while i < len(combined_scores):
            if combined_scores[i] >= threshold:
                window_end = min(i + min_distance, len(combined_scores))
                window_scores = combined_scores[i:window_end]
                max_idx = i + window_scores.index(max(window_scores))

                supporting = []
                for n in self.n_values:
                    if max_idx in all_offset_counts[n]:
                        top_ngrams = sorted(
                            all_offset_counts[n][max_idx].items(),
                            key=lambda x: -x[1]
                        )[:3]
                        supporting.extend([ng for ng, _ in top_ngrams])

                boundaries.append(FieldBoundary(
                    offset=max_idx,
                    confidence=combined_scores[max_idx],
                    supporting_ngrams=supporting[:5]
                ))
                i = max_idx + min_distance
            else:
                i += 1

        return boundaries

    def analyze(self, messages: List[bytes]) -> Dict[int, NGramResult]:
        """Perform full n-gram analysis for all n values."""
        results = {}

        for n in self.n_values:
            frequencies = self.count_ngrams(messages, n)
            offset_counts = self.count_ngrams_by_offset(messages, n)
            boundary_scores = self.calculate_boundary_score(offset_counts, n, len(messages))

            probable = []
            for i, score in enumerate(boundary_scores):
                if score >= 0.5:
                    probable.append(i)

            results[n] = NGramResult(
                n=n,
                frequencies=frequencies,
                boundary_scores=boundary_scores,
                probable_boundaries=probable,
                total_ngrams=sum(frequencies.values())
            )

        return results

    def find_common_prefixes(self, messages: List[bytes], min_len: int = 2) -> List[Tuple[bytes, int]]:
        """Find common byte prefixes across messages."""
        prefix_counts: Dict[bytes, int] = defaultdict(int)

        for msg in messages:
            for length in range(min_len, min(len(msg), 16) + 1):
                prefix = msg[:length]
                prefix_counts[prefix] += 1

        sorted_prefixes = sorted(
            prefix_counts.items(),
            key=lambda x: (-x[1], -len(x[0]))
        )

        return [(p, c) for p, c in sorted_prefixes if c >= 2]
