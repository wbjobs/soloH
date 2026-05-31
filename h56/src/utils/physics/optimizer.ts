import type { EmitterLayer } from '../../types';
import { calculateReflectanceSpectrum } from './tmm';
import { planckPhotonFlux, bandgapToCutoffWavelength, wavelengthToEnergy } from './blackbody';
import { PHYSICAL_CONSTANTS } from '../../data/materials';

const { q } = PHYSICAL_CONSTANTS;

export function objectiveFunction(
  layers: EmitterLayer[],
  sourceTemp: number,
  bandgap: number
): number {
  const reflectance = calculateReflectanceSpectrum(layers, 200, 5000, 100, 0, 3.5, sourceTemp);
  const cutoffWavelength = bandgapToCutoffWavelength(bandgap);
  
  let usefulPower = 0;
  let totalPower = 0;
  
  for (let i = 0; i < reflectance.length - 1; i++) {
    const { wavelength, r } = reflectance[i];
    const step = reflectance[i + 1].wavelength - wavelength;
    
    const flux = planckPhotonFlux(wavelength, sourceTemp);
    const energy = wavelengthToEnergy(wavelength) * q;
    
    totalPower += flux * energy * step * 1e-9;
    
    if (wavelength < cutoffWavelength) {
      usefulPower += flux * energy * (1 - r) * step * 1e-9;
    } else {
      usefulPower += flux * energy * r * step * 1e-9;
    }
  }
  
  return totalPower > 0 ? usefulPower / totalPower : 0;
}

export interface OptimizationConfig {
  populationSize: number;
  maxGenerations: number;
  mutationRate: number;
  crossoverRate: number;
  minThickness: number;
  maxThickness: number;
  numLayers: number;
  availableMaterials: { name: string; n: number; k: number; dn_dT: number; dk_dT: number; referenceTemperature: number }[];
}

const DEFAULT_CONFIG: OptimizationConfig = {
  populationSize: 30,
  maxGenerations: 50,
  mutationRate: 0.2,
  crossoverRate: 0.7,
  minThickness: 10,
  maxThickness: 500,
  numLayers: 3,
  availableMaterials: [
    { name: 'W', n: 3.5, k: 2.5, dn_dT: 2e-4, dk_dT: 1e-3, referenceTemperature: 300 },
    { name: 'SiO₂', n: 1.45, k: 0, dn_dT: 1e-5, dk_dT: 0, referenceTemperature: 300 },
    { name: 'Si₃N₄', n: 2.0, k: 0, dn_dT: 2e-5, dk_dT: 0, referenceTemperature: 300 },
    { name: 'TiO₂', n: 2.5, k: 0, dn_dT: 3e-5, dk_dT: 0, referenceTemperature: 300 },
  ],
};

interface Individual {
  layers: EmitterLayer[];
  fitness: number;
}

function createRandomIndividual(config: OptimizationConfig): Individual {
  const layers: EmitterLayer[] = [];
  for (let i = 0; i < config.numLayers; i++) {
    const mat = config.availableMaterials[Math.floor(Math.random() * config.availableMaterials.length)];
    layers.push({
      thickness: config.minThickness + Math.random() * (config.maxThickness - config.minThickness),
      material: mat.name,
      n: mat.n,
      k: mat.k,
      dn_dT: mat.dn_dT,
      dk_dT: mat.dk_dT,
      referenceTemperature: mat.referenceTemperature,
    });
  }
  return { layers, fitness: 0 };
}

function crossover(parent1: Individual, parent2: Individual, config: OptimizationConfig): Individual {
  const childLayers: EmitterLayer[] = [];
  const crossoverPoint = Math.floor(Math.random() * config.numLayers);
  
  for (let i = 0; i < config.numLayers; i++) {
    if (i < crossoverPoint) {
      childLayers.push({ ...parent1.layers[i] });
    } else {
      childLayers.push({ ...parent2.layers[i] });
    }
  }
  
  return { layers: childLayers, fitness: 0 };
}

function mutate(individual: Individual, config: OptimizationConfig): Individual {
  const mutatedLayers = individual.layers.map(layer => {
    if (Math.random() < config.mutationRate) {
      const newMat = config.availableMaterials[Math.floor(Math.random() * config.availableMaterials.length)];
      return {
        ...layer,
        thickness: Math.max(
          config.minThickness,
          Math.min(
            config.maxThickness,
            layer.thickness + (Math.random() - 0.5) * 50
          )
        ),
        material: newMat.name,
        n: newMat.n,
        k: newMat.k,
        dn_dT: newMat.dn_dT,
        dk_dT: newMat.dk_dT,
        referenceTemperature: newMat.referenceTemperature,
      };
    }
    return { ...layer };
  });
  
  return { layers: mutatedLayers, fitness: 0 };
}

function tournamentSelection(population: Individual[], tournamentSize: number = 3): Individual {
  const tournament: Individual[] = [];
  for (let i = 0; i < tournamentSize; i++) {
    const idx = Math.floor(Math.random() * population.length);
    tournament.push(population[idx]);
  }
  tournament.sort((a, b) => b.fitness - a.fitness);
  return tournament[0];
}

export async function geneticAlgorithmOptimizer(
  sourceTemp: number,
  bandgap: number,
  config: Partial<OptimizationConfig> = {},
  onProgress?: (progress: number, bestFitness: number) => void
): Promise<EmitterLayer[]> {
  const fullConfig = { ...DEFAULT_CONFIG, ...config };
  
  let population: Individual[] = [];
  for (let i = 0; i < fullConfig.populationSize; i++) {
    population.push(createRandomIndividual(fullConfig));
  }
  
  let bestFitness = -Infinity;
  let bestIndividual: Individual | null = null;
  
  for (let gen = 0; gen < fullConfig.maxGenerations; gen++) {
    for (const individual of population) {
      individual.fitness = objectiveFunction(individual.layers, sourceTemp, bandgap);
      if (individual.fitness > bestFitness) {
        bestFitness = individual.fitness;
        bestIndividual = { ...individual };
      }
    }
    
    population.sort((a, b) => b.fitness - a.fitness);
    
    if (onProgress) {
      await new Promise(resolve => setTimeout(resolve, 0));
      onProgress((gen + 1) / fullConfig.maxGenerations, bestFitness);
    }
    
    const newPopulation: Individual[] = [];
    
    newPopulation.push(population[0], population[1]);
    
    while (newPopulation.length < fullConfig.populationSize) {
      const parent1 = tournamentSelection(population);
      const parent2 = tournamentSelection(population);
      
      let child: Individual;
      if (Math.random() < fullConfig.crossoverRate) {
        child = crossover(parent1, parent2, fullConfig);
      } else {
        child = Math.random() < 0.5 ? { ...parent1 } : { ...parent2 };
      }
      
      child = mutate(child, fullConfig);
      newPopulation.push(child);
    }
    
    population = newPopulation;
  }
  
  return bestIndividual?.layers || population[0].layers;
}

export async function simpleGridOptimizer(
  sourceTemp: number,
  bandgap: number,
  baseStructure: EmitterLayer[],
  onProgress?: (progress: number, bestFitness: number) => void
): Promise<EmitterLayer[]> {
  let bestFitness = -Infinity;
  let bestStructure = [...baseStructure];
  
  const thicknessSteps = 50;
  const totalIterations = baseStructure.length * thicknessSteps;
  let currentIteration = 0;
  
  for (let layerIdx = 0; layerIdx < baseStructure.length; layerIdx++) {
    for (let t = 20; t <= 500; t += 10) {
      const testStructure = baseStructure.map((layer, idx) => 
        idx === layerIdx ? { ...layer, thickness: t } : layer
      );
      
      const fitness = objectiveFunction(testStructure, sourceTemp, bandgap);
      
      if (fitness > bestFitness) {
        bestFitness = fitness;
        bestStructure = testStructure;
      }
      
      currentIteration++;
      
      if (onProgress && currentIteration % 5 === 0) {
        await new Promise(resolve => setTimeout(resolve, 0));
        onProgress(currentIteration / totalIterations, bestFitness);
      }
    }
  }
  
  return bestStructure;
}

export async function optimizeEmitter(
  sourceTemp: number,
  bandgap: number,
  initialStructure: EmitterLayer[],
  useGenetic: boolean = true,
  onProgress?: (progress: number, bestFitness: number) => void
): Promise<EmitterLayer[]> {
  if (useGenetic) {
    return geneticAlgorithmOptimizer(sourceTemp, bandgap, {
      numLayers: initialStructure.length,
      availableMaterials: [
        { name: 'W', n: 3.5, k: 2.5, dn_dT: 2e-4, dk_dT: 1e-3, referenceTemperature: 300 },
        { name: 'SiO₂', n: 1.45, k: 0, dn_dT: 1e-5, dk_dT: 0, referenceTemperature: 300 },
        { name: 'Si₃N₄', n: 2.0, k: 0, dn_dT: 2e-5, dk_dT: 0, referenceTemperature: 300 },
      ],
    }, onProgress);
  } else {
    return simpleGridOptimizer(sourceTemp, bandgap, initialStructure, onProgress);
  }
}
