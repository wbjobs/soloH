import {
  SimulationParameters,
  SimulationStatus,
  SimulationControl,
  PIDParameters,
  PerturbationConfig,
  OptimizationConfig,
  OptimizationStatus,
  SimulationTimeSeries,
  NeuralSurrogateConfig,
  NeuralSurrogateStatus,
  MultichannelConfig,
  FaultDetectionStatus,
  ChannelResult,
  MultichannelSummary,
  SimulationConfig,
  ExtendedSimulationStatus,
} from '../types';

const API_BASE = 'http://localhost:8001/api';

export async function healthCheck(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/health`);
  return response.json();
}

export async function getSimulationStatus(): Promise<ExtendedSimulationStatus> {
  const response = await fetch(`${API_BASE}/simulation/status`);
  return response.json();
}

export async function controlSimulation(action: SimulationControl['action']): Promise<{ status: string; action: string }> {
  const response = await fetch(`${API_BASE}/simulation/control`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action })
  });
  return response.json();
}

export async function updateParameters(params: SimulationParameters): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/simulation/parameters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  return response.json();
}

export async function updateSimulationConfig(config: SimulationConfig): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/simulation/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  return response.json();
}

export async function getTimeSeries(): Promise<SimulationTimeSeries> {
  const response = await fetch(`${API_BASE}/simulation/time-series`);
  return response.json();
}

export async function updatePIDParameters(params: PIDParameters): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/pid/parameters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  return response.json();
}

export async function updatePerturbationConfig(config: PerturbationConfig): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/perturbation/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  return response.json();
}

export async function getOptimizationStatus(): Promise<OptimizationStatus> {
  const response = await fetch(`${API_BASE}/optimization/status`);
  return response.json();
}

export async function startOptimization(config: OptimizationConfig): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/optimization/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to start optimization');
  }
  return response.json();
}

export async function stopOptimization(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/optimization/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  return response.json();
}

export async function singleStepSimulation(params: SimulationParameters): Promise<{
  dropletSize: number;
  generationFrequency: number;
  flowRateRatio: number;
  capillaryNumber: number;
}> {
  const response = await fetch(`${API_BASE}/simulation/single-step`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  return response.json();
}

export async function trainNeuralSurrogate(config: NeuralSurrogateConfig): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/neural-surrogate/train`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Training failed');
  }
  return response.json();
}

export async function getNeuralSurrogateStatus(): Promise<NeuralSurrogateStatus> {
  const response = await fetch(`${API_BASE}/neural-surrogate/status`);
  return response.json();
}

export async function neuralSurrogatePredict(params: SimulationParameters): Promise<{
  dropletSize: number;
  generationFrequency: number;
  model: string;
}> {
  const response = await fetch(`${API_BASE}/neural-surrogate/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Prediction failed');
  }
  return response.json();
}

export async function updateMultichannelConfig(config: MultichannelConfig): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/multichannel/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  return response.json();
}

export async function setChannelBlocked(channelId: number, blocked: boolean, severity: number = 0.5): Promise<{
  status: string;
  channelId: number;
  blocked: boolean;
  severity: number;
}> {
  const response = await fetch(`${API_BASE}/multichannel/channel/${channelId}/blocked?blocked=${blocked}&severity=${severity}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  return response.json();
}

export async function setChannelEnabled(channelId: number, enabled: boolean): Promise<{
  status: string;
  channelId: number;
  enabled: boolean;
}> {
  const response = await fetch(`${API_BASE}/multichannel/channel/${channelId}/enabled?enabled=${enabled}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  return response.json();
}

export async function getFaultDetectionStatus(): Promise<FaultDetectionStatus> {
  const response = await fetch(`${API_BASE}/fault-detection/status`);
  return response.json();
}

export async function getMultichannelResults(): Promise<{
  results: ChannelResult[];
  summary: MultichannelSummary;
}> {
  const response = await fetch(`${API_BASE}/multichannel/results`);
  return response.json();
}

export const api = {
  healthCheck,
  getSimulationStatus,
  controlSimulation,
  updateParameters,
  updateSimulationConfig,
  getTimeSeries,
  updatePIDParameters,
  updatePerturbationConfig,
  getOptimizationStatus,
  startOptimization,
  stopOptimization,
  singleStepSimulation,
  trainNeuralSurrogate,
  getNeuralSurrogateStatus,
  neuralSurrogatePredict,
  updateMultichannelConfig,
  setChannelBlocked,
  setChannelEnabled,
  getFaultDetectionStatus,
  getMultichannelResults,
};
