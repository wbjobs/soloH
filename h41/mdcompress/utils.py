import torch
import numpy as np
from typing import Tuple, Optional, List
import re


ELEMENT_LIST = ["H", "C", "N", "O", "S", "P", "F", "Cl", "Br", "I", "Na", "K", "Mg", "Ca", "Zn", "Fe"]

VDW_RADIUS = {
    "H": 1.20,
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "S": 1.80,
    "P": 1.80,
    "F": 1.47,
    "Cl": 1.75,
    "Br": 1.85,
    "I": 1.98,
    "Na": 2.27,
    "K": 2.75,
    "Mg": 1.73,
    "Ca": 2.31,
    "Zn": 1.39,
    "Fe": 1.63,
}


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def remove_pbc_wrapping(
    coords: np.ndarray,
    box: Optional[np.ndarray] = None,
    reference_coords: Optional[np.ndarray] = None,
) -> np.ndarray:
    n_frames, n_atoms, _ = coords.shape
    unwrapped = coords.copy().astype(np.float64)

    if reference_coords is None:
        reference_coords = coords[0].astype(np.float64)

    prev = reference_coords.astype(np.float64)

    for i in range(n_frames):
        if box is not None and box[i] is not None:
            box_size = np.asarray(box[i], dtype=np.float64)
            diff = unwrapped[i] - prev
            diff = diff - box_size * np.round(diff / box_size)
            unwrapped[i] = prev + diff
        else:
            diff = unwrapped[i] - prev
            for dim in range(3):
                jumps = np.where(np.abs(diff[:, dim]) > 10.0)[0]
                if len(jumps) > 0:
                    pass
        prev = unwrapped[i]

    return unwrapped.astype(np.float32)


def remove_translation_rotation(
    coords: np.ndarray,
    reference_coords: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, List]:
    n_frames, n_atoms, _ = coords.shape
    aligned = np.zeros_like(coords, dtype=np.float64)
    transforms = []

    if reference_coords is None:
        reference_coords = coords[0].astype(np.float64)

    ref_centered, ref_center = center_coords(reference_coords.astype(np.float64))

    for i in range(n_frames):
        frame_coords = coords[i].astype(np.float64)
        R, frame_center, _ = kabsch_alignment(frame_coords, reference_coords.astype(np.float64))
        centered = frame_coords - frame_center
        aligned[i] = centered @ R + ref_center
        transforms.append((R, frame_center, ref_center))

    return aligned.astype(np.float32), transforms


def normalize_coords(coords: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = coords.mean(axis=(0, 1))
    std = coords.std(axis=(0, 1)) + 1e-8
    normalized = (coords - mean) / std
    return normalized, mean, std


def denormalize_coords(
    coords: np.ndarray, mean: np.ndarray, std: np.ndarray
) -> np.ndarray:
    return coords * std + mean


def center_coords(coords: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    center = coords.mean(axis=0, keepdims=True)
    centered = coords - center
    return centered, center


def kabsch_alignment(P: np.ndarray, Q: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    P_centered, P_center = center_coords(P.astype(np.float64))
    Q_centered, Q_center = center_coords(Q.astype(np.float64))
    H = P_centered.T @ Q_centered
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1, 1, d])
    R = U @ D @ Vt
    return R.astype(np.float64), P_center, Q_center


def compute_rmsd(P: np.ndarray, Q: np.ndarray) -> float:
    R, P_center, Q_center = kabsch_alignment(P, Q)
    P_centered = P.astype(np.float64) - P_center
    Q_centered = Q.astype(np.float64) - Q_center
    P_aligned = P_centered @ R
    diff = P_aligned - Q_centered
    return float(np.sqrt(np.mean(np.sum(diff**2, axis=1))))


def compute_bond_length(
    coords: np.ndarray,
    i: int,
    j: int,
    box: Optional[np.ndarray] = None,
) -> float:
    coords = coords.astype(np.float64)
    diff = coords[i] - coords[j]
    if box is not None:
        box = np.asarray(box, dtype=np.float64)
        diff = diff - box * np.round(diff / box)
    return float(np.linalg.norm(diff))


def compute_bond_lengths_batch(
    coords: np.ndarray,
    bond_pairs: List[Tuple[int, int]],
    box: Optional[np.ndarray] = None,
) -> np.ndarray:
    coords = coords.astype(np.float64)
    n_frames = coords.shape[0]
    n_bonds = len(bond_pairs)
    bond_lengths = np.zeros((n_frames, n_bonds), dtype=np.float64)

    for frame_idx in range(n_frames):
        frame_box = box[frame_idx] if box is not None else None
        for bond_idx, (i, j) in enumerate(bond_pairs):
            bond_lengths[frame_idx, bond_idx] = compute_bond_length(
                coords[frame_idx], i, j, frame_box
            )

    return bond_lengths


def build_bond_list(
    atom_types: list,
    coords: np.ndarray,
    cutoff: float = 2.0,
    elements: Optional[List[str]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    n_atoms = len(atom_types)
    coords_f64 = coords.astype(np.float64)
    diff = coords_f64[:, None, :] - coords_f64[None, :, :]
    dist_matrix = np.sqrt(np.sum(diff**2, axis=2))

    edges = []
    edge_attr = []

    for i in range(n_atoms):
        for j in range(i + 1, n_atoms):
            if dist_matrix[i, j] < cutoff:
                edges.append([i, j])
                edges.append([j, i])
                edge_attr.append([float(dist_matrix[i, j])])
                edge_attr.append([float(dist_matrix[i, j])])

    if len(edges) == 0:
        edges = np.zeros((2, 0), dtype=np.int64)
        edge_attr = np.zeros((0, 1), dtype=np.float32)
    else:
        edges = np.array(edges, dtype=np.int64).T
        edge_attr = np.array(edge_attr, dtype=np.float32)

    return edges, edge_attr


def get_element_from_atom_name(atom_name: str, residue_name: Optional[str] = None) -> str:
    atom_name = atom_name.strip()
    upper_name = atom_name.upper()

    ion_atom_names = {
        'NA': 'Na', 'K': 'K', 'MG': 'Mg', 'CA': 'Ca', 'ZN': 'Zn', 'FE': 'Fe',
        'CL': 'Cl', 'BR': 'Br', 'I': 'I', 'F': 'F', 'LI': 'Li', 'CS': 'Cs',
        'MN': 'Mn', 'CO': 'Co', 'CU': 'Cu', 'NI': 'Ni', 'CD': 'Cd',
        'HG': 'Hg', 'AG': 'Ag', 'AU': 'Au', 'PT': 'Pt', 'PD': 'Pd',
        'CAL': 'Ca', 'SOD': 'Na', 'POT': 'K', 'CLA': 'Cl', 'MG2': 'Mg',
        'CA2': 'Ca', 'ZN2': 'Zn', 'FE2': 'Fe', 'FE3': 'Fe',
    }

    protein_backbone_atoms = {
        'N', 'CA', 'C', 'O', 'OXT', 'H', 'HA',
    }

    protein_sidechain_carbon = {
        'CB', 'CG', 'CD', 'CE', 'CZ', 'CG1', 'CG2', 'CD1', 'CD2', 'CE1', 'CE2', 'CE3',
        'CZ1', 'CZ2', 'CZ3', 'CH2',
    }

    protein_sidechain_nitrogen = {
        'ND1', 'ND2', 'NE1', 'NE2', 'NE', 'NZ', 'NH1', 'NH2', 'NH',
    }

    protein_sidechain_oxygen = {
        'OD1', 'OD2', 'OE1', 'OE2', 'OG', 'OG1', 'OG2', 'OH', 'OX1', 'OX2',
    }

    protein_sidechain_sulfur = {
        'SG', 'SD',
    }

    water_atoms = {
        'OW', 'OH2', 'H2O', 'WAT', 'SOL',
    }

    if upper_name in ion_atom_names:
        if upper_name in protein_backbone_atoms and residue_name is not None:
            res_upper = residue_name.upper()
            standard_amino_acids = {
                'ALA', 'ARG', 'ASN', 'ASP', 'CYS', 'GLN', 'GLU', 'GLY',
                'HIS', 'ILE', 'LEU', 'LYS', 'MET', 'PHE', 'PRO', 'SER',
                'THR', 'TRP', 'TYR', 'VAL', 'HID', 'HIE', 'HIP',
            }
            if res_upper in standard_amino_acids:
                if upper_name == 'CA':
                    return 'C'

        if upper_name in protein_backbone_atoms:
            if upper_name == 'CA':
                return 'C'
            if upper_name in ['N', 'C', 'O']:
                return upper_name
            if upper_name.startswith('H'):
                return 'H'

        return ion_atom_names[upper_name]

    if upper_name in protein_backbone_atoms:
        if upper_name == 'CA':
            return 'C'
        if upper_name in ['N', 'C', 'O']:
            return upper_name
        if upper_name.startswith('H'):
            return 'H'

    if upper_name in protein_sidechain_carbon:
        return 'C'
    if upper_name in protein_sidechain_nitrogen:
        return 'N'
    if upper_name in protein_sidechain_oxygen:
        return 'O'
    if upper_name in protein_sidechain_sulfur:
        return 'S'

    if upper_name.startswith('H') and len(upper_name) >= 1:
        if len(upper_name) == 1 or (len(upper_name) == 2 and upper_name[1].isdigit()):
            return 'H'
        if upper_name in ['HA', 'HB', 'HG', 'HD', 'HE', 'HH', 'HW'] or upper_name.startswith(('HA', 'HB', 'HG', 'HD', 'HE', 'HH', 'HW')):
            return 'H'

    if len(upper_name) > 0 and upper_name[0].isdigit():
        rest = upper_name.lstrip('0123456789')
        if rest.startswith('H'):
            return 'H'
        if rest.startswith('C'):
            return 'C'
        if rest.startswith('N'):
            return 'N'
        if rest.startswith('O'):
            return 'O'
        if rest.startswith('S'):
            return 'S'
        if rest.startswith('P'):
            return 'P'
        if rest.startswith('F'):
            return 'F'
        if rest.startswith('CL'):
            return 'Cl'
        if rest.startswith('BR'):
            return 'Br'
        if rest.startswith('I'):
            return 'I'

    patterns = [
        r'^([A-Z][a-z]?)',
        r'^([A-Z])',
    ]

    for pattern in patterns:
        match = re.match(pattern, atom_name)
        if match:
            elem = match.group(1).capitalize()
            if elem in ELEMENT_LIST:
                return elem

    for pattern in patterns:
        match = re.match(pattern, upper_name)
        if match:
            elem = match.group(1).capitalize()
            if elem in ELEMENT_LIST:
                return elem

    if len(upper_name) > 0:
        for c in upper_name:
            if c in ['H', 'C', 'N', 'O', 'S', 'P', 'F', 'I']:
                return c

    return 'C'


def get_element_from_mda(atom) -> str:
    try:
        elem = getattr(atom, 'element', None)
        if elem is not None:
            elem_str = str(elem).strip().capitalize()
            if elem_str in ELEMENT_LIST:
                return elem_str
    except (AttributeError, ValueError):
        pass

    return get_element_from_atom_name(atom.name)


def atom_type_to_feature(
    atom_type: str,
    element: Optional[str] = None,
    mass: Optional[float] = None,
) -> np.ndarray:
    if element is None:
        element = get_element_from_atom_name(atom_type)

    element = element.capitalize()
    if element not in ELEMENT_LIST:
        element = 'C'

    elem_idx = ELEMENT_LIST.index(element)
    elem_onehot = np.zeros(len(ELEMENT_LIST), dtype=np.float32)
    elem_onehot[elem_idx] = 1.0

    mass_values = {
        'H': 1.008, 'C': 12.011, 'N': 14.007, 'O': 15.999,
        'S': 32.06, 'P': 30.974, 'F': 18.998, 'Cl': 35.45,
        'Br': 79.904, 'I': 126.904, 'Na': 22.99, 'K': 39.098,
        'Mg': 24.305, 'Ca': 40.078, 'Zn': 65.38, 'Fe': 55.845,
    }

    if mass is None:
        mass = mass_values.get(element, 12.011)

    normalized_mass = np.clip(mass / 100.0, 0.0, 2.0)

    is_hydrogen = 1.0 if element == 'H' else 0.0
    is_heavy = 0.0 if element == 'H' else 1.0
    is_backbone = 1.0 if atom_type.upper() in ['CA', 'C', 'N', 'O'] else 0.0

    feature = np.concatenate([
        elem_onehot,
        [normalized_mass, is_hydrogen, is_heavy, is_backbone],
    ])

    return feature.astype(np.float32)


def get_atom_feature_dim() -> int:
    return len(ELEMENT_LIST) + 4


def get_vdw_radius(element: str) -> float:
    return VDW_RADIUS.get(element, 1.5)


def get_vdw_radii_from_features(atom_features: np.ndarray) -> np.ndarray:
    n_atoms = atom_features.shape[0]
    radii = np.zeros(n_atoms, dtype=np.float64)
    for i in range(n_atoms):
        elem_idx = np.argmax(atom_features[i, :len(ELEMENT_LIST)])
        element = ELEMENT_LIST[elem_idx]
        radii[i] = VDW_RADIUS.get(element, 1.5)
    return radii


def compute_rmsf(coords: np.ndarray) -> np.ndarray:
    n_frames, n_atoms, _ = coords.shape
    coords_f64 = coords.astype(np.float64)
    mean_coords = np.mean(coords_f64, axis=0)
    diff = coords_f64 - mean_coords
    rmsf = np.sqrt(np.mean(np.sum(diff * diff, axis=-1), axis=0))
    return rmsf.astype(np.float32)


def compute_rmsf_preservation(
    rmsf_true: np.ndarray,
    rmsf_pred: np.ndarray,
) -> dict:
    rmsf_true_f64 = rmsf_true.astype(np.float64)
    rmsf_pred_f64 = rmsf_pred.astype(np.float64)

    correlation = np.corrcoef(rmsf_true_f64, rmsf_pred_f64)[0, 1]

    abs_diff = np.abs(rmsf_true_f64 - rmsf_pred_f64)
    mae = np.mean(abs_diff)

    with np.errstate(divide='ignore', invalid='ignore'):
        rel_diff = np.where(
            rmsf_true_f64 > 1e-8,
            abs_diff / rmsf_true_f64 * 100.0,
            0.0
        )
    mean_relative_error = np.mean(rel_diff)

    ratio = np.where(
        rmsf_true_f64 > 1e-8,
        rmsf_pred_f64 / rmsf_true_f64,
        1.0
    )
    mean_ratio = np.mean(ratio)

    return {
        "correlation": float(correlation) if not np.isnan(correlation) else 0.0,
        "mae": float(mae),
        "mean_relative_error_percent": float(mean_relative_error),
        "mean_ratio": float(mean_ratio),
        "rmsf_true": rmsf_true,
        "rmsf_pred": rmsf_pred,
    }
