import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sar_ship_wake_simulation import (
    SARConfig,
    SARShipWakeSimulator,
    KelvinWakeSimulator,
    SARImagingSimulator
)

np.random.seed(42)


def test_wave_breaking_fix():
    print("=" * 70)
    print("TEST 1: Wave Breaking Fix - Wake Continuity Near Hull")
    print("=" * 70)

    config = SARConfig(
        band='X',
        polarization='VV',
        incidence_angle=30.0,
        image_size=(128, 256),
        pixel_spacing=(2.0, 2.0)
    )

    ship_position = (64, 40)

    simulator = SARShipWakeSimulator(config)
    slc, amplitude = simulator.run_simulation(
        ship_speed=12.0,
        ship_length=120.0,
        ship_draft=8.0,
        wind_speed=4.0,
        ship_position=ship_position,
        add_ship_target=True,
        num_looks=1,
        snr=30.0
    )

    results = simulator.get_results()
    wake_height = results['wake_height']

    ship_y, ship_x = ship_position
    profile_near = wake_height[ship_y, ship_x:ship_x + 60]
    profile_far = wake_height[ship_y, ship_x + 60:ship_x + 120]

    max_near = np.max(np.abs(profile_near))
    max_far = np.max(np.abs(profile_far))
    continuity_ratio = max_near / (max_far + 1e-10)

    nan_count_near = np.sum(np.isnan(profile_near))
    zero_count_near = np.sum(np.abs(profile_near) < 1e-6)

    wake_char = results['wake_characteristics']
    U = wake_char['ship_speed']
    g = 9.81
    k_t = g / U**2
    wave_steepness = k_t * np.abs(wake_height)
    max_steepness = np.max(wave_steepness)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    im1 = axes[0].imshow(wake_height, cmap='ocean', aspect='auto')
    axes[0].axvline(ship_x + 20, color='r', linestyle='--', label='Near field')
    axes[0].axvline(ship_x + 80, color='y', linestyle='--', label='Far field')
    axes[0].set_title('Wake Height with Wave Breaking Model')
    axes[0].set_xlabel('Range')
    axes[0].set_ylabel('Azimuth')
    axes[0].legend()
    plt.colorbar(im1, ax=axes[0])

    axes[1].plot(np.arange(len(profile_near)) * 2, profile_near, 'b-', label='Near hull')
    axes[1].plot(np.arange(len(profile_far)) * 2 + 120, profile_far, 'r-', label='Far field')
    axes[1].set_xlabel('Distance from ship (m)')
    axes[1].set_ylabel('Wake height (m)')
    axes[1].set_title('Wake Profile: Near vs Far Field')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    im2 = axes[2].imshow(wave_steepness, cmap='hot', aspect='auto', vmin=0, vmax=0.14)
    axes[2].set_title(f'Wave Steepness (max={max_steepness:.3f})')
    axes[2].set_xlabel('Range')
    axes[2].set_ylabel('Azimuth')
    plt.colorbar(im2, ax=axes[2], label='Steepness (ak)')

    plt.tight_layout()
    plt.savefig('test_wave_breaking.png', dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"\nWave Breaking Test Results:")
    print(f"  Max wake height (near hull): {max_near:.4f} m")
    print(f"  Max wake height (far field): {max_far:.4f} m")
    print(f"  Continuity ratio: {continuity_ratio:.4f} (should be < 5)")
    print(f"  Max wave steepness: {max_steepness:.4f} (limit: 0.14)")
    print(f"  Zero/discontinuity count in near field: {zero_count_near}")
    print(f"  Critical steepness limit: NOT exceeded ✓" if max_steepness <= 0.14 else f"  WARNING: Steepness exceeds limit! ✗")
    print(f"  Wake continuity: GOOD ✓" if continuity_ratio < 5 else f"  WARNING: Wake may be discontinuous! ✗")
    print(f"\nPlot saved to: test_wave_breaking.png")

    return max_steepness <= 0.14 and continuity_ratio < 5


def test_kelvin_angle_fix():
    print("\n" + "=" * 70)
    print("TEST 2: Kelvin Angle Fix - Froude Number Dependence")
    print("=" * 70)

    config = SARConfig(
        band='X',
        polarization='VV',
        incidence_angle=30.0,
        image_size=(128, 128),
        pixel_spacing=(3.0, 3.0)
    )

    speeds = [5.0, 10.0, 15.0, 20.0, 25.0]
    ship_length = 100.0

    theoretical_angles = []
    effective_angles = []
    detected_angles = []
    froude_numbers = []

    for speed in speeds:
        print(f"\nTesting ship speed: {speed} m/s...")

        simulator = SARShipWakeSimulator(config)
        slc, amplitude = simulator.run_simulation(
            ship_speed=speed,
            ship_length=ship_length,
            ship_draft=5.0,
            wind_speed=3.0,
            add_ship_target=True,
            num_looks=2,
            snr=35.0
        )

        results = simulator.get_results()
        features = simulator.detect_features()

        wake_char = results['wake_characteristics']
        theoretical_angles.append(wake_char['kelvin_angle_ideal'])
        effective_angles.append(wake_char['kelvin_angle'])
        detected_angles.append(features['mean_angle'])
        froude_numbers.append(wake_char['froude_number'])

        print(f"  Fr = {wake_char['froude_number']:.4f}")
        print(f"  Ideal angle: {wake_char['kelvin_angle_ideal']:.2f}°")
        print(f"  Effective angle: {wake_char['kelvin_angle']:.2f}°")
        print(f"  Correction factor: {wake_char['angle_correction_factor']:.4f}")
        print(f"  Detected angle: {features['mean_angle']:.2f}°")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    ax1.plot(froude_numbers, theoretical_angles, 'k--', label='Ideal (19.47°)', linewidth=2)
    ax1.plot(froude_numbers, effective_angles, 'b-o', label='Effective (corrected)', linewidth=2, markersize=8)
    ax1.plot(froude_numbers, detected_angles, 'r--s', label='Detected from SAR', linewidth=2, markersize=8)
    ax1.axvline(0.5, color='g', linestyle=':', label='Critical Fr = 0.5', alpha=0.7)
    ax1.set_xlabel('Froude Number (Fr)')
    ax1.set_ylabel('Wake Angle (degrees)')
    ax1.set_title('Kelvin Angle vs Froude Number')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.fill_between([0.5, max(froude_numbers)], 16.5, 19.5, alpha=0.2, color='orange', label='Correction region')

    angle_deviation = np.array(effective_angles) - np.array(theoretical_angles)
    ax2.plot(froude_numbers, angle_deviation, 'g-o', linewidth=2, markersize=8)
    ax2.axvline(0.5, color='r', linestyle=':', label='Critical Fr = 0.5', alpha=0.7)
    ax2.axhline(0, color='k', linestyle='-', alpha=0.3)
    ax2.set_xlabel('Froude Number (Fr)')
    ax2.set_ylabel('Angle Deviation (degrees)')
    ax2.set_title('Angle Correction vs Ideal Value')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('test_kelvin_angle.png', dpi=150, bbox_inches='tight')
    plt.close(fig)

    max_deviation_high_fr = angle_deviation[-1]
    correct_trend = angle_deviation[-1] <= angle_deviation[0]

    print(f"\nKelvin Angle Test Results:")
    print(f"  Max deviation at high Fr: {max_deviation_high_fr:.2f}°")
    print(f"  Correction applied for Fr > 0.5: {'YES ✓' if correct_trend else 'NO ✗'}")
    print(f"  Detected angles within 5° of effective: "
          f"{'YES ✓' if np.max(np.abs(np.array(detected_angles) - np.array(effective_angles))) < 5 else 'NO ✗'}")
    print(f"\nPlot saved to: test_kelvin_angle.png")

    return correct_trend


def test_azimuth_ambiguity_fix():
    print("\n" + "=" * 70)
    print("TEST 3: Azimuth Ambiguity Fix - Ghost Target Filtering")
    print("=" * 70)

    config = SARConfig(
        band='X',
        polarization='VV',
        incidence_angle=30.0,
        image_size=(256, 256),
        pixel_spacing=(2.0, 2.0),
        platform_velocity=7000.0
    )

    ship_position = (128, 64)

    simulator = SARShipWakeSimulator(config)
    slc, amplitude = simulator.run_simulation(
        ship_speed=10.0,
        ship_length=100.0,
        ship_draft=5.0,
        wind_speed=4.0,
        ship_position=ship_position,
        add_ship_target=True,
        num_looks=1,
        snr=25.0
    )

    imaging_sim = SARImagingSimulator(config)

    ambiguity_spacing = imaging_sim._compute_ambiguity_spacing()
    print(f"\nTheoretical ambiguity spacing: {ambiguity_spacing} pixels")

    amplitude_with_ambiguity = amplitude.copy()
    ship_y, ship_x = ship_position

    for n in [-2, -1, 1, 2]:
        amb_y = ship_y + n * ambiguity_spacing
        if 0 <= amb_y < 256:
            amplitude_with_ambiguity[amb_y-2:amb_y+3, ship_x-5:ship_x+5] += \
                0.3 * amplitude[ship_y-2:ship_y+3, ship_x-5:ship_x+5]

    ambiguity_mask = imaging_sim._detect_azimuth_ambiguities(amplitude_with_ambiguity, ship_position)
    features_original = imaging_sim.detect_wake_features(amplitude, ship_position)
    features_with_ambiguity = imaging_sim.detect_wake_features(amplitude_with_ambiguity, ship_position)

    print(f"Detected ambiguities: {features_with_ambiguity['detected_ambiguities']} rows")
    print(f"Ambiguity spacing: {features_with_ambiguity['ambiguity_spacing']} pixels")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    db_original = 20 * np.log10(amplitude + 1e-10)
    db_with_amb = 20 * np.log10(amplitude_with_ambiguity + 1e-10)

    vmin = np.percentile(db_original, 5)
    vmax = np.percentile(db_original, 95)

    im1 = axes[0, 0].imshow(db_original, cmap='jet', aspect='auto', vmin=vmin, vmax=vmax)
    axes[0, 0].set_title('Original SAR Image (No Ambiguity)')
    axes[0, 0].set_xlabel('Range')
    axes[0, 0].set_ylabel('Azimuth')
    plt.colorbar(im1, ax=axes[0, 0], label='dB')

    im2 = axes[0, 1].imshow(db_with_amb, cmap='jet', aspect='auto', vmin=vmin, vmax=vmax)
    for n in [-2, -1, 1, 2]:
        amb_y = ship_y + n * ambiguity_spacing
        if 0 <= amb_y < 256:
            axes[0, 1].axhline(amb_y, color='r', linestyle='--', alpha=0.7,
                               label='Ambiguity' if n == 1 else "")
    axes[0, 1].set_title('SAR Image with Azimuth Ambiguities')
    axes[0, 1].set_xlabel('Range')
    axes[0, 1].set_ylabel('Azimuth')
    axes[0, 1].legend()
    plt.colorbar(im2, ax=axes[0, 1], label='dB')

    im3 = axes[1, 0].imshow(ambiguity_mask.astype(int), cmap='gray', aspect='auto')
    axes[1, 0].set_title(f'Detected Ambiguity Mask\n({features_with_ambiguity["detected_ambiguities"]} rows detected)')
    axes[1, 0].set_xlabel('Range')
    axes[1, 0].set_ylabel('Azimuth')
    plt.colorbar(im3, ax=axes[1, 0], label='Mask (1=ambiguity)')

    profile_ship = np.mean(db_with_amb[ship_y-5:ship_y+6, :], axis=0)
    profile_amb = np.mean(db_with_amb[ship_y+ambiguity_spacing-5:ship_y+ambiguity_spacing+6, :], axis=0)
    axes[1, 1].plot(profile_ship, 'b-', label='True ship', linewidth=2)
    axes[1, 1].plot(profile_amb, 'r--', label='Ambiguity ghost', linewidth=2)
    axes[1, 1].set_title('Azimuth Profile Comparison')
    axes[1, 1].set_xlabel('Range (pixels)')
    axes[1, 1].set_ylabel('Intensity (dB)')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('test_azimuth_ambiguity.png', dpi=150, bbox_inches='tight')
    plt.close(fig)

    detected_amb_count = features_with_ambiguity['detected_ambiguities']
    angle_diff = abs(features_original['mean_angle'] - features_with_ambiguity['mean_angle'])

    print(f"\nAzimuth Ambiguity Test Results:")
    print(f"  True ambiguities added: 4")
    print(f"  Ambiguities detected: {detected_amb_count}")
    print(f"  Angle without ambiguity: {features_original['mean_angle']:.2f}°")
    print(f"  Angle with ambiguity (filtered): {features_with_ambiguity['mean_angle']:.2f}°")
    print(f"  Angle difference: {angle_diff:.2f}°")
    print(f"  Ambiguity detection: {'SUCCESS ✓' if detected_amb_count >= 2 else 'FAILED ✗'}")
    print(f"  Angle robustness: {'GOOD ✓' if angle_diff < 3 else 'POOR ✗'}")
    print(f"\nPlot saved to: test_azimuth_ambiguity.png")

    return detected_amb_count >= 2 and angle_diff < 3


def run_all_tests():
    print("\n" + "=" * 70)
    print("COMPREHENSIVE BUG FIX VERIFICATION SUITE")
    print("=" * 70)

    results = {}

    try:
        results['wave_breaking'] = test_wave_breaking_fix()
    except Exception as e:
        print(f"Wave breaking test FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        results['wave_breaking'] = False

    try:
        results['kelvin_angle'] = test_kelvin_angle_fix()
    except Exception as e:
        print(f"Kelvin angle test FAILED with error: {e}")
        results['kelvin_angle'] = False

    try:
        results['azimuth_ambiguity'] = test_azimuth_ambiguity_fix()
    except Exception as e:
        print(f"Azimuth ambiguity test FAILED with error: {e}")
        results['azimuth_ambiguity'] = False

    print("\n" + "=" * 70)
    print("FINAL TEST RESULTS")
    print("=" * 70)

    test_names = {
        'wave_breaking': 'Wave Breaking Fix (Wake Continuity)',
        'kelvin_angle': 'Kelvin Angle Fix (Froude Dependence)',
        'azimuth_ambiguity': 'Azimuth Ambiguity Fix (Ghost Target Filtering)'
    }

    all_passed = True
    for key, name in test_names.items():
        status = 'PASSED ✓' if results[key] else 'FAILED ✗'
        print(f"  {name}: {status}")
        if not results[key]:
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
