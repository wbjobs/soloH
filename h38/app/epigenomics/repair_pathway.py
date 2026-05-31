import re
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass
from app.constants import SGRNA_LENGTH


@dataclass
class RepairPathwayResult:
    nhej_ratio: float
    hdr_ratio: float
    alt_nhej_ratio: float
    ssa_ratio: float
    mmej_ratio: float
    microhomology_score: float
    dsb_position: int
    cell_type_effect: float
    confidence: float


class RepairPathwayPredictor:
    _instance: Optional["RepairPathwayPredictor"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._cell_type_biases = self._init_cell_type_biases()

    def _init_cell_type_biases(self) -> Dict[str, Dict[str, float]]:
        return {
            "default": {"nhej": 0.70, "hdr": 0.10, "alt_nhej": 0.15, "ssa": 0.03, "mmej": 0.02},
            "HEK293": {"nhej": 0.65, "hdr": 0.15, "alt_nhej": 0.12, "ssa": 0.05, "mmej": 0.03},
            "K562": {"nhej": 0.72, "hdr": 0.08, "alt_nhej": 0.13, "ssa": 0.04, "mmej": 0.03},
            "iPSC": {"nhej": 0.55, "hdr": 0.25, "alt_nhej": 0.12, "ssa": 0.05, "mmej": 0.03},
            "Jurkat": {"nhej": 0.68, "hdr": 0.10, "alt_nhej": 0.15, "ssa": 0.04, "mmej": 0.03},
            "U2OS": {"nhej": 0.60, "hdr": 0.20, "alt_nhej": 0.13, "ssa": 0.04, "mmej": 0.03},
        }

    def predict(
        self,
        target_sequence: str,
        cut_site: Optional[int] = None,
        cell_type: str = "default",
        has_hdr_template: bool = False,
        template_concentration: float = 1.0,
        chromatin_accessibility: float = 0.5,
        cell_cycle_phase: Optional[str] = None,
    ) -> RepairPathwayResult:
        seq_length = len(target_sequence)
        if cut_site is None:
            cut_site = seq_length - 6 if seq_length >= 6 else seq_length // 2

        microhomology_score = calculate_microhomology_score(
            target_sequence, cut_site
        )

        gc_content = sum(1 for b in target_sequence.upper() if b in "GC") / max(
            1, seq_length
        )

        sequence_bias = self._calculate_sequence_bias(
            target_sequence, cut_site, microhomology_score
        )

        base_ratios = self._cell_type_biases.get(
            cell_type, self._cell_type_biases["default"]
        )

        nhej = base_ratios["nhej"]
        hdr = base_ratios["hdr"]
        alt_nhej = base_ratios["alt_nhej"]
        ssa = base_ratios["ssa"]
        mmej = base_ratios["mmej"]

        if has_hdr_template:
            hdr_boost = 1.0 + template_concentration * 2.0
            if cell_cycle_phase == "S/G2":
                hdr_boost *= 2.0
            elif cell_cycle_phase == "G1":
                hdr_boost *= 0.3
            hdr *= hdr_boost

        if microhomology_score > 0.3:
            mmej_boost = 1.0 + microhomology_score * 2.0
            mmej *= mmej_boost
            alt_nhej *= 1.0 + microhomology_score * 0.5

        if chromatin_accessibility < 0.3:
            nhej *= 0.8
            hdr *= 0.7
            alt_nhej *= 1.2

        gc_effect = 1.0
        if gc_content < 0.3 or gc_content > 0.7:
            gc_effect = 0.8
            nhej *= gc_effect
            hdr *= gc_effect

        total = nhej + hdr + alt_nhej + ssa + mmej
        nhej_ratio = nhej / total
        hdr_ratio = hdr / total
        alt_nhej_ratio = alt_nhej / total
        ssa_ratio = ssa / total
        mmej_ratio = mmej / total

        confidence = self._calculate_confidence(
            microhomology_score, chromatin_accessibility, gc_content
        )

        return RepairPathwayResult(
            nhej_ratio=round(nhej_ratio, 6),
            hdr_ratio=round(hdr_ratio, 6),
            alt_nhej_ratio=round(alt_nhej_ratio, 6),
            ssa_ratio=round(ssa_ratio, 6),
            mmej_ratio=round(mmej_ratio, 6),
            microhomology_score=round(microhomology_score, 6),
            dsb_position=cut_site,
            cell_type_effect=1.0 if cell_type == "default" else 0.85,
            confidence=round(confidence, 6),
        )

    def _calculate_sequence_bias(
        self,
        sequence: str,
        cut_site: int,
        microhomology_score: float,
    ) -> float:
        bias = 1.0

        if cut_site + 3 < len(sequence):
            pam_region = sequence[cut_site : cut_site + 3].upper()
            if pam_region.endswith("GG"):
                bias *= 1.1

        if cut_site >= 3:
            pre_cut = sequence[cut_site - 3 : cut_site].upper()
            if pre_cut.count("AT") > 0:
                bias *= 1.05

        if microhomology_score > 0.5:
            bias *= 0.9

        return max(0.5, min(1.5, bias))

    def _calculate_confidence(
        self,
        microhomology_score: float,
        chromatin_accessibility: float,
        gc_content: float,
    ) -> float:
        confidence = 0.7

        if microhomology_score > 0.2:
            confidence += 0.1

        if 0.3 <= chromatin_accessibility <= 0.7:
            confidence += 0.1

        if 0.4 <= gc_content <= 0.6:
            confidence += 0.05

        return max(0.5, min(1.0, confidence))

    def get_repair_products(
        self,
        result: RepairPathwayResult,
        total_events: int = 1000,
    ) -> Dict[str, int]:
        return {
            "nhej_events": int(result.nhej_ratio * total_events),
            "hdr_events": int(result.hdr_ratio * total_events),
            "alt_nhej_events": int(result.alt_nhej_ratio * total_events),
            "ssa_events": int(result.ssa_ratio * total_events),
            "mmej_events": int(result.mmej_ratio * total_events),
        }

    def suggest_optimization(
        self,
        result: RepairPathwayResult,
        target_hdr_ratio: float = 0.3,
    ) -> Dict[str, str]:
        suggestions = {}

        if result.hdr_ratio < target_hdr_ratio:
            suggestions["hdr_enhancement"] = (
                "Consider using HDR enhancers (e.g., L755507, Brefeldin A) "
                "or cell cycle synchronization to S/G2 phase"
            )

        if result.mmej_ratio > 0.05 and result.microhomology_score > 0.3:
            suggestions["mmej_suppression"] = (
                "High microhomology detected. MMEJ may compete with HDR. "
                "Consider using MMEJ inhibitors or optimizing sgRNA design"
            )

        if result.confidence < 0.7:
            suggestions["validation"] = (
                "Low confidence prediction. Consider experimental validation "
                "with NGS-based assays"
            )

        if result.hdr_ratio >= target_hdr_ratio:
            suggestions["optimization_status"] = (
                "HDR ratio meets target. Consider validating with functional assay"
            )

        return suggestions


def calculate_microhomology_score(
    sequence: str,
    cut_site: int,
    max_mh_length: int = 15,
    max_search_distance: int = 50,
) -> float:
    seq = sequence.upper()
    n = len(seq)

    if cut_site < 0 or cut_site >= n:
        return 0.0

    max_score = 0.0

    for mh_length in range(3, max_mh_length + 1):
        if cut_site - mh_length < 0 or cut_site + mh_length >= n:
            continue

        left_seq = seq[cut_site - mh_length : cut_site]

        max_right = min(cut_site + mh_length + max_search_distance, n)
        for right_start in range(cut_site, max_right - mh_length + 1):
            right_seq = seq[right_start : right_start + mh_length]

            if left_seq == right_seq:
                distance = right_start - cut_site
                score = mh_length / max_mh_length
                distance_penalty = max(0.0, 1.0 - distance / max_search_distance)
                combined_score = score * (0.5 + 0.5 * distance_penalty)

                if combined_score > max_score:
                    max_score = combined_score

    for mh_length in range(3, max_mh_length + 1):
        if cut_site + mh_length >= n or cut_site - mh_length < 0:
            continue

        right_seq = seq[cut_site : cut_site + mh_length]

        min_left = max(0, cut_site - mh_length - max_search_distance)
        for left_end in range(min_left + mh_length, cut_site):
            left_start = left_end - mh_length
            left_seq = seq[left_start:left_end]

            if left_seq == right_seq:
                distance = cut_site - left_end
                score = mh_length / max_mh_length
                distance_penalty = max(0.0, 1.0 - distance / max_search_distance)
                combined_score = score * (0.5 + 0.5 * distance_penalty)

                if combined_score > max_score:
                    max_score = combined_score

    return max_score


def predict_repair_pathways(
    target_sequence: str,
    cut_site: Optional[int] = None,
    cell_type: str = "default",
    has_hdr_template: bool = False,
    template_concentration: float = 1.0,
    chromatin_accessibility: float = 0.5,
    cell_cycle_phase: Optional[str] = None,
) -> RepairPathwayResult:
    predictor = RepairPathwayPredictor()
    return predictor.predict(
        target_sequence=target_sequence,
        cut_site=cut_site,
        cell_type=cell_type,
        has_hdr_template=has_hdr_template,
        template_concentration=template_concentration,
        chromatin_accessibility=chromatin_accessibility,
        cell_cycle_phase=cell_cycle_phase,
    )
