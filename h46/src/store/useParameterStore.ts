import { create } from 'zustand';
import { SPHParameters, TerrainParams, BridgeParams, createVector3 } from '../types/physics';

interface ParameterState {
  sphParams: SPHParameters;
  terrainParams: TerrainParams;
  bridgeParams: BridgeParams;
  terrainHeights: number[][] | null;
  bridgeMesh: THREE.Mesh | null;
  isTerrainGenerated: boolean;
  isBridgeLoaded: boolean;
  updateSPHParams: (params: Partial<SPHParameters>) => void;
  updateTerrainParams: (params: Partial<TerrainParams>) => void;
  updateBridgeParams: (params: Partial<BridgeParams>) => void;
  setTerrainHeights: (heights: number[][]) => void;
  setBridgeMesh: (mesh: THREE.Mesh | null) => void;
  setTerrainGenerated: (generated: boolean) => void;
  setBridgeLoaded: (loaded: boolean) => void;
  resetToDefaults: () => void;
}

const defaultSPHParams: SPHParameters = {
  density0: 2000,
  viscosity: 0.5,
  yieldStress: 150,
  smoothingLength: 0.6,
  particleRadius: 0.25,
  particleMass: 0.15,
  gravity: createVector3(0, -9.81, 0),
  stiffness: 2000,
  timeStep: 0.005,
  maxParticles: 2000,
  cflCoefficient: 0.3,
  vegetation: {
    enabled: false,
    density: 50,
    stemDiameter: 0.1,
    stemHeight: 2,
    dragCoefficient: 1.2,
    bendingStiffness: 1000,
    vegetationZone: {
      startZ: -30,
      endZ: 20,
      startX: -30,
      endX: 30
    }
  },
  grainSize: {
    fineFraction: 0.6,
    coarseFraction: 0.4,
    fineRadius: 0.15,
    coarseRadius: 0.4,
    fineDensity: 1800,
    coarseDensity: 2600,
    segregationVelocity: 0.3,
    turbulentDiffusion: 0.01
  }
};

const defaultTerrainParams: TerrainParams = {
  width: 80,
  depth: 100,
  resolution: 128,
  amplitude: 8,
  roughness: 30,
  slope: 15,
  seed: 12345
};

const defaultBridgeParams: BridgeParams = {
  position: createVector3(0, 5, 10),
  scale: createVector3(1, 1, 1),
  rotation: createVector3(0, 0, 0),
  modelPath: null
};

export const useParameterStore = create<ParameterState>((set, get) => ({
  sphParams: defaultSPHParams,
  terrainParams: defaultTerrainParams,
  bridgeParams: defaultBridgeParams,
  terrainHeights: null,
  bridgeMesh: null,
  isTerrainGenerated: false,
  isBridgeLoaded: false,

  updateSPHParams: (params: Partial<SPHParameters>) => {
    set(state => ({
      sphParams: { ...state.sphParams, ...params }
    }));
  },

  updateTerrainParams: (params: Partial<TerrainParams>) => {
    set(state => ({
      terrainParams: { ...state.terrainParams, ...params }
    }));
  },

  updateBridgeParams: (params: Partial<BridgeParams>) => {
    set(state => ({
      bridgeParams: { ...state.bridgeParams, ...params }
    }));
  },

  setTerrainHeights: (heights: number[][]) => {
    set({ terrainHeights: heights });
  },

  setBridgeMesh: (mesh: THREE.Mesh | null) => {
    set({ bridgeMesh: mesh });
  },

  setTerrainGenerated: (generated: boolean) => {
    set({ isTerrainGenerated: generated });
  },

  setBridgeLoaded: (loaded: boolean) => {
    set({ isBridgeLoaded: loaded });
  },

  resetToDefaults: () => {
    set({
      sphParams: { ...defaultSPHParams },
      terrainParams: { ...defaultTerrainParams },
      bridgeParams: { ...defaultBridgeParams }
    });
  }
}));
