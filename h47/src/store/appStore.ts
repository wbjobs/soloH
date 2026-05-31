import { create } from 'zustand';
import { FrameData, RecognizedWord, GrammarCheckResult, ErrorRecord, RecordedSession, ContextState, DialectConfig, NonManualFeatures, RecognitionResultWithContext, DialectMapping } from '@/types';
import { checkChineseSignLanguageGrammar } from '@/data/grammarRules';
import { storageService } from '@/services/storageService';
import { gestureRecognizer } from '@/services/gestureRecognizer';
import { contextAwareService } from '@/services/contextAwareService';
import { dialectService } from '@/services/dialectService';
import { facialExpressionService } from '@/services/facialExpressionService';

interface AppState {
  isRecording: boolean;
  isPaused: boolean;
  isCameraActive: boolean;
  isModelLoaded: boolean;
  currentFrames: FrameData[];
  recognizedWords: RecognizedWord[];
  grammarResult: GrammarCheckResult | null;
  currentSession: RecordedSession | null;
  sessionStartTime: number | null;
  playbackSpeed: number;
  showOverlay: boolean;
  minConfidence: number;
  error: string | null;
  latestFrame: FrameData | null;
  processingStatus: string;
  contextState: ContextState;
  dialectConfig: DialectConfig;
  latestNonManualFeatures: NonManualFeatures | null;
  enableFaceDetection: boolean;
  enableContextAwareness: boolean;
  recognitionHistory: RecognitionResultWithContext[];
}

interface AppActions {
  setRecording: (recording: boolean) => void;
  setPaused: (paused: boolean) => void;
  setCameraActive: (active: boolean) => void;
  setModelLoaded: (loaded: boolean) => void;
  addFrame: (frame: FrameData) => void;
  addRecognizedWord: (word: RecognizedWord) => void;
  clearRecognizedWords: () => void;
  checkGrammar: () => void;
  setPlaybackSpeed: (speed: number) => void;
  setShowOverlay: (show: boolean) => void;
  setMinConfidence: (confidence: number) => void;
  setError: (error: string | null) => void;
  setProcessingStatus: (status: string) => void;
  startSession: () => void;
  endSession: () => Promise<void>;
  saveCurrentError: () => Promise<void>;
  resetState: () => void;
  processFrameForRecognition: (frame: FrameData) => void;
  flushRecognition: () => void;
  setEnableFaceDetection: (enabled: boolean) => void;
  setEnableContextAwareness: (enabled: boolean) => void;
  setActiveDialect: (dialect: string) => void;
  addCustomDialectMapping: (mapping: Omit<DialectMapping, 'id'>) => void;
  resetContext: () => void;
}

const initialState: AppState = {
  isRecording: false,
  isPaused: false,
  isCameraActive: false,
  isModelLoaded: false,
  currentFrames: [],
  recognizedWords: [],
  grammarResult: null,
  currentSession: null,
  sessionStartTime: null,
  playbackSpeed: 1,
  showOverlay: true,
  minConfidence: 0.6,
  error: null,
  latestFrame: null,
  processingStatus: '',
  contextState: {
    recentWords: [],
    recentCategories: [],
    sentenceType: 'unknown',
    predictedNextCategories: [],
    contextWindowSize: 5
  },
  dialectConfig: {
    activeDialect: 'standard',
    availableDialects: ['standard', 'beijing', 'shanghai', 'guangzhou', 'hongkong', 'taiwan', 'chengdu', 'northeast'],
    customMappings: [],
    autoDetect: false,
    confidenceThreshold: 0.6
  },
  latestNonManualFeatures: null,
  enableFaceDetection: true,
  enableContextAwareness: true,
  recognitionHistory: []
};

export const useAppStore = create<AppState & AppActions>((set, get) => ({
  ...initialState,

  setRecording: (recording) => set({ isRecording: recording }),
  setPaused: (paused) => set({ isPaused: paused }),
  setCameraActive: (active) => set({ isCameraActive: active }),
  setModelLoaded: (loaded) => set({ isModelLoaded: loaded }),

  addFrame: (frame) => set((state) => ({
    currentFrames: [...state.currentFrames.slice(-300), frame],
    latestFrame: frame,
    latestNonManualFeatures: frame.nonManualFeatures || state.latestNonManualFeatures
  })),

  addRecognizedWord: (word) => set((state) => {
    const EMPHASIS_TIME_WINDOW = 2000;
    const MAX_REPEATS_FOR_EMPHASIS = 3;

    const recentSameWords = state.recognizedWords.filter(
      w => w.word === word.word && (word.startTime - w.endTime) < EMPHASIS_TIME_WINDOW
    );

    const lastWord = state.recognizedWords[state.recognizedWords.length - 1];
    if (lastWord && lastWord.word === word.word &&
        word.startTime - lastWord.endTime < 300 &&
        recentSameWords.length >= MAX_REPEATS_FOR_EMPHASIS) {
      return state;
    }

    let processedWord = { ...word };
    let isDialectVariant = false;
    let contextScore = 1.0;
    let dialectScore = 1.0;
    let nonManualScore = 1.0;
    let contextViolations: string[] = [];

    if (state.dialectConfig.activeDialect !== 'standard') {
      const dialectResult = dialectService.translateDialectToStandard(word, state.dialectConfig.activeDialect);
      if (dialectResult.isDialect) {
        processedWord = dialectResult.word;
        isDialectVariant = true;
        dialectScore = dialectResult.mapping ? 
          dialectService.calculateDialectScore(word, word.frameIndex >= 0 ? state.currentFrames[word.frameIndex]?.features || [] : []).score : 0.8;
      }
    }

    let finalContextState = state.contextState;
    if (state.enableContextAwareness) {
      const contextResult = contextAwareService.calculateContextScore(processedWord);
      contextScore = contextResult.score;
      contextViolations = contextResult.violations;

      finalContextState = contextAwareService.updateContext(processedWord);

      const finalConfidence = processedWord.confidence * 0.5 + contextScore * 0.3 + dialectScore * 0.2;
      processedWord.confidence = Math.max(0.1, Math.min(1.0, finalConfidence));
    }

    const nonManualFeatures = state.latestNonManualFeatures;
    if (nonManualFeatures && facialExpressionService) {
      const expectedType = finalContextState.sentenceType === 'question' ? 'question' :
                          finalContextState.sentenceType === 'negative' ? 'negative' :
                          finalContextState.sentenceType === 'declarative' ? 'affirmative' : 'neutral';
      const nmResult = facialExpressionService.calculateNonManualScore(nonManualFeatures, expectedType);
      nonManualScore = nmResult.score;
      
      if (nmResult.mismatchingFeatures.length > 0 && processedWord.confidence < 0.7) {
        processedWord.confidence = Math.max(0.1, processedWord.confidence * 0.9);
      }
    }

    const historyEntry: RecognitionResultWithContext = {
      word: processedWord,
      contextScore,
      dialectScore,
      nonManualScore,
      finalScore: processedWord.confidence,
      isDialectVariant,
      contextViolations
    };

    const newWords = [...state.recognizedWords, processedWord];
    const grammarResult = checkChineseSignLanguageGrammar(newWords);

    return {
      recognizedWords: newWords,
      grammarResult,
      contextState: finalContextState,
      recognitionHistory: [...state.recognitionHistory.slice(-50), historyEntry]
    };
  }),

  clearRecognizedWords: () => {
    contextAwareService.resetContext();
    facialExpressionService.reset();
    set({ 
      recognizedWords: [], 
      grammarResult: null,
      contextState: contextAwareService.getContextState(),
      latestNonManualFeatures: null,
      recognitionHistory: []
    });
  },

  checkGrammar: () => set((state) => {
    if (state.recognizedWords.length === 0) {
      return { grammarResult: null };
    }
    const result = checkChineseSignLanguageGrammar(state.recognizedWords);
    return { grammarResult: result };
  }),

  setPlaybackSpeed: (speed) => set({ playbackSpeed: speed }),
  setShowOverlay: (show) => set({ showOverlay: show }),
  setMinConfidence: (confidence) => set({ minConfidence: confidence }),
  setError: (error) => set({ error }),
  setProcessingStatus: (status) => set({ processingStatus: status }),

  startSession: () => {
    const sessionId = `session_${Date.now()}`;
    contextAwareService.resetContext();
    facialExpressionService.reset();
    set({
      sessionStartTime: Date.now(),
      currentSession: {
        id: sessionId,
        timestamp: Date.now(),
        duration: 0,
        frames: [],
        recognizedWords: [],
        grammarResult: null
      },
      isRecording: true,
      recognizedWords: [],
      grammarResult: null,
      currentFrames: [],
      contextState: contextAwareService.getContextState(),
      latestNonManualFeatures: null,
      recognitionHistory: []
    });
    gestureRecognizer.reset();
  },

  endSession: async () => {
    const state = get();
    if (!state.currentSession || state.sessionStartTime === null) return;

    const remainingWords = gestureRecognizer.flush();
    let allWords = [...state.recognizedWords];
    
    if (remainingWords.length > 0) {
      allWords = [...allWords, ...remainingWords];
    }

    const finalGrammarResult = allWords.length > 0 
      ? checkChineseSignLanguageGrammar(allWords) 
      : null;

    const session: RecordedSession = {
      ...state.currentSession,
      duration: Date.now() - state.sessionStartTime,
      frames: state.currentFrames,
      recognizedWords: allWords,
      grammarResult: finalGrammarResult
    };

    try {
      await storageService.saveSession(session);
    } catch (e) {
      console.error('Failed to save session:', e);
    }

    if (finalGrammarResult && !finalGrammarResult.isCorrect) {
      const errorRecord: ErrorRecord = {
        id: `error_${Date.now()}`,
        timestamp: Date.now(),
        originalSequence: allWords.map(w => w.word),
        correctedSequence: finalGrammarResult.correctedSequence.map(w => w.word),
        errors: finalGrammarResult.errors,
        translation: finalGrammarResult.translation
      };
      try {
        await storageService.saveErrorRecord(errorRecord);
      } catch (e) {
        console.error('Failed to save error record:', e);
      }
    }

    set({
      isRecording: false,
      currentSession: session,
      recognizedWords: allWords,
      grammarResult: finalGrammarResult,
      sessionStartTime: null
    });
  },

  saveCurrentError: async () => {
    const state = get();
    if (!state.grammarResult || state.grammarResult.isCorrect) return;

    const errorRecord: ErrorRecord = {
      id: `error_${Date.now()}`,
      timestamp: Date.now(),
      originalSequence: state.recognizedWords.map(w => w.word),
      correctedSequence: state.grammarResult.correctedSequence.map(w => w.word),
      errors: state.grammarResult.errors,
      translation: state.grammarResult.translation
    };

    try {
      await storageService.saveErrorRecord(errorRecord);
    } catch (e) {
      console.error('Failed to save error record:', e);
    }
  },

  resetState: () => {
    gestureRecognizer.reset();
    set(initialState);
  },

  processFrameForRecognition: (frame) => {
    const state = get();
    if (!state.isRecording || state.isPaused) return;

    const recognizedWord = gestureRecognizer.addFrame(frame);
    if (recognizedWord && recognizedWord.confidence >= state.minConfidence) {
      get().addRecognizedWord(recognizedWord);
    }

    if (state.currentSession) {
      set((s) => ({
        currentSession: {
          ...s.currentSession!,
          frames: [...s.currentSession!.frames.slice(-300), frame],
          recognizedWords: s.recognizedWords
        }
      }));
    }
  },

  flushRecognition: () => {
    const remainingWords = gestureRecognizer.flush();
    remainingWords.forEach(word => {
      if (word.confidence >= get().minConfidence) {
        get().addRecognizedWord(word);
      }
    });
  },

  setEnableFaceDetection: (enabled) => set({ enableFaceDetection: enabled }),

  setEnableContextAwareness: (enabled) => set({ enableContextAwareness: enabled }),

  setActiveDialect: (dialect) => set((state) => {
    dialectService.setActiveDialect(dialect);
    return {
      dialectConfig: {
        ...state.dialectConfig,
        activeDialect: dialect
      }
    };
  }),

  addCustomDialectMapping: (mapping) => {
    dialectService.addCustomMapping(mapping);
    set((state) => ({
      dialectConfig: {
        ...state.dialectConfig,
        customMappings: dialectService.getConfig().customMappings
      }
    }));
  },

  resetContext: () => {
    contextAwareService.resetContext();
    facialExpressionService.reset();
    set((state) => ({
      contextState: contextAwareService.getContextState(),
      latestNonManualFeatures: null
    }));
  }
}));
