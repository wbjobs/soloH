"""
Reduced Order Modeling (ROM) for accelerating inverse heat conduction problems.
Uses Proper Orthogonal Decomposition (POD) / Reduced Basis (RB) method.
"""

from __future__ import annotations

import numpy as np
from dolfin import *
from typing import Union, Optional, List, Tuple, Callable, Dict, TYPE_CHECKING
from scipy import linalg
from .forward import HeatForwardSolver
from .measurements import MeasurementData
from .objective import ObjectiveFunction

if TYPE_CHECKING:
    from .regularization import Regularization


class PODBasisGenerator:
    """
    Generate Proper Orthogonal Decomposition (POD) basis functions
    for model order reduction.

    Uses the method of snapshots:
    1. Collect solution snapshots for different parameter values
    2. Compute correlation matrix
    3. Solve eigenvalue problem
    4. Select dominant modes based on energy criterion
    """

    def __init__(self, V: FunctionSpace):
        """
        Initialize POD basis generator.

        Parameters
        ----------
        V : FunctionSpace
            Full-order function space
        """
        self.V = V
        self.n_dofs = V.dim()
        self.snapshots = []
        self.basis_functions = []
        self.basis_vectors = None
        self.singular_values = None
        self.energy_captured = None
        self.n_basis = 0

    def add_snapshot(self, solution: Union[Function, np.ndarray]):
        """
        Add a solution snapshot.

        Parameters
        ----------
        solution : Function or np.ndarray
            Solution field or its vector representation
        """
        if hasattr(solution, 'vector') and callable(solution.vector):
            vec = solution.vector().get_local()
        else:
            vec = np.asarray(solution)

        if len(vec) != self.n_dofs:
            raise ValueError(f"Snapshot dimension {len(vec)} does not match "
                           f"function space dimension {self.n_dofs}")

        self.snapshots.append(vec)

    def add_snapshots(self, solutions: List[Union[Function, np.ndarray]]):
        """Add multiple snapshots."""
        for sol in solutions:
            self.add_snapshot(sol)

    def generate_parameter_snapshots(self, forward_solver: HeatForwardSolver,
                                     k_values: List[Union[float, np.ndarray, Function]],
                                     transient: bool = False,
                                     times: Optional[np.ndarray] = None) -> int:
        """
        Generate snapshots by solving forward problem for multiple k values.

        Parameters
        ----------
        forward_solver : HeatForwardSolver
            Forward problem solver
        k_values : list
            List of thermal conductivity values/fields
        transient : bool, optional
            Whether to solve transient problem
        times : np.ndarray, optional
            Time points for transient problems

        Returns
        -------
        int
            Number of snapshots added
        """
        n_added = 0
        for k_val in k_values:
            if isinstance(k_val, (int, float)):
                k = Function(self.V)
                k.vector()[:] = k_val
            elif isinstance(k_val, np.ndarray):
                k = Function(self.V)
                k.vector()[:] = k_val
            else:
                k = k_val

            if transient and times is not None:
                solutions = forward_solver.solve_transient(k, times=times)
                for sol in solutions:
                    self.add_snapshot(sol)
                    n_added += 1
            else:
                solution = forward_solver.solve(k)
                self.add_snapshot(solution)
                n_added += 1

        return n_added

    def compute_basis(self, n_basis: Optional[int] = None,
                      energy_threshold: float = 0.99,
                      method: str = 'svd') -> Tuple[List[Function], np.ndarray, np.ndarray]:
        """
        Compute POD basis from snapshots using SVD.

        Parameters
        ----------
        n_basis : int, optional
            Number of basis functions to keep (if None, use energy_threshold)
        energy_threshold : float, optional
            Fraction of energy to capture (0.99 = 99%)
        method : str, optional
            Method for computing basis: 'svd' or 'correlation'

        Returns
        -------
        tuple
            (basis_functions, singular_values, energy_captured)
        """
        if len(self.snapshots) == 0:
            raise ValueError("No snapshots available. Add snapshots first.")

        S = np.array(self.snapshots).T

        if method == 'svd':
            U, s, Vh = linalg.svd(S, full_matrices=False)
            singular_values = s
            energy_total = np.sum(singular_values**2)
            energy_captured = np.cumsum(singular_values**2) / energy_total

            if n_basis is None:
                n_basis = np.argmax(energy_captured >= energy_threshold) + 1

            n_basis = min(n_basis, len(singular_values))
            self.n_basis = n_basis

            self.basis_vectors = U[:, :n_basis]
            self.singular_values = singular_values[:n_basis]
            self.energy_captured = energy_captured

        elif method == 'correlation':
            C = S.T @ S
            eigvals, eigvecs = linalg.eigh(C)
            idx = np.argsort(eigvals)[::-1]
            eigvals = eigvals[idx]
            eigvecs = eigvecs[:, idx]

            singular_values = np.sqrt(np.maximum(eigvals, 0))
            energy_total = np.sum(singular_values**2)
            energy_captured = np.cumsum(singular_values**2) / energy_total

            if n_basis is None:
                n_basis = np.argmax(energy_captured >= energy_threshold) + 1

            n_basis = min(n_basis, len(singular_values))
            self.n_basis = n_basis

            Phi = S @ eigvecs[:, :n_basis]
            for i in range(n_basis):
                norm = np.linalg.norm(Phi[:, i])
                if norm > 0:
                    Phi[:, i] /= norm

            self.basis_vectors = Phi
            self.singular_values = singular_values[:n_basis]
            self.energy_captured = energy_captured
        else:
            raise ValueError(f"Unknown method: {method}. Use 'svd' or 'correlation'.")

        self.basis_functions = []
        for i in range(self.n_basis):
            phi = Function(self.V)
            phi.vector()[:] = self.basis_vectors[:, i]
            self.basis_functions.append(phi)

        return self.basis_functions, self.singular_values, self.energy_captured

    def project_to_basis(self, solution: Union[Function, np.ndarray]) -> np.ndarray:
        """
        Project a solution onto the reduced basis.

        Parameters
        ----------
        solution : Function or np.ndarray
            Full-order solution

        Returns
        -------
        np.ndarray
            Reduced coefficients (length n_basis)
        """
        if self.basis_vectors is None:
            raise ValueError("Basis not computed yet. Call compute_basis() first.")

        if isinstance(solution, Function):
            vec = solution.vector().get_local()
        else:
            vec = np.asarray(solution)

        coeffs = self.basis_vectors.T @ vec
        return coeffs

    def reconstruct_from_basis(self, coefficients: np.ndarray) -> Function:
        """
        Reconstruct full-order solution from reduced coefficients.

        Parameters
        ----------
        coefficients : np.ndarray
            Reduced basis coefficients

        Returns
        -------
        Function
            Reconstructed full-order solution
        """
        if self.basis_vectors is None:
            raise ValueError("Basis not computed yet. Call compute_basis() first.")

        full_vec = self.basis_vectors @ coefficients
        solution = Function(self.V)
        solution.vector()[:] = full_vec
        return solution

    def save_basis(self, filename: str):
        """Save basis to NPZ file."""
        np.savez(filename,
                 basis_vectors=self.basis_vectors,
                 singular_values=self.singular_values,
                 energy_captured=self.energy_captured,
                 n_basis=self.n_basis,
                 n_dofs=self.n_dofs)

    def load_basis(self, filename: str):
        """Load basis from NPZ file."""
        data = np.load(filename)
        self.basis_vectors = data['basis_vectors']
        self.singular_values = data['singular_values']
        self.energy_captured = data['energy_captured']
        self.n_basis = int(data['n_basis'])
        self.n_dofs = int(data['n_dofs'])

        self.basis_functions = []
        for i in range(self.n_basis):
            phi = Function(self.V)
            phi.vector()[:] = self.basis_vectors[:, i]
            self.basis_functions.append(phi)


class ReducedOrderSolver:
    """
    Reduced order solver using Galerkin projection on POD basis.

    For the heat equation:
    Full order: M du/dt + A u = F
    Reduced: M_r du_r/dt + A_r u_r = F_r
    where:
    - M_r = Φ^T M Φ (reduced mass matrix)
    - A_r = Φ^T A Φ (reduced stiffness matrix)
    - F_r = Φ^T F (reduced load vector)
    - Φ = basis matrix
    """

    def __init__(self, forward_solver: HeatForwardSolver,
                 basis_vectors: np.ndarray):
        """
        Initialize reduced order solver.

        Parameters
        ----------
        forward_solver : HeatForwardSolver
            Full-order forward solver
        basis_vectors : np.ndarray
            POD basis vectors (shape: n_dofs x n_basis)
        """
        self.forward_solver = forward_solver
        self.V = forward_solver.V
        self.basis_vectors = basis_vectors
        self.n_dofs, self.n_basis = basis_vectors.shape

        self.M = None
        self.A = None
        self.F = None

        self.M_r = None
        self.A_r = None
        self.F_r = None

    def assemble_full_order(self, k: Function):
        """
        Assemble full-order matrices for given k.

        Parameters
        ----------
        k : Function
            Thermal conductivity field
        """
        V = self.V
        u = TrialFunction(V)
        v = TestFunction(V)
        dx = self.forward_solver.dx

        rho_cp = self.forward_solver.rho * self.forward_solver.cp
        f = self.forward_solver.f

        self.M = assemble(rho_cp * u * v * dx)
        self.A = assemble(inner(k * grad(u), grad(v)) * dx)
        self.F = assemble(f * v * dx)

    def assemble_reduced(self):
        """Assemble reduced-order matrices via Galerkin projection."""
        if self.M is None or self.A is None or self.F is None:
            raise ValueError("Full-order matrices not assembled. "
                           "Call assemble_full_order(k) first.")

        self.M_r = self.basis_vectors.T @ self.M.array() @ self.basis_vectors
        self.A_r = self.basis_vectors.T @ self.A.array() @ self.basis_vectors
        self.F_r = self.basis_vectors.T @ self.F.get_local()

    def solve_stationary(self, k: Function, dirichlet_bcs: Optional[List] = None) -> np.ndarray:
        """
        Solve stationary problem using reduced order model.

        Parameters
        ----------
        k : Function
            Thermal conductivity
        dirichlet_bcs : list, optional
            Dirichlet boundary conditions

        Returns
        -------
        np.ndarray
            Reduced solution coefficients
        """
        self.assemble_full_order(k)

        if dirichlet_bcs is not None and len(dirichlet_bcs) > 0:
            V = self.V
            u_dummy = Function(V)
            for bc in dirichlet_bcs:
                try:
                    bc.apply(self.A, self.F)
                except Exception:
                    pass

        self.assemble_reduced()

        A_r = self.A_r
        F_r = self.F_r

        if dirichlet_bcs is not None and len(dirichlet_bcs) > 0:
            u_full = Function(V)
            for bc in dirichlet_bcs:
                try:
                    bc.apply(u_full.vector())
                except Exception:
                    pass
            coeffs_diri = self.basis_vectors.T @ u_full.vector().get_local()
            for i in range(self.n_basis):
                if np.abs(A_r[i, i]) > 1e-10:
                    pass
                else:
                    A_r[i, :] = 0
                    A_r[i, i] = 1
                    F_r[i] = coeffs_diri[i]

        u_r = np.linalg.solve(A_r, F_r)
        return u_r

    def solve_transient(self, k: Function, T0: Function,
                        times: np.ndarray,
                        theta: float = 0.5,
                        dirichlet_bcs: Optional[List] = None) -> List[np.ndarray]:
        """
        Solve transient problem using reduced order model (theta-method).

        Parameters
        ----------
        k : Function
            Thermal conductivity
        T0 : Function
            Initial condition
        times : np.ndarray
            Time points
        theta : float, optional
            Time discretization parameter (0.5 = Crank-Nicolson)
        dirichlet_bcs : list, optional
            Dirichlet boundary conditions

        Returns
        -------
        list of np.ndarray
            Reduced solution coefficients at each time step
        """
        self.assemble_full_order(k)
        self.assemble_reduced()

        n_times = len(times)
        dt = times[1] - times[0] if n_times > 1 else 1.0

        coeffs_prev = self.basis_vectors.T @ T0.vector().get_local()

        M_r = self.M_r
        A_r = self.A_r
        F_r = self.F_r

        solutions_r = [coeffs_prev.copy()]

        for i in range(1, n_times):
            A_sys = M_r / dt + theta * A_r
            b = (M_r / dt - (1 - theta) * A_r) @ coeffs_prev + F_r

            if dirichlet_bcs is not None and len(dirichlet_bcs) > 0:
                u_full = Function(self.V)
                for bc in dirichlet_bcs:
                    try:
                        bc.apply(u_full.vector(), t=times[i])
                    except Exception:
                        pass
                coeffs_diri = self.basis_vectors.T @ u_full.vector().get_local()
                for j in range(self.n_basis):
                    if np.abs(A_sys[j, j]) > 1e-10:
                        pass
                    else:
                        A_sys[j, :] = 0
                        A_sys[j, j] = 1
                        b[j] = coeffs_diri[j]

            coeffs_current = np.linalg.solve(A_sys, b)
            solutions_r.append(coeffs_current)
            coeffs_prev = coeffs_current

        return solutions_r

    def reconstruct(self, u_r: np.ndarray) -> Function:
        """Reconstruct full-order solution from reduced coefficients."""
        full_vec = self.basis_vectors @ u_r
        solution = Function(self.V)
        solution.vector()[:] = full_vec
        return solution

    def reconstruct_list(self, u_r_list: List[np.ndarray]) -> List[Function]:
        """Reconstruct multiple time steps."""
        return [self.reconstruct(u_r) for u_r in u_r_list]


class ROMObjectiveFunction(ObjectiveFunction):
    """
    Objective function using Reduced Order Model for fast evaluation.

    The objective uses the ROM for forward solves during optimization,
    optionally switching to full-order for final verification.

    Can optionally use an error estimator for adaptive basis enrichment.
    """

    def __init__(self,
                 forward_solver: HeatForwardSolver,
                 measurements: MeasurementData,
                 regularization: Regularization,
                 k_space: FunctionSpace,
                 basis_vectors: np.ndarray,
                 use_error_estimation: bool = True,
                 full_order_check_interval: int = 10,
                 k_ref: Optional[Union[float, Function]] = None):
        """
        Initialize ROM-based objective function.

        Parameters
        ----------
        forward_solver : HeatForwardSolver
            Full-order forward solver
        measurements : MeasurementData
            Measurement data
        regularization : Regularization
            Regularization term
        k_space : FunctionSpace
            Function space for k
        basis_vectors : np.ndarray
            POD basis vectors (n_dofs x n_basis)
        use_error_estimation : bool, optional
            Whether to use error estimation for adaptive enrichment
        full_order_check_interval : int, optional
            How often to check with full-order model
        k_ref : float or Function, optional
            Reference conductivity
        """
        super().__init__(
            forward_solver=forward_solver,
            measurements=measurements,
            regularization=regularization,
            k_space=k_space
        )

        self.rom_solver = ReducedOrderSolver(forward_solver, basis_vectors)
        self.basis_vectors = basis_vectors
        self.n_basis = basis_vectors.shape[1]

        self.use_error_estimation = use_error_estimation
        self.full_order_check_interval = full_order_check_interval
        self.eval_count = 0
        self.k_ref = k_ref

        self.rom_solutions = []
        self.full_order_solutions = []
        self.errors = []

    def compute_value(self, k: Function) -> float:
        """
        Compute objective value using ROM for forward solve.

        Parameters
        ----------
        k : Function
            Thermal conductivity

        Returns
        -------
        float
            Objective value
        """
        self.eval_count += 1

        if self.measurements.is_transient:
            T0 = self._last_T0 if hasattr(self, '_last_T0') and self._last_T0 is not None else k
            try:
                T0_func = self._last_T0 if hasattr(self, '_last_T0') else None
                if T0_func is None:
                    T0_func = Function(self.V_T)
                    T0_func.vector()[:] = 300.0

                u_r_list = self.rom_solver.solve_transient(
                    k, T0_func, self.measurements.time_grid,
                    dirichlet_bcs=self.forward_solver.dirichlet_bcs
                )
                T_list = self.rom_solver.reconstruct_list(u_r_list)
            except Exception as e:
                T_list = self.forward_solver.solve_transient(
                    k, times=self.measurements.time_grid
                )
        else:
            try:
                u_r = self.rom_solver.solve_stationary(
                    k, dirichlet_bcs=self.forward_solver.dirichlet_bcs
                )
                T = self.rom_solver.reconstruct(u_r)
            except Exception as e:
                T = self.forward_solver.solve(k)
            T_list = [T]

        if (self.eval_count % self.full_order_check_interval == 0) and self.use_error_estimation:
            try:
                self._estimate_error(k, T_list)
            except Exception:
                pass

        J_data = self._compute_data_misfit(T_list)
        J_reg = self.regularization.compute_value(k, self.dx)
        J_total = J_data + J_reg

        return J_total

    def _estimate_error(self, k: Function, T_rom: List[Function]) -> float:
        """
        Estimate ROM error by comparing with full-order solution.

        Parameters
        ----------
        k : Function
            Thermal conductivity
        T_rom : list of Function
            ROM solutions

        Returns
        -------
        float
            Estimated relative error
        """
        if self.measurements.is_transient:
            T0 = self._last_T0 if hasattr(self, '_last_T0') else None
            if T0 is None:
                T0 = Function(self.V_T)
                T0.vector()[:] = 300.0
            T_full_list = self.forward_solver.solve_transient(k, times=self.measurements.time_grid)
        else:
            T_full_list = [self.forward_solver.solve(k)]

        errors = []
        for t_rom, t_full in zip(T_rom, T_full_list):
            err = np.linalg.norm(t_rom.vector().get_local() - t_full.vector().get_local())
            norm_full = np.linalg.norm(t_full.vector().get_local())
            if norm_full > 0:
                errors.append(err / norm_full)
            else:
                errors.append(err)

        max_error = max(errors) if errors else 0.0
        self.errors.append(max_error)
        self.rom_solutions.append(T_rom)
        self.full_order_solutions.append(T_full_list)

        return max_error

    def suggest_basis_enrichment(self, max_error_threshold: float = 0.05) -> bool:
        """
        Check if basis enrichment is needed based on error estimates.

        Parameters
        ----------
        max_error_threshold : float, optional
            Maximum allowed relative error

        Returns
        -------
        bool
            True if enrichment suggested
        """
        if len(self.errors) == 0:
            return False
        return self.errors[-1] > max_error_threshold
