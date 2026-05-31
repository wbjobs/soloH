export interface HandLandmark {
  x: number;
  y: number;
  z: number;
  visibility?: number;
}

export interface PoseLandmark {
  x: number;
  y: number;
  z: number;
  visibility: number;
}

export interface FaceLandmark {
  x: number;
  y: number;
  z: number;
  visibility?: number;
}

export interface FacialExpression {
  type: 'neutral' | 'happy' | 'sad' | 'angry' | 'surprised' | 'questioning' | 'affirmative' | 'negative';
  confidence: number;
  eyebrowRaise: number;
  mouthOpen: number;
  lipCornerRaise: number;
}

export interface MouthShape {
  type: 'closed' | 'open' | 'rounded' | 'spread' | 'pursed';
  width: number;
  height: number;
  aspectRatio: number;
}

export interface NonManualFeatures {
  facialExpression: FacialExpression;
  mouthShape: MouthShape;
  headTilt: number;
  eyeGaze: { x: number; y: number };
  bodyPosture: string;
}

export interface FrameData {
  timestamp: number;
  leftHand: HandLandmark[] | null;
  rightHand: HandLandmark[] | null;
  pose: PoseLandmark[];
  face: FaceLandmark[] | null;
  nonManualFeatures: NonManualFeatures | null;
  features: number[];
}

export interface RecognizedWord {
  word: string;
  pinyin: string;
  confidence: number;
  startTime: number;
  endTime: number;
  frameIndex: number;
  isCorrect?: boolean;
  category?: string;
}

export type GrammarErrorType = 'word_order' | 'missing_topic' | 'missing_time' | 'structure_error' | 'missing_action' | 'missing_object';

export interface GrammarError {
  type: GrammarErrorType;
  position: number;
  word: string;
  description: string;
  suggestion: string;
}

export interface GrammarCheckResult {
  isCorrect: boolean;
  errors: GrammarError[];
  correctedSequence: RecognizedWord[];
  translation: string;
  ruleApplied: string[];
}

export interface ErrorRecord {
  id: string;
  timestamp: number;
  originalSequence: string[];
  correctedSequence: string[];
  errors: GrammarError[];
  translation: string;
  videoUrl?: string;
}

export interface ErrorStatistics {
  totalCount: number;
  byType: Record<string, number>;
  byWord: Record<string, number>;
  trend: { date: string; count: number }[];
}

export interface VocabularyItem {
  id: string;
  word: string;
  pinyin: string;
  category: 'noun' | 'verb' | 'time' | 'adjective' | 'pronoun' | 'question' | 'preposition' | 'phrase' | 'adverb' | 'conjunction';
  featureTemplate: number[];
}

export interface GrammarRule {
  id: string;
  name: string;
  description: string;
  pattern: RegExp;
  correction: string;
}

export interface RecordedSession {
  id: string;
  timestamp: number;
  duration: number;
  frames: FrameData[];
  recognizedWords: RecognizedWord[];
  grammarResult: GrammarCheckResult | null;
  videoBlob?: Blob;
}

export type Handedness = 'Left' | 'Right';

export interface MediaPipeResults {
  multiHandLandmarks: HandLandmark[][];
  multiHandedness: { classification: { label: Handedness }[] }[];
  poseLandmarks: PoseLandmark[];
  faceLandmarks: FaceLandmark[];
}

export interface ContextState {
  recentWords: RecognizedWord[];
  recentCategories: string[];
  sentenceType: 'declarative' | 'question' | 'negative' | 'imperative' | 'unknown';
  topicWord?: RecognizedWord;
  timeWord?: RecognizedWord;
  predictedNextCategories: { category: string; probability: number }[];
  contextWindowSize: number;
}

export interface DialectMapping {
  id: string;
  dialectName: string;
  region: string;
  standardWord: string;
  dialectWord: string;
  pinyin: string;
  featureTemplate: number[];
  category: string;
  description?: string;
}

export interface DialectConfig {
  activeDialect: string;
  availableDialects: string[];
  customMappings: DialectMapping[];
  autoDetect: boolean;
  confidenceThreshold: number;
}

export type DialectRegion = 'beijing' | 'shanghai' | 'guangzhou' | 'hongkong' | 'taiwan' | 'chengdu' | 'wuhan' | 'xian' | 'northeast' | 'standard';

export interface ContextualConstraint {
  type: 'category_sequence' | 'sentence_type' | 'topic_comment' | 'time_action_object' | 'custom';
  weight: number;
  allowedNextCategories: string[];
  forbiddenNextCategories: string[];
  description: string;
}

export interface RecognitionResultWithContext {
  word: RecognizedWord;
  contextScore: number;
  dialectScore: number;
  nonManualScore: number;
  finalScore: number;
  isDialectVariant: boolean;
  dialectMapping?: DialectMapping;
  contextViolations: string[];
}
