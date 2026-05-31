import React, { useState } from 'react';
import { Droplets, ChevronDown, ChevronRight } from 'lucide-react';
import { NumberInput, SelectInput } from '../ui/NumberInput';
import { SectionHeader } from '../ui/SectionHeader';
import { SimulationParameters, JunctionType } from '../../types';

interface FluidPropertiesProps {
  parameters: SimulationParameters;
  onChange: (params: SimulationParameters) => void;
  disabled?: boolean;
}

export const FluidProperties: React.FC<FluidPropertiesProps> = ({
  parameters,
  onChange,
  disabled = false
}) => {
  const [isOpen, setIsOpen] = useState(true);

  const updateContinuous = (field: string, value: number) => {
    onChange({
      ...parameters,
      continuousPhase: {
        ...parameters.continuousPhase,
        [field]: value
      }
    });
  };

  const updateDispersed = (field: string, value: number) => {
    onChange({
      ...parameters,
      dispersedPhase: {
        ...parameters.dispersedPhase,
        [field]: value
      }
    });
  };

  const updateChannel = (field: string, value: number | string) => {
    onChange({
      ...parameters,
      channel: {
        ...parameters.channel,
        [field]: value
      }
    });
  };

  return (
    <div className="border border-zinc-700/50 rounded-xl bg-zinc-900/50 backdrop-blur-sm overflow-hidden">
      <div className="px-4">
        <SectionHeader
          title="流体物性与通道几何"
          icon={<Droplets size={20} />}
          isOpen={isOpen}
          onToggle={() => setIsOpen(!isOpen)}
        />
      </div>

      {isOpen && (
        <div className="px-4 pb-4 space-y-6">
          <div className="space-y-4">
            <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wider">连续相 (水)</h4>
            <div className="grid grid-cols-2 gap-3">
              <NumberInput
                label="流速"
                value={parameters.continuousPhase.flowRate}
                unit="μL/min"
                min={0.1}
                max={1000}
                step={0.1}
                onChange={(v) => updateContinuous('flowRate', v)}
                disabled={disabled}
              />
              <NumberInput
                label="粘度"
                value={parameters.continuousPhase.viscosity}
                unit="mPa·s"
                min={0.1}
                max={1000}
                step={0.1}
                onChange={(v) => updateContinuous('viscosity', v)}
                disabled={disabled}
              />
              <NumberInput
                label="密度"
                value={parameters.continuousPhase.density}
                unit="kg/m³"
                min={500}
                max={3000}
                step={10}
                onChange={(v) => updateContinuous('density', v)}
                disabled={disabled}
              />
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider">离散相 (油)</h4>
            <div className="grid grid-cols-2 gap-3">
              <NumberInput
                label="流速"
                value={parameters.dispersedPhase.flowRate}
                unit="μL/min"
                min={0.1}
                max={500}
                step={0.1}
                onChange={(v) => updateDispersed('flowRate', v)}
                disabled={disabled}
              />
              <NumberInput
                label="粘度"
                value={parameters.dispersedPhase.viscosity}
                unit="mPa·s"
                min={0.1}
                max={1000}
                step={0.1}
                onChange={(v) => updateDispersed('viscosity', v)}
                disabled={disabled}
              />
              <NumberInput
                label="密度"
                value={parameters.dispersedPhase.density}
                unit="kg/m³"
                min={500}
                max={3000}
                step={10}
                onChange={(v) => updateDispersed('density', v)}
                disabled={disabled}
              />
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="text-xs font-semibold text-green-400 uppercase tracking-wider">界面张力</h4>
            <NumberInput
              label="界面张力系数"
              value={parameters.interfacialTension}
              unit="mN/m"
              min={1}
              max={100}
              step={0.5}
              onChange={(v) => onChange({ ...parameters, interfacialTension: v })}
              disabled={disabled}
            />
          </div>

          <div className="space-y-4">
            <h4 className="text-xs font-semibold text-purple-400 uppercase tracking-wider">通道几何参数</h4>
            <div className="grid grid-cols-2 gap-3">
              <NumberInput
                label="通道宽度"
                value={parameters.channel.width}
                unit="μm"
                min={10}
                max={1000}
                step={1}
                onChange={(v) => updateChannel('width', v)}
                disabled={disabled}
              />
              <NumberInput
                label="通道高度"
                value={parameters.channel.height}
                unit="μm"
                min={5}
                max={500}
                step={1}
                onChange={(v) => updateChannel('height', v)}
                disabled={disabled}
              />
              <NumberInput
                label="通道长度"
                value={parameters.channel.length}
                unit="μm"
                min={100}
                max={10000}
                step={10}
                onChange={(v) => updateChannel('length', v)}
                disabled={disabled}
              />
              <SelectInput
                label="交汇类型"
                value={parameters.channel.junctionType}
                options={[
                  { value: 'T', label: 'T型交叉' },
                  { value: 'flow-focusing', label: '流动聚焦' },
                  { value: 'co-flow', label: '共流' }
                ]}
                onChange={(v) => updateChannel('junctionType', v as JunctionType)}
                disabled={disabled}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
