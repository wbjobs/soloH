import { Vector3, createVector3 } from '../types/physics';

export interface TerrainGenerateParams {
  width: number;
  depth: number;
  resolution: number;
  amplitude: number;
  roughness: number;
  slope: number;
  seed: number;
}

class SimplexNoise {
  private perm: number[];
  private gradP: { x: number; y: number; z: number }[];

  private grad3 = [
    { x: 1, y: 1, z: 0 }, { x: -1, y: 1, z: 0 }, { x: 1, y: -1, z: 0 }, { x: -1, y: -1, z: 0 },
    { x: 1, y: 0, z: 1 }, { x: -1, y: 0, z: 1 }, { x: 1, y: 0, z: -1 }, { x: -1, y: 0, z: -1 },
    { x: 0, y: 1, z: 1 }, { x: 0, y: -1, z: 1 }, { x: 0, y: 1, z: -1 }, { x: 0, y: -1, z: -1 }
  ];

  constructor(seed: number = Math.random()) {
    const p: number[] = [];
    for (let i = 0; i < 256; i++) {
      p[i] = i;
    }

    let n: number;
    let q: number;
    for (let i = 255; i > 0; i--) {
      seed = (seed * 16807) % 2147483647;
      n = seed % (i + 1);
      q = p[i];
      p[i] = p[n];
      p[n] = q;
    }

    this.perm = new Array(512);
    this.gradP = new Array(512);
    for (let i = 0; i < 512; i++) {
      this.perm[i] = p[i & 255];
      this.gradP[i] = this.grad3[this.perm[i] % 12];
    }
  }

  private dot(g: { x: number; y: number; z: number }, x: number, y: number): number {
    return g.x * x + g.y * y;
  }

  noise2D(xin: number, yin: number): number {
    const F2 = 0.5 * (Math.sqrt(3.0) - 1.0);
    const G2 = (3.0 - Math.sqrt(3.0)) / 6.0;

    let n0, n1, n2;

    const s = (xin + yin) * F2;
    const i = Math.floor(xin + s);
    const j = Math.floor(yin + s);

    const t = (i + j) * G2;
    const X0 = i - t;
    const Y0 = j - t;
    const x0 = xin - X0;
    const y0 = yin - Y0;

    let i1, j1;
    if (x0 > y0) { i1 = 1; j1 = 0; }
    else { i1 = 0; j1 = 1; }

    const x1 = x0 - i1 + G2;
    const y1 = y0 - j1 + G2;
    const x2 = x0 - 1.0 + 2.0 * G2;
    const y2 = y0 - 1.0 + 2.0 * G2;

    const ii = i & 255;
    const jj = j & 255;
    const gi0 = this.gradP[ii + this.perm[jj]];
    const gi1 = this.gradP[ii + i1 + this.perm[jj + j1]];
    const gi2 = this.gradP[ii + 1 + this.perm[jj + 1]];

    let t0 = 0.5 - x0 * x0 - y0 * y0;
    if (t0 < 0) n0 = 0.0;
    else {
      t0 *= t0;
      n0 = t0 * t0 * this.dot(gi0, x0, y0);
    }

    let t1 = 0.5 - x1 * x1 - y1 * y1;
    if (t1 < 0) n1 = 0.0;
    else {
      t1 *= t1;
      n1 = t1 * t1 * this.dot(gi1, x1, y1);
    }

    let t2 = 0.5 - x2 * x2 - y2 * y2;
    if (t2 < 0) n2 = 0.0;
    else {
      t2 *= t2;
      n2 = t2 * t2 * this.dot(gi2, x2, y2);
    }

    return 70.0 * (n0 + n1 + n2);
  }
}

export function generateTerrain(params: TerrainGenerateParams): {
  heights: number[][];
  vertices: Vector3[];
  normals: Vector3[];
} {
  const { width, depth, resolution, amplitude, roughness, slope, seed } = params;
  const noise = new SimplexNoise(seed);

  const heights: number[][] = [];
  const vertices: Vector3[] = [];
  const normals: Vector3[] = [];

  const scale = roughness / Math.max(width, depth);
  const slopeFactor = slope / Math.max(width, depth);

  for (let ix = 0; ix < resolution; ix++) {
    heights[ix] = [];
    for (let iz = 0; iz < resolution; iz++) {
      const x = (ix / (resolution - 1) - 0.5) * width;
      const z = (iz / (resolution - 1) - 0.5) * depth;

      let height = 0;
      let freq = 1;
      let amp = 1;
      let maxAmp = 0;

      for (let octave = 0; octave < 6; octave++) {
        height += noise.noise2D(x * scale * freq, z * scale * freq) * amp;
        maxAmp += amp;
        amp *= 0.5;
        freq *= 2;
      }

      height = (height / maxAmp + 1) * 0.5;
      height = height * amplitude;

      height += z * slopeFactor + Math.max(0, -z) * slopeFactor * 0.5;

      heights[ix][iz] = height;
      vertices.push(createVector3(x, height, z));
    }
  }

  for (let ix = 0; ix < resolution; ix++) {
    for (let iz = 0; iz < resolution; iz++) {
      const hL = ix > 0 ? heights[ix - 1][iz] : heights[ix][iz];
      const hR = ix < resolution - 1 ? heights[ix + 1][iz] : heights[ix][iz];
      const hD = iz > 0 ? heights[ix][iz - 1] : heights[ix][iz];
      const hU = iz < resolution - 1 ? heights[ix][iz + 1] : heights[ix][iz];

      const dx = (hR - hL) / (2 * width / resolution);
      const dz = (hU - hD) / (2 * depth / resolution);

      const normal = createVector3(-dx, 1, -dz);
      const len = Math.sqrt(normal.x * normal.x + normal.y * normal.y + normal.z * normal.z);
      normal.x /= len;
      normal.y /= len;
      normal.z /= len;

      normals.push(normal);
    }
  }

  return { heights, vertices, normals };
}

export function generateRiverBedTerrain(params: TerrainGenerateParams): {
  heights: number[][];
  vertices: Vector3[];
  normals: Vector3[];
} {
  const { width, depth, resolution, amplitude, seed } = params;
  const noise = new SimplexNoise(seed);

  const heights: number[][] = [];
  const vertices: Vector3[] = [];
  const normals: Vector3[] = [];

  const channelWidth = width * 0.3;
  const channelDepth = amplitude * 0.8;

  for (let ix = 0; ix < resolution; ix++) {
    heights[ix] = [];
    for (let iz = 0; iz < resolution; iz++) {
      const x = (ix / (resolution - 1) - 0.5) * width;
      const z = (iz / (resolution - 1) - 0.5) * depth;

      const distFromCenter = Math.abs(x);
      const channelFactor = Math.exp(-(distFromCenter * distFromCenter) / (channelWidth * channelWidth));
      
      let height = -channelDepth * channelFactor;

      let noiseVal = 0;
      let freq = 0.5;
      let amp = 1;
      let maxAmp = 0;

      for (let octave = 0; octave < 5; octave++) {
        noiseVal += noise.noise2D(x * 0.1 * freq, z * 0.1 * freq) * amp;
        maxAmp += amp;
        amp *= 0.6;
        freq *= 2;
      }

      height += (noiseVal / maxAmp) * amplitude * 0.3;
      height += z * 0.05;

      const bankHeight = (1 - channelFactor) * amplitude * 0.5;
      height += bankHeight;

      heights[ix][iz] = height;
      vertices.push(createVector3(x, height, z));
    }
  }

  for (let ix = 0; ix < resolution; ix++) {
    for (let iz = 0; iz < resolution; iz++) {
      const hL = ix > 0 ? heights[ix - 1][iz] : heights[ix][iz];
      const hR = ix < resolution - 1 ? heights[ix + 1][iz] : heights[ix][iz];
      const hD = iz > 0 ? heights[ix][iz - 1] : heights[ix][iz];
      const hU = iz < resolution - 1 ? heights[ix][iz + 1] : heights[ix][iz];

      const dx = (hR - hL) / (2 * width / resolution);
      const dz = (hU - hD) / (2 * depth / resolution);

      const normal = createVector3(-dx, 1, -dz);
      const len = Math.sqrt(normal.x * normal.x + normal.y * normal.y + normal.z * normal.z);
      normal.x /= len;
      normal.y /= len;
      normal.z /= len;

      normals.push(normal);
    }
  }

  return { heights, vertices, normals };
}

export function getTerrainHeight(heights: number[][], x: number, z: number, width: number, depth: number, resolution: number): number {
  const nx = ((x + width / 2) / width) * (resolution - 1);
  const nz = ((z + depth / 2) / depth) * (resolution - 1);

  const ix = Math.max(0, Math.min(resolution - 2, Math.floor(nx)));
  const iz = Math.max(0, Math.min(resolution - 2, Math.floor(nz)));

  const fx = nx - ix;
  const fz = nz - iz;

  const h00 = heights[ix][iz];
  const h10 = heights[ix + 1][iz];
  const h01 = heights[ix][iz + 1];
  const h11 = heights[ix + 1][iz + 1];

  const h0 = h00 * (1 - fx) + h10 * fx;
  const h1 = h01 * (1 - fx) + h11 * fx;

  return h0 * (1 - fz) + h1 * fz;
}
