import numpy as np
import matplotlib.pyplot as plt
import time
import sys
import os

from config import SimulationConfig
from solver import ElasticSolver
from visualization import (
    plot_wiggle,
    plot_snapshot,
    animate_snapshots,
    plot_particle_motion,
    plot_seismogram,
    create_summary_figure
)


def progress_callback(current: int, total: int, elapsed: float) -> None:
    percent = 100 * current / total
    remaining = (elapsed / current) * (total - current) if current > 0 else 0
    sys.stdout.write(f"\rProgress: {current}/{total} ({percent:.1f}%) | "
                    f"Elapsed: {elapsed:.1f}s | Remaining: {remaining:.1f}s")
    sys.stdout.flush()
    if current == total:
        print()


def run_isotropic_simulation(show_plots: bool = True,
                             save_results: bool = True) -> dict:
    print("=" * 70)
    print("Running Isotropic Elastic Wave Simulation")
    print("=" * 70)
    
    config = SimulationConfig(
        nx=301,
        nz=301,
        dx=10.0,
        dz=10.0,
        dt=0.001,
        nt=800,
        space_order=12,
        cpml_width=30,
        vp=3000.0,
        vs=1732.0,
        rho=2500.0,
        anisotropy_type='isotropic',
        source_type='explosive',
        source_x=150,
        source_z=150,
        source_f0=20.0,
        source_amplitude=1e9,
        source_time_delay=0.05,
        receiver_x_start=50,
        receiver_x_end=250,
        receiver_z=5,
        receiver_spacing=5,
        snapshot_interval=20,
        output_dir='output/isotropic',
        dtype=np.float64
    )
    
    solver = ElasticSolver(config)
    
    particle_points = [(100, 100), (200, 100), (150, 200)]
    solver.set_particle_motion_points(particle_points)
    
    print(f"\nGrid size: {config.nx} x {config.nz}")
    print(f"Grid spacing: {config.dx} x {config.dz} m")
    print(f"Time steps: {config.nt}, dt: {config.dt*1000:.2f} ms")
    print(f"Total time: {config.nt*config.dt:.2f} s")
    print(f"Space order: {config.space_order}")
    print(f"Number of receivers: {len(solver.receivers)}")
    print(f"CFL number: {config.cfl:.4f}")
    print(f"\nStarting simulation...")
    
    start_time = time.time()
    results = solver.solve(progress_callback=progress_callback)
    total_time = time.time() - start_time
    
    print(f"\nSimulation completed in {total_time:.2f} seconds")
    print(f"Average time per step: {total_time/config.nt*1000:.3f} ms")
    
    if save_results:
        print("\nSaving results...")
        results['receivers'].save(config.output_dir)
        create_summary_figure(results, config.output_dir)
        
        print("\nCreating wavefield animation...")
        animate_snapshots(results['snapshots'], 'vx',
                         config.get_axis('x'), config.get_axis('z'),
                         output_file=os.path.join(config.output_dir, 'animation_vx.gif'),
                         fps=15, dpi=80)
        
        animate_snapshots(results['snapshots'], 'vz',
                         config.get_axis('x'), config.get_axis('z'),
                         output_file=os.path.join(config.output_dir, 'animation_vz.gif'),
                         fps=15, dpi=80)
        
        if 'particle_motion' in results:
            pm = results['particle_motion']
            for i in range(len(particle_points)):
                attrs = pm.get_polarization_attributes(i)
                print(f"\nPolarization attributes for point {i} ({pm.point_positions[i]}):")
                print(f"  Major axis: {attrs['major_axis']:.6e} m")
                print(f"  Minor axis: {attrs['minor_axis']:.6e} m")
                print(f"  Ellipticity: {attrs['ellipticity']:.4f}")
                print(f"  Polarization angle: {attrs['polarization_angle']:.2f}°")
                print(f"  Rectilinearity: {attrs['rectilinearity']:.4f}")
    
    if show_plots:
        plt.show()
    
    return results


def run_vti_simulation(show_plots: bool = True,
                       save_results: bool = True) -> dict:
    print("\n" + "=" * 70)
    print("Running VTI (Vertical Transverse Isotropy) Simulation")
    print("=" * 70)
    
    config = SimulationConfig(
        nx=301,
        nz=301,
        dx=10.0,
        dz=10.0,
        dt=0.001,
        nt=800,
        space_order=12,
        cpml_width=30,
        vp=3000.0,
        vs=1732.0,
        rho=2500.0,
        anisotropy_type='vti',
        epsilon=0.15,
        delta=0.08,
        gamma=0.10,
        source_type='explosive',
        source_x=150,
        source_z=150,
        source_f0=15.0,
        source_amplitude=1e9,
        source_time_delay=0.06,
        receiver_x_start=50,
        receiver_x_end=250,
        receiver_z=5,
        receiver_spacing=5,
        snapshot_interval=20,
        output_dir='output/vti',
        dtype=np.float64
    )
    
    solver = ElasticSolver(config)
    
    particle_points = [(100, 100), (200, 100), (150, 200)]
    solver.set_particle_motion_points(particle_points)
    
    print(f"\nAnisotropy parameters:")
    print(f"  ε = {config.epsilon}, δ = {config.delta}, γ = {config.gamma}")
    print(f"  Vp(0°) = {config.vp} m/s")
    print(f"  Vp(90°) = {config.vp * np.sqrt(1 + 2*config.epsilon):.1f} m/s")
    
    start_time = time.time()
    results = solver.solve(progress_callback=progress_callback)
    total_time = time.time() - start_time
    
    print(f"\nVTI simulation completed in {total_time:.2f} seconds")
    
    if save_results:
        print("\nSaving VTI results...")
        results['receivers'].save(config.output_dir)
        create_summary_figure(results, config.output_dir)
        
        animate_snapshots(results['snapshots'], 'vx',
                         config.get_axis('x'), config.get_axis('z'),
                         output_file=os.path.join(config.output_dir, 'animation_vx.gif'),
                         fps=15, dpi=80)
    
    if show_plots:
        plt.show()
    
    return results


def run_tti_simulation(show_plots: bool = True,
                       save_results: bool = True) -> dict:
    print("\n" + "=" * 70)
    print("Running TTI (Tilted Transverse Isotropy) Simulation")
    print("=" * 70)
    
    config = SimulationConfig(
        nx=301,
        nz=301,
        dx=10.0,
        dz=10.0,
        dt=0.001,
        nt=800,
        space_order=12,
        cpml_width=30,
        vp=3000.0,
        vs=1732.0,
        rho=2500.0,
        anisotropy_type='tti',
        epsilon=0.15,
        delta=0.08,
        gamma=0.10,
        theta=30.0,
        phi=0.0,
        source_type='explosive',
        source_x=150,
        source_z=150,
        source_f0=15.0,
        source_amplitude=1e9,
        source_time_delay=0.06,
        receiver_x_start=50,
        receiver_x_end=250,
        receiver_z=5,
        receiver_spacing=5,
        snapshot_interval=20,
        output_dir='output/tti',
        dtype=np.float64
    )
    
    solver = ElasticSolver(config)
    
    particle_points = [(100, 100), (200, 100), (150, 200)]
    solver.set_particle_motion_points(particle_points)
    
    print(f"\nAnisotropy parameters:")
    print(f"  ε = {config.epsilon}, δ = {config.delta}, γ = {config.gamma}")
    print(f"  Tilt angle θ = {config.theta}°, φ = {config.phi}°")
    
    start_time = time.time()
    results = solver.solve(progress_callback=progress_callback)
    total_time = time.time() - start_time
    
    print(f"\nTTI simulation completed in {total_time:.2f} seconds")
    
    if save_results:
        print("\nSaving TTI results...")
        results['receivers'].save(config.output_dir)
        create_summary_figure(results, config.output_dir)
        
        animate_snapshots(results['snapshots'], 'vx',
                         config.get_axis('x'), config.get_axis('z'),
                         output_file=os.path.join(config.output_dir, 'animation_vx.gif'),
                         fps=15, dpi=80)
    
    if show_plots:
        plt.show()
    
    return results


def run_shear_source_simulation(show_plots: bool = True,
                                save_results: bool = True) -> dict:
    print("\n" + "=" * 70)
    print("Running Shear Source Simulation")
    print("=" * 70)
    
    config = SimulationConfig(
        nx=301,
        nz=301,
        dx=10.0,
        dz=10.0,
        dt=0.001,
        nt=800,
        space_order=12,
        cpml_width=30,
        vp=3000.0,
        vs=1732.0,
        rho=2500.0,
        anisotropy_type='isotropic',
        source_type='shear',
        source_x=150,
        source_z=150,
        source_f0=15.0,
        source_amplitude=5e8,
        source_time_delay=0.06,
        receiver_x_start=50,
        receiver_x_end=250,
        receiver_z=5,
        receiver_spacing=5,
        snapshot_interval=20,
        output_dir='output/shear',
        dtype=np.float64
    )
    
    solver = ElasticSolver(config)
    
    particle_points = [(100, 100), (200, 100)]
    solver.set_particle_motion_points(particle_points)
    
    print(f"\nSource type: {config.source_type}")
    
    start_time = time.time()
    results = solver.solve(progress_callback=progress_callback)
    total_time = time.time() - start_time
    
    print(f"\nShear source simulation completed in {total_time:.2f} seconds")
    
    if save_results:
        print("\nSaving shear source results...")
        results['receivers'].save(config.output_dir)
        create_summary_figure(results, config.output_dir)
        
        animate_snapshots(results['snapshots'], 'tau_xz',
                         config.get_axis('x'), config.get_axis('z'),
                         output_file=os.path.join(config.output_dir, 'animation_tauxz.gif'),
                         fps=15, dpi=80)
    
    if show_plots:
        plt.show()
    
    return results


def run_heterogeneous_model(show_plots: bool = True,
                            save_results: bool = True) -> dict:
    print("\n" + "=" * 70)
    print("Running Heterogeneous Model Simulation")
    print("=" * 70)
    
    config = SimulationConfig(
        nx=401,
        nz=401,
        dx=10.0,
        dz=10.0,
        dt=0.001,
        nt=1000,
        space_order=12,
        cpml_width=30,
        vp=3000.0,
        vs=1732.0,
        rho=2500.0,
        anisotropy_type='isotropic',
        source_type='explosive',
        source_x=200,
        source_z=50,
        source_f0=15.0,
        source_amplitude=1e9,
        source_time_delay=0.06,
        receiver_x_start=50,
        receiver_x_end=350,
        receiver_z=5,
        receiver_spacing=5,
        snapshot_interval=20,
        output_dir='output/heterogeneous',
        dtype=np.float64
    )
    
    solver = ElasticSolver(config)
    
    x = config.get_axis('x')
    z = config.get_axis('z')
    X, Z = np.meshgrid(x, z)
    
    vp_model = 2500.0 + 0.5 * Z + 200.0 * np.sin(2 * np.pi * X / 4000.0)
    vs_model = vp_model / np.sqrt(3)
    rho_model = 2200.0 + 0.3 * Z
    
    solver.medium.set_heterogeneous_model(vp_model, vs_model, rho_model)
    
    particle_points = [(150, 200), (250, 200), (200, 300)]
    solver.set_particle_motion_points(particle_points)
    
    print(f"\nModel features:")
    print(f"  Vp range: {vp_model.min():.1f} - {vp_model.max():.1f} m/s")
    print(f"  Vs range: {vs_model.min():.1f} - {vs_model.max():.1f} m/s")
    print(f"  Includes vertical gradient and lateral velocity variation")
    
    start_time = time.time()
    results = solver.solve(progress_callback=progress_callback)
    total_time = time.time() - start_time
    
    print(f"\nHeterogeneous simulation completed in {total_time:.2f} seconds")
    
    if save_results:
        print("\nSaving heterogeneous model results...")
        results['receivers'].save(config.output_dir)
        create_summary_figure(results, config.output_dir)
        
        animate_snapshots(results['snapshots'], 'vx',
                         config.get_axis('x'), config.get_axis('z'),
                         output_file=os.path.join(config.output_dir, 'animation_vx.gif'),
                         fps=15, dpi=80)
    
    if show_plots:
        plt.show()
    
    return results


def run_comparison_study(show_plots: bool = True,
                         save_results: bool = True) -> None:
    print("\n" + "=" * 70)
    print("Running Comparative Study: Isotropic vs VTI vs TTI")
    print("=" * 70)
    
    base_config = dict(
        nx=251,
        nz=251,
        dx=10.0,
        dz=10.0,
        dt=0.001,
        nt=600,
        space_order=8,
        cpml_width=30,
        vp=3000.0,
        vs=1732.0,
        rho=2500.0,
        source_type='explosive',
        source_x=125,
        source_z=125,
        source_f0=20.0,
        source_amplitude=1e9,
        source_time_delay=0.05,
        receiver_x_start=50,
        receiver_x_end=200,
        receiver_z=5,
        receiver_spacing=10,
        snapshot_interval=30,
        dtype=np.float64
    )
    
    results_dict = {}
    
    for aniso_type, output_dir, extra_params in [
        ('isotropic', 'output/comparison/isotropic', {}),
        ('vti', 'output/comparison/vti', {'epsilon': 0.15, 'delta': 0.08, 'gamma': 0.10}),
        ('tti', 'output/comparison/tti', {'epsilon': 0.15, 'delta': 0.08, 'gamma': 0.10, 'theta': 30.0})
    ]:
        print(f"\n--- Running {aniso_type.upper()} simulation ---")
        
        config = SimulationConfig(
            **base_config,
            anisotropy_type=aniso_type,
            output_dir=output_dir,
            **extra_params
        )
        
        solver = ElasticSolver(config)
        
        start_time = time.time()
        results = solver.solve(progress_callback=progress_callback)
        elapsed = time.time() - start_time
        
        results_dict[aniso_type] = results
        print(f"  Completed in {elapsed:.2f}s")
        
        if save_results:
            results['receivers'].save(output_dir)
    
    if show_plots or save_results:
        fig, axes = plt.subplots(1, 3, figsize=(18, 8))
        
        for ax, (aniso_type, results) in zip(axes, results_dict.items()):
            data = results['receivers'].get_seismogram('vz')
            time_axis = results['receivers'].get_time_axis() * 1000
            offset_axis = results['receivers'].get_offset_axis()
            
            plot_wiggle(data, time_axis=time_axis, offset_axis=offset_axis,
                       ax=ax, scale=0.7,
                       title=f'{aniso_type.upper()} - Vz Component',
                       xlabel='Offset (m)', ylabel='Time (ms)')
        
        plt.tight_layout()
        
        if save_results:
            plt.savefig('output/comparison/comparison_shot_gathers.png', dpi=150, bbox_inches='tight')
            print("\nComparison figure saved to output/comparison/")
        
        if show_plots:
            plt.show()
        else:
            plt.close(fig)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        for aniso_type, results in results_dict.items():
            mid_rec = len(results['receivers']) // 2
            data = results['receivers'].get_seismogram('vz', receiver_idx=mid_rec)
            data = data / np.max(np.abs(data))
            time_axis = results['receivers'].get_time_axis() * 1000
            
            ax.plot(time_axis, data, label=aniso_type.upper(), linewidth=1.5, alpha=0.8)
        
        ax.set_xlabel('Time (ms)', fontsize=11)
        ax.set_ylabel('Normalized Amplitude', fontsize=11)
        ax.set_title('Comparison: Center Receiver Vz Component', fontsize=13, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='both', labelsize=10)
        
        if save_results:
            plt.savefig('output/comparison/comparison_traces.png', dpi=150, bbox_inches='tight')
        
        if show_plots:
            plt.show()
        else:
            plt.close(fig)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Elastic Wave Equation Simulator')
    parser.add_argument('--mode', type=str, default='isotropic',
                       choices=['isotropic', 'vti', 'tti', 'shear', 'heterogeneous', 'comparison', 'all'],
                       help='Simulation mode')
    parser.add_argument('--no-plots', action='store_true',
                       help='Disable interactive plots')
    parser.add_argument('--no-save', action='store_true',
                       help='Disable saving results')
    
    args = parser.parse_args()
    
    show_plots = not args.no_plots
    save_results = not args.no_save
    
    try:
        if args.mode == 'isotropic' or args.mode == 'all':
            run_isotropic_simulation(show_plots, save_results)
        
        if args.mode == 'vti' or args.mode == 'all':
            run_vti_simulation(show_plots, save_results)
        
        if args.mode == 'tti' or args.mode == 'all':
            run_tti_simulation(show_plots, save_results)
        
        if args.mode == 'shear' or args.mode == 'all':
            run_shear_source_simulation(show_plots, save_results)
        
        if args.mode == 'heterogeneous' or args.mode == 'all':
            run_heterogeneous_model(show_plots, save_results)
        
        if args.mode == 'comparison' or args.mode == 'all':
            run_comparison_study(show_plots, save_results)
        
        print("\n" + "=" * 70)
        print("All simulations completed successfully!")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\nSimulation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError during simulation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
