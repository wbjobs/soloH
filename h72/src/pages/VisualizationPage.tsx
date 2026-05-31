import { useAppStore } from '../store';
import { BandDiagram } from '../components/visualization/BandDiagram';
import { CarrierDistributionChart } from '../components/visualization/CarrierDistributionChart';
import { SliderInput } from '../components/forms/SliderInput';
import { Layers, Users, AlertCircle, Play } from 'lucide-react';

export function VisualizationPage() {
  const { results, selectedVoltage, setSelectedVoltage, visualizationMode, setVisualizationMode } = useAppStore();

  if (!results) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12">
        <div className="glass-card p-12 text-center">
          <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-space-800/50 flex items-center justify-center">
            <AlertCircle className="w-10 h-10 text-slate-500" />
          </div>
          <h2 className="text-xl font-semibold text-slate-300 mb-2">暂无可视化数据</h2>
          <p className="text-slate-500 mb-6 max-w-md mx-auto">
            请先完成计算，然后在此页面查看能带图和载流子浓度分布的可视化展示。
          </p>
          <button
            onClick={() => useAppStore.getState().setActiveTab('params')}
            className="btn-primary inline-flex items-center gap-2"
          >
            <Play className="w-4 h-4" />
            前往参数设置
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="glass-card p-4 mb-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setVisualizationMode('band')}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-all duration-300 ${
                visualizationMode === 'band'
                  ? 'bg-quantum-400/20 text-quantum-400 border border-quantum-400/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-space-800/50'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span className="text-sm font-medium">能带图</span>
            </button>
            <button
              onClick={() => setVisualizationMode('carrier')}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-all duration-300 ${
                visualizationMode === 'carrier'
                  ? 'bg-energy-400/20 text-energy-400 border border-energy-400/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-space-800/50'
              }`}
            >
              <Users className="w-4 h-4" />
              <span className="text-sm font-medium">载流子分布</span>
            </button>
          </div>

          <div className="w-64">
            <SliderInput
              label="偏置电压"
              value={selectedVoltage}
              min={useAppStore.getState().inputParams.calculationParams.voltageStart}
              max={useAppStore.getState().inputParams.calculationParams.voltageEnd}
              step={useAppStore.getState().inputParams.calculationParams.voltageStep}
              unit="V"
              onChange={setSelectedVoltage}
            />
          </div>
        </div>
      </div>

      <div className="animate-fade-in">
        {visualizationMode === 'band' ? (
          <div className="space-y-6">
            <BandDiagram data={results.bandDiagram} />
            <div className="glass-card p-6">
              <h3 className="text-lg font-semibold text-slate-200 mb-4">能带结构说明</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-space-800/30 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-quantum-400" />
                    <span className="text-quantum-400 font-medium">导带 (E_c)</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    电子可以占据的最低能量能级。电子从阴极注入，经过电子传输层到达量子点发光层。
                  </p>
                </div>
                <div className="p-4 bg-space-800/30 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-energy-400" />
                    <span className="text-energy-400 font-medium">价带 (E_v)</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    空穴可以占据的最高能量能级。空穴从阳极注入，经过空穴传输层到达发光层。
                  </p>
                </div>
                <div className="p-4 bg-space-800/30 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-yellow-400" />
                    <span className="text-yellow-400 font-medium">费米能级 (E_f)</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    电子占据概率为50%的能级。在平衡状态下，费米能级在整个器件中保持恒定。
                  </p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <CarrierDistributionChart data={results.carrierDistribution} />
            <div className="glass-card p-6">
              <h3 className="text-lg font-semibold text-slate-200 mb-4">载流子输运说明</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-space-800/30 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-quantum-400" />
                    <span className="text-quantum-400 font-medium">电子浓度 (n)</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    电子从阴极注入，经过电子传输层。在发光层与空穴复合产生光子。
                  </p>
                </div>
                <div className="p-4 bg-space-800/30 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-energy-400" />
                    <span className="text-energy-400 font-medium">空穴浓度 (p)</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    空穴从阳极注入，经过空穴传输层。在发光层与电子复合产生光子。
                  </p>
                </div>
                <div className="p-4 bg-space-800/30 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-yellow-400" />
                    <span className="text-yellow-400 font-medium">复合速率 (R)</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    电子和空穴的复合速率。峰值区域对应发光层，是主要的发光区域。
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
