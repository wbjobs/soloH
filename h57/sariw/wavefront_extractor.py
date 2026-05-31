import numpy as np
import cv2
from scipy import ndimage
from skimage.morphology import thin as skimage_thin
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class WavefrontParams:
    """Parameters for wavefront extraction."""
    canny_low: int = 30
    canny_high: int = 100
    edge_thinning: bool = True
    min_edge_length: int = 20
    max_edge_gap: int = 5
    hough_threshold: int = 50
    hough_min_line_length: int = 30
    hough_max_line_gap: int = 10
    fit_polynomial: bool = True
    polynomial_order: int = 2


@dataclass
class Wavefront:
    """Data class for an extracted wavefront."""
    wavefront_id: int
    points: List[Tuple[int, int]]
    line_coeffs: Optional[np.ndarray] = None
    polynomial_coeffs: Optional[np.ndarray] = None
    length: float = 0.0
    curvature: float = 0.0
    direction: float = 0.0
    is_bright: bool = True
    associated_wave_id: Optional[int] = None

    def get_points_geo(self, geotiff_data) -> List[Tuple[float, float]]:
        """Get wavefront points in geographic coordinates."""
        return [geotiff_data.pixel_to_wgs84(r, c) for r, c in self.points]

    def sample_along_front(self, num_points: int = 100) -> List[Tuple[float, float]]:
        """Sample evenly spaced points along the wavefront."""
        if len(self.points) < 2:
            return self.points

        points_arr = np.array(self.points)
        distances = np.zeros(len(points_arr))
        for i in range(1, len(points_arr)):
            distances[i] = distances[i - 1] + np.linalg.norm(points_arr[i] - points_arr[i - 1])

        total_length = distances[-1]
        sample_distances = np.linspace(0, total_length, num_points)

        sampled = []
        for d in sample_distances:
            idx = np.searchsorted(distances, d)
            if idx == 0:
                sampled.append(tuple(points_arr[0]))
            elif idx >= len(points_arr):
                sampled.append(tuple(points_arr[-1]))
            else:
                t = (d - distances[idx - 1]) / (distances[idx] - distances[idx - 1] + 1e-8)
                pt = points_arr[idx - 1] + t * (points_arr[idx] - points_arr[idx - 1])
                sampled.append((float(pt[0]), float(pt[1])))

        return sampled


@dataclass
class WavefrontExtractionResult:
    """Result of wavefront extraction."""
    wavefronts: List[Wavefront] = field(default_factory=list)
    edge_image: Optional[np.ndarray] = None
    bright_fronts: List[Wavefront] = field(default_factory=list)
    dark_fronts: List[Wavefront] = field(default_factory=list)


class WavefrontExtractor:
    """Extractor for wavefronts using Canny edge detection."""

    def __init__(self, params: Optional[WavefrontParams] = None):
        """
        Initialize wavefront extractor.

        Args:
            params: Extraction parameters
        """
        self.params = params or WavefrontParams()

    def extract(self, preprocessed_image: np.ndarray,
                detection_result: Optional[Any] = None) -> WavefrontExtractionResult:
        """
        Extract wavefronts from preprocessed image.

        Args:
            preprocessed_image: Preprocessed SAR image
            detection_result: Optional wave detection result for guidance

        Returns:
            WavefrontExtractionResult
        """
        logger.info("Starting wavefront extraction...")

        result = WavefrontExtractionResult()

        logger.info("  Applying Canny edge detection...")
        edges = self._canny_edges(preprocessed_image)
        result.edge_image = edges

        if self.params.edge_thinning:
            edges = self._thin_edges(edges)

        logger.info("  Extracting and linking edge segments...")
        edge_segments = self._extract_edge_segments(edges)
        edge_segments = self._filter_short_segments(edge_segments)
        edge_segments = self._link_segments(edge_segments)

        logger.info("  Classifying wavefronts (bright/dark)...")
        bright_fronts, dark_fronts = self._classify_fronts(
            preprocessed_image, edge_segments
        )

        logger.info(f"  Fitting geometric models to {len(bright_fronts)} bright and {len(dark_fronts)} dark fronts...")
        wavefront_id = 0
        for points in bright_fronts:
            wf = self._create_wavefront(points, wavefront_id, is_bright=True)
            result.wavefronts.append(wf)
            result.bright_fronts.append(wf)
            wavefront_id += 1

        for points in dark_fronts:
            wf = self._create_wavefront(points, wavefront_id, is_bright=False)
            result.wavefronts.append(wf)
            result.dark_fronts.append(wf)
            wavefront_id += 1

        if detection_result is not None and hasattr(detection_result, 'waves'):
            self._associate_waves(detection_result.waves, result.wavefronts)

        logger.info(f"Extraction completed. Found {len(result.wavefronts)} wavefronts.")
        return result

    def _canny_edges(self, image: np.ndarray) -> np.ndarray:
        """
        Apply Canny edge detection.

        Args:
            image: Input image

        Returns:
            Binary edge image
        """
        img_8bit = (image * 255).astype(np.uint8)

        img_blur = cv2.GaussianBlur(img_8bit, (3, 3), 0)

        edges = cv2.Canny(img_blur, self.params.canny_low, self.params.canny_high)

        return edges

    def _thin_edges(self, edges: np.ndarray) -> np.ndarray:
        """
        Apply morphological thinning to edges.

        Args:
            edges: Binary edge image

        Returns:
            Thinned edge image
        """
        edges_bool = edges > 0
        thinned = skimage_thin(edges_bool)
        return (thinned * 255).astype(np.uint8)

    def _extract_edge_segments(self, edges: np.ndarray) -> List[List[Tuple[int, int]]]:
        """
        Extract connected edge segments.

        Args:
            edges: Binary edge image

        Returns:
            List of edge segments, each is a list of (row, col) points
        """
        labeled, num_features = ndimage.label(edges > 0)

        segments = []
        for i in range(1, num_features + 1):
            y, x = np.where(labeled == i)
            points = list(zip(y, x))
            if len(points) >= self.params.min_edge_length:
                segments.append(points)

        return segments

    def _filter_short_segments(self, segments: List[List[Tuple[int, int]]]) -> List[List[Tuple[int, int]]]:
        """
        Filter out short edge segments.

        Args:
            segments: List of edge segments

        Returns:
            Filtered list of segments
        """
        return [s for s in segments if len(s) >= self.params.min_edge_length]

    def _link_segments(self, segments: List[List[Tuple[int, int]]]) -> List[List[Tuple[int, int]]]:
        """
        Link nearby edge segments.

        Args:
            segments: List of edge segments

        Returns:
            List of linked segments
        """
        if len(segments) < 2:
            return segments

        linked = segments.copy()
        changed = True

        while changed:
            changed = False
            for i in range(len(linked)):
                for j in range(i + 1, len(linked)):
                    dist = self._segment_distance(linked[i], linked[j])
                    if dist < self.params.max_edge_gap:
                        linked[i] = self._merge_segments(linked[i], linked[j])
                        del linked[j]
                        changed = True
                        break
                if changed:
                    break

        return linked

    def _segment_distance(self, seg1: List[Tuple[int, int]], seg2: List[Tuple[int, int]]) -> float:
        """
        Compute minimum distance between two segments.

        Args:
            seg1: First segment
            seg2: Second segment

        Returns:
            Minimum distance
        """
        pts1 = np.array(seg1)
        pts2 = np.array(seg2)

        endpoints1 = [pts1[0], pts1[-1]]
        endpoints2 = [pts2[0], pts2[-1]]

        min_dist = np.inf
        for p1 in endpoints1:
            for p2 in endpoints2:
                dist = np.linalg.norm(p1 - p2)
                if dist < min_dist:
                    min_dist = dist

        return min_dist

    def _merge_segments(self, seg1: List[Tuple[int, int]], seg2: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        Merge two segments.

        Args:
            seg1: First segment
            seg2: Second segment

        Returns:
            Merged segment
        """
        pts1 = np.array(seg1)
        pts2 = np.array(seg2)

        d1 = np.linalg.norm(pts1[-1] - pts2[0])
        d2 = np.linalg.norm(pts1[-1] - pts2[-1])
        d3 = np.linalg.norm(pts1[0] - pts2[0])
        d4 = np.linalg.norm(pts1[0] - pts2[-1])

        min_d = min(d1, d2, d3, d4)

        if min_d == d1:
            merged = np.vstack([pts1, pts2])
        elif min_d == d2:
            merged = np.vstack([pts1, pts2[::-1]])
        elif min_d == d3:
            merged = np.vstack([pts1[::-1], pts2])
        else:
            merged = np.vstack([pts1[::-1], pts2[::-1]])

        return [tuple(p) for p in merged]

    def _classify_fronts(self, image: np.ndarray,
                         segments: List[List[Tuple[int, int]]]) -> Tuple[List[List[Tuple[int, int]]], List[List[Tuple[int, int]]]]:
        """
        Classify fronts as bright or dark based on local contrast.

        Args:
            image: Preprocessed image
            segments: List of edge segments

        Returns:
            Tuple of (bright_fronts, dark_fronts)
        """
        bright_fronts = []
        dark_fronts = []

        for seg in segments:
            points = np.array(seg)

            values = []
            for (r, c) in seg:
                if 0 <= r < image.shape[0] and 0 <= c < image.shape[1]:
                    values.append(image[r, c])

            if len(values) == 0:
                continue

            mean_val = np.mean(values)
            img_mean = np.mean(image)

            if mean_val > img_mean + np.std(image) * 0.3:
                bright_fronts.append(seg)
            elif mean_val < img_mean - np.std(image) * 0.3:
                dark_fronts.append(seg)
            else:
                if mean_val > img_mean:
                    bright_fronts.append(seg)
                else:
                    dark_fronts.append(seg)

        return bright_fronts, dark_fronts

    def _create_wavefront(self, points: List[Tuple[int, int]],
                          wavefront_id: int, is_bright: bool) -> Wavefront:
        """
        Create a Wavefront object from points, fitting geometric models.

        Args:
            points: List of (row, col) points
            wavefront_id: ID for this wavefront
            is_bright: Whether this is a bright front

        Returns:
            Wavefront object
        """
        points_arr = np.array(points)

        line_coeffs = self._fit_line(points_arr)
        direction = self._compute_direction(line_coeffs)

        if self.params.fit_polynomial and len(points) > 5:
            poly_coeffs = self._fit_polynomial(points_arr)
            curvature = self._compute_curvature(poly_coeffs, points_arr)
        else:
            poly_coeffs = None
            curvature = 0.0

        length = self._compute_length(points_arr)

        return Wavefront(
            wavefront_id=wavefront_id,
            points=points,
            line_coeffs=line_coeffs,
            polynomial_coeffs=poly_coeffs,
            length=float(length),
            curvature=float(curvature),
            direction=float(direction),
            is_bright=is_bright
        )

    def _fit_line(self, points: np.ndarray) -> np.ndarray:
        """
        Fit a line to points using least squares.

        Args:
            points: Array of (row, col) points

        Returns:
            Line coefficients [a, b, c] for ax + by + c = 0
        """
        y = points[:, 0]
        x = points[:, 1]

        A = np.vstack([x, np.ones(len(x))]).T
        m, c = np.linalg.lstsq(A, y, rcond=None)[0]

        return np.array([m, -1, c])

    def _fit_polynomial(self, points: np.ndarray) -> np.ndarray:
        """
        Fit a polynomial to points.

        Args:
            points: Array of (row, col) points

        Returns:
            Polynomial coefficients
        """
        y = points[:, 0]
        x = points[:, 1]

        coeffs = np.polyfit(x, y, self.params.polynomial_order)
        return coeffs

    def _compute_direction(self, line_coeffs: np.ndarray) -> float:
        """
        Compute wavefront direction from line coefficients.

        Args:
            line_coeffs: Line coefficients [m, -1, c] (y = mx + c)

        Returns:
            Direction in degrees (0-180)
        """
        m = line_coeffs[0]
        angle_rad = np.arctan(m)
        angle_deg = np.rad2deg(angle_rad)

        propagation_angle = (angle_deg + 90) % 180
        return propagation_angle

    def _compute_curvature(self, poly_coeffs: np.ndarray, points: np.ndarray) -> float:
        """
        Compute mean curvature of polynomial.

        Args:
            poly_coeffs: Polynomial coefficients
            points: Points along the curve

        Returns:
            Mean curvature
        """
        if poly_coeffs is None or len(poly_coeffs) < 3:
            return 0.0

        x = points[:, 1]
        order = len(poly_coeffs) - 1

        first_deriv = np.polyder(poly_coeffs)
        second_deriv = np.polyder(poly_coeffs, 2)

        dy_dx = np.polyval(first_deriv, x)
        d2y_dx2 = np.polyval(second_deriv, x)

        curvature = np.abs(d2y_dx2) / (1 + dy_dx**2)**(1.5)
        return float(np.mean(curvature))

    def _compute_length(self, points: np.ndarray) -> float:
        """
        Compute total length of the wavefront.

        Args:
            points: Array of (row, col) points

        Returns:
            Total length in pixels
        """
        if len(points) < 2:
            return 0.0

        diffs = np.diff(points, axis=0)
        distances = np.sqrt(np.sum(diffs**2, axis=1))
        return float(np.sum(distances))

    def _associate_waves(self, waves: List[Any], wavefronts: List[Wavefront]) -> None:
        """
        Associate wavefronts with detected waves.

        Args:
            waves: List of detected waves
            wavefronts: List of wavefronts
        """
        for wf in wavefronts:
            if len(wf.points) == 0:
                continue

            center_r = int(np.mean([p[0] for p in wf.points]))
            center_c = int(np.mean([p[1] for p in wf.points]))

            min_dist = np.inf
            best_wave_id = None

            for wave in waves:
                dist = np.sqrt((center_r - wave.center_row)**2 +
                               (center_c - wave.center_col)**2)
                if dist < min_dist:
                    min_dist = dist
                    best_wave_id = wave.wave_id

            wf.associated_wave_id = best_wave_id

    def visualize(self, result: WavefrontExtractionResult,
                  base_image: np.ndarray) -> np.ndarray:
        """
        Visualize extracted wavefronts.

        Args:
            result: Extraction result
            base_image: Base image for visualization

        Returns:
            Visualization image
        """
        if len(base_image.shape) == 2:
            display = cv2.cvtColor((base_image * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        else:
            display = (base_image * 255).astype(np.uint8).copy()

        for wf in result.bright_fronts:
            for (r, c) in wf.points:
                if 0 <= r < display.shape[0] and 0 <= c < display.shape[1]:
                    display[r, c] = [0, 255, 0]

        for wf in result.dark_fronts:
            for (r, c) in wf.points:
                if 0 <= r < display.shape[0] and 0 <= c < display.shape[1]:
                    display[r, c] = [0, 0, 255]

        for wf in result.wavefronts:
            if len(wf.points) > 0:
                center_r = int(np.mean([p[0] for p in wf.points]))
                center_c = int(np.mean([p[1] for p in wf.points]))

                color = (0, 255, 0) if wf.is_bright else (0, 0, 255)
                cv2.circle(display, (center_c, center_r), 5, color, -1)
                cv2.putText(display, f"F{wf.wavefront_id}",
                            (center_c + 8, center_r - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        info = f"Bright: {len(result.bright_fronts)} | Dark: {len(result.dark_fronts)}"
        cv2.putText(display, info, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        return display
