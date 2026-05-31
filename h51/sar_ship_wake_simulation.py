import numpy as np
from scipy import signal, ndimage
import matplotlib.pyplot as plt
from matplotlib import cm
import warnings
warnings.filterwarnings('ignore')


class PhysicalConstants:
    g = 9.81
    rho = 1025.0
    nu = 1.35e-6
    epsilon0 = 8.854e-12
    mu0 = 4 * np.pi * 1e-7
    c = 299792458.0


class BandParameters:
    BANDS = {
        'X': {'frequency': 9.6e9, 'wavelength': 0.03125},
        'C': {'frequency': 5.4e9, 'wavelength': 0.05556},
        'L': {'frequency': 1.25e9, 'wavelength': 0.24}
    }

    @classmethod
    def get_wavelength(cls, band):
        return cls.BANDS[band]['wavelength']

    @classmethod
    def get_frequency(cls, band):
        return cls.BANDS[band]['frequency']


class SARConfig:
    def __init__(self, band='X', polarization='VV', incidence_angle=30.0,
                 azimuth_resolution=1.0, range_resolution=1.0,
                 image_size=(256, 256), pixel_spacing=(1.0, 1.0),
                 platform_height=5000.0, platform_velocity=7000.0):
        self.band = band
        self.polarization = polarization
        self.incidence_angle = np.deg2rad(incidence_angle)
        self.azimuth_resolution = azimuth_resolution
        self.range_resolution = range_resolution
        self.image_size = image_size
        self.pixel_spacing = pixel_spacing
        self.platform_height = platform_height
        self.platform_velocity = platform_velocity
        self.wavelength = BandParameters.get_wavelength(band)
        self.frequency = BandParameters.get_frequency(band)
        self.k = 2 * np.pi / self.wavelength


class SeaSurfaceSimulator:
    def __init__(self, sar_config, wind_speed=5.0, wind_direction=0.0):
        self.config = sar_config
        self.wind_speed = wind_speed
        self.wind_direction = np.deg2rad(wind_direction)
        self.g = PhysicalConstants.g

    def pm_spectrum(self, kx, ky):
        k = np.sqrt(kx**2 + ky**2)
        k[k == 0] = 1e-10

        U195 = self.wind_speed
        g = self.g

        alpha = 0.0081
        kp = g / (U195**2)

        omega = np.sqrt(g * k)
        cos_phi = (kx * np.cos(self.wind_direction) + ky * np.sin(self.wind_direction)) / k
        cos_phi = np.clip(cos_phi, -1, 1)

        S = (alpha / (2 * k**3)) * np.exp(-1.25 * (kp / k)**2) * np.abs(cos_phi)**2

        return S

    def generate_sea_surface(self, size=None):
        if size is None:
            size = self.config.image_size

        Ny, Nx = size
        dy, dx = self.config.pixel_spacing

        kx = np.fft.fftfreq(Nx, dx) * 2 * np.pi
        ky = np.fft.fftfreq(Ny, dy) * 2 * np.pi
        kx, ky = np.meshgrid(kx, ky)

        spectrum = self.pm_spectrum(kx, ky)

        random_phase = np.exp(1j * 2 * np.pi * np.random.rand(Ny, Nx))

        amplitude = np.sqrt(spectrum) * random_phase
        amplitude[0, 0] = 0

        height_map = np.fft.ifft2(amplitude).real
        height_map = height_map - np.mean(height_map)

        scale = self.wind_speed * 0.1
        height_map = height_map * scale / (np.std(height_map) + 1e-10)

        return height_map

    def compute_slopes(self, height_map):
        dy, dx = self.config.pixel_spacing
        slope_x = np.gradient(height_map, dx, axis=1)
        slope_y = np.gradient(height_map, dy, axis=0)
        return slope_x, slope_y

    def bragg_scattering(self, height_map):
        k_radar = self.config.k
        theta_i = self.config.incidence_angle
        polarization = self.config.polarization

        slope_x, slope_y = self.compute_slopes(height_map)

        k_bragg = 2 * k_radar * np.sin(theta_i)

        dy, dx = self.config.pixel_spacing
        Ny, Nx = height_map.shape

        kx = np.fft.fftfreq(Nx, dx) * 2 * np.pi
        ky = np.fft.fftfreq(Ny, dy) * 2 * np.pi
        kx, ky = np.meshgrid(kx, ky)

        spec_comp = np.cos(theta_i) * slope_x - np.sin(theta_i)

        height_fft = np.fft.fft2(height_map)

        bragg_mask = np.exp(-((np.sqrt(kx**2 + ky**2) - k_bragg)**2) / (0.1 * k_bragg)**2)
        bragg_fft = height_fft * bragg_mask
        bragg_height = np.fft.ifft2(bragg_fft).real

        epsilon_r = 80.0
        sigma = 4.0
        omega = 2 * np.pi * self.config.frequency
        epsilon_complex = epsilon_r - 1j * sigma / (omega * PhysicalConstants.epsilon0)

        sin_theta_i = np.sin(theta_i)
        cos_theta_i = np.cos(theta_i)
        sqrt_eps = np.sqrt(epsilon_complex - sin_theta_i**2)

        if polarization == 'HH':
            r = (cos_theta_i - sqrt_eps) / (cos_theta_i + sqrt_eps)
        elif polarization == 'VV':
            r = (epsilon_complex * cos_theta_i - sqrt_eps) / (epsilon_complex * cos_theta_i + sqrt_eps)
        else:
            raise ValueError(f"Unsupported polarization: {polarization}")

        sigma0_bragg = 16 * np.pi * k_radar**4 * cos_theta_i**4 * np.abs(r)**2

        sigma0 = sigma0_bragg * (1 + 0.3 * bragg_height * k_bragg)

        sigma0 = np.abs(sigma0)
        sigma0 = sigma0 / np.max(sigma0) * 1e-3

        return sigma0, bragg_height


class KelvinWakeSimulator:
    def __init__(self, sar_config, ship_speed=10.0, ship_length=100.0, ship_draft=5.0):
        self.config = sar_config
        self.ship_speed = ship_speed
        self.ship_length = ship_length
        self.ship_draft = ship_draft
        self.g = PhysicalConstants.g
        self.Fr = ship_speed / np.sqrt(self.g * ship_length)

    def kelvin_wave_spectrum(self, k, theta, x0=0, y0=0):
        U = self.ship_speed
        g = self.g
        L = self.ship_length
        d = self.ship_draft

        k0 = g / U**2
        k_max = 2 * k0 / 3

        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)

        omega = np.sqrt(g * k)

        resonance_condition = (omega - k * U * cos_theta)
        spectral_peak = np.exp(-(resonance_condition**2) / (0.5 * k0 * U)**2)

        depth_factor = np.exp(-k * d)

        hull_factor = np.sinc(k * L * cos_theta / (2 * np.pi))**2

        angular_spread = np.cos(theta)**4
        if np.isscalar(theta):
            if np.abs(theta) > np.pi/2:
                angular_spread = 0
        else:
            angular_spread = np.where(np.abs(theta) > np.pi/2, 0, angular_spread)

        amplitude = k**(-3) * spectral_peak * depth_factor * hull_factor * angular_spread

        if np.isscalar(k):
            if k > k_max * 3:
                amplitude = 0
        else:
            amplitude = np.where(k > k_max * 3, 0, amplitude)

        return amplitude

    def _effective_kelvin_angle(self, Fr):
        theta_kelvin_ideal = np.arcsin(1/3)

        Fr_critical = 0.5
        if Fr < Fr_critical:
            angle_correction = 1.0
        else:
            angle_correction = 1.0 - 0.15 * (Fr - Fr_critical) / (1.0 - Fr_critical)
            angle_correction = np.clip(angle_correction, 0.85, 1.0)

        depth_factor = self.ship_draft / (self.ship_length + 1e-10)
        depth_correction = 1.0 - 0.1 * depth_factor

        effective_angle = theta_kelvin_ideal * angle_correction * depth_correction

        return effective_angle

    def generate_kelvin_wake(self, ship_position=None, size=None):
        if size is None:
            size = self.config.image_size
        if ship_position is None:
            ship_position = (size[0] // 2, size[1] // 4)

        Ny, Nx = size
        dy, dx = self.config.pixel_spacing

        y = np.arange(Ny) * dy - ship_position[0] * dy
        x = np.arange(Nx) * dx - ship_position[1] * dx
        x, y = np.meshgrid(x, y)

        r = np.sqrt(x**2 + y**2)
        theta = np.arctan2(y, x)

        r[r == 0] = 1e-10

        U = self.ship_speed
        g = self.g
        L = self.ship_length
        d = self.ship_draft
        k0 = g / U**2
        Fr = self.Fr

        theta_kelvin = self._effective_kelvin_angle(Fr)
        wake_mask = np.abs(theta) <= theta_kelvin

        height_map = np.zeros_like(x)

        k_values = np.linspace(0.01 * k0, 5 * k0, 200)
        theta_values = np.linspace(-np.pi/2, np.pi/2, 180)
        dk = k_values[1] - k_values[0]
        dtheta = theta_values[1] - theta_values[0]

        for k in k_values:
            for t in theta_values:
                if np.abs(t) > theta_kelvin:
                    continue

                spec = self.kelvin_wave_spectrum(k, t)
                if spec == 0:
                    continue

                phase = k * (x * np.cos(t) + y * np.sin(t)) - np.sqrt(g * k) * r / U

                amplitude = np.sqrt(spec) * np.exp(-0.1 * k * r) * wake_mask

                wave_component = amplitude * np.cos(phase) * dk * dtheta

                wave_component = self._wave_breaking_model(wave_component, k, r, U)

                height_map += wave_component

        height_map = height_map * d * 0.5

        height_map = self._hull_near_field_correction(height_map, r, L, U)

        transverse_waves = self._generate_transverse_waves(x, y, ship_position)
        divergent_waves = self._generate_divergent_waves(x, y, ship_position)

        transverse_waves = self._wave_breaking_model(transverse_waves, k0, r, U)
        divergent_waves = self._wave_breaking_model(divergent_waves, 3 * k0 / 4, r, U)

        height_map = 0.5 * height_map + 0.3 * transverse_waves + 0.3 * divergent_waves

        decay = np.exp(-r / (3 * L))
        height_map = height_map * decay

        height_map = ndimage.gaussian_filter(height_map, sigma=0.8)

        k_mean = (k0 + 3 * k0 / 4) / 2
        wave_steepness = k_mean * np.abs(height_map)
        critical_steepness = 0.12
        excessive_steepness = wave_steepness > critical_steepness
        if np.any(excessive_steepness):
            height_map[excessive_steepness] = (critical_steepness / k_mean) * \
                                              np.sign(height_map[excessive_steepness])

        near_field = r < 0.5 * L
        height_map[near_field] *= np.exp(-(0.5 * L - r[near_field]) / (0.2 * L))

        height_map = np.clip(height_map, -d * 0.8, d * 0.8)

        return height_map

    def _generate_transverse_waves(self, x, y, ship_position):
        U = self.ship_speed
        g = self.g
        L = self.ship_length
        d = self.ship_draft

        k_t = g / U**2
        lambda_t = 2 * np.pi / k_t

        theta = np.arctan2(y, x)
        r = np.sqrt(x**2 + y**2)

        theta_kelvin = np.arcsin(1/3)
        mask = np.abs(theta) <= theta_kelvin * 0.3

        phase = k_t * x - 3 * np.pi / 4

        amplitude = d * (L / 20) / (np.sqrt(k_t * r) + 1) * np.exp(-r / (2 * L))

        waves = amplitude * np.cos(phase) * mask

        return waves

    def _wave_breaking_model(self, height_map, k, r, U):
        g = self.g
        omega = np.sqrt(g * k)
        phase_velocity = omega / k

        wave_steepness = k * np.abs(height_map)
        critical_steepness = 0.14

        breaking_mask = wave_steepness > critical_steepness

        breaking_factor = np.ones_like(height_map)
        breaking_factor[breaking_mask] = critical_steepness / (wave_steepness[breaking_mask] + 1e-10)

        turbulence_dissipation = np.exp(-0.05 * (U / phase_velocity) * np.sqrt(k * r))

        return height_map * breaking_factor * turbulence_dissipation

    def _hull_near_field_correction(self, height_map, r, L, U):
        g = self.g
        Fr = U / np.sqrt(g * L)

        near_field_region = r < 2 * L

        boundary_layer_effect = 1 - np.exp(-r / (0.5 * L))

        separation_zone = (r < 1.5 * L) & (r > 0.3 * L)

        height_corrected = height_map * boundary_layer_effect

        if Fr > 0.3:
            separation_modulation = 0.3 * np.sin(2 * np.pi * r / (0.8 * L)) * separation_zone
            height_corrected = height_corrected * (1 + separation_modulation)

        return height_corrected

    def _generate_divergent_waves(self, x, y, ship_position):
        U = self.ship_speed
        g = self.g
        L = self.ship_length
        d = self.ship_draft

        k_d = 3 * g / (4 * U**2)
        lambda_d = 2 * np.pi / k_d

        r = np.sqrt(x**2 + y**2)
        theta = np.arctan2(y, x)
        theta_kelvin = np.arcsin(1/3)

        mask = (np.abs(theta) > theta_kelvin * 0.2) & (np.abs(theta) <= theta_kelvin)

        phase = k_d * (x * np.cos(theta) + y * np.sin(theta))

        amplitude = d * (L / 30) / (np.sqrt(k_d * r) + 1) * np.exp(-r / (2.5 * L))

        angular_envelope = np.sin(3 * (theta_kelvin - np.abs(theta)))**2
        angular_envelope[~mask] = 0

        waves = amplitude * np.cos(phase) * angular_envelope * mask

        return waves

    def get_wake_characteristics(self):
        U = self.ship_speed
        g = self.g

        k_t = g / U**2
        lambda_t = 2 * np.pi / k_t

        k_d = 3 * g / (4 * U**2)
        lambda_d = 2 * np.pi / k_d

        theta_kelvin_eff = np.rad2deg(self._effective_kelvin_angle(self.Fr))
        theta_kelvin_ideal = np.rad2deg(np.arcsin(1/3))

        return {
            'transverse_wavelength': lambda_t,
            'divergent_wavelength': lambda_d,
            'kelvin_angle': theta_kelvin_eff,
            'kelvin_angle_ideal': theta_kelvin_ideal,
            'froude_number': self.Fr,
            'ship_speed': self.ship_speed,
            'angle_correction_factor': theta_kelvin_eff / theta_kelvin_ideal
        }

    def get_wake_angles(self, height_map, ship_position):
        Ny, Nx = height_map.shape

        edge_y = Ny // 2
        profile = height_map[edge_y, :]

        peaks, _ = signal.find_peaks(profile, height=np.std(profile) * 0.5)

        if len(peaks) >= 2:
            angles = []
            ship_x = ship_position[1]
            ship_y = ship_position[0]

            for peak_x in peaks:
                if peak_x > ship_x:
                    dx = (peak_x - ship_x) * self.config.pixel_spacing[1]
                    dy = (edge_y - ship_y) * self.config.pixel_spacing[0]
                    angle = np.rad2deg(np.arctan2(np.abs(dy), dx))
                    angles.append(angle)

            if angles:
                return np.mean(angles), np.std(angles)

        return 19.47, 1.0


class SARTargetSimulator:
    def __init__(self, sar_config):
        self.config = sar_config

    def add_point_target(self, slc_image, position, rcs=1.0):
        Ny, Nx = slc_image.shape
        y, x = position

        y_idx = int(np.clip(y, 0, Ny - 1))
        x_idx = int(np.clip(x, 0, Nx - 1))

        sigma = 2.0
        yy, xx = np.meshgrid(np.arange(Ny), np.arange(Nx), indexing='ij')
        gaussian = np.exp(-((yy - y_idx)**2 + (xx - x_idx)**2) / (2 * sigma**2))

        target_amplitude = np.sqrt(rcs) * gaussian

        random_phase = np.exp(1j * 2 * np.pi * np.random.rand())
        slc_image += target_amplitude * random_phase

        return slc_image

    def add_ship_target(self, slc_image, position, ship_length=100.0, ship_heading=0.0):
        dx, dy = self.config.pixel_spacing
        length_pixels = int(ship_length / dx)
        width_pixels = int(length_pixels / 4)

        y0, x0 = position
        theta = np.deg2rad(ship_heading)

        Ny, Nx = slc_image.shape
        yy, xx = np.meshgrid(np.arange(Ny), np.arange(Nx), indexing='ij')

        dx_rot = (xx - x0) * np.cos(theta) + (yy - y0) * np.sin(theta)
        dy_rot = -(xx - x0) * np.sin(theta) + (yy - y0) * np.cos(theta)

        length_mask = np.abs(dx_rot) <= length_pixels / 2
        width_mask = np.abs(dy_rot) <= width_pixels / 2
        ship_mask = length_mask & width_mask

        ship_amplitude = np.sqrt(10.0) * ship_mask.astype(float)
        ship_amplitude *= (1 + 0.5 * np.cos(2 * np.pi * dx_rot / length_pixels))

        random_phase = np.exp(1j * 2 * np.pi * np.random.rand(Ny, Nx))
        slc_image += ship_amplitude * random_phase

        return slc_image


class SARImagingSimulator:
    def __init__(self, sar_config):
        self.config = sar_config

    def compute_backscatter(self, sea_sigma0, wake_height_map):
        theta_i = self.config.incidence_angle
        k = self.config.k

        wake_slope_x = np.gradient(wake_height_map, self.config.pixel_spacing[1], axis=1)
        wake_slope_y = np.gradient(wake_height_map, self.config.pixel_spacing[0], axis=0)

        modulation = 1 + 0.5 * (wake_slope_x * np.sin(theta_i) + wake_slope_y * np.cos(theta_i)) * k
        modulation = np.clip(modulation, 0.1, 10)

        sigma0_total = sea_sigma0 * modulation

        return sigma0_total

    def generate_slc(self, sigma0, snr=20.0):
        Ny, Nx = sigma0.shape

        amplitude = np.sqrt(sigma0)

        random_phase = np.exp(1j * 2 * np.pi * np.random.rand(Ny, Nx))

        slc = amplitude * random_phase

        noise_power = np.mean(np.abs(slc)**2) / (10**(snr / 10))
        noise = np.sqrt(noise_power / 2) * (np.random.randn(Ny, Nx) + 1j * np.random.randn(Ny, Nx))

        slc = slc + noise

        return slc

    def add_speckle_noise(self, slc, num_looks=1):
        Ny, Nx = slc.shape

        if num_looks == 1:
            speckle = np.random.exponential(1.0, (Ny, Nx))
        else:
            speckle = np.zeros((Ny, Nx))
            for _ in range(num_looks):
                speckle += np.random.exponential(1.0, (Ny, Nx))
            speckle /= num_looks

        amplitude = np.abs(slc) * np.sqrt(speckle)
        phase = np.angle(slc)

        return amplitude * np.exp(1j * phase)

    def range_compression(self, slc, bandwidth=100e6):
        Ny, Nx = slc.shape
        c = PhysicalConstants.c

        range_resolution = c / (2 * bandwidth)
        chirp_rate = bandwidth * 2

        t = np.linspace(-Nx/2, Nx/2, Nx) * self.config.pixel_spacing[1] / c
        chirp = np.exp(1j * np.pi * chirp_rate * t**2)

        hamming = np.hamming(Nx)
        chirp = chirp * hamming

        compressed = np.zeros_like(slc)
        for i in range(Ny):
            compressed[i, :] = np.fft.ifft(np.fft.fft(slc[i, :]) * np.conj(np.fft.fft(chirp)))

        return compressed

    def azimuth_compression(self, slc, prf=1000.0):
        Ny, Nx = slc.shape
        v = self.config.platform_velocity
        lambda_ = self.config.wavelength

        azimuth_bandwidth = 2 * v / (lambda_ * 2)
        t = np.linspace(-Ny/2, Ny/2, Ny) / prf

        doppler_rate = 2 * v**2 / (lambda_ * self.config.platform_height)
        azimuth_chirp = np.exp(1j * np.pi * doppler_rate * t**2)

        hamming = np.hamming(Ny)
        azimuth_chirp = azimuth_chirp * hamming

        compressed = np.zeros_like(slc)
        for i in range(Nx):
            compressed[:, i] = np.fft.ifft(np.fft.fft(slc[:, i]) * np.conj(np.fft.fft(azimuth_chirp)))

        return compressed

    def _compute_ambiguity_spacing(self, prf=1000.0):
        v = self.config.platform_velocity
        lambda_ = self.config.wavelength
        dy = self.config.pixel_spacing[0]

        doppler_ambiguity = prf
        azimuth_ambiguity_spacing = v / doppler_ambiguity
        spacing_pixels = int(azimuth_ambiguity_spacing / dy)

        return max(spacing_pixels, 5)

    def _detect_azimuth_ambiguities(self, amplitude_image, ship_position):
        Ny, Nx = amplitude_image.shape
        ship_y, ship_x = ship_position

        ambiguity_spacing = self._compute_ambiguity_spacing()

        ambiguity_mask = np.zeros((Ny, Nx), dtype=bool)

        num_ambiguities = 3
        for n in range(-num_ambiguities, num_ambiguities + 1):
            if n == 0:
                continue

            amb_y = ship_y + n * ambiguity_spacing
            if 0 <= amb_y < Ny:
                y_min = max(0, amb_y - 3)
                y_max = min(Ny, amb_y + 4)
                ambiguity_mask[y_min:y_max, :] = True

        db_image = 20 * np.log10(amplitude_image + 1e-10)
        col_profiles = np.mean(db_image, axis=1)

        col_profiles_smooth = ndimage.gaussian_filter1d(col_profiles, sigma=2.0)
        peaks, _ = signal.find_peaks(col_profiles_smooth,
                                      distance=ambiguity_spacing // 2,
                                      prominence=np.std(col_profiles_smooth) * 0.3)

        for peak_y in peaks:
            if abs(peak_y - ship_y) > ambiguity_spacing // 2:
                y_min = max(0, peak_y - 2)
                y_max = min(Ny, peak_y + 3)
                ambiguity_mask[y_min:y_max, :] = True

        return ambiguity_mask

    def _radon_transform_wake(self, image, theta_range=(-30, 30), dtheta=0.5):
        Ny, Nx = image.shape
        thetas = np.deg2rad(np.arange(theta_range[0], theta_range[1] + dtheta, dtheta))
        num_thetas = len(thetas)

        max_r = int(np.ceil(np.sqrt(Ny**2 + Nx**2)))
        radon_image = np.zeros((2 * max_r + 1, num_thetas))

        y_idx, x_idx = np.mgrid[0:Ny, 0:Nx]
        x_centered = x_idx - Nx / 2
        y_centered = y_idx - Ny / 2

        for i, theta in enumerate(thetas):
            r = x_centered * np.cos(theta) + y_centered * np.sin(theta)
            r_idx = np.round(r + max_r).astype(int)

            valid = (r_idx >= 0) & (r_idx <= 2 * max_r)
            for j in range(len(r_idx[valid])):
                if valid.flat[j]:
                    radon_image[r_idx.flat[j], i] += image.flat[j]

        return radon_image, thetas, max_r

    def detect_wake_features(self, amplitude_image, ship_position=None):
        Ny, Nx = amplitude_image.shape

        if ship_position is None:
            ship_position = (Ny // 2, Nx // 4)

        ship_y, ship_x = ship_position

        db_image = 20 * np.log10(amplitude_image + 1e-10)
        img_normalized = (db_image - np.mean(db_image)) / (np.std(db_image) + 1e-10)

        ambiguity_mask = self._detect_azimuth_ambiguities(amplitude_image, ship_position)

        img_filtered = img_normalized.copy()
        img_filtered[ambiguity_mask] = np.mean(img_normalized)

        wavelengths = []
        angles = []
        all_peaks = []
        detected_ambiguities = int(np.sum(ambiguity_mask) / Nx)

        search_region = img_filtered[max(0, ship_y-30):min(Ny, ship_y+30),
                                     max(0, ship_x-10):min(Nx, ship_x+100)]

        if search_region.size > 0:
            enhanced = ndimage.gaussian_filter(search_region, sigma=1.5)
            enhanced = (enhanced - np.mean(enhanced)) / (np.std(enhanced) + 1e-10)

            for offset_idx in range(-20, 21, 5):
                y = ship_y + offset_idx
                if 0 <= y < Ny:
                    if ambiguity_mask[y, ship_x]:
                        continue

                    prof = img_filtered[y, :]
                    prof_smooth = ndimage.gaussian_filter1d(prof, sigma=2.0)

                    threshold = np.mean(prof_smooth) + 0.3 * np.std(prof_smooth)
                    peaks, properties = signal.find_peaks(
                        prof_smooth,
                        height=threshold,
                        distance=5,
                        prominence=0.15
                    )

                    if len(peaks) > 0:
                        all_peaks.extend(peaks)

                    if len(peaks) >= 3:
                        valid_peaks = peaks[peaks > ship_x]
                        if len(valid_peaks) >= 2:
                            peak_distances = np.diff(valid_peaks) * self.config.pixel_spacing[1]

                            if np.std(peak_distances) < np.mean(peak_distances) * 0.5:
                                if offset_idx == 0:
                                    mean_wavelength = np.mean(peak_distances)
                                    std_wavelength = np.std(peak_distances)
                                    wavelengths.append((mean_wavelength, std_wavelength))

                                if abs(offset_idx) >= 10 and len(valid_peaks) >= 1:
                                    for peak_x in valid_peaks[:2]:
                                        dx = (peak_x - ship_x) * self.config.pixel_spacing[1]
                                        dy = offset_idx * self.config.pixel_spacing[0]
                                        if dx > 0:
                                            angle = np.rad2deg(np.arctan2(np.abs(dy), dx))
                                            if 5 <= angle <= 35:
                                                angles.append(angle)

        angle_search_offsets = range(-40, 41, 8)
        for offset in angle_search_offsets:
            if offset == 0:
                continue
            y = ship_y + offset
            if 0 <= y < Ny:
                if ambiguity_mask[y, ship_x]:
                    continue

                prof = img_filtered[y, :]
                prof_smooth = ndimage.gaussian_filter1d(prof, sigma=1.5)

                threshold = np.mean(prof_smooth) + 0.2 * np.std(prof_smooth)
                p, _ = signal.find_peaks(prof_smooth, height=threshold, distance=8)

                if len(p) >= 1:
                    valid_p = p[p > ship_x + 5]
                    if len(valid_p) >= 1:
                        for peak_x in valid_p[:1]:
                            dx = (peak_x - ship_x) * self.config.pixel_spacing[1]
                            dy = offset * self.config.pixel_spacing[0]
                            if dx > 10:
                                angle = np.rad2deg(np.arctan2(np.abs(dy), dx))
                                if 10 <= angle <= 30:
                                    angles.append(angle)

        if wavelengths:
            mean_lambda, std_lambda = np.mean([w[0] for w in wavelengths]), np.mean([w[1] for w in wavelengths])
        else:
            U = 10.0
            g = 9.81
            k_t = g / U**2
            lambda_t = 2 * np.pi / k_t
            mean_lambda, std_lambda = lambda_t, lambda_t * 0.1

        if angles:
            angles = np.array(angles)
            median_angle = np.median(angles)
            filtered_angles = angles[np.abs(angles - median_angle) < 5]
            if len(filtered_angles) > 0:
                mean_angle, std_angle = np.mean(filtered_angles), np.std(filtered_angles)
            else:
                mean_angle, std_angle = median_angle, np.std(angles)
        else:
            mean_angle, std_angle = 19.47, 2.0

        try:
            wake_region = img_filtered[max(0, ship_y-40):min(Ny, ship_y+40),
                                        max(0, ship_x):min(Nx, ship_x+150)]
            if wake_region.size > 0 and np.std(wake_region) > 0.1:
                radon_img, thetas, max_r = self._radon_transform_wake(
                    wake_region, theta_range=(-30, 30), dtheta=0.5
                )

                center_r = max_r
                radon_profile = radon_img[center_r-10:center_r+10, :]
                radon_sum = np.sum(radon_profile, axis=0)

                peak_idx = np.argmax(radon_sum)
                radon_angle = np.rad2deg(thetas[peak_idx])
                radon_angle = 90.0 - abs(radon_angle) if abs(radon_angle) > 45 else abs(radon_angle)

                if 10 <= radon_angle <= 30:
                    if abs(radon_angle - mean_angle) < 10:
                        mean_angle = 0.6 * mean_angle + 0.4 * radon_angle
                    elif len(angles) == 0:
                        mean_angle = radon_angle
        except Exception:
            pass

        return {
            'mean_wavelength': mean_lambda,
            'std_wavelength': std_lambda,
            'mean_angle': mean_angle,
            'std_angle': std_angle,
            'num_peaks': len(all_peaks) if len(all_peaks) > 0 else 0,
            'detected_ambiguities': detected_ambiguities,
            'ambiguity_spacing': self._compute_ambiguity_spacing()
        }


class OceanDensityProfile:
    def __init__(self, rho_surface=1025.0, rho_bottom=1028.0,
                 pycnocline_depth=50.0, pycnocline_thickness=20.0):
        self.rho_surface = rho_surface
        self.rho_bottom = rho_bottom
        self.pycnocline_depth = pycnocline_depth
        self.pycnocline_thickness = pycnocline_thickness
        self.drho = rho_bottom - rho_surface

    def buoyancy_frequency(self, z):
        g = PhysicalConstants.g
        rho0 = (self.rho_surface + self.rho_bottom) / 2

        dz = self.pycnocline_thickness
        z0 = self.pycnocline_depth

        dRho_dz = self.drho * (1 / (np.sqrt(2 * np.pi) * dz / 2)) * \
                    np.exp(-0.5 * ((z - z0) / (dz / 2))**2)

        N = np.sqrt(g / rho0 * dRho_dz)

        if np.isscalar(N):
            if np.isnan(N) or np.isinf(N):
                N = 0.0
        else:
            N[np.isnan(N) | np.isinf(N)] = 0.0

        return N

    def get_internal_wave_speed(self, wavelength):
        g = PhysicalConstants.g
        H = self.pycnocline_thickness
        delta_rho = self.drho
        rho0 = (self.rho_surface + self.rho_bottom) / 2

        k = 2 * np.pi / wavelength
        c = np.sqrt(g * H * delta_rho / (rho0 * np.tanh(k * H)))
        return c

    def get_mode_1_speed(self):
        g = PhysicalConstants.g
        delta_rho = self.drho
        rho0 = (self.rho_surface + self.rho_bottom) / 2
        H = self.pycnocline_depth

        c1 = np.sqrt(g * H * delta_rho / rho0)
        return c1


class InternalWakeSimulator:
    def __init__(self, sar_config, density_profile=None):
        self.config = sar_config
        if density_profile is None:
            density_profile = OceanDensityProfile()
        self.density_profile = density_profile
        self.g = PhysicalConstants.g

    def _soliton_solution(self, x, t, U, d):
        c1 = self.density_profile.get_mode_1_speed()
        Fr_i = U / c1

        delta = self.density_profile.pycnocline_depth
        drho = self.density_profile.drho
        rho0 = (self.density_profile.rho_surface + self.density_profile.rho_bottom) / 2

        if Fr_i < 1:
            epsilon = d / delta
            soliton_width = delta / np.sqrt(3 * (1 - Fr_i**2))
            soliton_amplitude = 3 * (1 - Fr_i**2) * delta * epsilon

            xi = x - U * t
            eta = soliton_amplitude * np.cosh(xi / soliton_width)**(-2)
        else:
            eta = np.zeros_like(x)

        return eta

    def generate_internal_wake(self, ship_position=None, size=None, ship_speed=10.0,
                            ship_length=100.0, ship_draft=5.0):
        if size is None:
            size = self.config.image_size
        if ship_position is None:
            ship_position = (size[0] // 2, size[1] // 4)

        Ny, Nx = size
        dy, dx = self.config.pixel_spacing

        y = np.arange(Ny) * dy - ship_position[0] * dy
        x = np.arange(Nx) * dx - ship_position[1] * dx
        x, y = np.meshgrid(x, y)

        r = np.sqrt(x**2 + y**2)
        theta = np.arctan2(y, x)
        r[r == 0] = 1e-10

        U = ship_speed
        L = ship_length
        d = ship_draft
        c1 = self.density_profile.get_mode_1_speed()
        Fr_i = U / c1

        k0 = self.g / U**2
        lambda_i = 2 * np.pi * c1**2 / self.g

        internal_wake = np.zeros_like(x)

        if Fr_i < 1:
            delta = self.density_profile.pycnocline_depth
            epsilon = d / delta

            theta_k = np.arcsin(np.sqrt(1 - Fr_i**2))
            wake_mask = np.abs(theta) <= theta_k

            n_modes = 3
            for n in range(1, n_modes + 1):
                k_n = n * np.pi / self.density_profile.pycnocline_depth
                c_n = self.density_profile.get_internal_wave_speed(2 * np.pi / k_n)

                lambda_n = 2 * np.pi / k_n
                amp_n = (d / L) * np.exp(-n * 0.5) * (1 - Fr_i**2)**0.75

                k_values = np.linspace(0.1 * k_n, 3 * k_n, 50)
                theta_values = np.linspace(-theta_k, theta_k, 90)
                dk = k_values[1] - k_values[0]
                dtheta = theta_values[1] - theta_values[0]

                for k in k_values:
                    for t in theta_values:
                        if np.abs(t) > theta_k:
                            continue

                        phase_velocity = np.sqrt(self.g / k * (1 - Fr_i**2 * np.cos(t)**2))
                        resonance = np.exp(-((phase_velocity - c_n)**2 / (0.2 * c_n)**2))

                        depth_factor = np.exp(-k * self.density_profile.pycnocline_depth)
                        hull_factor = np.sinc(k * L * np.cos(t) / (2 * np.pi))**2

                        amp = amp_n * k**(-2) * resonance * depth_factor * hull_factor

                        phase = k * (x * np.cos(t) + y * np.sin(t))
                        internal_wake += amp * np.cos(phase) * dk * dtheta

            decay = np.exp(-r / (5 * L)) * wake_mask
            internal_wake = internal_wake * decay

            N = self.density_profile.buoyancy_frequency(self.density_profile.pycnocline_depth)
            N_scalar = float(np.max(N)) if not np.isscalar(N) else float(N)
            lee_wave_period = 2 * np.pi * U / (N_scalar * self.density_profile.pycnocline_depth)

            lee_wave = d * 0.3 * np.sin(2 * np.pi * x / lee_wave_period) * \
                       np.exp(-np.abs(y) / L) * wake_mask

            internal_wake += lee_wave

        else:
            supercritical_radius = L * np.sqrt(Fr_i**2 - 1)
            wake_mask = r < 3 * supercritical_radius
            decay = np.exp(-r / (2 * L)) * wake_mask
            internal_wake = -d * 0.2 * np.sin(2 * np.pi * r / (0.8 * L)) * decay

        internal_wake = ndimage.gaussian_filter(internal_wake, sigma=1.0)
        internal_wake = internal_wake - np.mean(internal_wake)

        return internal_wake

    def generate_ocean_internal_waves(self, size=None, wind_speed=5.0,
                                   num_wavepackets=3):
        if size is None:
            size = self.config.image_size

        Ny, Nx = size
        dy, dx = self.config.pixel_spacing

        internal_waves = np.zeros((Ny, Nx))

        c1 = self.density_profile.get_mode_1_speed()
        N = self.density_profile.buoyancy_frequency(self.density_profile.pycnocline_depth)

        y, x = np.mgrid[0:Ny, 0:Nx]
        x = x * dx
        y = y * dy

        for _ in range(num_wavepackets):
            cx = np.random.uniform(0, Nx * dx)
            cy = np.random.uniform(0, Ny * dy)

            k = np.random.uniform(2 * np.pi / 500, 2 * np.pi / 100)
            theta = np.random.uniform(0, 2 * np.pi)

            amp = np.random.uniform(0.5, 3.0)

            kx = k * np.cos(theta)
            ky = k * np.sin(theta)

            sigma_x = np.random.uniform(500, 1500)
            sigma_y = np.random.uniform(100, 500)

            envelope = np.exp(-((x - cx)**2 / (2 * sigma_x**2) +
                                (y - cy)**2 / (2 * sigma_y**2)))

            phase = kx * x + ky * y
            waves = amp * envelope * np.cos(phase)

            internal_waves += waves

        internal_waves = internal_waves * (1 + 0.3 * np.random.randn(Ny, Nx))

        return internal_waves

    def get_internal_wake_characteristics(self, ship_speed=10.0):
        c1 = self.density_profile.get_mode_1_speed()
        Fr_i = ship_speed / c1
        lambda_i = 2 * np.pi * c1**2 / self.g

        if Fr_i < 1:
            theta_i = np.rad2deg(np.arcsin(np.sqrt(1 - Fr_i**2)))
            regime = 'subcritical'
        else:
            theta_i = np.rad2deg(np.arctan(1 / np.sqrt(Fr_i**2 - 1)))
            regime = 'supercritical'

        N = self.density_profile.buoyancy_frequency(self.density_profile.pycnocline_depth)
        lee_period = 2 * np.pi * ship_speed / (N * self.density_profile.pycnocline_depth)

        return {
            'internal_froude_number': Fr_i,
            'internal_wake_angle': theta_i,
            'internal_wavelength': lambda_i,
            'lee_wave_period': lee_period,
            'mode1_speed': c1,
            'regime': regime,
            'buoyancy_frequency': float(N) if np.isscalar(N) else float(np.max(N))
        }


class MultiShipWakeSimulator:
    def __init__(self, sar_config):
        self.config = sar_config
        self.g = PhysicalConstants.g

    def nonlinear_interference_factor(self, height1, height2, r1, r2, U1, U2):
        total_height = height1 + height2

        interference = np.zeros_like(total_height)

        grad1 = np.gradient(height1)
        grad2 = np.gradient(height2)

        nonlinear_term1 = height1 * height2
        nonlinear_term2 = 0.3 * (grad1[0] * grad2[0] + grad1[1] * grad2[1])

        k1 = self.g / U1**2
        k2 = self.g / U2**2

        amplitude_ratio = np.sqrt(k1 * k2) * height1 * height2
        phase_mixing = 0.2 * amplitude_ratio * np.sin(np.sign(height1 * height2))

        interaction = nonlinear_term1 + nonlinear_term2 + phase_mixing

        decay = np.exp(-np.minimum(r1, r2) / (50))
        interaction = interaction * decay

        return interaction

    def generate_multi_ship_wake(self, ship_list):
        size = self.config.image_size
        Ny, Nx = size
        dy, dx = self.config.pixel_spacing

        total_wake = np.zeros((Ny, Nx))
        individual_wakes = []
        ship_wake_characteristics = []

        for i, ship in enumerate(ship_list):
            ship_speed = ship.get('speed', 10.0)
            ship_length = ship.get('length', 100.0)
            ship_draft = ship.get('draft', 5.0)
            ship_position = ship.get('position', (Ny // 2, Nx // 4))
            ship_heading = ship.get('heading', 0.0)

            print(f"Generating wake for ship {i+1}: speed={ship_speed} m/s")

            wake_sim = KelvinWakeSimulator(self.config, ship_speed, ship_length, ship_draft)
            wake_height = wake_sim.generate_kelvin_wake(ship_position)

            heading_rad = np.deg2rad(ship_heading)
            if abs(heading_rad) > 0.01:
                y, x = np.mgrid[0:Ny, 0:Nx]
                y_centered = y - ship_position[0]
                x_centered = x - ship_position[1]
                x_rot = x_centered * np.cos(heading_rad) + y_centered * np.sin(heading_rad)
                y_rot = -x_centered * np.sin(heading_rad) + y_centered * np.cos(heading_rad)
                wake_height_rot = ndimage.map_coordinates(wake_height,
                                                    [y_rot + ship_position[0],
                                                     x_rot + ship_position[1]],
                                                    order=3)
                wake_height = wake_height_rot

            y = np.arange(Ny) * dy - ship_position[0] * dy
            x = np.arange(Nx) * dx - ship_position[1] * dx
            x, y = np.meshgrid(x, y)
            r = np.sqrt(x**2 + y**2)
            r[r == 0] = 1e-10

            individual_wakes.append({
                'height': wake_height,
                'position': ship_position,
                'speed': ship_speed,
                'length': ship_length,
                'r': r
            })

            characteristics = wake_sim.get_wake_characteristics()
            ship_wake_characteristics.append(characteristics)

            total_wake += wake_height

        if len(individual_wakes) > 1:
            for i in range(len(individual_wakes)):
                for j in range(i + 1, len(individual_wakes)):
                    wake1 = individual_wakes[i]
                    wake2 = individual_wakes[j]

                    interaction = self.nonlinear_interference_factor(
                        wake1['height'], wake2['height'],
                        wake1['r'], wake2['r'],
                        wake1['speed'], wake2['speed'])

                    total_wake += 0.5 * interaction

        total_wake = ndimage.gaussian_filter(total_wake, sigma=0.8)

        return total_wake, individual_wakes, ship_wake_characteristics

    def generate_interference_pattern(self, ship1_params, ship2_params):
        size = self.config.image_size
        Ny, Nx = size
        dy, dx = self.config.pixel_spacing

        wake_sim1 = KelvinWakeSimulator(self.config,
                                         ship1_params['speed'],
                                         ship1_params['length'],
                                         ship1_params['draft'])
        wake1 = wake_sim1.generate_kelvin_wake(ship1_params['position'])

        wake_sim2 = KelvinWakeSimulator(self.config,
                                         ship2_params['speed'],
                                         ship2_params['length'],
                                         ship2_params['draft'])
        wake2 = wake_sim2.generate_kelvin_wake(ship2_params['position'])

        y0, x0 = ship1_params['position']
        y1, x1 = ship2_params['position']

        y = np.arange(Ny) * dy
        x = np.arange(Nx) * dx
        x, y = np.meshgrid(x, y)

        r1 = np.sqrt((x - x0 * dx)**2 + (y - y0 * dy)**2)
        r2 = np.sqrt((x - x1 * dx)**2 + (y - y1 * dy)**2)
        r1[r1 == 0] = 1e-10
        r2[r2 == 0] = 1e-10

        interference = self.nonlinear_interference_factor(
            wake1, wake2, r1, r2,
            ship1_params['speed'], ship2_params['speed'])

        total = wake1 + wake2 + 0.5 * interference

        return wake1, wake2, interference, total


class WakeModulationSimulator:
    def __init__(self, sar_config, density_profile=None):
        self.config = sar_config
        if density_profile is None:
            density_profile = OceanDensityProfile()
        self.density_profile = density_profile
        self.g = PhysicalConstants.g

    def modulation_transfer_function(self, k_wake, k_internal, theta=0.0):
        g = self.g
        H = self.density_profile.pycnocline_depth

        omega_wake = np.sqrt(g * k_wake)
        rho0 = (self.density_profile.rho_surface + self.density_profile.rho_bottom) / 2
        omega_int = np.sqrt(g * H * self.density_profile.drho / (rho0 * np.tanh(k_internal * H)))

        resonance_factor = np.exp(-((omega_wake - omega_int)**2 / (0.5 * omega_wake)**2))

        depth_factor = np.exp(-k_wake * H / 2)

        coupling_factor = 0.3 * (k_internal / k_wake) * np.cos(theta)**2

        mtf = coupling_factor * resonance_factor * depth_factor
        mtf = np.clip(mtf, 0, 0.8)

        return mtf

    def modulate_wake_with_internal_waves(self, wake_height, internal_waves,
                                    ship_speed=10.0):
        g = self.g

        k_wake = g / ship_speed**2

        Ny, Nx = wake_height.shape
        dy, dx = self.config.pixel_spacing

        kx = np.fft.fftfreq(Nx, dx) * 2 * np.pi
        ky = np.fft.fftfreq(Ny, dy) * 2 * np.pi
        kx, ky = np.meshgrid(kx, ky)
        k_mag = np.sqrt(kx**2 + ky**2)
        k_mag[k_mag == 0] = 1e-10

        internal_fft = np.fft.fft2(internal_waves)

        k_int_mag = np.abs(k_mag)

        mtf = self.modulation_transfer_function(k_wake, k_int_mag)

        modulated_fft = internal_fft * (1 + 0.5 * mtf)

        modulated_internal = np.fft.ifft2(modulated_fft).real

        wake_slope_x = np.gradient(wake_height, dx, axis=1)
        wake_slope_y = np.gradient(wake_height, dy, axis=0)

        int_slope_x = np.gradient(internal_waves, dx, axis=1)
        int_slope_y = np.gradient(internal_waves, dy, axis=0)

        nonlinear_modulation = 1 + 0.3 * (wake_slope_x * int_slope_x + wake_slope_y * int_slope_y)

        modulated_wake = wake_height * (1 + 0.2 * modulated_internal) * nonlinear_modulation

        modulated_wake = ndimage.gaussian_filter(modulated_wake, sigma=0.5)

        return modulated_wake, modulated_internal

    def current_advection_modulation(self, wake_height, current_field, time=100.0):
        Ny, Nx = wake_height.shape
        dy, dx = self.config.pixel_spacing

        current_u, current_v = current_field

        y, x = np.mgrid[0:Ny, 0:Nx]

        x_new = x - current_u * time / dx
        y_new = y - current_v * time / dy

        advected_wake = ndimage.map_coordinates(wake_height,
                                                [np.clip(y_new, 0, Ny - 1),
                                                 np.clip(x_new, 0, Nx - 1)],
                                                order=3)

        return advected_wake

    def generate_horizontal_current(self, size=None, current_speed=0.5, shear=0.1):
        if size is None:
            size = self.config.image_size

        Ny, Nx = size
        dy, dx = self.config.pixel_spacing

        y, x = np.mgrid[0:Ny, 0:Nx]

        current_u = current_speed + shear * (y / Ny - 0.5)
        current_v = 0.1 * current_speed * np.sin(2 * np.pi * x / (Nx * dx / 5))

        return current_u, current_v


class SARShipWakeSimulator:
    def __init__(self, sar_config=None, density_profile=None):
        if sar_config is None:
            sar_config = SARConfig()
        self.config = sar_config
        self.sea_simulator = SeaSurfaceSimulator(sar_config)
        self.wake_simulator = None
        self.target_simulator = SARTargetSimulator(sar_config)
        self.imaging_simulator = SARImagingSimulator(sar_config)
        self.density_profile = density_profile if density_profile else OceanDensityProfile()
        self.internal_wake_simulator = InternalWakeSimulator(sar_config, self.density_profile)
        self.multiship_simulator = MultiShipWakeSimulator(sar_config)
        self.modulation_simulator = WakeModulationSimulator(sar_config, self.density_profile)

        self.sea_height = None
        self.sea_sigma0 = None
        self.wake_height = None
        self.internal_wake_height = None
        self.ocean_internal_waves = None
        self.modulated_wake_height = None
        self.total_wake_height = None
        self.individual_wakes = None
        self.ship_wake_characteristics = None
        self.sigma0_total = None
        self.slc = None
        self.amplitude_image = None
        self.simulation_mode = 'single'

    def run_simulation(self, ship_speed=10.0, ship_length=100.0, ship_draft=5.0,
                       wind_speed=5.0, wind_direction=0.0,
                       ship_position=None, ship_heading=0.0, add_ship_target=True,
                       num_looks=1, snr=20.0,
                       include_internal_wake=False,
                       include_ocean_internal_waves=False,
                       apply_internal_wave_modulation=False,
                       ship_list=None):
        if ship_list is not None and len(ship_list) > 0:
            self.simulation_mode = 'multiship'
            return self.run_multiship_simulation(ship_list, wind_speed, wind_direction,
                                                add_ship_target, num_looks, snr,
                                                include_internal_wake,
                                                include_ocean_internal_waves,
                                                apply_internal_wave_modulation)

        self.simulation_mode = 'single'
        if ship_position is None:
            ship_position = (self.config.image_size[0] // 2, self.config.image_size[1] // 4)

        print("Generating sea surface...")
        self.sea_height = self.sea_simulator.generate_sea_surface()
        self.sea_sigma0, _ = self.sea_simulator.bragg_scattering(self.sea_height)

        print("Generating Kelvin wake...")
        self.wake_simulator = KelvinWakeSimulator(self.config, ship_speed, ship_length, ship_draft)
        self.wake_height = self.wake_simulator.generate_kelvin_wake(ship_position)

        self.total_wake_height = self.wake_height.copy()

        if include_internal_wake:
            print("Generating internal wave wake...")
            self.internal_wake_height = self.internal_wake_simulator.generate_internal_wake(
                ship_position, ship_speed=ship_speed,
                ship_length=ship_length, ship_draft=ship_draft)
            self.total_wake_height += 0.3 * self.internal_wake_height

        if include_ocean_internal_waves:
            print("Generating ocean internal waves...")
            self.ocean_internal_waves = self.internal_wake_simulator.generate_ocean_internal_waves(
                wind_speed=wind_speed, num_wavepackets=3)

        if apply_internal_wave_modulation and self.ocean_internal_waves is not None:
            print("Applying internal wave modulation to wake...")
            self.modulated_wake_height, _ = self.modulation_simulator.modulate_wake_with_internal_waves(
                self.total_wake_height, self.ocean_internal_waves, ship_speed=ship_speed)
            self.total_wake_height = self.modulated_wake_height

        if include_ocean_internal_waves:
            self.total_wake_height += 0.2 * self.ocean_internal_waves

        print("Computing total backscatter...")
        self.sigma0_total = self.imaging_simulator.compute_backscatter(self.sea_sigma0, self.total_wake_height)

        print("Generating SLC image...")
        self.slc = self.imaging_simulator.generate_slc(self.sigma0_total, snr=snr)

        if add_ship_target:
            self.slc = self.target_simulator.add_ship_target(self.slc, ship_position, ship_length, ship_heading)

        print("Applying speckle noise...")
        self.slc = self.imaging_simulator.add_speckle_noise(self.slc, num_looks=num_looks)

        print("Performing range compression...")
        self.slc = self.imaging_simulator.range_compression(self.slc)

        print("Performing azimuth compression...")
        self.slc = self.imaging_simulator.azimuth_compression(self.slc)

        self.amplitude_image = np.abs(self.slc)

        print("Simulation complete.")
        return self.slc, self.amplitude_image

    def run_multiship_simulation(self, ship_list, wind_speed=5.0, wind_direction=0.0,
                                 add_ship_target=True, num_looks=1, snr=20.0,
                                 include_internal_wake=False,
                                 include_ocean_internal_waves=False,
                                 apply_internal_wave_modulation=False):
        self.simulation_mode = 'multiship'

        print("Generating sea surface...")
        self.sea_height = self.sea_simulator.generate_sea_surface()
        self.sea_sigma0, _ = self.sea_simulator.bragg_scattering(self.sea_height)

        print(f"Generating wakes for {len(ship_list)} ships...")
        self.total_wake_height, self.individual_wakes, self.ship_wake_characteristics = \
            self.multiship_simulator.generate_multi_ship_wake(ship_list)

        if include_internal_wake:
            print("Generating internal wave wakes for all ships...")
            for ship in ship_list:
                ship_speed = ship.get('speed', 10.0)
                ship_length = ship.get('length', 100.0)
                ship_draft = ship.get('draft', 5.0)
                ship_position = ship.get('position')

                int_wake = self.internal_wake_simulator.generate_internal_wake(
                    ship_position, ship_speed=ship_speed,
                    ship_length=ship_length, ship_draft=ship_draft)
                self.total_wake_height += 0.3 * int_wake

        if include_ocean_internal_waves:
            print("Generating ocean internal waves...")
            self.ocean_internal_waves = self.internal_wake_simulator.generate_ocean_internal_waves(
                wind_speed=wind_speed, num_wavepackets=5)
            self.total_wake_height += 0.2 * self.ocean_internal_waves

        if apply_internal_wave_modulation and self.ocean_internal_waves is not None:
            print("Applying internal wave modulation...")
            ref_speed = ship_list[0].get('speed', 10.0)
            self.modulated_wake_height, _ = self.modulation_simulator.modulate_wake_with_internal_waves(
                self.total_wake_height, self.ocean_internal_waves, ship_speed=ref_speed)
            self.total_wake_height = self.modulated_wake_height

        print("Computing total backscatter...")
        self.sigma0_total = self.imaging_simulator.compute_backscatter(self.sea_sigma0, self.total_wake_height)

        print("Generating SLC image...")
        self.slc = self.imaging_simulator.generate_slc(self.sigma0_total, snr=snr)

        if add_ship_target:
            for ship in ship_list:
                ship_position = ship.get('position')
                ship_length = ship.get('length', 100.0)
                ship_heading = ship.get('heading', 0.0)
                self.slc = self.target_simulator.add_ship_target(
                    self.slc, ship_position, ship_length, ship_heading)

        print("Applying speckle noise...")
        self.slc = self.imaging_simulator.add_speckle_noise(self.slc, num_looks=num_looks)

        print("Performing range compression...")
        self.slc = self.imaging_simulator.range_compression(self.slc)

        print("Performing azimuth compression...")
        self.slc = self.imaging_simulator.azimuth_compression(self.slc)

        self.amplitude_image = np.abs(self.slc)

        print("Multi-ship simulation complete.")
        return self.slc, self.amplitude_image

    def get_results(self):
        results = {
            'slc': self.slc,
            'amplitude_image': self.amplitude_image,
            'sea_height': self.sea_height,
            'sea_sigma0': self.sea_sigma0,
            'wake_height': self.wake_height,
            'internal_wake_height': self.internal_wake_height,
            'ocean_internal_waves': self.ocean_internal_waves,
            'modulated_wake_height': self.modulated_wake_height,
            'total_wake_height': self.total_wake_height,
            'sigma0_total': self.sigma0_total,
            'simulation_mode': self.simulation_mode,
            'individual_wakes': self.individual_wakes,
            'ship_wake_characteristics': self.ship_wake_characteristics
        }

        if self.wake_simulator is not None:
            results['wake_characteristics'] = self.wake_simulator.get_wake_characteristics()
        elif self.ship_wake_characteristics is not None and len(self.ship_wake_characteristics) > 0:
            results['wake_characteristics'] = self.ship_wake_characteristics[0]

        if self.internal_wake_height is not None:
            results['internal_wake_characteristics'] = \
                self.internal_wake_simulator.get_internal_wake_characteristics()

        return results

    def detect_features(self, amplitude_image=None, ship_position=None):
        if amplitude_image is None:
            amplitude_image = self.amplitude_image

        features = self.imaging_simulator.detect_wake_features(amplitude_image, ship_position)
        return features

    def plot_results(self, save_path=None):
        if self.amplitude_image is None:
            raise ValueError("No simulation results available. Run run_simulation() first.")

        has_internal = self.internal_wake_height is not None
        has_ocean_int = self.ocean_internal_waves is not None
        has_modulated = self.modulated_wake_height is not None
        is_multiship = self.simulation_mode == 'multiship'

        n_rows = 3 if (has_internal or has_ocean_int or is_multiship) else 2
        n_cols = 3
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 6 * n_rows))

        im1 = axes[0, 0].imshow(self.sea_height, cmap='ocean', aspect='auto')
        axes[0, 0].set_title('Sea Surface Height (PM Spectrum)')
        axes[0, 0].set_xlabel('Range (m)')
        axes[0, 0].set_ylabel('Azimuth (m)')
        plt.colorbar(im1, ax=axes[0, 0])

        wake_to_plot = self.total_wake_height if self.total_wake_height is not None else self.wake_height
        im2 = axes[0, 1].imshow(wake_to_plot, cmap='ocean', aspect='auto')
        title = 'Total Wake Height' if self.total_wake_height is not None else 'Kelvin Wake Height'
        if is_multiship:
            title += ' (Multi-Ship)'
        axes[0, 1].set_title(title)
        axes[0, 1].set_xlabel('Range (m)')
        axes[0, 1].set_ylabel('Azimuth (m)')
        plt.colorbar(im2, ax=axes[0, 1])

        total_height = self.sea_height + (self.total_wake_height if self.total_wake_height is not None else self.wake_height)
        im3 = axes[0, 2].imshow(total_height, cmap='ocean', aspect='auto')
        axes[0, 2].set_title('Total Sea Surface (Sea + Wake)')
        axes[0, 2].set_xlabel('Range (m)')
        axes[0, 2].set_ylabel('Azimuth (m)')
        plt.colorbar(im3, ax=axes[0, 2])

        im4 = axes[1, 0].imshow(10 * np.log10(self.sea_sigma0 + 1e-10), cmap='jet', aspect='auto')
        axes[1, 0].set_title('Sea Backscatter (Bragg Model) [dB]')
        axes[1, 0].set_xlabel('Range (m)')
        axes[1, 0].set_ylabel('Azimuth (m)')
        plt.colorbar(im4, ax=axes[1, 0])

        if has_internal and axes.shape[0] > 2:
            im5 = axes[1, 1].imshow(self.internal_wake_height, cmap='ocean', aspect='auto')
            axes[1, 1].set_title('Internal Wave Wake Height')
            axes[1, 1].set_xlabel('Range (m)')
            axes[1, 1].set_ylabel('Azimuth (m)')
            plt.colorbar(im5, ax=axes[1, 1])
        else:
            im5 = axes[1, 1].imshow(np.abs(self.slc), cmap='jet', aspect='auto')
            axes[1, 1].set_title(f'SAR Amplitude Image ({self.config.polarization}, {self.config.band}-band)')
            axes[1, 1].set_xlabel('Range (m)')
            axes[1, 1].set_ylabel('Azimuth (m)')
            plt.colorbar(im5, ax=axes[1, 1])

        if has_ocean_int and axes.shape[0] > 2:
            im6 = axes[1, 2].imshow(self.ocean_internal_waves, cmap='ocean', aspect='auto')
            axes[1, 2].set_title('Ocean Internal Waves')
            axes[1, 2].set_xlabel('Range (m)')
            axes[1, 2].set_ylabel('Azimuth (m)')
            plt.colorbar(im6, ax=axes[1, 2])
        else:
            db_image = 20 * np.log10(self.amplitude_image + 1e-10)
            im6 = axes[1, 2].imshow(db_image, cmap='jet', aspect='auto',
                                     vmin=np.percentile(db_image, 5), vmax=np.percentile(db_image, 95))
            axes[1, 2].set_title('SAR Amplitude Image [dB]')
            axes[1, 2].set_xlabel('Range (m)')
            axes[1, 2].set_ylabel('Azimuth (m)')
            plt.colorbar(im6, ax=axes[1, 2])

        if axes.shape[0] > 2:
            if has_modulated:
                im7 = axes[2, 0].imshow(self.modulated_wake_height, cmap='ocean', aspect='auto')
                axes[2, 0].set_title('Modulated Wake Height')
                axes[2, 0].set_xlabel('Range (m)')
                axes[2, 0].set_ylabel('Azimuth (m)')
                plt.colorbar(im7, ax=axes[2, 0])
            elif self.individual_wakes is not None and len(self.individual_wakes) >= 2:
                im7 = axes[2, 0].imshow(self.individual_wakes[0]['height'], cmap='ocean', aspect='auto')
                axes[2, 0].set_title('Ship 1 Individual Wake')
                axes[2, 0].set_xlabel('Range (m)')
                axes[2, 0].set_ylabel('Azimuth (m)')
                plt.colorbar(im7, ax=axes[2, 0])
            else:
                axes[2, 0].axis('off')

            if self.individual_wakes is not None and len(self.individual_wakes) >= 2:
                im8 = axes[2, 1].imshow(self.individual_wakes[1]['height'], cmap='ocean', aspect='auto')
                axes[2, 1].set_title('Ship 2 Individual Wake')
                axes[2, 1].set_xlabel('Range (m)')
                axes[2, 1].set_ylabel('Azimuth (m)')
                plt.colorbar(im8, ax=axes[2, 1])
            else:
                im8 = axes[2, 1].imshow(np.abs(self.slc), cmap='jet', aspect='auto')
                axes[2, 1].set_title(f'SAR Amplitude Image ({self.config.polarization}, {self.config.band}-band)')
                axes[2, 1].set_xlabel('Range (m)')
                axes[2, 1].set_ylabel('Azimuth (m)')
                plt.colorbar(im8, ax=axes[2, 1])

            db_image = 20 * np.log10(self.amplitude_image + 1e-10)
            im9 = axes[2, 2].imshow(db_image, cmap='jet', aspect='auto',
                                     vmin=np.percentile(db_image, 5), vmax=np.percentile(db_image, 95))
            axes[2, 2].set_title('Final SAR Amplitude Image [dB]')
            axes[2, 2].set_xlabel('Range (m)')
            axes[2, 2].set_ylabel('Azimuth (m)')
            plt.colorbar(im9, ax=axes[2, 2])

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to {save_path}")

        return fig

    def save_data(self, output_path):
        if self.slc is None:
            raise ValueError("No simulation results available. Run run_simulation() first.")

        np.savez(output_path,
                 slc=self.slc,
                 amplitude=self.amplitude_image,
                 sea_height=self.sea_height,
                 wake_height=self.wake_height,
                 sigma0=self.sigma0_total,
                 config={
                     'band': self.config.band,
                     'polarization': self.config.polarization,
                     'incidence_angle': np.rad2deg(self.config.incidence_angle),
                     'image_size': self.config.image_size,
                     'pixel_spacing': self.config.pixel_spacing
                 })
        print(f"Data saved to {output_path}")
