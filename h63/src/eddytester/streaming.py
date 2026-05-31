import numpy as np
from typing import List, Optional, Tuple, Dict, Union, Callable
from dataclasses import dataclass, field
from collections import deque
import time
import threading
import queue
from abc import ABC, abstractmethod

from .data_io import EddyCurrentData
from .config import Config
from .preprocessing import Preprocessor
from .features import FeatureExtractor
from .identification import CrackIdentifier


@dataclass
class StreamConfig:
    buffer_size: int = Config.STREAM_BUFFER_SIZE
    overlap: int = Config.STREAM_OVERLAP
    sampling_rate: float = Config.SAMPLING_RATE
    n_frequencies: int = len(Config.DEFAULT_FREQUENCIES)
    n_channels: int = 1
    alarm_threshold: float = Config.ALARM_THRESHOLD
    alarm_cooldown: float = Config.ALARM_COOLDOWN


@dataclass
class StreamDataChunk:
    chunk_id: int
    timestamp: float
    impedance: np.ndarray
    positions: Optional[np.ndarray] = None
    timestamps: Optional[np.ndarray] = None
    metadata: Dict = field(default_factory=dict)

    def to_eddy_current_data(self, frequencies: List[float]) -> EddyCurrentData:
        if self.impedance.ndim == 2:
            impedance = self.impedance
        elif self.impedance.ndim == 3:
            impedance = self.impedance[0]
        else:
            raise ValueError(f"Unsupported impedance shape: {self.impedance.shape}")
        
        return EddyCurrentData(
            impedance=impedance,
            frequencies=frequencies,
            positions=self.positions,
            timestamps=self.timestamps,
            metadata={**self.metadata, 'chunk_id': self.chunk_id, 'chunk_timestamp': self.timestamp}
        )


@dataclass
class AlarmEvent:
    alarm_id: int
    timestamp: float
    chunk_id: int
    confidence: float
    position: Optional[float] = None
    crack_length: Optional[float] = None
    crack_depth: Optional[float] = None
    severity: str = 'warning'
    message: str = ''
    raw_data: Optional[np.ndarray] = None

    def to_dict(self) -> Dict:
        return {
            'alarm_id': self.alarm_id,
            'timestamp': self.timestamp,
            'chunk_id': self.chunk_id,
            'confidence': self.confidence,
            'position': self.position,
            'crack_length': self.crack_length,
            'crack_depth': self.crack_depth,
            'severity': self.severity,
            'message': self.message,
            'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.timestamp))
        }


class DataSource(ABC):
    @abstractmethod
    def read_chunk(self) -> Optional[StreamDataChunk]:
        pass

    @abstractmethod
    def is_complete(self) -> bool:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class SimulatedDataSource(DataSource):
    def __init__(self,
                 n_chunks: int = 100,
                 chunk_size: int = 256,
                 n_frequencies: int = 4,
                 n_channels: int = 1,
                 sampling_rate: float = 1000.0,
                 include_cracks: bool = True,
                 crack_probability: float = 0.1):
        self.n_chunks = n_chunks
        self.chunk_size = chunk_size
        self.n_frequencies = n_frequencies
        self.n_channels = n_channels
        self.sampling_rate = sampling_rate
        self.include_cracks = include_cracks
        self.crack_probability = crack_probability
        self.current_chunk = 0
        self.global_position = 0.0
        self.rng = np.random.RandomState(Config.RANDOM_SEED)

    def read_chunk(self) -> Optional[StreamDataChunk]:
        if self.current_chunk >= self.n_chunks:
            return None
        
        n_samples = self.chunk_size
        impedance = np.zeros((self.n_channels, n_samples, self.n_frequencies), dtype=complex)
        
        positions = np.zeros(n_samples)
        timestamps = np.zeros(n_samples)
        
        for s in range(n_samples):
            positions[s] = self.global_position
            timestamps[s] = time.time() + s / self.sampling_rate
            self.global_position += 0.001
            
            for c in range(self.n_channels):
                for f in range(self.n_frequencies):
                    base_real = 1.0 + self.rng.randn() * 0.01
                    base_imag = -0.5 + self.rng.randn() * 0.01
                    impedance[c, s, f] = base_real + 1j * base_imag
        
        if self.include_cracks and self.rng.rand() < self.crack_probability:
            crack_start = self.rng.randint(0, n_samples // 2)
            crack_end = crack_start + self.rng.randint(10, 50)
            
            for s in range(crack_start, crack_end):
                crack_intensity = np.sin(np.pi * (s - crack_start) / (crack_end - crack_start))
                for c in range(self.n_channels):
                    for f in range(self.n_frequencies):
                        perturbation = crack_intensity * 0.3 * (1 + f / self.n_frequencies)
                        impedance[c, s, f] += perturbation - 1j * perturbation * 0.5
        
        chunk = StreamDataChunk(
            chunk_id=self.current_chunk,
            timestamp=time.time(),
            impedance=impedance,
            positions=positions.reshape(-1, 1),
            timestamps=timestamps,
            metadata={'simulated': True}
        )
        
        self.current_chunk += 1
        return chunk

    def is_complete(self) -> bool:
        return self.current_chunk >= self.n_chunks

    def close(self) -> None:
        pass


class FileDataSource(DataSource):
    def __init__(self,
                 data: EddyCurrentData,
                 chunk_size: int = 256,
                 overlap: int = 0):
        self.data = data
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.current_idx = 0
        self.total_samples = data.impedance.shape[0]
        self.chunk_counter = 0

    def read_chunk(self) -> Optional[StreamDataChunk]:
        if self.current_idx >= self.total_samples:
            return None
        
        end_idx = min(self.current_idx + self.chunk_size, self.total_samples)
        n_samples = end_idx - self.current_idx
        
        impedance = self.data.impedance[self.current_idx:end_idx]
        if impedance.ndim == 2:
            impedance = impedance[np.newaxis, :, :]
        
        positions = self.data.positions[self.current_idx:end_idx] if self.data.positions is not None else None
        timestamps = self.data.timestamps[self.current_idx:end_idx] if self.data.timestamps is not None else None
        
        chunk = StreamDataChunk(
            chunk_id=self.chunk_counter,
            timestamp=time.time(),
            impedance=impedance,
            positions=positions,
            timestamps=timestamps,
            metadata={'file_source': True, 'start_idx': self.current_idx, 'end_idx': end_idx}
        )
        
        self.current_idx += self.chunk_size - self.overlap
        self.chunk_counter += 1
        return chunk

    def is_complete(self) -> bool:
        return self.current_idx >= self.total_samples

    def close(self) -> None:
        pass


class AlarmHandler(ABC):
    @abstractmethod
    def handle_alarm(self, alarm: AlarmEvent) -> None:
        pass


class ConsoleAlarmHandler(AlarmHandler):
    def handle_alarm(self, alarm: AlarmEvent) -> None:
        severity_colors = {
            'info': '\033[94m',
            'warning': '\033[93m',
            'critical': '\033[91m',
        }
        color = severity_colors.get(alarm.severity, '\033[0m')
        reset = '\033[0m'
        
        print(f"{color}[ALARM {alarm.alarm_id}] {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alarm.timestamp))}")
        print(f"  Confidence: {alarm.confidence:.2f} | Severity: {alarm.severity}")
        if alarm.position is not None:
            print(f"  Position: {alarm.position*1000:.2f}mm")
        if alarm.crack_length is not None:
            print(f"  Length: {alarm.crack_length*1000:.2f}mm | Depth: {alarm.crack_depth*1000:.2f}mm")
        if alarm.message:
            print(f"  Message: {alarm.message}")
        print(f"{reset}")


class FileAlarmHandler(AlarmHandler):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._file = open(filepath, 'a')

    def handle_alarm(self, alarm: AlarmEvent) -> None:
        line = (f"{alarm.timestamp:.3f},{alarm.alarm_id},{alarm.chunk_id},"
                f"{alarm.confidence:.3f},{alarm.position or -1},{alarm.crack_length or -1},"
                f"{alarm.crack_depth or -1},{alarm.severity},\"{alarm.message}\"\n")
        self._file.write(line)
        self._file.flush()

    def close(self) -> None:
        self._file.close()


class CallbackAlarmHandler(AlarmHandler):
    def __init__(self, callback: Callable[[AlarmEvent], None]):
        self.callback = callback

    def handle_alarm(self, alarm: AlarmEvent) -> None:
        self.callback(alarm)


class StreamProcessor:
    def __init__(self,
                 config: Optional[StreamConfig] = None,
                 preprocessor: Optional[Preprocessor] = None,
                 feature_extractor: Optional[FeatureExtractor] = None,
                 crack_identifier: Optional[CrackIdentifier] = None,
                 alarm_handlers: Optional[List[AlarmHandler]] = None,
                 frequencies: Optional[List[float]] = None):
        self.config = config or StreamConfig()
        self.preprocessor = preprocessor or Preprocessor()
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.crack_identifier = crack_identifier or CrackIdentifier()
        self.alarm_handlers = alarm_handlers or [ConsoleAlarmHandler()]
        self.frequencies = frequencies or Config.DEFAULT_FREQUENCIES
        
        self.buffer = deque(maxlen=self.config.buffer_size)
        self.position_buffer = deque(maxlen=self.config.buffer_size)
        self.timestamp_buffer = deque(maxlen=self.config.buffer_size)
        
        self.chunk_counter = 0
        self.alarm_counter = 0
        self.last_alarm_time = 0.0
        
        self.processed_chunks = []
        self.alarm_history = []
        
        self.is_running = False
        self._data_queue = queue.Queue(maxsize=10)
        self._processing_thread = None

    def process_chunk(self, chunk: StreamDataChunk) -> Dict:
        self.chunk_counter += 1
        
        impedance = chunk.impedance
        if impedance.ndim == 3:
            impedance_2d = impedance[0]
        else:
            impedance_2d = impedance
        
        n_new = impedance_2d.shape[0]
        
        for i in range(n_new):
            self.buffer.append(impedance_2d[i])
            if chunk.positions is not None:
                pos = chunk.positions[i]
                if isinstance(pos, np.ndarray):
                    pos = pos[0] if pos.ndim > 0 else pos
                self.position_buffer.append(pos)
            if chunk.timestamps is not None:
                ts = chunk.timestamps[i]
                if isinstance(ts, np.ndarray):
                    ts = ts[0] if ts.ndim > 0 else ts
                self.timestamp_buffer.append(ts)
        
        if len(self.buffer) < self.config.overlap * 2:
            return {
                'chunk_id': chunk.chunk_id,
                'processed': False,
                'reason': 'buffer_filling',
                'buffer_size': len(self.buffer)
            }
        
        buffer_array = np.array(self.buffer)
        positions_array = np.array(self.position_buffer).reshape(-1, 1) if len(self.position_buffer) > 0 else None
        timestamps_array = np.array(self.timestamp_buffer) if len(self.timestamp_buffer) > 0 else None
        
        ec_data = EddyCurrentData(
            impedance=buffer_array,
            frequencies=self.frequencies,
            positions=positions_array,
            timestamps=timestamps_array,
            metadata={'chunk_id': chunk.chunk_id}
        )
        
        try:
            processed_data = self.preprocessor.process(ec_data)
        except Exception as e:
            return {
                'chunk_id': chunk.chunk_id,
                'processed': False,
                'reason': f'preprocessing_error: {str(e)}'
            }
        
        try:
            features = self.feature_extractor.extract(processed_data)
        except Exception as e:
            return {
                'chunk_id': chunk.chunk_id,
                'processed': False,
                'reason': f'feature_extraction_error: {str(e)}'
            }
        
        crack_result = {
            'has_crack': False,
            'confidence': 0.0
        }
        
        if self.crack_identifier.is_trained:
            try:
                crack_result = self.crack_identifier.identify(processed_data)
            except Exception as e:
                return {
                    'chunk_id': chunk.chunk_id,
                    'processed': False,
                    'reason': f'identification_error: {str(e)}'
                }
        
        crack_prob = crack_result.get('probability', crack_result.get('confidence', 0.0))
        if isinstance(crack_prob, np.ndarray):
            crack_prob = float(np.max(crack_prob))
        
        triggered_alarm = None
        
        if (crack_prob >= self.config.alarm_threshold and 
            (time.time() - self.last_alarm_time) >= self.config.alarm_cooldown):
            
            severity = 'critical' if crack_prob >= 0.95 else 'warning'
            
            alarm = AlarmEvent(
                alarm_id=self.alarm_counter,
                timestamp=time.time(),
                chunk_id=chunk.chunk_id,
                confidence=float(crack_prob),
                position=crack_result.get('position_mm', None),
                crack_length=crack_result.get('estimated_length_mm', None),
                crack_depth=crack_result.get('depth_estimation', None),
                severity=severity,
                message=f"Crack detected with {crack_prob*100:.1f}% confidence",
                raw_data=buffer_array
            )
            
            triggered_alarm = alarm
            self._trigger_alarm(alarm)
        
        result = {
            'chunk_id': chunk.chunk_id,
            'processed': True,
            'buffer_size': len(self.buffer),
            'features': features,
            'crack_detection': crack_result,
            'crack_probability': float(crack_prob),
            'alarm_triggered': triggered_alarm is not None,
            'alarm': triggered_alarm.to_dict() if triggered_alarm else None,
            'processed_data': processed_data
        }
        
        self.processed_chunks.append({
            'chunk_id': chunk.chunk_id,
            'timestamp': chunk.timestamp,
            'crack_probability': float(crack_prob),
            'alarm_triggered': triggered_alarm is not None
        })
        
        return result

    def _trigger_alarm(self, alarm: AlarmEvent) -> None:
        self.alarm_counter += 1
        self.last_alarm_time = time.time()
        self.alarm_history.append(alarm.to_dict())
        
        for handler in self.alarm_handlers:
            try:
                handler.handle_alarm(alarm)
            except Exception as e:
                print(f"Error in alarm handler: {e}")

    def process_stream(self,
                       data_source: DataSource,
                       max_chunks: Optional[int] = None,
                       real_time: bool = False,
                       verbose: bool = True) -> List[Dict]:
        results = []
        chunk_count = 0
        
        while not data_source.is_complete():
            chunk = data_source.read_chunk()
            if chunk is None:
                break
            
            result = self.process_chunk(chunk)
            results.append(result)
            
            if verbose and result['processed']:
                status = f"Chunk {chunk.chunk_id:4d} | " \
                         f"Buffer: {result.get('buffer_size', 0):4d} | " \
                         f"Crack Prob: {result.get('crack_probability', 0):.3f} | " \
                         f"Alarm: {'YES' if result['alarm_triggered'] else 'no'}"
                print(status)
            
            chunk_count += 1
            if max_chunks is not None and chunk_count >= max_chunks:
                break
            
            if real_time:
                time.sleep(1.0 / self.config.sampling_rate * chunk.impedance.shape[1])
        
        return results

    def start_async(self, data_source: DataSource) -> None:
        self.is_running = True
        
        def _source_reader():
            while self.is_running and not data_source.is_complete():
                chunk = data_source.read_chunk()
                if chunk is not None:
                    self._data_queue.put(chunk)
                else:
                    break
            
            self._data_queue.put(None)
        
        def _processor():
            while self.is_running:
                try:
                    chunk = self._data_queue.get(timeout=1.0)
                    if chunk is None:
                        break
                    self.process_chunk(chunk)
                except queue.Empty:
                    continue
        
        self._source_thread = threading.Thread(target=_source_reader, daemon=True)
        self._processor_thread = threading.Thread(target=_processor, daemon=True)
        
        self._source_thread.start()
        self._processor_thread.start()

    def stop_async(self) -> None:
        self.is_running = False
        if hasattr(self, '_source_thread'):
            self._source_thread.join(timeout=2.0)
        if hasattr(self, '_processor_thread'):
            self._processor_thread.join(timeout=2.0)

    def get_statistics(self) -> Dict:
        total_chunks = len(self.processed_chunks)
        processed_chunks = [c for c in self.processed_chunks if len(self.processed_chunks) > 0]
        alarm_count = sum(1 for c in self.processed_chunks if c.get('alarm_triggered', False))
        
        if self.processed_chunks:
            probs = [c['crack_probability'] for c in self.processed_chunks]
            avg_prob = np.mean(probs)
            max_prob = np.max(probs)
        else:
            avg_prob = 0.0
            max_prob = 0.0
        
        return {
            'total_chunks': total_chunks,
            'alarm_count': alarm_count,
            'avg_crack_probability': float(avg_prob),
            'max_crack_probability': float(max_prob),
            'alarm_rate': alarm_count / total_chunks if total_chunks > 0 else 0.0,
            'buffer_size': len(self.buffer),
            'running': self.is_running
        }

    def save_alarm_history(self, filepath: str) -> None:
        import json
        with open(filepath, 'w') as f:
            json.dump({
                'alarms': self.alarm_history,
                'statistics': self.get_statistics()
            }, f, indent=2)


class RealTimeMonitor:
    def __init__(self,
                 stream_processor: StreamProcessor,
                 update_interval: float = 1.0):
        self.stream_processor = stream_processor
        self.update_interval = update_interval
        self.is_monitoring = False

    def start(self, data_source: DataSource) -> None:
        self.is_monitoring = True
        self.stream_processor.start_async(data_source)
        
        import threading
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        while self.is_monitoring:
            stats = self.stream_processor.get_statistics()
            print("\033[2J\033[H")
            print("=" * 60)
            print("REAL-TIME EDDY CURRENT MONITORING")
            print("=" * 60)
            print(f"Chunks Processed: {stats['total_chunks']}")
            print(f"Alarms Triggered: {stats['alarm_count']}")
            print(f"Avg Crack Probability: {stats['avg_crack_probability']:.3f}")
            print(f"Max Crack Probability: {stats['max_crack_probability']:.3f}")
            print(f"Alarm Rate: {stats['alarm_rate']*100:.1f}%")
            print(f"Buffer Size: {stats['buffer_size']}")
            print("=" * 60)
            print(f"Recent Alarms:")
            for alarm in self.stream_processor.alarm_history[-5:]:
                print(f"  [{alarm['time_str']}] {alarm['severity'].upper()} - "
                      f"conf={alarm['confidence']:.2f} pos={alarm.get('position', 'N/A')}")
            print("=" * 60)
            print("Press Ctrl+C to stop...")
            
            time.sleep(self.update_interval)

    def stop(self) -> None:
        self.is_monitoring = False
        self.stream_processor.stop_async()
