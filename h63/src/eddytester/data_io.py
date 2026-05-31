import numpy as np
import pandas as pd
import os
from typing import Tuple, List, Optional, Dict, Union
from pathlib import Path


class EddyCurrentData:
    def __init__(self,
                 impedance: Optional[np.ndarray] = None,
                 frequencies: Optional[List[float]] = None,
                 positions: Optional[np.ndarray] = None,
                 timestamps: Optional[np.ndarray] = None,
                 labels: Optional[np.ndarray] = None,
                 conductivity: Optional[float] = None,
                 permeability: Optional[float] = None,
                 metadata: Optional[Dict] = None):
        self.impedance = impedance
        self.frequencies = frequencies or []
        self.positions = positions
        self.timestamps = timestamps
        self.labels = labels
        self.conductivity = conductivity
        self.permeability = permeability
        self.metadata = metadata or {}
        self._normalized = False
        self._resampled = False

    @property
    def real(self) -> np.ndarray:
        if self.impedance is None:
            raise ValueError("No impedance data loaded")
        return np.real(self.impedance)

    @property
    def imag(self) -> np.ndarray:
        if self.impedance is None:
            raise ValueError("No impedance data loaded")
        return np.imag(self.impedance)

    @property
    def amplitude(self) -> np.ndarray:
        return np.abs(self.impedance)

    @property
    def phase(self) -> np.ndarray:
        return np.angle(self.impedance)

    def __repr__(self) -> str:
        shape = self.impedance.shape if self.impedance is not None else "None"
        return f"EddyCurrentData(shape={shape}, n_freqs={len(self.frequencies)})"

    def _copy_flags_from(self, other: 'EddyCurrentData') -> 'EddyCurrentData':
        self._normalized = getattr(other, '_normalized', False)
        self._resampled = getattr(other, '_resampled', False)
        return self


class DataLoader:
    @staticmethod
    def load_csv(filepath: Union[str, Path]) -> EddyCurrentData:
        df = pd.read_csv(filepath)
        impedance_cols = [c for c in df.columns if 'real' in c.lower() or 'imag' in c.lower()]
        real_cols = [c for c in impedance_cols if 'real' in c.lower()]
        imag_cols = [c for c in impedance_cols if 'imag' in c.lower()]
        
        n_freqs = max(len(real_cols), len(imag_cols))
        n_samples = len(df)
        
        impedance = np.zeros((n_samples, n_freqs), dtype=complex)
        
        for i in range(n_freqs):
            if i < len(real_cols):
                impedance[:, i] += df[real_cols[i]].values
            if i < len(imag_cols):
                impedance[:, i] += 1j * df[imag_cols[i]].values
        
        positions = None
        if 'x' in df.columns and 'y' in df.columns:
            positions = df[['x', 'y']].values
        elif 'position' in df.columns:
            positions = df['position'].values.reshape(-1, 1)
        
        labels = None
        for col in ['label', 'crack', 'crack_depth', 'crack_length', 'has_crack']:
            if col in df.columns:
                labels = df[col].values
                break
        
        frequencies = []
        freq_cols = sorted([c for c in df.columns if 'frequency_' in c.lower()])
        if freq_cols:
            for fc in freq_cols:
                frequencies.append(float(df[fc].iloc[0]))
        else:
            freq_cols_alt = [c for c in df.columns if 'freq' in c.lower() and 'frequency_' not in c.lower()]
            if freq_cols_alt:
                frequencies = df[freq_cols_alt[0]].unique().tolist()
        
        metadata = {'source': 'csv', 'filepath': str(filepath)}
        
        return EddyCurrentData(
            impedance=impedance,
            frequencies=frequencies,
            positions=positions,
            labels=labels,
            metadata=metadata
        )

    @staticmethod
    def load_numpy(filepath: Union[str, Path]) -> EddyCurrentData:
        data = np.load(filepath, allow_pickle=True).item()
        return EddyCurrentData(
            impedance=data.get('impedance'),
            frequencies=data.get('frequencies', []),
            positions=data.get('positions'),
            labels=data.get('labels'),
            metadata=data.get('metadata', {})
        )

    @staticmethod
    def load_mat(filepath: Union[str, Path]) -> EddyCurrentData:
        from scipy.io import loadmat
        mat = loadmat(filepath)
        impedance = None
        for key in ['Z', 'impedance', 'Impedance']:
            if key in mat:
                impedance = mat[key]
                if impedance.ndim == 2:
                    impedance = impedance.astype(complex)
                break
        
        frequencies = []
        for key in ['f', 'freq', 'frequencies', 'Freq']:
            if key in mat:
                frequencies = np.atleast_1d(mat[key]).flatten().tolist()
                break
        
        positions = None
        for key in ['pos', 'positions', 'x', 'X']:
            if key in mat:
                positions = mat[key]
                break
        
        labels = None
        for key in ['label', 'crack', 'y', 'Y']:
            if key in mat:
                labels = np.atleast_1d(mat[key]).flatten()
                break
        
        return EddyCurrentData(
            impedance=impedance,
            frequencies=frequencies,
            positions=positions,
            labels=labels,
            metadata={'source': 'mat', 'filepath': str(filepath)}
        )

    @staticmethod
    def load(filepath: Union[str, Path]) -> EddyCurrentData:
        ext = Path(filepath).suffix.lower()
        if ext == '.csv':
            return DataLoader.load_csv(filepath)
        elif ext == '.npy' or ext == '.npz':
            return DataLoader.load_numpy(filepath)
        elif ext == '.mat':
            return DataLoader.load_mat(filepath)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    @staticmethod
    def save(data: EddyCurrentData, filepath: Union[str, Path]) -> None:
        ext = Path(filepath).suffix.lower()
        if ext == '.npy' or ext == '.npz':
            save_data = {
                'impedance': data.impedance,
                'frequencies': data.frequencies,
                'positions': data.positions,
                'labels': data.labels,
                'metadata': data.metadata
            }
            np.save(filepath, save_data)
        elif ext == '.csv':
            df = DataLoader._to_dataframe(data)
            df.to_csv(filepath, index=False)
        else:
            raise ValueError(f"Unsupported save format: {ext}")

    @staticmethod
    def _to_dataframe(data: EddyCurrentData) -> pd.DataFrame:
        n_samples, n_freqs = data.impedance.shape
        
        data_dict = {}
        
        if data.frequencies:
            for i in range(n_freqs):
                data_dict[f'frequency_{i}'] = [data.frequencies[i]] * n_samples
        
        for i in range(n_freqs):
            freq_label = f"_{data.frequencies[i]:.0f}Hz" if data.frequencies else f"_{i}"
            data_dict[f'real{freq_label}'] = data.real[:, i]
            data_dict[f'imag{freq_label}'] = data.imag[:, i]
        
        if data.positions is not None:
            if data.positions.ndim == 1:
                data_dict['position'] = data.positions
            else:
                for j in range(data.positions.shape[1]):
                    data_dict[f'pos_{j}'] = data.positions[:, j]
        
        if data.labels is not None:
            if data.labels.ndim == 1:
                data_dict['label'] = data.labels
            else:
                for j in range(data.labels.shape[1]):
                    col_names = ['has_crack', 'crack_depth', 'crack_length', 'crack_position']
                    col_name = col_names[j] if j < len(col_names) else f'label_{j}'
                    data_dict[col_name] = data.labels[:, j]
        
        return pd.DataFrame(data_dict)

    @staticmethod
    def load_directory(dirpath: Union[str, Path]) -> List[EddyCurrentData]:
        dirpath = Path(dirpath)
        datasets = []
        for filepath in dirpath.glob('*'):
            try:
                if filepath.suffix.lower() in ['.csv', '.npy', '.npz', '.mat']:
                    datasets.append(DataLoader.load(filepath))
            except Exception as e:
                print(f"Warning: Could not load {filepath}: {e}")
        return datasets


class DataVisualizer:
    @staticmethod
    def plot_impedance(data: EddyCurrentData, freq_idx: int = 0, ax=None):
        import matplotlib.pyplot as plt
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        
        real = data.real[:, freq_idx]
        imag = data.imag[:, freq_idx]
        
        ax.plot(real, imag, 'b-', label='Impedance trajectory')
        ax.plot(real[0], imag[0], 'go', label='Start')
        ax.plot(real[-1], imag[-1], 'ro', label='End')
        
        freq_label = f"{data.frequencies[freq_idx]:.0f} Hz" if data.frequencies else f"Frequency {freq_idx}"
        ax.set_xlabel('Real (Ohm)')
        ax.set_ylabel('Imaginary (Ohm)')
        ax.set_title(f'Impedance Plane - {freq_label}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.axis('equal')
        
        return ax

    @staticmethod
    def plot_amplitude_phase(data: EddyCurrentData, freq_idx: int = 0, axes=None):
        import matplotlib.pyplot as plt
        if axes is None:
            fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        
        n_samples = data.impedance.shape[0]
        x = np.arange(n_samples)
        if data.positions is not None and data.positions.ndim >= 1:
            x = data.positions[:, 0] if data.positions.ndim > 1 else data.positions
        
        axes[0].plot(x, data.amplitude[:, freq_idx], 'b-')
        axes[0].set_ylabel('Amplitude (Ohm)')
        axes[0].grid(True, alpha=0.3)
        freq_label = f"{data.frequencies[freq_idx]:.0f} Hz" if data.frequencies else f"Frequency {freq_idx}"
        axes[0].set_title(f'Amplitude - {freq_label}')
        
        axes[1].plot(x, np.degrees(data.phase[:, freq_idx]), 'r-')
        axes[1].set_xlabel('Position' if data.positions is not None else 'Sample')
        axes[1].set_ylabel('Phase (degrees)')
        axes[1].grid(True, alpha=0.3)
        axes[1].set_title(f'Phase - {freq_label}')
        
        return axes
