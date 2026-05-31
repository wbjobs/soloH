import type { SourceConfig, SubstrateConfig, CalculationResult, OccluderConfig, Euler, Vector3 } from '../../types';
import { generateSubstratePoints, generateMotionPoses, type SubstratePoint } from '../substrates';
import { sampleEmissionDirection, getSourceNormal } from '../sources';
import { vec3, eulerRotate } from '../math/vector';
import { checkOcclusion } from '../occlusion';

interface Ray {
  origin: { x: number; y: number; z: number };
  direction: { x: number; y: number; z: number };
  sourceIndex: number;
}

const eulerRotateLocal = (v: Vector3, euler: Euler): Vector3 => eulerRotate(v, euler);

export const calculateThicknessMonteCarlo = (
  sources: SourceConfig[],
  substrate: SubstrateConfig,
  occluders: OccluderConfig[],
  numParticles: number = 100000,
  onProgress?: (progress: number, message: string) => void
): CalculationResult => {
  const nx = substrate.resolution.x;
  const ny = substrate.resolution.y;

  const motionPoses = generateMotionPoses(
    substrate.position,
    substrate.orientation,
    substrate.motion
  );

  const basePoints = generateSubstratePoints({
    ...substrate,
    position: { x: 0, y: 0, z: 0 },
    orientation: { x: 0, y: 0, z: 0, order: 'XYZ' },
  });

  const nPoints = basePoints.length;
  const nPoses = motionPoses.length;

  const allPosePoints: SubstratePoint[][] = [];
  for (const pose of motionPoses) {
    const transformedPoints = basePoints.map((bp) => {
      const rotatedPos = eulerRotateLocal(bp.position, pose.orientation);
      const rotatedNormal = eulerRotateLocal(bp.normal, pose.orientation);
      return {
        position: {
          x: pose.position.x + rotatedPos.x,
          y: pose.position.y + rotatedPos.y,
          z: pose.position.z + rotatedPos.z,
        },
        normal: rotatedNormal,
        uv: bp.uv,
      };
    });
    allPosePoints.push(transformedPoints);
  }

  const thickness = new Float64Array(nPoints);
  const xCoords = new Float64Array(nx);
  const yCoords = new Float64Array(ny);

  for (let i = 0; i < nx; i++) {
    xCoords[i] = ((i / (nx - 1)) * 2 - 1) * (substrate.size.width / 2);
  }
  for (let j = 0; j < ny; j++) {
    yCoords[j] = ((j / (ny - 1)) * 2 - 1) * (substrate.size.height / 2);
  }

  const totalSourcePower = sources.reduce((sum, s) => sum + s.power, 0);

  const progressInterval = Math.max(1, Math.floor(numParticles / 100));

  for (let p = 0; p < numParticles; p++) {
    const r1 = Math.random();
    let cumulative = 0;
    let selectedSourceIdx = 0;
    for (let i = 0; i < sources.length; i++) {
      cumulative += sources[i].power / totalSourcePower;
      if (r1 <= cumulative) {
        selectedSourceIdx = i;
        break;
      }
    }

    const source = sources[selectedSourceIdx];
    const emission = sampleEmissionDirection(source, Math.random(), Math.random());

    const ray: Ray = {
      origin: { ...source.position },
      direction: emission.direction,
      sourceIndex: selectedSourceIdx,
    };

    const selectedPoseIdx = Math.floor(Math.random() * nPoses);
    const points = allPosePoints[selectedPoseIdx];

    let closestHit: { pointIdx: number; t: number } | null = null;

    for (let i = 0; i < nPoints; i++) {
      const point = points[i];

      if (i < points.length - 1) {
        const nextPoint = points[i + 1];
        const v1 = point.position;
        const v2 = nextPoint.position;
        const v3 = i + nx < points.length ? points[i + nx].position : null;

        if (v3) {
          const hit1 = rayTriangleIntersect(ray, v1, v2, v3);
          if (hit1 && (!closestHit || hit1.t < closestHit.t)) {
            const hitPoint = {
              x: ray.origin.x + ray.direction.x * hit1.t,
              y: ray.origin.y + ray.direction.y * hit1.t,
              z: ray.origin.z + ray.direction.z * hit1.t,
            };
            if (occluders.length === 0 || !checkOcclusion(source.position, hitPoint, occluders)) {
              closestHit = { pointIdx: i, t: hit1.t };
            }
          }

          if (i + nx + 1 < points.length) {
            const v4 = points[i + nx + 1].position;
            const hit2 = rayTriangleIntersect(ray, v2, v4, v3);
            if (hit2 && (!closestHit || hit2.t < closestHit.t)) {
              const hitPoint = {
                x: ray.origin.x + ray.direction.x * hit2.t,
                y: ray.origin.y + ray.direction.y * hit2.t,
                z: ray.origin.z + ray.direction.z * hit2.t,
              };
              if (occluders.length === 0 || !checkOcclusion(source.position, hitPoint, occluders)) {
                closestHit = { pointIdx: i, t: hit2.t };
              }
            }
          }
        }
      }
    }

    if (closestHit) {
      thickness[closestHit.pointIdx] += 1 / nPoses;
    }

    if (p % progressInterval === 0 && onProgress) {
      const progress = (p / numParticles) * 100;
      onProgress(progress, `蒙特卡洛模拟中... ${progress.toFixed(0)}% (${p.toLocaleString()} / ${numParticles.toLocaleString()})`);
    }
  }

  let maxThickness = -Infinity;
  let minThickness = Infinity;
  let sumThickness = 0;

  for (let i = 0; i < nPoints; i++) {
    const t = thickness[i];
    maxThickness = Math.max(maxThickness, t);
    minThickness = Math.min(minThickness, t);
    sumThickness += t;
  }

  const avgThickness = sumThickness / nPoints;
  const uniformity = maxThickness > 0
    ? (1 - (maxThickness - minThickness) / (maxThickness + minThickness)) * 100
    : 0;

  const thicknessMatrix: number[][] = [];
  for (let j = 0; j < ny; j++) {
    const row: number[] = [];
    for (let i = 0; i < nx; i++) {
      row.push(thickness[j * nx + i]);
    }
    thicknessMatrix.push(row);
  }

  if (onProgress) {
    onProgress(100, '蒙特卡洛模拟完成');
  }

  return {
    thickness,
    coordinates: { x: xCoords, y: yCoords },
    uniformity,
    maxThickness,
    minThickness,
    avgThickness,
    thicknessMatrix,
  };
};

function rayTriangleIntersect(
  ray: Ray,
  v0: { x: number; y: number; z: number },
  v1: { x: number; y: number; z: number },
  v2: { x: number; y: number; z: number }
): { t: number; u: number; v: number } | null {
  const eps = 1e-6;

  const edge1 = vec3.sub(v1, v0);
  const edge2 = vec3.sub(v2, v0);
  const h = vec3.cross(ray.direction, edge2);
  const a = vec3.dot(edge1, h);

  if (a > -eps && a < eps) return null;

  const f = 1 / a;
  const s = vec3.sub(ray.origin, v0);
  const u = f * vec3.dot(s, h);

  if (u < 0 || u > 1) return null;

  const q = vec3.cross(s, edge1);
  const v = f * vec3.dot(ray.direction, q);

  if (v < 0 || u + v > 1) return null;

  const t = f * vec3.dot(edge2, q);

  if (t > eps) {
    return { t, u, v };
  }

  return null;
}
