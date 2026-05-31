import { useAppStore, useAllMaterials } from '@/store/useAppStore';
import { Thermometer, Zap, Layers, Database, Settings, Play, Square, Sun, Clock } from 'lucide-react';
import type { CalculationState } from '@/types';
import { getBandgapAtTemperature } from '@/data/materials';

interface ParameterPanelProps {
  calculationState: CalculationState;
  onStart: () => void;
  onCancel: () => void;
}

export function ParameterPanel({ calculationState, onStart, onCancel }: ParameterPanelProps) {
  const {
    params,
    setSourceTemperature,
    setMaterialId,
    setParams,
    setShowMaterialModal,
    setShowEmitterModal,
  } = useAppStore();

  const allMaterials = useAllMaterials();
  const selectedMaterial = allMaterials.find(m => m.id === params.materialId);
  const currentBandgap = selectedMaterial 
    ? getBandgapAtTemperature(selectedMaterial, params.temperature) 
    : 0;

  return (
    <div className="glass-card p-5 space-y-5 animate-slide-in stagger-1">
      <div className="flex items-center justify-between">
        <h2 className="section-title flex items-center gap-2">
          <Settings className="w-5 h-5 text-primary-400" />
          计算参数
        </h2>
        {calculationState.status === 'running' && (
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
            <span className="text-xs text-dark-300 font-mono">计算中</span>
          </div>
        )}
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <label className="text-sm text-dark-200 flex items-center gap-2">
              <Thermometer className="w-4 h-4 text-accent-400" />
              热源温度
            </label>
            <span className="text-sm font-mono text-accent-400">
              {params.sourceTemperature} K
            </span>
          </div>
          <input
            type="range"
            min="600"
            max="2000"
            step="10"
            value={params.sourceTemperature}
            onChange={(e) => setSourceTemperature(Number(e.target.value))}
            disabled={calculationState.status === 'running'}
            className="w-full h-2 bg-dark-700 rounded-full appearance-none cursor-pointer
                       [&::-webkit-slider-thumb]:appearance-none
                       [&::-webkit-slider-thumb]:w-5
                       [&::-webkit-slider-thumb]:h-5
                       [&::-webkit-slider-thumb]:bg-primary-500
                       [&::-webkit-slider-thumb]:rounded-full
                       [&::-webkit-slider-thumb]:cursor-grab
                       [&::-webkit-slider-thumb]:transition-all
                       [&::-webkit-slider-thumb]:hover:scale-110
                       [&::-webkit-slider-thumb]:hover:shadow-lg
                       [&::-webkit-slider-thumb]:hover:shadow-primary-500/50
                       disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <div className="flex justify-between text-xs text-dark-400 font-mono">
            <span>600K</span>
            <span>1300K</span>
            <span>2000K</span>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm text-dark-200 flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary-400" />
            电池材料
          </label>
          <div className="flex gap-2">
            <select
              value={params.materialId}
              onChange={(e) => setMaterialId(e.target.value)}
              disabled={calculationState.status === 'running'}
              className="input-field flex-1"
            >
              {allMaterials.map((mat) => (
                <option key={mat.id} value={mat.id}>
                  {mat.name} ({mat.formula}) - {mat.bandgap}eV
                </option>
              ))}
            </select>
            <button
              onClick={() => setShowMaterialModal(true)}
              disabled={calculationState.status === 'running'}
              className="btn-secondary px-3 py-2 flex items-center gap-1 disabled:opacity-50"
              title="材料数据库"
            >
              <Database className="w-4 h-4" />
            </button>
          </div>
          {selectedMaterial && (
            <div className="text-xs text-dark-400 font-mono space-y-1 mt-2 p-2 bg-dark-900/50 rounded-lg">
              <div>带隙: <span className="text-primary-400">{currentBandgap.toFixed(3)} eV</span> (300K: {selectedMaterial.bandgap}eV)</div>
              <div>截止波长: <span className="text-accent-400">{(1239.8 / currentBandgap).toFixed(0)} nm</span></div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-dark-300">电池温度 (K)</label>
            <input
              type="number"
              value={params.temperature}
              onChange={(e) => setParams({ temperature: Number(e.target.value) })}
              disabled={calculationState.status === 'running'}
              min="200"
              max="500"
              className="input-field"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-dark-300">串联电阻 (Ω·cm²)</label>
            <input
              type="number"
              step="0.01"
              value={params.seriesResistance}
              onChange={(e) => setParams({ seriesResistance: Number(e.target.value) })}
              disabled={calculationState.status === 'running'}
              min="0"
              className="input-field"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-dark-300">并联电阻 (Ω·cm²)</label>
            <input
              type="number"
              value={params.shuntResistance}
              onChange={(e) => setParams({ shuntResistance: Number(e.target.value) })}
              disabled={calculationState.status === 'running'}
              min="0"
              className="input-field"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-dark-300 flex items-center gap-1">
              <Layers className="w-3 h-3" />
              发射极结构
            </label>
            <button
              onClick={() => setShowEmitterModal(true)}
              disabled={calculationState.status === 'running'}
              className="input-field text-left flex items-center justify-between"
            >
              <span>{params.emitterStructure.length} 层</span>
              <span className="text-xs text-primary-400">编辑</span>
            </button>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm text-dark-200">损耗机制</label>
          <div className="grid grid-cols-3 gap-2">
            <label className="flex items-center gap-2 text-xs text-dark-300 cursor-pointer">
              <input
                type="checkbox"
                checked={params.includeRadiative}
                onChange={(e) => setParams({ includeRadiative: e.target.checked })}
                disabled={calculationState.status === 'running'}
                className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-primary-500 focus:ring-primary-500"
              />
              辐射复合
            </label>
            <label className="flex items-center gap-2 text-xs text-dark-300 cursor-pointer">
              <input
                type="checkbox"
                checked={params.includeAuger}
                onChange={(e) => setParams({ includeAuger: e.target.checked })}
                disabled={calculationState.status === 'running'}
                className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-primary-500 focus:ring-primary-500"
              />
              俄歇复合
            </label>
            <label className="flex items-center gap-2 text-xs text-dark-300 cursor-pointer">
              <input
                type="checkbox"
                checked={params.includeSeriesResistance}
                onChange={(e) => setParams({ includeSeriesResistance: e.target.checked })}
                disabled={calculationState.status === 'running'}
                className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-primary-500 focus:ring-primary-500"
              />
              串联电阻
            </label>
          </div>
          <label className="flex items-center gap-2 text-xs text-dark-300 cursor-pointer">
            <input
              type="checkbox"
              checked={params.optimizeEmitter}
              onChange={(e) => setParams({ optimizeEmitter: e.target.checked })}
              disabled={calculationState.status === 'running'}
              className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-accent-500 focus:ring-accent-500"
            />
            优化选择性发射极结构
          </label>
        </div>

        <div className="space-y-3 border-t border-dark-700/50 pt-4">
          <label className="text-sm text-dark-200 flex items-center gap-2">
            <Zap className="w-4 h-4 text-accent-400" />
            发射极电阻模型
          </label>
          
          <label className="flex items-center gap-2 text-xs text-dark-300 cursor-pointer">
            <input
              type="checkbox"
              checked={params.useDistributedResistance}
              onChange={(e) => setParams({ useDistributedResistance: e.target.checked })}
              disabled={calculationState.status === 'running'}
              className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-accent-500 focus:ring-accent-500"
            />
            启用分布电阻模型 (TLM)
          </label>
          
          {params.useDistributedResistance && (
            <div className="space-y-3 pl-6 animate-fade-in">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-dark-400">薄层电阻 (Ω/□)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={params.emitterSheetResistance}
                    onChange={(e) => setParams({ emitterSheetResistance: Number(e.target.value) })}
                    disabled={calculationState.status === 'running'}
                    min="0"
                    className="input-field text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-dark-400">指间距 (μm)</label>
                  <input
                    type="number"
                    step="10"
                    value={params.fingerSpacing}
                    onChange={(e) => setParams({ fingerSpacing: Number(e.target.value) })}
                    disabled={calculationState.status === 'running'}
                    min="10"
                    className="input-field text-sm"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-dark-400">指宽 (μm)</label>
                <input
                  type="number"
                  step="1"
                  value={params.fingerWidth}
                  onChange={(e) => setParams({ fingerWidth: Number(e.target.value) })}
                  disabled={calculationState.status === 'running'}
                  min="1"
                  className="input-field text-sm"
                />
              </div>
              <p className="text-xs text-dark-500">
                传输线模型 (TLM) 考虑发射极横向电流分布，适用于 Jsc &gt; 1A/cm² 的情况
              </p>
            </div>
          )}
        </div>

        <div className="space-y-3 border-t border-dark-700/50 pt-4">
          <label className="text-sm text-dark-200 flex items-center gap-2">
            <Sun className="w-4 h-4 text-yellow-400" />
            聚光条件
          </label>
          
          <label className="flex items-center gap-2 text-xs text-dark-300 cursor-pointer">
            <input
              type="checkbox"
              checked={params.includeConcentration}
              onChange={(e) => setParams({ includeConcentration: e.target.checked })}
              disabled={calculationState.status === 'running'}
              className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-yellow-500 focus:ring-yellow-500"
            />
            启用聚光条件分析
          </label>
          
          {params.includeConcentration && (
            <div className="space-y-3 pl-6 animate-fade-in">
              <div className="space-y-1">
                <label className="text-xs text-dark-400">
                  聚光比: <span className="text-yellow-400 font-mono">{params.concentrationRatio}×</span>
                </label>
                <input
                  type="range"
                  min="1"
                  max="1000"
                  step="1"
                  value={params.concentrationRatio}
                  onChange={(e) => setParams({ concentrationRatio: Number(e.target.value) })}
                  disabled={calculationState.status === 'running'}
                  className="w-full h-2 bg-dark-700 rounded-lg appearance-none cursor-pointer accent-yellow-500"
                />
                <div className="flex justify-between text-xs text-dark-600">
                  <span>1×</span>
                  <span>100×</span>
                  <span>500×</span>
                  <span>1000×</span>
                </div>
              </div>
              <p className="text-xs text-dark-500">
                高光强下 Jsc 线性增加，Voc 对数增加，串联电阻损失增大
              </p>
            </div>
          )}
        </div>

        <div className="space-y-3 border-t border-dark-700/50 pt-4">
          <label className="text-sm text-dark-200 flex items-center gap-2">
            <Thermometer className="w-4 h-4 text-red-400" />
            热电耦合废热回收
          </label>
          
          <label className="flex items-center gap-2 text-xs text-dark-300 cursor-pointer">
            <input
              type="checkbox"
              checked={params.includeWasteHeatRecovery}
              onChange={(e) => setParams({ includeWasteHeatRecovery: e.target.checked })}
              disabled={calculationState.status === 'running'}
              className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-red-500 focus:ring-red-500"
            />
            启用热电耦合分析
          </label>
          
          {params.includeWasteHeatRecovery && (
            <div className="space-y-3 pl-6 animate-fade-in">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-dark-400">TEG 优值系数 ZT</label>
                  <input
                    type="number"
                    step="0.1"
                    value={params.tegFigureOfMerit}
                    onChange={(e) => setParams({ tegFigureOfMerit: Number(e.target.value) })}
                    disabled={calculationState.status === 'running'}
                    min="0.1"
                    max="5"
                    className="input-field text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-dark-400">冷端温度 (K)</label>
                  <input
                    type="number"
                    step="1"
                    value={params.tegColdSideTemperature}
                    onChange={(e) => setParams({ tegColdSideTemperature: Number(e.target.value) })}
                    disabled={calculationState.status === 'running'}
                    min="200"
                    max="400"
                    className="input-field text-sm"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-dark-400">
                  自定义 TEG 效率 (%): <span className="text-dark-500">（留空则由ZT计算）</span>
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={params.tegEfficiency}
                  onChange={(e) => setParams({ tegEfficiency: Number(e.target.value) })}
                  disabled={calculationState.status === 'running'}
                  min="0"
                  max="30"
                  className="input-field text-sm"
                />
              </div>
              <p className="text-xs text-dark-500">
                利用 Seebeck 效应将电池废热转化为额外电能，提高系统总效率
              </p>
            </div>
          )}
        </div>

        <div className="space-y-3 border-t border-dark-700/50 pt-4">
          <label className="text-sm text-dark-200 flex items-center gap-2">
            <Clock className="w-4 h-4 text-purple-400" />
            寿命预测
          </label>
          
          <label className="flex items-center gap-2 text-xs text-dark-300 cursor-pointer">
            <input
              type="checkbox"
              checked={params.includeLifetimePrediction}
              onChange={(e) => setParams({ includeLifetimePrediction: e.target.checked })}
              disabled={calculationState.status === 'running'}
              className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-purple-500 focus:ring-purple-500"
            />
            启用电池寿命预测
          </label>
          
          {params.includeLifetimePrediction && (
            <div className="space-y-3 pl-6 animate-fade-in">
              <div className="space-y-1">
                <label className="text-xs text-dark-400">
                  参考寿命 (小时): <span className="text-purple-400 font-mono">
                    {params.referenceLifetime.toLocaleString()} h
                  </span>
                </label>
                <input
                  type="range"
                  min="10000"
                  max="500000"
                  step="10000"
                  value={params.referenceLifetime}
                  onChange={(e) => setParams({ referenceLifetime: Number(e.target.value) })}
                  disabled={calculationState.status === 'running'}
                  className="w-full h-2 bg-dark-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-dark-400">
                  退化激活能 Ea (eV): <span className="text-purple-400 font-mono">
                    {params.activationEnergy.toFixed(2)} eV
                  </span>
                </label>
                <input
                  type="range"
                  min="0.5"
                  max="2.0"
                  step="0.05"
                  value={params.activationEnergy}
                  onChange={(e) => setParams({ activationEnergy: Number(e.target.value) })}
                  disabled={calculationState.status === 'running'}
                  className="w-full h-2 bg-dark-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
                />
                <div className="flex justify-between text-xs text-dark-600">
                  <span>0.5 eV</span>
                  <span>1.0 eV</span>
                  <span>1.5 eV</span>
                  <span>2.0 eV</span>
                </div>
              </div>
              <p className="text-xs text-dark-500">
                基于 Arrhenius 加速退化模型，温度每升高10°C寿命约减半
              </p>
            </div>
          )}
        </div>
      </div>

      {calculationState.status === 'running' && (
        <div className="space-y-2 animate-fade-in">
          <div className="flex justify-between text-xs">
            <span className="text-dark-300">{calculationState.currentStep}</span>
            <span className="text-primary-400 font-mono">{(calculationState.progress * 100).toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-primary-500 to-accent-500 rounded-full transition-all duration-300 animate-pulse-glow"
              style={{ width: `${calculationState.progress * 100}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex gap-3">
        {calculationState.status !== 'running' ? (
          <button
            onClick={onStart}
            className="btn-primary flex-1 flex items-center justify-center gap-2"
          >
            <Play className="w-4 h-4" />
            开始计算
          </button>
        ) : (
          <button
            onClick={onCancel}
            className="btn-secondary flex-1 flex items-center justify-center gap-2 text-red-400 border-red-500/30 hover:border-red-500"
          >
            <Square className="w-4 h-4" />
            中止计算
          </button>
        )}
      </div>
    </div>
  );
}
