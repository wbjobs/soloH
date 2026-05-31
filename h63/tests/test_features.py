import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pytest

from eddytester.features import (
    ImpedanceFeatures,
    MultiFrequencyFusion,
    FeatureExtractor
)
from eddytester.data_io import EddyCurrentData


@pytest.fixture
def sample_impedance():
    np.random.seed(42)
    n_samples = 500
    n_freqs = 4
    
    t = np.linspace(0, 1, n_samples)
    impedance = np.zeros((n_samples, n_freqs), dtype=complex)
    
    for i in range(n_freqs):
        real = np.sin(2 * np.pi * (i + 1) * t) + 0.1 * np.random.randn(n_samples)
        imag = np.cos(2 * np.pi * (i + 1) * t) + 0.1 * np.random.randn(n_samples)
        impedance[:, i] = real + 1j * imag
    
    return impedance


@pytest.fixture
def sample_data(sample_impedance):
    return EddyCurrentData(
        impedance=sample_impedance,
        frequencies=[10e3, 50e3, 100e3, 200e3],
        positions=np.linspace(0, 0.1, 500).reshape(-1, 1)
    )


@pytest.fixture
def sample_dataset(sample_impedance):
    n_samples = 20
    n_points, n_freqs = sample_impedance.shape
    
    dataset = np.zeros((n_samples, n_points, n_freqs), dtype=complex)
    for i in range(n_samples):
        phase_shift = np.random.uniform(0, 2 * np.pi)
        dataset[i] = sample_impedance * np.exp(1j * phase_shift)
    
    return dataset


def test_extract_amplitude(sample_impedance):
    amp = ImpedanceFeatures.extract_amplitude(sample_impedance)
    assert amp.shape == sample_impedance.shape
    assert np.all(amp >= 0)
    assert np.allclose(amp, np.abs(sample_impedance))


def test_extract_phase(sample_impedance):
    phase = ImpedanceFeatures.extract_phase(sample_impedance)
    assert phase.shape == sample_impedance.shape
    assert np.all(phase >= -np.pi)
    assert np.all(phase <= np.pi)


def test_extract_phase_degrees(sample_impedance):
    phase_deg = ImpedanceFeatures.extract_phase_degrees(sample_impedance)
    assert phase_deg.shape == sample_impedance.shape
    assert np.all(phase_deg >= -180)
    assert np.all(phase_deg <= 180)


def test_extract_rotating_phase(sample_impedance):
    r_phase = ImpedanceFeatures.extract_rotating_phase(sample_impedance, reference_idx=0)
    assert r_phase.shape == sample_impedance.shape
    assert r_phase[0, 0] == 0


def test_extract_trajectory_length(sample_impedance):
    length = ImpedanceFeatures.extract_trajectory_length(sample_impedance)
    assert length.shape == sample_impedance.shape
    assert np.all(length >= 0)


def test_extract_derivatives(sample_impedance):
    d1 = ImpedanceFeatures.extract_derivatives(sample_impedance, order=1)
    d2 = ImpedanceFeatures.extract_derivatives(sample_impedance, order=2)
    
    assert d1.shape == sample_impedance.shape
    assert d2.shape == sample_impedance.shape
    assert np.iscomplexobj(d1)
    assert np.iscomplexobj(d2)


def test_extract_statistical_features(sample_impedance):
    stats = ImpedanceFeatures.extract_statistical_features(sample_impedance)
    assert stats.ndim == 1
    assert len(stats) == 4 * 4 * 9


def test_extract_spectral_features(sample_impedance):
    spec = ImpedanceFeatures.extract_spectral_features(sample_impedance)
    assert spec.ndim == 1
    assert len(spec) == 4 * 2 * 3


def test_multifrequency_fusion(sample_data, sample_dataset):
    fusion = MultiFrequencyFusion(n_components=3)
    fused = fusion.fit_transform(sample_dataset)
    
    assert fused.shape == (20, 3)
    assert fusion.fitted == True
    
    var_ratio = fusion.get_explained_variance_ratio()
    assert len(var_ratio) == 3
    assert np.all(var_ratio >= 0)
    assert np.sum(var_ratio) <= 1.0


def test_multifrequency_fusion_transform(sample_data, sample_dataset):
    fusion = MultiFrequencyFusion(n_components=3)
    fusion.fit(sample_dataset)
    
    fused = fusion.transform(sample_dataset)
    assert fused.shape == (20, 3)


def test_multifrequency_fusion_not_fitted(sample_data):
    fusion = MultiFrequencyFusion(n_components=3)
    with pytest.raises(ValueError, match='not fitted'):
        fusion.transform(sample_data)


def test_feature_extractor_extract(sample_data):
    extractor = FeatureExtractor()
    features = extractor.extract(sample_data)
    
    assert 'amplitude' in features
    assert 'phase' in features
    assert 'phase_degrees' in features
    assert 'rotating_phase' in features
    assert 'derivative_1st' in features
    assert 'derivative_2nd' in features
    assert 'trajectory_length' in features
    assert 'fused' in features
    
    assert features['amplitude'].shape == sample_data.impedance.shape
    assert features['phase'].shape == sample_data.impedance.shape


def test_feature_extractor_for_classification(sample_data):
    extractor = FeatureExtractor()
    features = extractor.extract_for_classification(sample_data, window_size=50, step=25)
    
    assert features.ndim == 2
    assert features.shape[1] == 4 * 16


def test_feature_extractor_extract_single(sample_data):
    extractor = FeatureExtractor()
    features = extractor.extract_single(sample_data)
    
    assert features.ndim == 1
    assert len(features) > 0


def test_feature_extractor_no_statistics(sample_data):
    extractor = FeatureExtractor(include_statistics=False)
    features = extractor.extract(sample_data)
    
    assert 'statistics' not in features
    assert 'spectral' not in features


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
