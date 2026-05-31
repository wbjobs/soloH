"""
Test script that runs without FEniCS using mock dolfin.
"""

import os
import sys

test_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, test_dir)
sys.path.insert(0, os.path.dirname(test_dir))

import mock_dolfin as dolfin
sys.modules['dolfin'] = dolfin

print("Testing with mock dolfin...\n")

try:
    from heat_inv.geometry import GeometryHandler
    from heat_inv.boundary import BoundaryConditionManager, BoundaryCondition
    from heat_inv.measurements import MeasurementData
    from heat_inv.objective import ObjectiveFunction, Regularization
    from heat_inv.adjoint import AdjointGradient
    from heat_inv.forward import HeatForwardSolver
    from heat_inv.optimizer import InverseOptimizer, OptimizationOptions
    from heat_inv.uqt import UncertaintyQuantifier
    from heat_inv.vtk_output import VTKWriter, ResultsVisualizer

    print("✅ All modules imported successfully!")

    print("\n1. Testing GeometryHandler...")
    geo = GeometryHandler()
    mesh = geo.create_box_mesh(nx=10, ny=10, length=1.0, width=1.0)
    V_T = geo.get_function_space(degree=1)
    V_k = geo.get_function_space(degree=1)
    print(f"   Mesh: {mesh.num_vertices()} vertices, {mesh.num_cells()} cells")
    print(f"   V_T dim: {V_T.dim()}, V_k dim: {V_k.dim()}")

    print("\n2. Testing BoundaryConditionManager...")
    bc_manager = BoundaryConditionManager(geo.mesh, geo.boundaries)
    bc_manager.add_dirichlet(350.0)
    bc_manager.add_neumann(10.0)
    bc_manager.add_robin(5.0, 298.0)
    print(f"   BCs: {len(bc_manager.bcs)} total")
    print(f"   Dirichlet: {bc_manager.has_dirichlet()}")
    print(f"   Neumann: {bc_manager.has_neumann()}")
    print(f"   Robin: {bc_manager.has_robin()}")

    print("\n3. Testing HeatForwardSolver...")
    forward_solver = HeatForwardSolver(V_T, bc_manager)
    T = forward_solver.solve(dolfin.Constant(10.0))
    print(f"   Temperature solution vector size: {T.vector().size()}")

    print("\n4. Testing MeasurementData...")
    md = MeasurementData()
    md.add_point(0.25, 0.25, temperature=350.0, std_dev=0.5)
    md.add_point(0.75, 0.75, temperature=320.0, std_dev=0.5)
    print(f"   {md.num_points} measurement points")
    print(f"   Coordinates: {md.get_coordinates()}")
    print(f"   Temperatures: {md.get_measurement_vector()}")

    print("\n5. Testing Regularization...")
    reg = Regularization(reg_type='tikhonov', alpha=1e-3, beta=1e-4)
    k = dolfin.Function(V_k)
    k.vector()[:] = 10.0
    J_reg = reg.compute_value(k, geo.dx)
    print(f"   Regularization value: {J_reg}")

    print("\n6. Testing ObjectiveFunction...")
    objective = ObjectiveFunction(forward_solver, md, reg, V_k)
    k_vec = dolfin.np.ones(V_k.dim()) * 10.0
    J = objective.compute(k_vec)
    print(f"   Objective value: {J:.6e}")

    print("\n7. Testing AdjointGradient...")
    gradient = AdjointGradient(forward_solver, objective, md, reg, V_k)
    grad = gradient.compute_gradient(k_vec)
    print(f"   Gradient norm: {dolfin.np.linalg.norm(grad):.6e}")

    print("\n8. Testing Optimization setup...")
    opt_options = OptimizationOptions(
        max_iter=5,
        display_progress=False,
        k_min=0.1,
        k_max=100.0
    )
    optimizer = InverseOptimizer(objective, gradient, V_k, opt_options)
    print(f"   Optimizer initialized with max_iter={opt_options.max_iter}")

    print("\n9. Testing VTKWriter...")
    output_dir = os.path.join(test_dir, 'test_output')
    writer = VTKWriter(output_dir=output_dir)
    print(f"   VTKWriter initialized with output_dir: {output_dir}")

    print("\n10. Testing UncertaintyQuantifier...")
    uqt = UncertaintyQuantifier(objective, gradient, forward_solver, md, reg, V_k)
    print("   UncertaintyQuantifier initialized")

    print("\n" + "=" * 60)
    print("✅ All tests passed with mock dolfin!")
    print("=" * 60)
    print("\nCode structure is valid. Install FEniCS/dolfin for full functionality.")

except Exception as e:
    print(f"\n❌ Error during testing: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
