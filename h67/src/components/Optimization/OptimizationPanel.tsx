import React, { useState } from 'react';
import { TrendingUp, Play, Square, CheckCircle } from 'lucide-react';
import { NumberInput, SliderInput, SelectInput } from '../ui/NumberInput';
import { SectionHeader } from '../ui/SectionHeader';
import { OptimizationConfig, OptimizationStatus, OptimizationResult } from '../../types';

interface OptimizationPanelProps {
  status: OptimizationStatus | null;
  onStart: (config: OptimizationConfig) => void;
  onStop: () => void;
  onApplyResult: (result: OptimizationResult) => void;
  disabled?: boolean;
}

export const OptimizationPanel: React.FC<OptimizationPanelProps> = ({
  status,
  onStart,
  onStop,
  onApplyResult,
  disabled = false
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const [config, setConfig] = useState<OptimizationConfig>({
    targetSize: 80.0,
    continuousFlowRateRange: [5.0, 50.0],
    dispersedFlowRateRange: [1.0, 20.0],
    resolution: 10,
    objective: 'minimize_error'
  });

  const updateConfig = (field: keyof OptimizationConfig, value: any) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const updateRange = (field: 'continuousFlowRateRange' | 'dispersedFlowRateRange', index: number, value: number) => {
    setConfig(prev => {
      const range = [...prev[field]] as [number, number];
      range[index] = value;
      return { ...prev, [field]: range };
    });
  };

  const handleStart = () => {
    onStart(config);
  };

  return (
    <div className="border border-zinc-700/50 rounded-xl bg-zinc-900/50 backdrop-blur-sm overflow-hidden">
      <div className="px-4">
        <SectionHeader
          title="批量参数优化"
          icon={<TrendingUp size={20} />}
          isOpen={isOpen}
          onToggle={() => setIsOpen(!isOpen)}
        />
      </div>

      {isOpen && (
        <div className="px-4 pb-4 space-y-4">
          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-green-400 uppercase tracking-wider">优化目标</h4>
            <div className="grid grid-cols-2 gap-3">
              <NumberInput
                label="目标液滴尺寸"
                value={config.targetSize}
                unit="μm"
                min={10}
                max={500}
                step={1}
                onChange={(v) => updateConfig('targetSize', v)}
                disabled={disabled || status?.running}
              />
              <SelectInput
                label="优化目标"
                value={config.objective}
                options={[
                  { value: 'minimize_error', label: '最小化尺寸误差' },
                  { value: 'maximize_frequency', label: '最大化生成频率' },
                  { value: 'minimize_polydispersity', label: '最小化多分散性' }
                ]}
                onChange={(v) => updateConfig('objective', v)}
                disabled={disabled || status?.running}
              />
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wider">连续相流速范围</h4>
            <div className="grid grid-cols-2 gap-3">
              <NumberInput
                label="最小值"
                value={config.continuousFlowRateRange[0]}
                unit="μL/min"
                min={0.1}
                max={1000}
                step={0.1}
                onChange={(v) => updateRange('continuousFlowRateRange', 0, v)}
                disabled={disabled || status?.running}
              />
              <NumberInput
                label="最大值"
                value={config.continuousFlowRateRange[1]}
                unit="μL/min"
                min={0.1}
                max={1000}
                step={0.1}
                onChange={(v) => updateRange('continuousFlowRateRange', 1, v)}
                disabled={disabled || status?.running}
              />
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider">离散相流速范围</h4>
            <div className="grid grid-cols-2 gap-3">
              <NumberInput
                label="最小值"
                value={config.dispersedFlowRateRange[0]}
                unit="μL/min"
                min={0.1}
                max={500}
                step={0.1}
                onChange={(v) => updateRange('dispersedFlowRateRange', 0, v)}
                disabled={disabled || status?.running}
              />
              <NumberInput
                label="最大值"
                value={config.dispersedFlowRateRange[1]}
                unit="μL/min"
                min={0.1}
                max={500}
                step={0.1}
                onChange={(v) => updateRange('dispersedFlowRateRange', 1, v)}
                disabled={disabled || status?.running}
              />
            </div>
          </div>

          <div>
            <SliderInput
              label="采样分辨率"
              value={config.resolution}
              unit="点"
              min={3}
              max={30}
              step={1}
              onChange={(v) => updateConfig('resolution', Math.round(v))}
              disabled={disabled || status?.running}
            />
            <p className="text-xs text-zinc-500 mt-1">
              总迭代次数: {config.resolution * config.resolution}
            </p>
          </div>

          <div className="flex gap-2">
            {!status?.running ? (
              <button
                onClick={handleStart}
                disabled={disabled}
                className="flex-1 flex items-center justify-center gap-2 bg-green-600 hover:bg-green-500 disabled:bg-zinc-700 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-lg transition-all"
              >
                <Play size={16} />
                开始优化
              </button>
            ) : (
              <button
                onClick={onStop}
                className="flex-1 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-500 text-white font-medium py-2 px-4 rounded-lg transition-all"
              >
                <Square size={16} />
                停止优化
              </button>
            )}
          </div>

          {status && (
            <div className="space-y-3">
              <div className="p-3 bg-zinc-800/50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-zinc-400">优化进度</span>
                  <span className="text-xs text-zinc-300 font-mono">
                    {status.completedIterations} / {status.totalIterations}
                  </span>
                </div>
                <div className="w-full h-2 bg-zinc-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-green-500 transition-all duration-300"
                    style={{ width: `${(status.progress * 100).toFixed(1)}%` }}
                  />
                </div>
              </div>

              {status.bestResult && (
                <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg space-y-2">
                  <h4 className="text-xs font-semibold text-green-400 uppercase tracking-wider flex items-center gap-2">
                    <CheckCircle size={14} />
                    最优结果
                  </h4>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-zinc-400">连续相流速:</span>
                      <span className="text-white font-mono">{status.bestResult.continuousFlowRate.toFixed(2)} μL/min</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">离散相流速:</span>
                      <span className="text-white font-mono">{status.bestResult.dispersedFlowRate.toFixed(2)} μL/min</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">液滴尺寸:</span>
                      <span className="text-blue-400 font-mono">{status.bestResult.dropletSize.toFixed(2)} μm</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">生成频率:</span>
                      <span className="text-amber-400 font-mono">{status.bestResult.frequency.toFixed(2)} Hz</span>
                    </div>
                    <div className="flex justify-between col-span-2">
                      <span className="text-zinc-400">误差:</span>
                      <span className="text-green-400 font-mono">{status.bestResult.error.toFixed(3)}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => onApplyResult(status.bestResult!)}
                    disabled={disabled}
                    className="w-full mt-2 py-2 bg-green-600 hover:bg-green-500 disabled:bg-zinc-700 text-white text-sm font-medium rounded-lg transition-all"
                  >
                    应用此参数组合
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
