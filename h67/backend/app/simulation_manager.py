import asyncio
import numpy as np
import threading
from typing import List, Optional, Dict, Any
from collections import deque

from .models import (
    SimulationParameters,
    SimulationResult,
    PIDParameters,
    PerturbationConfig,
    SimulationStatus,
    PIDStatus,
    SimulationTimeSeries,
    SimulationMode,
    SimulationConfig,
    ChannelResult,
    FaultTypeEnum,
    ChannelFaultStatus,
    FaultDetectionStatus,
    MultichannelConfig,
    NeuralSurrogateConfig,
    NeuralSurrogateStatus,
    MultichannelStatus,
    ExtendedSimulationStatus
)
from .droplet_model import DropletFormationModel
from .pid_controller import PIDController
from .perturbation import PerturbationGenerator
from .neural_surrogate import DropletNeuralSurrogate
from .multichannel import MultichannelDropletGenerator
from .fault_detection import FaultDetector, FaultDetectionResult


class SimulationManager:
    def __init__(self):
        self.parameters = SimulationParameters()
        self.droplet_model = DropletFormationModel()
        self.pid_controller = PIDController(PIDParameters())
        self.perturbation = PerturbationGenerator(PerturbationConfig())

        self.mode: SimulationMode = SimulationMode.SINGLE_CHANNEL
        self.simulation_config = SimulationConfig()

        self._neural_surrogate: Optional[DropletNeuralSurrogate] = None
        self._multichannel_generator: Optional[MultichannelDropletGenerator] = None
        self._fault_detector: Optional[FaultDetector] = None
        self._neural_training_thread: Optional[threading.Thread] = None
        self._neural_training_progress: float = 0.0

        self.running = False
        self.paused = False
        self.time = 0.0
        self.dt = 0.1

        self._history_size = 500
        self._timestamps: deque = deque(maxlen=self._history_size)
        self._droplet_sizes: deque = deque(maxlen=self._history_size)
        self._frequencies: deque = deque(maxlen=self._history_size)
        self._continuous_flow_rates: deque = deque(maxlen=self._history_size)
        self._dispersed_flow_rates: deque = deque(maxlen=self._history_size)

        self._multichannel_history: List[List[Dict]] = []

        self.latest_result: Optional[SimulationResult] = None
        self.latest_pid_status: Optional[PIDStatus] = None
        self.latest_multichannel_results: List[Dict] = []
        self.latest_fault_result: Optional[FaultDetectionResult] = None

        self._websocket_clients: List = []
        self._simulation_task: Optional[asyncio.Task] = None

        self._initialize_specialized_modules()

    def _initialize_specialized_modules(self):
        default_n_channels = 4
        self._multichannel_generator = MultichannelDropletGenerator(
            n_channels=default_n_channels,
            spacing=200.0
        )
        self._fault_detector = FaultDetector(
            n_channels=default_n_channels,
            window_size=50
        )
        self._neural_surrogate = DropletNeuralSurrogate(
            hidden_layers=[64, 32, 16]
        )

    def add_websocket_client(self, client):
        if client not in self._websocket_clients:
            self._websocket_clients.append(client)

    def remove_websocket_client(self, client):
        if client in self._websocket_clients:
            self._websocket_clients.remove(client)

    async def _broadcast(self, message: dict):
        for client in list(self._websocket_clients):
            try:
                await client.send_json(message)
            except Exception:
                self.remove_websocket_client(client)

    def update_parameters(self, params: SimulationParameters):
        self.parameters = params

    def update_pid_parameters(self, params: PIDParameters):
        self.pid_controller.update_parameters(params)

    def update_perturbation_config(self, config: PerturbationConfig):
        self.perturbation.update_config(config)

    def update_simulation_config(self, config: SimulationConfig):
        self.simulation_config = config
        self.mode = config.mode

        if config.multichannel is not None and self._multichannel_generator is not None:
            self._reinitialize_multichannel(config.multichannel)

        if config.faultDetectionEnabled and self._fault_detector is None and self._multichannel_generator is not None:
            self._fault_detector = FaultDetector(
                n_channels=config.multichannel.nChannels if config.multichannel else 4
            )

    def _reinitialize_multichannel(self, config: MultichannelConfig):
        if self._multichannel_generator is None or self._multichannel_generator.n_channels != config.nChannels:
            self._multichannel_generator = MultichannelDropletGenerator(
                n_channels=config.nChannels,
                spacing=config.channelSpacing
            )
            if self.simulation_config.faultDetectionEnabled:
                self._fault_detector = FaultDetector(
                    n_channels=config.nChannels,
                    window_size=50
                )

        self._multichannel_generator.set_crosstalk_parameters(
            strength=config.crosstalkStrength,
            decay_length=config.crosstalkDecay,
            pressure_coupling=config.pressureCoupling
        )

    def set_channel_blocked(self, channel_id: int, blocked: bool, severity: float = 0.5):
        if self._multichannel_generator is not None:
            self._multichannel_generator.set_channel_blocked(channel_id, blocked, severity)

    def set_channel_enabled(self, channel_id: int, enabled: bool):
        if self._multichannel_generator is not None:
            self._multichannel_generator.set_channel_enabled(channel_id, enabled)

    def train_neural_surrogate(self, config: NeuralSurrogateConfig) -> Dict:
        if self._neural_training_thread is not None and self._neural_training_thread.is_alive():
            return {"error": "Training already in progress"}

        self._neural_surrogate = DropletNeuralSurrogate(
            hidden_layers=config.hiddenLayers
        )
        self._neural_training_progress = 0.0

        def training_thread():
            try:
                metrics = self._neural_surrogate.train(
                    n_samples=config.trainingSamples,
                    epochs=config.epochs,
                    lr=config.learningRate,
                    batch_size=config.batchSize
                )
                self._neural_training_progress = 1.0
            except Exception as e:
                print(f"Training error: {e}")
                self._neural_training_progress = -1.0

        self._neural_training_thread = threading.Thread(target=training_thread, daemon=True)
        self._neural_training_thread.start()

        return {"status": "training_started"}

    def get_neural_surrogate_status(self) -> NeuralSurrogateStatus:
        if self._neural_surrogate is None:
            return NeuralSurrogateStatus(
                trained=False,
                architecture={},
                trainingProgress=0.0
            )

        info = self._neural_surrogate.get_model_info()
        progress = self._neural_training_progress

        if self._neural_training_thread is not None and self._neural_training_thread.is_alive():
            progress = 0.5

        return NeuralSurrogateStatus(
            trained=info['trained'],
            architecture=info['architecture'],
            metrics=info.get('metrics'),
            trainingProgress=progress
        )

    def get_time_series(self) -> SimulationTimeSeries:
        return SimulationTimeSeries(
            timestamps=list(self._timestamps),
            dropletSizes=list(self._droplet_sizes),
            frequencies=list(self._frequencies),
            continuousFlowRates=list(self._continuous_flow_rates),
            dispersedFlowRates=list(self._dispersed_flow_rates)
        )

    def _convert_channel_result(self, r: Dict) -> ChannelResult:
        return ChannelResult(
            channelId=r['channel_id'],
            enabled=r['enabled'],
            blocked=r.get('blocked', False),
            blockageSeverity=r.get('blockageSeverity'),
            dropletSize=r['dropletSize'],
            generationFrequency=r['generationFrequency'],
            continuousFlowRate=r['continuousFlowRate'],
            dispersedFlowRate=r['dispersedFlowRate'],
            baseContinuousFlowRate=r.get('baseContinuousFlowRate'),
            baseDispersedFlowRate=r.get('baseDispersedFlowRate'),
            flowRateRatio=r['flowRateRatio'],
            capillaryNumber=r['capillaryNumber'],
            polydispersity=r.get('polydispersity'),
            crosstalkDeltaQc=r.get('crosstalkDeltaQc'),
            crosstalkDeltaQd=r.get('crosstalkDeltaQd')
        )

    def _convert_fault_status(self, result: FaultDetectionResult) -> FaultDetectionStatus:
        channel_statuses = [
            ChannelFaultStatus(
                channelId=s.channel_id,
                faultType=FaultTypeEnum(s.fault_type.value),
                confidence=s.confidence,
                blockageSeverity=s.blockage_severity,
                anomalyScore=s.anomaly_score
            )
            for s in result.channel_statuses
        ]

        return FaultDetectionStatus(
            enabled=self.simulation_config.faultDetectionEnabled,
            overallStatus=result.overall_status,
            channelStatuses=channel_statuses,
            anomalies=result.anomalies,
            recommendations=result.recommendations
        )

    def get_multichannel_status(self) -> Optional[MultichannelStatus]:
        if self._multichannel_generator is None:
            return None

        summary = None
        if self.latest_multichannel_results:
            summary = self._multichannel_generator.get_summary_statistics(
                self.latest_multichannel_results
            )

        return MultichannelStatus(
            nChannels=self._multichannel_generator.n_channels,
            channelConfigs=self._multichannel_generator.get_channel_configs(),
            crosstalkInfo=self._multichannel_generator.get_crosstalk_info(),
            summaryStats=summary,
            lastResults=[self._convert_channel_result(r) for r in self.latest_multichannel_results]
        )

    def get_status(self) -> ExtendedSimulationStatus:
        base_status = {
            'running': self.running and not self.paused,
            'time': self.time,
            'parameters': self.parameters,
            'latestResult': self.latest_result,
            'pidStatus': self.latest_pid_status,
            'perturbation': self.perturbation.config,
            'mode': self.mode,
        }

        if self.mode == SimulationMode.MULTICHANNEL:
            base_status['multichannel'] = self.get_multichannel_status()

        if self.simulation_config.faultDetectionEnabled and self.latest_fault_result is not None:
            base_status['faultDetection'] = self._convert_fault_status(self.latest_fault_result)

        if self.mode == SimulationMode.NEURAL_SURROGATE:
            base_status['neuralSurrogate'] = self.get_neural_surrogate_status()

        return ExtendedSimulationStatus(**base_status)

    def start(self):
        if not self.running:
            self.running = True
            self.paused = False
            self._simulation_task = asyncio.create_task(self._run_simulation())

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def reset(self):
        self.running = False
        self.paused = False
        self.time = 0.0
        self._timestamps.clear()
        self._droplet_sizes.clear()
        self._frequencies.clear()
        self._continuous_flow_rates.clear()
        self._dispersed_flow_rates.clear()
        self._multichannel_history.clear()
        self.latest_result = None
        self.latest_pid_status = None
        self.latest_multichannel_results = []
        self.latest_fault_result = None
        self.pid_controller.reset()
        self.perturbation.reset()

        if self._fault_detector is not None:
            self._fault_detector.reset()

        if self._simulation_task:
            self._simulation_task.cancel()
            self._simulation_task = None

    def _run_single_channel_step(self, Qc_base: float, Qd_base: float) -> SimulationResult:
        Qc, Qd = self.perturbation.apply_perturbation(
            Qc_base=Qc_base,
            Qd_base=Qd_base,
            time=self.time
        )

        if self.latest_result is not None and self.pid_controller.params.enabled:
            Qd_pid, pid_status = self.pid_controller.compute(
                measurement=self.latest_result.dropletSize,
                current_time=self.time
            )
            Qd = Qd_pid
            self.latest_pid_status = pid_status

        if self.mode == SimulationMode.NEURAL_SURROGATE and self._neural_surrogate is not None and self._neural_surrogate._trained:
            D, f = self._neural_surrogate.predict(
                params=self.parameters,
                Qc_actual=Qc,
                Qd_actual=Qd
            )
            Q_ratio = Qd / Qc if Qc > 0 else 0
            Ca_c = (self.parameters.continuousPhase.viscosity * Qc * 1e3) / (60 * self.parameters.channel.width * self.parameters.channel.height * self.parameters.interfacialTension)
        else:
            D, f, Q_ratio, Ca_c = self.droplet_model.simulate_step(
                params=self.parameters,
                Qc_actual=Qc,
                Qd_actual=Qd,
                time=self.time,
                add_noise=True
            )

        recent_sizes = list(self._droplet_sizes)[-50:] + [D]
        if len(recent_sizes) >= 10:
            pd_result = self.droplet_model.compute_polydispersity_with_ci(
                np.array(recent_sizes)
            )
            polydispersity = pd_result['cv']
        else:
            polydispersity = self.droplet_model.compute_polydispersity(
                np.array(recent_sizes)
            )

        return SimulationResult(
            timestamp=self.time,
            dropletSize=float(D),
            generationFrequency=float(f),
            flowRateRatio=float(Q_ratio),
            capillaryNumber=float(Ca_c),
            continuousFlowRate=float(Qc),
            dispersedFlowRate=float(Qd),
            polydispersity=float(polydispersity)
        )

    def _run_multichannel_step(self) -> List[Dict]:
        if self._multichannel_generator is None:
            return []

        if self.latest_result is not None and self.pid_controller.params.enabled:
            Qd_pid, pid_status = self.pid_controller.compute(
                measurement=self.latest_result.dropletSize,
                current_time=self.time
            )
            self.parameters.dispersedPhase.flowRate = Qd_pid
            self.latest_pid_status = pid_status

        results = self._multichannel_generator.simulate_step(
            base_params=self.parameters,
            time=self.time,
            add_noise=True
        )

        if self.simulation_config.faultDetectionEnabled and self._fault_detector is not None:
            self.latest_fault_result = self._fault_detector.detect(
                channel_data=results,
                timestamp=self.time
            )

        return results

    async def _run_simulation(self):
        Qc_base = self.parameters.continuousPhase.flowRate
        Qd_base = self.parameters.dispersedPhase.flowRate

        try:
            while self.running:
                if not self.paused:
                    if self.mode == SimulationMode.MULTICHANNEL:
                        channel_results = self._run_multichannel_step()
                        self.latest_multichannel_results = channel_results

                        enabled_results = [r for r in channel_results if r['enabled']]
                        if enabled_results:
                            avg_size = np.mean([r['dropletSize'] for r in enabled_results])
                            avg_freq = np.mean([r['generationFrequency'] for r in enabled_results])
                            total_Qc = sum(r['continuousFlowRate'] for r in enabled_results)
                            total_Qd = sum(r['dispersedFlowRate'] for r in enabled_results)

                            self.latest_result = SimulationResult(
                                timestamp=self.time,
                                dropletSize=float(avg_size),
                                generationFrequency=float(avg_freq),
                                flowRateRatio=float(total_Qd / total_Qc if total_Qc > 0 else 0),
                                capillaryNumber=float(enabled_results[0]['capillaryNumber']),
                                continuousFlowRate=float(total_Qc),
                                dispersedFlowRate=float(total_Qd),
                                polydispersity=float(enabled_results[0].get('polydispersity', 0))
                            )

                            self._timestamps.append(self.time)
                            self._droplet_sizes.append(avg_size)
                            self._frequencies.append(avg_freq)
                            self._continuous_flow_rates.append(total_Qc)
                            self._dispersed_flow_rates.append(total_Qd)
                            self._multichannel_history.append(channel_results)
                    else:
                        result = self._run_single_channel_step(Qc_base, Qd_base)
                        self.latest_result = result
                        self._timestamps.append(self.time)
                        self._droplet_sizes.append(result.dropletSize)
                        self._frequencies.append(result.generationFrequency)
                        self._continuous_flow_rates.append(result.continuousFlowRate)
                        self._dispersed_flow_rates.append(result.dispersedFlowRate)

                    status = self.get_status()
                    await self._broadcast({
                        "type": "simulation_data",
                        "data": status
                    })

                    self.time += self.dt

                await asyncio.sleep(self.dt)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Simulation error: {e}")
            import traceback
            traceback.print_exc()
            self.running = False
