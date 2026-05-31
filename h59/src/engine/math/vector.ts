import type { Vector3, Euler } from '../../types';

export const vec3 = {
  create: (x = 0, y = 0, z = 0): Vector3 => ({ x, y, z }),

  clone: (v: Vector3): Vector3 => ({ x: v.x, y: v.y, z: v.z }),

  add: (a: Vector3, b: Vector3): Vector3 => ({
    x: a.x + b.x,
    y: a.y + b.y,
    z: a.z + b.z,
  }),

  sub: (a: Vector3, b: Vector3): Vector3 => ({
    x: a.x - b.x,
    y: a.y - b.y,
    z: a.z - b.z,
  }),

  mul: (v: Vector3, s: number): Vector3 => ({
    x: v.x * s,
    y: v.y * s,
    z: v.z * s,
  }),

  div: (v: Vector3, s: number): Vector3 => ({
    x: v.x / s,
    y: v.y / s,
    z: v.z / s,
  }),

  dot: (a: Vector3, b: Vector3): number => a.x * b.x + a.y * b.y + a.z * b.z,

  cross: (a: Vector3, b: Vector3): Vector3 => ({
    x: a.y * b.z - a.z * b.y,
    y: a.z * b.x - a.x * b.z,
    z: a.x * b.y - a.y * b.x,
  }),

  length: (v: Vector3): number => Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z),

  normalize: (v: Vector3): Vector3 => {
    const len = vec3.length(v);
    return len > 0 ? vec3.div(v, len) : { x: 0, y: 0, z: 0 };
  },

  distance: (a: Vector3, b: Vector3): number => vec3.length(vec3.sub(a, b)),

  lerp: (a: Vector3, b: Vector3, t: number): Vector3 => ({
    x: a.x + (b.x - a.x) * t,
    y: a.y + (b.y - a.y) * t,
    z: a.z + (b.z - a.z) * t,
  }),

  toArray: (v: Vector3): number[] => [v.x, v.y, v.z],
};

export const eulerToQuaternion = (euler: Euler): [number, number, number, number] => {
  const [x, y, z] = [euler.x, euler.y, euler.z];
  const cx = Math.cos(x / 2);
  const sx = Math.sin(x / 2);
  const cy = Math.cos(y / 2);
  const sy = Math.sin(y / 2);
  const cz = Math.cos(z / 2);
  const sz = Math.sin(z / 2);

  let qx: number, qy: number, qz: number, qw: number;

  if (euler.order === 'XYZ') {
    qx = sx * cy * cz + cx * sy * sz;
    qy = cx * sy * cz - sx * cy * sz;
    qz = cx * cy * sz + sx * sy * cz;
    qw = cx * cy * cz - sx * sy * sz;
  } else if (euler.order === 'ZYX') {
    qx = sx * cy * cz - cx * sy * sz;
    qy = cx * sy * cz + sx * cy * sz;
    qz = cx * cy * sz - sx * sy * cz;
    qw = cx * cy * cz + sx * sy * sz;
  } else {
    qx = sx * cy * cz + cx * sy * sz;
    qy = cx * sy * cz - sx * cy * sz;
    qz = cx * cy * sz + sx * sy * cz;
    qw = cx * cy * cz - sx * sy * sz;
  }

  return [qx, qy, qz, qw];
};

export const quaternionRotate = (
  v: Vector3,
  q: [number, number, number, number]
): Vector3 => {
  const [qx, qy, qz, qw] = q;
  const ix = qw * v.x + qy * v.z - qz * v.y;
  const iy = qw * v.y + qz * v.x - qx * v.z;
  const iz = qw * v.z + qx * v.y - qy * v.x;
  const iw = -qx * v.x - qy * v.y - qz * v.z;

  return {
    x: ix * qw + iw * -qx + iy * -qz - iz * -qy,
    y: iy * qw + iw * -qy + iz * -qx - ix * -qz,
    z: iz * qw + iw * -qz + ix * -qy - iy * -qx,
  };
};

export const eulerRotate = (v: Vector3, euler: Euler): Vector3 => {
  const q = eulerToQuaternion(euler);
  return quaternionRotate(v, q);
};

export const degToRad = (deg: number): number => (deg * Math.PI) / 180;

export const radToDeg = (rad: number): number => (rad * 180) / Math.PI;

export const clamp = (value: number, min: number, max: number): number =>
  Math.max(min, Math.min(max, value));

export const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;

export const randomRange = (min: number, max: number): number =>
  Math.random() * (max - min) + min;

export const gaussianRandom = (mean = 0, std = 1): number => {
  const u1 = Math.random();
  const u2 = Math.random();
  const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  return mean + z * std;
};
