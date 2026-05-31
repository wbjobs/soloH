import React, { useState } from 'react';
import {
  Activity,
  Waves,
  Layers,
  Zap,
  Thermometer,
  Maximize2,
  Gauge,
  GitBranch,
  Target,
  BarChart3,
} from 'lucide-react';
import { useSimulationStore } from '../store/simulationStore';
import {
  EfficiencyChart,
  IntensityEvolutionChart,
  ToleranceDisplay,
} from './charts/EfficiencyChart';
import { SpectrumChart } from './charts/SpectrumChart';
import { FieldVisualization, DomainStructure2D } from './visualization/FieldVisualization';

const TabButton: React.FC<{
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}> = ({ active, onClick, icon, label }) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-all rounded-t-lg ${
      active
        ? 'bg-gray-800/80 text-cyan-400 border-b-2 border-cyan-400'
        : 'text-gray-400 hover:text-white hover:bg-gray-800/40'
    }`}
  >
    {icon}
    <span className="hidden sm:inline">{label}</span>
  </button>
);

const ResultCard: React.FC<{
  label: string;
  value: string | number;
  unit?: string;
  highlight?: boolean;
}> = ({ label, value, unit, highlight }) => (
  <div className="p-3 rounded-lg border border-white/10 bg-white/5">
    <div className="text-xs text-gray-400 mb-1">{label}</div>
    <div className="flex items-baseline gap-1">
      <span
        className={`text-lg font-bold font-mono ${
          highlight ? 'text-cyan-400' : 'text-white'
        }`}
      >
        {typeof value === 'number' ? value.toFixed(4) : value}
      </span>
      {unit && <span className="text-xs text-gray-500">{unit}</span>}
    </div>
  </div>
);

export const ResultsPanel: React.FC = () => {
  const { result, params, activeTab, setActiveTab, scanType, setScanType } =
    useSimulationStore();
  const [showDomain2D, setShowDomain2D] = useState(false);
  const [showLaserBeam, setShowLaserBeam] = useState(true);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-1 px-4 pt-2 border-b border-gray-700/50 overflow-x-auto">
        <TabButton
          active={activeTab === 'phase'}
          onClick={() => setActiveTab('phase')}
          icon={<Activity size={16} />}
          label="相位匹配"
        />
        <TabButton
          active={activeTab === 'coupled'}
          onClick={() => setActiveTab('coupled')}
          icon={<Waves size={16} />}
          label="耦合波"
        />
        <TabButton
          active={activeTab === 'efficiency'}
          onClick={() => setActiveTab('efficiency')}
          icon={<Gauge size={16} />}
          label="效率曲线"
        />
        <TabButton
          active={activeTab === 'poling'}
          onClick={() => setActiveTab('poling')}
          icon={<Layers size={16} />}
          label="畴结构"
        />
        <TabButton
          active={activeTab === 'field'}
          onClick={() => setActiveTab('field')}
          icon={<Zap size={16} />}
          label="场分布"
        />
        <TabButton
          active={activeTab === 'spectrum'}
          onClick={() => setActiveTab('spectrum')}
          icon={<Thermometer size={16} />}
          label="频谱"
        />
        <TabButton
          active={activeTab === 'cascade'}
          onClick={() => setActiveTab('cascade')}
          icon={<GitBranch size={16} />}
          label="级联过程"
        />
        <TabButton
          active={activeTab === 'noncollinear'}
          onClick={() => setActiveTab('noncollinear')}
          icon={<Target size={16} />}
          label="非共线"
        />
        <TabButton
          active={activeTab === 'montecarlo'}
          onClick={() => setActiveTab('montecarlo')}
          icon={<BarChart3 size={16} />}
          label="蒙特卡洛"
        />
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'phase' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Activity className="text-cyan-400" size={20} />
              相位匹配计算结果
            </h3>

            {result.phaseMatching ? (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <ResultCard
                    label="相位匹配角 θ"
                    value={result.phaseMatching.phaseMatchAngle}
                    unit="°"
                    highlight
                  />
                  <ResultCard
                    label="走离角"
                    value={result.phaseMatching.walkoffAngle}
                    unit="°"
                  />
                  <ResultCard
                    label="有效非线性系数"
                    value={result.phaseMatching.effectiveNonlinearity}
                    unit="pm/V"
                    highlight
                  />
                  <ResultCard
                    label="相干长度"
                    value={
                      result.phaseMatching.coherenceLength > 0
                        ? result.phaseMatching.coherenceLength
                        : '∞'
                    }
                    unit="μm"
                  />
                  <ResultCard
                    label="泵浦光折射率"
                    value={result.phaseMatching.nPump}
                  />
                  <ResultCard
                    label="信号光折射率"
                    value={result.phaseMatching.nSignal}
                  />
                  <ResultCard
                    label="闲频光折射率"
                    value={result.phaseMatching.nIdler}
                  />
                  <ResultCard
                    label="闲频光波长"
                    value={result.phaseMatching.idlerWavelength}
                    unit="nm"
                    highlight
                  />
                  <ResultCard
                    label="相位失配 Δk"
                    value={result.phaseMatching.deltaK}
                    unit="m⁻¹"
                  />
                  <ResultCard
                    label="群速度失配"
                    value={result.phaseMatching.groupVelocityMismatch}
                    unit="s/m"
                  />
                </div>

                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-300 mb-3">
                    容许公差
                  </h4>
                  {result.toleranceData ? (
                    <ToleranceDisplay
                      bandwidth={result.toleranceData.bandwidth}
                      temperatureTolerance={result.toleranceData.temperatureTolerance}
                      angleTolerance={result.toleranceData.angleTolerance}
                      wavelengthTolerance={result.toleranceData.wavelengthTolerance}
                    />
                  ) : (
                    <div className="text-center text-gray-500 py-8">
                      请先进行完整计算以获取容许公差数据
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="text-center text-gray-500 py-12">
                请点击"开始计算"按钮进行相位匹配计算
              </div>
            )}
          </div>
        )}

        {activeTab === 'coupled' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Waves className="text-cyan-400" size={20} />
              耦合波方程求解结果
            </h3>

            {result.coupledWave ? (
              <>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <ResultCard
                    label="转换效率"
                    value={result.coupledWave.conversionEfficiency.toFixed(2)}
                    unit="%"
                    highlight
                  />
                  <ResultCard
                    label="泵浦光耗尽"
                    value={result.coupledWave.pumpDepletion.toFixed(2)}
                    unit="%"
                  />
                </div>

                <div className="h-80">
                  <IntensityEvolutionChart data={result.coupledWave} />
                </div>
              </>
            ) : (
              <div className="text-center text-gray-500 py-12">
                请点击"开始计算"按钮求解耦合波方程
              </div>
            )}
          </div>
        )}

        {activeTab === 'efficiency' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Gauge className="text-cyan-400" size={20} />
              转换效率曲线
            </h3>

            <div className="flex gap-2 flex-wrap">
              {(['wavelength', 'temperature', 'angle', 'length'] as const).map(
                (type) => (
                  <button
                    key={type}
                    onClick={() => setScanType(type)}
                    className={`px-3 py-1 text-xs rounded-full transition-all ${
                      scanType === type
                        ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50'
                        : 'bg-gray-800/50 text-gray-400 border border-gray-700 hover:border-gray-600'
                    }`}
                  >
                    {type === 'wavelength' && 'vs 波长'}
                    {type === 'temperature' && 'vs 温度'}
                    {type === 'angle' && 'vs 角度'}
                    {type === 'length' && 'vs 长度'}
                  </button>
                )
              )}
            </div>

            {result.efficiencyCurve.length > 0 ? (
              <div className="h-80">
                <EfficiencyChart
                  data={result.efficiencyCurve}
                  scanType={scanType}
                />
              </div>
            ) : (
              <div className="text-center text-gray-500 py-12">
                请点击"开始计算"按钮生成效率曲线
              </div>
            )}
          </div>
        )}

        {activeTab === 'poling' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Layers className="text-cyan-400" size={20} />
              周期极化畴结构
            </h3>

            <div className="flex gap-2">
              <button
                onClick={() => setShowDomain2D(!showDomain2D)}
                className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg transition-all ${
                  showDomain2D
                    ? 'bg-cyan-500/20 text-cyan-400'
                    : 'bg-gray-800 text-gray-400 hover:text-white'
                }`}
              >
                <Maximize2 size={14} />
                {showDomain2D ? '3D 视图' : '2D 视图'}
              </button>
            </div>

            {result.domainStructure.length > 0 ? (
              <div className="h-96">
                {showDomain2D ? (
                  <DomainStructure2D
                    data={result.domainStructure}
                    crystalLength={params.crystalLength}
                  />
                ) : (
                  <FieldVisualization
                    fieldData={[]}
                    domainData={result.domainStructure}
                    crystalLength={params.crystalLength}
                    showDomainStructure={true}
                    showField={false}
                    showLaserBeam={showLaserBeam}
                  />
                )}
              </div>
            ) : (
              <div className="text-center text-gray-500 py-12">
                请点击"开始计算"按钮生成畴结构
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <ResultCard
                label="极化周期"
                value={params.polingPeriod}
                unit="μm"
                highlight
              />
              <ResultCard
                label="占空比"
                value={params.dutyCycle}
              />
              <ResultCard
                label="结构类型"
                value={
                  params.polingType === 'uniform'
                    ? '均匀'
                    : params.polingType === 'linear_chirp'
                    ? '线性啁啾'
                    : params.polingType === 'quadratic_chirp'
                    ? '二次啁啾'
                    : params.polingType === 'fan'
                    ? '扇形'
                    : '二维'
                }
              />
              <ResultCard
                label="畴数目"
                value={Math.floor(
                  (params.crystalLength * 1000) / params.polingPeriod
                )}
              />
            </div>
          </div>
        )}

        {activeTab === 'field' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Zap className="text-cyan-400" size={20} />
              电场分布可视化
            </h3>

            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setShowLaserBeam(!showLaserBeam)}
                className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg transition-all ${
                  showLaserBeam
                    ? 'bg-cyan-500/20 text-cyan-400'
                    : 'bg-gray-800 text-gray-400 hover:text-white'
                }`}
              >
                激光光束
              </button>
            </div>

            {result.fieldDistribution.length > 0 ? (
              <div className="h-96">
                <FieldVisualization
                  fieldData={result.fieldDistribution}
                  domainData={result.domainStructure}
                  crystalLength={params.crystalLength}
                  showDomainStructure={true}
                  showField={true}
                  showLaserBeam={showLaserBeam}
                />
              </div>
            ) : (
              <div className="text-center text-gray-500 py-12">
                请点击"开始计算"按钮生成电场分布
              </div>
            )}

            <div className="text-xs text-gray-500">
              <p>提示：使用鼠标拖拽旋转视角，滚轮缩放。</p>
            </div>
          </div>
        )}

        {activeTab === 'spectrum' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Thermometer className="text-cyan-400" size={20} />
              频谱分析
            </h3>

            {result.spectrumData.length > 0 ? (
              <div className="h-80">
                <SpectrumChart data={result.spectrumData} />
              </div>
            ) : (
              <div className="text-center text-gray-500 py-12">
                请点击"开始计算"按钮进行频谱分析
              </div>
            )}
          </div>
        )}

        {activeTab === 'cascade' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <GitBranch className="text-cyan-400" size={20} />
              级联非线性过程
            </h3>

            {result.cascadeResult ? (
              <>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <ResultCard
                    label="总转换效率"
                    value={result.cascadeResult.totalEfficiency.toFixed(2)}
                    unit="%"
                    highlight
                  />
                  <ResultCard
                    label="级联过程"
                    value={
                      result.cascadeResult.process === 'opo'
                        ? 'OPO'
                        : result.cascadeResult.process === 'shg_signal'
                        ? '信号光倍频'
                        : result.cascadeResult.process === 'shg_idler'
                        ? '闲频光倍频'
                        : result.cascadeResult.process === 'sfg_pump_signal'
                        ? '和频'
                        : '完整级联'
                    }
                  />
                </div>

                <div className="space-y-3">
                  {result.cascadeResult.stages.map((stage, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-lg border border-gray-700/50 bg-gray-800/30"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-cyan-400">
                          阶段 {idx + 1}: {stage.processName}
                        </span>
                        <span className="text-xs text-gray-400">
                          输入波长: {stage.inputWavelength.toFixed(1)} nm
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <ResultCard
                          label="转换效率"
                          value={stage.efficiency.toFixed(2)}
                          unit="%"
                        />
                        <ResultCard
                          label="输出功率"
                          value={stage.outputPower.toFixed(3)}
                          unit="W"
                        />
                        {stage.outputWavelength && (
                          <ResultCard
                            label="输出波长"
                            value={stage.outputWavelength.toFixed(1)}
                            unit="nm"
                            highlight
                          />
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {result.cascadeResult.intermediateWavelengths &&
                  result.cascadeResult.intermediateWavelengths.length > 0 && (
                    <div className="mt-4">
                      <h4 className="text-sm font-medium text-gray-300 mb-2">
                        中间波长
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {result.cascadeResult.intermediateWavelengths.map(
                          (w, idx) => (
                            <span
                              key={idx}
                              className="px-2 py-1 text-xs font-mono bg-cyan-500/20 text-cyan-400 rounded"
                            >
                              {w.toFixed(1)} nm
                            </span>
                          )
                        )}
                      </div>
                    </div>
                  )}
              </>
            ) : (
              <div className="text-center text-gray-500 py-12">
                请先启用级联过程并点击"开始计算"
              </div>
            )}
          </div>
        )}

        {activeTab === 'noncollinear' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Target className="text-cyan-400" size={20} />
              非共线相位匹配
            </h3>

            {result.noncollinearResult ? (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <ResultCard
                    label="配置类型"
                    value={
                      result.noncollinearResult.config === 'collinear'
                        ? '共线'
                        : result.noncollinearResult.config === 'noncollinear_signal'
                        ? '仅信号光非共线'
                        : result.noncollinearResult.config === 'noncollinear_idler'
                        ? '仅闲频光非共线'
                        : '双光束非共线'
                    }
                  />
                  <ResultCard
                    label="相位失配 Δk"
                    value={result.noncollinearResult.deltaK.toFixed(1)}
                    unit="m⁻¹"
                    highlight
                  />
                  <ResultCard
                    label="Δk_x 分量"
                    value={result.noncollinearResult.deltaKx.toFixed(1)}
                    unit="m⁻¹"
                  />
                  <ResultCard
                    label="Δk_z 分量"
                    value={result.noncollinearResult.deltaKz.toFixed(1)}
                    unit="m⁻¹"
                  />
                  {result.noncollinearResult?.signalAngle !== undefined &&
                    result.noncollinearResult?.config !== 'collinear' && (
                    <ResultCard
                      label="信号光非共线角"
                      value={result.noncollinearResult.signalAngle.toFixed(2)}
                      unit="°"
                    />
                  )}
                  {result.noncollinearResult?.idlerAngle !== undefined &&
                    result.noncollinearResult?.config !== 'collinear' && (
                    <ResultCard
                      label="闲频光非共线角"
                      value={result.noncollinearResult.idlerAngle.toFixed(2)}
                      unit="°"
                    />
                  )}
                  <ResultCard
                    label="信号光接受角"
                    value={result.noncollinearResult.acceptanceAngleSignal.toFixed(3)}
                    unit="°·cm"
                  />
                  <ResultCard
                    label="闲频光接受角"
                    value={result.noncollinearResult.acceptanceAngleIdler.toFixed(3)}
                    unit="°·cm"
                  />
                  <ResultCard
                    label="有效非线性系数"
                    value={result.noncollinearResult.effectiveNonlinearity.toFixed(2)}
                    unit="pm/V"
                    highlight
                  />
                  {result.noncollinearResult.walkoffAngleSignal !== undefined && (
                    <ResultCard
                      label="信号光走离角"
                      value={result.noncollinearResult.walkoffAngleSignal.toFixed(3)}
                      unit="°"
                    />
                  )}
                  {result.noncollinearResult.walkoffAngleIdler !== undefined && (
                    <ResultCard
                      label="闲频光走离角"
                      value={result.noncollinearResult.walkoffAngleIdler.toFixed(3)}
                      unit="°"
                    />
                  )}
                </div>

                <div className="mt-4 p-4 rounded-lg border border-gray-700/50 bg-gray-800/30">
                  <h4 className="text-sm font-medium text-gray-300 mb-2">
                    波矢守恒图示
                  </h4>
                  <div className="text-xs text-gray-400 space-y-1">
                    <p>
                      k_pump = ({result.noncollinearResult.kPumpX.toFixed(2)}, {result.noncollinearResult.kPumpZ.toFixed(2)}) m⁻¹
                    </p>
                    <p>
                      k_signal = ({result.noncollinearResult.kSignalX.toFixed(2)}, {result.noncollinearResult.kSignalZ.toFixed(2)}) m⁻¹
                    </p>
                    <p>
                      k_idler = ({result.noncollinearResult.kIdlerX.toFixed(2)}, {result.noncollinearResult.kIdlerZ.toFixed(2)}) m⁻¹
                    </p>
                    <p>
                      k_grating = {result.noncollinearResult.kGrating.toFixed(2)} m⁻¹
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center text-gray-500 py-12">
                请先选择非共线配置并点击"开始计算"
              </div>
            )}
          </div>
        )}

        {activeTab === 'montecarlo' && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <BarChart3 className="text-cyan-400" size={20} />
              蒙特卡洛误差分析
            </h3>

            {result.monteCarloResult ? (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <ResultCard
                    label="试验次数"
                    value={result.monteCarloResult.trials}
                    highlight
                  />
                  <ResultCard
                    label="平均效率"
                    value={result.monteCarloResult.meanEfficiency.toFixed(2)}
                    unit="%"
                    highlight
                  />
                  <ResultCard
                    label="效率标准差"
                    value={result.monteCarloResult.stdEfficiency.toFixed(3)}
                    unit="%"
                  />
                  <ResultCard
                    label="中位效率"
                    value={result.monteCarloResult.medianEfficiency.toFixed(2)}
                    unit="%"
                  />
                  <ResultCard
                    label="最小效率"
                    value={result.monteCarloResult.minEfficiency.toFixed(3)}
                    unit="%"
                  />
                  <ResultCard
                    label="最大效率"
                    value={result.monteCarloResult.maxEfficiency.toFixed(3)}
                    unit="%"
                  />
                  <ResultCard
                    label="良率 (≥95%标称)"
                    value={(result.monteCarloResult.yield95 * 100).toFixed(1)}
                    unit="%"
                    highlight
                  />
                  <ResultCard
                    label="良率 (≥50%标称)"
                    value={(result.monteCarloResult.yield50 * 100).toFixed(1)}
                    unit="%"
                  />
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <ResultCard
                    label="畴周期涨落"
                    value={result.monteCarloResult.periodFluctuationStd.toFixed(2)}
                    unit="%"
                  />
                  <ResultCard
                    label="占空比涨落"
                    value={result.monteCarloResult.dutyCycleFluctuationStd.toFixed(2)}
                    unit="%"
                  />
                  <ResultCard
                    label="温度涨落"
                    value={result.monteCarloResult.temperatureFluctuationStd.toFixed(2)}
                    unit="°C"
                  />
                </div>

                <div className="mt-4 p-4 rounded-lg border border-gray-700/50 bg-gray-800/30">
                  <h4 className="text-sm font-medium text-gray-300 mb-3">
                    效率分布直方图
                  </h4>
                  <div className="space-y-2">
                    {result.monteCarloResult.efficiencyDistribution.map(
                      (bin, idx) => {
                        const maxCount = Math.max(
                          ...result.monteCarloResult.efficiencyDistribution.map(
                            (b) => b.count
                          )
                        );
                        const percentage = maxCount > 0 ? (bin.count / maxCount) * 100 : 0;
                        return (
                          <div key={idx} className="flex items-center gap-2">
                            <span className="text-xs text-gray-400 w-16 font-mono">
                              {bin.bin.toFixed(1)}%
                            </span>
                            <div className="flex-1 h-4 bg-gray-700/50 rounded overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-cyan-600 to-cyan-400 transition-all"
                                style={{ width: `${percentage}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-500 w-12 text-right">
                              {bin.count}
                            </span>
                          </div>
                        );
                      }
                    )}
                  </div>
                </div>

                {result.monteCarloResult.correlationData &&
                  result.monteCarloResult.correlationData.length > 0 && (
                    <div className="mt-4 p-4 rounded-lg border border-gray-700/50 bg-gray-800/30">
                      <h4 className="text-sm font-medium text-gray-300 mb-3">
                        畴周期误差 - 效率 相关性
                      </h4>
                      <div className="text-xs text-gray-400">
                        <p>
                          样本数: {result.monteCarloResult.correlationData.length}
                        </p>
                        <p className="mt-1">
                          提示：正误差表示周期大于标称值，负误差表示周期小于标称值
                        </p>
                      </div>
                    </div>
                  )}
              </>
            ) : (
              <div className="text-center text-gray-500 py-12">
                请先启用蒙特卡洛分析并点击"开始计算"
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
