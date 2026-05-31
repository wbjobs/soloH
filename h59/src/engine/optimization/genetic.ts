import type {
  SourceConfig,
  SubstrateConfig,
  CalculationConfig,
  OptimizationConfig,
  Vector3,
  OptimizationResult,
  OptimizationIteration,
  OccluderConfig,
} from '../../types';
import { calculateThicknessCosine } from '../methods/cosine';
import { vec3, randomRange, gaussianRandom } from '../math/vector';

interface Individual {
  positions: Vector3[];
  fitness: number;
  crowdingDistance?: number;
}

export const optimizeGenetic = (
  sources: SourceConfig[],
  substrate: SubstrateConfig,
  calcConfig: CalculationConfig,
  optConfig: OptimizationConfig,
  occluders: OccluderConfig[],
  onIteration?: (iteration: OptimizationIteration) => void,
  shouldCancel?: () => boolean
): OptimizationResult => {
  const populationSize = optConfig.populationSize || 20;
  const maxIterations = optConfig.maxIterations;
  const elitismCount = 2;
  const targetSourceIds = optConfig.sourceIds;
  const geneticConfig = optConfig.geneticConfig;

  const sourceIndices = targetSourceIds.map((id) =>
    sources.findIndex((s) => s.id === id)
  );

  const initialPositions = sourceIndices.map((i) => ({ ...sources[i].position }));

  const evaluateFitness = (positions: Vector3[]): number => {
    const modifiedSources = sources.map((s, idx) => {
      const sourceIdx = sourceIndices.indexOf(idx);
      if (sourceIdx >= 0) {
        return { ...s, position: positions[sourceIdx] };
      }
      return s;
    });

    const result = calculateThicknessCosine(modifiedSources, substrate, occluders);
    return result.uniformity;
  };

  const calculatePopulationDiversity = (population: Individual[]): number => {
    if (population.length < 2) return 0;

    let totalDistance = 0;
    let pairCount = 0;

    for (let i = 0; i < population.length; i++) {
      for (let j = i + 1; j < population.length; j++) {
        let dist = 0;
        for (let k = 0; k < population[i].positions.length; k++) {
          dist += vec3.distance(
            population[i].positions[k],
            population[j].positions[k]
          );
        }
        totalDistance += dist;
        pairCount++;
      }
    }

    return totalDistance / pairCount;
  };

  const calculateCrowdingDistance = (population: Individual[]): void => {
    const n = population.length;
    const m = population[0].positions.length;

    population.forEach((ind) => {
      ind.crowdingDistance = 0;
    });

    for (let i = 0; i < m; i++) {
      const sorted = [...population].sort(
        (a, b) => a.positions[i].x + a.positions[i].y + a.positions[i].z -
                   (b.positions[i].x + b.positions[i].y + b.positions[i].z)
      );

      sorted[0].crowdingDistance = Infinity;
      sorted[n - 1].crowdingDistance = Infinity;

      const minVal = sorted[0].positions[i].x + sorted[0].positions[i].y + sorted[0].positions[i].z;
      const maxVal = sorted[n - 1].positions[i].x + sorted[n - 1].positions[i].y + sorted[n - 1].positions[i].z;
      const range = maxVal - minVal || 1;

      for (let j = 1; j < n - 1; j++) {
        const prevVal = sorted[j - 1].positions[i].x + sorted[j - 1].positions[i].y + sorted[j - 1].positions[i].z;
        const nextVal = sorted[j + 1].positions[i].x + sorted[j + 1].positions[i].y + sorted[j + 1].positions[i].z;
        sorted[j].crowdingDistance += (nextVal - prevVal) / range;
      }
    }
  };

  const getAdaptiveMutationRate = (
    diversity: number,
    currentBestFitness: number,
    bestFitnessStagnation: number
  ): number => {
    if (!geneticConfig.adaptiveMutation) {
      return (geneticConfig.mutationRateMin + geneticConfig.mutationRateMax) / 2;
    }

    let rate = geneticConfig.mutationRateMax;

    const diversityRatio = diversity / geneticConfig.diversityThreshold;
    rate = geneticConfig.mutationRateMax -
      (geneticConfig.mutationRateMax - geneticConfig.mutationRateMin) *
        Math.min(1, diversityRatio);

    if (bestFitnessStagnation > geneticConfig.catastropheThreshold / 2) {
      rate = Math.min(geneticConfig.mutationRateMax, rate * 1.5);
    }

    return rate;
  };

  const crowdingCompetition = (
    parent1: Individual,
    parent2: Individual,
    child1: Individual,
    child2: Individual
  ): Individual[] => {
    if (!geneticConfig.crowdingEnabled) {
      return [child1, child2];
    }

    const survivors: Individual[] = [];
    const factor = geneticConfig.crowdingFactor;

    for (const child of [child1, child2]) {
      let closestParent = parent1;
      let minDist = Infinity;

      for (const parent of [parent1, parent2]) {
        let dist = 0;
        for (let i = 0; i < child.positions.length; i++) {
          dist += vec3.distance(child.positions[i], parent.positions[i]);
        }
        if (dist < minDist) {
          minDist = dist;
          closestParent = parent;
        }
      }

      if (Math.random() < factor && child.fitness > closestParent.fitness) {
        survivors.push(child);
      } else {
        survivors.push(closestParent);
      }
    }

    return survivors;
  };

  const createIndividual = (): Individual => {
    const positions = initialPositions.map((pos) => ({
      x: randomRange(optConfig.bounds.min.x, optConfig.bounds.max.x),
      y: randomRange(optConfig.bounds.min.y, optConfig.bounds.max.y),
      z: randomRange(optConfig.bounds.min.z, optConfig.bounds.max.z),
    }));
    return { positions, fitness: 0 };
  };

  const mutate = (individual: Individual, mutationRate: number): Individual => {
    const boundsRange = {
      x: optConfig.bounds.max.x - optConfig.bounds.min.x,
      y: optConfig.bounds.max.y - optConfig.bounds.min.y,
      z: optConfig.bounds.max.z - optConfig.bounds.min.z,
    };

    const newPositions = individual.positions.map((pos) => {
      if (Math.random() < mutationRate) {
        const sigma = {
          x: boundsRange.x * 0.1,
          y: boundsRange.y * 0.1,
          z: boundsRange.z * 0.1,
        };
        return {
          x: Math.max(
            optConfig.bounds.min.x,
            Math.min(optConfig.bounds.max.x, pos.x + gaussianRandom(0, sigma.x))
          ),
          y: Math.max(
            optConfig.bounds.min.y,
            Math.min(optConfig.bounds.max.y, pos.y + gaussianRandom(0, sigma.y))
          ),
          z: Math.max(
            optConfig.bounds.min.z,
            Math.min(optConfig.bounds.max.z, pos.z + gaussianRandom(0, sigma.z))
          ),
        };
      }
      return { ...pos };
    });
    return { positions: newPositions, fitness: 0 };
  };

  const crossover = (parent1: Individual, parent2: Individual): Individual => {
    const crossPoint = Math.floor(Math.random() * parent1.positions.length);
    const positions = parent1.positions.map((pos, i) => {
      if (i < crossPoint) {
        return { ...pos };
      }
      return { ...parent2.positions[i] };
    });
    return { positions, fitness: 0 };
  };

  const selectParent = (population: Individual[]): Individual => {
    const tournamentSize = 3;
    let best: Individual | null = null;

    for (let i = 0; i < tournamentSize; i++) {
      const idx = Math.floor(Math.random() * population.length);
      const candidate = population[idx];

      if (!best || candidate.fitness > best.fitness ||
          (geneticConfig.crowdingEnabled &&
           candidate.fitness === best.fitness &&
           (candidate.crowdingDistance || 0) > (best.crowdingDistance || 0))) {
        best = candidate;
      }
    }

    return best || population[0];
  };

  const applyCatastrophe = (
    population: Individual[],
    bestIndividual: Individual
  ): Individual[] => {
    const newPopulation: Individual[] = [];

    newPopulation.push({
      positions: bestIndividual.positions.map((p) => ({ ...p })),
      fitness: bestIndividual.fitness,
    });

    const count = geneticConfig.catastropheCount;
    for (let i = 0; i < count - 1; i++) {
      const ind = createIndividual();
      ind.positions = initialPositions.map((pos, idx) => ({
        x: bestIndividual.positions[idx].x + gaussianRandom(0, 30),
        y: bestIndividual.positions[idx].y + gaussianRandom(0, 30),
        z: bestIndividual.positions[idx].z + gaussianRandom(0, 30),
      }));
      newPopulation.push(ind);
    }

    while (newPopulation.length < population.length) {
      newPopulation.push(createIndividual());
    }

    return newPopulation;
  };

  let population: Individual[] = Array(populationSize)
    .fill(null)
    .map(() => createIndividual());

  let bestFitness = -Infinity;
  let bestPositions = initialPositions.map((p) => ({ ...p }));
  let bestFitnessStagnation = 0;
  const history: { iteration: number; uniformity: number; diversity?: number }[] = [];

  for (let i = 0; i < maxIterations; i++) {
    if (shouldCancel?.()) {
      return {
        success: false,
        bestUniformity: bestFitness,
        bestPositions: bestPositions.map((pos, idx) => ({
          sourceId: targetSourceIds[idx],
          position: pos,
        })),
        iterations: i,
        history,
      };
    }

    population.forEach((ind) => {
      ind.fitness = evaluateFitness(ind.positions);
    });

    if (geneticConfig.crowdingEnabled) {
      calculateCrowdingDistance(population);
    }

    population.sort((a, b) => {
      if (b.fitness !== a.fitness) {
        return b.fitness - a.fitness;
      }
      return (b.crowdingDistance || 0) - (a.crowdingDistance || 0);
    });

    const diversity = calculatePopulationDiversity(population);
    const currentBest = population[0];
    const fitnessImproved = currentBest.fitness > bestFitness + 0.01;

    if (fitnessImproved) {
      bestFitness = currentBest.fitness;
      bestPositions = currentBest.positions.map((p) => ({ ...p }));
      bestFitnessStagnation = 0;
    } else {
      bestFitnessStagnation++;
    }

    history.push({ iteration: i, uniformity: bestFitness, diversity });

    const avgFitness =
      population.reduce((sum, ind) => sum + ind.fitness, 0) / population.length;

    if (onIteration) {
      onIteration({
        iteration: i,
        bestUniformity: bestFitness,
        bestPositions: bestPositions.map((pos, idx) => ({
          sourceId: targetSourceIds[idx],
          position: pos,
        })),
        avgUniformity: avgFitness,
      });
    }

    if (bestFitness >= optConfig.targetUniformity) {
      break;
    }

    if (geneticConfig.catastropheEnabled &&
        bestFitnessStagnation >= geneticConfig.catastropheThreshold) {
      population = applyCatastrophe(population, population[0]);
      bestFitnessStagnation = 0;
      continue;
    }

    const mutationRate = getAdaptiveMutationRate(
      diversity,
      bestFitness,
      bestFitnessStagnation
    );

    const newPopulation: Individual[] = [];

    for (let e = 0; e < elitismCount; e++) {
      newPopulation.push({
        positions: population[e].positions.map((p) => ({ ...p })),
        fitness: population[e].fitness,
      });
    }

    while (newPopulation.length < populationSize) {
      const parent1 = selectParent(population);
      const parent2 = selectParent(population);
      const child1 = crossover(parent1, parent2);
      const child2 = crossover(parent2, parent1);

      child1.fitness = evaluateFitness(child1.positions);
      child2.fitness = evaluateFitness(child2.positions);

      const mutated1 = mutate(child1, mutationRate);
      const mutated2 = mutate(child2, mutationRate);

      mutated1.fitness = evaluateFitness(mutated1.positions);
      mutated2.fitness = evaluateFitness(mutated2.positions);

      const survivors = crowdingCompetition(parent1, parent2, mutated1, mutated2);
      newPopulation.push(...survivors);
    }

    population = newPopulation.slice(0, populationSize);
  }

  return {
    success: bestFitness >= optConfig.targetUniformity,
    bestUniformity: bestFitness,
    bestPositions: bestPositions.map((pos, idx) => ({
      sourceId: targetSourceIds[idx],
      position: pos,
    })),
    iterations: maxIterations,
    history,
  };
};
