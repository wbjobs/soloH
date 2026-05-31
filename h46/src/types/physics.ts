import * as THREE from 'three';

export interface Vector3 {
  x: number;
  y: number;
  z: number;
}

export type ParticleGrainType = 'fine' | 'coarse';

export interface Particle {
  id: number;
  position: Vector3;
  velocity: Vector3;
  acceleration: Vector3;
  density: number;
  densityPrev: number;
  pressure: number;
  mass: number;
  viscosity: number;
  impactForce: Vector3;
  isActive: boolean;
  isFreeSurface: boolean;
  neighborCount: number;
  colorField: number;
  grainType: ParticleGrainType;
  grainRadius: number;
  grainDensity: number;
  collisionCount: number;
  collidedWithBridge: boolean;
  velocityBeforeCollision: Vector3 | null;
  collisionNormal: Vector3 | null;
  bridgePenetration: number;
  smoothedImpactForce: Vector3;
}

export interface VegetationParams {
  enabled: boolean;
  density: number;
  stemDiameter: number;
  stemHeight: number;
  dragCoefficient: number;
  bendingStiffness: number;
  vegetationZone: {
    startZ: number;
    endZ: number;
    startX: number;
    endX: number;
  };
}

export interface GrainSizeDistribution {
  fineFraction: number;
  coarseFraction: number;
  fineRadius: number;
  coarseRadius: number;
  fineDensity: number;
  coarseDensity: number;
  segregationVelocity: number;
  turbulentDiffusion: number;
}

export interface ProbabilityBin {
  minValue: number;
  maxValue: number;
  count: number;
  probability: number;
  exceedanceProbability: number;
}

export interface ProbabilityDistribution {
  forceHistogram: ProbabilityBin[];
  pressureHistogram: ProbabilityBin[];
  forceCDF: { value: number; probability: number }[];
  pressureCDF: { value: number; probability: number }[];
  forceMean: number;
  forceStd: number;
  forceSkewness: number;
  pressureMean: number;
  pressureStd: number;
  pressureSkewness: number;
  returnPeriods: { period: number; force: number; pressure: number }[];
}

export interface SPHParameters {
  density0: number;
  viscosity: number;
  yieldStress: number;
  smoothingLength: number;
  particleRadius: number;
  particleMass: number;
  gravity: Vector3;
  stiffness: number;
  timeStep: number;
  maxParticles: number;
  cflCoefficient: number;
  vegetation: VegetationParams;
  grainSize: GrainSizeDistribution;
}

export interface ImpactForceData {
  timestamp: number;
  totalForce: Vector3;
  maxPressure: number;
  impactArea: number;
  particleCount: number;
  averageVelocity: number;
  fineParticleForce: Vector3;
  coarseParticleForce: Vector3;
  fineParticleCount: number;
  coarseParticleCount: number;
  probabilityDistribution?: ProbabilityDistribution;
}

export interface TerrainParams {
  width: number;
  depth: number;
  resolution: number;
  amplitude: number;
  roughness: number;
  slope: number;
  seed: number;
}

export interface BridgeParams {
  position: Vector3;
  scale: Vector3;
  rotation: Vector3;
  modelPath: string | null;
}

export interface BoundaryBox {
  min: Vector3;
  max: Vector3;
}

export interface CollisionResult {
  collided: boolean;
  normal: Vector3;
  penetration: number;
  point: Vector3;
}

export const createVector3 = (x: number = 0, y: number = 0, z: number = 0): Vector3 => ({
  x, y, z
});

export const vector3ToThree = (v: Vector3): THREE.Vector3 => 
  new THREE.Vector3(v.x, v.y, v.z);

export const threeToVector3 = (v: THREE.Vector3): Vector3 => 
  ({ x: v.x, y: v.y, z: v.z });

export const vecAdd = (a: Vector3, b: Vector3): Vector3 => 
  ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z });

export const vecSub = (a: Vector3, b: Vector3): Vector3 => 
  ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });

export const vecScale = (a: Vector3, s: number): Vector3 => 
  ({ x: a.x * s, y: a.y * s, z: a.z * s });

export const vecDot = (a: Vector3, b: Vector3): number => 
  a.x * b.x + a.y * b.y + a.z * b.z;

export const vecCross = (a: Vector3, b: Vector3): Vector3 => ({
  x: a.y * b.z - a.z * b.y,
  y: a.z * b.x - a.x * b.z,
  z: a.x * b.y - a.y * b.x
});

export const vecLength = (a: Vector3): number => 
  Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z);

export const vecNormalize = (a: Vector3): Vector3 => {
  const len = vecLength(a);
  return len > 1e-10 ? vecScale(a, 1 / len) : { x: 0, y: 0, z: 0 };
};

export const vecClone = (a: Vector3): Vector3 => ({ ...a });

export const vecDistance = (a: Vector3, b: Vector3): number => 
  vecLength(vecSub(a, b));
