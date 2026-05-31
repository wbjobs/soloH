import math
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass
from app.constants import SGRNA_LENGTH, PAM_LENGTH


@dataclass
class SequenceFeatures:
    gc_content: float = 0.0
    pam_strength: float = 0.0
    melting_temperature: float = 0.0
    has_poly_t: bool = False
    has_poly_g: bool = False
    dinucleotide_counts: Dict[str, int] = None
    position_specific_scores: List[float] = None
    seed_region_mismatches: int = 0
    distal_region_mismatches: int = 0
    overall_energy: float = 0.0
    hairpin_score: float = 0.0


class EditingEfficiencyPredictor:
    _instance: Optional["EditingEfficiencyPredictor"] = None
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
        self._position_weights = self._init_position_weights()
        self._dinucleotide_effects = self._init_dinucleotide_effects()

    def _init_position_weights(self) -> List[float]:
        weights = [
            0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0, 1.0, 1.0,
            1.0, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2
        ]
        return weights

    def _init_dinucleotide_effects(self) -> Dict[str, float]:
        return {
            "AA": 0.8, "AT": 0.7, "AC": 0.9, "AG": 1.0,
            "TA": 0.7, "TT": 0.6, "TC": 0.8, "TG": 0.9,
            "CA": 1.0, "CT": 0.9, "CC": 1.1, "CG": 1.2,
            "GA": 1.1, "GT": 1.0, "GC": 1.2, "GG": 1.3,
        }

    def predict(
        self,
        sgrna: str,
        target_sequence: str,
        mismatches: int = 0,
        mismatches_details: Optional[List] = None,
    ) -> Tuple[float, SequenceFeatures]:
        features = calculate_sequence_features(
            sgrna, target_sequence, mismatches, mismatches_details
        )

        base_efficiency = self._calculate_base_efficiency(sgrna)
        mismatch_penalty = self._calculate_mismatch_penalty(features)
        gc_effect = self._calculate_gc_effect(features.gc_content)
        pam_effect = self._calculate_pam_effect(target_sequence[-3:])
        position_effect = self._calculate_position_effect(
            sgrna, target_sequence, mismatches_details
        )
        structure_effect = self._calculate_structure_effect(features)

        efficiency = (
            base_efficiency
            * mismatch_penalty
            * gc_effect
            * pam_effect
            * position_effect
            * structure_effect
        )

        efficiency = max(0.0, min(1.0, efficiency))

        return efficiency, features

    def _calculate_base_efficiency(self, sgrna: str) -> float:
        if len(sgrna) < 20:
            return 0.5

        sgrna_only = sgrna[:20].upper()
        base_score = 0.6

        if sgrna_only[19] == "G":
            base_score += 0.1
        if sgrna_only[18] == "G":
            base_score += 0.05
        if sgrna_only[0] == "G":
            base_score += 0.05

        has_run_of_t = "TTTT" in sgrna_only
        if has_run_of_t:
            base_score -= 0.2

        return max(0.3, min(0.9, base_score))

    def _calculate_mismatch_penalty(self, features: SequenceFeatures) -> float:
        seed_penalty = features.seed_region_mismatches * 0.25
        distal_penalty = features.distal_region_mismatches * 0.10
        total_penalty = seed_penalty + distal_penalty
        return max(0.1, 1.0 - total_penalty)

    def _calculate_gc_effect(self, gc_content: float) -> float:
        if gc_content < 0.3 or gc_content > 0.8:
            return 0.5
        elif gc_content < 0.4 or gc_content > 0.7:
            return 0.8
        else:
            return 1.0

    def _calculate_pam_effect(self, pam: str) -> float:
        pam = pam.upper()
        pam_effects = {
            "AGG": 1.0, "TGG": 1.0, "CGG": 1.0, "GGG": 1.0,
            "NAG": 0.8, "AAG": 0.8, "TAG": 0.8, "CAG": 0.8, "GAG": 0.8,
            "NGA": 0.6, "AGA": 0.6, "TGA": 0.6, "CGA": 0.6, "GGA": 0.6,
        }
        return pam_effects.get(pam, 0.3)

    def _calculate_position_effect(
        self,
        sgrna: str,
        target: str,
        mismatches_details: Optional[List],
    ) -> float:
        if not mismatches_details:
            return 1.0

        effect = 1.0
        for mm in mismatches_details:
            pos = mm.position
            if 0 <= pos < len(self._position_weights):
                effect *= 1.0 - self._position_weights[pos] * 0.3

        return max(0.2, effect)

    def _calculate_structure_effect(self, features: SequenceFeatures) -> float:
        effect = 1.0
        if features.hairpin_score > 0.5:
            effect *= 0.8
        if features.has_poly_t:
            effect *= 0.85
        return max(0.5, effect)

    def predict_indel_frequency(
        self,
        sgrna: str,
        target_sequence: str,
        editing_efficiency: float,
        cell_type: Optional[str] = None,
    ) -> Dict[str, float]:
        from app.data_processing.sequence_utils import count_mismatches

        mismatches = count_mismatches(sgrna, target_sequence)

        base_indel_rate = 0.6
        if cell_type == "K562":
            base_indel_rate = 0.65
        elif cell_type == "HEK293":
            base_indel_rate = 0.7
        elif cell_type == "iPSC":
            base_indel_rate = 0.5

        mismatch_penalty = max(0.3, 1.0 - mismatches * 0.1)

        indel_1bp = base_indel_rate * 0.4 * editing_efficiency * mismatch_penalty
        indel_small = base_indel_rate * 0.35 * editing_efficiency * mismatch_penalty
        indel_large = base_indel_rate * 0.1 * editing_efficiency * mismatch_penalty
        no_edit = 1.0 - (indel_1bp + indel_small + indel_large)

        total = indel_1bp + indel_small + indel_large + no_edit
        return {
            "indel_1bp": round(indel_1bp / total, 6),
            "indel_small_2_10bp": round(indel_small / total, 6),
            "indel_large_gt10bp": round(indel_large / total, 6),
            "no_edit": round(no_edit / total, 6),
            "total_indel_frequency": round(
                (indel_1bp + indel_small + indel_large) / total, 6
            ),
        }


def calculate_sequence_features(
    sgrna: str,
    target_sequence: str,
    mismatches: int = 0,
    mismatches_details: Optional[List] = None,
) -> SequenceFeatures:
    sgrna_only = sgrna[:SGRNA_LENGTH].upper()
    target_only = target_sequence[:SGRNA_LENGTH].upper()

    gc_content = sum(1 for b in sgrna_only if b in "GC") / len(sgrna_only)

    pam = target_sequence[-3:].upper() if len(target_sequence) >= 23 else "NGG"
    pam_strength = 1.0 if pam.endswith("GG") else 0.6 if pam.endswith("AG") else 0.4

    tm = calculate_melting_temperature(sgrna_only)

    has_poly_t = "TTTT" in sgrna_only
    has_poly_g = "GGGG" in sgrna_only

    dinucleotide_counts = {}
    for i in range(len(sgrna_only) - 1):
        dinuc = sgrna_only[i : i + 2]
        dinucleotide_counts[dinuc] = dinucleotide_counts.get(dinuc, 0) + 1

    seed_mismatches = 0
    distal_mismatches = 0
    position_scores = [1.0] * SGRNA_LENGTH

    if mismatches_details:
        for mm in mismatches_details:
            pos = mm.position
            if 0 <= pos < 10:
                seed_mismatches += 1
            elif pos < SGRNA_LENGTH:
                distal_mismatches += 1
            if 0 <= pos < len(position_scores):
                position_scores[pos] = 0.0

    energy = calculate_folding_energy(sgrna_only)
    hairpin_score = calculate_hairpin_score(sgrna_only)

    return SequenceFeatures(
        gc_content=gc_content,
        pam_strength=pam_strength,
        melting_temperature=tm,
        has_poly_t=has_poly_t,
        has_poly_g=has_poly_g,
        dinucleotide_counts=dinucleotide_counts,
        position_specific_scores=position_scores,
        seed_region_mismatches=seed_mismatches,
        distal_region_mismatches=distal_mismatches,
        overall_energy=energy,
        hairpin_score=hairpin_score,
    )


def calculate_melting_temperature(sequence: str) -> float:
    seq = sequence.upper()
    n = len(seq)
    if n == 0:
        return 0.0

    count_a = seq.count("A")
    count_t = seq.count("T")
    count_g = seq.count("G")
    count_c = seq.count("C")

    if n <= 14:
        tm = 4 * (count_g + count_c) + 2 * (count_a + count_t)
    else:
        tm = 64.9 + 41 * (count_g + count_c - 16.4) / n

    return tm


def calculate_folding_energy(sequence: str) -> float:
    seq = sequence.upper()
    energy = 0.0

    base_stacking = {
        "AA": -1.0, "AT": -0.9, "AC": -1.1, "AG": -1.2,
        "TA": -0.8, "TT": -1.0, "TC": -1.0, "TG": -1.1,
        "CA": -1.1, "CT": -1.0, "CC": -1.2, "CG": -1.3,
        "GA": -1.2, "GT": -1.1, "GC": -1.3, "GG": -1.4,
    }

    for i in range(len(seq) - 1):
        dinuc = seq[i : i + 2]
        energy += base_stacking.get(dinuc, -1.0)

    return energy


def calculate_hairpin_score(sequence: str) -> float:
    seq = sequence.upper()
    n = len(seq)
    max_score = 0.0

    for stem_len in range(3, n // 3):
        for loop_len in range(3, 8):
            for start in range(n - 2 * stem_len - loop_len + 1):
                stem1 = seq[start : start + stem_len]
                stem2_start = start + stem_len + loop_len
                stem2 = seq[stem2_start : stem2_start + stem_len]
                stem2_rc = "".join(
                    {"A": "T", "T": "A", "C": "G", "G": "C"}.get(b, b)
                    for b in reversed(stem2)
                )

                matches = sum(1 for a, b in zip(stem1, stem2_rc) if a == b)
                score = matches / stem_len if stem_len > 0 else 0

                if score > 0.7 and score > max_score:
                    max_score = score

    return max_score


def predict_indel_frequency(
    sgrna: str,
    target_sequence: str,
    mismatches: int = 0,
    mismatches_details: Optional[List] = None,
    cell_type: Optional[str] = None,
) -> Dict[str, float]:
    predictor = EditingEfficiencyPredictor()
    efficiency, _ = predictor.predict(
        sgrna, target_sequence, mismatches, mismatches_details
    )
    return predictor.predict_indel_frequency(
        sgrna, target_sequence, efficiency, cell_type
    )
