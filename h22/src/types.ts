export interface LSystemRule {
  predecessor: string;
  successors: Array<{
    string: string;
    probability: number;
  }>;
}

export interface LSystemConfig {
  axiom: string;
  rules: LSystemRule[];
  iterations: number;
  angle: number;
  stepLength: number;
  trunkRadius: number;
  leafSize: number;
  randomness: number;
}

export interface EnvironmentParams {
  light: number;
  water: number;
  nutrients: number;
  temperature: number;
}

export interface GrowthModifier {
  growthRate: number;
  branchAngle: number;
  leafSize: number;
  stepLength: number;
  trunkRadius: number;
}

export interface TurtleState {
  position: [number, number, number];
  direction: [number, number, number];
  heading: number;
  up: [number, number, number];
  right: [number, number, number];
  radius: number;
  depth: number;
}

export interface BranchSegment {
  start: [number, number, number];
  end: [number, number, number];
  radius: number;
  depth: number;
}

export interface LeafData {
  position: [number, number, number];
  direction: [number, number, number];
  size: number;
  rotation: number;
  depth: number;
}

export interface PlantData {
  branches: BranchSegment[];
  leaves: LeafData[];
  lstring: string;
}

export type Season = 'spring' | 'summer' | 'autumn' | 'winter';

export interface SeasonColors {
  spring: [number, number, number];
  summer: [number, number, number];
  autumn: [number, number, number];
  winter: [number, number, number];
}

export type PlantPresetType = 'fern' | 'tree' | 'vine';

export interface PlantPreset {
  name: string;
  type: PlantPresetType;
  lsystem: Omit<LSystemConfig, 'iterations'>;
  seasonColors: SeasonColors;
  windResistance: number;
  lifecycle: Partial<LifecycleConfig>;
  rootCompetitionRadius: number;
  crownCompetitionRadius: number;
}

export interface WindParams {
  strength: number;
  frequency: number;
  direction: [number, number, number];
}

export interface WorkerResultMessage {
  type: 'result';
  plantId: string;
  data: PlantData;
  progress: number;
}

export interface WorkerProgressMessage {
  type: 'progress';
  progress: number;
}

export interface TropismParams {
  phototropism: number;
  hydrotropism: number;
  strength: number;
}

export interface PlantInstance {
  id: string;
  position: [number, number, number];
  presetType: PlantPresetType;
  plantData: PlantData | null;
  growthProgress: number;
  age: number;
  health: number;
  height: number;
  rootRadius: number;
  crownRadius: number;
  isAlive: boolean;
  lifecycleStage: LifecycleStage;
}

export type LifecycleStage = 'seed' | 'germination' | 'seedling' | 'juvenile' | 'mature' | 'senescent' | 'dying' | 'dead';

export interface LifecycleConfig {
  totalLifespan: number;
  seedDuration: number;
  germinationDuration: number;
  seedlingDuration: number;
  juvenileDuration: number;
  matureDuration: number;
  senescentDuration: number;
  dyingDuration: number;
}

export interface ResourceCompetitionParams {
  rootCompetitionWeight: number;
  shadeCompetitionWeight: number;
  resourceDepletionRate: number;
  recoveryRate: number;
}

export interface ResourceAvailability {
  light: number;
  water: number;
  nutrients: number;
}

export interface PlantResourceState {
  available: ResourceAvailability;
  consumed: ResourceAvailability;
  competitionFactor: number;
}

export interface TimelineState {
  currentTime: number;
  totalDuration: number;
  isPlaying: boolean;
  playbackSpeed: number;
  seasonTime: number;
}

export interface WorkerGenerateMessage {
  type: 'generate';
  plantId: string;
  config: LSystemConfig;
  environment: EnvironmentParams;
  iterations: number;
  tropismBias?: [number, number, number];
  ageFactor?: number;
}

export type WorkerMessage = WorkerGenerateMessage | WorkerResultMessage | WorkerProgressMessage;
