import { Vector3, createVector3 } from '../types/physics';

export interface DEMData {
  width: number;
  height: number;
  resolution: number;
  heights: number[][];
  minElevation: number;
  maxElevation: number;
  geotransform?: number[];
  projection?: string;
}

export async function loadDEMFromFile(file: File): Promise<DEMData> {
  const extension = file.name.split('.').pop()?.toLowerCase();

  if (extension === 'asc' || extension === 'txt') {
    return loadASCIIGrid(file);
  } else if (extension === 'tif' || extension === 'tiff') {
    throw new Error('TIFF DEM loading not implemented. Please convert to ASCII Grid format.');
  } else {
    throw new Error(`Unsupported DEM format: ${extension}`);
  }
}

async function loadASCIIGrid(file: File): Promise<DEMData> {
  const text = await file.text();
  const lines = text.split('\n').filter(line => line.trim() !== '');

  let ncols = 0;
  let nrows = 0;
  let xllcorner = 0;
  let yllcorner = 0;
  let cellsize = 1;
  let nodata_value = -9999;
  let dataStartIndex = 0;

  for (let i = 0; i < Math.min(lines.length, 10); i++) {
    const line = lines[i].trim().toLowerCase();
    
    if (line.startsWith('ncols')) {
      ncols = parseInt(line.split(/\s+/)[1]);
    } else if (line.startsWith('nrows')) {
      nrows = parseInt(line.split(/\s+/)[1]);
    } else if (line.startsWith('xllcorner')) {
      xllcorner = parseFloat(line.split(/\s+/)[1]);
    } else if (line.startsWith('yllcorner')) {
      yllcorner = parseFloat(line.split(/\s+/)[1]);
    } else if (line.startsWith('cellsize')) {
      cellsize = parseFloat(line.split(/\s+/)[1]);
    } else if (line.startsWith('nodata_value')) {
      nodata_value = parseFloat(line.split(/\s+/)[1]);
    } else if (line.startsWith('xllcenter') || line.startsWith('yllcenter')) {
    } else if (!isNaN(parseFloat(line.split(/\s+/)[0]))) {
      dataStartIndex = i;
      break;
    }
  }

  const heights: number[][] = [];
  let minElevation = Infinity;
  let maxElevation = -Infinity;

  for (let i = dataStartIndex; i < lines.length; i++) {
    const values = lines[i].trim().split(/\s+/).map(v => parseFloat(v));
    
    if (values.length === ncols) {
      const row: number[] = [];
      for (const val of values) {
        const h = val === nodata_value ? 0 : val;
        row.push(h);
        if (h !== 0) {
          minElevation = Math.min(minElevation, h);
          maxElevation = Math.max(maxElevation, h);
        }
      }
      heights.push(row);
    }
  }

  if (heights.length !== nrows) {
    console.warn(`Expected ${nrows} rows, got ${heights.length}`);
  }

  return {
    width: ncols * cellsize,
    height: nrows * cellsize,
    resolution: ncols,
    heights,
    minElevation,
    maxElevation,
    geotransform: [xllcorner, cellsize, 0, yllcorner + nrows * cellsize, 0, -cellsize]
  };
}

export function normalizeDEMHeights(demData: DEMData, targetMin: number = 0, targetMax: number = 10): number[][] {
  const { heights, minElevation, maxElevation } = demData;
  const range = maxElevation - minElevation;
  
  if (range === 0) {
    return heights.map(row => row.map(() => (targetMin + targetMax) / 2));
  }

  return heights.map(row => 
    row.map(h => {
      if (h === minElevation && h === 0) return targetMin;
      const normalized = (h - minElevation) / range;
      return targetMin + normalized * (targetMax - targetMin);
    })
  );
}

export function resampleDEM(
  heights: number[][],
  originalResolution: number,
  targetResolution: number
): number[][] {
  if (originalResolution === targetResolution) {
    return heights;
  }

  const newHeights: number[][] = [];
  const scale = originalResolution / targetResolution;

  for (let i = 0; i < targetResolution; i++) {
    newHeights[i] = [];
    for (let j = 0; j < targetResolution; j++) {
      const origI = Math.floor(i * scale);
      const origJ = Math.floor(j * scale);
      const fi = i * scale - origI;
      const fj = j * scale - origJ;

      const i0 = Math.max(0, Math.min(originalResolution - 1, origI));
      const i1 = Math.max(0, Math.min(originalResolution - 1, origI + 1));
      const j0 = Math.max(0, Math.min(originalResolution - 1, origJ));
      const j1 = Math.max(0, Math.min(originalResolution - 1, origJ + 1));

      const h00 = heights[i0][j0];
      const h10 = heights[i1][j0];
      const h01 = heights[i0][j1];
      const h11 = heights[i1][j1];

      const h0 = h00 * (1 - fi) + h10 * fi;
      const h1 = h01 * (1 - fi) + h11 * fi;
      newHeights[i][j] = h0 * (1 - fj) + h1 * fj;
    }
  }

  return newHeights;
}

export function generateDEMVertices(
  heights: number[][],
  width: number,
  depth: number,
  offsetY: number = 0
): { vertices: Vector3[]; normals: Vector3[] } {
  const resolution = heights.length;
  const vertices: Vector3[] = [];
  const normals: Vector3[] = [];

  for (let ix = 0; ix < resolution; ix++) {
    for (let iz = 0; iz < resolution; iz++) {
      const x = (ix / (resolution - 1) - 0.5) * width;
      const z = (iz / (resolution - 1) - 0.5) * depth;
      const y = heights[ix][iz] + offsetY;

      vertices.push(createVector3(x, y, z));

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

  return { vertices, normals };
}

export function generateSampleDEM(resolution: number = 64): DEMData {
  const heights: number[][] = [];
  let minElevation = Infinity;
  let maxElevation = -Infinity;

  for (let i = 0; i < resolution; i++) {
    heights[i] = [];
    for (let j = 0; j < resolution; j++) {
      const nx = (i / resolution - 0.5) * 4;
      const nz = (j / resolution - 0.5) * 4;
      
      let h = 0;
      h += Math.sin(nx * 1.5) * Math.cos(nz * 1.5) * 2;
      h += Math.sin(nx * 0.8 + 1) * Math.cos(nz * 0.6 + 0.5) * 3;
      h += nz * 0.5;
      h += 2;

      minElevation = Math.min(minElevation, h);
      maxElevation = Math.max(maxElevation, h);
      heights[i][j] = h;
    }
  }

  return {
    width: 80,
    height: 80,
    resolution,
    heights,
    minElevation,
    maxElevation
  };
}
