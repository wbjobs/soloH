import numpy as np
import argparse
import sys
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Generator
from config import Config, KEYBOARD_KEYS, CHAR_TO_KEY
from utils import read_wav_file, keys_to_text, get_key_index, softmax
from event_detection import EventDetector, KeyEvent
from feature_extraction import FeatureExtractor, KeyFeatures
from classifier import CNNTransformerClassifier, KNNClassifier, ClassificationResult
from source_localization import SourceLocalizer, SourceLocation
from calibration import MicrophoneCalibrator, CalibrationResult
from error_analysis import ErrorAnalyzer, ErrorAnalysisResult
from language_model import ViterbiDecoder, build_language_model_from_config
from side_channel_protection import (
    SideChannelProtector, FakeKeyDetectionResult, ProtectionStats,
    build_side_channel_protector
)
from streaming_recognition import (
    StreamingRecognizer, StreamingResult, simulate_streaming_recognition,
    build_streaming_recognizer
)


@dataclass
class RecognitionResult:
    key_sequence: List[str]
    key_indices: List[int]
    confidences: List[float]
    text: str
    locations: List[Optional[SourceLocation]]
    features: List[KeyFeatures]
    classification_results: List[ClassificationResult]
    events: List[KeyEvent]
    corrected_text: str = ""
    original_text: str = ""
    fake_key_results: List[FakeKeyDetectionResult] = field(default_factory=list)
    side_channel_stats: Optional[ProtectionStats] = None


class KeyRecognitionSystem:
    def __init__(self, config: Config):
        self.config = config
        self.sample_rate = config.audio.sample_rate
        self.num_channels = config.audio.num_channels
        
        self.event_detector = EventDetector(config.event_detection, self.sample_rate)
        self.feature_extractor = FeatureExtractor(
            config.feature_extraction, self.sample_rate, self.num_channels
        )
        self.localizer = SourceLocalizer(
            config.localization, self.sample_rate, self.num_channels
        )
        self.calibrator = MicrophoneCalibrator(
            config.calibration, self.sample_rate, self.num_channels
        )
        self.error_analyzer = ErrorAnalyzer(config.classifier.num_classes)
        
        self.language_decoder = build_language_model_from_config(
            config.language_model, config.classifier.num_classes
        )
        self.side_channel_protector = build_side_channel_protector(
            config.side_channel_protection, self.sample_rate, self.num_channels
        )
        self.streaming_recognizer: Optional[StreamingRecognizer] = None
        
        self.classifier = None
        self.is_calibrated = False
        self.use_location_prior = True
        self.enable_language_model = True
        self.enable_side_channel_protection = True

    def calibrate(self, calibration_audio: np.ndarray, 
                  calibration_sequence: Optional[str] = None) -> CalibrationResult:
        print("Starting system calibration...")
        
        calibration_result = self.calibrator.calibrate(
            calibration_audio, calibration_sequence
        )
        
        self.config.localization.mic_positions = calibration_result.mic_positions
        self.localizer.mic_positions = calibration_result.mic_positions
        self.is_calibrated = True
        
        print(f"Calibration completed in {calibration_result.iterations} iterations")
        print(f"Reconstruction error: {calibration_result.reconstruction_error:.6f} seconds")
        print(f"Converged: {calibration_result.converged}")
        print("Calibrated microphone positions:")
        for i, pos in enumerate(calibration_result.mic_positions):
            print(f"  Mic {i}: ({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f})")
        
        return calibration_result

    def init_classifier(self, classifier_type: str = 'knn',
                        mel_shape: Tuple[int, int] = (32, 128),
                        tdoa_dim: int = 768):
        if classifier_type == 'cnn_transformer':
            print("Initializing CNN+Transformer classifier...")
            self.classifier = CNNTransformerClassifier(
                self.config.classifier, mel_shape, tdoa_dim
            )
        elif classifier_type == 'knn':
            print("Initializing KNN classifier...")
            self.classifier = KNNClassifier(
                num_classes=self.config.classifier.num_classes
            )
        else:
            raise ValueError(f"Unknown classifier type: {classifier_type}")

    def train(self, training_audios: List[np.ndarray], 
              training_labels: List[List[int]],
              classifier_type: str = 'knn'):
        if len(training_audios) != len(training_labels):
            raise ValueError("Number of audios and labels must match")
        
        all_features = []
        all_labels = []
        all_events_list = []
        
        print("Extracting training features...")
        for audio, labels in zip(training_audios, training_labels):
            events = self.event_detector.detect(audio)
            num_events = min(len(events), len(labels))
            all_events_list.extend(events[:num_events])
            all_labels.extend(labels[:num_events])
        
        all_features = self.feature_extractor.extract_batch(
            all_events_list, training_audios[0] if training_audios else None, 
            fit_whitener=True
        )
        
        print(f"Total training samples: {len(all_features)}")
        
        if isinstance(self.classifier, KNNClassifier):
            print("Training KNN classifier...")
            self.classifier.fit(all_features, all_labels)
        elif isinstance(self.classifier, CNNTransformerClassifier):
            print("Training CNN+Transformer classifier...")
            batch_size = 8
            num_epochs = 10
            
            for epoch in range(num_epochs):
                total_loss = 0.0
                num_batches = 0
                
                indices = np.random.permutation(len(all_features))
                shuffled_features = [all_features[i] for i in indices]
                shuffled_labels = [all_labels[i] for i in indices]
                
                for start_idx in range(0, len(all_features), batch_size):
                    end_idx = min(start_idx + batch_size, len(all_features))
                    batch_features = shuffled_features[start_idx:end_idx]
                    batch_labels = shuffled_labels[start_idx:end_idx]
                    
                    loss, _ = self.classifier.train_step(
                        batch_features, batch_labels
                    )
                    total_loss += loss
                    num_batches += 1
                
                avg_loss = total_loss / max(num_batches, 1)
                print(f"Epoch {epoch + 1}/{num_epochs}, Average Loss: {avg_loss:.4f}")
        
        print("Training completed.")

    def recognize(self, audio: np.ndarray, 
                  use_location: bool = True) -> RecognitionResult:
        print("Detecting key events...")
        events = self.event_detector.detect(audio)
        print(f"Detected {len(events)} key events")
        
        fake_key_results = []
        if self.enable_side_channel_protection:
            print("Applying side channel protection...")
            self.side_channel_protector.reset_stats()
            events, fake_key_results = self.side_channel_protector.filter_events(
                events, audio
            )
            stats = self.side_channel_protector.get_stats()
            print(f"Filtered out {stats.fake_events_detected} fake keys, "
                  f"keeping {len(events)} real keys")
        
        if not events:
            print("No valid events to recognize")
            return RecognitionResult(
                key_sequence=[],
                key_indices=[],
                confidences=[],
                text="",
                locations=[],
                features=[],
                classification_results=[],
                events=[],
                corrected_text="",
                original_text="",
                fake_key_results=fake_key_results,
                side_channel_stats=self.side_channel_protector.get_stats()
            )
        
        print("Extracting features...")
        features = self.feature_extractor.extract_batch(events, audio)
        
        print("Classifying keys...")
        classifications = self.classifier.predict(features, top_k=5)
        
        locations = []
        if use_location and self.is_calibrated:
            print("Performing source localization...")
            for event in events:
                start = event.start_sample
                end = event.end_sample
                event_audio = audio[:, start:end]
                location = self.localizer.localize(event_audio, method='taylor')
                locations.append(location)
                
                if self.use_location_prior:
                    idx = len(locations) - 1
                    class_probs = softmax(classifications[idx].logits)
                    refined_probs = self.localizer.combine_predictions(
                        class_probs, location, alpha=0.3
                    )
                    
                    top_indices = np.argsort(refined_probs)[::-1][:5]
                    top_k_preds = []
                    for pred_idx in top_indices:
                        from utils import get_key_name
                        key_name = get_key_name(int(pred_idx)) or f"Unknown_{pred_idx}"
                        top_k_preds.append((int(pred_idx), key_name, float(refined_probs[pred_idx])))
                    
                    classifications[idx] = ClassificationResult(
                        key_index=int(top_indices[0]),
                        key_name=top_k_preds[0][1],
                        confidence=top_k_preds[0][2],
                        logits=refined_probs,
                        top_k_predictions=top_k_preds
                    )
        else:
            locations = [None] * len(events)
        
        original_key_sequence = [c.key_name for c in classifications]
        original_text = keys_to_text(original_key_sequence)
        
        if self.enable_language_model:
            print("Applying language model correction...")
            classifications = self.language_decoder.decode(classifications)
            print(f"Applied Viterbi decoding with {len(classifications)} states")
        
        key_sequence = [c.key_name for c in classifications]
        key_indices = [c.key_index for c in classifications]
        confidences = [c.confidence for c in classifications]
        corrected_text = keys_to_text(key_sequence)
        
        print(f"Recognition completed. Recognized {len(key_sequence)} keys")
        print(f"Original text:  {original_text}")
        if corrected_text != original_text:
            print(f"Corrected text: {corrected_text}")
        
        return RecognitionResult(
            key_sequence=key_sequence,
            key_indices=key_indices,
            confidences=confidences,
            text=corrected_text,
            locations=locations,
            features=features,
            classification_results=classifications,
            events=events,
            corrected_text=corrected_text,
            original_text=original_text,
            fake_key_results=fake_key_results,
            side_channel_stats=self.side_channel_protector.get_stats()
        )

    def evaluate(self, test_audios: List[np.ndarray],
                 test_labels: List[List[int]],
                 true_texts: Optional[List[str]] = None,
                 output_report: Optional[str] = None) -> ErrorAnalysisResult:
        print("Starting evaluation...")
        
        for audio_idx, (audio, labels) in enumerate(zip(test_audios, test_labels)):
            result = self.recognize(audio, use_location=self.is_calibrated)
            
            num_events = min(len(result.key_indices), len(labels))
            for i in range(num_events):
                self.error_analyzer.add_prediction(
                    predicted_index=result.key_indices[i],
                    true_index=labels[i],
                    confidence=result.confidences[i],
                    top_k_predictions=result.classification_results[i].top_k_predictions
                )
            
            if true_texts is not None and audio_idx < len(true_texts):
                self.error_analyzer.set_texts(true_texts[audio_idx], result.text)
        
        analysis_result = self.error_analyzer.analyze()
        self.error_analyzer.print_report(analysis_result)
        
        if output_report is not None:
            self.error_analyzer.save_report(analysis_result, output_report)
            print(f"Report saved to {output_report}")
        
        return analysis_result

    def save_classifier(self, filepath: str):
        if isinstance(self.classifier, CNNTransformerClassifier):
            self.classifier.save(filepath)
            print(f"Classifier saved to {filepath}")
        else:
            import pickle
            with open(filepath, 'wb') as f:
                pickle.dump(self.classifier, f)
            print(f"Classifier saved to {filepath}")

    def load_classifier(self, filepath: str):
        try:
            self.classifier = CNNTransformerClassifier.load(filepath)
            print(f"CNN+Transformer classifier loaded from {filepath}")
        except Exception:
            import pickle
            with open(filepath, 'rb') as f:
                self.classifier = pickle.load(f)
            print(f"KNN classifier loaded from {filepath}")
    
    def init_streaming_recognizer(self):
        print("Initializing streaming recognizer...")
        self.streaming_recognizer = build_streaming_recognizer(
            config=self.config.streaming,
            event_detector=self.event_detector,
            feature_extractor=self.feature_extractor,
            sample_rate=self.sample_rate,
            num_channels=self.num_channels,
            classifier=self.classifier,
            language_decoder=self.language_decoder if self.enable_language_model else None,
            side_channel_protector=self.side_channel_protector if self.enable_side_channel_protection else None
        )
        return self.streaming_recognizer
    
    def process_streaming_chunk(self, audio_chunk: np.ndarray) -> List[StreamingResult]:
        if self.streaming_recognizer is None:
            self.init_streaming_recognizer()
        
        return self.streaming_recognizer.process_audio(audio_chunk)
    
    def finalize_streaming(self) -> StreamingResult:
        if self.streaming_recognizer is None:
            raise ValueError("Streaming recognizer not initialized")
        
        return self.streaming_recognizer.finalize()
    
    def recognize_streaming(self, audio: np.ndarray,
                            chunk_size: int = 4800
                            ) -> Tuple[List[StreamingResult], StreamingResult]:
        if self.streaming_recognizer is None:
            self.init_streaming_recognizer()
        
        self.streaming_recognizer.reset()
        
        print(f"Running streaming recognition with chunk size={chunk_size} samples...")
        results, final_result = simulate_streaming_recognition(
            audio=audio,
            recognizer=self.streaming_recognizer,
            chunk_size=chunk_size
        )
        
        print(f"Streaming completed: {len(results)} intermediate results")
        print(f"Final text: {final_result.text}")
        
        return results, final_result
    
    def train_language_model(self, texts: List[str]):
        print(f"Training language model with {len(texts)} texts...")
        self.language_decoder.train_ngram(texts)
        print("Language model training completed.")
    
    def get_keyboard_correction_candidates(self, key_name: str,
                                            max_distance: float = 0.06
                                            ) -> List[Tuple[str, float]]:
        return self.language_decoder.get_keyboard_correction_candidates(
            key_name, max_distance
        )
    
    def get_side_channel_stats(self) -> Optional[ProtectionStats]:
        return self.side_channel_protector.get_stats()
    
    def generate_fake_key_signal(self, sample_rate: int, duration: float = 0.05,
                                  fake_type: str = 'sine') -> np.ndarray:
        return self.side_channel_protector.generate_fake_key_signal(
            sample_rate, duration, fake_type
        )


def generate_key_signal(sample_rate: int, key_duration: float, 
                         keyboard_type: str = 'mechanical',
                         seed: int = None) -> np.ndarray:
    if seed is not None:
        np.random.seed(seed)
    
    key_samples = int(key_duration * sample_rate)
    t = np.linspace(0, key_duration, key_samples)
    
    if keyboard_type == 'mechanical':
        base_freqs = [800, 1500, 2500, 3500]
        decay_rates = [50, 30, 40, 60]
        amplitudes = [1.0, 0.8, 0.6, 0.4]
        click_amp = 2.0
        noise_amp = 0.1
    elif keyboard_type == 'membrane':
        base_freqs = [500, 1000, 1800, 2500]
        decay_rates = [80, 50, 60, 70]
        amplitudes = [0.8, 0.6, 0.5, 0.3]
        click_amp = 0.5
        noise_amp = 0.2
    else:
        base_freqs = [600, 1200, 2000]
        decay_rates = [60, 40, 50]
        amplitudes = [0.9, 0.7, 0.5]
        click_amp = 1.0
        noise_amp = 0.15
    
    base_signal = np.zeros(key_samples)
    for freq, decay, amp in zip(base_freqs, decay_rates, amplitudes):
        base_signal += amp * np.sin(2 * np.pi * freq * t) * np.exp(-t * decay)
    
    click_samples = int(0.01 * sample_rate)
    click_envelope = np.exp(-np.linspace(0, 5, click_samples))
    click = np.zeros(key_samples)
    if click_samples < key_samples:
        click[:click_samples] = click_amp * click_envelope * np.random.randn(click_samples)
    
    noise = noise_amp * np.random.randn(key_samples)
    
    final_signal = base_signal + click + noise
    final_signal = final_signal / (np.max(np.abs(final_signal)) + 1e-10)
    
    return final_signal


def generate_long_press_signal(sample_rate: int, total_duration: float,
                                press_count: int = 5,
                                keyboard_type: str = 'mechanical') -> np.ndarray:
    total_samples = int(total_duration * sample_rate)
    signal = np.zeros(total_samples)
    
    press_interval = total_duration / (press_count + 1)
    
    for i in range(press_count):
        center_time = press_interval * (i + 1)
        center_sample = int(center_time * sample_rate)
        
        key_duration = 0.05
        key_samples = int(key_duration * sample_rate)
        
        key_signal = generate_key_signal(sample_rate, key_duration, keyboard_type, seed=i)
        
        start_sample = center_sample - key_samples // 2
        end_sample = start_sample + key_samples
        
        if start_sample >= 0 and end_sample <= total_samples:
            signal[start_sample:end_sample] += key_signal * 0.8
    
    return signal


def generate_demo_data(sample_rate: int = 48000, num_channels: int = 4,
                       duration: float = 15.0,
                       keyboard_type: str = 'mechanical',
                       include_collisions: bool = True,
                       include_long_press: bool = True) -> Tuple[np.ndarray, List[int], str]:
    text = "hello world 123"
    keys = [CHAR_TO_KEY[c] for c in text if c in CHAR_TO_KEY]
    valid_keys = [k for k in keys if get_key_index(k) is not None]
    labels = [get_key_index(k) for k in valid_keys]
    
    num_samples = int(duration * sample_rate)
    audio = np.random.randn(num_channels, num_samples) * 0.001
    
    mic_positions = np.array([
        [0.0, 0.0, 0.0],
        [0.1, 0.0, 0.0],
        [0.1, 0.1, 0.0],
        [0.0, 0.1, 0.0]
    ])
    
    sound_speed = 343.0
    key_start_time = 0.5
    key_interval = 0.3
    
    from config import KEY_POSITIONS
    
    collision_added = False
    long_press_added = False
    all_labels = labels.copy()
    
    for key_idx, key in enumerate(valid_keys):
        if key not in KEY_POSITIONS:
            continue
        
        key_2d = KEY_POSITIONS[key]
        key_pos = np.array([0.2 + key_2d[0], 0.3 + key_2d[1], 0.0])
        
        start_time = key_start_time + key_idx * key_interval
        
        if include_collisions and key_idx == 3 and not collision_added:
            collision_key = valid_keys[key_idx + 1] if key_idx + 1 < len(valid_keys) else 'a'
            collision_key_2d = KEY_POSITIONS.get(collision_key, KEY_POSITIONS['a'])
            collision_pos = np.array([0.2 + collision_key_2d[0], 0.3 + collision_key_2d[1], 0.0])
            
            collision_offset = 0.015
            collision_time = start_time + collision_offset
            
            center_sample = int(start_time * sample_rate)
            collision_center_sample = int(collision_time * sample_rate)
            
            key_duration = 0.06
            key_samples = int(key_duration * sample_rate)
            
            base_signal1 = generate_key_signal(sample_rate, key_duration, keyboard_type, seed=key_idx)
            base_signal2 = generate_key_signal(sample_rate, key_duration, keyboard_type, seed=key_idx + 100)
            
            for ch in range(num_channels):
                mic_pos = mic_positions[ch]
                
                distance1 = np.linalg.norm(key_pos - mic_pos)
                delay1 = int(distance1 / sound_speed * sample_rate)
                attenuation1 = 1.0 / (1.0 + distance1 * 2)
                
                ch_start1 = center_sample + delay1 - key_samples // 2
                ch_end1 = ch_start1 + key_samples
                if ch_start1 >= 0 and ch_end1 <= num_samples:
                    audio[ch, ch_start1:ch_end1] += base_signal1 * attenuation1 * 0.5
                
                distance2 = np.linalg.norm(collision_pos - mic_pos)
                delay2 = int(distance2 / sound_speed * sample_rate)
                attenuation2 = 1.0 / (1.0 + distance2 * 2)
                
                ch_start2 = collision_center_sample + delay2 - key_samples // 2
                ch_end2 = ch_start2 + key_samples
                if ch_start2 >= 0 and ch_end2 <= num_samples:
                    audio[ch, ch_start2:ch_end2] += base_signal2 * attenuation2 * 0.45
            
            collision_added = True
            continue
        
        if include_long_press and key_idx == 6 and not long_press_added:
            long_press_duration = 0.8
            press_count = 4
            long_press_start = start_time
            
            long_press_signal = generate_long_press_signal(
                sample_rate, long_press_duration, press_count, keyboard_type
            )
            
            center_sample = int(long_press_start * sample_rate + long_press_duration * sample_rate // 2)
            key_duration_samples = len(long_press_signal)
            
            for ch in range(num_channels):
                mic_pos = mic_positions[ch]
                distance = np.linalg.norm(key_pos - mic_pos)
                delay = int(distance / sound_speed * sample_rate)
                attenuation = 1.0 / (1.0 + distance * 2)
                
                ch_start = center_sample + delay - key_duration_samples // 2
                ch_end = ch_start + key_duration_samples
                if ch_start >= 0 and ch_end <= num_samples:
                    audio[ch, ch_start:ch_end] += long_press_signal * attenuation * 0.5
            
            for _ in range(press_count - 1):
                if len(all_labels) > key_idx:
                    all_labels.insert(key_idx + 1, labels[key_idx])
            
            long_press_added = True
            continue
        
        center_sample = int(start_time * sample_rate)
        
        key_duration = 0.05
        key_samples = int(key_duration * sample_rate)
        
        base_signal = generate_key_signal(sample_rate, key_duration, keyboard_type, seed=key_idx)
        
        for ch in range(num_channels):
            mic_pos = mic_positions[ch]
            distance = np.linalg.norm(key_pos - mic_pos)
            delay = int(distance / sound_speed * sample_rate)
            attenuation = 1.0 / (1.0 + distance * 2)
            
            ch_start = center_sample + delay - key_samples // 2
            ch_end = ch_start + key_samples
            
            if ch_start >= 0 and ch_end <= num_samples:
                audio[ch, ch_start:ch_end] += base_signal * attenuation * 0.5
    
    audio = audio / np.max(np.abs(audio)) * 0.9
    
    return audio, all_labels, text


def main():
    parser = argparse.ArgumentParser(
        description='Multi-Channel Audio Key Recognition System'
    )
    parser.add_argument('--mode', type=str, default='demo',
                       choices=['demo', 'recognize', 'calibrate', 'train', 'evaluate'],
                       help='Operation mode')
    parser.add_argument('--input', type=str, help='Input audio file path')
    parser.add_argument('--calibration_audio', type=str, help='Calibration audio file')
    parser.add_argument('--calibration_sequence', type=str, 
                       default='the quick brown fox jumps over the lazy dog 0123456789',
                       help='Known calibration sequence')
    parser.add_argument('--classifier_type', type=str, default='knn',
                       choices=['knn', 'cnn_transformer'],
                       help='Classifier type')
    parser.add_argument('--classifier_path', type=str, 
                       help='Path to save/load classifier')
    parser.add_argument('--report_path', type=str, default='error_report.txt',
                       help='Path to save error analysis report')
    parser.add_argument('--no_location', action='store_true',
                       help='Disable location-based prior')
    
    args = parser.parse_args()
    
    config = Config()
    system = KeyRecognitionSystem(config)
    system.use_location_prior = not args.no_location
    
    system.init_classifier(args.classifier_type)
    
    if args.mode == 'demo':
        print("Running in DEMO mode with synthetic data...")
        print("=" * 70)
        print("DEMO MODE - Testing Three Key Fixes:")
        print("  1. Collision detection (near-simultaneous keys)")
        print("  2. Long press detection")
        print("  3. Keyboard type robustness (mechanical vs membrane)")
        print("=" * 70)
        
        print("\n" + "-" * 70)
        print("TEST 1: Collision and Long Press Detection")
        print("-" * 70)
        
        print("\nGenerating data with collisions and long presses...")
        calib_audio, calib_labels, calib_text = generate_demo_data(
            sample_rate=config.audio.sample_rate,
            num_channels=config.audio.num_channels,
            duration=18.0,
            keyboard_type='mechanical',
            include_collisions=True,
            include_long_press=True
        )
        
        system.calibrate(calib_audio, args.calibration_sequence)
        
        print("\nEvent Detection Analysis:")
        events = system.event_detector.detect(calib_audio)
        print(f"  Total events detected: {len(events)}")
        collision_events = [e for e in events if e.is_collision]
        long_press_events = [e for e in events if e.is_long_press]
        print(f"  Collision events: {len(collision_events)}")
        print(f"  Long press events: {len(long_press_events)}")
        
        if collision_events:
            print("\n  Collision event details:")
            for i, e in enumerate(collision_events[:3]):
                print(f"    Event {i}: t={e.start_time:.3f}s, order={e.collision_order}, "
                      f"ch={e.channel}, energy={e.peak_energy:.4f}")
        
        if long_press_events:
            print("\n  Long press event details:")
            for i, e in enumerate(long_press_events[:3]):
                print(f"    Event {i}: t={e.start_time:.3f}s, duration={e.duration:.3f}s, "
                      f"press_count={e.press_count}")
        
        print("\nGenerating training data with multiple keyboard types...")
        train_audios = []
        train_labels = []
        
        for kb_type in ['mechanical', 'membrane', 'mechanical']:
            audio, labels, text = generate_demo_data(
                sample_rate=config.audio.sample_rate,
                num_channels=config.audio.num_channels,
                duration=10.0,
                keyboard_type=kb_type,
                include_collisions=False,
                include_long_press=False
            )
            train_audios.append(audio)
            train_labels.append(labels)
        
        system.train(train_audios, train_labels, args.classifier_type)
        
        print("\n" + "-" * 70)
        print("TEST 2: Baseline Recognition (Clean Data)")
        print("-" * 70)
        
        test_audio_clean, test_labels_clean, test_text_clean = generate_demo_data(
            sample_rate=config.audio.sample_rate,
            num_channels=config.audio.num_channels,
            duration=10.0,
            keyboard_type='mechanical',
            include_collisions=False,
            include_long_press=False
        )
        
        print(f"Expected text: {test_text_clean}")
        print(f"Expected key count: {len(test_labels_clean)}")
        
        result_clean = system.recognize(test_audio_clean, use_location=True)
        
        print(f"\nRecognized text: {result_clean.text}")
        print(f"Recognized key count: {len(result_clean.key_sequence)}")
        
        print("\n" + "-" * 70)
        print("TEST 3: Collision and Long Press Detection")
        print("-" * 70)
        
        test_audio_special, test_labels_special, test_text_special = generate_demo_data(
            sample_rate=config.audio.sample_rate,
            num_channels=config.audio.num_channels,
            duration=12.0,
            keyboard_type='mechanical',
            include_collisions=True,
            include_long_press=True
        )
        
        events_special = system.event_detector.detect(test_audio_special)
        print(f"Detected {len(events_special)} events")
        
        collision_events = [e for e in events_special if e.is_collision]
        long_press_events = [e for e in events_special if e.is_long_press]
        
        print(f"  Collision events detected: {len(collision_events)}")
        print(f"  Long press events detected: {len(long_press_events)}")
        
        if collision_events:
            print("\n  Collision events:")
            for i, e in enumerate(collision_events[:5]):
                print(f"    Event {i}: t={e.start_time:.3f}s, order={e.collision_order}, "
                      f"peak={e.peak_energy:.4f}")
        
        if long_press_events:
            print("\n  Long press events:")
            for i, e in enumerate(long_press_events[:3]):
                print(f"    Event {i}: t={e.start_time:.3f}s, duration={e.duration:.3f}s, "
                      f"press_count={e.press_count}")
        
        result_special = system.recognize(test_audio_special, use_location=True)
        
        print("\nRecognition results with special events:")
        for i, (key, conf, event) in enumerate(zip(
                result_special.key_sequence, result_special.confidences, result_special.events)):
            flags = []
            if event.is_collision:
                flags.append(f"COLLISION(#{event.collision_order})")
            if event.is_long_press:
                flags.append(f"LONG_PRESS(x{event.press_count})")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"  {i:3d}: {key:10s} (conf: {conf*100:5.1f}%){flag_str}")
        
        print("\n" + "-" * 70)
        print("TEST 4: Cross-Keyboard-Type Robustness")
        print("-" * 70)
        print("Testing on membrane keyboard (trained on mixed types)...")
        
        test_audio_membrane, test_labels_membrane, test_text_membrane = generate_demo_data(
            sample_rate=config.audio.sample_rate,
            num_channels=config.audio.num_channels,
            duration=10.0,
            keyboard_type='membrane',
            include_collisions=False,
            include_long_press=False
        )
        
        result_membrane = system.recognize(test_audio_membrane, use_location=True)
        
        print(f"Expected (membrane): {test_text_membrane}")
        print(f"Recognized (membrane): {result_membrane.text}")
        
        print("\nRobust Feature Comparison (mechanical vs membrane):")
        if result_clean.features and result_membrane.features:
            f1 = result_clean.features[0].robust_features
            f2 = result_membrane.features[0].robust_features
            print(f"  Spectral Centroid: {f1.spectral_centroid:.0f} Hz vs {f2.spectral_centroid:.0f} Hz")
            print(f"  Spectral Bandwidth: {f1.spectral_bandwidth:.0f} Hz vs {f2.spectral_bandwidth:.0f} Hz")
            print(f"  Decay Rate: {f1.decay_rate:.2f} vs {f2.decay_rate:.2f}")
            print(f"  Attack Time: {f1.attack_time*1000:.1f} ms vs {f2.attack_time*1000:.1f} ms")
            print(f"  Zero Crossing Rate: {f1.zero_crossing_rate:.4f} vs {f2.zero_crossing_rate:.4f}")
        
        print("\n" + "=" * 70)
        print("ERROR ANALYSIS (Clean Mechanical Test)")
        print("=" * 70)
        system.evaluate([test_audio_clean], [test_labels_clean], [test_text_clean], args.report_path)
        
        print("\n" + "=" * 70)
        print("ERROR ANALYSIS (Membrane Keyboard Test)")
        print("=" * 70)
        membrane_report = args.report_path.replace('.txt', '_membrane.txt')
        system.error_analyzer = ErrorAnalyzer(config.classifier.num_classes)
        system.evaluate([test_audio_membrane], [test_labels_membrane], 
                       [test_text_membrane], membrane_report)
        
        if args.classifier_path:
            system.save_classifier(args.classifier_path)
    
    elif args.mode == 'recognize':
        if not args.input:
            print("Error: --input is required for recognize mode")
            sys.exit(1)
        
        if args.classifier_path:
            system.load_classifier(args.classifier_path)
        
        print(f"Loading audio from {args.input}...")
        audio, sample_rate = read_wav_file(args.input)
        config.audio.sample_rate = sample_rate
        
        result = system.recognize(audio, use_location=system.is_calibrated)
        
        print("\n" + "=" * 60)
        print("RECOGNITION RESULTS")
        print("=" * 60)
        print(f"Text: {result.text}")
        print(f"Number of keys: {len(result.key_sequence)}")
        print(f"Average confidence: {np.mean(result.confidences)*100:.1f}%")
        print("\nDetailed results:")
        for i, (key, conf) in enumerate(zip(result.key_sequence, result.confidences)):
            print(f"  {i:3d}: {key:10s} (conf: {conf*100:5.1f}%)")
    
    elif args.mode == 'calibrate':
        if not args.calibration_audio:
            print("Error: --calibration_audio is required for calibrate mode")
            sys.exit(1)
        
        print(f"Loading calibration audio from {args.calibration_audio}...")
        calib_audio, sample_rate = read_wav_file(args.calibration_audio)
        config.audio.sample_rate = sample_rate
        
        system.calibrate(calib_audio, args.calibration_sequence)
        
        print("\nCalibration completed successfully!")
    
    elif args.mode == 'train':
        if not args.input:
            print("Error: --input is required for train mode")
            sys.exit(1)
        
        print(f"Loading training audio from {args.input}...")
        train_audio, sample_rate = read_wav_file(args.input)
        config.audio.sample_rate = sample_rate
        
        print("Enter training labels (key indices separated by spaces):")
        label_input = input().strip()
        train_labels = [int(x) for x in label_input.split()]
        
        system.train([train_audio], [train_labels], args.classifier_type)
        
        if args.classifier_path:
            system.save_classifier(args.classifier_path)
    
    elif args.mode == 'evaluate':
        if not args.input:
            print("Error: --input is required for evaluate mode")
            sys.exit(1)
        
        if args.classifier_path:
            system.load_classifier(args.classifier_path)
        
        print(f"Loading test audio from {args.input}...")
        test_audio, sample_rate = read_wav_file(args.input)
        config.audio.sample_rate = sample_rate
        
        print("Enter ground truth labels (key indices separated by spaces):")
        label_input = input().strip()
        test_labels = [int(x) for x in label_input.split()]
        
        print("Enter ground truth text:")
        true_text = input().strip()
        
        system.evaluate([test_audio], [test_labels], [true_text], args.report_path)
    
    print("\nDone!")


if __name__ == '__main__':
    main()
