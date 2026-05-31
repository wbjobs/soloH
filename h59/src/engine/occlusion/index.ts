import type { OccluderConfig, Vector3 } from '../../types';
import { vec3, eulerRotate } from '../math/vector';

interface Ray {
  origin: Vector3;
  direction: Vector3;
}

export const checkOcclusion = (
  sourcePos: Vector3,
  targetPos: Vector3,
  occluders: OccluderConfig[]
): boolean => {
  const direction = vec3.normalize(vec3.sub(targetPos, sourcePos));
  const maxDistance = vec3.distance(sourcePos, targetPos);
  const ray: Ray = { origin: sourcePos, direction };

  for (const occluder of occluders) {
    let hit: { t: number } | null = null;

    switch (occluder.shape) {
      case 'box':
        hit = rayBoxIntersect(ray, occluder);
        break;
      case 'cylinder':
        hit = rayCylinderIntersect(ray, occluder);
        break;
      case 'sphere':
        hit = raySphereIntersect(ray, occluder);
        break;
    }

    if (hit && hit.t > 1e-6 && hit.t < maxDistance - 1e-6) {
      return true;
    }
  }

  return false;
};

const transformToLocal = (
  point: Vector3,
  occluder: OccluderConfig
): Vector3 => {
  const translated = vec3.sub(point, occluder.position);
  const inverseOrientation = {
    x: -occluder.orientation.x,
    y: -occluder.orientation.y,
    z: -occluder.orientation.z,
    order: occluder.orientation.order,
  };
  return eulerRotate(translated, inverseOrientation);
};

const rayBoxIntersect = (
  ray: Ray,
  occluder: OccluderConfig
): { t: number } | null => {
  const localOrigin = transformToLocal(ray.origin, occluder);
  const inverseOrientation = {
    x: -occluder.orientation.x,
    y: -occluder.orientation.y,
    z: -occluder.orientation.z,
    order: occluder.orientation.order,
  };
  const localDir = eulerRotate(ray.direction, inverseOrientation);

  const hx = (occluder.size.width || 10) / 2;
  const hy = (occluder.size.height || 10) / 2;
  const hz = (occluder.size.depth || 10) / 2;

  let tmin = -Infinity;
  let tmax = Infinity;

  if (Math.abs(localDir.x) > 1e-10) {
    const t1 = (-hx - localOrigin.x) / localDir.x;
    const t2 = (hx - localOrigin.x) / localDir.x;
    tmin = Math.max(tmin, Math.min(t1, t2));
    tmax = Math.min(tmax, Math.max(t1, t2));
  } else if (localOrigin.x < -hx || localOrigin.x > hx) {
    return null;
  }

  if (Math.abs(localDir.y) > 1e-10) {
    const t1 = (-hy - localOrigin.y) / localDir.y;
    const t2 = (hy - localOrigin.y) / localDir.y;
    tmin = Math.max(tmin, Math.min(t1, t2));
    tmax = Math.min(tmax, Math.max(t1, t2));
  } else if (localOrigin.y < -hy || localOrigin.y > hy) {
    return null;
  }

  if (Math.abs(localDir.z) > 1e-10) {
    const t1 = (-hz - localOrigin.z) / localDir.z;
    const t2 = (hz - localOrigin.z) / localDir.z;
    tmin = Math.max(tmin, Math.min(t1, t2));
    tmax = Math.min(tmax, Math.max(t1, t2));
  } else if (localOrigin.z < -hz || localOrigin.z > hz) {
    return null;
  }

  if (tmax >= tmin && tmax > 0) {
    return { t: Math.max(tmin, 0) };
  }

  return null;
};

const raySphereIntersect = (
  ray: Ray,
  occluder: OccluderConfig
): { t: number } | null => {
  const localOrigin = transformToLocal(ray.origin, occluder);
  const inverseOrientation = {
    x: -occluder.orientation.x,
    y: -occluder.orientation.y,
    z: -occluder.orientation.z,
    order: occluder.orientation.order,
  };
  const localDir = eulerRotate(ray.direction, inverseOrientation);

  const radius = occluder.size.radius || 10;
  const radius2 = radius * radius;

  const a = vec3.dot(localDir, localDir);
  const b = 2 * vec3.dot(localOrigin, localDir);
  const c = vec3.dot(localOrigin, localOrigin) - radius2;

  const discriminant = b * b - 4 * a * c;

  if (discriminant < 0) return null;

  const sqrtDisc = Math.sqrt(discriminant);
  const t1 = (-b - sqrtDisc) / (2 * a);
  const t2 = (-b + sqrtDisc) / (2 * a);

  if (t1 > 0) return { t: t1 };
  if (t2 > 0) return { t: t2 };

  return null;
};

const rayCylinderIntersect = (
  ray: Ray,
  occluder: OccluderConfig
): { t: number } | null => {
  const localOrigin = transformToLocal(ray.origin, occluder);
  const inverseOrientation = {
    x: -occluder.orientation.x,
    y: -occluder.orientation.y,
    z: -occluder.orientation.z,
    order: occluder.orientation.order,
  };
  const localDir = eulerRotate(ray.direction, inverseOrientation);

  const radius = occluder.size.radius || 10;
  const height = occluder.size.height || 20;
  const halfHeight = height / 2;
  const radius2 = radius * radius;

  const ox = localOrigin.x;
  const oy = localOrigin.y;
  const oz = localOrigin.z;
  const dx = localDir.x;
  const dy = localDir.y;
  const dz = localDir.z;

  const a = dx * dx + dz * dz;
  const b = 2 * (ox * dx + oz * dz);
  const c = ox * ox + oz * oz - radius2;

  let tmin = Infinity;

  if (Math.abs(a) > 1e-10) {
    const discriminant = b * b - 4 * a * c;
    if (discriminant >= 0) {
      const sqrtDisc = Math.sqrt(discriminant);
      const t1 = (-b - sqrtDisc) / (2 * a);
      const t2 = (-b + sqrtDisc) / (2 * a);

      for (const t of [t1, t2]) {
        if (t > 0) {
          const y = oy + t * dy;
          if (y >= -halfHeight && y <= halfHeight) {
            tmin = Math.min(tmin, t);
          }
        }
      }
    }
  }

  if (Math.abs(dy) > 1e-10) {
    const tBottom = (-halfHeight - oy) / dy;
    if (tBottom > 0) {
      const x = ox + tBottom * dx;
      const z = oz + tBottom * dz;
      if (x * x + z * z <= radius2) {
        tmin = Math.min(tmin, tBottom);
      }
    }

    const tTop = (halfHeight - oy) / dy;
    if (tTop > 0) {
      const x = ox + tTop * dx;
      const z = oz + tTop * dz;
      if (x * x + z * z <= radius2) {
        tmin = Math.min(tmin, tTop);
      }
    }
  }

  if (tmin < Infinity) {
    return { t: tmin };
  }

  return null;
};

export const createDefaultOccluder = (index: number): OccluderConfig => ({
  id: `occluder-${Date.now()}-${index}`,
  shape: 'box',
  position: { x: 0, y: 0, z: -100 - index * 50 },
  orientation: { x: 0, y: 0, z: 0, order: 'XYZ' },
  size: { width: 20, height: 20, depth: 20 },
});

export const getOccluderMeshData = (
  occluder: OccluderConfig
): { positions: Float32Array; indices: Uint32Array } => {
  switch (occluder.shape) {
    case 'box':
      return createBoxMesh(
        occluder.size.width || 10,
        occluder.size.height || 10,
        occluder.size.depth || 10
      );
    case 'sphere':
      return createSphereMesh(occluder.size.radius || 10, 16, 16);
    case 'cylinder':
      return createCylinderMesh(
        occluder.size.radius || 10,
        occluder.size.height || 20,
        16
      );
  }
};

const createBoxMesh = (w: number, h: number, d: number) => {
  const hw = w / 2, hh = h / 2, hd = d / 2;
  const positions = new Float32Array([
    -hw, -hh, hd, hw, -hh, hd, hw, hh, hd, -hw, hh, hd,
    hw, -hh, -hd, -hw, -hh, -hd, -hw, hh, -hd, hw, hh, -hd,
    -hw, hh, hd, hw, hh, hd, hw, hh, -hd, -hw, hh, -hd,
    -hw, -hh, -hd, hw, -hh, -hd, hw, -hh, hd, -hw, -hh, hd,
    hw, -hh, hd, hw, -hh, -hd, hw, hh, -hd, hw, hh, hd,
    -hw, -hh, -hd, -hw, -hh, hd, -hw, hh, hd, -hw, hh, -hd,
  ]);
  const indices = new Uint32Array([
    0, 1, 2, 0, 2, 3,
    4, 5, 6, 4, 6, 7,
    8, 9, 10, 8, 10, 11,
    12, 13, 14, 12, 14, 15,
    16, 17, 18, 16, 18, 19,
    20, 21, 22, 20, 22, 23,
  ]);
  return { positions, indices };
};

const createSphereMesh = (radius: number, widthSeg: number, heightSeg: number) => {
  const positions: number[] = [];
  const indices: number[] = [];

  for (let y = 0; y <= heightSeg; y++) {
    const v = y / heightSeg;
    const phi = v * Math.PI;
    for (let x = 0; x <= widthSeg; x++) {
      const u = x / widthSeg;
      const theta = u * 2 * Math.PI;
      positions.push(
        -radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.cos(phi),
        radius * Math.sin(phi) * Math.sin(theta)
      );
    }
  }

  for (let y = 0; y < heightSeg; y++) {
    for (let x = 0; x < widthSeg; x++) {
      const a = y * (widthSeg + 1) + x;
      const b = a + widthSeg + 1;
      indices.push(a, b, a + 1, b, b + 1, a + 1);
    }
  }

  return { positions: new Float32Array(positions), indices: new Uint32Array(indices) };
};

const createCylinderMesh = (radius: number, height: number, segments: number) => {
  const hh = height / 2;
  const positions: number[] = [];
  const indices: number[] = [];

  positions.push(0, hh, 0);
  positions.push(0, -hh, 0);

  for (let i = 0; i <= segments; i++) {
    const theta = (i / segments) * 2 * Math.PI;
    const x = radius * Math.cos(theta);
    const z = radius * Math.sin(theta);
    positions.push(x, hh, z);
    positions.push(x, -hh, z);
  }

  for (let i = 0; i < segments; i++) {
    const idx = 2 + i * 2;
    indices.push(0, idx, idx + 2);
    indices.push(1, idx + 3, idx + 1);
    indices.push(idx, idx + 1, idx + 2);
    indices.push(idx + 1, idx + 3, idx + 2);
  }

  return { positions: new Float32Array(positions), indices: new Uint32Array(indices) };
};
