export interface SellmeierCoefficients {
  A1: number;
  B1: number;
  A2: number;
  B2: number;
  A3: number;
  B3: number;
}

export interface CrystalMaterial {
  id: string;
  name: string;
  formula: string;
  sellmeier: {
    ordinary: SellmeierCoefficients;
    extraordinary?: SellmeierCoefficients;
  };
  nonlinearCoefficients: {
    d33: number;
    d31: number;
    d22: number;
  };
  thermoOpticCoefficients: {
    dn_o_dT: number;
    dn_e_dT: number;
  };
  transparencyRange: [number, number];
  damageThreshold: number;
}

export type PhaseMatchType = 'type1' | 'type2';
export type PolingType = 'uniform' | 'linear_chirp' | 'quadratic_chirp' | 'fan' | '2d';
export type Polarization = 'ordinary' | 'extraordinary';
export type CascadeProcess = 'opo' | 'shg_signal' | 'shg_idler' | 'sfg_pump_signal' | 'full_cascade';
export type NoncollinearConfig = 'collinear' | 'noncollinear_signal' | 'noncollinear_idler' | 'noncollinear_both';

export interface SimulationParams {
  pumpWavelength: number;
  signalWavelengthMin: number;
  signalWavelengthMax: number;
  signalWavelengthStep: number;
  crystalId: string;
  temperature: number;
  angleTheta: number;
  anglePhi: number;
  crystalLength: number;
  phaseMatchType: PhaseMatchType;
  polingType: PolingType;
  polingPeriod: number;
  pumpPower: number;
  pumpWaist: number;
  signalPower: number;
  signalWaist: number;
  chirpRate: number;
  quadraticChirpRate: number;
  dutyCycle: number;
  // 级联非线性过程
  enableCascade: boolean;
  cascadeProcess: CascadeProcess;
  cascadeEfficiencyThreshold: number;
  // 非共线相位匹配
  noncollinearConfig: NoncollinearConfig;
  noncollinearAngleSignal: number;
  noncollinearAngleIdler: number;
  // 蒙特卡洛分析
  enableMonteCarlo: boolean;
  monteCarloTrials: number;
  periodFluctuationStd: number;
  dutyCycleFluctuationStd: number;
  temperatureFluctuationStd: number;
}

export interface PhaseMatchingResult {
  phaseMatchAngle: number;
  walkoffAngle: number;
  effectiveNonlinearity: number;
  coherenceLength: number;
  groupVelocityMismatch: number;
  nPump: number;
  nSignal: number;
  nIdler: number;
  idlerWavelength: number;
  deltaK: number;
}

export interface CoupledWaveResult {
  z: number[];
  pumpIntensity: number[];
  signalIntensity: number[];
  idlerIntensity: number[];
  pumpPhase: number[];
  signalPhase: number[];
  idlerPhase: number[];
  conversionEfficiency: number;
  pumpDepletion: number;
}

export interface EfficiencyCurvePoint {
  wavelength: number;
  efficiency: number;
}

export interface ToleranceData {
  temperatureTolerance: number;
  angleTolerance: number;
  wavelengthTolerance: number;
  bandwidth: number;
}

export interface FieldDataPoint {
  x: number;
  y: number;
  z: number;
  amplitude: number;
  phase: number;
}

export interface DomainStructurePoint {
  x: number;
  y: number;
  z: number;
  polarity: number;
  period: number;
}

export interface SpectrumPoint {
  frequency: number;
  amplitude: number;
  wavelength: number;
}

export interface CascadeResult {
  process: CascadeProcess;
  stages: CascadeStageResult[];
  totalEfficiency: number;
  intermediateWavelengths: number[];
}

export interface CascadeStageResult {
  stage: number;
  processType: 'opo' | 'shg' | 'sfg' | 'dfg';
  processName: string;
  inputWavelengths: number[];
  inputWavelength: number;
  outputWavelength: number;
  efficiency: number;
  outputPower: number;
  z: number[];
  intensity: number[];
}

export interface NoncollinearResult {
  config: NoncollinearConfig;
  signalAngle: number;
  idlerAngle: number;
  walkoffAngleSignal: number;
  walkoffAngleIdler: number;
  acceptanceAngleSignal: number;
  acceptanceAngleIdler: number;
  phaseMatchAngle: number;
  effectiveNonlinearity: number;
  kPump: number;
  kSignal: number;
  kIdler: number;
  kGrating: number;
  kPumpX: number;
  kPumpZ: number;
  kSignalX: number;
  kSignalZ: number;
  kIdlerX: number;
  kIdlerZ: number;
  deltaKx: number;
  deltaKz: number;
  deltaK: number;
}

export interface MonteCarloResult {
  trials: number;
  meanEfficiency: number;
  stdEfficiency: number;
  minEfficiency: number;
  maxEfficiency: number;
  medianEfficiency: number;
  efficiencyDistribution: { bin: number; count: number }[];
  periodFluctuationStd: number;
  dutyCycleFluctuationStd: number;
  temperatureFluctuationStd: number;
  yield95: number;
  yield50: number;
  correlationData: { periodError: number; efficiency: number }[];
}

export interface CalculationResult {
  phaseMatching: PhaseMatchingResult | null;
  coupledWave: CoupledWaveResult | null;
  efficiencyCurve: EfficiencyCurvePoint[];
  toleranceData: ToleranceData | null;
  fieldDistribution: FieldDataPoint[];
  domainStructure: DomainStructurePoint[];
  spectrumData: SpectrumPoint[];
  cascadeResult: CascadeResult | null;
  noncollinearResult: NoncollinearResult | null;
  monteCarloResult: MonteCarloResult | null;
}

export const DEFAULT_PARAMS: SimulationParams = {
  pumpWavelength: 1064,
  signalWavelengthMin: 1400,
  signalWavelengthMax: 1800,
  signalWavelengthStep: 5,
  crystalId: 'linbo3',
  temperature: 25,
  angleTheta: 90,
  anglePhi: 0,
  crystalLength: 30,
  phaseMatchType: 'type1',
  polingType: 'uniform',
  polingPeriod: 28.5,
  pumpPower: 1.0,
  pumpWaist: 50,
  signalPower: 0.001,
  signalWaist: 50,
  chirpRate: 0.1,
  quadraticChirpRate: 0.001,
  dutyCycle: 0.5,
  enableCascade: false,
  cascadeProcess: 'opo',
  cascadeEfficiencyThreshold: 0.01,
  noncollinearConfig: 'collinear',
  noncollinearAngleSignal: 0.5,
  noncollinearAngleIdler: 0.5,
  enableMonteCarlo: false,
  monteCarloTrials: 100,
  periodFluctuationStd: 0.05,
  dutyCycleFluctuationStd: 0.02,
  temperatureFluctuationStd: 0.1,
};
