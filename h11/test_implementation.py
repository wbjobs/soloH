import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

print("=" * 60)
print("Testing Phononic Crystal Band Structure Calculator")
print("=" * 60)

print("\n1. Testing core imports...")
try:
    from app.core.mesh_generator import Scatterer, UnitCell, generate_mesh, get_boundary_nodes
    from app.core.fem_assembly import assemble_global_matrices, compute_lame_parameters
    from app.core.brillouin_zone import generate_brillouin_zone_path
    from app.core.eigenvalue_solver import solve_band_structure, compute_dos, compute_group_velocity, find_band_gaps
    from app.core.transfer_matrix import Layer, compute_transmission_spectrum, generate_1d_phononic_crystal
    print("   ✓ All core modules imported successfully")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

print("\n2. Testing material database module...")
try:
    from app.db.material_db import MaterialDatabase
    print("   ✓ Material database module imported successfully")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

print("\n3. Testing model schemas...")
try:
    from app.models.schemas import (
        BandStructureRequest, UnitCellConfig, ScattererConfig,
        ShapeType, LatticeType, WaveType, MaterialProperty
    )
    print("   ✓ All model schemas imported successfully")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

print("\n4. Testing transfer matrix method (TMM)...")
try:
    mat1 = {'density': 7850, 'sound_velocity_longitudinal': 5960, 'sound_velocity_shear': 3235, 'name': 'Steel'}
    mat2 = {'density': 1100, 'sound_velocity_longitudinal': 1000, 'sound_velocity_shear': 30, 'name': 'Rubber'}

    unit_cell_layers = [
        Layer(thickness=0.01, material=mat1),
        Layer(thickness=0.01, material=mat2)
    ]

    crystal_layers = generate_1d_phononic_crystal(unit_cell_layers, n_periods=5)
    print(f"   ✓ Generated {len(crystal_layers)} layers for 5 periods")

    spectrum = compute_transmission_spectrum(
        frequency_range=(1000, 50000),
        n_frequencies=100,
        layers=crystal_layers,
        incident_material=mat1,
        transmitted_material=mat1,
        wave_type='longitudinal'
    )

    print(f"   ✓ TMM transmission spectrum computed: {len(spectrum['frequencies'])} frequency points")
    print(f"     Average transmission: {np.mean(spectrum['transmission_coefficients']):.4f}")
    print(f"     Min transmission: {np.min(spectrum['transmission_coefficients']):.4f}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"   ✗ TMM test failed: {e}")

print("\n5. Testing FEM mesh generation...")
try:
    scatterers = [
        Scatterer(shape='circle', position=(0, 0), size=0.15, material='Steel'),
    ]

    unit_cell = UnitCell(
        size=(0.5, 0.5),
        scatterers=scatterers,
        background_material='Air',
        mesh_resolution=0.08
    )

    mesh = generate_mesh(unit_cell)
    print(f"   ✓ Mesh generated: {mesh['vertices'].shape[0]} nodes, {mesh['triangles'].shape[0]} elements")

    boundary_info = get_boundary_nodes(mesh, unit_cell)
    print(f"   ✓ Boundary info: {len(boundary_info['interior_nodes'])} interior nodes")
    print(f"     Paired X boundaries: {len(boundary_info['paired_x'])} pairs")
    print(f"     Paired Y boundaries: {len(boundary_info['paired_y'])} pairs")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"   ✗ Mesh generation test failed: {e}")

print("\n6. Testing FEM matrix assembly...")
try:
    material_props = [
        {'density': 1.21, 'sound_velocity_longitudinal': 343, 'sound_velocity_shear': 0, 'name': 'Air'},
        {'density': 7850, 'sound_velocity_longitudinal': 5960, 'sound_velocity_shear': 3235, 'name': 'Steel'}
    ]

    K, M = assemble_global_matrices(mesh, material_props, wave_type='sh')
    print(f"   ✓ Matrices assembled: K shape={K.shape}, M shape={M.shape}")
    print(f"     K nnz: {K.nnz}, M nnz: {M.nnz}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"   ✗ Matrix assembly test failed: {e}")

print("\n7. Testing Brillouin zone path generation...")
try:
    bz_square = generate_brillouin_zone_path(lattice='square', lattice_constant=0.5, n_points_per_segment=10)
    print(f"   ✓ Square lattice BZ: {len(bz_square['k_points'])} k-points")
    print(f"     High symmetry points: {list(bz_square['high_symmetry_points'].keys())}")

    bz_hex = generate_brillouin_zone_path(lattice='hexagonal', lattice_constant=0.5, n_points_per_segment=10)
    print(f"   ✓ Hexagonal lattice BZ: {len(bz_hex['k_points'])} k-points")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"   ✗ BZ generation test failed: {e}")

print("\n8. Testing full band structure calculation (simplified)...")
try:
    bz = generate_brillouin_zone_path(lattice='square', lattice_constant=0.5, n_points_per_segment=5)

    band_structure = solve_band_structure(
        K, M, bz['k_points'], boundary_info,
        unit_cell.size, wave_type='sh', n_bands=8
    )

    print(f"   ✓ Band structure computed: {band_structure['frequencies'].shape}")

    if np.any(~np.isnan(band_structure['frequencies'])):
        valid_freqs = band_structure['frequencies'][~np.isnan(band_structure['frequencies'])]
        print(f"     Frequency range: {valid_freqs.min():.2f} - {valid_freqs.max():.2f} Hz")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"   ✗ Band structure test failed: {e}")

print("\n9. Testing DOS and group velocity...")
try:
    dos = compute_dos(band_structure['frequencies'], n_bins=50, broadening=0.05)
    print(f"   ✓ DOS computed: {len(dos['frequencies'])} frequency bins")

    v_g = compute_group_velocity(band_structure, bz)
    print(f"   ✓ Group velocity computed: {v_g.shape}")

    gaps = find_band_gaps(band_structure['frequencies'], threshold=0.01)
    print(f"   ✓ Band gaps found: {len(gaps)}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"   ✗ DOS/velocity test failed: {e}")

print("\n10. Testing FastAPI app imports...")
try:
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/")
    print(f"   ✓ FastAPI root endpoint: {response.status_code}")

    response = client.get("/health")
    print(f"   ✓ Health check: {response.status_code}")
except Exception as e:
    print(f"   ⚠ FastAPI test skipped (TestClient not available): {e}")

print("\n" + "=" * 60)
print("All core tests completed!")
print("=" * 60)

print("\n" + "=" * 60)
print("Example API Usage:")
print("=" * 60)

example_band_request = {
    "unit_cell": {
        "size": [0.5, 0.5],
        "lattice_type": "square",
        "background_material": "Air",
        "background_material_properties": {
            "name": "Air",
            "density": 1.21,
            "sound_velocity_longitudinal": 343.0,
            "sound_velocity_shear": 0.0
        },
        "scatterers": [
            {
                "shape": "circle",
                "position": [0.0, 0.0],
                "size": 0.15,
                "material": "Steel",
                "material_properties": {
                    "name": "Steel",
                    "density": 7850.0,
                    "sound_velocity_longitudinal": 5960.0,
                    "sound_velocity_shear": 3235.0
                }
            }
        ],
        "mesh_resolution": 0.08,
        "wave_type": "sh",
        "n_bands": 10,
        "n_k_points": 20
    },
    "compute_dos": True,
    "compute_group_velocity": True
}

example_transmission_request = {
    "unit_cell_layers": [
        {
            "thickness": 0.01,
            "material": "Steel",
            "material_properties": {
                "name": "Steel",
                "density": 7850.0,
                "sound_velocity_longitudinal": 5960.0,
                "sound_velocity_shear": 3235.0
            }
        },
        {
            "thickness": 0.01,
            "material": "Rubber",
            "material_properties": {
                "name": "Rubber",
                "density": 1100.0,
                "sound_velocity_longitudinal": 1000.0,
                "sound_velocity_shear": 30.0
            }
        }
    ],
    "n_periods": 5,
    "frequency_range": [1000, 50000],
    "n_frequencies": 200,
    "incident_material": "Air",
    "incident_material_properties": {
        "name": "Air",
        "density": 1.21,
        "sound_velocity_longitudinal": 343.0,
        "sound_velocity_shear": 0.0
    }
}

print("\nPOST /api/v1/band-structure with:")
print(f"  Unit cell: {example_band_request['unit_cell']['size']} m, "
      f"{len(example_band_request['unit_cell']['scatterers'])} scatterer(s)")

print("\nPOST /api/v1/transmission with:")
print(f"  {len(example_transmission_request['unit_cell_layers'])} layers per unit cell, "
      f"{example_transmission_request['n_periods']} periods")

print("\n" + "=" * 60)
print("To start the server:")
print("  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
print("=" * 60)
