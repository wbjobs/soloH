from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Tuple, Optional
import numpy as np

from app.models import (
    BandStructureRequest, BandStructureResponse, BandPoint,
    MaterialProperty
)
from app.core import (
    Scatterer, UnitCell, generate_mesh, get_boundary_nodes,
    assemble_global_matrices, generate_brillouin_zone_path,
    solve_band_structure, compute_group_velocity, compute_dos, find_band_gaps
)
from app.db import MaterialDatabase

router = APIRouter(prefix="/band-structure", tags=["band-structure"])

db_instance = None


def get_db():
    global db_instance
    if db_instance is None:
        db_instance = MaterialDatabase()
        db_instance.connect()
    return db_instance


def resolve_material(material_name: str, material_props: Optional[MaterialProperty],
                      db: MaterialDatabase) -> Dict:
    if material_props is not None:
        return {
            'density': material_props.density,
            'sound_velocity_longitudinal': material_props.sound_velocity_longitudinal,
            'sound_velocity_shear': material_props.sound_velocity_shear,
            'name': material_props.name
        }

    if db.client is not None and db.collection is not None:
        mat = db.get_material(material_name)
        if mat is not None:
            return {
                'density': mat['density'],
                'sound_velocity_longitudinal': mat['sound_velocity_longitudinal'],
                'sound_velocity_shear': mat['sound_velocity_shear'],
                'name': mat['name']
            }

    raise HTTPException(
        status_code=404,
        detail=f"Material '{material_name}' not found in database and no inline properties provided"
    )


@router.post("", response_model=BandStructureResponse)
def calculate_band_structure(request: BandStructureRequest, db: MaterialDatabase = Depends(get_db)):
    uc = request.unit_cell

    try:
        scatterers = []
        material_properties_list = []

        bg_mat = resolve_material(uc.background_material, uc.background_material_properties, db)
        material_properties_list.append(bg_mat)

        for scat_cfg in uc.scatterers:
            scat_mat = resolve_material(scat_cfg.material, scat_cfg.material_properties, db)

            mat_idx = next(
                (i for i, m in enumerate(material_properties_list)
                 if m['name'] == scat_mat['name']),
                None
            )
            if mat_idx is None:
                material_properties_list.append(scat_mat)
                mat_idx = len(material_properties_list) - 1

            scatterers.append(Scatterer(
                shape=scat_cfg.shape.value,
                position=tuple(scat_cfg.position),
                size=scat_cfg.size,
                material=scat_mat['name']
            ))

        unit_cell = UnitCell(
            size=tuple(uc.size),
            scatterers=scatterers,
            background_material=bg_mat['name'],
            mesh_resolution=uc.mesh_resolution
        )

        mesh = generate_mesh(unit_cell)

        boundary_info = get_boundary_nodes(mesh, unit_cell)

        K, M = assemble_global_matrices(
            mesh, material_properties_list, wave_type=uc.wave_type.value
        )

        lattice_constant = max(uc.size)
        bz = generate_brillouin_zone_path(
            lattice=uc.lattice_type.value,
            lattice_constant=lattice_constant,
            n_points_per_segment=uc.n_k_points,
            ensure_symmetry=True
        )

        band_structure = solve_band_structure(
            K, M, bz['k_points'], boundary_info,
            unit_cell.size, uc.wave_type.value, uc.n_bands
        )

        band_points = []
        for i, k in enumerate(band_structure['k_points']):
            freqs = band_structure['frequencies'][i]
            if np.iscomplexobj(freqs):
                freqs = np.real(freqs)
            freqs = [float(f) if not np.isnan(f) else 0.0 for f in freqs]
            band_points.append(BandPoint(
                kx=float(k[0]),
                ky=float(k[1]),
                cumulative_distance=float(bz['cumulative_dist'][i]),
                frequencies=freqs
            ))

        high_sym_labels = {}
        for idx, label in bz['label_positions'].items():
            if idx < len(bz['cumulative_dist']):
                high_sym_labels[label] = float(bz['cumulative_dist'][idx])

        result = {
            'band_points': band_points,
            'high_symmetry_labels': high_sym_labels,
            'n_bands': uc.n_bands,
            'wave_type': uc.wave_type.value,
            'mesh_info': {
                'n_nodes': int(mesh['vertices'].shape[0]),
                'n_elements': int(mesh['triangles'].shape[0]),
                'n_interior_nodes': int(len(boundary_info['interior_nodes'])),
                'material_regions': {
                    f'region_{i}': int(np.sum(mesh['materials'] == i))
                    for i in np.unique(mesh['materials'])
                }
            }
        }

        if request.compute_group_velocity:
            v_g = compute_group_velocity(band_structure, bz)
            result['group_velocities'] = [
                [float(v) for v in row] for row in v_g
            ]

        if request.compute_dos:
            dos = compute_dos(
                band_structure['frequencies'],
                n_bins=request.dos_n_bins,
                broadening=request.dos_broadening
            )
            result['dos'] = {
                'frequencies': [float(f) for f in dos['frequencies']],
                'values': [float(d) for d in dos['dos']]
            }

        band_gaps = find_band_gaps(band_structure['frequencies'])
        result['band_gaps'] = [(float(g1), float(g2)) for g1, g2 in band_gaps]

        return BandStructureResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Band structure calculation failed: {str(e)}"
        )
