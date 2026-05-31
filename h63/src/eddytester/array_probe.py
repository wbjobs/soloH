import numpy as np
from typing import List, Optional, Tuple, Dict, Union
from dataclasses import dataclass, field
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from .data_io import EddyCurrentData
from .config import Config
from .preprocessing import Preprocessor


@dataclass
class ArrayProbeConfig:
    n_elements: int = Config.ARRAY_N_ELEMENTS
    element_spacing: float = Config.ARRAY_SPACING
    operating_frequencies: List[float] = field(default_factory=lambda: Config.DEFAULT_FREQUENCIES)
    probe_width: float = 0.0

    def __post_init__(self):
        self.probe_width = (self.n_elements - 1) * self.element_spacing


@dataclass
class ArrayScanData:
    impedance: np.ndarray
    positions: np.ndarray
    frequencies: List[float]
    probe_config: ArrayProbeConfig
    timestamps: Optional[np.ndarray] = None
    labels: Optional[np.ndarray] = None
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if self.impedance.ndim != 4:
            raise ValueError(
                f"Array impedance must be 4D: (n_scans, n_elements, n_positions, n_freqs), "
                f"got {self.impedance.ndim}D"
            )

    @property
    def shape(self) -> Tuple:
        return self.impedance.shape

    @property
    def n_scans(self) -> int:
        return self.impedance.shape[0]

    @property
    def n_elements(self) -> int:
        return self.impedance.shape[1]

    @property
    def n_positions(self) -> int:
        return self.impedance.shape[2]

    @property
    def n_freqs(self) -> int:
        return self.impedance.shape[3]

    def to_eddy_current_data(self, element_idx: int = 0) -> EddyCurrentData:
        if element_idx >= self.n_elements:
            raise ValueError(f"Element index {element_idx} out of range (0-{self.n_elements-1})")
        
        impedance_2d = self.impedance[0, element_idx, :, :]
        
        return EddyCurrentData(
            impedance=impedance_2d,
            frequencies=self.frequencies,
            positions=self.positions.reshape(-1, 1) if self.positions.ndim == 1 else self.positions,
            timestamps=self.timestamps,
            labels=self.labels,
            metadata={**self.metadata, 'element_idx': element_idx}
        )


class ArrayDataLoader:
    @staticmethod
    def load_numpy(filepath: Union[str, Path]) -> ArrayScanData:
        filepath = Path(filepath)
        data = np.load(filepath, allow_pickle=True)
        
        if isinstance(data, np.ndarray):
            impedance = data
            positions = np.arange(impedance.shape[2])
            frequencies = Config.DEFAULT_FREQUENCIES
            probe_config = ArrayProbeConfig(n_elements=impedance.shape[1])
        else:
            impedance = data['impedance']
            positions = data.get('positions', np.arange(impedance.shape[2]))
            frequencies = data.get('frequencies', Config.DEFAULT_FREQUENCIES).tolist()
            probe_config = ArrayProbeConfig(
                n_elements=data.get('n_elements', impedance.shape[1]),
                element_spacing=data.get('element_spacing', Config.ARRAY_SPACING),
                operating_frequencies=frequencies
            )
        
        return ArrayScanData(
            impedance=impedance,
            positions=positions,
            frequencies=frequencies,
            probe_config=probe_config,
            metadata={'source': str(filepath)}
        )

    @staticmethod
    def save_numpy(data: ArrayScanData, filepath: Union[str, Path]) -> None:
        filepath = Path(filepath)
        np.savez(
            filepath,
            impedance=data.impedance,
            positions=data.positions,
            frequencies=np.array(data.frequencies),
            n_elements=data.n_elements,
            element_spacing=data.probe_config.element_spacing,
            timestamps=data.timestamps,
            labels=data.labels
        )


class ArrayDataFusion:
    def __init__(self, probe_config: ArrayProbeConfig):
        self.probe_config = probe_config
        self.fusion_weights = None

    def fit(self, array_data: ArrayScanData) -> 'ArrayDataFusion':
        n_elements = array_data.n_elements
        self.fusion_weights = np.ones(n_elements) / n_elements
        return self

    def transform(self, array_data: ArrayScanData) -> np.ndarray:
        if self.fusion_weights is None:
            raise ValueError("Fusion model not fitted. Call fit() first.")
        
        weighted_impedance = np.zeros_like(array_data.impedance)
        for i in range(array_data.n_elements):
            weighted_impedance[:, i, :, :] = array_data.impedance[:, i, :, :] * self.fusion_weights[i]
        
        fused = np.sum(weighted_impedance, axis=1)
        return fused

    def fit_transform(self, array_data: ArrayScanData) -> np.ndarray:
        return self.fit(array_data).transform(array_data)

    def dynamic_fusion(self, array_data: ArrayScanData, snr_weighting: bool = True) -> np.ndarray:
        n_scans, n_elements, n_pos, n_freqs = array_data.shape
        fused = np.zeros((n_scans, n_pos, n_freqs), dtype=complex)
        
        for s in range(n_scans):
            for p in range(n_pos):
                for f in range(n_freqs):
                    signals = array_data.impedance[s, :, p, f]
                    
                    if snr_weighting:
                        amplitudes = np.abs(signals)
                        noise_est = np.std(amplitudes)
                        if noise_est > 0:
                            weights = amplitudes / (noise_est + 1e-10)
                        else:
                            weights = np.ones_like(amplitudes)
                        weights /= np.sum(weights)
                    else:
                        weights = np.ones(n_elements) / n_elements
                    
                    fused[s, p, f] = np.sum(signals * weights)
        
        return fused


class CScanImaging:
    def __init__(self,
                 pixel_size: float = Config.C_SCAN_PIXEL_SIZE,
                 color_map: str = Config.CSCAN_COLOR_MAP):
        self.pixel_size = pixel_size
        self.color_map = color_map
        self.cscan_data = None
        self.x_grid = None
        self.y_grid = None

    def generate_cscan(self,
                       array_data: ArrayScanData,
                       scan_direction: str = 'x',
                       quantity: str = 'amplitude',
                       freq_idx: int = 0,
                       scan_idx: int = 0) -> Dict:
        n_elements = array_data.n_elements
        n_positions = array_data.n_positions
        element_spacing = array_data.probe_config.element_spacing
        
        positions = array_data.positions.flatten()
        scan_length = positions[-1] - positions[0]
        
        probe_width = (n_elements - 1) * element_spacing
        
        if scan_direction == 'x':
            nx = int(np.ceil(scan_length / self.pixel_size)) + 1
            ny = int(np.ceil(probe_width / self.pixel_size)) + 1
            self.x_grid = np.linspace(positions[0], positions[-1], nx)
            self.y_grid = np.linspace(-probe_width / 2, probe_width / 2, ny)
        else:
            ny = int(np.ceil(scan_length / self.pixel_size)) + 1
            nx = int(np.ceil(probe_width / self.pixel_size)) + 1
            self.y_grid = np.linspace(positions[0], positions[-1], ny)
            self.x_grid = np.linspace(-probe_width / 2, probe_width / 2, nx)
        
        self.cscan_data = np.zeros((ny, nx))
        
        impedance = array_data.impedance[scan_idx, :, :, freq_idx]
        
        if quantity == 'amplitude':
            signal_data = np.abs(impedance)
        elif quantity == 'phase':
            signal_data = np.angle(impedance)
        elif quantity == 'real':
            signal_data = np.real(impedance)
        elif quantity == 'imag':
            signal_data = np.imag(impedance)
        else:
            raise ValueError(f"Unknown quantity: {quantity}")
        
        from scipy.interpolate import griddata
        
        points = []
        values = []
        
        for elem_idx in range(n_elements):
            elem_y = (elem_idx - (n_elements - 1) / 2) * element_spacing
            
            for pos_idx in range(n_positions):
                scan_x = positions[pos_idx]
                if scan_direction == 'x':
                    points.append((scan_x, elem_y))
                else:
                    points.append((elem_y, scan_x))
                values.append(signal_data[elem_idx, pos_idx])
        
        points = np.array(points)
        values = np.array(values)
        
        X, Y = np.meshgrid(self.x_grid, self.y_grid)
        xi = np.vstack([X.ravel(), Y.ravel()]).T
        
        self.cscan_data = griddata(points, values, xi, method='cubic', fill_value=np.nan)
        self.cscan_data = self.cscan_data.reshape((ny, nx))
        
        return {
            'cscan': self.cscan_data,
            'x_grid': self.x_grid,
            'y_grid': self.y_grid,
            'quantity': quantity,
            'frequency': array_data.frequencies[freq_idx]
        }

    def plot_cscan(self,
                   cscan_result: Dict,
                   title: str = None,
                   show: bool = True,
                   save_path: Optional[Union[str, Path]] = None) -> plt.Figure:
        fig, ax = plt.subplots(figsize=(10, 8))
        
        data = cscan_result['cscan']
        x_grid = cscan_result['x_grid']
        y_grid = cscan_result['y_grid']
        quantity = cscan_result['quantity']
        freq = cscan_result['frequency']
        
        im = ax.pcolormesh(x_grid * 1000, y_grid * 1000, data,
                           cmap=self.color_map, shading='auto')
        
        ax.set_xlabel('X Position (mm)')
        ax.set_ylabel('Y Position (mm)')
        
        if title is None:
            title = f'C-Scan - {quantity.capitalize()} @ {freq/1000:.1f} kHz'
        ax.set_title(title)
        
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label(f'{quantity.capitalize()}')
        
        ax.set_aspect('equal')
        
        if save_path is not None:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        
        if show:
            plt.show()
        
        return fig

    def detect_cracks_in_cscan(self,
                               cscan_result: Dict,
                               threshold_sigma: float = 3.0,
                               min_pixels: int = 5) -> List[Dict]:
        data = cscan_result['cscan']
        valid_mask = ~np.isnan(data)
        
        if not np.any(valid_mask):
            return []
        
        valid_data = data[valid_mask]
        mean_val = np.mean(valid_data)
        std_val = np.std(valid_data)
        threshold = mean_val + threshold_sigma * std_val
        
        binary_map = data > threshold
        
        from scipy.ndimage import label, find_objects
        
        labeled, num_regions = label(binary_map)
        regions = find_objects(labeled)
        
        cracks = []
        for i, region in enumerate(regions):
            region_data = data[region]
            region_size = np.sum(~np.isnan(region_data))
            
            if region_size < min_pixels:
                continue
            
            max_val = np.nanmax(region_data)
            
            x_coords = self.x_grid[region[1]]
            y_coords = self.y_grid[region[0]]
            
            cracks.append({
                'crack_id': i,
                'bbox_x': [x_coords[0], x_coords[-1]],
                'bbox_y': [y_coords[0], y_coords[-1]],
                'max_value': float(max_val),
                'area_pixels': int(region_size),
                'confidence': float(min(1.0, (max_val - mean_val) / (threshold_sigma * std_val)))
            })
        
        return cracks


class ArrayPreprocessor:
    def __init__(self,
                 element_wise_preprocessor: Optional[Preprocessor] = None,
                 fusion: Optional[ArrayDataFusion] = None):
        self.element_wise_preprocessor = element_wise_preprocessor or Preprocessor()
        self.fusion = fusion

    def process(self, array_data: ArrayScanData) -> ArrayScanData:
        processed_impedance = np.zeros_like(array_data.impedance)
        
        for s in range(array_data.n_scans):
            for e in range(array_data.n_elements):
                element_data = EddyCurrentData(
                    impedance=array_data.impedance[s, e, :, :],
                    frequencies=array_data.frequencies,
                    positions=array_data.positions.reshape(-1, 1) if array_data.positions.ndim == 1 else array_data.positions,
                )
                
                processed = self.element_wise_preprocessor.process(element_data)
                processed_impedance[s, e, :, :] = processed.impedance
        
        return ArrayScanData(
            impedance=processed_impedance,
            positions=array_data.positions,
            frequencies=array_data.frequencies,
            probe_config=array_data.probe_config,
            timestamps=array_data.timestamps,
            labels=array_data.labels,
            metadata={**array_data.metadata, 'array_processed': True}
        )

    def process_and_fuse(self, array_data: ArrayScanData) -> np.ndarray:
        processed = self.process(array_data)
        
        if self.fusion is None:
            self.fusion = ArrayDataFusion(array_data.probe_config)
        
        return self.fusion.fit_transform(processed)


class ArraySimulator:
    def __init__(self, probe_config: Optional[ArrayProbeConfig] = None):
        self.probe_config = probe_config or ArrayProbeConfig()

    def simulate_array_scan(self,
                            n_positions: int = 200,
                            scan_length: float = 0.2,
                            crack_params: Optional[List[Dict]] = None,
                            material_conductivity: float = Config.CONDUCTIVITY_AL,
                            material_permeability: float = Config.PERMEABILITY,
                            noise_level: float = Config.SIGNAL_NOISE_LEVEL) -> ArrayScanData:
        n_elements = self.probe_config.n_elements
        n_freqs = len(self.probe_config.operating_frequencies)
        
        impedance = np.zeros((1, n_elements, n_positions, n_freqs), dtype=complex)
        positions = np.linspace(0, scan_length, n_positions)
        
        omega = np.array([2 * np.pi * f for f in self.probe_config.operating_frequencies])
        skin_depth = np.sqrt(2 / (omega * material_permeability * material_conductivity))
        
        for e in range(n_elements):
            elem_offset = (e - (n_elements - 1) / 2) * self.probe_config.element_spacing
            
            for p in range(n_positions):
                scan_pos = positions[p]
                
                for f in range(n_freqs):
                    base_real = 1.0
                    base_imag = -0.5
                    
                    if crack_params is not None:
                        for crack in crack_params:
                            crack_center = crack['center']
                            crack_length = crack['length']
                            crack_depth = crack['depth']
                            crack_y = crack.get('y', 0.0)
                            
                            dist_from_crack = abs(scan_pos - crack_center)
                            y_dist = abs(elem_offset - crack_y)
                            
                            if dist_from_crack < crack_length / 2 and y_dist < 0.01:
                                depth_factor = 1 - np.exp(-crack_depth / skin_depth[f])
                                spatial_decay = np.exp(-(dist_from_crack ** 2) / (2 * (crack_length / 4) ** 2))
                                perturbation = depth_factor * spatial_decay * 0.3
                                
                                base_real += perturbation
                                base_imag -= perturbation * 0.5
                    
                    noise = np.random.randn(2) * noise_level
                    impedance[0, e, p, f] = (base_real + noise[0]) + 1j * (base_imag + noise[1])
        
        return ArrayScanData(
            impedance=impedance,
            positions=positions,
            frequencies=self.probe_config.operating_frequencies,
            probe_config=self.probe_config,
            metadata={
                'material_conductivity': material_conductivity,
                'material_permeability': material_permeability,
                'crack_params': crack_params
            }
        )
