import { create } from 'zustand';
import type {
  AppState,
  SourceConfig,
  SubstrateConfig,
  CalculationConfig,
  OptimizationConfig,
  CalculationResult,
  OptimizationResult,
  OptimizationIteration,
  Vector3,
  Euler,
  OccluderConfig,
  SubstrateMotion,
} from '../types';
import { createDefaultSource } from '../engine/sources';
import { createDefaultSubstrate, createDefaultMotion } from '../engine/substrates';
import { createDefaultOccluder } from '../engine/occlusion';
import { degToRad } from '../engine/math/vector';

const initialSources: SourceConfig[] = [
  createDefaultSource('source-1', 0),
  createDefaultSource('source-2', 1),
];

const initialSubstrate: SubstrateConfig = createDefaultSubstrate();

const initialOccluders: OccluderConfig[] = [];

const initialCalculationConfig: CalculationConfig = {
  method: 'cosine',
  monteCarloParticles: 100000,
  integrationPoints: 100,
  occluders: initialOccluders,
};

const initialOptimizationConfig: OptimizationConfig = {
  enabled: false,
  method: 'genetic',
  sourceIds: ['source-1', 'source-2'],
  bounds: {
    min: { x: -300, y: -300, z: -400 },
    max: { x: 300, y: 300, z: -100 },
  },
  targetUniformity: 95,
  maxIterations: 50,
  populationSize: 20,
  geneticConfig: {
    adaptiveMutation: true,
    mutationRateMin: 0.05,
    mutationRateMax: 0.4,
    diversityThreshold: 50,
    catastropheEnabled: true,
    catastropheThreshold: 15,
    catastropheCount: 5,
    crowdingEnabled: true,
    crowdingFactor: 0.8,
  },
};

export const useAppStore = create<AppState & {
  setSourcePosition: (id: string, position: Partial<Vector3>) => void;
  setSourceOrientation: (id: string, orientation: Partial<Euler>) => void;
  setSourceType: (id: string, type: SourceConfig['type']) => void;
  setSourcePower: (id: string, power: number) => void;
  setSourceEmissionCoefficient: (id: string, coefficient: number) => void;
  addSource: () => void;
  removeSource: (id: string) => void;
  setSubstrate: (substrate: Partial<SubstrateConfig>) => void;
  setSubstrateMotion: (motion: Partial<SubstrateMotion>) => void;
  setSubstrateSize: (size: Partial<SubstrateConfig['size']>) => void;
  setSubstrateResolution: (resolution: Partial<SubstrateConfig['resolution']>) => void;
  setCalculationConfig: (config: Partial<CalculationConfig>) => void;
  setOptimizationConfig: (config: Partial<OptimizationConfig>) => void;
  addOccluder: () => void;
  removeOccluder: (id: string) => void;
  setOccluderPosition: (id: string, position: Partial<Vector3>) => void;
  setOccluderOrientation: (id: string, orientation: Partial<Euler>) => void;
  setOccluderShape: (id: string, shape: OccluderConfig['shape']) => void;
  setOccluderSize: (id: string, size: Partial<OccluderConfig['size']>) => void;
  setCalculationResult: (result: CalculationResult | null) => void;
  setOptimizationResult: (result: OptimizationResult | null) => void;
  addOptimizationIteration: (iteration: OptimizationIteration) => void;
  setIsCalculating: (isCalculating: boolean) => void;
  setIsOptimizing: (isOptimizing: boolean) => void;
  setProgress: (progress: number, message: string) => void;
  setError: (error: string | null) => void;
  resetResults: () => void;
  applyOptimizedPositions: (positions: { sourceId: string; position: Vector3 }[]) => void;
}>((set) => ({
  sources: initialSources,
  substrate: initialSubstrate,
  calculationConfig: initialCalculationConfig,
  optimizationConfig: initialOptimizationConfig,
  occluders: initialOccluders,
  calculationResult: null,
  optimizationResult: null,
  optimizationHistory: [],
  isCalculating: false,
  isOptimizing: false,
  progress: 0,
  progressMessage: '',
  error: null,

  setSourcePosition: (id, position) =>
    set((state) => ({
      sources: state.sources.map((s) =>
        s.id === id ? { ...s, position: { ...s.position, ...position } } : s
      ),
    })),

  setSourceOrientation: (id, orientation) =>
    set((state) => ({
      sources: state.sources.map((s) =>
        s.id === id ? { ...s, orientation: { ...s.orientation, ...orientation } } : s
      ),
    })),

  setSourceType: (id, type) =>
    set((state) => ({
      sources: state.sources.map((s) => (s.id === id ? { ...s, type } : s)),
    })),

  setSourcePower: (id, power) =>
    set((state) => ({
      sources: state.sources.map((s) => (s.id === id ? { ...s, power } : s)),
    })),

  setSourceEmissionCoefficient: (id, emissionCoefficient) =>
    set((state) => ({
      sources: state.sources.map((s) => (s.id === id ? { ...s, emissionCoefficient } : s)),
    })),

  addSource: () =>
    set((state) => {
      const newId = `source-${Date.now()}`;
      const index = state.sources.length;
      const newSource = createDefaultSource(newId, index);
      return {
        sources: [...state.sources, newSource],
        optimizationConfig: {
          ...state.optimizationConfig,
          sourceIds: [...state.optimizationConfig.sourceIds, newId],
        },
      };
    }),

  removeSource: (id) =>
    set((state) => ({
      sources: state.sources.filter((s) => s.id !== id),
      optimizationConfig: {
        ...state.optimizationConfig,
        sourceIds: state.optimizationConfig.sourceIds.filter((sid) => sid !== id),
      },
    })),

  setSubstrate: (substrate) =>
    set((state) => ({
      substrate: { ...state.substrate, ...substrate },
    })),

  setSubstrateSize: (size) =>
    set((state) => ({
      substrate: {
        ...state.substrate,
        size: { ...state.substrate.size, ...size },
      },
    })),

  setSubstrateResolution: (resolution) =>
    set((state) => ({
      substrate: {
        ...state.substrate,
        resolution: { ...state.substrate.resolution, ...resolution },
      },
    })),

  setCalculationConfig: (config) =>
    set((state) => ({
      calculationConfig: { ...state.calculationConfig, ...config },
    })),

  setOptimizationConfig: (config) =>
    set((state) => ({
      optimizationConfig: { ...state.optimizationConfig, ...config },
    })),

  setCalculationResult: (result) =>
    set({ calculationResult: result }),

  setOptimizationResult: (result) =>
    set({ optimizationResult: result }),

  addOptimizationIteration: (iteration) =>
    set((state) => ({
      optimizationHistory: [...state.optimizationHistory, iteration],
    })),

  setIsCalculating: (isCalculating) =>
    set({ isCalculating }),

  setIsOptimizing: (isOptimizing) =>
    set({ isOptimizing }),

  setSubstrateMotion: (motion) =>
    set((state) => ({
      substrate: { ...state.substrate, motion: { ...state.substrate.motion, ...motion } },
    })),

  addOccluder: () =>
    set((state) => ({
      occluders: [...state.occluders, createDefaultOccluder(state.occluders.length)],
    })),

  removeOccluder: (id) =>
    set((state) => ({
      occluders: state.occluders.filter((o) => o.id !== id),
    })),

  setOccluderPosition: (id, position) =>
    set((state) => ({
      occluders: state.occluders.map((o) =>
        o.id === id ? { ...o, position: { ...o.position, ...position } } : o
      ),
    })),

  setOccluderOrientation: (id, orientation) =>
    set((state) => ({
      occluders: state.occluders.map((o) =>
        o.id === id ? { ...o, orientation: { ...o.orientation, ...orientation } } : o
      ),
    })),

  setOccluderShape: (id, shape) =>
    set((state) => ({
      occluders: state.occluders.map((o) => (o.id === id ? { ...o, shape } : o)),
    })),

  setOccluderSize: (id, size) =>
    set((state) => ({
      occluders: state.occluders.map((o) =>
        o.id === id ? { ...o, size: { ...o.size, ...size } } : o
      ),
    })),

  setProgress: (progress, message) =>
    set({ progress, progressMessage: message }),

  setError: (error) =>
    set({ error }),

  resetResults: () =>
    set({
      calculationResult: null,
      optimizationResult: null,
      optimizationHistory: [],
      progress: 0,
      progressMessage: '',
      error: null,
    }),

  applyOptimizedPositions: (positions) =>
    set((state) => ({
      sources: state.sources.map((s) => {
        const optimized = positions.find((p) => p.sourceId === s.id);
        if (optimized) {
          return { ...s, position: optimized.position };
        }
        return s;
      }),
    })),
}));
