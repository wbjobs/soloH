import type { SourceConfig, Vector3 } from '../../types';
import { vec3, eulerRotate, degToRad } from '../math/vector';

export interface SourceEmissionResult {
  direction: Vector3;
  probability: number;
}

export const getSourceNormal = (source: SourceConfig): Vector3 => {
  const normal = eulerRotate({ x: 0, y: 0, z: 1 }, source.orientation);
  return vec3.normalize(normal);
};

export const sampleEmissionDirection = (
  source: SourceConfig,
  random1: number,
  random2: number
): SourceEmissionResult => {
  const n = source.emissionCoefficient;
  const normal = getSourceNormal(source);

  let theta: number;
  let probability: number;

  switch (source.type) {
    case 'point': {
      theta = Math.acos(2 * random1 - 1);
      probability = 1 / (4 * Math.PI);
      break;
    }
    case 'small_face': {
      theta = Math.acos(Math.pow(random1, 1 / (n + 1)));
      probability = ((n + 1) / (2 * Math.PI)) * Math.pow(Math.cos(theta), n);
      break;
    }
    case 'extended': {
      theta = Math.acos(Math.sqrt(random1));
      probability = Math.cos(theta) / Math.PI;
      break;
    }
    default: {
      theta = Math.acos(Math.pow(random1, 1 / (n + 1)));
      probability = ((n + 1) / (2 * Math.PI)) * Math.pow(Math.cos(theta), n);
    }
  }

  const phi = 2 * Math.PI * random2;

  const sinTheta = Math.sin(theta);
  const localDir = {
    x: sinTheta * Math.cos(phi),
    y: sinTheta * Math.sin(phi),
    z: Math.cos(theta),
  };

  const rotation = source.orientation;
  const worldDir = eulerRotate(localDir, rotation);

  return {
    direction: vec3.normalize(worldDir),
    probability,
  };
};

export const getSourceEmissionRate = (
  source: SourceConfig,
  direction: Vector3
): number => {
  const normal = getSourceNormal(source);
  const cosTheta = Math.max(0, vec3.dot(vec3.normalize(direction), normal));
  const n = source.emissionCoefficient;

  switch (source.type) {
    case 'point':
      return source.power / (4 * Math.PI);
    case 'small_face':
      return (source.power * (n + 1) / (2 * Math.PI)) * Math.pow(cosTheta, n);
    case 'extended':
      return (source.power / Math.PI) * cosTheta;
    default:
      return (source.power * (n + 1) / (2 * Math.PI)) * Math.pow(cosTheta, n);
  }
};

export const getCosineLawThickness = (
  source: SourceConfig,
  sourcePos: Vector3,
  substratePoint: Vector3,
  substrateNormal: Vector3
): number => {
  const toSubstrate = vec3.sub(substratePoint, sourcePos);
  const distance = vec3.length(toSubstrate);
  const direction = vec3.div(toSubstrate, distance);

  const sourceNormal = getSourceNormal(source);
  const cosTheta = Math.max(0, vec3.dot(direction, sourceNormal));
  const cosPhi = Math.max(0, vec3.dot(vec3.mul(direction, -1), substrateNormal));

  const n = source.emissionCoefficient;
  let angularFactor: number;

  switch (source.type) {
    case 'point':
      angularFactor = 1 / (4 * Math.PI);
      break;
    case 'small_face':
      angularFactor = ((n + 1) / (2 * Math.PI)) * Math.pow(cosTheta, n);
      break;
    case 'extended':
      angularFactor = cosTheta / Math.PI;
      break;
    default:
      angularFactor = ((n + 1) / (2 * Math.PI)) * Math.pow(cosTheta, n);
  }

  const geometricFactor = cosPhi / (distance * distance);
  return source.power * angularFactor * geometricFactor;
};

export const createDefaultSource = (id: string, index: number): SourceConfig => {
  const angle = (index * 2 * Math.PI) / 3;
  const radius = 150;
  return {
    id,
    type: 'small_face',
    position: {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
      z: -200,
    },
    orientation: {
      x: degToRad(-30),
      y: 0,
      z: angle + Math.PI / 2,
      order: 'XYZ',
    },
    power: 1.0,
    emissionCoefficient: 2.0,
  };
};
