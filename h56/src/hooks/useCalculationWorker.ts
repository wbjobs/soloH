import { useCallback, useEffect, useRef, useState } from 'react';
import type { 
  CalculationParams, 
  CalculationResult, 
  CalculationState,
  Material,
  WorkerMessage 
} from '@/types';

export function useCalculationWorker() {
  const workerRef = useRef<Worker | null>(null);
  const [state, setState] = useState<CalculationState>({
    status: 'idle',
    progress: 0,
    currentStep: '',
    result: null,
    error: null,
  });

  useEffect(() => {
    const worker = new Worker(
      new URL('../workers/calculation.worker.ts', import.meta.url),
      { type: 'module' }
    );
    
    workerRef.current = worker;

    worker.onmessage = (e: MessageEvent<WorkerMessage>) => {
      const { type, payload } = e.data;

      switch (type) {
        case 'progress':
          setState(prev => ({
            ...prev,
            status: 'running',
            progress: payload.progress,
            currentStep: payload.currentStep,
          }));
          break;
        case 'result':
          setState(prev => ({
            ...prev,
            status: 'completed',
            progress: 1,
            result: payload as CalculationResult,
            error: null,
          }));
          break;
        case 'error':
          setState(prev => ({
            ...prev,
            status: 'error',
            error: payload.message,
          }));
          break;
      }
    };

    worker.onerror = (error) => {
      setState(prev => ({
        ...prev,
        status: 'error',
        error: error.message,
      }));
    };

    return () => {
      worker.terminate();
    };
  }, []);

  const startCalculation = useCallback((
    params: CalculationParams,
    customMaterials: Material[] = []
  ) => {
    if (!workerRef.current) return;

    setState({
      status: 'running',
      progress: 0,
      currentStep: '初始化计算...',
      result: null,
      error: null,
    });

    workerRef.current.postMessage({
      type: 'startCalculation',
      payload: { params, customMaterials },
    });
  }, []);

  const cancelCalculation = useCallback(() => {
    if (!workerRef.current) return;
    
    workerRef.current.postMessage({
      type: 'cancelCalculation',
    });
    
    setState(prev => ({
      ...prev,
      status: 'idle',
      progress: 0,
      currentStep: '',
    }));
  }, []);

  const reset = useCallback(() => {
    setState({
      status: 'idle',
      progress: 0,
      currentStep: '',
      result: null,
      error: null,
    });
  }, []);

  return {
    state,
    startCalculation,
    cancelCalculation,
    reset,
  };
}
