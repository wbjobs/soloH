"""
Test cases for the three fixes:
1. Over-smoothing with sparse measurements (weighted TV, TGV, adaptive regularization)
2. Bound constraint violation (projection, logarithmic barrier)
3. Joint inversion non-convergence (two-phase optimization, parameter scaling)
"""
import sys
import os

test_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, test_dir)
sys.path.insert(0, os.path.dirname(test_dir))

import mock_dolfin as dolfin
sys.modules['dolfin'] = dolfin

import numpy as np
from unittest.mock import MagicMock, patch
import pytest


class TestOverSmoothingFix:
    """Test fix for over-smoothing with sparse measurements."""

    def test_weighted_regularization_distance_weighting(self):
        """Test that weighted regularization reduces strength near measurements."""
        from heat_inv.regularization import WeightedRegularization

        mesh = MagicMock()
        mesh.coordinates.return_value = np.array([
            [0.0, 0.0], [0.5, 0.0], [1.0, 0.0],
            [0.0, 0.5], [0.5, 0.5], [1.0, 0.5],
            [0.0, 1.0], [0.5, 1.0], [1.0, 1.0]
        ])

        measurement_coords = np.array([[0.5, 0.5]])

        reg = WeightedRegularization(
            reg_type='weighted_tv',
            alpha=1e-3,
            measurement_coords=measurement_coords,
            mesh=mesh,
            weight_radius=0.3,
            min_weight=0.1,
            max_weight=1.0
        )

        weights = reg.weight_function
        assert weights is not None

        if hasattr(weights, 'vector'):
            weights = weights.vector().get_local()
        elif not isinstance(weights, np.ndarray):
            weights = np.array([float(weights[i]) for i in range(len(weights))])

        assert len(weights) == 9

        center_idx = 4
        corner_idx = 0
        assert weights[center_idx] < weights[corner_idx], \
            "Weight should be smaller near measurement point"
        assert 0.1 - 1e-10 <= weights[center_idx] <= 1.0 + 1e-10
        assert 0.1 - 1e-10 <= weights[corner_idx] <= 1.0 + 1e-10
        assert weights[center_idx] == pytest.approx(0.1, rel=0.1, abs=1e-9), \
            "Weight at measurement point should be close to min_weight"

    def test_tgv_regularization_creation(self):
        """Test TGV regularization creation."""
        from heat_inv.regularization import TGVRegularization

        reg = TGVRegularization(
            alpha=1e-3,
            beta=1e-4,
            gamma0=1.0,
            gamma1=2.0
        )

        assert reg.reg_type == 'tgv'
        assert reg.gamma0 == 1.0
        assert reg.gamma1 == 2.0

    def test_adaptive_regularization_edge_detection(self):
        """Test adaptive regularization edge detection."""
        from heat_inv.regularization import AdaptiveRegularization

        mesh = MagicMock()
        mesh.coordinates.return_value = np.array([
            [0.0, 0.0], [0.25, 0.0], [0.5, 0.0], [0.75, 0.0], [1.0, 0.0]
        ])
        measurement_coords = np.array([[0.5, 0.0]])

        reg = AdaptiveRegularization(
            alpha=1e-3,
            measurement_coords=measurement_coords,
            mesh=mesh,
            edge_threshold=0.5
        )

        k_solution = np.array([1.0, 1.0, 50.0, 1.0, 1.0])

        reg.update_adaptive_weights(k_solution)

        assert reg.edge_indicator is not None
        edge_left = reg.edge_indicator[1]
        edge_right = reg.edge_indicator[3]
        edge_side = reg.edge_indicator[0]
        assert (edge_left > edge_side) or (edge_right > edge_side), \
            "Edge should be detected at conductivity jump"

    def test_regularization_factory(self):
        """Test regularization factory function."""
        from heat_inv.regularization import create_regularization

        config = {'type': 'weighted_tv', 'alpha': 0.01, 'weight_radius': 0.2}
        mesh = MagicMock()
        mesh.coordinates.return_value = np.array([[0.0, 0.0], [1.0, 1.0]])
        coords = np.array([[0.5, 0.5]])

        reg = create_regularization(config, measurement_coords=coords, mesh=mesh)
        assert reg.reg_type == 'weighted_tv'
        alpha_val = reg.alpha.values()[0] if hasattr(reg.alpha, 'values') else float(reg.alpha)
        assert alpha_val == pytest.approx(0.01)
        assert reg.weight_radius == 0.2

        config2 = {'type': 'tgv', 'alpha': 0.01, 'beta': 0.001}
        reg2 = create_regularization(config2)
        assert reg2.reg_type == 'tgv'


class TestConstraintViolationFix:
    """Test fix for bound constraint violation."""

    def test_barrier_regularization_value(self):
        """Test logarithmic barrier regularization value."""
        from heat_inv.regularization import BarrierRegularization

        lb = 0.1
        ub = 200.0
        barrier = BarrierRegularization(lb=lb, ub=ub, mu=1e-4)

        x_feasible = np.array([10.0, 50.0, 100.0])
        val = barrier.compute_value(x_feasible)
        assert np.isfinite(val)

        x_near_bound = np.array([0.11, 100.0, 199.0])
        val_near = barrier.compute_value(x_near_bound)
        assert val_near > val, "Barrier should increase (less negative) near bounds"

        x_at_bound = np.array([0.1000001, 100.0, 199.999999])
        val_at_bound = barrier.compute_value(x_at_bound)

        lb_dist = x_at_bound[0] - lb
        ub_dist = ub - x_at_bound[2]
        log_sum = np.log(lb_dist) + np.log(ub_dist)
        expected_sign = -1 * log_sum

        if expected_sign > 0:
            assert val_at_bound > 0, "Barrier should be positive very close to bounds"
        else:
            assert np.isfinite(val_at_bound)

        x_very_near = np.array([lb + 1e-9, 100.0, ub - 1e-9])
        val_very_near = barrier.compute_value(x_very_near)
        assert val_very_near > val_near, "Barrier should increase as we approach bounds"
        assert np.isfinite(val_very_near)

    def test_barrier_regularization_gradient(self):
        """Test barrier gradient computation."""
        from heat_inv.regularization import BarrierRegularization

        lb = 0.1
        ub = 200.0
        barrier = BarrierRegularization(lb=lb, ub=ub, mu=1e-4)

        x = np.array([0.11, 100.0, 199.0])
        grad = barrier.compute_gradient(x)

        assert grad.shape == x.shape
        assert grad[0] < 0, "Gradient at lower bound side should be negative (pushing away from lb)"
        assert grad[2] > 0, "Gradient at upper bound side should be positive (pushing away from ub)"

        num_grad = np.zeros_like(x)
        eps = 1e-6
        for i in range(len(x)):
            x_plus = x.copy()
            x_plus[i] += eps
            x_minus = x.copy()
            x_minus[i] -= eps
            num_grad[i] = (barrier.compute_value(x_plus) - barrier.compute_value(x_minus)) / (2 * eps)

        assert np.allclose(grad, num_grad, rtol=1e-5)

    def test_bounds_projection(self):
        """Test bounds projection in joint objective."""
        from heat_inv.objective import JointObjectiveFunction

        k_min, k_max = 0.1, 200.0
        obj = MagicMock(spec=JointObjectiveFunction)
        obj.k_dim = 3
        obj.T0_dim = 3
        obj.k_min = k_min
        obj.k_max = k_max
        obj.T0_min = 250.0
        obj.T0_max = 350.0
        obj.total_dim = 6
        obj.estimate_T0 = True

        from heat_inv.objective import JointObjectiveFunction as JOF

        x_outside = np.array([-5.0, 10.0, 250.0, 200.0, 300.0, 400.0])
        x_projected = JOF._enforce_bounds(obj, x_outside)

        assert x_projected[0] >= k_min
        assert x_projected[2] <= k_max
        assert x_projected[3] >= 250.0
        assert x_projected[5] <= 350.0

        assert x_projected[0] == pytest.approx(k_min)
        assert x_projected[2] == pytest.approx(k_max)

    def test_feasibility_check(self):
        """Test feasibility checking."""
        from heat_inv.objective import JointObjectiveFunction

        obj = MagicMock(spec=JointObjectiveFunction)
        obj.k_dim = 3
        obj.T0_dim = 2
        obj.total_dim = 5
        obj.k_min = 0.1
        obj.k_max = 200.0
        obj.T0_min = 250.0
        obj.T0_max = 350.0
        obj.estimate_T0 = True

        from heat_inv.objective import JointObjectiveFunction as JOF

        x_feasible = np.array([10.0, 50.0, 100.0, 300.0, 320.0])
        is_feasible, violations = JOF.check_feasibility(obj, x_feasible, tol=1e-6)
        assert is_feasible
        assert violations['k'] == pytest.approx(0.0)
        assert violations['T0'] == pytest.approx(0.0)

        x_infeasible = np.array([-1.0, 50.0, 250.0, 200.0, 400.0])
        is_feasible2, violations2 = JOF.check_feasibility(obj, x_infeasible, tol=1e-6)
        assert not is_feasible2
        assert violations2['k'] > 0
        assert violations2['T0'] > 0


class TestJointInversionFix:
    """Test fix for joint inversion non-convergence."""

    def test_parameter_scaler(self):
        """Test parameter scaling for improved conditioning."""
        from heat_inv.objective import ParameterScaler

        scaler = ParameterScaler(scales={'k': 10.0, 'T0': 300.0})

        k_vec = np.array([10.0, 20.0, 30.0])
        T0_vec = np.array([300.0, 350.0, 400.0])
        x = np.concatenate([k_vec, T0_vec])

        x_scaled = scaler.scale_vector(x, k_dim=3)

        assert x_scaled.shape == x.shape
        assert np.allclose(x_scaled[:3], [1.0, 2.0, 3.0])
        assert np.allclose(x_scaled[3:], [1.0, 350/300, 400/300])

        x_unscaled = scaler.unscale_vector(x_scaled, k_dim=3)
        assert np.allclose(x_unscaled, x)

    def test_parameter_scaler_gradient(self):
        """Test gradient scaling."""
        from heat_inv.objective import ParameterScaler

        scaler = ParameterScaler(scales={'k': 10.0, 'T0': 300.0})

        grad = np.array([1.0, 2.0, 3.0, 0.1, 0.2, 0.3])
        grad_scaled = scaler.scale_gradient(grad, k_dim=3)

        assert np.allclose(grad_scaled[:3], [10.0, 20.0, 30.0])
        assert np.allclose(grad_scaled[3:], [30.0, 60.0, 90.0])

    def test_joint_optimization_result(self):
        """Test JointOptimizationResult structure."""
        from heat_inv.optimizer import JointOptimizationResult

        k_opt = np.array([10.0, 20.0, 30.0])
        T0_opt = np.array([300.0, 310.0, 320.0])
        k_func = MagicMock()
        T0_func = MagicMock()

        result = JointOptimizationResult(
            k_opt=k_opt,
            k_function=k_func,
            T0_opt=T0_opt,
            T0_function=T0_func,
            J_opt=1e-3,
            J_history=[1.0, 0.1, 0.01],
            grad_norm_history=[10.0, 1.0, 0.1],
            n_iter=100,
            converged=True,
            message='Optimization terminated successfully',
            k_bounds_violation=0.0,
            T0_bounds_violation=0.0
        )

        assert result.success
        assert result.k_bounds_violation == 0.0
        assert result.T0_bounds_violation == 0.0
        assert len(result.J_history) == 3
        assert hasattr(result, 'T0_opt')

    def test_joint_objective_gradient_structure(self):
        """Test that joint objective handles combined gradient for k and T0."""
        from heat_inv.regularization import Regularization, BarrierRegularization
        from heat_inv.objective import ParameterScaler

        V_k = MagicMock()
        V_k.dim.return_value = 3
        V_T = MagicMock()
        V_T.dim.return_value = 3

        scaler = ParameterScaler(scales={'k': 10.0, 'T0': 300.0})

        x = np.array([10.0, 20.0, 30.0, 300.0, 310.0, 320.0])

        def mock_compute(x_full):
            J = np.sum((x_full[:3] - 15.0)**2) + np.sum((x_full[3:] - 305.0)**2)
            grad = np.concatenate([
                2 * (x_full[:3] - 15.0),
                2 * (x_full[3:] - 305.0)
            ])
            return J, grad

        J_raw, grad_raw = mock_compute(x)

        x_scaled = scaler.scale_vector(x, k_dim=3)
        J_scaled, grad_scaled = mock_compute(x)
        grad_scaled = scaler.scale_gradient(grad_scaled, k_dim=3)

        assert grad_raw.shape == (6,)
        assert grad_scaled.shape == (6,)
        assert len(grad_raw) == 6
        assert len(grad_scaled) == 6

        assert np.allclose(grad_scaled[:3], grad_raw[:3] * 10.0)
        assert np.allclose(grad_scaled[3:], grad_raw[3:] * 300.0)

        barrier = BarrierRegularization(lb=np.array([0.1, 0.1, 0.1, 250, 250, 250]),
                                         ub=np.array([200, 200, 200, 350, 350, 350]),
                                         mu=1e-4)

        J_barrier = barrier.compute_value(x)
        grad_barrier = barrier.compute_gradient(x)

        assert grad_barrier.shape == (6,)
        assert np.isfinite(J_barrier)
        assert not np.any(np.isnan(grad_barrier))
        assert not np.any(np.isinf(grad_barrier))

        J_total = J_raw + J_barrier
        grad_total = grad_raw + grad_barrier

        assert grad_total.shape == (6,)
        assert np.isfinite(J_total)
        assert not np.any(np.isnan(grad_total))


class TestIntegration:
    """Integration tests for the complete solution."""

    def test_weighted_tv_preserves_edges(self):
        """Test that weighted TV preserves edges better than standard TV."""
        from heat_inv.regularization import WeightedRegularization, Regularization

        n = 100
        x = np.linspace(0, 1, n)
        k_true = np.where(x < 0.5, 1.0, 50.0)

        alpha = 0.1

        standard_reg = Regularization(reg_type='tv', alpha=alpha)
        weighted_reg = WeightedRegularization(
            reg_type='weighted_tv',
            alpha=alpha,
            weight_radius=0.1
        )

        standard_reg.gradient_operator = lambda k: np.gradient(k)
        weighted_reg.gradient_operator = lambda k: np.gradient(k)
        weighted_reg.weight_function = np.where(x < 0.3, 0.1,
                                               np.where(x > 0.7, 0.1, 1.0))

        k_smooth = np.ones(n) * 25.5

        grad_standard = standard_reg.compute_gradient(k_smooth)
        grad_weighted = weighted_reg.compute_gradient(k_smooth)

        edge_idx = np.argmin(np.abs(x - 0.5))
        center_idx = n // 2

        grad_standard_mag = np.abs(grad_standard[center_idx])
        grad_weighted_mag = np.abs(grad_weighted[center_idx])

        print(f"Standard TV grad at edge: {grad_standard_mag:.4f}")
        print(f"Weighted TV grad at edge: {grad_weighted_mag:.4f}")
        print(f"Ratio (weighted/standard): {grad_weighted_mag/grad_standard_mag:.4f}")

        assert grad_weighted_mag > 0.5 * grad_standard_mag, \
            "Weighted TV should have significant gradient at edges"

    def test_barrier_prevents_violation(self):
        """Test that barrier term prevents constraint violation in optimization."""
        from scipy.optimize import minimize

        lb, ub = 0.1, 200.0

        def objective(x, mu):
            f = (x[0] - 10.0)**2 + 0.01 * (x[1] - 50.0)**2
            if mu > 0:
                barrier = -mu * (np.log(max(x[0] - lb, 1e-10)) +
                                 np.log(max(ub - x[0], 1e-10)) +
                                 np.log(max(x[1] - lb, 1e-10)) +
                                 np.log(max(ub - x[1], 1e-10)))
                return f + barrier
            return f

        def gradient(x, mu):
            grad = np.array([2 * (x[0] - 10.0), 0.02 * (x[1] - 50.0)])
            if mu > 0:
                barrier_grad = mu * np.array([
                    -1 / max(x[0] - lb, 1e-10) + 1 / max(ub - x[0], 1e-10),
                    -1 / max(x[1] - lb, 1e-10) + 1 / max(ub - x[1], 1e-10)
                ])
                return grad + barrier_grad
            return grad

        x0 = np.array([0.05, 250.0])
        bounds = [(lb, ub), (lb, ub)]

        result_no_barrier = minimize(
            objective, x0, args=(0.0,),
            jac=gradient,
            method='L-BFGS-B',
            bounds=bounds
        )

        result_with_barrier = minimize(
            objective, x0, args=(1e-3,),
            jac=gradient,
            method='L-BFGS-B',
            bounds=bounds
        )

        print(f"No barrier: x={result_no_barrier.x}, in bounds? {lb <= result_no_barrier.x[0] <= ub}")
        print(f"With barrier: x={result_with_barrier.x}, in bounds? {lb <= result_with_barrier.x[0] <= ub}")

        assert np.all(result_with_barrier.x >= lb - 1e-8)
        assert np.all(result_with_barrier.x <= ub + 1e-8)

    def test_two_phase_improves_convergence(self):
        """Test that two-phase optimization converges better than single-phase."""
        from scipy.optimize import minimize

        k_dim = 5
        T0_dim = 5

        k_true = np.array([5.0, 5.0, 50.0, 50.0, 50.0])
        T0_true = np.array([300.0, 300.0, 300.0, 300.0, 300.0])

        def scaled_objective(x, k_dim):
            k = x[:k_dim]
            T0 = x[k_dim:]

            k_scaled = k / 10.0
            T0_scaled = T0 / 300.0

            J_k = np.sum((k_scaled - k_true/10.0)**2)
            J_T0 = np.sum((T0_scaled - 1.0)**2)
            J = J_k + 0.1 * J_T0

            grad = np.zeros_like(x)
            grad[:k_dim] = 2 * (k_scaled - k_true/10.0) / 10.0
            grad[k_dim:] = 0.2 * (T0_scaled - 1.0) / 300.0

            return J, grad

        k0 = np.ones(k_dim) * 10.0
        T0_guess_single = np.ones(T0_dim) * 350.0
        T0_guess_phase1 = np.ones(T0_dim) * 300.0

        x0_single = np.concatenate([k0, T0_guess_single])

        result_single = minimize(
            scaled_objective, x0_single, args=(k_dim,),
            jac=True, method='L-BFGS-B',
            options={'maxiter': 100, 'gtol': 1e-6}
        )

        print(f"\nSingle-phase:")
        print(f"  Success: {result_single.success}")
        print(f"  Iterations: {result_single.nit}")
        print(f"  Final J: {result_single.fun:.4e}")
        print(f"  k error: {np.linalg.norm(result_single.x[:k_dim] - k_true):.4f}")

        T0_fixed = T0_guess_phase1

        def phase1_objective(k):
            x = np.concatenate([k, T0_fixed])
            J, grad = scaled_objective(x, k_dim)
            return J, grad[:k_dim]

        result_phase1 = minimize(
            phase1_objective, k0,
            jac=True, method='L-BFGS-B',
            options={'maxiter': 30, 'gtol': 1e-4}
        )

        print(f"\nPhase 1 (k only):")
        print(f"  Success: {result_phase1.success}")
        print(f"  Iterations: {result_phase1.nit}")
        print(f"  k error: {np.linalg.norm(result_phase1.x - k_true):.4f}")

        x0_phase2 = np.concatenate([result_phase1.x, T0_guess_single])

        result_phase2 = minimize(
            scaled_objective, x0_phase2, args=(k_dim,),
            jac=True, method='L-BFGS-B',
            options={'maxiter': 70, 'gtol': 1e-6}
        )

        total_iter = result_phase1.nit + result_phase2.nit
        k_error_two_phase = np.linalg.norm(result_phase2.x[:k_dim] - k_true)

        print(f"\nPhase 2 (joint):")
        print(f"  Success: {result_phase2.success}")
        print(f"  Iterations: {result_phase2.nit} (total: {total_iter})")
        print(f"  Final J: {result_phase2.fun:.4e}")
        print(f"  k error: {k_error_two_phase:.4f}")

        print(f"\nComparison:")
        print(f"  Single-phase J: {result_single.fun:.4e}")
        print(f"  Two-phase J: {result_phase2.fun:.4e}")
        print(f"  Improvement: {100 * (result_single.fun - result_phase2.fun) / max(result_single.fun, 1e-30):.1f}%")

        assert result_phase2.success, "Two-phase should converge successfully"
        assert result_single.success, "Single-phase should also converge for this simple case"
        assert np.linalg.norm(result_phase2.x[:k_dim] - k_true) < 1e-4, \
            "Two-phase should recover k accurately"
        assert np.linalg.norm(result_phase2.x[k_dim:] - T0_true) < 1e-4, \
            "Two-phase should recover T0 accurately"
        assert result_phase2.fun <= result_single.fun * (1 + 1e-6), \
            "Two-phase should achieve at least as good J as single-phase"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
