import React, { useState } from 'react';
import { Activity, AlertTriangle } from 'lucide-react';
import { ToggleSwitch, NumberInput, SliderInput, SelectInput } from '../ui/NumberInput';
import { SectionHeader } from '../ui/SectionHeader';
import { PerturbationConfig, PerturbationType, PerturbationPhase } from '../../types';

interface PerturbationPanelProps {
  config: PerturbationConfig;
  onChange: (config: PerturbationConfig) => void;
  disabled?: boolean;
}

export const PerturbationPanel: React.FC<PerturbationPanelProps> = ({
  config,
  onChange,
  disabled = false
}) => {
  const [isOpen, setIsOpen] = useState(true);

  const updateConfig = (field: keyof PerturbationConfig, value: any) => {
    onChange({
      ...config,
      [field]: value
    });
  };

  return (
    <div className="border border-zinc-700/50 rounded-xl bg-zinc-900/50 backdrop-blur-sm overflow-hidden">
      <div className="px-4">
        <SectionHeader
          title="流速扰动分析"
          icon={<Activity size={20} />}
          isOpen={isOpen}
          onToggle={() => setIsOpen(!isOpen)}
        />
      </div>

      {isOpen && (
        <div className="px-4 pb-4 space-y-4">
          <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg">
            <ToggleSwitch
              label="启用流速扰动"
              checked={config.enabled}
              onChange={(v) => updateConfig('enabled', v)}
              disabled={disabled}
            />
            {config.enabled && (
              <span className="px-2 py-1 bg-amber-500/20 text-amber-400 text-xs rounded-full font-medium flex items-center gap-1">
                <AlertTriangle size={12} />
                扰动中
              </span>
            )}
          </div>

          {config.enabled && (
            <>
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                <p className="text-xs text-amber-300">
                  扰动将应用于指定相的流速，用于分析系统的鲁棒性和稳定性。
                </p>
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider">扰动设置</h4>
                <SelectInput
                  label="扰动类型"
                  value={config.type}
                  options={[
                    { value: 'sinusoidal', label: '正弦波动' },
                    { value: 'step', label: '阶跃变化' },
                    { value: 'random', label: '随机噪声' }
                  ]}
                  onChange={(v) => updateConfig('type', v as PerturbationType)}
                  disabled={disabled}
                />
                <SelectInput
                  label="施加相位"
                  value={config.phase}
                  options={[
                    { value: 'continuous', label: '仅连续相' },
                    { value: 'dispersed', label: '仅离散相' },
                    { value: 'both', label: '两相同时' }
                  ]}
                  onChange={(v) => updateConfig('phase', v as PerturbationPhase)}
                  disabled={disabled}
                />
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-purple-400 uppercase tracking-wider">扰动参数</h4>
                <SliderInput
                  label="扰动幅值"
                  value={config.amplitude}
                  unit="%"
                  min={0}
                  max={100}
                  step={1}
                  onChange={(v) => updateConfig('amplitude', v)}
                  disabled={disabled}
                />
                {config.type !== 'step' && (
                  <SliderInput
                    label="扰动频率"
                    value={config.frequency}
                    unit="Hz"
                    min={0.01}
                    max={10}
                    step={0.01}
                    onChange={(v) => updateConfig('frequency', v)}
                    disabled={disabled}
                  />
                )}
              </div>

              {config.type === 'sinusoidal' && (
                <div className="p-3 bg-zinc-800/50 rounded-lg">
                  <p className="text-xs text-zinc-400 mb-2">扰动公式:</p>
                  <p className="text-xs font-mono text-zinc-300">
                    Q(t) = Q₀ × [1 + A × sin(2πft)]
                  </p>
                  <div className="mt-2 text-xs text-zinc-500">
                    <p>Q₀: 基础流速, A: {config.amplitude}%, f: {config.frequency} Hz</p>
                  </div>
                </div>
              )}

              {config.type === 'step' && (
                <div className="p-3 bg-zinc-800/50 rounded-lg">
                  <p className="text-xs text-zinc-400 mb-2">扰动特性:</p>
                  <p className="text-xs text-zinc-300">
                    仿真开始1秒后，流速将产生 {config.amplitude}% 的阶跃变化
                  </p>
                </div>
              )}

              {config.type === 'random' && (
                <div className="p-3 bg-zinc-800/50 rounded-lg">
                  <p className="text-xs text-zinc-400 mb-2">扰动特性:</p>
                  <p className="text-xs text-zinc-300">
                    在 ±{config.amplitude}% 范围内产生随机噪声扰动
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};
