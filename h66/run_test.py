"""
Synthetic test case for heat inversion solver.

This script demonstrates the complete workflow:
1. Create geometry
2. Set up boundary conditions
3. Generate synthetic measurements from known conductivity
4. Solve inverse problem
5. Visualize results
"""

import os
import sys
import numpy as np
from dolfin import *

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heat_inv.geometry import GeometryHandler
from heat_inv.boundary import BoundaryConditionManager
from heat_inv.forward import HeatForwardSolver
from heat_inv.measurements import MeasurementData
from heat_inv.objective import ObjectiveFunction, Regularization
from heat_inv.adjoint import AdjointGradient
from heat_inv.optimizer import InverseOptimizer, OptimizationOptions
from heat_inv.uqt import UncertaintyQuantifier
from heat_inv.vtk_output import VTKWriter, ResultsVisualizer


def run_test_case(transient=False):
    """Run a complete test case."""
    output_dir = f"output/test_{'transient' if transient else 'steady'}"
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print(f"TEST CASE: {'Transient' if transient else 'Steady-State'} Inversion")
    print("=" * 60)

    # Step 1: Geometry
    print("\n1. Creating geometry...")
    geo = GeometryHandler()
    geo.create_box_mesh(nx=20, ny=20, length=1.0, width=1.0)

    V_T = geo.get_function_space(degree=1)
    V_k = geo.get_function_space(degree=1)

    print(f"   Mesh: {geo.mesh.num_vertices()} vertices, {geo.mesh.num_cells()} cells")
    print(f"   DOFs: T={V_T.dim()}, k={V_k.dim()}")

    # Step 2: Boundary conditions
    print("\n2. Setting up boundary conditions...")
    bc_manager = BoundaryConditionManager(geo.mesh, geo.boundaries)

    class LeftBoundary(SubDomain):
        def inside(self, x, on_boundary):
            return on_boundary and x[0] < DOLFIN_EPS

    class RightBoundary(SubDomain):
        def inside(self, x, on_boundary):
            return on_boundary and x[0] > 1.0 - DOLFIN_EPS

    bc_manager.boundaries.set_all(0)
    LeftBoundary().mark(bc_manager.boundaries, 1)
    RightBoundary().mark(bc_manager.boundaries, 2)
    bc_manager.ds = Measure("ds", domain=geo.mesh, subdomain_data=bc_manager.boundaries)

    bc_manager.add_dirichlet(380.0, boundary_marker=1)
    bc_manager.add_dirichlet(300.0, boundary_marker=2)

    print(f"   Dirichlet BCs: T={380}K (left), T={300}K (right)")

    # Step 3: Forward solver
    print("\n3. Initializing forward solver...")
    forward_solver = HeatForwardSolver(
        V=V_T,
        bc_manager=bc_manager,
        rho=8960.0,
        cp=385.0,
        f_source=0.0
    )

    # Step 4: True conductivity and synthetic measurements
    print("\n4. Generating synthetic measurements...")
    k_true_expr = Expression(
        '5.0 + 15.0 * (x[0] > 0.3 && x[0] < 0.7 && x[1] > 0.3 && x[1] < 0.7)',
        degree=1
    )
    k_true = interpolate(k_true_expr, V_k)

    measurements = MeasurementData()
    measurements.generate_synthetic(
        geometry_handler=geo,
        num_points=25,
        mode='grid',
        true_k=k_true,
        forward_solver=forward_solver,
        noise_std=0.5,
        transient=transient,
        t_start=0.0,
        t_end=50.0,
        num_times=10
    )

    print(f"   {measurements.num_points} measurement points")
    if transient:
        print(f"   {len(measurements.time_grid)} time steps")

    measurements.save_h5(os.path.join(output_dir, 'measurements.h5'))

    # Step 5: Save true conductivity
    vtk_writer = VTKWriter(output_dir=output_dir)
    vtk_writer.write_conductivity(k_true, "conductivity_true")

    # Step 6: Objective function and regularization
    print("\n5. Setting up objective function...")
    regularization = Regularization(
        reg_type='tikhonov',
        alpha=1e-2,
        beta=1e-6
    )

    objective = ObjectiveFunction(
        forward_solver=forward_solver,
        measurements=measurements,
        regularization=regularization,
        k_space=V_k
    )

    # Step 7: Adjoint gradient
    print("\n6. Setting up adjoint gradient...")
    gradient = AdjointGradient(
        forward_solver=forward_solver,
        objective=objective,
        measurements=measurements,
        regularization=regularization,
        k_space=V_k
    )

    # Gradient check
    print("\n   Checking gradient...")
    k0_check = np.ones(V_k.dim()) * 10.0
    gradient.check_gradient(k0_check, eps=1e-5)

    # Step 8: Optimization
    print("\n7. Running optimization...")
    opt_options = OptimizationOptions(
        max_iter=50,
        display_progress=True,
        k_min=0.5,
        k_max=50.0
    )

    optimizer = InverseOptimizer(
        objective=objective,
        gradient=gradient,
        k_space=V_k,
        options=opt_options
    )

    k0 = np.ones(V_k.dim()) * 10.0
    result = optimizer.optimize(k0=k0)

    # Step 9: Post-processing
    print("\n8. Post-processing results...")

    vtk_writer.write_conductivity(result.k_function, "conductivity_optimized")

    if transient:
        T_sim = forward_solver.solve_transient(result.k_function, times=measurements.time_grid)
        vtk_writer.write_transient(T_sim, measurements.time_grid, "temperature_optimized")
        T_final = T_sim[-1]
        T_true = forward_solver.solve_transient(k_true, times=measurements.time_grid)[-1]
    else:
        T_sim = forward_solver.solve(result.k_function)
        vtk_writer.write_temperature(T_sim, "temperature_optimized")
        T_final = T_sim
        T_true = forward_solver.solve(k_true)

    # Step 10: Uncertainty quantification
    print("\n9. Uncertainty quantification...")
    try:
        uqt = UncertaintyQuantifier(
            objective=objective,
            gradient=gradient,
            forward_solver=forward_solver,
            measurements=measurements,
            regularization=regularization,
            k_space=V_k
        )

        sigma = uqt.compute_std_dev(result.k_opt)
        vtk_writer.write_conductivity(sigma, "conductivity_std_dev",
                                      name="conductivity_std_dev")

        lower, upper = uqt.compute_confidence_interval(result.k_opt, alpha=0.95)
        vtk_writer.write_conductivity(lower, "conductivity_lower_95CI")
        vtk_writer.write_conductivity(upper, "conductivity_upper_95CI")

        vtk_writer.write_combined(result.k_function, T_final,
                                  "results_combined", uncertainty=sigma)
    except Exception as e:
        print(f"   Warning: UQT failed: {e}")
        sigma = None

    # Step 11: Visualization
    print("\n10. Generating plots...")
    visualizer = ResultsVisualizer(output_dir=output_dir)

    k_error = Function(V_k)
    k_error.vector()[:] = np.abs(result.k_function.vector().get_local() - k_true.vector().get_local())
    vtk_writer.write_conductivity(k_error, "conductivity_error", name="error")

    visualizer.plot_conductivity_2d(k_true, "conductivity_true.png",
                                    title="True Thermal Conductivity")
    visualizer.plot_conductivity_2d(result.k_function, "conductivity_optimized.png",
                                    title="Reconstructed Thermal Conductivity")
    visualizer.plot_conductivity_2d(k_error, "conductivity_error.png",
                                    title="Absolute Error", cmap="Reds")
    visualizer.plot_temperature_2d(T_final, "temperature_optimized.png")
    if sigma is not None:
        visualizer.plot_uncertainty_2d(sigma)
    visualizer.plot_optimization_history(result.J_history, result.grad_norm_history)

    # Error metrics
    k_true_vec = k_true.vector().get_local()
    k_opt_vec = result.k_function.vector().get_local()
    rel_error = np.linalg.norm(k_opt_vec - k_true_vec) / np.linalg.norm(k_true_vec)
    max_error = np.max(np.abs(k_opt_vec - k_true_vec))

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"Relative L2 error in k: {rel_error:.4%}")
    print(f"Max absolute error in k: {max_error:.4f}")
    print(f"Final objective: {result.J_opt:.6e}")
    print(f"Iterations: {result.n_iter}")
    print(f"Converged: {result.converged}")
    print(f"Output: {output_dir}")
    print("=" * 60)

    return {
        'k_true': k_true,
        'k_opt': result.k_function,
        'T_final': T_final,
        'sigma': sigma,
        'result': result,
        'output_dir': output_dir
    }


if __name__ == '__main__':
    print("Running heat inversion test cases...\n")

    print("\n" + "#" * 60)
    print("# STEADY-STATE TEST CASE")
    print("#" * 60)
    run_test_case(transient=False)

    print("\n" + "#" * 60)
    print("# TRANSIENT TEST CASE")
    print("#" * 60)
    run_test_case(transient=True)

    print("\n✅ All test cases completed!")
