from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Tuple
from app.models import MaterialResponse, MaterialListResponse, MaterialProperty
from app.db import MaterialDatabase

router = APIRouter(prefix="/materials", tags=["materials"])

db_instance = None


def get_db():
    global db_instance
    if db_instance is None:
        db_instance = MaterialDatabase()
        if not db_instance.connect():
            raise HTTPException(status_code=503, detail="Could not connect to MongoDB")
        db_instance.initialize_default_materials()
    return db_instance


@router.get("", response_model=MaterialListResponse)
def get_all_materials(db: MaterialDatabase = Depends(get_db)):
    materials = db.get_all_materials()
    return MaterialListResponse(
        materials=[MaterialResponse(**m) for m in materials]
    )


@router.get("/{name}", response_model=MaterialResponse)
def get_material(name: str, db: MaterialDatabase = Depends(get_db)):
    material = db.get_material(name)
    if material is None:
        raise HTTPException(status_code=404, detail=f"Material '{name}' not found")
    return MaterialResponse(**material)


@router.post("", response_model=MaterialResponse)
def add_material(material: MaterialProperty, db: MaterialDatabase = Depends(get_db)):
    material_id = db.add_material(
        name=material.name,
        density=material.density,
        sound_velocity_longitudinal=material.sound_velocity_longitudinal,
        sound_velocity_shear=material.sound_velocity_shear,
        description=material.description or ""
    )
    if material_id is None:
        raise HTTPException(status_code=500, detail="Failed to add material")
    return material


@router.delete("/{name}")
def delete_material(name: str, db: MaterialDatabase = Depends(get_db)):
    if not db.delete_material(name):
        raise HTTPException(status_code=404, detail=f"Material '{name}' not found")
    return {"message": f"Material '{name}' deleted successfully"}


@router.get("/search/by-properties", response_model=MaterialListResponse)
def find_materials_by_properties(
    density_min: Optional[float] = Query(None, ge=0, description="Minimum density in kg/m³"),
    density_max: Optional[float] = Query(None, ge=0, description="Maximum density in kg/m³"),
    velocity_min: Optional[float] = Query(None, ge=0, description="Minimum longitudinal velocity in m/s"),
    velocity_max: Optional[float] = Query(None, ge=0, description="Maximum longitudinal velocity in m/s"),
    limit: int = Query(100, ge=1, le=1000),
    db: MaterialDatabase = Depends(get_db)
):
    density_range = (density_min, density_max) if density_min is not None and density_max is not None else None
    velocity_range = (velocity_min, velocity_max) if velocity_min is not None and velocity_max is not None else None

    materials = db.find_materials_by_properties(density_range, velocity_range, limit)
    return MaterialListResponse(
        materials=[MaterialResponse(**m) for m in materials]
    )


@router.get("/indexes/info")
def get_index_info(db: MaterialDatabase = Depends(get_db)):
    if db.collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    indexes = db.collection.index_information()
    return {
        "indexes": indexes,
        "compound_indexes": [
            {
                "name": idx_name,
                "fields": idx_info["key"],
                "unique": idx_info.get("unique", False),
                "sparse": idx_info.get("sparse", False)
            }
            for idx_name, idx_info in indexes.items()
            if len(idx_info["key"]) > 1
        ]
    }
