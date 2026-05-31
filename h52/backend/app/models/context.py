import numpy as np
from typing import Dict, Optional, List, Tuple, Deque
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class EmotionState:
    emotion: str
    confidence: float
    valence: float
    arousal: float
    probabilities: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = ""
    turn_id: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'emotion': self.emotion,
            'confidence': self.confidence,
            'valence': self.valence,
            'arousal': self.arousal,
            'probabilities': self.probabilities,
            'timestamp': self.timestamp.isoformat(),
            'session_id': self.session_id,
            'turn_id': self.turn_id
        }


@dataclass
class EmotionTransition:
    from_emotion: str
    to_emotion: str
    probability: float
    count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'from_emotion': self.from_emotion,
            'to_emotion': self.to_emotion,
            'probability': self.probability,
            'count': self.count
        }


class ConversationContextTracker:
    def __init__(
        self,
        max_history_length: int = 50,
        session_timeout_minutes: int = 30,
        transition_smoothing: float = 0.1
    ):
        self.max_history_length = max_history_length
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.transition_smoothing = transition_smoothing
        
        self.session_history: Dict[str, Deque[EmotionState]] = {}
        self.session_metadata: Dict[str, Dict] = {}
        self.transition_matrix: Dict[str, Dict[str, EmotionTransition]] = {}
        self.user_emotion_profiles: Dict[str, Dict] = {}
        
        self.emotions = ['anger', 'joy', 'sadness', 'surprise', 'disgust', 'fear', 'neutral']
        self._init_transition_matrix()
        
        self.context_weight = 0.3
        
        logger.info(f"ConversationContextTracker initialized with max_history={max_history_length}")

    def _init_transition_matrix(self):
        for from_e in self.emotions:
            self.transition_matrix[from_e] = {}
            for to_e in self.emotions:
                prob = 1.0 / len(self.emotions) if from_e == to_e else 0.5 / len(self.emotions)
                self.transition_matrix[from_e][to_e] = EmotionTransition(
                    from_emotion=from_e,
                    to_emotion=to_e,
                    probability=prob,
                    count=1 if from_e == to_e else 0
                )

    def start_session(self, session_id: str, user_id: Optional[str] = None) -> Dict:
        self.session_history[session_id] = deque(maxlen=self.max_history_length)
        self.session_metadata[session_id] = {
            'created_at': datetime.now(),
            'last_updated': datetime.now(),
            'user_id': user_id,
            'turn_count': 0,
            'emotion_shifts': 0
        }
        
        logger.info(f"Started conversation session {session_id}")
        return {
            'session_id': session_id,
            'user_id': user_id,
            'created_at': datetime.now().isoformat(),
            'max_history': self.max_history_length
        }

    def add_emotion_state(
        self,
        session_id: str,
        emotion: str,
        confidence: float,
        valence: float,
        arousal: float,
        probabilities: Dict[str, float],
        user_id: Optional[str] = None
    ) -> EmotionState:
        if session_id not in self.session_history:
            self.start_session(session_id, user_id)
        
        turn_id = self.session_metadata[session_id]['turn_count']
        state = EmotionState(
            emotion=emotion,
            confidence=confidence,
            valence=valence,
            arousal=arousal,
            probabilities=probabilities,
            session_id=session_id,
            turn_id=turn_id
        )
        
        if len(self.session_history[session_id]) > 0:
            prev_state = self.session_history[session_id][-1]
            if prev_state.emotion != state.emotion:
                self.session_metadata[session_id]['emotion_shifts'] += 1
            
            self._update_transition_matrix(prev_state.emotion, state.emotion)
        
        self.session_history[session_id].append(state)
        self.session_metadata[session_id]['last_updated'] = datetime.now()
        self.session_metadata[session_id]['turn_count'] += 1
        
        if user_id:
            self._update_user_profile(user_id, state)
        
        logger.debug(f"Added emotion state {turn_id} to session {session_id}: {emotion}")
        
        return state

    def _update_transition_matrix(self, from_emotion: str, to_emotion: str):
        transition = self.transition_matrix[from_emotion][to_emotion]
        transition.count += 1
        
        for to_e in self.emotions:
            trans = self.transition_matrix[from_emotion][to_e]
            total_count = sum(self.transition_matrix[from_emotion][e].count for e in self.emotions)
            if total_count > 0:
                new_prob = trans.count / total_count
                trans.probability = (
                    (1 - self.transition_smoothing) * new_prob +
                    self.transition_smoothing * trans.probability
                )

    def _update_user_profile(self, user_id: str, state: EmotionState):
        if user_id not in self.user_emotion_profiles:
            self.user_emotion_profiles[user_id] = {
                'emotion_counts': {e: 0 for e in self.emotions},
                'avg_valence': 0.0,
                'avg_arousal': 0.0,
                'total_states': 0,
                'emotion_transitions': {e: {e2: 0 for e2 in self.emotions} for e in self.emotions}
            }
        
        profile = self.user_emotion_profiles[user_id]
        profile['emotion_counts'][state.emotion] += 1
        profile['total_states'] += 1
        
        n = profile['total_states']
        profile['avg_valence'] = ((n - 1) * profile['avg_valence'] + state.valence) / n
        profile['avg_arousal'] = ((n - 1) * profile['avg_arousal'] + state.arousal) / n

    def get_context_aware_prediction(
        self,
        session_id: str,
        raw_probs: Dict[str, float],
        raw_valence: float,
        raw_arousal: float
    ) -> Tuple[Dict[str, float], float, float]:
        if session_id not in self.session_history or len(self.session_history[session_id]) == 0:
            return raw_probs, raw_valence, raw_arousal
        
        prev_state = self.session_history[session_id][-1]
        
        transition_probs = {}
        for to_e in self.emotions:
            transition_probs[to_e] = self.transition_matrix[prev_state.emotion][to_e].probability
        
        context_probs = {}
        for emotion in self.emotions:
            context_probs[emotion] = (
                (1 - self.context_weight) * raw_probs.get(emotion, 0) +
                self.context_weight * transition_probs[emotion]
            )
        
        total = sum(context_probs.values())
        if total > 0:
            context_probs = {k: v/total for k, v in context_probs.items()}
        
        context_valence = (
            (1 - self.context_weight) * raw_valence +
            self.context_weight * prev_state.valence
        )
        context_arousal = (
            (1 - self.context_weight) * raw_arousal +
            self.context_weight * prev_state.arousal
        )
        
        context_valence = max(-1.0, min(1.0, context_valence))
        context_arousal = max(-1.0, min(1.0, context_arousal))
        
        return context_probs, context_valence, context_arousal

    def get_session_history(self, session_id: str) -> List[EmotionState]:
        if session_id not in self.session_history:
            return []
        return list(self.session_history[session_id])

    def get_session_summary(self, session_id: str) -> Dict:
        if session_id not in self.session_metadata:
            return {}
        
        metadata = self.session_metadata[session_id]
        history = self.get_session_history(session_id)
        
        if not history:
            return {**metadata, 'error': 'No history available'}
        
        emotion_counts = {e: 0 for e in self.emotions}
        valences = []
        arousals = []
        
        for state in history:
            emotion_counts[state.emotion] += 1
            valences.append(state.valence)
            arousals.append(state.arousal)
        
        total = sum(emotion_counts.values())
        emotion_distribution = {e: c/total if total > 0 else 0 for e, c in emotion_counts.items()}
        
        dominant_emotion = max(emotion_counts, key=emotion_counts.get)
        
        emotion_shifts = self._detect_emotion_shifts(history)
        
        return {
            'session_id': session_id,
            'user_id': metadata.get('user_id'),
            'duration_seconds': (metadata['last_updated'] - metadata['created_at']).total_seconds(),
            'turn_count': metadata['turn_count'],
            'emotion_shifts': metadata['emotion_shifts'],
            'dominant_emotion': dominant_emotion,
            'emotion_distribution': emotion_distribution,
            'avg_valence': float(np.mean(valences)),
            'avg_arousal': float(np.mean(arousals)),
            'valence_trend': self._calculate_trend(valences),
            'arousal_trend': self._calculate_trend(arousals),
            'emotion_shift_points': emotion_shifts,
            'created_at': metadata['created_at'].isoformat(),
            'last_updated': metadata['last_updated'].isoformat()
        }

    def _detect_emotion_shifts(self, history: List[EmotionState]) -> List[Dict]:
        shifts = []
        for i in range(1, len(history)):
            if history[i].emotion != history[i-1].emotion:
                shifts.append({
                    'turn_id': history[i].turn_id,
                    'from': history[i-1].emotion,
                    'to': history[i].emotion,
                    'timestamp': history[i].timestamp.isoformat(),
                    'confidence_change': abs(history[i].confidence - history[i-1].confidence)
                })
        return shifts

    def _calculate_trend(self, values: List[float]) -> str:
        if len(values) < 2:
            return 'stable'
        
        n = len(values)
        x = np.arange(n)
        slope, _ = np.polyfit(x, values, 1)
        
        if slope > 0.05:
            return 'increasing'
        elif slope < -0.05:
            return 'decreasing'
        else:
            return 'stable'

    def get_transition_matrix(self) -> List[Dict]:
        transitions = []
        for from_e in self.emotions:
            for to_e in self.emotions:
                transitions.append(self.transition_matrix[from_e][to_e].to_dict())
        return transitions

    def cleanup_expired_sessions(self):
        now = datetime.now()
        expired = []
        for session_id, metadata in self.session_metadata.items():
            if now - metadata['last_updated'] > self.session_timeout:
                expired.append(session_id)
        
        for session_id in expired:
            if session_id in self.session_history:
                del self.session_history[session_id]
            if session_id in self.session_metadata:
                del self.session_metadata[session_id]
            logger.info(f"Cleaned up expired session {session_id}")
        
        return len(expired)

    def get_user_profile(self, user_id: str) -> Dict:
        profile = self.user_emotion_profiles.get(user_id)
        if not profile:
            return {}
        
        total = profile['total_states']
        emotion_dist = {e: c/total if total > 0 else 0 for e, c in profile['emotion_counts'].items()}
        
        return {
            'user_id': user_id,
            'total_interactions': total,
            'emotion_distribution': emotion_dist,
            'avg_valence': profile['avg_valence'],
            'avg_arousal': profile['avg_arousal'],
            'dominant_emotion': max(profile['emotion_counts'], key=profile['emotion_counts'].get)
        }

    def end_session(self, session_id: str) -> Dict:
        summary = self.get_session_summary(session_id)
        
        if session_id in self.session_history:
            del self.session_history[session_id]
        if session_id in self.session_metadata:
            del self.session_metadata[session_id]
        
        logger.info(f"Ended session {session_id}")
        return summary
