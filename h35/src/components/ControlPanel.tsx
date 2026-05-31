import React from 'react';
import {
  Settings,
  Play,
  RotateCcw,
  Thermometer,
  Ruler,
  Zap,
  Layers,
  Activity,
  Waves,
  GitBranch,
  Target,
  BarChart3,
} from 'lucide-react';
import { useSimulationStore } from '../store/simulationStore';
import { CRYSTAL_DATABASE } from '../data/crystals';
import type { SimulationParams } from '../types';

const InputField: React.FC<{
  label: string;
  value: number;
  onChange: (value: number) => void;
  unit: string;
  min?: number;
  max?: number;
  step?: number;
}> = ({ label, value, onChange, unit, min, max, step = 1 }) => (
  <div className="mb-3">
    <label className="block text-xs text-gray-400 mb-1">{label}</label>
    <div className="flex items-center gap-2">
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        min={min}
        max={max}
        step={step}
        className="flex-1 bg-gray-800/50 border border-gray-700 rounded px-3 py-2 text-sm font-mono text-cyan-400 focus:outline-none focus:border-cyan-500 transition-colors"
      />
      <span className="text-xs text-gray-500 w-12">{unit}</span>
    </div>
  </div>
);

const SelectField: React.FC<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}> = ({ label, value, onChange, options }) => (
  <div className="mb-3">
    <label className="block text-xs text-gray-400 mb-1">{label}</label>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full bg-gray-800/50 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500 transition-colors appearance-none cursor-pointer"
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  </div>
);

const CheckboxField: React.FC<{
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}> = ({ label, checked, onChange }) => (
  <div className="mb-3 flex items-center gap-2">
    <input
      type="checkbox"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      className="w-4 h-4 accent-cyan-500 cursor-pointer"
    />
    <label className="text-sm text-gray-300 cursor-pointer">{label}</label>
  </div>
);

const Section: React.FC<{
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}> = ({ title, icon, children, defaultOpen = true }) => {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);

  return (
    <div className="mb-4 border border-gray-700/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 px-4 py-3 bg-gray-800/30 hover:bg-gray-800/50 transition-colors"
      >
        <span className="text-cyan-400">{icon}</span>
        <span className="text-sm font-medium text-white flex-1 text-left">{title}</span>
        <span className="text-gray-500 text-sm">{isOpen ? '−' : '+'}</span>
      </button>
      {isOpen && <div className="p-4 border-t border-gray-700/50">{children}</div>}
    </div>
  );
};

export const ControlPanel: React.FC = () => {
  const {
    params,
    isCalculating,
    calculationProgress,
    error,
    setParams,
    resetParams,
    calculateAll,
    calculatePhaseMatching,
    calculateCoupledWave,
    calculateEfficiencyCurve,
    generateDomainStructure,
    generateFieldDistribution,
    calculateSpectrum,
    calculateCascade,
    calculateNoncollinear,
    calculateMonteCarlo,
    clearError,
  } = useSimulationStore();

  const handleParamChange = <K extends keyof SimulationParams>(
    key: K,
    value: SimulationParams[K]
  ) => {
    setParams({ [key]: value } as Partial<SimulationParams>);
  };

  return (
    <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm text-red-400">{error}</span>
            <button
              onClick={clearError}
              className="text-red-400 hover:text-red-300 text-sm"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <div className="flex gap-2 mb-4">
        <button
          onClick={calculateAll}
          disabled={isCalculating}
          className="flex-1 flex items-center justify-center gap-2 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 disabled:from-gray-600 disabled:to-gray-600 text-white font-medium py-3 px-4 rounded-lg transition-all shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40 disabled:shadow-none"
        >
          <Play size={18} />
          <span>{isCalculating ? '计算中...' : '开始计算'}</span>
        </button>
        <button
          onClick={resetParams}
          disabled={isCalculating}
          className="flex items-center justify-center p-3 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-white rounded-lg transition-colors"
        >
          <RotateCcw size={18} />
        </button>
      </div>

      {isCalculating && (
        <div className="mb-4">
          <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 transition-all duration-300"
              style={{ width: `${calculationProgress * 100}%` }}
            />
          </div>
          <div className="text-center text-xs text-gray-500 mt-1">
            {Math.round(calculationProgress * 100)}%
          </div>
        </div>
      )}

      <Section title="激光参数" icon={<Zap size={16} />}>
        <InputField
          label="泵浦光波长"
          value={params.pumpWavelength}
          onChange={(v) => handleParamChange('pumpWavelength', v)}
          unit="nm"
          min={200}
          max={5000}
          step={1}
        />
        <div className="grid grid-cols-2 gap-2">
          <InputField
            label="信号光最小波长"
            value={params.signalWavelengthMin}
            onChange={(v) => handleParamChange('signalWavelengthMin', v)}
            unit="nm"
            min={200}
            max={10000}
            step={1}
          />
          <InputField
            label="信号光最大波长"
            value={params.signalWavelengthMax}
            onChange={(v) => handleParamChange('signalWavelengthMax', v)}
            unit="nm"
            min={200}
            max={10000}
            step={1}
          />
        </div>
        <InputField
          label="波长扫描步长"
          value={params.signalWavelengthStep}
          onChange={(v) => handleParamChange('signalWavelengthStep', v)}
          unit="nm"
          min={0.1}
          max={100}
          step={0.1}
        />
        <div className="grid grid-cols-2 gap-2">
          <InputField
            label="泵浦光功率"
            value={params.pumpPower}
            onChange={(v) => handleParamChange('pumpPower', v)}
            unit="W"
            min={0.001}
            max={100}
            step={0.1}
          />
          <InputField
            label="信号光功率"
            value={params.signalPower}
            onChange={(v) => handleParamChange('signalPower', v)}
            unit="W"
            min={0}
            max={10}
            step={0.001}
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <InputField
            label="泵浦光腰半径"
            value={params.pumpWaist}
            onChange={(v) => handleParamChange('pumpWaist', v)}
            unit="μm"
            min={1}
            max={500}
            step={1}
          />
          <InputField
            label="信号光腰半径"
            value={params.signalWaist}
            onChange={(v) => handleParamChange('signalWaist', v)}
            unit="μm"
            min={1}
            max={500}
            step={1}
          />
        </div>
      </Section>

      <Section title="晶体参数" icon={<Layers size={16} />}>
        <SelectField
          label="晶体材料"
          value={params.crystalId}
          onChange={(v) => handleParamChange('crystalId', v)}
          options={CRYSTAL_DATABASE.map((c) => ({
            value: c.id,
            label: c.name,
          }))}
        />
        <InputField
          label="晶体长度"
          value={params.crystalLength}
          onChange={(v) => handleParamChange('crystalLength', v)}
          unit="mm"
          min={0.1}
          max={100}
          step={0.1}
        />
        <InputField
          label="工作温度"
          value={params.temperature}
          onChange={(v) => handleParamChange('temperature', v)}
          unit="°C"
          min={-50}
          max={300}
          step={1}
        />
        <div className="grid grid-cols-2 gap-2">
          <InputField
            label="极角 θ"
            value={params.angleTheta}
            onChange={(v) => handleParamChange('angleTheta', v)}
            unit="°"
            min={0}
            max={90}
            step={0.1}
          />
          <InputField
            label="方位角 φ"
            value={params.anglePhi}
            onChange={(v) => handleParamChange('anglePhi', v)}
            unit="°"
            min={0}
            max={360}
            step={0.1}
          />
        </div>
        <SelectField
          label="相位匹配类型"
          value={params.phaseMatchType}
          onChange={(v) => handleParamChange('phaseMatchType', v as 'type1' | 'type2')}
          options={[
            { value: 'type1', label: 'I类 (e + e → o)' },
            { value: 'type2', label: 'II类 (e + o → e)' },
          ]}
        />
      </Section>

      <Section title="周期极化设计" icon={<Ruler size={16} />}>
        <SelectField
          label="极化结构类型"
          value={params.polingType}
          onChange={(v) =>
            handleParamChange('polingType', v as SimulationParams['polingType'])
          }
          options={[
            { value: 'uniform', label: '一维均匀周期' },
            { value: 'linear_chirp', label: '一维线性啁啾' },
            { value: 'quadratic_chirp', label: '一维二次啁啾' },
            { value: 'fan', label: '扇形结构' },
            { value: '2d', label: '二维周期极化' },
          ]}
        />
        <InputField
          label="极化周期"
          value={params.polingPeriod}
          onChange={(v) => handleParamChange('polingPeriod', v)}
          unit="μm"
          min={1}
          max={100}
          step={0.1}
        />
        <InputField
          label="占空比"
          value={params.dutyCycle}
          onChange={(v) => handleParamChange('dutyCycle', v)}
          unit=""
          min={0.1}
          max={0.9}
          step={0.01}
        />
        {(params.polingType === 'linear_chirp' ||
          params.polingType === 'quadratic_chirp' ||
          params.polingType === 'fan') && (
          <InputField
            label="啁啾率"
            value={params.chirpRate}
            onChange={(v) => handleParamChange('chirpRate', v)}
            unit="%/cm"
            min={-100}
            max={100}
            step={0.1}
          />
        )}
        {params.polingType === 'quadratic_chirp' && (
          <InputField
            label="二次啁啾率"
            value={params.quadraticChirpRate}
            onChange={(v) => handleParamChange('quadraticChirpRate', v)}
            unit="%/cm²"
            min={-10}
            max={10}
            step={0.001}
          />
        )}
      </Section>

      <Section title="级联非线性过程" icon={<GitBranch size={16} />} defaultOpen={false}>
        <CheckboxField
          label="启用级联过程"
          checked={params.enableCascade}
          onChange={(v) => handleParamChange('enableCascade', v)}
        />
        {params.enableCascade && (
          <>
            <SelectField
              label="级联过程类型"
              value={params.cascadeProcess}
              onChange={(v) =>
                handleParamChange('cascadeProcess', v as SimulationParams['cascadeProcess'])
              }
              options={[
                { value: 'opo', label: 'OPO: 泵浦→信号+闲频' },
                { value: 'shg_signal', label: 'SHG: 信号光倍频' },
                { value: 'shg_idler', label: 'SHG: 闲频光倍频' },
                { value: 'sfg_pump_signal', label: 'SFG: 泵浦+信号和频' },
                { value: 'full_cascade', label: '完整级联: 泵浦→信号→闲频→倍频' },
              ]}
            />
            <InputField
              label="级联效率阈值"
              value={params.cascadeEfficiencyThreshold}
              onChange={(v) => handleParamChange('cascadeEfficiencyThreshold', v)}
              unit="%"
              min={0.1}
              max={50}
              step={0.1}
            />
          </>
        )}
      </Section>

      <Section title="非共线相位匹配" icon={<Target size={16} />} defaultOpen={false}>
        <SelectField
          label="非共线配置"
          value={params.noncollinearConfig}
          onChange={(v) =>
            handleParamChange('noncollinearConfig', v as SimulationParams['noncollinearConfig'])
          }
          options={[
            { value: 'collinear', label: '共线' },
            { value: 'noncollinear_signal', label: '仅信号光非共线' },
            { value: 'noncollinear_idler', label: '仅闲频光非共线' },
            { value: 'noncollinear_both', label: '信号光+闲频光非共线' },
          ]}
        />
        {(params.noncollinearConfig === 'noncollinear_signal' ||
          params.noncollinearConfig === 'noncollinear_both') && (
          <InputField
            label="信号光非共线角"
            value={params.noncollinearAngleSignal}
            onChange={(v) => handleParamChange('noncollinearAngleSignal', v)}
            unit="°"
            min={0}
            max={10}
            step={0.1}
          />
        )}
        {(params.noncollinearConfig === 'noncollinear_idler' ||
          params.noncollinearConfig === 'noncollinear_both') && (
          <InputField
            label="闲频光非共线角"
            value={params.noncollinearAngleIdler}
            onChange={(v) => handleParamChange('noncollinearAngleIdler', v)}
            unit="°"
            min={0}
            max={10}
            step={0.1}
          />
        )}
      </Section>

      <Section title="蒙特卡洛误差分析" icon={<BarChart3 size={16} />} defaultOpen={false}>
        <CheckboxField
          label="启用蒙特卡洛分析"
          checked={params.enableMonteCarlo}
          onChange={(v) => handleParamChange('enableMonteCarlo', v)}
        />
        {params.enableMonteCarlo && (
          <>
            <InputField
              label="试验次数"
              value={params.monteCarloTrials}
              onChange={(v) => handleParamChange('monteCarloTrials', Math.round(v))}
              unit="次"
              min={10}
              max={5000}
              step={10}
            />
            <InputField
              label="畴周期涨落标准差"
              value={params.periodFluctuationStd}
              onChange={(v) => handleParamChange('periodFluctuationStd', v)}
              unit="%"
              min={0}
              max={20}
              step={0.1}
            />
            <InputField
              label="占空比涨落标准差"
              value={params.dutyCycleFluctuationStd}
              onChange={(v) => handleParamChange('dutyCycleFluctuationStd', v)}
              unit="%"
              min={0}
              max={10}
              step={0.1}
            />
            <InputField
              label="温度涨落标准差"
              value={params.temperatureFluctuationStd}
              onChange={(v) => handleParamChange('temperatureFluctuationStd', v)}
              unit="°C"
              min={0}
              max={10}
              step={0.1}
            />
          </>
        )}
      </Section>

      <Section title="快捷操作" icon={<Settings size={16} />} defaultOpen={false}>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={calculatePhaseMatching}
            disabled={isCalculating}
            className="flex items-center justify-center gap-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-white py-2 px-3 rounded transition-colors"
          >
            <Activity size={14} />
            相位匹配
          </button>
          <button
            onClick={calculateCoupledWave}
            disabled={isCalculating}
            className="flex items-center justify-center gap-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-white py-2 px-3 rounded transition-colors"
          >
            <Waves size={14} />
            耦合波
          </button>
          <button
            onClick={calculateEfficiencyCurve}
            disabled={isCalculating}
            className="flex items-center justify-center gap-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-white py-2 px-3 rounded transition-colors"
          >
            <Activity size={14} />
            效率曲线
          </button>
          <button
            onClick={generateDomainStructure}
            disabled={isCalculating}
            className="flex items-center justify-center gap-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-white py-2 px-3 rounded transition-colors"
          >
            <Layers size={14} />
            畴结构
          </button>
          <button
            onClick={generateFieldDistribution}
            disabled={isCalculating}
            className="flex items-center justify-center gap-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-white py-2 px-3 rounded transition-colors"
          >
            <Zap size={14} />
            场分布
          </button>
          <button
            onClick={calculateSpectrum}
            disabled={isCalculating}
            className="flex items-center justify-center gap-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-white py-2 px-3 rounded transition-colors"
          >
            <Waves size={14} />
            频谱
          </button>
          <button
            onClick={calculateCascade}
            disabled={isCalculating || !params.enableCascade}
            className="flex items-center justify-center gap-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-white py-2 px-3 rounded transition-colors"
          >
            <GitBranch size={14} />
            级联
          </button>
          <button
            onClick={calculateNoncollinear}
            disabled={isCalculating || params.noncollinearConfig === 'collinear'}
            className="flex items-center justify-center gap-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-white py-2 px-3 rounded transition-colors"
          >
            <Target size={14} />
            非共线
          </button>
          <button
            onClick={calculateMonteCarlo}
            disabled={isCalculating || !params.enableMonteCarlo}
            className="flex items-center justify-center gap-1 text-xs bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 text-white py-2 px-3 rounded transition-colors"
          >
            <BarChart3 size={14} />
            蒙特卡洛
          </button>
        </div>
      </Section>
    </div>
  );
};
