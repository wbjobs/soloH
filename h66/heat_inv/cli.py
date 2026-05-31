"""
Command Line Interface for heat inversion solver.
"""

import os
import sys
import click
import yaml
import numpy as np
from datetime import datetime
from typing import Optional

from .geometry import GeometryHandler
from .forward import HeatForwardSolver
from .boundary import BoundaryConditionManager
from .measurements import MeasurementData
from .objective import ObjectiveFunction, Regularization
from .adjoint import AdjointGradient
from .optimizer import InverseOptimizer, OptimizationOptions
from .uqt import UncertaintyQuantifier
from .vtk_output import VTKWriter, ResultsVisualizer


def load_config(config_file: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    return config


def setup_output_dir(config: dict) -> str:
    """Create output directory with timestamp."""
    base_output = config.get('output', {}).get('directory', 'output')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = os.path.join(base_output, f"run_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}")
    return output_dir


def setup_geometry(config: dict) -> GeometryHandler:
    """Set up geometry and mesh."""
    geom_config = config.get('geometry', {})
    geo = GeometryHandler(
        stl_file=geom_config.get('stl_file'),
        mesh_file=geom_config.get('mesh_file'),
        mesh_resolution=geom_config.get('resolution', 1.0)
    )

    if geom_config.get('use_box_mesh', False):
        nx = geom_config.get('nx', 30)
        ny = geom_config.get('ny', 30)
        nz = geom_config.get('nz', 1)
        Lx = geom_config.get('length', 1.0)
        Ly = geom_config.get('width', 1.0)
        Lz = geom_config.get('height', 0.1)
        geo.create_box_mesh(nx=nx, ny=ny, nz=nz, length=Lx, width=Ly, height=Lz)
    elif geom_config.get('mesh_file'):
        geo.load_mesh(geom_config['mesh_file'])
    elif geom_config.get('stl_file'):
        geo.generate_mesh_from_stl(
            output_dir=config.get('output', {}).get('directory', 'output'),
            max_cell_size=geom_config.get('max_cell_size')
        )
    else:
        raise ValueError("Must specify mesh_file, stl_file, or use_box_mesh=True")

    return geo


def setup_boundary_conditions(config: dict, mesh, boundaries=None) -> BoundaryConditionManager:
    """Set up boundary conditions."""
    bc_manager = BoundaryConditionManager(mesh, boundaries)
    bc_config = config.get('boundary_conditions', [])

    for bc_item in bc_config:
        bc_type = bc_item.get('type')
        value = bc_item.get('value', 0.0)
        marker = bc_item.get('marker', 1)

        if bc_type == 'dirichlet':
            bc_manager.add_dirichlet(value, marker)
        elif bc_type == 'neumann':
            bc_manager.add_neumann(value, marker)
        elif bc_type == 'robin':
            h = bc_item.get('heat_transfer_coefficient', 10.0)
            T_amb = bc_item.get('ambient_temperature', 298.15)
            bc_manager.add_robin(h, T_amb, marker)
        else:
            raise ValueError(f"Unknown boundary condition type: {bc_type}")

    print(f"Set up {len(bc_manager.bcs)} boundary conditions")
    for i, bc in enumerate(bc_manager.bcs):
        print(f"  BC {i+1}: type={bc.bc_type}, marker={bc.boundary_marker}, value={bc.value}")

    return bc_manager


def setup_measurements(config: dict, geometry_handler: GeometryHandler,
                       forward_solver: HeatForwardSolver, output_dir: str) -> MeasurementData:
    """Set up measurement data."""
    meas_config = config.get('measurements', {})
    measurements = MeasurementData()

    if meas_config.get('generate_synthetic', False):
        true_k_config = meas_config.get('true_conductivity', 10.0)
        num_points = meas_config.get('num_points', 10)
        noise_std = meas_config.get('noise_std', 0.5)
        transient = meas_config.get('transient', False)

        if isinstance(true_k_config, dict):
            from dolfin import Expression, FunctionSpace
            V = geometry_handler.get_function_space(degree=1)
            if true_k_config.get('type') == 'expression':
                k_expr = Expression(true_k_config['expression'], degree=2)
                from dolfin import interpolate
                true_k = interpolate(k_expr, V)
            else:
                true_k = true_k_config.get('constant', 10.0)
        else:
            true_k = true_k_config

        measurements.generate_synthetic(
            geometry_handler=geometry_handler,
            num_points=num_points,
            mode=meas_config.get('mode', 'random'),
            true_k=true_k,
            forward_solver=forward_solver,
            noise_std=noise_std,
            transient=transient,
            t_start=meas_config.get('t_start', 0.0),
            t_end=meas_config.get('t_end', 10.0),
            num_times=meas_config.get('num_times', 20)
        )

        meas_file = os.path.join(output_dir, 'synthetic_measurements.h5')
        measurements.save_h5(meas_file)
        measurements.save_csv(os.path.join(output_dir, 'synthetic_measurements.csv'))

    elif meas_config.get('file'):
        measurements.load_h5(meas_config['file'])

    else:
        points = meas_config.get('points', [])
        for pt in points:
            measurements.add_point(
                x=pt['x'], y=pt.get('y', 0), z=pt.get('z', 0),
                temperature=pt.get('temperature'),
                time_series=pt.get('time_series'),
                times=pt.get('times'),
                std_dev=pt.get('std_dev', 1.0)
            )

    print(f"Loaded {measurements.num_points} measurement points")
    if measurements.is_transient:
        print(f"  Transient: {len(measurements.time_grid)} time steps, "
              f"t=[{measurements.time_grid[0]:.2f}, {measurements.time_grid[-1]:.2f}]")

    return measurements


def solve_inverse_problem(config: dict, output_dir: str) -> dict:
    """
    Run the complete inverse problem workflow.

    Parameters
    ----------
    config : dict
        Configuration dictionary
    output_dir : str
        Output directory

    Returns
    -------
    dict
        Results dictionary
    """
    import shutil

    config_file = os.path.join(output_dir, 'config.yaml')
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

    print("\n" + "=" * 60)
    print("STEP 1: Setting up geometry and mesh")
    print("=" * 60)
    geo = setup_geometry(config)

    V_T = geo.get_function_space(degree=1)
    V_k = geo.get_function_space(degree=1)

    print(f"Temperature function space: {V_T.dim()} DOFs")
    print(f"Conductivity function space: {V_k.dim()} DOFs")

    print("\n" + "=" * 60)
    print("STEP 2: Setting up boundary conditions")
    print("=" * 60)
    bc_manager = setup_boundary_conditions(config, geo.mesh, geo.boundaries)

    print("\n" + "=" * 60)
    print("STEP 3: Setting up forward solver")
    print("=" * 60)
    physics_config = config.get('physics', {})
    forward_solver = HeatForwardSolver(
        V=V_T,
        bc_manager=bc_manager,
        rho=physics_config.get('rho', 1.0),
        cp=physics_config.get('cp', 1.0),
        f_source=physics_config.get('heat_source', 0.0)
    )
    print("Forward solver initialized")

    print("\n" + "=" * 60)
    print("STEP 4: Loading/generating measurement data")
    print("=" * 60)
    measurements = setup_measurements(config, geo, forward_solver, output_dir)

    print("\n" + "=" * 60)
    print("STEP 5: Setting up objective function and regularization")
    print("=" * 60)
    reg_config = config.get('regularization', {})
    opt_config = config.get('optimization', {})
    inverse_config = config.get('inverse', {})

    from .regularization import create_regularization
    reg_kwargs = {}
    if reg_config.get('type') in ['weighted_tv', 'adaptive']:
        reg_kwargs['measurement_coords'] = measurements.get_coordinates()
        reg_kwargs['mesh'] = geo.mesh

    regularization = create_regularization(reg_config, **reg_kwargs)
    print(f"Regularization: {regularization.reg_type}, "
          f"alpha={float(regularization.alpha):.2e}, "
          f"beta={float(regularization.beta):.2e}")

    estimate_T0 = inverse_config.get('estimate_T0', False) and measurements.is_transient
    use_barrier = inverse_config.get('use_barrier', True)
    use_scaling = inverse_config.get('use_scaling', True)

    if estimate_T0:
        print("Joint inversion mode: estimating k and T0 simultaneously")
        from .objective import JointObjectiveFunction, Regularization

        T0_reg_config = inverse_config.get('T0_regularization', {})
        T0_regularization = Regularization(
            reg_type=T0_reg_config.get('type', 'tikhonov1'),
            alpha=T0_reg_config.get('alpha', 1e-2),
            beta=T0_reg_config.get('beta', 0.0)
        )

        objective = JointObjectiveFunction(
            forward_solver=forward_solver,
            measurements=measurements,
            regularization=regularization,
            k_space=V_k,
            T0_space=V_T,
            estimate_T0=True,
            k_bounds=(opt_config.get('k_min', 0.1), opt_config.get('k_max', 200.0)),
            T0_bounds=inverse_config.get('T0_bounds'),
            use_barrier=use_barrier,
            barrier_mu=inverse_config.get('barrier_mu', 1e-4),
            use_scaling=use_scaling,
            T0_regularization=T0_regularization
        )
    else:
        objective = ObjectiveFunction(
            forward_solver=forward_solver,
            measurements=measurements,
            regularization=regularization,
            k_space=V_k
        )

    print("\n" + "=" * 60)
    print("STEP 6: Setting up adjoint gradient")
    print("=" * 60)
    gradient = AdjointGradient(
        forward_solver=forward_solver,
        objective=objective,
        measurements=measurements,
        regularization=regularization,
        k_space=V_k
    )
    print("Adjoint gradient computer initialized")

    if config.get('check_gradient', False):
        print("\nChecking adjoint gradient against numerical gradient...")
        k0 = np.ones(V_k.dim()) * 10.0
        gradient.check_gradient(k0, eps=1e-5)

    print("\n" + "=" * 60)
    print("STEP 7: Running optimization")
    print("=" * 60)
    opt_options = OptimizationOptions(
        max_iter=opt_config.get('max_iter', 100),
        ftol=opt_config.get('ftol', 1e-8),
        gtol=opt_config.get('gtol', 1e-5),
        k_min=opt_config.get('k_min', 0.1),
        k_max=opt_config.get('k_max', 200.0),
        display_progress=opt_config.get('display_progress', True),
        output_dir=output_dir,
        use_continuation=inverse_config.get('use_continuation', False),
        continuation_steps=inverse_config.get('continuation_steps', 3),
        use_two_phase=inverse_config.get('use_two_phase', True),
        phase1_iter=inverse_config.get('phase1_iter', 20),
        enforce_bounds_projection=inverse_config.get('enforce_bounds', True),
        adaptive_regularization=inverse_config.get('adaptive_regularization', False),
        initial_barrier_mu=inverse_config.get('barrier_mu', 1e-4),
        barrier_decrease_factor=inverse_config.get('barrier_decrease_factor', 0.1)
    )

    if estimate_T0:
        from .optimizer import JointInverseOptimizer
        optimizer = JointInverseOptimizer(
            objective=objective,
            gradient=gradient,
            k_space=V_k,
            T0_space=V_T,
            options=opt_options
        )

        k0_val = opt_config.get('initial_guess', 10.0)
        T0_guess = inverse_config.get('T0_initial_guess', 300.0)
        k0 = np.ones(V_k.dim()) * k0_val
        T0 = np.ones(V_T.dim()) * T0_guess

        print(f"Initial k guess: {k0_val} W/m·K")
        print(f"Initial T0 guess: {T0_guess} K")

        if opt_options.use_two_phase:
            print("\nUsing two-phase optimization strategy")
            result = optimizer.optimize_two_phase(k0=k0, T0=T0)
        else:
            x0 = np.concatenate([k0, T0])
            result = optimizer.optimize(x0=x0)
    else:
        optimizer = InverseOptimizer(
            objective=objective,
            gradient=gradient,
            k_space=V_k,
            options=opt_options
        )

        k0 = opt_config.get('initial_guess', 10.0)
        result = optimizer.optimize(k0=k0)

    print("\n" + "=" * 60)
    print("STEP 8: Post-processing and output")
    print("=" * 60)

    from .optimizer import JointOptimizationResult
    is_joint = isinstance(result, JointOptimizationResult)

    vtk_writer = VTKWriter(output_dir=output_dir)
    visualizer = ResultsVisualizer(output_dir=output_dir)

    vtk_writer.write_conductivity(result.k_function, "conductivity_opt")

    if is_joint and hasattr(result, 'T0_function') and result.T0_function is not None:
        vtk_writer.write_temperature(result.T0_function, "T0_initial_opt", name="T0")
        print("Wrote estimated initial temperature T0")

    if measurements.is_transient:
        if is_joint and hasattr(result, 'T0_function') and result.T0_function is not None:
            T_sim = forward_solver.solve_transient(
                result.k_function,
                T0=result.T0_function,
                times=measurements.time_grid
            )
        else:
            T_sim = forward_solver.solve_transient(result.k_function, times=measurements.time_grid)
        vtk_writer.write_transient(T_sim, measurements.time_grid, "temperature_opt")
        T_final = T_sim[-1]
    else:
        T_sim = forward_solver.solve(result.k_function)
        vtk_writer.write_temperature(T_sim, "temperature_opt")
        T_final = T_sim

    k_opt_vec = result.k_opt

    if is_joint and hasattr(result, 'k_bounds_violation'):
        print(f"\nOptimization Summary:")
        print(f"  k bounds: [{opt_options.k_min:.2f}, {opt_options.k_max:.2f}]")
        print(f"  final k range: [{np.min(k_opt_vec):.3f}, {np.max(k_opt_vec):.3f}]")
        print(f"  k bounds violation: {result.k_bounds_violation:.2e}")
        if hasattr(result, 'T0_opt') and result.T0_opt is not None:
            print(f"  final T0 range: [{np.min(result.T0_opt):.1f}, {np.max(result.T0_opt):.1f}] K")
            if hasattr(result, 'T0_bounds_violation'):
                print(f"  T0 bounds violation: {result.T0_bounds_violation:.2e}")

    sigma = None
    if config.get('uncertainty', {}).get('quantify', False):
        print("\n" + "=" * 60)
        print("STEP 9: Uncertainty Quantification")
        print("=" * 60)

        uqt_config = config.get('uncertainty', {})
        uqt = UncertaintyQuantifier(
            objective=objective,
            gradient=gradient,
            forward_solver=forward_solver,
            measurements=measurements,
            regularization=regularization,
            k_space=V_k
        )

        try:
            sigma = uqt.compute_std_dev(k_opt_vec)
            vtk_writer.write_conductivity(sigma, "conductivity_std_dev",
                                          name="conductivity_std_dev")

            lower, upper = uqt.compute_confidence_interval(k_opt_vec, alpha=0.95)
            vtk_writer.write_conductivity(lower, "conductivity_lower_95CI",
                                          name="conductivity_lower")
            vtk_writer.write_conductivity(upper, "conductivity_upper_95CI",
                                          name="conductivity_upper")

            if uqt_config.get('compute_eigenvalues', False):
                uqt.compute_eigenspectrum(k_opt_vec, num_eigenvalues=10)

            vtk_writer.write_combined(result.k_function, T_final,
                                      "results_combined", uncertainty=sigma)

        except Exception as e:
            print(f"Warning: Uncertainty quantification failed: {e}")
            import traceback
            traceback.print_exc()

    print("\nGenerating plots...")
    if geo.mesh.topology().dim() == 2:
        visualizer.plot_conductivity_2d(result.k_function)
        visualizer.plot_temperature_2d(T_final)
        if sigma is not None:
            visualizer.plot_uncertainty_2d(sigma)

    visualizer.plot_optimization_history(result.J_history, result.grad_norm_history)

    T_sim_pts = forward_solver.evaluate_at_points(T_final, measurements.get_coordinates())
    T_meas_pts = measurements.get_measurement_vector(
        time_idx=-1 if measurements.is_transient else None
    )
    visualizer.plot_measured_vs_simulated(
        T_meas_pts, T_sim_pts, measurements.get_std_dev_vector()
    )

    if measurements.is_transient:
        for pt_idx in [0, min(4, measurements.num_points - 1)]:
            T_meas_trans = np.array([p.time_series[pt_idx] for p in measurements.points]) \
                if pt_idx < measurements.num_points else measurements.points[0].time_series
            T_sim_trans = np.array([
                forward_solver.evaluate_at_points(T_t, measurements.get_coordinates())[
                    min(pt_idx, measurements.num_points - 1)]
                for T_t in T_sim
            ])
            visualizer.plot_transient_comparison(
                measurements.time_grid,
                measurements.points[min(pt_idx, measurements.num_points - 1)].time_series,
                T_sim_trans,
                point_idx=min(pt_idx, measurements.num_points - 1),
                filename=f"transient_comparison_pt{pt_idx}.png"
            )

    results = {
        'k_opt': result.k_function,
        'k_opt_vec': k_opt_vec,
        'T_sim': T_sim,
        'T_final': T_final,
        'sigma': sigma,
        'result': result,
        'output_dir': output_dir
    }

    print("\n" + "=" * 60)
    print("INVERSION COMPLETE")
    print("=" * 60)
    print(f"All results saved to: {output_dir}")

    return results


@click.group()
def cli():
    """Thermal Conductivity Inverse Problem Solver."""
    pass


@cli.command()
@click.argument('config_file', type=click.Path(exists=True))
def run(config_file):
    """Run inverse problem from configuration file."""
    print("=" * 60)
    print("THERMAL CONDUCTIVITY INVERSE PROBLEM SOLVER")
    print("=" * 60)
    print(f"Loading configuration from: {config_file}")

    config = load_config(config_file)
    output_dir = setup_output_dir(config)

    try:
        results = solve_inverse_problem(config, output_dir)
        print("\n✅ Inversion completed successfully!")
        return results
    except Exception as e:
        print(f"\n❌ Error during inversion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', default='example_config.yaml',
              help='Output configuration file name')
def generate_config(output):
    """Generate an example configuration file."""
    example_config = {
        'geometry': {
            'use_box_mesh': True,
            'nx': 30,
            'ny': 30,
            'nz': 1,
            'length': 1.0,
            'width': 1.0,
            'height': 0.1,
            'mesh_file': None,
            'stl_file': None,
            'resolution': 0.1
        },
        'boundary_conditions': [
            {
                'type': 'dirichlet',
                'value': 350.0,
                'marker': 1
            },
            {
                'type': 'robin',
                'heat_transfer_coefficient': 10.0,
                'ambient_temperature': 298.15,
                'marker': 2
            }
        ],
        'physics': {
            'rho': 8960.0,
            'cp': 385.0,
            'heat_source': 0.0
        },
        'measurements': {
            'generate_synthetic': True,
            'num_points': 20,
            'mode': 'random',
            'noise_std': 0.5,
            'transient': False,
            'true_conductivity': {
                'type': 'expression',
                'expression': '10.0 + 5.0 * sin(2*pi*x[0]) * sin(2*pi*x[1])'
            },
            'file': None,
            'points': []
        },
        'regularization': {
            'type': 'tikhonov',
            'alpha': 1e-3,
            'beta': 1e-6,
            'k_ref': None
        },
        'optimization': {
            'max_iter': 100,
            'ftol': 1e-8,
            'gtol': 1e-5,
            'k_min': 0.1,
            'k_max': 200.0,
            'initial_guess': 10.0,
            'display_progress': True
        },
        'uncertainty': {
            'quantify': True,
            'compute_eigenvalues': False
        },
        'check_gradient': False,
        'output': {
            'directory': 'output'
        }
    }

    with open(output, 'w') as f:
        yaml.dump(example_config, f, default_flow_style=False, sort_keys=False)

    print(f"Example configuration generated: {output}")
    print("Edit this file to set up your inverse problem.")


@cli.command()
@click.argument('config_file', type=click.Path(exists=True))
def check(config_file):
    """Check configuration and gradient without full optimization."""
    print("Checking configuration and gradient...")

    config = load_config(config_file)
    output_dir = setup_output_dir(config)
    config['check_gradient'] = True
    config['optimization']['max_iter'] = 1

    try:
        solve_inverse_problem(config, output_dir)
        print("\n✅ Configuration check passed!")
    except Exception as e:
        print(f"\n❌ Configuration error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == '__main__':
    main()
