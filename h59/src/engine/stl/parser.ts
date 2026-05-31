import type { STLData } from '../../types';

export const parseSTL = (file: File): Promise<STLData> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      try {
        const buffer = e.target?.result as ArrayBuffer;
        if (!buffer) {
          reject(new Error('Failed to read file'));
          return;
        }

        if (isBinarySTL(buffer)) {
          resolve(parseBinarySTL(buffer));
        } else {
          const text = new TextDecoder().decode(buffer);
          resolve(parseASCIISTL(text));
        }
      } catch (error) {
        reject(error);
      }
    };

    reader.onerror = () => reject(new Error('File read error'));
    reader.readAsArrayBuffer(file);
  });
};

const isBinarySTL = (buffer: ArrayBuffer): boolean => {
  const uint8 = new Uint8Array(buffer);
  const header = new TextDecoder('ascii').decode(uint8.slice(0, 80));
  return !header.trim().toLowerCase().startsWith('solid');
};

const parseBinarySTL = (buffer: ArrayBuffer): STLData => {
  const uint8 = new Uint8Array(buffer);
  const dataView = new DataView(buffer);

  const numTriangles = dataView.getUint32(80, true);
  const vertices = new Float32Array(numTriangles * 9);
  const normals = new Float32Array(numTriangles * 3);
  const faces = new Uint32Array(numTriangles * 3);

  let offset = 84;

  for (let i = 0; i < numTriangles; i++) {
    const ni = i * 3;
    normals[ni] = dataView.getFloat32(offset, true);
    normals[ni + 1] = dataView.getFloat32(offset + 4, true);
    normals[ni + 2] = dataView.getFloat32(offset + 8, true);
    offset += 12;

    const vi = i * 9;
    for (let j = 0; j < 3; j++) {
      vertices[vi + j * 3] = dataView.getFloat32(offset, true);
      vertices[vi + j * 3 + 1] = dataView.getFloat32(offset + 4, true);
      vertices[vi + j * 3 + 2] = dataView.getFloat32(offset + 8, true);
      offset += 12;
    }

    faces[i * 3] = i * 3;
    faces[i * 3 + 1] = i * 3 + 1;
    faces[i * 3 + 2] = i * 3 + 2;

    offset += 2;
  }

  return { vertices, normals, faces };
};

const parseASCIISTL = (text: string): STLData => {
  const lines = text.trim().split('\n');
  const triangles: {
    normal: number[];
    vertices: number[][];
  }[] = [];

  let currentTriangle: {
    normal: number[];
    vertices: number[][];
  } | null = null;
  let vertexCount = 0;

  for (const line of lines) {
    const trimmed = line.trim();
    const parts = trimmed.split(/\s+/);

    if (parts[0] === 'facet' && parts[1] === 'normal') {
      currentTriangle = {
        normal: [parseFloat(parts[2]), parseFloat(parts[3]), parseFloat(parts[4])],
        vertices: [],
      };
      vertexCount = 0;
    } else if (parts[0] === 'vertex' && currentTriangle) {
      currentTriangle.vertices.push([
        parseFloat(parts[1]),
        parseFloat(parts[2]),
        parseFloat(parts[3]),
      ]);
      vertexCount++;
    } else if (parts[0] === 'endfacet' && currentTriangle && vertexCount === 3) {
      triangles.push(currentTriangle);
      currentTriangle = null;
    }
  }

  const numTriangles = triangles.length;
  const vertices = new Float32Array(numTriangles * 9);
  const normals = new Float32Array(numTriangles * 3);
  const faces = new Uint32Array(numTriangles * 3);

  for (let i = 0; i < numTriangles; i++) {
    const tri = triangles[i];

    const ni = i * 3;
    normals[ni] = tri.normal[0];
    normals[ni + 1] = tri.normal[1];
    normals[ni + 2] = tri.normal[2];

    const vi = i * 9;
    for (let j = 0; j < 3; j++) {
      vertices[vi + j * 3] = tri.vertices[j][0];
      vertices[vi + j * 3 + 1] = tri.vertices[j][1];
      vertices[vi + j * 3 + 2] = tri.vertices[j][2];
    }

    faces[i * 3] = i * 3;
    faces[i * 3 + 1] = i * 3 + 1;
    faces[i * 3 + 2] = i * 3 + 2;
  }

  return { vertices, normals, faces };
};

export const simplifySTL = (data: STLData, maxTriangles: number = 10000): STLData => {
  const numTriangles = data.faces.length / 3;
  if (numTriangles <= maxTriangles) return data;

  const ratio = maxTriangles / numTriangles;
  const keepEvery = Math.floor(1 / ratio);

  const newNumTriangles = Math.floor(numTriangles / keepEvery);
  const vertices = new Float32Array(newNumTriangles * 9);
  const normals = new Float32Array(newNumTriangles * 3);
  const faces = new Uint32Array(newNumTriangles * 3);

  let newIdx = 0;
  for (let i = 0; i < numTriangles; i += keepEvery) {
    if (newIdx >= newNumTriangles) break;

    const srcVi = i * 9;
    const dstVi = newIdx * 9;
    vertices.set(data.vertices.slice(srcVi, srcVi + 9), dstVi);

    const srcNi = i * 3;
    const dstNi = newIdx * 3;
    normals.set(data.normals.slice(srcNi, srcNi + 3), dstNi);

    const dstFi = newIdx * 3;
    faces[dstFi] = newIdx * 3;
    faces[dstFi + 1] = newIdx * 3 + 1;
    faces[dstFi + 2] = newIdx * 3 + 2;

    newIdx++;
  }

  return {
    vertices: vertices.slice(0, newIdx * 9),
    normals: normals.slice(0, newIdx * 3),
    faces: faces.slice(0, newIdx * 3),
  };
};

export const getSTLBoundingBox = (data: STLData) => {
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;

  for (let i = 0; i < data.vertices.length; i += 3) {
    minX = Math.min(minX, data.vertices[i]);
    minY = Math.min(minY, data.vertices[i + 1]);
    minZ = Math.min(minZ, data.vertices[i + 2]);
    maxX = Math.max(maxX, data.vertices[i]);
    maxY = Math.max(maxY, data.vertices[i + 1]);
    maxZ = Math.max(maxZ, data.vertices[i + 2]);
  }

  return {
    min: { x: minX, y: minY, z: minZ },
    max: { x: maxX, y: maxY, z: maxZ },
    center: {
      x: (minX + maxX) / 2,
      y: (minY + maxY) / 2,
      z: (minZ + maxZ) / 2,
    },
    size: {
      x: maxX - minX,
      y: maxY - minY,
      z: maxZ - minZ,
    },
  };
};
