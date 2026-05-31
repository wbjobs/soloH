export type QDMaterial = 'CdSe' | 'InP' | 'Perovskite' | 'CdS' | 'ZnS';

export type TransportLayerMaterial = 
  | 'PEDOT:PSS' 
  | 'PVK' 
  | 'TPD' 
  | 'ZnO' 
  | 'TiO2' 
  | 'PBDB-T' 
  | 'PCBM';

export type ElectrodeMaterial = 'ITO' | 'Ag' | 'Al' | 'Au' | 'Ca';

export interface MaterialParams {
  name: string;
  bandGap: number;
  electronAffinity: number;
  electronMass: number;
  holeMass: number;
  permittivity: number;
  refractiveIndex: number;
  electronMobility: number;
  holeMobility: number;
  excitonBindingEnergy: number;
  augerCoefficientN?: number;
  augerCoefficientP?: number;
  interfaceStateDensity?: number;
  defectEnergyLevel?: number;
  electronCaptureCrossSection?: number;
  holeCaptureCrossSection?: number;
}

export interface MQWParams {
  numWells: number;
  wellWidth: number;
  barrierWidth: number;
  wellMaterial: QDMaterial;
  barrierMaterial: QDMaterial;
  couplingEnabled: boolean;
}

export interface CoupledEnergyLevels {
  minibandWidth: number;
  couplingStrength: number;
  splitLevels: number[];
  wavefunctionOverlaps: number[];
}

export interface InputParams {
  qdMaterial: QDMaterial;
  coreSize: number;
  shellThickness: number;
  shellMaterial: QDMaterial;
  deviceStructure: {
    anode: ElectrodeMaterial;
    anodeThickness: number;
    htl: TransportLayerMaterial;
    htlThickness: number;
    qdLayerThickness: number;
    etl: TransportLayerMaterial;
    etlThickness: number;
    cathode: ElectrodeMaterial;
    cathodeThickness: number;
  };
  calculationParams: {
    voltageStart: number;
    voltageEnd: number;
    voltageStep: number;
    gridPoints: number;
    temperature: number;
  };
  mqwParams?: MQWParams;
  agingParams?: {
    testCurrentDensity: number;
    testTemperature: number;
    targetLifetime: number;
  };
  angularParams?: {
    wavelength: number;
    numAngles: number;
  };
}

export interface EnergyLevels {
  conductionBand: number;
  valenceBand: number;
  electronLevels: number[];
  holeLevels: number[];
  fermiLevel: number;
  bandGap: number;
  wavefunctions?: {
    electron: number[][];
    hole: number[][];
  };
  mqwCoupling?: CoupledEnergyLevels;
}

export interface RecombinationResults {
  radiativeRate: number;
  nonRadiativeRate: number;
  srhRate: number;
  augerRate: number;
  iqe: number;
  eqe: number;
  overlapIntegral: number;
  currentDensity?: number;
}

export interface SpectrumPoint {
  wavelength: number;
  intensity: number;
}

export interface AngleSpectrumPoint {
  angle: number;
  intensity: number;
  wavelength: number;
}

export interface AngularDistribution {
  angles: number[];
  intensities: number[];
  peakIntensityAngle: number;
  fwhmAngle: number;
  data: AngleSpectrumPoint[];
}

export interface EmissionSpectrum {
  peakWavelength: number;
  fwhm: number;
  spectrumData: SpectrumPoint[];
  angularDistribution?: AngularDistribution;
}

export interface IVPoint {
  voltage: number;
  currentDensity: number;
}

export interface LVPoint {
  voltage: number;
  brightness: number;
}

export interface AgingPoint {
  time: number;
  brightness: number;
  currentDensity: number;
  voltage: number;
}

export interface AgingResults {
  lt50: number;
  lt70: number;
  lt95: number;
  agingData: AgingPoint[];
  accelerationFactor: number;
  degradationMode: string;
}

export interface IVLCharacteristics {
  jvData: IVPoint[];
  lvData: LVPoint[];
  turnOnVoltage: number;
  maxEQE: number;
  aging?: AgingResults;
}

export interface CarrierDistribution {
  depth: number[];
  electronDensity: number[];
  holeDensity: number[];
  recombinationRate: number[];
  electricField: number[];
}

export interface BandDiagram {
  depth: number[];
  conductionBand: number[];
  valenceBand: number[];
  fermiLevel: number[];
  layerBoundaries: { name: string; position: number }[];
}

export interface CalculationResults {
  energyLevels: EnergyLevels;
  recombination: RecombinationResults;
  emissionSpectrum: EmissionSpectrum;
  ivlCharacteristics: IVLCharacteristics;
  carrierDistribution: CarrierDistribution;
  bandDiagram: BandDiagram;
  calculationTime: number;
}

export interface CalculationProgress {
  status: 'idle' | 'calculating' | 'completed' | 'error';
  progress: number;
  message: string;
  error?: string;
}

export type TabType = 'params' | 'results' | 'visualization';
