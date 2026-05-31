import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
import logging
from scipy import ndimage, signal

logger = logging.getLogger(__name__)


@dataclass
class BreakingParams:
    """Parameters for wave breaking simulation."""
    breaking_threshold_richardson: float = 0.25
    breaking_threshold_amp_depth: float = 0.3
    breaking_threshold_steepness: float = 0.1
    surface_tension: float = 0.074
    kinematic_viscosity: float = 1.5e-6
    von_karman_constant: float = 0.41
    charnock_constant: float = 0.0185
    gravity: float = 9.81
    radar_frequency: float = 5.3e9
    incidence_angle: float = 23.0
    wind_drag_coefficient: float = 1.3e-3
    simulate_turbulence: bool = True
    turbulence_model: str = 'k_epsilon'
    roughness_model: str = 'cmog'
    min_breaking_probability: float = 0.05
    max_breaking_probability: float = 0.95


@dataclass
class BreakingRegion:
    """Data class for a wave breaking region."""
    region_id: int
    center_row: int
    center_col: int
    area: float
    probability: float
    breaking_type: str
    richardson_number: float
    amplitude_depth_ratio: float
    wave_steepness: float
    energy_dissipation: float
    turbulence_intensity: float
    surface_roughness: float
    radar_backscatter: float
    bbox: Tuple[int, int, int, int]
    mask: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoughnessMap:
    """Sea surface roughness map."""
    roughness: np.ndarray
    backscatter: np.ndarray
    turbulent_kinetic_energy: Optional[np.ndarray] = None
    dissipation_rate: Optional[np.ndarray] = None
    vorticity: Optional[np.ndarray] = None
    surface_current_u: Optional[np.ndarray] = None
    surface_current_v: Optional[np.ndarray] = None
    breaking_mask: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BreakingSimulationResult:
    """Result of wave breaking simulation."""
    breaking_regions: List[BreakingRegion] = field(default_factory=list)
    roughness_map: Optional[RoughnessMap] = None
    total_breaking_area: float = 0.0
    total_energy_dissipation: float = 0.0
    mean_breaking_probability: float = 0.0
    breaking_type_distribution: Dict[str, int] = field(default_factory=dict)
    simulation_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class WaveBreakingModel:
    """
    Internal wave breaking and sea surface roughness simulation model.

    This module simulates:
    1. Wave breaking probability based on multiple instability criteria
    2. Turbulence generation and dissipation in breaking regions
    3. Sea surface roughness modification by internal waves
    4. Radar backscatter changes due to roughness variations

    Physical models:
    - Richardson number criterion for shear instability
    - Amplitude/depth ratio for convective instability
    - Wave steepness for surface breaking
    - CMOG/Charnock roughness parameterization
    - k-ε turbulence model (simplified)
    """

    def __init__(self, params: Optional[BreakingParams] = None):
        self.params = params or BreakingParams()

    def simulate(self, image: np.ndarray, wave_amplitudes: List[float],
                 wave_wavelengths: List[float], wave_directions: List[float],
                 wave_centers: List[Tuple[int, int]],
                 wind_speed: float, ts_profile: Optional[Any] = None,
                 pixel_resolution: Tuple[float, float] = (10.0, 10.0)
                 ) -> BreakingSimulationResult:
        """
        Simulate wave breaking and surface roughness.

        Args:
            image: SAR image (2D array)
            wave_amplitudes: List of wave amplitudes (m)
            wave_wavelengths: List of wavelengths (m)
            wave_directions: List of wave directions (deg)
            wave_centers: List of wave center coordinates
            wind_speed: Surface wind speed (m/s)
            ts_profile: Optional T-S profile for stratification
            pixel_resolution: Pixel resolution in meters

        Returns:
            BreakingSimulationResult
        """
        import time
        start_time = time.time()

        logger.info("Starting wave breaking and roughness simulation...")

        result = BreakingSimulationResult()

        H, W = image.shape
        px_res = max(pixel_resolution[0], pixel_resolution[1])

        if ts_profile is not None:
            h1 = self._estimate_upper_layer_depth(ts_profile)
            N = np.max(ts_profile.buoyancy_frequency)
        else:
            h1 = 50.0
            N = 0.01

        logger.info(f"  Upper layer depth: {h1:.1f}m, N={N:.4f} rad/s")

        surface_slope = self._compute_surface_slope(image)
        vorticity = self._compute_surface_vorticity(image)

        breaking_prob = self._compute_breaking_probability(
            image, surface_slope, vorticity, wave_amplitudes, wave_wavelengths,
            wave_directions, wave_centers, h1, N, px_res
        )

        breaking_regions = self._identify_breaking_regions(
            breaking_prob, wave_amplitudes, wave_wavelengths, wave_directions,
            wave_centers, h1, N, px_res, wind_speed
        )
        result.breaking_regions = breaking_regions

        result.total_breaking_area = float(np.sum([r.area for r in breaking_regions]))
        result.total_energy_dissipation = float(np.sum([r.energy_dissipation for r in breaking_regions]))
        if breaking_regions:
            result.mean_breaking_probability = float(np.mean([r.probability for r in breaking_regions]))

        result.breaking_type_distribution = self._count_breaking_types(breaking_regions)

        roughness_map = self._compute_roughness_map(
            image, surface_slope, vorticity, breaking_prob, breaking_regions,
            wind_speed, wave_directions, wave_centers, px_res
        )
        result.roughness_map = roughness_map

        result.simulation_time = time.time() - start_time

        logger.info(f"Simulation complete: {len(breaking_regions)} breaking regions, "
                   f"total dissipation={result.total_energy_dissipation:.3e} W")
        for btype, count in result.breaking_type_distribution.items():
            logger.info(f"  {btype}: {count} regions")

        return result

    def _estimate_upper_layer_depth(self, ts_profile) -> float:
        """Estimate upper layer depth from T-S profile."""
        if hasattr(ts_profile, 'depth') and len(ts_profile.depth) > 0:
            return float(min(ts_profile.depth[-1], 50.0))
        return 50.0

    def _compute_surface_slope(self, image: np.ndarray) -> np.ndarray:
        """
        Compute sea surface slope from SAR image.

        Uses Sobel operators to compute spatial gradients.
        """
        dx = ndimage.sobel(image, axis=1)
        dy = ndimage.sobel(image, axis=0)
        slope = np.sqrt(dx**2 + dy**2)
        return slope

    def _compute_surface_vorticity(self, image: np.ndarray) -> np.ndarray:
        """
        Compute surface vorticity from SAR image.

        Vorticity is estimated from the curl of the image intensity gradients,
        which relates to surface current shear.
        """
        dx = ndimage.sobel(image, axis=1)
        dy = ndimage.sobel(image, axis=0)

        d2x_dy = ndimage.sobel(dx, axis=0)
        d2y_dx = ndimage.sobel(dy, axis=1)

        vorticity = d2y_dx - d2x_dy
        return vorticity

    def _compute_breaking_probability(self, image: np.ndarray,
                                       surface_slope: np.ndarray,
                                       vorticity: np.ndarray,
                                       wave_amplitudes: List[float],
                                       wave_wavelengths: List[float],
                                       wave_directions: List[float],
                                       wave_centers: List[Tuple[int, int]],
                                       h1: float, N: float,
                                       px_res: float) -> np.ndarray:
        """
        Compute wave breaking probability map.

        Combines three instability criteria:
        1. Richardson number (shear instability)
        2. Amplitude/depth ratio (convective instability)
        3. Wave steepness (surface breaking)

        Returns:
            Breaking probability map [0, 1]
        """
        H, W = image.shape

        prob_ri = np.zeros((H, W))
        prob_ad = np.zeros((H, W))
        prob_steep = np.zeros((H, W))

        for i in range(len(wave_amplitudes)):
            A = wave_amplitudes[i]
            λ = wave_wavelengths[i]
            dir_deg = wave_directions[i]
            center = wave_centers[i]

            mask = self._get_wave_region_mask(center, λ, dir_deg, (H, W), px_res)

            Ri = self._compute_richardson_number(A, λ, h1, N)
            ad_ratio = A / max(h1, 1.0)
            steepness = A / max(λ, 1.0) * 2 * np.pi

            p_ri = self._ri_to_probability(Ri)
            p_ad = self._amp_depth_to_probability(ad_ratio)
            p_steep = self._steepness_to_probability(steepness)

            prob_ri[mask] = np.maximum(prob_ri[mask], p_ri)
            prob_ad[mask] = np.maximum(prob_ad[mask], p_ad)
            prob_steep[mask] = np.maximum(prob_steep[mask], p_steep)

        slope_norm = (surface_slope - np.min(surface_slope)) / (np.max(surface_slope) - np.min(surface_slope) + 1e-8)
        prob_slope = 0.3 * slope_norm

        vorticity_norm = np.abs(vorticity)
        vorticity_norm = (vorticity_norm - np.min(vorticity_norm)) / (np.max(vorticity_norm) - np.min(vorticity_norm) + 1e-8)
        prob_vort = 0.2 * vorticity_norm

        combined_prob = np.maximum.reduce([prob_ri, prob_ad, prob_steep, prob_slope, prob_vort])
        combined_prob = np.clip(combined_prob, self.params.min_breaking_probability,
                                self.params.max_breaking_probability)

        combined_prob = ndimage.gaussian_filter(combined_prob, sigma=2.0)

        return combined_prob

    def _get_wave_region_mask(self, center: Tuple[int, int], wavelength: float,
                               direction: float, shape: Tuple[int, int],
                               px_res: float) -> np.ndarray:
        """Generate mask for a wave region."""
        H, W = shape
        y, x = np.ogrid[:H, :W]

        cy, cx = center

        dir_rad = np.deg2rad(direction)
        perp_rad = dir_rad + np.pi / 2

        dx = x - cx
        dy = y - cy

        dist_along = dx * np.cos(perp_rad) + dy * np.sin(perp_rad)
        dist_perp = dx * np.cos(dir_rad) + dy * np.sin(dir_rad)

        half_width_pixels = wavelength / px_res * 2

        mask = (np.abs(dist_along) < half_width_pixels) & (np.abs(dist_perp) < half_width_pixels * 2)

        return mask

    def _compute_richardson_number(self, A: float, λ: float, h1: float, N: float) -> float:
        """
        Compute gradient Richardson number.

        Ri = N² / (du/dz)²

        For internal waves, the velocity shear is estimated as:
            du/dz ~ Aω / h1 = A * (2πc/λ) / h1

        Args:
            A: Wave amplitude
            λ: Wavelength
            h1: Upper layer depth
            N: Buoyancy frequency

        Returns:
            Richardson number
        """
        if h1 <= 0 or λ <= 0 or N <= 0:
            return 1.0

        c = N * h1 / np.pi

        omega = 2 * np.pi * c / max(λ, 1.0)

        du_dz = A * omega / max(h1, 1.0)

        if abs(du_dz) < 1e-10:
            return 10.0

        Ri = N**2 / max(du_dz**2, 1e-20)

        return float(Ri)

    def _ri_to_probability(self, Ri: float) -> float:
        """
        Convert Richardson number to breaking probability.

        Ri < 0.25: dynamically unstable (high breaking prob)
        Ri > 1.0: dynamically stable (low breaking prob)
        """
        Ri_crit = self.params.breaking_threshold_richardson

        if Ri <= Ri_crit:
            prob = 0.9
        elif Ri >= 1.0:
            prob = 0.05
        else:
            prob = 0.9 - 0.85 * (Ri - Ri_crit) / max(1.0 - Ri_crit, 1e-6)

        return float(np.clip(prob, self.params.min_breaking_probability,
                            self.params.max_breaking_probability))

    def _amp_depth_to_probability(self, ad_ratio: float) -> float:
        """
        Convert amplitude/depth ratio to breaking probability.

        A/h1 > 0.3: Convective instability likely
        """
        crit = self.params.breaking_threshold_amp_depth

        if ad_ratio >= crit:
            prob = 0.85
        elif ad_ratio <= 0.1:
            prob = 0.05
        else:
            prob = 0.05 + 0.8 * (ad_ratio - 0.1) / max(crit - 0.1, 1e-6)

        return float(np.clip(prob, self.params.min_breaking_probability,
                            self.params.max_breaking_probability))

    def _steepness_to_probability(self, steepness: float) -> float:
        """
        Convert wave steepness (kA) to breaking probability.

        kA > 0.1: Likely to break
        """
        crit = self.params.breaking_threshold_steepness

        if steepness >= crit:
            prob = 0.8
        elif steepness <= 0.01:
            prob = 0.05
        else:
            prob = 0.05 + 0.75 * (steepness - 0.01) / max(crit - 0.01, 1e-6)

        return float(np.clip(prob, self.params.min_breaking_probability,
                            self.params.max_breaking_probability))

    def _identify_breaking_regions(self, breaking_prob: np.ndarray,
                                    wave_amplitudes: List[float],
                                    wave_wavelengths: List[float],
                                    wave_directions: List[float],
                                    wave_centers: List[Tuple[int, int]],
                                    h1: float, N: float, px_res: float,
                                    wind_speed: float) -> List[BreakingRegion]:
        """
        Identify and characterize individual breaking regions.

        Args:
            breaking_prob: Breaking probability map
            wave_amplitudes: Wave amplitudes
            wave_wavelengths: Wave wavelengths
            wave_directions: Wave directions
            wave_centers: Wave center coordinates
            h1: Upper layer depth
            N: Buoyancy frequency
            px_res: Pixel resolution
            wind_speed: Wind speed

        Returns:
            List of BreakingRegion objects
        """
        threshold = 0.5
        binary_mask = breaking_prob > threshold

        labeled, num_regions = ndimage.label(binary_mask)

        regions = []
        region_id = 0

        for reg_id in range(1, num_regions + 1):
            region_mask = labeled == reg_id
            area_pixels = np.sum(region_mask)

            if area_pixels < 25:
                continue

            area_m2 = area_pixels * px_res**2

            rows, cols = np.where(region_mask)
            center_row = int(np.mean(rows))
            center_col = int(np.mean(cols))
            min_row, max_row = np.min(rows), np.max(rows)
            min_col, max_col = np.min(cols), np.max(cols)

            prob_region = breaking_prob[region_mask]
            mean_prob = float(np.mean(prob_region))
            max_prob = float(np.max(prob_region))

            wave_idx = self._find_nearest_wave((center_row, center_col), wave_centers)

            if wave_idx >= 0 and wave_idx < len(wave_amplitudes):
                A = wave_amplitudes[wave_idx]
                λ = wave_wavelengths[wave_idx]
                dir_deg = wave_directions[wave_idx]

                Ri = self._compute_richardson_number(A, λ, h1, N)
                ad_ratio = A / max(h1, 1.0)
                steepness = A / max(λ, 1.0) * 2 * np.pi
            else:
                A = 10.0
                λ = 100.0
                dir_deg = 0.0
                Ri = 0.5
                ad_ratio = 0.2
                steepness = 0.05

            breaking_type = self._classify_breaking_type(Ri, ad_ratio, steepness)

            epsilon = self._compute_energy_dissipation(A, λ, N, h1, mean_prob)
            turb_intensity = self._compute_turbulence_intensity(epsilon, h1)
            roughness = self._compute_local_roughness(wind_speed, A, mean_prob)
            backscatter = self._compute_radar_backscatter(roughness, wind_speed)

            region = BreakingRegion(
                region_id=region_id,
                center_row=center_row,
                center_col=center_col,
                area=float(area_m2),
                probability=float(max(mean_prob, max_prob)),
                breaking_type=breaking_type,
                richardson_number=float(Ri),
                amplitude_depth_ratio=float(ad_ratio),
                wave_steepness=float(steepness),
                energy_dissipation=float(epsilon),
                turbulence_intensity=float(turb_intensity),
                surface_roughness=float(roughness),
                radar_backscatter=float(backscatter),
                bbox=(min_row, min_col, max_row, max_col),
                mask=region_mask.astype(np.uint8),
                metadata={
                    'wave_index': wave_idx,
                    'mean_probability': float(mean_prob),
                    'max_probability': float(max_prob),
                    'area_pixels': int(area_pixels),
                    'wave_direction': float(dir_deg)
                }
            )
            regions.append(region)
            region_id += 1

        return regions

    def _find_nearest_wave(self, point: Tuple[int, int],
                            wave_centers: List[Tuple[int, int]]) -> int:
        """Find the nearest wave to a point."""
        if not wave_centers:
            return -1

        distances = []
        for center in wave_centers:
            dist = np.sqrt((point[0] - center[0])**2 + (point[1] - center[1])**2)
            distances.append(dist)

        return int(np.argmin(distances))

    def _classify_breaking_type(self, Ri: float, ad_ratio: float,
                                 steepness: float) -> str:
        """
        Classify breaking type based on instability criteria.

        Types:
        - 'shear': Shear instability (low Ri)
        - 'convective': Convective instability (high A/h1)
        - 'surface': Surface wave breaking (high steepness)
        - 'mixed': Combination of multiple mechanisms
        """
        types = []

        if Ri < self.params.breaking_threshold_richardson:
            types.append('shear')
        if ad_ratio > self.params.breaking_threshold_amp_depth:
            types.append('convective')
        if steepness > self.params.breaking_threshold_steepness:
            types.append('surface')

        if len(types) == 0:
            return 'weak'
        elif len(types) == 1:
            return types[0]
        else:
            return 'mixed_' + '_'.join(sorted(types))

    def _compute_energy_dissipation(self, A: float, λ: float, N: float,
                                     h1: float, prob: float) -> float:
        """
        Compute turbulent energy dissipation rate in breaking region.

        Based on:
            ε ~ ρ0 * N² * A³ / T

        where T is the wave period, and scaled by breaking probability.

        Args:
            A: Wave amplitude
            λ: Wavelength
            N: Buoyancy frequency
            h1: Upper layer depth
            prob: Breaking probability

        Returns:
            Energy dissipation rate (W)
        """
        rho0 = 1027.0

        if λ <= 0 or N <= 0:
            return 0.0

        c = N * h1 / np.pi
        T = λ / max(c, 1e-6)

        epsilon_per_unit = rho0 * N**2 * A**3 / max(T, 1e-6)

        epsilon = epsilon_per_unit * prob * 1000.0

        return float(max(0, epsilon))

    def _compute_turbulence_intensity(self, epsilon: float, h1: float) -> float:
        """
        Compute turbulence intensity from energy dissipation.

        For isotropic turbulence:
            q ~ (ε * L)^(1/3)

        where L is the integral length scale (~h1/10).

        Returns:
            Turbulence intensity (m/s)
        """
        L = h1 / 10.0
        q = (epsilon * L / 1027.0)**(1.0 / 3.0)
        return float(q)

    def _compute_local_roughness(self, wind_speed: float, A: float, prob: float) -> float:
        """
        Compute local sea surface roughness length.

        Uses Charnock relation modified for internal wave effects:
            z0 = α * u_*² / g + z0_wave * P_break

        where the wave-induced roughness depends on wave amplitude
        and breaking probability.

        Args:
            wind_speed: Wind speed (m/s)
            A: Wave amplitude (m)
            prob: Breaking probability

        Returns:
            Roughness length (m)
        """
        Cd = self.params.wind_drag_coefficient
        u_star = np.sqrt(Cd) * wind_speed

        z0_charnock = self.params.charnock_constant * u_star**2 / self.params.gravity

        z0_wave = A * 0.01 * prob

        z0 = z0_charnock + z0_wave

        return float(max(z0, 1e-6))

    def _compute_radar_backscatter(self, roughness: float, wind_speed: float) -> float:
        """
        Compute normalized radar cross section (NRCS).

        Uses a simplified Geometrical Optics model:
            σ0 ~ (cos^4(θ) / λ_radar^4) * z0^2 * wind_factor

        Args:
            roughness: Surface roughness length (m)
            wind_speed: Wind speed (m/s)

        Returns:
            NRCS in linear units (not dB)
        """
        theta_rad = np.deg2rad(self.params.incidence_angle)
        c = 3e8
        lambda_radar = c / self.params.radar_frequency

        wind_factor = 1.0 + 0.1 * wind_speed

        sigma0 = (np.cos(theta_rad)**4 / lambda_radar**4) * roughness**2 * wind_factor

        return float(sigma0)

    def _count_breaking_types(self, regions: List[BreakingRegion]) -> Dict[str, int]:
        """Count breaking region types."""
        counts: Dict[str, int] = {}
        for r in regions:
            counts[r.breaking_type] = counts.get(r.breaking_type, 0) + 1
        return counts

    def _compute_roughness_map(self, image: np.ndarray,
                                surface_slope: np.ndarray,
                                vorticity: np.ndarray,
                                breaking_prob: np.ndarray,
                                breaking_regions: List[BreakingRegion],
                                wind_speed: float,
                                wave_directions: List[float],
                                wave_centers: List[Tuple[int, int]],
                                px_res: float) -> RoughnessMap:
        """
        Compute full sea surface roughness map.

        Args:
            image: SAR image
            surface_slope: Surface slope
            vorticity: Surface vorticity
            breaking_prob: Breaking probability
            breaking_regions: List of breaking regions
            wind_speed: Wind speed
            wave_directions: Wave directions
            wave_centers: Wave centers
            px_res: Pixel resolution

        Returns:
            RoughnessMap object
        """
        H, W = image.shape

        Cd = self.params.wind_drag_coefficient
        u_star = np.sqrt(Cd) * wind_speed
        z0_base = self.params.charnock_constant * u_star**2 / self.params.gravity

        slope_norm = (surface_slope - np.min(surface_slope)) / (np.max(surface_slope) - np.min(surface_slope) + 1e-8)
        vorticity_norm = np.abs(vorticity)
        vorticity_norm = (vorticity_norm - np.min(vorticity_norm)) / (np.max(vorticity_norm) - np.min(vorticity_norm) + 1e-8)

        roughness = z0_base * (1.0 + 2.0 * slope_norm + 1.5 * vorticity_norm + 5.0 * breaking_prob)

        for region in breaking_regions:
            if region.mask is not None:
                roughness[region.mask > 0] = region.surface_roughness

        roughness = ndimage.gaussian_filter(roughness, sigma=1.0)

        backscatter = np.zeros_like(roughness)
        theta_rad = np.deg2rad(self.params.incidence_angle)
        c = 3e8
        lambda_radar = c / self.params.radar_frequency

        for i in range(H):
            for j in range(W):
                wind_factor = 1.0 + 0.1 * wind_speed
                backscatter[i, j] = (np.cos(theta_rad)**4 / lambda_radar**4) * roughness[i, j]**2 * wind_factor

        epsilon_map = np.zeros_like(roughness)
        tke_map = np.zeros_like(roughness)

        for region in breaking_regions:
            if region.mask is not None:
                epsilon_map[region.mask > 0] = region.energy_dissipation
                tke_map[region.mask > 0] = 0.5 * (region.turbulence_intensity)**2

        u_map, v_map = self._compute_surface_current_perturbation(
            image, wave_directions, wave_centers, px_res
        )

        breaking_mask = np.zeros_like(roughness, dtype=bool)
        for region in breaking_regions:
            if region.mask is not None:
                breaking_mask = breaking_mask | (region.mask > 0)

        return RoughnessMap(
            roughness=roughness,
            backscatter=backscatter,
            turbulent_kinetic_energy=tke_map,
            dissipation_rate=epsilon_map,
            vorticity=vorticity,
            surface_current_u=u_map,
            surface_current_v=v_map,
            breaking_mask=breaking_mask,
            metadata={
                'base_roughness': float(z0_base),
                'wind_speed': float(wind_speed),
                'px_resolution': float(px_res)
            }
        )

    def _compute_surface_current_perturbation(self, image: np.ndarray,
                                               wave_directions: List[float],
                                               wave_centers: List[Tuple[int, int]],
                                               px_res: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute wave-induced surface current perturbation.

        For an internal wave propagating in direction θ:
            u' = (Aω/kH1) * sin(kx - ωt) * cos(θ)
            v' = (Aω/kH1) * sin(kx - ωt) * sin(θ)

        Args:
            image: SAR image
            wave_directions: Wave directions
            wave_centers: Wave centers
            px_res: Pixel resolution

        Returns:
            Tuple of (u, v) current perturbation maps
        """
        H, W = image.shape
        u_map = np.zeros((H, W))
        v_map = np.zeros((H, W))

        for i, (cy, cx) in enumerate(wave_centers):
            dir_rad = np.deg2rad(wave_directions[i])

            y, x = np.ogrid[:H, :W]
            dx = (x - cx) * px_res
            dy = (y - cy) * px_res

            phase = dx * np.cos(dir_rad) + dy * np.sin(dir_rad)

            k = 2 * np.pi / 100.0
            omega = 0.1

            u_amp = 0.1
            perturbation = u_amp * np.sin(k * phase - omega * 0)

            u_map += perturbation * np.cos(dir_rad)
            v_map += perturbation * np.sin(dir_rad)

        u_map = ndimage.gaussian_filter(u_map, sigma=2.0)
        v_map = ndimage.gaussian_filter(v_map, sigma=2.0)

        return u_map, v_map

    def print_simulation_summary(self, result: BreakingSimulationResult) -> None:
        """Print summary of breaking simulation results."""
        print("\n=== Wave Breaking & Roughness Simulation Summary ===")
        print(f"Simulation time: {result.simulation_time:.3f}s")
        print(f"Breaking regions detected: {len(result.breaking_regions)}")
        print(f"Total breaking area: {result.total_breaking_area:.1f} m2")
        print(f"Total energy dissipation: {result.total_energy_dissipation:.3e} W")
        print(f"Mean breaking probability: {result.mean_breaking_probability:.3f}")

        print(f"\nBreaking type distribution:")
        for btype, count in sorted(result.breaking_type_distribution.items()):
            print(f"  {btype}: {count}")

        if result.roughness_map is not None:
            rmap = result.roughness_map
            print(f"\nSurface roughness statistics:")
            print(f"  Mean z0: {np.mean(rmap.roughness):.6f} m")
            print(f"  Max z0: {np.max(rmap.roughness):.6f} m")
            print(f"  Min z0: {np.min(rmap.roughness):.6f} m")
            if rmap.dissipation_rate is not None and np.max(rmap.dissipation_rate) > 0:
                print(f"  Max dissipation: {np.max(rmap.dissipation_rate):.3e} W/m³")

        if result.breaking_regions:
            print(f"\nTop 5 breaking regions (by dissipation):")
            print("-" * 95)
            print(f"{'ID':<4} {'Type':<20} {'Area(m2)':<10} {'Prob':<6} {'Ri':<6} "
                  f"{'A/h1':<6} {'kA':<6} {'Diss(W)':<12} {'z0(m)':<10} {'NRCS(dB)':<12}")
            print("-" * 95)

            top_regions = sorted(result.breaking_regions,
                                key=lambda r: r.energy_dissipation, reverse=True)[:5]
            for r in top_regions:
                sigma0_db = 10 * np.log10(max(r.radar_backscatter, 1e-20))
                print(f"{r.region_id:<4} {r.breaking_type:<20} {r.area:<10.1f} "
                      f"{r.probability:<6.2f} {r.richardson_number:<6.2f} "
                      f"{r.amplitude_depth_ratio:<6.2f} {r.wave_steepness:<6.3f} "
                      f"{r.energy_dissipation:<12.3e} {r.surface_roughness:<10.6f} "
                      f"{sigma0_db:<12.2f}")
            print("-" * 95)

    def visualize_simulation(self, result: BreakingSimulationResult,
                              original_image: np.ndarray,
                              save_path: Optional[str] = None) -> Any:
        """
        Create visualization of breaking simulation results.

        Args:
            result: Breaking simulation result
            original_image: Original SAR image
            save_path: Optional path to save figure

        Returns:
            Matplotlib figure object
        """
        import matplotlib.pyplot as plt
        import cv2

        if result.roughness_map is None:
            return None

        if len(original_image.shape) == 2:
            display_image = cv2.cvtColor((original_image * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        else:
            display_image = (original_image * 255).astype(np.uint8).copy()

        for region in result.breaking_regions:
            color = self._get_breaking_color(region.breaking_type)
            min_r, min_c, max_r, max_c = region.bbox
            cv2.rectangle(display_image, (min_c, min_r), (max_c, max_r), color, 2)

            label = f"{region.region_id}: {region.breaking_type[:8]}"
            cv2.putText(display_image, label, (min_c, max(0, min_r - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        fig, axes = plt.subplots(2, 3, figsize=(18, 12))

        rmap = result.roughness_map

        axes[0, 0].imshow(display_image[:, :, ::-1])
        axes[0, 0].set_title('SAR Image with Breaking Regions')
        axes[0, 0].axis('off')

        im1 = axes[0, 1].imshow(rmap.roughness, cmap='viridis')
        axes[0, 1].set_title('Surface Roughness z0 (m)')
        axes[0, 1].axis('off')
        plt.colorbar(im1, ax=axes[0, 1], fraction=0.046, pad=0.04)

        if rmap.dissipation_rate is not None:
            im2 = axes[0, 2].imshow(rmap.dissipation_rate, cmap='hot')
            axes[0, 2].set_title('Energy Dissipation ε (W/m³)')
            axes[0, 2].axis('off')
            plt.colorbar(im2, ax=axes[0, 2], fraction=0.046, pad=0.04)

        if rmap.backscatter is not None:
            sigma0_db = 10 * np.log10(np.maximum(rmap.backscatter, 1e-20))
            im3 = axes[1, 0].imshow(sigma0_db, cmap='jet')
            axes[1, 0].set_title('NRCS (dB)')
            axes[1, 0].axis('off')
            plt.colorbar(im3, ax=axes[1, 0], fraction=0.046, pad=0.04)

        if rmap.turbulent_kinetic_energy is not None:
            im4 = axes[1, 1].imshow(rmap.turbulent_kinetic_energy, cmap='plasma')
            axes[1, 1].set_title('Turbulent Kinetic Energy (m²/s²)')
            axes[1, 1].axis('off')
            plt.colorbar(im4, ax=axes[1, 1], fraction=0.046, pad=0.04)

        if rmap.surface_current_u is not None and rmap.surface_current_v is not None:
            H, W = rmap.roughness.shape
            Y, X = np.mgrid[0:H:10, 0:W:10]
            U = rmap.surface_current_u[::10, ::10]
            V = rmap.surface_current_v[::10, ::10]
            axes[1, 2].imshow(original_image, cmap='gray', alpha=0.5)
            axes[1, 2].quiver(X, Y, U, V, color='cyan', scale=2.0)
            axes[1, 2].set_title('Wave-induced Surface Current')
            axes[1, 2].axis('off')

        plt.suptitle('Internal Wave Breaking & Sea Surface Roughness Simulation', fontsize=14)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Saved breaking simulation plot: {save_path}")

        return fig

    def _get_breaking_color(self, breaking_type: str) -> Tuple[int, int, int]:
        """Get BGR color for breaking type."""
        if 'shear' in breaking_type:
            return (0, 0, 255)
        elif 'convective' in breaking_type:
            return (0, 165, 255)
        elif 'surface' in breaking_type:
            return (255, 0, 255)
        elif 'mixed' in breaking_type:
            return (255, 0, 0)
        else:
            return (0, 255, 0)
