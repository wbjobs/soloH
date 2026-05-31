import numpy as np
from typing import List, Tuple, Dict, Optional, Union
from dataclasses import dataclass, field
from .config import Config
from .data_io import EddyCurrentData


@dataclass
class CrackParams:
    depth: float
    length: float
    width: float = 0.1e-3
    position: float = 0.5
    orientation: float = 0.0
    conductivity_ratio: float = 0.1


@dataclass
class MaterialParams:
    conductivity: float = Config.CONDUCTIVITY_AL
    permeability: float = Config.PERMEABILITY
    thickness: float = 2.0e-3


@dataclass
class ProbeParams:
    coil_radius: float = 1.0e-3
    coil_turns: int = 100
    lift_off: float = 0.1e-3
    operating_frequencies: List[float] = field(default_factory=lambda: Config.DEFAULT_FREQUENCIES)


class EddyCurrentSimulator:
    def __init__(self,
                 material: Optional[MaterialParams] = None,
                 probe: Optional[ProbeParams] = None,
                 random_seed: int = Config.RANDOM_SEED):
        self.material = material or MaterialParams()
        self.probe = probe or ProbeParams()
        self.rng = np.random.RandomState(random_seed)

    def _calculate_skin_depth(self, frequency: float) -> float:
        sigma = self.material.conductivity
        mu = self.material.permeability
        return np.sqrt(2 / (2 * np.pi * frequency * mu * sigma))

    def _calculate_impedance_baseline(self, frequency: float) -> complex:
        omega = 2 * np.pi * frequency
        mu = self.material.permeability
        sigma = self.material.conductivity
        a = self.probe.coil_radius
        N = self.probe.coil_turns
        d = self.probe.lift_off
        t = self.material.thickness
        
        skin_depth = self._calculate_skin_depth(frequency)
        k = np.sqrt(1j * omega * mu * sigma)
        
        L0 = mu * N**2 * a * (np.log(8 * a / (d + t)) - 0.5)
        R0 = omega * mu * N**2 * a**2 / (4 * (d + t))
        
        factor = 1 - np.exp(-t / skin_depth) * np.cos(t / skin_depth)
        
        Z = R0 * factor + 1j * omega * L0 * (1 - 0.5 * factor)
        
        return Z

    def _calculate_crack_perturbation(self,
                                     frequency: float,
                                     crack: CrackParams,
                                     probe_pos: float,
                                     scan_length: float) -> complex:
        omega = 2 * np.pi * frequency
        mu = self.material.permeability
        sigma = self.material.conductivity
        skin_depth = self._calculate_skin_depth(frequency)
        
        dist = abs(probe_pos - crack.position) * scan_length
        crack_half_len = crack.length / 2
        
        if dist > crack_half_len + 3 * self.probe.coil_radius:
            return 0 + 0j
        
        spatial_extent = self.probe.coil_radius + crack_half_len
        gaussian_profile = np.exp(-(dist**2) / (2 * spatial_extent**2))
        
        depth_factor = min(crack.depth / self.material.thickness, 1.0)
        depth_profile = 1 - np.exp(-crack.depth / skin_depth)
        
        width_factor = crack.width / self.probe.coil_radius
        
        crack_sigma = sigma * crack.conductivity_ratio
        sigma_contrast = sigma - crack_sigma
        
        amplitude = sigma_contrast / sigma * depth_factor * depth_profile
        amplitude *= gaussian_profile * width_factor
        
        R_perturb = amplitude * omega * mu * self.probe.coil_radius**2
        X_perturb = R_perturb * (1 - depth_factor)
        
        return R_perturb + 1j * X_perturb

    def simulate_scan(self,
                     n_points: int = 500,
                     scan_length: float = 0.1,
                     crack: Optional[CrackParams] = None,
                     add_noise: bool = True,
                     add_lift_off_variation: bool = True) -> EddyCurrentData:
        positions = np.linspace(0, 1, n_points)
        physical_positions = np.linspace(0, scan_length, n_points)
        
        n_freqs = len(self.probe.operating_frequencies)
        impedance = np.zeros((n_points, n_freqs), dtype=complex)
        
        for f_idx, freq in enumerate(self.probe.operating_frequencies):
            Z0 = self._calculate_impedance_baseline(freq)
            
            for i, pos in enumerate(positions):
                Z = Z0
                
                if crack is not None:
                    delta_Z = self._calculate_crack_perturbation(freq, crack, pos, scan_length)
                    Z = Z + delta_Z
                
                impedance[i, f_idx] = Z
        
        if add_lift_off_variation:
            impedance = self._add_lift_off_variation(impedance)
        
        if add_noise:
            impedance = self._add_noise(impedance)
        
        labels = None
        if crack is not None:
            labels = self._generate_crack_labels(positions, crack, n_points)
        
        return EddyCurrentData(
            impedance=impedance,
            frequencies=self.probe.operating_frequencies,
            positions=physical_positions.reshape(-1, 1),
            labels=labels,
            metadata={
                'simulated': True,
                'crack': crack.__dict__ if crack else None,
                'material': self.material.__dict__,
                'probe': self.probe.__dict__,
                'scan_length': scan_length,
            }
        )

    def _add_noise(self, impedance: np.ndarray) -> np.ndarray:
        noise_level = Config.SIGNAL_NOISE_LEVEL
        noise_real = self.rng.normal(0, noise_level * np.abs(impedance), impedance.shape)
        noise_imag = self.rng.normal(0, noise_level * np.abs(impedance), impedance.shape)
        return impedance + noise_real + 1j * noise_imag

    def _add_lift_off_variation(self, impedance: np.ndarray) -> np.ndarray:
        n_points, n_freqs = impedance.shape
        lift_off_level = Config.LIFTOFF_NOISE_LEVEL
        
        drift = np.linspace(0, lift_off_level, n_points)
        oscillation = 0.3 * lift_off_level * np.sin(2 * np.pi * 0.05 * np.arange(n_points))
        
        lift_off_variation = drift + oscillation
        
        for f_idx in range(n_freqs):
            Z_mean = np.mean(impedance[:, f_idx])
            direction = np.array([np.real(Z_mean), np.imag(Z_mean)])
            direction = direction / np.linalg.norm(direction) if np.linalg.norm(direction) > 0 else np.array([1, 0])
            
            real_comp = direction[0] * lift_off_variation * np.abs(Z_mean)
            imag_comp = direction[1] * lift_off_variation * np.abs(Z_mean)
            
            impedance[:, f_idx] += real_comp + 1j * imag_comp
        
        return impedance

    def _generate_crack_labels(self, positions: np.ndarray, crack: CrackParams, n_points: int) -> np.ndarray:
        labels = np.zeros((n_points, 4))
        
        crack_half_len = crack.length / (2 * 0.1)
        crack_center = crack.position
        
        in_crack = np.abs(positions - crack_center) <= crack_half_len
        
        labels[:, 0] = in_crack.astype(int)
        labels[:, 1] = crack.depth * in_crack.astype(float)
        labels[:, 2] = crack.length * in_crack.astype(float)
        labels[:, 3] = crack.position
        
        return labels

    def generate_dataset(self,
                        n_samples: int = 100,
                        n_points: int = 500,
                        crack_depth_range: Tuple[float, float] = (0.1e-3, 2.0e-3),
                        crack_length_range: Tuple[float, float] = (1.0e-3, 20.0e-3),
                        position_range: Tuple[float, float] = (0.2, 0.8),
                        no_crack_ratio: float = 0.3,
                        seed: Optional[int] = None) -> List[EddyCurrentData]:
        if seed is not None:
            self.rng = np.random.RandomState(seed)
        
        datasets = []
        
        n_no_crack = int(n_samples * no_crack_ratio)
        n_with_crack = n_samples - n_no_crack
        
        for _ in range(n_no_crack):
            data = self.simulate_scan(
                n_points=n_points,
                crack=None,
                add_noise=True,
                add_lift_off_variation=True
            )
            datasets.append(data)
        
        for _ in range(n_with_crack):
            depth = self.rng.uniform(*crack_depth_range)
            length = self.rng.uniform(*crack_length_range)
            position = self.rng.uniform(*position_range)
            width = self.rng.uniform(0.05e-3, 0.5e-3)
            conductivity_ratio = self.rng.uniform(0.01, 0.3)
            
            crack = CrackParams(
                depth=depth,
                length=length,
                width=width,
                position=position,
                conductivity_ratio=conductivity_ratio
            )
            
            data = self.simulate_scan(
                n_points=n_points,
                crack=crack,
                add_noise=True,
                add_lift_off_variation=True
            )
            datasets.append(data)
        
        self.rng.shuffle(datasets)
        
        return datasets

    def generate_dataset_array(self,
                              n_samples: int = 100,
                              n_points: int = 500,
                              **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        datasets = self.generate_dataset(n_samples=n_samples, n_points=n_points, **kwargs)
        
        n_freqs = len(self.probe.operating_frequencies)
        X = np.zeros((n_samples, n_points, n_freqs), dtype=complex)
        y = np.zeros((n_samples, 4))
        
        for i, data in enumerate(datasets):
            X[i] = data.impedance
            if data.labels is not None:
                max_idx = np.argmax(data.labels[:, 0])
                y[i, 0] = data.labels[max_idx, 0]
                y[i, 1] = data.labels[max_idx, 1]
                y[i, 2] = data.labels[max_idx, 2]
                y[i, 3] = data.labels[max_idx, 3]
        
        return X, y


class MultiMaterialSimulator:
    def __init__(self, random_seed: int = Config.RANDOM_SEED):
        self.materials = {
            'aluminum': MaterialParams(conductivity=37.7e6),
            'steel': MaterialParams(conductivity=10e6, permeability=100 * Config.PERMEABILITY),
            'copper': MaterialParams(conductivity=59.6e6),
            'brass': MaterialParams(conductivity=15.9e6),
        }
        self.rng = np.random.RandomState(random_seed)

    def generate_multi_material_dataset(self,
                                       n_samples_per_material: int = 50,
                                       n_points: int = 500) -> List[EddyCurrentData]:
        all_data = []
        
        for name, material in self.materials.items():
            probe = ProbeParams()
            simulator = EddyCurrentSimulator(material=material, probe=probe)
            
            data_list = simulator.generate_dataset(
                n_samples=n_samples_per_material,
                n_points=n_points,
                no_crack_ratio=0.3
            )
            
            for data in data_list:
                data.metadata['material'] = name
            all_data.extend(data_list)
        
        self.rng.shuffle(all_data)
        return all_data


def generate_standard_dataset(save_path: Optional[str] = None,
                             n_train: int = 200,
                             n_test: int = 50,
                             n_points: int = 500) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    simulator = EddyCurrentSimulator()
    
    X_train, y_train = simulator.generate_dataset_array(n_samples=n_train, n_points=n_points, seed=42)
    X_test, y_test = simulator.generate_dataset_array(n_samples=n_test, n_points=n_points, seed=123)
    
    result = {
        'train': (X_train, y_train),
        'test': (X_test, y_test),
    }
    
    if save_path:
        np.savez(save_path, X_train=X_train, y_train=y_train, X_test=X_test, y_test=y_test)
    
    return result
