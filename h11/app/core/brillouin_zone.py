import numpy as np
from typing import List, Tuple, Dict


def generate_brillouin_zone_path(lattice: str = 'square',
                                   lattice_constant: float = 1.0,
                                   n_points_per_segment: int = 50,
                                   ensure_symmetry: bool = True) -> Dict:
    if lattice.lower() == 'square':
        return generate_square_brillouin_zone(lattice_constant, n_points_per_segment, ensure_symmetry)
    elif lattice.lower() == 'hexagonal' or lattice.lower() == 'triangular':
        return generate_hexagonal_brillouin_zone(lattice_constant, n_points_per_segment, ensure_symmetry)
    elif lattice.lower() == 'rectangular':
        return generate_rectangular_brillouin_zone(lattice_constant, n_points_per_segment, ensure_symmetry)
    else:
        raise ValueError(f"Unsupported lattice type: {lattice}")


def generate_symmetric_path(start: np.ndarray, end: np.ndarray, n_points: int,
                             ensure_symmetry: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    if ensure_symmetry and n_points % 2 == 1:
        n_points += 1

    segment = np.linspace(start, end, n_points, endpoint=True)
    distances = np.zeros(n_points)
    for i in range(1, n_points):
        distances[i] = distances[i - 1] + np.linalg.norm(segment[i] - segment[i - 1])

    return segment, distances


def generate_square_brillouin_zone(a: float, n_points: int = 50, ensure_symmetry: bool = True) -> Dict:
    b1 = 2 * np.pi / a
    b2 = 2 * np.pi / a

    Gamma = np.array([0.0, 0.0])
    X = np.array([b1 / 2, 0.0])
    M = np.array([b1 / 2, b2 / 2])

    path_segments = [
        ('Gamma', 'X', Gamma, X),
        ('X', 'M', X, M),
        ('M', 'Gamma', M, Gamma)
    ]

    all_k_points = []
    all_distances = []
    label_positions = {}
    cumulative_dist = 0.0
    current_idx = 0

    for seg_idx, (start_label, end_label, start, end) in enumerate(path_segments):
        if seg_idx == len(path_segments) - 1:
            n_seg = n_points
        else:
            n_seg = n_points if ensure_symmetry else n_points

        segment, distances = generate_symmetric_path(start, end, n_seg, ensure_symmetry)

        if seg_idx > 0:
            segment = segment[1:]
            distances = distances[1:] + cumulative_dist

        if start_label not in label_positions.values():
            label_positions[current_idx] = start_label

        all_k_points.extend(segment.tolist())
        all_distances.extend(distances.tolist())

        cumulative_dist = distances[-1] if len(distances) > 0 else cumulative_dist
        current_idx = len(all_k_points)
        label_positions[current_idx - 1] = end_label

    k_points = np.array(all_k_points)
    cumulative_dists = np.array(all_distances)

    if ensure_symmetry:
        k_points, cumulative_dists, label_positions = enforce_time_reversal_symmetry(
            k_points, cumulative_dists, label_positions, a, 'square'
        )

    return {
        'k_points': k_points,
        'cumulative_dist': cumulative_dists,
        'label_positions': label_positions,
        'high_symmetry_points': {
            'Gamma': Gamma,
            'X': X,
            'M': M
        },
        'reciprocal_lattice_vectors': {
            'b1': np.array([b1, 0]),
            'b2': np.array([0, b2])
        }
    }


def generate_rectangular_brillouin_zone(a: float, n_points: int = 50, ensure_symmetry: bool = True) -> Dict:
    b1 = 2 * np.pi / a
    b2 = 2 * np.pi / a

    Gamma = np.array([0.0, 0.0])
    X = np.array([b1 / 2, 0.0])
    S = np.array([b1 / 2, b2 / 2])
    Y = np.array([0.0, b2 / 2])

    path_segments = [
        ('Gamma', 'X', Gamma, X),
        ('X', 'S', X, S),
        ('S', 'Y', S, Y),
        ('Y', 'Gamma', Y, Gamma)
    ]

    all_k_points = []
    all_distances = []
    label_positions = {}
    cumulative_dist = 0.0
    current_idx = 0

    for seg_idx, (start_label, end_label, start, end) in enumerate(path_segments):
        segment, distances = generate_symmetric_path(start, end, n_points, ensure_symmetry)

        if seg_idx > 0:
            segment = segment[1:]
            distances = distances[1:] + cumulative_dist

        if start_label not in label_positions.values():
            label_positions[current_idx] = start_label

        all_k_points.extend(segment.tolist())
        all_distances.extend(distances.tolist())

        cumulative_dist = distances[-1] if len(distances) > 0 else cumulative_dist
        current_idx = len(all_k_points)
        label_positions[current_idx - 1] = end_label

    k_points = np.array(all_k_points)
    cumulative_dists = np.array(all_distances)

    if ensure_symmetry:
        k_points, cumulative_dists, label_positions = enforce_time_reversal_symmetry(
            k_points, cumulative_dists, label_positions, a, 'rectangular'
        )

    return {
        'k_points': k_points,
        'cumulative_dist': cumulative_dists,
        'label_positions': label_positions,
        'high_symmetry_points': {
            'Gamma': Gamma,
            'X': X,
            'S': S,
            'Y': Y
        },
        'reciprocal_lattice_vectors': {
            'b1': np.array([b1, 0]),
            'b2': np.array([0, b2])
        }
    }


def generate_hexagonal_brillouin_zone(a: float, n_points: int = 50, ensure_symmetry: bool = True) -> Dict:
    b1 = 2 * np.pi / (a * np.sqrt(3)) * np.array([np.sqrt(3), 1.0])
    b2 = 2 * np.pi / (a * np.sqrt(3)) * np.array([0.0, 2.0])

    Gamma = np.array([0.0, 0.0])
    M = 0.5 * b1
    K = (b1 + b2) / 3.0

    path_segments = [
        ('Gamma', 'M', Gamma, M),
        ('M', 'K', M, K),
        ('K', 'Gamma', K, Gamma)
    ]

    all_k_points = []
    all_distances = []
    label_positions = {}
    cumulative_dist = 0.0
    current_idx = 0

    for seg_idx, (start_label, end_label, start, end) in enumerate(path_segments):
        segment, distances = generate_symmetric_path(start, end, n_points, ensure_symmetry)

        if seg_idx > 0:
            segment = segment[1:]
            distances = distances[1:] + cumulative_dist

        if start_label not in label_positions.values():
            label_positions[current_idx] = start_label

        all_k_points.extend(segment.tolist())
        all_distances.extend(distances.tolist())

        cumulative_dist = distances[-1] if len(distances) > 0 else cumulative_dist
        current_idx = len(all_k_points)
        label_positions[current_idx - 1] = end_label

    k_points = np.array(all_k_points)
    cumulative_dists = np.array(all_distances)

    if ensure_symmetry:
        k_points, cumulative_dists, label_positions = enforce_time_reversal_symmetry(
            k_points, cumulative_dists, label_positions, a, 'hexagonal'
        )

    return {
        'k_points': k_points,
        'cumulative_dist': cumulative_dists,
        'label_positions': label_positions,
        'high_symmetry_points': {
            'Gamma': Gamma,
            'M': M,
            'K': K
        },
        'reciprocal_lattice_vectors': {
            'b1': b1,
            'b2': b2
        }
    }


def enforce_time_reversal_symmetry(k_points: np.ndarray, cumulative_dist: np.ndarray,
                                    label_positions: Dict, a: float, lattice: str) -> Tuple:
    tol = 1e-10
    n_k = len(k_points)

    for i in range(n_k):
        kx, ky = k_points[i]
        for j in range(n_k):
            if j != i and np.allclose(k_points[j], [-kx, -ky], atol=tol):
                break
        else:
            pass

    for idx, label in list(label_positions.items()):
        if label == 'Gamma' and idx > 0:
            if not np.allclose(k_points[idx], [0, 0], atol=tol):
                k_points[idx] = np.array([0.0, 0.0])

        if label == 'X' and lattice in ['square', 'rectangular']:
            expected_kx = np.pi / a
            if abs(k_points[idx, 0] - expected_kx) > tol or abs(k_points[idx, 1]) > tol:
                k_points[idx] = np.array([expected_kx, 0.0])

        if label == 'M' and lattice in ['square', 'rectangular']:
            expected_k = np.pi / a
            if abs(k_points[idx, 0] - expected_k) > tol or abs(k_points[idx, 1] - expected_k) > tol:
                k_points[idx] = np.array([expected_k, expected_k])

    corrected_labels = {}
    for idx, label in label_positions.items():
        if idx < len(k_points):
            corrected_labels[idx] = label

    corrected_dists = np.zeros_like(cumulative_dist)
    for i in range(1, len(cumulative_dist)):
        corrected_dists[i] = corrected_dists[i - 1] + np.linalg.norm(k_points[i] - k_points[i - 1])

    return k_points, corrected_dists, corrected_labels


def get_brillouin_zone_boundary(lattice: str, a: float) -> np.ndarray:
    if lattice.lower() == 'square':
        b1 = 2 * np.pi / a
        b2 = 2 * np.pi / a
        boundary = np.array([
            [b1 / 2, -b2 / 2],
            [b1 / 2, b2 / 2],
            [-b1 / 2, b2 / 2],
            [-b1 / 2, -b2 / 2],
            [b1 / 2, -b2 / 2]
        ])
    elif lattice.lower() == 'hexagonal' or lattice.lower() == 'triangular':
        b1 = 2 * np.pi / (a * np.sqrt(3)) * np.array([np.sqrt(3), 1])
        b2 = 2 * np.pi / (a * np.sqrt(3)) * np.array([0, 2])
        n_vertices = 6
        angles = np.linspace(0, 2 * np.pi, n_vertices + 1, endpoint=True)
        boundary = np.zeros((n_vertices + 1, 2))
        for i, theta in enumerate(angles):
            if i < n_vertices:
                angle1 = theta + np.pi / 6
                normal = np.array([np.cos(angle1), np.sin(angle1)])
                d = np.pi / (a * np.sqrt(3)) * 2 / np.sqrt(3)
                boundary[i] = normal * d / np.dot(normal, normal) * np.linalg.norm(normal)
            else:
                boundary[i] = boundary[0]

        boundary_alt = np.zeros((7, 2))
        pts = [
            (b1 + b2) / 3,
            (2 * b2 - b1) / 3,
            b2 - b1,
            -(b1 + b2) / 3,
            (b1 - 2 * b2) / 3,
            b1 - b2
        ]
        for i, pt in enumerate(pts):
            boundary_alt[i] = pt
        boundary_alt[6] = boundary_alt[0]
        boundary = boundary_alt
    else:
        raise ValueError(f"Unsupported lattice type: {lattice}")
    return boundary
