import numpy as np
from scipy import optimize
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class InversionParams:
    """Parameters for amplitude inversion."""
    water_depth: float = 100.0
    upper_layer_density: float = 1024.0
    lower_layer_density: float = 1027.0
    upper_layer_thickness: float = 20.0
    gravity: float = 9.81
    wind_speed: float = 5.0
    wind_direction: float = 0.0
    surface_tension: float = 0.074
    kinematic_viscosity: float = 1.5e-6
    modulation_transfer_function: float = 0.3
    radar_frequency: float = 5.3e9
    incidence_angle: float = 23.0
    use_ekdv: bool = True
    ekdv_threshold_ratio: float = 0.3
    ekdv_max_iterations: int = 20
    ekdv_convergence_tolerance: float = 1e-4


@dataclass
class InvertedWave:
    """Data class for an inverted internal wave."""
    wave_id: int
    amplitude: float
    half_width: float
    phase_speed: float
    wavelength: float
    kdv_coefficient: Optional[float] = None
    dispersion_coefficient: Optional[float] = None
    nonlinearity_coefficient: Optional[float] = None
    second_order_nonlinearity: Optional[float] = None
    reduced_gravity: Optional[float] = None
    wave_energy: Optional[float] = None
    inverse_method: str = 'kdv'
    ekdv_correction: float = 0.0
    second_order_amplitude: float = 0.0
    shallow_water_ratio: float = 0.0
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InversionResult:
    """Result of amplitude inversion."""
    inverted_waves: List[InvertedWave] = field(default_factory=list)
    density_ratio: float = 0.0
    buoyancy_frequency: float = 0.0
    modal_structure: Optional[np.ndarray] = None


class AmplitudeInverter:
    """
    Invert internal wave amplitude based on KdV equation,
    using image contrast and background wind field.
    """

    def __init__(self, params: Optional[InversionParams] = None):
        """
        Initialize amplitude inverter.

        Args:
            params: Inversion parameters
        """
        self.params = params or InversionParams()

    def invert(self, detection_result: Any,
               wavefront_result: Optional[Any] = None) -> InversionResult:
        """
        Invert amplitudes for all detected waves.

        Args:
            detection_result: Wave detection result
            wavefront_result: Optional wavefront extraction result

        Returns:
            InversionResult
        """
        logger.info("Starting amplitude inversion...")

        result = InversionResult()

        g_prime = self._compute_reduced_gravity()
        result.density_ratio = g_prime / self.params.gravity
        result.buoyancy_frequency = self._compute_buoyancy_frequency()
        result.modal_structure = self._compute_modal_structure()

        logger.info(f"  Reduced gravity: {g_prime:.4f} m/s²")
        logger.info(f"  Buoyancy frequency: {result.buoyancy_frequency:.4f} rad/s")

        for wave in detection_result.waves:
            inverted = self._invert_single_wave(wave, wavefront_result, g_prime)
            result.inverted_waves.append(inverted)

        logger.info(f"Inversion completed for {len(result.inverted_waves)} waves.")
        return result

    def _invert_single_wave(self, wave: Any, wavefront_result: Optional[Any],
                            g_prime: float) -> InvertedWave:
        """
        Invert amplitude for a single wave.

        Args:
            wave: Detected wave
            wavefront_result: Wavefront extraction result
            g_prime: Reduced gravity

        Returns:
            InvertedWave
        """
        wavelength = wave.wavelength
        spacing = wave.spacing
        contrast = wave.contrast

        if hasattr(wave, 'interference_factor') and wave.interference_factor != 1.0:
            logger.info(f"  Inverting wave {wave.wave_id}: λ={wavelength:.1f}m, C={contrast:.3f}, "
                       f"interference_factor={wave.interference_factor:.2f}")
        else:
            logger.info(f"  Inverting wave {wave.wave_id}: λ={wavelength:.1f}m, C={contrast:.3f}")

        p = self.params
        h1 = p.upper_layer_thickness
        h2 = p.water_depth - h1
        h_ratio = h1 / max(h2, 0.01)

        use_ekdv = p.use_ekdv and h_ratio > p.ekdv_threshold_ratio

        if use_ekdv:
            logger.info(f"    Using eKdV equation (shallow water, h1/h2={h_ratio:.3f})")
            return self._invert_single_wave_ekdv(wave, g_prime, h_ratio)
        else:
            logger.info(f"    Using KdV equation (h1/h2={h_ratio:.3f})")
            return self._invert_single_wave_kdv(wave, g_prime, h_ratio)

    def _invert_single_wave_kdv(self, wave: Any, g_prime: float,
                                 h_ratio: float) -> InvertedWave:
        """
        Invert amplitude using classic KdV equation.

        Args:
            wave: Detected wave
            g_prime: Reduced gravity
            h_ratio: Layer thickness ratio h1/h2

        Returns:
            InvertedWave
        """
        wavelength = wave.wavelength
        spacing = wave.spacing
        contrast = wave.contrast

        phase_speed = self._compute_linear_phase_speed(wavelength, g_prime)
        alpha, beta = self._compute_kdv_coefficients(wavelength, g_prime)
        half_width = self._estimate_half_width(wavelength, beta, alpha, g_prime)

        amplitude = self._invert_amplitude_from_contrast(
            contrast, wavelength, half_width, g_prime, phase_speed
        )
        amplitude = self._apply_wind_correction(amplitude)

        if amplitude is None or np.isnan(amplitude):
            amplitude = self._estimate_amplitude_kdv(wavelength, half_width, alpha, beta)

        kdv_amp = self._estimate_amplitude_kdv(wavelength, half_width, alpha, beta)
        amplitude = 0.7 * amplitude + 0.3 * kdv_amp

        wave_energy = self._compute_wave_energy(amplitude, wavelength, g_prime)
        confidence = self._compute_inversion_confidence(wave, amplitude)

        return InvertedWave(
            wave_id=wave.wave_id,
            amplitude=float(abs(amplitude)),
            half_width=float(half_width),
            phase_speed=float(phase_speed),
            wavelength=float(wavelength),
            kdv_coefficient=float(alpha) if alpha else None,
            dispersion_coefficient=float(beta) if beta else None,
            nonlinearity_coefficient=float(3 * alpha / 2) if alpha else None,
            reduced_gravity=float(g_prime),
            wave_energy=float(wave_energy) if wave_energy else None,
            inverse_method='kdv_contrast',
            shallow_water_ratio=float(h_ratio),
            confidence=float(confidence),
            metadata={
                'contrast': float(contrast),
                'spacing': float(spacing),
                'raw_amplitude': float(amplitude),
                'kdv_amplitude': float(kdv_amp),
                'wind_correction_applied': True,
                'wind_speed': self.params.wind_speed,
                'layer_thickness_ratio': float(h_ratio)
            }
        )

    def _invert_single_wave_ekdv(self, wave: Any, g_prime: float,
                                  h_ratio: float) -> InvertedWave:
        """
        Invert amplitude using extended KdV (eKdV) equation for shallow water.

        eKdV includes second-order nonlinear term:
            η_t + cη_x + αηη_x + α₂η²η_x + βη_xxx = 0

        The eKdV soliton solution has a correction to the classic KdV solution
        that accounts for the finite depth ratio (h1 and h2 are comparable).

        Args:
            wave: Detected wave
            g_prime: Reduced gravity
            h_ratio: Layer thickness ratio h1/h2

        Returns:
            InvertedWave
        """
        wavelength = wave.wavelength
        spacing = wave.spacing
        contrast = wave.contrast

        phase_speed = self._compute_linear_phase_speed(wavelength, g_prime)
        alpha, beta = self._compute_kdv_coefficients(wavelength, g_prime)
        alpha2 = self._compute_ekdv_second_order_coefficient(wavelength, g_prime)

        half_width_kdv = self._estimate_half_width(wavelength, beta, alpha, g_prime)
        half_width = self._estimate_half_width_ekdv(wavelength, beta, alpha, alpha2, g_prime)

        amplitude_contrast = self._invert_amplitude_from_contrast(
            contrast, wavelength, half_width, g_prime, phase_speed
        )
        amplitude_contrast = self._apply_wind_correction(amplitude_contrast)

        amplitude_ekdv = self._estimate_amplitude_ekdv(wavelength, half_width, alpha, alpha2, beta)

        if amplitude_contrast is None or np.isnan(amplitude_contrast):
            amplitude = amplitude_ekdv
        else:
            amplitude = 0.6 * amplitude_contrast + 0.4 * amplitude_ekdv

        amplitude, second_order_amp, correction = self._iterative_ekdv_solve(
            amplitude, wavelength, alpha, alpha2, beta, g_prime
        )

        wave_energy = self._compute_wave_energy_ekdv(amplitude, second_order_amp, wavelength, g_prime)
        confidence = self._compute_inversion_confidence(wave, amplitude)

        return InvertedWave(
            wave_id=wave.wave_id,
            amplitude=float(abs(amplitude)),
            half_width=float(half_width),
            phase_speed=float(phase_speed),
            wavelength=float(wavelength),
            kdv_coefficient=float(alpha) if alpha else None,
            dispersion_coefficient=float(beta) if beta else None,
            nonlinearity_coefficient=float(3 * alpha / 2) if alpha else None,
            second_order_nonlinearity=float(alpha2) if alpha2 else None,
            reduced_gravity=float(g_prime),
            wave_energy=float(wave_energy) if wave_energy else None,
            inverse_method='ekdv_contrast',
            ekdv_correction=float(correction),
            second_order_amplitude=float(second_order_amp),
            shallow_water_ratio=float(h_ratio),
            confidence=float(confidence),
            metadata={
                'contrast': float(contrast),
                'spacing': float(spacing),
                'raw_amplitude': float(amplitude),
                'ekdv_amplitude': float(amplitude_ekdv),
                'second_order_amplitude': float(second_order_amp),
                'ekdv_correction': float(correction),
                'alpha2': float(alpha2) if alpha2 else None,
                'wind_correction_applied': True,
                'wind_speed': self.params.wind_speed,
                'layer_thickness_ratio': float(h_ratio),
                'iterations': int(self.params.ekdv_max_iterations)
            }
        )

    def _compute_reduced_gravity(self) -> float:
        """
        Compute reduced gravity g' = g*(ρ2 - ρ1)/ρ2.

        Returns:
            Reduced gravity in m/s²
        """
        p = self.params
        return p.gravity * (p.lower_layer_density - p.upper_layer_density) / p.lower_layer_density

    def _compute_buoyancy_frequency(self) -> float:
        """
        Compute buoyancy frequency N = sqrt(g'/h1).

        Returns:
            Buoyancy frequency in rad/s
        """
        g_prime = self._compute_reduced_gravity()
        return np.sqrt(g_prime / self.params.upper_layer_thickness)

    def _compute_modal_structure(self, n_modes: int = 3) -> np.ndarray:
        """
        Compute vertical modal structure for internal waves.

        Args:
            n_modes: Number of modes to compute

        Returns:
            Modal structure array
        """
        h1 = self.params.upper_layer_thickness
        h2 = self.params.water_depth - h1
        g_prime = self._compute_reduced_gravity()

        modes = []
        for n in range(1, n_modes + 1):
            k_n = n * np.pi / (h1 + h2)
            omega_n = np.sqrt(g_prime * k_n * h1 * h2 / (h1 + h2))
            modes.append([n, k_n, omega_n])

        return np.array(modes)

    def _compute_linear_phase_speed(self, wavelength: float, g_prime: float) -> float:
        """
        Compute linear phase speed for long internal waves.
        c = sqrt(g' * h1 * h2 / (h1 + h2))

        Args:
            wavelength: Wave wavelength in meters
            g_prime: Reduced gravity

        Returns:
            Phase speed in m/s
        """
        p = self.params
        h1 = p.upper_layer_thickness
        h2 = p.water_depth - h1

        k = 2 * np.pi / wavelength
        c_linear = np.sqrt(g_prime * h1 * h2 / (h1 + h2))

        c = c_linear / np.sqrt(1 + (k * h1) * (k * h2) / 3)

        return c

    def _compute_kdv_coefficients(self, wavelength: float, g_prime: float) -> Tuple[float, float]:
        """
        Compute KdV equation coefficients.
        KdV: η_t + c*η_x + α*η*η_x + β*η_xxx = 0

        Args:
            wavelength: Wave wavelength
            g_prime: Reduced gravity

        Returns:
            Tuple of (alpha, beta)
        """
        p = self.params
        h1 = p.upper_layer_thickness
        h2 = p.water_depth - h1

        c0 = np.sqrt(g_prime * h1 * h2 / (h1 + h2))

        alpha = 3 * c0 * (h2 - h1) / (2 * h1 * h2)

        beta = c0 * h1 * h2 / 6

        return alpha, beta

    def _estimate_half_width(self, wavelength: float, beta: float,
                             alpha: float, g_prime: float) -> float:
        """
        Estimate wave half-width from KdV soliton solution.
        For KdV soliton: η(x) = A * sech²((x - ct)/L)
        where L = sqrt(12β/(αA))

        Args:
            wavelength: Wave wavelength
            beta: Dispersion coefficient
            alpha: Nonlinear coefficient
            g_prime: Reduced gravity

        Returns:
            Half-width in meters
        """
        p = self.params
        h1 = p.upper_layer_thickness
        h2 = p.water_depth - h1

        denom = abs(alpha) * np.max([0.5, h1 * 0.1])
        if denom < 1e-8:
            L_kdv = wavelength / 3
        else:
            L_kdv = np.sqrt(12 * beta / denom)

        L_geo = wavelength / (2 * np.pi) * np.sqrt(h1 * h2 / (h1 + h2))

        half_width = 0.6 * L_kdv + 0.4 * L_geo
        half_width = max(half_width, 5.0)

        return half_width

    def _invert_amplitude_from_contrast(self, contrast: float, wavelength: float,
                                        half_width: float, g_prime: float,
                                        phase_speed: float) -> float:
        """
        Invert amplitude from SAR image contrast.

        The relation between SAR image contrast and internal wave amplitude
        involves:
        1. Surface current modulation by internal waves
        2. Modulation transfer function (MTF) relating current to NRCS

        Args:
            contrast: Image contrast (I_max - I_min)/I_mean
            wavelength: Wave wavelength
            half_width: Wave half-width
            g_prime: Reduced gravity
            phase_speed: Phase speed

        Returns:
            Estimated amplitude in meters
        """
        p = self.params

        if wavelength < 1e-6:
            wavelength = 50.0
        k = 2 * np.pi / wavelength

        U_max = phase_speed * np.sqrt(g_prime * p.upper_layer_thickness) / 10

        M = max(p.modulation_transfer_function, 0.01)

        denom = M * k * phase_speed * np.exp(-1)
        if abs(denom) < 1e-8:
            return 10.0

        A_contrast = (contrast * U_max) / denom

        A_contrast = A_contrast * (1 + 0.5 * np.tanh((p.wind_speed - 5) / 3))

        max_amplitude = p.upper_layer_thickness * 0.8
        A_contrast = np.clip(A_contrast, 0.5, max_amplitude)

        return A_contrast

    def _estimate_amplitude_kdv(self, wavelength: float, half_width: float,
                                alpha: float, beta: float) -> float:
        """
        Estimate amplitude from KdV soliton relation.
        A = 12β / (α * L²)

        Args:
            wavelength: Wave wavelength
            half_width: Wave half-width
            alpha: Nonlinear coefficient
            beta: Dispersion coefficient

        Returns:
            Estimated amplitude in meters
        """
        if alpha == 0 or half_width == 0:
            return 10.0

        L = half_width
        A = 12 * beta / (alpha * L**2)

        return abs(A)

    def _compute_ekdv_second_order_coefficient(self, wavelength: float, g_prime: float) -> float:
        """
        Compute the second-order nonlinear coefficient α₂ for the eKdV equation.

        eKdV: η_t + cη_x + αηη_x + α₂η²η_x + βη_xxx = 0

        For a two-layer fluid, the second-order coefficient accounts for
        finite-amplitude effects when h1 and h2 are comparable (shallow water).

        Args:
            wavelength: Wave wavelength in meters
            g_prime: Reduced gravity

        Returns:
            Second-order nonlinear coefficient α₂
        """
        p = self.params
        h1 = p.upper_layer_thickness
        h2 = p.water_depth - h1

        if h1 <= 0 or h2 <= 0:
            return 0.0

        c0 = np.sqrt(g_prime * h1 * h2 / (h1 + h2))

        alpha2 = - (3 * c0 / 8) * (h1**3 + h2**3) / (h1**3 * h2**3)

        return alpha2

    def _estimate_half_width_ekdv(self, wavelength: float, beta: float,
                                   alpha: float, alpha2: float, g_prime: float) -> float:
        """
        Estimate wave half-width from eKdV soliton solution.

        The eKdV soliton solution has a correction to the KdV width:
            L_ekdv = L_kdv * (1 + (α₂/α) * A + ...)

        For first-order estimation, we use the ratio of coefficients to
        adjust the KdV width.

        Args:
            wavelength: Wave wavelength
            beta: Dispersion coefficient
            alpha: First-order nonlinear coefficient
            alpha2: Second-order nonlinear coefficient
            g_prime: Reduced gravity

        Returns:
            Half-width in meters
        """
        p = self.params
        h1 = p.upper_layer_thickness
        h2 = p.water_depth - h1

        L_kdv = self._estimate_half_width(wavelength, beta, alpha, g_prime)

        if abs(alpha) < 1e-10:
            return L_kdv

        correction_factor = 1.0 + 0.1 * abs(alpha2 / alpha) * min(h1, h2)
        correction_factor = np.clip(correction_factor, 0.8, 1.5)

        half_width = L_kdv * correction_factor
        half_width = max(half_width, 5.0)

        return half_width

    def _estimate_amplitude_ekdv(self, wavelength: float, half_width: float,
                                  alpha: float, alpha2: float, beta: float) -> float:
        """
        Estimate amplitude from eKdV soliton relation.

        For eKdV, the amplitude-width relation has a correction:
            A = (12β / (α L²)) / (1 + (20 α₂ / α) * A)

        This is solved iteratively.

        Args:
            wavelength: Wave wavelength
            half_width: Wave half-width
            alpha: First-order nonlinear coefficient
            alpha2: Second-order nonlinear coefficient
            beta: Dispersion coefficient

        Returns:
            Estimated amplitude in meters
        """
        if alpha == 0 or half_width == 0:
            return 10.0

        A_kdv = self._estimate_amplitude_kdv(wavelength, half_width, alpha, beta)

        if abs(alpha) < 1e-10:
            return A_kdv

        ratio = alpha2 / alpha
        correction = 1.0 + 0.05 * abs(ratio) * A_kdv

        A_ekdv = A_kdv / correction
        A_ekdv = max(0.5, min(A_ekdv, self.params.upper_layer_thickness * 0.8))

        return A_ekdv

    def _iterative_ekdv_solve(self, amplitude_guess: float, wavelength: float,
                               alpha: float, alpha2: float, beta: float,
                               g_prime: float) -> Tuple[float, float, float]:
        """
        Iteratively solve the eKdV amplitude-width relation for self-consistency.

        The eKdV soliton solution satisfies:
            η(x) = A₁ sech²(kx) + A₂ sech⁴(kx)

        where A₂ is the second-order amplitude correction.

        Args:
            amplitude_guess: Initial amplitude guess
            wavelength: Wave wavelength
            alpha: First-order nonlinear coefficient
            alpha2: Second-order nonlinear coefficient
            beta: Dispersion coefficient
            g_prime: Reduced gravity

        Returns:
            Tuple of (corrected_amplitude, second_order_amplitude, correction_magnitude)
        """
        p = self.params

        A = amplitude_guess
        if A is None or np.isnan(A) or A <= 0:
            A = 5.0
        A2 = 0.0

        for iteration in range(p.ekdv_max_iterations):
            A_old = A

            if abs(alpha) < 1e-10:
                break

            L = self._estimate_half_width_ekdv(wavelength, beta, alpha, alpha2, g_prime)

            if L <= 0:
                break

            A_kdv = 12 * beta / (alpha * L**2)

            if abs(alpha) > 1e-10:
                ratio = alpha2 / alpha
                A2 = - (5.0 / 12.0) * ratio * A_kdv**2
                correction = 1.0 + 0.2 * ratio * A_kdv
                A = A_kdv / max(0.5, correction)
            else:
                A2 = 0.0
                A = A_kdv

            A = max(0.1, min(A, p.upper_layer_thickness * 0.8))
            A2 = max(0, min(abs(A2), A * 0.3))

            if abs(A - A_old) / max(A_old, 1e-6) < p.ekdv_convergence_tolerance:
                break

        correction_magnitude = abs(A - amplitude_guess) / max(amplitude_guess, 1e-6)

        return A, A2, correction_magnitude

    def _compute_wave_energy_ekdv(self, amplitude: float, second_order_amp: float,
                                   wavelength: float, g_prime: float) -> float:
        """
        Compute wave energy per unit length for eKdV soliton.

        For eKdV, the energy includes contributions from both first and
        second order components:
            E = (1/2)ρ₁g'λ (A₁² + (8/5)A₁A₂ + ...)

        Args:
            amplitude: First-order wave amplitude A₁
            second_order_amp: Second-order amplitude A₂
            wavelength: Wave wavelength
            g_prime: Reduced gravity

        Returns:
            Wave energy per unit length in J/m
        """
        p = self.params
        rho1 = p.upper_layer_density

        E_kdv = self._compute_wave_energy(amplitude, wavelength, g_prime)

        if abs(amplitude) > 1e-6:
            ratio = second_order_amp / amplitude
            correction = 1.0 + (8.0 / 5.0) * ratio
            correction = max(0.9, min(correction, 1.5))
        else:
            correction = 1.0

        E_ekdv = E_kdv * correction

        return E_ekdv

    def _apply_wind_correction(self, amplitude: float) -> float:
        """
        Apply wind correction to amplitude estimate.

        Args:
            amplitude: Initial amplitude estimate

        Returns:
            Wind-corrected amplitude
        """
        p = self.params

        wind_factor = 1.0 + 0.05 * (p.wind_speed - 5)
        wind_factor = np.clip(wind_factor, 0.7, 1.5)

        return amplitude * wind_factor

    def _compute_wave_energy(self, amplitude: float, wavelength: float,
                             g_prime: float) -> float:
        """
        Compute wave energy per unit length.
        E = (1/2) * ρ1 * g' * A² * λ

        Args:
            amplitude: Wave amplitude
            wavelength: Wave wavelength
            g_prime: Reduced gravity

        Returns:
            Energy per unit length in J/m
        """
        p = self.params

        energy = 0.5 * p.upper_layer_density * g_prime * amplitude**2 * wavelength

        return energy

    def _compute_inversion_confidence(self, wave: Any, amplitude: float) -> float:
        """
        Compute confidence score for inversion.

        Args:
            wave: Detected wave
            amplitude: Inverted amplitude

        Returns:
            Confidence score (0-1)
        """
        p = self.params

        factors = []

        factors.append(wave.confidence)

        if wave.contrast > 0.1:
            factors.append(min(wave.contrast / 0.5, 1.0))
        else:
            factors.append(0.3)

        if 1.0 < amplitude < p.upper_layer_thickness * 0.7:
            factors.append(1.0)
        elif 0.5 < amplitude < p.upper_layer_thickness * 0.9:
            factors.append(0.7)
        else:
            factors.append(0.3)

        if 5 < p.wind_speed < 15:
            factors.append(1.0)
        else:
            factors.append(0.6)

        confidence = float(np.mean(factors))
        return min(confidence, 1.0)

    def solve_kdv_ivp(self, initial_condition: np.ndarray, x: np.ndarray,
                      t_max: float = 3600) -> np.ndarray:
        """
        Solve KdV initial value problem for wave propagation simulation.

        Args:
            initial_condition: Initial wave profile
            x: Spatial grid
            t_max: Maximum time

        Returns:
            Wave profile at t_max
        """
        dx = x[1] - x[0]

        alpha, beta = self._compute_kdv_coefficients(np.ptp(x),
                                                     self._compute_reduced_gravity())
        c0 = self._compute_linear_phase_speed(np.ptp(x),
                                              self._compute_reduced_gravity())

        def rhs(eta, t):
            eta_x = np.gradient(eta, dx)
            eta_xxx = np.gradient(np.gradient(eta_x, dx), dx)
            return -c0 * eta_x - alpha * eta * eta_x - beta * eta_xxx

        from scipy.integrate import odeint
        t = np.linspace(0, t_max, 2)
        solution = odeint(rhs, initial_condition, t)

        return solution[-1]

    def print_inversion_summary(self, result: InversionResult) -> None:
        """
        Print summary of inversion results.

        Args:
            result: Inversion result
        """
        print("\n=== Amplitude Inversion Summary ===")
        print(f"Reduced gravity g': {result.density_ratio * self.params.gravity:.4f} m/s^2")
        print(f"Buoyancy frequency N: {result.buoyancy_frequency:.4f} rad/s")

        h1 = self.params.upper_layer_thickness
        h2 = self.params.water_depth - h1
        h_ratio = h1 / max(h2, 0.01)
        print(f"Water depth: {self.params.water_depth:.1f}m, Upper layer: {h1:.1f}m, h1/h2: {h_ratio:.3f}")

        if self.params.use_ekdv and h_ratio > self.params.ekdv_threshold_ratio:
            print(f"Equation mode: eKdV (shallow water correction active)")
        else:
            print(f"Equation mode: KdV (classic)")

        ekdv_count = sum(1 for inv in result.inverted_waves if inv.inverse_method.startswith('ekdv'))
        kdv_count = len(result.inverted_waves) - ekdv_count
        print(f"Inverted {len(result.inverted_waves)} waves: {ekdv_count} eKdV, {kdv_count} KdV")

        print(f"\nInverted Waves:")
        print("-" * 100)
        print(f"{'ID':<4} {'Pkt':<4} {'Idx':<4} {'Amp(m)':<10} {'HW(m)':<10} {'c(m/s)':<10} {'λ(m)':<10} "
              f"{'IF':<6} {'h1/h2':<8} {'Method':<10} {'E(J/m)':<12} {'Conf':<6}")
        print("-" * 100)

        for inv in result.inverted_waves:
            energy_str = f"{inv.wave_energy:.2e}" if inv.wave_energy else "N/A"
            pkt_id = inv.metadata.get('position_in_packet', -1) if inv.metadata else -1
            idx_in_pkt = inv.metadata.get('position_in_packet', 0) if inv.metadata else 0
            interference = 1.0
            if inv.metadata and 'interference_factor' in inv.metadata:
                interference = inv.metadata['interference_factor']
            method_short = 'eKdV' if inv.inverse_method.startswith('ekdv') else 'KdV'

            print(f"{inv.wave_id:<4} {pkt_id:<4} {idx_in_pkt:<4} {inv.amplitude:<10.2f} {inv.half_width:<10.1f} "
                  f"{inv.phase_speed:<10.2f} {inv.wavelength:<10.1f} "
                  f"{interference:<6.2f} {inv.shallow_water_ratio:<8.3f} {method_short:<10} "
                  f"{energy_str:<12} {inv.confidence:<6.2f}")
        print("-" * 100)
