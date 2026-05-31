import { create } from 'zustand';
import { Particle, ImpactForceData, SPHParameters, createVector3, vecLength } from '../types/physics';
import { SPHEngine } from '../physics/SPHEngine';

interface SimulationState {
  isRunning: boolean;
  isPaused: boolean;
  simulationTime: number;
  frameCount: number;
  fps: number;
  particles: Particle[];
  impactForceHistory: ImpactForceData[];
  currentImpactData: ImpactForceData | null;
  peakForce: number;
  peakPressure: number;
  engine: SPHEngine | null;
  stats: {
    avgDensity: number;
    avgSpeed: number;
    activeCells: number;
  };
  initEngine: (params: SPHParameters) => void;
  start: () => void;
  pause: () => void;
  reset: () => void;
  step: (dt: number) => void;
  updateFPS: (fps: number) => void;
  getEngine: () => SPHEngine | null;
}

const defaultParams: SPHParameters = {
  density0: 2000,
  viscosity: 0.1,
  yieldStress: 100,
  smoothingLength: 0.5,
  particleRadius: 0.2,
  particleMass: 0.1,
  gravity: createVector3(0, -9.81, 0),
  stiffness: 1000,
  timeStep: 0.005,
  maxParticles: 5000,
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

export const useSimulationStore = create<SimulationState>((set, get) => ({
  isRunning: false,
  isPaused: false,
  simulationTime: 0,
  frameCount: 0,
  fps: 0,
  particles: [],
  impactForceHistory: [],
  currentImpactData: null,
  peakForce: 0,
  peakPressure: 0,
  engine: null,
  stats: {
    avgDensity: 0,
    avgSpeed: 0,
    activeCells: 0
  },

  initEngine: (params: SPHParameters = defaultParams) => {
    const engine = new SPHEngine(params);
    engine.initParticles(Math.min(1000, params.maxParticles));
    set({ engine });
  },

  start: () => {
    const { engine } = get();
    if (!engine) {
      const newEngine = new SPHEngine(defaultParams);
      newEngine.initParticles(1000);
      set({ engine: newEngine, isRunning: true, isPaused: false });
    } else {
      if (engine.getParticleCount() === 0) {
        engine.initParticles(1000);
      }
      set({ isRunning: true, isPaused: false });
    }
  },

  pause: () => {
    set(state => ({ isPaused: !state.isPaused }));
  },

  reset: () => {
    const { engine } = get();
    if (engine) {
      engine.reset();
      engine.initParticles(engine.getParameters().maxParticles > 0 ? 
        Math.min(1000, engine.getParameters().maxParticles) : 1000);
    }
    set({
      isRunning: false,
      isPaused: false,
      simulationTime: 0,
      frameCount: 0,
      particles: [],
      impactForceHistory: [],
      currentImpactData: null,
      peakForce: 0,
      peakPressure: 0,
      stats: { avgDensity: 0, avgSpeed: 0, activeCells: 0 }
    });
  },

  step: (dt: number) => {
    const { engine, isRunning, isPaused } = get();
    if (!engine || !isRunning || isPaused) return;

    engine.step(dt);

    const particles = engine.getParticles();
    const impactData = engine.getImpactForceData();
    const history = engine.getImpactHistory();
    const peakForceData = engine.getPeakImpactForce();
    const peakPressureData = engine.getPeakPressure();
    const stats = engine.getStats();

    let totalDensity = 0;
    let totalSpeed = 0;
    for (const p of particles) {
      totalDensity += p.density;
      totalSpeed += vecLength(p.velocity);
    }

    set(state => ({
      simulationTime: engine.getSimulationTime(),
      frameCount: state.frameCount + 1,
      particles,
      currentImpactData: impactData,
      impactForceHistory: history.slice(-500),
      peakForce: Math.max(state.peakForce, peakForceData.magnitude),
      peakPressure: Math.max(state.peakPressure, peakPressureData.pressure),
      stats: {
        avgDensity: particles.length > 0 ? totalDensity / particles.length : 0,
        avgSpeed: particles.length > 0 ? totalSpeed / particles.length : 0,
        activeCells: stats.spatialHashStats.cellCount
      }
    }));
  },

  updateFPS: (fps: number) => {
    set({ fps });
  },

  getEngine: () => {
    return get().engine;
  }
}));
