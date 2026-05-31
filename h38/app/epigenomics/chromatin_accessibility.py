import os
import re
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from app.config import get_settings
from app.constants import CHROMOSOMES


@dataclass
class ATACPeak:
    chromosome: str
    start: int
    end: int
    name: str = ""
    score: float = 0.0
    strand: str = "."
    signal_value: float = 0.0
    p_value: float = 0.0
    q_value: float = 0.0
    peak_point: Optional[int] = None


@dataclass
class ChromatinAccessibility:
    _instance: Optional["ChromatinAccessibility"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        settings = get_settings()
        self.atac_peak_path: Optional[str] = getattr(
            settings, "ATAC_PEAK_PATH", None
        )
        self.peaks: Dict[str, List[ATACPeak]] = {}
        self._initialized = True
        self._loaded = False

        if self.atac_peak_path and os.path.exists(self.atac_peak_path):
            self._load_peaks()

    def _load_peaks(self):
        if not self.atac_peak_path or not os.path.exists(self.atac_peak_path):
            return

        try:
            with open(self.atac_peak_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    parts = line.split("\t")
                    if len(parts) < 3:
                        continue

                    chrom = parts[0]
                    start = int(parts[1])
                    end = int(parts[2])
                    name = parts[3] if len(parts) > 3 else ""
                    score = float(parts[4]) if len(parts) > 4 else 0.0
                    strand = parts[5] if len(parts) > 5 else "."
                    signal = float(parts[6]) if len(parts) > 6 else 0.0
                    p_val = float(parts[7]) if len(parts) > 7 else 0.0
                    q_val = float(parts[8]) if len(parts) > 8 else 0.0
                    peak_point = int(parts[9]) if len(parts) > 9 else None

                    peak = ATACPeak(
                        chromosome=chrom,
                        start=start,
                        end=end,
                        name=name,
                        score=score,
                        strand=strand,
                        signal_value=signal,
                        p_value=p_val,
                        q_value=q_val,
                        peak_point=peak_point,
                    )

                    if chrom not in self.peaks:
                        self.peaks[chrom] = []
                    self.peaks[chrom].append(peak)

            for chrom in self.peaks:
                self.peaks[chrom].sort(key=lambda x: x.start)

            self._loaded = True
        except Exception as e:
            print(f"Warning: Could not load ATAC-seq peaks: {e}")
            self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def get_overlapping_peaks(
        self,
        chromosome: str,
        start: int,
        end: int,
        extend: int = 1000,
    ) -> List[ATACPeak]:
        if not self._loaded or chromosome not in self.peaks:
            return []

        search_start = max(0, start - extend)
        search_end = end + extend

        peaks = self.peaks[chromosome]
        results = []

        left, right = 0, len(peaks)
        while left < right:
            mid = (left + right) // 2
            if peaks[mid].end < search_start:
                left = mid + 1
            else:
                right = mid

        for i in range(left, len(peaks)):
            peak = peaks[i]
            if peak.start > search_end:
                break
            if peak.end >= search_start and peak.start <= search_end:
                results.append(peak)

        return results

    def get_accessibility(
        self,
        chromosome: str,
        position: int,
        window: int = 2000,
    ) -> Tuple[float, Optional[ATACPeak]]:
        if not self._loaded:
            return 0.5, None

        start = max(0, position - window // 2)
        end = position + window // 2

        peaks = self.get_overlapping_peaks(chromosome, start, end)

        if not peaks:
            return 0.0, None

        max_signal = max(p.signal_value for p in peaks) if peaks else 0.0
        nearest_peak = min(
            peaks,
            key=lambda p: min(
                abs(position - p.start),
                abs(position - p.end),
                abs(position - (p.start + p.end) // 2),
            ),
        )

        accessibility = min(1.0, max_signal / 100.0) if max_signal > 0 else 0.0

        return accessibility, nearest_peak


def calculate_accessibility_score(
    accessibility: float,
    site_in_peak: bool = True,
    distance_to_peak: float = 0,
    peak_signal: float = 0,
) -> float:
    if accessibility <= 0:
        return 0.1

    if site_in_peak:
        base_score = 0.5 + accessibility * 0.5
    else:
        distance_penalty = max(0.0, 1.0 - distance_to_peak / 5000.0)
        base_score = 0.3 + accessibility * 0.5 * distance_penalty

    return max(0.1, min(1.0, base_score))


def correct_offtarget_score(
    original_score: float,
    accessibility_score: float,
    weight: float = 0.3,
) -> float:
    if accessibility_score <= 0:
        accessibility_score = 0.1

    corrected = original_score * (1 - weight + weight * accessibility_score)

    return max(0.0, min(1.0, corrected))


def get_chromatin_accessibility() -> ChromatinAccessibility:
    return ChromatinAccessibility()
