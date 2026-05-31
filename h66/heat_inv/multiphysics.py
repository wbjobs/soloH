"""
Multiphysics coupling for inverse heat conduction problems.
Supports thermoelectric and thermoelastic couplings.
"""

import numpy as np
from dolfin import *
from typing import Union, Optional, List, Tuple, Dict
from .boundary import BoundaryConditionManager
from .forward import HeatForwardSolver


class ThermoelectricSolver:
    """
    Coupled thermoelectric solver (Seebeck + Peltier + Thomson effects).

    Governing equations:
    1. Heat: ρc_p ∂T/∂t - ∇·(k ∇T) = T α J·∇V + J·J/σ
    2. Current: ∇·(σ ∇V + σ α ∇T) = 0

    where:
    - T: temperature
    - V: electric potential
    - k: thermal conductivity
    - σ: electrical conductivity
    - α: Seebeck coefficient
    - J: current density = -σ(∇V + α ∇T)
    """

    def __init__(self, V_T, V_V, bc_manager: BoundaryConditionManager,
                 rho=1.0, cp=1.0, sigma=1e5, alpha=1e-4):
        """
        Initialize thermoelectric solver.

        Parameters
        ----------
        V_T : FunctionSpace
            Function space for temperature
        V_V : FunctionSpace
            Function space for electric potential
        bc_manager : BoundaryConditionManager
            Boundary condition manager
        rho : float, optional
            Mass density
        cp : float, optional
            Specific heat capacity
        sigma : float, optional
            Electrical conductivity (S/m)
        alpha : float, optional
            Seebeck coefficient (V/K)
        """
        self.V_T = V_T
        self.V_V = V_V
        self.mesh = V_T.mesh()
        self.bc_manager = bc_manager
        self.rho = Constant(rho)
        self.cp = Constant(cp)
        self.sigma = Constant(sigma)
        self.alpha = Constant(alpha)

        self.u_T = TrialFunction(V_T)
        self.v_T = TestFunction(V_T)
        self.u_V = TrialFunction(V_V)
        self.v_V = TestFunction(V_V)

        self.dx = Measure("dx", domain=self.mesh)
        self.ds = Measure("ds", domain=self.mesh)

        self._T_solution = Function(V_T)
        self._V_solution = Function(V_V)

        self.dirichlet_bcs_T = bc_manager.setup_dirichlet_bcs(V_T, 'temperature')
        self.dirichlet_bcs_V = bc_manager.setup_dirichlet_bcs(V_V, 'potential')

    def solve(self, k: Function, T0: Optional[Function] = None,
              V0: Optional[Function] = None) -> Tuple[Function, Function]:
        """
        Solve coupled thermoelectric equations (steady-state).

        Parameters
        ----------
        k : Function
            Thermal conductivity field
        T0 : Function, optional
            Initial guess for temperature
        V0 : Function, optional
            Initial guess for electric potential

        Returns
        -------
        tuple
            (T_solution, V_solution)
        """
        if T0 is not None:
            self._T_solution.assign(T0)
        if V0 is not None:
            self._V_solution.assign(V0)

        T, V = self._T_solution, self._V_solution

        F_T = (inner(k * grad(T), grad(self.v_T))
               - T * self.alpha * inner(-self.sigma * (grad(V) + self.alpha * grad(T)),
                                         grad(self.v_T))
               - inner(-self.sigma * (grad(V) + self.alpha * grad(T)),
                       -self.sigma * (grad(V) + self.alpha * grad(T))) / self.sigma * self.v_T) * self.dx

        F_V = inner(self.sigma * (grad(V) + self.alpha * grad(T)), grad(self.v_V)) * self.dx

        J_T = derivative(F_T, T, self.u_T)
        J_V = derivative(F_V, V, self.u_V)

        problem_T = NonlinearVariationalProblem(F_T, T, self.dirichlet_bcs_T, J_T)
        solver_T = NonlinearVariationalSolver(problem_T)
        solver_T.solve()

        problem_V = NonlinearVariationalProblem(F_V, V, self.dirichlet_bcs_V, J_V)
        solver_V = NonlinearVariationalSolver(problem_V)
        solver_V.solve()

        return T, V

    def solve_linearized(self, k: Function, T: Function, V: Function) -> Tuple[Function, Function]:
        """
        Solve linearized thermoelectric equations (fixed-point iteration).

        Parameters
        ----------
        k : Function
            Thermal conductivity
        T : Function
            Current temperature (for linearization)
        V : Function
            Current potential (for linearization)

        Returns
        -------
        tuple
            (T_new, V_new)
        """
        J = -self.sigma * (grad(V) + self.alpha * grad(T))

        a_T = inner(k * grad(self.u_T), grad(self.v_T)) * self.dx
        L_T = (T * self.alpha * inner(J, grad(self.v_T))
               + inner(J, J) / self.sigma * self.v_T) * self.dx

        a_V = inner(self.sigma * grad(self.u_V), grad(self.v_V)) * self.dx
        L_V = -inner(self.sigma * self.alpha * grad(T), grad(self.v_V)) * self.dx

        T_new = Function(self.V_T)
        V_new = Function(self.V_V)

        solve(a_T == L_T, T_new, self.dirichlet_bcs_T)
        solve(a_V == L_V, V_new, self.dirichlet_bcs_V)

        return T_new, V_new

    def compute_current_density(self, T: Function, V: Function) -> Function:
        """Compute current density J = -σ(∇V + α ∇T)."""
        J_vec = -self.sigma * (grad(V) + self.alpha * grad(T))
        V_vec = VectorFunctionSpace(self.mesh, 'CG', 1)
        J_func = project(J_vec, V_vec)
        return J_func


class ThermoelasticSolver:
    """
    Coupled thermoelastic solver (thermal expansion + stress).

    Governing equations:
    1. Heat: ρc_p ∂T/∂t - ∇·(k ∇T) = 0
    2. Elasticity: ∇·σ = 0, σ = C : (ε - α_T ΔT I)

    where:
    - σ: Cauchy stress tensor
    - ε: strain tensor = 1/2(∇u + ∇u^T)
    - C: elasticity tensor
    - α_T: thermal expansion coefficient
    - ΔT: temperature change from reference T0
    - u: displacement field
    """

    def __init__(self, V_T, V_u, bc_manager: BoundaryConditionManager,
                 rho=1.0, cp=1.0, E=1e9, nu=0.3, alpha_T=1e-5, T_ref=293.0):
        """
        Initialize thermoelastic solver.

        Parameters
        ----------
        V_T : FunctionSpace
            Function space for temperature
        V_u : VectorFunctionSpace
            Function space for displacement
        bc_manager : BoundaryConditionManager
            Boundary condition manager
        rho : float, optional
            Mass density
        cp : float, optional
            Specific heat capacity
        E : float, optional
            Young's modulus (Pa)
        nu : float, optional
            Poisson's ratio
        alpha_T : float, optional
            Thermal expansion coefficient (1/K)
        T_ref : float, optional
            Reference temperature for thermal expansion (K)
        """
        self.V_T = V_T
        self.V_u = V_u
        self.mesh = V_T.mesh()
        self.dim = self.mesh.topology().dim()
        self.bc_manager = bc_manager
        self.rho = Constant(rho)
        self.cp = Constant(cp)
        self.E = Constant(E)
        self.nu = Constant(nu)
        self.alpha_T = Constant(alpha_T)
        self.T_ref = Constant(T_ref)

        self.mu = self.E / (2 * (1 + self.nu))
        self.lmbda = self.E * self.nu / ((1 + self.nu) * (1 - 2 * self.nu))

        self.u_T = TrialFunction(V_T)
        self.v_T = TestFunction(V_T)
        self.u_u = TrialFunction(V_u)
        self.v_u = TestFunction(V_u)

        self.dx = Measure("dx", domain=self.mesh)
        self.ds = Measure("ds", domain=self.mesh)

        self._T_solution = Function(V_T)
        self._u_solution = Function(V_u)

        self.dirichlet_bcs_T = bc_manager.setup_dirichlet_bcs(V_T, 'temperature')
        self.dirichlet_bcs_u = bc_manager.setup_dirichlet_bcs(V_u, 'displacement')

    def _strain(self, u):
        """Compute infinitesimal strain tensor ε = 1/2(∇u + ∇u^T)."""
        return sym(grad(u))

    def _stress(self, u, dT):
        """
        Compute Cauchy stress σ = C:(ε - α_T ΔT I).
        For isotropic linear elasticity:
        σ = 2μ ε + λ tr(ε) I - (3λ + 2μ) α_T ΔT I
        """
        eps = self._strain(u)
        sigma = 2 * self.mu * eps + self.lmbda * tr(eps) * Identity(self.dim)
        if self.dim == 2:
            dT_tensor = dT * Identity(2)
        else:
            dT_tensor = dT * Identity(3)
        sigma -= (3 * self.lmbda + 2 * self.mu) * self.alpha_T * dT_tensor
        return sigma

    def solve(self, k: Function, T0: Optional[Function] = None,
              u0: Optional[Function] = None) -> Tuple[Function, Function]:
        """
        Solve coupled thermoelastic equations (steady-state).

        Parameters
        ----------
        k : Function
            Thermal conductivity field
        T0 : Function, optional
            Initial guess for temperature
        u0 : Function, optional
            Initial guess for displacement

        Returns
        -------
        tuple
            (T_solution, u_solution)
        """
        if T0 is not None:
            self._T_solution.assign(T0)
        if u0 is not None:
            self._u_solution.assign(u0)

        T, u = self._T_solution, self._u_solution

        a_T = inner(k * grad(self.u_T), grad(self.v_T)) * self.dx
        L_T = Constant(0) * self.v_T * self.dx
        solve(a_T == L_T, T, self.dirichlet_bcs_T)

        dT = T - self.T_ref

        a_u = inner(self._stress(self.u_u, Constant(0)), self._strain(self.v_u)) * self.dx
        thermal_stress = (3 * self.lmbda + 2 * self.mu) * self.alpha_T * dT
        L_u = inner(thermal_stress * Identity(self.dim), self._strain(self.v_u)) * self.dx

        solve(a_u == L_u, u, self.dirichlet_bcs_u)

        return T, u

    def solve_stress(self, k: Function, T: Function) -> Function:
        """Solve elasticity for given temperature field."""
        dT = T - self.T_ref

        a_u = inner(self._stress(self.u_u, Constant(0)), self._strain(self.v_u)) * self.dx
        thermal_stress = (3 * self.lmbda + 2 * self.mu) * self.alpha_T * dT
        L_u = inner(thermal_stress * Identity(self.dim), self._strain(self.v_u)) * self.dx

        u = Function(self.V_u)
        solve(a_u == L_u, u, self.dirichlet_bcs_u)

        return u

    def compute_stress_tensor(self, T: Function, u: Function) -> Function:
        """Compute stress tensor field."""
        dT = T - self.T_ref
        sigma = self._stress(u, dT)

        if self.dim == 2:
            V_sigma = TensorFunctionSpace(self.mesh, 'CG', 1)
        else:
            V_sigma = TensorFunctionSpace(self.mesh, 'CG', 1, shape=(3, 3))

        sigma_func = project(sigma, V_sigma)
        return sigma_func

    def compute_von_mises(self, sigma_func: Function) -> Function:
        """Compute von Mises equivalent stress."""
        s_dev = sigma_func - (1.0/3.0) * tr(sigma_func) * Identity(self.dim)
        von_mises = sqrt(3.0/2.0 * inner(s_dev, s_dev))

        V_scalar = FunctionSpace(self.mesh, 'CG', 1)
        von_mises_func = project(von_mises, V_scalar)
        return von_mises_func


class MultiphysicsCoupling:
    """
    Interface for multiphysics coupling in inverse problems.
    Supports both thermoelectric and thermoelastic couplings.
    """

    COUPLING_TYPES = ['thermoelectric', 'thermoelastic']

    def __init__(self, coupling_type: str,
                 function_spaces: Dict[str, FunctionSpace],
                 bc_manager: BoundaryConditionManager,
                 **kwargs):
        """
        Initialize multiphysics coupling.

        Parameters
        ----------
        coupling_type : str
            Type of coupling: 'thermoelectric' or 'thermoelastic'
        function_spaces : dict
            Dictionary of function spaces with keys:
            - 'temperature': temperature space
            - 'potential': electric potential space (for thermoelectric)
            - 'displacement': displacement space (for thermoelastic)
        bc_manager : BoundaryConditionManager
            Boundary condition manager
        **kwargs
            Material properties passed to the specific solver
        """
        if coupling_type not in self.COUPLING_TYPES:
            raise ValueError(f"Unknown coupling type: {coupling_type}. "
                           f"Supported: {self.COUPLING_TYPES}")

        self.coupling_type = coupling_type
        self.function_spaces = function_spaces
        self.bc_manager = bc_manager

        if coupling_type == 'thermoelectric':
            self.solver = ThermoelectricSolver(
                V_T=function_spaces['temperature'],
                V_V=function_spaces['potential'],
                bc_manager=bc_manager,
                **kwargs
            )
            self.field_names = ['temperature', 'potential']
        else:
            self.solver = ThermoelasticSolver(
                V_T=function_spaces['temperature'],
                V_u=function_spaces['displacement'],
                bc_manager=bc_manager,
                **kwargs
            )
            self.field_names = ['temperature', 'displacement']

    def solve(self, k: Function, **init_guess) -> Dict[str, Function]:
        """
        Solve multiphysics problem.

        Parameters
        ----------
        k : Function
            Thermal conductivity field
        **init_guess
            Initial guess fields

        Returns
        -------
        dict
            Dictionary of solution fields with keys as field_names
        """
        if self.coupling_type == 'thermoelectric':
            T, V = self.solver.solve(
                k,
                T0=init_guess.get('temperature'),
                V0=init_guess.get('potential')
            )
            return {'temperature': T, 'potential': V}
        else:
            T, u = self.solver.solve(
                k,
                T0=init_guess.get('temperature'),
                u0=init_guess.get('displacement')
            )
            return {'temperature': T, 'displacement': u}

    def get_heat_solver(self) -> HeatForwardSolver:
        """Get a pure heat solver for decoupled solves."""
        return HeatForwardSolver(
            V=self.function_spaces['temperature'],
            bc_manager=self.bc_manager,
            rho=float(self.solver.rho),
            cp=float(self.solver.cp)
        )
