import type { SubstrateConfig, Vector3, SubstrateMotion, Euler } from '../../types';
import { vec3, eulerRotate, degToRad } from '../math/vector';

export interface SubstratePoint {
  position: Vector3;
  normal: Vector3;
  uv: { u: number; v: number };
}

export const generateSubstratePoints = (
  config: SubstrateConfig
): SubstratePoint[] => {
  const { resolution, size } = config;
  const points: SubstratePoint[] = [];
  const nx = resolution.x;
  const ny = resolution.y;

  for (let j = 0; j < ny; j++) {
    for (let i = 0; i < nx; i++) {
      const u = (i / (nx - 1)) * 2 - 1;
      const v = (j / (ny - 1)) * 2 - 1;

      let localPos: Vector3;
      let localNormal: Vector3;

      switch (config.type) {
        case 'plane': {
          localPos = {
            x: (u * size.width) / 2,
            y: (v * size.height) / 2,
            z: 0,
          };
          localNormal = { x: 0, y: 0, z: 1 };
          break;
        }
        case 'sphere': {
          const radius = size.radius || 100;
          const theta = u * Math.PI;
          const phi = v * Math.PI / 2;
          localPos = {
            x: radius * Math.sin(phi) * Math.cos(theta),
            y: radius * Math.sin(phi) * Math.sin(theta),
            z: radius * Math.cos(phi),
          };
          localNormal = vec3.normalize(localPos);
          break;
        }
        case 'aspheric': {
          const curvature = size.curvature || 0.01;
          const k = -1;
          const x = (u * size.width) / 2;
          const y = (v * size.height) / 2;
          const r2 = x * x + y * y;
          const sqrtTerm = Math.sqrt(1 - (1 + k) * curvature * curvature * r2);
          const z = (curvature * r2) / (1 + sqrtTerm);
          localPos = { x, y, z };
          const dzdx = (curvature * x) / sqrtTerm;
          const dzdy = (curvature * y) / sqrtTerm;
          localNormal = vec3.normalize({ x: -dzdx, y: -dzdy, z: 1 });
          break;
        }
        case 'stl': {
          localPos = {
            x: (u * size.width) / 2,
            y: (v * size.height) / 2,
            z: 0,
          };
          localNormal = { x: 0, y: 0, z: 1 };
          break;
        }
        default: {
          localPos = {
            x: (u * size.width) / 2,
            y: (v * size.height) / 2,
            z: 0,
          };
          localNormal = { x: 0, y: 0, z: 1 };
        }
      }

      const worldPos = vec3.add(config.position, eulerRotate(localPos, config.orientation));
      const worldNormal = eulerRotate(localNormal, config.orientation);

      points.push({
        position: worldPos,
        normal: vec3.normalize(worldNormal),
        uv: { u, v },
      });
    }
  }

  return points;
};

export const getSubstrateMeshPoints = (
  config: SubstrateConfig
): { positions: Float32Array; normals: Float32Array } => {
  const points = generateSubstratePoints(config);
  const positions = new Float32Array(points.length * 3);
  const normals = new Float32Array(points.length * 3);

  points.forEach((p, i) => {
    positions[i * 3] = p.position.x;
    positions[i * 3 + 1] = p.position.y;
    positions[i * 3 + 2] = p.position.z;
    normals[i * 3] = p.normal.x;
    normals[i * 3 + 1] = p.normal.y;
    normals[i * 3 + 2] = p.normal.z;
  });

  return { positions, normals };
};

export const createDefaultSubstrate = (): SubstrateConfig => ({
  type: 'plane',
  position: { x: 0, y: 0, z: 0 },
  orientation: { x: 0, y: 0, z: 0, order: 'XYZ' },
  size: { width: 200, height: 200 },
  resolution: { x: 50, y: 50 },
  motion: {
    type: 'none',
    enabled: false,
    rotationAxis: 'z',
    rotationSpeed: 30,
    rotationCenter: { x: 0, y: 0, z: 0 },
    tiltAngle: 0,
    tiltAxis: 'x',
    integrationSteps: 36,
  },
});

export const createDefaultMotion = (): SubstrateMotion => ({
  type: 'none',
  enabled: false,
  rotationAxis: 'z',
  rotationSpeed: 30,
  rotationCenter: { x: 0, y: 0, z: 0 },
  tiltAngle: 0,
  tiltAxis: 'x',
  integrationSteps: 36,
});

export const generateMotionPoses = (
  basePosition: Vector3,
  baseOrientation: Euler,
  motion: SubstrateMotion
): { position: Vector3; orientation: Euler }[] => {
  if (!motion.enabled || motion.type === 'none') {
    return [{ position: { ...basePosition }, orientation: { ...baseOrientation } }];
  }

  const poses: { position: Vector3; orientation: Euler }[] = [];
  const steps = motion.integrationSteps;

  for (let i = 0; i < steps; i++) {
    const t = i / steps;
    let position = { ...basePosition };
    let orientation = { ...baseOrientation };

    if (motion.type === 'rotation' || motion.type === 'planetary') {
      const angle = (t * 2 * Math.PI * motion.rotationSpeed) / 360;
      const rotatedPos = rotateAroundAxis(
        vec3.sub(position, motion.rotationCenter),
        motion.rotationAxis,
        angle
      );
      position = vec3.add(rotatedPos, motion.rotationCenter);

      orientation = composeEulerRotation(orientation, motion.rotationAxis, angle);
    }

    if (motion.type === 'tilt') {
      const tiltAngleRad = degToRad(motion.tiltAngle);
      const angle = Math.sin(t * 2 * Math.PI) * tiltAngleRad;
      orientation = composeEulerRotation(orientation, motion.tiltAxis, angle);
    }

    if (motion.type === 'planetary' && motion.planetaryRadius) {
      const planetAngle = (t * 2 * Math.PI * (motion.planetaryRotationSpeed || 60)) / 360;
      const planetOffset = {
        x: Math.cos(planetAngle) * motion.planetaryRadius,
        y: Math.sin(planetAngle) * motion.planetaryRadius,
        z: 0,
      };
      position = vec3.add(position, planetOffset);
    }

    poses.push({ position, orientation });
  }

  return poses;
};

const rotateAroundAxis = (v: Vector3, axis: 'x' | 'y' | 'z', angle: number): Vector3 => {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);

  if (axis === 'x') {
    return {
      x: v.x,
      y: v.y * cos - v.z * sin,
      z: v.y * sin + v.z * cos,
    };
  } else if (axis === 'y') {
    return {
      x: v.x * cos + v.z * sin,
      y: v.y,
      z: -v.x * sin + v.z * cos,
    };
  } else {
    return {
      x: v.x * cos - v.y * sin,
      y: v.x * sin + v.y * cos,
      z: v.z,
    };
  }
};

const composeEulerRotation = (euler: Euler, axis: 'x' | 'y' | 'z', angle: number): Euler => {
  const result = { ...euler };
  result[axis] += angle;
  return result;
};

export const getSubstrateBoundingBox = (config: SubstrateConfig) => {
  const points = generateSubstratePoints(config);
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;

  points.forEach(p => {
    minX = Math.min(minX, p.position.x);
    minY = Math.min(minY, p.position.y);
    minZ = Math.min(minZ, p.position.z);
    maxX = Math.max(maxX, p.position.x);
    maxY = Math.max(maxY, p.position.y);
    maxZ = Math.max(maxZ, p.position.z);
  });

  return {
    min: { x: minX, y: minY, z: minZ },
    max: { x: maxX, y: maxY, z: maxZ },
  };
};
