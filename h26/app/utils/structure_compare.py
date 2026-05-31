import numpy as np
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass, asdict
from scipy.spatial.distance import cdist
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class StructureComparisonResult:
    tm_score: float
    gdt_ts: float
    gdt_ha: float
    rmsd: float
    aligned_length: int
    sequence_identity: float
    contact_map_similarity: float
    per_residue_errors: List[Dict]
    aligned_positions: List[int]
    transformation: Optional[Dict] = None

    def to_dict(self):
        return {
            "tm_score": float(self.tm_score),
            "gdt_ts": float(self.gdt_ts),
            "gdt_ha": float(self.gdt_ha),
            "rmsd": float(self.rmsd),
            "aligned_length": int(self.aligned_length),
            "sequence_identity": float(self.sequence_identity),
            "contact_map_similarity": float(self.contact_map_similarity),
            "per_residue_errors": self.per_residue_errors,
            "aligned_positions": [int(p) for p in self.aligned_positions],
            "transformation": self.transformation
        }


def parse_pdb_coordinates(
    pdb_content: str,
    atom_type: str = "CA"
) -> Tuple[np.ndarray, str, List[int]]:
    coords = []
    sequence = []
    residue_numbers = []

    current_residue = None

    atom_pattern = re.compile(
        r'^ATOM\s+(\d+)\s+(\S+)\s+(\S+)\s+\S?\s*(\d+)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)'
    )

    three_to_one = {
        'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C',
        'GLN': 'Q', 'GLU': 'E', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
        'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F', 'PRO': 'P',
        'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V'
    }

    for line in pdb_content.splitlines():
        line = line.rstrip()

        if line.startswith("ATOM"):
            match = atom_pattern.match(line)
            if not match:
                continue

            atom_name = match.group(2).strip()
            residue_name = match.group(3).strip()
            residue_num = int(match.group(4))
            x = float(match.group(5))
            y = float(match.group(6))
            z = float(match.group(7))

            if atom_name == atom_type:
                if residue_num != current_residue:
                    coords.append([x, y, z])
                    sequence.append(three_to_one.get(residue_name, 'X'))
                    residue_numbers.append(residue_num)
                    current_residue = residue_num

    if not coords:
        raise ValueError(f"No {atom_type} atoms found in PDB content")

    coords_array = np.array(coords, dtype=np.float32)
    sequence_str = ''.join(sequence)

    return coords_array, sequence_str, residue_numbers


def kabsch_alignment(
    coords_pred: np.ndarray,
    coords_true: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    assert coords_pred.shape == coords_true.shape, "Coordinate shapes must match"
    assert coords_pred.shape[1] == 3, "Coordinates must be 3D"

    centroid_pred = np.mean(coords_pred, axis=0)
    centroid_true = np.mean(coords_true, axis=0)

    coords_pred_centered = coords_pred - centroid_pred
    coords_true_centered = coords_true - centroid_true

    H = coords_pred_centered.T @ coords_true_centered

    U, S, Vt = np.linalg.svd(H)

    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1, 1, d])
    R = Vt.T @ D @ U.T

    t = centroid_true - R @ centroid_pred

    coords_aligned = (R @ coords_pred.T).T + t

    rmsd = np.sqrt(np.mean(np.sum((coords_aligned - coords_true) ** 2, axis=1)))

    return R, t, coords_aligned, rmsd


def calculate_tm_score(
    coords_pred: np.ndarray,
    coords_true: np.ndarray,
    d0: Optional[float] = None
) -> Tuple[float, int, List[int]]:
    n_min = min(len(coords_pred), len(coords_true))
    L_target = len(coords_true)

    if d0 is None:
        d0 = 1.24 * (L_target - 15) ** (1.0 / 3.0) - 1.8
        d0 = max(d0, 0.5)

    best_tm = 0.0
    best_aligned = []
    best_alignment_indices = []

    for start_pred in range(0, len(coords_pred) - n_min + 1):
        for start_true in range(0, len(coords_true) - n_min + 1):
            subset_pred = coords_pred[start_pred:start_pred + n_min]
            subset_true = coords_true[start_true:start_true + n_min]

            try:
                R, t, coords_aligned, rmsd = kabsch_alignment(subset_pred, subset_true)

                distances = np.sqrt(np.sum((coords_aligned - subset_true) ** 2, axis=1))
                tm_scores = 1.0 / (1.0 + (distances / d0) ** 2)
                tm_score = np.sum(tm_scores) / L_target

                aligned = np.where(distances < 5.0)[0]

                if tm_score > best_tm:
                    best_tm = tm_score
                    best_aligned = aligned.tolist()
                    best_alignment_indices = list(range(start_pred, start_pred + n_min))
            except Exception as e:
                logger.warning(f"Alignment failed: {e}")
                continue

    return best_tm, len(best_aligned), best_alignment_indices


def calculate_gdt(
    coords_pred: np.ndarray,
    coords_true: np.ndarray,
    thresholds: List[float] = None
) -> Dict[str, float]:
    if thresholds is None:
        thresholds = [1.0, 2.0, 4.0, 8.0]

    try:
        R, t, coords_aligned, rmsd = kabsch_alignment(coords_pred, coords_true)
    except Exception as e:
        logger.warning(f"Kabsch alignment failed for GDT: {e}")
        return {f"gdt_{int(t*10)}": 0.0 for t in thresholds}

    distances = np.sqrt(np.sum((coords_aligned - coords_true) ** 2, axis=1))

    gdt_scores = {}
    for t in thresholds:
        fraction = np.sum(distances < t) / len(distances)
        gdt_scores[f"gdt_{int(t*10)}"] = float(fraction)

    gdt_ts = (gdt_scores["gdt_10"] + gdt_scores["gdt_20"] + gdt_scores["gdt_40"] + gdt_scores["gdt_80"]) / 4.0
    gdt_ha = (gdt_scores["gdt_10"] + gdt_scores["gdt_20"] + 2 * gdt_scores["gdt_40"] + 2 * gdt_scores["gdt_80"]) / 6.0

    gdt_scores["gdt_ts"] = float(gdt_ts)
    gdt_scores["gdt_ha"] = float(gdt_ha)

    return gdt_scores


def calculate_contact_map_similarity(
    contact_map_pred: np.ndarray,
    coords_true: np.ndarray,
    threshold: float = 8.0,
    min_separation: int = 6
) -> Tuple[float, np.ndarray]:
    seq_len = len(coords_true)

    dist_matrix_true = cdist(coords_true, coords_true)
    true_contacts = (dist_matrix_true < threshold).astype(float)

    mask = np.zeros_like(true_contacts, dtype=bool)
    for i in range(seq_len):
        for j in range(i + min_separation, seq_len):
            mask[i, j] = True
            mask[j, i] = True

    if contact_map_pred.shape != true_contacts.shape:
        if contact_map_pred.shape[0] < seq_len:
            pad_width = seq_len - contact_map_pred.shape[0]
            contact_map_pred = np.pad(
                contact_map_pred,
                ((0, pad_width), (0, pad_width)),
                mode='constant'
            )
        else:
            contact_map_pred = contact_map_pred[:seq_len, :seq_len]

    pred_contacts = (contact_map_pred > 0.5).astype(float)

    tp = np.sum(np.logical_and(pred_contacts == 1, true_contacts == 1) & mask)
    fp = np.sum(np.logical_and(pred_contacts == 1, true_contacts == 0) & mask)
    fn = np.sum(np.logical_and(pred_contacts == 0, true_contacts == 1) & mask)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return float(f1), true_contacts


def calculate_sequence_identity(seq1: str, seq2: str) -> float:
    if len(seq1) != len(seq2):
        min_len = min(len(seq1), len(seq2))
        seq1 = seq1[:min_len]
        seq2 = seq2[:min_len]

    matches = sum(1 for a, b in zip(seq1, seq2) if a == b)
    return matches / len(seq1) if len(seq1) > 0 else 0.0


def compare_with_alphafold(
    predicted_coords: np.ndarray,
    predicted_contact_map: np.ndarray,
    alphafold_pdb_content: str,
    threshold_angstrom: float = 8.0
) -> StructureComparisonResult:
    try:
        af_coords, af_sequence, af_residue_numbers = parse_pdb_coordinates(
            alphafold_pdb_content,
            atom_type="CA"
        )
    except Exception as e:
        raise ValueError(f"Failed to parse AlphaFold PDB: {e}")

    n_min = min(len(predicted_coords), len(af_coords))
    pred_subset = predicted_coords[:n_min]
    af_subset = af_coords[:n_min]

    try:
        R, t, coords_aligned, rmsd = kabsch_alignment(pred_subset, af_subset)
        transformation = {
            "rotation_matrix": R.tolist(),
            "translation_vector": t.tolist()
        }
    except Exception as e:
        logger.warning(f"Kabsch alignment failed: {e}")
        coords_aligned = pred_subset
        rmsd = float('inf')
        transformation = None

    per_residue_errors = []
    for i in range(n_min):
        error = float(np.linalg.norm(coords_aligned[i] - af_subset[i]))
        per_residue_errors.append({
            "residue_index": i,
            "pdb_residue_number": af_residue_numbers[i] if i < len(af_residue_numbers) else i,
            "error_angstrom": error,
            "within_threshold": error < threshold_angstrom
        })

    tm_score, aligned_length, aligned_positions = calculate_tm_score(
        pred_subset, af_subset
    )

    gdt_scores = calculate_gdt(pred_subset, af_subset)

    contact_similarity, true_contacts = calculate_contact_map_similarity(
        predicted_contact_map,
        af_coords,
        threshold=threshold_angstrom
    )

    seq_pred_len = len(predicted_coords)
    seq_af = af_sequence[:seq_pred_len] if len(af_sequence) >= seq_pred_len else af_sequence
    seq_pred = "X" * seq_pred_len
    seq_identity = calculate_sequence_identity(seq_pred, seq_af)

    return StructureComparisonResult(
        tm_score=tm_score,
        gdt_ts=gdt_scores["gdt_ts"],
        gdt_ha=gdt_scores["gdt_ha"],
        rmsd=rmsd if rmsd != float('inf') else 0.0,
        aligned_length=aligned_length,
        sequence_identity=seq_identity,
        contact_map_similarity=contact_similarity,
        per_residue_errors=per_residue_errors,
        aligned_positions=aligned_positions,
        transformation=transformation
    )
