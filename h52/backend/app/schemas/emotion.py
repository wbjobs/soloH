from pydantic import BaseModel, Field
from typing import Literal, List, Dict
from datetime import datetime
import uuid

EmotionCategory = Literal['anger', 'joy', 'sadness', 'surprise', 'disgust', 'fear', 'neutral']
Modality = Literal['audio', 'video', 'text']
RecordingStatus = Literal['idle', 'requesting', 'recording', 'stopped', 'uploading', 'analyzing', 'completed', 'error']

EMOTION_LABELS: Dict[EmotionCategory, str] = {
    'anger': '愤怒',
    'joy': '快乐',
    'sadness': '悲伤',
    'surprise': '惊讶',
    'disgust': '厌恶',
    'fear': '恐惧',
    'neutral': '中性'
}

EMOTION_COLORS: Dict[EmotionCategory, str] = {
    'anger': '#e74c3c',
    'joy': '#f1c40f',
    'sadness': '#3498db',
    'surprise': '#e67e22',
    'disgust': '#27ae60',
    'fear': '#9b59b6',
    'neutral': '#95a5a6'
}

MODALITY_LABELS: Dict[Modality, str] = {
    'audio': '语音',
    'video': '面部表情',
    'text': '文本内容'
}

MODALITY_COLORS: Dict[Modality, str] = {
    'audio': '#667eea',
    'video': '#f093fb',
    'text': '#4facfe'
}


class EmotionProbabilities(BaseModel):
    anger: float = Field(ge=0, le=1, default=0)
    joy: float = Field(ge=0, le=1, default=0)
    sadness: float = Field(ge=0, le=1, default=0)
    surprise: float = Field(ge=0, le=1, default=0)
    disgust: float = Field(ge=0, le=1, default=0)
    fear: float = Field(ge=0, le=1, default=0)
    neutral: float = Field(ge=0, le=1, default=0)


class ValenceArousal(BaseModel):
    valence: float = Field(ge=-1, le=1, default=0)
    arousal: float = Field(ge=-1, le=1, default=0)


class ModalityResult(BaseModel):
    contribution: float = Field(ge=0, le=1, default=0)
    features: List[float] = Field(default_factory=list)
    emotionProbabilities: EmotionProbabilities = Field(default_factory=EmotionProbabilities)


class AttentionMatrix(BaseModel):
    timeSteps: int = Field(default=0)
    modalities: List[Modality] = Field(default_factory=lambda: ['audio', 'video', 'text'])
    weights: List[List[float]] = Field(default_factory=list)


class TimeSeriesPoint(BaseModel):
    time: int = Field(default=0)
    emotion: EmotionCategory = Field(default='neutral')
    valence: float = Field(ge=-1, le=1, default=0)
    arousal: float = Field(ge=-1, le=1, default=0)
    probabilities: EmotionProbabilities = Field(default_factory=EmotionProbabilities)


class EmotionResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    duration: float = Field(default=0.0)
    emotion: dict = Field(default_factory=lambda: {
        'category': 'neutral',
        'confidence': 0.0,
        'probabilities': EmotionProbabilities().model_dump()
    })
    valenceArousal: ValenceArousal = Field(default_factory=ValenceArousal)
    modalities: dict = Field(default_factory=lambda: {
        'audio': ModalityResult().model_dump(),
        'video': ModalityResult().model_dump(),
        'text': ModalityResult().model_dump()
    })
    attentionWeights: AttentionMatrix = Field(default_factory=AttentionMatrix)
    timeSeries: List[TimeSeriesPoint] = Field(default_factory=list)
    transcript: str = Field(default='')
    userId: str | None = Field(default=None)
    sessionId: str | None = Field(default=None)
    personalized: bool = Field(default=False)
    contextAware: bool = Field(default=False)
    adversarialCheck: dict | None = Field(default=None)
    emotionTransition: dict | None = Field(default=None)
    
    class Config:
        extra = 'allow'


class UploadResponse(BaseModel):
    videoId: str
    filename: str
    size: int
    duration: float


class AnalyzeRequest(BaseModel):
    modalities: List[Modality] | None = Field(default=None)
    includeAttention: bool = Field(default=True)
    timeStep: int = Field(default=2)
    userId: str | None = Field(default=None)
    sessionId: str | None = Field(default=None)


class AnalyzeResponse(BaseModel):
    taskId: str
    status: Literal['queued', 'processing', 'completed', 'failed'] = Field(default='queued')
    progress: float = Field(default=0.0, ge=0, le=100)


class ResultResponse(BaseModel):
    taskId: str
    status: Literal['completed'] = Field(default='completed')
    result: EmotionResult
    processingTime: float = Field(default=0.0)


class StreamFrame(BaseModel):
    frame: str
    audio: str | None = Field(default=None)
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class StreamResult(BaseModel):
    timestamp: int
    emotion: EmotionCategory
    confidence: float = Field(ge=0, le=1)
    valence: float = Field(ge=-1, le=1)
    arousal: float = Field(ge=-1, le=1)
    probabilities: EmotionProbabilities
    modalityContributions: Dict[Modality, float]


class HistoryItem(BaseModel):
    id: str
    videoId: str
    createdAt: str
    primaryEmotion: EmotionCategory
    confidence: float
    valence: float
    arousal: float
    duration: float


class CalibrationStartResponse(BaseModel):
    userId: str
    sessionStarted: str
    requiredSamples: int
    currentSamples: int


class CalibrationSampleRequest(BaseModel):
    userId: str
    facialLandmarks: List[float] | None = None
    voiceFeatures: List[float] | None = None
    textFeatures: Dict[str, float] | None = None
    emotionProbabilities: Dict[str, float] | None = None
    valence: float | None = None
    arousal: float | None = None


class CalibrationSampleResponse(BaseModel):
    userId: str
    currentSamples: int
    requiredSamples: int
    canComplete: bool


class CalibrationCompleteResponse(BaseModel):
    userId: str
    isCalibrated: bool
    calibrationSamples: int
    emotionBaseline: Dict[str, float]
    valenceBaseline: float
    arousalBaseline: float


class SessionStartRequest(BaseModel):
    sessionId: str
    userId: str | None = None


class SessionStartResponse(BaseModel):
    sessionId: str
    userId: str | None
    createdAt: str
    maxHistory: int


class AdversarialDetectionResponse(BaseModel):
    isAdversarial: bool
    confidence: float
    detectionMethod: str
    anomalyScores: Dict[str, float]
    reasons: List[str]
    timestamp: str


class EnhancedEmotionResult(EmotionResult):
    userId: str | None = None
    sessionId: str | None = None
    personalized: bool = False
    contextAware: bool = False
    adversarialCheck: AdversarialDetectionResponse | None = None
    emotionTransition: Dict[str, float] | None = None
