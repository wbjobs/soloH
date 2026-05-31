import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pytest
import tempfile
import os

from eddytester.data_io import EddyCurrentData, DataLoader, DataVisualizer


@pytest.fixture
def sample_data():
    np.random.seed(42)
    n_samples = 100
    n_freqs = 4
    
    impedance = np.random.randn(n_samples, n_freqs) + 1j * np.random.randn(n_samples, n_freqs)
    positions = np.linspace(0, 0.1, n_samples).reshape(-1, 1)
    labels = np.random.randint(0, 2, n_samples)
    frequencies = [10e3, 50e3, 100e3, 200e3]
    
    return EddyCurrentData(
        impedance=impedance,
        frequencies=frequencies,
        positions=positions,
        labels=labels,
        metadata={'test': True}
    )


def test_eddy_current_data_properties(sample_data):
    assert sample_data.impedance.shape == (100, 4)
    assert sample_data.real.shape == (100, 4)
    assert sample_data.imag.shape == (100, 4)
    assert sample_data.amplitude.shape == (100, 4)
    assert sample_data.phase.shape == (100, 4)
    assert np.all(sample_data.amplitude >= 0)
    assert np.all(sample_data.phase >= -np.pi)
    assert np.all(sample_data.phase <= np.pi)


def test_eddy_current_data_repr(sample_data):
    repr_str = repr(sample_data)
    assert 'EddyCurrentData' in repr_str
    assert '(100, 4)' in repr_str
    assert '4' in repr_str


def test_data_loader_save_load_numpy(sample_data):
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, 'test_data.npy')
        DataLoader.save(sample_data, filepath)
        assert os.path.exists(filepath)
        
        loaded = DataLoader.load(filepath)
        assert loaded.impedance.shape == sample_data.impedance.shape
        assert np.allclose(loaded.impedance, sample_data.impedance)
        assert loaded.frequencies == sample_data.frequencies
        assert np.allclose(loaded.positions, sample_data.positions)


def test_data_loader_save_load_csv(sample_data):
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, 'test_data.csv')
        DataLoader.save(sample_data, filepath)
        assert os.path.exists(filepath)
        
        loaded = DataLoader.load_csv(filepath)
        assert loaded.impedance.shape == sample_data.impedance.shape
        assert loaded.frequencies == sample_data.frequencies


def test_data_loader_load_directory(sample_data):
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(3):
            filepath = os.path.join(tmpdir, f'test_data_{i}.npy')
            DataLoader.save(sample_data, filepath)
        
        datasets = DataLoader.load_directory(tmpdir)
        assert len(datasets) == 3
        for d in datasets:
            assert d.impedance.shape == (100, 4)


def test_data_loader_unsupported_format():
    with pytest.raises(ValueError, match='Unsupported file format'):
        DataLoader.load('test.txt')


def test_data_visualizer_plot_impedance(sample_data):
    import matplotlib
    matplotlib.use('Agg')
    ax = DataVisualizer.plot_impedance(sample_data, freq_idx=0)
    assert ax is not None
    assert ax.get_title() is not None


def test_data_visualizer_plot_amplitude_phase(sample_data):
    import matplotlib
    matplotlib.use('Agg')
    axes = DataVisualizer.plot_amplitude_phase(sample_data, freq_idx=0)
    assert axes is not None
    assert len(axes) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
