from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict
import numpy as np

from app.models import (
    TransmissionRequest, TransmissionResponse,
    TransmissionLayerConfig, MaterialProperty
)
from app.core import (
    Layer, compute_transmission_spectrum, generate_1d_phononic_crystal
)
from app.db import MaterialDatabase

router = APIRouter(prefix="/transmission", tags=["transmission"])

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


@router.post("", response_model=TransmissionResponse)
def calculate_transmission(request: TransmissionRequest, db: MaterialDatabase = Depends(get_db)):
    try:
        unit_cell_layers = []
        for layer_cfg in request.unit_cell_layers:
            mat = resolve_material(layer_cfg.material, layer_cfg.material_properties, db)
            unit_cell_layers.append(Layer(
                thickness=layer_cfg.thickness,
                material=mat
            ))

        crystal_layers = generate_1d_phononic_crystal(
            unit_cell_layers, request.n_periods
        )

        incident_mat = resolve_material(
            request.incident_material, request.incident_material_properties, db
        )

        if request.transmitted_material:
            transmitted_mat = resolve_material(
                request.transmitted_material, request.transmitted_material_properties, db
            )
        else:
            transmitted_mat = incident_mat

        if request.wave_type.value == 'sh':
            wave_type_tmm = 'longitudinal'
        else:
            wave_type_tmm = 'longitudinal'

        spectrum = compute_transmission_spectrum(
            frequency_range=tuple(request.frequency_range),
            n_frequencies=request.n_frequencies,
            layers=crystal_layers,
            incident_material=incident_mat,
            transmitted_material=transmitted_mat,
            wave_type=wave_type_tmm
        )

        return TransmissionResponse(
            frequencies=[float(f) for f in spectrum['frequencies']],
            transmission_coefficients=[float(t) for t in spectrum['transmission_coefficients']],
            reflection_coefficients=[float(r) for r in spectrum['reflection_coefficients']],
            transmission_loss_db=[float(l) for l in spectrum['transmission_loss_db']],
            n_periods=request.n_periods,
            n_layers=spectrum['n_layers'],
            wave_type=request.wave_type.value
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Transmission calculation failed: {str(e)}"
        )
