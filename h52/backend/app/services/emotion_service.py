import os
import tempfile
import numpy as np
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import uuid
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.models import (
    AudioFeatureExtractor,
    FacialFeatureExtractor,
    ASRTranscriber,
    TextFeatureExtractor,
    MultimodalFusionTransformer,
)
from app.models.personalization import PersonalizationCalibrator
from app.models.context import ConversationContextTracker
from app.models.adversarial import AdversarialSampleDetector
from app.schemas import (
    EmotionResult,
    EmotionProbabilities,
    ModalityResult,
    AttentionMatrix,
    TimeSeriesPoint,
    StreamResult,
    HistoryItem,
    ValenceArousal,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class KalmanFilter1D:
    def __init__(
        self,
        process_noise: float = 0.01,
        measurement_noise: float = 0.1,
        estimation_error: float = 1.0,
        initial_value: float = 0.0
    ):
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.estimation_error = estimation_error
        self.current_estimate = initial_value
        self.posteri_error = estimation_error
        self.priori_error = estimation_error
        self.kalman_gain = 0.0

    def update(self, measurement: float) -> float:
        self.priori_error = self.posteri_error + self.process_noise
        
        self.kalman_gain = self.priori_error / (self.priori_error + self.measurement_noise)
        
        self.current_estimate = self.current_estimate + self.kalman_gain * (measurement - self.current_estimate)
        
        self.posteri_error = (1 - self.kalman_gain) * self.priori_error
        
        return self.current_estimate

    def reset(self, initial_value: float = 0.0):
        self.current_estimate = initial_value
        self.posteri_error = self.estimation_error
        self.priori_error = self.estimation_error


class EmotionKalmanFilter:
    def __init__(self, num_emotions: int = 7):
        self.emotion_filters = [
            KalmanFilter1D(process_noise=0.02, measurement_noise=0.15, estimation_error=1.0, initial_value=1.0/num_emotions)
            for _ in range(num_emotions)
        ]
        self.valence_filter = KalmanFilter1D(process_noise=0.03, measurement_noise=0.2, estimation_error=1.0, initial_value=0.0)
        self.arousal_filter = KalmanFilter1D(process_noise=0.03, measurement_noise=0.2, estimation_error=1.0, initial_value=0.0)
        self.emotion_keys = ['anger', 'joy', 'sadness', 'surprise', 'disgust', 'fear', 'neutral']

    def smooth(self, emotion_probs: Dict[str, float], valence: float, arousal: float) -> Tuple[Dict[str, float], float, float]:
        smoothed_probs = {}
        for i, key in enumerate(self.emotion_keys):
            if i < len(self.emotion_filters):
                smoothed_probs[key] = self.emotion_filters[i].update(emotion_probs.get(key, 0.0))
        
        total = sum(smoothed_probs.values())
        if total > 0:
            smoothed_probs = {k: v / total for k, v in smoothed_probs.items()}
        
        smoothed_valence = self.valence_filter.update(valence)
        smoothed_arousal = self.arousal_filter.update(arousal)
        
        smoothed_valence = max(-1.0, min(1.0, smoothed_valence))
        smoothed_arousal = max(-1.0, min(1.0, smoothed_arousal))
        
        return smoothed_probs, smoothed_valence, smoothed_arousal

    def reset(self):
        for f in self.emotion_filters:
            f.reset(initial_value=1.0/len(self.emotion_filters))
        self.valence_filter.reset(0.0)
        self.arousal_filter.reset(0.0)


class EmotionAnalysisService:
    def __init__(self):
        self.device = getattr(settings, 'DEVICE', 'cpu')
        
        self.audio_extractor = AudioFeatureExtractor(device=self.device)
        self.video_extractor = FacialFeatureExtractor(device=self.device)
        self.asr_transcriber = ASRTranscriber(
            model_size=getattr(settings, 'WHISPER_MODEL_SIZE', 'base'),
            device=self.device
        )
        self.text_extractor = TextFeatureExtractor(device=self.device)
        self.fusion_model = MultimodalFusionTransformer(device=self.device)
        
        self.audio_extractor.eval()
        self.video_extractor.eval()
        self.text_extractor.eval()
        self.fusion_model.eval()
        
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        self.timeseries_kalman = EmotionKalmanFilter(num_emotions=7)
        
        self.stream_kalman = EmotionKalmanFilter(num_emotions=7)
        
        self.enable_smoothing = True
        
        self.personalization = PersonalizationCalibrator(min_calibration_samples=5)
        self.context_tracker = ConversationContextTracker(max_history_length=50)
        self.adversarial_detector = AdversarialSampleDetector(threshold=0.45)
        
        self.feature_history: Dict[str, List[np.ndarray]] = {
            'audio': [],
            'video': [],
            'text': []
        }
        self.max_feature_history = 100
        
        self.enable_personalization = True
        self.enable_context = True
        self.enable_adversarial_detection = True
        
        logger.info(f"EmotionAnalysisService initialized on {self.device}")

    def _extract_audio_from_video(self, video_path: str) -> str:
        try:
            import moviepy.editor as mp
            video = mp.VideoFileClip(video_path)
            audio = video.audio
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                audio_path = f.name
            
            audio.write_audiofile(audio_path, codec='pcm_s16le')
            video.close()
            
            return audio_path
        except Exception as e:
            logger.warning(f"Failed to extract audio with moviepy: {e}. Trying ffmpeg...")
            try:
                import ffmpeg
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    audio_path = f.name
                
                (
                    ffmpeg
                    .input(video_path)
                    .output(audio_path, acodec='pcm_s16le', ar=16000, ac=1)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                return audio_path
            except Exception as e2:
                logger.error(f"Failed to extract audio with ffmpeg: {e2}")
                return ""

    async def analyze_video(
        self,
        video_path: str,
        include_attention: bool = True,
        time_step: int = 2,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> EmotionResult:
        loop = asyncio.get_event_loop()
        
        try:
            audio_path = await loop.run_in_executor(
                self.executor, self._extract_audio_from_video, video_path
            )
            
            audio_result, video_result, transcript = await asyncio.gather(
                loop.run_in_executor(
                    self.executor, self._process_audio, audio_path
                ),
                loop.run_in_executor(
                    self.executor, self._process_video, video_path, time_step
                ),
                loop.run_in_executor(
                    self.executor, self._transcribe_audio, audio_path
                )
            )
            
            text_result = await loop.run_in_executor(
                self.executor, self._process_text, transcript
            )
            
            if audio_path and os.path.exists(audio_path):
                os.unlink(audio_path)
            
            fusion_result = await loop.run_in_executor(
                self.executor,
                self._fuse_modalities,
                audio_result,
                video_result,
                text_result,
                include_attention
            )
            
            result = self._build_final_result(
                audio_result,
                video_result,
                text_result,
                fusion_result,
                transcript,
                time_step,
                user_id=user_id,
                session_id=session_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing video: {e}", exc_info=True)
            raise

    def _process_audio(self, audio_path: str) -> Dict:
        if not audio_path or not os.path.exists(audio_path):
            return {
                'features': np.zeros((30, 768), dtype=np.float32),
                'features_sequence': np.zeros((30, 768), dtype=np.float32),
                'emotion_probabilities': EmotionProbabilities().model_dump(),
                'emotion_sequence': [EmotionProbabilities().model_dump() for _ in range(30)],
                'valence': 0.0,
                'arousal': 0.0,
                'va_sequence': [(0.0, 0.0) for _ in range(30)],
                'num_frames': 30,
            }
        
        result = self.audio_extractor(audio_path, return_sequence=True)
        
        if len(result['features'].shape) == 3:
            features_seq = result['features'][0]
        else:
            features_seq = result['features']
        
        num_frames = features_seq.shape[0]
        target_frames = 30
        
        if num_frames != target_frames:
            indices = np.linspace(0, num_frames - 1, target_frames, dtype=int)
            features_seq = features_seq[indices]
        
        avg_features = np.mean(features_seq, axis=0)
        
        return {
            'features': avg_features,
            'features_sequence': features_seq,
            'emotion_probabilities': result['emotion_probabilities'],
            'emotion_sequence': [result['emotion_probabilities'] for _ in range(target_frames)],
            'valence': result['valence'],
            'arousal': result['arousal'],
            'va_sequence': [(result['valence'], result['arousal']) for _ in range(target_frames)],
            'num_frames': target_frames,
        }

    def _process_video(self, video_path: str, sample_rate: int) -> Dict:
        result = self.video_extractor.process_video(
            video_path, sample_rate=sample_rate, max_frames=30
        )
        return result

    def _transcribe_audio(self, audio_path: str) -> str:
        if not audio_path or not os.path.exists(audio_path):
            return ""
        
        transcript, _ = self.asr_transcriber.transcribe(audio_path)
        return transcript

    def _process_text(self, text: str) -> Dict:
        result = self.text_extractor(text, return_sequence=True)
        
        if len(result['features'].shape) == 3:
            features_seq = result['features'][0]
        else:
            features_seq = result['features']
        
        if len(features_seq.shape) == 1:
            features_seq = np.tile(features_seq, (30, 1))
        elif features_seq.shape[0] < 30:
            padding = np.tile(features_seq[-1:], (30 - features_seq.shape[0], 1))
            features_seq = np.concatenate([features_seq, padding], axis=0)
        else:
            indices = np.linspace(0, features_seq.shape[0] - 1, 30, dtype=int)
            features_seq = features_seq[indices]
        
        avg_features = np.mean(features_seq, axis=0)
        
        return {
            'features': avg_features,
            'features_sequence': features_seq,
            'emotion_probabilities': result['emotion_probabilities'],
            'emotion_sequence': [result['emotion_probabilities'] for _ in range(30)],
            'valence': result['valence'],
            'arousal': result['arousal'],
            'va_sequence': [(result['valence'], result['arousal']) for _ in range(30)],
            'num_frames': 30,
        }

    def _fuse_modalities(
        self,
        audio_result: Dict,
        video_result: Dict,
        text_result: Dict,
        include_attention: bool
    ) -> Dict:
        audio_features = audio_result['features_sequence']
        video_features = video_result['features_sequence']
        text_features = text_result['features_sequence']
        
        result = self.fusion_model(
            audio_features,
            video_features,
            text_features,
            return_attention=include_attention
        )
        
        return result

    def _build_final_result(
        self,
        audio_result: Dict,
        video_result: Dict,
        text_result: Dict,
        fusion_result: Dict,
        transcript: str,
        time_step: int,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> EmotionResult:
        raw_emotion_probs = fusion_result['emotion']['probabilities']
        raw_valence = fusion_result['valenceArousal']['valence']
        raw_arousal = fusion_result['valenceArousal']['arousal']
        
        personalized = False
        context_aware = False
        emotion_transition = None
        
        if self.enable_personalization and user_id:
            try:
                adjusted_probs, adjusted_valence, adjusted_arousal = self.personalization.adjust_emotion(
                    user_id, raw_emotion_probs, raw_valence, raw_arousal
                )
                fusion_result['emotion']['probabilities'] = adjusted_probs
                fusion_result['valenceArousal']['valence'] = adjusted_valence
                fusion_result['valenceArousal']['arousal'] = adjusted_arousal
                fusion_result['emotion']['category'] = max(adjusted_probs, key=adjusted_probs.get)
                fusion_result['emotion']['confidence'] = adjusted_probs[fusion_result['emotion']['category']]
                personalized = True
                logger.info(f"Applied personalization for user {user_id}")
            except Exception as e:
                logger.warning(f"Personalization failed for user {user_id}: {e}")
        
        if self.enable_context and session_id:
            try:
                context_probs, context_valence, context_arousal = self.context_tracker.get_context_aware_prediction(
                    session_id,
                    fusion_result['emotion']['probabilities'],
                    fusion_result['valenceArousal']['valence'],
                    fusion_result['valenceArousal']['arousal']
                )
                
                history = self.context_tracker.get_session_history(session_id)
                if history:
                    prev_emotion = history[-1].emotion
                    curr_emotion = max(context_probs, key=context_probs.get)
                    emotion_transition = {
                        'from': prev_emotion,
                        'to': curr_emotion,
                        'transition_probability': self.context_tracker.transition_matrix[prev_emotion][curr_emotion].probability
                    }
                
                fusion_result['emotion']['probabilities'] = context_probs
                fusion_result['valenceArousal']['valence'] = context_valence
                fusion_result['valenceArousal']['arousal'] = context_arousal
                fusion_result['emotion']['category'] = max(context_probs, key=context_probs.get)
                fusion_result['emotion']['confidence'] = context_probs[fusion_result['emotion']['category']]
                context_aware = True
                
                self.context_tracker.add_emotion_state(
                    session_id,
                    fusion_result['emotion']['category'],
                    fusion_result['emotion']['confidence'],
                    fusion_result['valenceArousal']['valence'],
                    fusion_result['valenceArousal']['arousal'],
                    fusion_result['emotion']['probabilities'],
                    user_id=user_id
                )
                logger.info(f"Applied context awareness for session {session_id}")
            except Exception as e:
                logger.warning(f"Context awareness failed for session {session_id}: {e}")
        
        adversarial_check = None
        if self.enable_adversarial_detection:
            try:
                self._update_feature_history(audio_result, video_result, text_result)
                
                adv_result = self.adversarial_detector.detect(
                    audio_features=audio_result['features'],
                    video_features=video_result['features'],
                    text_features=text_result['features'],
                    fused_probabilities=fusion_result['emotion']['probabilities'],
                    audio_probs=audio_result['emotion_probabilities'],
                    video_probs=video_result['emotion_probabilities'],
                    text_probs=text_result['emotion_probabilities'],
                    feature_history=self.feature_history
                )
                
                adversarial_check = {
                    'isAdversarial': adv_result.is_adversarial,
                    'confidence': adv_result.confidence,
                    'detectionMethod': adv_result.detection_method,
                    'anomalyScores': adv_result.anomaly_scores,
                    'reasons': adv_result.reasons,
                    'timestamp': adv_result.timestamp.isoformat()
                }
                
                if adv_result.is_adversarial:
                    logger.warning(f"Adversarial sample detected: {adv_result.confidence:.2f} - {adv_result.reasons}")
            except Exception as e:
                logger.warning(f"Adversarial detection failed: {e}")
        
        modalities = {
            'audio': ModalityResult(
                contribution=fusion_result['modalityContributions']['audio'],
                features=audio_result['features'].tolist(),
                emotionProbabilities=EmotionProbabilities(**audio_result['emotion_probabilities'])
            ).model_dump(),
            'video': ModalityResult(
                contribution=fusion_result['modalityContributions']['video'],
                features=video_result['features'].tolist(),
                emotionProbabilities=EmotionProbabilities(**video_result['emotion_probabilities'])
            ).model_dump(),
            'text': ModalityResult(
                contribution=fusion_result['modalityContributions']['text'],
                features=text_result['features'].tolist(),
                emotionProbabilities=EmotionProbabilities(**text_result['emotion_probabilities'])
            ).model_dump(),
        }
        
        time_series = self._build_time_series(
            audio_result, video_result, text_result, fusion_result, time_step
        )
        
        attention_weights = AttentionMatrix(
            timeSteps=fusion_result['attentionWeights']['timeSteps'],
            modalities=fusion_result['attentionWeights']['modalities'],
            weights=fusion_result['attentionWeights']['weights']
        )
        
        result_data = {
            'id': str(uuid.uuid4()),
            'timestamp': int(datetime.now().timestamp() * 1000),
            'emotion': fusion_result['emotion'],
            'valenceArousal': ValenceArousal(**fusion_result['valenceArousal']),
            'modalities': modalities,
            'attentionWeights': attention_weights,
            'timeSeries': time_series,
            'transcript': transcript,
            'userId': user_id,
            'sessionId': session_id,
            'personalized': personalized,
            'contextAware': context_aware,
            'adversarialCheck': adversarial_check,
            'emotionTransition': emotion_transition,
            'duration': 0.0
        }
        
        result = EmotionResult(**result_data)
        
        return result

    def _update_feature_history(self, audio_result: Dict, video_result: Dict, text_result: Dict):
        for modality, result in [('audio', audio_result), ('video', video_result), ('text', text_result)]:
            if 'features' in result and result['features'] is not None:
                self.feature_history[modality].append(result['features'].copy())
                if len(self.feature_history[modality]) > self.max_feature_history:
                    self.feature_history[modality].pop(0)

    def _build_time_series(
        self,
        audio_result: Dict,
        video_result: Dict,
        text_result: Dict,
        fusion_result: Dict,
        time_step: int
    ) -> List[TimeSeriesPoint]:
        num_steps = len(fusion_result['attentionWeights']['weights'])
        time_series = []
        
        emotions = ['anger', 'joy', 'sadness', 'surprise', 'disgust', 'fear', 'neutral']
        
        if self.enable_smoothing:
            self.timeseries_kalman.reset()
        
        for t in range(num_steps):
            audio_probs = audio_result['emotion_sequence'][min(t, len(audio_result['emotion_sequence']) - 1)]
            video_probs = video_result['emotion_sequence'][min(t, len(video_result['emotion_sequence']) - 1)]
            text_probs = text_result['emotion_sequence'][min(t, len(text_result['emotion_sequence']) - 1)]
            
            weights = fusion_result['attentionWeights']['weights'][t]
            
            combined_probs = {}
            for emotion in emotions:
                combined_probs[emotion] = (
                    weights[0] * audio_probs[emotion] +
                    weights[1] * video_probs[emotion] +
                    weights[2] * text_probs[emotion]
                )
            
            audio_va = audio_result['va_sequence'][min(t, len(audio_result['va_sequence']) - 1)]
            video_va = video_result['va_sequence'][min(t, len(video_result['va_sequence']) - 1)]
            text_va = text_result['va_sequence'][min(t, len(text_result['va_sequence']) - 1)]
            
            valence = (
                weights[0] * audio_va[0] +
                weights[1] * video_va[0] +
                weights[2] * text_va[0]
            )
            arousal = (
                weights[0] * audio_va[1] +
                weights[1] * video_va[1] +
                weights[2] * text_va[1]
            )
            
            if self.enable_smoothing:
                smoothed_probs, smoothed_valence, smoothed_arousal = self.timeseries_kalman.smooth(
                    combined_probs, valence, arousal
                )
                final_probs = smoothed_probs
                final_valence = smoothed_valence
                final_arousal = smoothed_arousal
            else:
                final_probs = combined_probs
                final_valence = valence
                final_arousal = arousal
            
            dominant_emotion = max(final_probs, key=final_probs.get)
            confidence = final_probs[dominant_emotion]
            
            time_series.append(TimeSeriesPoint(
                time=t * time_step,
                emotion=dominant_emotion,
                valence=final_valence,
                arousal=final_arousal,
                probabilities=EmotionProbabilities(**final_probs)
            ))
        
        return time_series

    def process_stream_frame(
        self,
        frame_base64: str,
        audio_chunk: Optional[np.ndarray] = None,
        transcript_text: Optional[str] = None
    ) -> StreamResult:
        timestamp = int(datetime.now().timestamp() * 1000)
        
        video_result = self.video_extractor.process_stream_frame(frame_base64)
        
        if video_result is None:
            video_result = {
                'features': np.zeros(512, dtype=np.float32),
                'emotion_probabilities': EmotionProbabilities().model_dump(),
                'valence': 0.0,
                'arousal': 0.0,
            }
        
        audio_features = np.zeros(768, dtype=np.float32)
        audio_probs = EmotionProbabilities().model_dump()
        audio_valence = 0.0
        audio_arousal = 0.0
        
        if audio_chunk is not None:
            try:
                _, emotion_logits, va = self.audio_extractor.extract_features(
                    audio_chunk, return_sequence=False
                )
                audio_probs = self.audio_extractor.get_emotion_probabilities(emotion_logits)
                va_values = va.cpu().numpy()[0]
                audio_valence = float(va_values[0])
                audio_arousal = float(va_values[1])
            except Exception as e:
                logger.warning(f"Error processing audio chunk: {e}")
        
        text_features = np.zeros(768, dtype=np.float32)
        text_probs = EmotionProbabilities().model_dump()
        text_valence = 0.0
        text_arousal = 0.0
        
        if transcript_text and transcript_text.strip():
            text_result = self.text_extractor(transcript_text)
            if len(text_result['features'].shape) > 1:
                text_features = text_result['features'][0]
            else:
                text_features = text_result['features']
            text_probs = text_result['emotion_probabilities']
            text_valence = text_result['valence']
            text_arousal = text_result['arousal']
        
        audio_seq = np.tile(audio_features, (10, 1))
        video_seq = np.tile(video_result['features'], (10, 1))
        text_seq = np.tile(text_features, (10, 1))
        
        fusion_result = self.fusion_model(
            audio_seq, video_seq, text_seq, return_attention=False
        )
        
        raw_probs = fusion_result['emotion']['probabilities']
        raw_valence = fusion_result['valenceArousal']['valence']
        raw_arousal = fusion_result['valenceArousal']['arousal']
        
        if self.enable_smoothing:
            smoothed_probs, smoothed_valence, smoothed_arousal = self.stream_kalman.smooth(
                raw_probs, raw_valence, raw_arousal
            )
            final_emotion = max(smoothed_probs, key=smoothed_probs.get)
            final_confidence = smoothed_probs[final_emotion]
            final_probs = smoothed_probs
            final_valence = smoothed_valence
            final_arousal = smoothed_arousal
        else:
            final_emotion = fusion_result['emotion']['category']
            final_confidence = fusion_result['emotion']['confidence']
            final_probs = raw_probs
            final_valence = raw_valence
            final_arousal = raw_arousal
        
        result = StreamResult(
            timestamp=timestamp,
            emotion=final_emotion,
            confidence=final_confidence,
            valence=final_valence,
            arousal=final_arousal,
            probabilities=EmotionProbabilities(**final_probs),
            modalityContributions=fusion_result['modalityContributions']
        )
        
        return result

    def reset_stream_filter(self):
        if hasattr(self, 'stream_kalman'):
            self.stream_kalman.reset()
        logger.info("Stream Kalman filter reset")

    def get_history(
        self,
        page: int = 1,
        page_size: int = 20,
        results: Optional[List[EmotionResult]] = None
    ) -> Tuple[List[HistoryItem], int]:
        if results is None:
            results = []
        
        history_items = []
        for result in results:
            item = HistoryItem(
                id=result.id,
                videoId=f"video_{result.id}",
                createdAt=datetime.fromtimestamp(result.timestamp / 1000).isoformat(),
                primaryEmotion=result.emotion['category'],
                confidence=result.emotion['confidence'],
                valence=result.valenceArousal.valence,
                arousal=result.valenceArousal.arousal,
                duration=60.0
            )
            history_items.append(item)
        
        total = len(history_items)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_items = history_items[start:end]
        
        return paginated_items, total


_service_instance: Optional[EmotionAnalysisService] = None


def get_emotion_service() -> EmotionAnalysisService:
    global _service_instance
    if _service_instance is None:
        _service_instance = EmotionAnalysisService()
    return _service_instance
