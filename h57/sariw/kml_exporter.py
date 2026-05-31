import numpy as np
import simplekml
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import os
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class KMLExportParams:
    """Parameters for KML export."""
    export_wave_points: bool = True
    export_wavefronts: bool = True
    export_direction_arrows: bool = True
    wave_point_size: float = 5.0
    wavefront_width: float = 3.0
    confidence_color_scale: bool = True
    altitude_mode: str = 'clampToGround'
    extrude: bool = False
    tessellate: bool = True
    name_prefix: str = 'InternalWave'


class KMLExporter:
    """Export internal wave analysis results to KML for Google Earth."""

    def __init__(self, params: Optional[KMLExportParams] = None):
        """
        Initialize KML exporter.

        Args:
            params: Export parameters
        """
        self.params = params or KMLExportParams()

    def export(self, geotiff_data: Any, detection_result: Any,
               inversion_result: Any,
               wavefront_result: Optional[Any] = None,
               output_path: str = 'output.kml') -> str:
        """
        Export all results to KML file.

        Args:
            geotiff_data: GeoTIFF data with coordinate information
            detection_result: Wave detection result
            inversion_result: Amplitude inversion result
            wavefront_result: Optional wavefront extraction result
            output_path: Path for output KML file

        Returns:
            Path to saved KML file
        """
        logger.info(f"Exporting results to KML: {output_path}")

        kml = simplekml.Kml()
        kml.document.name = f"{self.params.name_prefix}_Analysis"
        kml.document.description = "SAR Internal Wave Detection and Analysis Results"

        wave_folder = kml.newfolder(name="Detected Waves")
        front_folder = kml.newfolder(name="Wavefronts")
        direction_folder = kml.newfolder(name="Propagation Directions")

        inverted_dict = {inv.wave_id: inv for inv in inversion_result.inverted_waves}

        for wave in detection_result.waves:
            wave_id = wave.wave_id
            inv = inverted_dict.get(wave_id)

            self._add_wave_point(kml, wave_folder, wave, inv, geotiff_data)

            if self.params.export_direction_arrows:
                self._add_direction_arrow(kml, direction_folder, wave, inv, geotiff_data)

            if wavefront_result is not None:
                associated_fronts = [wf for wf in wavefront_result.wavefronts
                                     if wf.associated_wave_id == wave_id]
                for wf in associated_fronts:
                    self._add_wavefront(kml, front_folder, wf, inv, geotiff_data)

        if wavefront_result is not None:
            for wf in wavefront_result.wavefronts:
                if wf.associated_wave_id is None:
                    self._add_wavefront(kml, front_folder, wf, None, geotiff_data)

        self._add_legend(kml)

        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        kml.save(output_path)
        logger.info(f"KML file saved: {output_path}")

        return output_path

    def _add_wave_point(self, kml: simplekml.Kml, folder: simplekml.Folder,
                        wave: Any, inv: Optional[Any], geotiff_data: Any) -> None:
        """
        Add wave center point to KML.

        Args:
            kml: KML object
            folder: Folder to add to
            wave: Detected wave
            inv: Inverted wave data (optional)
            geotiff_data: GeoTIFF data
        """
        lon, lat = wave.center_geo(geotiff_data)

        pnt = folder.newpoint()
        pnt.name = f"Wave_{wave.wave_id}"

        description = self._build_wave_description(wave, inv)
        pnt.description = description

        pnt.coords = [(lon, lat)]

        confidence = wave.confidence
        if inv is not None:
            confidence = inv.confidence

        color = self._get_color_by_confidence(confidence)
        pnt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
        pnt.style.iconstyle.color = color
        pnt.style.iconstyle.scale = self.params.wave_point_size * (0.5 + confidence)

        pnt.altitudemode = self.params.altitude_mode
        pnt.extrude = self.params.extrude

    def _add_direction_arrow(self, kml: simplekml.Kml, folder: simplekml.Folder,
                             wave: Any, inv: Optional[Any], geotiff_data: Any) -> None:
        """
        Add propagation direction arrow to KML.

        Args:
            kml: KML object
            folder: Folder to add to
            wave: Detected wave
            inv: Inverted wave data (optional)
            geotiff_data: GeoTIFF data
        """
        lon, lat = wave.center_geo(geotiff_data)

        length_meters = wave.wavelength * 3
        direction_rad = np.deg2rad(wave.direction)

        dlat = (length_meters / 111000.0) * np.cos(direction_rad)
        dlon = (length_meters / (111000.0 * np.cos(np.deg2rad(lat)))) * np.sin(direction_rad)

        end_lon = lon + dlon
        end_lat = lat + dlat

        line = folder.newlinestring()
        line.name = f"Dir_Wave{wave.wave_id}"
        line.coords = [(lon, lat), (end_lon, end_lat)]

        confidence = wave.confidence
        if inv is not None:
            confidence = inv.confidence
        color = self._get_color_by_confidence(confidence)

        line.style.linestyle.color = color
        line.style.linestyle.width = 3
        line.altitudemode = self.params.altitude_mode
        line.tessellate = self.params.tessellate

        description = f"""
        <h4>Propagation Direction</h4>
        <b>Direction:</b> {wave.direction:.1f}°<br>
        <b>Speed:</b> {inv.phase_speed:.2f} m/s<br>
        <b>Wavelength:</b> {wave.wavelength:.1f} m
        """
        line.description = description

    def _add_wavefront(self, kml: simplekml.Kml, folder: simplekml.Folder,
                       wavefront: Any, inv: Optional[Any], geotiff_data: Any) -> None:
        """
        Add wavefront line to KML.

        Args:
            kml: KML object
            folder: Folder to add to
            wavefront: Wavefront data
            inv: Inverted wave data (optional)
            geotiff_data: GeoTIFF data
        """
        geo_points = wavefront.get_points_geo(geotiff_data)
        if len(geo_points) < 2:
            return

        sampled_points = wavefront.sample_along_front(50)
        sampled_geo = []
        for r, c in sampled_points:
            try:
                lon, lat = geotiff_data.pixel_to_wgs84(int(r), int(c))
                sampled_geo.append((lon, lat))
            except:
                continue

        if len(sampled_geo) < 2:
            sampled_geo = geo_points

        line = folder.newlinestring()
        front_type = "Bright" if wavefront.is_bright else "Dark"
        line.name = f"F{wavefront.wavefront_id}_{front_type}"

        coords = [(lon, lat) for lon, lat in sampled_geo]
        line.coords = coords

        if wavefront.is_bright:
            color = simplekml.Color.green
        else:
            color = simplekml.Color.red

        if inv is not None and self.params.confidence_color_scale:
            color = self._get_color_by_confidence(inv.confidence)

        line.style.linestyle.color = color
        line.style.linestyle.width = self.params.wavefront_width
        line.altitudemode = self.params.altitude_mode
        line.tessellate = self.params.tessellate

        description = self._build_wavefront_description(wavefront, inv)
        line.description = description

    def _build_wave_description(self, wave: Any, inv: Optional[Any]) -> str:
        """
        Build HTML description for wave placemark.

        Args:
            wave: Detected wave
            inv: Inverted wave data (optional)

        Returns:
            HTML description string
        """
        html = f"""
        <![CDATA[
        <div style="font-family: Arial, sans-serif; padding: 10px;">
            <h3 style="color: #1a5276; margin-top: 0;">Internal Wave #{wave.wave_id}</h3>
            <table border="0" cellpadding="4" cellspacing="0">
                <tr bgcolor="#eaf2f8">
                    <td><b>Parameter</b></td>
                    <td><b>Value</b></td>
                </tr>
                <tr>
                    <td>Detection Confidence</td>
                    <td>{wave.confidence:.2f}</td>
                </tr>
                <tr bgcolor="#eaf2f8">
                    <td>Propagation Direction</td>
                    <td>{wave.direction:.1f}°</td>
                </tr>
                <tr>
                    <td>Wavelength</td>
                    <td>{wave.wavelength:.1f} m</td>
                </tr>
                <tr bgcolor="#eaf2f8">
                    <td>Spacing</td>
                    <td>{wave.spacing:.1f} m</td>
                </tr>
                <tr>
                    <td>Image Contrast</td>
                    <td>{wave.contrast:.3f}</td>
                </tr>
        """

        if inv is not None:
            html += f"""
                <tr bgcolor="#d4efdf">
                    <td colspan="2" style="text-align: center;"><b>Inverted Parameters</b></td>
                </tr>
                <tr>
                    <td>Amplitude</td>
                    <td><b>{inv.amplitude:.2f} m</b></td>
                </tr>
                <tr bgcolor="#eaf2f8">
                    <td>Half-Width</td>
                    <td>{inv.half_width:.1f} m</td>
                </tr>
                <tr>
                    <td>Phase Speed</td>
                    <td>{inv.phase_speed:.2f} m/s</td>
                </tr>
                <tr bgcolor="#eaf2f8">
                    <td>Wave Energy</td>
                    <td>{inv.wave_energy:.2e} J/m</td>
                </tr>
                <tr>
                    <td>Inversion Method</td>
                    <td>{inv.inverse_method}</td>
                </tr>
                <tr bgcolor="#eaf2f8">
                    <td>Inversion Confidence</td>
                    <td>{inv.confidence:.2f}</td>
                </tr>
            """

        html += """
            </table>
        </div>
        ]]>
        """
        return html

    def _build_wavefront_description(self, wavefront: Any, inv: Optional[Any]) -> str:
        """
        Build HTML description for wavefront.

        Args:
            wavefront: Wavefront data
            inv: Inverted wave data (optional)

        Returns:
            HTML description string
        """
        front_type = "Bright" if wavefront.is_bright else "Dark"
        html = f"""
        <![CDATA[
        <div style="font-family: Arial, sans-serif; padding: 10px;">
            <h3 style="color: #1a5276; margin-top: 0;">Wavefront #{wavefront.wavefront_id}</h3>
            <table border="0" cellpadding="4" cellspacing="0">
                <tr bgcolor="#eaf2f8">
                    <td><b>Parameter</b></td>
                    <td><b>Value</b></td>
                </tr>
                <tr>
                    <td>Type</td>
                    <td>{front_type} Front</td>
                </tr>
                <tr bgcolor="#eaf2f8">
                    <td>Length</td>
                    <td>{wavefront.length:.1f} px</td>
                </tr>
                <tr>
                    <td>Direction</td>
                    <td>{wavefront.direction:.1f}°</td>
                </tr>
                <tr bgcolor="#eaf2f8">
                    <td>Curvature</td>
                    <td>{wavefront.curvature:.6f}</td>
                </tr>
                <tr>
                    <td>Associated Wave</td>
                    <td>#{wavefront.associated_wave_id if wavefront.associated_wave_id is not None else 'None'}</td>
                </tr>
            </table>
        </div>
        ]]>
        """
        return html

    def _add_legend(self, kml: simplekml.Kml) -> None:
        """
        Add legend/description screen overlay to KML.

        Args:
            kml: KML object
        """
        legend_html = """
        <div style="position: absolute; bottom: 10px; left: 10px;
                    background: rgba(255,255,255,0.9); padding: 10px;
                    border-radius: 5px; font-family: Arial, sans-serif;
                    font-size: 12px;">
            <b>Legend:</b><br>
            <span style="color: green;">●</span> Bright wavefront<br>
            <span style="color: red;">●</span> Dark wavefront<br>
            <span style="color: #00ff00;">●</span> High confidence wave<br>
            <span style="color: #ffff00;">●</span> Medium confidence wave<br>
            <span style="color: #ff8c00;">●</span> Low confidence wave<br>
            <span style="color: #ff0000;">●</span> Very low confidence wave
        </div>
        """

        screen = kml.newscreenoverlay()
        screen.name = "Legend"
        screen.overlayxy = simplekml.OverlayXY(x=0, y=0, xunits=simplekml.Units.fraction,
                                                yunits=simplekml.Units.fraction)
        screen.screenxy = simplekml.ScreenXY(x=0.02, y=0.02, xunits=simplekml.Units.fraction,
                                              yunits=simplekml.Units.fraction)
        screen.size = simplekml.Size(x=0, y=0, xunits=simplekml.Units.pixels,
                                     yunits=simplekml.Units.pixels)
        screen.description = legend_html

    def _get_color_by_confidence(self, confidence: float) -> str:
        """
        Get KML color based on confidence value.

        Args:
            confidence: Confidence value (0-1)

        Returns:
            SimpleKML color string
        """
        if confidence > 0.7:
            return simplekml.Color.green
        elif confidence > 0.4:
            return simplekml.Color.yellow
        elif confidence > 0.2:
            return simplekml.Color.orange
        else:
            return simplekml.Color.red

    def export_geojson(self, geotiff_data: Any, detection_result: Any,
                       inversion_result: Any,
                       wavefront_result: Optional[Any] = None,
                       output_path: str = 'output.geojson') -> str:
        """
        Export results to GeoJSON format.

        Args:
            geotiff_data: GeoTIFF data
            detection_result: Detection result
            inversion_result: Inversion result
            wavefront_result: Optional wavefront result
            output_path: Output path

        Returns:
            Path to saved GeoJSON file
        """
        features = []

        inverted_dict = {inv.wave_id: inv for inv in inversion_result.inverted_waves}

        for wave in detection_result.waves:
            lon, lat = wave.center_geo(geotiff_data)
            inv = inverted_dict.get(wave.wave_id)

            properties = {
                'type': 'wave_center',
                'wave_id': wave.wave_id,
                'direction': wave.direction,
                'wavelength': wave.wavelength,
                'spacing': wave.spacing,
                'contrast': wave.contrast,
                'detection_confidence': wave.confidence,
            }

            if inv is not None:
                properties.update({
                    'amplitude': inv.amplitude,
                    'half_width': inv.half_width,
                    'phase_speed': inv.phase_speed,
                    'wave_energy': inv.wave_energy,
                    'inversion_confidence': inv.confidence,
                })

            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [lon, lat]
                },
                'properties': properties
            }
            features.append(feature)

        if wavefront_result is not None:
            for wf in wavefront_result.wavefronts:
                geo_points = wf.get_points_geo(geotiff_data)
                if len(geo_points) < 2:
                    continue

                coords = [[lon, lat] for lon, lat in geo_points]

                feature = {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': coords
                    },
                    'properties': {
                        'type': 'wavefront',
                        'wavefront_id': wf.wavefront_id,
                        'is_bright': wf.is_bright,
                        'length': wf.length,
                        'direction': wf.direction,
                        'curvature': wf.curvature,
                        'associated_wave_id': wf.associated_wave_id
                    }
                }
                features.append(feature)

        geojson = {
            'type': 'FeatureCollection',
            'features': features
        }

        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(geojson, f, indent=2)

        logger.info(f"GeoJSON saved: {output_path}")
        return output_path
