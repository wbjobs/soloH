import { useAppStore, useAllMaterials } from '@/store/useAppStore';
import { BlackbodySpectrumChart } from '@/components/charts/BlackbodySpectrumChart';
import { IVCurveChart } from '@/components/charts/IVCurveChart';
import { QuantumEfficiencyChart } from '@/components/charts/QuantumEfficiencyChart';
import { BandgapEfficiencyContour } from '@/components/charts/BandgapEfficiencyContour';
import { ConcentrationEfficiencyChart } from '@/components/charts/ConcentrationEfficiencyChart';
import { WasteHeatChart } from '@/components/charts/WasteHeatChart';
import { LifetimeCurveChart } from '@/components/charts/LifetimeCurveChart';
import type { CalculationResult } from '@/types';
import { getBandgapAtTemperature } from '@/data/materials';
import { Zap, Thermometer, Battery, Gauge, Activity, Clock, Sun, Sparkles, Flame, Heart, TrendingUp } from 'lucide-react';

interface ResultPanelProps {
  result: CalculationResult | null;
}

const tabs = [
  { id: 'spectrum', label: '黑体辐射谱', icon: Sun },
  { id: 'iv', label: 'I-V 曲线', icon: Activity },
  { id: 'qe', label: '量子效率', icon: Sparkles },
  { id: 'contour', label: '带隙扫描', icon: Gauge },
  { id: 'concentration', label: '聚光特性', icon: TrendingUp, enabled: (r: CalculationResult) => !!r.concentrationResult },
  { id: 'wasteheat', label: '废热回收', icon: Flame, enabled: (r: CalculationResult) => !!r.wasteHeatResult },
  { id: 'lifetime', label: '寿命预测', icon: Heart, enabled: (r: CalculationResult) => !!r.lifetimeResult },
] as const;

type TabType = typeof tabs[number]['id'];

export function ResultPanel({ result }: ResultPanelProps) {
  const { activeTab, setActiveTab, params } = useAppStore();
  const allMaterials = useAllMaterials();
  
  const selectedMaterial = allMaterials.find(m => m.id === params.materialId);
  const currentBandgap = selectedMaterial 
    ? getBandgapAtTemperature(selectedMaterial, params.temperature) 
    : 0;

  return (
    <div className="space-y-4 animate-slide-in stagger-2">
      <div className="glass-card p-5">
        <h2 className="section-title flex items-center gap-2 mb-4">
          <Battery className="w-5 h-5 text-accent-400" />
          计算结果
        </h2>

        {!result ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-20 h-20 rounded-full bg-dark-700/50 flex items-center justify-center mb-4 animate-float">
              <Zap className="w-10 h-10 text-dark-500" />
            </div>
            <p className="text-dark-400 mb-2">设置参数后点击"开始计算"</p>
            <p className="text-xs text-dark-500">系统将使用详细平衡模型计算电池性能</p>
          </div>
        ) : (
          <div className="space-y-5">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="bg-dark-900/50 rounded-xl p-4 border border-dark-600 glow-border">
                <div className="text-xs text-dark-400 mb-1 flex items-center gap-1">
                  <Gauge className="w-3 h-3" />
                  转换效率
                </div>
                <div className="text-3xl font-display font-bold text-accent-400">
                  {result.efficiency.toFixed(2)}<span className="text-lg">%</span>
                </div>
              </div>
              <div className="bg-dark-900/50 rounded-xl p-4 border border-dark-600">
                <div className="text-xs text-dark-400 mb-1 flex items-center gap-1">
                  <Zap className="w-3 h-3" />
                  短路电流 Jsc
                </div>
                <div className="text-2xl font-mono font-bold text-primary-400">
                  {result.shortCircuitCurrent.toFixed(3)}
                  <span className="text-sm ml-1">A/cm²</span>
                </div>
              </div>
              <div className="bg-dark-900/50 rounded-xl p-4 border border-dark-600">
                <div className="text-xs text-dark-400 mb-1 flex items-center gap-1">
                  <Battery className="w-3 h-3" />
                  开路电压 Voc
                </div>
                <div className="text-2xl font-mono font-bold text-primary-400">
                  {result.openCircuitVoltage.toFixed(3)}
                  <span className="text-sm ml-1">V</span>
                </div>
              </div>
              <div className="bg-dark-900/50 rounded-xl p-4 border border-dark-600">
                <div className="text-xs text-dark-400 mb-1 flex items-center gap-1">
                  <Activity className="w-3 h-3" />
                  填充因子 FF
                </div>
                <div className="text-2xl font-mono font-bold text-primary-400">
                  {result.fillFactor.toFixed(1)}<span className="text-lg">%</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="bg-dark-900/30 rounded-xl p-3 border border-dark-700">
                <div className="text-xs text-dark-400 mb-1">最大功率密度</div>
                <div className="text-lg font-mono text-green-400">
                  {result.maxPowerDensity.toFixed(4)} W/cm²
                </div>
              </div>
              <div className="bg-dark-900/30 rounded-xl p-3 border border-dark-700">
                <div className="text-xs text-dark-400 mb-1">MPP 电压</div>
                <div className="text-lg font-mono text-dark-200">
                  {result.voltageAtMaxPower.toFixed(3)} V
                </div>
              </div>
              <div className="bg-dark-900/30 rounded-xl p-3 border border-dark-700">
                <div className="text-xs text-dark-400 mb-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  计算耗时
                </div>
                <div className="text-lg font-mono text-dark-200">
                  {result.calculationTime.toFixed(2)} s
                </div>
              </div>
            </div>

            {result.concentrationResult && (
              <div className="bg-gradient-to-r from-yellow-900/20 to-orange-900/20 rounded-xl p-4 border border-yellow-700/30">
                <div className="text-sm text-yellow-400 font-semibold mb-3 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  聚光条件下的性能 ({result.concentrationResult.concentrationRatio}×)
                </div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <div>
                    <div className="text-xs text-dark-400">聚光后效率</div>
                    <div className="text-xl font-mono font-bold text-yellow-400">
                      {result.concentrationResult.concentratedEfficiency.toFixed(2)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400">聚光后 Jsc</div>
                    <div className="text-lg font-mono text-yellow-300">
                      {result.concentrationResult.concentratedJsc.toFixed(2)} A/cm²
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400">聚光后 Voc</div>
                    <div className="text-lg font-mono text-yellow-300">
                      {result.concentrationResult.concentratedVoc.toFixed(3)} V
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400">电池温升</div>
                    <div className="text-lg font-mono text-orange-400">
                      +{result.concentrationResult.cellTemperatureRise.toFixed(1)} K
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400">最佳聚光比</div>
                    <div className="text-lg font-mono text-green-400">
                      {result.concentrationResult.optimumConcentration.toFixed(0)}×
                    </div>
                  </div>
                </div>
              </div>
            )}

            {result.wasteHeatResult && (
              <div className="bg-gradient-to-r from-red-900/20 to-orange-900/20 rounded-xl p-4 border border-red-700/30">
                <div className="text-sm text-red-400 font-semibold mb-3 flex items-center gap-2">
                  <Flame className="w-4 h-4" />
                  热电耦合废热回收系统
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <div className="text-xs text-dark-400">废热功率</div>
                    <div className="text-lg font-mono text-red-400">
                      {result.wasteHeatResult.wasteHeatDensity.toFixed(3)} W/cm²
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400">TEG 输出</div>
                    <div className="text-lg font-mono text-orange-400">
                      {result.wasteHeatResult.tegOutputPower.toFixed(4)} W/cm²
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400">TEG 效率</div>
                    <div className="text-lg font-mono text-orange-300">
                      {result.wasteHeatResult.tegEfficiency.toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400">系统总效率</div>
                    <div className="text-xl font-mono font-bold text-green-400">
                      {result.wasteHeatResult.systemTotalEfficiency.toFixed(2)}%
                    </div>
                  </div>
                </div>
              </div>
            )}

            {result.lifetimeResult && (
              <div className="bg-gradient-to-r from-purple-900/20 to-indigo-900/20 rounded-xl p-4 border border-purple-700/30">
                <div className="text-sm text-purple-400 font-semibold mb-3 flex items-center gap-2">
                  <Heart className="w-4 h-4" />
                  电池寿命预测
                </div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <div>
                    <div className="text-xs text-dark-400">估计寿命</div>
                    <div className="text-xl font-mono font-bold text-purple-400">
                      {(result.lifetimeResult.estimatedLifetime / 8760).toFixed(1)} 年
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400">加速因子</div>
                    <div className="text-lg font-mono text-purple-300">
                      {result.lifetimeResult.accelerationFactor.toFixed(1)}×
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400">MTBF</div>
                    <div className="text-lg font-mono text-purple-300">
                      {(result.lifetimeResult.mtbf / 8760).toFixed(1)} 年
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400">失效率</div>
                    <div className="text-lg font-mono text-red-400">
                      {(result.lifetimeResult.failureRate * 1e9).toFixed(2)} FIT
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400">退化率</div>
                    <div className="text-lg font-mono text-orange-400">
                      {(result.lifetimeResult.degradationRate * 100 * 8760).toFixed(3)} %/年
                    </div>
                  </div>
                </div>
              </div>
            )}

            {result.optimizedEmitter && (
              <div className="bg-dark-900/30 rounded-xl p-4 border border-dark-700">
                <div className="text-sm text-dark-300 mb-2">优化后的发射极结构</div>
                <div className="flex gap-2 flex-wrap">
                  {result.optimizedEmitter.map((layer, idx) => (
                    <div
                      key={idx}
                      className="px-3 py-1.5 bg-dark-700/50 rounded-lg text-xs font-mono"
                    >
                      <span className="text-primary-400">{layer.material}</span>
                      <span className="text-dark-400 ml-2">{layer.thickness.toFixed(0)} nm</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {result && (
        <div className="glass-card p-5">
          <div className="flex border-b border-dark-600 mb-5 overflow-x-auto scrollbar-thin">
            {tabs.filter(tab => !('enabled' in tab) || tab.enabled(result)).map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={`flex items-center gap-2 px-5 py-3 text-sm font-medium transition-all whitespace-nowrap
                    ${activeTab === tab.id
                      ? 'text-primary-400 border-b-2 border-primary-500 bg-dark-700/30'
                      : 'text-dark-400 hover:text-dark-200 hover:bg-dark-700/20'
                    }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div className="chart-container min-h-[380px]">
            {activeTab === 'spectrum' && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm text-dark-300">黑体辐射光谱 @ {params.sourceTemperature}K</h3>
                  <span className="text-xs text-dark-500 font-mono">
                    峰值波长: {(2.898e6 / params.sourceTemperature).toFixed(0)} nm
                  </span>
                </div>
                <BlackbodySpectrumChart
                  data={result.blackbodySpectrum}
                  bandgap={currentBandgap}
                  width={850}
                  height={350}
                />
              </div>
            )}

            {activeTab === 'iv' && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm text-dark-300">电流-电压 (I-V) 特性曲线</h3>
                  <span className="text-xs text-dark-500 font-mono">
                    {selectedMaterial?.formula} @ {params.temperature}K
                  </span>
                </div>
                <IVCurveChart
                  data={result.ivCurve}
                  vmp={result.voltageAtMaxPower}
                  jmp={result.currentAtMaxPower}
                  width={850}
                  height={350}
                />
              </div>
            )}

            {activeTab === 'qe' && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm text-dark-300">外量子效率 (EQE) 与发射极反射率</h3>
                  <span className="text-xs text-dark-500 font-mono">
                    带隙: {currentBandgap.toFixed(3)} eV
                  </span>
                </div>
                <QuantumEfficiencyChart
                  qeData={result.quantumEfficiency}
                  reflectanceData={result.emitterReflectance}
                  width={850}
                  height={350}
                />
              </div>
            )}

            {activeTab === 'contour' && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm text-dark-300">带隙-热源温度-效率 等高线图</h3>
                  <span className="text-xs text-accent-400 font-mono animate-pulse">
                    当前参数已标记
                  </span>
                </div>
                <BandgapEfficiencyContour
                  data={result.bandgapScan}
                  currentBandgap={currentBandgap}
                  currentTemperature={params.sourceTemperature}
                  width={850}
                  height={400}
                />
              </div>
            )}

            {activeTab === 'concentration' && result.concentrationResult && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm text-dark-300">聚光比-效率特性曲线</h3>
                  <span className="text-xs text-yellow-400 font-mono">
                    最佳聚光比: {result.concentrationResult.optimumConcentration.toFixed(0)}× @ {result.concentrationResult.maximumEfficiency.toFixed(2)}%
                  </span>
                </div>
                <ConcentrationEfficiencyChart
                  data={result.concentrationResult.concentrationEfficiencyCurve}
                  currentCR={result.concentrationResult.concentrationRatio}
                  optimumCR={result.concentrationResult.optimumConcentration}
                  maxEfficiency={result.concentrationResult.maximumEfficiency}
                  width={850}
                  height={350}
                />
              </div>
            )}

            {activeTab === 'wasteheat' && result.wasteHeatResult && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm text-dark-300">能量流与废热回收分析</h3>
                  <span className="text-xs text-green-400 font-mono">
                    系统总效率: {result.wasteHeatResult.systemTotalEfficiency.toFixed(2)}%
                  </span>
                </div>
                <WasteHeatChart
                  tpvEfficiency={result.concentrationResult?.concentratedEfficiency ?? result.efficiency}
                  wasteHeatDensity={result.wasteHeatResult.wasteHeatDensity}
                  tegOutputPower={result.wasteHeatResult.tegOutputPower}
                  tegEfficiency={result.wasteHeatResult.tegEfficiency}
                  systemTotalEfficiency={result.wasteHeatResult.systemTotalEfficiency}
                  carnotEfficiency={result.wasteHeatResult.carnotEfficiency}
                  width={850}
                  height={350}
                />
              </div>
            )}

            {activeTab === 'lifetime' && result.lifetimeResult && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm text-dark-300">温度-寿命曲线 (Arrhenius模型)</h3>
                  <span className="text-xs text-purple-400 font-mono">
                    估计寿命: {(result.lifetimeResult.estimatedLifetime / 8760).toFixed(1)} 年
                  </span>
                </div>
                <LifetimeCurveChart
                  data={result.lifetimeResult.lifetimeCurve}
                  currentTemperature={
                    result.wasteHeatResult?.heatRejectionTemperature 
                    ?? result.concentrationResult?.actualCellTemperature 
                    ?? params.temperature
                  }
                  estimatedLifetime={result.lifetimeResult.estimatedLifetime}
                  activationEnergy={params.activationEnergy}
                  width={850}
                  height={350}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
