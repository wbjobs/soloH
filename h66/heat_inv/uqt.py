"""
Uncertainty Quantification using Laplace approximation.
"""

import numpy as np
from dolfin import *
from scipy.sparse import csr_matrix, lil_matrix
from scipy.sparse.linalg import eigsh
from typing import Optional, Tuple
import time

from .forward import HeatForwardSolver
from .measurements import MeasurementData
from .adjoint import AdjointGradient
from .objective import ObjectiveFunction, Regularization


class UncertaintyQuantifier:
    """
    Uncertainty quantification for inverse heat conduction problem.

    Implements Laplace approximation (Gaussian approximation of posterior)
    by computing the Hessian of the objective function at the optimum.

    The posterior covariance is:
        Cov = H^{-1}

    where H is the Hessian of the negative log posterior (objective function).
    """

    def __init__(self,
                 objective: ObjectiveFunction,
                 gradient: AdjointGradient,
                 forward_solver: HeatForwardSolver,
                 measurements: MeasurementData,
                 regularization: Regularization,
                 k_space: FunctionSpace):
        """
        Initialize uncertainty quantifier.

        Parameters
        ----------
        objective : ObjectiveFunction
            Objective function
        gradient : AdjointGradient
            Gradient computer
        forward_solver : HeatForwardSolver
            Forward problem solver
        measurements : MeasurementData
            Measurement data
        regularization : Regularization
            Regularization object
        k_space : FunctionSpace
            Function space for thermal conductivity
        """
        self.objective = objective
        self.gradient = gradient
        self.forward_solver = forward_solver
        self.measurements = measurements
        self.regularization = regularization
        self.V_k = k_space
        self.V_T = forward_solver.V
        self.mesh = k_space.mesh()
        self.dim = self.mesh.topology().dim()

        self.dx = Measure("dx", domain=self.mesh)

        self._dk = TrialFunction(self.V_k)
        self._dq = TestFunction(self.V_k)

        self._hessian = None
        self._covariance = None
        self._std_dev = None
        self._eigenvalues = None
        self._eigenvectors = None

    def compute_hessian(self, k_opt: np.ndarray, method: str = "gauss_newton") -> csr_matrix:
        """
        Compute Hessian matrix of objective function at optimum.

        Parameters
        ----------
        k_opt : np.ndarray
            Optimal thermal conductivity vector
        method : str
            'gauss_newton' for approximate Hessian (J^T J + Hessian(reg))
            'full' for full Hessian via second adjoints (more expensive)

        Returns
        -------
        scipy.sparse.csr_matrix
            Hessian matrix
        """
        print(f"Computing Hessian using {method} method...")
        t_start = time.time()

        n = self.V_k.dim()

        if method == "gauss_newton":
            H = self._compute_gauss_newton_hessian(k_opt)
        else:
            raise NotImplementedError(f"Method {method} not implemented")

        print(f"Hessian computed in {time.time() - t_start:.2f}s")
        print(f"Hessian shape: {H.shape}")
        print(f"Hessian sparsity: {H.nnz / (n * n) * 100:.2f}%")

        self._hessian = H
        return H

    def _compute_gauss_newton_hessian(self, k_opt: np.ndarray) -> csr_matrix:
        """
        Compute Gauss-Newton approximation of Hessian.

        H ≈ J_data' * J_data + H_reg

        where J_data is the sensitivity of measurements to parameters.

        Uses:
        dT_i/dk = ∫ ∇T · ∇(p_i) * dk dx
        where p_i solves adjoint for each measurement point i.
        """
        k = Function(self.V_k)
        k.vector()[:] = k_opt

        n = self.V_k.dim()
        m = self.measurements.num_points

        bc_manager = self.forward_solver.bc_manager
        dirichlet_bcs = self.forward_solver.dirichlet_bcs

        if self.measurements.is_transient:
            times = self.measurements.time_grid
            T_solutions = self.forward_solver.solve_transient(k, times=times)
            n_times = len(times)

            print(f"Computing sensitivities for {m} points x {n_times} time steps...")

            JTJ = lil_matrix((n, n))
            for pt_idx in range(m):
                sigma = self.measurements.points[pt_idx].std_dev
                weight = 1.0 / (sigma ** 2)

                coord = self.measurements.points[pt_idx].as_array()

                for t_idx in range(n_times):
                    T = T_solutions[t_idx]
                    rhs = Function(self.V_T)
                    rhs.vector().zero()

                    if self.dim == 2:
                        pt = Point(coord[0], coord[1])
                    else:
                        pt = Point(coord[0], coord[1], coord[2])

                    try:
                        source = PointSource(self.V_T, pt, 1.0)
                        source.apply(rhs.vector())
                    except Exception:
                        continue

                    p = TrialFunction(self.V_T)
                    q = TestFunction(self.V_T)

                    a = inner(k * grad(p), grad(q)) * self.dx
                    L = rhs * q * self.dx

                    hom_bcs = []
                    for bc in dirichlet_bcs:
                        hom_bc = DirichletBC(bc.function_space(), Constant(0),
                                             bc.domain_args[0], bc.domain_args[1])
                        hom_bcs.append(hom_bc)

                    p_sol = Function(self.V_T)
                    solve(a == L, p_sol, hom_bcs,
                          solver_parameters={'linear_solver': 'gmres',
                                             'preconditioner': 'hypre_amg'})

                    dT_dk_form = -inner(grad(T), grad(p_sol)) * self._dk * self.dx / n_times
                    dT_dk_vec = assemble(dT_dk_form)
                    dT_dk = dT_dk_vec.get_local().reshape(-1, 1)

                    JTJ += weight * (dT_dk @ dT_dk.T)

        else:
            T = self.forward_solver.solve(k)

            print(f"Computing sensitivities for {m} points...")

            JTJ = lil_matrix((n, n))
            for pt_idx in range(m):
                sigma = self.measurements.points[pt_idx].std_dev
                weight = 1.0 / (sigma ** 2)

                coord = self.measurements.points[pt_idx].as_array()

                rhs = Function(self.V_T)
                rhs.vector().zero()

                if self.dim == 2:
                    pt = Point(coord[0], coord[1])
                else:
                    pt = Point(coord[0], coord[1], coord[2])

                try:
                    source = PointSource(self.V_T, pt, 1.0)
                    source.apply(rhs.vector())
                except Exception:
                    continue

                p = TrialFunction(self.V_T)
                q = TestFunction(self.V_T)

                a = inner(k * grad(p), grad(q)) * self.dx
                L = rhs * q * self.dx

                hom_bcs = []
                for bc in dirichlet_bcs:
                    hom_bc = DirichletBC(bc.function_space(), Constant(0),
                                         bc.domain_args[0], bc.domain_args[1])
                    hom_bcs.append(hom_bc)

                p_sol = Function(self.V_T)
                solve(a == L, p_sol, hom_bcs,
                      solver_parameters={'linear_solver': 'gmres',
                                         'preconditioner': 'hypre_amg'})

                dT_dk_form = -inner(grad(T), grad(p_sol)) * self._dk * self.dx
                dT_dk_vec = assemble(dT_dk_form)
                dT_dk = dT_dk_vec.get_local().reshape(-1, 1)

                JTJ += weight * (dT_dk @ dT_dk.T)

        H_reg = self._compute_regularization_hessian(k)

        H = JTJ.tocsr() + H_reg

        return H

    def _compute_regularization_hessian(self, k: Function) -> csr_matrix:
        """
        Compute Hessian of regularization term.

        Parameters
        ----------
        k : Function
            Thermal conductivity

        Returns
        -------
        scipy.sparse.csr_matrix
            Hessian of regularization term
        """
        if self.regularization.reg_type in ['tikhonov0', 'tikhonov1', 'tikhonov']:
            H_reg_form = (2 * self.regularization.alpha * inner(grad(self._dk), grad(self._dq)) * self.dx
                          + 2 * self.regularization.beta * self._dk * self._dq * self.dx)
            H_reg = assemble(H_reg_form)
            H_reg_mat = as_backend_type(H_reg).mat()
            return csr_matrix(H_reg_mat.getValuesCSR()[::-1], shape=H_reg_mat.size)
        elif self.regularization.reg_type == 'tv':
            eps = self.regularization._eps_tv
            grad_k = grad(k)
            norm_grad_k = sqrt(inner(grad_k, grad_k) + eps)

            P_ij = (delta_ij / norm_grad_k
                    - grad_k[i] * grad_k[j] / (norm_grad_k ** 3))

            H_reg_form = (self.regularization.alpha * P_ij * grad(self._dk)[i] * grad(self._dq)[j] * self.dx
                          + 2 * self.regularization.beta * self._dk * self._dq * self.dx)
            H_reg = assemble(H_reg_form)
            H_reg_mat = as_backend_type(H_reg).mat()
            return csr_matrix(H_reg_mat.getValuesCSR()[::-1], shape=H_reg_mat.size)

    def compute_std_dev(self, k_opt: np.ndarray) -> Function:
        """
        Compute standard deviation of thermal conductivity estimates.

        Parameters
        ----------
        k_opt : np.ndarray
            Optimal thermal conductivity vector

        Returns
        -------
        dolfin.Function
            Pointwise standard deviation
        """
        if self._hessian is None:
            self.compute_hessian(k_opt)

        print("Computing diagonal of covariance matrix...")
        t_start = time.time()

        n = self.V_k.dim()

        try:
            diag_cov = self._approximate_diagonal_covariance(self._hessian)
        except Exception as e:
            print(f"Warning: Hessian inversion failed, using diagonal approximation: {e}")
            diag_H = self._hessian.diagonal()
            diag_cov = 1.0 / np.maximum(diag_H, 1e-10)

        sigma_func = Function(self.V_k)
        sigma_func.vector()[:] = np.sqrt(np.maximum(diag_cov, 0))

        self._std_dev = sigma_func

        print(f"Standard deviation computed in {time.time() - t_start:.2f}s")
        print(f"Min sigma: {sigma_func.vector().min():.4e}")
        print(f"Max sigma: {sigma_func.vector().max():.4e}")
        print(f"Mean sigma: {sigma_func.vector().sum() / n:.4e}")

        return sigma_func

    def _approximate_diagonal_covariance(self, H: csr_matrix) -> np.ndarray:
        """
        Approximate diagonal of covariance matrix using Lanczos method
        or direct diagonal approximation.

        Uses the formula: diag(H^{-1}) ≈ 1 / diag(H) for diagonal approximation,
        or sparse LU for small problems.
        """
        n = H.shape[0]

        if n < 2000:
            from scipy.sparse.linalg import spsolve
            try:
                print("Using direct solve for diagonal estimation...")
                diag_cov = np.zeros(n)
                for i in range(n):
                    e = np.zeros(n)
                    e[i] = 1.0
                    diag_cov[i] = spsolve(H, e)[i]
                return diag_cov
            except Exception as e:
                print(f"Direct solve failed: {e}")

        print("Using diagonal approximation...")
        diag_H = H.diagonal()
        return 1.0 / np.maximum(diag_H, 1e-10)

    def compute_eigenspectrum(self, k_opt: np.ndarray, num_eigenvalues: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute eigenvalues and eigenvectors of the Hessian.

        Parameters
        ----------
        k_opt : np.ndarray
            Optimal thermal conductivity vector
        num_eigenvalues : int
            Number of eigenvalues to compute

        Returns
        -------
        tuple
            (eigenvalues, eigenvectors) - sorted descending
        """
        if self._hessian is None:
            self.compute_hessian(k_opt)

        print(f"Computing {num_eigenvalues} largest eigenvalues...")
        t_start = time.time()

        eigenvalues, eigenvectors = eigsh(
            self._hessian,
            k=num_eigenvalues,
            which='LM',
            maxiter=1000
        )

        idx = eigenvalues.argsort()[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        self._eigenvalues = eigenvalues
        self._eigenvectors = eigenvectors

        print(f"Eigenspectrum computed in {time.time() - t_start:.2f}s")
        print(f"Condition number estimate: {eigenvalues[0] / eigenvalues[-1]:.2e}")

        for i, lam in enumerate(eigenvalues):
            print(f"  λ_{i+1} = {lam:.4e}")

        return eigenvalues, eigenvectors

    def compute_confidence_interval(self, k_opt: np.ndarray, alpha: float = 0.95) -> Tuple[Function, Function]:
        """
        Compute pointwise confidence intervals.

        Parameters
        ----------
        k_opt : np.ndarray
            Optimal thermal conductivity
        alpha : float
            Confidence level (default 95%)

        Returns
        -------
        tuple
            (lower_bound, upper_bound) as FEniCS Functions
        """
        from scipy.stats import norm

        if self._std_dev is None:
            self.compute_std_dev(k_opt)

        z = norm.ppf((1 + alpha) / 2)

        k_opt_func = Function(self.V_k)
        k_opt_func.vector()[:] = k_opt

        lower = Function(self.V_k)
        upper = Function(self.V_k)
        lower.vector()[:] = k_opt - z * self._std_dev.vector().get_local()
        upper.vector()[:] = k_opt + z * self._std_dev.vector().get_local()

        print(f"{int(alpha * 100)}% confidence intervals computed")
        print(f"  z-score: {z:.4f}")

        return lower, upper

    def get_std_dev(self) -> Optional[Function]:
        """Get standard deviation function."""
        return self._std_dev

    def get_hessian(self) -> Optional[csr_matrix]:
        """Get Hessian matrix."""
        return self._hessian
