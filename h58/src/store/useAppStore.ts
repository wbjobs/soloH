import { create } from 'zustand';
import { 
  CharacterStyle, 
  GeneratedCharacter, 
  RenderParameters, 
  AppState,
  LayoutParameters,
  SealConfig,
  SignatureConfig,
  RubbingEffect
} from '../types';

interface AppStore extends AppState {
  setSamples: (samples: CharacterStyle[]) => void;
  addSample: (sample: CharacterStyle) => void;
  removeSample: (id: string) => void;
  updateSampleWeight: (id: string, weight: number) => void;
  setTargetText: (text: string) => void;
  setParameters: (params: Partial<RenderParameters>) => void;
  setLayout: (params: Partial<LayoutParameters>) => void;
  setSeal: (params: Partial<SealConfig>) => void;
  setSignature: (params: Partial<SignatureConfig>) => void;
  setRubbing: (params: Partial<RubbingEffect>) => void;
  setGeneratedCharacters: (characters: GeneratedCharacter[]) => void;
  setIsPlaying: (isPlaying: boolean) => void;
  setCurrentStrokeIndex: (index: number) => void;
  setCurrentCharacterIndex: (index: number) => void;
  setSelectedSampleId: (id: string | null) => void;
  resetAnimation: () => void;
  clearAll: () => void;
}

export const useAppStore = create<AppStore>((set) => ({
  samples: [],
  targetText: '永字八法',
  parameters: {
    thickness: 50,
    speed: 50,
    flyingWhite: 30
  },
  layout: {
    charSpacing: 20,
    lineSpacing: 30,
    scatterAmount: 0,
    direction: 'horizontal',
    alignment: 'left',
    charsPerLine: 10
  },
  seal: {
    enabled: false,
    text: '墨韵',
    size: 40,
    positionX: 90,
    positionY: 90,
    style: 'square',
    color: '#c41e3a',
    rotation: 5,
    opacity: 0.9
  },
  signature: {
    enabled: false,
    text: '手书',
    fontSize: 16,
    positionX: 80,
    positionY: 75,
    color: '#1a1a1a',
    rotation: 0,
    style: 'running'
  },
  rubbing: {
    enabled: false,
    invert: true,
    mottleIntensity: 40,
    edgeRoughness: 30,
    paperTexture: true,
    contrast: 70
  },
  generatedCharacters: [],
  isPlaying: false,
  currentStrokeIndex: 0,
  currentCharacterIndex: 0,
  selectedSampleId: null,

  setSamples: (samples) => set({ samples }),
  addSample: (sample) => set((state) => ({
    samples: [...state.samples, sample],
    selectedSampleId: sample.id
  })),
  removeSample: (id) => set((state) => ({
    samples: state.samples.filter(s => s.id !== id),
    selectedSampleId: state.selectedSampleId === id ? null : state.selectedSampleId
  })),
  updateSampleWeight: (id, weight) => set((state) => ({
    samples: state.samples.map(s =>
      s.id === id ? { ...s, weight } : s
    )
  })),
  setTargetText: (text) => set({ targetText: text }),
  setParameters: (params) => set((state) => ({
    parameters: { ...state.parameters, ...params }
  })),
  setLayout: (params) => set((state) => ({
    layout: { ...state.layout, ...params }
  })),
  setSeal: (params) => set((state) => ({
    seal: { ...state.seal, ...params }
  })),
  setSignature: (params) => set((state) => ({
    signature: { ...state.signature, ...params }
  })),
  setRubbing: (params) => set((state) => ({
    rubbing: { ...state.rubbing, ...params }
  })),
  setGeneratedCharacters: (characters) => set({ generatedCharacters: characters }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setCurrentStrokeIndex: (index) => set({ currentStrokeIndex: index }),
  setCurrentCharacterIndex: (index) => set({ currentCharacterIndex: index }),
  setSelectedSampleId: (id) => set({ selectedSampleId: id }),
  resetAnimation: () => set({
    isPlaying: false,
    currentStrokeIndex: 0,
    currentCharacterIndex: 0
  }),
  clearAll: () => set({
    samples: [],
    targetText: '',
    generatedCharacters: [],
    isPlaying: false,
    currentStrokeIndex: 0,
    currentCharacterIndex: 0,
    selectedSampleId: null
  })
}));
