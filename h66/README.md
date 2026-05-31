# Thermal Conductivity Inverse Problem Solver

A Python package for solving the inverse heat conduction problem to estimate
thermal conductivity distribution from temperature measurements, using FEniCS.

## Features

- **Geometry handling**: STL file import, mesh generation, box mesh for testing
- **Forward solver**: Steady-state and transient heat conduction using FEM (FEniCS)
- **Boundary conditions**: Dirichlet (temperature), Neumann (heat flux), Robin (convection)
- **Measurement data**: Steady-state and transient (time series) support
- **Regularization**: Tikhonov (L2, H1, combined) and Total Variation (TV)
- **Optimization**: L-BFGS with bounds, using adjoint method for gradient computation
- **Uncertainty quantification**: Laplace approximation (Gaussian posterior)
- **Output**: VTK format for visualization, XDMF for FEniCS, CSV for measurements

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

### Dependencies

- **FEniCS** (2019.1.0+) - Finite element library
- **numpy**, **scipy** - Numerical computing
- **trimesh** - STL file handling
- **meshio**, **pyvista** - Mesh I/O and visualization
- **click**, **PyYAML** - CLI and configuration
- **tqdm** - Progress bars
- **h5py** - HDF5 file format

## Quick Start

### 1. Generate example configuration

```bash
heat-inv generate-config -o my_config.yaml
```

### 2. Edit configuration

Edit `my_config.yaml` to specify:
- Geometry (STL file or box mesh)
- Boundary conditions
- Measurement data (or generate synthetic)
- Regularization type and parameters
- Optimization settings

### 3. Run the inversion

```bash
heat-inv run my_config.yaml
```

### 4. Check results

Results are saved in `output/run_YYYYMMDD_HHMMSS/`:
- `conductivity_opt.vtk` - Reconstructed thermal conductivity
- `temperature_opt.vtk` - Simulated temperature field
- `conductivity_std_dev.vtk` - Uncertainty (1σ)
- `convergence.png` - Optimization convergence history
- `conductivity.png`, `temperature.png` - 2D visualization
- `config.yaml` - Copy of configuration used

## Command Line Interface

```bash
# Generate configuration template
heat-inv generate-config [--output FILE]

# Check configuration and gradient
heat-inv check CONFIG_FILE

# Run full inversion
heat-inv run CONFIG_FILE [--output DIR]
```

## Python API Usage

```python
from heat_inv import (
    GeometryHandler,
    HeatForwardSolver,
    BoundaryConditionManager,
    MeasurementData,
    ObjectiveFunction,
    Regularization,
    AdjointGradient,
    InverseOptimizer,
    OptimizationOptions,
    UncertaintyQuantifier,
)

# Create geometry
geo = GeometryHandler()
geo.create_box_mesh(nx=30, ny=30, length=1.0, width=1.0)

V_T = geo.get_function_space(degree=1)
V_k = geo.get_function_space(degree=1)

# Boundary conditions
bc_manager = BoundaryConditionManager(geo.mesh, geo.boundaries)
bc_manager.add_dirichlet(350.0, boundary_marker=1)

# Forward solver
forward_solver = HeatForwardSolver(V_T, bc_manager)

# Measurements
measurements = MeasurementData()
measurements.generate_synthetic(
    geo, num_points=20, true_k=10.0,
    forward_solver=forward_solver, noise_std=0.5
)

# Regularization and objective
regularization = Regularization(reg_type='tikhonov', alpha=1e-3, beta=1e-6)
objective = ObjectiveFunction(forward_solver, measurements, regularization, V_k)

# Gradient via adjoint method
gradient = AdjointGradient(forward_solver, objective, measurements,
                            regularization, V_k)

# Optimization
options = OptimizationOptions(max_iter=100)
optimizer = InverseOptimizer(objective, gradient, V_k, options)
result = optimizer.optimize(k0=10.0)

# Uncertainty quantification
uqt = UncertaintyQuantifier(objective, gradient, forward_solver,
                             measurements, regularization, V_k)
sigma = uqt.compute_std_dev(result.k_opt)
```

## Mathematical Formulation

### Forward Problem

Heat conduction equation:
- Steady-state: ∇·(k(x) ∇T) = 0
- Transient: ρc_p ∂T/∂t - ∇·(k(x) ∇T) = 0

### Inverse Problem

Minimize objective function:
```
J(k) = J_data(k) + J_reg(k)
```

Data misfit:
```
J_data = 1/2 * Σ_i (T_i^sim - T_i^meas)^2 / σ_i^2
```

Regularization:
- Tikhonov: J_reg = α ||∇k||² + β ||k - k_ref||²
- TV: J_reg = α ||∇k||₁ + β ||k - k_ref||²

### Adjoint Method

Gradient computed efficiently via adjoint:
1. Solve forward problem for T
2. Solve adjoint problem for p
3. Gradient: dJ/dk = ∇T · ∇p + dJ_reg/dk

### Uncertainty Quantification

Laplace approximation:
- Compute Hessian H at optimum (Gauss-Newton approximation)
- Covariance: Cov = H⁻¹
- Standard deviation: σ = sqrt(diag(Cov))

## Running Tests

```bash
# Run unit tests
pytest tests/ -v

# Run synthetic test case
python run_test.py
```

## Project Structure

```
heat_inv/
├── __init__.py           # Package exports
├── __main__.py           # Main entry point
├── geometry.py           # Geometry and mesh handling
├── boundary.py           # Boundary conditions
├── forward.py            # Forward heat solver
├── measurements.py       # Measurement data handling
├── objective.py          # Objective function and regularization
├── adjoint.py            # Adjoint gradient computation
├── optimizer.py          # L-BFGS optimization
├── uqt.py                # Uncertainty quantification
├── vtk_output.py         # VTK output and visualization
└── cli.py                # Command line interface

tests/
└── test_heat_inv.py      # Unit tests

config.yaml               # Example configuration
run_test.py               # Synthetic test case
requirements.txt          # Python dependencies
setup.py                  # Package setup
```

## License

MIT License
