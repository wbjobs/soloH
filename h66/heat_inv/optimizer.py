"""
L-BFGS optimization for inverse heat conduction problem.
"""

import numpy as np
from scipy.optimize import minimize, fmin_l_bfgs_b
from dataclasses import dataclass, field
from typing import Optional, Callable, List
from dolfin import *
from tqdm import tqdm

from .objective import ObjectiveFunction
from .adjoint import AdjointGradient
from .regularization import AdaptiveRegularization


@dataclass
class OptimizationResult:
    """Container for optimization results."""
    k_opt: np.ndarray
    k_function: Function
    J_opt: float
    J_history: List[float]
    grad_norm_history: List[float]
    n_iter: int
    converged: bool
    message: str

    @property
    def success(self) -> bool:
        """Return True if optimization converged."""
        return self.converged


@dataclass
class JointOptimizationResult(OptimizationResult):
    """Container for joint optimization results (k and T0)."""
    T0_opt: Optional[np.ndarray] = None
    T0_function: Optional[Function] = None
    k_phase1: Optional[np.ndarray] = None
    T0_phase1: Optional[np.ndarray] = None
    k_bounds_violation: float = 0.0
    T0_bounds_violation: float = 0.0


@dataclass
class OptimizationOptions:
    """Options for L-BFGS optimization."""
    max_iter: int = 100
    max_fun_eval: int = 500
    ftol: float = 1e-8
    gtol: float = 1e-5
    bounds: Optional[tuple] = None
    m: int = 10
    pgtol: float = 1e-5
    factr: float = 1e7
    display_progress: bool = True
    save_interval: int = 5
    output_dir: str = "output"
    k_min: float = 0.1
    k_max: float = 200.0
    # Advanced options
    use_continuation: bool = False
    continuation_steps: int = 3
    use_two_phase: bool = False
    phase1_iter: int = 20
    enforce_bounds_projection: bool = True
    check_gradient: bool = False
    gradient_tol: float = 1e-3
    adaptive_regularization: bool = False
    regularization_update_interval: int = 10
    line_search_max_iter: int = 20
    # Barrier parameters
    initial_barrier_mu: float = 1e-4
    barrier_decrease_factor: float = 0.1
    final_barrier_mu: float = 1e-8


class InverseOptimizer:
    """
    L-BFGS optimizer for thermal conductivity inverse problem.

    Uses scipy's L-BFGS-B implementation with bounds support.
    """

    def __init__(self,
                 objective: ObjectiveFunction,
                 gradient: AdjointGradient,
                 k_space: FunctionSpace,
                 options: Optional[OptimizationOptions] = None):
        """
        Initialize optimizer.

        Parameters
        ----------
        objective : ObjectiveFunction
            Objective function to minimize
        gradient : AdjointGradient
            Gradient computer using adjoint method
        k_space : FunctionSpace
            Function space for thermal conductivity
        options : OptimizationOptions, optional
            Optimization options
        """
        self.objective = objective
        self.gradient = gradient
        self.V_k = k_space
        self.options = options or OptimizationOptions()

        self.J_history: List[float] = []
        self.grad_norm_history: List[float] = []
        self.k_history: List[np.ndarray] = []

        self._func_eval_count = 0
        self._grad_eval_count = 0
        self._progress_bar = None

    def _objective_wrapper(self, k_vec: np.ndarray) -> float:
        """Wrapper for objective function with history tracking."""
        J = self.objective.compute(k_vec)

        self._func_eval_count += 1
        self.J_history.append(J)

        if self._progress_bar is not None and self.options.display_progress:
            self._progress_bar.set_postfix({
                'J': f'{J:.4e}',
                'func': self._func_eval_count
            })

        return J

    def _gradient_wrapper(self, k_vec: np.ndarray) -> np.ndarray:
        """Wrapper for gradient function with history tracking."""
        g = self.gradient.compute_gradient(k_vec)

        self._grad_eval_count += 1
        grad_norm = np.linalg.norm(g)
        self.grad_norm_history.append(grad_norm)

        if len(self.J_history) == len(self.grad_norm_history) - 1:
            self.J_history.append(self.J_history[-1])

        if self._progress_bar is not None and self.options.display_progress:
            self._progress_bar.set_postfix({
                'J': f'{self.J_history[-1]:.4e}',
                '||g||': f'{grad_norm:.4e}',
                'func': self._func_eval_count,
                'grad': self._grad_eval_count
            })

        return g

    def optimize(self, k0: Optional[Union[np.ndarray, float, Function]] = None) -> OptimizationResult:
        """
        Run L-BFGS optimization.

        Parameters
        ----------
        k0 : np.ndarray, float, or Function, optional
            Initial guess for thermal conductivity. If None, uses 1.0.

        Returns
        -------
        OptimizationResult
            Optimization results
        """
        if k0 is None:
            k0_vec = np.ones(self.V_k.dim()) * 10.0
        elif isinstance(k0, (int, float)):
            k0_vec = np.ones(self.V_k.dim()) * k0
        elif isinstance(k0, Function):
            k0_vec = k0.vector().get_local()
        else:
            k0_vec = np.asarray(k0)

        if self.options.bounds is None:
            lb, ub = self.objective.get_optimization_bounds(
                k_min=self.options.k_min,
                k_max=self.options.k_max
            )
            bounds = list(zip(lb, ub))
        else:
            bounds = self.options.bounds

        self.J_history = []
        self.grad_norm_history = []
        self.k_history = []
        self._func_eval_count = 0
        self._grad_eval_count = 0

        if self.options.display_progress:
            self._progress_bar = tqdm(total=self.options.max_iter,
                                      desc="Optimizing")
        else:
            self._progress_bar = None

        try:
            k_opt, J_opt, info = fmin_l_bfgs_b(
                func=self._objective_wrapper,
                x0=k0_vec,
                fprime=self._gradient_wrapper,
                bounds=bounds,
                m=self.options.m,
                factr=self.options.factr,
                pgtol=self.options.pgtol,
                maxiter=self.options.max_iter,
                maxfun=self.options.max_fun_eval,
                iprint=0
            )

            converged = info['warnflag'] == 0
            message = self._get_lbfgs_message(info['warnflag'])
            n_iter = info['nit']

        finally:
            if self._progress_bar is not None:
                self._progress_bar.close()

        k_func = Function(self.V_k)
        k_func.vector()[:] = k_opt

        result = OptimizationResult(
            k_opt=k_opt,
            k_function=k_func,
            J_opt=J_opt,
            J_history=self.J_history.copy(),
            grad_norm_history=self.grad_norm_history.copy(),
            n_iter=n_iter,
            converged=converged,
            message=message
        )

        self._print_result_summary(result)

        return result

    def _get_lbfgs_message(self, warnflag: int) -> str:
        """Get human-readable message from L-BFGS warnflag."""
        messages = {
            0: "Convergence reached (both ftol and gtol satisfied)",
            1: "Maximum number of iterations reached",
            2: "Maximum number of function evaluations reached",
            3: "Line search failed",
            4: "Nan or Inf encountered in function or gradient"
        }
        return messages.get(warnflag, f"Unknown warnflag: {warnflag}")

    def _print_result_summary(self, result: OptimizationResult):
        """Print optimization summary."""
        print("\n" + "=" * 60)
        print("OPTIMIZATION SUMMARY")
        print("=" * 60)
        print(f"Converged: {result.converged}")
        print(f"Message: {result.message}")
        print(f"Number of iterations: {result.n_iter}")
        print(f"Function evaluations: {self._func_eval_count}")
        print(f"Gradient evaluations: {self._grad_eval_count}")
        print(f"Initial J: {self.J_history[0]:.6e}")
        print(f"Final J: {result.J_opt:.6e}")
        print(f"Relative improvement: {(self.J_history[0] - result.J_opt) / abs(self.J_history[0]):.4%}")
        if result.grad_norm_history:
            print(f"Final gradient norm: {result.grad_norm_history[-1]:.6e}")
        print("=" * 60 + "\n")

    def callback(self, xk):
        """Callback function for saving intermediate results."""
        if self.options.save_interval > 0 and self._func_eval_count % self.options.save_interval == 0:
            self.k_history.append(xk.copy())


class JointInverseOptimizer(InverseOptimizer):
    """
    Extended optimizer for joint inversion of thermal conductivity k
    and initial temperature T0 for transient problems.

    Features:
    - Two-phase optimization: first fix T0, estimate k; then refine both
    - Parameter scaling for improved conditioning
    - Logarithmic barrier for strict bound enforcement
    - Adaptive regularization updates
    - Interior point continuation (gradually reduce barrier strength)
    """

    def __init__(self,
                 objective: 'JointObjectiveFunction',
                 gradient: 'AdjointGradient',
                 k_space: FunctionSpace,
                 T0_space: Optional[FunctionSpace] = None,
                 options: Optional[OptimizationOptions] = None):
        """
        Initialize joint inversion optimizer.

        Parameters
        ----------
        objective : JointObjectiveFunction
            Objective function for joint inversion
        gradient : AdjointGradient
            Gradient computer
        k_space : FunctionSpace
            Function space for k
        T0_space : FunctionSpace, optional
            Function space for T0
        options : OptimizationOptions, optional
            Optimization options
        """
        super().__init__(objective, gradient, k_space, options)

        self.joint_objective = objective
        self.T0_space = T0_space or k_space
        self.estimate_T0 = getattr(objective, 'estimate_T0', False)

        self.T0_history: List[np.ndarray] = []

    def _objective_wrapper(self, params: np.ndarray) -> float:
        """Wrapper for objective with bounds projection."""
        if self.options.enforce_bounds_projection and hasattr(self.joint_objective, '_enforce_bounds'):
            if self.joint_objective.use_scaling:
                params_physical = self.joint_objective.scaler.unscale_vector(
                    params, self.joint_objective.k_dim)
                params_physical = self.joint_objective._enforce_bounds(params_physical)
                params = self.joint_objective.scaler.scale_vector(
                    params_physical, self.joint_objective.k_dim)

        J = self.joint_objective.compute(params)

        self._func_eval_count += 1
        self.J_history.append(J)

        if np.isnan(J) or np.isinf(J):
            print(f"Warning: Invalid J value at evaluation {self._func_eval_count}: {J}")
            J = 1e10

        if self._progress_bar is not None and self.options.display_progress:
            self._progress_bar.set_postfix({
                'J': f'{J:.4e}',
                'func': self._func_eval_count
            })

        return J

    def _gradient_wrapper(self, params: np.ndarray) -> np.ndarray:
        """Wrapper for gradient with bounds checking."""
        if hasattr(self.joint_objective, 'compute_gradient'):
            g = self.joint_objective.compute_gradient(params)
        else:
            g = self.gradient.compute_gradient(params)

        self._grad_eval_count += 1
        grad_norm = np.linalg.norm(g)
        self.grad_norm_history.append(grad_norm)

        if len(self.J_history) == len(self.grad_norm_history) - 1:
            self.J_history.append(self.J_history[-1])

        if np.any(np.isnan(g)) or np.any(np.isinf(g)):
            print(f"Warning: Invalid gradient at evaluation {self._grad_eval_count}")
            g = np.nan_to_num(g, nan=0.0, posinf=1e10, neginf=-1e10)

        if self._progress_bar is not None and self.options.display_progress:
            self._progress_bar.set_postfix({
                'J': f'{self.J_history[-1]:.4e}',
                '||g||': f'{grad_norm:.4e}',
                'func': self._func_eval_count,
                'grad': self._grad_eval_count
            })

        return g

    def _update_regularization(self, params: np.ndarray):
        """Update adaptive regularization if enabled."""
        if not self.options.adaptive_regularization:
            return

        if self._func_eval_count % self.options.regularization_update_interval != 0:
            return

        reg = self.joint_objective.regularization
        if isinstance(reg, AdaptiveRegularization):
            k, _ = self.joint_objective._unpack_params(params)
            reg.update(k, self.joint_objective.dx)
            if self.options.display_progress:
                print(f"\n  Updated regularization, alpha = {float(reg.alpha):.2e}")

    def optimize_two_phase(self, k0: Union[np.ndarray, float, Function],
                           T0_guess: Optional[Union[np.ndarray, float, Function]] = None,
                           T0_true: Optional[Function] = None) -> JointOptimizationResult:
        """
        Two-phase optimization for joint inversion.

        Phase 1: Fix initial temperature, estimate k only (well-posed)
        Phase 2: Jointly optimize both k and T0 (refinement)

        Parameters
        ----------
        k0 : float, np.ndarray, or Function
            Initial guess for thermal conductivity
        T0_guess : float, np.ndarray, or Function, optional
            Initial guess for initial temperature
        T0_true : Function, optional
            True initial temperature (for diagnostics, not used in optimization)

        Returns
        -------
        JointOptimizationResult
            Optimization results with both k and T0
        """
        if not self.estimate_T0:
            print("Warning: T0 estimation not enabled, using standard optimize")
            return self.optimize(k0)

        print("\n" + "=" * 60)
        print("TWO-PHASE JOINT INVERSION")
        print("=" * 60)

        initial_params = self.joint_objective.get_initial_params(k0, T0_guess)
        k_dim = self.joint_objective.k_dim

        print("\nPhase 1: Estimate k with fixed T0...")
        phase1_options = OptimizationOptions(**{
            **self.options.__dict__,
            'max_iter': self.options.phase1_iter,
            'use_two_phase': False,
            'enforce_bounds_projection': True,
        })

        phase1_objective = self.joint_objective
        phase1_objective.estimate_T0 = False
        phase1_objective.total_dim = k_dim
        phase1_objective.T0_dim = 0
        phase1_initial = initial_params[:k_dim]

        optimizer_phase1 = InverseOptimizer(
            phase1_objective, self.gradient, self.V_k, phase1_options
        )
        result_phase1 = optimizer_phase1.optimize(phase1_initial)

        print(f"\nPhase 1 complete: J = {result_phase1.J_opt:.4e}")

        print("\nPhase 2: Joint optimization of k and T0...")
        phase2_initial = self.joint_objective.get_initial_params(
            result_phase1.k_opt, T0_guess
        )

        phase2_objective = self.joint_objective
        phase2_objective.estimate_T0 = True
        phase2_objective.total_dim = k_dim + self.joint_objective.T0_dim

        result = self._optimize_internal(phase2_initial, is_joint=True)

        k_opt_physical = result.k_opt
        T0_opt_physical = None
        T0_func = None

        if self.joint_objective.use_scaling:
            full_params = self.joint_objective.scaler.unscale_vector(
                result.k_opt, k_dim)
            k_opt_physical = full_params[:k_dim]
            T0_opt_physical = full_params[k_dim:]
        elif len(result.k_opt) > k_dim:
            T0_opt_physical = result.k_opt[k_dim:]
            k_opt_physical = result.k_opt[:k_dim]

        k_func = Function(self.V_k)
        k_func.vector()[:] = k_opt_physical

        if T0_opt_physical is not None:
            T0_func = Function(self.T0_space)
            T0_func.vector()[:] = T0_opt_physical

        final_result = JointOptimizationResult(
            k_opt=k_opt_physical,
            k_function=k_func,
            T0_opt=T0_opt_physical,
            T0_function=T0_func,
            J_opt=result.J_opt,
            J_history=result.J_history,
            grad_norm_history=result.grad_norm_history,
            n_iter=result.n_iter + result_phase1.n_iter,
            converged=result.converged,
            message=result.message,
            k_phase1=result_phase1.k_opt,
        )

        self._print_joint_summary(final_result, T0_true)

        return final_result

    def _optimize_internal(self, x0: np.ndarray, is_joint: bool = False) -> OptimizationResult:
        """
        Internal optimization routine with continuation support.
        """
        self.J_history = []
        self.grad_norm_history = []
        self.k_history = []
        self._func_eval_count = 0
        self._grad_eval_count = 0

        if hasattr(self.joint_objective, 'get_bounds'):
            bounds = self.joint_objective.get_bounds()
        else:
            lb, ub = self.objective.get_optimization_bounds(
                k_min=self.options.k_min,
                k_max=self.options.k_max
            )
            bounds = list(zip(lb, ub))

        if self.options.display_progress:
            self._progress_bar = tqdm(total=self.options.max_iter,
                                      desc="Optimizing")

        x_current = x0.copy()
        info = None
        n_iter_total = 0

        try:
            if self.options.use_continuation and hasattr(self.joint_objective, 'barrier'):
                mu = self.options.initial_barrier_mu
                for step in range(self.options.continuation_steps):
                    print(f"\n  Continuation step {step + 1}/{self.options.continuation_steps}, "
                          f"mu = {mu:.2e}")

                    self.joint_objective.barrier.mu = mu

                    k_opt, J_opt, info = fmin_l_bfgs_b(
                        func=self._objective_wrapper,
                        x0=x_current,
                        fprime=self._gradient_wrapper,
                        bounds=bounds,
                        m=self.options.m,
                        factr=self.options.factr,
                        pgtol=self.options.pgtol,
                        maxiter=self.options.max_iter // self.options.continuation_steps,
                        maxfun=self.options.max_fun_eval // self.options.continuation_steps,
                        iprint=0
                    )

                    x_current = k_opt
                    n_iter_total += info['nit']
                    mu = max(mu * self.options.barrier_decrease_factor,
                             self.options.final_barrier_mu)
            else:
                k_opt, J_opt, info = fmin_l_bfgs_b(
                    func=self._objective_wrapper,
                    x0=x_current,
                    fprime=self._gradient_wrapper,
                    bounds=bounds,
                    m=self.options.m,
                    factr=self.options.factr,
                    pgtol=self.options.pgtol,
                    maxiter=self.options.max_iter,
                    maxfun=self.options.max_fun_eval,
                    iprint=0
                )
                n_iter_total = info['nit']

            converged = info['warnflag'] == 0
            message = self._get_lbfgs_message(info['warnflag'])

        finally:
            if self._progress_bar is not None:
                self._progress_bar.close()

        k_func = Function(self.V_k)
        k_func.vector()[:] = k_opt

        result = OptimizationResult(
            k_opt=k_opt,
            k_function=k_func,
            J_opt=J_opt,
            J_history=self.J_history.copy(),
            grad_norm_history=self.grad_norm_history.copy(),
            n_iter=n_iter_total,
            converged=converged,
            message=message
        )

        return result

    def optimize(self, k0: Optional[Union[np.ndarray, float, Function]] = None,
                 T0_guess: Optional[Union[np.ndarray, float, Function]] = None,
                 T0_true: Optional[Function] = None) -> OptimizationResult:
        """
        Run optimization, using two-phase if enabled.

        Parameters
        ----------
        k0 : np.ndarray, float, or Function, optional
            Initial guess for k
        T0_guess : np.ndarray, float, or Function, optional
            Initial guess for T0 (joint inversion)
        T0_true : Function, optional
            True T0 for diagnostics

        Returns
        -------
        OptimizationResult or JointOptimizationResult
        """
        if self.options.use_two_phase and self.estimate_T0:
            return self.optimize_two_phase(k0, T0_guess, T0_true)

        if self.estimate_T0:
            initial_params = self.joint_objective.get_initial_params(k0, T0_guess)
        else:
            if k0 is None:
                initial_params = np.ones(self.V_k.dim()) * 10.0
            elif isinstance(k0, (int, float)):
                initial_params = np.ones(self.V_k.dim()) * k0
            elif isinstance(k0, Function):
                initial_params = k0.vector().get_local()
            else:
                initial_params = np.asarray(k0)

            if hasattr(self.joint_objective, '_enforce_bounds'):
                initial_params = self.joint_objective._enforce_bounds(
                    np.concatenate([initial_params, np.zeros(self.joint_objective.T0_dim)])
                )[:self.joint_objective.k_dim]

        result = self._optimize_internal(initial_params, is_joint=self.estimate_T0)

        if self.estimate_T0 and len(result.k_opt) > self.joint_objective.k_dim:
            k_dim = self.joint_objective.k_dim
            full_params = result.k_opt

            if self.joint_objective.use_scaling:
                full_params = self.joint_objective.scaler.unscale_vector(
                    full_params, k_dim)

            k_func = Function(self.V_k)
            k_func.vector()[:] = full_params[:k_dim]

            T0_func = Function(self.T0_space)
            T0_func.vector()[:] = full_params[k_dim:]

            result = JointOptimizationResult(
                k_opt=full_params[:k_dim],
                k_function=k_func,
                T0_opt=full_params[k_dim:],
                T0_function=T0_func,
                J_opt=result.J_opt,
                J_history=result.J_history,
                grad_norm_history=result.grad_norm_history,
                n_iter=result.n_iter,
                converged=result.converged,
                message=result.message
            )

            self._print_joint_summary(result, T0_true)

        return result

    def _print_joint_summary(self, result: JointOptimizationResult,
                              T0_true: Optional[Function] = None):
        """Print joint optimization summary."""
        self._print_result_summary(result)

        if result.T0_opt is not None:
            print(f"Initial temperature estimation:")
            print(f"  T0 range: [{result.T0_opt.min():.2f}, {result.T0_opt.max():.2f}] K")
            print(f"  T0 mean: {result.T0_opt.mean():.2f} K")

            if T0_true is not None:
                T0_true_vec = T0_true.vector().get_local()
                error = np.linalg.norm(result.T0_opt - T0_true_vec) / np.linalg.norm(T0_true_vec)
                print(f"  T0 relative error: {error:.4%}")

        if hasattr(self.joint_objective, 'check_feasibility'):
            params = np.concatenate([result.k_opt, result.T0_opt]) \
                if result.T0_opt is not None else result.k_opt
            is_feasible, max_viol = self.joint_objective.check_feasibility(params)
            print(f"\nConstraint check:")
            print(f"  Feasible: {is_feasible}")
            print(f"  Max violation: {max_viol:.2e}")

        print("=" * 60 + "\n")

