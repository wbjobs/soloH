import type { WorkerGenerateMessage, WorkerResultMessage } from '../types';
import { TurtleInterpreter, InterpretationOptions } from '../lsystem/TurtleInterpreter';

const interpreter = new TurtleInterpreter();

const ctx: Worker = self as unknown as Worker;

ctx.onmessage = (e: MessageEvent<WorkerGenerateMessage>) => {
  if (e.data.type === 'generate') {
    const { plantId, config, environment, iterations, tropismBias, ageFactor } = e.data;
    
    const options: InterpretationOptions = {
      tropismBias: tropismBias,
      ageFactor: ageFactor,
      tropismStrength: tropismBias ? 0.5 : 0,
      maxDepth: 30
    };
    
    try {
      const data = interpreter.generatePlant(
        config,
        environment,
        iterations,
        (progress) => {
          ctx.postMessage({
            type: 'progress',
            progress
          });
        },
        options
      );
      
      const result: WorkerResultMessage = {
        type: 'result',
        plantId,
        data,
        progress: 1
      };
      
      ctx.postMessage(result);
    } catch (error) {
      ctx.postMessage({
        type: 'error',
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  }
};

export {};
