import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sar_ship_wake_simulation import (
    SARConfig,
    SARShipWakeSimulator,
    OceanDensityProfile
)

np.random.seed(42)

print("=" * 70)
print("INTEGRATED DEMO: Internal Waves + Multi-Ship + Modulation")
print("=" * 70)

density_profile = OceanDensityProfile(
    rho_surface=1025.0,
    rho_bottom=1028.5,
    pycnocline_depth=50.0,
    pycnocline_thickness=20.0
)

config = SARConfig(
    band='X',
    polarization='VV',
    incidence_angle=30.0,
    image_size=(128, 256),
    pixel_spacing=(3.0, 3.0)
)

print("\nOcean Density Profile:")
print(f"  Surface density: {density_profile.rho_surface} kg/m3")
print(f"  Bottom density: {density_profile.rho_bottom} kg/m3")
print(f"  Pycnocline depth: {density_profile.pycnocline_depth} m")
print(f"  Mode-1 internal wave speed: {density_profile.get_mode_1_speed():.2f} m/s")

print("\n" + "-" * 70)
print("DEMO 1: Single ship with internal wave wake")
print("-" * 70)

simulator = SARShipWakeSimulator(config, density_profile)
ship_position = (64, 60)

slc1, amp1 = simulator.run_simulation(
    ship_speed=8.0,
    ship_length=120.0,
    ship_draft=6.0,
    wind_speed=5.0,
    ship_position=ship_position,
    ship_heading=0.0,
    add_ship_target=True,
    num_looks=1,
    snr=25.0,
    include_internal_wake=True,
    include_ocean_internal_waves=False,
    apply_internal_wave_modulation=False
)

results1 = simulator.get_results()
int_char = results1.get('internal_wake_characteristics', {})

print("\nInternal Wave Wake Characteristics:")
print(f"  Ship speed: 8.0 m/s")
print(f"  Internal Froude number: {int_char.get('internal_froude_number', 0):.4f}")
print(f"  Regime: {int_char.get('regime', 'unknown')}")
print(f"  Internal wake angle: {int_char.get('internal_wake_angle', 0):.2f} deg")
print(f"  Internal wavelength: {int_char.get('internal_wavelength', 0):.1f} m")
print(f"  Buoyancy frequency: {int_char.get('buoyancy_frequency', 0):.4f} rad/s")

fig1 = simulator.plot_results(save_path='demo1_internal_wake.png')
plt.close(fig1)
print("\n  Plot saved to: demo1_internal_wake.png")

print("\n" + "-" * 70)
print("DEMO 2: Two ships with nonlinear interference")
print("-" * 70)

ship_list = [
    {
        'speed': 10.0,
        'length': 130.0,
        'draft': 7.0,
        'position': (40, 50),
        'heading': 0.0
    },
    {
        'speed': 12.0,
        'length': 110.0,
        'draft': 6.0,
        'position': (88, 80),
        'heading': 15.0
    }
]

simulator2 = SARShipWakeSimulator(config, density_profile)
slc2, amp2 = simulator2.run_simulation(
    ship_list=ship_list,
    wind_speed=4.0,
    add_ship_target=True,
    num_looks=1,
    snr=25.0,
    include_internal_wake=False,
    include_ocean_internal_waves=False,
    apply_internal_wave_modulation=False
)

results2 = simulator2.get_results()

print("\nShip Configurations:")
for i, ship in enumerate(ship_list):
    print(f"  Ship {i+1}: speed={ship['speed']} m/s, length={ship['length']} m, "
          f"position={ship['position']}, heading={ship['heading']} deg")

if results2['individual_wakes'] is not None and len(results2['individual_wakes']) >= 2:
    wake1 = results2['individual_wakes'][0]['height']
    wake2 = results2['individual_wakes'][1]['height']
    total = results2['total_wake_height']
    linear_sum = wake1 + wake2
    interference = total - linear_sum

    interference_energy = np.sum(interference**2)
    total_energy = np.sum(total**2)
    ratio = interference_energy / total_energy

    print("\nInterference Analysis:")
    print(f"  Interference energy ratio: {ratio:.4f}")
    print(f"  Constructive interference: {np.sum(interference > 0.05 * np.max(total))} pixels")
    print(f"  Destructive interference: {np.sum(interference < -0.05 * np.max(total))} pixels")

fig2 = simulator2.plot_results(save_path='demo2_multiship.png')
plt.close(fig2)
print("\n  Plot saved to: demo2_multiship.png")

print("\n" + "-" * 70)
print("DEMO 3: Internal wave modulation of ship wake")
print("-" * 70)

simulator3 = SARShipWakeSimulator(config, density_profile)

slc3, amp3 = simulator3.run_simulation(
    ship_speed=10.0,
    ship_length=100.0,
    ship_draft=5.0,
    wind_speed=5.0,
    ship_position=ship_position,
    add_ship_target=True,
    num_looks=1,
    snr=30.0,
    include_internal_wake=False,
    include_ocean_internal_waves=True,
    apply_internal_wave_modulation=True
)

results3 = simulator3.get_results()

if results3['modulated_wake_height'] is not None and results3['wake_height'] is not None:
    mod_effect = results3['modulated_wake_height'] - results3['wake_height']
    mod_amp = np.std(mod_effect)
    wake_amp = np.std(results3['wake_height'])
    mod_depth = mod_amp / wake_amp

    print("\nModulation Analysis:")
    print(f"  Original wake amplitude: {wake_amp:.4f} m")
    print(f"  Modulation amplitude: {mod_amp:.4f} m")
    print(f"  Modulation depth: {mod_depth:.2%}")
    print(f"  Modulation max: {np.max(mod_effect):.4f} m")
    print(f"  Modulation min: {np.min(mod_effect):.4f} m")

    spec_orig = np.abs(np.fft.fft2(results3['wake_height']))**2
    spec_mod = np.abs(np.fft.fft2(results3['modulated_wake_height']))**2
    spec_diff = np.mean(np.abs(spec_mod - spec_orig)) / np.mean(spec_orig)
    print(f"  Spectral difference: {spec_diff:.4%}")

fig3 = simulator3.plot_results(save_path='demo3_modulation.png')
plt.close(fig3)
print("\n  Plot saved to: demo3_modulation.png")

print("\n" + "-" * 70)
print("DEMO 4: Full integrated simulation (ALL features)")
print("-" * 70)

simulator4 = SARShipWakeSimulator(config, density_profile)

slc4, amp4 = simulator4.run_simulation(
    ship_list=ship_list,
    wind_speed=5.0,
    add_ship_target=True,
    num_looks=2,
    snr=25.0,
    include_internal_wake=True,
    include_ocean_internal_waves=True,
    apply_internal_wave_modulation=True
)

results4 = simulator4.get_results()
features4 = simulator4.detect_features(ship_position=ship_list[0]['position'])

print("\nFull Integrated Simulation Results:")
print(f"  Simulation mode: {results4['simulation_mode']}")
print(f"  Ships: {len(ship_list)}")
print(f"  SLC shape: {slc4.shape}, dtype: {slc4.dtype}")
print(f"  Amplitude range: [{np.min(amp4):.4f}, {np.max(amp4):.4f}]")

print("\nDetected Wake Features:")
print(f"  Mean wavelength: {features4['mean_wavelength']:.2f} +/- {features4['std_wavelength']:.2f} m")
print(f"  Mean angle: {features4['mean_angle']:.2f} +/- {features4['std_angle']:.2f} deg")
print(f"  Number of peaks: {features4['num_peaks']}")
print(f"  Detected ambiguities: {features4['detected_ambiguities']} rows")

simulator4.save_data('full_integrated_simulation.npz')
fig4 = simulator4.plot_results(save_path='demo4_full_integrated.png')
plt.close(fig4)
print("\n  Data saved to: full_integrated_simulation.npz")
print("  Plot saved to: demo4_full_integrated.png")

print("\n" + "=" * 70)
print("ALL DEMOS COMPLETED SUCCESSFULLY!")
print("=" * 70)
print("\nGenerated files:")
print("  - demo1_internal_wake.png")
print("  - demo2_multiship.png")
print("  - demo3_modulation.png")
print("  - demo4_full_integrated.png")
print("  - full_integrated_simulation.npz")
print("\nNew classes added:")
print("  - OceanDensityProfile: Ocean density stratification model")
print("  - InternalWakeSimulator: Internal wave wake generation")
print("  - MultiShipWakeSimulator: Multi-ship wake interference")
print("  - WakeModulationSimulator: Internal wave modulation effects")
print("\nNew features in SARShipWakeSimulator:")
print("  - ship_list parameter for multi-ship simulation")
print("  - include_internal_wake: Add internal wave wakes")
print("  - include_ocean_internal_waves: Add background internal waves")
print("  - apply_internal_wave_modulation: Apply MTF-based modulation")
print("  - ship_heading: Support for arbitrary ship headings")
print("=" * 70)
