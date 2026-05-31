import { create } from 'zustand';
import type { 
  InputParams, 
  CalculationResults, 
  CalculationProgress,
  TabType 
} from '../types';
import { defaultInputParams } from '../data/materials';
import { runFullSimulation, validateParams } from '../engine/scheduler';

interface AppState {
  activeTab: TabType;
  inputParams: InputParams;
  results: CalculationResults | null;
  progress: CalculationProgress;
  selectedVoltage: number;
  visualizationMode: 'band' | 'carrier';

  setActiveTab: (tab: TabType) => void;
  setInputParams: (params: Partial<InputParams>) => void;
  setSelectedVoltage: (voltage: number) => void;
  setVisualizationMode: (mode: 'band' | 'carrier') => void;
  resetParams: () => void;
  runSimulation: () => Promise<void>;
  clearResults: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  activeTab: 'params',
  inputParams: { ...defaultInputParams },
  results: null,
  progress: {
    status: 'idle',
    progress: 0,
    message: '等待开始计算',
  },
  selectedVoltage: 0,
  visualizationMode: 'band',

  setActiveTab: (tab) => set({ activeTab: tab }),

  setInputParams: (params) => set((state) => ({
    inputParams: {
      ...state.inputParams,
      ...params,
      deviceStructure: {
        ...state.inputParams.deviceStructure,
        ...params.deviceStructure,
      },
      calculationParams: {
        ...state.inputParams.calculationParams,
        ...params.calculationParams,
      },
      mqwParams: {
        ...state.inputParams.mqwParams,
        ...params.mqwParams,
      },
      agingParams: {
        ...state.inputParams.agingParams,
        ...params.agingParams,
      },
      angularParams: {
        ...state.inputParams.angularParams,
        ...params.angularParams,
      },
    },
  })),

  setSelectedVoltage: (voltage) => set({ selectedVoltage: voltage }),

  setVisualizationMode: (mode) => set({ visualizationMode: mode }),

  resetParams: () => set({ inputParams: { ...defaultInputParams } }),

  runSimulation: async () => {
    const { inputParams } = get();

    const errors = validateParams(inputParams);
    if (errors.length > 0) {
      set({
        progress: {
          status: 'error',
          progress: 0,
          message: '参数验证失败',
          error: errors.join('; '),
        },
      });
      return;
    }

    set({
      progress: {
        status: 'calculating',
        progress: 0,
        message: '开始计算...',
      },
      activeTab: 'results',
    });

    try {
      const results = await runFullSimulation(inputParams, async (progress) => {
        set({ progress });
      });

      set({
        results,
        selectedVoltage: inputParams.calculationParams.voltageStart + 
          (inputParams.calculationParams.voltageEnd - inputParams.calculationParams.voltageStart) / 2,
      });
    } catch (error) {
      console.error('Simulation error:', error);
    }
  },

  clearResults: () => set({
    results: null,
    progress: {
      status: 'idle',
      progress: 0,
      message: '等待开始计算',
    },
  }),
}));
