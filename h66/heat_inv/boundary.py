"""
Boundary condition handling for heat conduction problems.
"""

from dataclasses import dataclass, field
from typing import List, Union, Callable
import numpy as np
from dolfin import *


@dataclass
class BoundaryCondition:
    """
    Represents a boundary condition for the heat equation.

    Supported types:
    - 'dirichlet': Fixed temperature T = T_bc
    - 'neumann': Fixed heat flux q = q_bc (positive = outward)
    - 'robin': Convective heat flux q = h(T - T_ambient)
    """
    bc_type: str
    value: Union[float, Callable, Expression]
    boundary_marker: int = 1
    ambient_temperature: float = 298.15
    heat_transfer_coefficient: float = 10.0

    def __post_init__(self):
        if self.bc_type not in ['dirichlet', 'neumann', 'robin']:
            raise ValueError(f"Unknown boundary condition type: {self.bc_type}")

    def as_expression(self, degree=1):
        """Convert value to FEniCS Expression if needed."""
        if isinstance(self.value, (int, float)):
            return Constant(self.value)
        elif callable(self.value):
            return Expression(self.value, degree=degree)
        return self.value


class BoundaryConditionManager:
    """Manages multiple boundary conditions for a problem."""

    def __init__(self, mesh, boundaries=None):
        """
        Initialize boundary condition manager.

        Parameters
        ----------
        mesh : dolfin.Mesh
            FEniCS mesh object
        boundaries : dolfin.MeshFunction, optional
            Boundary markers mesh function
        """
        self.mesh = mesh
        self.boundaries = boundaries
        self.bcs: List[BoundaryCondition] = []
        self.dirichlet_bcs: List[DirichletBC] = []

        if boundaries is not None:
            self.ds = Measure("ds", domain=mesh, subdomain_data=boundaries)
        else:
            self.ds = Measure("ds", domain=mesh)

        self.dx = Measure("dx", domain=mesh)

    def add_bc(self, bc: BoundaryCondition):
        """Add a boundary condition."""
        self.bcs.append(bc)

    def add_dirichlet(self, value, boundary_marker=1):
        """Add Dirichlet boundary condition (fixed temperature)."""
        bc = BoundaryCondition(
            bc_type='dirichlet',
            value=value,
            boundary_marker=boundary_marker
        )
        self.add_bc(bc)

    def add_neumann(self, value, boundary_marker=1):
        """Add Neumann boundary condition (fixed heat flux)."""
        bc = BoundaryCondition(
            bc_type='neumann',
            value=value,
            boundary_marker=boundary_marker
        )
        self.add_bc(bc)

    def add_robin(self, heat_transfer_coeff, ambient_temp=298.15, boundary_marker=1):
        """Add Robin boundary condition (convection)."""
        bc = BoundaryCondition(
            bc_type='robin',
            value=0.0,
            boundary_marker=boundary_marker,
            ambient_temperature=ambient_temp,
            heat_transfer_coefficient=heat_transfer_coeff
        )
        self.add_bc(bc)

    def setup_dirichlet_bcs(self, V):
        """
        Setup Dirichlet boundary conditions for a given function space.

        Parameters
        ----------
        V : dolfin.FunctionSpace
            Function space for temperature
        """
        self.dirichlet_bcs = []
        for bc in self.bcs:
            if bc.bc_type == 'dirichlet':
                value = bc.as_expression()
                if self.boundaries is not None:
                    dbc = DirichletBC(V, value, self.boundaries, bc.boundary_marker)
                else:
                    def boundary(x, on_boundary):
                        return on_boundary
                    dbc = DirichletBC(V, value, boundary)
                self.dirichlet_bcs.append(dbc)

        return self.dirichlet_bcs

    def get_neumann_terms(self, u, v):
        """
        Get Neumann boundary integral terms for weak form.

        Parameters
        ----------
        u : dolfin.TrialFunction
            Temperature trial function
        v : dolfin.TestFunction
            Test function

        Returns
        -------
        ufl.form.Form
            Neumann boundary integral terms
        """
        L_neumann = 0
        for bc in self.bcs:
            if bc.bc_type == 'neumann':
                q = bc.as_expression()
                marker = bc.boundary_marker
                L_neumann += q * v * self.ds(marker)
        return L_neumann

    def get_robin_terms(self, u, v):
        """
        Get Robin boundary terms for weak form (matrix and vector).

        Parameters
        ----------
        u : dolfin.TrialFunction
            Temperature trial function
        v : dolfin.TestFunction
            Test function

        Returns
        -------
        tuple
            (a_robin, L_robin) - Robin terms for bilinear and linear forms
        """
        a_robin = 0
        L_robin = 0
        for bc in self.bcs:
            if bc.bc_type == 'robin':
                h = Constant(bc.heat_transfer_coefficient)
                T_amb = Constant(bc.ambient_temperature)
                marker = bc.boundary_marker
                a_robin += h * u * v * self.ds(marker)
                L_robin += h * T_amb * v * self.ds(marker)
        return a_robin, L_robin

    def get_boundary_terms(self, u, v):
        """
        Get all boundary terms for weak form.

        Parameters
        ----------
        u : dolfin.TrialFunction
            Temperature trial function
        v : dolfin.TestFunction
            Test function

        Returns
        -------
        tuple
            (a_bc, L_bc) - Boundary contributions to bilinear and linear forms
        """
        a_robin, L_robin = self.get_robin_terms(u, v)
        L_neumann = self.get_neumann_terms(u, v)
        return a_robin, L_robin + L_neumann

    def has_dirichlet(self):
        """Check if any Dirichlet BCs are defined."""
        return any(bc.bc_type == 'dirichlet' for bc in self.bcs)

    def has_neumann(self):
        """Check if any Neumann BCs are defined."""
        return any(bc.bc_type == 'neumann' for bc in self.bcs)

    def has_robin(self):
        """Check if any Robin BCs are defined."""
        return any(bc.bc_type == 'robin' for bc in self.bcs)
