"""
Advanced regularization for inverse heat conduction problems.
Includes weighted TV, TGV, adaptive, and spatially varying regularization.
"""

import numpy as np
from dolfin import *
from typing import Union, Optional, List


class Regularization:
    """
    Regularization terms for inverse problems.

    Supported types:
    - 'tikhonov0': L2 regularization (zero-order) ||k - k_ref||^2
    - 'tikhonov1': H1 regularization (first-order) ||∇k||^2
    - 'tikhonov': Combined L2 + H1 regularization
    - 'tv': Total Variation regularization ||∇k||_1
    """

    def __init__(self, reg_type: str = 'tikhonov', alpha: float = 1e-3,
                 beta: float = 1e-6, k_ref: Union[float, Function] = None):
        """
        Initialize regularization.

        Parameters
        ----------
        reg_type : str
            Type of regularization
        alpha : float
            Regularization parameter for smoothness (H1 or TV)
        beta : float
            Regularization parameter for L2 penalty
        k_ref : float or Function, optional
            Reference conductivity for Tikhonov0 term
        """
        self.reg_type = reg_type
        self.alpha = Constant(alpha)
        self.beta = Constant(beta)
        self.k_ref = k_ref

        if reg_type not in ['tikhonov0', 'tikhonov1', 'tikhonov', 'tv',
                            'weighted_tv', 'tgv', 'adaptive']:
            raise ValueError(f"Unknown regularization type: {reg_type}")

        self._eps_tv = Constant(1e-8)

    def set_alpha(self, alpha):
        """Update regularization parameter alpha."""
        if isinstance(alpha, Constant):
            self.alpha = alpha
        else:
            self.alpha = Constant(alpha)

    def set_beta(self, beta):
        """Update regularization parameter beta."""
        if isinstance(beta, Constant):
            self.beta = beta
        else:
            self.beta = Constant(beta)

    def compute_value(self, k: Function, dx: Measure) -> float:
        """
        Compute regularization value.

        Parameters
        ----------
        k : dolfin.Function
            Thermal conductivity field
        dx : dolfin.Measure
            Integration measure

        Returns
        -------
        float
            Regularization value
        """
        value = 0.0

        if self.reg_type in ['tikhonov0', 'tikhonov']:
            if self.k_ref is not None:
                k_ref_fe = self.k_ref if isinstance(self.k_ref, Function) else Constant(self.k_ref)
                value += assemble(self.beta * (k - k_ref_fe)**2 * dx)
            else:
                value += assemble(self.beta * k**2 * dx)

        if self.reg_type in ['tikhonov1', 'tikhonov']:
            value += assemble(self.alpha * inner(grad(k), grad(k)) * dx)

        if self.reg_type == 'tv':
            grad_k = grad(k)
            tv_norm = sqrt(inner(grad_k, grad_k) + self._eps_tv)
            value += assemble(self.alpha * tv_norm * dx)
            if self.k_ref is not None:
                k_ref_fe = self.k_ref if isinstance(self.k_ref, Function) else Constant(self.k_ref)
                value += assemble(self.beta * (k - k_ref_fe)**2 * dx)

        return value

    def compute_variation(self, k: Function, dk: TestFunction, dx: Measure) -> Form:
        """
        Compute variation (derivative) of regularization term.

        Parameters
        ----------
        k : dolfin.Function
            Thermal conductivity field
        dk : dolfin.TestFunction
            Test function for variation
        dx : dolfin.Measure
            Integration measure

        Returns
        -------
        ufl.form.Form
            Variational form of regularization derivative
        """
        dR = 0

        if self.reg_type in ['tikhonov0', 'tikhonov']:
            if self.k_ref is not None:
                k_ref_fe = self.k_ref if isinstance(self.k_ref, Function) else Constant(self.k_ref)
                dR += 2 * self.beta * (k - k_ref_fe) * dk * dx
            else:
                dR += 2 * self.beta * k * dk * dx

        if self.reg_type in ['tikhonov1', 'tikhonov']:
            dR += 2 * self.alpha * inner(grad(k), grad(dk)) * dx

        if self.reg_type == 'tv':
            grad_k = grad(k)
            tv_denom = sqrt(inner(grad_k, grad_k) + self._eps_tv)
            dR += self.alpha * inner(grad_k, grad(dk)) / tv_denom * dx
            if self.k_ref is not None:
                k_ref_fe = self.k_ref if isinstance(self.k_ref, Function) else Constant(self.k_ref)
                dR += 2 * self.beta * (k - k_ref_fe) * dk * dx

        return dR

    def compute_gradient(self, k_vec: np.ndarray) -> np.ndarray:
        """
        Compute gradient of regularization with respect to nodal values.
        Default implementation uses finite differences.
        """
        n = len(k_vec)
        grad = np.zeros(n)
        eps = 1e-6

        def func(x):
            if not hasattr(self, 'gradient_operator'):
                self.gradient_operator = lambda k: np.gradient(k)
            reg = self.gradient_operator(x)
            if hasattr(self, 'weight_function') and self.weight_function is not None:
                reg = reg * self.weight_function
            alpha_val = self.alpha.values()[0] if hasattr(self.alpha, 'values') else float(self.alpha)
            return np.sum(alpha_val * np.abs(reg))

        f0 = func(k_vec)
        for i in range(n):
            k_plus = k_vec.copy()
            k_plus[i] += eps
            grad[i] = (func(k_plus) - f0) / eps

        return grad


class WeightedRegularization(Regularization):
    """
    Spatially weighted regularization for preserving sharp interfaces.

    Reduces regularization strength where measurements provide information,
    increases regularization in data-sparse regions.
    """

    def __init__(self, reg_type: str = 'tv', alpha: float = 1e-3,
                 beta: float = 1e-6, k_ref: Union[float, Function] = None,
                 weight_function: Optional[Function] = None,
                 measurement_coords: Optional[np.ndarray] = None,
                 mesh: Optional[Mesh] = None,
                 weight_radius: float = 0.1,
                 min_weight: float = 0.1,
                 max_weight: float = 1.0):
        """
        Initialize weighted regularization.

        Parameters
        ----------
        reg_type : str
            Type of regularization ('tv', 'tikhonov', etc.)
        alpha : float
            Regularization parameter
        beta : float
            L2 penalty parameter
        k_ref : float or Function, optional
            Reference conductivity
        weight_function : Function, optional
            Spatially varying weight function (0 = no regularization, 1 = full)
        measurement_coords : np.ndarray, optional
            Measurement point coordinates for automatic weight generation
        mesh : Mesh, optional
            Mesh for weight function generation
        weight_radius : float
            Radius around measurements for weight reduction
        min_weight : float
            Minimum weight (in data-sparse regions)
        max_weight : float
            Maximum weight (in data-rich regions, actually lower)
        """
        super().__init__(reg_type=reg_type, alpha=alpha, beta=beta, k_ref=k_ref)
        self.reg_type = 'weighted_tv'

        self.weight_function = weight_function
        self.measurement_coords = measurement_coords
        self.mesh = mesh
        self.weight_radius = weight_radius
        self.min_weight = min_weight
        self.max_weight = max_weight

        if weight_function is None and measurement_coords is not None and mesh is not None:
            self._generate_measurement_based_weight()

    def _generate_measurement_based_weight(self):
        """Generate weight function based on distance to measurements."""
        V = FunctionSpace(self.mesh, 'CG', 1)

        try:
            dof_coords = V.tabulate_dof_coordinates()
        except AttributeError:
            dof_coords = self.mesh.coordinates()

        dim = self.mesh.topology().dim()
        n_dofs = len(dof_coords)

        weights_np = np.ones(n_dofs) * self.max_weight

        if self.measurement_coords is not None and len(self.measurement_coords) > 0:
            for i in range(n_dofs):
                min_dist = np.inf
                for meas_coord in self.measurement_coords:
                    dist = np.linalg.norm(dof_coords[i][:dim] - meas_coord[:dim])
                    min_dist = min(min_dist, dist)

                w = self.max_weight - (self.max_weight - self.min_weight) * \
                    np.exp(-min_dist**2 / (2 * self.weight_radius**2))
                weights_np[i] = w

        try:
            weight = Function(V)
            weight_vec = weight.vector()
            try:
                weight_vec[:] = weights_np
            except (TypeError, AttributeError):
                for i in range(len(weights_np)):
                    weight_vec[i] = weights_np[i]
            self.weight_function = weight
        except Exception:
            self.weight_function = weights_np

    def _get_weight(self):
        """Get weight function, defaulting to 1 if not set."""
        if self.weight_function is not None:
            return self.weight_function
        return Constant(1.0)

    def compute_value(self, k: Function, dx: Measure) -> float:
        """
        Compute weighted regularization value.
        """
        w = self._get_weight()
        value = 0.0

        if self.reg_type in ['tikhonov0', 'tikhonov']:
            if self.k_ref is not None:
                k_ref_fe = self.k_ref if isinstance(self.k_ref, Function) else Constant(self.k_ref)
                value += assemble(w * self.beta * (k - k_ref_fe)**2 * dx)
            else:
                value += assemble(w * self.beta * k**2 * dx)

        if self.reg_type in ['tikhonov1', 'tikhonov']:
            value += assemble(w * self.alpha * inner(grad(k), grad(k)) * dx)

        if self.reg_type == 'tv':
            grad_k = grad(k)
            tv_norm = sqrt(inner(grad_k, grad_k) + self._eps_tv)
            value += assemble(w * self.alpha * tv_norm * dx)
            if self.k_ref is not None:
                k_ref_fe = self.k_ref if isinstance(self.k_ref, Function) else Constant(self.k_ref)
                value += assemble(w * self.beta * (k - k_ref_fe)**2 * dx)

        return value

    def compute_variation(self, k: Function, dk: TestFunction, dx: Measure) -> Form:
        """
        Compute variation of weighted regularization.
        """
        w = self._get_weight()
        dR = 0

        if self.reg_type in ['tikhonov0', 'tikhonov']:
            if self.k_ref is not None:
                k_ref_fe = self.k_ref if isinstance(self.k_ref, Function) else Constant(self.k_ref)
                dR += 2 * w * self.beta * (k - k_ref_fe) * dk * dx
            else:
                dR += 2 * w * self.beta * k * dk * dx

        if self.reg_type in ['tikhonov1', 'tikhonov']:
            dR += 2 * w * self.alpha * inner(grad(k), grad(dk)) * dx

        if self.reg_type == 'tv':
            grad_k = grad(k)
            tv_denom = sqrt(inner(grad_k, grad_k) + self._eps_tv)
            dR += w * self.alpha * inner(grad_k, grad(dk)) / tv_denom * dx
            if self.k_ref is not None:
                k_ref_fe = self.k_ref if isinstance(self.k_ref, Function) else Constant(self.k_ref)
                dR += 2 * w * self.beta * (k - k_ref_fe) * dk * dx

        return dR


class TGVRegularization(Regularization):
    """
    Total Generalized Variation (TGV) regularization.

    Preserves sharp interfaces better than TV by penalizing higher-order
    derivatives in a weaker way. TGV2 is implemented.
    """

    def __init__(self, alpha: float = 1e-3, alpha0: float = None, alpha1: float = None,
                 beta: float = 1e-6, k_ref: Union[float, Function] = None,
                 gamma0: float = 1.0, gamma1: float = 2.0,
                 eps: float = 1e-8):
        """
        Initialize TGV regularization.

        Parameters
        ----------
        alpha : float, optional
            Overall regularization parameter (convenience alias for alpha1)
        alpha0 : float, optional
            Regularization parameter for second derivative (symmetric gradient)
        alpha1 : float, optional
            Regularization parameter for first derivative
        beta : float
            L2 penalty parameter
        k_ref : float or Function, optional
            Reference conductivity
        gamma0 : float, optional
            Convenience alias for alpha0
        gamma1 : float, optional
            Convenience alias for alpha1
        eps : float
            Smoothing parameter for norm
        """
        if alpha1 is None:
            alpha1 = alpha
        if alpha0 is None:
            alpha0 = alpha / 2.0
        if gamma0 is not None and alpha0 == alpha / 2.0:
            alpha0 = gamma0
        if gamma1 is not None and alpha1 == alpha:
            alpha1 = gamma1

        super().__init__(reg_type='tgv', alpha=alpha1, beta=beta, k_ref=k_ref)
        self.alpha0 = Constant(alpha0)
        self.alpha1 = Constant(alpha1)
        self.gamma0 = gamma0
        self.gamma1 = gamma1
        self._eps = Constant(eps)

    def compute_value(self, k: Function, dx: Measure) -> float:
        """
        Compute TGV2 value using mixed formulation.

        Minimizes over auxiliary variable v (vector field):
        TGV2(k) = min_v alpha1 * ||∇k - v||_1 + alpha0 * ||ε(v)||_1
        """
        mesh = k.function_space().mesh()
        dim = mesh.topology().dim()

        if dim == 2:
            V = VectorFunctionSpace(mesh, 'CG', 1, dim=2)
            W = FunctionSpace(mesh, 'CG', 1)
        else:
            V = VectorFunctionSpace(mesh, 'CG', 1, dim=3)
            W = FunctionSpace(mesh, 'CG', 1)

        v = Function(V)
        u = TrialFunction(W)
        w = TestFunction(W)

        grad_k = grad(k)
        diff = grad_k - v
        first_order = sqrt(inner(diff, diff) + self._eps)
        J1 = assemble(self.alpha1 * first_order * dx)

        eps_v = 0.5 * (grad(v) + grad(v).T)
        second_order = sqrt(inner(eps_v, eps_v) + self._eps)
        J2 = assemble(self.alpha0 * second_order * dx)

        J_reg = J1 + J2

        if self.k_ref is not None:
            k_ref_fe = self.k_ref if isinstance(self.k_ref, Function) else Constant(self.k_ref)
            J_reg += assemble(self.beta * (k - k_ref_fe)**2 * dx)

        return J_reg

    def compute_variation(self, k: Function, dk: TestFunction, dx: Measure) -> Form:
        """
        Compute variation of TGV (approximate by treating v as fixed at optimal).
        For simplicity, use an approximation of the subgradient.
        """
        grad_k = grad(k)
        denom = sqrt(inner(grad_k, grad_k) + self._eps)

        dR = self.alpha1 * inner(grad_k, grad(dk)) / denom * dx

        if self.k_ref is not None:
            k_ref_fe = self.k_ref if isinstance(self.k_ref, Function) else Constant(self.k_ref)
            dR += 2 * self.beta * (k - k_ref_fe) * dk * dx

        return dR


class AdaptiveRegularization(WeightedRegularization):
    """
    Adaptive regularization that updates based on solution features.

    Automatically adjusts regularization strength to preserve edges
    while suppressing noise in smooth regions.
    """

    def __init__(self, reg_type: str = 'tv', alpha: float = 1e-3,
                 beta: float = 1e-6, k_ref: Union[float, Function] = None,
                 measurement_coords: Optional[np.ndarray] = None,
                 mesh: Optional[Mesh] = None,
                 adaptive: bool = True,
                 edge_threshold: float = 0.1,
                 alpha_max: float = 1e-1,
                 alpha_min: float = 1e-5):
        """
        Initialize adaptive regularization.

        Parameters
        ----------
        reg_type : str
            Regularization type
        alpha : float
            Initial regularization parameter
        beta : float
            L2 penalty
        k_ref : float or Function, optional
            Reference conductivity
        measurement_coords : np.ndarray, optional
            Measurement point coordinates for distance-based weighting
        mesh : Mesh, optional
            Mesh for weight function generation
        adaptive : bool
            Enable adaptive updates
        edge_threshold : float
            Threshold for edge detection (normalized gradient)
        alpha_max : float
            Maximum allowed alpha
        alpha_min : float
            Minimum allowed alpha
        """
        super().__init__(reg_type=reg_type, alpha=alpha, beta=beta, k_ref=k_ref)
        self.measurement_coords = measurement_coords
        self.mesh = mesh
        self.adaptive = adaptive
        self.edge_threshold = edge_threshold
        self.alpha_max = alpha_max
        self.alpha_min = alpha_min
        self._iteration_count = 0
        self.edge_indicator = None

        if measurement_coords is not None and mesh is not None:
            self._initialize_distance_weights()

    def update(self, k: Function, dx: Measure):
        """
        Update regularization based on current solution.

        In regions with high gradient (edges), reduce regularization.
        In smooth regions, increase regularization.
        """
        if not self.adaptive:
            return

        self._iteration_count += 1

        grad_k_mag = sqrt(inner(grad(k), grad(k)))
        grad_max = assemble(grad_k_mag * dx) / assemble(Constant(1) * dx)

        if grad_max > 0:
            V = FunctionSpace(k.function_space().mesh(), 'CG', 1)
            weight_expr = Expression(
                '1.0 - alpha_factor * exp(-pow(grad_mag / threshold, 2))',
                alpha_factor=0.8,
                threshold=self.edge_threshold * grad_max,
                grad_mag=grad_k_mag,
                degree=2
            )
            self.weight_function = interpolate(weight_expr, V)

        alpha_new = float(self.alpha) * (0.99 if self._iteration_count < 20 else 1.0)
        alpha_new = np.clip(alpha_new, self.alpha_min, self.alpha_max)
        self.set_alpha(alpha_new)

    def _initialize_distance_weights(self):
        """Initialize weight function based on distance to measurements."""
        V = FunctionSpace(self.mesh, 'CG', 1)

        try:
            dof_coords = V.tabulate_dof_coordinates()
        except AttributeError:
            dof_coords = self.mesh.coordinates()

        dim = self.mesh.topology().dim()
        n_dofs = len(dof_coords)
        weights = np.ones(n_dofs) * self.max_weight if hasattr(self, 'max_weight') else 1.0

        if self.measurement_coords is not None and len(self.measurement_coords) > 0:
            min_weight = self.min_weight if hasattr(self, 'min_weight') else 0.1
            weight_radius = self.weight_radius if hasattr(self, 'weight_radius') else 0.1

            for i in range(n_dofs):
                min_dist = np.inf
                for meas in self.measurement_coords:
                    dist = np.linalg.norm(dof_coords[i][:dim] - meas[:dim])
                    min_dist = min(min_dist, dist)

                if min_dist < weight_radius:
                    weights[i] = min_weight + (1.0 - min_weight) * (min_dist / weight_radius) ** 2

        try:
            weight = Function(V)
            weight_vec = weight.vector()
            vec_size = len(weight_vec)
            if vec_size == n_dofs:
                try:
                    weight_vec[:] = weights
                except (TypeError, AttributeError, IndexError, ValueError):
                    for i in range(min(len(weights), vec_size)):
                        weight_vec[i] = float(weights[i])
                self.weight_function = weight
            else:
                self.weight_function = weights
        except Exception:
            self.weight_function = weights

    def update_adaptive_weights(self, k_solution: np.ndarray):
        """
        Update adaptive weights based on current solution (nodal values).
        Detects edges and reduces regularization strength there.

        Parameters
        ----------
        k_solution : np.ndarray
            Current solution vector of thermal conductivity nodal values
        """
        n = len(k_solution)
        grad_k = np.gradient(k_solution)
        grad_mag = np.abs(grad_k)
        grad_max = np.max(grad_mag) if np.max(grad_mag) > 0 else 1.0
        self.edge_indicator = grad_mag / grad_max

        weights = np.ones(n)
        edge_mask = self.edge_indicator > self.edge_threshold
        weights[edge_mask] = 0.1

        self.weight_function = weights


class BarrierRegularization:
    """
    Logarithmic barrier function for enforcing box constraints.

    Adds penalty when parameters approach bounds:
    barrier = -mu * sum(log(x - lb) + log(ub - x))
    """

    def __init__(self, lb: np.ndarray, ub: np.ndarray, mu: float = 1e-4):
        """
        Initialize barrier regularization.

        Parameters
        ----------
        lb : np.ndarray
            Lower bounds
        ub : np.ndarray
            Upper bounds
        mu : float
            Barrier strength
        """
        self.lb = np.asarray(lb)
        self.ub = np.asarray(ub)
        self.mu = mu
        self._eps = 1e-10

    def compute_value(self, x: np.ndarray) -> float:
        """
        Compute barrier value.
        """
        lb_dist = x - self.lb
        ub_dist = self.ub - x

        lb_dist = np.maximum(lb_dist, self._eps)
        ub_dist = np.maximum(ub_dist, self._eps)

        barrier = -self.mu * np.sum(np.log(lb_dist) + np.log(ub_dist))
        return barrier

    def compute_gradient(self, x: np.ndarray) -> np.ndarray:
        """
        Compute barrier gradient.
        """
        lb_dist = x - self.lb
        ub_dist = self.ub - x

        lb_dist = np.maximum(lb_dist, self._eps)
        ub_dist = np.maximum(ub_dist, self._eps)

        grad = self.mu * (-1.0 / lb_dist + 1.0 / ub_dist)
        return grad

    def update_mu(self, factor: float = 0.1):
        """
        Reduce barrier strength (interior point method).
        """
        self.mu *= factor


def create_regularization(config: dict, **kwargs) -> Regularization:
    """
    Factory function to create appropriate regularization object.

    Parameters
    ----------
    config : dict
        Configuration dictionary with keys:
        - type: 'tikhonov', 'tv', 'weighted_tv', 'tgv', 'adaptive'
        - alpha, beta, etc.
    **kwargs
        Additional arguments (mesh, measurement_coords, etc.)

    Returns
    -------
    Regularization
        Appropriate regularization object
    """
    reg_type = config.get('type', 'tikhonov')
    alpha = config.get('alpha', 1e-3)
    beta = config.get('beta', 1e-6)
    k_ref = config.get('k_ref')

    if reg_type == 'weighted_tv':
        return WeightedRegularization(
            reg_type='tv',
            alpha=alpha,
            beta=beta,
            k_ref=k_ref,
            weight_radius=config.get('weight_radius', 0.1),
            min_weight=config.get('min_weight', 0.1),
            max_weight=config.get('max_weight', 1.0),
            **kwargs
        )

    elif reg_type == 'tgv':
        return TGVRegularization(
            alpha0=config.get('alpha0', alpha * 0.1),
            alpha1=config.get('alpha1', alpha),
            beta=beta,
            k_ref=k_ref
        )

    elif reg_type == 'adaptive':
        return AdaptiveRegularization(
            reg_type=config.get('base_reg', 'tv'),
            alpha=alpha,
            beta=beta,
            k_ref=k_ref,
            edge_threshold=config.get('edge_threshold', 0.1),
            alpha_max=config.get('alpha_max', 1e-1),
            alpha_min=config.get('alpha_min', 1e-5)
        )

    else:
        return Regularization(
            reg_type=reg_type,
            alpha=alpha,
            beta=beta,
            k_ref=k_ref
        )
