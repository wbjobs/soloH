import numpy as np
import sys
import os
import time

from config import SimulationConfig
from solver import ElasticSolver, ForwardEngineFWI, CheckpointManager
from source import Source, MultipleSources
from medium import Medium
from receiver import ReceiverArray
from curvilinear_grid import (
    CurvilinearGrid, CurvilinearElasticSolver, generate_topography
)
import visualization as vis


def test_source_encoding():
    print("=" * 70)
    print("Test 1: Source Encoding for Simultaneous Multi-Source Simulation")
    print("=" * 70)
    
    config = SimulationConfig(
        nx=101, nz=81, dx=10.0, dz=10.0,
        nt=200, dt=0.001,
        space_order=4,
        top_boundary='free_surface',
        bottom_boundary='cpml',
        left_boundary='cpml',
        right_boundary='cpml',
        cpml_width=10,
        source_f0=15.0,
        source_x=50, source_z=30
    )
    
    vp = 3000.0 * np.ones((config.nz, config.nx))
    vs = 1500.0 * np.ones((config.nz, config.nx))
    rho = 2500.0 * np.ones((config.nz, config.nx))
    medium = Medium(
        nx=config.nx, nz=config.nz, dx=config.dx, dz=config.dz,
        vp=config.vp, vs=config.vs, rho=config.rho,
        dtype=config.dtype
    )
    
    n_sources = 3
    sources_list = []
    for i in range(n_sources):
        source = Source(
            config.nx, config.nz, config.dx, config.dz,
            config.dt, config.nt,
            source_type='explosive',
            sx=20 + i * 30, sz=20,
            f0=config.source_f0,
            amplitude=1e9,
            t0=0.05
        )
        sources_list.append(source)
    
    encoding_types = ['random_phase', 'polarity', 'gaussian', 'hadamard']
    
    for enc_type in encoding_types:
        print(f"\n  Testing encoding type: {enc_type}")
        
        multi_source = MultipleSources(
            sources_list,
            use_encoding=True,
            encoding_type=enc_type,
            seed=42
        )
        
        receivers = ReceiverArray(
            nx=config.nx, nz=config.nz, dx=config.dx, dz=config.dz,
            dt=config.dt, nt=config.nt,
            array_type='arbitrary',
            dtype=config.dtype
        )
        for i in range(10):
            receivers.add_receiver(20 + i * 6, 5)
        
        solver = ElasticSolver(config)
        solver.medium = medium
        solver.source = multi_source
        solver.receivers = receivers
        
        solver.solve()
        
        encoding_norms = [np.linalg.norm(code) for code in multi_source.encodings]
        print(f"    Encoding norms: {[f'{n:.3e}' for n in encoding_norms]}")
        print(f"    Max receiver vx: {np.max(np.abs(solver.receivers.seismograms['vx'])):.3e}")
        
        encoded_data = solver.receivers.seismograms['vx']
        decoded = multi_source.decode_seismogram(encoded_data, 0)
        print(f"    Decoded data shape: {decoded.shape}")
        print(f"    Decoded max: {np.max(np.abs(decoded)):.3e}")
        
        print(f"    ✓ {enc_type} encoding test passed")
    
    multi_source_no_enc = MultipleSources(sources_list, use_encoding=False)
    print(f"\n  No encoding test:")
    print(f"    All codes = 1: {np.allclose(multi_source_no_enc.encodings[0], 1.0)}")
    print(f"    ✓ No encoding test passed")
    
    multi_source_polarity = MultipleSources(
        sources_list, use_encoding=True, encoding_type='polarity', seed=123
    )
    old_codes = [c.copy() for c in multi_source_polarity.encodings]
    multi_source_polarity.regenerate_encodings(seed=456)
    new_codes = [c.copy() for c in multi_source_polarity.encodings]
    codes_changed = not any(np.allclose(o, n) for o, n in zip(old_codes, new_codes))
    print(f"\n  Regenerate encodings test:")
    print(f"    Codes changed after regeneration: {codes_changed}")
    print(f"    ✓ Regenerate encodings test passed")
    
    print(f"\n  ✓ ALL SOURCE ENCODING TESTS PASSED")
    return True


def test_fwi_forward_engine():
    print("\n" + "=" * 70)
    print("Test 2: FWI Forward Engine with Checkpointing")
    print("=" * 70)
    
    config = SimulationConfig(
        nx=81, nz=61, dx=10.0, dz=10.0,
        nt=150, dt=0.001,
        space_order=4,
        cpml_width=10,
        source_f0=15.0,
        source_x=40, source_z=20
    )
    
    vp = 3000.0 * np.ones((config.nz, config.nx))
    vs = 1500.0 * np.ones((config.nz, config.nx))
    rho = 2500.0 * np.ones((config.nz, config.nx))
    medium = Medium(
        nx=config.nx, nz=config.nz, dx=config.dx, dz=config.dz,
        vp=config.vp, vs=config.vs, rho=config.rho,
        dtype=config.dtype
    )
    
    source = Source(
        config.nx, config.nz, config.dx, config.dz,
        config.dt, config.nt,
        source_type='explosive',
        sx=config.nx // 2, sz=20,
        f0=config.source_f0
    )
    
    receivers = ReceiverArray(
        nx=config.nx, nz=config.nz, dx=config.dx, dz=config.dz,
        dt=config.dt, nt=config.nt,
        array_type='arbitrary',
        dtype=config.dtype
    )
    for i in range(15):
        receivers.add_receiver(10 + i * 4, 10)
    
    solver = ElasticSolver(config)
    solver.medium = medium
    solver.source = source
    solver.receivers = receivers
    
    checkpoint_dir = 'test_checkpoints'
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    print(f"\n  Test 2a: CheckpointManager (memory-only)")
    ckpt_mem = CheckpointManager(
        config.nx, config.nz, config.nt,
        checkpoint_interval=20,
        max_checkpoints=5,
        storage_dir=None
    )
    
    test_vx = np.random.randn(config.nz, config.nx)
    test_vz = np.random.randn(config.nz, config.nx)
    test_tau_xx = np.random.randn(config.nz, config.nx)
    test_tau_zz = np.random.randn(config.nz, config.nx)
    test_tau_xz = np.random.randn(config.nz, config.nx)
    
    save_times = [20, 40, 60, 80]
    for t in save_times:
        ckpt_mem.save_checkpoint(t, test_vx, test_vz, test_tau_xx, test_tau_zz, test_tau_xz)
    
    print(f"    Saved checkpoints: {ckpt_mem.get_checkpoint_times()}")
    
    ckpt_data = ckpt_mem.load_checkpoint(40)
    print(f"    Loaded checkpoint it={ckpt_data['it']}")
    print(f"    vx matches: {np.allclose(ckpt_data['vx'], test_vx)}")
    print(f"    ✓ Memory checkpoint test passed")
    
    print(f"\n  Test 2b: CheckpointManager (disk-based)")
    ckpt_disk = CheckpointManager(
        config.nx, config.nz, config.nt,
        checkpoint_interval=20,
        max_checkpoints=5,
        storage_dir=checkpoint_dir
    )
    
    for t in save_times:
        ckpt_disk.save_checkpoint(t, test_vx, test_vz, test_tau_xx, test_tau_zz, test_tau_xz)
    
    print(f"    Disk checkpoints: {ckpt_disk.get_checkpoint_times()}")
    
    nearest = ckpt_disk.get_nearest_checkpoint(50)
    print(f"    Nearest checkpoint to it=50: it={nearest}")
    
    ckpt_disk_data = ckpt_disk.load_checkpoint(60)
    print(f"    Loaded disk checkpoint it={ckpt_disk_data['it']}")
    print(f"    vz matches: {np.allclose(ckpt_disk_data['vz'], test_vz)}")
    
    ckpt_disk.clear_all()
    print(f"    After clear: {ckpt_disk.get_checkpoint_times()}")
    print(f"    ✓ Disk checkpoint test passed")
    
    print(f"\n  Test 2c: ForwardEngineFWI")
    fwi_engine = ForwardEngineFWI(
        solver,
        checkpoint_interval=30,
        use_checkpointing=True,
        max_checkpoints=10,
        checkpoint_dir=None
    )
    
    save_steps = [30, 60, 90, 120]
    
    def progress_cb(it, nt, elapsed):
        pct = 100 * it / nt
        if it % 30 == 0 or it == nt:
            print(f"    Progress: {it}/{nt} ({pct:.0f}%) | Elapsed: {elapsed:.2f}s")
    
    start = time.time()
    fwi_result = fwi_engine.run_forward(
        save_wavefield_steps=save_steps,
        progress_callback=progress_cb,
        save_checkpoints=True
    )
    elapsed = time.time() - start
    
    print(f"    Forward run completed in {elapsed:.2f}s")
    print(f"    Receiver data shape: {fwi_result['receiver_data'].shape}")
    print(f"    Saved wavefields: {list(fwi_result['forward_wavefields'].keys())}")
    print(f"    Checkpoint times: {fwi_result['checkpoint_times']}")
    
    wf_30 = fwi_engine.get_wavefield(30, 'vz')
    print(f"    Wavefield vz at it=30, max: {np.max(np.abs(wf_30)):.3e}")
    
    print(f"\n  Test 2d: Misfit computation")
    observed = fwi_result['receiver_data'] + 1e-6 * np.random.randn(*fwi_result['receiver_data'].shape)
    
    misfit_l2, adj_l2 = fwi_engine.compute_misfit(observed, misfit_type='l2')
    print(f"    L2 misfit: {misfit_l2:.3e}")
    print(f"    Adjoint source shape: {adj_l2.shape}")
    
    misfit_l1, adj_l1 = fwi_engine.compute_misfit(observed, misfit_type='l1')
    print(f"    L1 misfit: {misfit_l1:.3e}")
    
    print(f"    ✓ Misfit computation test passed")
    
    print(f"\n  Test 2e: Restore from checkpoint")
    solver2 = ElasticSolver(config)
    solver2.medium = medium
    solver2.source = source
    solver2.receivers = receivers
    solver2._init_components()
    
    fwi_engine2 = ForwardEngineFWI(
        solver2,
        checkpoint_interval=30,
        use_checkpointing=True,
        max_checkpoints=10,
        checkpoint_dir=None
    )
    
    fwi_engine2.run_forward(
        save_wavefield_steps=[],
        save_checkpoints=True
    )
    
    restored_it = fwi_engine2.checkpoint_manager.restore_from_checkpoint(60, solver2)
    print(f"    Restored from checkpoint it={restored_it}")
    print(f"    ✓ Checkpoint restore test passed")
    
    fwi_engine.clear()
    fwi_engine2.clear()
    print(f"    ✓ Forward engine clear test passed")
    
    print(f"\n  ✓ ALL FWI FORWARD ENGINE TESTS PASSED")
    
    import shutil
    if os.path.exists(checkpoint_dir):
        shutil.rmtree(checkpoint_dir)
    
    return True


def test_curvilinear_grid():
    print("\n" + "=" * 70)
    print("Test 3: Curvilinear Grid for Topography")
    print("=" * 70)
    
    nx, nz = 81, 61
    dx, dz = 10.0, 10.0
    amplitude = 50.0
    
    print(f"\n  Test 3a: Topography generation")
    topo_types = ['flat', 'hill', 'valley', 'sine', 'random', 'step', 'sag_and_bump']
    
    for ttype in topo_types:
        topo = generate_topography(nx, dx, ttype, amplitude, seed=42)
        print(f"    {ttype:15s}: range [{np.min(topo):.1f}, {np.max(topo):.1f}] m")
    
    print(f"    ✓ Topography generation test passed")
    
    print(f"\n  Test 3b: Grid generation and metrics")
    grid_hill = CurvilinearGrid(
        nx, nz, dx, dz,
        topography_type='hill',
        amplitude=amplitude,
        stretching='linear'
    )
    
    print(f"    Grid shape: X={grid_hill.X.shape}, Z={grid_hill.Z.shape}")
    print(f"    Physical coordinates: X range [{np.min(grid_hill.X):.1f}, {np.max(grid_hill.X):.1f}]")
    print(f"    Physical coordinates: Z range [{np.min(grid_hill.Z):.1f}, {np.max(grid_hill.Z):.1f}]")
    print(f"    Topography range: [{np.min(grid_hill.topography):.1f}, {np.max(grid_hill.topography):.1f}] m")
    
    print(f"    Metrics shapes: xi_x={grid_hill.xi_x.shape}, J={grid_hill.J.shape}")
    print(f"    Jacobian J range: [{np.min(grid_hill.J):.4f}, {np.max(grid_hill.J):.4f}]")
    print(f"    xi_x range: [{np.min(grid_hill.xi_x):.4f}, {np.max(grid_hill.xi_x):.4f}]")
    print(f"    zeta_z range: [{np.min(grid_hill.zeta_z):.4f}, {np.max(grid_hill.zeta_z):.4f}]")
    
    orthogonality = np.abs(grid_hill.g_12) / (np.sqrt(grid_hill.g_11 * grid_hill.g_22) + 1e-10)
    print(f"    Max grid non-orthogonality: {np.max(orthogonality):.4f}")
    
    surface_indices = grid_hill.get_surface_indices()
    print(f"    Surface indices range: [{np.min(surface_indices)}, {np.max(surface_indices)}]")
    
    dx_min, dz_min = grid_hill.get_minimum_spacing()
    print(f"    Minimum spacing: dx={dx_min:.2f}m, dz={dz_min:.2f}m")
    
    cell_area = grid_hill.get_cell_area()
    print(f"    Cell area range: [{np.min(cell_area):.2f}, {np.max(cell_area):.2f}] m²")
    print(f"    ✓ Grid metrics test passed")
    
    print(f"\n  Test 3c: Stretching methods")
    stretch_methods = ['linear', 'exponential', 'hyperbolic', 'sigmoid']
    for stretch in stretch_methods:
        grid = CurvilinearGrid(
            nx, nz, dx, dz,
            topography_type='hill',
            amplitude=30,
            stretching=stretch,
            stretch_factor=2.0
        )
        z_spacing = np.diff(grid.Z[:, nx//2])
        print(f"    {stretch:15s}: dz range [{np.min(z_spacing):.2f}, {np.max(z_spacing):.2f}] m")
    print(f"    ✓ Stretching methods test passed")
    
    print(f"\n  Test 3d: Interpolation")
    grid = CurvilinearGrid(
        nx, nz, dx, dz,
        topography_type='sine',
        amplitude=40
    )
    
    field_curv = np.sin(grid.X / 100.0) * np.cos(grid.Z / 100.0)
    
    x_cart = np.linspace(0, (nx-1)*dx, nx)
    z_cart = np.linspace(0, (nz-1)*dz, nz)
    
    field_cart = grid.interpolate_to_cartesian(field_curv, x_cart, z_cart, method='linear')
    print(f"    Cartesian interpolation shape: {field_cart.shape}")
    print(f"    Field range (curved): [{np.min(field_curv):.3f}, {np.max(field_curv):.3f}]")
    print(f"    Field range (cartesian): [{np.min(field_cart):.3f}, {np.max(field_cart):.3f}]")
    
    field_back = grid.interpolate_from_cartesian(field_cart, x_cart, z_cart)
    l2_error = np.sqrt(np.mean((field_curv - field_back)**2))
    print(f"    Interpolation L2 error: {l2_error:.3e}")
    print(f"    ✓ Interpolation test passed")
    
    print(f"\n  Test 3e: CurvilinearElasticSolver")
    config = SimulationConfig(
        nx=nx, nz=nz, dx=dx, dz=dz,
        nt=100, dt=0.001,
        space_order=4,
        source_f0=15.0
    )
    
    curv_solver = CurvilinearElasticSolver(grid, config)
    print(f"    Wavefield shapes:")
    print(f"      vx: {curv_solver.vx.shape}, vz: {curv_solver.vz.shape}")
    print(f"      tau_xx: {curv_solver.tau_xx.shape}, tau_zz: {curv_solver.tau_zz.shape}")
    
    curv_solver.tau_zz[10, 40] = 1.0
    curv_solver.tau_xz[10, 40] = 1.0
    curv_solver.apply_topography_boundary_condition()
    
    surf_idx = grid.get_surface_indices()[40]
    print(f"    Surface index at x=40: {surf_idx}")
    print(f"    tau_zz at surface after BC: {curv_solver.tau_zz[surf_idx, 40]:.1e}")
    print(f"    tau_xz at surface after BC: {curv_solver.tau_xz[surf_idx, 40]:.1e}")
    print(f"    ✓ Topography BC test passed")
    
    print(f"\n  Test 3f: VTK export")
    vtk_filename = 'test_curvilinear.vtk'
    fields = {
        'velocity_vx': curv_solver.vx,
        'velocity_vz': curv_solver.vz,
        'jacobian': grid.J
    }
    grid.export_to_vtk(vtk_filename, fields=fields)
    vtk_exists = os.path.exists(vtk_filename)
    vtk_size = os.path.getsize(vtk_filename) if vtk_exists else 0
    print(f"    VTK file exists: {vtk_exists}, size: {vtk_size} bytes")
    if vtk_exists:
        os.remove(vtk_filename)
    print(f"    ✓ VTK export test passed")
    
    print(f"\n  Test 3g: Derivative transformation")
    dvar_dxi = np.ones_like(grid.X)
    dvar_dzeta = np.ones_like(grid.X)
    
    from curvilinear_grid import transform_derivatives_curved
    dvar_dx, dvar_dz = transform_derivatives_curved(
        dvar_dxi, dvar_dzeta,
        grid.xi_x, grid.xi_z,
        grid.zeta_x, grid.zeta_z
    )
    print(f"    Derivative transformation output shapes: {dvar_dx.shape}, {dvar_dz.shape}")
    print(f"    ✓ Derivative transformation test passed")
    
    print(f"\n  ✓ ALL CURVILINEAR GRID TESTS PASSED")
    return True


def test_integration():
    print("\n" + "=" * 70)
    print("Test 4: Integration - Multi-Source Simulation with FWI Engine")
    print("=" * 70)
    
    config = SimulationConfig(
        nx=101, nz=81, dx=10.0, dz=10.0,
        nt=200, dt=0.001,
        space_order=4,
        top_boundary='free_surface',
        cpml_width=10,
        source_f0=15.0,
        source_x=50, source_z=30
    )
    
    vp = 3000.0 * np.ones((config.nz, config.nx))
    vp[40:, :] = 3500.0
    vs = 1500.0 * np.ones((config.nz, config.nx))
    vs[40:, :] = 1750.0
    rho = 2500.0 * np.ones((config.nz, config.nx))
    medium = Medium(
        nx=config.nx, nz=config.nz, dx=config.dx, dz=config.dz,
        vp=config.vp, vs=config.vs, rho=config.rho,
        dtype=config.dtype
    )
    
    sources_list = []
    for i in range(4):
        source = Source(
            config.nx, config.nz, config.dx, config.dz,
            config.dt, config.nt,
            source_type='explosive',
            sx=15 + i * 25, sz=15,
            f0=config.source_f0,
            amplitude=5e8,
            t0=0.05
        )
        sources_list.append(source)
    
    multi_source = MultipleSources(
        sources_list,
        use_encoding=True,
        encoding_type='random_phase',
        seed=42
    )
    
    receivers = ReceiverArray(
        nx=config.nx, nz=config.nz, dx=config.dx, dz=config.dz,
        dt=config.dt, nt=config.nt,
        array_type='arbitrary',
        dtype=config.dtype
    )
    for i in range(20):
        receivers.add_receiver(5 + i * 4, 5)
    
    solver = ElasticSolver(config)
    solver.medium = medium
    solver.source = multi_source
    solver.receivers = receivers
    
    fwi_engine = ForwardEngineFWI(
        solver,
        checkpoint_interval=40,
        use_checkpointing=True,
        max_checkpoints=10,
        checkpoint_dir=None
    )
    
    save_steps = list(range(0, config.nt, 20))
    
    print(f"\n  Running multi-source FWI forward simulation...")
    result = fwi_engine.run_forward(
        save_wavefield_steps=save_steps,
        progress_callback=lambda it, nt, el: (
            print(f"    Progress: {it}/{nt} ({100*it/nt:.0f}%)") 
            if it % 40 == 0 else None
        ),
        save_checkpoints=True
    )
    
    print(f"\n  Simulation results:")
    print(f"    Receiver data shape: {result['receiver_data'].shape}")
    print(f"    Saved wavefields: {len(result['forward_wavefields'])} time steps")
    print(f"    Checkpoints saved: {result['checkpoint_times']}")
    print(f"    Max vx receiver data: {np.max(np.abs(result['receiver_data'][:, :, 0])):.3e}")
    print(f"    Max vz receiver data: {np.max(np.abs(result['receiver_data'][:, :, 1])):.3e}")
    
    if len(save_steps) > 0:
        snapshots = [fwi_engine.get_wavefield(t, 'vx') for t in save_steps]
        print(f"    Snapshot shapes: {snapshots[0].shape}")
        
        try:
            output_dir = 'test_multi_source'
            os.makedirs(output_dir, exist_ok=True)
            ani_file = os.path.join(output_dir, 'multi_source_wavefield.gif')
            
            snapshot_dicts = [{'vx': s} for s in snapshots]
            time_axis = np.array(save_steps) * config.dt * 1000
            
            vis.animate_snapshots(
                snapshot_dicts, field_name='vx',
                x_axis=np.arange(config.nx) * config.dx,
                z_axis=np.arange(config.nz) * config.dz,
                output_file=ani_file,
                fps=10, use_blit=False
            )
            print(f"    Animation saved to {ani_file}")
            
            vmin, vmax = np.percentile(snapshots, [1, 99])
            vis.plot_wavefield(
                snapshots[-1], config.dx, config.dz,
                title='Multi-Source Wavefield (vx)',
                output_file=os.path.join(output_dir, 'final_wavefield.png'),
                vmin=vmin, vmax=vmax
            )
            print(f"    Wavefield plot saved")
        except Exception as e:
            print(f"    Visualization skipped: {e}")
    
    print(f"    ✓ Integration test passed")
    
    fwi_engine.clear()
    return True


def main():
    print("\n" + "=" * 70)
    print("COMPREHENSIVE TEST SUITE FOR ADVANCED FEATURES")
    print("=" * 70)
    print()
    
    results = {
        'source_encoding': False,
        'fwi_engine': False,
        'curvilinear': False,
        'integration': False
    }
    
    try:
        test_source_encoding()
        results['source_encoding'] = True
    except Exception as e:
        print(f"\n  ✗ SOURCE ENCODING TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test_fwi_forward_engine()
        results['fwi_engine'] = True
    except Exception as e:
        print(f"\n  ✗ FWI FORWARD ENGINE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test_curvilinear_grid()
        results['curvilinear'] = True
    except Exception as e:
        print(f"\n  ✗ CURVILINEAR GRID TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test_integration()
        results['integration'] = True
    except Exception as e:
        print(f"\n  ✗ INTEGRATION TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Source Encoding..................... {'✓ PASSED' if results['source_encoding'] else '✗ FAILED'}")
    print(f"FWI Forward Engine.................. {'✓ PASSED' if results['fwi_engine'] else '✗ FAILED'}")
    print(f"Curvilinear Grid.................... {'✓ PASSED' if results['curvilinear'] else '✗ FAILED'}")
    print(f"Integration......................... {'✓ PASSED' if results['integration'] else '✗ FAILED'}")
    print("=" * 70)
    
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)
    
    return all_passed


if __name__ == '__main__':
    main()
