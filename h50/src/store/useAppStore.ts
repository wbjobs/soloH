import { create } from 'zustand';
import type {
  Jianzi,
  DetectionResult,
  EditorState,
  UploadResponse,
} from '@/types/index';

interface AppState {
  imageId: string | null;
  imageUrl: string | null;
  imageWidth: number;
  imageHeight: number;
  detectionResult: DetectionResult | null;
  selectedJianziId: string | null;
  audioUrl: string | null;
  midiUrl: string | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  tempo: number;
  zoom: number;
  panX: number;
  panY: number;
  isEditing: boolean;
}

interface AppActions {
  setImage: (data: UploadResponse) => void;
  setDetectionResult: (result: DetectionResult) => void;
  selectJianzi: (id: string | null) => void;
  updateJianzi: (id: string, data: Partial<Jianzi>) => void;
  setAudioState: (state: Partial<{
    audioUrl: string | null;
    midiUrl: string | null;
    isPlaying: boolean;
    currentTime: number;
    duration: number;
    tempo: number;
  }>) => void;
  setEditorView: (state: Partial<EditorState>) => void;
  reset: () => void;
}

const initialState: AppState = {
  imageId: null,
  imageUrl: null,
  imageWidth: 0,
  imageHeight: 0,
  detectionResult: null,
  selectedJianziId: null,
  audioUrl: null,
  midiUrl: null,
  isPlaying: false,
  currentTime: 0,
  duration: 0,
  tempo: 120,
  zoom: 1,
  panX: 0,
  panY: 0,
  isEditing: false,
};

export const useAppStore = create<AppState & AppActions>((set) => ({
  ...initialState,

  setImage: (data) =>
    set({
      imageId: data.imageId,
      imageUrl: data.imageUrl,
      imageWidth: data.width,
      imageHeight: data.height,
    }),

  setDetectionResult: (result) =>
    set({
      detectionResult: result,
    }),

  selectJianzi: (id) =>
    set({
      selectedJianziId: id,
    }),

  updateJianzi: (id, data) =>
    set((state) => {
      if (!state.detectionResult) return state;
      return {
        detectionResult: {
          ...state.detectionResult,
          jianziList: state.detectionResult.jianziList.map((j) =>
            j.id === id ? { ...j, ...data } : j
          ),
        },
      };
    }),

  setAudioState: (state) =>
    set((prev) => ({
      ...prev,
      ...state,
    })),

  setEditorView: (state) =>
    set((prev) => ({
      ...prev,
      ...state,
    })),

  reset: () => set(initialState),
}));
