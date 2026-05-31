from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, List, Tuple, Optional, Any
import numpy as np

from app.models.schemas import (
    TopologicalAnalysisRequest,
    TopologicalAnalysisResponse,
    EdgeStatePrediction,
    WilsonLoopData,
    HomogenizationRequest,
    HomogenizationResponse,
    ComplexBandStructureRequest,
    ComplexBandStructureResponse,
    ComplexBandPoint,
    UnitCellConfig,
    BandStructureResponse,
    BandPoint,
    MaterialProperty
)
from app.core.brillouin_zone import generate_brillouin_zone_path
from app.core.mesh_generator import generate_mesh, UnitCell, Scatterer
from app.core.fem_assembly import (
    assemble_global_matrices,
    convert_material_to_complex
)
from app.core.eigenvalue_solver import (
    solve_band_structure,
    compute_group_velocity,
    compute_dos
)
from app.core.topological_analysis import (
    compute_full_topological_analysis,
    compute_zak_phases_for_bands,
    compute_wilson_loop_spectrum,
    extract_topological_invariants
)
from app.core.homogenization import (
    solve_homogenization_problem,
    compute_effective_properties_simple,
    compute_volume_fractions,
    compute_voigt_average,
    compute_reuss_average,
    compute_hashin_shtrikman_bounds
)
from app.db.material_db import MaterialDatabase
from app.dependencies import get_db

router = APIRouter(prefix="/api/v1/advanced", tags=["advanced"])


def resolve_materials(unit_cell: UnitCellConfig, db: Optional[MaterialDatabase]) -> List[Dict]:
    materials = {}

    bg_mat = unit_cell.background_material_properties
    if bg_mat is None and db is not None:
        bg_mat_data = db.get_material(unit_cell.background_material)
        if bg_mat_data:
            bg_mat = MaterialProperty(**bg_mat_data)

    if bg_mat is not None:
        materials['background'] = bg_mat.model_dump()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Background material '{unit_cell.background_material}' not found in database or inline properties"
        )

    for i, scatterer in enumerate(unit_cell.scatterers):
        scat_mat = scatterer.material_properties
        if scat_mat is None and db is not None:
            scat_mat_data = db.get_material(scatterer.material)
            if scat_mat_data:
                scat_mat = MaterialProperty(**scat_mat_data)

        if scat_mat is not None:
            materials[f'scatterer_{i}'] = scat_mat.model_dump()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scatterer material '{scatterer.material}' not found in database or inline properties"
            )

    return list(materials.values())


def prepare_mesh_and_matrices(unit_cell: UnitCellConfig, materials: List[Dict],
                               convert_to_complex: bool = False):
    scatterers = []
    for scat in unit_cell.scatterers:
        scatterers.append(Scatterer(
            shape=scat.shape.value,
            position=scat.position,
            size=scat.size,
            material=scat.material
        ))

    uc = UnitCell(
        size=unit_cell.size,
        scatterers=scatterers,
        background_material=unit_cell.background_material,
        mesh_resolution=unit_cell.mesh_resolution
    )

    if convert_to_complex:
        materials_complex = []
        for mat in materials:
            try:
                mat_c = convert_material_to_complex(mat)
                materials_complex.append(mat_c)
            except Exception:
                materials_complex.append(mat)
        materials = materials_complex

    mesh = generate_mesh(uc)
    vertices = mesh['vertices']

    eps = 1e-6
    min_x, max_x = vertices[:, 0].min(), vertices[:, 0].max()
    min_y, max_y = vertices[:, 1].min(), vertices[:, 1].max()

    x_left = np.where(np.abs(vertices[:, 0] - min_x) < eps)[0]
    x_right = np.where(np.abs(vertices[:, 0] - max_x) < eps)[0]
    y_bottom = np.where(np.abs(vertices[:, 1] - min_y) < eps)[0]
    y_top = np.where(np.abs(vertices[:, 1] - max_y) < eps)[0]

    paired_x = [(int(ln), int(rn)) for ln, rn in zip(x_left, x_right)]
    paired_y = [(int(bn), int(tn)) for bn, tn in zip(y_bottom, y_top)]

    boundary_nodes = set(list(x_left) + list(x_right) + list(y_bottom) + list(y_top))
    interior_nodes = [i for i in range(len(vertices)) if i not in boundary_nodes]

    boundary_info = {
        'paired_x': paired_x,
        'paired_y': paired_y,
        'interior_nodes': interior_nodes,
        'n_boundary_nodes': len(boundary_nodes)
    }

    has_complex = any(
        isinstance(m.get('density'), complex) or
        isinstance(m.get('sound_velocity_longitudinal'), complex) or
        isinstance(m.get('sound_velocity_shear'), complex)
        for m in materials
    )

    K, M = assemble_global_matrices(
        mesh=mesh,
        material_properties=materials,
        wave_type=unit_cell.wave_type.value,
        has_complex_materials=has_complex
    )

    return mesh, boundary_info, K, M, materials


def compute_band_gaps(frequencies: np.ndarray, threshold_ratio: float = 0.01) -> List[Tuple[float, float]]:
    if frequencies is None or len(frequencies) == 0:
        return []

    if np.iscomplexobj(frequencies):
        freqs = np.real(frequencies)
    else:
        freqs = frequencies.copy()

    freqs = freqs[~np.isnan(freqs)]
    if len(freqs) < 4:
        return []

    n_k, n_bands = frequencies.shape
    gaps = []

    for band in range(n_bands - 1):
        band_upper = frequencies[:, band]
        band_lower = frequencies[:, band + 1]

        max_upper = np.nanmax(band_upper)
        min_lower = np.nanmin(band_lower)

        if min_lower > max_upper * (1 + threshold_ratio):
            gaps.append((float(max_upper), float(min_lower)))

    return gaps


@router.post("/topological-analysis", response_model=TopologicalAnalysisResponse)
async def topological_analysis(
    request: TopologicalAnalysisRequest,
    db: Optional[MaterialDatabase] = Depends(get_db)
):
    try:
        uc = request.unit_cell

        materials = resolve_materials(uc, db)

        mesh, boundary_info, K, M, _ = prepare_mesh_and_matrices(uc, materials)

        bz = generate_brillouin_zone_path(
            lattice=uc.lattice_type.value,
            lattice_constant=uc.size[0],
            n_points_per_segment=uc.n_k_points,
            ensure_symmetry=True
        )

        band_result = solve_band_structure(
            K=K, M=M,
            k_points=bz['k_points'],
            boundary_info=boundary_info,
            unit_cell_size=uc.size,
            wave_type=uc.wave_type.value,
            n_bands=min(uc.n_bands, request.max_bands + 2),
            has_loss=False
        )

        topo_result = compute_full_topological_analysis(
            band_structure=band_result,
            boundary_info=boundary_info,
            unit_cell_size=uc.size,
            brillouin_zone=bz,
            compute_wilson=request.compute_wilson_loop,
            n_phi=request.n_phi_wilson,
            max_bands=request.max_bands
        )

        edge_predictions = [
            EdgeStatePrediction(**p)
            for p in topo_result['edge_state_predictions']
        ]

        wilson_data = None
        if 'wilson_loop' in topo_result:
            wl = topo_result['wilson_loop']
            eigvals = np.array(wl['eigenvalues'])
            wilson_data = WilsonLoopData(
                phi_values=wl['phi_values'],
                eigenvalues=np.real(eigvals).tolist(),
                eigenvalues_imag=np.imag(eigvals).tolist(),
                phases=wl['phases'],
                band_subset=wl['band_subset']
            )

        group_vel = None
        if request.compute_wilson_loop:
            try:
                group_vel = compute_group_velocity(band_result, bz).tolist()
            except Exception:
                pass

        dos_result = None
        try:
            if 'real_frequencies' in band_result:
                dos_result = compute_dos(band_result['real_frequencies'])
            else:
                dos_result = compute_dos(band_result['frequencies'])
        except Exception:
            pass

        band_points = []
        cumulative_dist = bz['cumulative_dist']
        for i, k in enumerate(bz['k_points']):
            freqs = band_result['frequencies'][i, :]
            if np.iscomplexobj(freqs):
                freqs = np.real(freqs)
            band_points.append(BandPoint(
                kx=float(k[0]),
                ky=float(k[1]),
                cumulative_distance=float(cumulative_dist[i]),
                frequencies=freqs.tolist()
            ))

        band_gaps = compute_band_gaps(band_result['frequencies'])

        mesh_info = {
            'n_nodes': len(mesh['vertices']),
            'n_elements': len(mesh['triangles']),
            'n_boundary_nodes': boundary_info.get('n_boundary_nodes', 0)
        }

        band_structure_info = BandStructureResponse(
            band_points=band_points,
            high_symmetry_labels={str(k): float(v) for k, v in bz['label_positions'].items()},
            group_velocities=group_vel,
            dos=dos_result,
            band_gaps=band_gaps,
            n_bands=uc.n_bands,
            wave_type=uc.wave_type.value,
            mesh_info=mesh_info
        )

        return TopologicalAnalysisResponse(
            zak_phases=topo_result['zak_phases'].tolist(),
            band_topology=topo_result['band_topology'],
            edge_state_predictions=edge_predictions,
            topological_gap_indices=topo_result['topological_gap_indices'],
            wilson_loop=wilson_data,
            wilson_winding_numbers=topo_result.get('wilson_winding_numbers'),
            chern_numbers=topo_result.get('chern_numbers'),
            band_structure_info=band_structure_info
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Topological analysis failed: {str(e)}"
        ) from e


@router.post("/homogenization", response_model=HomogenizationResponse)
async def homogenization_analysis(
    request: HomogenizationRequest,
    db: Optional[MaterialDatabase] = Depends(get_db)
):
    try:
        uc = request.unit_cell

        materials = resolve_materials(uc, db)

        scatterer_configs = []
        for i, scat in enumerate(uc.scatterers):
            scatterer_configs.append({
                'shape': scat.shape.value,
                'position': scat.position,
                'size': scat.size,
                'material_id': i + 1
            })

        mesh, boundary_info = generate_unit_cell_mesh(
            unit_cell_size=uc.size,
            scatterers=scatterer_configs,
            max_area=uc.mesh_resolution
        )

        volume_fractions = compute_volume_fractions(mesh, materials)

        simple_props = compute_effective_properties_simple(volume_fractions, materials)

        if request.method.lower() == 'simple' or request.method.lower() == 'voigt':
            C_eff = compute_voigt_average(volume_fractions, materials)
        elif request.method.lower() == 'reuss':
            C_eff = compute_reuss_average(volume_fractions, materials)
        elif request.method.lower() == 'hashin_shtrikman':
            hs_bounds = compute_hashin_shtrikman_bounds(volume_fractions, materials)
            C_eff = 0.5 * (hs_bounds['lower'] + hs_bounds['upper'])
        else:
            try:
                result = solve_homogenization_problem(
                    mesh=mesh,
                    material_properties=materials,
                    boundary_info=boundary_info,
                    unit_cell_size=uc.size,
                    wave_type=uc.wave_type.value,
                    method=request.method
                )
                C_eff = result.effective_modulus
                volume_fractions = result.volume_fractions
            except Exception as e:
                print(f"Asymptotic homogenization failed, using Voigt: {e}")
                C_eff = compute_voigt_average(volume_fractions, materials)

        rho_eff = simple_props['effective_density']
        rho_matrix = [
            [rho_eff, 0.0],
            [0.0, rho_eff]
        ]

        C11 = float(np.real(C_eff[0, 0]))
        C12 = float(np.real(C_eff[0, 1]))
        C44 = float(np.real(C_eff[2, 2]))

        K_eff = (C11 + 2 * C12) / 3
        mu_eff = C44

        if rho_eff > 0:
            v_l = np.sqrt((K_eff + 4 * mu_eff / 3) / rho_eff)
            v_s = np.sqrt(mu_eff / rho_eff)
        else:
            v_l = 0.0
            v_s = 0.0

        modulus_tensor = [
            [float(np.real(C_eff[0, 0])), float(np.real(C_eff[0, 1])), float(np.real(C_eff[0, 2]))],
            [float(np.real(C_eff[1, 0])), float(np.real(C_eff[1, 1])), float(np.real(C_eff[1, 2]))],
            [float(np.real(C_eff[2, 0])), float(np.real(C_eff[2, 1])), float(np.real(C_eff[2, 2]))]
        ]

        hs_bounds_serializable = None
        try:
            hs = compute_hashin_shtrikman_bounds(volume_fractions, materials)
            hs_bounds_serializable = {
                'lower_modulus_tensor': [[float(np.real(v)) for v in row] for row in hs['lower']],
                'upper_modulus_tensor': [[float(np.real(v)) for v in row] for row in hs['upper']]
            }
        except Exception:
            pass

        return HomogenizationResponse(
            effective_density_matrix=rho_matrix,
            effective_modulus_tensor=modulus_tensor,
            effective_density_scalar=float(rho_eff),
            effective_bulk_modulus=float(K_eff),
            effective_shear_modulus=float(mu_eff),
            effective_velocity_longitudinal=float(v_l),
            effective_velocity_shear=float(v_s),
            volume_fractions={k: float(v) for k, v in volume_fractions.items()},
            method=request.method,
            voigt_bounds={
                'velocity_longitudinal': simple_props['effective_velocity_longitudinal_voigt'],
                'velocity_shear': simple_props['effective_velocity_shear_voigt'],
                'bulk_modulus': simple_props['effective_bulk_modulus_voigt'],
                'shear_modulus': simple_props['effective_shear_modulus_voigt']
            },
            reuss_bounds={
                'velocity_longitudinal': simple_props['effective_velocity_longitudinal_reuss'],
                'velocity_shear': simple_props['effective_velocity_shear_reuss'],
                'bulk_modulus': simple_props['effective_bulk_modulus_reuss'],
                'shear_modulus': simple_props['effective_shear_modulus_reuss']
            },
            hashin_shtrikman_bounds=hs_bounds_serializable
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Homogenization analysis failed: {str(e)}"
        ) from e


@router.post("/complex-band-structure", response_model=ComplexBandStructureResponse)
async def complex_band_structure(
    request: ComplexBandStructureRequest,
    db: Optional[MaterialDatabase] = Depends(get_db)
):
    try:
        uc = request.unit_cell

        materials = resolve_materials(uc, db)

        has_any_loss = any(
            m.get('loss_factor') is not None or
            m.get('loss_factor_longitudinal') is not None or
            m.get('loss_factor_shear') is not None
            for m in materials
        )

        if not request.include_loss and not has_any_loss:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No loss parameters provided. Set include_loss=True and provide loss_factor in material properties."
            )

        loss_model = None
        for m in materials:
            if m.get('loss_model'):
                loss_model = m.get('loss_model')
                break

        mesh, boundary_info, K, M, materials_with_loss = prepare_mesh_and_matrices(
            uc, materials, convert_to_complex=request.include_loss
        )

        bz = generate_brillouin_zone_path(
            lattice=uc.lattice_type.value,
            lattice_constant=uc.size[0],
            n_points_per_segment=uc.n_k_points,
            ensure_symmetry=True
        )

        band_result = solve_band_structure(
            K=K, M=M,
            k_points=bz['k_points'],
            boundary_info=boundary_info,
            unit_cell_size=uc.size,
            wave_type=uc.wave_type.value,
            n_bands=uc.n_bands,
            has_loss=request.include_loss
        )

        cumulative_dist = bz['cumulative_dist']
        band_points = []

        real_freqs = band_result.get('real_frequencies', band_result['frequencies'])
        imag_freqs = np.imag(band_result['frequencies']) if band_result.get('has_loss') else np.zeros_like(real_freqs)
        attenuation = band_result.get('attenuation', np.zeros_like(real_freqs))

        for i, k in enumerate(bz['k_points']):
            real_f = real_freqs[i, :].tolist() if not np.isnan(real_freqs[i, :]).all() else [0.0] * uc.n_bands
            imag_f = imag_freqs[i, :].tolist() if not np.isnan(imag_freqs[i, :]).all() else [0.0] * uc.n_bands
            att = attenuation[i, :].tolist() if not np.isnan(attenuation[i, :]).all() else [0.0] * uc.n_bands

            phase_vel = []
            q_factors = []
            for rf, imf in zip(real_f, imag_f):
                pv = 2 * np.pi * rf if rf > 0 else 0.0
                phase_vel.append(float(pv))
                if abs(imf) > 1e-15 and abs(rf) > 1e-15:
                    q_factors.append(float(abs(rf) / (2 * abs(imf))))
                else:
                    q_factors.append(None)

            band_points.append(ComplexBandPoint(
                kx=float(k[0]),
                ky=float(k[1]),
                cumulative_distance=float(cumulative_dist[i]),
                real_frequencies=real_f,
                imaginary_frequencies=imag_f,
                attenuation_db_per_m=att,
                phase_velocity=phase_vel,
                quality_factors=q_factors if any(q is not None for q in q_factors) else None
            ))

        group_vel = None
        if request.compute_group_velocity:
            try:
                if band_result.get('has_loss'):
                    gv = compute_group_velocity(band_result, bz)
                    group_vel = np.real(gv).tolist()
                else:
                    gv = compute_group_velocity(band_result, bz)
                    group_vel = gv.tolist()
            except Exception:
                pass

        dos_result = None
        if request.compute_dos:
            try:
                dos_result = compute_dos(real_freqs)
            except Exception:
                pass

        band_gaps = compute_band_gaps(real_freqs)

        mesh_info = {
            'n_nodes': len(mesh['vertices']),
            'n_elements': len(mesh['triangles']),
            'n_boundary_nodes': boundary_info.get('n_boundary_nodes', 0)
        }

        return ComplexBandStructureResponse(
            band_points=band_points,
            high_symmetry_labels={str(k): float(v) for k, v in bz['label_positions'].items()},
            group_velocities=group_vel,
            dos=dos_result,
            band_gaps=band_gaps,
            n_bands=uc.n_bands,
            wave_type=uc.wave_type.value,
            has_loss=band_result.get('has_loss', False),
            loss_model=loss_model,
            mesh_info=mesh_info
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Complex band structure calculation failed: {str(e)}"
        ) from e
