import { create } from 'zustand';
import {
  SimulationStatus,
  SimulationParameters,
  PIDParameters,
  PerturbationConfig,
  OptimizationStatus,
  SimulationTimeSeries,
  ExtendedSimulationStatus,
  NeuralSurrogateConfig,
  NeuralSurrogateStatus,
  MultichannelConfig,
  FaultDetectionStatus,
  SimulationConfig,
  SimulationMode,
} from '../types';
import * as api from '../services/api';
import { simulationWs } from '../services/websocket';

interface SimulationState {
  status: ExtendedSimulationStatus | null;
  optimizationStatus: OptimizationStatus | null;
  timeSeries: SimulationTimeSeries | null;
  wsConnected: boolean;
  isLoading: boolean;
  error: string | null;

  fetchStatus: () => Promise<void>;
  fetchTimeSeries: () => Promise<void>;
  controlSimulation: (action: 'start' | 'pause' | 'reset') => Promise<void>;
  updateParameters: (params: SimulationParameters) => Promise<void>;
  updatePID: (params: PIDParameters) => Promise<void>;
  updatePerturbation: (config: PerturbationConfig) => Promise<void>;
  updateSimulationConfig: (config: SimulationConfig) => Promise<void>;

  startOptimization: (config: any) => Promise<void>;
  stopOptimization: () => Promise<void>;

  trainNeuralSurrogate: (config: NeuralSurrogateConfig) => Promise<void>;
  fetchNeuralSurrogateStatus: () => Promise<void>;

  updateMultichannelConfig: (config: MultichannelConfig) => Promise<void>;
  setChannelBlocked: (channelId: number, blocked: boolean, severity?: number) => Promise<void>;
  setChannelEnabled: (channelId: number, enabled: boolean) => Promise<void>;
  fetchFaultDetectionStatus: () => Promise<void>;

  connectWebSocket: () => void;
  disconnectWebSocket: () => void;

  simulationMode: SimulationMode;
  setSimulationMode: (mode: SimulationMode) => void;
  multichannelConfig: MultichannelConfig;
  neuralSurrogateConfig: NeuralSurrogateConfig;
  neuralSurrogateStatus: NeuralSurrogateStatus | null;
  faultDetectionStatus: FaultDetectionStatus | null;
}

const initialParameters: SimulationParameters = {
  continuousPhase: {
    flowRate: 20.0,
    viscosity: 1.0,
    density: 1000.0
  },
  dispersedPhase: {
    flowRate: 5.0,
    viscosity: 5.0,
    density: 800.0
  },
  interfacialTension: 30.0,
  channel: {
    width: 100.0,
    height: 50.0,
    length: 1000.0,
    junctionType: 'T'
  }
};

const initialPID: PIDParameters = {
  enabled: false,
  targetDropletSize: 80.0,
  Kp: 0.5,
  Ki: 0.1,
  Kd: 0.01,
  outputMin: 0.5,
  outputMax: 50.0
};

const initialPerturbation: PerturbationConfig = {
  enabled: false,
  type: 'sinusoidal',
  phase: 'dispersed',
  amplitude: 10.0,
  frequency: 0.5
};

const initialSimulationConfig: SimulationConfig = {
  mode: 'single_channel',
  faultDetectionEnabled: true,
};

const initialMultichannelConfig: MultichannelConfig = {
  nChannels: 4,
  channelSpacing: 200.0,
  crosstalkStrength: 0.15,
  crosstalkDecay: 2.0,
  pressureCoupling: 0.1,
};

const initialNeuralConfig: NeuralSurrogateConfig = {
  hiddenLayers: [64, 32, 16],
  trainingSamples: 10000,
  epochs: 2000,
  learningRate: 0.001,
  batchSize: 64,
};

const initialStatus: ExtendedSimulationStatus = {
  running: false,
  time: 0,
  parameters: initialParameters,
  perturbation: initialPerturbation,
  mode: 'single_channel',
};

export const useSimulationStore = create<SimulationState>((set, get) => ({
  status: initialStatus,
  optimizationStatus: null,
  timeSeries: null,
  wsConnected: false,
  isLoading: false,
  error: null,

  simulationMode: 'single_channel',
  multichannelConfig: initialMultichannelConfig,
  neuralSurrogateConfig: initialNeuralConfig,
  neuralSurrogateStatus: null,
  faultDetectionStatus: null,

  fetchStatus: async () => {
    set({ isLoading: true });
    try {
      const status = await api.getSimulationStatus();
      set({ status, isLoading: false });
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
    }
  },

  fetchTimeSeries: async () => {
    try {
      const data = await api.getTimeSeries();
      set({ timeSeries: data });
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  controlSimulation: async (action) => {
    set({ isLoading: true });
    try {
      await api.controlSimulation(action);
      if (action === 'reset') {
        set({ timeSeries: null });
      }
      set({ isLoading: false });
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
    }
  },

  updateParameters: async (params) => {
    try {
      await api.updateParameters(params);
      set((state) => ({
        status: state.status ? { ...state.status, parameters: params } : null
      }));
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  updatePID: async (params) => {
    try {
      await api.updatePIDParameters(params);
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  updatePerturbation: async (config) => {
    try {
      await api.updatePerturbationConfig(config);
      set((state) => ({
        status: state.status ? { ...state.status, perturbation: config } : null
      }));
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  startOptimization: async (config) => {
    set({ isLoading: true });
    try {
      await api.startOptimization(config);
      set({ isLoading: false });
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
    }
  },

  stopOptimization: async () => {
    try {
      await api.stopOptimization();
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  connectWebSocket: () => {
    simulationWs.connect({
      onSimulationData: (data: ExtendedSimulationStatus) => {
        set({
          status: data,
          wsConnected: true,
          error: null
        });

        set((state) => {
          if (!data.latestResult) return {};

          const result = data.latestResult;
          const currentTS = state.timeSeries;

          if (!currentTS) {
            return {
              timeSeries: {
                timestamps: [result.timestamp],
                dropletSizes: [result.dropletSize],
                frequencies: [result.generationFrequency],
                continuousFlowRates: [result.continuousFlowRate],
                dispersedFlowRates: [result.dispersedFlowRate]
              }
            };
          }

          const maxPoints = 500;
          const newTimestamps = [...currentTS.timestamps, result.timestamp].slice(-maxPoints);
          const newSizes = [...currentTS.dropletSizes, result.dropletSize].slice(-maxPoints);
          const newFreqs = [...currentTS.frequencies, result.generationFrequency].slice(-maxPoints);
          const newQc = [...currentTS.continuousFlowRates, result.continuousFlowRate].slice(-maxPoints);
          const newQd = [...currentTS.dispersedFlowRates, result.dispersedFlowRate].slice(-maxPoints);

          return {
            timeSeries: {
              timestamps: newTimestamps,
              dropletSizes: newSizes,
              frequencies: newFreqs,
              continuousFlowRates: newQc,
              dispersedFlowRates: newQd
            }
          };
        });
      },
      onOptimizationUpdate: (data) => {
        set({ optimizationStatus: data });
      },
      onOpen: () => {
        set({ wsConnected: true, error: null });
      },
      onClose: () => {
        set({ wsConnected: false });
      },
      onError: () => {
        set({ wsConnected: false, error: 'WebSocket connection error' });
      }
    });
  },

  disconnectWebSocket: () => {
    simulationWs.disconnect();
    set({ wsConnected: false });
  },

  setSimulationMode: async (mode: SimulationMode) => {
    const config: SimulationConfig = {
      mode,
      multichannel: get().multichannelConfig,
      neuralSurrogate: get().neuralSurrogateConfig,
      faultDetectionEnabled: true,
    };
    try {
      await api.updateSimulationConfig(config);
      set({ simulationMode: mode });
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  updateSimulationConfig: async (config: SimulationConfig) => {
    try {
      await api.updateSimulationConfig(config);
      set({
        simulationMode: config.mode,
        multichannelConfig: config.multichannel || get().multichannelConfig,
        neuralSurrogateConfig: config.neuralSurrogate || get().neuralSurrogateConfig,
      });
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  trainNeuralSurrogate: async (config: NeuralSurrogateConfig) => {
    set({ isLoading: true });
    try {
      await api.trainNeuralSurrogate(config);
      set({ isLoading: false, neuralSurrogateConfig: config });
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
    }
  },

  fetchNeuralSurrogateStatus: async () => {
    try {
      const status = await api.getNeuralSurrogateStatus();
      set({ neuralSurrogateStatus: status });
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  updateMultichannelConfig: async (config: MultichannelConfig) => {
    try {
      await api.updateMultichannelConfig(config);
      set({ multichannelConfig: config });
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  setChannelBlocked: async (channelId: number, blocked: boolean, severity: number = 0.5) => {
    try {
      await api.setChannelBlocked(channelId, blocked, severity);
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  setChannelEnabled: async (channelId: number, enabled: boolean) => {
    try {
      await api.setChannelEnabled(channelId, enabled);
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  fetchFaultDetectionStatus: async () => {
    try {
      const status = await api.getFaultDetectionStatus();
      set({ faultDetectionStatus: status });
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },
}));
