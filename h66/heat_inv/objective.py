"""
Objective function for inverse heat conduction problem.
Includes data misfit and regularization terms (Tikhonov or TV).

Extended to support:
- Joint inversion of k and initial temperature T0
- Parameter scaling for multi-parameter optimization
- Barrier functions for strict constraint enforcement
- Spatially weighted regularization
"""

import numpy as np
from dolfin import *
from typing import Union, Optional, Callable, List, Tuple, Dict
from .forward import HeatForwardSolver
from .measurements import MeasurementData
from .regularization import Regularization, BarrierRegularization
from .multiphysics import MultiphysicsCoupling


class ObjectiveFunction:
    """
    Objective function for inverse heat conduction problem.

    J(k) = J_data(k) + J_reg(k)

    where:
    - J_data = 1/2 * sum_i (T_i^sim - T_i^meas)^2 / sigma_i^2
    - J_reg = regularization term
    """

    def __init__(self,
                 forward_solver: HeatForwardSolver,
                 measurements: MeasurementData,
                 regularization: Regularization,
                 k_space: FunctionSpace):
        """
        Initialize objective function.

        Parameters
        ----------
        forward_solver : HeatForwardSolver
            Forward problem solver
        measurements : MeasurementData
            Measurement data
        regularization : Regularization
            Regularization object
        k_space : FunctionSpace
            Function space for thermal conductivity
        """
        self.forward_solver = forward_solver
        self.measurements = measurements
        self.regularization = regularization
        self.V_k = k_space
        self.mesh = k_space.mesh()
        self.V_T = forward_solver.V

        self.dx = Measure("dx", domain=self.mesh)

        self._measurement_coords = measurements.get_coordinates()
        self._measurement_std = measurements.get_std_dev_vector()

        self._dk = TestFunction(self.V_k)
        self._grad = Function(self.V_k)

        self._last_k = None
        self._last_J = None
        self._last_T = None
        self._call_count = 0

    def _compute_data_misfit(self, T_sim: Union[Function, list], time_idx: int = None) -> float:
        """
        Compute data misfit term J_data.

        Parameters
        ----------
        T_sim : Function or list of Functions
            Simulated temperature field(s)
        time_idx : int, optional
            Time index for transient problems

        Returns
        -------
        float
            Data misfit value
        """
        if self.measurements.is_transient and isinstance(T_sim, list):
            total_misfit = 0.0
            times = self.measurements.time_grid
            for t_idx, T_t in enumerate(T_sim):
                T_sim_pts = self.forward_solver.evaluate_at_points(T_t, self._measurement_coords)
                T_meas = self.measurements.get_measurement_vector(time_idx=t_idx)
                weights = 1.0 / (self._measurement_std ** 2)
                misfit = 0.5 * np.sum(weights * (T_sim_pts - T_meas) ** 2)
                total_misfit += misfit
            return total_misfit / len(T_sim)
        else:
            T_sim_pts = self.forward_solver.evaluate_at_points(T_sim, self._measurement_coords)
            T_meas = self.measurements.get_measurement_vector(time_idx=time_idx)
            weights = 1.0 / (self._measurement_std ** 2)
            misfit = 0.5 * np.sum(weights * (T_sim_pts - T_meas) ** 2)
            return misfit

    def compute(self, k_vec: np.ndarray) -> float:
        """
        Compute objective function value.

        Parameters
        ----------
        k_vec : np.ndarray
            Thermal conductivity field as vector

        Returns
        -------
        float
            Objective function value
        """
        k = Function(self.V_k)
        k.vector()[:] = k_vec

        if self.measurements.is_transient:
            times = self.measurements.time_grid
            T_sim = self.forward_solver.solve_transient(k, times=times)
        else:
            T_sim = self.forward_solver.solve(k)

        J_data = self._compute_data_misfit(T_sim)
        J_reg = self.regularization.compute_value(k, self.dx)
        J = J_data + J_reg

        self._last_k = k_vec.copy()
        self._last_J = J
        self._last_T = T_sim
        self._call_count += 1

        return J

    def __call__(self, k_vec: np.ndarray) -> float:
        """Call compute method."""
        return self.compute(k_vec)

    def _eval_at_points_form(self, T: Function, measurement_coords: np.ndarray) -> Form:
        """
        Create UFL form for point evaluations using Dirac delta function approximation.

        Parameters
        ----------
        T : Function
            Temperature function
        measurement_coords : np.ndarray
            Measurement point coordinates

        Returns
        -------
        Form
            UFL form representing point evaluations
        """
        return None

    def get_optimization_bounds(self, k_min: float = 0.1, k_max: float = 100.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get lower and upper bounds for optimization variables.

        Parameters
        ----------
        k_min : float, optional
            Minimum thermal conductivity value
        k_max : float, optional
            Maximum thermal conductivity value

        Returns
        -------
        tuple
            (lower_bounds, upper_bounds) as numpy arrays
        """
        n = self.V_k.dim()
        lb = np.ones(n) * k_min
        ub = np.ones(n) * k_max
        return lb, ub


class ParameterScaler:
    """
    Parameter scaling for multi-parameter optimization.

    Scales parameters to similar magnitudes to improve conditioning
    of the optimization problem.
    """

    def __init__(self, scales: Optional[dict] = None):
        """
        Initialize parameter scaler.

        Parameters
        ----------
        scales : dict, optional
            Dictionary with keys 'k' and 'T0' specifying scale factors.
            If None, automatic scaling will be used.
        """
        self.scales = scales or {}
        self.k_scale = self.scales.get('k', 10.0)
        self.T0_scale = self.scales.get('T0', 300.0)

    def scale_k(self, k):
        """Scale thermal conductivity to dimensionless."""
        return k / self.k_scale

    def unscale_k(self, k_scaled):
        """Unscale thermal conductivity to physical units."""
        return k_scaled * self.k_scale

    def scale_T0(self, T0):
        """Scale initial temperature to dimensionless."""
        return T0 / self.T0_scale

    def unscale_T0(self, T0_scaled):
        """Unscale initial temperature to physical units."""
        return T0_scaled * self.T0_scale

    def scale_vector(self, vec: np.ndarray, k_dim: int) -> np.ndarray:
        """Scale combined parameter vector."""
        vec_scaled = vec.copy()
        vec_scaled[:k_dim] /= self.k_scale
        if len(vec) > k_dim:
            vec_scaled[k_dim:] /= self.T0_scale
        return vec_scaled

    def unscale_vector(self, vec_scaled: np.ndarray, k_dim: int) -> np.ndarray:
        """Unscale combined parameter vector."""
        vec = vec_scaled.copy()
        vec[:k_dim] *= self.k_scale
        if len(vec) > k_dim:
            vec[k_dim:] *= self.T0_scale
        return vec

    def scale_gradient(self, grad: np.ndarray, k_dim: int) -> np.ndarray:
        """Scale gradient (chain rule)."""
        grad_scaled = grad.copy()
        grad_scaled[:k_dim] *= self.k_scale
        if len(grad) > k_dim:
            grad_scaled[k_dim:] *= self.T0_scale
        return grad_scaled


class JointObjectiveFunction(ObjectiveFunction):
    """
    Objective function for joint inversion of thermal conductivity k
    and initial temperature field T0 for transient problems.

    Parameters vector layout: [k_0, k_1, ..., k_{n-1}, T0_0, T0_1, ..., T0_{n-1}]

    J(k, T0) = J_data(k, T0) + J_reg(k) + J_barrier(k, T0)
    """

    def __init__(self,
                 forward_solver: HeatForwardSolver,
                 measurements: MeasurementData,
                 regularization: 'Regularization',
                 k_space: FunctionSpace,
                 T0_space: Optional[FunctionSpace] = None,
                 estimate_T0: bool = False,
                 k_bounds: Tuple[float, float] = (0.1, 200.0),
                 T0_bounds: Optional[Tuple[float, float]] = None,
                 use_barrier: bool = True,
                 barrier_mu: float = 1e-4,
                 use_scaling: bool = True,
                 parameter_scaler: Optional[ParameterScaler] = None,
                 T0_regularization: Optional['Regularization'] = None):
        """
        Initialize joint objective function.

        Parameters
        ----------
        forward_solver : HeatForwardSolver
            Forward problem solver
        measurements : MeasurementData
            Measurement data (must be transient)
        regularization : Regularization
            Regularization for k
        k_space : FunctionSpace
            Function space for k
        T0_space : FunctionSpace, optional
            Function space for T0 (defaults to k_space if None)
        estimate_T0 : bool
            Whether to estimate initial temperature
        k_bounds : tuple
            (min, max) bounds for thermal conductivity
        T0_bounds : tuple, optional
            (min, max) bounds for initial temperature
        use_barrier : bool
            Use logarithmic barrier for strict constraint enforcement
        barrier_mu : float
            Barrier strength parameter
        use_scaling : bool
            Use parameter scaling
        parameter_scaler : ParameterScaler, optional
            Custom parameter scaler
        T0_regularization : Regularization, optional
            Regularization for T0 (smoothing)
        """
        super().__init__(forward_solver, measurements, regularization, k_space)

        if estimate_T0 and not measurements.is_transient:
            raise ValueError("T0 estimation requires transient measurements")

        self.estimate_T0 = estimate_T0
        self.T0_space = T0_space or k_space
        self.k_dim = k_space.dim()
        self.T0_dim = self.T0_space.dim() if estimate_T0 else 0
        self.total_dim = self.k_dim + self.T0_dim

        self.k_min, self.k_max = k_bounds
        if T0_bounds is None:
            T0_min = measurements.get_measurement_vector(time_idx=0).min() - 50
            T0_max = measurements.get_measurement_vector(time_idx=0).max() + 50
            T0_bounds = (T0_min, T0_max)
        self.T0_min, self.T0_max = T0_bounds

        self.use_barrier = use_barrier
        self.use_scaling = use_scaling
        self.scaler = parameter_scaler or ParameterScaler()

        self.T0_regularization = T0_regularization
        self._last_T0 = None

        if use_barrier:
            self._setup_barrier(barrier_mu)

        self._dT0 = TestFunction(self.T0_space) if estimate_T0 else None

    def _setup_barrier(self, barrier_mu: float):
        """Set up barrier regularization for all parameters."""
        n = self.total_dim
        lb = np.ones(n) * self.k_min
        ub = np.ones(n) * self.k_max

        if self.estimate_T0:
            lb[self.k_dim:] = self.T0_min
            ub[self.k_dim:] = self.T0_max

        self.barrier = BarrierRegularization(lb, ub, mu=barrier_mu)

    def _unpack_params(self, params: np.ndarray) -> Tuple[Function, Optional[Function]]:
        """
        Unpack parameter vector into k and T0 Functions.

        Parameters
        ----------
        params : np.ndarray
            Combined parameter vector (possibly scaled)

        Returns
        -------
        tuple
            (k_function, T0_function)
        """
        if self.use_scaling:
            params = self.scaler.unscale_vector(params, self.k_dim)

        k = Function(self.k_space)
        k.vector()[:] = params[:self.k_dim]

        T0 = None
        if self.estimate_T0:
            T0 = Function(self.T0_space)
            T0.vector()[:] = params[self.k_dim:]

        return k, T0

    def _pack_params(self, k: Function, T0: Optional[Function] = None) -> np.ndarray:
        """
        Pack k and T0 Functions into combined parameter vector.

        Parameters
        ----------
        k : Function
            Thermal conductivity
        T0 : Function, optional
            Initial temperature

        Returns
        -------
        np.ndarray
            Combined parameter vector (scaled if enabled)
        """
        params = np.zeros(self.total_dim)
        params[:self.k_dim] = k.vector().get_local()

        if self.estimate_T0 and T0 is not None:
            params[self.k_dim:] = T0.vector().get_local()

        if self.use_scaling:
            params = self.scaler.scale_vector(params, self.k_dim)

        return params

    def _enforce_bounds(self, params: np.ndarray) -> np.ndarray:
        """
        Project parameters onto feasible region.

        Parameters
        ----------
        params : np.ndarray
            Parameter vector (in physical units, not scaled)

        Returns
        -------
        np.ndarray
            Projected parameter vector
        """
        params_proj = params.copy()

        params_proj[:self.k_dim] = np.clip(params_proj[:self.k_dim],
                                           self.k_min, self.k_max)

        if self.estimate_T0:
            params_proj[self.k_dim:] = np.clip(params_proj[self.k_dim:],
                                               self.T0_min, self.T0_max)

        return params_proj

    def check_feasibility(self, params: np.ndarray, tol: float = 1e-10) -> Tuple[bool, dict]:
        """
        Check if parameters are within bounds.

        Parameters
        ----------
        params : np.ndarray
            Parameter vector (in physical units)
        tol : float, optional
            Tolerance for feasibility check

        Returns
        -------
        tuple
            (is_feasible, violations_dict)
            violations_dict has keys 'k' and 'T0' with max violations
        """
        lb = np.ones(self.total_dim) * self.k_min
        ub = np.ones(self.total_dim) * self.k_max
        if self.estimate_T0:
            lb[self.k_dim:] = self.T0_min
            ub[self.k_dim:] = self.T0_max

        k_viol = max(np.max(lb[:self.k_dim] - params[:self.k_dim]),
                     np.max(params[:self.k_dim] - ub[:self.k_dim]),
                     0.0)

        T0_viol = 0.0
        if self.estimate_T0:
            T0_viol = max(np.max(lb[self.k_dim:] - params[self.k_dim:]),
                          np.max(params[self.k_dim:] - ub[self.k_dim:]),
                          0.0)

        max_viol = max(k_viol, T0_viol)
        is_feasible = max_viol < tol

        violations = {'k': k_viol, 'T0': T0_viol}

        return is_feasible, violations

    def compute(self, params: np.ndarray) -> float:
        """
        Compute objective function value for joint inversion.

        Parameters
        ----------
        params : np.ndarray
            Parameter vector [k; T0] (possibly scaled)

        Returns
        -------
        float
            Objective value
        """
        k, T0 = self._unpack_params(params)

        if self.measurements.is_transient:
            times = self.measurements.time_grid
            if self.estimate_T0 and T0 is not None:
                T_sim = self.forward_solver.solve_transient(k, times=times, T_initial=T0)
            else:
                T_sim = self.forward_solver.solve_transient(k, times=times)
        else:
            T_sim = self.forward_solver.solve(k)

        J_data = self._compute_data_misfit(T_sim)
        J_reg = self.regularization.compute_value(k, self.dx)
        J = J_data + J_reg

        if self.estimate_T0 and T0 is not None and self.T0_regularization is not None:
            J += self.T0_regularization.compute_value(T0, self.dx)

        if self.use_barrier:
            if self.use_scaling:
                params_physical = self.scaler.unscale_vector(params, self.k_dim)
            else:
                params_physical = params
            J += self.barrier.compute_value(params_physical)

        self._last_k = k.vector().get_local().copy()
        if T0 is not None:
            self._last_T0 = T0.vector().get_local().copy()
        self._last_J = J
        self._last_T = T_sim
        self._call_count += 1

        return J

    def compute_gradient(self, params: np.ndarray) -> np.ndarray:
        """
        Compute gradient for joint inversion.

        Parameters
        ----------
        params : np.ndarray
            Parameter vector [k; T0] (possibly scaled)

        Returns
        -------
        np.ndarray
            Gradient vector (scaled if enabled)
        """
        k, T0 = self._unpack_params(params)
        bc_manager = self.forward_solver.bc_manager
        dirichlet_bcs = self.forward_solver.dirichlet_bcs

        grad = np.zeros(self.total_dim)

        if self.measurements.is_transient:
            times = self.measurements.time_grid
            if self.estimate_T0 and T0 is not None:
                T_solutions = self.forward_solver.solve_transient(k, times=times, T_initial=T0)
            else:
                T_solutions = self.forward_solver.solve_transient(k, times=times)

            p_solutions = self._solve_adjoint_transient_joint(
                k, T_solutions, times, bc_manager, dirichlet_bcs
            )

            n_times = len(times)
            dt = times[1] - times[0] if n_times > 1 else 1.0
            rho_cp = self.forward_solver.rho * self.forward_solver.cp

            grad_form_k = 0
            for T, p in zip(T_solutions, p_solutions):
                grad_form_k += -inner(grad(T), grad(p)) * self._dk * self.dx / n_times

            grad_k_vec = assemble(grad_form_k)
            grad[:self.k_dim] = grad_k_vec.get_local()

            grad[:self.k_dim] += assemble(
                self.regularization.compute_variation(k, self._dk, self.dx)
            ).get_local()

            if self.estimate_T0 and T0 is not None:
                p0 = p_solutions[0]
                grad_T0_form = -rho_cp * p0 * self._dT0 * self.dx
                grad_T0_vec = assemble(grad_T0_form)
                grad[self.k_dim:] = grad_T0_vec.get_local()

                if self.T0_regularization is not None:
                    grad[self.k_dim:] += assemble(
                        self.T0_regularization.compute_variation(T0, self._dT0, self.dx)
                    ).get_local()

        else:
            T = self.forward_solver.solve(k)
            p = self._solve_adjoint_stationary(k, T, bc_manager, dirichlet_bcs)

            grad_form_k = -inner(grad(T), grad(p)) * self._dk * self.dx
            grad_k_vec = assemble(grad_form_k)
            grad[:self.k_dim] = grad_k_vec.get_local()

            grad[:self.k_dim] += assemble(
                self.regularization.compute_variation(k, self._dk, self.dx)
            ).get_local()

        if self.use_barrier:
            if self.use_scaling:
                params_physical = self.scaler.unscale_vector(params, self.k_dim)
            else:
                params_physical = params
            grad += self.barrier.compute_gradient(params_physical)

        if self.use_scaling:
            grad = self.scaler.scale_gradient(grad, self.k_dim)

        return grad

    def _solve_adjoint_transient_joint(self, k: Function, T_solutions: List[Function],
                                        times: np.ndarray, bc_manager,
                                        dirichlet_bcs, theta: float = 0.5) -> List[Function]:
        """
        Solve adjoint equation backward in time for joint inversion.

        This is used to compute gradients for both k and T0.
        """
        n_times = len(times)
        dt = times[1] - times[0] if n_times > 1 else 1.0
        rho_cp = self.forward_solver.rho * self.forward_solver.cp

        p_solutions = []
        p_next = Function(self.V_T)
        p_next.vector().zero()

        p = TrialFunction(self.V_T)
        q = TestFunction(self.V_T)

        hom_bcs = []
        for bc in dirichlet_bcs:
            try:
                V_bc = bc.function_space()
            except (AttributeError, TypeError):
                V_bc = self.V_T
            try:
                if len(bc.domain_args) >= 2:
                    hom_bc = DirichletBC(V_bc, Constant(0),
                                         bc.domain_args[0], bc.domain_args[1])
                else:
                    hom_bc = DirichletBC(V_bc, Constant(0), bc.domain_args[0])
            except (IndexError, TypeError, AttributeError):
                def boundary(x, on_boundary):
                    return on_boundary
                hom_bc = DirichletBC(V_bc, Constant(0), boundary)
            hom_bcs.append(hom_bc)

        for i in range(n_times - 1, -1, -1):
            T_i = T_solutions[i]
            rhs = self._create_point_source_terms(T_i, time_idx=i)

            F = (rho_cp * (p - p_next) / Constant(dt) * q * self.dx
                 + inner(k * grad(theta * p + (1 - theta) * p_next), grad(q)) * self.dx
                 - rhs * q * self.dx)

            a_bc, L_bc = bc_manager.get_boundary_terms(p, q)
            F += theta * (a_bc - L_bc)
            a_bc_prev, L_bc_prev = bc_manager.get_boundary_terms(p_next, q)
            F += (1 - theta) * (a_bc_prev - L_bc_prev)

            a = lhs(F)
            L = rhs(F)

            A = assemble(a)
            for bc in hom_bcs:
                bc.apply(A)

            b = assemble(L)
            for bc in hom_bcs:
                bc.apply(b)

            p_current = Function(self.V_T)
            solve(A, p_current.vector(), b, 'gmres', 'hypre_amg')

            p_solutions.insert(0, p_current)
            p_next.assign(p_current)

        return p_solutions

    def get_bounds(self) -> List[Tuple[float, float]]:
        """
        Get bounds for optimization (in scaled space if scaling is used).

        Returns
        -------
        list of tuples
            List of (lower, upper) bounds for each parameter
        """
        bounds = []

        if self.use_scaling:
            k_min_s = self.scaler.scale_k(self.k_min)
            k_max_s = self.scaler.scale_k(self.k_max)
            bounds.extend([(k_min_s, k_max_s)] * self.k_dim)

            if self.estimate_T0:
                T0_min_s = self.scaler.scale_T0(self.T0_min)
                T0_max_s = self.scaler.scale_T0(self.T0_max)
                bounds.extend([(T0_min_s, T0_max_s)] * self.T0_dim)
        else:
            bounds.extend([(self.k_min, self.k_max)] * self.k_dim)
            if self.estimate_T0:
                bounds.extend([(self.T0_min, self.T0_max)] * self.T0_dim)

        return bounds

    def get_initial_params(self, k0: Union[float, np.ndarray, Function],
                           T0: Optional[Union[float, np.ndarray, Function]] = None) -> np.ndarray:
        """
        Create initial parameter vector.

        Parameters
        ----------
        k0 : float, np.ndarray, or Function
            Initial guess for k
        T0 : float, np.ndarray, or Function, optional
            Initial guess for T0

        Returns
        -------
        np.ndarray
            Initial parameter vector (scaled if enabled)
        """
        if isinstance(k0, (int, float)):
            k_vec = np.ones(self.k_dim) * k0
        elif isinstance(k0, Function):
            k_vec = k0.vector().get_local()
        else:
            k_vec = np.asarray(k0)

        k_vec = self._enforce_bounds(np.concatenate([
            k_vec, np.zeros(self.T0_dim)
        ]))[:self.k_dim]

        k_func = Function(self.V_k)
        k_func.vector()[:] = k_vec

        T0_func = None
        if self.estimate_T0:
            if T0 is None:
                T0_vec = np.ones(self.T0_dim) * 300.0
            elif isinstance(T0, (int, float)):
                T0_vec = np.ones(self.T0_dim) * T0
            elif isinstance(T0, Function):
                T0_vec = T0.vector().get_local()
            else:
                T0_vec = np.asarray(T0)

            full_params = self._enforce_bounds(np.concatenate([k_vec, T0_vec]))
            T0_func = Function(self.T0_space)
            T0_func.vector()[:] = full_params[self.k_dim:]
            k_vec = full_params[:self.k_dim]
            k_func.vector()[:] = k_vec

        return self._pack_params(k_func, T0_func)

    def update_barrier_mu(self, factor: float = 0.1):
        """Update barrier strength (for interior point continuation)."""
        if self.use_barrier:
            self.barrier.update_mu(factor)

    def get_optimization_bounds(self, k_min=0.1, k_max=100.0):
        """Override for backward compatibility."""
        n = self.V_k.dim()
        lb = np.ones(n) * k_min
        ub = np.ones(n) * k_max
        return lb, ub


class MultiphysicsObjectiveFunction(ObjectiveFunction):
    """
    Objective function for multiphysics inverse problems.
    Supports combining measurements from multiple physical fields.

    For thermoelectric coupling, measurements can be:
    - temperature (T)
    - electric potential (V)
    - current density (J)

    For thermoelastic coupling, measurements can be:
    - temperature (T)
    - displacement (u)
    - surface strains

    Data misfit:
    J_data = sum_field (1/2 * sum_i (field_sim_i - field_meas_i)^2 / sigma_i^2)
    """

    def __init__(self,
                 multiphysics_coupling: MultiphysicsCoupling,
                 measurements: MeasurementData,
                 regularization: Regularization,
                 k_space: FunctionSpace,
                 field_weights: Optional[Dict[str, float]] = None,
                 k_ref: Optional[Union[float, Function]] = None):
        """
        Initialize multiphysics objective function.

        Parameters
        ----------
        multiphysics_coupling : MultiphysicsCoupling
            Multiphysics coupling solver
        measurements : MeasurementData
            Measurement data (can include multiple field types)
        regularization : Regularization
            Regularization term
        k_space : FunctionSpace
            Function space for thermal conductivity
        field_weights : dict, optional
            Weights for each field in data misfit (default: equal weights)
        k_ref : float or Function, optional
            Reference conductivity
        """
        self.multiphysics = multiphysics_coupling
        self.coupling_type = multiphysics_coupling.coupling_type
        self.field_names = multiphysics_coupling.field_names

        heat_solver = multiphysics_coupling.get_heat_solver()

        super().__init__(
            forward_solver=heat_solver,
            measurements=measurements,
            regularization=regularization,
            k_space=k_space,
            k_ref=k_ref
        )

        if field_weights is None:
            self.field_weights = {field: 1.0 for field in self.field_names}
        else:
            self.field_weights = field_weights
            for field in self.field_names:
                if field not in self.field_weights:
                    self.field_weights[field] = 1.0

        self._field_solutions = {}

    def _compute_field_misfit(self, field_name: str,
                              sim_field: Function,
                              meas_indices: np.ndarray,
                              meas_values: np.ndarray,
                              meas_uncertainty: np.ndarray) -> Tuple[float, np.ndarray]:
        """
        Compute misfit for a single field.

        Parameters
        ----------
        field_name : str
            Name of the field
        sim_field : Function
            Simulated field
        meas_indices : np.ndarray
            Indices of measurement points
        meas_values : np.ndarray
            Measured values
        meas_uncertainty : np.ndarray
            Measurement uncertainties

        Returns
        -------
        tuple
            (misfit_value, misfit_residuals)
        """
        sim_values = np.array([float(sim_field(meas_indices[i]))
                               for i in range(len(meas_indices))])

        residuals = (sim_values - meas_values) / meas_uncertainty
        misfit = 0.5 * np.sum(residuals**2)

        return misfit, residuals

    def compute_value(self, k: Function) -> float:
        """
        Compute objective value for multiphysics problem.

        Parameters
        ----------
        k : Function
            Thermal conductivity field

        Returns
        -------
        float
            Objective value (data misfit + regularization)
        """
        solutions = self.multiphysics.solve(k)
        self._field_solutions = solutions

        J_data = 0.0

        for field_name in self.field_names:
            field_data = self.measurements.get_field_measurements(field_name)
            if field_data is None or len(field_data['values']) == 0:
                continue

            weight = self.field_weights.get(field_name, 1.0)
            misfit, _ = self._compute_field_misfit(
                field_name, solutions[field_name],
                field_data['indices'], field_data['values'],
                field_data['uncertainty']
            )
            J_data += weight * misfit

        J_reg = self.regularization.compute_value(k, self.dx)
        J_total = J_data + J_reg

        return J_total

    def compute_gradient(self, k: Function) -> np.ndarray:
        """
        Compute gradient using multiphysics adjoint approach.

        For multiple fields, we sum the contributions:
        dJ/dk = sum_field (dJ_data_field/dk) + dJ_reg/dk

        Each dJ_data_field/dk is computed via the adjoint method
        with appropriate source terms from the field's residuals.

        Parameters
        ----------
        k : Function
            Thermal conductivity field

        Returns
        -------
        np.ndarray
            Gradient vector
        """
        if len(self._field_solutions) == 0:
            _ = self.compute_value(k)

        solutions = self._field_solutions
        T = solutions.get('temperature')

        if T is None:
            T = self.forward_solver.solve(k)

        grad_total = np.zeros(self.k_space.dim())

        for field_name in self.field_names:
            field_data = self.measurements.get_field_measurements(field_name)
            if field_data is None or len(field_data['values']) == 0:
                continue

            weight = self.field_weights.get(field_name, 1.0)
            sim_field = solutions[field_name]

            _, residuals = self._compute_field_misfit(
                field_name, sim_field,
                field_data['indices'], field_data['values'],
                field_data['uncertainty']
            )

            grad_field = self._compute_field_gradient(
                field_name, k, T, sim_field,
                field_data, residuals, weight
            )
            grad_total += grad_field

        grad_reg_fe = Function(self.k_space)
        dk = TestFunction(self.k_space)
        dR_form = self.regularization.compute_variation(k, dk, self.dx)
        assemble(dR_form, tensor=grad_reg_fe.vector())
        grad_reg = grad_reg_fe.vector().get_local()

        grad_total += grad_reg

        return grad_total

    def _compute_field_gradient(self, field_name: str, k: Function,
                                T: Function, sim_field: Function,
                                field_data: dict, residuals: np.ndarray,
                                weight: float) -> np.ndarray:
        """
        Compute gradient contribution from one field.

        Uses a simplified adjoint-like approach by approximating
        the sensitivity of each field to changes in k.

        For temperature field: uses standard heat adjoint
        For other fields: uses chain rule dField/dT * dT/dk

        Parameters
        ----------
        field_name : str
            Field name
        k : Function
            Thermal conductivity
        T : Function
            Temperature field
        sim_field : Function
            Simulated field value
        field_data : dict
            Measurement data for this field
        residuals : np.ndarray
            Measurement residuals
        weight : float
            Weight for this field

        Returns
        -------
        np.ndarray
            Gradient contribution from this field
        """
        if field_name == 'temperature':
            return self._compute_heat_gradient(k, T, field_data, residuals, weight)
        else:
            return self._compute_coupled_field_gradient(
                field_name, k, T, sim_field, field_data, residuals, weight
            )

    def _compute_heat_gradient(self, k: Function, T: Function,
                               field_data: dict, residuals: np.ndarray,
                               weight: float) -> np.ndarray:
        """Compute gradient from temperature measurements (standard adjoint)."""
        adjoint_source = Function(self.V_T)
        v_arr = adjoint_source.vector()
        v_arr.zero()

        for i, idx in enumerate(field_data['indices']):
            v_arr[idx] = weight * residuals[i] / field_data['uncertainty'][i]

        p = TrialFunction(self.V_T)
        q = TestFunction(self.V_T)
        a = inner(k * grad(p), grad(q)) * self.dx
        L = adjoint_source * q * self.dx

        hom_bcs = []
        for bc in self.forward_solver.dirichlet_bcs:
            try:
                V_bc = bc.function_space()
                hom_bcs.append(DirichletBC(V_bc, Constant(0), bc.domain_args[0]))
            except Exception:
                pass

        p_sol = Function(self.V_T)
        solve(a == L, p_sol, hom_bcs)

        grad_form = inner(grad(T), grad(p_sol)) * TestFunction(self.k_space) * self.dx
        grad_fe = Function(self.k_space)
        assemble(grad_form, tensor=grad_fe.vector())

        return grad_fe.vector().get_local()

    def _compute_coupled_field_gradient(self, field_name: str, k: Function,
                                        T: Function, sim_field: Function,
                                        field_data: dict, residuals: np.ndarray,
                                        weight: float) -> np.ndarray:
        """
        Compute gradient from coupled fields (potential, displacement, etc.)
        using chain rule approximation.

        Uses sensitivity: dJ/dk = sum_i (dJ/dField_i * dField_i/dT * dT/dk)
        where dT/dk is computed via heat adjoint.
        """
        dField_dT = self._estimate_field_sensitivity(field_name, T, sim_field)

        if dField_dT is None:
            return np.zeros(self.k_space.dim())

        adjoint_source = Function(self.V_T)
        v_arr = adjoint_source.vector()
        v_arr.zero()

        for i, idx in enumerate(field_data['indices']):
            meas_coord = field_data['coordinates'][i]
            dFdT_val = dField_dT(meas_coord) if hasattr(dField_dT, '__call__') else float(dField_dT)
            v_arr[idx] = weight * residuals[i] / field_data['uncertainty'][i] * dFdT_val

        p = TrialFunction(self.V_T)
        q = TestFunction(self.V_T)
        a = inner(k * grad(p), grad(q)) * self.dx
        L = adjoint_source * q * self.dx

        hom_bcs = []
        for bc in self.forward_solver.dirichlet_bcs:
            try:
                V_bc = bc.function_space()
                hom_bcs.append(DirichletBC(V_bc, Constant(0), bc.domain_args[0]))
            except Exception:
                pass

        p_sol = Function(self.V_T)
        solve(a == L, p_sol, hom_bcs)

        grad_form = inner(grad(T), grad(p_sol)) * TestFunction(self.k_space) * self.dx
        grad_fe = Function(self.k_space)
        assemble(grad_form, tensor=grad_fe.vector())

        return grad_fe.vector().get_local()

    def _estimate_field_sensitivity(self, field_name: str, T: Function,
                                     sim_field: Function) -> Optional[Function]:
        """
        Estimate dField/dT sensitivity using numerical differentiation or
        material property relationships.

        For electric potential V:
        dV/dT ~ -α (Seebeck effect)

        For displacement u:
        du/dT ~ α_T * x (thermal expansion)

        Parameters
        ----------
        field_name : str
            Field name
        T : Function
            Temperature field
        sim_field : Function
            Simulated field

        Returns
        -------
        Function or None
            Estimated sensitivity field
        """
        if self.coupling_type == 'thermoelectric':
            if field_name == 'potential':
                alpha = float(self.multiphysics.solver.alpha)
                V_sens = Function(self.V_T)
                V_sens.vector()[:] = -alpha
                return V_sens

        elif self.coupling_type == 'thermoelastic':
            if field_name == 'displacement':
                alpha_T = float(self.multiphysics.solver.alpha_T)
                u_sens = Function(self.multiphysics.function_spaces['displacement'])
                coords = self.V_T.tabulate_dof_coordinates()
                for i in range(len(coords)):
                    u_sens.vector()[i*len(coords[i]): (i+1)*len(coords[i])] = alpha_T * coords[i]
                return u_sens

        return None

