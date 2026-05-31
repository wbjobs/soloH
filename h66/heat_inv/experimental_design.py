"""
Optimal Experimental Design (OED) for inverse heat conduction problems.
Optimizes sensor positions to maximize information gain and minimize
reconstruction uncertainty.

Design criteria:
- D-optimality: maximize |FIM| (minimize volume of confidence ellipsoid)
- A-optimality: minimize tr(FIM^-1) (minimize average variance)
- E-optimality: maximize λ_min(FIM) (minimize maximum variance)
- G-optimality: minimize max prediction variance
"""

import numpy as np
from dolfin import *
from typing import Union, Optional, List, Tuple, Dict, Callable
from scipy import linalg
from scipy.optimize import minimize, brute, basinhopping
from itertools import combinations

from .forward import HeatForwardSolver
from .measurements import MeasurementData
from .adjoint import AdjointGradient
from .uqt import UncertaintyQuantifier


class SensorOptimizer:
    """
    Optimize sensor positions for inverse heat conduction problems.

    Uses the Fisher Information Matrix (FIM) to quantify information content:
    FIM_ij = (∂T/∂k_i)^T Σ^-1 (∂T/∂k_j)

    where Σ is the measurement noise covariance.

    Supports multiple optimization criteria and algorithms.
    """

    CRITERIA = ['D', 'A', 'E', 'G']
    ALGORITHMS = ['greedy', 'exchange', 'genetic', 'gradient', 'brute']

    def __init__(self,
                 forward_solver: HeatForwardSolver,
                 k_space: FunctionSpace,
                 candidate_positions: Optional[np.ndarray] = None,
                 measurement_uncertainty: float = 0.01,
                 transient: bool = False,
                 times: Optional[np.ndarray] = None):
        """
        Initialize sensor optimizer.

        Parameters
        ----------
        forward_solver : HeatForwardSolver
            Forward problem solver
        k_space : FunctionSpace
            Function space for parameter (thermal conductivity)
        candidate_positions : np.ndarray, optional
            Candidate sensor positions (n_candidates x dim)
            If None, will generate candidates from mesh nodes
        measurement_uncertainty : float, optional
            Standard deviation of measurement noise
        transient : bool, optional
            Whether the problem is transient
        times : np.ndarray, optional
            Time points for transient problems
        """
        self.forward_solver = forward_solver
        self.V_T = forward_solver.V
        self.V_k = k_space
        self.mesh = k_space.mesh()
        self.dim = self.mesh.topology().dim()

        self.transient = transient
        self.times = times
        self.sigma = measurement_uncertainty

        if candidate_positions is None:
            self._generate_candidate_positions()
        else:
            self.candidate_positions = np.asarray(candidate_positions)
        self.n_candidates = len(self.candidate_positions)

        self.sensitivity_matrix = None
        self.fim = None
        self.current_sensor_indices = None

    def _generate_candidate_positions(self, min_distance: float = 0.01):
        """Generate candidate positions from mesh nodes with minimum distance."""
        coords = self.mesh.coordinates()
        n_coords = len(coords)

        if min_distance <= 0:
            self.candidate_positions = coords
            return

        selected = []
        for i in range(n_coords):
            too_close = False
            for j in selected:
                dist = np.linalg.norm(coords[i] - coords[j])
                if dist < min_distance:
                    too_close = True
                    break
            if not too_close:
                selected.append(i)

        self.candidate_positions = coords[selected]
        self.n_candidates = len(self.candidate_positions)

    def compute_sensitivities(self, k: Function,
                              measurement_type: str = 'temperature') -> np.ndarray:
        """
        Compute sensitivity matrix S = ∂T/∂k for all candidate positions.

        For transient problems, S is concatenated over time.

        Parameters
        ----------
        k : Function
            Thermal conductivity (nominal value for sensitivity analysis)
        measurement_type : str, optional
            Type of measurement ('temperature', 'heat_flux', etc.)

        Returns
        -------
        np.ndarray
            Sensitivity matrix (n_measurements x n_parameters)
            where n_measurements = n_candidates * n_times (transient)
            or n_candidates (steady)
        """
        n_params = self.V_k.dim()
        n_candidates = self.n_candidates

        if self.transient and self.times is not None:
            n_times = len(self.times)
            S = np.zeros((n_candidates * n_times, n_params))
        else:
            n_times = 1
            S = np.zeros((n_candidates, n_params))

        for i in range(n_params):
            k_perturbed = Function(self.V_k)
            k_perturbed.vector()[:] = k.vector().get_local()

            eps = 1e-6 * max(np.abs(k_perturbed.vector().get_local()[i]), 1e-8)
            k_perturbed.vector()[i] += eps

            if self.transient and self.times is not None:
                T_list_plus = self.forward_solver.solve_transient(
                    k_perturbed, times=self.times
                )
                T_list_minus = None

                k_perturbed.vector()[i] -= 2 * eps
                T_list_minus = self.forward_solver.solve_transient(
                    k_perturbed, times=self.times
                )

                for t_idx in range(n_times):
                    for p_idx in range(n_candidates):
                        pos = self.candidate_positions[p_idx]
                        dT_dki = (T_list_plus[t_idx](pos) - T_list_minus[t_idx](pos)) / (2 * eps)
                        S[p_idx * n_times + t_idx, i] = dT_dki
            else:
                T_plus = self.forward_solver.solve(k_perturbed)

                k_perturbed.vector()[i] -= 2 * eps
                T_minus = self.forward_solver.solve(k_perturbed)

                for p_idx in range(n_candidates):
                    pos = self.candidate_positions[p_idx]
                    dT_dki = (T_plus(pos) - T_minus(pos)) / (2 * eps)
                    S[p_idx, i] = dT_dki

        self.sensitivity_matrix = S
        return S

    def compute_sensitivities_adjoint(self, k: Function,
                                      T: Optional[Function] = None,
                                      measurement_type: str = 'temperature') -> np.ndarray:
        """
        Compute sensitivity matrix using adjoint method (more efficient for
        large number of parameters).

        Parameters
        ----------
        k : Function
            Thermal conductivity
        T : Function, optional
            Temperature solution (if None, will compute)
        measurement_type : str, optional
            Type of measurement

        Returns
        -------
        np.ndarray
            Sensitivity matrix
        """
        if T is None:
            T = self.forward_solver.solve(k)

        n_params = self.V_k.dim()
        n_candidates = self.n_candidates

        if self.transient and self.times is not None:
            n_times = len(self.times)
            S = np.zeros((n_candidates * n_times, n_params))
        else:
            n_times = 1
            S = np.zeros((n_candidates, n_params))

        from .adjoint import AdjointGradient
        from .measurements import MeasurementData, MeasurementPoint
        from .objective import ObjectiveFunction, Regularization

        reg = Regularization(reg_type='tikhonov', alpha=0)
        meas = MeasurementData()

        for p_idx in range(n_candidates):
            pos = self.candidate_positions[p_idx]

            if self.transient and self.times is not None:
                for t_idx in range(n_times):
                    pt = MeasurementPoint(
                        coordinates=pos,
                        value=0.0,
                        uncertainty=self.sigma,
                        time=self.times[t_idx]
                    )
                    meas.add_point(pt)

                    obj = ObjectiveFunction(self.forward_solver, meas, reg, self.V_k)
                    adj = AdjointGradient(self.forward_solver, obj, meas, reg, self.V_k)

                    sens_row = adj.compute_gradient(k)
                    S[p_idx * n_times + t_idx, :] = sens_row / self.sigma

                    meas.points = []
            else:
                pt = MeasurementPoint(
                    coordinates=pos,
                    value=0.0,
                    uncertainty=self.sigma
                )
                meas.add_point(pt)

                obj = ObjectiveFunction(self.forward_solver, meas, reg, self.V_k)
                adj = AdjointGradient(self.forward_solver, obj, meas, reg, self.V_k)

                sens_row = adj.compute_gradient(k)
                S[p_idx, :] = sens_row / self.sigma

                meas.points = []

        self.sensitivity_matrix = S
        return S

    def compute_fim(self, sensor_indices: Optional[List[int]] = None,
                    sigma: Optional[float] = None) -> np.ndarray:
        """
        Compute Fisher Information Matrix (FIM) for selected sensors.

        FIM = S^T Σ^-1 S, where Σ = σ² I

        Parameters
        ----------
        sensor_indices : list of int, optional
            Indices of selected sensors (if None, use all candidates)
        sigma : float, optional
            Measurement noise standard deviation

        Returns
        -------
        np.ndarray
            Fisher Information Matrix (n_params x n_params)
        """
        if self.sensitivity_matrix is None:
            raise ValueError("Sensitivity matrix not computed. "
                           "Call compute_sensitivities() first.")

        if sigma is None:
            sigma = self.sigma

        if sensor_indices is None:
            S_sel = self.sensitivity_matrix
        else:
            if self.transient and self.times is not None:
                n_times = len(self.times)
                indices = []
                for idx in sensor_indices:
                    indices.extend(range(idx * n_times, (idx + 1) * n_times))
                S_sel = self.sensitivity_matrix[indices, :]
            else:
                S_sel = self.sensitivity_matrix[sensor_indices, :]

        fim = S_sel.T @ S_sel / (sigma ** 2)
        self.fim = fim
        self.current_sensor_indices = sensor_indices
        return fim

    def evaluate_criterion(self, fim: np.ndarray, criterion: str = 'D') -> float:
        """
        Evaluate optimality criterion.

        Parameters
        ----------
        fim : np.ndarray
            Fisher Information Matrix
        criterion : str, optional
            Optimality criterion: 'D', 'A', 'E', or 'G'

        Returns
        -------
        float
            Criterion value (to be maximized)
        """
        if criterion not in self.CRITERIA:
            raise ValueError(f"Unknown criterion: {criterion}. "
                           f"Must be one of {self.CRITERIA}")

        n = fim.shape[0]
        eps = 1e-12

        try:
            if criterion == 'D':
                sign, logdet = np.linalg.slogdet(fim + eps * np.eye(n))
                if sign <= 0:
                    return -np.inf
                return logdet

            elif criterion == 'A':
                try:
                    fim_inv = np.linalg.inv(fim + eps * np.eye(n))
                    return -np.trace(fim_inv)
                except np.linalg.LinAlgError:
                    return -np.inf

            elif criterion == 'E':
                eigvals = np.linalg.eigvalsh(fim)
                return max(np.min(eigvals), -1e12)

            elif criterion == 'G':
                if self.sensitivity_matrix is None or self.current_sensor_indices is None:
                    raise ValueError("Need sensitivity matrix for G-optimality")

                S_sel = self.sensitivity_matrix[self.current_sensor_indices, :]
                pred_variance = np.diag(S_sel @ np.linalg.pinv(fim) @ S_sel.T)
                return -np.max(pred_variance)

        except Exception as e:
            return -np.inf

    def optimize_greedy(self, n_sensors: int, criterion: str = 'D',
                        start_indices: Optional[List[int]] = None) -> Tuple[List[int], float]:
        """
        Greedy sensor selection.

        Algorithm:
        1. Start with empty or provided set
        2. At each step, add the sensor that maximizes the criterion

        Parameters
        ----------
        n_sensors : int
            Number of sensors to select
        criterion : str, optional
            Optimality criterion
        start_indices : list of int, optional
            Initial set of sensor indices

        Returns
        -------
        tuple
            (selected_indices, criterion_value)
        """
        if n_sensors > self.n_candidates:
            raise ValueError(f"Cannot select {n_sensors} sensors from "
                           f"{self.n_candidates} candidates")

        selected = list(start_indices) if start_indices is not None else []

        while len(selected) < n_sensors:
            best_idx = None
            best_value = -np.inf

            for i in range(self.n_candidates):
                if i in selected:
                    continue

                test_indices = selected + [i]
                fim = self.compute_fim(test_indices)
                value = self.evaluate_criterion(fim, criterion)

                if value > best_value:
                    best_value = value
                    best_idx = i

            if best_idx is None:
                break

            selected.append(best_idx)

        fim = self.compute_fim(selected)
        final_value = self.evaluate_criterion(fim, criterion)

        return selected, final_value

    def optimize_exchange(self, n_sensors: int, criterion: str = 'D',
                          initial_indices: Optional[List[int]] = None,
                          max_iter: int = 100) -> Tuple[List[int], float]:
        """
        Exchange algorithm for sensor selection.

        Algorithm:
        1. Start with an initial set of sensors
        2. At each step, try exchanging each selected sensor with each
           non-selected sensor. Keep the exchange that improves the criterion.
        3. Stop when no improvement can be made.

        Parameters
        ----------
        n_sensors : int
            Number of sensors
        criterion : str, optional
            Optimality criterion
        initial_indices : list of int, optional
            Initial set of indices
        max_iter : int, optional
            Maximum number of iterations

        Returns
        -------
        tuple
            (selected_indices, criterion_value)
        """
        if initial_indices is None:
            selected, _ = self.optimize_greedy(n_sensors, criterion)
        else:
            selected = list(initial_indices)

        fim = self.compute_fim(selected)
        best_value = self.evaluate_criterion(fim, criterion)

        for iteration in range(max_iter):
            improved = False

            for i_in, idx_in in enumerate(selected):
                for idx_out in range(self.n_candidates):
                    if idx_out in selected:
                        continue

                    test_indices = selected[:i_in] + [idx_out] + selected[i_in+1:]
                    fim_test = self.compute_fim(test_indices)
                    test_value = self.evaluate_criterion(fim_test, criterion)

                    if test_value > best_value + 1e-12:
                        best_value = test_value
                        selected = test_indices
                        improved = True
                        break

                if improved:
                    break

            if not improved:
                break

        fim = self.compute_fim(selected)
        final_value = self.evaluate_criterion(fim, criterion)

        return selected, final_value

    def optimize_brute_force(self, n_sensors: int,
                             criterion: str = 'D') -> Tuple[List[int], float]:
        """
        Brute force search over all combinations (for small problems).

        Parameters
        ----------
        n_sensors : int
            Number of sensors
        criterion : str, optional
            Optimality criterion

        Returns
        -------
        tuple
            (best_indices, best_value)
        """
        if n_sensors > self.n_candidates:
            raise ValueError(f"Cannot select {n_sensors} sensors from "
                           f"{self.n_candidates} candidates")

        if self.n_candidates > 20 and n_sensors > 5:
            import warnings
            warnings.warn(f"Brute force search with {self.n_candidates} choose "
                        f"{n_sensors} = {np.math.comb(self.n_candidates, n_sensors)} "
                        f"combinations may be slow.")

        best_indices = None
        best_value = -np.inf

        for combo in combinations(range(self.n_candidates), n_sensors):
            indices = list(combo)
            fim = self.compute_fim(indices)
            value = self.evaluate_criterion(fim, criterion)

            if value > best_value:
                best_value = value
                best_indices = indices

        return best_indices, best_value

    def optimize_gradient_based(self, n_sensors: int,
                                 criterion: str = 'D',
                                 initial_weights: Optional[np.ndarray] = None,
                                 max_iter: int = 1000) -> Tuple[np.ndarray, float, List[int]]:
        """
        Gradient-based optimization of continuous sensor weights.

        Uses relaxed formulation where each sensor has a continuous weight
        between 0 and 1, then thresholds to get discrete selection.

        Parameters
        ----------
        n_sensors : int
            Number of sensors to select
        criterion : str, optional
            Optimality criterion
        initial_weights : np.ndarray, optional
            Initial weights
        max_iter : int, optional
            Maximum iterations

        Returns
        -------
        tuple
            (weights, criterion_value, top_indices)
        """
        if initial_weights is None:
            w = np.ones(self.n_candidates) * 0.5
        else:
            w = np.clip(initial_weights, 0, 1)

        def objective(w):
            w = np.clip(w, 0, 1)
            fim = np.zeros((self.V_k.dim(), self.V_k.dim()))

            for i in range(self.n_candidates):
                if w[i] < 1e-6:
                    continue

                if self.transient and self.times is not None:
                    n_times = len(self.times)
                    indices = range(i * n_times, (i + 1) * n_times)
                    S_i = self.sensitivity_matrix[indices, :]
                else:
                    S_i = self.sensitivity_matrix[[i], :]

                fim += w[i] * (S_i.T @ S_i) / (self.sigma ** 2)

            value = self.evaluate_criterion(fim, criterion)
            return -value

        bounds = [(0, 1)] * self.n_candidates

        result = minimize(
            objective, w,
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': max_iter, 'ftol': 1e-8}
        )

        w_opt = np.clip(result.x, 0, 1)

        fim = np.zeros((self.V_k.dim(), self.V_k.dim()))
        for i in range(self.n_candidates):
            if self.transient and self.times is not None:
                n_times = len(self.times)
                indices = range(i * n_times, (i + 1) * n_times)
                S_i = self.sensitivity_matrix[indices, :]
            else:
                S_i = self.sensitivity_matrix[[i], :]
            fim += w_opt[i] * (S_i.T @ S_i) / (self.sigma ** 2)

        best_value = self.evaluate_criterion(fim, criterion)
        top_indices = np.argsort(-w_opt)[:n_sensors].tolist()

        return w_opt, best_value, top_indices

    def get_sensor_positions(self, indices: List[int]) -> np.ndarray:
        """Get coordinates of selected sensors."""
        return self.candidate_positions[indices]

    def compute_uncertainty_metrics(self, fim: np.ndarray) -> dict:
        """
        Compute uncertainty metrics from FIM.

        Parameters
        ----------
        fim : np.ndarray
            Fisher Information Matrix

        Returns
        -------
        dict
            Dictionary of uncertainty metrics
        """
        n = fim.shape[0]
        eps = 1e-10

        try:
            fim_inv = np.linalg.inv(fim + eps * np.eye(n))
            eigvals = np.linalg.eigvalsh(fim_inv)

            metrics = {
                'D_criterion': float(np.linalg.slogdet(fim_inv)[1]),
                'A_criterion': float(np.trace(fim_inv)),
                'E_criterion': float(np.max(eigvals)),
                'condition_number': float(np.max(eigvals) / (np.min(eigvals) + eps)),
                'average_std': float(np.sqrt(np.mean(np.diag(fim_inv)))),
                'max_std': float(np.sqrt(np.max(np.diag(fim_inv)))),
                'min_std': float(np.sqrt(np.min(np.diag(fim_inv)))),
            }
        except Exception as e:
            metrics = {
                'D_criterion': np.inf,
                'A_criterion': np.inf,
                'E_criterion': np.inf,
                'condition_number': np.inf,
                'average_std': np.inf,
                'max_std': np.inf,
                'min_std': np.inf,
            }

        return metrics

    def optimize(self, n_sensors: int,
                 criterion: str = 'D',
                 algorithm: str = 'exchange',
                 **kwargs) -> Tuple[List[int], float, dict]:
        """
        Main optimization interface.

        Parameters
        ----------
        n_sensors : int
            Number of sensors to select
        criterion : str, optional
            Optimality criterion: 'D', 'A', 'E', 'G'
        algorithm : str, optional
            Optimization algorithm: 'greedy', 'exchange', 'gradient', 'brute'
        **kwargs
            Additional arguments passed to the specific algorithm

        Returns
        -------
        tuple
            (selected_indices, criterion_value, metrics)
        """
        if criterion not in self.CRITERIA:
            raise ValueError(f"Unknown criterion: {criterion}. "
                           f"Supported: {self.CRITERIA}")

        if algorithm not in self.ALGORITHMS:
            raise ValueError(f"Unknown algorithm: {algorithm}. "
                           f"Supported: {self.ALGORITHMS}")

        if algorithm == 'greedy':
            indices, value = self.optimize_greedy(n_sensors, criterion, **kwargs)
        elif algorithm == 'exchange':
            indices, value = self.optimize_exchange(n_sensors, criterion, **kwargs)
        elif algorithm == 'gradient':
            weights, value, indices = self.optimize_gradient_based(
                n_sensors, criterion, **kwargs
            )
        elif algorithm == 'brute':
            indices, value = self.optimize_brute_force(n_sensors, criterion)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        fim = self.compute_fim(indices)
        metrics = self.compute_uncertainty_metrics(fim)

        return indices, value, metrics
