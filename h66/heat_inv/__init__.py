"""
Thermal Conductivity Inverse Problem Solver.

This package provides tools for solving the inverse heat conduction problem
to estimate thermal conductivity distribution from temperature measurements.
"""

from .geometry import GeometryHandler
from .forward import HeatForwardSolver
from .boundary import BoundaryConditionManager
from .measurements import MeasurementData
from .objective import (
    ObjectiveFunction,
    JointObjectiveFunction,
    MultiphysicsObjectiveFunction,
    Regularization,
    ParameterScaler,
)
from .regularization import (
    WeightedRegularization,
    TGVRegularization,
    AdaptiveRegularization,
    BarrierRegularization,
    create_regularization,
)
from .adjoint import AdjointGradient
from .optimizer import (
    InverseOptimizer,
    JointInverseOptimizer,
    OptimizationOptions,
    OptimizationResult,
    JointOptimizationResult,
)
from .uqt import UncertaintyQuantifier
from .vtk_output import VTKWriter, ResultsVisualizer
from .multiphysics import (
    ThermoelectricSolver,
    ThermoelasticSolver,
    MultiphysicsCoupling,
)
from .reduced_order import (
    PODBasisGenerator,
    ReducedOrderSolver,
    ROMObjectiveFunction,
)
from .experimental_design import SensorOptimizer

__all__ = [
    "GeometryHandler",
    "HeatForwardSolver",
    "BoundaryConditionManager",
    "MeasurementData",
    "ObjectiveFunction",
    "JointObjectiveFunction",
    "MultiphysicsObjectiveFunction",
    "Regularization",
    "ParameterScaler",
    "WeightedRegularization",
    "TGVRegularization",
    "AdaptiveRegularization",
    "BarrierRegularization",
    "create_regularization",
    "AdjointGradient",
    "InverseOptimizer",
    "JointInverseOptimizer",
    "OptimizationOptions",
    "OptimizationResult",
    "JointOptimizationResult",
    "UncertaintyQuantifier",
    "VTKWriter",
    "ResultsVisualizer",
    "ThermoelectricSolver",
    "ThermoelasticSolver",
    "MultiphysicsCoupling",
    "PODBasisGenerator",
    "ReducedOrderSolver",
    "ROMObjectiveFunction",
    "SensorOptimizer",
]
