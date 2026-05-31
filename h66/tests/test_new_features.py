"""
Test cases for the three new features:
1. Multiphysics coupling (thermoelectric, thermoelastic)
2. Reduced order modeling (POD basis, ROM solver)
3. Experimental design (sensor position optimization)
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


class TestMultiphysicsCoupling:
    """Test multiphysics coupling functionality."""

    def test_thermoelectric_solver_creation(self):
        """Test thermoelectric solver initialization."""
        from heat_inv.multiphysics import ThermoelectricSolver

        V_T = MagicMock()
        V_V = MagicMock()
        bc_manager = MagicMock()
        bc_manager.setup_dirichlet_bcs.return_value = []

        solver = ThermoelectricSolver(
            V_T=V_T,
            V_V=V_V,
            bc_manager=bc_manager,
            rho=8960,
            cp=385,
            sigma=5.96e7,
            alpha=1e-5
        )

        assert solver.V_T == V_T
        assert solver.V_V == V_V
        assert float(solver.sigma) == pytest.approx(5.96e7)
        assert float(solver.alpha) == pytest.approx(1e-5)
        assert float(solver.rho) == pytest.approx(8960)
        assert float(solver.cp) == pytest.approx(385)

    def test_thermoelastic_solver_creation(self):
        """Test thermoelastic solver initialization."""
        from heat_inv.multiphysics import ThermoelasticSolver

        V_T = MagicMock()
        V_u = MagicMock()
        bc_manager = MagicMock()
        bc_manager.setup_dirichlet_bcs.return_value = []

        solver = ThermoelasticSolver(
            V_T=V_T,
            V_u=V_u,
            bc_manager=bc_manager,
            rho=7850,
            cp=450,
            E=200e9,
            nu=0.3,
            alpha_T=1.2e-5,
            T_ref=293.0
        )

        assert solver.V_T == V_T
        assert solver.V_u == V_u
        assert float(solver.E) == pytest.approx(200e9)
        assert float(solver.nu) == pytest.approx(0.3)
        assert float(solver.alpha_T) == pytest.approx(1.2e-5)
        assert float(solver.T_ref) == pytest.approx(293.0)

        mu = float(solver.mu)
        lmbda = float(solver.lmbda)
        E_expected = 200e9
        nu_expected = 0.3

        assert mu == pytest.approx(E_expected / (2 * (1 + nu_expected)), rel=1e-6)
        assert lmbda == pytest.approx(E_expected * nu_expected /
                                     ((1 + nu_expected) * (1 - 2 * nu_expected)),
                                     rel=1e-6)

    def test_multiphysics_coupling_interface(self):
        """Test MultiphysicsCoupling interface."""
        from heat_inv.multiphysics import MultiphysicsCoupling, ThermoelectricSolver

        V_T = MagicMock()
        V_V = MagicMock()
        V_u = MagicMock()
        bc_manager = MagicMock()
        bc_manager.setup_dirichlet_bcs.return_value = []

        function_spaces_te = {
            'temperature': V_T,
            'potential': V_V
        }

        coupling_te = MultiphysicsCoupling(
            coupling_type='thermoelectric',
            function_spaces=function_spaces_te,
            bc_manager=bc_manager,
            sigma=1e6,
            alpha=1e-4
        )

        assert coupling_te.coupling_type == 'thermoelectric'
        assert coupling_te.field_names == ['temperature', 'potential']
        assert isinstance(coupling_te.solver, ThermoelectricSolver)

        function_spaces_te2 = {
            'temperature': V_T,
            'displacement': V_u
        }

        from heat_inv.multiphysics import ThermoelasticSolver
        coupling_tes = MultiphysicsCoupling(
            coupling_type='thermoelastic',
            function_spaces=function_spaces_te2,
            bc_manager=bc_manager,
            E=200e9,
            alpha_T=1e-5
        )

        assert coupling_tes.coupling_type == 'thermoelastic'
        assert coupling_tes.field_names == ['temperature', 'displacement']
        assert isinstance(coupling_tes.solver, ThermoelasticSolver)

    def test_multiphysics_coupling_invalid_type(self):
        """Test that invalid coupling type raises error."""
        from heat_inv.multiphysics import MultiphysicsCoupling

        V_T = MagicMock()
        V_V = MagicMock()
        bc_manager = MagicMock()

        function_spaces = {'temperature': V_T, 'potential': V_V}

        with pytest.raises(ValueError, match='Unknown coupling type'):
            MultiphysicsCoupling(
                coupling_type='invalid',
                function_spaces=function_spaces,
                bc_manager=bc_manager
            )

    def test_strain_computation(self):
        """Test strain tensor computation."""
        from heat_inv.multiphysics import ThermoelasticSolver

        V_T = MagicMock()
        V_u = MagicMock()
        bc_manager = MagicMock()
        bc_manager.setup_dirichlet_bcs.return_value = []

        solver = ThermoelasticSolver(V_T, V_u, bc_manager)

        assert solver._strain is not None
        assert callable(solver._strain)

    def test_stress_computation(self):
        """Test stress tensor computation."""
        from heat_inv.multiphysics import ThermoelasticSolver

        V_T = MagicMock()
        V_u = MagicMock()
        bc_manager = MagicMock()
        bc_manager.setup_dirichlet_bcs.return_value = []

        solver = ThermoelasticSolver(V_T, V_u, bc_manager)

        assert solver._stress is not None
        assert callable(solver._stress)

    def test_multiphysics_solve_interface(self):
        """Test MultiphysicsCoupling.solve interface."""
        from heat_inv.multiphysics import MultiphysicsCoupling

        V_T = MagicMock()
        V_V = MagicMock()
        bc_manager = MagicMock()
        bc_manager.setup_dirichlet_bcs.return_value = []

        function_spaces = {'temperature': V_T, 'potential': V_V}

        coupling = MultiphysicsCoupling(
            coupling_type='thermoelectric',
            function_spaces=function_spaces,
            bc_manager=bc_manager
        )

        k = MagicMock()
        mock_T = MagicMock()
        mock_V = MagicMock()
        coupling.solver.solve = MagicMock(return_value=(mock_T, mock_V))

        results = coupling.solve(k)

        assert 'temperature' in results
        assert 'potential' in results
        assert results['temperature'] == mock_T
        assert results['potential'] == mock_V
        coupling.solver.solve.assert_called_once()

    def test_coupling_type_list(self):
        """Test that coupling types are correctly defined."""
        from heat_inv.multiphysics import MultiphysicsCoupling

        assert 'thermoelectric' in MultiphysicsCoupling.COUPLING_TYPES
        assert 'thermoelastic' in MultiphysicsCoupling.COUPLING_TYPES
        assert len(MultiphysicsCoupling.COUPLING_TYPES) == 2


class TestReducedOrderModeling:
    """Test reduced order modeling functionality."""

    def test_pod_basis_generator_creation(self):
        """Test POD basis generator initialization."""
        from heat_inv.reduced_order import PODBasisGenerator

        V = MagicMock()
        V.dim.return_value = 100

        generator = PODBasisGenerator(V)

        assert generator.V == V
        assert generator.n_dofs == 100
        assert generator.basis_vectors is None
        assert generator.singular_values is None
        assert len(generator.snapshots) == 0

    def test_add_snapshots(self):
        """Test adding snapshots to POD generator."""
        from heat_inv.reduced_order import PODBasisGenerator

        V = MagicMock()
        V.dim.return_value = 10

        generator = PODBasisGenerator(V)

        for i in range(5):
            vec = np.random.randn(10)
            generator.add_snapshot(vec)

        assert len(generator.snapshots) == 5

        func = MagicMock()
        func.vector.return_value.get_local.return_value = np.random.randn(10)
        generator.add_snapshot(func)

        assert len(generator.snapshots) == 6

    def test_add_snapshots_invalid_dimension(self):
        """Test that snapshots with wrong dimension raise error."""
        from heat_inv.reduced_order import PODBasisGenerator

        V = MagicMock()
        V.dim.return_value = 10

        generator = PODBasisGenerator(V)

        with pytest.raises(ValueError, match='does not match'):
            generator.add_snapshot(np.random.randn(5))

    def test_compute_basis_svd(self):
        """Test POD basis computation using SVD."""
        from heat_inv.reduced_order import PODBasisGenerator

        n_dofs = 20
        n_snapshots = 10

        V = MagicMock()
        V.dim.return_value = n_dofs

        generator = PODBasisGenerator(V)

        snapshots = []
        for i in range(n_snapshots):
            vec = np.sin(i * np.pi / 5) * np.linspace(0, 1, n_dofs)
            vec += np.cos(i * np.pi / 3) * np.linspace(1, 0, n_dofs)
            snapshots.append(vec)
            generator.add_snapshot(vec)

        basis, sing_vals, energy = generator.compute_basis(n_basis=3, method='svd')

        assert len(basis) == 3
        assert len(sing_vals) == 3
        assert len(energy) == n_snapshots
        assert energy[-1] == pytest.approx(1.0, rel=1e-6)
        assert np.all(np.diff(sing_vals) <= 1e-10), "Singular values should be non-increasing"

        assert generator.basis_vectors.shape == (n_dofs, 3)
        for i in range(3):
            norm = np.linalg.norm(generator.basis_vectors[:, i])
            assert norm == pytest.approx(1.0, rel=1e-6)

    def test_compute_basis_correlation(self):
        """Test POD basis computation using correlation method."""
        from heat_inv.reduced_order import PODBasisGenerator

        n_dofs = 20
        n_snapshots = 10

        V = MagicMock()
        V.dim.return_value = n_dofs

        generator = PODBasisGenerator(V)

        for i in range(n_snapshots):
            vec = np.sin(i * np.pi / 5) * np.linspace(0, 1, n_dofs)
            vec += np.cos(i * np.pi / 3) * np.linspace(1, 0, n_dofs)
            generator.add_snapshot(vec)

        basis, sing_vals, energy = generator.compute_basis(n_basis=3, method='correlation')

        assert len(basis) == 3
        assert len(sing_vals) == 3
        assert energy[-1] == pytest.approx(1.0, rel=1e-6)

        for i in range(3):
            norm = np.linalg.norm(generator.basis_vectors[:, i])
            assert norm == pytest.approx(1.0, rel=1e-6)

    def test_compute_basis_energy_threshold(self):
        """Test automatic basis size selection based on energy threshold."""
        from heat_inv.reduced_order import PODBasisGenerator

        n_dofs = 100
        n_snapshots = 20

        V = MagicMock()
        V.dim.return_value = n_dofs

        generator = PODBasisGenerator(V)

        for i in range(n_snapshots):
            vec = np.exp(-(i - 5)**2 / 10) * np.sin(np.linspace(0, 2 * np.pi, n_dofs))
            generator.add_snapshot(vec)

        basis, sing_vals, energy = generator.compute_basis(energy_threshold=0.99, method='svd')

        assert generator.n_basis <= n_snapshots
        assert energy[generator.n_basis - 1] >= 0.99
        if generator.n_basis > 1:
            assert energy[generator.n_basis - 2] < 0.99

    def test_compute_basis_no_snapshots(self):
        """Test that computing basis without snapshots raises error."""
        from heat_inv.reduced_order import PODBasisGenerator

        V = MagicMock()
        V.dim.return_value = 10

        generator = PODBasisGenerator(V)

        with pytest.raises(ValueError, match='No snapshots'):
            generator.compute_basis()

    def test_project_and_reconstruct(self):
        """Test projection onto basis and reconstruction."""
        from heat_inv.reduced_order import PODBasisGenerator

        n_dofs = 50
        n_snapshots = 15

        V = MagicMock()
        V.dim.return_value = n_dofs

        generator = PODBasisGenerator(V)

        for i in range(n_snapshots):
            vec = np.sin((i + 1) * np.pi / (n_snapshots + 1)) * np.linspace(0.1, 1.0, n_dofs)
            generator.add_snapshot(vec)

        generator.compute_basis(n_basis=5, method='svd')

        test_vec = generator.snapshots[0]
        coeffs = generator.project_to_basis(test_vec)

        assert len(coeffs) == 5

        reconstructed = generator.reconstruct_from_basis(coeffs)

        recon_vec = reconstructed.vector().get_local() \
            if hasattr(reconstructed, 'vector') else reconstructed

        error = np.linalg.norm(test_vec - recon_vec) / np.linalg.norm(test_vec)
        assert error < 0.1, f"Reconstruction error {error} should be small"

    def test_reduced_order_solver_creation(self):
        """Test reduced order solver initialization."""
        from heat_inv.reduced_order import ReducedOrderSolver

        forward_solver = MagicMock()
        basis_vectors = np.random.randn(100, 10)

        rom_solver = ReducedOrderSolver(forward_solver, basis_vectors)

        assert rom_solver.n_dofs == 100
        assert rom_solver.n_basis == 10
        assert rom_solver.basis_vectors.shape == (100, 10)

    def test_rom_objective_function_creation(self):
        """Test ROM objective function initialization."""
        from heat_inv.reduced_order import ROMObjectiveFunction

        forward_solver = MagicMock()
        measurements = MagicMock()
        measurements.is_transient = False
        regularization = MagicMock()
        k_space = MagicMock()
        k_space.dim.return_value = 20

        basis_vectors = np.random.randn(50, 8)

        rom_obj = ROMObjectiveFunction(
            forward_solver=forward_solver,
            measurements=measurements,
            regularization=regularization,
            k_space=k_space,
            basis_vectors=basis_vectors,
            use_error_estimation=True,
            full_order_check_interval=10
        )

        assert rom_obj.n_basis == 8
        assert rom_obj.use_error_estimation
        assert rom_obj.full_order_check_interval == 10
        assert rom_obj.rom_solver is not None

    def test_save_and_load_basis(self, tmp_path):
        """Test saving and loading basis."""
        from heat_inv.reduced_order import PODBasisGenerator

        n_dofs = 20
        n_snapshots = 10

        V = MagicMock()
        V.dim.return_value = n_dofs

        generator = PODBasisGenerator(V)

        for i in range(n_snapshots):
            vec = np.sin(i * np.pi / 5) * np.linspace(0, 1, n_dofs)
            generator.add_snapshot(vec)

        generator.compute_basis(n_basis=4, method='svd')

        basis_file = tmp_path / "basis.npz"
        generator.save_basis(str(basis_file))

        assert basis_file.exists()

        generator2 = PODBasisGenerator(V)
        generator2.load_basis(str(basis_file))

        assert generator2.n_basis == 4
        assert np.allclose(generator2.basis_vectors, generator.basis_vectors)
        assert np.allclose(generator2.singular_values, generator.singular_values)


class TestExperimentalDesign:
    """Test experimental design (sensor optimization) functionality."""

    def test_sensor_optimizer_creation(self):
        """Test sensor optimizer initialization."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        candidates = np.array([[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]])

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=candidates,
            measurement_uncertainty=0.01
        )

        assert optimizer.n_candidates == 3
        assert optimizer.sigma == 0.01
        assert optimizer.candidate_positions.shape == (3, 2)

    def test_candidate_position_generation(self):
        """Test automatic candidate position generation."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        mesh = MagicMock()

        coords = np.array([
            [0.0, 0.0], [0.1, 0.0], [0.2, 0.0], [0.3, 0.0],
            [1.0, 0.0], [1.1, 0.0], [2.0, 0.0]
        ])
        mesh.coordinates.return_value = coords
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=None,
            measurement_uncertainty=0.01
        )

        assert optimizer.n_candidates <= len(coords)
        assert optimizer.candidate_positions is not None

        min_dist = np.inf
        for i in range(optimizer.n_candidates):
            for j in range(i + 1, optimizer.n_candidates):
                dist = np.linalg.norm(optimizer.candidate_positions[i] -
                                     optimizer.candidate_positions[j])
                min_dist = min(min_dist, dist)

        assert min_dist >= 0.01 - 1e-10

    def test_compute_fim(self):
        """Test Fisher Information Matrix computation."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        k_space.dim.return_value = 5
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        n_candidates = 10
        candidates = np.random.rand(n_candidates, 2)

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=candidates,
            measurement_uncertainty=0.01
        )

        n_params = 5
        optimizer.sensitivity_matrix = np.random.randn(n_candidates, n_params)

        selected_indices = [0, 2, 5]
        fim = optimizer.compute_fim(selected_indices, sigma=0.01)

        assert fim.shape == (n_params, n_params)
        assert np.allclose(fim, fim.T), "FIM should be symmetric"

        eigvals = np.linalg.eigvalsh(fim)
        assert np.all(eigvals >= -1e-10), "FIM should be positive semi-definite"

    def test_evaluate_criteria(self):
        """Test evaluation of optimality criteria."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        k_space.dim.return_value = 4
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=np.random.rand(10, 2),
            measurement_uncertainty=0.01
        )

        fim = np.diag([10.0, 5.0, 2.0, 1.0])

        d_value = optimizer.evaluate_criterion(fim, 'D')
        a_value = optimizer.evaluate_criterion(fim, 'A')
        e_value = optimizer.evaluate_criterion(fim, 'E')

        expected_logdet = np.sum(np.log(np.diag(fim)))
        assert d_value == pytest.approx(expected_logdet)

        expected_a = -np.trace(np.linalg.inv(fim))
        assert a_value == pytest.approx(expected_a)

        expected_e = np.min(np.diag(fim))
        assert e_value == pytest.approx(expected_e)

    def test_invalid_criterion(self):
        """Test that invalid criterion raises error."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=np.random.rand(5, 2)
        )

        fim = np.eye(3)

        with pytest.raises(ValueError, match='Unknown criterion'):
            optimizer.evaluate_criterion(fim, 'X')

    def test_greedy_optimization(self):
        """Test greedy sensor selection."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        k_space.dim.return_value = 3
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        n_candidates = 15
        candidates = np.random.rand(n_candidates, 2)

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=candidates,
            measurement_uncertainty=0.01
        )

        n_params = 3
        S = np.random.randn(n_candidates, n_params)
        for i in range(n_candidates):
            S[i, :] *= np.exp(-i / n_candidates * 2)
        optimizer.sensitivity_matrix = S

        n_sensors = 4
        indices, value = optimizer.optimize_greedy(n_sensors, criterion='D')

        assert len(indices) == n_sensors
        assert len(set(indices)) == n_sensors, "All indices should be unique"
        assert all(0 <= idx < n_candidates for idx in indices)
        assert np.isfinite(value)

    def test_exchange_optimization(self):
        """Test exchange algorithm for sensor selection."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        k_space.dim.return_value = 3
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        n_candidates = 15
        candidates = np.random.rand(n_candidates, 2)

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=candidates,
            measurement_uncertainty=0.01
        )

        n_params = 3
        S = np.random.randn(n_candidates, n_params)
        optimizer.sensitivity_matrix = S

        n_sensors = 4
        indices, value = optimizer.optimize_exchange(n_sensors, criterion='D', max_iter=20)

        assert len(indices) == n_sensors
        assert len(set(indices)) == n_sensors
        assert all(0 <= idx < n_candidates for idx in indices)
        assert np.isfinite(value)

        fim_initial = optimizer.compute_fim(indices)
        value_initial = optimizer.evaluate_criterion(fim_initial, 'D')
        assert value == pytest.approx(value_initial)

    def test_brute_force_optimization(self):
        """Test brute force optimization for small problems."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        k_space.dim.return_value = 2
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        n_candidates = 6
        candidates = np.random.rand(n_candidates, 2)

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=candidates,
            measurement_uncertainty=0.01
        )

        n_params = 2
        S = np.random.randn(n_candidates, n_params)
        optimizer.sensitivity_matrix = S

        n_sensors = 3
        indices, value = optimizer.optimize_brute_force(n_sensors, criterion='D')

        assert len(indices) == n_sensors
        assert len(set(indices)) == n_sensors

        best_val = -np.inf
        from itertools import combinations
        for combo in combinations(range(n_candidates), n_sensors):
            fim = optimizer.compute_fim(list(combo))
            val = optimizer.evaluate_criterion(fim, 'D')
            best_val = max(best_val, val)

        assert value == pytest.approx(best_val)

    def test_gradient_based_optimization(self):
        """Test gradient-based sensor optimization."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        k_space.dim.return_value = 3
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        n_candidates = 12
        candidates = np.random.rand(n_candidates, 2)

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=candidates,
            measurement_uncertainty=0.01
        )

        n_params = 3
        S = np.random.randn(n_candidates, n_params)
        optimizer.sensitivity_matrix = S

        n_sensors = 4
        weights, value, indices = optimizer.optimize_gradient_based(
            n_sensors, criterion='D', max_iter=50
        )

        assert len(weights) == n_candidates
        assert np.all(weights >= -1e-10)
        assert np.all(weights <= 1 + 1e-10)
        assert len(indices) == n_sensors
        assert np.isfinite(value)

    def test_uncertainty_metrics(self):
        """Test uncertainty metrics computation."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        k_space.dim.return_value = 4
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=np.random.rand(10, 2)
        )

        fim = np.diag([10.0, 5.0, 2.0, 1.0])
        metrics = optimizer.compute_uncertainty_metrics(fim)

        assert 'D_criterion' in metrics
        assert 'A_criterion' in metrics
        assert 'E_criterion' in metrics
        assert 'condition_number' in metrics
        assert 'average_std' in metrics
        assert 'max_std' in metrics
        assert 'min_std' in metrics

        assert np.isfinite(metrics['A_criterion'])
        assert metrics['A_criterion'] > 0
        assert metrics['average_std'] > 0
        assert metrics['max_std'] >= metrics['min_std']

    def test_get_sensor_positions(self):
        """Test retrieval of selected sensor positions."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        candidates = np.array([
            [0.0, 0.0], [0.25, 0.0], [0.5, 0.0], [0.75, 0.0], [1.0, 0.0]
        ])

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=candidates
        )

        selected_indices = [0, 2, 4]
        positions = optimizer.get_sensor_positions(selected_indices)

        assert positions.shape == (3, 2)
        assert np.allclose(positions[0], [0.0, 0.0])
        assert np.allclose(positions[1], [0.5, 0.0])
        assert np.allclose(positions[2], [1.0, 0.0])

    def test_main_optimize_interface(self):
        """Test the main optimize interface."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        k_space.dim.return_value = 3
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        n_candidates = 12
        candidates = np.random.rand(n_candidates, 2)

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=candidates
        )

        n_params = 3
        S = np.random.randn(n_candidates, n_params)
        optimizer.sensitivity_matrix = S

        indices, value, metrics = optimizer.optimize(
            n_sensors=4,
            criterion='D',
            algorithm='greedy'
        )

        assert len(indices) == 4
        assert np.isfinite(value)
        assert isinstance(metrics, dict)
        assert 'D_criterion' in metrics

        with pytest.raises(ValueError, match='Unknown criterion'):
            optimizer.optimize(4, criterion='X')

        with pytest.raises(ValueError, match='Unknown algorithm'):
            optimizer.optimize(4, algorithm='X')

    def test_compute_sensitivities_mock(self):
        """Test sensitivity computation with mocked forward solver."""
        from heat_inv.experimental_design import SensorOptimizer

        forward_solver = MagicMock()
        k_space = MagicMock()
        k_space.dim.return_value = 3
        mesh = MagicMock()
        mesh.topology.return_value.dim.return_value = 2
        k_space.mesh.return_value = mesh

        n_candidates = 5
        candidates = np.array([[0.0, 0.0], [0.25, 0.25], [0.5, 0.5],
                               [0.75, 0.75], [1.0, 1.0]])

        optimizer = SensorOptimizer(
            forward_solver=forward_solver,
            k_space=k_space,
            candidate_positions=candidates
        )

        k = MagicMock()
        k.vector.return_value.get_local.return_value = np.array([10.0, 20.0, 30.0])
        k.vector.return_value.__getitem__.side_effect = lambda i: np.array([10.0, 20.0, 30.0])[i]

        mock_T = MagicMock()
        mock_T.side_effect = lambda pos: 300.0 + 10.0 * pos[0] + 5.0 * pos[1]
        forward_solver.solve.return_value = mock_T

        S = optimizer.compute_sensitivities(k)

        assert S.shape == (n_candidates, k_space.dim())
        assert not np.any(np.isnan(S))
        assert not np.any(np.isinf(S))


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
