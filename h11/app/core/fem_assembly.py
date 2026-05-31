import numpy as np
from scipy.sparse import csr_matrix, lil_matrix
from typing import Dict, List, Tuple, Optional, Union


ComplexFloat = Union[float, complex]


def compute_lame_parameters(rho: ComplexFloat, v_l: ComplexFloat, v_s: ComplexFloat) -> Tuple[ComplexFloat, ComplexFloat]:
    mu = rho * v_s ** 2
    lambda_ = rho * v_l ** 2 - 2 * mu
    return lambda_, mu


def compute_complex_sound_velocity(v_real: float, loss_factor: float = 0.0,
                                    loss_model: str = 'viscous') -> complex:
    if loss_factor == 0.0:
        return complex(v_real, 0.0)

    if loss_model.lower() == 'viscous':
        v_complex = complex(v_real, v_real * loss_factor)
    elif loss_model.lower() == 'hysteretic':
        v_complex = v_real * np.sqrt(complex(1.0, loss_factor))
    elif loss_model.lower() == 'rayleigh':
        v_complex = v_real / np.sqrt(complex(1.0, -loss_factor))
    else:
        raise ValueError(f"Unknown loss model: {loss_model}")

    return v_complex


def convert_material_to_complex(material: Dict, loss_models: Optional[Dict] = None) -> Dict:
    if loss_models is None:
        loss_models = {}

    v_l = material.get('sound_velocity_longitudinal', 0.0)
    v_s = material.get('sound_velocity_shear', 0.0)
    rho = material.get('density', 0.0)

    loss_factor_l = material.get('loss_factor_longitudinal', 0.0)
    loss_factor_s = material.get('loss_factor_shear', 0.0)
    loss_model = material.get('loss_model', loss_models.get('default', 'viscous'))

    if 'loss_factor' in material:
        loss_factor_l = material['loss_factor']
        loss_factor_s = material['loss_factor']

    v_l_complex = compute_complex_sound_velocity(v_l, loss_factor_l, loss_model)
    v_s_complex = compute_complex_sound_velocity(v_s, loss_factor_s, loss_model)

    return {
        'name': material.get('name', 'unknown'),
        'density': complex(rho, 0.0),
        'sound_velocity_longitudinal': v_l_complex,
        'sound_velocity_shear': v_s_complex,
        'loss_factor_longitudinal': loss_factor_l,
        'loss_factor_shear': loss_factor_s,
        'loss_model': loss_model
    }


def assemble_element_matrices_sh(points: np.ndarray, element: np.ndarray,
                                  rho: ComplexFloat, v_s: ComplexFloat) -> Tuple[np.ndarray, np.ndarray]:
    xi = points[element, 0]
    eta = points[element, 1]

    J = np.array([
        [xi[1] - xi[0], xi[2] - xi[0]],
        [eta[1] - eta[0], eta[2] - eta[0]]
    ], dtype=np.complex128 if isinstance(rho, complex) or isinstance(v_s, complex) else np.float64)
    detJ = np.linalg.det(J)
    invJ = np.linalg.inv(J)

    area = 0.5 * abs(detJ)

    dtype = np.complex128 if isinstance(rho, complex) or isinstance(v_s, complex) else np.float64
    B = np.zeros((2, 3), dtype=dtype)
    B[0, 0] = -1
    B[0, 1] = 1
    B[0, 2] = 0
    B[1, 0] = -1
    B[1, 1] = 0
    B[1, 2] = 1

    B = invJ.T @ B

    mu = rho * v_s ** 2

    k_e = mu * area * (B.T @ B)

    m_e = (rho * area / 12) * np.array([
        [2, 1, 1],
        [1, 2, 1],
        [1, 1, 2]
    ], dtype=dtype)

    return k_e, m_e


def assemble_element_matrices_psv(points: np.ndarray, element: np.ndarray,
                                   rho: ComplexFloat, v_l: ComplexFloat,
                                   v_s: ComplexFloat) -> Tuple[np.ndarray, np.ndarray]:
    xi = points[element, 0]
    eta = points[element, 1]

    J = np.array([
        [xi[1] - xi[0], xi[2] - xi[0]],
        [eta[1] - eta[0], eta[2] - eta[0]]
    ], dtype=np.complex128 if isinstance(rho, complex) or isinstance(v_l, complex) or isinstance(v_s, complex) else np.float64)
    detJ = np.linalg.det(J)
    invJ = np.linalg.inv(J)

    area = 0.5 * abs(detJ)

    lambda_, mu = compute_lame_parameters(rho, v_l, v_s)

    dN_dxi = np.array([
        [-1, 1, 0],
        [-1, 0, 1]
    ])
    dN_dxy = invJ @ dN_dxi

    dtype = np.complex128 if isinstance(rho, complex) or isinstance(v_l, complex) or isinstance(v_s, complex) else np.float64
    B = np.zeros((3, 6), dtype=dtype)
    for i in range(3):
        B[0, 2 * i] = dN_dxy[0, i]
        B[1, 2 * i + 1] = dN_dxy[1, i]
        B[2, 2 * i] = dN_dxy[1, i]
        B[2, 2 * i + 1] = dN_dxy[0, i]

    C = np.array([
        [lambda_ + 2 * mu, lambda_, 0],
        [lambda_, lambda_ + 2 * mu, 0],
        [0, 0, mu]
    ], dtype=dtype)

    k_e = area * (B.T @ C @ B)

    m_e = np.zeros((6, 6), dtype=dtype)
    for i in range(3):
        for j in range(3):
            val = (1 + (i == j)) * rho * area / 24
            m_e[2 * i, 2 * j] = val
            m_e[2 * i + 1, 2 * j + 1] = val

    return k_e, m_e


def assemble_global_matrices(mesh: Dict, material_properties: List[Dict],
                              wave_type: str = 'sh',
                              has_complex_materials: bool = False) -> Tuple[csr_matrix, csr_matrix]:
    points = mesh['vertices']
    triangles = mesh['triangles']
    material_ids = mesh.get('materials', np.zeros(len(triangles), dtype=int))

    n_nodes = len(points)

    if wave_type.lower() == 'sh':
        n_dof = n_nodes
    elif wave_type.lower() == 'psv':
        n_dof = 2 * n_nodes
    else:
        raise ValueError(f"Unknown wave type: {wave_type}")

    if not has_complex_materials:
        for e, elem in enumerate(triangles):
            mat_id = material_ids[e]
            if mat_id >= len(material_properties):
                mat_id = 0

            mat = material_properties[mat_id]
            rho = mat['density']
            v_l = mat['sound_velocity_longitudinal']
            v_s = mat['sound_velocity_shear']

            if isinstance(rho, complex) or isinstance(v_l, complex) or isinstance(v_s, complex):
                has_complex_materials = True
                break

    dtype = np.complex128 if has_complex_materials else np.float64
    K = lil_matrix((n_dof, n_dof), dtype=dtype)
    M = lil_matrix((n_dof, n_dof), dtype=dtype)

    for e, elem in enumerate(triangles):
        mat_id = material_ids[e]
        if mat_id >= len(material_properties):
            mat_id = 0

        mat = material_properties[mat_id]
        rho = mat['density']
        v_l = mat['sound_velocity_longitudinal']
        v_s = mat['sound_velocity_shear']

        if wave_type.lower() == 'sh':
            k_e, m_e = assemble_element_matrices_sh(points, elem, rho, v_s)
            for i in range(3):
                for j in range(3):
                    K[elem[i], elem[j]] += k_e[i, j]
                    M[elem[i], elem[j]] += m_e[i, j]
        else:
            k_e, m_e = assemble_element_matrices_psv(points, elem, rho, v_l, v_s)
            for i in range(3):
                for j in range(3):
                    K[2 * elem[i]:2 * elem[i] + 2, 2 * elem[j]:2 * elem[j] + 2] += k_e[2 * i:2 * i + 2, 2 * j:2 * j + 2]
                    M[2 * elem[i]:2 * elem[i] + 2, 2 * elem[j]:2 * elem[j] + 2] += m_e[2 * i:2 * i + 2, 2 * j:2 * j + 2]

    return K.tocsr(), M.tocsr()


def apply_bloch_boundary_conditions(K: csr_matrix, M: csr_matrix,
                                     kx: float, ky: float,
                                     boundary_info: Dict,
                                     unit_cell_size: Tuple[float, float],
                                     wave_type: str = 'sh') -> Tuple[csr_matrix, csr_matrix, np.ndarray, Dict]:
    lx, ly = unit_cell_size
    paired_x = boundary_info['paired_x']
    paired_y = boundary_info['paired_y']
    interior_nodes = boundary_info['interior_nodes']

    n_nodes = K.shape[0] if wave_type.lower() == 'sh' else K.shape[0] // 2
    n_dof = K.shape[0]

    phase_x = np.exp(1j * kx * lx)
    phase_y = np.exp(1j * ky * ly)

    node_map = {}
    reduced_dof_list = []
    current_dof = 0

    if wave_type.lower() == 'sh':
        for node in interior_nodes:
            node_map[node] = current_dof
            reduced_dof_list.append(node)
            current_dof += 1

        for ln, rn in paired_x:
            if rn not in node_map and ln in node_map:
                node_map[rn] = -1

        for bn, tn in paired_y:
            if tn not in node_map and bn in node_map:
                node_map[tn] = -1
    else:
        for node in interior_nodes:
            node_map[2 * node] = current_dof
            node_map[2 * node + 1] = current_dof + 1
            reduced_dof_list.extend([2 * node, 2 * node + 1])
            current_dof += 2

        for ln, rn in paired_x:
            if 2 * rn not in node_map and 2 * ln in node_map:
                node_map[2 * rn] = -1
                node_map[2 * rn + 1] = -1

        for bn, tn in paired_y:
            if 2 * tn not in node_map and 2 * bn in node_map:
                node_map[2 * tn] = -1
                node_map[2 * tn + 1] = -1

    n_reduced = current_dof

    K_reduced = lil_matrix((n_reduced, n_reduced), dtype=complex)
    M_reduced = lil_matrix((n_reduced, n_reduced), dtype=complex)

    K_full = K.tocoo()
    M_full = M.tocoo()

    def get_dof_mapping(dof):
        if wave_type.lower() == 'sh':
            node = dof
        else:
            node = dof // 2

        is_x_pair = False
        is_y_pair = False
        base_node = node
        phase = 1.0

        for ln, rn in paired_x:
            if node == rn and ln in node_map:
                base_node = ln
                is_x_pair = True
                phase *= phase_x
                break

        for bn, tn in paired_y:
            if node == tn and bn in node_map:
                if is_x_pair:
                    pass
                else:
                    base_node = bn
                is_y_pair = True
                phase *= phase_y
                break

        if wave_type.lower() == 'sh':
            if base_node in node_map and node_map[base_node] >= 0:
                return node_map[base_node], phase
        else:
            if 2 * base_node in node_map and node_map[2 * base_node] >= 0:
                if dof % 2 == 0:
                    return node_map[2 * base_node], phase
                else:
                    return node_map[2 * base_node + 1], phase

        return None, 0

    for i, j, val in zip(K_full.row, K_full.col, K_full.data):
        i_map, phase_i = get_dof_mapping(i)
        j_map, phase_j = get_dof_mapping(j)

        if i_map is not None and j_map is not None:
            K_reduced[i_map, j_map] += val * phase_i * np.conj(phase_j)

    for i, j, val in zip(M_full.row, M_full.col, M_full.data):
        i_map, phase_i = get_dof_mapping(i)
        j_map, phase_j = get_dof_mapping(j)

        if i_map is not None and j_map is not None:
            M_reduced[i_map, j_map] += val * phase_i * np.conj(phase_j)

    dof_mapping = np.array(reduced_dof_list)

    return K_reduced.tocsr(), M_reduced.tocsr(), dof_mapping, node_map
