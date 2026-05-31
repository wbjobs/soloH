import numpy as np
from numba import njit, prange
from typing import Optional, Tuple, List, Union


class ReceiverArray:
    def __init__(self, nx: int, nz: int, dx: float, dz: float, dt: float, nt: int,
                 array_type: str = 'surface',
                 rx_start: int = 0, rx_end: int = 0, rz: int = 0,
                 spacing: int = 1,
                 dtype=np.float64):
        self.nx = nx
        self.nz = nz
        self.dx = dx
        self.dz = dz
        self.dt = dt
        self.nt = nt
        self.array_type = array_type
        self.spacing = spacing
        self.dtype = dtype
        
        self.receiver_indices: List[Tuple[int, int]] = []
        self.receiver_positions: List[Tuple[float, float]] = []
        self.seismograms: dict = {}
        
        self._setup_receivers(rx_start, rx_end, rz)
        self._init_seismograms()
    
    def _setup_receivers(self, rx_start: int, rx_end: int, rz: int):
        if self.array_type == 'surface':
            self._setup_surface_array(rx_start, rx_end, rz)
        elif self.array_type == 'vertical':
            self._setup_vertical_array(rx_start, rx_end, rz)
        elif self.array_type == 'arbitrary':
            pass
        else:
            raise ValueError(f"Unknown array type: {self.array_type}")
    
    def _setup_surface_array(self, rx_start: int, rx_end: int, rz: int):
        if rx_end < rx_start:
            rx_start, rx_end = rx_end, rx_start
        
        for rx in range(rx_start, rx_end + 1, self.spacing):
            if 0 <= rx < self.nx and 0 <= rz < self.nz:
                self.receiver_indices.append((rx, rz))
                self.receiver_positions.append((rx * self.dx, rz * self.dz))
    
    def _setup_vertical_array(self, rx: int, rz_start: int, rz_end: int):
        if rz_end < rz_start:
            rz_start, rz_end = rz_end, rz_start
        
        for rz in range(rz_start, rz_end + 1, self.spacing):
            if 0 <= rx < self.nx and 0 <= rz < self.nz:
                self.receiver_indices.append((rx, rz))
                self.receiver_positions.append((rx * self.dx, rz * self.dz))
    
    def add_receiver(self, rx: int, rz: int):
        if 0 <= rx < self.nx and 0 <= rz < self.nz:
            self.receiver_indices.append((rx, rz))
            self.receiver_positions.append((rx * self.dx, rz * self.dz))
            self._init_seismograms()
    
    def add_receivers(self, positions: List[Tuple[int, int]]):
        for rx, rz in positions:
            if 0 <= rx < self.nx and 0 <= rz < self.nz:
                self.receiver_indices.append((rx, rz))
                self.receiver_positions.append((rx * self.dx, rz * self.dz))
        self._init_seismograms()
    
    def _init_seismograms(self):
        nrec = len(self.receiver_indices)
        self.seismograms = {
            'vx': np.zeros((nrec, self.nt), dtype=self.dtype),
            'vz': np.zeros((nrec, self.nt), dtype=self.dtype),
            'tau_xx': np.zeros((nrec, self.nt), dtype=self.dtype),
            'tau_zz': np.zeros((nrec, self.nt), dtype=self.dtype),
            'tau_xz': np.zeros((nrec, self.nt), dtype=self.dtype),
            'pressure': np.zeros((nrec, self.nt), dtype=self.dtype),
        }
    
    def record(self, vx: np.ndarray, vz: np.ndarray,
               tau_xx: np.ndarray, tau_zz: np.ndarray, tau_xz: np.ndarray,
               it: int) -> None:
        _record_seismogram(vx, vz, tau_xx, tau_zz, tau_xz,
                          self.receiver_indices,
                          self.seismograms['vx'],
                          self.seismograms['vz'],
                          self.seismograms['tau_xx'],
                          self.seismograms['tau_zz'],
                          self.seismograms['tau_xz'],
                          self.seismograms['pressure'],
                          it)
    
    def get_seismogram(self, component: str, 
                       receiver_idx: Optional[int] = None) -> np.ndarray:
        if component not in self.seismograms:
            raise ValueError(f"Unknown component: {component}. "
                           f"Available: {list(self.seismograms.keys())}")
        
        if receiver_idx is None:
            return self.seismograms[component]
        else:
            return self.seismograms[component][receiver_idx]
    
    def get_shot_gather(self, component: str) -> np.ndarray:
        return self.get_seismogram(component)
    
    def get_receiver_position(self, idx: int) -> Tuple[float, float]:
        return self.receiver_positions[idx]
    
    def get_time_axis(self) -> np.ndarray:
        return np.arange(self.nt) * self.dt
    
    def get_offset_axis(self, source_x: float = 0.0, 
                       source_z: float = 0.0) -> np.ndarray:
        offsets = []
        for rx, rz in self.receiver_positions:
            offset = np.sqrt((rx - source_x)**2 + (rz - source_z)**2)
            offsets.append(offset)
        return np.array(offsets)
    
    def get_midpoint_axis(self, source_x: float = 0.0) -> np.ndarray:
        midpoints = []
        for rx, _ in self.receiver_positions:
            midpoints.append((rx + source_x) / 2)
        return np.array(midpoints)
    
    def apply_agc(self, component: str, window_length: float = 0.1) -> None:
        data = self.seismograms[component]
        nrec, nt = data.shape
        window_samples = int(window_length / self.dt)
        
        for i in range(nrec):
            trace = data[i]
            energy = np.convolve(trace**2, np.ones(window_samples), mode='same')
            energy = np.sqrt(energy + 1e-20)
            data[i] = trace / energy
        
        self.seismograms[component] = data
    
    def apply_bandpass(self, component: str, fmin: float, fmax: float,
                       order: int = 4) -> None:
        from scipy import signal
        nyquist = 0.5 / self.dt
        low = fmin / nyquist
        high = fmax / nyquist
        b, a = signal.butter(order, [low, high], btype='band')
        
        data = self.seismograms[component]
        for i in range(data.shape[0]):
            data[i] = signal.filtfilt(b, a, data[i])
        
        self.seismograms[component] = data
    
    def save(self, output_dir: str, prefix: str = '') -> None:
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        for component, data in self.seismograms.items():
            filename = os.path.join(output_dir, f'{prefix}seismogram_{component}.npy')
            np.save(filename, data)
        
        positions = np.array(self.receiver_positions)
        np.save(os.path.join(output_dir, f'{prefix}receiver_positions.npy'), positions)
    
    def load(self, input_dir: str, prefix: str = '') -> None:
        import os
        
        for component in self.seismograms.keys():
            filename = os.path.join(input_dir, f'{prefix}seismogram_{component}.npy')
            if os.path.exists(filename):
                self.seismograms[component] = np.load(filename)
        
        positions_file = os.path.join(input_dir, f'{prefix}receiver_positions.npy')
        if os.path.exists(positions_file):
            positions = np.load(positions_file)
            self.receiver_positions = [tuple(pos) for pos in positions]
    
    def __len__(self) -> int:
        return len(self.receiver_indices)
    
    def __getitem__(self, idx: int) -> Tuple[int, int]:
        return self.receiver_indices[idx]


@njit(parallel=True)
def _record_seismogram(vx: np.ndarray, vz: np.ndarray,
                       tau_xx: np.ndarray, tau_zz: np.ndarray, tau_xz: np.ndarray,
                       receiver_indices: List[Tuple[int, int]],
                       rec_vx: np.ndarray, rec_vz: np.ndarray,
                       rec_tau_xx: np.ndarray, rec_tau_zz: np.ndarray, 
                       rec_tau_xz: np.ndarray, rec_pressure: np.ndarray,
                       it: int):
    nrec = len(receiver_indices)
    
    for i in prange(nrec):
        rx, rz = receiver_indices[i]
        
        if 0 <= rx < vx.shape[1] and 0 <= rz < vx.shape[0]:
            vx_val = vx[rz, rx]
            vz_val = vz[rz, rx]
            txx = tau_xx[rz, rx]
            tzz = tau_zz[rz, rx]
            txz = tau_xz[rz, rx]
            press = -(txx + tzz) / 3.0
            
            rec_vx[i, it] = vx_val
            rec_vz[i, it] = vz_val
            rec_tau_xx[i, it] = txx
            rec_tau_zz[i, it] = tzz
            rec_tau_xz[i, it] = txz
            rec_pressure[i, it] = press


class ParticleMotionRecorder:
    def __init__(self, nx: int, nz: int, dx: float, dz: float, dt: float, nt: int,
                 points: List[Tuple[int, int]], dtype=np.float64):
        self.nx = nx
        self.nz = nz
        self.dx = dx
        self.dz = dz
        self.dt = dt
        self.nt = nt
        self.dtype = dtype
        
        self.points = points
        self.point_positions = [(p[0] * dx, p[1] * dz) for p in points]
        
        n_points = len(points)
        self.vx = np.zeros((n_points, nt), dtype=dtype)
        self.vz = np.zeros((n_points, nt), dtype=dtype)
        self.displacement_x = np.zeros((n_points, nt), dtype=dtype)
        self.displacement_z = np.zeros((n_points, nt), dtype=dtype)
    
    def record(self, vx: np.ndarray, vz: np.ndarray, it: int) -> None:
        for i, (px, pz) in enumerate(self.points):
            if 0 <= px < vx.shape[1] and 0 <= pz < vx.shape[0]:
                self.vx[i, it] = vx[pz, px]
                self.vz[i, it] = vz[pz, px]
                
                if it > 0:
                    self.displacement_x[i, it] = self.displacement_x[i, it-1] + vx[pz, px] * self.dt
                    self.displacement_z[i, it] = self.displacement_z[i, it-1] + vz[pz, px] * self.dt
    
    def get_particle_motion(self, idx: int, time_window: Optional[Tuple[int, int]] = None):
        if time_window is None:
            time_window = (0, self.nt)
        
        t_start, t_end = time_window
        return (self.displacement_x[idx, t_start:t_end], 
                self.displacement_z[idx, t_start:t_end])
    
    def get_polarization_attributes(self, idx: int, 
                                    time_window: Optional[Tuple[int, int]] = None):
        dx, dz = self.get_particle_motion(idx, time_window)
        
        cov_matrix = np.cov(dx, dz)
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        
        idx_sort = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx_sort]
        eigenvectors = eigenvectors[:, idx_sort]
        
        major_axis = np.sqrt(eigenvalues[0])
        minor_axis = np.sqrt(eigenvalues[1]) if eigenvalues[1] > 0 else 0
        
        ellipticity = minor_axis / major_axis if major_axis > 0 else 0
        
        angle = np.arctan2(eigenvectors[1, 0], eigenvectors[0, 0])
        angle_deg = np.degrees(angle)
        
        rectilinearity = 1 - (eigenvalues[1] / eigenvalues[0]) if eigenvalues[0] > 0 else 0
        
        return {
            'major_axis': major_axis,
            'minor_axis': minor_axis,
            'ellipticity': ellipticity,
            'polarization_angle': angle_deg,
            'rectilinearity': rectilinearity,
            'eigenvalues': eigenvalues,
            'eigenvectors': eigenvectors
        }
    
    def get_time_axis(self) -> np.ndarray:
        return np.arange(self.nt) * self.dt
