"""
数据IO模块 - 支持GeoTIFF读取和ENVI格式导出
"""

import numpy as np
import rasterio
from rasterio.transform import from_origin
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import os


class GeoTIFFReader:
    """GeoTIFF格式干涉图读取器"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.dataset = None
        self.metadata = {}

    def read(self) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        读取GeoTIFF格式的干涉图

        Returns:
            (相位数据数组, 元数据字典)
        """
        with rasterio.open(self.file_path) as src:
            data = src.read(1)

            self.metadata = {
                'width': src.width,
                'height': src.height,
                'transform': src.transform,
                'crs': src.crs,
                'nodata': src.nodata,
                'dtype': src.dtypes[0],
                'resolution': (src.res[0], src.res[1]),
                'bounds': src.bounds
            }

            if self.metadata['nodata'] is not None:
                data = np.where(data == self.metadata['nodata'], np.nan, data)

        return data.astype(np.float64), self.metadata

    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        if not self.metadata:
            self.read()
        return self.metadata


class ENVIWriter:
    """ENVI格式数据写入器"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.header_path = str(Path(file_path).with_suffix('.hdr'))

    def write(self, data: np.ndarray, metadata: Optional[Dict[str, Any]] = None,
              band_names: Optional[list] = None) -> None:
        """
        将数据写入ENVI格式

        Args:
            data: 要写入的数据数组，可以是2D或3D (bands, rows, cols)
            metadata: 元数据字典
            band_names: 波段名称列表
        """
        if data.ndim == 2:
            data = data[np.newaxis, :, :]

        nbands, nrows, ncols = data.shape

        interleave = 'bil'
        dtype = self._get_envi_dtype(data.dtype)

        header_lines = []
        header_lines.append('ENVI')
        header_lines.append(f'samples = {ncols}')
        header_lines.append(f'lines = {nrows}')
        header_lines.append(f'bands = {nbands}')
        header_lines.append(f'header offset = 0')
        header_lines.append(f'file type = ENVI Standard')
        header_lines.append(f'data type = {dtype}')
        header_lines.append(f'interleave = {interleave}')
        header_lines.append(f'byte order = 0')

        if metadata is not None:
            if 'coordinate_system_string' in metadata:
                header_lines.append(f'coordinate_system_string = {metadata["coordinate_system_string"]}')
            if 'map_info' in metadata:
                header_lines.append(f'map info = {metadata["map_info"]}')
            elif 'transform' in metadata and metadata['transform'] is not None:
                transform = metadata['transform']
                pixel_size_x = abs(transform[0])
                pixel_size_y = abs(transform[4])
                ulx = transform[2]
                uly = transform[5]
                map_info = f'Geographic Lat/Lon, 1, 1, {ulx}, {uly}, {pixel_size_x}, {pixel_size_y}'
                header_lines.append(f'map info = {map_info}')

        if band_names is not None:
            header_lines.append(f'band names = {{{", ".join(band_names)}}}')

        header_lines.append('')

        with open(self.header_path, 'w') as f:
            f.write('\n'.join(header_lines))

        output_data = data.astype(self._get_numpy_dtype(dtype))
        output_data = np.transpose(output_data, (1, 0, 2))
        output_data = output_data.reshape(nrows, nbands * ncols)

        with open(self.file_path, 'wb') as f:
            output_data.tofile(f)

    @staticmethod
    def _get_envi_dtype(np_dtype: np.dtype) -> int:
        """将numpy数据类型转换为ENVI数据类型代码"""
        dtype_map = {
            np.dtype('uint8'): 1,
            np.dtype('int16'): 2,
            np.dtype('int32'): 3,
            np.dtype('float32'): 4,
            np.dtype('float64'): 5,
            np.dtype('complex64'): 6,
            np.dtype('complex128'): 9,
            np.dtype('uint16'): 12,
            np.dtype('uint32'): 13,
            np.dtype('int64'): 14,
            np.dtype('uint64'): 15,
        }
        return dtype_map.get(np_dtype, 4)

    @staticmethod
    def _get_numpy_dtype(envi_dtype: int) -> np.dtype:
        """将ENVI数据类型代码转换为numpy数据类型"""
        dtype_map = {
            1: np.dtype('uint8'),
            2: np.dtype('int16'),
            3: np.dtype('int32'),
            4: np.dtype('float32'),
            5: np.dtype('float64'),
            6: np.dtype('complex64'),
            9: np.dtype('complex128'),
            12: np.dtype('uint16'),
            13: np.dtype('uint32'),
            14: np.dtype('int64'),
            15: np.dtype('uint64'),
        }
        return dtype_map.get(envi_dtype, np.dtype('float32'))


class ENVIReader:
    """ENVI格式数据读取器"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.header_path = str(Path(file_path).with_suffix('.hdr'))
        self.header = {}

    def _parse_header(self) -> None:
        """解析ENVI头文件"""
        if not os.path.exists(self.header_path):
            raise FileNotFoundError(f"ENVI头文件不存在: {self.header_path}")

        with open(self.header_path, 'r') as f:
            content = f.read()

        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line == 'ENVI':
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                if value.startswith('{') and value.endswith('}'):
                    value = value[1:-1].split(',')
                    value = [v.strip() for v in value]
                self.header[key] = value

    def read(self) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        读取ENVI格式数据

        Returns:
            (数据数组, 元数据字典)
        """
        self._parse_header()

        ncols = int(self.header.get('samples', 0))
        nrows = int(self.header.get('lines', 0))
        nbands = int(self.header.get('bands', 0))
        dtype = int(self.header.get('data type', 4))
        interleave = self.header.get('interleave', 'bil').lower()
        offset = int(self.header.get('header offset', 0))

        np_dtype = ENVIWriter._get_numpy_dtype(dtype)

        with open(self.file_path, 'rb') as f:
            f.seek(offset)
            raw_data = np.fromfile(f, dtype=np_dtype)

        if interleave == 'bil':
            data = raw_data.reshape(nrows, nbands, ncols)
            data = np.transpose(data, (1, 0, 2))
        elif interleave == 'bip':
            data = raw_data.reshape(nrows, ncols, nbands)
            data = np.transpose(data, (2, 0, 1))
        elif interleave == 'bsq':
            data = raw_data.reshape(nbands, nrows, ncols)
        else:
            raise ValueError(f"不支持的存储格式: {interleave}")

        if nbands == 1:
            data = data[0]

        return data, self.header


def read_interferogram(file_path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    通用干涉图读取函数，自动识别格式

    Args:
        file_path: 文件路径

    Returns:
        (相位数据数组, 元数据字典)
    """
    ext = Path(file_path).suffix.lower()

    if ext in ['.tif', '.tiff', '.gtif']:
        reader = GeoTIFFReader(file_path)
        return reader.read()
    elif ext in ['.dat', '.img', '.bin']:
        reader = ENVIReader(file_path)
        return reader.read()
    else:
        try:
            reader = GeoTIFFReader(file_path)
            return reader.read()
        except Exception:
            try:
                reader = ENVIReader(file_path)
                return reader.read()
            except Exception as e:
                raise ValueError(f"不支持的文件格式: {ext}, 错误: {e}")


def write_envi(data: np.ndarray, file_path: str,
               metadata: Optional[Dict[str, Any]] = None,
               band_names: Optional[list] = None) -> None:
    """
    便捷的ENVI格式写入函数

    Args:
        data: 要写入的数据
        file_path: 输出文件路径
        metadata: 元数据字典
        band_names: 波段名称列表
    """
    writer = ENVIWriter(file_path)
    writer.write(data, metadata, band_names)


def write_geotiff(data: np.ndarray, file_path: str,
                  metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    便捷的GeoTIFF格式写入函数

    Args:
        data: 要写入的数据
        file_path: 输出文件路径
        metadata: 元数据字典
    """
    if data.ndim == 2:
        data = data[np.newaxis, :, :]

    nbands, nrows, ncols = data.shape

    transform = None
    crs = None
    nodata = None

    if metadata is not None:
        transform = metadata.get('transform', None)
        crs = metadata.get('crs', None)
        nodata = metadata.get('nodata', None)

    if transform is None:
        transform = from_origin(0, 0, 1, 1)

    with rasterio.open(
            file_path,
            'w',
            driver='GTiff',
            height=nrows,
            width=ncols,
            count=nbands,
            dtype=data.dtype,
            crs=crs,
            transform=transform,
            nodata=nodata,
    ) as dst:
        for i in range(nbands):
            dst.write(data[i], i + 1)
