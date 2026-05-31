import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { CalculationParams, Material, EmitterLayer } from '@/types';
import { BUILTIN_MATERIALS, DEFAULT_EMITTER_STRUCTURE } from '@/data/materials';

interface AppState {
  params: CalculationParams;
  customMaterials: Material[];
  activeTab: 'spectrum' | 'iv' | 'qe' | 'contour' | 'concentration' | 'wasteheat' | 'lifetime';
  showMaterialModal: boolean;
  showEmitterModal: boolean;
  
  setParams: (params: Partial<CalculationParams>) => void;
  setSourceTemperature: (temp: number) => void;
  setMaterialId: (id: string) => void;
  addCustomMaterial: (material: Omit<Material, 'id' | 'createdAt' | 'isCustom'>) => void;
  updateCustomMaterial: (id: string, material: Partial<Material>) => void;
  deleteCustomMaterial: (id: string) => void;
  setEmitterStructure: (structure: EmitterLayer[]) => void;
  setActiveTab: (tab: 'spectrum' | 'iv' | 'qe' | 'contour' | 'concentration' | 'wasteheat' | 'lifetime') => void;
  setShowMaterialModal: (show: boolean) => void;
  setShowEmitterModal: (show: boolean) => void;
  resetParams: () => void;
}

const defaultParams: CalculationParams = {
  sourceTemperature: 1200,
  materialId: 'ingaas',
  seriesResistance: 0.1,
  shuntResistance: 1000,
  temperature: 300,
  includeAuger: true,
  includeRadiative: true,
  includeSeriesResistance: true,
  emitterStructure: [...DEFAULT_EMITTER_STRUCTURE],
  optimizeEmitter: true,
  emitterSheetResistance: 10,
  fingerSpacing: 200,
  fingerWidth: 20,
  useDistributedResistance: false,
  concentrationRatio: 10,
  includeConcentration: false,
  includeWasteHeatRecovery: false,
  tegFigureOfMerit: 1.5,
  tegColdSideTemperature: 300,
  tegEfficiency: 8,
  includeLifetimePrediction: false,
  referenceLifetime: 100000,
  activationEnergy: 1.2,
};

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      params: defaultParams,
      customMaterials: [],
      activeTab: 'spectrum',
      showMaterialModal: false,
      showEmitterModal: false,

      setParams: (newParams) =>
        set((state) => ({
          params: { ...state.params, ...newParams },
        })),

      setSourceTemperature: (temp) =>
        set((state) => ({
          params: { ...state.params, sourceTemperature: Math.max(600, Math.min(2000, temp)) },
        })),

      setMaterialId: (id) =>
        set((state) => ({
          params: { ...state.params, materialId: id },
        })),

      addCustomMaterial: (material) =>
        set((state) => ({
          customMaterials: [
            ...state.customMaterials,
            {
              ...material,
              id: `custom-${Date.now()}`,
              createdAt: Date.now(),
              isCustom: true,
            },
          ],
        })),

      updateCustomMaterial: (id, material) =>
        set((state) => ({
          customMaterials: state.customMaterials.map((m) =>
            m.id === id ? { ...m, ...material } : m
          ),
        })),

      deleteCustomMaterial: (id) =>
        set((state) => ({
          customMaterials: state.customMaterials.filter((m) => m.id !== id),
          params: state.params.materialId === id
            ? { ...state.params, materialId: 'si' }
            : state.params,
        })),

      setEmitterStructure: (structure) =>
        set((state) => ({
          params: { ...state.params, emitterStructure: structure },
        })),

      setActiveTab: (tab) =>
        set({ activeTab: tab }),

      setShowMaterialModal: (show) =>
        set({ showMaterialModal: show }),

      setShowEmitterModal: (show) =>
        set({ showEmitterModal: show }),

      resetParams: () =>
        set({ params: defaultParams }),
    }),
    {
      name: 'tpv-simulator-storage',
      partialize: (state) => ({
        params: state.params,
        customMaterials: state.customMaterials,
      }),
    }
  )
);

export const useAllMaterials = () => {
  const customMaterials = useAppStore((state) => state.customMaterials);
  return [...BUILTIN_MATERIALS, ...customMaterials];
};
