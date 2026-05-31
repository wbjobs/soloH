"""
Mock dolfin module for testing on systems without full FEniCS installation.
This provides basic functionality for syntax and logic verification.
"""

import numpy as np
from typing import Callable, Optional, Union, List, Tuple


class Point:
    def __init__(self, *args):
        if len(args) == 1:
            self.coords = np.array(args[0])
        else:
            self.coords = np.array(args)

    def __getitem__(self, idx):
        return self.coords[idx]

    def __repr__(self):
        return f"Point({', '.join(str(c) for c in self.coords)})"


class Constant:
    def __init__(self, value):
        self.value = np.array(value)

    def values(self):
        """Return array of values (for FEniCS compatibility)."""
        if np.isscalar(self.value) or self.value.ndim == 0:
            return np.array([self.value])
        return self.value

    def __mul__(self, other):
        if isinstance(other, Constant):
            return Constant(self.value * other.value)
        return other.__rmul__(self)

    def __rmul__(self, other):
        if isinstance(other, (int, float, np.ndarray)):
            return Constant(self.value * other)
        return other * self

    def __add__(self, other):
        if isinstance(other, Constant):
            return Constant(self.value + other.value)
        return other.__radd__(self)

    def __radd__(self, other):
        if isinstance(other, (int, float, np.ndarray)):
            return Constant(self.value + other)
        return other + self

    def __sub__(self, other):
        return self + (-other)

    def __neg__(self):
        return Constant(-self.value)

    def __rsub__(self, other):
        if isinstance(other, (int, float, np.ndarray)):
            return Constant(other - self.value)
        return Form(f"{other} - {self}")

    def __pow__(self, power):
        if isinstance(power, (int, float)):
            return Constant(self.value ** power)
        return Form(f"{self} ** {power}")

    def __truediv__(self, other):
        if isinstance(other, Constant):
            return Constant(self.value / other.value)
        if isinstance(other, (int, float, np.ndarray)):
            return Constant(self.value / other)
        return Form(f"{self} / {other}")

    def __rtruediv__(self, other):
        if isinstance(other, (int, float, np.ndarray)):
            return Constant(other / self.value)
        return Form(f"{other} / {self}")

    def __float__(self):
        val = self.values()
        if len(val) == 1:
            return float(val[0])
        raise TypeError("Cannot convert multi-valued Constant to float")

    def __repr__(self):
        return f"Constant({self.value})"


class Function:
    def __init__(self, function_space=None):
        self._space = function_space
        size = function_space.dim() if function_space else 0
        self._vector = Vector(size)

    def vector(self):
        return self._vector

    def assign(self, other):
        if isinstance(other, Function):
            self._vector = other._vector.copy()
        else:
            self._vector[:] = other

    def copy(self, deepcopy=True):
        new_func = Function(self._space)
        new_func._vector = self._vector.copy()
        return new_func

    def compute_vertex_values(self, mesh=None):
        return self._vector.get_local()

    def __call__(self, pt):
        idx = 0
        if hasattr(pt, 'coords'):
            if len(pt.coords) >= 1:
                idx = int(pt[0] * 10)
        return self._vector.get_local()[idx % len(self._vector)]

    def __mul__(self, other):
        return Form(f"{self} * {other}")

    def __add__(self, other):
        return Form(f"{self} + {other}")

    def __rmul__(self, other):
        return Form(f"{other} * {self}")

    def __pow__(self, power):
        return Form(f"{self} ** {power}")

    def __sub__(self, other):
        return Form(f"{self} - {other}")

    def __rsub__(self, other):
        return Form(f"{other} - {self}")

    def function_space(self):
        """Return the function space this function belongs to."""
        return self._space


class Vector:
    def __init__(self, size=0):
        self._data = np.zeros(size)

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            return self._data[idx]
        return self._data[idx]

    def __setitem__(self, idx, value):
        if isinstance(idx, slice):
            if np.isscalar(value):
                self._data[idx] = value
            else:
                val_arr = np.asarray(value)
                if val_arr.ndim == 0:
                    val_arr = np.full(len(self._data[idx]), val_arr.item())
                self._data[idx] = val_arr
        else:
            self._data[idx] = value

    def __len__(self):
        return len(self._data)

    def size(self):
        return len(self._data)

    def get_local(self):
        return self._data.copy()

    def zero(self):
        self._data[:] = 0

    def __repr__(self):
        return f"Vector({self._data})"

    def copy(self):
        new_vec = Vector(len(self._data))
        new_vec._data = self._data.copy()
        return new_vec


class FunctionSpace:
    def __init__(self, mesh=None, family='CG', degree=1):
        self._mesh = mesh
        self.family = family
        self.degree = degree
        self._dim = mesh.num_vertices() if mesh else 0

    def dim(self):
        return self._dim

    def mesh(self):
        return self._mesh

    def tabulate_dof_coordinates(self):
        """Return coordinates of degrees of freedom."""
        if self._mesh is not None:
            coords = self._mesh.coordinates()
            dim = getattr(self, '_dim', None)
            if dim is not None and isinstance(dim, int) and dim > 0:
                if len(coords) != dim:
                    if len(coords) >= dim:
                        return coords[:dim]
                    else:
                        pad = np.zeros((dim - len(coords), coords.shape[1] if coords.ndim > 1 else 2))
                        return np.vstack([coords, pad]) if coords.ndim > 1 else np.concatenate([coords, pad[:, 0]])
            return coords
        dim = getattr(self, '_dim', 0)
        dim = dim if isinstance(dim, int) else 0
        return np.zeros((dim, 2))


class VectorFunctionSpace(FunctionSpace):
    def __init__(self, mesh=None, family='CG', degree=1):
        super().__init__(mesh, family, degree)
        self._dim = self._dim * (mesh.topology().dim() if mesh else 2)


class Mesh:
    def __init__(self):
        self._coordinates = np.zeros((0, 2))
        self._cells = []
        self._topology_dim = 2

    def num_vertices(self):
        return len(self._coordinates)

    def num_cells(self):
        return len(self._cells)

    def topology(self):
        class Topology:
            def __init__(self, dim):
                self._dim = dim
            def dim(self):
                return self._dim
        return Topology(self._topology_dim)

    def coordinates(self):
        return self._coordinates

    def bounding_box_tree(self):
        class BBoxTree:
            def compute_first_entity_collision(self, pt):
                return 0
        return BBoxTree()

    def cells(self):
        return iter(self._cells)


class MeshFunction:
    def __init__(self, dtype, mesh, dim, value=0):
        self.mesh = mesh
        self.dim = dim
        self._values = {}

    def set_all(self, value):
        for i in range(1000):
            self._values[i] = value

    def __getitem__(self, idx):
        return self._values.get(idx, 0)

    def __setitem__(self, idx, value):
        self._values[idx] = value


class SubDomain:
    def inside(self, x, on_boundary):
        return False

    def mark(self, mesh_function, marker):
        pass


class Measure:
    def __init__(self, name, domain=None, subdomain_data=None):
        self.name = name
        self.domain = domain
        self.subdomain_data = subdomain_data

    def __call__(self, marker=None):
        return self


class Form:
    def __init__(self, expr=""):
        self.expr = expr

    def __mul__(self, other):
        if isinstance(other, Measure):
            return self
        return Form(f"{self.expr} * {other}")

    def __rmul__(self, other):
        return Form(f"{other} * {self.expr}")

    def __add__(self, other):
        if isinstance(other, (int, float)) and other == 0:
            return self
        if isinstance(other, Form):
            return Form(f"{self.expr} + {other.expr}")
        return Form(f"{self.expr} + {other}")

    def __radd__(self, other):
        if isinstance(other, (int, float)) and other == 0:
            return self
        return Form(f"{other} + {self.expr}")

    def __neg__(self):
        return Form(f"-{self.expr}")

    def __sub__(self, other):
        return Form(f"{self.expr} - {other}")

    def __rsub__(self, other):
        return Form(f"{other} - {self.expr}")

    def __pow__(self, power):
        return Form(f"{self.expr} ** {power}")

    def __eq__(self, other):
        """Create an Equation object for a == L form."""
        class Equation:
            def __init__(self, lhs, rhs):
                self.lhs = lhs
                self.rhs = rhs
        return Equation(self, other)

    def __repr__(self):
        return f"Form({self.expr})"


class TrialFunction:
    def __init__(self, V):
        self._space = V

    def __mul__(self, other):
        if isinstance(other, (TestFunction, Function)):
            return Form(f"Trial * {other}")
        return other.__rmul__(self)

    def __rmul__(self, other):
        return Form(f"{other} * Trial")

    def __add__(self, other):
        return Form(f"Trial + {other}")


class TestFunction:
    def __init__(self, V):
        self._space = V

    def __mul__(self, other):
        if isinstance(other, (TrialFunction, Function)):
            return Form(f"Test * {other}")
        return other.__rmul__(self)

    def __rmul__(self, other):
        return Form(f"{other} * Test")


def inner(a, b):
    return Form(f"inner({a}, {b})")


def grad(a):
    return Form(f"grad({a})")


def lhs(form):
    return form


def rhs(form):
    return form


def assemble(form):
    if isinstance(form, Form):
        expr = form.expr
        if any(op in expr for op in ['Test', 'Trial', 'dk', 'dq']):
            return Vector(121)
        return 0.1
    return form


def _extract_bc_value(bcs):
    """Extract boundary condition value from bcs list."""
    value = 300.0
    if bcs is not None:
        if isinstance(bcs, list) and len(bcs) > 0:
            bc = bcs[0]
            if hasattr(bc, '_value'):
                bc_val = bc._value
                if isinstance(bc_val, Constant):
                    value = float(bc_val)
                elif isinstance(bc_val, (int, float)):
                    value = float(bc_val)
    return value


def solve(*args, **kwargs):
    """
    Mock FEniCS solve function.
    Supports two forms:
    1. solve(a == L, u, bcs, ...)
    2. solve(a, L, u, bcs, ...)
    """
    u = None
    bcs = None

    if len(args) >= 2:
        # Check if first arg is a Form with '==' (Equation)
        first = args[0]
        if hasattr(first, 'lhs') and hasattr(first, 'rhs'):
            # Form: solve(eq, u, bcs, ...)
            if len(args) >= 2:
                u = args[1]
            if len(args) >= 3:
                bcs = args[2]
        else:
            # Form: solve(a, L, u, bcs, ...)
            if len(args) >= 3:
                u = args[2]
            if len(args) >= 4:
                bcs = args[3]

    if bcs is None and 'bcs' in kwargs:
        bcs = kwargs['bcs']

    if isinstance(u, Function):
        value = _extract_bc_value(bcs)
        u.vector()[:] = value
    return None


class DirichletBC:
    def __init__(self, V, value, *args, **kwargs):
        self._space = V
        self._value = value
        self.domain_args = args
        if len(args) >= 2:
            self.domain_args = args

    def function_space(self):
        return self._space

    def apply(self, A):
        """Apply boundary condition to matrix or vector."""
        if hasattr(A, '_data'):
            # Applying to a Vector - set all values to BC value
            val = self._value
            if isinstance(val, Constant):
                val = float(val)
            if isinstance(val, (int, float)):
                A[:] = val
        return None


class PointSource:
    def __init__(self, V, point, value):
        self._space = V
        self._point = point
        self._value = value

    def apply(self, vector):
        if len(vector) > 0:
            vector[0] += self._value


class Expression:
    def __init__(self, expr, degree=1, **kwargs):
        self.expr = expr
        self.degree = degree
        self.params = kwargs

    def __repr__(self):
        return f"Expression('{self.expr}')"


class KrylovSolver:
    def __init__(self, method='gmres', preconditioner='default'):
        self.parameters = {'absolute_tolerance': 1e-10, 'relative_tolerance': 1e-10}

    def solve(self, x, b):
        x[:] = b.get_local()


class LUSolver:
    def __init__(self, A=None):
        self.parameters = {'absolute_tolerance': 1e-10, 'relative_tolerance': 1e-10}

    def solve(self, x, b):
        x[:] = b.get_local()


class XDMFFile:
    def __init__(self, filename):
        self.filename = filename
        self.parameters = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, mesh):
        pass

    def write(self, mesh):
        pass

    def write_checkpoint(self, func, name, time_step, encoding=None, append=False):
        pass


def interpolate(expr, V):
    f = Function(V)
    f.vector()[:] = 10.0
    return f


def plot(obj, **kwargs):
    class FakePlot:
        def __init__(self):
            pass
    return FakePlot()


def cells(mesh):
    class Cell:
        def __init__(self, idx):
            self._idx = idx
        def entities(self, dim):
            return [self._idx * 3, self._idx * 3 + 1, self._idx * 3 + 2]
    return [Cell(i) for i in range(10)]


DOLFIN_EPS = 1e-14
DOLFIN_PI = np.pi


class delta_ij:
    def __getitem__(self, idx):
        i, j = idx
        return 1 if i == j else 0


delta_ij = delta_ij()


def as_backend_type(A):
    class BackendType:
        def mat(self):
            class Mat:
                def getValuesCSR(self):
                    return [np.array([0, 10]), np.array(range(10)), np.ones(10) * 0.1]
                def size(self):
                    return (10, 10)
            return Mat()
    return BackendType()


def sqrt(x):
    if isinstance(x, Form):
        return Form(f"sqrt({x.expr})")
    return np.sqrt(x)


def sin(x):
    if isinstance(x, Form):
        return Form(f"sin({x.expr})")
    return np.sin(x)


def cos(x):
    if isinstance(x, Form):
        return Form(f"cos({x.expr})")
    return np.cos(x)


def sym(A):
    return Form(f"sym({A})")


def tr(A):
    return Form(f"tr({A})")


def Identity(dim):
    return Form(f"Identity({dim})")


def exp(x):
    if isinstance(x, Form):
        return Form(f"exp({x.expr})")
    return np.exp(x)


pi = np.pi


def BoxMesh(p1, p2, nx, ny, nz=None):
    mesh = Mesh()
    if nz is None or nz == 1:
        mesh._topology_dim = 2
        mesh._coordinates = np.zeros(((nx + 1) * (ny + 1), 2))
        idx = 0
        for j in range(ny + 1):
            for i in range(nx + 1):
                mesh._coordinates[idx] = [i / nx, j / ny]
                idx += 1
    else:
        mesh._topology_dim = 3
        mesh._coordinates = np.zeros(((nx + 1) * (ny + 1) * (nz + 1), 3))
    mesh._cells = [i for i in range(nx * ny)]
    return mesh


def RectangleMesh(p1, p2, nx, ny):
    return BoxMesh(p1, p2, nx, ny, 1)


__version__ = "2019.1.0"
