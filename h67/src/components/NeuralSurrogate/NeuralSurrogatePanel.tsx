import React, { useState, useEffect } from 'react';
import { Brain, Activity, TrendingUp, BarChart3, Play, RefreshCw, CheckCircle, AlertTriangle } from 'lucide-react';
import { useSimulationStore } from '../../store/useSimulationStore';
import { NeuralSurrogateConfig } from '../../types';

export const NeuralSurrogatePanel: React.FC = () => {
  const {
    neuralSurrogateConfig,
    neuralSurrogateStatus,
    trainNeuralSurrogate,
    fetchNeuralSurrogateStatus,
    isLoading,
  } = useSimulationStore();

  const [localConfig, setLocalConfig] = useState<NeuralSurrogateConfig>(neuralSurrogateConfig);
  const [isTraining, setIsTraining] = useState(false);

  useEffect(() => {
    fetchNeuralSurrogateStatus();
    const interval = setInterval(fetchNeuralSurrogateStatus, 2000);
    return () => clearInterval(interval);
  }, [fetchNeuralSurrogateStatus]);

  useEffect(() => {
    if (neuralSurrogateStatus?.trainingProgress && neuralSurrogateStatus.trainingProgress < 1 && neuralSurrogateStatus.trainingProgress > 0) {
      setIsTraining(true);
    } else if (neuralSurrogateStatus?.trainingProgress === 1) {
      setIsTraining(false);
    }
  }, [neuralSurrogateStatus?.trainingProgress]);

  const handleTrain = async () => {
    setIsTraining(true);
    try {
      await trainNeuralSurrogate(localConfig);
    } catch (error) {
      setIsTraining(false);
    }
  };

  const getProgressColor = (progress: number) => {
    if (progress < 0) return 'text-red-400';
    if (progress < 0.5) return 'text-yellow-400';
    if (progress < 1) return 'text-blue-400';
    return 'text-green-400';
  };

  const getProgressLabel = (progress: number) => {
    if (progress < 0) return '训练失败';
    if (progress === 0) return '未训练';
    if (progress < 1) return '训练中...';
    return '训练完成';
  };

  return (
    <div className="bg-zinc-900/60 backdrop-blur-sm rounded-2xl border border-zinc-800 p-5 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-zinc-100">神经网络替代模型</h3>
            <p className="text-xs text-zinc-500">从仿真数据学习液滴生成规律</p>
          </div>
        </div>
        {neuralSurrogateStatus && (
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium ${
            neuralSurrogateStatus.trained
              ? 'bg-green-500/10 text-green-400 border border-green-500/30'
              : isTraining
              ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30 animate-pulse'
              : 'bg-zinc-800 text-zinc-500 border border-zinc-700'
          }`}>
            {neuralSurrogateStatus.trained ? (
              <CheckCircle size={12} />
            ) : isTraining ? (
              <RefreshCw size={12} className="animate-spin" />
            ) : (
              <Activity size={12} />
            )}
            {neuralSurrogateStatus.trained ? '已训练' : isTraining ? '训练中' : '未训练'}
          </div>
        )}
      </div>

      {neuralSurrogateStatus?.metrics && (
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-zinc-800/50 rounded-xl p-3">
            <div className="text-xs text-zinc-500 mb-1">尺寸预测MAPE</div>
            <div className="text-lg font-bold text-emerald-400">
              {neuralSurrogateStatus.metrics.size_mape.toFixed(2)}%
            </div>
          </div>
          <div className="bg-zinc-800/50 rounded-xl p-3">
            <div className="text-xs text-zinc-500 mb-1">频率预测MAPE</div>
            <div className="text-lg font-bold text-emerald-400">
              {neuralSurrogateStatus.metrics.frequency_mape.toFixed(2)}%
            </div>
          </div>
          <div className="bg-zinc-800/50 rounded-xl p-3">
            <div className="text-xs text-zinc-500 mb-1">尺寸R²</div>
            <div className="text-lg font-bold text-blue-400">
              {neuralSurrogateStatus.metrics.size_r2.toFixed(4)}
            </div>
          </div>
          <div className="bg-zinc-800/50 rounded-xl p-3">
            <div className="text-xs text-zinc-500 mb-1">频率R²</div>
            <div className="text-lg font-bold text-blue-400">
              {neuralSurrogateStatus.metrics.frequency_r2.toFixed(4)}
            </div>
          </div>
        </div>
      )}

      {neuralSurrogateStatus?.architecture && (
        <div className="bg-zinc-800/30 rounded-xl p-4">
          <div className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
            <BarChart3 size={14} />
            网络架构
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-zinc-500">总参数</span>
              <span className="text-zinc-200 font-mono">{neuralSurrogateStatus.architecture.totalParameters?.toLocaleString() || '-'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">隐藏层</span>
              <span className="text-zinc-200 font-mono">{neuralSurrogateStatus.architecture.hiddenLayers?.join(' → ') || '-'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">激活函数</span>
              <span className="text-zinc-200 font-mono">{neuralSurrogateStatus.architecture.activation || 'Leaky ReLU'}</span>
            </div>
            {neuralSurrogateStatus.metrics && (
              <div className="flex justify-between">
                <span className="text-zinc-500">训练样本</span>
                <span className="text-zinc-200 font-mono">{neuralSurrogateStatus.metrics.n_training_samples?.toLocaleString() || '-'}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {!neuralSurrogateStatus?.trained && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-zinc-500 block mb-1">训练样本数</label>
              <input
                type="number"
                value={localConfig.trainingSamples}
                onChange={(e) => setLocalConfig({ ...localConfig, trainingSamples: Number(e.target.value) })}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:border-purple-500 focus:outline-none transition-colors"
                min={1000}
                max={50000}
                step={1000}
                disabled={isTraining}
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 block mb-1">训练轮数</label>
              <input
                type="number"
                value={localConfig.epochs}
                onChange={(e) => setLocalConfig({ ...localConfig, epochs: Number(e.target.value) })}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:border-purple-500 focus:outline-none transition-colors"
                min={100}
                max={10000}
                step={100}
                disabled={isTraining}
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 block mb-1">学习率</label>
              <input
                type="number"
                value={localConfig.learningRate}
                onChange={(e) => setLocalConfig({ ...localConfig, learningRate: Number(e.target.value) })}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:border-purple-500 focus:outline-none transition-colors"
                min={0.00001}
                max={0.1}
                step={0.0001}
                disabled={isTraining}
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 block mb-1">批次大小</label>
              <input
                type="number"
                value={localConfig.batchSize}
                onChange={(e) => setLocalConfig({ ...localConfig, batchSize: Number(e.target.value) })}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:border-purple-500 focus:outline-none transition-colors"
                min={16}
                max={256}
                step={16}
                disabled={isTraining}
              />
            </div>
          </div>

          <button
            onClick={handleTrain}
            disabled={isTraining || isLoading}
            className="w-full py-2.5 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 disabled:from-zinc-700 disabled:to-zinc-700 disabled:text-zinc-500 text-white rounded-xl font-medium text-sm transition-all flex items-center justify-center gap-2"
          >
            {isTraining ? (
              <>
                <RefreshCw size={16} className="animate-spin" />
                训练中... {neuralSurrogateStatus?.trainingProgress === 0.5 ? '(异步训练)' : ''}
              </>
            ) : (
              <>
                <Play size={16} />
                开始训练
              </>
            )}
          </button>
        </div>
      )}

      {neuralSurrogateStatus?.trainingProgress !== undefined && neuralSurrogateStatus.trainingProgress >= 0 && (
        <div className="space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-zinc-500">训练进度</span>
            <span className={getProgressColor(neuralSurrogateStatus.trainingProgress)}>
              {getProgressLabel(neuralSurrogateStatus.trainingProgress)}
            </span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                neuralSurrogateStatus.trained
                  ? 'bg-gradient-to-r from-green-500 to-emerald-400'
                  : 'bg-gradient-to-r from-purple-500 to-pink-500'
              }`}
              style={{
                width: neuralSurrogateStatus.trainingProgress < 0
                  ? '100%'
                  : `${Math.max(neuralSurrogateStatus.trainingProgress * 100, neuralSurrogateStatus.trained ? 100 : 5)}%`
              }}
            />
          </div>
        </div>
      )}

      {neuralSurrogateStatus?.trained && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <div className="font-medium text-blue-300 mb-1">模型已就绪</div>
              <div className="text-blue-400/80 text-xs">
                切换到"神经网络模型"模式即可使用训练好的模型进行快速预测。预测速度比经验模型快10-100倍。
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
