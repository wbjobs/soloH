import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';

export interface LoadedModel {
  mesh: THREE.Mesh;
  boundingBox: THREE.Box3;
  center: THREE.Vector3;
  size: THREE.Vector3;
}

export async function loadOBJModel(
  url: string,
  scale: THREE.Vector3 = new THREE.Vector3(1, 1, 1),
  position: THREE.Vector3 = new THREE.Vector3(0, 0, 0),
  rotation: THREE.Euler = new THREE.Euler(0, 0, 0)
): Promise<LoadedModel> {
  const loader = new OBJLoader();

  return new Promise((resolve, reject) => {
    loader.load(
      url,
      (object) => {
        let mesh: THREE.Mesh | null = null;

        object.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            if (!mesh) {
              mesh = child;
            } else {
              const geometries: THREE.BufferGeometry[] = [];
              geometries.push(mesh.geometry);
              geometries.push(child.geometry);
              
              const mergedGeometry = mergeGeometries(geometries);
              mesh = new THREE.Mesh(
                mergedGeometry,
                new THREE.MeshStandardMaterial({
                  color: 0x8b4513,
                  metalness: 0.3,
                  roughness: 0.7
                })
              );
            }
          }
        });

        if (!mesh) {
          reject(new Error('No mesh found in OBJ file'));
          return;
        }

        mesh.scale.copy(scale);
        mesh.position.copy(position);
        mesh.rotation.copy(rotation);
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        if (!mesh.geometry.attributes.position) {
          mesh.geometry.computeVertexNormals();
        }

        const boundingBox = new THREE.Box3().setFromObject(mesh);
        const center = new THREE.Vector3();
        const size = new THREE.Vector3();
        boundingBox.getCenter(center);
        boundingBox.getSize(size);

        resolve({ mesh, boundingBox, center, size });
      },
      (xhr) => {
        console.log(`Loading OBJ: ${(xhr.loaded / xhr.total * 100).toFixed(2)}%`);
      },
      (error) => {
        reject(error);
      }
    );
  });
}

export async function loadOBJFromFile(
  file: File,
  scale: THREE.Vector3 = new THREE.Vector3(1, 1, 1),
  position: THREE.Vector3 = new THREE.Vector3(0, 0, 0),
  rotation: THREE.Euler = new THREE.Euler(0, 0, 0)
): Promise<LoadedModel> {
  const url = URL.createObjectURL(file);
  try {
    const result = await loadOBJModel(url, scale, position, rotation);
    URL.revokeObjectURL(url);
    return result;
  } catch (error) {
    URL.revokeObjectURL(url);
    throw error;
  }
}

export function createDefaultBridgePillar(
  position: THREE.Vector3 = new THREE.Vector3(0, 0, 0),
  scale: THREE.Vector3 = new THREE.Vector3(1, 1, 1)
): LoadedModel {
  const geometry = new THREE.CylinderGeometry(1.5, 2, 12, 16);
  const material = new THREE.MeshStandardMaterial({
    color: 0x696969,
    metalness: 0.2,
    roughness: 0.8
  });
  
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.copy(position);
  mesh.scale.copy(scale);
  mesh.castShadow = true;
  mesh.receiveShadow = true;

  const boundingBox = new THREE.Box3().setFromObject(mesh);
  const center = new THREE.Vector3();
  const size = new THREE.Vector3();
  boundingBox.getCenter(center);
  boundingBox.getSize(size);

  return { mesh, boundingBox, center, size };
}

export function createBridgeWithPillars(
  position: THREE.Vector3 = new THREE.Vector3(0, 5, 10),
  scale: THREE.Vector3 = new THREE.Vector3(1, 1, 1)
): { group: THREE.Group; mesh: THREE.Mesh } {
  const group = new THREE.Group();

  const deckGeometry = new THREE.BoxGeometry(20, 0.8, 4);
  const deckMaterial = new THREE.MeshStandardMaterial({
    color: 0x4a4a4a,
    metalness: 0.3,
    roughness: 0.7
  });
  const deck = new THREE.Mesh(deckGeometry, deckMaterial);
  deck.position.set(0, 6, 0);
  deck.castShadow = true;
  deck.receiveShadow = true;
  group.add(deck);

  const pillarGeometry = new THREE.CylinderGeometry(1, 1.2, 6, 12);
  const pillarMaterial = new THREE.MeshStandardMaterial({
    color: 0x696969,
    metalness: 0.2,
    roughness: 0.8
  });

  const pillar1 = new THREE.Mesh(pillarGeometry, pillarMaterial);
  pillar1.position.set(-7, 3, 0);
  pillar1.castShadow = true;
  pillar1.receiveShadow = true;
  group.add(pillar1);

  const pillar2 = new THREE.Mesh(pillarGeometry, pillarMaterial);
  pillar2.position.set(7, 3, 0);
  pillar2.castShadow = true;
  pillar2.receiveShadow = true;
  group.add(pillar2);

  const pillar3 = new THREE.Mesh(pillarGeometry, pillarMaterial);
  pillar3.position.set(0, 3, 0);
  pillar3.castShadow = true;
  pillar3.receiveShadow = true;
  group.add(pillar3);

  group.position.copy(position);
  group.scale.copy(scale);

  const mergedGeometry = mergeMeshes(group.children as THREE.Mesh[]);
  const mergedMesh = new THREE.Mesh(mergedGeometry, pillarMaterial);
  mergedMesh.position.copy(position);
  mergedMesh.scale.copy(scale);

  return { group, mesh: mergedMesh };
}

function mergeGeometries(geometries: THREE.BufferGeometry[]): THREE.BufferGeometry {
  if (geometries.length === 0) {
    return new THREE.BufferGeometry();
  }

  const mergedGeometry = new THREE.BufferGeometry();
  const positions: number[] = [];
  const normals: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];

  let indexOffset = 0;

  for (const geometry of geometries) {
    const posAttr = geometry.getAttribute('position');
    const normAttr = geometry.getAttribute('normal');
    const uvAttr = geometry.getAttribute('uv');
    const indexAttr = geometry.getIndex();

    if (!posAttr) continue;

    for (let i = 0; i < posAttr.count; i++) {
      positions.push(posAttr.getX(i), posAttr.getY(i), posAttr.getZ(i));
      if (normAttr) {
        normals.push(normAttr.getX(i), normAttr.getY(i), normAttr.getZ(i));
      }
      if (uvAttr) {
        uvs.push(uvAttr.getX(i), uvAttr.getY(i));
      }
    }

    if (indexAttr) {
      for (let i = 0; i < indexAttr.count; i++) {
        indices.push(indexAttr.getX(i) + indexOffset);
      }
    } else {
      for (let i = 0; i < posAttr.count; i++) {
        indices.push(i + indexOffset);
      }
    }

    indexOffset += posAttr.count;
  }

  mergedGeometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  if (normals.length > 0) {
    mergedGeometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  }
  if (uvs.length > 0) {
    mergedGeometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  }
  mergedGeometry.setIndex(indices);

  return mergedGeometry;
}

function mergeMeshes(meshes: THREE.Mesh[]): THREE.BufferGeometry {
  const geometries: THREE.BufferGeometry[] = [];
  
  for (const mesh of meshes) {
    const clonedGeometry = mesh.geometry.clone();
    clonedGeometry.applyMatrix4(mesh.matrix);
    geometries.push(clonedGeometry);
  }

  return mergeGeometries(geometries);
}

export function getMeshInfo(mesh: THREE.Mesh): {
  vertexCount: number;
  triangleCount: number;
  boundingBox: THREE.Box3;
} {
  const vertexCount = mesh.geometry.attributes.position?.count || 0;
  const index = mesh.geometry.getIndex();
  const triangleCount = index ? index.count / 3 : vertexCount / 3;
  const boundingBox = new THREE.Box3().setFromObject(mesh);

  return { vertexCount, triangleCount, boundingBox };
}
