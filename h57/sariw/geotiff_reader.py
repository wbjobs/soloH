import numpy as np
import rasterio
from rasterio.transform import xy, rowcol
from rasterio.warp import transform_geom, calculate_default_transform, reproject, Resampling
from pyproj import Transformer, CRS
from dataclasses import dataclass, field
from typing import Tuple, Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class GeoTIFFData:
    """Data class for storing GeoTIFF data and metadata."""
    data: np.ndarray
    transform: Any
    crs: Optional[Any]
    width: int
    height: int
    bands: int
    nodata_value: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def pixel_to_geo(self, row: int, col: int) -> Tuple[float, float]:
        """Convert pixel coordinates to geographic coordinates."""
        x, y = xy(self.transform, row, col)
        return x, y

    def geo_to_pixel(self, x: float, y: float) -> Tuple[int, int]:
        """Convert geographic coordinates to pixel coordinates."""
        row, col = rowcol(self.transform, x, y)
        return row, col

    def pixel_to_wgs84(self, row: int, col: int) -> Tuple[float, float]:
        """Convert pixel coordinates to WGS84 (lon, lat)."""
        x, y = self.pixel_to_geo(row, col)
        if self.crs is not None and self.crs.to_epsg() != 4326:
            transformer = Transformer.from_crs(self.crs, CRS.from_epsg(4326), always_xy=True)
            lon, lat = transformer.transform(x, y)
            return lon, lat
        return x, y

    def wgs84_to_pixel(self, lon: float, lat: float) -> Tuple[int, int]:
        """Convert WGS84 coordinates to pixel coordinates."""
        if self.crs is not None and self.crs.to_epsg() != 4326:
            transformer = Transformer.from_crs(CRS.from_epsg(4326), self.crs, always_xy=True)
            x, y = transformer.transform(lon, lat)
        else:
            x, y = lon, lat
        return self.geo_to_pixel(x, y)

    def get_pixel_resolution(self) -> Tuple[float, float]:
        """Get pixel resolution in meters (x, y)."""
        if self.transform is not None:
            return abs(self.transform.a), abs(self.transform.e)
        return 1.0, 1.0


class GeoTIFFReader:
    """Reader for GeoTIFF format SAR images."""

    def __init__(self, filepath: str):
        """
        Initialize GeoTIFF reader.

        Args:
            filepath: Path to the GeoTIFF file
        """
        self.filepath = filepath
        self.dataset: Optional[rasterio.DatasetReader] = None

    def open(self) -> None:
        """Open the GeoTIFF file."""
        try:
            self.dataset = rasterio.open(self.filepath)
            logger.info(f"Opened GeoTIFF: {self.filepath}")
            logger.info(f"  Dimensions: {self.dataset.width} x {self.dataset.height}")
            logger.info(f"  Bands: {self.dataset.count}")
            logger.info(f"  CRS: {self.dataset.crs}")
        except Exception as e:
            logger.error(f"Failed to open GeoTIFF: {e}")
            raise

    def close(self) -> None:
        """Close the GeoTIFF file."""
        if self.dataset is not None:
            self.dataset.close()
            self.dataset = None

    def read(self, band: int = 1) -> GeoTIFFData:
        """
        Read data from the GeoTIFF file.

        Args:
            band: Band number to read (1-indexed)

        Returns:
            GeoTIFFData object containing image data and metadata
        """
        if self.dataset is None:
            self.open()

        try:
            data = self.dataset.read(band)
            data = data.astype(np.float32)

            nodata = self.dataset.nodata
            if nodata is not None:
                data[data == nodata] = np.nan

            metadata = {
                'driver': self.dataset.driver,
                'descriptions': self.dataset.descriptions,
                'tags': self.dataset.tags(),
            }

            return GeoTIFFData(
                data=data,
                transform=self.dataset.transform,
                crs=self.dataset.crs,
                width=self.dataset.width,
                height=self.dataset.height,
                bands=self.dataset.count,
                nodata_value=nodata,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to read GeoTIFF band {band}: {e}")
            raise

    def read_all_bands(self) -> List[GeoTIFFData]:
        """
        Read all bands from the GeoTIFF file.

        Returns:
            List of GeoTIFFData objects
        """
        if self.dataset is None:
            self.open()

        return [self.read(band=i + 1) for i in range(self.dataset.count)]

    def __enter__(self) -> 'GeoTIFFReader':
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    def reproject_to_wgs84(self, output_path: str) -> None:
        """
        Reproject the GeoTIFF to WGS84 coordinate system.

        Args:
            output_path: Path for the reprojected output file
        """
        if self.dataset is None:
            self.open()

        target_crs = CRS.from_epsg(4326)
        transform, width, height = calculate_default_transform(
            self.dataset.crs, target_crs,
            self.dataset.width, self.dataset.height,
            *self.dataset.bounds
        )

        kwargs = self.dataset.meta.copy()
        kwargs.update({
            'crs': target_crs,
            'transform': transform,
            'width': width,
            'height': height
        })

        with rasterio.open(output_path, 'w', **kwargs) as dst:
            for i in range(1, self.dataset.count + 1):
                reproject(
                    source=rasterio.band(self.dataset, i),
                    destination=rasterio.band(dst, i),
                    src_transform=self.dataset.transform,
                    src_crs=self.dataset.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear
                )

        logger.info(f"Reprojected to WGS84: {output_path}")
