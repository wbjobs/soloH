import numpy as np
import pytest
from eddytester.data_io import EddyCurrentData
from eddytester.preprocessing import MaterialNormalizer, SpatialResampler, Preprocessor
from eddytester.identification import CrackIdentifier
from eddytester.config import Config
from eddytester.simulation import EddyCurrentSimulator, CrackParams


@pytest.fixture
def sample_data_with_material():
    n_samples = 200
    n_freqs = 4
    impedance = np.random.randn(n_samples, n_freqs) + 1j * np.random.randn(n_samples, n_freqs)
    positions = np.linspace(0, 100, n_samples).reshape(-1, 1)
    timestamps = np.linspace(0, 2, n_samples)
    
    return EddyCurrentData(
        impedance=impedance,
        frequencies=[10e3, 50e3, 100e3, 200e3],
        positions=positions,
        timestamps=timestamps,
        conductivity=Config.CONDUCTIVITY_STEEL,
        permeability=Config.PERMEABILITY
    )


@pytest.fixture
def uneven_sampling_data():
    n_samples = 150
    n_freqs = 4
    
    base_positions = np.linspace(0, 100, n_samples)
    noise = np.random.randn(n_samples) * 0.5
    uneven_positions = np.sort(base_positions + noise)
    
    impedance = np.zeros((n_samples, n_freqs), dtype=complex)
    for i in range(n_freqs):
        real = np.sin(uneven_positions * 0.1 + i) + np.random.randn(n_samples) * 0.1
        imag = np.cos(uneven_positions * 0.1 + i) + np.random.randn(n_samples) * 0.1
        impedance[:, i] = real + 1j * imag
    
    timestamps = np.cumsum(np.random.uniform(0.008, 0.015, n_samples))
    
    crack_labels = np.zeros((n_samples, 4))
    crack_start_idx = 50
    crack_end_idx = 80
    crack_labels[crack_start_idx:crack_end_idx, 0] = 1
    crack_labels[crack_start_idx:crack_end_idx, 1] = 1.0
    crack_labels[crack_start_idx:crack_end_idx, 2] = 10.0
    crack_labels[crack_start_idx:crack_end_idx, 3] = uneven_positions[crack_start_idx]
    
    return EddyCurrentData(
        impedance=impedance,
        frequencies=[10e3, 50e3, 100e3, 200e3],
        positions=uneven_positions.reshape(-1, 1),
        timestamps=timestamps,
        labels=crack_labels,
        conductivity=Config.CONDUCTIVITY_AL,
        permeability=Config.PERMEABILITY
    )


@pytest.fixture
def data_with_crack_edges():
    n_samples = 500
    n_freqs = 4
    positions = np.linspace(0, 200, n_samples).reshape(-1, 1)
    
    impedance = np.zeros((n_samples, n_freqs), dtype=complex)
    
    baseline_real = 1.0
    baseline_imag = 0.5
    
    crack_start = 150
    crack_end = 250
    crack_center = (crack_start + crack_end) / 2
    crack_width = crack_end - crack_start
    
    for i in range(n_freqs):
        real = np.ones(n_samples) * baseline_real
        imag = np.ones(n_samples) * baseline_imag
        
        for j in range(n_samples):
            if crack_start <= j <= crack_end:
                dist_from_center = abs(j - crack_center) / (crack_width / 2)
                gaussian = np.exp(-(dist_from_center ** 2) * 4)
                real[j] += 0.5 * gaussian
                imag[j] -= 0.3 * gaussian
        
        real += np.random.randn(n_samples) * 0.02
        imag += np.random.randn(n_samples) * 0.02
        impedance[:, i] = real + 1j * imag
    
    labels = np.zeros((n_samples, 4))
    labels[crack_start:crack_end, 0] = 1
    labels[crack_start:crack_end, 1] = 1.5
    labels[crack_start:crack_end, 2] = (positions[crack_end] - positions[crack_start])[0]
    labels[crack_start:crack_end, 3] = positions[crack_start, 0]
    
    return EddyCurrentData(
        impedance=impedance,
        frequencies=[10e3, 50e3, 100e3, 200e3],
        positions=positions,
        labels=labels,
        conductivity=Config.CONDUCTIVITY_AL,
        permeability=Config.PERMEABILITY
    )


class TestMaterialNormalizer:
    def test_fit_transform_steel_to_aluminum(self, sample_data_with_material):
        normalizer = MaterialNormalizer(
            reference_conductivity=Config.CONDUCTIVITY_AL,
            reference_permeability=Config.PERMEABILITY
        )
        
        normalized = normalizer.fit_transform(sample_data_with_material)
        
        assert normalized._normalized == True
        assert normalized.conductivity == Config.CONDUCTIVITY_AL
        assert normalized.impedance.shape == sample_data_with_material.impedance.shape
        assert np.iscomplexobj(normalized.impedance)
    
    def test_normalization_factor_calculation(self, sample_data_with_material):
        normalizer = MaterialNormalizer()
        normalizer.fit(sample_data_with_material)
        
        sigma_ratio = Config.REFERENCE_CONDUCTIVITY / Config.CONDUCTIVITY_STEEL
        expected_factor = np.sqrt(sigma_ratio)
        
        assert normalizer._normalization_factor == pytest.approx(expected_factor, rel=0.01)
    
    def test_frequency_dependent_normalization(self, sample_data_with_material):
        normalizer = MaterialNormalizer()
        normalized = normalizer.fit_transform(sample_data_with_material)
        
        original_amp = np.abs(sample_data_with_material.impedance)
        normalized_amp = np.abs(normalized.impedance)
        
        freq_ratios = normalized_amp / original_amp
        for i in range(1, len(sample_data_with_material.frequencies)):
            assert freq_ratios[:, i].mean() < freq_ratios[:, i-1].mean()
    
    def test_normalizer_not_fitted(self, sample_data_with_material):
        normalizer = MaterialNormalizer()
        
        with pytest.raises(ValueError, match='not fitted'):
            normalizer.transform(sample_data_with_material)
    
    def test_normalize_with_default_reference(self, sample_data_with_material):
        sample_data_with_material.conductivity = None
        sample_data_with_material.permeability = None
        
        normalizer = MaterialNormalizer()
        normalized = normalizer.fit_transform(sample_data_with_material)
        
        assert normalized.conductivity == Config.REFERENCE_CONDUCTIVITY
        assert normalized.permeability == Config.REFERENCE_PERMEABILITY


class TestSpatialResampler:
    def test_fix_number_of_points(self, uneven_sampling_data):
        resampler = SpatialResampler(n_points=200)
        resampled = resampler.fit_transform(uneven_sampling_data)
        
        assert resampled.impedance.shape[0] == 200
        assert resampled._resampled == True
        assert resampled.positions is not None
        assert np.all(np.diff(resampled.positions[:, 0]) > 0)
    
    def test_target_spacing(self, uneven_sampling_data):
        target_spacing = 1.0
        resampler = SpatialResampler(target_spacing=target_spacing)
        resampled = resampler.fit_transform(uneven_sampling_data)
        
        actual_spacing = np.mean(np.diff(resampled.positions[:, 0]))
        assert actual_spacing == pytest.approx(target_spacing, rel=0.1)
    
    def test_uniform_spacing_after_resampling(self, uneven_sampling_data):
        resampler = SpatialResampler(n_points=200)
        resampled = resampler.fit_transform(uneven_sampling_data)
        
        spacing = np.diff(resampled.positions[:, 0])
        spacing_std = np.std(spacing)
        
        original_spacing = np.diff(uneven_sampling_data.positions[:, 0])
        original_std = np.std(original_spacing)
        
        assert spacing_std < original_std * 0.01
    
    def test_impedance_preservation(self, uneven_sampling_data):
        resampler = SpatialResampler(n_points=150, method='linear')
        resampled = resampler.fit_transform(uneven_sampling_data)
        
        original_mean = np.mean(np.abs(uneven_sampling_data.impedance))
        resampled_mean = np.mean(np.abs(resampled.impedance))
        
        assert original_mean == pytest.approx(resampled_mean, rel=0.1)
    
    def test_label_interpolation(self, uneven_sampling_data):
        resampler = SpatialResampler(n_points=200)
        resampled = resampler.fit_transform(uneven_sampling_data)
        
        assert resampled.labels is not None
        assert resampled.labels.shape == (200, 4)
        assert np.sum(resampled.labels[:, 0] > 0.5) > 0
    
    def test_estimate_from_timestamps(self, uneven_sampling_data):
        uneven_sampling_data.positions = None
        
        resampler = SpatialResampler(n_points=100)
        resampled = resampler.fit_transform(uneven_sampling_data)
        
        assert resampled.positions is not None
        assert len(resampled.positions) == 100
    
    def test_resampler_not_fitted(self, uneven_sampling_data):
        resampler = SpatialResampler()
        
        with pytest.raises(ValueError, match='not fitted'):
            resampler.transform(uneven_sampling_data)
    
    def test_insufficient_points(self):
        n_samples = 1
        impedance = np.random.randn(n_samples, 2) + 1j * np.random.randn(n_samples, 2)
        positions = np.array([[0.0]])
        
        data = EddyCurrentData(
            impedance=impedance,
            frequencies=[10e3, 50e3],
            positions=positions
        )
        
        resampler = SpatialResampler()
        
        with pytest.raises(ValueError, match='at least 2 points'):
            resampler.fit(data)


class TestCrackEdgeDetection:
    def test_edge_detection_with_clear_crack(self, data_with_crack_edges):
        identifier = CrackIdentifier()
        crack_info = identifier._detect_crack_edges(data_with_crack_edges)
        
        assert crack_info is not None
        assert 'start_idx' in crack_info
        assert 'end_idx' in crack_info
        assert 'length' in crack_info
        assert 'confidence' in crack_info
        
        assert 100 <= crack_info['start_idx'] <= 200
        assert 200 <= crack_info['end_idx'] <= 300
        
        expected_length = data_with_crack_edges.positions[250] - data_with_crack_edges.positions[150]
        assert crack_info['length'] == pytest.approx(expected_length[0], rel=0.3)
    
    def test_edge_detection_confidence(self, data_with_crack_edges):
        identifier = CrackIdentifier()
        crack_info = identifier._detect_crack_edges(data_with_crack_edges)
        
        assert crack_info['confidence'] > 0.3
        assert crack_info['confidence'] <= 1.0
    
    def test_edge_detection_output_in_identify(self, data_with_crack_edges):
        simulator = EddyCurrentSimulator()
        train_data = simulator.generate_dataset(n_samples=30, seed=42)
        
        identifier = CrackIdentifier()
        identifier.fit(train_data, use_cnn=False)
        
        result = identifier.identify(data_with_crack_edges, use_cnn=False)
        
        assert 'crack_start_idx' in result
        assert 'crack_end_idx' in result
        assert 'estimated_length_mm' in result
        assert 'edge_confidence' in result
        assert 'crack_start_mm' in result
        assert 'crack_end_mm' in result
    
    def test_simple_fallback_when_no_edges(self):
        n_samples = 20
        n_freqs = 2
        impedance = np.ones((n_samples, n_freqs), dtype=complex) * (1 + 0.5j)
        positions = np.linspace(0, 10, n_samples).reshape(-1, 1)
        positions[10:12, 0] += 2.0
        
        data = EddyCurrentData(
            impedance=impedance,
            frequencies=[10e3, 50e3],
            positions=positions
        )
        
        identifier = CrackIdentifier()
        crack_info = identifier._detect_crack_edges(data)
        
        assert crack_info is not None
        assert 'start_idx' in crack_info
        assert 'end_idx' in crack_info
    
    def test_edge_detection_multiple_frequencies(self, data_with_crack_edges):
        identifier = CrackIdentifier()
        crack_info = identifier._detect_crack_edges(data_with_crack_edges)
        
        mean_amp = np.mean(np.abs(data_with_crack_edges.impedance), axis=1)
        expected_center = np.argmax(mean_amp)
        
        actual_center = int((crack_info['start_idx'] + crack_info['end_idx']) / 2)
        assert abs(actual_center - expected_center) < 20


class TestEnhancedPreprocessor:
    def test_preprocessor_with_all_enhancements(self, uneven_sampling_data):
        preprocessor = Preprocessor(
            material_normalizer=MaterialNormalizer(),
            spatial_resampler=SpatialResampler(n_points=200)
        )
        
        processed = preprocessor.process(uneven_sampling_data)
        
        assert processed.impedance.shape[0] == 200
        assert processed._resampled == True
        assert processed.metadata.get('preprocessed') == True
        assert processed.conductivity == Config.REFERENCE_CONDUCTIVITY
    
    def test_preprocessor_with_spatial_resampler_only(self, uneven_sampling_data):
        preprocessor = Preprocessor(
            spatial_resampler=SpatialResampler(n_points=150),
            normalize=False
        )
        
        processed = preprocessor.process(uneven_sampling_data)
        
        assert processed.impedance.shape[0] == 150
        assert processed._resampled == True
    
    def test_preprocessor_with_material_normalizer_only(self, sample_data_with_material):
        preprocessor = Preprocessor(
            material_normalizer=MaterialNormalizer(),
            normalize=False
        )
        
        processed = preprocessor.process(sample_data_with_material)
        
        assert processed.conductivity == Config.REFERENCE_CONDUCTIVITY
        assert processed.impedance.shape == sample_data_with_material.impedance.shape


class TestMultiMaterialNormalization:
    def test_aluminum_steel_consistency(self):
        simulator_al = EddyCurrentSimulator()
        crack = CrackParams(depth=1.0e-3, length=10.0e-3, position=0.5)
        
        data_al = simulator_al.simulate_scan(
            n_points=200,
            scan_length=0.2,
            crack=crack
        )
        data_al.conductivity = Config.CONDUCTIVITY_AL
        data_al.permeability = Config.PERMEABILITY
        
        simulator_steel = EddyCurrentSimulator()
        data_steel = simulator_steel.simulate_scan(
            n_points=200,
            scan_length=0.2,
            crack=crack
        )
        data_steel.conductivity = Config.CONDUCTIVITY_STEEL
        data_steel.permeability = Config.PERMEABILITY
        
        normalizer = MaterialNormalizer()
        
        norm_al = normalizer.fit_transform(data_al)
        norm_steel = normalizer.fit_transform(data_steel)
        
        al_amp = np.mean(np.abs(norm_al.impedance))
        steel_amp = np.mean(np.abs(norm_steel.impedance))
        
        assert al_amp == pytest.approx(steel_amp, rel=0.5)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
