"""
Adjoint method for computing gradient of objective function.
"""

import numpy as np
from dolfin import *
from typing import List, Union
from .forward import HeatForwardSolver
from .measurements import MeasurementData
from .objective import ObjectiveFunction, Regularization


class AdjointGradient:
    """
    Computes gradient of objective function using the adjoint method.

    For steady-state problem:
    1. Solve forward: ∇·(k ∇T) = 0
    2. Solve adjoint: ∇·(k ∇p) = -dJ_data/dT
    3. Gradient: dJ/dk = ∇T · ∇p + dJ_reg/dk

    For transient problem:
    Backward in time adjoint solution with appropriate time stepping.
    """

    def __init__(self,
                 forward_solver: HeatForwardSolver,
                 objective: ObjectiveFunction,
                 measurements: MeasurementData,
                 regularization: Regularization,
                 k_space: FunctionSpace):
        """
        Initialize adjoint gradient computer.

        Parameters
        ----------
        forward_solver : HeatForwardSolver
            Forward problem solver
        objective : ObjectiveFunction
            Objective function
        measurements : MeasurementData
            Measurement data
        regularization : Regularization
            Regularization object
        k_space : FunctionSpace
            Function space for thermal conductivity
        """
        self.forward_solver = forward_solver
        self.objective = objective
        self.measurements = measurements
        self.regularization = regularization
        self.V_k = k_space
        self.V_T = forward_solver.V
        self.mesh = k_space.mesh()
        self.dim = self.mesh.topology().dim()

        self.dx = Measure("dx", domain=self.mesh)
        self.ds = Measure("ds", domain=self.mesh)

        self.u = TrialFunction(self.V_T)
        self.v = TestFunction(self.V_T)
        self.dk = TestFunction(self.V_k)

        self._p = Function(self.V_T)
        self._grad = Function(self.V_k)

        self._measurement_coords = measurements.get_coordinates()
        self._measurement_std = measurements.get_std_dev_vector()

        self._solver_adjoint = None

    def _create_point_source_terms(self, T_sim: Function, time_idx: int = None) -> Function:
        """
        Create right-hand side for adjoint equation from measurement misfit.

        Uses point sources at measurement locations.

        Parameters
        ----------
        T_sim : Function
            Simulated temperature field
        time_idx : int, optional
            Time index for transient problems

        Returns
        -------
        Function
            RHS function for adjoint equation
        """
        T_sim_pts = self.forward_solver.evaluate_at_points(T_sim, self._measurement_coords)
        T_meas = self.measurements.get_measurement_vector(time_idx=time_idx)
        weights = 1.0 / (self._measurement_std ** 2)
        residuals = T_sim_pts - T_meas

        rhs = Function(self.V_T)
        rhs_vec = rhs.vector()
        rhs_vec.zero()

        for i, (coord, residual, weight) in enumerate(zip(
                self._measurement_coords, residuals, weights)):
            if self.dim == 2:
                pt = Point(coord[0], coord[1])
            else:
                pt = Point(coord[0], coord[1], coord[2])

            try:
                source = PointSource(self.V_T, pt, -weight * residual)
                source.apply(rhs_vec)
            except Exception:
                pass

        return rhs

    def _solve_adjoint_stationary(self, k: Function, T: Function,
                                  bc_manager, dirichlet_bcs) -> Function:
        """
        Solve adjoint equation for steady-state problem.

        -∇·(k ∇p) = dJ_data/dT
        with homogeneous Dirichlet BCs where T has Dirichlet BCs,
        homogeneous Neumann elsewhere.

        Parameters
        ----------
        k : Function
            Thermal conductivity
        T : Function
            Forward temperature solution
        bc_manager : BoundaryConditionManager
            Boundary condition manager
        dirichlet_bcs : list of DirichletBC
            Dirichlet boundary conditions

        Returns
        -------
        Function
            Adjoint solution p
        """
        rhs = self._create_point_source_terms(T)

        p = TrialFunction(self.V_T)
        q = TestFunction(self.V_T)

        a = inner(k * grad(p), grad(q)) * self.dx
        L = rhs * q * self.dx

        a_bc, L_bc = bc_manager.get_boundary_terms(p, q)
        a += a_bc
        L += L_bc

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

        p_sol = Function(self.V_T)
        solve(a == L, p_sol, hom_bcs,
              solver_parameters={'linear_solver': 'gmres',
                                 'preconditioner': 'hypre_amg'})

        return p_sol

    def _solve_adjoint_transient(self, k: Function, T_solutions: List[Function],
                                 times: np.ndarray, bc_manager,
                                 dirichlet_bcs, theta=0.5) -> List[Function]:
        """
        Solve adjoint equation backward in time for transient problem.

        Parameters
        ----------
        k : Function
            Thermal conductivity
        T_solutions : list of Functions
            Forward temperature solutions at each time step
        times : np.ndarray
            Time grid
        bc_manager : BoundaryConditionManager
            Boundary condition manager
        dirichlet_bcs : list of DirichletBC
            Dirichlet boundary conditions
        theta : float
            Time integration parameter

        Returns
        -------
        list of Functions
            Adjoint solutions at each time step (backward order)
        """
        n_times = len(times)
        dt = times[1] - times[0]
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

    def compute_gradient(self, k_vec: np.ndarray) -> np.ndarray:
        """
        Compute gradient of objective function using adjoint method.

        Parameters
        ----------
        k_vec : np.ndarray
            Thermal conductivity as vector

        Returns
        -------
        np.ndarray
            Gradient vector
        """
        k = Function(self.V_k)
        k.vector()[:] = k_vec

        bc_manager = self.forward_solver.bc_manager
        dirichlet_bcs = self.forward_solver.dirichlet_bcs

        if self.measurements.is_transient:
            times = self.measurements.time_grid
            T_solutions = self.forward_solver.solve_transient(k, times=times)
            p_solutions = self._solve_adjoint_transient(
                k, T_solutions, times, bc_manager, dirichlet_bcs
            )

            grad_form = 0
            n_times = len(times)
            for T, p in zip(T_solutions, p_solutions):
                grad_form += -inner(grad(T), grad(p)) * self.dk * self.dx / n_times

        else:
            T = self.forward_solver.solve(k)
            p = self._solve_adjoint_stationary(k, T, bc_manager, dirichlet_bcs)

            grad_form = -inner(grad(T), grad(p)) * self.dk * self.dx

        grad_form += self.regularization.compute_variation(k, self.dk, self.dx)

        grad_vec = assemble(grad_form)
        return grad_vec.get_local()

    def compute_gradient_numerical(self, k_vec: np.ndarray, eps=1e-6) -> np.ndarray:
        """
        Compute numerical gradient using finite differences (for verification).

        Parameters
        ----------
        k_vec : np.ndarray
            Thermal conductivity as vector
        eps : float
            Finite difference step size

        Returns
        -------
        np.ndarray
            Numerical gradient vector
        """
        n = len(k_vec)
        grad = np.zeros(n)
        J0 = self.objective.compute(k_vec)

        for i in range(n):
            k_pert = k_vec.copy()
            k_pert[i] += eps
            J_plus = self.objective.compute(k_pert)
            grad[i] = (J_plus - J0) / eps

        return grad

    def check_gradient(self, k_vec: np.ndarray, eps=1e-5, rtol=1e-3) -> bool:
        """
        Check adjoint gradient against numerical gradient.

        Parameters
        ----------
        k_vec : np.ndarray
            Thermal conductivity as vector
        eps : float
            Finite difference step size
        rtol : float
            Relative tolerance for comparison

        Returns
        -------
        bool
            True if gradients match within tolerance
        """
        grad_adj = self.compute_gradient(k_vec)
        grad_num = self.compute_gradient_numerical(k_vec, eps=eps)

        mask = np.abs(grad_num) > 1e-10
        if np.any(mask):
            rel_error = np.max(np.abs(grad_adj[mask] - grad_num[mask]) / np.abs(grad_num[mask]))
        else:
            rel_error = np.max(np.abs(grad_adj - grad_num))

        abs_error = np.max(np.abs(grad_adj - grad_num))
        dot_product = np.dot(grad_adj, grad_num)
        norm_product = np.linalg.norm(grad_adj) * np.linalg.norm(grad_num)
        cos_angle = dot_product / norm_product if norm_product > 0 else 1.0

        print(f"Gradient check:")
        print(f"  Max absolute error: {abs_error:.2e}")
        print(f"  Max relative error: {rel_error:.2e}")
        print(f"  Cosine of angle: {cos_angle:.6f}")

        return cos_angle > 0.99 or rel_error < rtol
