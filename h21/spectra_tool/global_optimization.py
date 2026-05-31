import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from scipy.signal import savgol_filter, find_peaks


@dataclass
class PSOResult:
    wavelengths: List[float]
    intensities: List[float]
    amplitudes: List[float]
    fwhms: List[float]
    r_squared: float
    chi_squared: float
    n_iterations: int
    convergence_history: List[float]
    uncertainty: Optional[List[float]] = field(default_factory=list)


class ParticleSwarmOptimizer:
    """
    Particle Swarm Optimization for multi-peak global search.

    Parameters:
    -----------
    n_particles : int
        Number of particles in the swarm
    max_iterations : int
        Maximum number of iterations
    inertia_weight : float
        Inertia weight (w) for velocity update
    cognitive_weight : float
        Cognitive weight (c1) for personal best
    social_weight : float
        Social weight (c2) for global best
    tolerance : float
        Convergence tolerance
    """

    def __init__(
        self,
        n_particles: int = 50,
        max_iterations: int = 200,
        inertia_weight: float = 0.7,
        cognitive_weight: float = 1.5,
        social_weight: float = 1.5,
        tolerance: float = 1e-6,
    ):
        self.n_particles = n_particles
        self.max_iterations = max_iterations
        self.inertia_weight = inertia_weight
        self.cognitive_weight = cognitive_weight
        self.social_weight = social_weight
        self.tolerance = tolerance

    def _objective_function(
        self,
        params: np.ndarray,
        x: np.ndarray,
        y: np.ndarray,
        n_peaks: int,
        line_profile: str = "gaussian",
    ) -> float:
        """Calculate residual sum of squared errors between model and data."""
        try:
            y_fit = self._multi_peak_model(x, params, n_peaks, line_profile)
            residual = np.sum((y - y_fit) ** 2)
            if np.isnan(residual) or np.isinf(residual):
                return 1e10
            return residual
        except Exception:
            return 1e10

    def _gaussian_peak(
        self, x: np.ndarray, amplitude: float, center: float, fwhm: float
    ) -> np.ndarray:
        sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
        return amplitude * np.exp(-((x - center) ** 2) / (2 * sigma ** 2))

    def _lorentzian_peak(
        self, x: np.ndarray, amplitude: float, center: float, fwhm: float
    ) -> np.ndarray:
        gamma = fwhm / 2
        return amplitude * (gamma ** 2) / ((x - center) ** 2 + gamma ** 2)

    def _multi_peak_model(
        self,
        x: np.ndarray,
        params: np.ndarray,
        n_peaks: int,
        line_profile: str,
    ) -> np.ndarray:
        """Generate multi-peak model from parameters."""
        y = np.zeros_like(x, dtype=float)
        offset = params[-1]

        peak_func = (
            self._gaussian_peak if line_profile == "gaussian" else self._lorentzian_peak
        )

        for i in range(n_peaks):
            amplitude = params[3 * i]
            center = params[3 * i + 1]
            fwhm = params[3 * i + 2]
            y += peak_func(x, amplitude, center, fwhm)

        return y + offset

    def optimize(
        self,
        x: np.ndarray,
        y: np.ndarray,
        n_peaks: int,
        line_profile: str = "gaussian",
        bounds: Optional[np.ndarray] = None,
        initial_guess: Optional[np.ndarray] = None,
        verbose: bool = False,
    ) -> PSOResult:
        """
        Perform PSO optimization to find multi-peak parameters.

        Parameters:
        -----------
        x : np.ndarray
            Wavelength array
        y : np.ndarray
            Intensity array
        n_peaks : int
            Number of peaks to fit
        line_profile : str
            Line profile type: 'gaussian' or 'lorentzian'
        bounds : np.ndarray, optional
            Parameter bounds array of shape (n_params, 2)
        initial_guess : np.ndarray, optional
            Initial parameter guess
        verbose : bool
            Whether to print progress

        Returns:
        --------
        PSOResult
            Optimization result with optimized parameters
        """
        n_params = 3 * n_peaks + 1

        if bounds is None:
            x_min, x_max = np.min(x), np.max(x)
            y_min, y_max = np.min(y), np.max(y)
            y_range = y_max - y_min
            x_range = x_max - x_min
            fwhm_guess = x_range / (n_peaks * 3)

            bounds = []
            for i in range(n_peaks):
                bounds.append([y_range * 0.05, y_range * 3.0])
                bounds.append([x_min, x_max])
                bounds.append([fwhm_guess * 0.1, fwhm_guess * 10])
            bounds.append([y_min * 0.5, y_max * 0.5])
            bounds = np.array(bounds)

        if initial_guess is None:
            try:
                window_len = min(51, len(y) // 4 * 2 + 1)
                if window_len < 5:
                    window_len = 5
                if window_len % 2 == 0:
                    window_len += 1

                smoothed = savgol_filter(y, window_length=window_len, polyorder=3)
                y_range_smooth = np.max(smoothed) - np.min(smoothed)

                peak_indices, properties = find_peaks(
                    smoothed,
                    distance=max(5, len(y) // (n_peaks * 3)),
                    prominence=(y_range_smooth * 0.02),
                    height=(np.min(smoothed) + y_range_smooth * 0.05),
                )

                if len(peak_indices) >= n_peaks:
                    prominences = properties.get("prominences", np.ones(len(peak_indices)))
                    sorted_idx = np.argsort(prominences)[::-1]
                    peak_indices = peak_indices[sorted_idx[:n_peaks]]
                else:
                    peak_indices = np.argsort(smoothed)[-n_peaks:]

                peak_indices = np.sort(peak_indices)

                initial_guess = []
                for idx in peak_indices[:n_peaks]:
                    amplitude = max(smoothed[idx] - y_min, y_range * 0.1)
                    center = x[idx]

                    half_max = y_min + amplitude / 2
                    try:
                        left_idx = idx
                        while left_idx > 0 and smoothed[left_idx] > half_max:
                            left_idx -= 1
                        right_idx = idx
                        while right_idx < len(smoothed) - 1 and smoothed[right_idx] > half_max:
                            right_idx += 1
                        estimated_fwhm = abs(x[right_idx] - x[left_idx])
                        if estimated_fwhm < fwhm_guess * 0.1:
                            estimated_fwhm = fwhm_guess
                        if estimated_fwhm > fwhm_guess * 3:
                            estimated_fwhm = fwhm_guess
                    except:
                        estimated_fwhm = fwhm_guess

                    initial_guess.append(amplitude)
                    initial_guess.append(center)
                    initial_guess.append(estimated_fwhm)
                initial_guess.append(y_min * 0.5)
                initial_guess = np.array(initial_guess)
            except Exception as e:
                print(f"Initial guess estimation failed: {e}, using random initialization")
                initial_guess = np.random.uniform(bounds[:, 0], bounds[:, 1])

        particles = np.random.uniform(
            bounds[:, 0], bounds[:, 1], size=(self.n_particles, n_params)
        )
        particles[0] = initial_guess

        velocities = np.random.uniform(
            -0.1 * (bounds[:, 1] - bounds[:, 0]),
            0.1 * (bounds[:, 1] - bounds[:, 0]),
            size=(self.n_particles, n_params),
        )

        personal_best_positions = particles.copy()
        personal_best_scores = np.array(
            [
                self._objective_function(p, x, y, n_peaks, line_profile)
                for p in particles
            ]
        )

        global_best_idx = np.argmin(personal_best_scores)
        global_best_position = personal_best_positions[global_best_idx].copy()
        global_best_score = personal_best_scores[global_best_idx]

        convergence_history = [global_best_score]

        iteration = 0
        for iteration in range(self.max_iterations):
            r1 = np.random.random((self.n_particles, n_params))
            r2 = np.random.random((self.n_particles, n_params))

            velocities = (
                self.inertia_weight * velocities
                + self.cognitive_weight * r1 * (personal_best_positions - particles)
                + self.social_weight * r2 * (global_best_position - particles)
            )

            particles = particles + velocities

            for i in range(self.n_particles):
                particles[i] = np.clip(particles[i], bounds[:, 0], bounds[:, 1])

            scores = np.array(
                [
                    self._objective_function(p, x, y, n_peaks, line_profile)
                    for p in particles
                ]
            )

            update_mask = scores < personal_best_scores
            personal_best_positions[update_mask] = particles[update_mask]
            personal_best_scores[update_mask] = scores[update_mask]

            new_global_best_idx = np.argmin(personal_best_scores)
            new_global_best_score = personal_best_scores[new_global_best_idx]

            if new_global_best_score < global_best_score:
                global_best_position = personal_best_positions[new_global_best_idx].copy()
                global_best_score = new_global_best_score

            convergence_history.append(global_best_score)

            if iteration > 10:
                recent_improvement = (
                    convergence_history[-10] - convergence_history[-1]
                ) / max(abs(convergence_history[-10]), 1e-10)
                if recent_improvement < self.tolerance:
                    if verbose:
                        print(f"Converged at iteration {iteration}")
                    break

            if verbose and iteration % 20 == 0:
                print(f"Iteration {iteration}: Best score = {global_best_score:.6f}")

        y_fit = self._multi_peak_model(x, global_best_position, n_peaks, line_profile)

        ss_res = np.sum((y - y_fit) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        dof = max(len(x) - n_params, 1)
        chi_squared = ss_res / dof

        wavelengths = []
        intensities = []
        amplitudes = []
        fwhms = []

        for i in range(n_peaks):
            amplitudes.append(global_best_position[3 * i])
            wavelengths.append(global_best_position[3 * i + 1])
            fwhms.append(global_best_position[3 * i + 2])

        sort_idx = np.argsort(wavelengths)
        wavelengths = [wavelengths[i] for i in sort_idx]
        amplitudes = [amplitudes[i] for i in sort_idx]
        fwhms = [fwhms[i] for i in sort_idx]

        offset = global_best_position[-1]
        for i in range(n_peaks):
            peak_curve = self._gaussian_peak(
                x, amplitudes[i], wavelengths[i], fwhms[i]
            ) if line_profile == "gaussian" else self._lorentzian_peak(
                x, amplitudes[i], wavelengths[i], fwhms[i]
            )
            intensities.append(float(np.max(peak_curve + offset)))

        return PSOResult(
            wavelengths=wavelengths,
            intensities=intensities,
            amplitudes=amplitudes,
            fwhms=fwhms,
            r_squared=r_squared,
            chi_squared=chi_squared,
            n_iterations=iteration + 1,
            convergence_history=convergence_history,
        )


def pso_peak_search(
    wavelength: np.ndarray,
    intensity: np.ndarray,
    n_peaks: int,
    line_profile: str = "gaussian",
    n_particles: int = 50,
    max_iterations: int = 200,
    verbose: bool = False,
    **kwargs,
) -> PSOResult:
    """
    High-level function for PSO-based global peak search.

    Parameters:
    -----------
    wavelength : np.ndarray
        Wavelength array
    intensity : np.ndarray
        Intensity array
    n_peaks : int
        Number of peaks to find
    line_profile : str
        Line profile: 'gaussian' or 'lorentzian'
    n_particles : int
        Number of particles in the swarm
    max_iterations : int
        Maximum number of iterations
    verbose : bool
        Whether to print progress
    **kwargs
        Additional arguments for ParticleSwarmOptimizer

    Returns:
    --------
    PSOResult
        Peak search results
    """
    pso_kwargs = {}
    valid_params = ["inertia_weight", "cognitive_weight", "social_weight", "tolerance"]
    for k, v in kwargs.items():
        if k in valid_params:
            pso_kwargs[k] = v

    optimizer = ParticleSwarmOptimizer(
        n_particles=n_particles,
        max_iterations=max_iterations,
        **pso_kwargs,
    )

    return optimizer.optimize(
        wavelength, intensity, n_peaks=n_peaks, line_profile=line_profile, verbose=verbose
    )
