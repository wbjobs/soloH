"""Halo Analysis Tool - C++ + Python hybrid for cosmological simulation analysis.

This package provides tools for:
- Reading Gadget-2 format snapshot files
- Friends-of-Friends (FoF) halo finding
- Merger tree building across snapshots
- Subhalo identification and analysis
- Merger tree visualization with Graphviz
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

try:
    from . import halo_analysis_cpp
    CPP_AVAILABLE = True
except ImportError:
    CPP_AVAILABLE = False

from . import core
from . import analysis
from . import visualization

from .core import (
    EllipsoidalShape,
    EllipsoidalFitter,
    SubstructureFinder,
    GravityModel,
    FR_Parameters,
    HaloStatistics,
    ModelComparison,
    ModifiedGravityInterface,
)

if not CPP_AVAILABLE:
    from .core import (
        GadgetReader,
        FoFFinder,
        MergerTreeBuilder,
        Snapshot,
        Halo,
        MergerTreeNode,
        compute_mean_interparticle_spacing,
        periodic_distance,
    )
else:
    from .halo_analysis_cpp import (
        GadgetReader,
        FoFFinder,
        MergerTreeBuilder,
        Snapshot,
        Halo,
        MergerTreeNode,
        compute_mean_interparticle_spacing,
        periodic_distance,
    )

from .analysis import (
    compute_mass_function,
    compute_mass_function_adaptive,
    compute_subhalo_mass_function,
    compute_spin_parameter_distribution,
    compute_formation_redshift_distribution,
    filter_halos_by_mass,
    filter_halos_by_redshift,
    get_merger_history,
    save_halo_catalog,
    load_halo_catalog,
    save_merger_history,
)

from .visualization import (
    plot_merger_tree,
    plot_mass_function,
    plot_spin_distribution,
    plot_formation_redshift_distribution,
    save_merger_tree_graphviz,
)

__version__ = "1.1.0"
__all__ = [
    "CPP_AVAILABLE",
    "GadgetReader",
    "FoFFinder",
    "MergerTreeBuilder",
    "Snapshot",
    "Halo",
    "MergerTreeNode",
    "EllipsoidalShape",
    "EllipsoidalFitter",
    "SubstructureFinder",
    "GravityModel",
    "FR_Parameters",
    "HaloStatistics",
    "ModelComparison",
    "ModifiedGravityInterface",
    "compute_mean_interparticle_spacing",
    "periodic_distance",
    "compute_mass_function",
    "compute_mass_function_adaptive",
    "compute_subhalo_mass_function",
    "compute_spin_parameter_distribution",
    "compute_formation_redshift_distribution",
    "filter_halos_by_mass",
    "filter_halos_by_redshift",
    "get_merger_history",
    "save_halo_catalog",
    "load_halo_catalog",
    "save_merger_history",
    "plot_merger_tree",
    "plot_mass_function",
    "plot_spin_distribution",
    "plot_formation_redshift_distribution",
    "save_merger_tree_graphviz",
    "create_summary_plots",
]
