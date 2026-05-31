export type EmotionCategory = 'anger' | 'joy' | 'sadness' | 'surprise' | 'disgust' | 'fear' | 'neutral';

export type Modality = 'audio' | 'video' | 'text';

export interface EmotionProbabilities {
  anger: number;
  joy: number;
  sadness: number;
  surprise: number;
  disgust: number;
  fear: number;
  neutral: number;
}

export interface ValenceArousal {
  valence: number;
  arousal: number;
}

export interface ModalityResult {
  contribution: number;
  features: number[];
  emotionProbabilities: EmotionProbabilities;
}

export interface AttentionMatrix {
  timeSteps: number;
  modalities: Modality[];
  weights: number[][];
}

export interface TimeSeriesPoint {
  time: number;
  emotion: EmotionCategory;
  valence: number;
  arousal: number;
  probabilities: EmotionProbabilities;
}

export interface EmotionResult {
  id: string;
  timestamp: number;
  emotion: {
    category: EmotionCategory;
    confidence: number;
    probabilities: EmotionProbabilities;
  };
  valenceArousal: ValenceArousal;
  modalities: {
    audio: ModalityResult;
    video: ModalityResult;
    text: ModalityResult;
  };
  attentionWeights: AttentionMatrix;
  timeSeries: TimeSeriesPoint[];
  transcript: string;
}

export interface UploadResponse {
  videoId: string;
  filename: string;
  size: number;
  duration: number;
}

export interface AnalyzeRequest {
  modalities?: Modality[];
  includeAttention?: boolean;
  timeStep?: number;
}

export interface AnalyzeResponse {
  taskId: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;
}

export interface ResultResponse {
  taskId: string;
  status: 'completed';
  result: EmotionResult;
  processingTime: number;
}

export interface StreamFrame {
  frame: string;
  audio?: string;
  timestamp: number;
}

export interface StreamResult {
  timestamp: number;
  emotion: EmotionCategory;
  confidence: number;
  valence: number;
  arousal: number;
  probabilities: EmotionProbabilities;
  modalityContributions: Record<Modality, number>;
}

export interface HistoryItem {
  id: string;
  videoId: string;
  createdAt: string;
  primaryEmotion: EmotionCategory;
  confidence: number;
  valence: number;
  arousal: number;
  duration: number;
}

export type RecordingStatus = 'idle' | 'requesting' | 'recording' | 'stopped' | 'uploading' | 'analyzing' | 'completed' | 'error';

export interface RecordingState {
  status: RecordingStatus;
  stream: MediaStream | null;
  mediaRecorder: MediaRecorder | null;
  recordedChunks: Blob[];
  recordedBlob: Blob | null;
  duration: number;
  videoUrl: string | null;
  error: string | null;
}

export const EMOTION_LABELS: Record<EmotionCategory, string> = {
  anger: '愤怒',
  joy: '快乐',
  sadness: '悲伤',
  surprise: '惊讶',
  disgust: '厌恶',
  fear: '恐惧',
  neutral: '中性'
};

export const EMOTION_COLORS: Record<EmotionCategory, string> = {
  anger: '#e74c3c',
  joy: '#f1c40f',
  sadness: '#3498db',
  surprise: '#e67e22',
  disgust: '#27ae60',
  fear: '#9b59b6',
  neutral: '#95a5a6'
};

export const MODALITY_LABELS: Record<Modality, string> = {
  audio: '语音',
  video: '面部表情',
  text: '文本内容'
};

export const MODALITY_COLORS: Record<Modality, string> = {
  audio: '#667eea',
  video: '#f093fb',
  text: '#4facfe'
};
