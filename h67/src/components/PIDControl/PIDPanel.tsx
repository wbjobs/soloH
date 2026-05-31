import React, { useState } from 'react';
import { Settings, Target } from 'lucide-react';
import { ToggleSwitch, NumberInput, SliderInput } from '../ui/NumberInput';
import { SectionHeader } from '../ui/SectionHeader';
import { PIDParameters, PIDStatus } from '../../types';

interface PIDPanelProps {
  parameters: PIDParameters;
  pidStatus?: PIDStatus;
  onChange: (params: PIDParameters) => void;
  disabled?: boolean;
}

export const PIDPanel: React.FC<PIDPanelProps> = ({
  parameters,
  pidStatus,
  onChange,
  disabled = false
}) => {
  const [isOpen, setIsOpen] = useState(true);

  const updateParam = (field: keyof PIDParameters, value: number | boolean) => {
    onChange({
      ...parameters,
      [field]: value
    });
  };

  return (
    <div className="border border-zinc-700/50 rounded-xl bg-zinc-900/50 backdrop-blur-sm overflow-hidden">
      <div className="px-4">
        <SectionHeader
          title="PID 反馈控制"
          icon={<Settings size={20} />}
          isOpen={isOpen}
          onToggle={() => setIsOpen(!isOpen)}
        />
      </div>

      {isOpen && (
        <div className="px-4 pb-4 space-y-4">
          <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg">
            <ToggleSwitch
              label="启用PID控制"
              checked={parameters.enabled}
              onChange={(v) => updateParam('enabled', v)}
              disabled={disabled}
            />
            {parameters.enabled && (
              <span className="px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded-full font-medium">
                运行中
              </span>
            )}
          </div>

          {parameters.enabled && (
            <>
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wider">控制目标</h4>
                <NumberInput
                  label="目标液滴尺寸"
                  value={parameters.targetDropletSize}
                  unit="μm"
                  min={10}
                  max={500}
                  step={1}
                  onChange={(v) => updateParam('targetDropletSize', v)}
                  disabled={disabled}
                />
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider">PID 参数</h4>
                <SliderInput
                  label="比例系数 Kp"
                  value={parameters.Kp}
                  unit=""
                  min={0}
                  max={10}
                  step={0.01}
                  onChange={(v) => updateParam('Kp', v)}
                  disabled={disabled}
                />
                <SliderInput
                  label="积分系数 Ki"
                  value={parameters.Ki}
                  unit=""
                  min={0}
                  max={5}
                  step={0.01}
                  onChange={(v) => updateParam('Ki', v)}
                  disabled={disabled}
                />
                <SliderInput
                  label="微分系数 Kd"
                  value={parameters.Kd}
                  unit=""
                  min={0}
                  max={2}
                  step={0.001}
                  onChange={(v) => updateParam('Kd', v)}
                  disabled={disabled}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <NumberInput
                  label="最小输出"
                  value={parameters.outputMin}
                  unit="μL/min"
                  min={0.1}
                  max={100}
                  step={0.1}
                  onChange={(v) => updateParam('outputMin', v)}
                  disabled={disabled}
                />
                <NumberInput
                  label="最大输出"
                  value={parameters.outputMax}
                  unit="μL/min"
                  min={1}
                  max={500}
                  step={0.1}
                  onChange={(v) => updateParam('outputMax', v)}
                  disabled={disabled}
                />
              </div>

              {pidStatus && (
                <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg space-y-2">
                  <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wider flex items-center gap-2">
                    <Target size={14} />
                    实时状态
                  </h4>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-zinc-400">当前尺寸:</span>
                      <span className="text-white font-mono">{pidStatus.currentSize.toFixed(2)} μm</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">目标尺寸:</span>
                      <span className="text-blue-400 font-mono">{pidStatus.targetSize.toFixed(2)} μm</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">误差:</span>
                      <span className={`font-mono ${Math.abs(pidStatus.error) < 1 ? 'text-green-400' : 'text-amber-400'}`}>
                        {pidStatus.error.toFixed(2)} μm
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">控制输出:</span>
                      <span className="text-white font-mono">{pidStatus.controlOutput.toFixed(2)} μL/min</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">积分项:</span>
                      <span className="text-zinc-300 font-mono">{pidStatus.integralTerm.toFixed(3)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">微分项:</span>
                      <span className="text-zinc-300 font-mono">{pidStatus.derivativeTerm.toFixed(3)}</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};
