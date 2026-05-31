import numpy as np
from typing import List, Tuple, Optional, Dict
from .models import SimulationParameters, JunctionType
from .droplet_model import DropletFormationModel


class ChannelConfig:
    def __init__(self, channel_id: int, params: SimulationParameters,
                 x_offset: float = 0.0, y_offset: float = 0.0):
        self.channel_id = channel_id
        self.params = params
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.enabled = True
        self.blocked = False
        self.blockage_severity = 0.0


class MultichannelDropletGenerator:
    def __init__(self, n_channels: int = 4, spacing: float = 200.0):
        self.n_channels = n_channels
        self.spacing = spacing
        self.channels: List[ChannelConfig] = []
        self.droplet_model = DropletFormationModel()

        self._crosstalk_strength = 0.15
        self._hydrodynamic_interaction_decay = 2.0
        self._pressure_coupling = 0.1

        self._initialize_channels()

    def _initialize_channels(self):
        base_params = SimulationParameters()
        self.channels = []

        for i in range(self.n_channels):
            params = SimulationParameters(
                continuousPhase=base_params.continuousPhase.model_copy(),
                dispersedPhase=base_params.dispersedPhase.model_copy(),
                interfacialTension=base_params.interfacialTension,
                channel=base_params.channel.model_copy()
            )

            x_offset = 0
            y_offset = i * self.spacing

            channel = ChannelConfig(i, params, x_offset, y_offset)
            self.channels.append(channel)

    def set_channel_parameters(self, channel_id: int, params: SimulationParameters):
        if 0 <= channel_id < self.n_channels:
            self.channels[channel_id].params = params

    def set_channel_enabled(self, channel_id: int, enabled: bool):
        if 0 <= channel_id < self.n_channels:
            self.channels[channel_id].enabled = enabled

    def set_channel_blocked(self, channel_id: int, blocked: bool, severity: float = 0.5):
        if 0 <= channel_id < self.n_channels:
            self.channels[channel_id].blocked = blocked
            self.channels[channel_id].blockage_severity = severity

    def _compute_hydrodynamic_crosstalk(self, channel_idx: int,
                                       all_flow_rates: List[Tuple[float, float]],
                                       time: float) -> Tuple[float, float]:
        Qc_i, Qd_i = all_flow_rates[channel_idx]
        delta_Qc = 0.0
        delta_Qd = 0.0

        for j, (Qc_j, Qd_j) in enumerate(all_flow_rates):
            if j == channel_idx or not self.channels[j].enabled:
                continue

            distance = abs(j - channel_idx) * self.spacing
            decay = np.exp(-distance / (self.spacing * self._hydrodynamic_interaction_decay))

            delta_Qc += (Qc_j - Qc_i) * self._crosstalk_strength * decay
            delta_Qd += (Qd_j - Qd_i) * self._crosstalk_strength * decay

        global_Qc = sum(Qc for Qc, _ in all_flow_rates) / max(sum(1 for c in self.channels if c.enabled), 1)
        delta_Qc += (global_Qc - Qc_i) * self._pressure_coupling

        return delta_Qc, delta_Qd

    def _apply_blockage(self, channel: ChannelConfig,
                        Qc: float, Qd: float) -> Tuple[float, float]:
        if not channel.blocked:
            return Qc, Qd

        severity = channel.blockage_severity
        resistance_factor = 1.0 / (1.0 - severity)

        Qc_blocked = Qc / resistance_factor
        Qd_blocked = Qd / resistance_factor

        flow_reduction = severity * 0.8
        Qc_blocked = Qc * (1 - flow_reduction)
        Qd_blocked = Qd * (1 - flow_reduction * 1.5)

        return max(Qc_blocked, 0.01), max(Qd_blocked, 0.01)

    def simulate_step(self, base_params: Optional[SimulationParameters] = None,
                       time: float = 0.0, add_noise: bool = True) -> List[Dict]:
        if base_params is not None:
            for channel in self.channels:
                channel.params = base_params.model_copy()

        results = []
        all_flow_rates = []

        for channel in self.channels:
            if not channel.enabled:
                all_flow_rates.append((0.0, 0.0))
                continue

            Qc = channel.params.continuousPhase.flowRate
            Qd = channel.params.dispersedPhase.flowRate

            Qc, Qd = self._apply_blockage(channel, Qc, Qd)
            all_flow_rates.append((Qc, Qd))

        for i, channel in enumerate(self.channels):
            if not channel.enabled:
                results.append({
                    'channel_id': i,
                    'enabled': False,
                    'blocked': channel.blocked,
                    'dropletSize': 0.0,
                    'generationFrequency': 0.0,
                    'continuousFlowRate': 0.0,
                    'dispersedFlowRate': 0.0,
                    'flowRateRatio': 0.0,
                    'capillaryNumber': 0.0,
                    'crosstalkDeltaQc': 0.0,
                    'crosstalkDeltaQd': 0.0
                })
                continue

            Qc, Qd = all_flow_rates[i]

            delta_Qc, delta_Qd = self._compute_hydrodynamic_crosstalk(i, all_flow_rates, time)

            Qc_effective = Qc + delta_Qc
            Qd_effective = Qd + delta_Qd

            params = channel.params
            D, f, Q_ratio, Ca_c = self.droplet_model.simulate_step(
                params=params,
                Qc_actual=Qc_effective,
                Qd_actual=Qd_effective,
                time=time,
                add_noise=add_noise
            )

            recent_sizes = []
            polydispersity = 0.0
            if len(recent_sizes) >= 3:
                polydispersity = self.droplet_model.compute_polydispersity(np.array(recent_sizes))

            results.append({
                'channel_id': i,
                'enabled': True,
                'blocked': channel.blocked,
                'blockageSeverity': channel.blockage_severity if channel.blocked else 0.0,
                'dropletSize': float(D),
                'generationFrequency': float(f),
                'continuousFlowRate': float(Qc_effective),
                'dispersedFlowRate': float(Qd_effective),
                'baseContinuousFlowRate': float(Qc),
                'baseDispersedFlowRate': float(Qd),
                'flowRateRatio': float(Q_ratio),
                'capillaryNumber': float(Ca_c),
                'polydispersity': float(polydispersity),
                'crosstalkDeltaQc': float(delta_Qc),
                'crosstalkDeltaQd': float(delta_Qd),
                'x_offset': float(channel.x_offset),
                'y_offset': float(channel.y_offset)
            })

        return results

    def get_summary_statistics(self, results: List[Dict]) -> Dict:
        enabled_results = [r for r in results if r['enabled']]
        if not enabled_results:
            return {}

        sizes = [r['dropletSize'] for r in enabled_results]
        freqs = [r['generationFrequency'] for r in enabled_results]
        Qc_total = sum(r['continuousFlowRate'] for r in enabled_results)
        Qd_total = sum(r['dispersedFlowRate'] for r in enabled_results)

        size_cv = np.std(sizes) / np.mean(sizes) * 100 if np.mean(sizes) > 0 else 0
        freq_cv = np.std(freqs) / np.mean(freqs) * 100 if np.mean(freqs) > 0 else 0

        return {
            'n_enabled_channels': len(enabled_results),
            'n_blocked_channels': sum(1 for r in results if r.get('blocked', False)),
            'mean_droplet_size': float(np.mean(sizes)),
            'std_droplet_size': float(np.std(sizes)),
            'size_cv_percent': float(size_cv),
            'mean_frequency': float(np.mean(freqs)),
            'std_frequency': float(np.std(freqs)),
            'frequency_cv_percent': float(freq_cv),
            'total_continuous_flowrate': float(Qc_total),
            'total_dispersed_flowrate': float(Qd_total),
            'total_throughput_hz': float(sum(freqs)),
            'channel_uniformity_score': float(max(0, 100 - size_cv))
        }

    def get_channel_configs(self) -> List[Dict]:
        return [{
            'channel_id': c.channel_id,
            'enabled': c.enabled,
            'blocked': c.blocked,
            'blockage_severity': c.blockage_severity,
            'continuousFlowRate': c.params.continuousPhase.flowRate,
            'dispersedFlowRate': c.params.dispersedPhase.flowRate,
            'x_offset': c.x_offset,
            'y_offset': c.y_offset
        } for c in self.channels]

    def set_crosstalk_parameters(self, strength: float = 0.15,
                                 decay_length: float = 2.0,
                                 pressure_coupling: float = 0.1):
        self._crosstalk_strength = max(0.0, min(strength, 1.0))
        self._hydrodynamic_interaction_decay = max(0.1, decay_length)
        self._pressure_coupling = max(0.0, min(pressure_coupling, 1.0))

    def get_crosstalk_info(self) -> Dict:
        return {
            'crosstalk_strength': self._crosstalk_strength,
            'hydrodynamic_decay_length': self._hydrodynamic_interaction_decay,
            'pressure_coupling': self._pressure_coupling
        }
