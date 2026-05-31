import numpy as np
import matplotlib.pyplot as plt
from sar_ship_wake_simulation import (
    SARConfig,
    SARShipWakeSimulator,
    BandParameters
)

np.random.seed(42)


def example_basic_simulation():
    print("=" * 60)
    print("Example 1: Basic SAR Ship Wake Simulation")
    print("=" * 60)

    config = SARConfig(
        band='X',
        polarization='VV',
        incidence_angle=30.0,
        image_size=(256, 256),
        pixel_spacing=(2.0, 2.0)
    )

    simulator = SARShipWakeSimulator(config)

    slc, amplitude = simulator.run_simulation(
        ship_speed=10.0,
        ship_length=100.0,
        ship_draft=5.0,
        wind_speed=5.0,
        wind_direction=0.0,
        add_ship_target=True,
        num_looks=1,
        snr=25.0
    )

    print("\nSLC Image Shape:", slc.shape)
    print("SLC Image dtype:", slc.dtype)
    print("Amplitude Image Shape:", amplitude.shape)

    results = simulator.get_results()
    print("\nWake Characteristics:")
    for key, value in results['wake_characteristics'].items():
        print(f"  {key}: {value:.4f}")

    features = simulator.detect_features()
    print("\nDetected Wake Features:")
    for key, value in features.items():
        print(f"  {key}: {value:.4f}")

    fig = simulator.plot_results(save_path='simulation_results.png')

    simulator.save_data('simulation_data.npz')

    plt.close(fig)
    print("\nExample 1 completed.\n")


def example_different_bands():
    print("=" * 60)
    print("Example 2: Comparison of Different Bands (X, C, L)")
    print("=" * 60)

    bands = ['X', 'C', 'L']
    polarizations = ['HH', 'VV']

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))

    for i, band in enumerate(bands):
        for j, pol in enumerate(polarizations):
            print(f"\nSimulating {band}-band, {pol} polarization...")

            config = SARConfig(
                band=band,
                polarization=pol,
                incidence_angle=35.0,
                image_size=(128, 128),
                pixel_spacing=(3.0, 3.0)
            )

            simulator = SARShipWakeSimulator(config)

            slc, amplitude = simulator.run_simulation(
                ship_speed=8.0,
                ship_length=80.0,
                ship_draft=4.0,
                wind_speed=6.0,
                add_ship_target=True,
                num_looks=2,
                snr=20.0
            )

            db_image = 20 * np.log10(amplitude + 1e-10)
            vmin = np.percentile(db_image, 5)
            vmax = np.percentile(db_image, 95)

            ax = axes[j, i]
            im = ax.imshow(db_image, cmap='jet', aspect='auto', vmin=vmin, vmax=vmax)
            ax.set_title(f'{band}-band, {pol}')
            ax.set_xlabel('Range')
            ax.set_ylabel('Azimuth')
            plt.colorbar(im, ax=ax, label='dB')

            features = simulator.detect_features()
            ax.text(0.02, 0.98,
                    f'λ={features["mean_wavelength"]:.1f}m\nθ={features["mean_angle"]:.1f}°',
                    transform=ax.transAxes, color='white',
                    verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='black', alpha=0.5))

    plt.tight_layout()
    plt.savefig('band_comparison.png', dpi=150, bbox_inches='tight')
    print("\nBand comparison plot saved to band_comparison.png")
    plt.close(fig)
    print("Example 2 completed.\n")


def example_multiple_ship_speeds():
    print("=" * 60)
    print("Example 3: Comparison of Different Ship Speeds")
    print("=" * 60)

    speeds = [5.0, 10.0, 15.0]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    theoretical_angles = []
    detected_angles = []
    theoretical_wavelengths = []
    detected_wavelengths = []

    for i, speed in enumerate(speeds):
        print(f"\nSimulating ship speed = {speed} m/s...")

        config = SARConfig(
            band='X',
            polarization='VV',
            incidence_angle=30.0,
            image_size=(128, 128),
            pixel_spacing=(3.0, 3.0)
        )

        simulator = SARShipWakeSimulator(config)

        slc, amplitude = simulator.run_simulation(
            ship_speed=speed,
            ship_length=100.0,
            ship_draft=5.0,
            wind_speed=4.0,
            add_ship_target=True,
            num_looks=1,
            snr=30.0
        )

        results = simulator.get_results()
        features = simulator.detect_features()

        wake_char = results['wake_characteristics']
        theoretical_angles.append(wake_char['kelvin_angle'])
        detected_angles.append(features['mean_angle'])
        theoretical_wavelengths.append(wake_char['transverse_wavelength'])
        detected_wavelengths.append(features['mean_wavelength'])

        db_image = 20 * np.log10(amplitude + 1e-10)
        vmin = np.percentile(db_image, 5)
        vmax = np.percentile(db_image, 95)

        ax = axes[i]
        im = ax.imshow(db_image, cmap='jet', aspect='auto', vmin=vmin, vmax=vmax)
        ax.set_title(f'Ship Speed = {speed} m/s\nFr = {wake_char["froude_number"]:.3f}')
        ax.set_xlabel('Range')
        ax.set_ylabel('Azimuth')
        plt.colorbar(im, ax=ax, label='dB')

        ax.text(0.02, 0.98,
                f'λ_t = {wake_char["transverse_wavelength"]:.1f}m\nθ_K = {wake_char["kelvin_angle"]:.1f}°',
                transform=ax.transAxes, color='white',
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='black', alpha=0.5))

    plt.tight_layout()
    plt.savefig('speed_comparison.png', dpi=150, bbox_inches='tight')

    fig2, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.plot(speeds, theoretical_angles, 'b-o', label='Theoretical (Kelvin)')
    ax1.plot(speeds, detected_angles, 'r--s', label='Detected')
    ax1.set_xlabel('Ship Speed (m/s)')
    ax1.set_ylabel('Wake Angle (degrees)')
    ax1.set_title('Wake Angle vs Ship Speed')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(speeds, theoretical_wavelengths, 'b-o', label='Theoretical')
    ax2.plot(speeds, detected_wavelengths, 'r--s', label='Detected')
    ax2.set_xlabel('Ship Speed (m/s)')
    ax2.set_ylabel('Transverse Wavelength (m)')
    ax2.set_title('Wavelength vs Ship Speed')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('wake_characteristics_plot.png', dpi=150, bbox_inches='tight')
    print("\nPlots saved to speed_comparison.png and wake_characteristics_plot.png")

    plt.close(fig)
    plt.close(fig2)
    print("Example 3 completed.\n")


def example_incidence_angle_effect():
    print("=" * 60)
    print("Example 4: Effect of Incidence Angle")
    print("=" * 60)

    angles = [20.0, 35.0, 50.0]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    backscatter_values = []

    for i, angle in enumerate(angles):
        print(f"\nSimulating incidence angle = {angle} degrees...")

        config = SARConfig(
            band='C',
            polarization='VV',
            incidence_angle=angle,
            image_size=(128, 128),
            pixel_spacing=(2.0, 2.0)
        )

        simulator = SARShipWakeSimulator(config)

        slc, amplitude = simulator.run_simulation(
            ship_speed=12.0,
            ship_length=120.0,
            ship_draft=6.0,
            wind_speed=5.0,
            add_ship_target=True,
            num_looks=1,
            snr=25.0
        )

        results = simulator.get_results()
        mean_sigma0 = np.mean(results['sea_sigma0'])
        backscatter_values.append(mean_sigma0)

        db_image = 20 * np.log10(amplitude + 1e-10)
        vmin = np.percentile(db_image, 5)
        vmax = np.percentile(db_image, 95)

        ax = axes[i]
        im = ax.imshow(db_image, cmap='jet', aspect='auto', vmin=vmin, vmax=vmax)
        ax.set_title(f'Incidence Angle = {angle}°')
        ax.set_xlabel('Range')
        ax.set_ylabel('Azimuth')
        plt.colorbar(im, ax=ax, label='dB')

        ax.text(0.02, 0.98,
                f'Mean σ₀ = {10*np.log10(mean_sigma0):.1f} dB',
                transform=ax.transAxes, color='white',
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='black', alpha=0.5))

    plt.tight_layout()
    plt.savefig('incidence_angle_comparison.png', dpi=150, bbox_inches='tight')
    print("\nPlot saved to incidence_angle_comparison.png")

    plt.close(fig)
    print("Example 4 completed.\n")


def example_slc_data_analysis():
    print("=" * 60)
    print("Example 5: SLC Data Analysis and Feature Extraction")
    print("=" * 60)

    config = SARConfig(
        band='X',
        polarization='VV',
        incidence_angle=30.0,
        image_size=(256, 256),
        pixel_spacing=(2.0, 2.0)
    )

    simulator = SARShipWakeSimulator(config)

    slc, amplitude = simulator.run_simulation(
        ship_speed=10.0,
        ship_length=100.0,
        ship_draft=5.0,
        wind_speed=5.0,
        add_ship_target=True,
        num_looks=1,
        snr=25.0
    )

    print("\nSLC Complex Data Analysis:")
    print(f"  Mean amplitude: {np.mean(np.abs(slc)):.6f}")
    print(f"  Max amplitude: {np.max(np.abs(slc)):.6f}")
    print(f"  Mean phase: {np.mean(np.angle(slc)):.4f} rad")
    print(f"  SLC real part range: [{np.min(slc.real):.4f}, {np.max(slc.real):.4f}]")
    print(f"  SLC imag part range: [{np.min(slc.imag):.4f}, {np.max(slc.imag):.4f}]")

    real_part = slc.real
    imag_part = slc.imag
    phase_image = np.angle(slc)

    fig, axes = plt.subplots(2, 2, figsize=(12, 12))

    im1 = axes[0, 0].imshow(amplitude, cmap='jet', aspect='auto')
    axes[0, 0].set_title('Amplitude (|SLC|)')
    plt.colorbar(im1, ax=axes[0, 0])

    im2 = axes[0, 1].imshow(20 * np.log10(amplitude + 1e-10), cmap='jet', aspect='auto')
    axes[0, 1].set_title('Amplitude [dB]')
    plt.colorbar(im2, ax=axes[0, 1])

    im3 = axes[1, 0].imshow(phase_image, cmap='hsv', aspect='auto', vmin=-np.pi, vmax=np.pi)
    axes[1, 0].set_title('Phase (radians)')
    plt.colorbar(im3, ax=axes[1, 0])

    correlation = np.abs(slc) ** 2
    im4 = axes[1, 1].imshow(10 * np.log10(correlation + 1e-10), cmap='jet', aspect='auto')
    axes[1, 1].set_title('Intensity (|SLC|²) [dB]')
    plt.colorbar(im4, ax=axes[1, 1])

    plt.tight_layout()
    plt.savefig('slc_analysis.png', dpi=150, bbox_inches='tight')
    print("\nSLC analysis plot saved to slc_analysis.png")

    features = simulator.detect_features()
    print("\nExtracted Wake Features:")
    print(f"  Mean Wavelength: {features['mean_wavelength']:.2f} ± {features['std_wavelength']:.2f} m")
    print(f"  Mean Angle: {features['mean_angle']:.2f} ± {features['std_angle']:.2f} degrees")
    print(f"  Number of detected peaks: {features['num_peaks']}")

    results = simulator.get_results()
    wake_char = results['wake_characteristics']
    print("\nTheoretical Wake Characteristics:")
    print(f"  Transverse Wavelength: {wake_char['transverse_wavelength']:.2f} m")
    print(f"  Divergent Wavelength: {wake_char['divergent_wavelength']:.2f} m")
    print(f"  Kelvin Angle: {wake_char['kelvin_angle']:.2f} degrees")
    print(f"  Froude Number: {wake_char['froude_number']:.4f}")

    plt.close(fig)
    print("\nExample 5 completed.\n")


def example_custom_parameters():
    print("=" * 60)
    print("Example 6: Custom Configuration - High Resolution")
    print("=" * 60)

    config = SARConfig(
        band='X',
        polarization='HH',
        incidence_angle=25.0,
        azimuth_resolution=0.5,
        range_resolution=0.5,
        image_size=(512, 512),
        pixel_spacing=(0.5, 0.5),
        platform_height=8000.0,
        platform_velocity=7500.0
    )

    simulator = SARShipWakeSimulator(config)

    print("\nSAR Configuration:")
    print(f"  Band: {config.band}")
    print(f"  Frequency: {config.frequency / 1e9:.2f} GHz")
    print(f"  Wavelength: {config.wavelength * 100:.2f} cm")
    print(f"  Polarization: {config.polarization}")
    print(f"  Incidence Angle: {np.rad2deg(config.incidence_angle):.1f}°")
    print(f"  Image Size: {config.image_size}")
    print(f"  Pixel Spacing: {config.pixel_spacing} m")

    ship_position = (256, 100)

    slc, amplitude = simulator.run_simulation(
        ship_speed=12.0,
        ship_length=150.0,
        ship_draft=8.0,
        wind_speed=7.0,
        wind_direction=45.0,
        ship_position=ship_position,
        add_ship_target=True,
        num_looks=3,
        snr=30.0
    )

    print("\nGenerating visualization...")
    fig = simulator.plot_results(save_path='high_res_simulation.png')

    features = simulator.detect_features(ship_position=ship_position)
    print("\nDetected Features:")
    for key, value in features.items():
        print(f"  {key}: {value:.4f}")

    simulator.save_data('high_res_data.npz')

    plt.close(fig)
    print("\nExample 6 completed.\n")


if __name__ == '__main__':
    import time

    start_time = time.time()

    example_basic_simulation()
    time.sleep(1)

    example_different_bands()
    time.sleep(1)

    example_multiple_ship_speeds()
    time.sleep(1)

    example_incidence_angle_effect()
    time.sleep(1)

    example_slc_data_analysis()
    time.sleep(1)

    example_custom_parameters()

    total_time = time.time() - start_time
    print("=" * 60)
    print(f"All examples completed in {total_time:.2f} seconds")
    print("=" * 60)
