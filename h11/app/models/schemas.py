from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Dict, Any, Union
from enum import Enum


class WaveType(str, Enum):
    SH = "sh"
    PSV = "psv"


class LatticeType(str, Enum):
    SQUARE = "square"
    RECTANGULAR = "rectangular"
    HEXAGONAL = "hexagonal"
    TRIANGULAR = "triangular"


class ShapeType(str, Enum):
    CIRCLE = "circle"
    SQUARE = "square"


class LossModel(str, Enum):
    VISCOUS = "viscous"
    HYSTERETIC = "hysteretic"
    RAYLEIGH = "rayleigh"


class MaterialProperty(BaseModel):
    name: str
    density: float = Field(..., gt=0, description="Density in kg/m³")
    sound_velocity_longitudinal: float = Field(..., gt=0, description="Longitudinal sound velocity in m/s")
    sound_velocity_shear: float = Field(0.0, ge=0, description="Shear sound velocity in m/s")
    description: Optional[str] = None
    loss_factor: Optional[float] = Field(None, ge=0, description="Loss factor for dissipative materials")
    loss_factor_longitudinal: Optional[float] = Field(None, ge=0, description="Longitudinal loss factor")
    loss_factor_shear: Optional[float] = Field(None, ge=0, description="Shear loss factor")
    loss_model: Optional[LossModel] = Field(None, description="Loss model for complex velocity calculation")


class ScattererConfig(BaseModel):
    shape: ShapeType
    position: Tuple[float, float] = Field(..., description="(x, y) position in meters")
    size: float = Field(..., gt=0, description="Radius for circle, side length for square")
    material: str = Field(..., description="Material name from database or inline properties")
    material_properties: Optional[MaterialProperty] = None


class UnitCellConfig(BaseModel):
    size: Tuple[float, float] = Field(..., description="(lx, ly) unit cell dimensions in meters")
    lattice_type: LatticeType = LatticeType.SQUARE
    background_material: str = Field(..., description="Background material name")
    background_material_properties: Optional[MaterialProperty] = None
    scatterers: List[ScattererConfig] = Field(default_factory=list)
    mesh_resolution: float = Field(0.1, gt=0.01, description="Maximum triangle area")
    wave_type: WaveType = WaveType.SH
    n_bands: int = Field(10, gt=0, le=100, description="Number of bands to compute")
    n_k_points: int = Field(50, gt=5, description="Number of k-points per segment")


class BandStructureRequest(BaseModel):
    unit_cell: UnitCellConfig
    compute_dos: bool = True
    compute_group_velocity: bool = True
    dos_broadening: float = Field(0.01, gt=0, description="DOS broadening parameter")
    dos_n_bins: int = Field(100, gt=10, description="Number of DOS frequency bins")


class BandPoint(BaseModel):
    kx: float
    ky: float
    cumulative_distance: float
    frequencies: List[float]


class BandStructureResponse(BaseModel):
    band_points: List[BandPoint]
    high_symmetry_labels: Dict[str, float]
    group_velocities: Optional[List[List[float]]] = None
    dos: Optional[Dict[str, List[float]]] = None
    band_gaps: Optional[List[Tuple[float, float]]] = None
    n_bands: int
    wave_type: str
    mesh_info: Dict[str, Any]


class TransmissionLayerConfig(BaseModel):
    thickness: float = Field(..., gt=0, description="Layer thickness in meters")
    material: str = Field(..., description="Material name")
    material_properties: Optional[MaterialProperty] = None


class TransmissionRequest(BaseModel):
    unit_cell_layers: List[TransmissionLayerConfig]
    n_periods: int = Field(5, gt=0, description="Number of unit cell repetitions")
    frequency_range: Tuple[float, float] = Field(..., description="(f_min, f_max) in Hz")
    n_frequencies: int = Field(200, gt=10, description="Number of frequency points")
    incident_material: str = "Air"
    transmitted_material: Optional[str] = None
    wave_type: WaveType = WaveType.SH
    incident_material_properties: Optional[MaterialProperty] = None
    transmitted_material_properties: Optional[MaterialProperty] = None


class TransmissionResponse(BaseModel):
    frequencies: List[float]
    transmission_coefficients: List[float]
    reflection_coefficients: List[float]
    transmission_loss_db: List[float]
    n_periods: int
    n_layers: int
    wave_type: str


class MaterialResponse(BaseModel):
    name: str
    density: float
    sound_velocity_longitudinal: float
    sound_velocity_shear: float
    description: Optional[str] = None


class MaterialListResponse(BaseModel):
    materials: List[MaterialResponse]


class MeshInfoResponse(BaseModel):
    n_nodes: int
    n_elements: int
    n_boundary_nodes: Dict[str, int]
    material_regions: Dict[str, int]


class TopologicalAnalysisRequest(BaseModel):
    unit_cell: UnitCellConfig
    compute_wilson_loop: bool = Field(True, description="Compute Wilson loop spectrum")
    n_phi_wilson: int = Field(15, gt=3, le=50, description="Number of phi angles for Wilson loop")
    max_bands: int = Field(10, gt=1, le=50, description="Maximum number of bands to analyze")
    zak_phase_threshold: float = Field(1.5708, gt=0, description="Threshold for topological classification (default: pi/2)")


class EdgeStatePrediction(BaseModel):
    gap_index: int
    prediction: str
    zak_phase_jump: float


class WilsonLoopData(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    phi_values: List[float]
    eigenvalues: List[List[float]]
    eigenvalues_imag: List[List[float]]
    phases: List[List[float]]
    band_subset: List[int]


class TopologicalAnalysisResponse(BaseModel):
    zak_phases: List[float]
    band_topology: List[str]
    edge_state_predictions: List[EdgeStatePrediction]
    topological_gap_indices: List[int]
    wilson_loop: Optional[WilsonLoopData] = None
    wilson_winding_numbers: Optional[List[float]] = None
    chern_numbers: Optional[List[int]] = None
    band_structure_info: Optional[BandStructureResponse] = None


class HomogenizationRequest(BaseModel):
    unit_cell: UnitCellConfig
    method: str = Field("voigt", description="Homogenization method: voigt, reuss, hashin_shtrikman, asymptotic")
    compute_field_data: bool = Field(False, description="Compute and return cell-level fields")


class HomogenizationResponse(BaseModel):
    effective_density_matrix: List[List[float]]
    effective_modulus_tensor: List[List[float]]
    effective_density_scalar: float
    effective_bulk_modulus: float
    effective_shear_modulus: float
    effective_velocity_longitudinal: float
    effective_velocity_shear: float
    volume_fractions: Dict[str, float]
    method: str
    voigt_bounds: Optional[Dict[str, float]] = None
    reuss_bounds: Optional[Dict[str, float]] = None
    hashin_shtrikman_bounds: Optional[Dict[str, Any]] = None


class ComplexBandStructureRequest(BaseModel):
    unit_cell: UnitCellConfig
    include_loss: bool = Field(True, description="Include material loss in calculation")
    compute_dos: bool = Field(True, description="Compute density of states")
    compute_group_velocity: bool = Field(True, description="Compute group velocity")


class ComplexBandPoint(BaseModel):
    kx: float
    ky: float
    cumulative_distance: float
    real_frequencies: List[float]
    imaginary_frequencies: List[float]
    attenuation_db_per_m: List[float]
    phase_velocity: List[float]
    quality_factors: Optional[List[float]] = None


class ComplexBandStructureResponse(BaseModel):
    band_points: List[ComplexBandPoint]
    high_symmetry_labels: Dict[str, float]
    group_velocities: Optional[List[List[float]]] = None
    dos: Optional[Dict[str, List[float]]] = None
    band_gaps: Optional[List[Tuple[float, float]]] = None
    n_bands: int
    wave_type: str
    has_loss: bool
    loss_model: Optional[str] = None
    mesh_info: Dict[str, Any]
