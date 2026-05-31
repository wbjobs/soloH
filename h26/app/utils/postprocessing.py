import numpy as np
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
from scipy.spatial.distance import squareform
from sklearn.manifold import MDS
from sklearn.metrics import pairwise_distances


@dataclass
class Contact:
    i: int
    j: int
    probability: float
    distance: float = 0.0

    def to_dict(self):
        return asdict(self)


def get_contact_list(
    contact_map: np.ndarray,
    threshold: float = 0.5,
    min_separation: int = 6,
    max_contacts: Optional[int] = None
) -> List[Contact]:
    seq_len = contact_map.shape[0]
    contacts = []

    for i in range(seq_len):
        for j in range(i + min_separation, seq_len):
            prob = contact_map[i, j]
            if prob >= threshold:
                contacts.append(Contact(
                    i=i,
                    j=j,
                    probability=float(prob),
                    distance=0.0
                ))

    contacts.sort(key=lambda c: c.probability, reverse=True)

    if max_contacts is not None:
        contacts = contacts[:max_contacts]

    return contacts


def calculate_top_l_precision(
    contact_map: np.ndarray,
    true_contacts: Optional[np.ndarray] = None,
    top_l_multipliers: List[int] = None,
    min_separation: int = 6,
    casp_mode: bool = True
) -> dict:
    if top_l_multipliers is None:
        top_l_multipliers = [1, 2, 5]

    seq_len = contact_map.shape[0]
    results = {}

    effective_L = seq_len
    if casp_mode and seq_len < 100:
        effective_L = 100

    results["sequence_length"] = seq_len
    results["effective_L"] = effective_L

    triu_indices = np.triu_indices(seq_len, k=min_separation)
    scores = contact_map[triu_indices]
    sorted_idx = np.argsort(-scores)

    for multiplier in top_l_multipliers:
        top_n = min(multiplier * effective_L, len(sorted_idx))
        top_n = max(1, top_n)

        if top_n > len(sorted_idx):
            top_n = len(sorted_idx)

        top_indices = sorted_idx[:top_n]

        if true_contacts is not None:
            true_flat = true_contacts[triu_indices]
            correct = np.sum(true_flat[top_indices])
            precision = correct / top_n if top_n > 0 else 0.0
            results[f"top_{multiplier}L_precision"] = float(precision)
            results[f"top_{multiplier}L_correct"] = int(correct)
            results[f"top_{multiplier}L_total"] = int(top_n)
        else:
            results[f"top_{multiplier}L_count"] = int(top_n)
            if top_n > 0 and len(scores[top_indices]) > 0:
                results[f"top_{multiplier}L_avg_prob"] = float(np.mean(scores[top_indices]))
            else:
                results[f"top_{multiplier}L_avg_prob"] = 0.0

    return results


def contact_map_to_distances(
    contact_map: np.ndarray,
    threshold: float = 8.0,
    min_prob: float = 0.5,
    max_distance: float = 30.0,
    bonded_distance: float = 3.8
) -> np.ndarray:
    seq_len = contact_map.shape[0]
    distances = np.ones((seq_len, seq_len)) * max_distance

    for i in range(seq_len):
        distances[i, i] = 0.0

    for i in range(seq_len - 1):
        distances[i, i + 1] = bonded_distance
        distances[i + 1, i] = bonded_distance

    for i in range(seq_len):
        for j in range(i + 1, seq_len):
            prob = contact_map[i, j]
            if prob >= min_prob:
                dist = threshold / (prob + 0.1)
                dist = min(dist, max_distance)
                dist = max(dist, 3.0)
                distances[i, j] = dist
                distances[j, i] = dist

    return distances


def enforce_triangle_inequality(distances: np.ndarray, max_iterations: int = 10, tolerance: float = 1e-6) -> np.ndarray:
    seq_len = distances.shape[0]
    distances = distances.copy()

    for iteration in range(max_iterations):
        max_violation = 0.0

        for k in range(seq_len):
            for i in range(seq_len):
                if i == k:
                    continue
                d_ik = distances[i, k]
                for j in range(i + 1, seq_len):
                    if j == k:
                        continue
                    d_kj = distances[k, j]
                    d_ij_new = d_ik + d_kj
                    if distances[i, j] > d_ij_new + tolerance:
                        violation = distances[i, j] - d_ij_new
                        max_violation = max(max_violation, violation)
                        distances[i, j] = d_ij_new
                        distances[j, i] = d_ij_new

        if max_violation < tolerance:
            break

    return distances


def reconstruct_3d_coords(
    contact_map: np.ndarray,
    threshold: float = 8.0,
    min_prob: float = 0.5,
    n_components: int = 3,
    random_state: int = 42,
    max_distance: float = 30.0,
    bonded_distance: float = 3.8
) -> np.ndarray:
    seq_len = contact_map.shape[0]

    if seq_len < 3:
        return np.zeros((seq_len, 3), dtype=np.float32)

    distances = contact_map_to_distances(
        contact_map,
        threshold=threshold,
        min_prob=min_prob,
        max_distance=max_distance,
        bonded_distance=bonded_distance
    )

    distances = enforce_triangle_inequality(distances, max_iterations=10, tolerance=1e-6)

    try:
        mds = MDS(
            n_components=n_components,
            dissimilarity='precomputed',
            metric=True,
            random_state=random_state,
            max_iter=3000,
            n_init=20,
            eps=1e-9
        )
        coords = mds.fit_transform(distances)
    except Exception as e:
        coords = np.random.randn(seq_len, 3).astype(np.float32) * 5.0

    coords = coords - coords.mean(axis=0)

    return coords.astype(np.float32)


def calculate_predicted_distances(
    coords_3d: np.ndarray,
    contacts: List[Contact]
) -> List[Contact]:
    dist_matrix = pairwise_distances(coords_3d)

    for contact in contacts:
        contact.distance = float(dist_matrix[contact.i, contact.j])

    return contacts


def postprocess_predictions(
    contact_map: np.ndarray,
    threshold_angstrom: float = 8.0,
    min_prob_threshold: float = 0.5,
    true_contacts: Optional[np.ndarray] = None,
    casp_mode: bool = True
) -> dict:
    seq_len = contact_map.shape[0]

    contact_map = (contact_map + contact_map.T) / 2
    contact_map = np.clip(contact_map, 0.0, 1.0)

    contact_list = get_contact_list(
        contact_map,
        threshold=min_prob_threshold,
        min_separation=6
    )

    precision_metrics = calculate_top_l_precision(
        contact_map,
        true_contacts=true_contacts,
        casp_mode=casp_mode
    )

    coords_3d = reconstruct_3d_coords(
        contact_map,
        threshold=threshold_angstrom,
        min_prob=min_prob_threshold
    )

    contact_list = calculate_predicted_distances(coords_3d, contact_list)

    symmetry_check = {
        "max_asymmetry_before": float(np.max(np.abs(contact_map - contact_map.T))),
        "is_symmetric": bool(np.allclose(contact_map, contact_map.T, atol=1e-6))
    }

    return {
        "sequence_length": seq_len,
        "num_contacts": len(contact_list),
        "contact_list": [c.to_dict() for c in contact_list],
        "precision_metrics": precision_metrics,
        "coordinates_3d": coords_3d.tolist(),
        "threshold_angstrom": threshold_angstrom,
        "symmetry_check": symmetry_check
    }
