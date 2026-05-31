"""
Forward heat conduction solver using FEniCS.
Supports both steady-state and transient problems.
"""

import numpy as np
from dolfin import *
from typing import Union, Optional, List
from .boundary import BoundaryConditionManager


class HeatForwardSolver:
    """
    Finite element solver for the heat conduction equation.

    Solves:
    - Steady-state: ∇·(k(x) ∇T) = 0
    - Transient: ρc_p ∂T/∂t - ∇·(k(x) ∇T) = 0

    with appropriate boundary conditions.
    """

    def __init__(self, V, bc_manager: BoundaryConditionManager,
                 rho=1.0, cp=1.0, f_source=0.0):
        """
        Initialize forward solver.

        Parameters
        ----------
        V : dolfin.FunctionSpace
            Function space for temperature
        bc_manager : BoundaryConditionManager
            Boundary condition manager
        rho : float, optional
            Mass density (for transient problems)
        cp : float, optional
            Specific heat capacity (for transient problems)
        f_source : float or Expression, optional
            Volumetric heat source
        """
        self.V = V
        self.mesh = V.mesh()
        self.bc_manager = bc_manager
        self.rho = Constant(rho)
        self.cp = Constant(cp)
        self.f = Constant(f_source) if isinstance(f_source, (int, float)) else f_source

        self.u = TrialFunction(V)
        self.v = TestFunction(V)

        self.dx = Measure("dx", domain=self.mesh)
        self.ds = Measure("ds", domain=self.mesh)

        self.dirichlet_bcs = bc_manager.setup_dirichlet_bcs(V)

        self._T_solution = Function(V)
        self._T_prev = Function(V)

        self._assemble_stationary = True
        self._stationary_matrices = None

    def set_heat_source(self, f):
        """Set volumetric heat source."""
        if isinstance(f, (int, float)):
            self.f = Constant(f)
        else:
            self.f = f
        self._assemble_stationary = True

    def _get_thermal_conductivity(self, k):
        """Convert k to FEniCS Function or Constant."""
        if isinstance(k, (int, float, np.floating, np.integer)):
            return Constant(k)
        elif isinstance(k, Function):
            return k
        elif hasattr(k, 'value') or hasattr(k, '_vector'):
            return k
        else:
            raise ValueError(f"Unsupported type for k: {type(k)}")

    def solve(self, k: Union[float, Function], T0: Optional[float] = 300.0) -> Function:
        """
        Solve steady-state heat conduction problem.

        Parameters
        ----------
        k : float or dolfin.Function
            Thermal conductivity distribution
        T0 : float, optional
            Initial guess for temperature

        Returns
        -------
        dolfin.Function
            Temperature field solution
        """
        k_fe = self._get_thermal_conductivity(k)

        a = inner(k_fe * grad(self.u), grad(self.v)) * self.dx
        L = self.f * self.v * self.dx

        a_bc, L_bc = self.bc_manager.get_boundary_terms(self.u, self.v)
        a += a_bc
        L += L_bc

        self._T_solution.vector()[:] = T0

        solve(a == L, self._T_solution, self.dirichlet_bcs,
              solver_parameters={'linear_solver': 'gmres',
                                 'preconditioner': 'hypre_amg'})

        return self._T_solution

    def solve_transient(self, k: Union[float, Function],
                        times: np.ndarray,
                        T_initial: Union[float, Function] = 300.0,
                        theta: float = 0.5,
                        save_interval: int = 1) -> List[Function]:
        """
        Solve transient heat conduction problem using theta-method.

        Parameters
        ----------
        k : float or dolfin.Function
            Thermal conductivity distribution
        times : np.ndarray
            Time points for solution
        T_initial : float or Function, optional
            Initial temperature distribution
        theta : float, optional
            Time integration parameter (0=forward Euler, 0.5=Crank-Nicolson, 1=backward Euler)
        save_interval : int, optional
            Save solution every N time steps

        Returns
        -------
        list of dolfin.Function
            Temperature field at each saved time step
        """
        k_fe = self._get_thermal_conductivity(k)

        if isinstance(T_initial, (int, float)):
            self._T_prev.vector()[:] = T_initial
        else:
            self._T_prev.assign(T_initial)

        solutions = [self._T_prev.copy(deepcopy=True)]

        dt = times[1] - times[0] if len(times) > 1 else 1.0
        dt_const = Constant(dt)

        u_theta = theta * self.u + (1 - theta) * self._T_prev
        du_dt = (self.u - self._T_prev) / dt_const

        F = (self.rho * self.cp * du_dt * self.v * self.dx
             + inner(k_fe * grad(u_theta), grad(self.v)) * self.dx
             - self.f * self.v * self.dx)

        a_bc, L_bc = self.bc_manager.get_boundary_terms(self.u, self.v)
        a_bc_prev, L_bc_prev = self.bc_manager.get_boundary_terms(self._T_prev, self.v)
        F += theta * (a_bc - L_bc) + (1 - theta) * (a_bc_prev - L_bc_prev)

        a = lhs(F)
        L = rhs(F)

        A = assemble(a)
        for bc in self.dirichlet_bcs:
            bc.apply(A)

        solver = LUSolver(A) if len(self.dirichlet_bcs) > 0 else KrylovSolver('gmres', 'hypre_amg')
        solver.parameters['absolute_tolerance'] = 1e-10
        solver.parameters['relative_tolerance'] = 1e-10

        for i in range(1, len(times)):
            b = assemble(L)
            for bc in self.dirichlet_bcs:
                bc.apply(b)

            solver.solve(self._T_solution.vector(), b)
            self._T_prev.assign(self._T_solution)

            if i % save_interval == 0 or i == len(times) - 1:
                solutions.append(self._T_solution.copy(deepcopy=True))

        return solutions

    def get_solution(self):
        """Get the current solution."""
        return self._T_solution

    def evaluate_at_points(self, T: Function, points: np.ndarray) -> np.ndarray:
        """
        Evaluate temperature field at given points.

        Parameters
        ----------
        T : dolfin.Function
            Temperature field
        points : np.ndarray
            Array of point coordinates (N x 2 or N x 3)

        Returns
        -------
        np.ndarray
            Temperature values at each point
        """
        values = np.zeros(len(points))
        dim = self.mesh.topology().dim()

        for i, pt in enumerate(points):
            try:
                if dim == 2:
                    values[i] = T(Point(pt[0], pt[1]))
                else:
                    values[i] = T(Point(pt[0], pt[1], pt[2]))
            except Exception:
                tree = self.mesh.bounding_box_tree()
                if dim == 2:
                    p = Point(pt[0], pt[1])
                else:
                    p = Point(pt[0], pt[1], pt[2])
                cell_id = tree.compute_first_entity_collision(p)
                if cell_id < self.mesh.num_cells():
                    values[i] = T(p)
                else:
                    values[i] = np.nan

        return values

    def save_solution(self, T: Function, filename: str, name: str = "temperature"):
        """
        Save temperature solution to XDMF file.

        Parameters
        ----------
        T : dolfin.Function
            Temperature field
        filename : str
            Output file path
        name : str, optional
            Name of the field in the output file
        """
        with XDMFFile(filename) as f:
            f.parameters["flush_output"] = True
            f.parameters["functions_share_mesh"] = True
            f.write_checkpoint(T, name, 0, XDMFFile.Encoding.HDF5, append=False)
        print(f"Solution saved to: {filename}")
