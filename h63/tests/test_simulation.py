import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pytest
import tempfile
import os

from eddytester.simulation import (
    EddyCurrentSimulator,
    CrackParams,
    MaterialParams,
    ProbeParams,
    MultiMaterialSimulator,
    generate_standard_dataset
)
from eddytester.config import Config


@pytest.fixture
def simulator():
    material = MaterialParams(conductivity=Config.CONDUCTIVITY_AL)
    probe = ProbeParams()
    return EddyCurrentSimulator(material=material, probe=probe, random_seed=42)


def test_crack_params():
    crack = CrackParams(depth=1.0e-3, length=10e-3, position=0.5)
    assert crack.depth == 1.0e-3
    assert crack.length == 10e-3
    assert crack.position == 0.5
    assert crack.width == 0.1e-3


def test_material_params():
    material = MaterialParams()
    assert material.conductivity == Config.CONDUCTIVITY_AL
    assert material.permeability == Config.PERMEABILITY
    assert material.thickness == 2.0e-3


def test_probe_params():
    probe = ProbeParams()
    assert probe.coil_radius == 1.0e-3
    assert probe.coil_turns == 100
    assert len(probe.operating_frequencies) == 4


def test_simulator_skin_depth(simulator):
    skin_depth = simulator._calculate_skin_depth(100e3)
    assert skin_depth > 0
    assert skin_depth < 1e-2


def test_simulator_baseline_impedance(simulator):
    Z = simulator._calculate_impedance_baseline(100e3)
    assert isinstance(Z, complex)
    assert Z.real > 0
    assert Z.imag > 0


def test_simulate_scan_no_crack(simulator):
    data = simulator.simulate_scan(
        n_points=500,
        crack=None,
        add_noise=False,
        add_lift_off_variation=False
    )
    
    assert data.impedance.shape == (500, 4)
    assert np.iscomplexobj(data.impedance)
    assert data.positions is not None
    assert data.labels is None
    assert data.metadata['simulated'] == True


def test_simulate_scan_with_crack(simulator):
    crack = CrackParams(depth=1.0e-3, length=10e-3, position=0.5)
    
    data = simulator.simulate_scan(
        n_points=500,
        crack=crack,
        add_noise=True,
        add_lift_off_variation=True
    )
    
    assert data.impedance.shape == (500, 4)
    assert data.labels is not None
    assert data.labels.shape == (500, 4)
    assert np.max(data.labels[:, 0]) == 1
    assert np.max(data.labels[:, 1]) == crack.depth
    assert np.max(data.labels[:, 2]) == crack.length


def test_generate_dataset(simulator):
    datasets = simulator.generate_dataset(
        n_samples=20,
        n_points=100,
        no_crack_ratio=0.3,
        seed=42
    )
    
    assert len(datasets) == 20
    for d in datasets:
        assert d.impedance.shape == (100, 4)
    
    n_with_crack = sum(1 for d in datasets if d.labels is not None and np.max(d.labels[:, 0]) > 0)
    n_no_crack = sum(1 for d in datasets if d.labels is None or np.max(d.labels[:, 0]) == 0)
    assert n_with_crack + n_no_crack == 20
    assert n_no_crack >= 0


def test_generate_dataset_array(simulator):
    X, y = simulator.generate_dataset_array(n_samples=10, n_points=100, seed=42)
    
    assert X.shape == (10, 100, 4)
    assert y.shape == (10, 4)
    assert np.iscomplexobj(X)


def test_multi_material_simulator():
    simulator = MultiMaterialSimulator(random_seed=42)
    datasets = simulator.generate_multi_material_dataset(
        n_samples_per_material=5,
        n_points=100
    )
    
    assert len(datasets) == 20
    materials = set(d.metadata.get('material') for d in datasets)
    assert materials.issubset({'aluminum', 'steel', 'copper', 'brass'})


def test_generate_standard_dataset():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, 'dataset.npz')
        
        dataset = generate_standard_dataset(
            save_path=filepath,
            n_train=10,
            n_test=5,
            n_points=100
        )
        
        assert 'train' in dataset
        assert 'test' in dataset
        
        X_train, y_train = dataset['train']
        X_test, y_test = dataset['test']
        
        assert X_train.shape == (10, 100, 4)
        assert y_train.shape == (10, 4)
        assert X_test.shape == (5, 100, 4)
        assert y_test.shape == (5, 4)
        
        assert os.path.exists(filepath)


def test_crack_perturbation(simulator):
    crack = CrackParams(depth=1.0e-3, length=10e-3, position=0.5)
    
    delta_Z_near = simulator._calculate_crack_perturbation(100e3, crack, 0.5, 0.1)
    delta_Z_far = simulator._calculate_crack_perturbation(100e3, crack, 0.1, 0.1)
    
    assert isinstance(delta_Z_near, complex)
    assert abs(delta_Z_near) > abs(delta_Z_far)


def test_noise_addition(simulator):
    data_noisy = simulator.simulate_scan(
        n_points=100,
        crack=None,
        add_noise=True,
        add_lift_off_variation=False,
    )
    
    data_clean = simulator.simulate_scan(
        n_points=100,
        crack=None,
        add_noise=False,
        add_lift_off_variation=False,
    )
    
    assert np.std(data_noisy.impedance) > np.std(data_clean.impedance)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
