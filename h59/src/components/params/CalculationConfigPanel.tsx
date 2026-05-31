import React from 'react';
import { Calculator, Target } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';
import { CollapsiblePanel } from '../common/CollapsiblePanel';
import { NumberInput } from '../common/NumberInput';
import type { CalculationMethod, OptimizationMethod } from '../../types';

const methodLabels: Record<CalculationMethod, string> = {
  cosine: '余弦定律',
  monte_carlo: '蒙特卡洛',
};

const optMethodLabels: Record<OptimizationMethod, string> = {
  genetic: '遗传算法',
  gradient_descent: '梯度下降',
};

export const CalculationConfigPanel: React.FC = () => {
  const {
    calculationConfig,
    optimizationConfig,
    setCalculationConfig,
    setOptimizationConfig,
  } = useAppStore();

  return (
    <>
      <CollapsiblePanel title="计算方法" icon={<Calculator className="w-4 h-4" />}>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 mb-1 block">计算方法</label>
            <div className="flex gap-1">
              {(Object.keys(methodLabels) as CalculationMethod[]).map((method) => (
                <button
                  key={method}
                  onClick={() => setCalculationConfig({ method })}
                  className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors ${
                    calculationConfig.method === method
                      ? 'bg-cyan-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                  }`}
                >
                  {methodLabels[method]}
                </button>
              ))}
            </div>
          </div>

          {calculationConfig.method === 'monte_carlo' && (
            <NumberInput
              label="模拟粒子数"
              value={calculationConfig.monteCarloParticles || 100000}
              onChange={(v) => setCalculationConfig({ monteCarloParticles: Math.round(v) })}
              step={10000}
              min={10000}
              max={1000000}
            />
          )}

          {calculationConfig.method === 'cosine' && (
            <NumberInput
              label="积分点数"
              value={calculationConfig.integrationPoints || 100}
              onChange={(v) => setCalculationConfig({ integrationPoints: Math.round(v) })}
              step={10}
              min={10}
              max={500}
            />
          )}
        </div>
      </CollapsiblePanel>

      <CollapsiblePanel
        title="源位置优化"
        icon={<Target className="w-4 h-4" />}
        defaultOpen={false}
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-300">启用优化</span>
            <button
              onClick={() => setOptimizationConfig({ enabled: !optimizationConfig.enabled })}
              className={`w-12 h-6 rounded-full transition-colors ${
                optimizationConfig.enabled ? 'bg-cyan-500' : 'bg-slate-600'
              }`}
            >
              <div
                className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                  optimizationConfig.enabled ? 'translate-x-6' : 'translate-x-0.5'
                }`}
              />
            </button>
          </div>

          {optimizationConfig.enabled && (
            <>
              <div>
                <label className="text-xs text-slate-400 mb-1 block">优化算法</label>
                <div className="flex gap-1">
                  {(Object.keys(optMethodLabels) as OptimizationMethod[]).map((method) => (
                    <button
                      key={method}
                      onClick={() => setOptimizationConfig({ method })}
                      className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors ${
                        optimizationConfig.method === method
                          ? 'bg-cyan-600 text-white'
                          : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                      }`}
                    >
                      {optMethodLabels[method]}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <NumberInput
                  label="目标均匀性"
                  value={optimizationConfig.targetUniformity}
                  onChange={(v) => setOptimizationConfig({ targetUniformity: v })}
                  step={0.1}
                  min={50}
                  max={99.9}
                  unit="%"
                />
                <NumberInput
                  label="最大迭代"
                  value={optimizationConfig.maxIterations}
                  onChange={(v) =>
                    setOptimizationConfig({ maxIterations: Math.round(v) })
                  }
                  step={1}
                  min={5}
                  max={200}
                />
              </div>

              {optimizationConfig.method === 'genetic' && (
                <>
                  <NumberInput
                    label="种群大小"
                    value={optimizationConfig.populationSize || 20}
                    onChange={(v) =>
                      setOptimizationConfig({ populationSize: Math.round(v) })
                    }
                    step={1}
                    min={10}
                    max={100}
                  />

                  <div className="pt-2 border-t border-slate-700">
                    <div className="text-xs text-slate-400 mb-2 font-medium">
                      早熟收敛保护
                    </div>

                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-300">自适应变异率</span>
                        <button
                          onClick={() =>
                            setOptimizationConfig({
                              geneticConfig: {
                                ...optimizationConfig.geneticConfig,
                                adaptiveMutation:
                                  !optimizationConfig.geneticConfig
                                    .adaptiveMutation,
                              },
                            })
                          }
                          className={`w-10 h-5 rounded-full transition-colors ${
                            optimizationConfig.geneticConfig.adaptiveMutation
                              ? 'bg-cyan-500'
                              : 'bg-slate-600'
                          }`}
                        >
                          <div
                            className={`w-4 h-4 bg-white rounded-full shadow transition-transform ${
                              optimizationConfig.geneticConfig.adaptiveMutation
                                ? 'translate-x-5'
                                : 'translate-x-0.5'
                            }`}
                          />
                        </button>
                      </div>

                      {optimizationConfig.geneticConfig.adaptiveMutation && (
                        <div className="grid grid-cols-2 gap-2">
                          <NumberInput
                            label="最小变异率"
                            value={
                              optimizationConfig.geneticConfig.mutationRateMin
                            }
                            onChange={(v) =>
                              setOptimizationConfig({
                                geneticConfig: {
                                  ...optimizationConfig.geneticConfig,
                                  mutationRateMin: Math.max(
                                    0.01,
                                    Math.min(v, 0.5)
                                  ),
                                },
                              })
                            }
                            step={0.01}
                            min={0.01}
                            max={0.5}
                          />
                          <NumberInput
                            label="最大变异率"
                            value={
                              optimizationConfig.geneticConfig.mutationRateMax
                            }
                            onChange={(v) =>
                              setOptimizationConfig({
                                geneticConfig: {
                                  ...optimizationConfig.geneticConfig,
                                  mutationRateMax: Math.max(
                                    0.01,
                                    Math.min(v, 0.8)
                                  ),
                                },
                              })
                            }
                            step={0.01}
                            min={0.01}
                            max={0.8}
                          />
                        </div>
                      )}

                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-300">
                          拥挤度选择
                        </span>
                        <button
                          onClick={() =>
                            setOptimizationConfig({
                              geneticConfig: {
                                ...optimizationConfig.geneticConfig,
                                crowdingEnabled:
                                  !optimizationConfig.geneticConfig
                                    .crowdingEnabled,
                              },
                            })
                          }
                          className={`w-10 h-5 rounded-full transition-colors ${
                            optimizationConfig.geneticConfig.crowdingEnabled
                              ? 'bg-cyan-500'
                              : 'bg-slate-600'
                          }`}
                        >
                          <div
                            className={`w-4 h-4 bg-white rounded-full shadow transition-transform ${
                              optimizationConfig.geneticConfig.crowdingEnabled
                                ? 'translate-x-5'
                                : 'translate-x-0.5'
                            }`}
                          />
                        </button>
                      </div>

                      {optimizationConfig.geneticConfig.crowdingEnabled && (
                        <NumberInput
                          label="拥挤因子"
                          value={
                            optimizationConfig.geneticConfig.crowdingFactor
                          }
                          onChange={(v) =>
                            setOptimizationConfig({
                              geneticConfig: {
                                ...optimizationConfig.geneticConfig,
                                crowdingFactor: Math.max(0.1, Math.min(v, 1)),
                              },
                            })
                          }
                          step={0.05}
                          min={0.1}
                          max={1}
                        />
                      )}

                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-300">
                          灾变机制
                        </span>
                        <button
                          onClick={() =>
                            setOptimizationConfig({
                              geneticConfig: {
                                ...optimizationConfig.geneticConfig,
                                catastropheEnabled:
                                  !optimizationConfig.geneticConfig
                                    .catastropheEnabled,
                              },
                            })
                          }
                          className={`w-10 h-5 rounded-full transition-colors ${
                            optimizationConfig.geneticConfig.catastropheEnabled
                              ? 'bg-cyan-500'
                              : 'bg-slate-600'
                          }`}
                        >
                          <div
                            className={`w-4 h-4 bg-white rounded-full shadow transition-transform ${
                              optimizationConfig.geneticConfig.catastropheEnabled
                                ? 'translate-x-5'
                                : 'translate-x-0.5'
                            }`}
                          />
                        </button>
                      </div>

                      {optimizationConfig.geneticConfig.catastropheEnabled && (
                        <div className="grid grid-cols-2 gap-2">
                          <NumberInput
                            label="灾变阈值(代)"
                            value={
                              optimizationConfig.geneticConfig
                                .catastropheThreshold
                            }
                            onChange={(v) =>
                              setOptimizationConfig({
                                geneticConfig: {
                                  ...optimizationConfig.geneticConfig,
                                  catastropheThreshold: Math.max(
                                    5,
                                    Math.round(v)
                                  ),
                                },
                              })
                            }
                            step={1}
                            min={5}
                            max={100}
                          />
                          <NumberInput
                            label="灾变数量"
                            value={
                              optimizationConfig.geneticConfig.catastropheCount
                            }
                            onChange={(v) =>
                              setOptimizationConfig({
                                geneticConfig: {
                                  ...optimizationConfig.geneticConfig,
                                  catastropheCount: Math.max(
                                    2,
                                    Math.round(v)
                                  ),
                                },
                              })
                            }
                            step={1}
                            min={2}
                            max={50}
                          />
                        </div>
                      )}

                      <NumberInput
                        label="多样性阈值"
                        value={
                          optimizationConfig.geneticConfig.diversityThreshold
                        }
                        onChange={(v) =>
                          setOptimizationConfig({
                            geneticConfig: {
                              ...optimizationConfig.geneticConfig,
                              diversityThreshold: Math.max(1, v),
                            },
                          })
                        }
                        step={1}
                        min={1}
                        max={200}
                        unit="mm"
                      />
                    </div>
                  </div>
                </>
              )}

              <div>
                <label className="text-xs text-slate-400 mb-2 block">优化变量范围</label>
                <div className="grid grid-cols-3 gap-2">
                  <NumberInput
                    label="X 最小"
                    value={optimizationConfig.bounds.min.x}
                    onChange={(v) =>
                      setOptimizationConfig({
                        bounds: {
                          ...optimizationConfig.bounds,
                          min: { ...optimizationConfig.bounds.min, x: v },
                        },
                      })
                    }
                    step={10}
                    unit="mm"
                  />
                  <NumberInput
                    label="Y 最小"
                    value={optimizationConfig.bounds.min.y}
                    onChange={(v) =>
                      setOptimizationConfig({
                        bounds: {
                          ...optimizationConfig.bounds,
                          min: { ...optimizationConfig.bounds.min, y: v },
                        },
                      })
                    }
                    step={10}
                    unit="mm"
                  />
                  <NumberInput
                    label="Z 最小"
                    value={optimizationConfig.bounds.min.z}
                    onChange={(v) =>
                      setOptimizationConfig({
                        bounds: {
                          ...optimizationConfig.bounds,
                          min: { ...optimizationConfig.bounds.min, z: v },
                        },
                      })
                    }
                    step={10}
                    unit="mm"
                  />
                </div>
                <div className="grid grid-cols-3 gap-2 mt-2">
                  <NumberInput
                    label="X 最大"
                    value={optimizationConfig.bounds.max.x}
                    onChange={(v) =>
                      setOptimizationConfig({
                        bounds: {
                          ...optimizationConfig.bounds,
                          max: { ...optimizationConfig.bounds.max, x: v },
                        },
                      })
                    }
                    step={10}
                    unit="mm"
                  />
                  <NumberInput
                    label="Y 最大"
                    value={optimizationConfig.bounds.max.y}
                    onChange={(v) =>
                      setOptimizationConfig({
                        bounds: {
                          ...optimizationConfig.bounds,
                          max: { ...optimizationConfig.bounds.max, y: v },
                        },
                      })
                    }
                    step={10}
                    unit="mm"
                  />
                  <NumberInput
                    label="Z 最大"
                    value={optimizationConfig.bounds.max.z}
                    onChange={(v) =>
                      setOptimizationConfig({
                        bounds: {
                          ...optimizationConfig.bounds,
                          max: { ...optimizationConfig.bounds.max, z: v },
                        },
                      })
                    }
                    step={10}
                    unit="mm"
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </CollapsiblePanel>
    </>
  );
};
