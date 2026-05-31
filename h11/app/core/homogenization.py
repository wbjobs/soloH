import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import spsolve
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class HomogenizationResult:
    effective_density: np.ndarray
    effective_modulus: np.ndarray
    effective_velocity_longitudinal: float
    effective_velocity_shear: float
    volume_fractions: Dict[str, float]
    cell_velocity_field: Optional[np.ndarray] = None
    cell_strain_field: Optional[np.ndarray] = None
    chi_fields: Optional[List[np.ndarray]] = None


def compute_volume_fractions(mesh: Dict, material_properties: List[Dict]) -> Dict[str, float]:
    triangles = mesh['triangles']
    vertices = mesh['vertices']
    material_ids = mesh.get('materials', np.zeros(len(triangles), dtype=int))

    total_area = 0.0
    material_areas = {}

    for e, elem in enumerate(triangles):
        xi = vertices[elem, 0]
        eta = vertices[elem, 1]

        area = 0.5 * abs(
            (xi[1] - xi[0]) * (eta[2] - eta[0]) -
            (xi[2] - xi[0]) * (eta[1] - eta[0])
        )

        mat_id = material_ids[e]
        mat_name = material_properties[mat_id].get('name', f'material_{mat_id}')

        total_area += area
        if mat_name in material_areas:
            material_areas[mat_name] += area
        else:
            material_areas[mat_name] = area

    volume_fractions = {}
    for name, area in material_areas.items():
        volume_fractions[name] = area / total_area if total_area > 0 else 0.0

    return volume_fractions


def compute_effective_density(volume_fractions: Dict[str, float],
                                material_properties: List[Dict]) -> np.ndarray:
    rho_eff = 0.0
    for mat in material_properties:
        name = mat.get('name', 'unknown')
        rho = mat.get('density', 0.0)
        vf = volume_fractions.get(name, 0.0)
        rho_eff += vf * rho

    return np.array([
        [rho_eff, 0.0],
        [0.0, rho_eff]
    ])


def compute_voigt_average(volume_fractions: Dict[str, float],
                           material_properties: List[Dict]) -> np.ndarray:
    C_eff = np.zeros((3, 3), dtype=np.complex128)

    for mat in material_properties:
        name = mat.get('name', 'unknown')
        vf = volume_fractions.get(name, 0.0)

        rho = mat.get('density', 0.0)
        v_l = mat.get('sound_velocity_longitudinal', 0.0)
        v_s = mat.get('sound_velocity_shear', 0.0)

        mu = rho * v_s ** 2
        lambda_ = rho * v_l ** 2 - 2 * mu

        C = np.array([
            [lambda_ + 2 * mu, lambda_, 0],
            [lambda_, lambda_ + 2 * mu, 0],
            [0, 0, mu]
        ], dtype=np.complex128)

        C_eff += vf * C

    return C_eff


def compute_reuss_average(volume_fractions: Dict[str, float],
                           material_properties: List[Dict]) -> np.ndarray:
    S_eff = np.zeros((3, 3), dtype=np.complex128)

    for mat in material_properties:
        name = mat.get('name', 'unknown')
        vf = volume_fractions.get(name, 0.0)

        rho = mat.get('density', 0.0)
        v_l = mat.get('sound_velocity_longitudinal', 0.0)
        v_s = mat.get('sound_velocity_shear', 0.0)

        mu = rho * v_s ** 2
        lambda_ = rho * v_l ** 2 - 2 * mu

        K = lambda_ + 2 * mu / 3

        S = np.array([
            [1 / (3 * K) + 1 / (3 * mu), 1 / (6 * mu) - 1 / (3 * K), 0],
            [1 / (6 * mu) - 1 / (3 * K), 1 / (3 * K) + 1 / (3 * mu), 0],
            [0, 0, 1 / mu]
        ], dtype=np.complex128)

        S_eff += vf * S

    return np.linalg.inv(S_eff)


def compute_hashin_shtrikman_bounds(volume_fractions: Dict[str, float],
                                     material_properties: List[Dict]) -> Dict[str, np.ndarray]:
    if len(material_properties) < 2:
        C_voigt = compute_voigt_average(volume_fractions, material_properties)
        return {'lower': C_voigt, 'upper': C_voigt}

    rho1 = material_properties[0]['density']
    v_l1 = material_properties[0]['sound_velocity_longitudinal']
    v_s1 = material_properties[0]['sound_velocity_shear']
    mu1 = rho1 * v_s1 ** 2
    K1 = rho1 * v_l1 ** 2 - 2 * mu1 / 3

    rho2 = material_properties[1]['density']
    v_l2 = material_properties[1]['sound_velocity_longitudinal']
    v_s2 = material_properties[1]['sound_velocity_shear']
    mu2 = rho2 * v_s2 ** 2
    K2 = rho2 * v_l2 ** 2 - 2 * mu2 / 3

    f1 = volume_fractions.get(material_properties[0].get('name', 'mat1'), 0.5)
    f2 = 1.0 - f1

    if K2 >= K1 and mu2 >= mu1:
        K_lower = K1 + f2 / (1 / (K2 - K1) + 3 * f1 / (3 * K1 + 4 * mu1))
        mu_lower = mu1 + f2 / (1 / (mu2 - mu1) + 6 * f1 * (K1 + 2 * mu1) / (5 * mu1 * (3 * K1 + 4 * mu1)))
        K_upper = K2 + f1 / (1 / (K1 - K2) + 3 * f2 / (3 * K2 + 4 * mu2))
        mu_upper = mu2 + f1 / (1 / (mu1 - mu2) + 6 * f2 * (K2 + 2 * mu2) / (5 * mu2 * (3 * K2 + 4 * mu2)))
    else:
        K_lower = K2 + f1 / (1 / (K1 - K2) + 3 * f2 / (3 * K2 + 4 * mu2))
        mu_lower = mu2 + f1 / (1 / (mu1 - mu2) + 6 * f2 * (K2 + 2 * mu2) / (5 * mu2 * (3 * K2 + 4 * mu2)))
        K_upper = K1 + f2 / (1 / (K2 - K1) + 3 * f1 / (3 * K1 + 4 * mu1))
        mu_upper = mu1 + f2 / (1 / (mu2 - mu1) + 6 * f1 * (K1 + 2 * mu1) / (5 * mu1 * (3 * K1 + 4 * mu1)))

    def construct_C(K, mu):
        lambda_ = K - 2 * mu / 3
        return np.array([
            [lambda_ + 2 * mu, lambda_, 0],
            [lambda_, lambda_ + 2 * mu, 0],
            [0, 0, mu]
        ], dtype=np.complex128)

    return {
        'lower': construct_C(K_lower, mu_lower),
        'upper': construct_C(K_upper, mu_upper)
    }


def assemble_homogenization_matrices(mesh: Dict, material_properties: List[Dict],
                                      wave_type: str = 'psv') -> Tuple[csr_matrix, Dict]:
    from .fem_assembly import assemble_element_matrices_psv, assemble_element_matrices_sh

    vertices = mesh['vertices']
    triangles = mesh['triangles']
    material_ids = mesh.get('materials', np.zeros(len(triangles), dtype=int))

    n_nodes = len(vertices)
    n_dof = 2 * n_nodes if wave_type == 'psv' else n_nodes

    from scipy.sparse import lil_matrix
    K = lil_matrix((n_dof, n_dof), dtype=np.complex128)
    F = lil_matrix((n_dof, 3), dtype=np.complex128)

    B_e_list = []
    element_areas = []

    for e, elem in enumerate(triangles):
        mat_id = material_ids[e]
        if mat_id >= len(material_properties):
            mat_id = 0

        mat = material_properties[mat_id]
        rho = mat['density']
        v_l = mat['sound_velocity_longitudinal']
        v_s = mat['sound_velocity_shear']

        if wave_type == 'psv':
            k_e, _ = assemble_element_matrices_psv(vertices, elem, rho, v_l, v_s)

            xi = vertices[elem, 0]
            eta = vertices[elem, 1]
            J = np.array([
                [xi[1] - xi[0], xi[2] - xi[0]],
                [eta[1] - eta[0], eta[2] - eta[0]]
            ])
            detJ = np.linalg.det(J)
            invJ = np.linalg.inv(J)
            area = 0.5 * abs(detJ)

            lambda_, mu = rho * v_s ** 2, rho * v_l ** 2 - 2 * rho * v_s ** 2
            lambda_, mu = rho * v_s ** 2, rho * v_l ** 2 - 2 * rho * v_s ** 2

            dN_dxi = np.array([[-1, 1, 0], [-1, 0, 1]])
            dN_dxy = invJ @ dN_dxi

            B_e = np.zeros((3, 6))
            for i in range(3):
                B_e[0, 2 * i] = dN_dxy[0, i]
                B_e[1, 2 * i + 1] = dN_dxy[1, i]
                B_e[2, 2 * i] = dN_dxy[1, i]
                B_e[2, 2 * i + 1] = dN_dxy[0, i]

            C_e = np.array([
                [lambda_ + 2 * mu, lambda_, 0],
                [lambda_, lambda_ + 2 * mu, 0],
                [0, 0, mu]
            ])

            B_e_list.append(B_e)
            element_areas.append(area)

            for i in range(3):
                for j in range(3):
                    K[2 * elem[i]:2 * elem[i] + 2, 2 * elem[j]:2 * elem[j] + 2] += k_e[2 * i:2 * i + 2, 2 * j:2 * j + 2]

            for load_case in range(3):
                E0 = np.zeros(3)
                E0[load_case] = 1.0

                f_e = area * B_e.T @ C_e @ E0

                for i in range(3):
                    F[2 * elem[i]:2 * elem[i] + 2, load_case] += f_e[2 * i:2 * i + 2]
        else:
            k_e, _ = assemble_element_matrices_sh(vertices, elem, rho, v_s)
            for i in range(3):
                for j in range(3):
                    K[elem[i], elem[j]] += k_e[i, j]

    K = K.tocsr()
    F = F.tocsr()

    return K, {'F': F, 'B_e_list': B_e_list, 'element_areas': element_areas,
               'triangles': triangles, 'vertices': vertices, 'n_dof': n_dof}


def apply_periodic_bc_homogenization(K: csr_matrix, F: csr_matrix,
                                      boundary_info: Dict,
                                      unit_cell_size: Tuple[float, float],
                                      wave_type: str = 'psv') -> Tuple[csr_matrix, csr_matrix, np.ndarray, Dict]:
    lx, ly = unit_cell_size
    paired_x = boundary_info['paired_x']
    paired_y = boundary_info['paired_y']
    interior_nodes = boundary_info['interior_nodes']

    n_nodes = K.shape[0] // 2 if wave_type == 'psv' else K.shape[0]
    n_dof = K.shape[0]

    node_map = {}
    reduced_dof_list = []
    current_dof = 0

    if wave_type == 'psv':
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
    else:
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

    n_reduced = current_dof
    if n_reduced == 0:
        return K, F, np.array([]), node_map

    from scipy.sparse import lil_matrix
    K_reduced = lil_matrix((n_reduced, n_reduced), dtype=K.dtype)
    F_reduced = lil_matrix((n_reduced, F.shape[1]), dtype=F.dtype)

    K_coo = K.tocoo()
    F_coo = F.tocoo()

    def get_dof_mapping(dof):
        if wave_type == 'psv':
            node = dof // 2
            offset = dof % 2
        else:
            node = dof
            offset = 0

        for ln, rn in paired_x:
            if node == rn and ln in node_map:
                if wave_type == 'psv':
                    return node_map[2 * ln + offset]
                else:
                    return node_map[ln]

        for bn, tn in paired_y:
            if node == tn and bn in node_map:
                if wave_type == 'psv':
                    return node_map[2 * bn + offset]
                else:
                    return node_map[bn]

        if wave_type == 'psv':
            if 2 * node in node_map and node_map[2 * node] >= 0:
                return node_map[dof]
        else:
            if node in node_map and node_map[node] >= 0:
                return node_map[dof]

        return None

    for i, j, val in zip(K_coo.row, K_coo.col, K_coo.data):
        i_map = get_dof_mapping(i)
        j_map = get_dof_mapping(j)

        if i_map is not None and j_map is not None:
            K_reduced[i_map, j_map] += val

    for i, j, val in zip(F_coo.row, F_coo.col, F_coo.data):
        i_map = get_dof_mapping(i)

        if i_map is not None:
            F_reduced[i_map, j] += val

    dof_mapping = np.array(reduced_dof_list)

    return K_reduced.tocsr(), F_reduced.tocsr(), dof_mapping, node_map


def solve_homogenization_problem(mesh: Dict, material_properties: List[Dict],
                                  boundary_info: Dict,
                                  unit_cell_size: Tuple[float, float],
                                  wave_type: str = 'psv',
                                  method: str = 'asymptotic') -> HomogenizationResult:
    volume_fractions = compute_volume_fractions(mesh, material_properties)

    rho_eff = compute_effective_density(volume_fractions, material_properties)

    if method.lower() == 'voigt':
        C_eff = compute_voigt_average(volume_fractions, material_properties)
        chi_fields = None
    elif method.lower() == 'reuss':
        C_eff = compute_reuss_average(volume_fractions, material_properties)
        chi_fields = None
    elif method.lower() == 'hashin_shtrikman':
        bounds = compute_hashin_shtrikman_bounds(volume_fractions, material_properties)
        C_eff = 0.5 * (bounds['lower'] + bounds['upper'])
        chi_fields = None
    else:
        K, aux_data = assemble_homogenization_matrices(mesh, material_properties, wave_type)

        F = aux_data['F']
        K_reduced, F_reduced, dof_mapping, node_map = apply_periodic_bc_homogenization(
            K, F, boundary_info, unit_cell_size, wave_type
        )

        if K_reduced.shape[0] < 2:
            C_eff = compute_voigt_average(volume_fractions, material_properties)
            chi_fields = None
        else:
            try:
                chi_reduced = spsolve(K_reduced, F_reduced)

                n_dof = aux_data['n_dof']
                chi_full = np.zeros((n_dof, F.shape[1]), dtype=complex)
                for i, dof in enumerate(dof_mapping):
                    chi_full[dof, :] = chi_reduced[i, :]

                B_e_list = aux_data['B_e_list']
                element_areas = aux_data['element_areas']
                triangles = aux_data['triangles']

                n_nodes = len(aux_data['vertices'])
                cell_vel_field = chi_full.reshape(n_nodes, 2, 3) if wave_type == 'psv' else chi_full

                cell_area = unit_cell_size[0] * unit_cell_size[1]

                C_eff = np.zeros((3, 3), dtype=np.complex128)
                chi_fields = []

                for load_case in range(3):
                    E0 = np.zeros(3)
                    E0[load_case] = 1.0

                    strain_field = np.zeros((len(triangles), 3), dtype=np.complex128)
                    for e, elem in enumerate(triangles):
                        if wave_type == 'psv' and e < len(B_e_list):
                            if wave_type == 'psv':
                                chi_e = np.zeros(6)
                                for i in range(3):
                                    chi_e[2 * i] = chi_full[2 * elem[i], load_case]
                                    chi_e[2 * i + 1] = chi_full[2 * elem[i] + 1, load_case]

                                B_e = B_e_list[e]
                                strain_field[e, :] = B_e @ chi_e + E0

                                area = element_areas[e]
                                C_eff += (area / cell_area) * np.outer(strain_field[e, :], strain_field[e, :]) * (
                                    material_properties[mesh.get('materials', np.zeros(len(triangles), dtype=int))[e]]['density'] *
                                    material_properties[mesh.get('materials', np.zeros(len(triangles), dtype=int))[e]]['sound_velocity_shear'] ** 2
                                )

                    chi_fields.append(chi_full[:, load_case].copy())

            except Exception as e:
                print(f"Asymptotic homogenization failed, falling back to Voigt: {e}")
                C_eff = compute_voigt_average(volume_fractions, material_properties)
                chi_fields = None

    rho_scalar = np.real(rho_eff[0, 0])
    C11 = np.real(C_eff[0, 0])
    C44 = np.real(C_eff[2, 2])

    if rho_scalar > 0:
        v_l_eff = np.sqrt(C11 / rho_scalar)
        v_s_eff = np.sqrt(C44 / rho_scalar)
    else:
        v_l_eff = 0.0
        v_s_eff = 0.0

    return HomogenizationResult(
        effective_density=rho_eff,
        effective_modulus=C_eff,
        effective_velocity_longitudinal=float(v_l_eff),
        effective_velocity_shear=float(v_s_eff),
        volume_fractions=volume_fractions,
        chi_fields=chi_fields
    )


def compute_effective_properties_simple(volume_fractions: Dict[str, float],
                                         material_properties: List[Dict]) -> Dict:
    rho_eff = 0.0
    K_eff_inv = 0.0
    mu_eff_inv = 0.0

    for mat in material_properties:
        name = mat.get('name', 'unknown')
        vf = volume_fractions.get(name, 0.0)
        rho = mat.get('density', 0.0)
        v_l = mat.get('sound_velocity_longitudinal', 0.0)
        v_s = mat.get('sound_velocity_shear', 0.0)

        mu = rho * v_s ** 2
        K = rho * v_l ** 2 - 2 * mu / 3

        rho_eff += vf * rho
        if K > 0:
            K_eff_inv += vf / K
        if mu > 0:
            mu_eff_inv += vf / mu

    K_eff_reuss = 1.0 / K_eff_inv if K_eff_inv > 0 else 0.0
    mu_eff_reuss = 1.0 / mu_eff_inv if mu_eff_inv > 0 else 0.0

    v_l_reuss = np.sqrt((K_eff_reuss + 4 * mu_eff_reuss / 3) / rho_eff) if rho_eff > 0 else 0.0
    v_s_reuss = np.sqrt(mu_eff_reuss / rho_eff) if rho_eff > 0 else 0.0

    K_eff_voigt = 0.0
    mu_eff_voigt = 0.0
    for mat in material_properties:
        name = mat.get('name', 'unknown')
        vf = volume_fractions.get(name, 0.0)
        rho = mat.get('density', 0.0)
        v_l = mat.get('sound_velocity_longitudinal', 0.0)
        v_s = mat.get('sound_velocity_shear', 0.0)

        mu = rho * v_s ** 2
        K = rho * v_l ** 2 - 2 * mu / 3

        K_eff_voigt += vf * K
        mu_eff_voigt += vf * mu

    v_l_voigt = np.sqrt((K_eff_voigt + 4 * mu_eff_voigt / 3) / rho_eff) if rho_eff > 0 else 0.0
    v_s_voigt = np.sqrt(mu_eff_voigt / rho_eff) if rho_eff > 0 else 0.0

    return {
        'effective_density': float(rho_eff),
        'effective_bulk_modulus_voigt': float(K_eff_voigt),
        'effective_shear_modulus_voigt': float(mu_eff_voigt),
        'effective_bulk_modulus_reuss': float(K_eff_reuss),
        'effective_shear_modulus_reuss': float(mu_eff_reuss),
        'effective_velocity_longitudinal_voigt': float(v_l_voigt),
        'effective_velocity_shear_voigt': float(v_s_voigt),
        'effective_velocity_longitudinal_reuss': float(v_l_reuss),
        'effective_velocity_shear_reuss': float(v_s_reuss),
        'volume_fractions': volume_fractions
    }
