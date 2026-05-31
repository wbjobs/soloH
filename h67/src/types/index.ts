export type JunctionType = 'T' | 'flow-focusing' | 'co-flow';

export interface ContinuousPhase {
  flowRate: number;
  viscosity: number;
  density: number;
}

export interface DispersedPhase {
  flowRate: number;
  viscosity: number;
  density: number;
}

export interface ChannelGeometry {
  width: number;
  height: number;
  length: number;
  junctionType: JunctionType;
}

export interface SimulationParameters {
  continuousPhase: ContinuousPhase;
  dispersedPhase: DispersedPhase;
  interfacialTension: number;
  channel: ChannelGeometry;
}

export interface SimulationResult {
  timestamp: number;
  dropletSize: number;
  generationFrequency: number;
  flowRateRatio: number;
  capillaryNumber: number;
  continuousFlowRate: number;
  dispersedFlowRate: number;
  polydispersity?: number;
}

export interface PIDParameters {
  enabled: boolean;
  targetDropletSize: number;
  Kp: number;
  Ki: number;
  Kd: number;
  outputMin: number;
  outputMax: number;
}

export interface PIDStatus {
  enabled: boolean;
  targetSize: number;
  currentSize: number;
  error: number;
  controlOutput: number;
  integralTerm: number;
  derivativeTerm: number;
}

export interface OptimizationConfig {
  targetSize: number;
  continuousFlowRateRange: [number, number];
  dispersedFlowRateRange: [number, number];
  resolution: number;
  objective: 'minimize_error' | 'maximize_frequency' | 'minimize_polydispersity';
}

export interface OptimizationResult {
  continuousFlowRate: number;
  dispersedFlowRate: number;
  dropletSize: number;
  frequency: number;
  error: number;
}

export interface OptimizationStatus {
  running: boolean;
  progress: number;
  totalIterations: number;
  completedIterations: number;
  bestResult?: OptimizationResult;
  results: OptimizationResult[];
}

export type PerturbationType = 'sinusoidal' | 'step' | 'random';
export type PerturbationPhase = 'continuous' | 'dispersed' | 'both';

export interface PerturbationConfig {
  enabled: boolean;
  type: PerturbationType;
  phase: PerturbationPhase;
  amplitude: number;
  frequency: number;
}

export interface SimulationStatus {
  running: boolean;
  time: number;
  parameters: SimulationParameters;
  latestResult?: SimulationResult;
  pidStatus?: PIDStatus;
  perturbation: PerturbationConfig;
}

export interface SimulationTimeSeries {
  timestamps: number[];
  dropletSizes: number[];
  frequencies: number[];
  continuousFlowRates: number[];
  dispersedFlowRates: number[];
}

export type SimulationAction = 'start' | 'pause' | 'reset';

export interface SimulationControl {
  action: SimulationAction;
}

export type SimulationMode = 'single_channel' | 'multichannel' | 'neural_surrogate';
export type FaultType = 'normal' | 'partial_blockage' | 'full_blockage' | 'flow_instability' | 'pressure_anomaly' | 'leakage';
export type OverallStatus = 'normal' | 'warning' | 'critical';

export interface NeuralSurrogateConfig {
  hiddenLayers: number[];
  trainingSamples: number;
  epochs: number;
  learningRate: number;
  batchSize: number;
}

export interface NeuralSurrogateStatus {
  trained: boolean;
  architecture: {
    inputFeatures: string[];
    hiddenLayers: number[];
    outputFeatures: string[];
    activation: string;
    totalParameters: number;
  };
  metrics?: {
    size_mape: number;
    frequency_mape: number;
    size_r2: number;
    frequency_r2: number;
    n_training_samples: number;
    n_validation_samples: number;
    n_epochs: number;
  };
  trainingProgress: number;
  trainingLosses?: number[];
  validationLoss?: number[];
}

export interface MultichannelConfig {
  nChannels: number;
  channelSpacing: number;
  crosstalkStrength: number;
  crosstalkDecay: number;
  pressureCoupling: number;
}

export interface ChannelConfig {
  channelId: number;
  enabled: boolean;
  blocked: boolean;
  blockageSeverity: number;
  continuousFlowRate: number;
  dispersedFlowRate: number;
  xOffset: number;
  yOffset: number;
}

export interface ChannelResult {
  channelId: number;
  enabled: boolean;
  blocked: boolean;
  blockageSeverity?: number;
  dropletSize: number;
  generationFrequency: number;
  continuousFlowRate: number;
  dispersedFlowRate: number;
  baseContinuousFlowRate?: number;
  baseDispersedFlowRate?: number;
  flowRateRatio: number;
  capillaryNumber: number;
  polydispersity?: number;
  crosstalkDeltaQc?: number;
  crosstalkDeltaQd?: number;
}

export interface MultichannelSummary {
  nEnabledChannels: number;
  nBlockedChannels: number;
  meanDropletSize: number;
  stdDropletSize: number;
  sizeCvPercent: number;
  meanFrequency: number;
  stdFrequency: number;
  frequencyCvPercent: number;
  totalContinuousFlowrate: number;
  totalDispersedFlowrate: number;
  totalThroughputHz: number;
  channelUniformityScore: number;
}

export interface MultichannelStatus {
  nChannels: number;
  channelConfigs: ChannelConfig[];
  crosstalkInfo: {
    crosstalkStrength: number;
    hydrodynamicDecayLength: number;
    pressureCoupling: number;
  };
  summaryStats?: MultichannelSummary;
  lastResults: ChannelResult[];
}

export interface ChannelFaultStatus {
  channelId: number;
  faultType: FaultType;
  confidence: number;
  blockageSeverity: number;
  anomalyScore: number;
}

export interface FaultDetectionStatus {
  enabled: boolean;
  overallStatus: OverallStatus;
  channelStatuses: ChannelFaultStatus[];
  anomalies: Array<{
    channelId: number;
    type: string;
    confidence: number;
    severity?: number;
    description: string;
  }>;
  recommendations: string[];
}

export interface SimulationConfig {
  mode: SimulationMode;
  multichannel?: MultichannelConfig;
  neuralSurrogate?: NeuralSurrogateConfig;
  faultDetectionEnabled: boolean;
}

export interface ExtendedSimulationStatus extends SimulationStatus {
  mode: SimulationMode;
  multichannel?: MultichannelStatus;
  faultDetection?: FaultDetectionStatus;
  neuralSurrogate?: NeuralSurrogateStatus;
}

export interface WebSocketMessage {
  type: 'simulation_data' | 'optimization_update' | 'pong';
  data: ExtendedSimulationStatus | OptimizationStatus;
}
