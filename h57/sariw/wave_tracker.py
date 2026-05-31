import numpy as np
from scipy.spatial import distance
from scipy.optimize import linear_sum_assignment
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import logging
import json
import os

logger = logging.getLogger(__name__)


@dataclass
class TrackParams:
    """Parameters for wave tracking."""
    max_distance: float = 50.0
    direction_tolerance: float = 30.0
    wavelength_tolerance: float = 0.5
    min_track_length: int = 2
    use_hungarian: bool = True
    distance_weight: float = 0.5
    direction_weight: float = 0.3
    wavelength_weight: float = 0.2


@dataclass
class TrackedWave:
    """Data class for a tracked wave across multiple frames."""
    track_id: int
    wave_ids: List[int] = field(default_factory=list)
    frames: List[int] = field(default_factory=list)
    positions: List[Tuple[float, float]] = field(default_factory=list)
    directions: List[float] = field(default_factory=list)
    wavelengths: List[float] = field(default_factory=list)
    amplitudes: List[float] = field(default_factory=list)
    half_widths: List[float] = field(default_factory=list)
    phase_speeds: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    mean_velocity: Optional[float] = None
    attenuation_rate: Optional[float] = None
    lifetime: float = 0.0

    def add_observation(self, frame: int, wave: Any, inverted: Optional[Any],
                        timestamp: float, geotiff_data: Any) -> None:
        """
        Add a new observation to this track.

        Args:
            frame: Frame index
            wave: Detected wave object
            inverted: Inverted wave data (optional)
            timestamp: Timestamp in seconds
            geotiff_data: GeoTIFF data for coordinate conversion
        """
        self.wave_ids.append(wave.wave_id)
        self.frames.append(frame)
        self.timestamps.append(timestamp)
        self.directions.append(wave.direction)
        self.wavelengths.append(wave.wavelength)

        lon, lat = wave.center_geo(geotiff_data)
        self.positions.append((lon, lat))

        if inverted is not None:
            self.amplitudes.append(inverted.amplitude)
            self.half_widths.append(inverted.half_width)
            self.phase_speeds.append(inverted.phase_speed)

    def compute_metrics(self) -> None:
        """Compute tracking metrics (velocity, attenuation)."""
        if len(self.timestamps) >= 2:
            self.lifetime = self.timestamps[-1] - self.timestamps[0]

            velocities = []
            for i in range(1, len(self.positions)):
                dt = self.timestamps[i] - self.timestamps[i - 1]
                if dt > 0:
                    dx = self.positions[i][0] - self.positions[i - 1][0]
                    dy = self.positions[i][1] - self.positions[i - 1][1]
                    dist_m = np.sqrt((dx * 111000)**2 + (dy * 111000)**2)
                    velocities.append(dist_m / dt)

            if velocities:
                self.mean_velocity = float(np.mean(velocities))

            if len(self.amplitudes) >= 2:
                amps = np.array(self.amplitudes)
                times = np.array(self.timestamps) - self.timestamps[0]
                if len(times) >= 2 and np.std(times) > 0:
                    try:
                        slope, _ = np.polyfit(times, np.log(amps + 1e-8), 1)
                        self.attenuation_rate = float(-slope)
                    except:
                        self.attenuation_rate = None


@dataclass
class TrackingResult:
    """Result of multi-frame wave tracking."""
    tracks: List[TrackedWave] = field(default_factory=list)
    num_frames: int = 0
    total_waves: int = 0
    time_intervals: List[float] = field(default_factory=list)


class WaveTracker:
    """
    Track internal waves across multiple SAR image frames.
    """

    def __init__(self, params: Optional[TrackParams] = None):
        """
        Initialize wave tracker.

        Args:
            params: Tracking parameters
        """
        self.params = params or TrackParams()

    def track(self, frame_results: List[Dict[str, Any]],
              time_intervals: Optional[List[float]] = None) -> TrackingResult:
        """
        Track waves across multiple frames.

        Args:
            frame_results: List of dictionaries containing per-frame results
                          Each dict should have: 'geotiff', 'detection', 'inversion'
            time_intervals: Optional list of time intervals between frames (seconds)

        Returns:
            TrackingResult
        """
        logger.info(f"Starting wave tracking across {len(frame_results)} frames...")

        result = TrackingResult()
        result.num_frames = len(frame_results)

        if time_intervals is None:
            time_intervals = [3600.0] * (len(frame_results) - 1)
        result.time_intervals = time_intervals

        timestamps = [0.0]
        for interval in time_intervals:
            timestamps.append(timestamps[-1] + interval)

        if len(frame_results) < 2:
            logger.warning("Need at least 2 frames for tracking.")
            return result

        active_tracks: List[TrackedWave] = []
        next_track_id = 0

        for frame_idx, frame_data in enumerate(frame_results):
            logger.info(f"  Processing frame {frame_idx + 1}/{len(frame_results)}...")

            geotiff_data = frame_data['geotiff']
            detection_result = frame_data['detection']
            inversion_result = frame_data.get('inversion')

            waves = detection_result.waves
            inverted_dict = {}
            if inversion_result is not None:
                inverted_dict = {inv.wave_id: inv for inv in inversion_result.inverted_waves}

            result.total_waves += len(waves)

            if frame_idx == 0:
                for wave in waves:
                    track = TrackedWave(track_id=next_track_id)
                    inv = inverted_dict.get(wave.wave_id)
                    track.add_observation(frame_idx, wave, inv, timestamps[frame_idx], geotiff_data)
                    active_tracks.append(track)
                    next_track_id += 1
            else:
                cost_matrix = self._compute_cost_matrix(
                    active_tracks, waves, geotiff_data, frame_idx, timestamps[frame_idx]
                )

                if len(active_tracks) > 0 and len(waves) > 0:
                    if self.params.use_hungarian:
                        track_indices, wave_indices = self._hungarian_assignment(cost_matrix)
                    else:
                        track_indices, wave_indices = self._greedy_assignment(cost_matrix)

                    assigned_waves = set()
                    assigned_tracks = set()

                    for track_idx, wave_idx in zip(track_indices, wave_indices):
                        if cost_matrix[track_idx, wave_idx] < self.params.max_distance:
                            track = active_tracks[track_idx]
                            wave = waves[wave_idx]
                            inv = inverted_dict.get(wave.wave_id)
                            track.add_observation(frame_idx, wave, inv, timestamps[frame_idx], geotiff_data)

                            assigned_tracks.add(track_idx)
                            assigned_waves.add(wave_idx)

                    for wave_idx, wave in enumerate(waves):
                        if wave_idx not in assigned_waves:
                            track = TrackedWave(track_id=next_track_id)
                            inv = inverted_dict.get(wave.wave_id)
                            track.add_observation(frame_idx, wave, inv, timestamps[frame_idx], geotiff_data)
                            active_tracks.append(track)
                            next_track_id += 1

                else:
                    for wave in waves:
                        track = TrackedWave(track_id=next_track_id)
                        inv = inverted_dict.get(wave.wave_id)
                        track.add_observation(frame_idx, wave, inv, timestamps[frame_idx], geotiff_data)
                        active_tracks.append(track)
                        next_track_id += 1

        for track in active_tracks:
            if len(track.frames) >= self.params.min_track_length:
                track.compute_metrics()
                result.tracks.append(track)

        result.tracks.sort(key=lambda t: len(t.frames), reverse=True)

        logger.info(f"Tracking completed. Found {len(result.tracks)} valid tracks.")
        return result

    def _compute_cost_matrix(self, tracks: List[TrackedWave],
                             waves: List[Any], geotiff_data: Any,
                             frame_idx: int, timestamp: float) -> np.ndarray:
        """
        Compute cost matrix for assigning waves to tracks.

        Args:
            tracks: List of active tracks
            waves: List of detected waves in current frame
            geotiff_data: GeoTIFF data
            frame_idx: Current frame index
            timestamp: Current timestamp

        Returns:
            Cost matrix (n_tracks x n_waves)
        """
        n_tracks = len(tracks)
        n_waves = len(waves)
        cost_matrix = np.full((n_tracks, n_waves), np.inf)

        for i, track in enumerate(tracks):
            if len(track.positions) == 0:
                continue

            last_lon, last_lat = track.positions[-1]
            last_dir = track.directions[-1]
            last_wl = track.wavelengths[-1]

            if len(track.timestamps) >= 2 and track.mean_velocity is not None:
                dt = timestamp - track.timestamps[-1]
                pred_dx = track.mean_velocity * dt * np.cos(np.deg2rad(last_dir)) / 111000
                pred_dy = track.mean_velocity * dt * np.sin(np.deg2rad(last_dir)) / 111000
                pred_lon = last_lon + pred_dx
                pred_lat = last_lat + pred_dy
            else:
                pred_lon, pred_lat = last_lon, last_lat

            for j, wave in enumerate(waves):
                wave_lon, wave_lat = wave.center_geo(geotiff_data)

                dist_deg = np.sqrt((wave_lon - pred_lon)**2 + (wave_lat - pred_lat)**2)
                dist_m = dist_deg * 111000

                dir_diff = np.abs(((wave.direction - last_dir) + 180) % 360 - 180)
                wl_diff = np.abs(wave.wavelength - last_wl) / last_wl if last_wl > 0 else 1.0

                cost = (
                    self.params.distance_weight * (dist_m / self.params.max_distance) +
                    self.params.direction_weight * (dir_diff / self.params.direction_tolerance) +
                    self.params.wavelength_weight * (wl_diff / self.params.wavelength_tolerance)
                )

                cost_matrix[i, j] = cost

        return cost_matrix

    def _hungarian_assignment(self, cost_matrix: np.ndarray) -> Tuple[List[int], List[int]]:
        """
        Hungarian algorithm for optimal assignment.

        Args:
            cost_matrix: Cost matrix

        Returns:
            Tuple of (track_indices, wave_indices)
        """
        finite_mask = np.isfinite(cost_matrix)
        if not np.any(finite_mask):
            return [], []

        max_cost = np.max(cost_matrix[finite_mask]) + 1
        safe_matrix = np.where(finite_mask, cost_matrix, max_cost)

        track_indices, wave_indices = linear_sum_assignment(safe_matrix)

        valid = [i for i, (t, w) in enumerate(zip(track_indices, wave_indices))
                 if np.isfinite(cost_matrix[t, w])]

        return list(track_indices[valid]), list(wave_indices[valid])

    def _greedy_assignment(self, cost_matrix: np.ndarray) -> Tuple[List[int], List[int]]:
        """
        Greedy nearest-neighbor assignment.

        Args:
            cost_matrix: Cost matrix

        Returns:
            Tuple of (track_indices, wave_indices)
        """
        n_tracks, n_waves = cost_matrix.shape
        track_indices = []
        wave_indices = []
        used_tracks = set()
        used_waves = set()

        costs = []
        for i in range(n_tracks):
            for j in range(n_waves):
                if np.isfinite(cost_matrix[i, j]):
                    costs.append((cost_matrix[i, j], i, j))

        costs.sort()

        for cost, i, j in costs:
            if i not in used_tracks and j not in used_waves:
                track_indices.append(i)
                wave_indices.append(j)
                used_tracks.add(i)
                used_waves.add(j)

        return track_indices, wave_indices

    def print_tracking_summary(self, result: TrackingResult) -> None:
        """
        Print summary of tracking results.

        Args:
            result: Tracking result
        """
        print("\n=== Wave Tracking Summary ===")
        print(f"Number of frames: {result.num_frames}")
        print(f"Total waves detected: {result.total_waves}")
        print(f"Valid tracks found: {len(result.tracks)}")
        print("\nTrack Details:")
        print("-" * 80)
        print(f"{'ID':<5} {'Frames':<8} {'Life(s)':<10} {'AvgV(m/s)':<12} {'Atten(1/s)':<12} {'AmpRange(m)':<15}")
        print("-" * 80)

        for track in result.tracks:
            amp_range = f"{min(track.amplitudes):.1f}-{max(track.amplitudes):.1f}" if track.amplitudes else "N/A"
            vel_str = f"{track.mean_velocity:.2f}" if track.mean_velocity else "N/A"
            atten_str = f"{track.attenuation_rate:.4f}" if track.attenuation_rate else "N/A"
            print(f"{track.track_id:<5} {len(track.frames):<8} {track.lifetime:<10.0f} "
                  f"{vel_str:<12} {atten_str:<12} {amp_range:<15}")
        print("-" * 80)

    def export_tracks_geojson(self, result: TrackingResult,
                              output_path: str = 'tracks.geojson') -> str:
        """
        Export tracking results to GeoJSON.

        Args:
            result: Tracking result
            output_path: Output path

        Returns:
            Path to saved file
        """
        features = []

        for track in result.tracks:
            coords = [[lon, lat] for lon, lat in track.positions]

            properties = {
                'track_id': track.track_id,
                'num_frames': len(track.frames),
                'lifetime_seconds': track.lifetime,
                'mean_velocity_ms': track.mean_velocity,
                'attenuation_rate': track.attenuation_rate,
                'wave_ids': track.wave_ids,
                'frames': track.frames,
                'timestamps': track.timestamps,
                'directions': track.directions,
                'wavelengths': track.wavelengths,
                'amplitudes': track.amplitudes,
                'half_widths': track.half_widths,
                'phase_speeds': track.phase_speeds,
            }

            line_feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': coords
                },
                'properties': {
                    **properties,
                    'type': 'track_path'
                }
            }
            features.append(line_feature)

            for i, (lon, lat) in enumerate(track.positions):
                point_feature = {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [lon, lat]
                    },
                    'properties': {
                        'track_id': track.track_id,
                        'type': 'track_point',
                        'frame': track.frames[i],
                        'timestamp': track.timestamps[i],
                        'amplitude': track.amplitudes[i] if i < len(track.amplitudes) else None,
                        'wavelength': track.wavelengths[i],
                        'direction': track.directions[i],
                    }
                }
                features.append(point_feature)

        geojson = {
            'type': 'FeatureCollection',
            'features': features
        }

        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(geojson, f, indent=2)

        logger.info(f"Tracks GeoJSON saved: {output_path}")
        return output_path

    def export_tracks_kml(self, result: TrackingResult,
                          output_path: str = 'tracks.kml') -> str:
        """
        Export tracking results to KML.

        Args:
            result: Tracking result
            output_path: Output path

        Returns:
            Path to saved file
        """
        import simplekml

        kml = simplekml.Kml()
        kml.document.name = "Internal Wave Tracks"
        kml.document.description = "Multi-frame internal wave tracking results"

        tracks_folder = kml.newfolder(name="Wave Tracks")

        colors = [simplekml.Color.red, simplekml.Color.green, simplekml.Color.blue,
                  simplekml.Color.yellow, simplekml.Color.magenta, simplekml.Color.cyan]

        for track in result.tracks:
            track_folder = tracks_folder.newfolder(name=f"Track_{track.track_id}")

            coords = [(lon, lat) for lon, lat in track.positions]
            if len(coords) >= 2:
                line = track_folder.newlinestring(name=f"Path_{track.track_id}")
                line.coords = coords
                line.style.linestyle.color = colors[track.track_id % len(colors)]
                line.style.linestyle.width = 3
                line.altitudemode = 'clampToGround'
                line.tessellate = True

                desc = self._build_track_description(track)
                line.description = desc

            for i, (lon, lat) in enumerate(track.positions):
                pnt = track_folder.newpoint(name=f"Frame{track.frames[i]}")
                pnt.coords = [(lon, lat)]
                pnt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
                pnt.style.iconstyle.color = colors[track.track_id % len(colors)]
                pnt.style.iconstyle.scale = 1.0 + i * 0.1

                if i == len(track.positions) - 1:
                    pnt.style.iconstyle.scale = 1.5

        kml.save(output_path)
        logger.info(f"Tracks KML saved: {output_path}")
        return output_path

    def _build_track_description(self, track: TrackedWave) -> str:
        """
        Build HTML description for a track.

        Args:
            track: Tracked wave

        Returns:
            HTML description
        """
        html = f"""
        <![CDATA[
        <div style="font-family: Arial, sans-serif; padding: 10px;">
            <h3 style="color: #1a5276; margin-top: 0;">Wave Track #{track.track_id}</h3>
            <table border="0" cellpadding="4" cellspacing="0">
                <tr bgcolor="#eaf2f8">
                    <td><b>Parameter</b></td>
                    <td><b>Value</b></td>
                </tr>
                <tr>
                    <td>Number of frames</td>
                    <td>{len(track.frames)}</td>
                </tr>
                <tr bgcolor="#eaf2f8">
                    <td>Lifetime</td>
                    <td>{track.lifetime:.0f} seconds</td>
                </tr>
                <tr>
                    <td>Mean velocity</td>
                    <td>{track.mean_velocity:.2f} m/s</td>
                </tr>
                <tr bgcolor="#eaf2f8">
                    <td>Attenuation rate</td>
                    <td>{track.attenuation_rate:.4f} 1/s</td>
                </tr>
                <tr>
                    <td>Amplitude range</td>
                    <td>{min(track.amplitudes):.1f} - {max(track.amplitudes):.1f} m</td>
                </tr>
                <tr bgcolor="#eaf2f8">
                    <td>Mean wavelength</td>
                    <td>{np.mean(track.wavelengths):.1f} m</td>
                </tr>
                <tr>
                    <td>Mean direction</td>
                    <td>{np.mean(track.directions):.1f}°</td>
                </tr>
            </table>
        </div>
        ]]>
        """
        return html
