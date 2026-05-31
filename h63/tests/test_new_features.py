import numpy as np
import pytest
import tempfile
import os
from pathlib import Path

from eddytester.config import Config
from eddytester.array_probe import (
    ArrayProbeConfig,
    ArrayScanData,
    ArraySimulator,
    ArrayDataFusion,
    CScanImaging,
    ArrayPreprocessor,
    ArrayDataLoader
)
from eddytester.streaming import (
    StreamConfig,
    StreamDataChunk,
    AlarmEvent,
    SimulatedDataSource,
    FileDataSource,
    StreamProcessor,
    ConsoleAlarmHandler,
    FileAlarmHandler,
    CallbackAlarmHandler
)
from eddytester import PINN_AVAILABLE

try:
    from eddytester.pinn_inversion import (
        PINNConfig,
        HelmholtzPDE,
        PINNNetwork,
        CrackReconstructorPINN,
        PINNInverter
    )
    _pinn_classes_available = True
except ImportError:
    _pinn_classes_available = False

from eddytester.data_io import EddyCurrentData
from eddytester.preprocessing import Preprocessor
from eddytester.simulation import EddyCurrentSimulator


@pytest.fixture
def array_simulator():
    probe_config = ArrayProbeConfig(
        n_elements=8,
        element_spacing=0.5e-3,
        operating_frequencies=[10e3, 50e3, 100e3]
    )
    return ArraySimulator(probe_config=probe_config)


@pytest.fixture
def array_data_with_crack(array_simulator):
    crack_params = [{
        'center': 0.1,
        'length': 0.02,
        'depth': 0.005,
        'y': 0.0
    }]
    
    return array_simulator.simulate_array_scan(
        n_positions=200,
        scan_length=0.2,
        crack_params=crack_params,
        noise_level=0.01
    )


@pytest.fixture
def sample_single_channel_data():
    np.random.seed(42)
    n_points = 500
    n_freqs = 4
    
    impedance = np.zeros((n_points, n_freqs), dtype=complex)
    positions = np.linspace(0, 0.2, n_points).reshape(-1, 1)
    
    for f in range(n_freqs):
        base_real = 1.0 + np.random.randn(n_points) * 0.01
        base_imag = -0.5 + np.random.randn(n_points) * 0.01
        
        crack_start, crack_end = 200, 280
        for i in range(crack_start, crack_end):
            crack_intensity = np.sin(np.pi * (i - crack_start) / (crack_end - crack_start))
            perturbation = crack_intensity * 0.3 * (1 + f / n_freqs)
            base_real[i] += perturbation
            base_imag[i] -= perturbation * 0.5
        
        impedance[:, f] = base_real + 1j * base_imag
    
    return EddyCurrentData(
        impedance=impedance,
        frequencies=Config.DEFAULT_FREQUENCIES,
        positions=positions,
        conductivity=Config.CONDUCTIVITY_AL,
        permeability=Config.PERMEABILITY
    )


class TestArrayProbeConfig:
    def test_probe_config_initialization(self):
        config = ArrayProbeConfig(n_elements=16, element_spacing=0.5e-3)
        assert config.n_elements == 16
        assert config.element_spacing == 0.5e-3
        assert config.probe_width == (16 - 1) * 0.5e-3

    def test_post_init_probe_width(self):
        config = ArrayProbeConfig(n_elements=8, element_spacing=1e-3)
        assert config.probe_width == pytest.approx(7e-3)


class TestArrayScanData:
    def test_valid_4d_array(self, array_data_with_crack):
        assert array_data_with_crack.impedance.ndim == 4
        assert array_data_with_crack.n_scans == 1
        assert array_data_with_crack.n_elements == 8
        assert array_data_with_crack.n_positions == 200
        assert array_data_with_crack.n_freqs == 3
        assert array_data_with_crack.shape == (1, 8, 200, 3)

    def test_invalid_dimensions_raises(self):
        with pytest.raises(ValueError, match="4D"):
            ArrayScanData(
                impedance=np.zeros((2, 100, 4), dtype=complex),
                positions=np.arange(100),
                frequencies=[10e3],
                probe_config=ArrayProbeConfig()
            )

    def test_to_eddy_current_data(self, array_data_with_crack):
        ec_data = array_data_with_crack.to_eddy_current_data(element_idx=0)
        assert isinstance(ec_data, EddyCurrentData)
        assert ec_data.impedance.shape == (200, 3)
        assert ec_data.metadata['element_idx'] == 0

    def test_element_index_out_of_range(self, array_data_with_crack):
        with pytest.raises(ValueError, match="out of range"):
            array_data_with_crack.to_eddy_current_data(element_idx=100)


class TestArraySimulator:
    def test_simulate_basic(self, array_simulator):
        data = array_simulator.simulate_array_scan(n_positions=100, scan_length=0.1)
        assert data.n_scans == 1
        assert data.n_elements == 8
        assert data.n_positions == 100
        assert data.n_freqs == 3
        assert data.positions[0] == 0.0
        assert data.positions[-1] == pytest.approx(0.1)

    def test_simulate_with_crack(self, array_data_with_crack):
        assert array_data_with_crack.n_positions == 200
        center_idx = np.argmin(np.abs(array_data_with_crack.positions - 0.1))
        
        crack_signal = np.abs(array_data_with_crack.impedance[0, 4, center_idx-10:center_idx+10, 0])
        baseline_signal = np.abs(array_data_with_crack.impedance[0, 4, 0:50, 0])
        
        assert np.mean(crack_signal) > np.mean(baseline_signal)

    def test_different_materials(self, array_simulator):
        data_cu = array_simulator.simulate_array_scan(
            n_positions=50,
            material_conductivity=Config.CONDUCTIVITY_CU
        )
        data_al = array_simulator.simulate_array_scan(
            n_positions=50,
            material_conductivity=Config.CONDUCTIVITY_AL
        )
        assert not np.allclose(data_cu.impedance, data_al.impedance)


class TestArrayDataFusion:
    def test_static_fusion(self, array_data_with_crack):
        fusion = ArrayDataFusion(array_data_with_crack.probe_config)
        fused = fusion.fit_transform(array_data_with_crack)
        
        assert fused.shape == (1, 200, 3)
        assert fused.ndim == 3

    def test_dynamic_fusion(self, array_data_with_crack):
        fusion = ArrayDataFusion(array_data_with_crack.probe_config)
        fused = fusion.dynamic_fusion(array_data_with_crack)
        
        assert fused.shape == (1, 200, 3)

    def test_fusion_weights_sum_to_one(self, array_data_with_crack):
        fusion = ArrayDataFusion(array_data_with_crack.probe_config)
        fusion.fit(array_data_with_crack)
        assert np.sum(fusion.fusion_weights) == pytest.approx(1.0)

    def test_fusion_not_fitted_raises(self, array_data_with_crack):
        fusion = ArrayDataFusion(array_data_with_crack.probe_config)
        with pytest.raises(ValueError, match="not fitted"):
            fusion.transform(array_data_with_crack)


class TestCScanImaging:
    def test_generate_cscan(self, array_data_with_crack):
        imager = CScanImaging(pixel_size=0.5e-3)
        result = imager.generate_cscan(
            array_data_with_crack,
            quantity='amplitude',
            freq_idx=0
        )
        
        assert 'cscan' in result
        assert 'x_grid' in result
        assert 'y_grid' in result
        assert result['cscan'].ndim == 2
        assert len(result['x_grid']) == result['cscan'].shape[1]
        assert len(result['y_grid']) == result['cscan'].shape[0]

    @pytest.mark.parametrize("quantity", ['amplitude', 'phase', 'real', 'imag'])
    def test_different_quantities(self, array_data_with_crack, quantity):
        imager = CScanImaging(pixel_size=1e-3)
        result = imager.generate_cscan(
            array_data_with_crack,
            quantity=quantity,
            freq_idx=0
        )
        assert result['quantity'] == quantity

    def test_invalid_quantity_raises(self, array_data_with_crack):
        imager = CScanImaging()
        with pytest.raises(ValueError, match="Unknown quantity"):
            imager.generate_cscan(array_data_with_crack, quantity='invalid')

    def test_detect_cracks(self, array_data_with_crack):
        imager = CScanImaging(pixel_size=0.5e-3)
        cscan_result = imager.generate_cscan(
            array_data_with_crack,
            quantity='amplitude',
            freq_idx=0
        )
        
        cracks = imager.detect_cracks_in_cscan(cscan_result, threshold_sigma=2.0)
        assert isinstance(cracks, list)
        
        if len(cracks) > 0:
            crack = cracks[0]
            assert 'crack_id' in crack
            assert 'bbox_x' in crack
            assert 'confidence' in crack
            assert 0.0 <= crack['confidence'] <= 1.0

    def test_plot_cscan_without_showing(self, array_data_with_crack):
        imager = CScanImaging(pixel_size=1e-3)
        cscan_result = imager.generate_cscan(array_data_with_crack)
        
        import matplotlib
        matplotlib.use('Agg')
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            temp_path = f.name
        
        try:
            fig = imager.plot_cscan(
                cscan_result,
                show=False,
                save_path=temp_path
            )
            assert os.path.exists(temp_path)
            assert os.path.getsize(temp_path) > 0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestArrayDataLoader:
    def test_save_and_load(self, array_data_with_crack):
        with tempfile.NamedTemporaryFile(suffix='.npz', delete=False) as f:
            temp_path = f.name
        
        try:
            ArrayDataLoader.save_numpy(array_data_with_crack, temp_path)
            loaded = ArrayDataLoader.load_numpy(temp_path)
            
            assert loaded.shape == array_data_with_crack.shape
            assert loaded.n_elements == array_data_with_crack.n_elements
            np.testing.assert_allclose(loaded.positions, array_data_with_crack.positions)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestArrayPreprocessor:
    def test_process_array(self, array_data_with_crack):
        preprocessor = ArrayPreprocessor()
        processed = preprocessor.process(array_data_with_crack)
        
        assert processed.shape == array_data_with_crack.shape
        assert processed.metadata.get('array_processed') == True

    def test_process_and_fuse(self, array_data_with_crack):
        preprocessor = ArrayPreprocessor()
        fused = preprocessor.process_and_fuse(array_data_with_crack)
        
        assert fused.ndim == 3
        assert fused.shape[0] == 1
        assert fused.shape[1] == array_data_with_crack.n_positions


class TestStreamConfig:
    def test_default_values(self):
        config = StreamConfig()
        assert config.buffer_size == Config.STREAM_BUFFER_SIZE
        assert config.overlap == Config.STREAM_OVERLAP
        assert config.alarm_threshold == Config.ALARM_THRESHOLD

    def test_custom_values(self):
        config = StreamConfig(
            buffer_size=512,
            overlap=64,
            alarm_threshold=0.9
        )
        assert config.buffer_size == 512
        assert config.overlap == 64
        assert config.alarm_threshold == 0.9


class TestAlarmEvent:
    def test_alarm_to_dict(self):
        alarm = AlarmEvent(
            alarm_id=1,
            timestamp=1234567890.0,
            chunk_id=5,
            confidence=0.95,
            position=0.123,
            crack_length=0.045,
            crack_depth=0.005,
            severity='critical',
            message='Test alarm'
        )
        
        d = alarm.to_dict()
        assert d['alarm_id'] == 1
        assert d['chunk_id'] == 5
        assert d['confidence'] == 0.95
        assert d['position'] == 0.123
        assert d['severity'] == 'critical'
        assert 'time_str' in d


class TestSimulatedDataSource:
    def test_basic_simulation(self):
        source = SimulatedDataSource(
            n_chunks=10,
            chunk_size=100,
            n_frequencies=4,
            include_cracks=False
        )
        
        chunks = []
        while not source.is_complete():
            chunk = source.read_chunk()
            if chunk:
                chunks.append(chunk)
        
        assert len(chunks) == 10
        assert chunks[0].impedance.shape == (1, 100, 4)
        assert chunks[0].chunk_id == 0

    def test_simulation_with_cracks(self):
        source = SimulatedDataSource(
            n_chunks=5,
            chunk_size=200,
            crack_probability=1.0
        )
        
        chunk = source.read_chunk()
        assert chunk is not None
        
        signal = np.abs(chunk.impedance[0, :, 0])
        has_peak = np.max(signal) > np.mean(signal) + 2 * np.std(signal)
        assert has_peak

    def test_is_complete(self):
        source = SimulatedDataSource(n_chunks=3)
        assert not source.is_complete()
        
        for _ in range(3):
            source.read_chunk()
        
        assert source.is_complete()
        assert source.read_chunk() is None


class TestFileDataSource:
    def test_chunking(self, sample_single_channel_data):
        source = FileDataSource(
            data=sample_single_channel_data,
            chunk_size=100,
            overlap=0
        )
        
        chunks = []
        while not source.is_complete():
            chunk = source.read_chunk()
            if chunk:
                chunks.append(chunk)
        
        assert len(chunks) == 5
        assert chunks[0].impedance.shape[1] == 100
        assert chunks[-1].impedance.shape[1] == 100

    def test_overlap(self, sample_single_channel_data):
        source = FileDataSource(
            data=sample_single_channel_data,
            chunk_size=100,
            overlap=50
        )
        
        chunks = []
        while not source.is_complete():
            chunk = source.read_chunk()
            if chunk:
                chunks.append(chunk)
        
        assert len(chunks) == 10
        assert chunks[0].metadata['start_idx'] == 0
        assert chunks[0].metadata['end_idx'] == 100
        assert chunks[1].metadata['start_idx'] == 50
        assert chunks[-1].metadata['start_idx'] == 450
        assert chunks[-1].metadata['end_idx'] == 500


class TestStreamProcessor:
    def test_process_single_chunk(self):
        config = StreamConfig(
            buffer_size=256,
            overlap=128,
            alarm_threshold=0.8
        )
        
        processor = StreamProcessor(config=config)
        
        impedance = np.zeros((1, 256, 4), dtype=complex)
        impedance[0, :, 0] = 1.0 + 1j * 0.5
        positions = np.linspace(0, 0.1, 256).reshape(-1, 1)
        
        chunk = StreamDataChunk(
            chunk_id=0,
            timestamp=time.time(),
            impedance=impedance,
            positions=positions
        )
        
        result = processor.process_chunk(chunk)
        assert 'chunk_id' in result
        assert result['buffer_size'] == 256

    def test_process_stream(self):
        config = StreamConfig(
            buffer_size=256,
            overlap=128,
            alarm_threshold=0.8
        )
        
        processor = StreamProcessor(config=config)
        source = SimulatedDataSource(
            n_chunks=5,
            chunk_size=100,
            include_cracks=False
        )
        
        results = processor.process_stream(source, verbose=False)
        assert len(results) == 5
        assert processor.chunk_counter == 5

    def test_alarm_triggering(self):
        config = StreamConfig(
            buffer_size=256,
            overlap=128,
            alarm_threshold=0.5
        )
        
        alarm_events = []
        
        def custom_handler(alarm):
            alarm_events.append(alarm)
        
        from eddytester.streaming import CallbackAlarmHandler
        
        processor = StreamProcessor(
            config=config,
            alarm_handlers=[CallbackAlarmHandler(custom_handler)]
        )
        
        processor.last_alarm_time = 0
        
        processor.crack_identifier.is_trained = True
        processor.crack_identifier.identify = lambda x: {
            'has_crack': True,
            'probability': 0.9,
            'position_mm': 100.0,
            'estimated_length_mm': 20.0,
            'depth_estimation': 5.0
        }
        
        impedance = np.zeros((1, 256, 4), dtype=complex)
        impedance[0, :, 0] = 1.0 + 1j * 0.5
        positions = np.linspace(0, 0.1, 256).reshape(-1, 1)
        
        chunk = StreamDataChunk(
            chunk_id=0,
            timestamp=time.time(),
            impedance=impedance,
            positions=positions
        )
        
        processor.buffer.extend([impedance[0, i] for i in range(256)])
        processor.position_buffer.extend(positions.flatten())
        
        result = processor.process_chunk(chunk)
        
        assert result['alarm_triggered'] == True
        assert len(alarm_events) > 0
        assert alarm_events[0].confidence == 0.9

    def test_statistics(self):
        processor = StreamProcessor()
        processor.processed_chunks = [
            {'crack_probability': 0.3, 'alarm_triggered': False},
            {'crack_probability': 0.9, 'alarm_triggered': True},
            {'crack_probability': 0.5, 'alarm_triggered': False},
        ]
        
        stats = processor.get_statistics()
        assert stats['total_chunks'] == 3
        assert stats['alarm_count'] == 1
        assert stats['alarm_rate'] == pytest.approx(1/3)
        assert stats['max_crack_probability'] == 0.9
        assert stats['avg_crack_probability'] == pytest.approx((0.3 + 0.9 + 0.5) / 3)

    def test_alarm_cooldown(self):
        config = StreamConfig(
            buffer_size=128,
            overlap=64,
            alarm_threshold=0.5,
            alarm_cooldown=10.0
        )
        
        processor = StreamProcessor(config=config)
        processor.last_alarm_time = time.time() - 5.0
        
        processor.crack_identifier.is_trained = True
        processor.crack_identifier.identify = lambda x: {
            'has_crack': True,
            'probability': 0.9
        }
        
        processor.buffer.extend([1.0 + 1j * 0.5] * 128)
        processor.position_buffer.extend(np.linspace(0, 0.1, 128))
        
        impedance = np.zeros((1, 128, 4), dtype=complex)
        impedance[0, :, 0] = 1.0 + 1j * 0.5
        positions = np.linspace(0, 0.1, 128).reshape(-1, 1)
        
        chunk = StreamDataChunk(
            chunk_id=0,
            timestamp=time.time(),
            impedance=impedance,
            positions=positions
        )
        
        result = processor.process_chunk(chunk)
        assert result['alarm_triggered'] == False

    def test_save_alarm_history(self):
        processor = StreamProcessor()
        processor.alarm_history = [
            {'alarm_id': 0, 'timestamp': 1234567890, 'confidence': 0.9}
        ]
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            processor.save_alarm_history(temp_path)
            assert os.path.exists(temp_path)
            
            import json
            with open(temp_path) as f:
                data = json.load(f)
            assert 'alarms' in data
            assert 'statistics' in data
            assert len(data['alarms']) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestFileAlarmHandler:
    def test_write_alarm(self):
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            temp_path = f.name
        
        try:
            handler = FileAlarmHandler(temp_path)
            
            alarm = AlarmEvent(
                alarm_id=1,
                timestamp=1234567890.0,
                chunk_id=5,
                confidence=0.95,
                position=0.123,
                severity='critical',
                message='Test'
            )
            
            handler.handle_alarm(alarm)
            handler.close()
            
            assert os.path.exists(temp_path)
            with open(temp_path) as f:
                content = f.read()
            assert '1234567890' in content
            assert '0.95' in content
            assert 'critical' in content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


@pytest.mark.skipif(not _pinn_classes_available, reason="PyTorch or PINN classes not available")
class TestPINNConfig:
    def test_default_config(self):
        config = PINNConfig()
        assert config.hidden_layers == Config.PINN_HIDDEN_LAYERS
        assert config.learning_rate == Config.PINN_LEARNING_RATE
        assert config.epochs == Config.PINN_EPOCHS

    def test_custom_config(self):
        config = PINNConfig(
            hidden_layers=[32, 32],
            learning_rate=1e-4,
            epochs=100
        )
        assert config.hidden_layers == [32, 32]
        assert config.learning_rate == 1e-4
        assert config.epochs == 100


@pytest.mark.skipif(not _pinn_classes_available, reason="PyTorch or PINN classes not available")
class TestHelmholtzPDE:
    def test_pde_initialization(self):
        pde = HelmholtzPDE(
            frequency=50e3,
            conductivity=Config.CONDUCTIVITY_AL,
            permeability=Config.PERMEABILITY
        )
        assert pde.frequency == 50e3
        assert pde.sigma == Config.CONDUCTIVITY_AL
        assert pde.k_squared is not None
        assert np.iscomplex(pde.k_squared)


@pytest.mark.skipif(not _pinn_classes_available, reason="PyTorch or PINN classes not available")
class TestPINNNetwork:
    def test_network_architecture(self):
        net = PINNNetwork(input_dim=3, output_dim=2, hidden_layers=[16, 16])
        
        import torch
        x = torch.randn(10, 3)
        output = net(x)
        
        assert output.shape == (10, 2)


@pytest.mark.skipif(not _pinn_classes_available, reason="PyTorch or PINN classes not available")
class TestCrackReconstructorPINN:
    def test_prepare_data(self, sample_single_channel_data):
        pinn = CrackReconstructorPINN(PINNConfig(epochs=10))
        prepared = pinn.prepare_data(sample_single_channel_data, freq_idx=0)
        
        assert 'x_train' in prepared
        assert 'y_train' in prepared
        assert 'x_bounds' in prepared
        assert prepared['x_train'].shape[1] == 3
        assert prepared['y_train'].shape[1] == 2

    def test_generate_collocation_points(self):
        pinn = CrackReconstructorPINN(PINNConfig(epochs=10))
        
        bounds = np.array([[0, 0.2], [-0.01, 0.01], [0, 0]])
        colloc = pinn.generate_collocation_points(bounds, n_points=100)
        
        assert colloc.shape == (100, 3)
        assert np.all(colloc[:, 0] >= 0) and np.all(colloc[:, 0] <= 0.2)

    def test_train(self, sample_single_channel_data):
        config = PINNConfig(epochs=10, pde_weight=0.01)
        pinn = CrackReconstructorPINN(config)
        
        result = pinn.train(
            sample_single_channel_data,
            freq_idx=0,
            verbose=False
        )
        
        assert 'history' in result
        assert 'final_loss' in result
        assert len(result['history']['total_loss']) == 10
        assert pinn.trained == True

    def test_predict(self, sample_single_channel_data):
        config = PINNConfig(epochs=10, pde_weight=0.01)
        pinn = CrackReconstructorPINN(config)
        pinn.train(sample_single_channel_data, freq_idx=0, verbose=False)
        
        test_positions = np.linspace(0, 0.2, 10).reshape(-1, 1)
        predictions = pinn.predict(test_positions)
        
        assert predictions.shape == (10,)
        assert np.iscomplexobj(predictions)

    def test_reconstruct_crack_profile(self, sample_single_channel_data):
        config = PINNConfig(epochs=10, pde_weight=0.01)
        pinn = CrackReconstructorPINN(config)
        pinn.train(sample_single_channel_data, freq_idx=0, verbose=False)
        
        result = pinn.reconstruct_crack_profile(
            sample_single_channel_data,
            grid_resolution=20
        )
        
        assert 'reconstructed_amplitude' in result
        assert 'cracks' in result
        assert result['reconstructed_amplitude'].shape == (20, 20)

    def test_save_load_model(self, sample_single_channel_data):
        config = PINNConfig(epochs=10, pde_weight=0.01)
        pinn = CrackReconstructorPINN(config)
        pinn.train(sample_single_channel_data, freq_idx=0, verbose=False)
        
        with tempfile.NamedTemporaryFile(suffix='.pt', delete=False) as f:
            temp_path = f.name
        
        try:
            pinn.save_model(temp_path)
            assert os.path.exists(temp_path)
            
            pinn2 = CrackReconstructorPINN(config)
            pinn2.load_model(temp_path)
            assert pinn2.trained == True
            
            test_pos = np.array([[0.1, 0.0, 0.0]])
            pred1 = pinn.predict(test_pos)
            pred2 = pinn2.predict(test_pos)
            
            np.testing.assert_allclose(pred1, pred2, rtol=1e-5)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


@pytest.mark.skipif(not _pinn_classes_available, reason="PyTorch or PINN classes not available")
class TestPINNInverter:
    def test_single_freq_inversion(self, sample_single_channel_data):
        config = PINNConfig(epochs=10, pde_weight=0.01)
        inverter = PINNInverter(config)
        
        result = inverter.invert(
            sample_single_channel_data,
            freq_indices=[0],
            use_multi_freq=False,
            verbose=False
        )
        
        assert 'multi_freq' in result
        assert result['multi_freq'] == False
        assert 'reconstruction' in result

    def test_multi_freq_inversion(self, sample_single_channel_data):
        config = PINNConfig(epochs=10, pde_weight=0.01)
        inverter = PINNInverter(config)
        
        result = inverter.invert(
            sample_single_channel_data,
            freq_indices=[0, 1],
            use_multi_freq=True,
            verbose=False
        )
        
        assert result['multi_freq'] == True
        assert 'fused' in result
        assert 'weights' in result
        assert len(result['weights']) == 2


import time
