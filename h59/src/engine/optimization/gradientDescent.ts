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

export const optimizeGradientDescent = (
  sources: SourceConfig[],
  substrate: SubstrateConfig,
  calcConfig: CalculationConfig,
  optConfig: OptimizationConfig,
  occluders: OccluderConfig[],
  onIteration?: (iteration: OptimizationIteration) => void,
  shouldCancel?: () => boolean
): OptimizationResult => {
  const maxIterations = optConfig.maxIterations;
  const learningRate = 5.0;
  const epsilon = 1.0;
  const targetSourceIds = optConfig.sourceIds;

  const sourceIndices = targetSourceIds.map((id) =>
    sources.findIndex((s) => s.id === id)
  );

  let positions = sourceIndices.map((i) => ({ ...sources[i].position }));
  let bestPositions = positions.map((p) => ({ ...p }));
  let bestFitness = -Infinity;
  const history: { iteration: number; uniformity: number }[] = [];

  const evaluateFitness = (pos: Vector3[]): number => {
    const modifiedSources = sources.map((s, idx) => {
      const sourceIdx = sourceIndices.indexOf(idx);
      if (sourceIdx >= 0) {
        return { ...s, position: pos[sourceIdx] };
      }
      return s;
    });

    const result = calculateThicknessCosine(modifiedSources, substrate, occluders);
    return result.uniformity;
  };

  const computeGradient = (pos: Vector3[]): Vector3[] => {
    const gradient: Vector3[] = pos.map(() => ({ x: 0, y: 0, z: 0 }));
    const baseFitness = evaluateFitness(pos);

    for (let i = 0; i < pos.length; i++) {
      const posPlus = pos.map((p, j) => (j === i ? { ...p, x: p.x + epsilon } : p));
      const posMinus = pos.map((p, j) => (j === i ? { ...p, x: p.x - epsilon } : p));
      gradient[i].x = (evaluateFitness(posPlus) - evaluateFitness(posMinus)) / (2 * epsilon);

      const posPlusY = pos.map((p, j) => (j === i ? { ...p, y: p.y + epsilon } : p));
      const posMinusY = pos.map((p, j) => (j === i ? { ...p, y: p.y - epsilon } : p));
      gradient[i].y = (evaluateFitness(posPlusY) - evaluateFitness(posMinusY)) / (2 * epsilon);

      const posPlusZ = pos.map((p, j) => (j === i ? { ...p, z: p.z + epsilon } : p));
      const posMinusZ = pos.map((p, j) => (j === i ? { ...p, z: p.z - epsilon } : p));
      gradient[i].z = (evaluateFitness(posPlusZ) - evaluateFitness(posMinusZ)) / (2 * epsilon);
    }

    return gradient;
  };

  const clampPosition = (pos: Vector3): Vector3 => ({
    x: Math.max(optConfig.bounds.min.x, Math.min(optConfig.bounds.max.x, pos.x)),
    y: Math.max(optConfig.bounds.min.y, Math.min(optConfig.bounds.max.y, pos.y)),
    z: Math.max(optConfig.bounds.min.z, Math.min(optConfig.bounds.max.z, pos.z)),
  });

  let currentLearningRate = learningRate;

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

    const currentFitness = evaluateFitness(positions);

    if (currentFitness > bestFitness) {
      bestFitness = currentFitness;
      bestPositions = positions.map((p) => ({ ...p }));
    }

    history.push({ iteration: i, uniformity: bestFitness });

    if (onIteration) {
      onIteration({
        iteration: i,
        bestUniformity: bestFitness,
        bestPositions: bestPositions.map((pos, idx) => ({
          sourceId: targetSourceIds[idx],
          position: pos,
        })),
        avgUniformity: currentFitness,
      });
    }

    if (bestFitness >= optConfig.targetUniformity) {
      break;
    }

    const gradient = computeGradient(positions);

    let newPositions = positions.map((pos, idx) =>
      clampPosition({
        x: pos.x + gradient[idx].x * currentLearningRate,
        y: pos.y + gradient[idx].y * currentLearningRate,
        z: pos.z + gradient[idx].z * currentLearningRate,
      })
    );

    const newFitness = evaluateFitness(newPositions);
    if (newFitness < currentFitness) {
      currentLearningRate *= 0.5;
    } else {
      currentLearningRate *= 1.1;
      positions = newPositions;
    }

    if (currentLearningRate < 0.01) {
      break;
    }
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
