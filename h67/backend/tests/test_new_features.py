import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import (
    SimulationParameters,
    SimulationConfig,
    SimulationMode,
    NeuralSurrogateConfig,
    MultichannelConfig
)
from app.simulation_manager import SimulationManager
from app.neural_surrogate import DropletNeuralSurrogate
from app.multichannel import MultichannelDropletGenerator
from app.fault_detection import FaultDetector


class TestNeuralSurrogate:
    def test_neural_network_initialization(self):
        surrogate = DropletNeuralSurrogate(hidden_layers=[64, 32, 16])
        info = surrogate.get_model_info()
        assert info['trained'] is False
        assert 'architecture' in info
        assert len(info['architecture']['input_features']) == 10
        assert len(info['architecture']['output_features']) == 2
        assert info['architecture']['hidden_layers'] == [64, 32, 16]

    def test_training_data_generation(self):
        surrogate = DropletNeuralSurrogate(hidden_layers=[32, 16])
        X, y = surrogate.generate_training_data(n_samples=100, noise_level=0.0)
        assert X.shape == (100, 10)
        assert y.shape == (100, 2)
        assert not np.any(np.isnan(X))
        assert not np.any(np.isnan(y))

    def test_neural_network_training(self):
        surrogate = DropletNeuralSurrogate(hidden_layers=[32, 16])
        metrics = surrogate.train(n_samples=500, epochs=100, lr=0.01, batch_size=32)
        assert surrogate._trained is True
        assert 'size_mape' in metrics
        assert 'frequency_mape' in metrics
        assert metrics['size_mape'] > 0

    def test_neural_network_prediction(self):
        surrogate = DropletNeuralSurrogate(hidden_layers=[32, 16])
        surrogate.train(n_samples=500, epochs=100, lr=0.01, batch_size=32)
        
        params = SimulationParameters()
        D, f = surrogate.predict(params)
        assert D > 0
        assert f > 0


class TestMultichannelGenerator:
    def test_multichannel_initialization(self):
        generator = MultichannelDropletGenerator(n_channels=4, spacing=200.0)
        assert generator.n_channels == 4
        assert generator.spacing == 200.0
        assert len(generator.channels) == 4

    def test_crosstalk_calculation(self):
        generator = MultichannelDropletGenerator(n_channels=4, spacing=200.0)
        generator.set_crosstalk_parameters(strength=0.3, decay_length=2.0, pressure_coupling=0.1)
        
        all_flow_rates = [(20.0, 5.0) for _ in range(4)]
        delta_Qc, delta_Qd = generator._compute_hydrodynamic_crosstalk(
            channel_idx=0,
            all_flow_rates=all_flow_rates,
            time=0.0
        )
        assert delta_Qc == 0.0
        assert delta_Qd == 0.0

        all_flow_rates[1] = (25.0, 7.0)
        delta_Qc, delta_Qd = generator._compute_hydrodynamic_crosstalk(
            channel_idx=0,
            all_flow_rates=all_flow_rates,
            time=0.0
        )
        assert delta_Qc != 0.0
        assert delta_Qd != 0.0

    def test_channel_blockage(self):
        generator = MultichannelDropletGenerator(n_channels=4, spacing=200.0)
        generator.set_channel_blocked(channel_id=1, blocked=True, severity=0.5)
        
        Qc_reduced, Qd_reduced = generator._apply_blockage(
            channel=generator.channels[1],
            Qc=20.0,
            Qd=5.0
        )
        assert Qc_reduced < 20.0
        assert Qd_reduced < 5.0
        assert Qc_reduced > 0

    def test_multichannel_simulation_step(self):
        generator = MultichannelDropletGenerator(n_channels=4, spacing=200.0)
        params = SimulationParameters()
        results = generator.simulate_step(base_params=params, time=0.0, add_noise=False)
        
        assert len(results) == 4
        for r in results:
            assert r['enabled'] is True
            assert r['dropletSize'] > 0
            assert r['generationFrequency'] > 0

    def test_summary_statistics(self):
        generator = MultichannelDropletGenerator(n_channels=4, spacing=200.0)
        params = SimulationParameters()
        results = generator.simulate_step(base_params=params, time=0.0, add_noise=False)
        
        summary = generator.get_summary_statistics(results)
        assert summary['n_enabled_channels'] == 4
        assert summary['n_blocked_channels'] == 0
        assert summary['mean_droplet_size'] > 0
        assert summary['size_cv_percent'] >= 0


class TestFaultDetection:
    def test_fault_detector_initialization(self):
        detector = FaultDetector(n_channels=4, window_size=20)
        assert detector.n_channels == 4
        assert detector.window_size == 20

    def test_baseline_learning(self):
        detector = FaultDetector(n_channels=4, window_size=20)
        
        for i in range(30):
            channel_data = []
            for ch in range(4):
                channel_data.append({
                    'channel_id': ch,
                    'enabled': True,
                    'blocked': False,
                    'continuousFlowRate': 20.0 + np.random.normal(0, 0.5),
                    'dispersedFlowRate': 5.0 + np.random.normal(0, 0.2),
                    'dropletSize': 80.0 + np.random.normal(0, 2.0),
                    'generationFrequency': 100.0 + np.random.normal(0, 5.0)
                })
            detector.detect(channel_data=channel_data, timestamp=float(i))
        
        for ch in range(4):
            assert detector._baseline_flow[ch] is not None
            assert detector._baseline_flow[ch] > 0

    def test_blockage_detection(self):
        detector = FaultDetector(n_channels=4, window_size=50)
        detector._threshold_blockage_flow = 0.8
        detector._threshold_blockage_size = 1.2
        
        for i in range(50):
            channel_data = []
            for ch in range(4):
                channel_data.append({
                    'channel_id': ch,
                    'enabled': True,
                    'blocked': False,
                    'continuousFlowRate': 20.0,
                    'dispersedFlowRate': 5.0,
                    'dropletSize': 80.0,
                    'generationFrequency': 100.0
                })
            result = detector.detect(channel_data=channel_data, timestamp=float(i))
        
        for i in range(50, 150):
            channel_data = []
            for ch in range(4):
                qc = 10.0 if ch == 1 else 20.0
                qd = 2.5 if ch == 1 else 5.0
                size = 120.0 if ch == 1 else 80.0
                freq = 50.0 if ch == 1 else 100.0
                channel_data.append({
                    'channel_id': ch,
                    'enabled': True,
                    'blocked': ch == 1,
                    'continuousFlowRate': qc,
                    'dispersedFlowRate': qd,
                    'dropletSize': size,
                    'generationFrequency': freq
                })
            result = detector.detect(channel_data=channel_data, timestamp=float(i))
        
        assert result.overall_status in ['warning', 'critical'], f"Expected warning/critical, got {result.overall_status}"
        assert len(result.anomalies) > 0, f"Expected anomalies, got {result.anomalies}"
        
        ch1_status = next(s for s in result.channel_statuses if s.channel_id == 1)
        assert ch1_status.fault_type.value in ['partial_blockage', 'full_blockage'], \
            f"Expected blockage, got {ch1_status.fault_type.value}"
        assert ch1_status.confidence > 0.3, f"Expected confidence > 0.3, got {ch1_status.confidence}"


class TestSimulationManagerIntegration:
    def test_mode_switching(self):
        manager = SimulationManager()
        
        config = SimulationConfig(mode=SimulationMode.NEURAL_SURROGATE)
        manager.update_simulation_config(config)
        assert manager.mode == SimulationMode.NEURAL_SURROGATE
        
        config = SimulationConfig(mode=SimulationMode.MULTICHANNEL)
        manager.update_simulation_config(config)
        assert manager.mode == SimulationMode.MULTICHANNEL
        
        config = SimulationConfig(mode=SimulationMode.SINGLE_CHANNEL)
        manager.update_simulation_config(config)
        assert manager.mode == SimulationMode.SINGLE_CHANNEL

    def test_neural_training_in_manager(self):
        manager = SimulationManager()
        config = NeuralSurrogateConfig(
            hiddenLayers=[32, 16],
            trainingSamples=1000,
            epochs=200,
            learningRate=0.005,
            batchSize=32
        )
        result = manager.train_neural_surrogate(config)
        assert 'status' in result
        assert result['status'] == 'training_started'

    def test_multichannel_config_update(self):
        manager = SimulationManager()
        config = MultichannelConfig(
            nChannels=6,
            channelSpacing=300.0,
            crosstalkStrength=0.2,
            crosstalkDecay=1.5,
            pressureCoupling=0.1
        )
        sim_config = SimulationConfig(
            mode=SimulationMode.MULTICHANNEL,
            multichannel=config
        )
        manager.update_simulation_config(sim_config)
        assert manager._multichannel_generator is not None
        assert manager._multichannel_generator.n_channels == 6

    def test_get_status_extended(self):
        manager = SimulationManager()
        status = manager.get_status()
        assert hasattr(status, 'mode')
        assert status.mode == SimulationMode.SINGLE_CHANNEL


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
