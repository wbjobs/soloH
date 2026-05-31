import type {
  WorkerMessage,
  WorkerResponse,
  CalculationPayload,
  OptimizationPayload,
} from '../types';
import { calculateThicknessCosine } from '../engine/methods/cosine';
import { calculateThicknessMonteCarlo } from '../engine/methods/monteCarlo';
import { optimizeGenetic } from '../engine/optimization/genetic';
import { optimizeGradientDescent } from '../engine/optimization/gradientDescent';

let isCancelled = false;

const sendProgress = (progress: number, message: string) => {
  const response: WorkerResponse = {
    type: 'PROGRESS',
    payload: { progress, message },
  };
  self.postMessage(response);
};

const handleCalculation = (payload: CalculationPayload) => {
  isCancelled = false;

  try {
    const { sources, substrate, config, occluders } = payload;

    const onProgress = (progress: number, message: string) => {
      if (!isCancelled) {
        sendProgress(progress, message);
      }
    };

    let result;

    if (config.method === 'cosine') {
      result = calculateThicknessCosine(sources, substrate, occluders, onProgress);
    } else {
      const numParticles = config.monteCarloParticles || 100000;
      result = calculateThicknessMonteCarlo(
        sources,
        substrate,
        occluders,
        numParticles,
        onProgress
      );
    }

    if (!isCancelled) {
      const response: WorkerResponse = {
        type: 'CALCULATION_COMPLETE',
        payload: result,
      };
      self.postMessage(response);
    }
  } catch (error) {
    const response: WorkerResponse = {
      type: 'ERROR',
      payload: { message: (error as Error).message },
    };
    self.postMessage(response);
  }
};

const handleOptimization = (payload: OptimizationPayload) => {
  isCancelled = false;

  try {
    const { sources, substrate, config, optimization, occluders } = payload;

    const onIteration = (iteration) => {
      if (!isCancelled) {
        const response: WorkerResponse = {
          type: 'OPTIMIZATION_ITERATION',
          payload: iteration,
        };
        self.postMessage(response);

        const progress = ((iteration.iteration + 1) / optimization.maxIterations) * 100;
        sendProgress(
          progress,
          `优化迭代 ${iteration.iteration + 1}/${optimization.maxIterations}, 当前最佳均匀性: ${iteration.bestUniformity.toFixed(2)}%`
        );
      }
    };

    const shouldCancel = () => isCancelled;

    let result;

    if (optimization.method === 'genetic') {
      result = optimizeGenetic(
        sources,
        substrate,
        config,
        optimization,
        occluders,
        onIteration,
        shouldCancel
      );
    } else {
      result = optimizeGradientDescent(
        sources,
        substrate,
        config,
        optimization,
        occluders,
        onIteration,
        shouldCancel
      );
    }

    if (!isCancelled) {
      const response: WorkerResponse = {
        type: 'OPTIMIZATION_COMPLETE',
        payload: result,
      };
      self.postMessage(response);
    }
  } catch (error) {
    const response: WorkerResponse = {
      type: 'ERROR',
      payload: { message: (error as Error).message },
    };
    self.postMessage(response);
  }
};

self.onmessage = (e: MessageEvent<WorkerMessage>) => {
  const message = e.data;

  switch (message.type) {
    case 'START_CALCULATION':
      handleCalculation(message.payload);
      break;
    case 'START_OPTIMIZATION':
      handleOptimization(message.payload);
      break;
    case 'CANCEL':
      isCancelled = true;
      break;
  }
};
