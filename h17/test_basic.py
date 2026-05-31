import sys
import numpy as np

print('Testing imports...')

from config import SimulationConfig
print('✓ config imported')

from fd_coefficients import get_fd_coefficients, StaggeredGrid
print('✓ fd_coefficients imported')

from cpml import CPML
print('✓ cpml imported')

from medium import Medium
print('✓ medium imported')

from source import Source, ricker_wavelet
print('✓ source imported')

from receiver import ReceiverArray, ParticleMotionRecorder
print('✓ receiver imported')

from solver import ElasticSolver
print('✓ solver imported')

from visualization import plot_wiggle, plot_snapshot, animate_snapshots, plot_particle_motion
print('✓ visualization imported')

from parallel import ParallelManager, check_parallel_availability, print_system_info
print('✓ parallel imported')

print()
print('Testing basic functionality...')

config = SimulationConfig(
    nx=50, nz=50, dx=10.0, dz=10.0, dt=0.001, nt=10,
    space_order=4, vp=3000, vs=1732, rho=2500,
    source_x=25, source_z=25,
    receiver_x_start=10, receiver_x_end=40, receiver_z=5,
    output_dir='test_output',
    dtype=np.float64
)
print(f'✓ Config created: {config.nx}x{config.nz} grid, {config.nt} time steps')
print(f'  CFL number: {config.cfl:.4f}')
print(f'  Anisotropy type: {config.anisotropy_type}')

coeffs = get_fd_coefficients(4)
print(f'✓ FD coefficients for 4th order: {coeffs}')

coeffs_12 = get_fd_coefficients(12)
print(f'✓ FD coefficients for 12th order: {len(coeffs_12)} terms')

t = np.arange(100) * 0.001
w = ricker_wavelet(t, f0=20.0, t0=0.05)
print(f'✓ Ricker wavelet generated, max amplitude: {np.max(np.abs(w)):.4e}')

medium = Medium(nx=50, nz=50, dx=10, dz=10, vp=3000, vs=1732, rho=2500)
print(f'✓ Isotropic medium created')
print(f'  Vp range: {medium.get_velocity("p").min():.1f} - {medium.get_velocity("p").max():.1f} m/s')

medium_vti = Medium(nx=50, nz=50, dx=10, dz=10, vp=3000, vs=1732, rho=2500,
                    anisotropy_type='vti', epsilon=0.15, delta=0.08, gamma=0.1)
print(f'✓ VTI medium created')
print(f'  ε={medium_vti.epsilon}, δ={medium_vti.delta}, γ={medium_vti.gamma}')

medium_tti = Medium(nx=50, nz=50, dx=10, dz=10, vp=3000, vs=1732, rho=2500,
                    anisotropy_type='tti', epsilon=0.15, delta=0.08, gamma=0.1, theta=30)
print(f'✓ TTI medium created, tilt angle: {medium_tti.theta}°')

cpml = CPML(nx=50, nz=50, dx=10, dz=10, dt=0.001, width=10)
print(f'✓ CPML created with width: {cpml.width} points')

source = Source(nx=50, nz=50, dx=10, dz=10, dt=0.001, nt=100,
                source_type='explosive', sx=25, sz=25, f0=20, amplitude=1e9)
print(f'✓ Source created: {source.source_type} at ({source.sx}, {source.sz})')
print(f'  Wavelet length: {len(source.wavelet)} samples')

receivers = ReceiverArray(nx=50, nz=50, dx=10, dz=10, dt=0.001, nt=100,
                          array_type='surface', rx_start=10, rx_end=40, rz=5, spacing=2)
print(f'✓ Receiver array created: {len(receivers)} receivers')

solver = ElasticSolver(config)
print(f'✓ Solver created successfully')
print(f'  FD half order: {solver.half_order}')
print(f'  Number of coefficients: {len(solver.fd_coeffs)}')

print()
print_system_info()

print()
print('All basic tests passed! ✓')
