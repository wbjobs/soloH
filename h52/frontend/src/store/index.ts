import { create } from 'zustand';
import type {
  EmotionResult,
  StreamResult,
  RecordingStatus,
  EmotionCategory,
} from '@/types';

interface AppState {
  darkMode: boolean;
  toggleDarkMode: () => void;

  recording: {
    status: RecordingStatus;
    duration: number;
    videoUrl: string | null;
    videoId: string | null;
    error: string | null;
  };
  setRecordingStatus: (status: RecordingStatus) => void;
  setRecordingDuration: (duration: number) => void;
  setVideoUrl: (url: string | null) => void;
  setVideoId: (id: string | null) => void;
  setRecordingError: (error: string | null) => void;
  resetRecording: () => void;

  analysis: {
    taskId: string | null;
    status: 'idle' | 'queued' | 'processing' | 'completed' | 'failed';
    progress: number;
    result: EmotionResult | null;
    error: string | null;
  };
  setAnalysisTaskId: (id: string | null) => void;
  setAnalysisStatus: (status: 'idle' | 'queued' | 'processing' | 'completed' | 'failed') => void;
  setAnalysisProgress: (progress: number) => void;
  setAnalysisResult: (result: EmotionResult | null) => void;
  setAnalysisError: (error: string | null) => void;
  resetAnalysis: () => void;

  stream: {
    isConnected: boolean;
    isStreaming: boolean;
    results: StreamResult[];
    currentEmotion: EmotionCategory | null;
    error: string | null;
  };
  setStreamConnected: (connected: boolean) => void;
  setStreamActive: (active: boolean) => void;
  addStreamResult: (result: StreamResult) => void;
  clearStreamResults: () => void;
  setStreamError: (error: string | null) => void;
  resetStream: () => void;
}

const initialRecordingState = {
  status: 'idle' as RecordingStatus,
  duration: 0,
  videoUrl: null,
  videoId: null,
  error: null,
};

const initialAnalysisState = {
  taskId: null,
  status: 'idle' as const,
  progress: 0,
  result: null,
  error: null,
};

const initialStreamState = {
  isConnected: false,
  isStreaming: false,
  results: [] as StreamResult[],
  currentEmotion: null as EmotionCategory | null,
  error: null,
};

export const useAppStore = create<AppState>((set) => ({
  darkMode: true,
  toggleDarkMode: () => set((state) => ({ darkMode: !state.darkMode })),

  recording: initialRecordingState,
  setRecordingStatus: (status) =>
    set((state) => ({ recording: { ...state.recording, status } })),
  setRecordingDuration: (duration) =>
    set((state) => ({ recording: { ...state.recording, duration } })),
  setVideoUrl: (videoUrl) =>
    set((state) => ({ recording: { ...state.recording, videoUrl } })),
  setVideoId: (videoId) =>
    set((state) => ({ recording: { ...state.recording, videoId } })),
  setRecordingError: (error) =>
    set((state) => ({ recording: { ...state.recording, error } })),
  resetRecording: () => set({ recording: initialRecordingState }),

  analysis: initialAnalysisState,
  setAnalysisTaskId: (taskId) =>
    set((state) => ({ analysis: { ...state.analysis, taskId } })),
  setAnalysisStatus: (status) =>
    set((state) => ({ analysis: { ...state.analysis, status } })),
  setAnalysisProgress: (progress) =>
    set((state) => ({ analysis: { ...state.analysis, progress } })),
  setAnalysisResult: (result) =>
    set((state) => ({ analysis: { ...state.analysis, result, status: result ? 'completed' : state.analysis.status } })),
  setAnalysisError: (error) =>
    set((state) => ({ analysis: { ...state.analysis, error, status: 'failed' } })),
  resetAnalysis: () => set({ analysis: initialAnalysisState }),

  stream: initialStreamState,
  setStreamConnected: (isConnected) =>
    set((state) => ({ stream: { ...state.stream, isConnected } })),
  setStreamActive: (isStreaming) =>
    set((state) => ({ stream: { ...state.stream, isStreaming } })),
  addStreamResult: (result) =>
    set((state) => ({
      stream: {
        ...state.stream,
        results: [...state.stream.results.slice(-299), result],
        currentEmotion: result.emotion,
      },
    })),
  clearStreamResults: () =>
    set((state) => ({ stream: { ...state.stream, results: [], currentEmotion: null } })),
  setStreamError: (error) =>
    set((state) => ({ stream: { ...state.stream, error } })),
  resetStream: () => set({ stream: initialStreamState }),
}));

export default useAppStore;
