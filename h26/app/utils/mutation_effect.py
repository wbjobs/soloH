import torch
import numpy as np
from typing import List, Tuple, Dict, Optional, Callable
from dataclasses import dataclass, asdict
import logging

from app.utils.fasta_parser import AMINO_ACIDS, AMINO_ACID_ORDER
from app.utils.encoding import get_sequence_features, build_input_tensor
from app.utils.pssm import create_dummy_pssm

logger = logging.getLogger(__name__)


@dataclass
class MutationResult:
    position: int
    wild_type: str
    mutant: str
    contact_map_change: float
    affected_contacts: List[Dict]
    structure_change_score: float
    functional_impact: str
    delta_probability: float

    def to_dict(self):
        return {
            "position": int(self.position),
            "wild_type": self.wild_type,
            "mutant": self.mutant,
            "contact_map_change": float(self.contact_map_change),
            "affected_contacts": self.affected_contacts,
            "structure_change_score": float(self.structure_change_score),
            "functional_impact": self.functional_impact,
            "delta_probability": float(self.delta_probability)
        }


def predict_mutation_effect(
    model: torch.nn.Module,
    sequence: str,
    position: int,
    mutant_aa: str,
    model_name: str,
    device: Optional[str] = None,
    threshold: float = 0.5
) -> MutationResult:
    seq_len = len(sequence)

    if position < 0 or position >= seq_len:
        raise ValueError(f"Position {position} out of range (0-{seq_len-1})")

    if mutant_aa not in AMINO_ACIDS:
        raise ValueError(f"Invalid mutant amino acid: {mutant_aa}")

    wild_type_aa = sequence[position]
    if wild_type_aa not in AMINO_ACIDS:
        raise ValueError(f"Invalid wild type amino acid at position {position}: {wild_type_aa}")

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = model.to(device)
    model.eval()

    mutant_sequence = sequence[:position] + mutant_aa + sequence[position + 1:]

    with torch.no_grad():
        wt_pssm = create_dummy_pssm(sequence)
        wt_features = get_sequence_features(sequence, wt_pssm)
        wt_input = build_input_tensor(wt_features).to(device)
        wt_contact_map = model(wt_input).squeeze(0).cpu().numpy()

        mt_pssm = create_dummy_pssm(mutant_sequence)
        mt_features = get_sequence_features(mutant_sequence, mt_pssm)
        mt_input = build_input_tensor(mt_features).to(device)
        mt_contact_map = model(mt_input).squeeze(0).cpu().numpy()

    wt_contact_map = (wt_contact_map + wt_contact_map.T) / 2
    mt_contact_map = (mt_contact_map + mt_contact_map.T) / 2

    contact_map_change = np.mean(np.abs(wt_contact_map - mt_contact_map))

    wt_prob_at_pos = np.mean([
        np.mean(wt_contact_map[position, :]),
        np.mean(wt_contact_map[:, position])
    ])
    mt_prob_at_pos = np.mean([
        np.mean(mt_contact_map[position, :]),
        np.mean(mt_contact_map[:, position])
    ])
    delta_probability = mt_prob_at_pos - wt_prob_at_pos

    affected_contacts = []
    for i in range(seq_len):
        for j in range(i + 6, seq_len):
            if i == position or j == position:
                wt_prob = wt_contact_map[i, j]
                mt_prob = mt_contact_map[i, j]
                if abs(wt_prob - mt_prob) > 0.1:
                    affected_contacts.append({
                        "i": int(i),
                        "j": int(j),
                        "wild_type_probability": float(wt_prob),
                        "mutant_probability": float(mt_prob),
                        "delta": float(mt_prob - wt_prob),
                        "is_significant": abs(wt_prob - mt_prob) > 0.3 and max(wt_prob, mt_prob) > threshold
                    })

    affected_contacts.sort(key=lambda x: abs(x["delta"]), reverse=True)

    structure_change_score = calculate_structure_change_score(
        wt_contact_map, mt_contact_map, threshold
    )

    functional_impact = classify_functional_impact(
        contact_map_change,
        len([c for c in affected_contacts if c["is_significant"]]),
        delta_probability
    )

    return MutationResult(
        position=position,
        wild_type=wild_type_aa,
        mutant=mutant_aa,
        contact_map_change=contact_map_change,
        affected_contacts=affected_contacts[:20],
        structure_change_score=structure_change_score,
        functional_impact=functional_impact,
        delta_probability=delta_probability
    )


def calculate_structure_change_score(
    wt_map: np.ndarray,
    mt_map: np.ndarray,
    threshold: float = 0.5
) -> float:
    wt_contacts = wt_map > threshold
    mt_contacts = mt_map > threshold

    gained = np.sum(np.logical_and(~wt_contacts, mt_contacts))
    lost = np.sum(np.logical_and(wt_contacts, ~mt_contacts))
    total = np.sum(wt_contacts) + 1e-8

    score = (gained + lost) / (2 * total)

    high_prob_change = 0
    for i in range(wt_map.shape[0]):
        for j in range(i + 1, wt_map.shape[1]):
            if abs(wt_map[i, j] - mt_map[i, j]) > 0.5:
                high_prob_change += 1

    score += 0.5 * high_prob_change / (wt_map.shape[0] ** 2)

    return min(score, 1.0)


def classify_functional_impact(
    contact_map_change: float,
    significant_changes: int,
    delta_probability: float
) -> str:
    if contact_map_change > 0.15 or significant_changes > 10 or abs(delta_probability) > 0.2:
        return "high"
    elif contact_map_change > 0.08 or significant_changes > 5 or abs(delta_probability) > 0.1:
        return "medium"
    elif contact_map_change > 0.03 or significant_changes > 0 or abs(delta_probability) > 0.03:
        return "low"
    else:
        return "neutral"


def scan_all_mutations(
    model: torch.nn.Module,
    sequence: str,
    model_name: str,
    positions: Optional[List[int]] = None,
    device: Optional[str] = None,
    threshold: float = 0.5
) -> List[MutationResult]:
    if positions is None:
        positions = list(range(len(sequence)))

    results = []
    for pos in positions:
        wt_aa = sequence[pos]
        for mutant_aa in AMINO_ACID_ORDER:
            if mutant_aa != wt_aa:
                try:
                    result = predict_mutation_effect(
                        model, sequence, pos, mutant_aa, model_name, device, threshold
                    )
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Failed to predict mutation {wt_aa}{pos}{mutant_aa}: {e}")

    return results


def analyze_mutation_impact(
    mutation_results: List[MutationResult]
) -> Dict:
    if not mutation_results:
        return {"summary": "No mutations analyzed"}

    impact_counts = {"high": 0, "medium": 0, "low": 0, "neutral": 0}
    position_effects: Dict[int, float] = {}

    for result in mutation_results:
        impact_counts[result.functional_impact] += 1

        pos = result.position
        if pos not in position_effects:
            position_effects[pos] = 0
        position_effects[pos] += abs(result.contact_map_change)

    hotspot_positions = sorted(
        position_effects.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    total_mutations = len(mutation_results)
    impact_percentages = {
        k: v / total_mutations * 100 for k, v in impact_counts.items()
    }

    avg_contact_change = np.mean([r.contact_map_change for r in mutation_results])
    max_contact_change = np.max([r.contact_map_change for r in mutation_results])

    return {
        "total_mutations": total_mutations,
        "impact_counts": impact_counts,
        "impact_percentages": impact_percentages,
        "hotspot_positions": [
            {"position": int(pos), "average_effect": float(effect)}
            for pos, effect in hotspot_positions
        ],
        "avg_contact_map_change": float(avg_contact_change),
        "max_contact_map_change": float(max_contact_change),
        "most_damaging": max(
            mutation_results,
            key=lambda r: r.structure_change_score
        ).to_dict() if mutation_results else None
    }
