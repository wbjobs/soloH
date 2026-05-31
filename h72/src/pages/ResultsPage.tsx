import { Atom, Zap, Lightbulb, Activity, Clock, Layers, TrendingUp, AlertCircle, Compass, Timer, Link } from 'lucide-react';
import { useAppStore } from '../store';
import { ResultCard } from '../components/charts/ResultCard';
import { EmissionSpectrumChart } from '../components/charts/EmissionSpectrumChart';
import { IVLCurvesChart } from '../components/charts/IVLCurvesChart';
import { AngularDistributionChart } from '../components/charts/AngularDistributionChart';
import { AgingCurveChart } from '../components/charts/AgingCurveChart';
import { MQWCouplingChart } from '../components/charts/MQWCouplingChart';
import { Play } from 'lucide-react';

export function ResultsPage() {
  const { results, progress, runSimulation, inputParams } = useAppStore();

  if (progress.status === 'calculating') {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12">
        <div className="glass-card p-12 text-center">
          <div className="relative w-24 h-24 mx-auto mb-6">
            <div className="absolute inset-0 rounded-full border-4 border-quantum-400/20" />
            <div
              className="absolute inset-0 rounded-full border-4 border-transparent border-t-quantum-400 animate-spin"
              style={{ animationDuration: '1s' }}
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-2xl font-bold text-quantum-400 font-mono">
                {progress.progress.toFixed(0)}%
              </span>
            </div>
          </div>
          <h2 className="text-xl font-semibold text-slate-200 mb-2">正在进行数值计算</h2>
          <p className="text-slate-400 mb-6">{progress.message}</p>
          <div className="w-64 mx-auto h-2 bg-space-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-quantum-400 to-energy-400 rounded-full transition-all duration-300"
              style={{ width: `${progress.progress}%` }}
            />
          </div>
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-left max-w-2xl mx-auto">
            <div className="p-3 bg-space-800/30 rounded-lg">
              <p className="text-quantum-400 font-medium mb-1">薛定谔方程</p>
              <p className="text-slate-500 text-xs">
                {progress.progress >= 10 ? '✓ 已完成' : '⏳ 进行中...'}
              </p>
            </div>
            <div className="p-3 bg-space-800/30 rounded-lg">
              <p className="text-energy-400 font-medium mb-1">费米黄金定则</p>
              <p className="text-slate-500 text-xs">
                {progress.progress >= 45 ? '✓ 已完成' : '⏳ 进行中...'}
              </p>
            </div>
            <div className="p-3 bg-space-800/30 rounded-lg">
              <p className="text-slate-300 font-medium mb-1">漂移扩散模型</p>
              <p className="text-slate-500 text-xs">
                {progress.progress >= 85 ? '✓ 已完成' : '⏳ 进行中...'}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12">
        <div className="glass-card p-12 text-center">
          <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-space-800/50 flex items-center justify-center">
            <AlertCircle className="w-10 h-10 text-slate-500" />
          </div>
          <h2 className="text-xl font-semibold text-slate-300 mb-2">暂无计算结果</h2>
          <p className="text-slate-500 mb-6 max-w-md mx-auto">
            请先在"参数设置"页面配置量子点材料、尺寸和器件结构参数，然后点击"开始计算"按钮运行模拟。
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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <ResultCard
          title="内量子效率 (IQE)"
          value={(results.recombination.iqe * 100).toFixed(1)}
          unit="%"
          icon={<Zap className="w-5 h-5 text-quantum-400" />}
          color="quantum"
          description="辐射复合占总复合的比例"
          trend={results.recombination.iqe > 0.7 ? 15 : -5}
        />
        <ResultCard
          title="外量子效率 (EQE)"
          value={(results.recombination.eqe * 100).toFixed(1)}
          unit="%"
          icon={<Lightbulb className="w-5 h-5 text-energy-400" />}
          color="energy"
          description="出射光子数/注入电子数"
        />
        <ResultCard
          title="峰值波长"
          value={results.emissionSpectrum.peakWavelength.toFixed(1)}
          unit="nm"
          icon={<Activity className="w-5 h-5 text-slate-300" />}
          color="slate"
          description={`FWHM: ${results.emissionSpectrum.fwhm.toFixed(1)} nm`}
        />
        <ResultCard
          title="开启电压"
          value={results.ivlCharacteristics.turnOnVoltage.toFixed(2)}
          unit="V"
          icon={<Layers className="w-5 h-5 text-slate-300" />}
          color="slate"
          description={`最大EQE: ${results.ivlCharacteristics.maxEQE.toFixed(2)}%`}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Atom className="w-4 h-4 text-quantum-400" />
            能级结构
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 bg-space-800/30 rounded-lg">
              <span className="text-slate-400 text-sm">导带 (E_c)</span>
              <span className="font-mono text-quantum-400">{results.energyLevels.conductionBand.toFixed(3)} eV</span>
            </div>
            <div className="space-y-2 pl-4 border-l-2 border-quantum-400/30">
              {results.energyLevels.electronLevels.slice(0, 3).map((level, idx) => (
                <div key={idx} className="flex justify-between items-center p-2 bg-quantum-400/5 rounded">
                  <span className="text-slate-400 text-xs">电子能级 {idx + 1}</span>
                  <span className="font-mono text-quantum-400 text-sm">{level.toFixed(3)} eV</span>
                </div>
              ))}
            </div>
            <div className="flex justify-between items-center p-3 bg-space-800/30 rounded-lg">
              <span className="text-slate-400 text-sm">费米能级 (E_f)</span>
              <span className="font-mono text-yellow-400">{results.energyLevels.fermiLevel.toFixed(3)} eV</span>
            </div>
            <div className="space-y-2 pl-4 border-l-2 border-energy-400/30">
              {results.energyLevels.holeLevels.slice(0, 3).reverse().map((level, idx) => (
                <div key={idx} className="flex justify-between items-center p-2 bg-energy-400/5 rounded">
                  <span className="text-slate-400 text-xs">空穴能级 {3 - idx}</span>
                  <span className="font-mono text-energy-400 text-sm">{level.toFixed(3)} eV</span>
                </div>
              ))}
            </div>
            <div className="flex justify-between items-center p-3 bg-space-800/30 rounded-lg">
              <span className="text-slate-400 text-sm">价带 (E_v)</span>
              <span className="font-mono text-energy-400">{results.energyLevels.valenceBand.toFixed(3)} eV</span>
            </div>
          </div>
        </div>

        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4 text-energy-400" />
            复合动力学
          </h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 bg-space-800/30 rounded-lg">
              <span className="text-slate-400 text-sm">辐射复合速率</span>
              <span className="font-mono text-quantum-400">
                {results.recombination.radiativeRate.toExponential(2)} s⁻¹
              </span>
            </div>
            <div className="flex justify-between items-center p-3 bg-space-800/30 rounded-lg">
              <span className="text-slate-400 text-sm">非辐射复合速率</span>
              <span className="font-mono text-slate-400">
                {results.recombination.nonRadiativeRate.toExponential(2)} s⁻¹
              </span>
            </div>
            <div className="flex justify-between items-center p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
              <span className="text-red-400 text-sm">SRH界面态复合</span>
              <span className="font-mono text-red-400">
                {results.recombination.srhRate.toExponential(2)} s⁻¹
              </span>
            </div>
            <div className="flex justify-between items-center p-3 bg-purple-500/10 border border-purple-500/20 rounded-lg">
              <span className="text-purple-400 text-sm">俄歇复合</span>
              <span className="font-mono text-purple-400">
                {results.recombination.augerRate.toExponential(2)} s⁻¹
              </span>
            </div>
            <div className="flex justify-between items-center p-3 bg-space-800/30 rounded-lg">
              <span className="text-slate-400 text-sm">波函数重叠积分</span>
              <span className="font-mono text-yellow-400">
                {results.recombination.overlapIntegral.toFixed(3)}
              </span>
            </div>
            <div className="flex justify-between items-center p-3 bg-space-800/30 rounded-lg">
              <span className="text-slate-400 text-sm">带隙 (E_g)</span>
              <span className="font-mono text-slate-300">
                {results.energyLevels.bandGap.toFixed(3)} eV
              </span>
            </div>
            <div className="flex justify-between items-center p-3 bg-space-800/30 rounded-lg">
              <span className="text-slate-400 text-sm flex items-center gap-2">
                <Clock className="w-4 h-4" />
                计算耗时
              </span>
              <span className="font-mono text-slate-300">
                {results.calculationTime.toFixed(2)} s
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <EmissionSpectrumChart data={results.emissionSpectrum} />
        <IVLCurvesChart data={results.ivlCharacteristics} />
      </div>

      {results.emissionSpectrum.angularDistribution && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Compass className="w-4 h-4 text-quantum-400" />
            电致发光角度分布
          </h3>
          <AngularDistributionChart data={results.emissionSpectrum.angularDistribution} />
        </div>
      )}

      {results.ivlCharacteristics.aging && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Timer className="w-4 h-4 text-energy-400" />
            老化特性与寿命预测
          </h3>
          <AgingCurveChart data={results.ivlCharacteristics.aging} />
        </div>
      )}

      {results.energyLevels.mqwCoupling && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Link className="w-4 h-4 text-purple-400" />
            多量子阱耦合效应
          </h3>
          <MQWCouplingChart 
            data={results.energyLevels.mqwCoupling} 
            mqwParams={inputParams.mqwParams}
          />
        </div>
      )}
    </div>
  );
}
