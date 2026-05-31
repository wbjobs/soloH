export type SourceType = 'point' | 'small_face' | 'extended';

export type SubstrateType = 'plane' | 'sphere' | 'aspheric' | 'stl';

export type CalculationMethod = 'cosine' | 'monte_carlo';

export type OptimizationMethod = 'genetic' | 'gradient_descent';

export type MotionType = 'none' | 'rotation' | 'tilt' | 'planetary';

export type OccluderShape = 'box' | 'cylinder' | 'sphere';

export interface Vector3 {
  x: number;
  y: number;
  z: number;
}

export interface Euler {
  x: number;
  y: number;
  z: number;
  order: string;
}

export interface SourceConfig {
  id: string;
  type: SourceType;
  position: Vector3;
  orientation: Euler;
  power: number;
  emissionCoefficient: number;
}

export interface SubstrateMotion {
  type: MotionType;
  enabled: boolean;
  rotationAxis: 'x' | 'y' | 'z';
  rotationSpeed: number;
  rotationCenter: Vector3;
  tiltAngle: number;
  tiltAxis: 'x' | 'y' | 'z';
  integrationSteps: number;
  planetaryRadius?: number;
  planetaryRotationSpeed?: number;
}

export interface OccluderConfig {
  id: string;
  shape: OccluderShape;
  position: Vector3;
  orientation: Euler;
  size: { width?: number; height?: number; depth?: number; radius?: number };
}

export interface SubstrateConfig {
  type: SubstrateType;
  position: Vector3;
  orientation: Euler;
  size: { width: number; height: number; radius?: number; curvature?: number };
  resolution: { x: number; y: number };
  stlData?: STLData;
  motion: SubstrateMotion;
}

export interface GeneticConfig {
  adaptiveMutation: boolean;
  mutationRateMin: number;
  mutationRateMax: number;
  diversityThreshold: number;
  catastropheEnabled: boolean;
  catastropheThreshold: number;
  catastropheCount: number;
  crowdingEnabled: boolean;
  crowdingFactor: number;
}

export interface STLData {
  vertices: Float32Array;
  normals: Float32Array;
  faces: Uint32Array;
}

export interface CalculationConfig {
  method: CalculationMethod;
  monteCarloParticles?: number;
  integrationPoints?: number;
  occluders: OccluderConfig[];
}

export interface CalculationResult {
  thickness: Float64Array;
  coordinates: { x: Float64Array; y: Float64Array };
  uniformity: number;
  maxThickness: number;
  minThickness: number;
  avgThickness: number;
  thicknessMatrix?: number[][];
}

export interface OptimizationConfig {
  enabled: boolean;
  method: OptimizationMethod;
  sourceIds: string[];
  bounds: { min: Vector3; max: Vector3 };
  targetUniformity: number;
  maxIterations: number;
  populationSize?: number;
  geneticConfig: GeneticConfig;
}

export interface OptimizationIteration {
  iteration: number;
  bestUniformity: number;
  bestPositions: { sourceId: string; position: Vector3 }[];
  avgUniformity: number;
}

export interface OptimizationResult {
  success: boolean;
  bestUniformity: number;
  bestPositions: { sourceId: string; position: Vector3 }[];
  iterations: number;
  history: { iteration: number; uniformity: number }[];
}

export interface CalculationPayload {
  sources: SourceConfig[];
  substrate: SubstrateConfig;
  config: CalculationConfig;
  occluders: OccluderConfig[];
}

export interface OptimizationPayload {
  sources: SourceConfig[];
  substrate: SubstrateConfig;
  config: CalculationConfig;
  optimization: OptimizationConfig;
  occluders: OccluderConfig[];
}

export type WorkerMessage =
  | { type: 'START_CALCULATION'; payload: CalculationPayload }
  | { type: 'START_OPTIMIZATION'; payload: OptimizationPayload }
  | { type: 'CANCEL' };

export type WorkerResponse =
  | { type: 'PROGRESS'; payload: { progress: number; message: string } }
  | { type: 'CALCULATION_COMPLETE'; payload: CalculationResult }
  | { type: 'OPTIMIZATION_ITERATION'; payload: OptimizationIteration }
  | { type: 'OPTIMIZATION_COMPLETE'; payload: OptimizationResult }
  | { type: 'ERROR'; payload: { message: string } };

export interface AppState {
  sources: SourceConfig[];
  substrate: SubstrateConfig;
  calculationConfig: CalculationConfig;
  optimizationConfig: OptimizationConfig;
  occluders: OccluderConfig[];
  calculationResult: CalculationResult | null;
  optimizationResult: OptimizationResult | null;
  optimizationHistory: OptimizationIteration[];
  isCalculating: boolean;
  isOptimizing: boolean;
  progress: number;
  progressMessage: string;
  error: string | null;
}
