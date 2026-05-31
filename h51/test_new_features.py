import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sar_ship_wake_simulation import (
    SARConfig,
    SARShipWakeSimulator,
    OceanDensityProfile,
    InternalWakeSimulator,
    MultiShipWakeSimulator,
    WakeModulationSimulator
)

np.random.seed(42)


def test_internal_wake_simulation():
    print("=" * 70)
    print("TEST 1: Internal Wave Wake Simulation (Density Stratified Ocean)")
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

    simulator = SARShipWakeSimulator(config, density_profile)
    ship_position = (64, 50)

    slc, amplitude = simulator.run_simulation(
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
        include_ocean_internal_waves=True,
        apply_internal_wave_modulation=False
    )

    results = simulator.get_results()
    int_char = results.get('internal_wake_characteristics', {})

    print("\nOcean Density Profile:")
    print(f"  Surface density: {density_profile.rho_surface} kg/m³")
    print(f"  Bottom density: {density_profile.rho_bottom} kg/m³")
    print(f"  Density difference: {density_profile.drho} kg/m³")
    print(f"  Pycnocline depth: {density_profile.pycnocline_depth} m")

    print("\nInternal Wave Characteristics:")
    print(f"  Mode 1 wave speed: {int_char.get('mode1_speed', 0):.2f} m/s")
    print(f"  Internal Froude number: {int_char.get('internal_froude_number', 0):.4f}")
    print(f"  Internal wake angle: {int_char.get('internal_wake_angle', 0):.2f}°")
    print(f"  Internal wavelength: {int_char.get('internal_wavelength', 0):.1f} m")
    print(f"  Lee wave period: {int_char.get('lee_wave_period', 0):.1f} m")
    print(f"  Regime: {int_char.get('regime', 'unknown')}")
    print(f"  Buoyancy frequency: {int_char.get('buoyancy_frequency', 0):.4f} rad/s")

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    im1 = axes[0, 0].imshow(results['sea_height'], cmap='ocean', aspect='auto')
    axes[0, 0].set_title('Sea Surface Height')
    plt.colorbar(im1, ax=axes[0, 0])

    im2 = axes[0, 1].imshow(results['wake_height'], cmap='ocean', aspect='auto')
    axes[0, 1].set_title('Surface Kelvin Wake Height')
    plt.colorbar(im2, ax=axes[0, 1])

    if results['internal_wake_height'] is not None:
        im3 = axes[0, 2].imshow(results['internal_wake_height'], cmap='ocean', aspect='auto')
        axes[0, 2].set_title('Internal Wave Wake Height')
        plt.colorbar(im3, ax=axes[0, 2])

    if results['ocean_internal_waves'] is not None:
        im4 = axes[1, 0].imshow(results['ocean_internal_waves'], cmap='ocean', aspect='auto')
        axes[1, 0].set_title('Background Ocean Internal Waves')
        plt.colorbar(im4, ax=axes[1, 0])

    im5 = axes[1, 1].imshow(results['total_wake_height'], cmap='ocean', aspect='auto')
    axes[1, 1].set_title('Total Wake (Surface + Internal)')
    plt.colorbar(im5, ax=axes[1, 1])

    db_image = 20 * np.log10(amplitude + 1e-10)
    im6 = axes[1, 2].imshow(db_image, cmap='jet', aspect='auto',
                             vmin=np.percentile(db_image, 5), vmax=np.percentile(db_image, 95))
    axes[1, 2].set_title('SAR Amplitude Image [dB]')
    plt.colorbar(im6, ax=axes[1, 2])

    plt.tight_layout()
    plt.savefig('test_internal_wake.png', dpi=150, bbox_inches='tight')
    plt.close(fig)

    wake_std = np.std(results['total_wake_height'])
    internal_wake_std = np.std(results['internal_wake_height']) if results['internal_wake_height'] is not None else 0
    test_passed = internal_wake_std > 0.1 and wake_std > 0.1

    print(f"\nTest Results:")
    print(f"  Surface wake std: {np.std(results['wake_height']):.4f} m")
    print(f"  Internal wake std: {internal_wake_std:.4f} m")
    print(f"  Total wake std: {wake_std:.4f} m")
    print(f"  Test: {'PASSED ✓' if test_passed else 'FAILED ✗'}")
    print(f"  Plot saved to: test_internal_wake.png")

    return test_passed


def test_multiship_interference():
    print("\n" + "=" * 70)
    print("TEST 2: Multi-Ship Wake Interference")
    print("=" * 70)

    config = SARConfig(
        band='X',
        polarization='VV',
        incidence_angle=30.0,
        image_size=(256, 256),
        pixel_spacing=(2.0, 2.0)
    )

    simulator = SARShipWakeSimulator(config)

    ship_list = [
        {
            'speed': 12.0,
            'length': 150.0,
            'draft': 8.0,
            'position': (80, 60),
            'heading': 0.0
        },
        {
            'speed': 10.0,
            'length': 120.0,
            'draft': 6.0,
            'position': (180, 100),
            'heading': 30.0
        }
    ]

    slc, amplitude = simulator.run_simulation(
        ship_list=ship_list,
        wind_speed=4.0,
        add_ship_target=True,
        num_looks=1,
        snr=25.0,
        include_internal_wake=False,
        include_ocean_internal_waves=False,
        apply_internal_wave_modulation=False
    )

    results = simulator.get_results()

    print("\nShip Configurations:")
    for i, ship in enumerate(ship_list):
        print(f"  Ship {i+1}: speed={ship['speed']} m/s, length={ship['length']} m, "
              f"position={ship['position']}, heading={ship['heading']}°")

    print("\nWake Characteristics:")
    for i, char in enumerate(results['ship_wake_characteristics']):
        print(f"  Ship {i+1}: Fr={char['froude_number']:.4f}, "
              f"Kelvin angle={char['kelvin_angle']:.2f}°, "
              f"λ_t={char['transverse_wavelength']:.1f} m")

    if results['individual_wakes'] is not None and len(results['individual_wakes']) >= 2:
        wake1 = results['individual_wakes'][0]['height']
        wake2 = results['individual_wakes'][1]['height']
        total_wake = results['total_wake_height']

        linear_sum = wake1 + wake2
        interference_pattern = total_wake - linear_sum
        interference_energy = np.sum(interference_pattern**2)
        total_energy = np.sum(total_wake**2)
        interference_ratio = interference_energy / total_energy

        constructive = np.sum(interference_pattern > 0.1 * np.max(total_wake))
        destructive = np.sum(interference_pattern < -0.1 * np.max(total_wake))

        print("\nInterference Analysis:")
        print(f"  Interference energy ratio: {interference_ratio:.4f}")
        print(f"  Constructive interference pixels: {constructive}")
        print(f"  Destructive interference pixels: {destructive}")

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    if results['individual_wakes'] is not None and len(results['individual_wakes']) >= 2:
        im1 = axes[0, 0].imshow(results['individual_wakes'][0]['height'], cmap='ocean', aspect='auto')
        axes[0, 0].set_title('Ship 1 Individual Wake')
        axes[0, 0].plot(ship_list[0]['position'][1], ship_list[0]['position'][0], 'r*', markersize=12, label='Ship 1')
        axes[0, 0].legend()
        plt.colorbar(im1, ax=axes[0, 0])

        im2 = axes[0, 1].imshow(results['individual_wakes'][1]['height'], cmap='ocean', aspect='auto')
        axes[0, 1].set_title('Ship 2 Individual Wake')
        axes[0, 1].plot(ship_list[1]['position'][1], ship_list[1]['position'][0], 'r*', markersize=12, label='Ship 2')
        axes[0, 1].legend()
        plt.colorbar(im2, ax=axes[0, 1])

        linear_sum = results['individual_wakes'][0]['height'] + results['individual_wakes'][1]['height']
        interference = results['total_wake_height'] - linear_sum
        im3 = axes[0, 2].imshow(interference, cmap='seismic', aspect='auto',
                                vmin=-np.max(np.abs(interference)), vmax=np.max(np.abs(interference)))
        axes[0, 2].set_title('Nonlinear Interference Pattern')
        plt.colorbar(im3, ax=axes[0, 2], label='Interference')

        im4 = axes[1, 0].imshow(linear_sum, cmap='ocean', aspect='auto')
        axes[1, 0].set_title('Linear Superposition')
        plt.colorbar(im4, ax=axes[1, 0])

        im5 = axes[1, 1].imshow(results['total_wake_height'], cmap='ocean', aspect='auto')
        axes[1, 1].set_title('Total Wake with Nonlinear Interference')
        for ship in ship_list:
            axes[1, 1].plot(ship['position'][1], ship['position'][0], 'r*', markersize=10)
        plt.colorbar(im5, ax=axes[1, 1])

        db_image = 20 * np.log10(amplitude + 1e-10)
        im6 = axes[1, 2].imshow(db_image, cmap='jet', aspect='auto',
                                 vmin=np.percentile(db_image, 5), vmax=np.percentile(db_image, 95))
        axes[1, 2].set_title('SAR Image with Two Ship Wakes [dB]')
        for ship in ship_list:
            axes[1, 2].plot(ship['position'][1], ship['position'][0], 'r*', markersize=10)
        plt.colorbar(im6, ax=axes[1, 2])

    plt.tight_layout()
    plt.savefig('test_multiship_interference.png', dpi=150, bbox_inches='tight')
    plt.close(fig)

    test_passed = interference_ratio > 0.01 if 'interference_ratio' in locals() else False
    print(f"\nTest Results:")
    print(f"  Interference ratio: {interference_ratio:.4f}" if 'interference_ratio' in locals() else "  Interference ratio: N/A")
    print(f"  Test: {'PASSED ✓' if test_passed else 'FAILED ✗'}")
    print(f"  Plot saved to: test_multiship_interference.png")

    return test_passed


def test_internal_wave_modulation():
    print("\n" + "=" * 70)
    print("TEST 3: Internal Wave Modulation of Ship Wake")
    print("=" * 70)

    config = SARConfig(
        band='X',
        polarization='VV',
        incidence_angle=30.0,
        image_size=(128, 256),
        pixel_spacing=(3.0, 3.0)
    )

    density_profile = OceanDensityProfile()
    simulator = SARShipWakeSimulator(config, density_profile)

    ship_position = (64, 50)

    slc_no_mod, amp_no_mod = simulator.run_simulation(
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
        apply_internal_wave_modulation=False
    )

    results_no_mod = simulator.get_results()

    slc_with_mod, amp_with_mod = simulator.run_simulation(
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

    results_with_mod = simulator.get_results()

    modulation_simulator = WakeModulationSimulator(config, density_profile)
    k_values = np.linspace(0.001, 0.1, 100)
    k_wake = 9.81 / 10.0**2

    mtf_values = []
    for k in k_values:
        mtf = modulation_simulator.modulation_transfer_function(k_wake, k)
        mtf_values.append(mtf)

    print("\nModulation Transfer Function (MTF) Analysis:")
    print(f"  Surface wake wavenumber (k_wake): {k_wake:.4f} rad/m")
    print(f"  Surface wake wavelength: {2 * np.pi / k_wake:.1f} m")
    print(f"  Max MTF value: {np.max(mtf_values):.4f}")
    print(f"  Resonance occurs at k = {k_values[np.argmax(mtf_values)]:.4f} rad/m")

    if results_with_mod['modulated_wake_height'] is not None and results_with_mod['wake_height'] is not None:
        modulation_effect = results_with_mod['modulated_wake_height'] - results_with_mod['wake_height']
        modulation_amplitude = np.std(modulation_effect)
        wake_amplitude = np.std(results_with_mod['wake_height'])
        modulation_depth = modulation_amplitude / wake_amplitude

        spectrum_original = np.abs(np.fft.fft2(results_with_mod['wake_height']))**2
        spectrum_modulated = np.abs(np.fft.fft2(results_with_mod['modulated_wake_height']))**2

        spectral_diff = np.mean(np.abs(spectrum_modulated - spectrum_original)) / np.mean(spectrum_original)

        print("\nModulation Effects:")
        print(f"  Modulation amplitude: {modulation_amplitude:.4f} m")
        print(f"  Wake amplitude: {wake_amplitude:.4f} m")
        print(f"  Modulation depth: {modulation_depth:.2%}")
        print(f"  Spectral difference: {spectral_diff:.4%}")

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    im1 = axes[0, 0].imshow(results_no_mod['wake_height'], cmap='ocean', aspect='auto')
    axes[0, 0].set_title('Original Kelvin Wake (No Modulation)')
    plt.colorbar(im1, ax=axes[0, 0])

    if results_with_mod['modulated_wake_height'] is not None:
        im2 = axes[0, 1].imshow(results_with_mod['modulated_wake_height'], cmap='ocean', aspect='auto')
        axes[0, 1].set_title('Modulated Wake Height')
        plt.colorbar(im2, ax=axes[0, 1])

        modulation_effect = results_with_mod['modulated_wake_height'] - results_with_mod['wake_height']
        im3 = axes[0, 2].imshow(modulation_effect, cmap='seismic', aspect='auto',
                                vmin=-np.max(np.abs(modulation_effect)), vmax=np.max(np.abs(modulation_effect)))
        axes[0, 2].set_title('Modulation Effect (Difference)')
        plt.colorbar(im3, ax=axes[0, 2], label='Modulation [m]')

    if results_with_mod['ocean_internal_waves'] is not None:
        im4 = axes[1, 0].imshow(results_with_mod['ocean_internal_waves'], cmap='ocean', aspect='auto')
        axes[1, 0].set_title('Background Internal Waves')
        plt.colorbar(im4, ax=axes[1, 0])

    axes[1, 1].plot(k_values, mtf_values, 'b-', linewidth=2)
    axes[1, 1].axvline(k_wake, color='r', linestyle='--', label=f'k_wake = {k_wake:.4f} rad/m')
    axes[1, 1].set_xlabel('Internal Wave Wavenumber [rad/m]')
    axes[1, 1].set_ylabel('Modulation Transfer Function')
    axes[1, 1].set_title('MTF vs Internal Wave Wavenumber')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    db_no_mod = 20 * np.log10(amp_no_mod + 1e-10)
    db_with_mod = 20 * np.log10(amp_with_mod + 1e-10)
    db_diff = db_with_mod - db_no_mod

    vmin = np.percentile(db_no_mod, 5)
    vmax = np.percentile(db_no_mod, 95)

    im6 = axes[1, 2].imshow(db_diff, cmap='seismic', aspect='auto',
                            vmin=-np.max(np.abs(db_diff)), vmax=np.max(np.abs(db_diff)))
    axes[1, 2].set_title('SAR Image Difference (With - Without Modulation) [dB]')
    plt.colorbar(im6, ax=axes[1, 2], label='Δ dB')

    plt.tight_layout()
    plt.savefig('test_wake_modulation.png', dpi=150, bbox_inches='tight')
    plt.close(fig)

    test_passed = np.max(mtf_values) > 0.01
    print(f"\nTest Results:")
    print(f"  Max MTF: {np.max(mtf_values):.4f}")
    print(f"  Test: {'PASSED ✓' if test_passed else 'FAILED ✗'}")
    print(f"  Plot saved to: test_wake_modulation.png")

    return test_passed


def test_combined_simulation():
    print("\n" + "=" * 70)
    print("TEST 4: Combined Simulation - All Features Together")
    print("=" * 70)

    config = SARConfig(
        band='C',
        polarization='VV',
        incidence_angle=35.0,
        image_size=(256, 256),
        pixel_spacing=(2.0, 2.0)
    )

    density_profile = OceanDensityProfile(
        rho_surface=1024.5,
        rho_bottom=1028.0,
        pycnocline_depth=60.0,
        pycnocline_thickness=25.0
    )

    simulator = SARShipWakeSimulator(config, density_profile)

    ship_list = [
        {
            'speed': 10.0,
            'length': 130.0,
            'draft': 7.0,
            'position': (80, 50),
            'heading': 5.0
        },
        {
            'speed': 14.0,
            'length': 160.0,
            'draft': 9.0,
            'position': (180, 80),
            'heading': -10.0
        }
    ]

    print("\nRunning full combined simulation...")
    print("This includes:")
    print("  - Multi-ship nonlinear wake interference")
    print("  - Internal wave wakes for each ship")
    print("  - Background ocean internal waves")
    print("  - Internal wave modulation of surface wakes")
    print()

    slc, amplitude = simulator.run_simulation(
        ship_list=ship_list,
        wind_speed=6.0,
        add_ship_target=True,
        num_looks=2,
        snr=25.0,
        include_internal_wake=True,
        include_ocean_internal_waves=True,
        apply_internal_wave_modulation=True
    )

    results = simulator.get_results()

    print("\nSimulation Summary:")
    print(f"  Simulation mode: {results['simulation_mode']}")
    print(f"  Number of ships: {len(ship_list)}")
    print(f"  SLC shape: {slc.shape}, dtype: {slc.dtype}")
    print(f"  Amplitude range: [{np.min(amplitude):.4f}, {np.max(amplitude):.4f}]")

    print("\nDetected Features:")
    features = simulator.detect_features(ship_position=ship_list[0]['position'])
    print(f"  Mean wavelength: {features['mean_wavelength']:.2f} ± {features['std_wavelength']:.2f} m")
    print(f"  Mean angle: {features['mean_angle']:.2f} ± {features['std_angle']:.2f}°")
    print(f"  Number of peaks: {features['num_peaks']}")

    fig = simulator.plot_results(save_path='test_combined_simulation.png')
    simulator.save_data('combined_simulation_data.npz')

    plt.close(fig)

    test_passed = slc is not None and np.mean(amplitude) > 0
    print(f"\nTest Results:")
    print(f"  SLC generated: {'YES ✓' if slc is not None else 'NO ✗'}")
    print(f"  Mean amplitude: {np.mean(amplitude):.4f}")
    print(f"  Test: {'PASSED ✓' if test_passed else 'FAILED ✗'}")
    print(f"  Plot saved to: test_combined_simulation.png")
    print(f"  Data saved to: combined_simulation_data.npz")

    return test_passed


def run_all_tests():
    print("\n" + "=" * 70)
    print("COMPREHENSIVE NEW FEATURES VERIFICATION SUITE")
    print("=" * 70)

    results = {}
    test_names = {
        'internal_wake': 'Internal Wave Wake Simulation',
        'multiship': 'Multi-Ship Wake Interference',
        'modulation': 'Internal Wave Modulation',
        'combined': 'Combined Full Simulation'
    }

    try:
        results['internal_wake'] = test_internal_wake_simulation()
    except Exception as e:
        print(f"Internal wave test FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        results['internal_wake'] = False

    try:
        results['multiship'] = test_multiship_interference()
    except Exception as e:
        print(f"Multi-ship test FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        results['multiship'] = False

    try:
        results['modulation'] = test_internal_wave_modulation()
    except Exception as e:
        print(f"Modulation test FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        results['modulation'] = False

    try:
        results['combined'] = test_combined_simulation()
    except Exception as e:
        print(f"Combined test FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        results['combined'] = False

    print("\n" + "=" * 70)
    print("FINAL TEST RESULTS")
    print("=" * 70)

    all_passed = True
    for key, name in test_names.items():
        status = 'PASSED ✓' if results.get(key, False) else 'FAILED ✗'
        print(f"  {name}: {status}")
        if not results.get(key, False):
            all_passed = False

    print("-" * 70)
    if all_passed:
        print("  ALL TESTS PASSED! ✓✓✓")
    else:
        print("  SOME TESTS FAILED - Review the output above")
    print("=" * 70)

    return all_passed


if __name__ == '__main__':
    import time
    start_time = time.time()

    run_all_tests()

    elapsed = time.time() - start_time
    print(f"\nTotal test time: {elapsed:.2f} seconds")
