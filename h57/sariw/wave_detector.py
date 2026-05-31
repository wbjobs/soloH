import numpy as np
import cv2
from skimage.transform import radon
from scipy import ndimage, signal
from scipy.signal import find_peaks
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class WaveDetectionParams:
    """Parameters for internal wave detection."""
    radon_angles: np.ndarray = field(default_factory=lambda: np.linspace(0, 180, 360, endpoint=False))
    radon_threshold: float = 0.5
    min_wavelength: float = 10.0
    max_wavelength: float = 500.0
    gabor_sigma: float = 3.0
    gabor_frequencies: List[float] = field(default_factory=lambda: [0.05, 0.1, 0.15, 0.2])
    direction_search_range: float = 30.0
    peak_prominence: float = 0.1
    min_wave_length_pixels: int = 50
    enable_wavepacket_separation: bool = True
    wavepacket_separation_threshold: float = 0.3
    max_waves_per_packet: int = 5
    interference_correction: bool = True
    low_wind_mode: bool = False
    low_wind_enhancement: float = 2.0


@dataclass
class DetectedWave:
    """Data class for a detected internal wave."""
    wave_id: int
    center_row: int
    center_col: int
    direction: float
    wavelength: float
    spacing: float
    contrast: float
    confidence: float
    bright_stripes: List[Tuple[int, int]] = field(default_factory=list)
    dark_stripes: List[Tuple[int, int]] = field(default_factory=list)
    envelope: Optional[np.ndarray] = None
    packet_id: int = -1
    wave_index_in_packet: int = 0
    total_waves_in_packet: int = 1
    interference_factor: float = 1.0
    raw_contrast: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def center_geo(self, geotiff_data) -> Tuple[float, float]:
        """Get center geographic coordinates."""
        return geotiff_data.pixel_to_wgs84(self.center_row, self.center_col)


@dataclass
class WaveDetectionResult:
    """Result of wave detection."""
    waves: List[DetectedWave] = field(default_factory=list)
    radon_image: Optional[np.ndarray] = None
    radon_angles: Optional[np.ndarray] = None
    dominant_direction: float = 0.0
    dominant_spacing: float = 0.0
    direction_confidence: float = 0.0
    preprocessed_image: Optional[np.ndarray] = None
    energy_map: Optional[np.ndarray] = None


class WaveDetector:
    """Detector for internal wave features in SAR images."""

    def __init__(self, params: Optional[WaveDetectionParams] = None):
        """
        Initialize wave detector.

        Args:
            params: Detection parameters
        """
        self.params = params or WaveDetectionParams()

    def detect(self, preprocessed_image: np.ndarray,
               pixel_resolution: Tuple[float, float] = (1.0, 1.0)) -> WaveDetectionResult:
        """
        Detect internal waves in the preprocessed image.

        Args:
            preprocessed_image: Preprocessed SAR image
            pixel_resolution: Pixel resolution in meters (x, y)

        Returns:
            WaveDetectionResult containing detected waves
        """
        logger.info("Starting internal wave detection...")

        result = WaveDetectionResult()
        result.preprocessed_image = preprocessed_image

        working_image = preprocessed_image.copy()

        if self.params.low_wind_mode:
            logger.info("  Applying low-wind signal enhancement...")
            energy_map_pre, _ = self._compute_directional_energy(working_image)
            working_image = self._low_wind_enhancement(working_image, energy_map_pre)

        logger.info("  Computing directional energy map using Gabor filters...")
        energy_map, direction_map = self._compute_directional_energy(working_image)
        result.energy_map = energy_map

        logger.info("  Performing Radon transform for direction and spacing estimation...")
        radon_image, angles = self._radon_transform(preprocessed_image)
        result.radon_image = radon_image
        result.radon_angles = angles

        dominant_dir, spacing, conf = self._estimate_dominant_parameters(radon_image, angles, pixel_resolution)
        result.dominant_direction = dominant_dir
        result.dominant_spacing = spacing
        result.direction_confidence = conf

        logger.info(f"  Dominant direction: {dominant_dir:.1f}°, spacing: {spacing:.1f}m, confidence: {conf:.3f}")

        logger.info("  Detecting individual wave packets...")
        waves = self._detect_wave_packets(working_image, energy_map, direction_map,
                                          dominant_dir, spacing, pixel_resolution)

        if self.params.enable_wavepacket_separation:
            logger.info("  Separating waves within packets and correcting interference...")
            waves = self._separate_waves_in_packet(
                working_image, waves, dominant_dir, spacing, pixel_resolution
            )

        result.waves = waves

        total_individual_waves = sum(w.total_waves_in_packet for w in waves)
        logger.info(f"Detection completed. Found {len(waves)} packets containing {total_individual_waves} individual waves.")
        return result

    def _compute_directional_energy(self, image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute directional energy using Gabor filters.

        Args:
            image: Input image

        Returns:
            Tuple of (energy_map, direction_map)
        """
        img_8bit = (image * 255).astype(np.uint8)

        directions = np.linspace(0, np.pi, 16, endpoint=False)
        energies = np.zeros((len(directions),) + image.shape, dtype=np.float32)

        for i, theta in enumerate(directions):
            for freq in self.params.gabor_frequencies:
                kernel = cv2.getGaborKernel(
                    ksize=(31, 31),
                    sigma=self.params.gabor_sigma,
                    theta=theta,
                    lambd=1.0 / freq,
                    gamma=0.5,
                    psi=0
                )
                filtered = cv2.filter2D(img_8bit, cv2.CV_32F, kernel)
                energies[i] += np.abs(filtered)

        energy_map = np.max(energies, axis=0)
        direction_map = directions[np.argmax(energies, axis=0)]

        energy_map = (energy_map - np.min(energy_map)) / (np.max(energy_map) - np.min(energy_map) + 1e-8)

        return energy_map, direction_map

    def _radon_transform(self, image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Perform Radon transform to detect linear features.

        Args:
            image: Input image

        Returns:
            Tuple of (radon_image, angles)
        """
        img_8bit = (image * 255).astype(np.uint8)
        edges = cv2.Canny(img_8bit, 30, 100)

        edges_float = edges.astype(np.float32) / 255.0

        theta = self.params.radon_angles
        sinogram = radon(edges_float, theta=theta, circle=False)

        sinogram = (sinogram - np.min(sinogram)) / (np.max(sinogram) - np.min(sinogram) + 1e-8)

        return sinogram, theta

    def _estimate_dominant_parameters(self, radon_image: np.ndarray, angles: np.ndarray,
                                      pixel_resolution: Tuple[float, float]) -> Tuple[float, float, float]:
        """
        Estimate dominant wave direction and spacing from Radon transform.

        Args:
            radon_image: Radon transform result (sinogram)
            angles: Angles used in Radon transform
            pixel_resolution: Pixel resolution in meters

        Returns:
            Tuple of (dominant_direction_deg, spacing_meters, confidence)
        """
        angle_profile = np.max(radon_image, axis=0)

        angle_peaks, angle_props = find_peaks(
            angle_profile,
            prominence=self.params.peak_prominence * np.max(angle_profile),
            distance=10
        )

        if len(angle_peaks) == 0:
            smooth_profile = ndimage.gaussian_filter1d(angle_profile, sigma=3)
            angle_peaks, angle_props = find_peaks(
                smooth_profile,
                prominence=0.05 * np.max(smooth_profile),
                distance=10
            )

        if len(angle_peaks) == 0:
            return 0.0, 50.0, 0.1

        best_peak_idx = angle_peaks[np.argmax(angle_props['prominences'])]
        dominant_angle = angles[best_peak_idx]

        shift_profile = radon_image[:, best_peak_idx]
        shift_peaks, shift_props = find_peaks(
            shift_profile,
            prominence=0.2 * np.max(shift_profile),
            distance=5
        )

        if len(shift_peaks) >= 2:
            peak_shifts = np.sort(shift_peaks)
            spacings = np.diff(peak_shifts)
            spacing_pixels = np.median(spacings)

            res = np.sqrt(pixel_resolution[0]**2 + pixel_resolution[1]**2) / np.sqrt(2)
            spacing_meters = spacing_pixels * res

            if spacing_meters < 5.0 or np.isnan(spacing_meters):
                spacing_meters = 50.0
        else:
            spacing_meters = 50.0

        confidence = angle_props['prominences'][np.argmax(angle_props['prominences'])] / np.max(angle_profile)
        confidence = min(confidence, 1.0)

        propagation_direction = (dominant_angle + 90) % 180

        return propagation_direction, spacing_meters, confidence

    def _detect_wave_packets(self, image: np.ndarray, energy_map: np.ndarray,
                             direction_map: np.ndarray, dominant_direction: float,
                             dominant_spacing: float,
                             pixel_resolution: Tuple[float, float]) -> List[DetectedWave]:
        """
        Detect individual wave packets.

        Args:
            image: Preprocessed image
            energy_map: Directional energy map
            direction_map: Direction map
            dominant_direction: Estimated dominant direction (degrees)
            dominant_spacing: Estimated dominant spacing (meters)
            pixel_resolution: Pixel resolution in meters

        Returns:
            List of detected waves
        """
        waves = []

        if self.params.low_wind_mode:
            energy_threshold = np.median(energy_map) + np.std(energy_map) * 0.5
            min_pixels = max(10, self.params.min_wave_length_pixels // 3)
        else:
            energy_threshold = np.median(energy_map) + np.std(energy_map) * 2
            min_pixels = self.params.min_wave_length_pixels

        energy_mask = energy_map > energy_threshold

        dir_rad = np.deg2rad(dominant_direction)
        dir_tolerance = np.deg2rad(self.params.direction_search_range)
        direction_mask = np.abs(direction_map - dir_rad) < dir_tolerance

        combined_mask = energy_mask & direction_mask

        labeled, num_features = ndimage.label(combined_mask)

        wave_id = 0
        for i in range(1, num_features + 1):
            region_mask = labeled == i

            if np.sum(region_mask) < min_pixels:
                continue

            rows, cols = np.where(region_mask)
            center_row = int(np.mean(rows))
            center_col = int(np.mean(cols))

            local_image = image[region_mask]
            contrast = np.max(local_image) - np.min(local_image)

            if self.params.low_wind_mode:
                std_factor = 0.2
                min_stripe_pixels = 3
            else:
                std_factor = 0.5
                min_stripe_pixels = 10

            bright_mask = (image > np.mean(local_image) + np.std(local_image) * std_factor) & region_mask
            dark_mask = (image < np.mean(local_image) - np.std(local_image) * std_factor) & region_mask

            bright_pixels = list(zip(*np.where(bright_mask)))
            dark_pixels = list(zip(*np.where(dark_mask)))

            if len(bright_pixels) < min_stripe_pixels or len(dark_pixels) < min_stripe_pixels:
                continue

            if self.params.low_wind_mode:
                confidence = min(contrast * 3, 1.0) * (np.sum(region_mask) / (image.shape[0] * image.shape[1]) * 150)
            else:
                confidence = min(contrast * 2, 1.0) * (np.sum(region_mask) / (image.shape[0] * image.shape[1]) * 100)
            confidence = min(confidence, 1.0)

            wave = DetectedWave(
                wave_id=wave_id,
                center_row=center_row,
                center_col=center_col,
                direction=dominant_direction,
                wavelength=dominant_spacing,
                spacing=dominant_spacing,
                contrast=float(contrast),
                confidence=float(confidence),
                bright_stripes=bright_pixels[:100],
                dark_stripes=dark_pixels[:100],
                metadata={
                    'num_pixels': int(np.sum(region_mask)),
                    'local_contrast': float(contrast),
                    'direction_consistency': float(np.mean(np.abs(direction_map[region_mask] - dir_rad)))
                }
            )

            waves.append(wave)
            wave_id += 1

        waves.sort(key=lambda w: w.confidence, reverse=True)
        return waves

    def _separate_waves_in_packet(self, image: np.ndarray, waves: List[DetectedWave],
                                  dominant_direction: float, dominant_spacing: float,
                                  pixel_resolution: Tuple[float, float]) -> List[DetectedWave]:
        """
        Separate multiple waves within a wave packet and correct interference effects.

        For each detected wave packet, extract the profile perpendicular to the wave
        direction, identify individual wave crests/troughs, and estimate each wave's
        parameters while accounting for interference between adjacent waves.

        Args:
            image: Preprocessed image
            waves: List of detected wave packets
            dominant_direction: Dominant wave direction (degrees)
            dominant_spacing: Dominant wave spacing (meters)
            pixel_resolution: Pixel resolution in meters

        Returns:
            List of separated waves with interference-corrected parameters
        """
        if not self.params.enable_wavepacket_separation or not waves:
            return waves

        px_res = max(pixel_resolution[0], pixel_resolution[1])
        if px_res <= 0:
            px_res = 10.0

        dir_rad = np.deg2rad(dominant_direction)
        perp_rad = dir_rad + np.pi / 2

        separated_waves = []
        wave_id_counter = max(w.wave_id for w in waves) + 1 if waves else 0

        for packet_idx, packet in enumerate(waves):
            rows, cols = np.where(self._get_packet_mask(packet, image.shape))

            if len(rows) < 20:
                packet.packet_id = packet_idx
                packet.wave_index_in_packet = 0
                packet.total_waves_in_packet = 1
                separated_waves.append(packet)
                continue

            profile = self._extract_wave_profile(image, rows, cols, perp_rad, packet)

            if profile is None or len(profile) < 10:
                packet.packet_id = packet_idx
                packet.wave_index_in_packet = 0
                packet.total_waves_in_packet = 1
                separated_waves.append(packet)
                continue

            individual_waves = self._identify_individual_waves(
                profile, dominant_spacing, px_res, packet, packet_idx, wave_id_counter
            )

            if len(individual_waves) <= 1:
                packet.packet_id = packet_idx
                packet.wave_index_in_packet = 0
                packet.total_waves_in_packet = 1
                separated_waves.append(packet)
            else:
                wave_id_counter += len(individual_waves)
                if self.params.interference_correction:
                    individual_waves = self._correct_interference(
                        individual_waves, profile, dominant_spacing
                    )
                separated_waves.extend(individual_waves)

        return separated_waves

    def _get_packet_mask(self, packet: DetectedWave, shape: Tuple[int, int]) -> np.ndarray:
        """Get binary mask for a wave packet region."""
        mask = np.zeros(shape, dtype=bool)
        all_pixels = list(packet.bright_stripes) + list(packet.dark_stripes)
        for r, c in all_pixels:
            if 0 <= r < shape[0] and 0 <= c < shape[1]:
                mask[r, c] = True
        if np.sum(mask) > 0:
            mask = ndimage.binary_dilation(mask, iterations=3)
        return mask

    def _extract_wave_profile(self, image: np.ndarray, rows: np.ndarray, cols: np.ndarray,
                               perp_rad: float, packet: DetectedWave) -> Optional[np.ndarray]:
        """
        Extract 1D profile perpendicular to wave direction through the packet center.

        Args:
            image: Preprocessed image
            rows: Row coordinates of packet pixels
            cols: Column coordinates of packet pixels
            perp_rad: Perpendicular direction (radians)
            packet: Wave packet data

        Returns:
            1D intensity profile along the perpendicular direction
        """
        proj_coords = cols * np.cos(perp_rad) + rows * np.sin(perp_rad)

        min_proj = np.min(proj_coords)
        max_proj = np.max(proj_coords)
        if max_proj - min_proj < 5:
            return None

        n_bins = int(max_proj - min_proj) + 1
        if n_bins < 10:
            n_bins = 10

        profile = np.zeros(n_bins)
        count = np.zeros(n_bins)

        for i, coord in enumerate(proj_coords):
            bin_idx = int(coord - min_proj)
            bin_idx = np.clip(bin_idx, 0, n_bins - 1)
            r, c = int(rows[i]), int(cols[i])
            if 0 <= r < image.shape[0] and 0 <= c < image.shape[1]:
                profile[bin_idx] += image[r, c]
                count[bin_idx] += 1

        valid = count > 0
        profile[valid] /= count[valid]

        profile_smooth = ndimage.gaussian_filter1d(profile, sigma=1.5)

        return profile_smooth

    def _identify_individual_waves(self, profile: np.ndarray, dominant_spacing: float,
                                   px_res: float, packet: DetectedWave,
                                   packet_idx: int, start_wave_id: int) -> List[DetectedWave]:
        """
        Identify individual waves within a packet from the 1D profile.

        Uses peak detection on both the original and inverted profile to find
        bright crests and dark troughs.

        Args:
            profile: 1D intensity profile
            dominant_spacing: Expected wave spacing (meters)
            px_res: Pixel resolution (meters)
            packet: Original wave packet
            packet_idx: Packet identifier
            start_wave_id: Starting wave ID for new waves

        Returns:
            List of individual wave detections
        """
        min_distance_pixels = max(3, int(dominant_spacing / px_res / 2))

        peaks, peak_props = find_peaks(profile, distance=min_distance_pixels,
                                       prominence=self.params.wavepacket_separation_threshold)
        troughs, trough_props = find_peaks(-profile, distance=min_distance_pixels,
                                           prominence=self.params.wavepacket_separation_threshold)

        all_features = []
        for p in peaks:
            all_features.append((p, 'crest', profile[p]))
        for t in troughs:
            all_features.append((t, 'trough', profile[t]))

        all_features.sort(key=lambda x: x[0])

        if len(all_features) < 2:
            return []

        pairs = []
        for i in range(len(all_features) - 1):
            pos1, type1, val1 = all_features[i]
            pos2, type2, val2 = all_features[i + 1]

            if type1 != type2:
                contrast = abs(val1 - val2)
                if contrast > self.params.wavepacket_separation_threshold * 0.5:
                    center = (pos1 + pos2) // 2
                    pairs.append((center, pos1, pos2, contrast, type1))

        if len(pairs) > self.params.max_waves_per_packet:
            pairs.sort(key=lambda x: x[3], reverse=True)
            pairs = pairs[:self.params.max_waves_per_packet]
            pairs.sort(key=lambda x: x[0])

        individual_waves = []
        center_row = packet.center_row
        center_col = packet.center_col
        perp_rad = np.deg2rad(packet.direction) + np.pi / 2

        for i, (center_pos, pos1, pos2, contrast, _) in enumerate(pairs):
            offset = center_pos - len(profile) // 2

            wave_row = int(center_row + offset * np.sin(perp_rad))
            wave_col = int(center_col + offset * np.cos(perp_rad))

            wave_row = np.clip(wave_row, 0, 2000)
            wave_col = np.clip(wave_col, 0, 2000)

            spacing_m = dominant_spacing
            if i < len(pairs) - 1:
                spacing_pixels = pairs[i + 1][0] - center_pos
                spacing_m = spacing_pixels * px_res

            local_contrast = contrast
            raw_contrast = contrast

            interference_factor = self._estimate_interference_factor(len(pairs), i)
            if self.params.interference_correction:
                local_contrast = contrast / interference_factor

            confidence = min(packet.confidence * (contrast / np.max([p[3] for p in pairs])), 1.0)

            wave = DetectedWave(
                wave_id=start_wave_id + i,
                center_row=wave_row,
                center_col=wave_col,
                direction=packet.direction,
                wavelength=dominant_spacing,
                spacing=spacing_m,
                contrast=float(local_contrast),
                raw_contrast=float(raw_contrast),
                confidence=float(confidence),
                bright_stripes=packet.bright_stripes[:20],
                dark_stripes=packet.dark_stripes[:20],
                packet_id=packet_idx,
                wave_index_in_packet=i,
                total_waves_in_packet=len(pairs),
                interference_factor=float(interference_factor),
                metadata={
                    'num_pixels': packet.metadata.get('num_pixels', 0) // len(pairs),
                    'local_contrast': float(local_contrast),
                    'raw_contrast': float(raw_contrast),
                    'interference_factor': float(interference_factor),
                    'position_in_packet': i,
                    'total_in_packet': len(pairs)
                }
            )
            individual_waves.append(wave)

        return individual_waves

    def _estimate_interference_factor(self, total_waves: int, wave_index: int) -> float:
        """
        Estimate interference correction factor for a wave within a packet.

        Based on the KdV soliton interaction theory, leading waves in a packet
        are less affected by interference than trailing waves. The correction
        factor accounts for constructive/destructive interference between
        adjacent solitons.

        Args:
            total_waves: Total number of waves in the packet
            wave_index: Index of this wave (0 = leading wave)

        Returns:
            Interference correction factor (divide observed contrast by this)
        """
        if total_waves <= 1:
            return 1.0

        position_ratio = wave_index / max(1, total_waves - 1)

        if wave_index == 0:
            factor = 0.95
        elif wave_index == total_waves - 1:
            factor = 0.75
        else:
            factor = 0.85 + 0.1 * np.sin(position_ratio * np.pi)

        return max(0.6, min(1.1, factor))

    def _correct_interference(self, waves: List[DetectedWave], profile: np.ndarray,
                              dominant_spacing: float) -> List[DetectedWave]:
        """
        Apply interference correction to waves in a packet.

        Uses a simplified model of soliton-soliton interaction to correct
        the observed contrast for interference effects between adjacent waves.

        Args:
            waves: List of individual waves in the packet
            profile: 1D intensity profile
            dominant_spacing: Dominant wave spacing

        Returns:
            Waves with interference-corrected contrast values
        """
        if len(waves) <= 1:
            return waves

        for i, wave in enumerate(waves):
            total_adjacent_interference = 0.0

            for j, other in enumerate(waves):
                if i == j:
                    continue

                dist_pixels = abs(wave.center_col - other.center_col) + abs(wave.center_row - other.center_row)
                phase_diff = 2 * np.pi * dist_pixels * 0.1 / max(dominant_spacing, 1.0)

                amplitude = other.raw_contrast
                interference_contribution = amplitude * np.cos(phase_diff) * np.exp(-dist_pixels / 50.0)
                total_adjacent_interference += interference_contribution

            observed = wave.raw_contrast
            intrinsic = observed - 0.3 * total_adjacent_interference
            corrected_contrast = max(0.01, min(1.0, abs(intrinsic)))

            wave.contrast = corrected_contrast
            wave.metadata['interference_corrected'] = True
            wave.metadata['adjacent_interference'] = float(total_adjacent_interference)
            wave.confidence = min(1.0, wave.confidence * (corrected_contrast / max(wave.raw_contrast, 0.01)))

        return waves

    def _low_wind_enhancement(self, image: np.ndarray, energy_map: np.ndarray) -> np.ndarray:
        """
        Enhanced weak wave signals under low wind conditions.

        Low wind (< 3 m/s) results in smooth sea surface and weak SAR contrast
        for internal waves. This method uses multi-scale edge enhancement and
        adaptive thresholding to improve detectability.

        Args:
            image: Preprocessed image
            energy_map: Directional energy map

        Returns:
            Enhanced image with improved weak signal visibility
        """
        if not self.params.low_wind_mode:
            return image

        enhancement = self.params.low_wind_enhancement

        img_8bit = (image * 255).astype(np.uint8)

        edges = cv2.Canny(img_8bit, 5, 30)

        edges_smoothed = ndimage.gaussian_filter(edges.astype(np.float32), sigma=1.0)
        edges_normalized = (edges_smoothed - np.min(edges_smoothed)) / (np.max(edges_smoothed) - np.min(edges_smoothed) + 1e-8)

        laplacian = cv2.Laplacian(img_8bit, cv2.CV_64F)
        laplacian_abs = np.abs(laplacian)
        laplacian_normalized = (laplacian_abs - np.min(laplacian_abs)) / (np.max(laplacian_abs) - np.min(laplacian_abs) + 1e-8)

        combined_edges = np.maximum(edges_normalized, laplacian_normalized)

        enhanced = image.copy().astype(np.float32)

        local_std = ndimage.generic_filter(image, np.std, size=11)
        local_mean = ndimage.gaussian_filter(image, sigma=3)

        weak_signal_mask = (local_std < 0.1) & (combined_edges > 0.1)

        enhanced[weak_signal_mask] = (
            local_mean[weak_signal_mask] +
            (enhanced[weak_signal_mask] - local_mean[weak_signal_mask]) * enhancement
        )

        detail_enhanced = enhanced + 0.3 * combined_edges * enhancement

        detail_enhanced = np.clip(detail_enhanced, 0, 1)

        return detail_enhanced.astype(np.float32)

    def visualize_detection(self, result: WaveDetectionResult,
                            original_image: np.ndarray) -> np.ndarray:
        """
        Create visualization of detection results.

        Args:
            result: Detection result
            original_image: Original preprocessed image

        Returns:
            Visualization image (BGR for OpenCV)
        """
        if len(original_image.shape) == 2:
            display = cv2.cvtColor((original_image * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        else:
            display = (original_image * 255).astype(np.uint8).copy()

        for wave in result.waves:
            color = self._get_confidence_color(wave.confidence)

            for (r, c) in wave.bright_stripes[:50]:
                cv2.circle(display, (c, r), 1, color, -1)

            for (r, c) in wave.dark_stripes[:50]:
                cv2.circle(display, (c, r), 1, (255, 0, 0), -1)

            cv2.circle(display, (wave.center_col, wave.center_row), 8, color, 2)

            dir_rad = np.deg2rad(wave.direction)
            length = 30
            end_col = int(wave.center_col + np.cos(dir_rad) * length)
            end_row = int(wave.center_row + np.sin(dir_rad) * length)
            cv2.arrowedLine(display, (wave.center_col, wave.center_row),
                            (end_col, end_row), color, 2)

            label = f"ID{wave.wave_id}: {wave.wavelength:.0f}m"
            cv2.putText(display, label, (wave.center_col + 10, wave.center_row - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        info_text = f"Dir: {result.dominant_direction:.1f}° | Space: {result.dominant_spacing:.0f}m | Conf: {result.direction_confidence:.2f}"
        cv2.putText(display, info_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        return display

    def visualize_radon(self, result: WaveDetectionResult) -> np.ndarray:
        """
        Create visualization of Radon transform.

        Args:
            result: Detection result

        Returns:
            Radon transform visualization
        """
        if result.radon_image is None:
            return np.zeros((100, 100, 3), dtype=np.uint8)

        radon_img = (result.radon_image * 255).astype(np.uint8)
        radon_img = cv2.applyColorMap(radon_img, cv2.COLORMAP_JET)

        return radon_img

    def _get_confidence_color(self, confidence: float) -> Tuple[int, int, int]:
        """Get color based on confidence value."""
        if confidence > 0.7:
            return (0, 255, 0)
        elif confidence > 0.4:
            return (0, 255, 255)
        elif confidence > 0.2:
            return (0, 165, 255)
        else:
            return (0, 0, 255)
