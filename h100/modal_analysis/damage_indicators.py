import numpy as np


def modal_strain_energy(mode_shapes, connectivity):
    n_modes = mode_shapes.shape[1]
    n_elements = len(connectivity)
    mse = np.zeros((n_modes, n_elements))
    for m in range(n_modes):
        mode = mode_shapes[:, m]
        for e, (i, j) in enumerate(connectivity):
            diff = mode[j] - mode[i]
            mse[m, e] = 0.5 * diff ** 2
    return mse


def modal_strain_energy_change(mse_baseline, mse_current):
    n_modes = mse_baseline.shape[0]
    n_elements = mse_baseline.shape[1]
    mse_change = np.zeros((n_modes, n_elements))
    for m in range(n_modes):
        for e in range(n_elements):
            baseline = mse_baseline[m, e]
            current = mse_current[m, e]
            if baseline > 1e-10:
                mse_change[m, e] = (current - baseline) / baseline
            elif current > 1e-10:
                mse_change[m, e] = float('inf')
            else:
                mse_change[m, e] = 0.0
    return mse_change


def total_modal_strain_energy(mse, weights=None):
    n_modes = mse.shape[0]
    n_elements = mse.shape[1]
    if weights is None:
        weights = np.ones(n_modes) / n_modes
    total_mse = np.zeros(n_elements)
    for e in range(n_elements):
        total_mse[e] = np.sum(weights * mse[:, e])
    return total_mse


def mse_damage_index(mse_baseline, mse_current, weights=None):
    n_elements = mse_baseline.shape[1]
    total_baseline = total_modal_strain_energy(mse_baseline, weights)
    total_current = total_modal_strain_energy(mse_current, weights)
    damage_index = np.zeros(n_elements)
    for e in range(n_elements):
        if total_baseline[e] > 1e-10:
            damage_index[e] = (total_current[e] - total_baseline[e]) / total_baseline[e]
        elif total_current[e] > 1e-10:
            damage_index[e] = 10.0
    return damage_index


def flexibility_matrix(mode_shapes, natural_frequencies, damping_ratios=None,
                       mass_normalized=False):
    n_dofs = mode_shapes.shape[0]
    n_modes = len(natural_frequencies)
    F = np.zeros((n_dofs, n_dofs))
    for m in range(n_modes):
        omega_sq = (2 * np.pi * natural_frequencies[m]) ** 2
        if omega_sq > 1e-10:
            phi = mode_shapes[:, m:m+1]
            F += phi @ phi.T / omega_sq
    return F


def flexibility_curvature(flexibility):
    n_dofs = flexibility.shape[0]
    curvature = np.zeros((n_dofs, n_dofs))
    for i in range(1, n_dofs - 1):
        curvature[i, :] = (flexibility[i+1, :] - 2 * flexibility[i, :] + flexibility[i-1, :])
        curvature[:, i] = (flexibility[:, i+1] - 2 * flexibility[:, i] + flexibility[:, i-1])
    return curvature


def flexibility_curvature_change(F_baseline, F_current):
    n_dofs = F_baseline.shape[0]
    curvature_baseline = flexibility_curvature(F_baseline)
    curvature_current = flexibility_curvature(F_current)
    curvature_change = np.zeros((n_dofs, n_dofs))
    for i in range(n_dofs):
        for j in range(n_dofs):
            if abs(curvature_baseline[i, j]) > 1e-10:
                curvature_change[i, j] = abs((curvature_current[i, j] - curvature_baseline[i, j]) / curvature_baseline[i, j])
            else:
                curvature_change[i, j] = abs(curvature_current[i, j] - curvature_baseline[i, j])
    return curvature_change, curvature_baseline, curvature_current


def flexibility_based_damage_index(F_baseline, F_current, dof_positions=None):
    n_dofs = F_baseline.shape[0]
    damage_index = np.zeros(n_dofs)
    curvature_change, _, _ = flexibility_curvature_change(F_baseline, F_current)
    for i in range(n_dofs):
        damage_index[i] = np.max(np.abs(curvature_change[i, :]))
    if dof_positions is not None:
        element_indices = []
        for i in range(1, n_dofs):
            element_indices.append(i)
        element_damage = np.zeros(len(element_indices))
        for e_idx, elem in enumerate(element_indices):
            if elem < n_dofs:
                element_damage[e_idx] = damage_index[elem]
        return damage_index, curvature_change, element_damage
    return damage_index, curvature_change


def damage_index_summary(mse_di, flex_di, connectivity, node_labels=None):
    n_elements = len(connectivity)
    n_nodes = max(max(conn) for conn in connectivity) + 1
    if node_labels is None:
        node_labels = [f"Node_{i}" for i in range(n_nodes)]
    elements = []
    for e, (i, j) in enumerate(connectivity):
        elements.append({
            'element_id': e,
            'node_i': i,
            'node_j': j,
            'label_i': node_labels[i] if i < len(node_labels) else f"Node_{i}",
            'label_j': node_labels[j] if j < len(node_labels) else f"Node_{j}",
            'mse_damage_index': mse_di[e] if e < len(mse_di) else 0.0,
            'flexibility_damage_index': flex_di[e] if e < len(flex_di) else 0.0,
        })
    return elements


def modal_energy_distribution(mode_shapes, connectivity):
    n_modes = mode_shapes.shape[1]
    n_elements = len(connectivity)
    distribution = np.zeros((n_modes, n_elements))
    for m in range(n_modes):
        mode = mode_shapes[:, m]
        total_energy = 0
        for e, (i, j) in enumerate(connectivity):
            energy = 0.5 * (mode[j] - mode[i]) ** 2
            distribution[m, e] = energy
            total_energy += energy
        if total_energy > 1e-10:
            distribution[m, :] /= total_energy
    return distribution


def combined_damage_indicator(mse_di, flex_di, alpha=0.5):
    if len(mse_di) != len(flex_di):
        min_len = min(len(mse_di), len(flex_di))
        mse_norm = mse_di[:min_len] / (np.max(np.abs(mse_di[:min_len])) + 1e-10)
        flex_norm = flex_di[:min_len] / (np.max(np.abs(flex_di[:min_len])) + 1e-10)
        return alpha * mse_norm + (1 - alpha) * flex_norm
    mse_norm = mse_di / (np.max(np.abs(mse_di)) + 1e-10)
    flex_norm = flex_di / (np.max(np.abs(flex_di)) + 1e-10)
    return alpha * mse_norm + (1 - alpha) * flex_norm
