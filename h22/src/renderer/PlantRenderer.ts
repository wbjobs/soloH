import { Engine } from '@babylonjs/core/Engines/engine';
import { Scene } from '@babylonjs/core/scene';
import { ArcRotateCamera } from '@babylonjs/core/Cameras/arcRotateCamera';
import { HemisphericLight } from '@babylonjs/core/Lights/hemisphericLight';
import { DirectionalLight } from '@babylonjs/core/Lights/directionalLight';
import { Vector3 } from '@babylonjs/core/Maths/math.vector';
import { Color3, Color4 } from '@babylonjs/core/Maths/math.color';
import { CreateGround } from '@babylonjs/core/Meshes/Builders/groundBuilder';
import { CreateSphere } from '@babylonjs/core/Meshes/Builders/sphereBuilder';
import { StandardMaterial } from '@babylonjs/core/Materials/standardMaterial';
import { Mesh } from '@babylonjs/core/Meshes/mesh';
import { VertexData } from '@babylonjs/core/Meshes/mesh.vertexData';
import type { PlantData, BranchSegment, LeafData, SeasonColors, WindParams, PlantInstance } from '../types';
import { WindSystem } from '../environment/WindSystem';
import { SeasonSystem } from '../environment/SeasonSystem';

interface PlantRenderData {
  plantContainer: Mesh;
  branchMeshes: Mesh[];
  leafMeshes: Mesh[];
  branchOriginalPositions: Float32Array[];
  branchOriginalNormals: Float32Array[];
  leafOriginalPositions: Float32Array[];
  leafOriginalNormals: Float32Array[];
  seedMesh: Mesh | null;
  seasonColors: SeasonColors;
  windResistance: number;
  position: [number, number, number];
  colorModifier: [number, number, number];
}

export class PlantRenderer {
  private engine: Engine;
  private scene: Scene;
  private camera: ArcRotateCamera;
  private ambientLight: HemisphericLight;
  private sunLight: DirectionalLight;
  private ground: Mesh;
  
  private plants: Map<string, PlantRenderData> = new Map();
  
  private windSystem: WindSystem;
  private seasonSystem: SeasonSystem;
  
  private branchMaterial: StandardMaterial;
  private leafMaterial: StandardMaterial;
  private seedMaterial: StandardMaterial;
  private deadMaterial: StandardMaterial;

  constructor(canvas: HTMLCanvasElement) {
    this.engine = new Engine(canvas, true, { preserveDrawingBuffer: true });
    this.scene = new Scene(this.engine);
    this.scene.clearColor = new Color4(0.1, 0.12, 0.15, 1);
    
    this.camera = new ArcRotateCamera(
      'camera',
      -Math.PI / 2,
      Math.PI / 3,
      20,
      Vector3.Zero(),
      this.scene
    );
    this.camera.attachControl(canvas, true);
    this.camera.wheelPrecision = 50;
    this.camera.minZ = 0.1;
    this.camera.upperRadiusLimit = 80;
    this.camera.lowerRadiusLimit = 2;
    
    this.ambientLight = new HemisphericLight(
      'ambientLight',
      new Vector3(0, 1, 0),
      this.scene
    );
    this.ambientLight.intensity = 0.6;
    
    this.sunLight = new DirectionalLight(
      'sunLight',
      new Vector3(-0.3, -1, -0.3),
      this.scene
    );
    this.sunLight.position = new Vector3(10, 20, 10);
    this.sunLight.intensity = 1.2;
    
    this.ground = CreateGround('ground', { width: 60, height: 60 }, this.scene);
    const groundMaterial = new StandardMaterial('groundMaterial', this.scene);
    groundMaterial.diffuseColor = new Color3(0.3, 0.25, 0.2);
    groundMaterial.specularColor = new Color3(0.1, 0.1, 0.1);
    this.ground.material = groundMaterial;
    
    this.branchMaterial = new StandardMaterial('branchMaterial', this.scene);
    this.branchMaterial.diffuseColor = new Color3(0.35, 0.2, 0.1);
    this.branchMaterial.specularColor = new Color3(0.1, 0.1, 0.1);
    
    this.leafMaterial = new StandardMaterial('leafMaterial', this.scene);
    this.leafMaterial.diffuseColor = new Color3(0.2, 0.6, 0.2);
    this.leafMaterial.specularColor = new Color3(0.1, 0.2, 0.1);
    this.leafMaterial.backFaceCulling = false;
    
    this.seedMaterial = new StandardMaterial('seedMaterial', this.scene);
    this.seedMaterial.diffuseColor = new Color3(0.6, 0.4, 0.2);
    this.seedMaterial.specularColor = new Color3(0.2, 0.2, 0.2);
    
    this.deadMaterial = new StandardMaterial('deadMaterial', this.scene);
    this.deadMaterial.diffuseColor = new Color3(0.4, 0.35, 0.3);
    this.deadMaterial.specularColor = new Color3(0.1, 0.1, 0.1);
    
    this.windSystem = new WindSystem();
    this.seasonSystem = new SeasonSystem();
    
    this.setupFog();
  }

  private setupFog(): void {
    this.scene.fogMode = Scene.FOGMODE_EXP;
    this.scene.fogDensity = 0.015;
    const fogColor = this.seasonSystem.getFogColor();
    this.scene.fogColor = new Color3(fogColor[0], fogColor[1], fogColor[2]);
  }

  setWindParams(params: Partial<WindParams>): void {
    this.windSystem.setParams(params);
  }

  getWindDirection(): [number, number, number] {
    const dir = this.sunLight.direction;
    return [dir.x, dir.y, dir.z];
  }

  setLightDirection(direction: [number, number, number]): void {
    const len = Math.sqrt(direction[0] ** 2 + direction[1] ** 2 + direction[2] ** 2);
    if (len > 0) {
      this.sunLight.direction = new Vector3(
        direction[0] / len,
        direction[1] / len,
        direction[2] / len
      );
    }
  }

  setSeasonColors(plantId: string, colors: SeasonColors): void {
    const data = this.plants.get(plantId);
    if (data) {
      data.seasonColors = colors;
    }
  }

  setWindResistance(plantId: string, resistance: number): void {
    const data = this.plants.get(plantId);
    if (data) {
      data.windResistance = resistance;
    }
  }

  setColorModifier(plantId: string, modifier: [number, number, number]): void {
    const data = this.plants.get(plantId);
    if (data) {
      data.colorModifier = modifier;
    }
  }

  setLightIntensity(intensity: number): void {
    this.ambientLight.intensity = 0.3 + intensity * 0.6;
    this.sunLight.intensity = 0.5 + intensity * 1.5;
  }

  getScene(): Scene {
    return this.scene;
  }

  getEngine(): Engine {
    return this.engine;
  }

  getWindSystem(): WindSystem {
    return this.windSystem;
  }

  getSeasonSystem(): SeasonSystem {
    return this.seasonSystem;
  }

  getSunDirection(): Vector3 {
    return this.sunLight.direction;
  }

  clearPlant(plantId: string): void {
    const data = this.plants.get(plantId);
    if (data) {
      data.plantContainer.dispose(false, true);
      this.plants.delete(plantId);
    }
  }

  clearAllPlants(): void {
    this.plants.forEach(data => {
      data.plantContainer.dispose(false, true);
    });
    this.plants.clear();
  }

  hasPlant(plantId: string): boolean {
    return this.plants.has(plantId);
  }

  createSeedVisualization(plant: PlantInstance): void {
    const existing = this.plants.get(plant.id);
    if (existing) {
      this.clearPlant(plant.id);
    }

    const container = new Mesh(`container_${plant.id}`, this.scene);
    container.position.set(plant.position[0], plant.position[1], plant.position[2]);

    const seed = CreateSphere(`seed_${plant.id}`, { diameter: 0.3, segments: 8 }, this.scene);
    seed.parent = container;
    seed.position.y = 0.15;
    seed.material = this.seedMaterial;

    const presetColors = this.getDefaultSeasonColors(plant.presetType);
    this.plants.set(plant.id, {
      plantContainer: container,
      branchMeshes: [],
      leafMeshes: [],
      branchOriginalPositions: [],
      branchOriginalNormals: [],
      leafOriginalPositions: [],
      leafOriginalNormals: [],
      seedMesh: seed,
      seasonColors: presetColors,
      windResistance: 0.5,
      position: plant.position,
      colorModifier: [1, 1, 1]
    });
  }

  createPlantGeometry(plant: PlantInstance, plantData: PlantData): void {
    this.clearPlant(plant.id);
    
    const container = new Mesh(`container_${plant.id}`, this.scene);
    container.position.set(plant.position[0], plant.position[1], plant.position[2]);
    
    const branchMeshes: Mesh[] = [];
    const leafMeshes: Mesh[] = [];
    const branchOriginalPositions: Float32Array[] = [];
    const branchOriginalNormals: Float32Array[] = [];
    const leafOriginalPositions: Float32Array[] = [];
    const leafOriginalNormals: Float32Array[] = [];
    
    if (plantData.branches.length > 0) {
      for (let i = 0; i < plantData.branches.length; i++) {
        const branch = plantData.branches[i];
        const mesh = this.createSingleBranch(branch, i, plant.id);
        if (mesh) {
          mesh.parent = container;
          branchMeshes.push(mesh);
          
          const positions = mesh.getVerticesData('position') as Float32Array;
          const normals = mesh.getVerticesData('normal') as Float32Array;
          branchOriginalPositions.push(new Float32Array(positions));
          branchOriginalNormals.push(new Float32Array(normals));
        }
      }
    }
    
    if (plantData.leaves.length > 0) {
      for (let i = 0; i < plantData.leaves.length; i++) {
        const leaf = plantData.leaves[i];
        const mesh = this.createSingleLeaf(leaf, i, plant.id);
        if (mesh) {
          mesh.parent = container;
          leafMeshes.push(mesh);
          
          const positions = mesh.getVerticesData('position') as Float32Array;
          const normals = mesh.getVerticesData('normal') as Float32Array;
          leafOriginalPositions.push(new Float32Array(positions));
          leafOriginalNormals.push(new Float32Array(normals));
        }
      }
    }

    const presetColors = this.getDefaultSeasonColors(plant.presetType);
    this.plants.set(plant.id, {
      plantContainer: container,
      branchMeshes,
      leafMeshes,
      branchOriginalPositions,
      branchOriginalNormals,
      leafOriginalPositions,
      leafOriginalNormals,
      seedMesh: null,
      seasonColors: presetColors,
      windResistance: 0.5,
      position: plant.position,
      colorModifier: [1, 1, 1]
    });
  }

  updatePlantLifecycle(plant: PlantInstance, colorModifier: [number, number, number]): void {
    const data = this.plants.get(plant.id);
    if (!data) return;

    data.colorModifier = colorModifier;

    if (plant.lifecycleStage === 'seed') {
      data.plantContainer.visibility = plant.growthProgress * 0.5;
    } else if (plant.lifecycleStage === 'dead') {
      data.branchMeshes.forEach(m => m.material = this.deadMaterial);
      data.leafMeshes.forEach(m => m.visibility = 0.1);
    }
  }

  setPlantGrowthProgress(plantId: string, progress: number): void {
    const data = this.plants.get(plantId);
    if (data) {
      data.plantContainer.visibility = Math.max(0.01, progress);
      
      if (data.seedMesh) {
        data.seedMesh.visibility = Math.max(0, 1 - progress * 2);
      }
    }
  }

  private getDefaultSeasonColors(type: string): SeasonColors {
    switch (type) {
      case 'tree':
        return {
          spring: [0.7, 0.9, 0.4],
          summer: [0.2, 0.6, 0.2],
          autumn: [0.9, 0.5, 0.1],
          winter: [0.6, 0.6, 0.5]
        };
      case 'fern':
        return {
          spring: [0.5, 0.8, 0.3],
          summer: [0.1, 0.5, 0.1],
          autumn: [0.7, 0.6, 0.2],
          winter: [0.4, 0.4, 0.3]
        };
      case 'vine':
        return {
          spring: [0.6, 0.85, 0.35],
          summer: [0.15, 0.55, 0.15],
          autumn: [0.8, 0.45, 0.15],
          winter: [0.5, 0.5, 0.4]
        };
      default:
        return {
          spring: [0.7, 0.9, 0.4],
          summer: [0.2, 0.6, 0.2],
          autumn: [0.9, 0.5, 0.1],
          winter: [0.6, 0.6, 0.5]
        };
    }
  }

  private createSingleBranch(branch: BranchSegment, index: number, plantId: string): Mesh | null {
    const start = new Vector3(branch.start[0], branch.start[1], branch.start[2]);
    const end = new Vector3(branch.end[0], branch.end[1], branch.end[2]);
    const direction = end.subtract(start);
    const length = direction.length();
    
    if (length < 0.01) return null;
    
    const mesh = new Mesh(`branch_${plantId}_${index}`, this.scene);
    
    const radialSegments = 6;
    const heightSegments = 1;
    const positions: number[] = [];
    const indices: number[] = [];
    const normals: number[] = [];
    const uvs: number[] = [];
    
    const up = direction.clone().normalize();
    const right = Vector3.Cross(up, Vector3.Up()).normalize();
    if (right.length() < 0.01) {
      right.copyFrom(Vector3.Right());
    }
    const forward = Vector3.Cross(right, up).normalize();
    
    for (let h = 0; h <= heightSegments; h++) {
      const t = h / heightSegments;
      const radius = branch.radius * (1 - t * 0.3);
      const center = start.add(direction.scale(t));
      
      for (let r = 0; r < radialSegments; r++) {
        const angle = (r / radialSegments) * Math.PI * 2;
        const cosA = Math.cos(angle);
        const sinA = Math.sin(angle);
        
        const offset = right.scale(cosA * radius).add(forward.scale(sinA * radius));
        const position = center.add(offset);
        const normal = offset.normalize();
        
        positions.push(position.x, position.y, position.z);
        normals.push(normal.x, normal.y, normal.z);
        uvs.push(r / radialSegments, t);
      }
    }
    
    for (let h = 0; h < heightSegments; h++) {
      for (let r = 0; r < radialSegments; r++) {
        const current = h * radialSegments + r;
        const next = h * radialSegments + ((r + 1) % radialSegments);
        const currentUp = (h + 1) * radialSegments + r;
        const nextUp = (h + 1) * radialSegments + ((r + 1) % radialSegments);
        
        indices.push(current, next, currentUp);
        indices.push(next, nextUp, currentUp);
      }
    }
    
    const vertexData = new VertexData();
    vertexData.positions = positions;
    vertexData.indices = indices;
    vertexData.normals = normals;
    vertexData.uvs = uvs;
    
    vertexData.applyToMesh(mesh);
    mesh.material = this.branchMaterial;
    mesh.metadata = { plantId, branchIndex: index, depth: branch.depth, originalStart: start, originalEnd: end };
    
    return mesh;
  }

  private createSingleLeaf(leaf: LeafData, index: number, plantId: string): Mesh | null {
    const mesh = new Mesh(`leaf_${plantId}_${index}`, this.scene);
    
    const widthSegments = 3;
    const heightSegments = 4;
    const positions: number[] = [];
    const indices: number[] = [];
    const normals: number[] = [];
    const uvs: number[] = [];
    
    const dir = new Vector3(leaf.direction[0], leaf.direction[1], leaf.direction[2]).normalize();
    const right = Vector3.Cross(dir, Vector3.Up()).normalize();
    if (right.length() < 0.01) right.copyFrom(Vector3.Right());
    const up = Vector3.Cross(right, dir).normalize();
    
    const size = leaf.size;
    const pos = new Vector3(leaf.position[0], leaf.position[1], leaf.position[2]);
    
    const rotation = leaf.rotation;
    const rotatedRight = right.scale(Math.cos(rotation)).add(up.scale(Math.sin(rotation)));
    const rotatedUp = up.scale(Math.cos(rotation)).subtract(right.scale(Math.sin(rotation)));
    
    for (let h = 0; h <= heightSegments; h++) {
      const t = h / heightSegments;
      const widthFactor = Math.sin(t * Math.PI) * 0.6 + 0.2;
      const heightOffset = dir.scale(t * size);
      
      for (let w = 0; w <= widthSegments; w++) {
        const u = w / widthSegments - 0.5;
        const widthOffset = rotatedRight.scale(u * size * widthFactor);
        const upOffset = rotatedUp.scale(Math.sin(t * Math.PI) * 0.1 * size);
        
        const position = pos.add(heightOffset).add(widthOffset).add(upOffset);
        const normal = rotatedUp.clone();
        
        positions.push(position.x, position.y, position.z);
        normals.push(normal.x, normal.y, normal.z);
        uvs.push(w / widthSegments, t);
      }
    }
    
    for (let h = 0; h < heightSegments; h++) {
      for (let w = 0; w < widthSegments; w++) {
        const current = h * (widthSegments + 1) + w;
        const next = current + 1;
        const currentUp = current + widthSegments + 1;
        const nextUp = currentUp + 1;
        
        indices.push(current, currentUp, next);
        indices.push(next, currentUp, nextUp);
      }
    }
    
    const vertexData = new VertexData();
    vertexData.positions = positions;
    vertexData.indices = indices;
    vertexData.normals = normals;
    vertexData.uvs = uvs;
    
    vertexData.applyToMesh(mesh);
    mesh.material = this.leafMaterial;
    mesh.metadata = { plantId, leafIndex: index, depth: leaf.depth, originalPos: pos, rotation: leaf.rotation };
    
    return mesh;
  }

  frameCameraToPlants(): void {
    if (this.plants.size === 0) {
      this.camera.target = Vector3.Zero();
      this.camera.radius = 20;
      return;
    }

    const min = new Vector3(Infinity, Infinity, Infinity);
    const max = new Vector3(-Infinity, -Infinity, -Infinity);

    this.plants.forEach(data => {
      const boundingInfo = data.plantContainer.getBoundingInfo();
      min.minimizeInPlace(boundingInfo.minimum);
      max.maximizeInPlace(boundingInfo.maximum);
    });

    const center = min.add(max).scale(0.5);
    const height = max.y - min.y;
    const radius = Math.max(max.x - min.x, max.z - min.z);
    const fitRadius = Math.max(height, radius) * 1.5;

    this.camera.radius = Math.max(this.camera.radius, fitRadius);
    this.camera.target = center;
  }

  private rotateVectorByBending(
    v: [number, number, number],
    originalDir: Vector3,
    bentDir: Vector3
  ): [number, number, number] {
    const vVec = new Vector3(v[0], v[1], v[2]);
    
    const axis = Vector3.Cross(originalDir, bentDir);
    const axisLength = axis.length();
    
    if (axisLength < 0.0001) {
      return v;
    }
    
    axis.normalize();
    const cosAngle = Vector3.Dot(originalDir, bentDir);
    const angle = Math.acos(Math.max(-1, Math.min(1, cosAngle)));
    
    const sinAngle = Math.sin(angle);
    const cosVal = Math.cos(angle);
    const oneMinusCos = 1 - cosVal;
    
    const [ax, ay, az] = [axis.x, axis.y, axis.z];
    const [vx, vy, vz] = [vVec.x, vVec.y, vVec.z];
    
    const m00 = cosVal + ax * ax * oneMinusCos;
    const m01 = ax * ay * oneMinusCos - az * sinAngle;
    const m02 = ax * az * oneMinusCos + ay * sinAngle;
    
    const m10 = ay * ax * oneMinusCos + az * sinAngle;
    const m11 = cosVal + ay * ay * oneMinusCos;
    const m12 = ay * az * oneMinusCos - ax * sinAngle;
    
    const m20 = az * ax * oneMinusCos - ay * sinAngle;
    const m21 = az * ay * oneMinusCos + ax * sinAngle;
    const m22 = cosVal + az * az * oneMinusCos;
    
    return [
      m00 * vx + m01 * vy + m02 * vz,
      m10 * vx + m11 * vy + m12 * vz,
      m20 * vx + m21 * vy + m22 * vz
    ];
  }

  private normalizeVector(v: [number, number, number]): [number, number, number] {
    const len = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    if (len < 0.0001) return [0, 1, 0];
    return [v[0] / len, v[1] / len, v[2] / len];
  }

  private rotateVectorAroundAxis(
    v: [number, number, number],
    axis: [number, number, number],
    angle: number
  ): [number, number, number] {
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    const oneMinusCos = 1 - cos;
    
    const [ax, ay, az] = this.normalizeVector(axis);
    const [vx, vy, vz] = v;
    
    const m00 = cos + ax * ax * oneMinusCos;
    const m01 = ax * ay * oneMinusCos - az * sin;
    const m02 = ax * az * oneMinusCos + ay * sin;
    
    const m10 = ay * ax * oneMinusCos + az * sin;
    const m11 = cos + ay * ay * oneMinusCos;
    const m12 = ay * az * oneMinusCos - ax * sin;
    
    const m20 = az * ax * oneMinusCos - ay * sin;
    const m21 = az * ay * oneMinusCos + ax * sin;
    const m22 = cos + az * az * oneMinusCos;
    
    return [
      m00 * vx + m01 * vy + m02 * vz,
      m10 * vx + m11 * vy + m12 * vz,
      m20 * vx + m21 * vy + m22 * vz
    ];
  }

  update(deltaTime: number): void {
    this.windSystem.update(deltaTime);
    this.seasonSystem.update(deltaTime);
    
    this.plants.forEach(data => {
      this.updatePlantWind(data);
      this.updatePlantLeafColor(data);
    });
    
    this.updateFog();
    
    this.scene.render();
  }

  private updatePlantWind(data: PlantRenderData): void {
    for (let i = 0; i < data.branchMeshes.length; i++) {
      const mesh = data.branchMeshes[i];
      const originalPos = data.branchOriginalPositions[i];
      const originalNorm = data.branchOriginalNormals[i];
      const metadata = mesh.metadata;
      
      if (!originalPos || !originalNorm || !metadata) continue;
      
      const start = metadata.originalStart as Vector3;
      const end = metadata.originalEnd as Vector3;
      const depth = metadata.depth as number;
      
      const bending = this.windSystem.getBranchBending(
        [start.x, start.y, start.z],
        [end.x, end.y, end.z],
        depth,
        data.windResistance
      );
      
      const originalDir = end.subtract(start).normalize();
      
      const positions = new Float32Array(originalPos.length);
      const normals = new Float32Array(originalNorm.length);
      const radialSegments = 6;
      const heightSegments = 1;
      
      for (let h = 0; h <= heightSegments; h++) {
        const t = h / heightSegments;
        const bendFactor = t * t;
        
        const partialBending: [number, number, number] = [
          bending[0] * bendFactor,
          bending[1] * bendFactor,
          bending[2] * bendFactor
        ];
        
        const partialBentDir = originalDir.add(new Vector3(partialBending[0], partialBending[1], partialBending[2])).normalize();
        
        for (let r = 0; r < radialSegments; r++) {
          const idx = (h * radialSegments + r) * 3;
          
          positions[idx] = originalPos[idx] + partialBending[0];
          positions[idx + 1] = originalPos[idx + 1] + partialBending[1];
          positions[idx + 2] = originalPos[idx + 2] + partialBending[2];
          
          const origNormal: [number, number, number] = [
            originalNorm[idx],
            originalNorm[idx + 1],
            originalNorm[idx + 2]
          ];
          
          const rotatedNormal = this.rotateVectorByBending(origNormal, originalDir, partialBentDir);
          const normalizedNormal = this.normalizeVector(rotatedNormal);
          
          normals[idx] = normalizedNormal[0];
          normals[idx + 1] = normalizedNormal[1];
          normals[idx + 2] = normalizedNormal[2];
        }
      }
      
      mesh.updateVerticesData('position', positions);
      mesh.updateVerticesData('normal', normals);
    }
  }

  private updatePlantLeafColor(data: PlantRenderData): void {
    const leafColor = this.seasonSystem.getCurrentColor(data.seasonColors);
    
    const finalColor: [number, number, number] = [
      leafColor[0] * data.colorModifier[0],
      leafColor[1] * data.colorModifier[1],
      leafColor[2] * data.colorModifier[2]
    ];
    
    this.leafMaterial.diffuseColor = new Color3(finalColor[0], finalColor[1], finalColor[2]);
    
    const foliageDensity = this.seasonSystem.getFoliageDensity();
    
    for (let i = 0; i < data.leafMeshes.length; i++) {
      const mesh = data.leafMeshes[i];
      const originalPos = data.leafOriginalPositions[i];
      const originalNorm = data.leafOriginalNormals[i];
      const metadata = mesh.metadata;
      
      if (!originalPos || !originalNorm || !metadata) continue;
      
      const pos = metadata.originalPos as Vector3;
      const rotation = metadata.rotation as number;
      
      const sway = this.windSystem.getLeafSway(
        [pos.x, pos.y, pos.z],
        rotation,
        this.windSystem['time']
      );
      
      mesh.visibility = data.plantContainer.visibility * foliageDensity;
      
      const positions = new Float32Array(originalPos.length);
      const normals = new Float32Array(originalNorm.length);
      
      const swayDir: [number, number, number] = [
        sway.positionOffset[0],
        sway.positionOffset[1],
        sway.positionOffset[2]
      ];
      
      const swayLen = Math.sqrt(swayDir[0] * swayDir[0] + swayDir[1] * swayDir[1] + swayDir[2] * swayDir[2]);
      const tiltAngle = swayLen > 0 ? Math.min(swayLen * 0.5, Math.PI * 0.25) : 0;
      const tiltAxis: [number, number, number] = swayLen > 0 ? 
        this.normalizeVector([-swayDir[2], 0, swayDir[0]]) : 
        [1, 0, 0];
      
      const rotationAngle = sway.rotationOffset;
      
      for (let j = 0; j < originalPos.length; j += 3) {
        positions[j] = originalPos[j] + swayDir[0];
        positions[j + 1] = originalPos[j + 1] + swayDir[1];
        positions[j + 2] = originalPos[j + 2] + swayDir[2];
        
        let normal: [number, number, number] = [
          originalNorm[j],
          originalNorm[j + 1],
          originalNorm[j + 2]
        ];
        
        if (tiltAngle > 0.001) {
          normal = this.rotateVectorAroundAxis(normal, tiltAxis, tiltAngle);
        }
        
        if (Math.abs(rotationAngle) > 0.001) {
          const leafNormal: [number, number, number] = [
            originalNorm[j],
            originalNorm[j + 1],
            originalNorm[j + 2]
          ];
          normal = this.rotateVectorAroundAxis(normal, leafNormal, rotationAngle);
        }
        
        normal = this.normalizeVector(normal);
        
        normals[j] = normal[0];
        normals[j + 1] = normal[1];
        normals[j + 2] = normal[2];
      }
      
      mesh.updateVerticesData('position', positions);
      mesh.updateVerticesData('normal', normals);
    }
  }

  private updateFog(): void {
    const fogColor = this.seasonSystem.getFogColor();
    this.scene.fogColor = new Color3(fogColor[0], fogColor[1], fogColor[2]);
    
    const ambientColor = this.seasonSystem.getAmbientColor();
    this.scene.ambientColor = new Color3(ambientColor[0] * 0.3, ambientColor[1] * 0.3, ambientColor[2] * 0.3);
  }

  resize(): void {
    this.engine.resize();
  }

  dispose(): void {
    this.engine.dispose();
  }
}
