import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sar_ship_wake_simulation import SARConfig, SARShipWakeSimulator

np.random.seed(42)

config = SARConfig(
    band='X',
    polarization='VV',
    incidence_angle=30.0,
    image_size=(256, 256),
    pixel_spacing=(2.0, 2.0)
)

simulator = SARShipWakeSimulator(config)
slc, amplitude = simulator.run_simulation(
    ship_speed=12.0,
    ship_length=120.0,
    ship_draft=6.0,
    wind_speed=5.0,
    add_ship_target=True,
    num_looks=2,
    snr=25.0
)

fig = simulator.plot_results(save_path='full_simulation_results.png')
simulator.save_data('full_simulation_data.npz')

results = simulator.get_results()
features = simulator.detect_features()

print('=' * 60)
print('Simulation Results Summary')
print('=' * 60)
print(f'Band: {config.band}, Polarization: {config.polarization}')
print(f'Incidence Angle: {np.rad2deg(config.incidence_angle):.1f} deg')
print(f'Image Size: {config.image_size}')
print()
print('Wake Characteristics (Theoretical):')
wc = results['wake_characteristics']
print(f'  Ship Speed: {wc["ship_speed"]:.1f} m/s')
print(f'  Froude Number: {wc["froude_number"]:.4f}')
print(f'  Transverse Wavelength: {wc["transverse_wavelength"]:.2f} m')
print(f'  Divergent Wavelength: {wc["divergent_wavelength"]:.2f} m')
print(f'  Kelvin Angle: {wc["kelvin_angle"]:.2f} deg')
print()
print('Detected Features:')
print(f'  Mean Wavelength: {features["mean_wavelength"]:.2f} +/- {features["std_wavelength"]:.2f} m')
print(f'  Mean Angle: {features["mean_angle"]:.2f} +/- {features["std_angle"]:.2f} deg')
print(f'  Number of Peaks: {features["num_peaks"]}')
print()
print('SLC Data:')
print(f'  Shape: {slc.shape}, dtype: {slc.dtype}')
print(f'  Mean |SLC|: {np.mean(np.abs(slc)):.4f}')
print(f'  Max |SLC|: {np.max(np.abs(slc)):.4f}')
print()
print('Output files:')
print('  - full_simulation_results.png (visualization)')
print('  - full_simulation_data.npz (SLC, amplitude, height maps)')
print('=' * 60)
plt.close(fig)
print('\nDone!')
