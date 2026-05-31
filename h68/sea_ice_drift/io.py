"""
Data input/output module for SSM/I and AMSR-E brightness temperature images.

Supports reading HDF5 files with polar stereographic projection data.
"""

import os
import h5py
import numpy as np
import xarray as xr
from datetime import datetime, timedelta


class BrightnessTemperatureData:
    """
    Container for brightness temperature image data with metadata.
    
    Attributes:
        data: 2D array of brightness temperatures (K)
        lats: 2D array of latitudes
        lons: 2D array of longitudes
        timestamp: datetime object of acquisition time
        sensor: sensor type ('SSMI' or 'AMSR2')
        channel: frequency channel (e.g., '19H', '37V')
        projection: projection information
    """
    
    def __init__(self, data, lats, lons, timestamp, sensor, channel, projection=None):
        self.data = data
        self.lats = lats
        self.lons = lons
        self.timestamp = timestamp
        self.sensor = sensor
        self.channel = channel
        self.projection = projection or {}
        
    def __repr__(self):
        return (f'BrightnessTemperatureData(sensor={self.sensor}, '
                f'channel={self.channel}, shape={self.data.shape}, '
                f'time={self.timestamp})')


def read_hdf_file(filepath, sensor='SSMI', channel='19H'):
    """
    Read brightness temperature data from HDF5 file.
    
    Parameters
    ----------
    filepath : str
        Path to HDF5 file
    sensor : str
        Sensor type ('SSMI' or 'AMSR2')
    channel : str
        Frequency channel to read
        
    Returns
    -------
    BrightnessTemperatureData
        Object containing data and metadata
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f'File not found: {filepath}')
    
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext in ['.h5', '.hdf5', '.he5']:
        return _read_hdf5(filepath, sensor, channel)
    elif ext in ['.hdf', '.h4']:
        return _read_hdf4(filepath, sensor, channel)
    else:
        raise ValueError(f'Unsupported file format: {ext}')


def _read_hdf5(filepath, sensor, channel):
    """Read data from HDF5 format."""
    with h5py.File(filepath, 'r') as f:
        tb_data = None
        lats = None
        lons = None
        timestamp = None
        
        data_paths = [
            f'/{sensor}/BrightnessTemperature/{channel}',
            f'/BrightnessTemperature/{channel}',
            f'/tb/{channel}',
            '/data',
        ]
        
        lat_paths = [
            f'/{sensor}/Geolocation/latitude',
            '/Geolocation/latitude',
            '/latitude',
            '/lat',
        ]
        
        lon_paths = [
            f'/{sensor}/Geolocation/longitude',
            '/Geolocation/longitude',
            '/longitude',
            '/lon',
        ]
        
        for path in data_paths:
            if path in f:
                tb_data = f[path][:]
                break
        
        for path in lat_paths:
            if path in f:
                lats = f[path][:]
                break
        
        for path in lon_paths:
            if path in f:
                lons = f[path][:]
                break
        
        time_attrs = ['time', 'timestamp', 'acquisition_time', 'start_time']
        for attr in time_attrs:
            if attr in f.attrs:
                time_str = f.attrs[attr]
                if isinstance(time_str, bytes):
                    time_str = time_str.decode()
                try:
                    timestamp = datetime.fromisoformat(time_str)
                except ValueError:
                    try:
                        timestamp = datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S')
                    except ValueError:
                        timestamp = None
                break
        
        projection = {}
        if 'Projection' in f:
            proj_group = f['Projection']
            for key in proj_group.attrs:
                projection[key] = proj_group.attrs[key]
        
        if tb_data is None:
            raise ValueError(f'Could not find brightness temperature data for channel {channel}')
        
        if lats is None or lons is None:
            lats, lons = _generate_polar_coords(tb_data.shape, hemisphere='north')
        
        return BrightnessTemperatureData(
            data=tb_data,
            lats=lats,
            lons=lons,
            timestamp=timestamp or datetime.now(),
            sensor=sensor,
            channel=channel,
            projection=projection
        )


def _read_hdf4(filepath, sensor, channel):
    """Read data from HDF4 format using pyhdf if available."""
    try:
        from pyhdf.SD import SD, SDC
    except ImportError:
        raise ImportError('pyhdf is required for HDF4 files. Install with: pip install pyhdf')
    
    sd = SD(filepath, SDC.READ)
    
    datasets_dic = sd.datasets()
    
    tb_data = None
    lats = None
    lons = None
    timestamp = None
    
    for name in datasets_dic:
        if channel.lower() in name.lower() or 'brightness' in name.lower():
            tb_data = sd.select(name)[:]
            break
    
    for name in datasets_dic:
        if 'lat' in name.lower():
            lats = sd.select(name)[:]
        elif 'lon' in name.lower():
            lons = sd.select(name)[:]
    
    attrs = sd.attributes()
    for key in attrs:
        if 'time' in key.lower() or 'date' in key.lower():
            try:
                timestamp = datetime.fromisoformat(str(attrs[key]))
            except:
                pass
            break
    
    sd.end()
    
    if tb_data is None:
        raise ValueError(f'Could not find brightness temperature data for channel {channel}')
    
    if lats is None or lons is None:
        lats, lons = _generate_polar_coords(tb_data.shape, hemisphere='north')
    
    return BrightnessTemperatureData(
        data=tb_data,
        lats=lats,
        lons=lons,
        timestamp=timestamp or datetime.now(),
        sensor=sensor,
        channel=channel
    )


def _generate_polar_coords(shape, hemisphere='north', resolution=12.5):
    """
    Generate polar stereographic coordinates for given shape.
    
    Parameters
    ----------
    shape : tuple
        (rows, cols) of the grid
    hemisphere : str
        'north' or 'south'
    resolution : float
        Grid resolution in km
        
    Returns
    -------
    tuple
        (lats, lons) 2D arrays
    """
    rows, cols = shape
    lat_0 = 90 if hemisphere == 'north' else -90
    lon_0 = -45 if hemisphere == 'north' else 0
    
    x = np.arange(cols) - cols / 2
    y = np.arange(rows) - rows / 2
    x, y = np.meshgrid(x, y)
    
    x *= resolution * 1000
    y *= resolution * 1000
    
    from pyproj import Proj, Transformer
    
    proj_str = (f'+proj=stere +lat_0={lat_0} +lon_0={lon_0} '
                f'+lat_ts={70 if hemisphere == "north" else -70} '
                f'+k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs')
    
    proj = Proj(proj_str)
    transformer = Transformer.from_proj(proj, Proj('+proj=latlong +datum=WGS84'))
    
    lons, lats = transformer.transform(x, y)
    
    return lats, lons


def read_time_series(filepaths, sensor='SSMI', channel='19H'):
    """
    Read a time series of brightness temperature images.
    
    Parameters
    ----------
    filepaths : list
        List of file paths sorted by time
    sensor : str
        Sensor type
    channel : str
        Frequency channel
        
    Returns
    -------
    list
        List of BrightnessTemperatureData objects
    """
    images = []
    for fp in filepaths:
        img = read_hdf_file(fp, sensor, channel)
        images.append(img)
    
    images.sort(key=lambda x: x.timestamp)
    return images


def create_sample_data(shape=(200, 200), num_frames=3, save_dir='sample_data'):
    """
    Create synthetic sample data for testing.
    
    Parameters
    ----------
    shape : tuple
        (rows, cols) of each frame
    num_frames : int
        Number of time frames
    save_dir : str
        Directory to save sample HDF5 files
    """
    os.makedirs(save_dir, exist_ok=True)
    
    lats, lons = _generate_polar_coords(shape)
    
    base_background = 240 + 20 * np.sin(np.linspace(0, 2*np.pi, shape[0]))[:, np.newaxis]
    base_background = np.tile(base_background, (1, shape[1]))
    
    for t in range(num_frames):
        tb_data = base_background.copy()
        
        margin = min(30, shape[0] // 4, shape[1] // 4)
        max_r = min(20, shape[0] // 6, shape[1] // 6)
        min_r = max(5, max_r // 3)
        
        for i in range(5):
            cx = np.random.randint(margin, shape[1]-margin)
            cy = np.random.randint(margin, shape[0]-margin)
            r = np.random.randint(min_r, max_r)
            amplitude = np.random.uniform(10, 40)
            
            y, x = np.ogrid[:shape[0], :shape[1]]
            dist = np.sqrt((x - cx)**2 + (y - cy)**2)
            
            tb_data += amplitude * np.exp(-dist**2 / (2 * r**2))
        
        dx = int(t * 2)
        dy = int(t * 1)
        if dx != 0 or dy != 0:
            tb_data = np.roll(tb_data, shift=(dy, dx), axis=(0, 1))
        
        noise = np.random.normal(0, 3, tb_data.shape)
        tb_data += noise
        
        timestamp = datetime(2023, 1, 1) + timedelta(hours=12*t)
        
        filepath = os.path.join(save_dir, f'tb_frame_{t:03d}.h5')
        
        with h5py.File(filepath, 'w') as f:
            f.create_dataset('BrightnessTemperature/19H', data=tb_data)
            f.create_dataset('Geolocation/latitude', data=lats)
            f.create_dataset('Geolocation/longitude', data=lons)
            f.attrs['time'] = timestamp.isoformat()
            f.attrs['sensor'] = 'SSMI'
            
            proj_group = f.create_group('Projection')
            proj_group.attrs['proj_type'] = 'polar_stereographic'
            proj_group.attrs['hemisphere'] = 'north'
            proj_group.attrs['resolution_km'] = 12.5
        
        print(f'Created sample file: {filepath}')
    
    print(f'Sample data created in {save_dir}')
    return save_dir


if __name__ == '__main__':
    create_sample_data()
