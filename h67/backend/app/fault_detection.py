import numpy as np
from typing import List, Tuple, Dict, Optional
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class FaultType(Enum):
    NORMAL = "normal"
    PARTIAL_BLOCKAGE = "partial_blockage"
    FULL_BLOCKAGE = "full_blockage"
    FLOW_INSTABILITY = "flow_instability"
    PRESSURE_ANOMALY = "pressure_anomaly"
    LEAKAGE = "leakage"


@dataclass
class ChannelStatus:
    channel_id: int
    fault_type: FaultType = FaultType.NORMAL
    confidence: float = 0.0
    blockage_severity: float = 0.0
    anomaly_score: float = 0.0
    last_updated: float = 0.0


@dataclass
class FaultDetectionResult:
    timestamp: float
    overall_status: str = "normal"
    channel_statuses: List[ChannelStatus] = field(default_factory=list)
    anomalies: List[Dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class FaultDetector:
    def __init__(self, n_channels: int = 4, window_size: int = 50):
        self.n_channels = n_channels
        self.window_size = window_size

        self._flow_rate_history: List[deque] = [deque(maxlen=window_size) for _ in range(n_channels)]
        self._droplet_size_history: List[deque] = [deque(maxlen=window_size) for _ in range(n_channels)]
        self._frequency_history: List[deque] = [deque(maxlen=window_size) for _ in range(n_channels)]
        self._pressure_history: List[deque] = [deque(maxlen=window_size) for _ in range(n_channels)]

        self._baseline_flow: List[Optional[float]] = [None for _ in range(n_channels)]
        self._baseline_size: List[Optional[float]] = [None for _ in range(n_channels)]
        self._baseline_freq: List[Optional[float]] = [None for _ in range(n_channels)]

        self._ewma_flow: List[Optional[float]] = [None for _ in range(n_channels)]
        self._ewma_var_flow: List[Optional[float]] = [None for _ in range(n_channels)]
        self._ewma_alpha = 0.1

        self._threshold_blockage_flow = 0.7
        self._threshold_blockage_size = 1.3
        self._threshold_instability = 0.15
        self._min_samples = 10

        self._channel_statuses: List[ChannelStatus] = [
            ChannelStatus(channel_id=i) for i in range(n_channels)
        ]

    def set_baseline(self, channel_id: int, flow_rate: float,
                     droplet_size: float, frequency: float):
        if 0 <= channel_id < self.n_channels:
            self._baseline_flow[channel_id] = flow_rate
            self._baseline_size[channel_id] = droplet_size
            self._baseline_freq[channel_id] = frequency

    def _update_ewma(self, channel_id: int, value: float):
        if self._ewma_flow[channel_id] is None:
            self._ewma_flow[channel_id] = value
            self._ewma_var_flow[channel_id] = 0.0
        else:
            prev_ewma = self._ewma_flow[channel_id]
            prev_var = self._ewma_var_flow[channel_id]

            new_ewma = self._ewma_alpha * value + (1 - self._ewma_alpha) * prev_ewma
            new_var = (1 - self._ewma_alpha) * (prev_var + self._ewma_alpha * (value - prev_ewma) ** 2)

            self._ewma_flow[channel_id] = new_ewma
            self._ewma_var_flow[channel_id] = new_var

    def _compute_statistical_features(self, history: deque) -> Dict:
        if len(history) < self._min_samples:
            return {}

        data = np.array(history)
        return {
            'mean': float(np.mean(data)),
            'std': float(np.std(data)),
            'cv': float(np.std(data) / np.mean(data)) if np.mean(data) > 0 else 0,
            'min': float(np.min(data)),
            'max': float(np.max(data)),
            'trend': float(np.polyfit(range(len(data)), data, 1)[0]),
            'last': float(data[-1])
        }

    def _detect_blockage(self, channel_id: int, current_flow: float,
                         current_size: float) -> Tuple[bool, float, float]:
        baseline_flow = self._baseline_flow[channel_id]
        baseline_size = self._baseline_size[channel_id]

        if baseline_flow is None or baseline_size is None:
            return False, 0.0, 0.0

        flow_ratio = current_flow / baseline_flow if baseline_flow > 0 else 1.0
        size_ratio = current_size / baseline_size if baseline_size > 0 else 1.0

        flow_deviation = 1.0 - flow_ratio
        size_deviation = size_ratio - 1.0

        blockage_score = 0.0
        severity = 0.0

        if flow_ratio < self._threshold_blockage_flow:
            flow_contribution = (self._threshold_blockage_flow - flow_ratio) / self._threshold_blockage_flow
            blockage_score += flow_contribution * 0.6
            severity += flow_contribution * 0.8

        if size_ratio > self._threshold_blockage_size:
            size_contribution = (size_ratio - self._threshold_blockage_size) / (self._threshold_blockage_size * 0.5)
            blockage_score += min(size_contribution, 1.0) * 0.4
            severity += min(size_contribution, 1.0) * 0.6

        ewma = self._ewma_flow[channel_id]
        ewma_var = self._ewma_var_flow[channel_id]
        if ewma is not None and ewma_var is not None and ewma_var > 0:
            z_score = abs(current_flow - ewma) / np.sqrt(ewma_var)
            if z_score > 3:
                blockage_score += 0.2 * min(z_score / 5, 1.0)

        confidence = min(blockage_score, 1.0)
        severity = min(severity, 1.0)

        return confidence > 0.3, confidence, severity

    def _detect_instability(self, channel_id: int) -> Tuple[bool, float]:
        flow_features = self._compute_statistical_features(self._flow_rate_history[channel_id])
        size_features = self._compute_statistical_features(self._droplet_size_history[channel_id])

        if not flow_features or not size_features:
            return False, 0.0

        instability_score = 0.0

        if flow_features['cv'] > self._threshold_instability:
            instability_score += (flow_features['cv'] - self._threshold_instability) / 0.15

        if size_features['cv'] > self._threshold_instability:
            instability_score += (size_features['cv'] - self._threshold_instability) / 0.15

        if abs(flow_features['trend']) > 0.5:
            instability_score += 0.3

        confidence = min(instability_score, 1.0)
        return confidence > 0.3, confidence

    def _detect_pressure_anomaly(self, channel_id: int) -> Tuple[bool, float]:
        pressure_features = self._compute_statistical_features(self._pressure_history[channel_id])
        if not pressure_features:
            return False, 0.0

        anomaly_score = 0.0

        if pressure_features['cv'] > 0.1:
            anomaly_score += pressure_features['cv'] * 2

        if len(self._pressure_history[channel_id]) > 20:
            recent = np.array(list(self._pressure_history[channel_id])[-10:])
            older = np.array(list(self._pressure_history[channel_id])[:10])
            if np.mean(recent) > np.mean(older) * 1.2:
                anomaly_score += 0.5

        confidence = min(anomaly_score, 1.0)
        return confidence > 0.3, confidence

    def detect(self, channel_data: List[Dict], timestamp: float) -> FaultDetectionResult:
        anomalies = []
        recommendations = []
        overall_status = "normal"

        for data in channel_data:
            channel_id = data['channel_id']
            if not data.get('enabled', True):
                self._channel_statuses[channel_id] = ChannelStatus(
                    channel_id=channel_id,
                    fault_type=FaultType.NORMAL,
                    confidence=0.0,
                    last_updated=timestamp
                )
                continue

            flow = data.get('continuousFlowRate', 0) + data.get('dispersedFlowRate', 0)
            size = data.get('dropletSize', 0)
            freq = data.get('generationFrequency', 0)
            pressure = flow * 10

            self._flow_rate_history[channel_id].append(flow)
            self._droplet_size_history[channel_id].append(size)
            self._frequency_history[channel_id].append(freq)
            self._pressure_history[channel_id].append(pressure)

            self._update_ewma(channel_id, flow)

            if self._baseline_flow[channel_id] is None and len(self._flow_rate_history[channel_id]) >= 20:
                self.set_baseline(
                    channel_id,
                    np.mean(self._flow_rate_history[channel_id]),
                    np.mean(self._droplet_size_history[channel_id]),
                    np.mean(self._frequency_history[channel_id])
                )

            fault_type = FaultType.NORMAL
            confidence = 0.0
            severity = 0.0
            anomaly_score = 0.0

            blocked, block_conf, block_sev = self._detect_blockage(
                channel_id, flow, size
            )
            if blocked:
                if block_sev > 0.7:
                    fault_type = FaultType.FULL_BLOCKAGE
                else:
                    fault_type = FaultType.PARTIAL_BLOCKAGE
                confidence = block_conf
                severity = block_sev
                anomaly_score = block_conf

                anomalies.append({
                    'channel_id': channel_id,
                    'type': fault_type.value,
                    'confidence': confidence,
                    'severity': severity,
                    'description': f"通道{channel_id}检测到堵塞"
                })

                if severity > 0.7:
                    recommendations.append(f"紧急：通道{channel_id}严重堵塞，建议立即清理")
                else:
                    recommendations.append(f"警告：通道{channel_id}部分堵塞，建议检查")

            unstable, inst_conf = self._detect_instability(channel_id)
            if unstable and fault_type == FaultType.NORMAL:
                fault_type = FaultType.FLOW_INSTABILITY
                confidence = inst_conf
                anomaly_score = inst_conf

                anomalies.append({
                    'channel_id': channel_id,
                    'type': fault_type.value,
                    'confidence': confidence,
                    'description': f"通道{channel_id}流动不稳定"
                })
                recommendations.append(f"提示：通道{channel_id}流动波动较大，检查流速设置")

            pressure_anom, p_conf = self._detect_pressure_anomaly(channel_id)
            if pressure_anom and fault_type == FaultType.NORMAL:
                fault_type = FaultType.PRESSURE_ANOMALY
                confidence = p_conf
                anomaly_score = p_conf

                anomalies.append({
                    'channel_id': channel_id,
                    'type': fault_type.value,
                    'confidence': confidence,
                    'description': f"通道{channel_id}压力异常"
                })

            if fault_type != FaultType.NORMAL:
                if overall_status == "normal":
                    overall_status = "warning"
                if fault_type in [FaultType.FULL_BLOCKAGE]:
                    overall_status = "critical"

            self._channel_statuses[channel_id] = ChannelStatus(
                channel_id=channel_id,
                fault_type=fault_type,
                confidence=confidence,
                blockage_severity=severity,
                anomaly_score=anomaly_score,
                last_updated=timestamp
            )

        if not recommendations:
            recommendations.append("所有通道运行正常")

        return FaultDetectionResult(
            timestamp=timestamp,
            overall_status=overall_status,
            channel_statuses=self._channel_statuses.copy(),
            anomalies=anomalies,
            recommendations=recommendations
        )

    def reset(self):
        for i in range(self.n_channels):
            self._flow_rate_history[i].clear()
            self._droplet_size_history[i].clear()
            self._frequency_history[i].clear()
            self._pressure_history[i].clear()
            self._baseline_flow[i] = None
            self._baseline_size[i] = None
            self._baseline_freq[i] = None
            self._ewma_flow[i] = None
            self._ewma_var_flow[i] = None
            self._channel_statuses[i] = ChannelStatus(channel_id=i)

    def get_channel_history(self, channel_id: int) -> Dict:
        if not (0 <= channel_id < self.n_channels):
            return {}

        return {
            'flow_rate': list(self._flow_rate_history[channel_id]),
            'droplet_size': list(self._droplet_size_history[channel_id]),
            'frequency': list(self._frequency_history[channel_id]),
            'baseline_flow': self._baseline_flow[channel_id],
            'baseline_size': self._baseline_size[channel_id],
            'baseline_freq': self._baseline_freq[channel_id]
        }

    def get_diagnostics(self) -> Dict:
        return {
            'n_channels': self.n_channels,
            'window_size': self.window_size,
            'ewma_alpha': self._ewma_alpha,
            'thresholds': {
                'blockage_flow_ratio': self._threshold_blockage_flow,
                'blockage_size_ratio': self._threshold_blockage_size,
                'instability_cv': self._threshold_instability
            },
            'baselines_set': sum(1 for b in self._baseline_flow if b is not None),
            'channel_statuses': [
                {
                    'channel_id': s.channel_id,
                    'fault_type': s.fault_type.value,
                    'confidence': s.confidence,
                    'blockage_severity': s.blockage_severity,
                    'anomaly_score': s.anomaly_score
                }
                for s in self._channel_statuses
            ]
        }
