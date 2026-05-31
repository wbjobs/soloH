import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from config import Config


@dataclass
class StationInfo:
    id: str
    latitude: float
    longitude: float
    elevation: float = 0.0
    site_class: str = 'C'
    p_wave_detection: bool = True
    s_wave_detection: bool = False


@dataclass
class EarthquakeLocation:
    latitude: float
    longitude: float
    depth: float
    origin_time: float
    magnitude: float
    location_uncertainty: float = 5.0


@dataclass
class WarningZoneResult:
    time_since_p_arrival: float
    blind_zone_radius: float
    warning_zone_radius: float
    blind_zone_area: float
    warning_zone_area: float
    estimated_s_arrival_time: float
    current_time: float
    p_arrival_time: float
    stations_in_blind_zone: List[str] = field(default_factory=list)
    stations_in_warning_zone: List[str] = field(default_factory=list)
    stations_safe: List[str] = field(default_factory=list)


class SeismicWaveModel:
    def __init__(self, model_type='iasp91'):
        self.model_type = model_type
        self._init_velocity_model()

    def _init_velocity_model(self):
        self.vp_crust = 6.0
        self.vs_crust = 3.5
        self.vp_mantle = 8.0
        self.vs_mantle = 4.5
        self.crust_thickness = 35.0

        self.vp_coeffs = [6.3, 0.001, -0.00001]
        self.vs_coeffs = [3.5, 0.0005, -0.000005]

    def get_p_velocity(self, depth, distance=0.0):
        if depth < self.crust_thickness:
            vp = self.vp_crust + 0.001 * depth
        else:
            vp = self.vp_mantle + 0.0005 * (depth - self.crust_thickness)
        return vp

    def get_s_velocity(self, depth, distance=0.0):
        if depth < self.crust_thickness:
            vs = self.vs_crust + 0.0005 * depth
        else:
            vs = self.vs_mantle + 0.0002 * (depth - self.crust_thickness)
        return vs

    def get_vs_over_vp(self, depth):
        return self.get_s_velocity(depth) / self.get_p_velocity(depth)

    def estimate_travel_time(self, epicentral_distance, depth, phase='P'):
        if epicentral_distance < 0:
            epicentral_distance = 0

        if phase == 'P':
            vel = self.get_p_velocity(depth, epicentral_distance)
        elif phase == 'S':
            vel = self.get_s_velocity(depth, epicentral_distance)
        else:
            raise ValueError(f"Unknown phase: {phase}")

        ray_path = np.sqrt(epicentral_distance**2 + depth**2)
        travel_time = ray_path / vel

        if epicentral_distance > 100:
            travel_time *= 1.0 + 0.0005 * (epicentral_distance - 100)

        return travel_time

    def estimate_distance_from_time(self, travel_time, depth, phase='P'):
        if travel_time <= 0:
            return 0.0

        if phase == 'P':
            vel = self.get_p_velocity(depth)
        elif phase == 'S':
            vel = self.get_s_velocity(depth)
        else:
            raise ValueError(f"Unknown phase: {phase}")

        distance = np.sqrt((travel_time * vel)**2 - depth**2)
        if np.isnan(distance):
            distance = travel_time * vel * 0.8

        return max(0.0, distance)


class WarningZoneCalculator:
    def __init__(self, wave_model=None, stations=None):
        self.wave_model = wave_model or SeismicWaveModel()
        self.stations = stations or []
        self.earthquake_location = None
        self.p_arrival_time = None
        self.lead_time_warning_threshold = 3.0

    def set_earthquake_location(self, lat, lon, depth, origin_time, magnitude):
        self.earthquake_location = EarthquakeLocation(
            latitude=lat,
            longitude=lon,
            depth=depth,
            origin_time=origin_time,
            magnitude=magnitude
        )

    def set_stations(self, stations):
        self.stations = stations

    def add_station(self, station):
        self.stations.append(station)

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        R = 6371.0

        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        delta_lat = np.radians(lat2 - lat1)
        delta_lon = np.radians(lon2 - lon1)

        a = (np.sin(delta_lat / 2)**2 +
             np.cos(lat1_rad) * np.cos(lat2_rad) *
             np.sin(delta_lon / 2)**2)
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        return R * c

    def calculate_warning_zone(self, current_time, p_arrival_time=None,
                               s_arrival_time=None, epicentral_distance=None):
        if p_arrival_time is None:
            p_arrival_time = self.p_arrival_time

        if p_arrival_time is None:
            raise ValueError("P波到时未提供")

        time_since_p = current_time - p_arrival_time

        depth = self.earthquake_location.depth if self.earthquake_location else 10.0
        vp = self.wave_model.get_p_velocity(depth)
        vs = self.wave_model.get_s_velocity(depth)
        vs_vp_ratio = vs / vp

        if s_arrival_time is not None:
            s_p_interval = s_arrival_time - p_arrival_time
            estimated_distance = self.wave_model.estimate_distance_from_time(
                s_p_interval, depth, phase='S'
            ) - self.wave_model.estimate_distance_from_time(
                s_p_interval, depth, phase='P'
            )
            estimated_distance = max(0, vp * s_p_interval / (1 - vs_vp_ratio))
        elif epicentral_distance is not None:
            estimated_distance = epicentral_distance
        else:
            estimated_distance = self._estimate_distance_from_magnitude(
                self.earthquake_location.magnitude if self.earthquake_location else 5.0
            )

        blind_zone_radius = self._calculate_blind_zone(
            time_since_p, vs, estimated_distance, depth
        )

        warning_zone_radius = self._calculate_warning_zone(
            time_since_p, vp, vs, estimated_distance, depth
        )

        estimated_s_arrival = p_arrival_time + estimated_distance / vs * (1 + vs_vp_ratio)

        blind_zone_area = np.pi * blind_zone_radius**2
        warning_zone_area = np.pi * (warning_zone_radius**2 - blind_zone_radius**2)

        result = WarningZoneResult(
            time_since_p_arrival=time_since_p,
            blind_zone_radius=blind_zone_radius,
            warning_zone_radius=warning_zone_radius,
            blind_zone_area=blind_zone_area,
            warning_zone_area=warning_zone_area,
            estimated_s_arrival_time=estimated_s_arrival,
            current_time=current_time,
            p_arrival_time=p_arrival_time
        )

        result = self._classify_stations(result)

        return result

    def _calculate_blind_zone(self, time_since_p, vs, estimated_distance, depth):
        if time_since_p <= 0:
            return 0.0

        s_wave_distance = vs * time_since_p

        blind_radius = min(s_wave_distance, estimated_distance)

        magnitude = self.earthquake_location.magnitude if self.earthquake_location else 5.0
        if magnitude >= 7.0:
            blind_radius *= 1.2
        elif magnitude >= 6.0:
            blind_radius *= 1.1

        return blind_radius

    def _calculate_warning_zone(self, time_since_p, vp, vs, estimated_distance, depth):
        if time_since_p <= 0:
            return estimated_distance * 2.0

        s_wave_distance = vs * time_since_p

        warning_radius = max(s_wave_distance * 1.5, estimated_distance * 2.0)

        max_warning_radius = estimated_distance * 3.0
        warning_radius = min(warning_radius, max_warning_radius)

        return warning_radius

    def _estimate_distance_from_magnitude(self, magnitude):
        return 10.0 * 10 ** (0.5 * (magnitude - 5.0))

    def _classify_stations(self, result):
        if not self.earthquake_location or not self.stations:
            return result

        eq_lat = self.earthquake_location.latitude
        eq_lon = self.earthquake_location.longitude

        for station in self.stations:
            dist = self.haversine_distance(
                eq_lat, eq_lon, station.latitude, station.longitude
            )

            if dist <= result.blind_zone_radius:
                result.stations_in_blind_zone.append(station.id)
            elif dist <= result.warning_zone_radius:
                result.stations_in_warning_zone.append(station.id)
            else:
                result.stations_safe.append(station.id)

        return result

    def calculate_lead_time(self, station_distance, current_time, p_arrival_time):
        depth = self.earthquake_location.depth if self.earthquake_location else 10.0

        s_travel_time = self.wave_model.estimate_travel_time(
            station_distance, depth, phase='S'
        )

        if self.earthquake_location:
            expected_s_arrival = self.earthquake_location.origin_time + s_travel_time
        else:
            expected_s_arrival = p_arrival_time + s_travel_time

        lead_time = expected_s_arrival - current_time

        return max(0.0, lead_time), expected_s_arrival

    def generate_time_series(self, p_arrival_time, duration=60.0, time_step=1.0,
                             s_arrival_time=None, epicentral_distance=None):
        time_points = np.arange(p_arrival_time, p_arrival_time + duration, time_step)
        results = []

        for t in time_points:
            wz = self.calculate_warning_zone(
                t, p_arrival_time, s_arrival_time, epicentral_distance
            )
            results.append(wz)

        return time_points, results

    def estimate_intensity(self, distance, magnitude, site_class='C'):
        if distance <= 0:
            distance = 1.0

        site_amplification = {
            'A': 0.7, 'B': 0.85, 'C': 1.0, 'D': 1.3, 'E': 1.6, 'F': 2.0
        }
        amp = site_amplification.get(site_class, 1.0)

        intensity = (magnitude +
                     1.7 * np.log10(np.max([distance, 1.0])) -
                     2.5) * amp

        intensity = np.clip(intensity, 1, 12)

        return intensity

    def get_damage_potential(self, intensity):
        if intensity < 3:
            return 'none', '无破坏'
        elif intensity < 5:
            return 'light', '轻微破坏'
        elif intensity < 7:
            return 'moderate', '中等破坏'
        elif intensity < 9:
            return 'severe', '严重破坏'
        else:
            return 'extreme', '极严重破坏'


class RealTimeWarningSystem:
    def __init__(self, warning_zone_calculator=None):
        self.calculator = warning_zone_calculator or WarningZoneCalculator()
        self.detection_history = []
        self.warning_history = []
        self.current_warning_level = 'normal'

    def update(self, detection, current_time):
        self.detection_history.append({
            'time': current_time,
            'detection': detection
        })

        p_arrival = detection.get('arrival_time', current_time)
        s_arrival = detection.get('s_arrival_time')
        magnitude = detection.get('magnitude', 5.0)

        if self.calculator.earthquake_location is None:
            self.calculator.set_earthquake_location(
                lat=0.0, lon=0.0, depth=10.0,
                origin_time=p_arrival - 5.0,
                magnitude=magnitude
            )

        warning_zone = self.calculator.calculate_warning_zone(
            current_time, p_arrival_time=p_arrival,
            s_arrival_time=s_arrival
        )

        warning_level = self._determine_warning_level(warning_zone, magnitude)
        self.current_warning_level = warning_level

        self.warning_history.append({
            'time': current_time,
            'warning_zone': warning_zone,
            'warning_level': warning_level
        })

        return warning_zone, warning_level

    def _determine_warning_level(self, warning_zone, magnitude):
        time_to_s = warning_zone.estimated_s_arrival_time - warning_zone.current_time

        if magnitude >= 7.0 and time_to_s < 10.0:
            return 'critical'
        elif magnitude >= 6.0 and time_to_s < 15.0:
            return 'severe'
        elif magnitude >= 5.0 and time_to_s < 20.0:
            return 'warning'
        elif magnitude >= 4.0 and time_to_s < 30.0:
            return 'advisory'
        else:
            return 'info'

    def get_warning_summary(self):
        if not self.warning_history:
            return "无预警信息"

        latest = self.warning_history[-1]
        wz = latest['warning_zone']
        level = latest['warning_level']

        time_to_s = wz.estimated_s_arrival_time - wz.current_time

        summary = f"""
预警级别: {level.upper()}
盲域半径: {wz.blind_zone_radius:.1f} km
预警范围: {wz.warning_zone_radius:.1f} km
盲域面积: {wz.blind_zone_area:.0f} km²
预警区面积: {wz.warning_zone_area:.0f} km²
S波预计到达: {time_to_s:.1f} s后
盲域内台站: {len(wz.stations_in_blind_zone)} 个
预警区内台站: {len(wz.stations_in_warning_zone)} 个
安全区台站: {len(wz.stations_safe)} 个
        """.strip()

        return summary


def format_warning_zone(wz, include_stations=False):
    lines = []

    warning_levels = {
        'critical': '紧急',
        'severe': '严重',
        'warning': '警告',
        'advisory': '注意',
        'info': '信息'
    }

    lines.append("  预警盲区与范围计算:")
    lines.append(f"    P波后经过时间: {wz.time_since_p_arrival:.1f} s")

    time_to_s = wz.estimated_s_arrival_time - wz.current_time
    if time_to_s > 0:
        lines.append(f"    S波预计到达: {wz.estimated_s_arrival_time:.2f} s (还有 {time_to_s:.1f} s)")
    else:
        lines.append(f"    S波已到达: {wz.estimated_s_arrival_time:.2f} s (已过 {-time_to_s:.1f} s)")

    lines.append(f"    盲域半径: {wz.blind_zone_radius:.2f} km")
    lines.append(f"    预警范围半径: {wz.warning_zone_radius:.2f} km")
    lines.append(f"    盲域面积: {wz.blind_zone_area:.1f} km²")
    lines.append(f"    预警区面积: {wz.warning_zone_area:.1f} km²")

    if include_stations:
        if wz.stations_in_blind_zone:
            lines.append(f"    盲域内台站 ({len(wz.stations_in_blind_zone)}): {', '.join(wz.stations_in_blind_zone)}")
        if wz.stations_in_warning_zone:
            lines.append(f"    预警区内台站 ({len(wz.stations_in_warning_zone)}): {', '.join(wz.stations_in_warning_zone)}")
        if wz.stations_safe:
            lines.append(f"    安全区台站 ({len(wz.stations_safe)}): {', '.join(wz.stations_safe)}")

    return lines
