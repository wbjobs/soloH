"""
Test suite for heat_inv package.
"""

import os
import sys
import numpy as np
import tempfile
import pytest

# Add parent directory to path
test_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, test_dir)
sys.path.insert(0, os.path.dirname(test_dir))

# Use mock dolfin module
import mock_dolfin as dolfin
sys.modules['dolfin'] = dolfin

from dolfin import *


@pytest.fixture
def setup_2d_problem():
    """Set up a simple 2D test problem."""
    from heat_inv.geometry import GeometryHandler
    from heat_inv.boundary import BoundaryConditionManager
    from heat_inv.forward import HeatForwardSolver
    from heat_inv.measurements import MeasurementData
    from heat_inv.objective import ObjectiveFunction, Regularization
    from heat_inv.adjoint import AdjointGradient

    geo = GeometryHandler()
    geo.create_box_mesh(nx=10, ny=10, length=1.0, width=1.0)

    V_T = geo.get_function_space(degree=1)
    V_k = geo.get_function_space(degree=1)

    bc_manager = BoundaryConditionManager(geo.mesh, geo.boundaries)
    bc_manager.add_dirichlet(350.0)

    forward_solver = HeatForwardSolver(V_T, bc_manager)

    measurements = MeasurementData()
    measurements.generate_synthetic(
        geo, num_points=5, mode='grid',
        true_k=10.0, forward_solver=forward_solver,
        noise_std=0.1, transient=False
    )

    regularization = Regularization(reg_type='tikhonov', alpha=1e-3, beta=1e-4)

    objective = ObjectiveFunction(forward_solver, measurements, regularization, V_k)
    gradient = AdjointGradient(forward_solver, objective, measurements, regularization, V_k)

    return {
        'geo': geo,
        'V_T': V_T,
        'V_k': V_k,
        'bc_manager': bc_manager,
        'forward_solver': forward_solver,
        'measurements': measurements,
        'regularization': regularization,
        'objective': objective,
        'gradient': gradient
    }


def test_geometry_handler():
    """Test geometry handler with simple mesh creation."""
    from heat_inv.geometry import GeometryHandler

    geo = GeometryHandler()
    mesh = geo.create_box_mesh(nx=10, ny=10, length=1.0, width=1.0)

    assert mesh is not None
    assert mesh.num_vertices() > 0
    assert geo.boundaries is not None
    assert geo.dx is not None
    assert geo.ds is not None


def test_function_spaces():
    """Test creation of function spaces."""
    from heat_inv.geometry import GeometryHandler

    geo = GeometryHandler()
    geo.create_box_mesh(nx=5, ny=5, length=1.0, width=1.0)

    V_scalar = geo.get_function_space(degree=1)
    V_vector = geo.get_vector_function_space(degree=1)

    assert V_scalar.dim() > 0
    assert V_vector.dim() == 2 * V_scalar.dim()


def test_boundary_conditions():
    """Test boundary condition handling."""
    from heat_inv.geometry import GeometryHandler
    from heat_inv.boundary import BoundaryConditionManager, BoundaryCondition

    geo = GeometryHandler()
    geo.create_box_mesh(nx=5, ny=5, length=1.0, width=1.0)

    bc_manager = BoundaryConditionManager(geo.mesh, geo.boundaries)
    bc_manager.add_dirichlet(300.0)
    bc_manager.add_neumann(10.0)
    bc_manager.add_robin(5.0, 298.0)

    assert len(bc_manager.bcs) == 3
    assert bc_manager.has_dirichlet()
    assert bc_manager.has_neumann()
    assert bc_manager.has_robin()

    V = geo.get_function_space(degree=1)
    dirichlet_bcs = bc_manager.setup_dirichlet_bcs(V)
    assert len(dirichlet_bcs) == 1


def test_forward_solver_steady(setup_2d_problem):
    """Test steady-state forward solver."""
    problem = setup_2d_problem
    forward_solver = problem['forward_solver']

    k = Constant(10.0)
    T = forward_solver.solve(k)

    assert T is not None
    T_vec = T.vector().get_local()
    assert np.all(T_vec > 0)
    assert np.allclose(T_vec, 350.0, atol=1.0)


def test_forward_solver_transient(setup_2d_problem):
    """Test transient forward solver."""
    problem = setup_2d_problem
    forward_solver = problem['forward_solver']

    k = Constant(10.0)
    times = np.linspace(0, 1.0, 5)
    T_solutions = forward_solver.solve_transient(
        k, times=times, T_initial=300.0
    )

    assert len(T_solutions) == len(times)
    T_final = T_solutions[-1].vector().get_local()
    assert np.all(T_final > 0)


def test_measurement_data():
    """Test measurement data handling."""
    from heat_inv.measurements import MeasurementData

    md = MeasurementData()
    md.add_point(0.25, 0.25, temperature=350.0, std_dev=0.5)
    md.add_point(0.75, 0.75, temperature=320.0, std_dev=0.5)

    assert md.num_points == 2
    assert not md.is_transient

    coords = md.get_coordinates()
    assert coords.shape == (2, 3)
    assert np.allclose(coords[0], [0.25, 0.25, 0.0])

    temps = md.get_measurement_vector()
    assert np.allclose(temps, [350.0, 320.0])


def test_transient_measurement_data():
    """Test transient measurement data handling."""
    from heat_inv.measurements import MeasurementData

    times = np.linspace(0, 10, 21)
    time_series = 300.0 + 50.0 * (1 - np.exp(-times / 2.0))

    md = MeasurementData()
    md.add_point(0.5, 0.5, time_series=time_series, times=times, std_dev=0.5)

    assert md.is_transient
    assert md.num_points == 1
    assert md.time_grid is not None
    assert len(md.time_grid) == 21

    T_10 = md.points[0].get_temperature_at(10.0)
    assert T_10 > 300.0


def test_objective_function(setup_2d_problem):
    """Test objective function computation."""
    problem = setup_2d_problem
    objective = problem['objective']
    V_k = problem['V_k']

    k_vec = np.ones(V_k.dim()) * 10.0
    J = objective.compute(k_vec)

    assert J >= 0
    assert np.isfinite(J)


def test_regularization_values():
    """Test different regularization types."""
    from heat_inv.geometry import GeometryHandler
    from heat_inv.objective import Regularization

    geo = GeometryHandler()
    geo.create_box_mesh(nx=5, ny=5, length=1.0, width=1.0)
    V = geo.get_function_space(degree=1)
    dx = Measure("dx", domain=geo.mesh)

    k = Function(V)
    k.vector()[:] = 10.0

    for reg_type in ['tikhonov0', 'tikhonov1', 'tikhonov', 'tv']:
        reg = Regularization(reg_type=reg_type, alpha=1e-3, beta=1e-4)
        J_reg = reg.compute_value(k, dx)
        assert J_reg >= 0
        assert np.isfinite(J_reg)


def test_adjoint_gradient(setup_2d_problem):
    """Test adjoint gradient computation."""
    problem = setup_2d_problem
    gradient = problem['gradient']
    V_k = problem['V_k']

    k_vec = np.ones(V_k.dim()) * 10.0
    grad_adj = gradient.compute_gradient(k_vec)

    assert grad_adj.shape == k_vec.shape
    assert np.all(np.isfinite(grad_adj))


def test_gradient_check(setup_2d_problem):
    """Test gradient check (comparing adjoint to numerical)."""
    problem = setup_2d_problem
    gradient = problem['gradient']
    V_k = problem['V_k']

    k_vec = np.ones(V_k.dim()) * 10.0

    grad_adj = gradient.compute_gradient(k_vec)
    grad_num = gradient.compute_gradient_numerical(k_vec, eps=1e-5)

    dot = np.dot(grad_adj, grad_num)
    norm = np.linalg.norm(grad_adj) * np.linalg.norm(grad_num)
    cos_angle = dot / norm if norm > 0 else 1.0

    assert cos_angle > 0.95, f"Gradient direction mismatch: cos(angle) = {cos_angle}"


def test_optimizer(setup_2d_problem):
    """Test L-BFGS optimizer with a simple problem."""
    from heat_inv.optimizer import InverseOptimizer, OptimizationOptions

    problem = setup_2d_problem
    objective = problem['objective']
    gradient = problem['gradient']
    V_k = problem['V_k']

    options = OptimizationOptions(
        max_iter=10,
        display_progress=False,
        k_min=0.1,
        k_max=100.0
    )

    optimizer = InverseOptimizer(objective, gradient, V_k, options)
    k0 = np.ones(V_k.dim()) * 15.0

    result = optimizer.optimize(k0=k0)

    assert result is not None
    assert len(result.J_history) > 0
    assert result.J_opt <= result.J_history[0]
    assert np.all(result.k_opt >= 0.1)
    assert np.all(result.k_opt <= 100.0)


def test_measurement_save_load():
    """Test saving and loading measurement data."""
    from heat_inv.measurements import MeasurementData
    import tempfile

    md = MeasurementData()
    md.add_point(0.25, 0.25, temperature=350.0, std_dev=0.5)
    md.add_point(0.75, 0.75, temperature=320.0, std_dev=0.5)

    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as f:
        tmp_name = f.name

    try:
        md.save_h5(tmp_name)

        md2 = MeasurementData()
        md2.load_h5(tmp_name)

        assert md2.num_points == md.num_points
        assert np.allclose(md2.get_measurement_vector(), md.get_measurement_vector())
        assert np.allclose(md2.get_coordinates(), md.get_coordinates())
    finally:
        os.unlink(tmp_name)


def test_vtk_writer():
    """Test VTK output writer."""
    from heat_inv.geometry import GeometryHandler
    from heat_inv.vtk_output import VTKWriter
    import tempfile

    geo = GeometryHandler()
    geo.create_box_mesh(nx=5, ny=5, length=1.0, width=1.0)
    V = geo.get_function_space(degree=1)

    k = Function(V)
    k.vector()[:] = 10.0

    T = Function(V)
    T.vector()[:] = 350.0

    with tempfile.TemporaryDirectory() as tmpdir:
        writer = VTKWriter(output_dir=tmpdir)

        k_file = writer.write_conductivity(k, "test_k")
        assert os.path.exists(k_file)

        T_file = writer.write_temperature(T, "test_T")
        assert os.path.exists(T_file)

        comb_file = writer.write_combined(k, T, "test_combined")
        assert os.path.exists(comb_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
