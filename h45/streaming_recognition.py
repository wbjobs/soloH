import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Generator, Dict, Any
from collections import deque
from config import StreamingConfig
from event_detection import EventDetector, KeyEvent
from feature_extraction import FeatureExtractor, KeyFeatures
from classifier import ClassificationResult
from language_model import ViterbiDecoder
from side_channel_protection import SideChannelProtector, FakeKeyDetectionResult


@dataclass
class StreamingResult:
    text: str
    key_sequence: List[str]
    confidences: List[float]
    is_partial: bool = False
    window_start_time: float = 0.0
    window_end_time: float = 0.0
    classification_results: List[ClassificationResult] = field(default_factory=list)
    events: List[KeyEvent] = field(default_factory=list)
    fake_key_results: List[FakeKeyDetectionResult] = field(default_factory=list)


@dataclass
class StreamingBuffer:
    audio_buffer: np.ndarray
    processed_samples: int = 0
    last_event_end_sample: int = 0
    event_queue: deque = field(default_factory=deque)
    feature_queue: deque = field(default_factory=deque)
    classification_queue: deque = field(default_factory=deque)
    confirmed_keys: List[str] = field(default_factory=list)
    confirmed_confidences: List[float] = field(default_factory=list)
    pending_results: List[StreamingResult] = field(default_factory=list)


class StreamingRecognizer:
    def __init__(self, 
                 config: StreamingConfig,
                 event_detector: EventDetector,
                 feature_extractor: FeatureExtractor,
                 sample_rate: int,
                 num_channels: int,
                 classifier: Optional[Any] = None,
                 language_decoder: Optional[ViterbiDecoder] = None,
                 side_channel_protector: Optional[SideChannelProtector] = None):
        self.config = config
        self.event_detector = event_detector
        self.feature_extractor = feature_extractor
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.classifier = classifier
        self.language_decoder = language_decoder
        self.side_channel_protector = side_channel_protector
        
        self.window_samples = int(config.window_size * sample_rate)
        self.overlap_samples = int(config.window_overlap * sample_rate)
        self.hop_samples = self.window_samples - self.overlap_samples
        self.buffer_samples = int(config.buffer_size * sample_rate)
        self.min_event_gap_samples = int(config.min_event_gap * sample_rate)
        
        self.total_samples_processed = 0
        self.current_window_start = 0
        
        max_buffer_samples = self.window_samples + self.buffer_samples
        self.audio_buffer = np.zeros((num_channels, max_buffer_samples), dtype=np.float32)
        self.buffer_write_pos = 0
        
        self.processed_events: Dict[int, KeyEvent] = {}
        self.event_id_counter = 0
        
        self.confirmed_keys: List[str] = []
        self.confirmed_confidences: List[float] = []
        self.confirmed_classifications: List[ClassificationResult] = []
        self.confirmed_events: List[KeyEvent] = []
        
        self.partial_keys: List[str] = []
        self.partial_confidences: List[float] = []
    
    def process_audio(self, audio_chunk: np.ndarray) -> List[StreamingResult]:
        if len(audio_chunk.shape) == 1:
            audio_chunk = audio_chunk.reshape(1, -1)
        
        if audio_chunk.shape[0] != self.num_channels:
            audio_chunk = np.repeat(audio_chunk[:1, :], self.num_channels, axis=0)
        
        chunk_samples = audio_chunk.shape[1]
        results = []
        
        self._write_to_buffer(audio_chunk)
        
        while self.buffer_write_pos >= self.current_window_start + self.window_samples:
            window_result = self._process_window()
            if window_result:
                results.append(window_result)
        
        return results
    
    def _write_to_buffer(self, audio_chunk: np.ndarray):
        chunk_samples = audio_chunk.shape[1]
        buffer_size = self.audio_buffer.shape[1]
        
        if self.buffer_write_pos + chunk_samples > buffer_size:
            shift = self.hop_samples
            keep_samples = buffer_size - shift
            
            self.audio_buffer[:, :keep_samples] = self.audio_buffer[:, shift:].copy()
            self.audio_buffer[:, keep_samples:] = 0
            self.buffer_write_pos = keep_samples
            self.current_window_start -= shift
        
        start = self.buffer_write_pos
        end = min(start + chunk_samples, buffer_size)
        self.audio_buffer[:, start:end] = audio_chunk[:, :end - start]
        self.buffer_write_pos = end
    
    def _process_window(self) -> Optional[StreamingResult]:
        window_start = self.current_window_start
        window_end = window_start + self.window_samples
        
        if window_end > self.buffer_write_pos:
            return None
        
        window_audio = self.audio_buffer[:, window_start:window_end].copy()
        
        window_time_start = window_start / self.sample_rate
        window_time_end = window_end / self.sample_rate
        
        events = self.event_detector.detect(window_audio)
        
        abs_events = []
        for event in events:
            abs_start = window_start + event.start_sample
            abs_end = window_start + event.end_sample
            abs_peak = window_start + event.peak_sample
            
            event_id = self._get_event_id(abs_peak)
            
            if event_id not in self.processed_events:
                event.start_sample = abs_start
                event.end_sample = abs_end
                event.peak_sample = abs_peak
                event.start_time = abs_start / self.sample_rate
                event.end_time = abs_end / self.sample_rate
                
                self.processed_events[event_id] = event
                abs_events.append(event)
        
        if abs_events and self.side_channel_protector:
            abs_events, fake_results = self.side_channel_protector.filter_events(
                abs_events, self.audio_buffer[:, :self.buffer_write_pos]
            )
        
        if abs_events and self.classifier:
            features = self.feature_extractor.extract_batch(
                abs_events, self.audio_buffer[:, :self.buffer_write_pos]
            )
            
            classifications = self.classifier.predict(features, top_k=5)
            
            if self.language_decoder:
                classifications = self.language_decoder.decode(classifications)
            
            if self.config.emit_partial_results:
                for cls, event in zip(classifications, abs_events):
                    self.partial_keys.append(cls.key_name)
                    self.partial_confidences.append(cls.confidence)
            
            confirm_threshold = window_end - self.overlap_samples // 2
            new_confirmed = []
            
            pending_events = list(zip(classifications, abs_events))
            still_partial = []
            
            for cls, event in pending_events:
                if event.peak_sample < confirm_threshold:
                    self.confirmed_keys.append(cls.key_name)
                    self.confirmed_confidences.append(cls.confidence)
                    self.confirmed_classifications.append(cls)
                    self.confirmed_events.append(event)
                    new_confirmed.append(cls.key_name)
                else:
                    still_partial.append((cls, event))
            
            self.partial_keys = [cls.key_name for cls, e in still_partial]
            self.partial_confidences = [cls.confidence for cls, e in still_partial]
        
        self.current_window_start += self.hop_samples
        self.total_samples_processed = window_end
        
        is_partial = len(self.partial_keys) > 0
        
        if self.config.emit_partial_results:
            display_keys = self.confirmed_keys + self.partial_keys
            display_confidences = self.confirmed_confidences + self.partial_confidences
        else:
            display_keys = self.confirmed_keys.copy()
            display_confidences = self.confirmed_confidences.copy()
        
        from utils import keys_to_text
        text = keys_to_text(display_keys)
        
        return StreamingResult(
            text=text,
            key_sequence=display_keys,
            confidences=display_confidences,
            is_partial=is_partial,
            window_start_time=window_time_start,
            window_end_time=window_time_end,
            classification_results=self.confirmed_classifications + 
                (self.confirmed_classifications[-len(self.partial_keys):] 
                 if self.partial_keys else []),
            events=self.confirmed_events + 
                ([self.confirmed_events[-1]] if self.partial_keys else []),
            fake_key_results=[]
        )
    
    def _get_event_id(self, peak_sample: int) -> int:
        tolerance = self.min_event_gap_samples
        
        for event_id, event in self.processed_events.items():
            if abs(event.peak_sample - peak_sample) < tolerance:
                return event_id
        
        self.event_id_counter += 1
        return self.event_id_counter
    
    def finalize(self) -> StreamingResult:
        while self.buffer_write_pos > self.current_window_start:
            result = self._process_window()
            if result is None:
                break
        
        from utils import keys_to_text
        
        return StreamingResult(
            text=keys_to_text(self.confirmed_keys),
            key_sequence=self.confirmed_keys.copy(),
            confidences=self.confirmed_confidences.copy(),
            is_partial=False,
            window_start_time=0.0,
            window_end_time=self.total_samples_processed / self.sample_rate,
            classification_results=self.confirmed_classifications.copy(),
            events=self.confirmed_events.copy(),
            fake_key_results=[]
        )
    
    def stream_generator(self, audio_source: Generator[np.ndarray, None, None]
                         ) -> Generator[StreamingResult, None, StreamingResult]:
        for audio_chunk in audio_source:
            results = self.process_audio(audio_chunk)
            for result in results:
                yield result
        
        return self.finalize()
    
    def get_current_text(self) -> str:
        from utils import keys_to_text
        if self.config.emit_partial_results:
            all_keys = self.confirmed_keys + self.partial_keys
        else:
            all_keys = self.confirmed_keys
        return keys_to_text(all_keys)
    
    def get_confirmed_text(self) -> str:
        from utils import keys_to_text
        return keys_to_text(self.confirmed_keys)
    
    def reset(self):
        self.audio_buffer.fill(0)
        self.buffer_write_pos = 0
        self.current_window_start = 0
        self.total_samples_processed = 0
        self.processed_events.clear()
        self.event_id_counter = 0
        self.confirmed_keys.clear()
        self.confirmed_confidences.clear()
        self.confirmed_classifications.clear()
        self.confirmed_events.clear()
        self.partial_keys.clear()
        self.partial_confidences.clear()


class SimulatedAudioStream:
    def __init__(self, audio: np.ndarray, chunk_size: int = 4800):
        self.audio = audio
        self.chunk_size = chunk_size
        self.position = 0
        
        if len(self.audio.shape) == 1:
            self.audio = self.audio.reshape(1, -1)
    
    def __iter__(self):
        return self
    
    def __next__(self) -> np.ndarray:
        if self.position >= self.audio.shape[1]:
            raise StopIteration
        
        start = self.position
        end = min(start + self.chunk_size, self.audio.shape[1])
        chunk = self.audio[:, start:end].copy()
        self.position = end
        
        return chunk
    
    def generator(self) -> Generator[np.ndarray, None, None]:
        while self.position < self.audio.shape[1]:
            start = self.position
            end = min(start + self.chunk_size, self.audio.shape[1])
            chunk = self.audio[:, start:end].copy()
            self.position = end
            yield chunk


def simulate_streaming_recognition(audio: np.ndarray,
                                   recognizer: StreamingRecognizer,
                                   chunk_size: int = 4800
                                   ) -> Tuple[List[StreamingResult], StreamingResult]:
    stream = SimulatedAudioStream(audio, chunk_size)
    results = []
    final_result = None
    
    try:
        for chunk in stream.generator():
            chunk_results = recognizer.process_audio(chunk)
            results.extend(chunk_results)
    except Exception as e:
        print(f"Streaming error: {e}")
    
    final_result = recognizer.finalize()
    
    return results, final_result


def build_streaming_recognizer(config: StreamingConfig,
                                event_detector: EventDetector,
                                feature_extractor: FeatureExtractor,
                                sample_rate: int,
                                num_channels: int,
                                classifier: Optional[Any] = None,
                                language_decoder: Optional[ViterbiDecoder] = None,
                                side_channel_protector: Optional[SideChannelProtector] = None
                                ) -> StreamingRecognizer:
    return StreamingRecognizer(
        config=config,
        event_detector=event_detector,
        feature_extractor=feature_extractor,
        sample_rate=sample_rate,
        num_channels=num_channels,
        classifier=classifier,
        language_decoder=language_decoder,
        side_channel_protector=side_channel_protector
    )
