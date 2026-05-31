export interface Material {
  id: string;
  name: string;
  formula: string;
  bandgap: number;
  bandgapTempCoeff: number;
  electronAffinity: number;
  effectiveMassElectron: number;
  effectiveMassHole: number;
  refractiveIndex: number;
  augerCoefficient: number;
  radiativeCoeff: number;
  mobilityElectron: number;
  mobilityHole: number;
  isCustom: boolean;
  createdAt: number;
}

export interface EmitterLayer {
  thickness: number;
  material: string;
  n: number;
  k: number;
  dn_dT: number;
  dk_dT: number;
  referenceTemperature: number;
}

export interface CalculationParams {
  sourceTemperature: number;
  materialId: string;
  seriesResistance: number;
  shuntResistance: number;
  temperature: number;
  includeAuger: boolean;
  includeRadiative: boolean;
  includeSeriesResistance: boolean;
  emitterStructure: EmitterLayer[];
  optimizeEmitter: boolean;
  emitterSheetResistance: number;
  fingerSpacing: number;
  fingerWidth: number;
  useDistributedResistance: boolean;
  concentrationRatio: number;
  includeConcentration: boolean;
  includeWasteHeatRecovery: boolean;
  tegFigureOfMerit: number;
  tegColdSideTemperature: number;
  tegEfficiency: number;
  includeLifetimePrediction: boolean;
  referenceLifetime: number;
  activationEnergy: number;
}

export interface SpectrumPoint {
  wavelength: number;
  intensity: number;
}

export interface IVPoint {
  v: number;
  j: number;
}

export interface QEPoint {
  wavelength: number;
  eqe: number;
}

export interface ReflectancePoint {
  wavelength: number;
  r: number;
}

export interface BandgapScanResult {
  bandgaps: number[];
  temperatures: number[];
  efficiencies: number[][];
}

export interface ConcentrationResult {
  concentrationRatio: number;
  concentratedJsc: number;
  concentratedVoc: number;
  concentratedEfficiency: number;
  concentratedFillFactor: number;
  cellTemperatureRise: number;
  actualCellTemperature: number;
  concentrationEfficiencyCurve: { cr: number; efficiency: number; jsc: number }[];
  optimumConcentration: number;
  maximumEfficiency: number;
}

export interface WasteHeatResult {
  wasteHeatDensity: number;
  totalWasteHeat: number;
  tegOutputPower: number;
  tegEfficiency: number;
  systemTotalEfficiency: number;
  heatRejectionTemperature: number;
  carnotEfficiency: number;
}

export interface LifetimeResult {
  estimatedLifetime: number;
  accelerationFactor: number;
  remainingLifetime: number;
  degradationRate: number;
  lifetimeCurve: { temperature: number; lifetime: number }[];
  mtbf: number;
  failureRate: number;
}

export interface CalculationResult {
  efficiency: number;
  shortCircuitCurrent: number;
  openCircuitVoltage: number;
  fillFactor: number;
  ivCurve: IVPoint[];
  quantumEfficiency: QEPoint[];
  blackbodySpectrum: SpectrumPoint[];
  emitterReflectance: ReflectancePoint[];
  bandgapScan: BandgapScanResult;
  optimizedEmitter: EmitterLayer[];
  calculationTime: number;
  maxPowerDensity: number;
  voltageAtMaxPower: number;
  currentAtMaxPower: number;
  concentrationResult?: ConcentrationResult;
  wasteHeatResult?: WasteHeatResult;
  lifetimeResult?: LifetimeResult;
}

export type CalculationStatus = 'idle' | 'running' | 'completed' | 'error';

export interface CalculationState {
  status: CalculationStatus;
  progress: number;
  currentStep: string;
  result: CalculationResult | null;
  error: string | null;
}

export type WorkerMessageType = 
  | 'startCalculation'
  | 'cancelCalculation'
  | 'progress'
  | 'result'
  | 'error';

export interface WorkerMessage {
  type: WorkerMessageType;
  payload?: any;
}
