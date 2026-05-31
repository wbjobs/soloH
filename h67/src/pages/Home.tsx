import React, { useEffect, useCallback, useState } from 'react';
import { Beaker, AlertCircle, Brain, Layers, Activity } from 'lucide-react';
import { useSimulationStore } from '../store/useSimulationStore';
import { FluidProperties } from '../components/ParameterPanel/FluidProperties';
import { ControlButtons } from '../components/SimulationControl/ControlButtons';
import { MetricsCards } from '../components/ResultsDisplay/MetricsCards';
import { RealTimeChart } from '../components/ResultsDisplay/RealTimeChart';
import { PIDPanel } from '../components/PIDControl/PIDPanel';
import { OptimizationPanel } from '../components/Optimization/OptimizationPanel';
import { PerturbationPanel } from '../components/Perturbation/PerturbationPanel';
import { NeuralSurrogatePanel } from '../components/NeuralSurrogate/NeuralSurrogatePanel';
import { MultichannelPanel } from '../components/Multichannel/MultichannelPanel';
import {
  SimulationParameters,
  PIDParameters,
  PerturbationConfig,
  OptimizationResult,
  SimulationMode,
  ChannelResult,
  FaultDetectionStatus,
} from '../types';

const modeOptions: { value: SimulationMode; label: string; icon: React.ReactNode; color: string }[] = [
  {
    value: 'single_channel',
    label: '经验模型',
    icon: <Beaker size={14} />,
    color: 'from-blue-500 to-cyan-500',
  },
  {
    value: 'neural_surrogate',
    label: '神经网络',
    icon: <Brain size={14} />,
    color: 'from-purple-500 to-pink-500',
  },
  {
    value: 'multichannel',
    label: '多通道仿真',
    icon: <Layers size={14} />,
    color: 'from-cyan-500 to-blue-500',
  },
];

export default function Home() {
  const {
    status,
    optimizationStatus,
    timeSeries,
    wsConnected,
    isLoading,
    error,
    simulationMode,
    setSimulationMode,
    fetchStatus,
    controlSimulation,
    updateParameters,
    updatePID,
    updatePerturbation,
    startOptimization,
    stopOptimization,
    connectWebSocket,
    disconnectWebSocket,
    neuralSurrogateStatus,
  } = useSimulationStore();

  const [localParams, setLocalParams] = useState<SimulationParameters | null>(null);
  const [localPID, setLocalPID] = useState<PIDParameters>({
    enabled: false,
    targetDropletSize: 80.0,
    Kp: 0.5,
    Ki: 0.1,
    Kd: 0.01,
    outputMin: 0.5,
    outputMax: 50.0,
  });
  const [localPerturbation, setLocalPerturbation] = useState<PerturbationConfig>({
    enabled: false,
    type: 'sinusoidal',
    phase: 'dispersed',
    amplitude: 10.0,
    frequency: 0.5,
  });

  useEffect(() => {
    fetchStatus();
    connectWebSocket();

    return () => {
      disconnectWebSocket();
    };
  }, []);

  useEffect(() => {
    if (status?.parameters && !localParams) {
      setLocalParams(status.parameters);
    }
  }, [status?.parameters, localParams]);

  const handleParamsChange = useCallback((params: SimulationParameters) => {
    setLocalParams(params);
  }, []);

  const handleParamsApply = useCallback(() => {
    if (localParams) {
      updateParameters(localParams);
    }
  }, [localParams, updateParameters]);

  const handlePIDChange = useCallback((params: PIDParameters) => {
    setLocalPID(params);
    updatePID(params);
  }, [updatePID]);

  const handlePerturbationChange = useCallback((config: PerturbationConfig) => {
    setLocalPerturbation(config);
    updatePerturbation(config);
  }, [updatePerturbation]);

  const handleStart = useCallback(() => {
    if (localParams) {
      updateParameters(localParams);
    }
    controlSimulation('start');
  }, [localParams, updateParameters, controlSimulation]);

  const handlePause = useCallback(() => {
    controlSimulation('pause');
  }, [controlSimulation]);

  const handleReset = useCallback(() => {
    controlSimulation('reset');
  }, [controlSimulation]);

  const handleApplyOptimizationResult = useCallback((result: OptimizationResult) => {
    if (localParams) {
      const newParams = {
        ...localParams,
        continuousPhase: {
          ...localParams.continuousPhase,
          flowRate: result.continuousFlowRate,
        },
        dispersedPhase: {
          ...localParams.dispersedPhase,
          flowRate: result.dispersedFlowRate,
        },
      };
      setLocalParams(newParams);
      updateParameters(newParams);
    }
  }, [localParams, updateParameters]);

  const handleModeChange = useCallback(async (mode: SimulationMode) => {
    if (mode === 'neural_surrogate' && neuralSurrogateStatus && !neuralSurrogateStatus.trained) {
      alert('神经网络模型尚未训练，请先在"神经网络"面板中训练模型');
      return;
    }
    await setSimulationMode(mode);
  }, [setSimulationMode, neuralSurrogateStatus]);

  const isRunning = status?.running || false;
  const time = status?.time || 0;

  const multichannelResults: ChannelResult[] = status?.multichannel?.lastResults || [];
  const faultStatus: FaultDetectionStatus | undefined = status?.faultDetection;
  const summaryStats = status?.multichannel?.summaryStats;

  const getModeDescription = () => {
    switch (simulationMode) {
      case 'single_channel':
        return '基于Garstecki等(2006)修正的经验模型，准确预测液滴尺寸和频率';
      case 'neural_surrogate':
        return '深度学习模型从仿真数据学习，预测速度提升10-100倍';
      case 'multichannel':
        return '多通道并行仿真，包含流体动力学串扰和通道堵塞故障检测';
      default:
        return '';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 text-zinc-100">
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-zinc-950/80 border-b border-zinc-800">
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-xl flex items-center justify-center">
                <Beaker className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
                  两相流液滴生成仿真系统
                </h1>
                <p className="text-xs text-zinc-500">Two-Phase Flow Droplet Generation Simulator v2.0</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {error && (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <AlertCircle size={14} className="text-red-400" />
                  <span className="text-xs text-red-300">{error}</span>
                </div>
              )}
              <div className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-2 ${
                wsConnected ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'
              }`}>
                <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
                {wsConnected ? '后端已连接' : '后端未连接'}
              </div>
            </div>
          </div>

          <div className="mt-4">
            <div className="flex items-center gap-2 mb-2">
              <Activity size={14} className="text-zinc-500" />
              <span className="text-xs text-zinc-500">仿真模式</span>
            </div>
            <div className="flex gap-2">
              {modeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => handleModeChange(option.value)}
                  disabled={isRunning}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                    simulationMode === option.value
                      ? `bg-gradient-to-r ${option.color} text-white shadow-lg`
                      : 'bg-zinc-800/50 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed'
                  }`}
                >
                  {option.icon}
                  {option.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-zinc-600 mt-2">{getModeDescription()}</p>
          </div>
        </div>
      </header>

      <main className="max-w-[1800px] mx-auto px-6 py-6">
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          <div className="xl:col-span-4 space-y-4 overflow-y-auto max-h-[calc(100vh-200px)] pr-2">
            <ControlButtons
              isRunning={isRunning}
              isConnected={wsConnected}
              time={time}
              onStart={handleStart}
              onPause={handlePause}
              onReset={handleReset}
              isLoading={isLoading}
            />

            {localParams && (
              <FluidProperties
                parameters={localParams}
                onChange={handleParamsChange}
                disabled={isRunning}
              />
            )}

            <PIDPanel
              parameters={localPID}
              pidStatus={status?.pidStatus}
              onChange={handlePIDChange}
              disabled={false}
            />

            {simulationMode === 'neural_surrogate' && (
              <NeuralSurrogatePanel />
            )}

            {simulationMode !== 'neural_surrogate' && (
              <OptimizationPanel
                status={optimizationStatus}
                onStart={startOptimization}
                onStop={stopOptimization}
                onApplyResult={handleApplyOptimizationResult}
                disabled={isRunning}
              />
            )}

            <PerturbationPanel
              config={localPerturbation}
              onChange={handlePerturbationChange}
              disabled={false}
            />
          </div>

          <div className="xl:col-span-8 space-y-4">
            {simulationMode === 'multichannel' ? (
              <MultichannelPanel
                channelResults={multichannelResults}
                faultStatus={faultStatus}
                summaryStats={summaryStats}
              />
            ) : (
              <>
                <MetricsCards result={status?.latestResult} />
                <RealTimeChart
                  timeSeries={timeSeries}
                  targetSize={localPID.targetDropletSize}
                  pidEnabled={localPID.enabled}
                />

                {simulationMode === 'neural_surrogate' && neuralSurrogateStatus?.trained && (
                  <div className="bg-zinc-900/60 backdrop-blur-sm rounded-2xl border border-purple-500/30 p-5">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center">
                        <Brain className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-zinc-100">神经网络推理模式</h3>
                        <p className="text-xs text-zinc-500">使用训练好的深度学习模型进行快速预测</p>
                      </div>
                    </div>
                    {neuralSurrogateStatus.metrics && (
                      <div className="grid grid-cols-4 gap-3">
                        <div className="bg-zinc-800/50 rounded-xl p-3 text-center">
                          <div className="text-xs text-zinc-500 mb-1">尺寸精度</div>
                          <div className="text-lg font-bold text-emerald-400">
                            {(100 - neuralSurrogateStatus.metrics.size_mape).toFixed(1)}%
                          </div>
                        </div>
                        <div className="bg-zinc-800/50 rounded-xl p-3 text-center">
                          <div className="text-xs text-zinc-500 mb-1">频率精度</div>
                          <div className="text-lg font-bold text-emerald-400">
                            {(100 - neuralSurrogateStatus.metrics.frequency_mape).toFixed(1)}%
                          </div>
                        </div>
                        <div className="bg-zinc-800/50 rounded-xl p-3 text-center">
                          <div className="text-xs text-zinc-500 mb-1">推理速度</div>
                          <div className="text-lg font-bold text-cyan-400">~1000x</div>
                        </div>
                        <div className="bg-zinc-800/50 rounded-xl p-3 text-center">
                          <div className="text-xs text-zinc-500 mb-1">训练样本</div>
                          <div className="text-lg font-bold text-blue-400">
                            {neuralSurrogateStatus.metrics.n_training_samples.toLocaleString()}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </main>

      <footer className="border-t border-zinc-800 mt-8 py-4">
        <div className="max-w-[1800px] mx-auto px-6">
          <p className="text-center text-xs text-zinc-600">
            两相流液滴生成仿真系统 v2.0 | 经验模型 + 神经网络替代模型 + 多通道并行仿真 + 故障检测
          </p>
        </div>
      </footer>
    </div>
  );
}
