import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
import logging
from scipy import interpolate, optimize

logger = logging.getLogger(__name__)


@dataclass
class TSInversionParams:
    """Parameters for T-S profile joint inversion."""
    surface_temperature: float = 25.0
    surface_salinity: float = 35.0
    bottom_temperature: float = 5.0
    bottom_salinity: float = 34.5
    thermocline_depth: float = 50.0
    thermocline_strength: float = 0.15
    num_depth_levels: int = 50
    max_depth: float = 200.0
    density_ratio: float = 0.003
    gravity: float = 9.81
    use_climatology: bool = True
    region: str = 'sargasso_sea'
    assimilation_weight: float = 0.3
    smooth_profile: bool = True
    smooth_sigma: float = 2.0


@dataclass
class TSProfile:
    """Temperature-Salinity profile data."""
    depth: np.ndarray
    temperature: np.ndarray
    salinity: np.ndarray
    density: np.ndarray
    buoyancy_frequency: np.ndarray
    potential_density: Optional[np.ndarray] = None
    sound_speed: Optional[np.ndarray] = None
    quality_flag: np.ndarray = field(default_factory=lambda: np.ones(0, dtype=bool))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_value_at_depth(self, depth: float, var: str = 'temperature') -> float:
        """Get profile value at a specific depth."""
        if var not in ['temperature', 'salinity', 'density', 'buoyancy_frequency',
                       'potential_density', 'sound_speed']:
            raise ValueError(f"Unknown variable: {var}")

        data = getattr(self, var)
        if data is None:
            return 0.0
        if depth <= self.depth[0]:
            return float(data[0])
        if depth >= self.depth[-1]:
            return float(data[-1])

        f = interpolate.interp1d(self.depth, data, kind='linear')
        return float(f(depth))

    def get_layer_average(self, z_top: float, z_bottom: float,
                           var: str = 'temperature') -> float:
        """Get layer-averaged value."""
        if var not in ['temperature', 'salinity', 'density', 'buoyancy_frequency',
                       'potential_density', 'sound_speed']:
            raise ValueError(f"Unknown variable: {var}")

        data = getattr(self, var)
        if data is None:
            return 0.0

        mask = (self.depth >= z_top) & (self.depth <= z_bottom)
        if not np.any(mask):
            return self.get_value_at_depth((z_top + z_bottom) / 2, var)

        return float(np.mean(data[mask]))


@dataclass
class TSInversionResult:
    """Result of T-S joint inversion."""
    background_profile: Optional[TSProfile] = None
    wave_induced_profile: Optional[TSProfile] = None
    mixed_layer_depth: float = 0.0
    pycnocline_depth: float = 0.0
    stratification_strength: float = 0.0
    inversion_uncertainty: float = 0.0
    observations: List[Dict[str, Any]] = field(default_factory=list)
    energy_conversion_rate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ThermoclineModel:
    """
    Analytical thermocline models for different ocean regions.

    Implements commonly used thermocline parameterizations:
    - Exponential model (Munk profile)
    - Hyperbolic tangent model
    - Piecewise linear model
    """

    def __init__(self, params: TSInversionParams):
        self.params = params

    def munk_profile(self, depth: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Munk ideal thermocline profile.

        T(z) = T_s - ΔT * (1 - exp(-z/z_0))
        S(z) = S_s - ΔS * (1 - exp(-z/z_0))

        Args:
            depth: Depth array

        Returns:
            Tuple of (temperature, salinity) profiles
        """
        p = self.params
        z0 = p.thermocline_depth / 2.0

        T = p.surface_temperature - (p.surface_temperature - p.bottom_temperature) * \
            (1 - np.exp(-depth / max(z0, 1.0)))

        S = p.surface_salinity - (p.surface_salinity - p.bottom_salinity) * \
            (1 - np.exp(-depth / max(z0, 1.0)))

        return T, S

    def tanh_profile(self, depth: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Hyperbolic tangent thermocline profile.

        T(z) = (T_s + T_b)/2 - (T_s - T_b)/2 * tanh((z - z_0)/d)

        Args:
            depth: Depth array

        Returns:
            Tuple of (temperature, salinity) profiles
        """
        p = self.params
        z0 = p.thermocline_depth
        d = p.thermocline_depth * p.thermocline_strength

        T = (p.surface_temperature + p.bottom_temperature) / 2 - \
            (p.surface_temperature - p.bottom_temperature) / 2 * \
            np.tanh((depth - z0) / max(d, 0.1))

        S = (p.surface_salinity + p.bottom_salinity) / 2 - \
            (p.surface_salinity - p.bottom_salinity) / 2 * \
            np.tanh((depth - z0) / max(d, 0.1))

        return T, S

    def piecewise_linear(self, depth: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Piecewise linear thermocline profile.

        Args:
            depth: Depth array

        Returns:
            Tuple of (temperature, salinity) profiles
        """
        p = self.params
        T = np.zeros_like(depth)
        S = np.zeros_like(depth)

        z_ml = p.thermocline_depth * 0.3
        z_bottom = p.max_depth

        for i, z in enumerate(depth):
            if z <= z_ml:
                T[i] = p.surface_temperature
                S[i] = p.surface_salinity
            elif z <= p.thermocline_depth:
                frac = (z - z_ml) / (p.thermocline_depth - z_ml)
                T[i] = p.surface_temperature - frac * (p.surface_temperature - 10.0)
                S[i] = p.surface_salinity - frac * (p.surface_salinity - 34.7)
            else:
                frac = min(1.0, (z - p.thermocline_depth) / (z_bottom - p.thermocline_depth))
                T[i] = 10.0 - frac * (10.0 - p.bottom_temperature)
                S[i] = 34.7 - frac * (34.7 - p.bottom_salinity)

        return T, S


class DensityModel:
    """
    Ocean density model based on UNESCO/TEOS-10 simplified equation of state.

    Implements:
    - Linear equation of state (for small perturbations)
    - Nonlinear equation of state (full TEOS-10 approximation)
    """

    @staticmethod
    def density_linear(T: np.ndarray, S: np.ndarray,
                        depth: np.ndarray, ref_T: float = 20.0) -> np.ndarray:
        """
        Linear equation of state.

        ρ = ρ0 [1 - α(T - T0) + β(S - S0)]

        Args:
            T: Temperature (°C)
            S: Salinity (PSU)
            depth: Depth (m)
            ref_T: Reference temperature

        Returns:
            Density (kg/m³)
        """
        rho0 = 1027.0
        alpha = 2.5e-4
        beta = 7.6e-4
        S0 = 35.0

        return rho0 * (1 - alpha * (T - ref_T) + beta * (S - S0))

    @staticmethod
    def density_nonlinear(T: np.ndarray, S: np.ndarray,
                           depth: np.ndarray) -> np.ndarray:
        """
        Simplified nonlinear equation of state.

        Based on the UNESCO polynomial approximation.

        Args:
            T: Temperature (°C)
            S: Salinity (PSU)
            depth: Depth (m)

        Returns:
            Density (kg/m³)
        """
        P = depth * 0.1

        rho_w = 999.842594 + 6.793952e-2 * T - 9.095290e-3 * T**2 + \
                1.001685e-4 * T**3 - 1.120083e-6 * T**4 + 6.536332e-9 * T**5

        A = 8.24493e-1 - 4.0899e-3 * T + 7.6438e-5 * T**2 - \
            8.2467e-7 * T**3 + 5.3875e-9 * T**4

        B = -5.72466e-3 + 1.0227e-4 * T - 1.6546e-6 * T**2

        C = 4.8314e-4

        K0 = 19652.21 + 148.4206 * T - 2.327105 * T**2 + 1.360477e-2 * T**3 - \
             5.155288e-5 * T**4

        K = K0 + 3.239908 * P + 1.43713e-3 * P**2 + 1.16092e-4 * P**3

        rho_0 = rho_w + A * S + B * S**1.5 + C * S**2

        rho = rho_0 / (1 - P / np.maximum(K, 1e-6))

        return rho

    @staticmethod
    def buoyancy_frequency(depth: np.ndarray, density: np.ndarray,
                            rho0: float = 1027.0, g: float = 9.81) -> np.ndarray:
        """
        Compute buoyancy frequency (Brunt-Väisälä frequency).

        N² = -(g/ρ0) dρ/dz

        Args:
            depth: Depth array
            density: Density array
            rho0: Reference density
            g: Gravitational acceleration

        Returns:
            Buoyancy frequency (rad/s)
        """
        if len(density) < 2:
            return np.zeros_like(depth)

        dRho_dz = np.gradient(density, depth)
        N2 = (g / rho0) * dRho_dz

        N2 = np.maximum(N2, 0)

        return np.sqrt(N2)

    @staticmethod
    def sound_speed(T: np.ndarray, S: np.ndarray, depth: np.ndarray) -> np.ndarray:
        """
        Compute sound speed in seawater (Chen-Millero formula).

        Args:
            T: Temperature (°C)
            S: Salinity (PSU)
            depth: Depth (m)

        Returns:
            Sound speed (m/s)
        """
        P = depth * 0.1

        C00 = 1402.388 + 5.03711 * T - 5.80852e-2 * T**2 + 3.3420e-4 * T**3 - \
              1.47800e-6 * T**4 + 3.1464e-9 * T**5

        C0 = C00 + S * (1.389 - 1.262e-2 * T + 7.82e-5 * T**2 - 7.69e-7 * T**3 + \
                        1.58e-8 * T**4) + S**1.5 * (9.4742e-5 - 1.2580e-5 * T + \
                        6.492e-8 * T**2)

        C = C0 + P * (1.6072e-1 + 1.0227e-3 * T - 3.4061e-5 * T**2 + 1.0319e-7 * T**3 + \
            1.727e-3 * S - 7.936e-5 * T * S) + \
            P**2 * (7.3522e-4 - 1.8058e-5 * T + 3.6841e-7 * T**2 + 1.3097e-6 * S)

        return C


class TSInverter:
    """
    Joint Temperature-Salinity profile inversion from SAR imagery.

    This module inverts vertical T-S profiles by combining:
    1. Internal wave parameters (amplitude, phase speed, wavelength)
    2. Reduced gravity and buoyancy frequency constraints
    3. Climatological T-S relationship
    4. Optional in-situ observation assimilation

    The inversion solves for the T-S profile that best satisfies:
    - Internal wave KdV/eKdV dynamics
    - Ocean equation of state
    - Regional climatological constraints
    """

    def __init__(self, params: Optional[TSInversionParams] = None):
        self.params = params or TSInversionParams()
        self.thermocline_model = ThermoclineModel(self.params)
        self.density_model = DensityModel()

    def invert(self, wave_amplitudes: List[float],
               wave_wavelengths: List[float],
               phase_speeds: List[float],
               g_prime: float,
               observations: Optional[List[Dict[str, Any]]] = None,
               ) -> TSInversionResult:
        """
        Perform joint T-S profile inversion.

        Args:
            wave_amplitudes: List of detected wave amplitudes (m)
            wave_wavelengths: List of wave wavelengths (m)
            phase_speeds: List of wave phase speeds (m/s)
            g_prime: Reduced gravity (m/s²)
            observations: Optional list of in-situ observations
                         Each observation: {'depth': z, 'temperature': T,
                                           'salinity': S, 'uncertainty': σ}

        Returns:
            TSInversionResult containing background and wave-induced profiles
        """
        logger.info("Starting T-S profile joint inversion...")

        result = TSInversionResult()
        if observations:
            result.observations = observations

        depth = np.linspace(0, self.params.max_depth, self.params.num_depth_levels)

        logger.info("  Estimating background stratification...")
        T, S = self._estimate_background_profile(depth, g_prime, phase_speeds)

        if observations and self.params.assimilation_weight > 0:
            logger.info(f"  Assimilating {len(observations)} observations...")
            T, S = self._assimilate_observations(depth, T, S, observations)

        if self.params.smooth_profile:
            from scipy import ndimage
            T = ndimage.gaussian_filter1d(T, sigma=self.params.smooth_sigma)
            S = ndimage.gaussian_filter1d(S, sigma=self.params.smooth_sigma)

        rho = self.density_model.density_nonlinear(T, S, depth)
        N = self.density_model.buoyancy_frequency(depth, rho)
        c = self.density_model.sound_speed(T, S, depth)

        h1 = self.params.thermocline_depth
        ml_density = np.mean(rho[depth <= h1 * 0.3])
        pyc_density = np.mean(rho[(depth >= h1 * 0.5) & (depth <= h1 * 1.5)])
        stratification = (pyc_density - ml_density) / max(h1, 1.0)

        result.background_profile = TSProfile(
            depth=depth,
            temperature=T,
            salinity=S,
            density=rho,
            buoyancy_frequency=N,
            sound_speed=c,
            quality_flag=np.ones_like(depth, dtype=bool),
            metadata={
                'model_type': self.params.region,
                'thermocline_model': 'tanh',
                'assimilated_obs': len(observations) if observations else 0
            }
        )

        logger.info("  Computing wave-induced profile perturbations...")
        result.wave_induced_profile = self._compute_wave_induced_profile(
            result.background_profile, wave_amplitudes, wave_wavelengths, phase_speeds
        )

        result.mixed_layer_depth = self._estimate_mixed_layer_depth(depth, rho, T)
        result.pycnocline_depth = self.params.thermocline_depth
        result.stratification_strength = stratification
        result.inversion_uncertainty = self._estimate_uncertainty(T, S, observations)
        result.energy_conversion_rate = self._estimate_energy_conversion_rate(N, wave_amplitudes)

        logger.info(f"Inversion complete: MLD={result.mixed_layer_depth:.1f}m, "
                   f"N_max={np.max(N):.4f} rad/s")

        return result

    def _estimate_background_profile(self, depth: np.ndarray, g_prime: float,
                                       phase_speeds: List[float]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Estimate background T-S profile constrained by wave dynamics.

        Uses the fact that g' = g*(ρ2-ρ1)/ρ2 and c = sqrt(g'*h1*h2/(h1+h2))
        to constrain the density jump across the pycnocline.
        """
        p = self.params
        rho0 = 1027.0

        if len(phase_speeds) > 0:
            c_mean = np.mean(phase_speeds)
            h1 = p.thermocline_depth
            h2 = p.max_depth - h1

            g_prime_est = c_mean**2 * (h1 + h2) / max(h1 * h2, 1.0)

            if g_prime <= 0:
                g_prime = g_prime_est

            g_prime = 0.7 * g_prime + 0.3 * g_prime_est

        delta_rho = g_prime * rho0 / max(p.gravity, 1e-6)

        T_tanh, S_tanh = self.thermocline_model.tanh_profile(depth)
        T_munk, S_munk = self.thermocline_model.munk_profile(depth)

        rho_tanh = self.density_model.density_linear(T_tanh, S_tanh, depth)
        rho_munk = self.density_model.density_linear(T_munk, S_munk, depth)

        ml_depth = p.thermocline_depth * 0.3
        ml_mask = depth <= ml_depth
        pyc_mask = (depth > ml_depth) & (depth <= p.thermocline_depth * 1.5)

        rho_ml_target = rho0
        rho_pyc_target = rho0 + delta_rho

        w_tanh = 0.5
        T = w_tanh * T_tanh + (1 - w_tanh) * T_munk
        S = w_tanh * S_tanh + (1 - w_tanh) * S_munk

        T[ml_mask] = T[ml_mask] * (rho_ml_target / rho0)
        S[ml_mask] = S[ml_mask] * (1 + (rho_ml_target - rho0) / (50 * rho0))

        rho_current = self.density_model.density_linear(T, S, depth)
        scale_factor = (rho0 + delta_rho) / max(np.mean(rho_current[pyc_mask]), rho0)
        scale_factor = np.clip(scale_factor, 0.99, 1.02)

        T = T / np.sqrt(scale_factor)
        S = S * (1 + (scale_factor - 1) * 0.3)

        return T, S

    def _assimilate_observations(self, depth: np.ndarray, T: np.ndarray, S: np.ndarray,
                                  observations: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Assimilate in-situ observations using optimal interpolation.

        Simple OI scheme:
            T_analysis = T_background + W (T_obs - T_background)
        where W is a Gaussian-weighted interpolation matrix.
        """
        w = self.params.assimilation_weight

        T_new = T.copy()
        S_new = S.copy()

        for obs in observations:
            z_obs = obs.get('depth', 0)
            T_obs = obs.get('temperature')
            S_obs = obs.get('salinity')
            sigma = obs.get('uncertainty', 1.0)

            dz = np.abs(depth - z_obs)
            L = 50.0
            weights = w * np.exp(-dz**2 / (2 * L**2)) / max(sigma, 0.1)
            weights = weights / max(1.0, np.max(weights))

            if T_obs is not None:
                f = interpolate.interp1d(depth, T, kind='linear', fill_value='extrapolate')
                T_bg_at_obs = float(f(z_obs))
                T_new = T_new + weights * (T_obs - T_bg_at_obs)

            if S_obs is not None:
                f = interpolate.interp1d(depth, S, kind='linear', fill_value='extrapolate')
                S_bg_at_obs = float(f(z_obs))
                S_new = S_new + weights * (S_obs - S_bg_at_obs)

        return T_new, S_new

    def _compute_wave_induced_profile(self, background: TSProfile,
                                       wave_amplitudes: List[float],
                                       wave_wavelengths: List[float],
                                       phase_speeds: List[float]) -> TSProfile:
        """
        Compute wave-induced perturbations to the T-S profile.

        For linear internal waves:
            η(z, t) = A * Φ(z) * sin(kx - ωt)
        where Φ(z) is the vertical mode structure.

        The induced temperature/salinity perturbations are:
            T' = -η dT/dz
            S' = -η dS/dz
        """
        depth = background.depth
        T = background.temperature
        S = background.salinity
        N = background.buoyancy_frequency

        if len(wave_amplitudes) == 0:
            amp = 5.0
            k = 2 * np.pi / 50.0
        else:
            amp = np.mean(wave_amplitudes)
            k = 2 * np.pi / np.mean(wave_wavelengths)

        dT_dz = np.gradient(T, depth)
        dS_dz = np.gradient(S, depth)

        N_max = np.max(N)
        z_peak = depth[np.argmax(N)]

        mode_shape = np.cos(np.pi * depth / max(2 * z_peak, 1.0))
        mode_shape = mode_shape / max(1e-6, np.max(np.abs(mode_shape)))

        eta = amp * mode_shape

        T_pert = -eta * dT_dz
        S_pert = -eta * dS_dz

        T_wave = T + T_pert
        S_wave = S + S_pert

        rho_wave = self.density_model.density_nonlinear(T_wave, S_wave, depth)
        N_wave = self.density_model.buoyancy_frequency(depth, rho_wave)
        c_wave = self.density_model.sound_speed(T_wave, S_wave, depth)

        return TSProfile(
            depth=depth,
            temperature=T_wave,
            salinity=S_wave,
            density=rho_wave,
            buoyancy_frequency=N_wave,
            sound_speed=c_wave,
            quality_flag=np.ones_like(depth, dtype=bool),
            metadata={
                'wave_amplitude': float(amp),
                'wavenumber': float(k),
                'mode_shape': 'first_baroclinic',
                'peak_depth': float(z_peak)
            }
        )

    def _estimate_mixed_layer_depth(self, depth: np.ndarray, rho: np.ndarray,
                                    T: np.ndarray, threshold: float = 0.03) -> float:
        """
        Estimate Mixed Layer Depth (MLD) using density criterion.

        MLD is defined as the depth where density differs from surface by threshold.

        Args:
            depth: Depth array
            rho: Density array
            T: Temperature array (for temperature-based fallback)
            threshold: Density threshold (kg/m³)

        Returns:
            Mixed layer depth in meters
        """
        if len(depth) < 2:
            return self.params.thermocline_depth * 0.3

        surface_rho = rho[0]
        surface_T = T[0]

        for i in range(1, len(depth)):
            if rho[i] - surface_rho > threshold:
                return float(depth[i])
            if surface_T - T[i] > 0.5:
                return float(depth[i])

        return float(depth[-1])

    def _estimate_uncertainty(self, T: np.ndarray, S: np.ndarray,
                               observations: Optional[List[Dict[str, Any]]]) -> float:
        """Estimate inversion uncertainty based on residuals and observation density."""
        base_uncertainty = 0.1

        if observations and len(observations) > 0:
            obs_unc = np.mean([obs.get('uncertainty', 1.0) for obs in observations])
            n_obs = len(observations)
            uncertainty = base_uncertainty * (1 + obs_unc) / np.sqrt(1 + n_obs)
        else:
            uncertainty = base_uncertainty * 2.0

        return float(min(uncertainty, 1.0))

    def _estimate_energy_conversion_rate(self, N: np.ndarray,
                                          wave_amplitudes: List[float]) -> float:
        """
        Estimate energy conversion rate from barotropic to baroclinic tides.

        Simple estimate based on:
            E_conversion ~ ρ0 * N² * A³ / λ

        Returns:
            Energy conversion rate (W/m²)
        """
        rho0 = 1027.0
        N_mean = np.mean(N[N > 0])

        if len(wave_amplitudes) == 0:
            return 0.0

        A_mean = np.mean(wave_amplitudes)
        A_max = np.max(wave_amplitudes)

        E = 0.5 * rho0 * N_mean**2 * A_mean**2 * A_max / 100.0

        return float(max(0, E))

    def print_inversion_summary(self, result: TSInversionResult) -> None:
        """Print summary of T-S inversion results."""
        print("\n=== T-S Profile Inversion Summary ===")

        if result.background_profile is None:
            print("  No inversion result available")
            return

        prof = result.background_profile
        print(f"\nProfile depth range: 0 - {prof.depth[-1]:.0f}m ({len(prof.depth)} levels)")
        print(f"Mixed Layer Depth: {result.mixed_layer_depth:.1f}m")
        print(f"Pycnocline depth: {result.pycnocline_depth:.1f}m")
        print(f"Stratification strength: {result.stratification_strength:.6f} kg/m^4")
        print(f"Max buoyancy frequency: {np.max(prof.buoyancy_frequency):.4f} rad/s")
        print(f"Inversion uncertainty: {result.inversion_uncertainty:.3f}")
        print(f"Energy conversion rate: {result.energy_conversion_rate:.3e} W/m^2")

        print(f"\nKey depth levels:")
        print("-" * 65)
        print(f"{'Depth(m)':<10} {'T(C)':<10} {'S(PSU)':<10} {'rho(kg/m3)':<12} {'N(rad/s)':<12} {'c(m/s)':<10}")
        print("-" * 65)

        key_depths = [0, 10, 25, 50, 100, 150, 200]
        for z in key_depths:
            if z <= prof.depth[-1]:
                T = prof.get_value_at_depth(z, 'temperature')
                S = prof.get_value_at_depth(z, 'salinity')
                rho = prof.get_value_at_depth(z, 'density')
                N = prof.get_value_at_depth(z, 'buoyancy_frequency')
                c = prof.get_value_at_depth(z, 'sound_speed') if prof.sound_speed is not None else 0
                print(f"{z:<10.0f} {T:<10.2f} {S:<10.2f} {rho:<12.3f} {N:<12.4f} {c:<10.1f}")
        print("-" * 65)

        if result.observations:
            print(f"\nAssimilated observations: {len(result.observations)}")

        if result.wave_induced_profile is not None:
            wprof = result.wave_induced_profile
            dT = np.max(wprof.temperature) - np.min(wprof.temperature)
            dS = np.max(wprof.salinity) - np.min(wprof.salinity)
            print(f"\nWave-induced perturbations: dT={dT:.2f}C, dS={dS:.3f} PSU")

    def visualize_profiles(self, result: TSInversionResult,
                            save_path: Optional[str] = None) -> Any:
        """
        Create visualization of T-S profiles.

        Args:
            result: T-S inversion result
            save_path: Optional path to save figure

        Returns:
            Matplotlib figure object
        """
        import matplotlib.pyplot as plt

        if result.background_profile is None:
            return None

        prof = result.background_profile

        fig, axes = plt.subplots(1, 4, figsize=(16, 8), sharey=True)

        axes[0].plot(prof.temperature, prof.depth, 'b-', linewidth=2)
        if result.wave_induced_profile is not None:
            axes[0].plot(result.wave_induced_profile.temperature,
                        result.wave_induced_profile.depth, 'b--', alpha=0.7, label='Wave-perturbed')
        axes[0].set_xlabel('Temperature (°C)')
        axes[0].set_ylabel('Depth (m)')
        axes[0].set_title('Temperature')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        axes[1].plot(prof.salinity, prof.depth, 'g-', linewidth=2)
        if result.wave_induced_profile is not None:
            axes[1].plot(result.wave_induced_profile.salinity,
                        result.wave_induced_profile.depth, 'g--', alpha=0.7)
        axes[1].set_xlabel('Salinity (PSU)')
        axes[1].set_title('Salinity')
        axes[1].grid(True, alpha=0.3)

        axes[2].plot(prof.density, prof.depth, 'r-', linewidth=2)
        if result.wave_induced_profile is not None:
            axes[2].plot(result.wave_induced_profile.density,
                        result.wave_induced_profile.depth, 'r--', alpha=0.7)
        axes[2].set_xlabel('Density (kg/m³)')
        axes[2].set_title('Density')
        axes[2].grid(True, alpha=0.3)

        axes[3].plot(prof.buoyancy_frequency, prof.depth, 'm-', linewidth=2)
        if result.wave_induced_profile is not None:
            axes[3].plot(result.wave_induced_profile.buoyancy_frequency,
                        result.wave_induced_profile.depth, 'm--', alpha=0.7)
        axes[3].set_xlabel('N (rad/s)')
        axes[3].set_title('Buoyancy Frequency')
        axes[3].grid(True, alpha=0.3)

        for ax in axes:
            ax.invert_yaxis()
            if result.mixed_layer_depth > 0:
                ax.axhline(result.mixed_layer_depth, color='k', linestyle=':', alpha=0.5, label='MLD')
            ax.axhline(result.pycnocline_depth, color='k', linestyle='--', alpha=0.5, label='Pycnocline')

        plt.suptitle('T-S Profile Joint Inversion from SAR Imagery', fontsize=14)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Saved T-S profile plot: {save_path}")

        return fig
