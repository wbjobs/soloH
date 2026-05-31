from .mesh_generator import Scatterer, UnitCell, generate_mesh, get_boundary_nodes
from .fem_assembly import assemble_global_matrices, apply_bloch_boundary_conditions, compute_lame_parameters
from .brillouin_zone import generate_brillouin_zone_path, get_brillouin_zone_boundary
from .eigenvalue_solver import (
    solve_generalized_eigenproblem, solve_band_structure,
    compute_group_velocity, compute_dos, find_band_gaps
)
from .transfer_matrix import (
    Layer, compute_transmission_coefficient, compute_transmission_spectrum,
    generate_1d_phononic_crystal, compute_band_structure_1d
)
