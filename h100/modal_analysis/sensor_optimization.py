import numpy as np
from itertools import combinations


def fisher_information_matrix(mode_shapes, measurement_noise_var=0.01):
    n_sensors, n_modes = mode_shapes.shape
    FIM = np.zeros((n_modes, n_modes))
    for i in range(n_modes):
        for j in range(n_modes):
            FIM[i, j] = np.sum(mode_shapes[:, i] * mode_shapes[:, j]) / measurement_noise_var
    return FIM


def shannon_entropy(FIM):
    try:
        eigenvalues = np.linalg.eigvals(FIM)
        eigenvalues = np.real(eigenvalues[eigenvalues > 1e-10])
        if len(eigenvalues) == 0:
            return np.inf
        entropy = 0.5 * np.sum(np.log(2 * np.pi * np.e / eigenvalues))
        return entropy
    except:
        return np.inf


def d_optimal_criterion(FIM):
    try:
        det = np.linalg.det(FIM)
        if det <= 0:
            return -np.inf
        return np.log(det)
    except:
        return -np.inf


def a_optimal_criterion(FIM):
    try:
        inv_FIM = np.linalg.inv(FIM + 1e-10 * np.eye(FIM.shape[0]))
        return -np.trace(inv_FIM)
    except:
        return -np.inf


def e_optimal_criterion(FIM):
    try:
        eigenvalues = np.linalg.eigvals(FIM)
        eigenvalues = np.real(eigenvalues)
        return -np.min(eigenvalues[eigenvalues > 0]) if np.any(eigenvalues > 0) else -np.inf
    except:
        return -np.inf


def modmac_criterion(selected_mode_shapes, full_mode_shapes):
    n_modes = full_mode_shapes.shape[1]
    mac_matrix = np.zeros((n_modes, n_modes))
    for i in range(n_modes):
        for j in range(n_modes):
            phi_i = selected_mode_shapes[:, i]
            phi_j = selected_mode_shapes[:, j]
            mac_matrix[i, j] = (np.dot(phi_i, phi_j) ** 2) / (np.dot(phi_i, phi_i) * np.dot(phi_j, phi_j) + 1e-10)
    off_diag_sum = np.sum(mac_matrix) - np.trace(mac_matrix)
    return -off_diag_sum / (n_modes * (n_modes - 1) + 1e-10)


def effective_independence(mode_shapes):
    n_sensors, n_modes = mode_shapes.shape
    E = np.zeros(n_sensors)
    U, s, Vt = np.linalg.svd(mode_shapes, full_matrices=False)
    for i in range(n_sensors):
        E[i] = np.sum(U[i, :] ** 2)
    return E


class SensorOptimizer:
    def __init__(self, full_mode_shapes, measurement_noise_var=0.01):
        self.full_mode_shapes = full_mode_shapes
        self.n_total_sensors = full_mode_shapes.shape[0]
        self.n_modes = full_mode_shapes.shape[1]
        self.measurement_noise_var = measurement_noise_var
        self.all_sensor_indices = np.arange(self.n_total_sensors)

    def _get_selected_mode_shapes(self, selected_indices):
        return self.full_mode_shapes[selected_indices, :]

    def _compute_objective(self, selected_indices, criterion='d_optimal'):
        if len(selected_indices) == 0:
            return -np.inf
        phi = self._get_selected_mode_shapes(selected_indices)
        if phi.shape[0] < self.n_modes:
            FIM = fisher_information_matrix(phi, self.measurement_noise_var)
            if criterion == 'd_optimal':
                det = np.linalg.det(FIM + 1e-6 * np.eye(FIM.shape[0]))
                return np.log(det) if det > 0 else -np.inf
            elif criterion == 'shannon_entropy':
                return -shannon_entropy(FIM + 1e-6 * np.eye(FIM.shape[0]))
            else:
                return -np.inf
        FIM = fisher_information_matrix(phi, self.measurement_noise_var)
        if criterion == 'd_optimal':
            return d_optimal_criterion(FIM)
        elif criterion == 'a_optimal':
            return a_optimal_criterion(FIM)
        elif criterion == 'e_optimal':
            return e_optimal_criterion(FIM)
        elif criterion == 'shannon_entropy':
            return -shannon_entropy(FIM)
        elif criterion == 'modmac':
            return modmac_criterion(phi, self.full_mode_shapes)
        else:
            raise ValueError(f"Unknown criterion: {criterion}")

    def sequential_forward_selection(self, n_sensors, criterion='d_optimal'):
        if n_sensors > self.n_total_sensors:
            n_sensors = self.n_total_sensors
        selected = []
        remaining = list(self.all_sensor_indices)
        for _ in range(n_sensors):
            best_idx = None
            best_score = -np.inf
            for cand in remaining:
                test_selected = selected + [cand]
                score = self._compute_objective(test_selected, criterion)
                if score > best_score and np.isfinite(score):
                    best_score = score
                    best_idx = cand
            if best_idx is None:
                best_idx = remaining[0]
            selected.append(best_idx)
            remaining.remove(best_idx)
        selected = sorted(selected)
        final_score = self._compute_objective(selected, criterion)
        return {
            'selected_sensors': selected,
            'objective_value': final_score,
            'criterion': criterion,
            'n_sensors': n_sensors
        }

    def sequential_backward_selection(self, n_sensors, criterion='d_optimal'):
        if n_sensors >= self.n_total_sensors:
            return {
                'selected_sensors': list(self.all_sensor_indices),
                'objective_value': self._compute_objective(self.all_sensor_indices, criterion),
                'criterion': criterion,
                'n_sensors': n_sensors
            }
        selected = list(self.all_sensor_indices)
        while len(selected) > n_sensors:
            worst_idx = None
            best_score = -np.inf
            for cand in selected:
                test_selected = [s for s in selected if s != cand]
                score = self._compute_objective(test_selected, criterion)
                if score > best_score:
                    best_score = score
                    worst_idx = cand
            selected.remove(worst_idx)
        selected = sorted(selected)
        final_score = self._compute_objective(selected, criterion)
        return {
            'selected_sensors': selected,
            'objective_value': final_score,
            'criterion': criterion,
            'n_sensors': n_sensors
        }

    def effective_independence_method(self, n_sensors):
        if n_sensors > self.n_total_sensors:
            n_sensors = self.n_total_sensors
        current_sensors = list(self.all_sensor_indices)
        phi = self.full_mode_shapes.copy()
        while len(current_sensors) > n_sensors:
            E = effective_independence(phi)
            remove_idx = np.argmin(E)
            current_sensors.pop(remove_idx)
            phi = np.delete(phi, remove_idx, axis=0)
        current_sensors = sorted(current_sensors)
        score = self._compute_objective(current_sensors, 'd_optimal')
        return {
            'selected_sensors': current_sensors,
            'objective_value': score,
            'criterion': 'effective_independence',
            'n_sensors': n_sensors
        }

    def brute_force(self, n_sensors, criterion='d_optimal'):
        if n_sensors > self.n_total_sensors:
            n_sensors = self.n_total_sensors
        best_score = -np.inf
        best_comb = None
        for comb in combinations(range(self.n_total_sensors), n_sensors):
            score = self._compute_objective(list(comb), criterion)
            if score > best_score:
                best_score = score
                best_comb = comb
        best_comb = sorted(best_comb)
        return {
            'selected_sensors': best_comb,
            'objective_value': best_score,
            'criterion': criterion,
            'n_sensors': n_sensors
        }

    def multi_criterion_optimization(self, n_sensors, weights=None):
        if weights is None:
            weights = {
                'd_optimal': 0.4,
                'modmac': 0.4,
                'shannon_entropy': 0.2
            }
        all_scores = {}
        for criterion in weights.keys():
            result = self.sequential_forward_selection(n_sensors, criterion)
            all_scores[criterion] = result
        combined_scores = []
        for comb in combinations(range(self.n_total_sensors), min(n_sensors, 6)):
            total_score = 0
            for criterion, w in weights.items():
                score = self._compute_objective(list(comb), criterion)
                total_score += w * score
            combined_scores.append((list(comb), total_score))
        combined_scores.sort(key=lambda x: x[1], reverse=True)
        best_comb, best_score = combined_scores[0]
        return {
            'selected_sensors': sorted(best_comb),
            'multi_criterion_score': best_score,
            'individual_results': all_scores,
            'n_sensors': n_sensors
        }

    def evaluate_configuration(self, selected_sensors):
        phi = self._get_selected_mode_shapes(selected_sensors)
        FIM = fisher_information_matrix(phi, self.measurement_noise_var)
        U, s, Vt = np.linalg.svd(phi, full_matrices=False)
        condition_number = s[0] / (s[-1] + 1e-10) if len(s) > 0 else np.inf
        return {
            'selected_sensors': selected_sensors,
            'n_sensors': len(selected_sensors),
            'fisher_information_matrix': FIM,
            'd_optimal': d_optimal_criterion(FIM),
            'a_optimal': a_optimal_criterion(FIM),
            'e_optimal': e_optimal_criterion(FIM),
            'shannon_entropy': shannon_entropy(FIM),
            'condition_number': condition_number,
            'singular_values': s
        }


def generate_sensor_layout_visualization(selected_sensors, node_positions, n_total_sensors):
    layout = {
        'selected': {},
        'unselected': {}
    }
    for idx in range(n_total_sensors):
        pos = node_positions.get(idx, (float(idx), 0.0))
        if idx in selected_sensors:
            layout['selected'][idx] = pos
        else:
            layout['unselected'][idx] = pos
    return layout


def coverage_score(selected_sensors, n_total_sensors, connectivity):
    covered_elements = set()
    for s in selected_sensors:
        for elem_idx, (n1, n2) in enumerate(connectivity):
            if s == n1 or s == n2:
                covered_elements.add(elem_idx)
    return len(covered_elements) / len(connectivity)


def redundancy_score(selected_sensors, mode_shapes, threshold=0.9):
    n = len(selected_sensors)
    if n < 2:
        return 0.0
    phi = mode_shapes[selected_sensors, :]
    redundant_pairs = 0
    total_pairs = n * (n - 1) / 2
    for i in range(n):
        for j in range(i + 1, n):
            mac = (np.dot(phi[i, :], phi[j, :]) ** 2) / (np.dot(phi[i, :], phi[i, :]) * np.dot(phi[j, :], phi[j, :]) + 1e-10)
            if mac > threshold:
                redundant_pairs += 1
    return redundant_pairs / total_pairs if total_pairs > 0 else 0.0
