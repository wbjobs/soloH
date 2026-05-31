import { useState } from 'react';
import { Play, RotateCcw, ChevronDown, ChevronUp, Atom, Layers, Zap, Calculator } from 'lucide-react';
import { useAppStore } from '../store';
import { SliderInput } from '../components/forms/SliderInput';
import { SelectInput } from '../components/forms/SelectInput';
import { MaterialParamsDisplay } from '../components/forms/MaterialParamsDisplay';
import { DeviceStructurePreview } from '../components/forms/DeviceStructurePreview';
import type { QDMaterial, TransportLayerMaterial, ElectrodeMaterial } from '../types';

interface CollapsibleSectionProps {
  title: string;
  icon: typeof Atom;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function CollapsibleSection({ title, icon: Icon, children, defaultOpen = true }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="glass-card overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-5 py-4 flex items-center justify-between bg-space-900/50 hover:bg-space-800/50 transition-colors duration-300"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-quantum-400/20 flex items-center justify-center">
            <Icon className="w-4 h-4 text-quantum-400" />
          </div>
          <span className="font-semibold text-slate-200">{title}</span>
        </div>
        {isOpen ? (
          <ChevronUp className="w-5 h-5 text-slate-500" />
        ) : (
          <ChevronDown className="w-5 h-5 text-slate-500" />
        )}
      </button>
      {isOpen && (
        <div className="p-5 space-y-5 animate-fade-in">
          {children}
        </div>
      )}
    </div>
  );
}

export function ParamsPage() {
  const { inputParams, setInputParams, runSimulation, resetParams, progress } = useAppStore();

  const qdMaterialOptions: { value: QDMaterial; label: string }[] = [
    { value: 'CdSe', label: '硒化镉 (CdSe)' },
    { value: 'InP', label: '磷化铟 (InP)' },
    { value: 'Perovskite', label: '钙钛矿 (MAPbI3)' },
    { value: 'CdS', label: '硫化镉 (CdS)' },
    { value: 'ZnS', label: '硫化锌 (ZnS)' },
  ];

  const shellMaterialOptions: { value: QDMaterial; label: string }[] = [
    { value: 'ZnS', label: '硫化锌 (ZnS)' },
    { value: 'CdS', label: '硫化镉 (CdS)' },
    { value: 'CdSe', label: '硒化镉 (CdSe)' },
  ];

  const htlOptions: { value: TransportLayerMaterial; label: string }[] = [
    { value: 'PEDOT:PSS', label: 'PEDOT:PSS' },
    { value: 'PVK', label: 'PVK' },
    { value: 'TPD', label: 'TPD' },
    { value: 'PBDB-T', label: 'PBDB-T' },
  ];

  const etlOptions: { value: TransportLayerMaterial; label: string }[] = [
    { value: 'ZnO', label: '氧化锌 (ZnO)' },
    { value: 'TiO2', label: '二氧化钛 (TiO2)' },
    { value: 'PCBM', label: 'PCBM' },
  ];

  const electrodeOptions: { value: ElectrodeMaterial; label: string }[] = [
    { value: 'ITO', label: '铟锡氧化物 (ITO)' },
    { value: 'Ag', label: '银 (Ag)' },
    { value: 'Al', label: '铝 (Al)' },
    { value: 'Au', label: '金 (Au)' },
    { value: 'Ca', label: '钙 (Ca)' },
  ];

  const isCalculating = progress.status === 'calculating';

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <CollapsibleSection title="量子点材料" icon={Atom}>
            <SelectInput
              label="核材料"
              value={inputParams.qdMaterial}
              options={qdMaterialOptions}
              onChange={(value) => setInputParams({ qdMaterial: value })}
            />
            <MaterialParamsDisplay material={inputParams.qdMaterial} type="qd" />

            <SelectInput
              label="壳材料"
              value={inputParams.shellMaterial}
              options={shellMaterialOptions}
              onChange={(value) => setInputParams({ shellMaterial: value })}
            />
            <MaterialParamsDisplay material={inputParams.shellMaterial} type="qd" />
          </CollapsibleSection>

          <CollapsibleSection title="核壳尺寸" icon={Layers}>
            <SliderInput
              label="核直径"
              value={inputParams.coreSize}
              min={1}
              max={10}
              step={0.1}
              unit="nm"
              onChange={(value) => setInputParams({ coreSize: value })}
              description="量子点核心直径，典型值2-5 nm"
            />
            <SliderInput
              label="壳层厚度"
              value={inputParams.shellThickness}
              min={0}
              max={5}
              step={0.1}
              unit="nm"
              onChange={(value) => setInputParams({ shellThickness: value })}
              description="外壳层厚度，典型值0.5-2 nm"
            />
          </CollapsibleSection>

          <CollapsibleSection title="器件结构" icon={Zap}>
            <div className="space-y-4">
              <div className="p-3 bg-space-800/30 rounded-lg">
                <p className="text-xs font-medium text-quantum-400 mb-3">阳极 (Anode)</p>
                <SelectInput
                  label="材料"
                  value={inputParams.deviceStructure.anode}
                  options={electrodeOptions}
                  onChange={(value) => setInputParams({ deviceStructure: { ...inputParams.deviceStructure, anode: value } })}
                />
                <MaterialParamsDisplay material={inputParams.deviceStructure.anode} type="electrode" />
                <SliderInput
                  label="厚度"
                  value={inputParams.deviceStructure.anodeThickness}
                  min={50}
                  max={300}
                  step={10}
                  unit="nm"
                  onChange={(value) => setInputParams({ deviceStructure: { ...inputParams.deviceStructure, anodeThickness: value } })}
                />
              </div>

              <div className="p-3 bg-space-800/30 rounded-lg">
                <p className="text-xs font-medium text-quantum-400 mb-3">空穴传输层 (HTL)</p>
                <SelectInput
                  label="材料"
                  value={inputParams.deviceStructure.htl}
                  options={htlOptions}
                  onChange={(value) => setInputParams({ deviceStructure: { ...inputParams.deviceStructure, htl: value } })}
                />
                <MaterialParamsDisplay material={inputParams.deviceStructure.htl} type="transport" />
                <SliderInput
                  label="厚度"
                  value={inputParams.deviceStructure.htlThickness}
                  min={10}
                  max={100}
                  step={5}
                  unit="nm"
                  onChange={(value) => setInputParams({ deviceStructure: { ...inputParams.deviceStructure, htlThickness: value } })}
                />
              </div>

              <div className="p-3 bg-space-800/30 rounded-lg">
                <p className="text-xs font-medium text-energy-400 mb-3">量子点发光层 (QDL)</p>
                <SliderInput
                  label="厚度"
                  value={inputParams.deviceStructure.qdLayerThickness}
                  min={20}
                  max={150}
                  step={5}
                  unit="nm"
                  onChange={(value) => setInputParams({ deviceStructure: { ...inputParams.deviceStructure, qdLayerThickness: value } })}
                  description="量子点活性层厚度"
                />
              </div>

              <div className="p-3 bg-space-800/30 rounded-lg">
                <p className="text-xs font-medium text-quantum-400 mb-3">电子传输层 (ETL)</p>
                <SelectInput
                  label="材料"
                  value={inputParams.deviceStructure.etl}
                  options={etlOptions}
                  onChange={(value) => setInputParams({ deviceStructure: { ...inputParams.deviceStructure, etl: value } })}
                />
                <MaterialParamsDisplay material={inputParams.deviceStructure.etl} type="transport" />
                <SliderInput
                  label="厚度"
                  value={inputParams.deviceStructure.etlThickness}
                  min={10}
                  max={150}
                  step={5}
                  unit="nm"
                  onChange={(value) => setInputParams({ deviceStructure: { ...inputParams.deviceStructure, etlThickness: value } })}
                />
              </div>

              <div className="p-3 bg-space-800/30 rounded-lg">
                <p className="text-xs font-medium text-quantum-400 mb-3">阴极 (Cathode)</p>
                <SelectInput
                  label="材料"
                  value={inputParams.deviceStructure.cathode}
                  options={electrodeOptions}
                  onChange={(value) => setInputParams({ deviceStructure: { ...inputParams.deviceStructure, cathode: value } })}
                />
                <MaterialParamsDisplay material={inputParams.deviceStructure.cathode} type="electrode" />
                <SliderInput
                  label="厚度"
                  value={inputParams.deviceStructure.cathodeThickness}
                  min={50}
                  max={200}
                  step={10}
                  unit="nm"
                  onChange={(value) => setInputParams({ deviceStructure: { ...inputParams.deviceStructure, cathodeThickness: value } })}
                />
              </div>
            </div>
          </CollapsibleSection>

          <CollapsibleSection title="计算参数" icon={Calculator}>
            <SliderInput
              label="起始电压"
              value={inputParams.calculationParams.voltageStart}
              min={0}
              max={2}
              step={0.1}
              unit="V"
              onChange={(value) => setInputParams({ calculationParams: { ...inputParams.calculationParams, voltageStart: value } })}
            />
            <SliderInput
              label="终止电压"
              value={inputParams.calculationParams.voltageEnd}
              min={2}
              max={10}
              step={0.5}
              unit="V"
              onChange={(value) => setInputParams({ calculationParams: { ...inputParams.calculationParams, voltageEnd: value } })}
            />
            <SliderInput
              label="电压步长"
              value={inputParams.calculationParams.voltageStep}
              min={0.1}
              max={1}
              step={0.1}
              unit="V"
              onChange={(value) => setInputParams({ calculationParams: { ...inputParams.calculationParams, voltageStep: value } })}
            />
            <SliderInput
              label="网格点数"
              value={inputParams.calculationParams.gridPoints}
              min={50}
              max={500}
              step={10}
              onChange={(value) => setInputParams({ calculationParams: { ...inputParams.calculationParams, gridPoints: value } })}
              description="数值计算网格精度，越高越精确但计算越慢"
            />
            <SliderInput
              label="温度"
              value={inputParams.calculationParams.temperature}
              min={100}
              max={500}
              step={10}
              unit="K"
              onChange={(value) => setInputParams({ calculationParams: { ...inputParams.calculationParams, temperature: value } })}
              description="工作温度，室温为300K"
            />
          </CollapsibleSection>

          <div className="flex gap-3">
            <button
              onClick={() => runSimulation()}
              disabled={isCalculating}
              className="flex-1 btn-primary flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="w-4 h-4" />
              {isCalculating ? '计算中...' : '开始计算'}
            </button>
            <button
              onClick={() => resetParams()}
              disabled={isCalculating}
              className="btn-secondary flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RotateCcw className="w-4 h-4" />
              重置
            </button>
          </div>

          {progress.status === 'error' && progress.error && (
            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
              <p className="text-sm text-red-400">{progress.error}</p>
            </div>
          )}
        </div>

        <div className="lg:col-span-2 space-y-6">
          <DeviceStructurePreview />

          <div className="glass-card p-6">
            <h3 className="text-lg font-semibold text-slate-200 mb-4">计算方法说明</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-space-800/30 rounded-lg border border-space-700/50">
                <h4 className="font-medium text-quantum-400 mb-2 flex items-center gap-2">
                  <Atom className="w-4 h-4" />
                  薛定谔方程
                </h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  使用有效质量近似和有限差分法求解核壳量子点的电子和空穴量子限制能级，获得波函数和本征能量。
                </p>
              </div>
              <div className="p-4 bg-space-800/30 rounded-lg border border-space-700/50">
                <h4 className="font-medium text-energy-400 mb-2 flex items-center gap-2">
                  <Zap className="w-4 h-4" />
                  费米黄金定则
                </h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  计算电子-空穴波函数重叠积分，基于费米黄金定则计算辐射复合速率和内量子效率。
                </p>
              </div>
              <div className="p-4 bg-space-800/30 rounded-lg border border-space-700/50">
                <h4 className="font-medium text-slate-300 mb-2 flex items-center gap-2">
                  <Layers className="w-4 h-4" />
                  漂移扩散模型
                </h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  自洽求解泊松方程和电流连续性方程，模拟载流子输运、复合和器件的J-V/L-V特性。
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
