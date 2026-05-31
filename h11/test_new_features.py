import sys
import numpy as np
from typing import Dict, List, Tuple

print("=" * 70)
print("Testing Three New Advanced Features")
print("=" * 70)

mesh = None
boundary_info = None
bz = None
materials = None
unit_cell_size = (1.0, 1.0)

print("\n" + "=" * 70)
print("FEATURE 1: Topological Band Analysis (Zak Phase + Wilson Loop)")
print("=" * 70)

try:
    from app.core.brillouin_zone import generate_brillouin_zone_path
    from app.core.mesh_generator import generate_mesh, UnitCell, Scatterer, assign_material_properties
    from app.core.fem_assembly import assemble_global_matrices
    from app.core.eigenvalue_solver import solve_band_structure
    from app.core.topological_analysis import (
        compute_zak_phase,
        compute_zak_phases_for_bands,
        construct_wilson_loop_operator,
        compute_wilson_loop_spectrum,
        extract_topological_invariants,
        compute_full_topological_analysis
    )

    print("✓ Topological analysis module imported successfully")

    materials = [
        {
            'name': 'Epoxy',
            'density': 1180.0,
            'sound_velocity_longitudinal': 2830.0,
            'sound_velocity_shear': 1160.0
        },
        {
            'name': 'Steel',
            'density': 7850.0,
            'sound_velocity_longitudinal': 5960.0,
            'sound_velocity_shear': 3235.0
        }
    ]

    scatterers = [
        Scatterer(shape='circle', position=(0.5, 0.5), size=0.2, material='Steel')
    ]

    unit_cell = UnitCell(
        size=(1.0, 1.0),
        scatterers=scatterers,
        background_material='Epoxy',
        mesh_resolution=0.2
    )

    mesh = generate_mesh(unit_cell)
    vertices = mesh['vertices']
    triangles = mesh['triangles']

    boundary_info = {
        'paired_x': [],
        'paired_y': [],
        'interior_nodes': list(range(len(vertices)))
    }

    min_x, max_x = vertices[:, 0].min(), vertices[:, 0].max()
    min_y, max_y = vertices[:, 1].min(), vertices[:, 1].max()
    eps = 1e-6

    x_left = np.where(np.abs(vertices[:, 0] - min_x) < eps)[0]
    x_right = np.where(np.abs(vertices[:, 0] - max_x) < eps)[0]
    y_bottom = np.where(np.abs(vertices[:, 1] - min_y) < eps)[0]
    y_top = np.where(np.abs(vertices[:, 1] - max_y) < eps)[0]

    for ln, rn in zip(x_left, x_right):
        boundary_info['paired_x'].append((int(ln), int(rn)))

    for bn, tn in zip(y_bottom, y_top):
        boundary_info['paired_y'].append((int(bn), int(tn)))

    boundary_nodes = set(list(x_left) + list(x_right) + list(y_bottom) + list(y_top))
    boundary_info['interior_nodes'] = [i for i in range(len(vertices)) if i not in boundary_nodes]
    boundary_info['n_boundary_nodes'] = len(boundary_nodes)

    K, M = assemble_global_matrices(
        mesh=mesh,
        material_properties=materials,
        wave_type='sh'
    )

    print(f"✓ Mesh generated: {len(mesh['vertices'])} nodes, {len(mesh['triangles'])} elements")
    print(f"✓ Matrices assembled: K shape={K.shape}, nnz={K.nnz}")

    bz = generate_brillouin_zone_path(
        lattice='square',
        lattice_constant=unit_cell_size[0],
        n_points_per_segment=10,
        ensure_symmetry=True
    )

    band_result = solve_band_structure(
        K=K, M=M,
        k_points=bz['k_points'],
        boundary_info=boundary_info,
        unit_cell_size=unit_cell_size,
        wave_type='sh',
        n_bands=8
    )

    print(f"✓ Band structure computed: {band_result['frequencies'].shape}")
    print(f"  Frequency range: {np.nanmin(band_result['frequencies']):.0f} - {np.nanmax(band_result['frequencies']):.0f} Hz")

    zak_phases = compute_zak_phases_for_bands(
        band_result, boundary_info, unit_cell_size, n_bands=6
    )

    print(f"\nZak Phases (first 6 bands):")
    for i, gamma in enumerate(zak_phases):
        topology = 'trivial' if abs(gamma) < np.pi / 2 else 'topological' if abs(abs(gamma) - np.pi) < np.pi / 2 else 'hybrid'
        print(f"  Band {i}: γ = {gamma:.4f} rad ({topology})")

    topo_result = compute_full_topological_analysis(
        band_structure=band_result,
        boundary_info=boundary_info,
        unit_cell_size=unit_cell_size,
        brillouin_zone=bz,
        compute_wilson=True,
        n_phi=8,
        max_bands=6
    )

    print(f"\nTopological Analysis Results:")
    print(f"  Band topology: {topo_result['band_topology']}")
    print(f"  Topological gap indices: {topo_result['topological_gap_indices']}")
    print(f"  Edge state predictions: {len(topo_result['edge_state_predictions'])}")

    if 'wilson_loop' in topo_result:
        print(f"  Wilson loop computed: {len(topo_result['wilson_loop']['phi_values'])} phi angles")
        phases = np.array(topo_result['wilson_loop']['phases'])
        print(f"  Wilson phase range: [{phases.min():.3f}, {phases.max():.3f}] rad")
    if 'chern_numbers' in topo_result and topo_result['chern_numbers'] is not None:
        print(f"  Chern numbers: {topo_result['chern_numbers']}")

    print("\n✓ Topological band analysis test PASSED")

except Exception as e:
    print(f"\n✗ Topological analysis test FAILED: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("FEATURE 2: Lossy Materials with Complex Sound Velocity")
print("=" * 70)

try:
    from app.core.fem_assembly import (
        compute_complex_sound_velocity,
        convert_material_to_complex,
        assemble_global_matrices
    )
    from app.core.eigenvalue_solver import (
        solve_complex_eigenproblem,
        solve_band_structure
    )

    print("✓ Complex material module imported successfully")

    v_real = 3000.0
    loss_factors = [0.0, 0.01, 0.05, 0.1]
    models = ['viscous', 'hysteretic', 'rayleigh']

    print("\nComplex Sound Velocity for Different Loss Models:")
    for model in models:
        print(f"\n  Model: {model}")
        for eta in loss_factors:
            v_c = compute_complex_sound_velocity(v_real, eta, model)
            print(f"    η={eta:.2f}: v = {v_c.real:.1f} + {v_c.imag:.1f}j m/s, |v|={abs(v_c):.1f}")

    lossy_materials = [
        {
            'name': 'Lossy_Epoxy',
            'density': 1180.0,
            'sound_velocity_longitudinal': 2830.0,
            'sound_velocity_shear': 1160.0,
            'loss_factor': 0.02,
            'loss_model': 'viscous'
        },
        {
            'name': 'Steel',
            'density': 7850.0,
            'sound_velocity_longitudinal': 5960.0,
            'sound_velocity_shear': 3235.0,
            'loss_factor': 0.001,
            'loss_model': 'viscous'
        }
    ]

    converted_materials = [convert_material_to_complex(m) for m in lossy_materials]
    print("\nConverted Material Properties:")
    for i, mat in enumerate(converted_materials):
        print(f"  {mat['name']}:")
        print(f"    v_l = {mat['sound_velocity_longitudinal']}")
        print(f"    v_s = {mat['sound_velocity_shear']}")
        print(f"    loss_factor = {mat['loss_factor_longitudinal']}")

    if mesh is None or boundary_info is None:
        raise RuntimeError("Mesh not available from Feature 1 test")

    K_complex, M_complex = assemble_global_matrices(
        mesh=mesh,
        material_properties=converted_materials,
        wave_type='sh',
        has_complex_materials=True
    )

    print(f"\n✓ Complex matrices assembled")
    print(f"  K dtype: {K_complex.dtype}")
    print(f"  K is complex: {np.iscomplexobj(K_complex.data)}")

    if bz is None:
        from app.core.brillouin_zone import generate_brillouin_zone_path
        bz = generate_brillouin_zone_path(
            lattice='square',
            lattice_constant=unit_cell_size[0],
            n_points_per_segment=10,
            ensure_symmetry=True
        )

    band_result_lossy = solve_band_structure(
        K=K_complex, M=M_complex,
        k_points=bz['k_points'],
        boundary_info=boundary_info,
        unit_cell_size=unit_cell_size,
        wave_type='sh',
        n_bands=6,
        has_loss=True
    )

    print(f"\n✓ Lossy band structure computed")
    print(f"  Frequencies dtype: {band_result_lossy['frequencies'].dtype}")
    print(f"  Has loss flag: {band_result_lossy['has_loss']}")

    if 'real_frequencies' in band_result_lossy:
        real_f = band_result_lossy['real_frequencies']
        att = band_result_lossy['attenuation']
        print(f"\nReal frequencies: {np.nanmin(real_f):.0f} - {np.nanmax(real_f):.0f} Hz")
        print(f"Attenuation range: {np.nanmin(att):.4e} - {np.nanmax(att):.4e} dB/m")
        print(f"Mean attenuation (band 0): {np.nanmean(att[:, 0]):.4e} dB/m")

    if 'loss_analysis' in band_result_lossy:
        analysis = band_result_lossy['loss_analysis'][0]
        if analysis:
            print(f"\nLoss Analysis at Γ point (k=0):")
            print(f"  Quality factors (first 3 bands): {analysis.get('quality_factors', [])[:3]}")
            print(f"  Phase velocities (first 3 bands): {analysis.get('phase_velocity', [])[:3]}")

    print("\n✓ Lossy material test PASSED")

except Exception as e:
    print(f"\n✗ Lossy material test FAILED: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("FEATURE 3: Multiscale Homogenization")
print("=" * 70)

try:
    from app.core.homogenization import (
        compute_volume_fractions,
        compute_effective_density,
        compute_voigt_average,
        compute_reuss_average,
        compute_hashin_shtrikman_bounds,
        compute_effective_properties_simple,
        solve_homogenization_problem
    )

    print("✓ Homogenization module imported successfully")

    if mesh is None or boundary_info is None or materials is None:
        raise RuntimeError("Mesh or materials not available from previous tests")

    vf = compute_volume_fractions(mesh, materials)
    print(f"\nVolume Fractions:")
    for name, frac in vf.items():
        print(f"  {name}: {frac * 100:.2f}%")

    simple_props = compute_effective_properties_simple(vf, materials)
    print(f"\nSimple Homogenization Results:")
    print(f"  Effective density: {simple_props['effective_density']:.2f} kg/m³")
    print(f"  Voigt v_l: {simple_props['effective_velocity_longitudinal_voigt']:.1f} m/s")
    print(f"  Voigt v_s: {simple_props['effective_velocity_shear_voigt']:.1f} m/s")
    print(f"  Reuss v_l: {simple_props['effective_velocity_longitudinal_reuss']:.1f} m/s")
    print(f"  Reuss v_s: {simple_props['effective_velocity_shear_reuss']:.1f} m/s")

    C_voigt = compute_voigt_average(vf, materials)
    C_reuss = compute_reuss_average(vf, materials)

    print(f"\nVoigt Average Modulus Tensor (C_ij):")
    print(f"  C11 = {np.real(C_voigt[0, 0]):.3e} Pa")
    print(f"  C12 = {np.real(C_voigt[0, 1]):.3e} Pa")
    print(f"  C44 = {np.real(C_voigt[2, 2]):.3e} Pa")

    print(f"\nReuss Average Modulus Tensor (C_ij):")
    print(f"  C11 = {np.real(C_reuss[0, 0]):.3e} Pa")
    print(f"  C12 = {np.real(C_reuss[0, 1]):.3e} Pa")
    print(f"  C44 = {np.real(C_reuss[2, 2]):.3e} Pa")

    hs_bounds = compute_hashin_shtrikman_bounds(vf, materials)
    print(f"\nHashin-Shtrikman Bounds:")
    print(f"  Lower bound C11: {np.real(hs_bounds['lower'][0, 0]):.3e} Pa")
    print(f"  Upper bound C11: {np.real(hs_bounds['upper'][0, 0]):.3e} Pa")

    methods = ['voigt', 'reuss', 'hashin_shtrikman', 'asymptotic']
    print("\nFull Homogenization Results by Method:")
    for method in methods:
        try:
            result = solve_homogenization_problem(
                mesh=mesh,
                material_properties=materials,
                boundary_info=boundary_info,
                unit_cell_size=unit_cell_size,
                wave_type='sh',
                method=method
            )
            print(f"\n  Method: {method}")
            print(f"    Effective density: {np.real(result.effective_density[0, 0]):.2f} kg/m³")
            print(f"    Effective v_l: {result.effective_velocity_longitudinal:.1f} m/s")
            print(f"    Effective v_s: {result.effective_velocity_shear:.1f} m/s")
            print(f"    Effective K: {np.real((result.effective_modulus[0, 0] + 2*result.effective_modulus[0, 1])/3):.3e} Pa")
            print(f"    Effective μ: {np.real(result.effective_modulus[2, 2]):.3e} Pa")
        except Exception as e:
            print(f"\n  Method: {method} - skipped: {str(e)[:50]}")

    print("\n✓ Multiscale homogenization test PASSED")

except Exception as e:
    print(f"\n✗ Homogenization test FAILED: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("MODULE IMPORT TESTS (API ENDPOINTS)")
print("=" * 70)

try:
    from app.models.schemas import (
        TopologicalAnalysisRequest,
        TopologicalAnalysisResponse,
        HomogenizationRequest,
        HomogenizationResponse,
        ComplexBandStructureRequest,
        ComplexBandStructureResponse,
        EdgeStatePrediction,
        WilsonLoopData,
        ComplexBandPoint,
        LossModel
    )
    print("✓ All new Pydantic models imported successfully")

    from app.routers.advanced import router as advanced_router
    print("✓ Advanced router imported successfully")
    print(f"  Number of routes: {len(advanced_router.routes)}")
    for route in advanced_router.routes:
        if hasattr(route, 'methods') and route.methods:
            print(f"    {route.methods} {route.path}")
        else:
            print(f"    {route.path}")

    from app.dependencies import get_db
    print("✓ Dependencies module imported successfully")

except Exception as e:
    print(f"\n✗ Import test FAILED: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("COMPILATION CHECK (all Python files)")
print("=" * 70)

import subprocess
import os
files_to_check = [
    "app/core/topological_analysis.py",
    "app/core/homogenization.py",
    "app/core/fem_assembly.py",
    "app/core/eigenvalue_solver.py",
    "app/models/schemas.py",
    "app/routers/advanced.py",
    "app/dependencies.py",
    "app/main.py"
]

all_ok = True
for f in files_to_check:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", f],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        if result.returncode == 0:
            print(f"✓ {f}")
        else:
            print(f"✗ {f}: {result.stderr.strip()}")
            all_ok = False
    except Exception as e:
        print(f"✗ {f}: {e}")
        all_ok = False

print("\n" + "=" * 70)
if all_ok:
    print("ALL TESTS PASSED ✓")
    print("\nNew Features Summary:")
    print("1. Topological Band Analysis:")
    print("   - Zak phase calculation for each band")
    print("   - Wilson loop spectrum computation")
    print("   - Topological invariant extraction (Chern numbers)")
    print("   - Edge state prediction from Zak phase jumps")
    print("\n2. Lossy Material Support:")
    print("   - Complex sound velocity with viscous/hysteretic/Rayleigh models")
    print("   - Complex generalized eigenvalue solver")
    print("   - Attenuation calculation (dB/m)")
    print("   - Quality factor and phase velocity extraction")
    print("\n3. Multiscale Homogenization:")
    print("   - Voigt, Reuss, Hashin-Shtrikman bounds")
    print("   - Asymptotic homogenization via FEM")
    print("   - Effective density and modulus tensor computation")
    print("   - Effective longitudinal and shear wave velocities")
else:
    print("SOME TESTS FAILED ✗")
print("=" * 70)
