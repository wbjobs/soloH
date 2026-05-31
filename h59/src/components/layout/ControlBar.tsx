import React, { useRef, useCallback, useEffect } from 'react';
import { Play, Square, RotateCcw, Loader2, AlertCircle } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';
import type { WorkerMessage, WorkerResponse } from '../../types';

export const ControlBar: React.FC = () => {
  const workerRef = useRef<Worker | null>(null);

  const {
    sources,
    substrate,
    calculationConfig,
    optimizationConfig,
    occluders,
    isCalculating,
    isOptimizing,
    progress,
    progressMessage,
    error,
    setIsCalculating,
    setIsOptimizing,
    setProgress,
    setError,
    setCalculationResult,
    setOptimizationResult,
    addOptimizationIteration,
    resetResults,
    applyOptimizedPositions,
  } = useAppStore();

  useEffect(() => {
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
      }
    };
  }, []);

  const initWorker = useCallback(() => {
    if (workerRef.current) {
      workerRef.current.terminate();
    }

    const worker = new Worker(new URL('../../workers/calculation.worker.ts', import.meta.url), {
      type: 'module',
    });

    worker.onmessage = (e: MessageEvent<WorkerResponse>) => {
      const message = e.data;

      switch (message.type) {
        case 'PROGRESS':
          setProgress(message.payload.progress, message.payload.message);
          break;
        case 'CALCULATION_COMPLETE':
          setCalculationResult(message.payload);
          setIsCalculating(false);
          setProgress(100, '计算完成');
          break;
        case 'OPTIMIZATION_ITERATION':
          addOptimizationIteration(message.payload);
          break;
        case 'OPTIMIZATION_COMPLETE':
          setOptimizationResult(message.payload);
          if (message.payload.success) {
            applyOptimizedPositions(message.payload.bestPositions);
          }
          setIsOptimizing(false);
          setProgress(100, '优化完成');
          break;
        case 'ERROR':
          setError(message.payload.message);
          setIsCalculating(false);
          setIsOptimizing(false);
          break;
      }
    };

    worker.onerror = (error) => {
      setError(error.message);
      setIsCalculating(false);
      setIsOptimizing(false);
    };

    workerRef.current = worker;
    return worker;
  }, [setProgress, setCalculationResult, setOptimizationResult, addOptimizationIteration, setIsCalculating, setIsOptimizing, setError, applyOptimizedPositions]);

  const handleStart = useCallback(() => {
    resetResults();
    const worker = initWorker();

    if (optimizationConfig.enabled) {
      setIsOptimizing(true);
      setProgress(0, '开始优化...');

      const message: WorkerMessage = {
        type: 'START_OPTIMIZATION',
        payload: {
          sources,
          substrate,
          config: calculationConfig,
          optimization: optimizationConfig,
          occluders,
        },
      };
      worker.postMessage(message);
    } else {
      setIsCalculating(true);
      setProgress(0, '开始计算...');

      const message: WorkerMessage = {
        type: 'START_CALCULATION',
        payload: {
          sources,
          substrate,
          config: calculationConfig,
          occluders,
        },
      };
      worker.postMessage(message);
    }
  }, [sources, substrate, calculationConfig, optimizationConfig, occluders, resetResults, initWorker, setIsCalculating, setIsOptimizing, setProgress]);

  const handleCancel = useCallback(() => {
    if (workerRef.current) {
      const message: WorkerMessage = { type: 'CANCEL' };
      workerRef.current.postMessage(message);
      workerRef.current.terminate();
      workerRef.current = null;
    }
    setIsCalculating(false);
    setIsOptimizing(false);
    setProgress(0, '已取消');
  }, [setIsCalculating, setIsOptimizing, setProgress]);

  const handleReset = useCallback(() => {
    handleCancel();
    resetResults();
    setError(null);
  }, [handleCancel, resetResults, setError]);

  const isRunning = isCalculating || isOptimizing;

  return (
    <div className="h-16 bg-slate-900 border-t border-slate-700 px-4 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          {isRunning ? (
            <div className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
          ) : error ? (
            <AlertCircle className="w-4 h-4 text-red-500" />
          ) : (
            <div className="w-2 h-2 rounded-full bg-green-500" />
          )}
          <span className="text-sm text-slate-300">
            {error || progressMessage || '就绪'}
          </span>
        </div>

        {isRunning && (
          <div className="w-48 h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={handleReset}
          disabled={isRunning}
          className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          重置
        </button>

        {isRunning ? (
          <button
            onClick={handleCancel}
            className="px-6 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg flex items-center gap-2 transition-colors"
          >
            <Square className="w-4 h-4" />
            停止
          </button>
        ) : (
          <button
            onClick={handleStart}
            className="px-6 py-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-sm font-medium rounded-lg flex items-center gap-2 transition-all shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40"
          >
            {isCalculating || isOptimizing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {optimizationConfig.enabled ? '开始优化' : '开始计算'}
          </button>
        )}
      </div>
    </div>
  );
};
